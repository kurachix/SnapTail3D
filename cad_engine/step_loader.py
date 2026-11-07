"""
Importador de Arquivos .STEP / .STL, Normalizador de Escala (RN08) e Gerador de Peças Demo.
Papel do Módulo: Carregar geometria B-Rep 3D via CadQuery/OpenCASCADE (com parser nativo fallback),
normalizar unidades cm->mm (RN08), extrair silhueta e furos internos (RN01) e criar peças de engenharia de teste.
"""

import math
from pathlib import Path
import re
import struct
from typing import List, Optional, Tuple
from models.part_model import BoundingBox3D, HoleFeature, PartModel, Point2D, Polygon2D


def _make_circle_polygon(center: Point2D, radius: float, num_pts: int = 24) -> Polygon2D:
    cx, cy = center
    return [
        (
            cx + radius * math.cos(2.0 * math.pi * i / num_pts),
            cy + radius * math.sin(2.0 * math.pi * i / num_pts),
        )
        for i in range(num_pts)
    ]


def _convex_hull_2d(points: List[Point2D]) -> Polygon2D:
    """Calcula o Fecho Convexo 2D (Monotone Chain de Andrew) em O(N log N)."""
    pts = sorted(set((round(x, 3), round(y, 3)) for x, y in points))
    if len(pts) <= 2:
        return pts

    def cross(o: Point2D, a: Point2D, b: Point2D) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Point2D] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: List[Point2D] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


def create_demo_structural_part(variant: str = "chassi_v") -> PartModel:
    """
    Cria a peça estrutural de demonstração do Dovetail Studio (inspirada no diagrama da seção 4.2):
    Um Chassi Estrutural em 'V' de 300 x 185 x 6 mm (maior que a mesa 256x256 mm da Bambu Lab A1),
    com braços superiores em 'V' (para demonstrar RN07 Alerta de Fragmentação) e furos de fixação
    estrategicamente posicionados (para demonstrar RN01 Proteção Automática de Furos).
    """
    if variant == "gabarito_industrial":
        outer: Polygon2D = [
            (0.0, 0.0),
            (290.0, 0.0),
            (290.0, 150.0),
            (0.0, 150.0),
        ]
        holes_spec = [
            ((35.0, 30.0), 6.0, "Furo M12 SE"),
            ((35.0, 120.0), 6.0, "Furo M12 NE"),
            ((145.0, 42.0), 7.5, "Furo Central Inf"),
            ((145.0, 75.0), 9.0, "Passagem Eixo Central"),
            ((145.0, 112.0), 7.5, "Furo Central Sup"),
            ((255.0, 30.0), 6.0, "Furo M12 SD"),
            ((255.0, 120.0), 6.0, "Furo M12 ND"),
        ]
        name = "Gabarito_Industrial_290mm"
        thickness_z = 6.0
    else:
        # Chassi Estrutural em V (300 x 180 x 6 mm) conforme diagrama da seção 4.2 da documentação
        outer = [
            (30.0, 0.0),
            (270.0, 0.0),
            (270.0, 68.0),
            (300.0, 125.0),
            (300.0, 180.0),
            (225.0, 180.0),
            (195.0, 112.0),
            (105.0, 112.0),
            (75.0, 180.0),
            (0.0, 180.0),
            (0.0, 125.0),
            (30.0, 68.0),
        ]
        holes_spec = [
            ((38.0, 152.0), 7.0, "Bucha Braço Esq"),
            ((262.0, 152.0), 7.0, "Bucha Braço Dir"),
            ((65.0, 35.0), 5.5, "Furo Base Esq"),
            ((235.0, 35.0), 5.5, "Furo Base Dir"),
            ((150.0, 32.0), 8.0, "Furo Central Base"),
            ((150.0, 74.0), 7.5, "Furo Central Costura"),
            ((112.0, 56.0), 5.0, "Furo Auxiliar Esq"),
            ((188.0, 56.0), 5.0, "Furo Auxiliar Dir"),
        ]
        name = "Chassi_Estrutural_V_300mm"
        thickness_z = 6.0

    holes: List[HoleFeature] = [
        HoleFeature(
            center=center,
            radius_mm=radius,
            polygon=_make_circle_polygon(center, radius, 24),
            label=label,
        )
        for center, radius, label in holes_spec
    ]

    xs = [p[0] for p in outer]
    ys = [p[1] for p in outer]
    bbox = BoundingBox3D(
        xmin=min(xs),
        ymin=min(ys),
        zmin=0.0,
        xmax=max(xs),
        ymax=max(ys),
        zmax=thickness_z,
    )

    cq_wp = None
    try:
        import cadquery as cq  # type: ignore

        wp = cq.Workplane("XY").polyline(outer).close().extrude(thickness_z)
        for h in holes:
            wp = (
                wp.faces(">Z")
                .workplane()
                .pushPoints([h.center])
                .circle(h.radius_mm)
                .cutThruAll()
            )
        cq_wp = wp
    except Exception:
        cq_wp = None

    return PartModel(
        name=name,
        source_path=None,
        bbox=bbox,
        outer_contour=outer,
        holes=holes,
        scale_factor_applied=1.0,
        scale_unit_warning=None,
        cq_workplane=cq_wp,
    )


