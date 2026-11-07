"""
Detecção de Trechos Maciços e Distribuição Simétrica de Dentes (RN01, RN03, LF02, LF03).
Papel do Módulo: Avaliar a integridade estrutural ao longo da costura (dente_cabe) e posicionar
dentes centralizados desviando automaticamente de furos e bordas (escolher_dentes).
"""

import math
from typing import List, Tuple
from config.settings import LIMITS
from geometry.coordinate_system import compute_scan_bounds_sn, point_in_polygon, point_to_segment_distance
from models.cut_line import CutLine, Point2D
from models.dovetail_params import DovetailParams
from models.part_model import HoleFeature, PartModel, Polygon2D
from models.validation_report import ToothCandidateInfo


def build_tooth_envelope_global(
    s_c: float,
    cut_line: CutLine,
    params: DovetailParams,
) -> Polygon2D:
    """
    LF02: Constrói os 4 cantos do prisma retangular de verificação ao redor do dente centrado em s_c,
    acrescido das margens obrigatórias MARGEM_BORDA (RN01) e MARGEM_PAREDE (RN01).
    """
    half_s = params.safety_half_span_s_mm  # W_head/2 + MARGEM_BORDA
    s0 = s_c - half_s
    s1 = s_c + half_s

    sign = params.normal_direction_sign
    if sign >= 0:
        n0 = -params.margin_wall_mm
        n1 = params.height_mm + params.margin_wall_mm
    else:
        n0 = -(params.height_mm + params.margin_wall_mm)
        n1 = params.margin_wall_mm

    return [
        cut_line.to_global(s0, n0),
        cut_line.to_global(s1, n0),
        cut_line.to_global(s1, n1),
        cut_line.to_global(s0, n1),
    ]


def _point_inside_any_outer(pt: Point2D, part: PartModel) -> bool:
    for poly in part.all_outer_polygons:
        if point_in_polygon(pt, poly):
            return True
    return False


def _point_inside_hole(pt: Point2D, hole: HoleFeature) -> bool:
    dx = pt[0] - hole.center[0]
    dy = pt[1] - hole.center[1]
    if math.hypot(dx, dy) <= hole.radius_mm:
        return True
    if hole.polygon and len(hole.polygon) >= 3 and point_in_polygon(pt, hole.polygon):
        return True
    return False


def dente_cabe(
    s_c: float,
    part: PartModel,
    cut_line: CutLine,
    params: DovetailParams,
    use_3d_kernel: bool = False,
) -> Tuple[bool, str, Polygon2D]:
    """
    LF02 — Algoritmo de Detecção de Trechos Maciços (dente_cabe).
    Retorna (aprovado, motivo, poligono_envelope_global).
    Motivos possíveis: "OK", "FURO_DESVIADO", "MARGEM_BORDA", "FORA_DA_PECA".
    """
    envelope = build_tooth_envelope_global(s_c, cut_line, params)
    center_pt = cut_line.to_global(s_c, 0.0)

    # 1. Verifica se o centro na linha de corte está dentro da silhueta da peça ou de um furo
    in_outer = _point_inside_any_outer(center_pt, part)
    for hole in part.holes:
        if _point_inside_hole(center_pt, hole):
            return (False, "FURO_DESVIADO", envelope)

    if not in_outer:
        return (False, "FORA_DA_PECA", envelope)

    # 2. Amostragem densa do envelope retangular [s_c - half_s, s_c + half_s] x [n0, n1]
    half_s = params.safety_half_span_s_mm
    sign = params.normal_direction_sign
    n_min = -params.margin_wall_mm if sign >= 0 else -(params.height_mm + params.margin_wall_mm)
    n_max = (params.height_mm + params.margin_wall_mm) if sign >= 0 else params.margin_wall_mm

    # Grade 5x4 de pontos de verificação dentro do envelope do prisma de teste
    s_samples = [s_c + frac * half_s for frac in (-1.0, -0.5, 0.0, 0.5, 1.0)]
    n_samples = [n_min + frac * (n_max - n_min) for frac in (0.0, 0.33, 0.67, 1.0)]

    for ss in s_samples:
        for nn in n_samples:
            pt = cut_line.to_global(ss, nn)
            # Verifica invasão de furos (RN01)
            for hole in part.holes:
                if _point_inside_hole(pt, hole):
                    return (False, "FURO_DESVIADO", envelope)
            # Verifica se saiu da borda externa da peça (RN01)
            if not _point_inside_any_outer(pt, part):
                return (False, "MARGEM_BORDA", envelope)

    # Verifica também se o centro de algum furo pequeno cai dentro do envelope ou se arestas do envelope
    # tangenciam o raio de algum furo
    for hole in part.holes:
        if point_in_polygon(hole.center, envelope):
            return (False, "FURO_DESVIADO", envelope)
        for i in range(4):
            d_edge = point_to_segment_distance(hole.center, envelope[i], envelope[(i + 1) % 4])
            if d_edge <= hole.radius_mm:
                return (False, "FURO_DESVIADO", envelope)

    # 3. Se o kernel 3D B-Rep (CadQuery) foi solicitado e está disponível, executa validação volumétrica exata (LF02)
    if use_3d_kernel and part.cq_workplane is not None:
        try:
            import cadquery as cq  # type: ignore

            z0 = part.bbox.zmin + LIMITS.FATIA_Z_OFFSET_MIN_MM
            z1 = min(part.bbox.zmax - 0.1, part.bbox.zmin + LIMITS.FATIA_Z_OFFSET_MAX_MM)
            h_slice = max(0.5, z1 - z0)
            prism = (
                cq.Workplane("XY")
                .workplane(offset=z0)
                .polyline(envelope)
                .close()
                .extrude(h_slice)
            )
            prism_vol = prism.val().Volume()
            if prism_vol > 1e-6:
                inter = part.cq_workplane.intersect(prism)
                inter_vol = inter.val().Volume()
                if (inter_vol / prism_vol) < LIMITS.RAZAO_VOLUME_MACICO_MIN:
                    return (False, "FURO_DESVIADO", envelope)
        except Exception:
            pass

    return (True, "OK", envelope)


