"""
Gerador de Corpo de Prova Rápido — Mini-Teste de Grip em 10 Minutos (RN10, RN11).
Papel do Módulo: Construir um bloco de calibração compacto (padrão 28 x 22 x 5 mm) contendo
1 único par macho/fêmea com os parâmetros ativos para validar a folga da impressora e do filamento.
"""

from cad_engine.solid_cutter import CutExecutionResult, CutSolidHalf, _build_cq_cutter_analytical_with_fallback
from config.printer_profiles import DEFAULT_PRINTER
from config.settings import LIMITS
from geometry.dovetail_math import construir_curva_offset
from models.cut_line import CutLine
from models.dovetail_params import DovetailParams
from models.part_model import Polygon2D
from models.validation_report import CutValidationReport, HalfNestingResult


def generate_grip_test_coupom(params: DovetailParams) -> CutExecutionResult:
    """
    RN10 — Geração de Corpo de Prova Rápido (Mini-Teste de Grip):
    Gera um bloco de calibração (mínimo 28 x 22 x 5 mm, ajustado caso o dente configurado seja maior)
    contendo 1 único par macho/fêmea centrado em s = 0.
    """
    width_x = max(
        LIMITS.CORPO_PROVA_LARGURA_MM,
        params.head_width_mm + 2.0 * params.margin_edge_mm + 4.0,
    )
    depth_y = max(
        LIMITS.CORPO_PROVA_PROFUNDIDADE_MM,
        2.0 * (params.height_mm + params.margin_wall_mm + 3.5),
    )
    height_z = LIMITS.CORPO_PROVA_ALTURA_MM

    half_w = width_x * 0.5
    half_d = depth_y * 0.5

    # Linha de corte horizontal no centro Y = 0, de X = -half_w até X = +half_w
    cut_line = CutLine(p1=(-half_w, 0.0), p2=(+half_w, 0.0), invert_normal=False)
    delta = params.delta_offset_mm

    curve_a = construir_curva_offset(
        teeth_s=[0.0],
        s_start=-half_w,
        s_end=+half_w,
        params=params,
        delta_offset=-delta,
        cut_line=cut_line,
    )
    curve_b = construir_curva_offset(
        teeth_s=[0.0],
        s_start=-half_w,
        s_end=+half_w,
        params=params,
        delta_offset=+delta,
        cut_line=cut_line,
    )

    # Polígono fechado da Metade A (inferior, y de -half_d até a costura + dente macho)
    poly_a_raw: Polygon2D = [(-half_w, -half_d), (+half_w, -half_d)] + list(
        reversed(curve_a.polyline_points)
    )
    # Polígono fechado da Metade B (superior, da costura até y = +half_d)
    poly_b_raw: Polygon2D = list(curve_b.polyline_points) + [(+half_w, +half_d), (-half_w, +half_d)]

    # Translada cada metade para o quadrante positivo X >= 0, Y >= 0 (RN08)
    min_ax = min(p[0] for p in poly_a_raw)
    min_ay = min(p[1] for p in poly_a_raw)
    outer_a = [(x - min_ax, y - min_ay) for x, y in poly_a_raw]

    min_bx = min(p[0] for p in poly_b_raw)
    min_by = min(p[1] for p in poly_b_raw)
    outer_b = [(x - min_bx, y - min_by) for x, y in poly_b_raw]

    cq_solid_a = None
    cq_solid_b = None
    used_cq = False

    try:
        import cadquery as cq  # type: ignore

        block = cq.Workplane("XY").box(width_x, depth_y, height_z, centered=(True, True, False))
        # Furo de chaveiro/identificação no canto da peça fêmea (fácil identificação de lado)
        closure_a = [(+half_w + 5.0, -half_d - 10.0), (-half_w - 5.0, -half_d - 10.0)]
        closure_b = [(+half_w + 5.0, +half_d + 10.0), (-half_w - 5.0, +half_d + 10.0)]

        cutter_a, _ = _build_cq_cutter_analytical_with_fallback(curve_a, closure_a, 0.0, height_z)
        cutter_b, _ = _build_cq_cutter_analytical_with_fallback(curve_b, closure_b, 0.0, height_z)

        raw_a = block.intersect(cutter_a)
        raw_b = block.intersect(cutter_b)

        bb_a = raw_a.val().BoundingBox()
        cq_solid_a = raw_a.translate((-bb_a.xmin, -bb_a.ymin, -bb_a.zmin))

        bb_b = raw_b.val().BoundingBox()
        cq_solid_b = raw_b.translate((-bb_b.xmin, -bb_b.ymin, -bb_b.zmin))
        used_cq = True
    except Exception:
        used_cq = False

    half_a = CutSolidHalf(
        label="A",
        outer_contour_xy=outer_a,
        holes_xy=[],
        thickness_z_mm=height_z,
        optimal_angle_deg=0.0,
        num_solids=1,
        used_analytical_arcs=True,
        cq_solid=cq_solid_a,
    )
    half_b = CutSolidHalf(
        label="B",
        outer_contour_xy=outer_b,
        holes_xy=[],
        thickness_z_mm=height_z,
        optimal_angle_deg=0.0,
        num_solids=1,
        used_analytical_arcs=True,
        cq_solid=cq_solid_b,
    )

    report = CutValidationReport(
        active_teeth_s=[0.0],
        centerline_points=curve_a.polyline_points,
        offset_curve_a_points=curve_a.polyline_points,
        offset_curve_b_points=curve_b.polyline_points,
        half_a_nesting=HalfNestingResult(
            "Metade A (Macho)", True, 0.0, width_x, depth_y * 0.5 + params.height_mm,
            DEFAULT_PRINTER.usable_x_mm, DEFAULT_PRINTER.usable_y_mm, 1, [outer_a], [outer_a]
        ),
        half_b_nesting=HalfNestingResult(
            "Metade B (Fêmea)", True, 0.0, width_x, depth_y * 0.5,
            DEFAULT_PRINTER.usable_x_mm, DEFAULT_PRINTER.usable_y_mm, 1, [outer_b], [outer_b]
        ),
        cut_angle_deg=0.0,
    )

    return CutExecutionResult(
        half_a=half_a,
        half_b=half_b,
        report=report,
        used_cadquery_kernel=used_cq,
    )