def _normalize_scale_rn08(
    points: List[Point2D],
    zmin: float,
    zmax: float,
    holes: List[HoleFeature],
) -> Tuple[List[Point2D], float, float, List[HoleFeature], float, Optional[str]]:
    """
    RN08 — Normalização de Escala Automática:
    Se o arquivo STEP/STL estiver em centímetros (dimensão máxima XY < 32 unidades),
    converte automaticamente para milímetros (x10).
    """
    if not points:
        return (points, zmin, zmax, holes, 1.0, None)

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    max_span = max(span_x, span_y)

    if 0.5 < max_span < 32.0:
        scale = 10.0
        scaled_pts = [(x * scale, y * scale) for x, y in points]
        scaled_holes = [
            HoleFeature(
                center=(h.center[0] * scale, h.center[1] * scale),
                radius_mm=h.radius_mm * scale,
                polygon=[(px * scale, py * scale) for px, py in h.polygon],
                label=h.label,
            )
            for h in holes
        ]
        warning = "RN08: Escala convertida automaticamente de cm para mm (×10.0)."
        return (scaled_pts, zmin * scale, zmax * scale, scaled_holes, scale, warning)

    return (points, zmin, zmax, holes, 1.0, None)


def _parse_step_fallback(file_path: Path) -> PartModel:
    """
    Parser nativo ISO-10303-21 (.STEP / .STP) quando CadQuery não está ativo no ambiente.
    Extrai CARTESIAN_POINT e CIRCLE para reconstruir BoundingBox, contorno externo e furos internos.
    """
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    pt_pattern = re.compile(
        r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([-\d.Ee+]+)\s*,\s*([-\d.Ee+]+)\s*,\s*([-\d.Ee+]+)\s*\)\s*\)"
    )
    pts_3d = {}
    for match in pt_pattern.finditer(text):
        pid = int(match.group(1))
        x = float(match.group(2))
        y = float(match.group(3))
        z = float(match.group(4))
        pts_3d[pid] = (x, y, z)

    if not pts_3d:
        return create_demo_structural_part("chassi_v")

    # Extrai AXIS2_PLACEMENT_3D -> CARTESIAN_POINT e CIRCLE -> raio para detectar furos
    axis_pattern = re.compile(r"#(\d+)\s*=\s*AXIS2_PLACEMENT_3D\s*\(\s*'[^']*'\s*,\s*#(\d+)")
    axis_to_pt = {}
    for match in axis_pattern.finditer(text):
        axis_to_pt[int(match.group(1))] = int(match.group(2))

    circle_pattern = re.compile(r"CIRCLE\s*\(\s*'[^']*'\s*,\s*#(\d+)\s*,\s*([-\d.Ee+]+)\s*\)")
    raw_circles: List[Tuple[Point2D, float]] = []
    for match in circle_pattern.finditer(text):
        axis_id = int(match.group(1))
        radius = float(match.group(2))
        pt_id = axis_to_pt.get(axis_id)
        if pt_id in pts_3d:
            cx, cy, _ = pts_3d[pt_id]
            raw_circles.append(((cx, cy), radius))

    pts_2d = [(x, y) for x, y, _ in pts_3d.values()]
    zs = [z for _, _, z in pts_3d.values()]
    zmin_raw, zmax_raw = min(zs), max(zs)
    if abs(zmax_raw - zmin_raw) < 0.5:
        zmin_raw, zmax_raw = 0.0, 5.0

    hull = _convex_hull_2d(pts_2d)
    xs = [p[0] for p in hull]
    ys = [p[1] for p in hull]
    max_dim = max(max(xs) - min(xs), max(ys) - min(ys))

    # Filtra círculos internos como furos de parafuso (RN01)
    seen_centers: List[Tuple[Point2D, float]] = []
    for (cx, cy), r in raw_circles:
        if 0.5 <= r <= max_dim * 0.22:
            if not any(math.hypot(cx - sc[0], cy - sc[1]) < 1.0 for sc, _ in seen_centers):
                seen_centers.append(((cx, cy), r))

    holes = [
        HoleFeature(
            center=c,
            radius_mm=r,
            polygon=_make_circle_polygon(c, r, 24),
            label=f"Furo Ø{2*r:.1f}",
        )
        for c, r in seen_centers
    ]

    hull_norm, z0, z1, holes_norm, scale, warn = _normalize_scale_rn08(
        hull, zmin_raw, zmax_raw, holes
    )
    nx = [p[0] for p in hull_norm]
    ny = [p[1] for p in hull_norm]
    bbox = BoundingBox3D(min(nx), min(ny), 0.0, max(nx), max(ny), max(1.0, z1 - z0))

    return PartModel(
        name=file_path.stem,
        source_path=str(file_path.resolve()),
        bbox=bbox,
        outer_contour=hull_norm,
        holes=holes_norm,
        scale_factor_applied=scale,
        scale_unit_warning=warn,
        cq_workplane=None,
    )


