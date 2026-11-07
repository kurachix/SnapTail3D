"""
Motor de Corte Sólido 3D Híbrido: B-Rep Analítico + Fallback Poligonal (LF05, RN06, RN07, RN08).
Papel do Módulo: Executar o corte booleano 3D das Metades A e B preservando arcos cilíndricos exatos
(threePointArc) com fallback automático para polilinha de 14 sub-segmentos e alinhamento em Z=0.
"""

from dataclasses import dataclass, field
import math
from typing import Any, List, Optional, Tuple
from config.printer_profiles import PrinterProfile
from config.settings import LIMITS
from geometry.coordinate_system import compute_scan_bounds_sn, point_in_polygon, polygon_signed_area
from geometry.dovetail_math import OffsetCurveData, construir_curva_offset
from geometry.nesting_optimizer import evaluate_cut_solution
from models.cut_line import CutLine, Point2D
from models.dovetail_params import DovetailParams
from models.part_model import HoleFeature, PartModel, Polygon2D
from models.validation_report import CutValidationReport


@dataclass
class CutSolidHalf:
    """
    Representa uma metade 3D pronta para exportação (.STL e .STEP),
    já rotacionada pelo ângulo ótimo de Auto-Nesting (RN06) e apoiada em Z = 0, X >= 0, Y >= 0 (RN08).
    """

    label: str  # "A" ou "B"
    outer_contour_xy: Polygon2D
    holes_xy: List[Polygon2D]
    thickness_z_mm: float
    optimal_angle_deg: float
    num_solids: int = 1
    used_analytical_arcs: bool = True
    cq_solid: Optional[Any] = None
    extra_contours_xy: List[Polygon2D] = field(default_factory=list)


@dataclass
class CutExecutionResult:
    """Resultado completo do corte 3D contendo Metade A, Metade B e o relatório de validação."""

    half_a: CutSolidHalf
    half_b: CutSolidHalf
    report: CutValidationReport
    used_cadquery_kernel: bool


def _build_cutter_closure_points(
    curve: OffsetCurveData,
    cut_line: CutLine,
    s_start: float,
    s_end: float,
    n_far: float,
) -> List[Point2D]:
    """Fecha o loop do cortador pelo lado distante (n_far) do BoundingBox."""
    c1 = cut_line.to_global(s_end, n_far)
    c2 = cut_line.to_global(s_start, n_far)
    return [c1, c2]


def _build_cq_cutter_analytical_with_fallback(
    curve: OffsetCurveData,
    closure_pts: List[Point2D],
    z_min: float,
    z_max: float,
) -> Tuple[Any, bool]:
    """
    LF05 — Corte Sólido 3D Híbrido:
    1. Modo Primário (Analítico): lineTo + threePointArc(P_meio, T2_off)
    2. Modo Fallback (Poligonal): polyline com 14 sub-segmentos por arco se o kernel acusar erro.
    """
    import cadquery as cq  # type: ignore

    z_bottom = z_min - 5.0
    extrude_h = (z_max - z_min) + 10.0

    # Tentativa 1: Modo Primário Analítico (LF05.1)
    try:
        wp = cq.Workplane("XY").workplane(offset=z_bottom).moveTo(*curve.start_point)
        for arc in curve.arcs:
            wp = wp.lineTo(*arc.t1)
            wp = wp.threePointArc(arc.p_mid, arc.t2)
        wp = wp.lineTo(*curve.end_point)
        for cp in closure_pts:
            wp = wp.lineTo(*cp)
        solid = wp.close().extrude(extrude_h)
        return (solid, True)
    except Exception:
        # Tentativa 2: Modo Fallback Poligonal com 14 sub-segmentos por arco (LF05.2)
        all_pts = list(curve.polyline_points) + list(closure_pts)
        solid = (
            cq.Workplane("XY")
            .workplane(offset=z_bottom)
            .polyline(all_pts)
            .close()
            .extrude(extrude_h)
        )
        return (solid, False)


def _normalize_cq_solid_rn08(wp: Any, angle_deg: float) -> Tuple[Any, int]:
    """
    RN06, RN07, RN08:
    - Conta o número de sólidos desconectados (RN07)
    - Rotaciona pelo ângulo ótimo θ* no plano XY (RN06)
    - Translada para X >= 0, Y >= 0 e face inferior em Z = 0 (RN08).
    """
    num_solids = len(wp.solids().vals())
    if abs(angle_deg) > 1e-3:
        wp = wp.rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), angle_deg)
    bb = wp.val().BoundingBox()
    wp = wp.translate((-bb.xmin, -bb.ymin, -bb.zmin))
    return (wp, max(1, num_solids))


