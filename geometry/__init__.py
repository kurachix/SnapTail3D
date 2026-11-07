"""Pacote de algoritmos matemáticos e geométricos analíticos (LF01 a LF07)."""

from geometry.auto_cutter import create_preset_cut_line, find_optimal_cut_line
from geometry.coordinate_system import (
    compute_scan_bounds_sn,
    distance_to_polygon_boundary,
    point_in_polygon,
    point_to_segment_distance,
    polygon_signed_area,
)
from geometry.dovetail_math import FilletArc2D, OffsetCurveData, build_sharp_vertices_sn, construir_curva_offset
from geometry.nesting_optimizer import (
    clip_polygon_halfplane,
    count_half_fragments_2d,
    evaluate_cut_solution,
    optimize_rotation_for_bed,
)
from geometry.tooth_placer import build_tooth_envelope_global, dente_cabe, escolher_dentes

__all__ = [
    "FilletArc2D",
    "OffsetCurveData",
    "build_sharp_vertices_sn",
    "build_tooth_envelope_global",
    "clip_polygon_halfplane",
    "compute_scan_bounds_sn",
    "construir_curva_offset",
    "count_half_fragments_2d",
    "create_preset_cut_line",
    "dente_cabe",
    "distance_to_polygon_boundary",
    "escolher_dentes",
    "evaluate_cut_solution",
    "find_optimal_cut_line",
    "optimize_rotation_for_bed",
    "point_in_polygon",
    "point_to_segment_distance",
    "polygon_signed_area",
]