def _parse_stl_fallback(file_path: Path) -> PartModel:
    """Leitor nativo de arquivos .STL (binário e ASCII) para extração de contorno e BoundingBox."""
    data = file_path.read_bytes()
    pts_2d: List[Point2D] = []
    zs: List[float] = []

    is_ascii = data[:5].lower() == b"solid" and b"vertex" in data[:1024].lower()
    if is_ascii:
        text = data.decode("utf-8", errors="ignore")
        for match in re.finditer(r"vertex\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)", text):
            pts_2d.append((float(match.group(1)), float(match.group(2))))
            zs.append(float(match.group(3)))
    else:
        if len(data) >= 84:
            num_tris = struct.unpack("<I", data[80:84])[0]
            offset = 84
            for _ in range(min(num_tris, 250000)):
                if offset + 50 > len(data):
                    break
                vals = struct.unpack("<12fH", data[offset : offset + 50])
                pts_2d.append((vals[3], vals[4]))
                pts_2d.append((vals[6], vals[7]))
                pts_2d.append((vals[9], vals[10]))
                zs.extend([vals[5], vals[8], vals[11]])
                offset += 50

    if not pts_2d:
        return create_demo_structural_part("chassi_v")

    hull = _convex_hull_2d(pts_2d)
    zmin_raw, zmax_raw = min(zs), max(zs)
    hull_norm, z0, z1, holes_norm, scale, warn = _normalize_scale_rn08(
        hull, zmin_raw, zmax_raw, []
    )
    nx = [p[0] for p in hull_norm]
    ny = [p[1] for p in hull_norm]
    bbox = BoundingBox3D(min(nx), min(ny), 0.0, max(nx), max(ny), max(1.0, z1 - z0))

    return PartModel(
        name=file_path.stem,
        source_path=str(file_path.resolve()),
        bbox=bbox,
        outer_contour=hull_norm,
        holes=holes_norm,
        scale_factor_applied=scale,
        scale_unit_warning=warn,
        cq_workplane=None,
    )


def load_part_from_file(file_path_str: str) -> PartModel:
    """
    Carrega um arquivo .STEP, .STP ou .STL aplicando a RN08 (normalização de escala e Z=0)
    e preservando o arquivo original intacto (RN09).
    """
    file_path = Path(file_path_str)
    if not file_path.exists():
        return create_demo_structural_part("chassi_v")

    ext = file_path.suffix.lower()
    if ext == ".stl":
        return _parse_stl_fallback(file_path)

    # Tenta importar via CadQuery B-Rep primeiro
    try:
        import cadquery as cq  # type: ignore

        wp = cq.importers.importStep(str(file_path))
        bb = wp.val().BoundingBox()
        max_xy = max(bb.xlen, bb.ylen)
        scale_applied = 1.0
        warn_msg = None

        # RN08: Conversão automática cm -> mm
        if 0.5 < max_xy < 32.0:
            scale_applied = 10.0
            wp = wp.val().scale(scale_applied)
            wp = cq.Workplane("XY").add(wp)
            bb = wp.val().BoundingBox()
            warn_msg = "RN08: Escala convertida automaticamente de cm para mm (×10.0)."

        # Apoia em Z = 0 (RN08)
        if abs(bb.zmin) > 1e-4:
            wp = wp.translate((0.0, 0.0, -bb.zmin))
            bb = wp.val().BoundingBox()

        # Extrai vértices para contorno e círculos para furos
        verts = wp.vertices().vals()
        pts_2d = [(v.X, v.Y) for v in verts]
        hull = _convex_hull_2d(pts_2d)

        # Fallback complementar para extrair furos circulares do arquivo STEP
        step_fallback = _parse_step_fallback(file_path)
        holes = step_fallback.holes

        bbox = BoundingBox3D(bb.xmin, bb.ymin, 0.0, bb.xmax, bb.ymax, bb.zmax)
        return PartModel(
            name=file_path.stem,
            source_path=str(file_path.resolve()),
            bbox=bbox,
            outer_contour=hull,
            holes=holes,
            scale_factor_applied=scale_applied,
            scale_unit_warning=warn_msg,
            cq_workplane=wp,
        )
    except Exception:
        return _parse_step_fallback(file_path)