def _stitch_half_polygon_with_seam(
    outer_poly: Polygon2D,
    seam_points: List[Point2D],
    cut_line: CutLine,
    keep_positive_n: bool,
) -> Polygon2D:
    """
    Constrói o polígono fechado de uma metade combinando o contorno externo recortado
    com a polilinha exata dos dentes dovetail (incluindo fillets C1 e offset normal ±δ).
    """
    if len(outer_poly) < 3:
        return []

    # Encontra o intervalo s onde o polígono externo intercepta a linha de corte
    s_intersections: List[float] = []
    n_verts = len(outer_poly)
    for i in range(n_verts):
        p1 = outer_poly[i]
        p2 = outer_poly[(i + 1) % n_verts]
        s1, d1 = cut_line.to_local(p1[0], p1[1])
        s2, d2 = cut_line.to_local(p2[0], p2[1])
        if (d1 <= 0.0 <= d2) or (d2 <= 0.0 <= d1):
            denom = d1 - d2
            t = d1 / denom if abs(denom) > 1e-12 else 0.5
            s_inter = s1 + t * (s2 - s1)
            s_intersections.append(s_inter)

    if len(s_intersections) < 2:
        from geometry.nesting_optimizer import clip_polygon_halfplane

        return clip_polygon_halfplane(outer_poly, cut_line, keep_positive_n=keep_positive_n)

    s_low = min(s_intersections)
    s_high = max(s_intersections)

    # Filtra os pontos da curva de costura que estão dentro do corpo da peça [s_low, s_high]
    active_seam: List[Point2D] = [cut_line.to_global(s_low, 0.0)]
    for pt in seam_points:
        s_pt, _ = cut_line.to_local(pt[0], pt[1])
        if s_low + 0.05 < s_pt < s_high - 0.05:
            active_seam.append(pt)
    active_seam.append(cut_line.to_global(s_high, 0.0))

    # Coleta os vértices do contorno externo que pertencem a este semiplano
    # ordenados de forma a fechar o ciclo com active_seam
    from geometry.nesting_optimizer import clip_polygon_halfplane

    clipped = clip_polygon_halfplane(outer_poly, cut_line, keep_positive_n=keep_positive_n)
    if len(clipped) < 3:
        return clipped

    # Substitui o trecho reto de corte (d ≈ 0) pela curva dentada active_seam
    non_seam_pts: List[Point2D] = []
    for pt in clipped:
        _, d_pt = cut_line.to_local(pt[0], pt[1])
        if abs(d_pt) > 0.25:
            non_seam_pts.append(pt)

    if not non_seam_pts:
        return clipped

    # Verifica orientação para conectar sem cruzar arestas
    first_ext = non_seam_pts[0]
    last_ext = non_seam_pts[-1]
    s_first, _ = cut_line.to_local(first_ext[0], first_ext[1])
    s_last, _ = cut_line.to_local(last_ext[0], last_ext[1])

    if s_last > s_first:
        stitched = non_seam_pts + list(reversed(active_seam))
    else:
        stitched = non_seam_pts + active_seam

    if polygon_signed_area(stitched) < 0:
        stitched.reverse()
    return stitched


def _rotate_and_shift_contours_rn08(
    outer_poly: Polygon2D,
    holes: List[HoleFeature],
    angle_deg: float,
) -> Tuple[Polygon2D, List[Polygon2D]]:
    """
    Aplica a rotação ótima θ* (RN06) e translada o conjunto para o quadrante positivo
    X >= 0, Y >= 0 (RN08), filtrando os furos internos que pertencem a esta metade.
    """
    if not outer_poly:
        return ([], [])

    # Seleciona os furos cujos centros estão dentro desta metade
    valid_holes: List[Polygon2D] = []
    for h in holes:
        if point_in_polygon(h.center, outer_poly):
            valid_holes.append(h.polygon)

    rad = math.radians(angle_deg)
    ca = math.cos(rad)
    sa = math.sin(rad)

    rot_outer = [(x * ca - y * sa, x * sa + y * ca) for x, y in outer_poly]
    min_x = min(p[0] for p in rot_outer)
    min_y = min(p[1] for p in rot_outer)

    shifted_outer = [(x - min_x, y - min_y) for x, y in rot_outer]
    shifted_holes: List[Polygon2D] = []
    for hp in valid_holes:
        rhp = [(x * ca - y * sa - min_x, x * sa + y * ca - min_y) for x, y in hp]
        shifted_holes.append(rhp)

    return (shifted_outer, shifted_holes)


