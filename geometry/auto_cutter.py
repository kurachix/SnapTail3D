"""
Algoritmo de Auto-Corte Inteligente e Presets de Costura (RN12, LF07).
Papel do Módulo: Posicionar automaticamente a linha de corte P1->P2 maximizando o número de dentes
e evitando furos internos e fragmentação, além de gerar presets rápidos.
"""

import math
from config.printer_profiles import PrinterProfile
from geometry.nesting_optimizer import evaluate_cut_solution
from models.cut_line import CutLine
from models.dovetail_params import DovetailParams
from models.part_model import PartModel


def create_preset_cut_line(part: PartModel, preset_type: str, invert_normal: bool = False) -> CutLine:
    """
    Cria uma linha de corte P1 -> P2 atravessando o centro do BoundingBox da peça
    para os presets: 'vertical', 'horizontal', 'diagonal_pos', 'diagonal_neg'.
    """
    cx, cy = part.bbox.center_2d
    span = max(part.bbox.size_x, part.bbox.size_y) * 0.58

    if preset_type == "vertical":
        return CutLine(p1=(cx, cy - span), p2=(cx, cy + span), invert_normal=invert_normal)
    if preset_type == "horizontal":
        return CutLine(p1=(cx - span, cy), p2=(cx + span, cy), invert_normal=invert_normal)
    if preset_type == "diagonal_neg":
        d = span * 0.78
        return CutLine(p1=(cx - d, cy + d), p2=(cx + d, cy - d), invert_normal=invert_normal)
    # Default: diagonal_pos
    d = span * 0.78
    return CutLine(p1=(cx - d, cy - d), p2=(cx + d, cy + d), invert_normal=invert_normal)


def find_optimal_cut_line(
    part: PartModel,
    params: DovetailParams,
    printer: PrinterProfile,
) -> CutLine:
    """
    LF07 & RN12 — Algoritmo de Auto-Corte Inteligente (Optimal Seam Finder).
    Avalia ângulos candidatos e pequenos deslocamentos normais em torno do centro da peça,
    maximizando a função objetivo multi-critério:
      J = 100 * I(Cabe na Mesa) - 80 * (N_fragmentos - 2) + 12 * N_dentes - 15 * N_furos - 0.2 * max_dim
    """
    cx, cy = part.bbox.center_2d
    span = max(part.bbox.size_x, part.bbox.size_y) * 0.58
    candidate_angles_deg = [90.0, 0.0, -26.6, 26.6, -45.0, 45.0, -60.0, 60.0, -30.0, 30.0]
    candidate_offsets_mm = [0.0, -6.0, 6.0, -14.0, 14.0, -22.0, 22.0]

    best_line = create_preset_cut_line(part, "vertical", invert_normal=params.invert_side)
    best_score = -1e9

    for ang_deg in candidate_angles_deg:
        rad = math.radians(ang_deg)
        tx, ty = math.cos(rad), math.sin(rad)
        nx, ny = -math.sin(rad), math.cos(rad)

        for off_n in candidate_offsets_mm:
            ox = cx + off_n * nx
            oy = cy + off_n * ny
            p1 = (ox - span * tx, oy - span * ty)
            p2 = (ox + span * tx, oy + span * ty)
            cand_line = CutLine(p1=p1, p2=p2, invert_normal=params.invert_side)

            report = evaluate_cut_solution(part, cand_line, params, printer, use_3d_kernel=False)
            if report.num_active_teeth == 0:
                continue

            fits_bonus = 100.0 if report.both_fit_on_bed else 0.0
            extra_frags = max(0, report.total_fragments - 2)
            frag_penalty = 80.0 * extra_frags
            teeth_bonus = 12.0 * report.num_active_teeth
            hole_penalty = 15.0 * report.num_avoided_holes
            max_dim = max(
                report.half_a_nesting.rotated_width_x_mm,
                report.half_a_nesting.rotated_height_y_mm,
                report.half_b_nesting.rotated_width_x_mm,
                report.half_b_nesting.rotated_height_y_mm,
            )
            dim_penalty = 0.2 * max_dim
            offset_penalty = 0.3 * abs(off_n)

            score = fits_bonus - frag_penalty + teeth_bonus - hole_penalty - dim_penalty - offset_penalty
            if score > best_score:
                best_score = score
                best_line = cand_line

    return best_line