def escolher_dentes(
    part: PartModel,
    cut_line: CutLine,
    params: DovetailParams,
    use_3d_kernel: bool = False,
) -> Tuple[List[float], List[Tuple[float, float]], List[ToothCandidateInfo], List[ToothCandidateInfo]]:
    """
    LF03 — Agrupamento em Trechos Contínuos e Centralização Simétrica (escolher_dentes).
    1. Varre s de s_min até s_max com passo de 1,0 mm.
    2. Agrupa posições válidas adjacentes em intervalos contínuos [s_a, s_b].
    3. Em cada intervalo de comprimento L = s_b - s_a:
       N = 1 + floor(L / P)
       s_k = (s_a + s_b)/2 - ((N - 1) * P)/2 + k * P
    Retorna:
       (teeth_s, valid_intervals, active_teeth_info, avoided_holes_info)
    """
    s_min, s_max, _, _ = compute_scan_bounds_sn(part, cut_line)
    step = LIMITS.PASSO_VARREDURA_MM

    num_steps = max(1, int(math.ceil((s_max - s_min) / step)))
    valid_s_points: List[float] = []
    hole_blocked_s: List[float] = []

    for i in range(num_steps + 1):
        s_val = s_min + i * step
        ok, reason, _ = dente_cabe(s_val, part, cut_line, params, use_3d_kernel=False)
        if ok:
            valid_s_points.append(s_val)
        elif reason == "FURO_DESVIADO":
            hole_blocked_s.append(s_val)

    # Agrupa posições válidas adjacentes (tolerância de 1.5 * step) em intervalos contínuos [s_a, s_b]
    valid_intervals: List[Tuple[float, float]] = []
    if valid_s_points:
        curr_start = valid_s_points[0]
        curr_end = valid_s_points[0]
        for s_val in valid_s_points[1:]:
            if s_val - curr_end <= step * 1.5:
                curr_end = s_val
            else:
                valid_intervals.append((curr_start, curr_end))
                curr_start = s_val
                curr_end = s_val
        valid_intervals.append((curr_start, curr_end))

    # Calcula os dentes simetricamente centralizados em cada trecho [s_a, s_b] (LF03)
    pitch = params.pitch_mm
    teeth_s: List[float] = []
    active_teeth_info: List[ToothCandidateInfo] = []

    for s_a, s_b in valid_intervals:
        length = max(0.0, s_b - s_a)
        n_teeth = 1 + int(math.floor(length / pitch))
        s_mid = 0.5 * (s_a + s_b)
        for k in range(n_teeth):
            s_k = s_mid - 0.5 * (n_teeth - 1) * pitch + k * pitch
            ok, reason, env = dente_cabe(s_k, part, cut_line, params, use_3d_kernel=use_3d_kernel)
            if ok:
                teeth_s.append(s_k)
                active_teeth_info.append(
                    ToothCandidateInfo(
                        s_coord=s_k,
                        global_center=cut_line.to_global(s_k, 0.0),
                        envelope_polygon=env,
                        approved=True,
                        reason="OK",
                    )
                )

    # Agrupa também os trechos bloqueados por furo para exibir marcadores visuais de "Furo Desviado" (RN01)
    avoided_holes_info: List[ToothCandidateInfo] = []
    if hole_blocked_s:
        h_start = hole_blocked_s[0]
        h_end = hole_blocked_s[0]
        hole_intervals: List[Tuple[float, float]] = []
        for s_val in hole_blocked_s[1:]:
            if s_val - h_end <= step * 2.0:
                h_end = s_val
            else:
                hole_intervals.append((h_start, h_end))
                h_start = s_val
                h_end = s_val
        hole_intervals.append((h_start, h_end))

        for ha, hb in hole_intervals:
            s_h = 0.5 * (ha + hb)
            env_h = build_tooth_envelope_global(s_h, cut_line, params)
            avoided_holes_info.append(
                ToothCandidateInfo(
                    s_coord=s_h,
                    global_center=cut_line.to_global(s_h, 0.0),
                    envelope_polygon=env_h,
                    approved=False,
                    reason="FURO_DESVIADO",
                )
            )

    return (teeth_s, valid_intervals, active_teeth_info, avoided_holes_info)