def execute_3d_cut(
    part: PartModel,
    cut_line: CutLine,
    params: DovetailParams,
    printer: PrinterProfile,
) -> CutExecutionResult:
    """
    Executa o pipeline completo de corte 3D (LF01 a LF06 + RN01 a RN08).
    Retorna os sólidos/contornos da Metade A e Metade B prontos para exportação .STL e .STEP.
    """
    report = evaluate_cut_solution(part, cut_line, params, printer, use_3d_kernel=True)
    s_min, s_max, n_min, n_max = compute_scan_bounds_sn(part, cut_line)
    s_start = s_min - 25.0
    s_end = s_max + 25.0
    n_span = max(abs(n_min), abs(n_max)) + params.height_mm + 40.0

    delta = params.delta_offset_mm
    curve_a = construir_curva_offset(
        report.active_teeth_s,
        s_start,
        s_end,
        params,
        delta_offset=-delta,
        cut_line=cut_line,
        subsegments_per_arc=LIMITS.SUBSEGMENTOS_ARCO_FALLBACK,
    )
    curve_b = construir_curva_offset(
        report.active_teeth_s,
        s_start,
        s_end,
        params,
        delta_offset=+delta,
        cut_line=cut_line,
        subsegments_per_arc=LIMITS.SUBSEGMENTOS_ARCO_FALLBACK,
    )

    # Polígonos 2D costurados com os dentes dovetail para exportação nativa e visualização
    poly_a_raw = _stitch_half_polygon_with_seam(
        part.outer_contour, curve_a.polyline_points, cut_line, keep_positive_n=False
    )
    poly_b_raw = _stitch_half_polygon_with_seam(
        part.outer_contour, curve_b.polyline_points, cut_line, keep_positive_n=True
    )

    angle_a = report.half_a_nesting.optimal_angle_deg
    angle_b = report.half_b_nesting.optimal_angle_deg

    outer_a_rot, holes_a_rot = _rotate_and_shift_contours_rn08(poly_a_raw, part.holes, angle_a)
    outer_b_rot, holes_b_rot = _rotate_and_shift_contours_rn08(poly_b_raw, part.holes, angle_b)

    cq_solid_a = None
    cq_solid_b = None
    used_cq = False
    analytical_ok = True

    if part.cq_workplane is not None:
        try:
            closure_a = _build_cutter_closure_points(curve_a, cut_line, s_start, s_end, -n_span)
            closure_b = _build_cutter_closure_points(curve_b, cut_line, s_start, s_end, +n_span)

            cutter_a, ana_a = _build_cq_cutter_analytical_with_fallback(
                curve_a, closure_a, part.bbox.zmin, part.bbox.zmax
            )
            cutter_b, ana_b = _build_cq_cutter_analytical_with_fallback(
                curve_b, closure_b, part.bbox.zmin, part.bbox.zmax
            )
            analytical_ok = ana_a and ana_b

            raw_half_a = part.cq_workplane.intersect(cutter_a)
            raw_half_b = part.cq_workplane.intersect(cutter_b)

            cq_solid_a, n_sol_a = _normalize_cq_solid_rn08(raw_half_a, angle_a)
            cq_solid_b, n_sol_b = _normalize_cq_solid_rn08(raw_half_b, angle_b)

            report.half_a_nesting.num_fragments = max(report.half_a_nesting.num_fragments, n_sol_a)
            report.half_b_nesting.num_fragments = max(report.half_b_nesting.num_fragments, n_sol_b)
            used_cq = True
        except Exception:
            used_cq = False

    thickness_z = max(1.0, part.bbox.size_z)
    half_a = CutSolidHalf(
        label="A",
        outer_contour_xy=outer_a_rot,
        holes_xy=holes_a_rot,
        thickness_z_mm=thickness_z,
        optimal_angle_deg=angle_a,
        num_solids=report.half_a_nesting.num_fragments,
        used_analytical_arcs=analytical_ok,
        cq_solid=cq_solid_a,
    )
    half_b = CutSolidHalf(
        label="B",
        outer_contour_xy=outer_b_rot,
        holes_xy=holes_b_rot,
        thickness_z_mm=thickness_z,
        optimal_angle_deg=angle_b,
        num_solids=report.half_b_nesting.num_fragments,
        used_analytical_arcs=analytical_ok,
        cq_solid=cq_solid_b,
    )

    return CutExecutionResult(
        half_a=half_a,
        half_b=half_b,
        report=report,
        used_cadquery_kernel=used_cq,
    )

