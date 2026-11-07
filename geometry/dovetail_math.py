"""
Geometria Analítica do Dovetail, Fillets Circulares C1 e Offset Paralelo Normal (LF04, LF05).
Papel do Módulo: Construir analiticamente os perfis de corte com arcos exatos de centro invariante Ci
e deslocamento perpendicular uniforme ±δ (RN02, RN03, RN04, RN05).
"""

from dataclasses import dataclass
import math
from typing import List, Optional, Tuple
from config.settings import LIMITS
from models.cut_line import CutLine, Point2D
from models.dovetail_params import DovetailParams


@dataclass
class FilletArc2D:
    """
    Representa um arco circular tangente C1 analítico (LF04, LF05).
    Contém os pontos inicial (t1), intermediário (p_mid) e final (t2) para threePointArc,
    além do centro invariante (center) e raio efetivo (r_eff = R - τ*δ).
    """

    center: Point2D
    t1: Point2D
    p_mid: Point2D
    t2: Point2D
    r_eff: float
    tau: float
    angle_start: float
    angle_end: float

    def sample_points(self, num_subsegments: int = LIMITS.SUBSEGMENTOS_ARCO_FALLBACK) -> List[Point2D]:
        """Discretiza o arco em sub-segmentos (LF05 Fallback Poligonal e Renderização Canvas)."""
        pts: List[Point2D] = []
        n = max(2, num_subsegments)
        cx, cy = self.center
        for idx in range(n + 1):
            frac = idx / float(n)
            ang = self.angle_start + frac * (self.angle_end - self.angle_start)
            pts.append((cx + self.r_eff * math.cos(ang), cy + self.r_eff * math.sin(ang)))
        return pts


@dataclass
class OffsetCurveData:
    """
    Estrutura completa gerada por construir_curva_offset (LF04, LF05).
    Armazena tanto as primitivas analíticas (retas + arcos de 3 pontos) quanto a polilinha densa.
    """

    delta_offset: float
    start_point: Point2D
    end_point: Point2D
    arcs: List[FilletArc2D]
    polyline_points: List[Point2D]
    sharp_vertices: List[Point2D]


def build_sharp_vertices_sn(
    teeth_s: List[float],
    s_start: float,
    s_end: float,
    params: DovetailParams,
) -> List[Point2D]:
    """
    LF04 (Etapas 1 e 2): Gera os vértices agudos do perfil dovetail no espaço local (s, n).
    """
    sorted_s = sorted(teeth_s)
    w_neck = params.neck_width_mm
    w_head = params.head_width_mm
    h_signed = params.height_mm * params.normal_direction_sign

    # Garante que s_start e s_end englobem todos os dentes com folga longitudinal
    if sorted_s:
        s_start = min(s_start, sorted_s[0] - w_head - 5.0)
        s_end = max(s_end, sorted_s[-1] + w_head + 5.0)

    verts: List[Point2D] = [(s_start, 0.0)]
    for sk in sorted_s:
        v1 = (sk - w_neck * 0.5, 0.0)
        v2 = (sk - w_head * 0.5, h_signed)
        v3 = (sk + w_head * 0.5, h_signed)
        v4 = (sk + w_neck * 0.5, 0.0)
        verts.extend([v1, v2, v3, v4])
    verts.append((s_end, 0.0))
    return verts


