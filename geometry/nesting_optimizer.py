"""
Otimizador de Auto-Nesting na Mesa (RN06, LF06) e Detector de Fragmentação Multi-Corpo (RN07).
Papel do Módulo: Encontrar a rotação ótima θ ∈ [0°, 180°) para cada metade caber na área útil da impressora
e detectar se a linha de corte divide qualquer metade em pedaços desconectados.
"""

from collections import deque
import math
from typing import List, Tuple
from config.printer_profiles import PrinterProfile
from geometry.coordinate_system import point_in_polygon
from geometry.dovetail_math import construir_curva_offset
from geometry.tooth_placer import escolher_dentes
from models.cut_line import CutLine, Point2D
from models.dovetail_params import DovetailParams
from models.part_model import PartModel, Polygon2D
from models.validation_report import CutValidationReport, HalfNestingResult


def clip_polygon_halfplane(
    polygon: Polygon2D,
    cut_line: CutLine,
    keep_positive_n: bool,
) -> Polygon2D:
    """
    Recorta um polígono 2D pelo semiplano d >= 0 (keep_positive_n=True)
    ou d <= 0 (keep_positive_n=False) no sistema local (s, d) da linha de corte.
    """
    if len(polygon) < 3:
        return []

    def is_inside(d_val: float) -> bool:
        return d_val >= -1e-6 if keep_positive_n else d_val <= 1e-6

    output: Polygon2D = []
    n_verts = len(polygon)
    for i in range(n_verts):
        p1 = polygon[i]
        p2 = polygon[(i + 1) % n_verts]
        _, d1 = cut_line.to_local(p1[0], p1[1])
        _, d2 = cut_line.to_local(p2[0], p2[1])
        in1 = is_inside(d1)
        in2 = is_inside(d2)

        if in1 and in2:
            output.append(p2)
        elif in1 and not in2:
            denom = d1 - d2
            t = d1 / denom if abs(denom) > 1e-12 else 0.5
            inter = (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
            output.append(inter)
        elif not in1 and in2:
            denom = d1 - d2
            t = d1 / denom if abs(denom) > 1e-12 else 0.5
            inter = (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
            output.append(inter)
            output.append(p2)

    return output


def count_half_fragments_2d(part: PartModel, cut_line: CutLine, grid_res: int = 44) -> Tuple[int, int]:
    """
    RN07 — Alerta de Fragmentação (Multi-Body Detection).
    Amostra a região maciça da peça em uma grade 2D e conta quantos componentes conexos
    existem no semiplano d <= 0 (Metade A) e no semiplano d > 0 (Metade B).
    """
    xmin, ymin = part.bbox.xmin, part.bbox.ymin
    xmax, ymax = part.bbox.xmax, part.bbox.ymax
    dx = (xmax - xmin) / float(grid_res)
    dy = (ymax - ymin) / float(grid_res)
    if dx < 1e-4 or dy < 1e-4:
        return (1, 1)

    # 0 = vazio, 1 = Metade A (d <= 0), 2 = Metade B (d > 0)
    grid = [[0] * grid_res for _ in range(grid_res)]
    for r in range(grid_res):
        py = ymin + (r + 0.5) * dy
        for c in range(grid_res):
            px = xmin + (c + 0.5) * dx
            inside = False
            for poly in part.all_outer_polygons:
                if point_in_polygon((px, py), poly):
                    inside = True
                    break
            if not inside:
                continue
            _, d_val = cut_line.to_local(px, py)
            grid[r][c] = 1 if d_val <= 0.0 else 2

    def count_components(target_val: int) -> int:
        visited = [[False] * grid_res for _ in range(grid_res)]
        comp_sizes: List[int] = []
        for r in range(grid_res):
            for c in range(grid_res):
                if grid[r][c] == target_val and not visited[r][c]:
                    q = deque([(r, c)])
                    visited[r][c] = True
                    size = 0
                    while q:
                        cr, cc = q.popleft()
                        size += 1
                        for dr in (-1, 0, 1):
                            for dc in (-1, 0, 1):
                                if dr == 0 and dc == 0:
                                    continue
                                nr, nc = cr + dr, cc + dc
                                if 0 <= nr < grid_res and 0 <= nc < grid_res:
                                    if not visited[nr][nc] and grid[nr][nc] == target_val:
                                        visited[nr][nc] = True
                                        q.append((nr, nc))
                    # Ignora artefatos de 1 célula isolada na borda
                    if size >= 2:
                        comp_sizes.append(size)
        return len(comp_sizes)

    frag_a = count_components(1)
    frag_b = count_components(2)
    return (frag_a, frag_b)


def optimize_rotation_for_bed(
    points: List[Point2D],
    printer: PrinterProfile,
    half_label: str,
    num_fragments: int = 1,
    base_polygons: List[Polygon2D] = None,
) -> HalfNestingResult:
    """
    LF06 & RN06 — Validação de Volume de Impressão e Auto-Aninhamento (Auto-Nesting).
    Testa rotações θ ∈ [0°, 180°) no plano XY para encontrar o ângulo ótimo que minimiza
    max(ΔX_rot, ΔY_rot) e valida contra (L_mesa - 2 * M_mesa).
    """
    usable_x = printer.usable_x_mm
    usable_y = printer.usable_y_mm
    polys = base_polygons or ([points] if len(points) >= 3 else [])

    if not points:
        return HalfNestingResult(
            half_label=half_label,
            fits_on_bed=False,
            optimal_angle_deg=0.0,
            rotated_width_x_mm=0.0,
            rotated_height_y_mm=0.0,
            usable_bed_x_mm=usable_x,
            usable_bed_y_mm=usable_y,
            num_fragments=0,
            polygons_2d=[],
            rotated_polygons_2d=[],
        )

    best_angle = 0.0
    best_dx = float("inf")
    best_dy = float("inf")
    best_metric = float("inf")
    best_fits = False

    # Varredura de 0° a 179° com passo de 2° + refinamento de 0.5°
    for deg_int in range(0, 180, 2):
        deg = float(deg_int)
        rad = math.radians(deg)
        ca = math.cos(rad)
        sa = math.sin(rad)

        xs = [px * ca - py * sa for px, py in points]
        ys = [px * sa + py * ca for px, py in points]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)

        fits_direct = (dx <= usable_x) and (dy <= usable_y)
        fits_swapped = (dy <= usable_x) and (dx <= usable_y)
        fits = fits_direct or fits_swapped

        # Métrica normalizada pelo limite útil da mesa
        ratio_direct = max(dx / usable_x, dy / usable_y)
        ratio_swapped = max(dy / usable_x, dx / usable_y)
        if ratio_swapped < ratio_direct:
            metric = ratio_swapped
            eff_deg = (deg + 90.0) % 180.0
            eff_dx, eff_dy = dy, dx
        else:
            metric = ratio_direct
            eff_deg = deg
            eff_dx, eff_dy = dx, dy

        if (fits and not best_fits) or (fits == best_fits and metric < best_metric):
            best_fits = fits
            best_metric = metric
            best_angle = eff_deg
            best_dx = eff_dx
            best_dy = eff_dy

    # Rotaciona os polígonos para best_angle e translada para o quadrante positivo (RN08)
    rad_opt = math.radians(best_angle)
    ca_opt = math.cos(rad_opt)
    sa_opt = math.sin(rad_opt)

    all_rot_pts = [(px * ca_opt - py * sa_opt, px * sa_opt + py * ca_opt) for px, py in points]
    min_rx = min(p[0] for p in all_rot_pts)
    min_ry = min(p[1] for p in all_rot_pts)

    rotated_polys: List[Polygon2D] = []
    for poly in polys:
        r_poly = [
            (px * ca_opt - py * sa_opt - min_rx, px * sa_opt + py * ca_opt - min_ry)
            for px, py in poly
        ]
        rotated_polys.append(r_poly)

    return HalfNestingResult(
        half_label=half_label,
        fits_on_bed=best_fits,
        optimal_angle_deg=best_angle,
        rotated_width_x_mm=best_dx,
        rotated_height_y_mm=best_dy,
        usable_bed_x_mm=usable_x,
        usable_bed_y_mm=usable_y,
        num_fragments=num_fragments,
        polygons_2d=polys,
        rotated_polygons_2d=rotated_polys,
    )


def evaluate_cut_solution(
    part: PartModel,
    cut_line: CutLine,
    params: DovetailParams,
    printer: PrinterProfile,
    use_3d_kernel: bool = False,
) -> CutValidationReport:
    """
    Executa o pipeline completo de análise geométrica (LF01 -> LF04 -> LF06 + RN01..RN07)
    e retorna um CutValidationReport detalhado para a UI e para o motor de exportação.
    """
    from geometry.coordinate_system import compute_scan_bounds_sn

    s_min, s_max, _, _ = compute_scan_bounds_sn(part, cut_line)
    teeth_s, valid_intervals, active_info, avoided_info = escolher_dentes(
        part, cut_line, params, use_3d_kernel=use_3d_kernel
    )

    delta = params.delta_offset_mm
    curve_center = construir_curva_offset(
        teeth_s, s_min - 10.0, s_max + 10.0, params, delta_offset=0.0, cut_line=cut_line
    )
    curve_a = construir_curva_offset(
        teeth_s, s_min - 10.0, s_max + 10.0, params, delta_offset=-delta, cut_line=cut_line
    )
    curve_b = construir_curva_offset(
        teeth_s, s_min - 10.0, s_max + 10.0, params, delta_offset=+delta, cut_line=cut_line
    )

    # Recorta o contorno externo pelo plano da costura e adiciona a saliência dos dentes para o Nesting
    poly_a = clip_polygon_halfplane(part.outer_contour, cut_line, keep_positive_n=False)
    poly_b = clip_polygon_halfplane(part.outer_contour, cut_line, keep_positive_n=True)

    # Inclui os pontos de topo dos dentes na metade que possui as saliências macho
    teeth_tip_points_a: List[Point2D] = list(poly_a)
    teeth_tip_points_b: List[Point2D] = list(poly_b)
    h_signed = params.height_mm * params.normal_direction_sign
    w_head_half = params.head_width_mm * 0.5

    for sk in teeth_s:
        tip1 = cut_line.to_global(sk - w_head_half, h_signed)
        tip2 = cut_line.to_global(sk + w_head_half, h_signed)
        if h_signed >= 0:
            # Os dentes avançam de d<=0 (Metade A) para dentro de d>0 (Metade B)
            teeth_tip_points_a.extend([tip1, tip2])
        else:
            teeth_tip_points_b.extend([tip1, tip2])

    frag_a, frag_b = count_half_fragments_2d(part, cut_line)

    nesting_a = optimize_rotation_for_bed(
        teeth_tip_points_a,
        printer,
        half_label="Metade A",
        num_fragments=frag_a,
        base_polygons=[poly_a] if len(poly_a) >= 3 else [],
    )
    nesting_b = optimize_rotation_for_bed(
        teeth_tip_points_b,
        printer,
        half_label="Metade B",
        num_fragments=frag_b,
        base_polygons=[poly_b] if len(poly_b) >= 3 else [],
    )

    return CutValidationReport(
        active_teeth_s=teeth_s,
        active_teeth_info=active_info,
        avoided_holes_info=avoided_info,
        valid_intervals_s=valid_intervals,
        centerline_points=curve_center.polyline_points,
        offset_curve_a_points=curve_a.polyline_points,
        offset_curve_b_points=curve_b.polyline_points,
        half_a_nesting=nesting_a,
        half_b_nesting=nesting_b,
        cut_angle_deg=cut_line.angle_deg,
    )

