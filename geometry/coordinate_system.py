"""
Sistema de Coordenadas Local da Linha de Corte (s, n) e Primitivas Geométricas 2D (LF01).
Papel do Módulo: Transformar coordenadas globais (X, Y) <-> locais (s, n) e calcular projeções e distâncias.
"""

import math
from typing import List, Tuple
from models.cut_line import CutLine, Point2D
from models.part_model import PartModel, Polygon2D


def compute_scan_bounds_sn(part: PartModel, cut_line: CutLine) -> Tuple[float, float, float, float]:
    """
    LF01: Projeta os 4 cantos do BoundingBox (e os vértices do contorno externo)
    nos vetores unitários tangente (t) e normal (n) para determinar:
    [s_min, s_max] e [n_min, n_max].
    """
    points_to_project: List[Point2D] = list(part.bbox.corners_2d)
    for poly in part.all_outer_polygons:
        points_to_project.extend(poly)

    s_vals: List[float] = []
    n_vals: List[float] = []
    for px, py in points_to_project:
        s, d = cut_line.to_local(px, py)
        s_vals.append(s)
        n_vals.append(d)

    if not s_vals:
        return (-100.0, 100.0, -100.0, 100.0)

    return (min(s_vals), max(s_vals), min(n_vals), max(n_vals))


def point_in_polygon(pt: Point2D, polygon: Polygon2D) -> bool:
    """
    Algoritmo Ray-Casting (Jordan Curve Theorem) para verificar se pt = (x, y)
    está estritamente dentro de um polígono fechado 2D.
    """
    n = len(polygon)
    if n < 3:
        return False
    x, y = pt
    inside = False
    x1, y1 = polygon[0]
    for i in range(1, n + 1):
        x2, y2 = polygon[i % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-15) + x1):
            inside = not inside
        x1, y1 = x2, y2
    return inside


def point_to_segment_distance(pt: Point2D, a: Point2D, b: Point2D) -> float:
    """Calcula a menor distância euclidiana de um ponto pt = (x, y) ao segmento AB."""
    px, py = pt
    ax, ay = a
    bx, by = b
    abx = bx - ax
    aby = by - ay
    len_sq = abx * abx + aby * aby
    if len_sq < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / len_sq))
    proj_x = ax + t * abx
    proj_y = ay + t * aby
    return math.hypot(px - proj_x, py - proj_y)


def distance_to_polygon_boundary(pt: Point2D, polygon: Polygon2D) -> float:
    """Calcula a menor distância perpendicular do ponto pt às arestas do polígono."""
    n = len(polygon)
    if n < 2:
        return float("inf")
    min_d = float("inf")
    for i in range(n):
        d = point_to_segment_distance(pt, polygon[i], polygon[(i + 1) % n])
        if d < min_d:
            min_d = d
    return min_d


def polygon_signed_area(polygon: Polygon2D) -> float:
    """Retorna a área com sinal do polígono (Fórmula de Shoelace)."""
    n = len(polygon)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return 0.5 * area