def construir_curva_offset(
    teeth_s: List[float],
    s_start: float,
    s_end: float,
    params: DovetailParams,
    delta_offset: float = 0.0,
    cut_line: Optional[CutLine] = None,
    subsegments_per_arc: int = LIMITS.SUBSEGMENTOS_ARCO_FALLBACK,
) -> OffsetCurveData:
    """
    LF04 — Geometria Analítica do Dovetail, Fillets Tangentes C1 e Offset Normal ±δ.
    Quando cut_line é fornecida, transforma os pontos analiticamente para o espaço global (X, Y);
    caso contrário, retorna no espaço local (s, n).
    """
    sharp_sn = build_sharp_vertices_sn(teeth_s, s_start, s_end, params)

    def transform_pt(pt_sn: Point2D) -> Point2D:
        if cut_line is None:
            return pt_sn
        return cut_line.to_global(pt_sn[0], pt_sn[1])

    sharp_transformed = [transform_pt(p) for p in sharp_sn]
    num_verts = len(sharp_transformed)

    # Caso sem dentes: apenas uma reta deslocada por delta_offset na normal à esquerda
    if num_verts <= 2:
        p0, p1 = sharp_transformed[0], sharp_transformed[-1]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        p0_off = (p0[0] + delta_offset * nx, p0[1] + delta_offset * ny)
        p1_off = (p1[0] + delta_offset * nx, p1[1] + delta_offset * ny)
        return OffsetCurveData(
            delta_offset=delta_offset,
            start_point=p0_off,
            end_point=p1_off,
            arcs=[],
            polyline_points=[p0_off, p1_off],
            sharp_vertices=sharp_transformed,
        )

    # Primeiro ponto e último ponto deslocados perpendicularmente ao primeiro/último segmento
    v_first_dx = sharp_transformed[1][0] - sharp_transformed[0][0]
    v_first_dy = sharp_transformed[1][1] - sharp_transformed[0][1]
    l_first = math.hypot(v_first_dx, v_first_dy) or 1.0
    n_first = (-v_first_dy / l_first, v_first_dx / l_first)
    start_off = (
        sharp_transformed[0][0] + delta_offset * n_first[0],
        sharp_transformed[0][1] + delta_offset * n_first[1],
    )

    v_last_dx = sharp_transformed[-1][0] - sharp_transformed[-2][0]
    v_last_dy = sharp_transformed[-1][1] - sharp_transformed[-2][1]
    l_last = math.hypot(v_last_dx, v_last_dy) or 1.0
    n_last = (-v_last_dy / l_last, v_last_dx / l_last)
    end_off = (
        sharp_transformed[-1][0] + delta_offset * n_last[0],
        sharp_transformed[-1][1] + delta_offset * n_last[1],
    )

    arcs: List[FilletArc2D] = []
    polyline: List[Point2D] = [start_off]
    r_target = params.effective_fillet_radius_mm

    for i in range(1, num_verts - 1):
        p_prev = sharp_transformed[i - 1]
        p_curr = sharp_transformed[i]
        p_next = sharp_transformed[i + 1]

        v1x, v1y = p_curr[0] - p_prev[0], p_curr[1] - p_prev[1]
        v2x, v2y = p_next[0] - p_curr[0], p_next[1] - p_curr[1]
        l1 = math.hypot(v1x, v1y)
        l2 = math.hypot(v2x, v2y)
        if l1 < 1e-6 or l2 < 1e-6:
            continue

        u1 = (v1x / l1, v1y / l1)
        u2 = (v2x / l2, v2y / l2)

        # Normais unitárias à esquerda: n = (-uy, ux)
        n1 = (-u1[1], u1[0])
        n2 = (-u2[1], u2[0])

        # Produto vetorial 2D u1 x u2 para determinar sentido de curva τ ∈ {-1, +1}
        cross = u1[0] * u2[1] - u1[1] * u2[0]
        if abs(cross) < 1e-6:
            continue
        tau = 1.0 if cross > 0.0 else -1.0

        # Ângulo interno γ = arccos(-u1 · u2)
        dot_neg = max(-0.999999, min(0.999999, -(u1[0] * u2[0] + u1[1] * u2[1])))
        gamma = math.acos(dot_neg)
        half_gamma_tan = math.tan(gamma * 0.5)

        # RN04: Limitação dinâmica do raio em cada vértice
        r_max_local = LIMITS.FATOR_SEGURANCA_FILLET * min(l1, l2) * half_gamma_tan
        r_base = min(r_target, r_max_local)

        # Distância de recuo dos pontos de tangência: d_tan = R / tan(γ/2)
        d_tan = r_base / max(1e-6, half_gamma_tan)

        # Pontos de tangência na linha central
        t1_center = (p_curr[0] - d_tan * u1[0], p_curr[1] - d_tan * u1[1])
        t2_center = (p_curr[0] + d_tan * u2[0], p_curr[1] + d_tan * u2[1])

        # Centro invariante do arco de fillet: Ci = T1 + τ * R * n1 (LF04)
        ci = (
            t1_center[0] + tau * r_base * n1[0],
            t1_center[1] + tau * r_base * n1[1],
        )

        # Novos pontos de tangência com offset normal δ: T(δ) = T + δ * n
        t1_off = (t1_center[0] + delta_offset * n1[0], t1_center[1] + delta_offset * n1[1])
        t2_off = (t2_center[0] + delta_offset * n2[0], t2_center[1] + delta_offset * n2[1])

        # Raio efetivo ajustado analiticamente: R_eff = R - τ * δ
        r_eff = max(0.02, r_base - tau * delta_offset)

        # Ângulos polares a partir de Ci para T1_off e T2_off
        ang1 = math.atan2(t1_off[1] - ci[1], t1_off[0] - ci[0])
        ang2 = math.atan2(t2_off[1] - ci[1], t2_off[0] - ci[0])

        # Ajuste da varredura angular conforme o sentido de curva τ
        d_ang = ang2 - ang1
        while d_ang <= -math.pi:
            d_ang += 2.0 * math.pi
        while d_ang > math.pi:
            d_ang -= 2.0 * math.pi
        if tau > 0 and d_ang < 0:
            d_ang += 2.0 * math.pi
        elif tau < 0 and d_ang > 0:
            d_ang -= 2.0 * math.pi

        ang_end = ang1 + d_ang
        ang_mid = ang1 + 0.5 * d_ang
        p_mid = (ci[0] + r_eff * math.cos(ang_mid), ci[1] + r_eff * math.sin(ang_mid))

        arc = FilletArc2D(
            center=ci,
            t1=t1_off,
            p_mid=p_mid,
            t2=t2_off,
            r_eff=r_eff,
            tau=tau,
            angle_start=ang1,
            angle_end=ang_end,
        )
        arcs.append(arc)
        polyline.extend(arc.sample_points(subsegments_per_arc))

    polyline.append(end_off)

    return OffsetCurveData(
        delta_offset=delta_offset,
        start_point=start_off,
        end_point=end_off,
        arcs=arcs,
        polyline_points=polyline,
        sharp_vertices=sharp_transformed,
    )

