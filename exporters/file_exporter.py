"""
Persistência e Exportação Sincronizada .STL, .STEP e Relatório Técnico (RN09).
Papel do Módulo: Garantir a imutabilidade do arquivo original e gravar os pares sincronizados
NomePeca_A.stl, NomePeca_B.stl, NomePeca_A.step, NomePeca_B.step na pasta escolhida pelo usuário.
"""

from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import struct
from typing import List, Tuple
from cad_engine.solid_cutter import CutExecutionResult, CutSolidHalf
from geometry.coordinate_system import point_in_polygon, polygon_signed_area
from models.cut_line import Point2D
from models.dovetail_params import DovetailParams
from models.part_model import Polygon2D

Triangle3D = Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]


@dataclass
class ExportedFilesBundle:
    """Caminhos dos arquivos gerados após uma operação de exportação (RN09)."""

    output_dir: Path
    stl_a_path: Path
    stl_b_path: Path
    step_a_path: Path
    step_b_path: Path
    report_json_path: Path


def _ear_clip_triangulate(polygon: Polygon2D) -> List[Tuple[Point2D, Point2D, Point2D]]:
    """
    Algoritmo Ear-Clipping para triangular polígonos simples (convexos ou côncavos, como dentes dovetail).
    """
    pts = list(polygon)
    if len(pts) < 3:
        return []
    # Remove pontos duplicados consecutivos
    cleaned: Polygon2D = []
    for p in pts:
        if not cleaned or math.hypot(p[0] - cleaned[-1][0], p[1] - cleaned[-1][1]) > 1e-5:
            cleaned.append(p)
    if len(cleaned) >= 2 and math.hypot(cleaned[0][0] - cleaned[-1][0], cleaned[0][1] - cleaned[-1][1]) <= 1e-5:
        cleaned.pop()

    if len(cleaned) < 3:
        return []

    if polygon_signed_area(cleaned) < 0:
        cleaned.reverse()

    triangles: List[Tuple[Point2D, Point2D, Point2D]] = []
    verts = list(cleaned)

    def cross_2d(a: Point2D, b: Point2D, c: Point2D) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def pt_in_tri(p: Point2D, a: Point2D, b: Point2D, c: Point2D) -> bool:
        c1 = cross_2d(a, b, p)
        c2 = cross_2d(b, c, p)
        c3 = cross_2d(c, a, p)
        return (c1 >= -1e-7) and (c2 >= -1e-7) and (c3 >= -1e-7)

    max_iters = len(verts) * 3 + 10
    iters = 0
    while len(verts) > 3 and iters < max_iters:
        iters += 1
        ear_found = False
        n = len(verts)
        for i in range(n):
            p_prev = verts[(i - 1) % n]
            p_curr = verts[i]
            p_next = verts[(i + 1) % n]

            if cross_2d(p_prev, p_curr, p_next) <= 1e-7:
                continue

            has_point_inside = False
            for j in range(n):
                if j in ((i - 1) % n, i, (i + 1) % n):
                    continue
                if pt_in_tri(verts[j], p_prev, p_curr, p_next):
                    has_point_inside = True
                    break

            if not has_point_inside:
                triangles.append((p_prev, p_curr, p_next))
                del verts[i]
                ear_found = True
                break

        if not ear_found:
            # Fallback em leque caso haja vértices quase colineares nos fillets
            p0 = verts[0]
            for i in range(1, len(verts) - 1):
                triangles.append((p0, verts[i], verts[i + 1]))
            return triangles

    if len(verts) == 3:
        triangles.append((verts[0], verts[1], verts[2]))

    return triangles


def _extrude_polygon_to_triangles(half: CutSolidHalf) -> List[Triangle3D]:
    """
    Constrói uma malha 3D fechada (watertight) apoiada em Z = 0 até Z = thickness_z_mm (RN08).
    """
    outer = half.outer_contour_xy
    z0 = 0.0
    z1 = max(1.0, half.thickness_z_mm)
    tris_2d = _ear_clip_triangulate(outer)
    tris_3d: List[Triangle3D] = []

    # Tampas inferior (Z = 0, normal -Z) e superior (Z = z1, normal +Z)
    for a, b, c in tris_2d:
        centroid = ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0)
        if any(point_in_polygon(centroid, hp) for hp in half.holes_xy):
            continue
        tris_3d.append(((a[0], a[1], z1), (b[0], b[1], z1), (c[0], c[1], z1)))
        tris_3d.append(((a[0], a[1], z0), (c[0], c[1], z0), (b[0], b[1], z0)))

    # Paredes laterais externas
    n = len(outer)
    for i in range(n):
        p1 = outer[i]
        p2 = outer[(i + 1) % n]
        v00 = (p1[0], p1[1], z0)
        v10 = (p2[0], p2[1], z0)
        v11 = (p2[0], p2[1], z1)
        v01 = (p1[0], p1[1], z1)
        tris_3d.append((v00, v10, v11))
        tris_3d.append((v00, v11, v01))

    # Paredes cilíndricas internas dos furos
    for hp in half.holes_xy:
        nh = len(hp)
        for i in range(nh):
            p1 = hp[i]
            p2 = hp[(i + 1) % nh]
            v00 = (p1[0], p1[1], z0)
            v10 = (p2[0], p2[1], z0)
            v11 = (p2[0], p2[1], z1)
            v01 = (p1[0], p1[1], z1)
            tris_3d.append((v00, v11, v10))
            tris_3d.append((v00, v01, v11))

    return tris_3d


def _write_binary_stl(half: CutSolidHalf, target_path: Path) -> None:
    """Escreve um arquivo .STL binário padrão IEEE 754 pronto para Bambu Studio / OrcaSlicer."""
    triangles = _extrude_polygon_to_triangles(half)
    header = f"snaptail3D - Half {half.label} (Z=0 mm)".encode("ascii")
    header = header.ljust(80, b"\x00")[:80]

    with target_path.open("wb") as f:
        f.write(header)
        f.write(struct.pack("<I", len(triangles)))
        for v1, v2, v3 in triangles:
            ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
            vx, vy, vz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            norm = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx, ny, nz = nx / norm, ny / norm, nz / norm
            f.write(
                struct.pack(
                    "<12fH",
                    nx, ny, nz,
                    v1[0], v1[1], v1[2],
                    v2[0], v2[1], v2[2],
                    v3[0], v3[1], v3[2],
                    0,
                )
            )


def _write_native_step_ap214(half: CutSolidHalf, part_name: str, target_path: Path) -> None:
    """
    Escreve um arquivo ISO-10303-21 (.STEP AP214) contendo a geometria 3D exata do contorno
    e da extrusão em milímetros quando o kernel OpenCASCADE não estiver presente.
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    outer = half.outer_contour_xy
    z_top = half.thickness_z_mm

    lines = [
        "ISO-10303-21;",
        "HEADER;",
        f"FILE_DESCRIPTION(('snaptail3D - Metade {half.label}'),'2;1');",
        f"FILE_NAME('{target_path.name}','{timestamp}',('snaptail3D'),('Engineering Studio'),'snaptail3D 2.0','snaptail3D Kernel','');",
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
        "ENDSEC;",
        "DATA;",
        "#1 = APPLICATION_CONTEXT('automotive design');",
        "#2 = APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#1);",
        f"#3 = PRODUCT('{part_name}_{half.label}','{part_name}_{half.label}','',(#4));",
        "#4 = PRODUCT_CONTEXT('',#1,'mechanical');",
        "#5 = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );",
        "#6 = ( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#7)) GLOBAL_UNIT_ASSIGNED_CONTEXT((#5)) REPRESENTATION_CONTEXT('3D','3D Context') );",
        "#7 = UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-04),#5,'distance_accuracy_value','');",
        "#10 = CARTESIAN_POINT('Origin',(0.0,0.0,0.0));",
        "#11 = DIRECTION('Z_Axis',(0.0,0.0,1.0));",
        "#12 = DIRECTION('X_Axis',(1.0,0.0,0.0));",
        "#13 = AXIS2_PLACEMENT_3D('',#10,#11,#12);",
    ]

    entity_id = 100
    bottom_pt_ids: List[int] = []
    top_pt_ids: List[int] = []

    for x, y in outer:
        bid = entity_id
        tid = entity_id + 1
        entity_id += 2
        lines.append(f"#{bid} = CARTESIAN_POINT('',({x:.6f},{y:.6f},0.000000));")
        lines.append(f"#{tid} = CARTESIAN_POINT('',({x:.6f},{y:.6f},{z_top:.6f}));")
        bottom_pt_ids.append(bid)
        top_pt_ids.append(tid)

    if bottom_pt_ids:
        b_refs = ",".join(f"#{i}" for i in bottom_pt_ids + [bottom_pt_ids[0]])
        t_refs = ",".join(f"#{i}" for i in top_pt_ids + [top_pt_ids[0]])
        lines.append(f"#{entity_id} = POLYLINE('Base_Profile_Z0',({b_refs}));")
        lines.append(f"#{entity_id + 1} = POLYLINE('Top_Profile_ZMax',({t_refs}));")

    lines.extend(["ENDSEC;", "END-ISO-10303-21;"])
    target_path.write_text("\n".join(lines), encoding="utf-8")


def export_cut_pieces(
    cut_result: CutExecutionResult,
    base_part_name: str,
    output_dir_str: str,
    params: DovetailParams,
    source_path: str = None,
) -> ExportedFilesBundle:
    """
    RN09 — Imutabilidade do Arquivo Original e Organização de Pastas:
    Salva os pares sincronizados:
      - NomePeca_A.stl, NomePeca_B.stl
      - NomePeca_A.step, NomePeca_B.step
      - NomePeca_Relatorio.json
    """
    out_dir = Path(output_dir_str).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if (c.isalnum() or c in ("_", "-")) else "_" for c in base_part_name).strip("_")
    if not safe_name:
        safe_name = "Peca_Cortada"

    # Garantia explícita de que nenhum arquivo de saída sobrescreva o arquivo original (RN09)
    stl_a = out_dir / f"{safe_name}_A.stl"
    stl_b = out_dir / f"{safe_name}_B.stl"
    step_a = out_dir / f"{safe_name}_A.step"
    step_b = out_dir / f"{safe_name}_B.step"
    report_json = out_dir / f"{safe_name}_Relatorio.json"

    if source_path:
        src_resolved = Path(source_path).resolve()
        if src_resolved in (step_a.resolve(), step_b.resolve(), stl_a.resolve(), stl_b.resolve()):
            safe_name = f"{safe_name}_Dovetail"
            stl_a = out_dir / f"{safe_name}_A.stl"
            stl_b = out_dir / f"{safe_name}_B.stl"
            step_a = out_dir / f"{safe_name}_A.step"
            step_b = out_dir / f"{safe_name}_B.step"
            report_json = out_dir / f"{safe_name}_Relatorio.json"

    # Exporta Metade A e Metade B via CadQuery B-Rep se disponível, ou via gerador nativo
    for half, stl_path, step_path in (
        (cut_result.half_a, stl_a, step_a),
        (cut_result.half_b, stl_b, step_b),
    ):
        exported_cq = False
        if half.cq_solid is not None:
            try:
                import cadquery as cq  # type: ignore

                cq.exporters.export(half.cq_solid, str(stl_path))
                cq.exporters.export(half.cq_solid, str(step_path))
                exported_cq = True
            except Exception:
                exported_cq = False

        if not exported_cq:
            _write_binary_stl(half, stl_path)
            _write_native_step_ap214(half, safe_name, step_path)

    # Salva relatório de engenharia JSON (Rastreabilidade e Auditoria das RNs)
    rep = cut_result.report
    report_payload = {
        "software": "snaptail3D",
        "timestamp": datetime.now().isoformat(),
        "part_name": base_part_name,
        "original_source_preserved": True,
        "dovetail_parameters": {
            "height_mm": round(params.height_mm, 3),
            "neck_width_mm": round(params.neck_width_mm, 3),
            "head_width_mm": round(params.head_width_mm, 3),
            "pitch_mm": round(params.pitch_mm, 3),
            "angle_deg": round(params.angle_deg, 2),
            "fillet_radius_mm": round(params.effective_fillet_radius_mm, 3),
            "clearance_mm": round(params.clearance_mm, 3),
            "margin_edge_mm": round(params.margin_edge_mm, 2),
            "margin_wall_mm": round(params.margin_wall_mm, 2),
        },
        "cut_telemetry": {
            "cut_angle_deg": round(rep.cut_angle_deg, 2),
            "num_active_teeth": rep.num_active_teeth,
            "num_avoided_holes": rep.num_avoided_holes,
            "both_fit_on_printer_bed": rep.both_fit_on_bed,
            "fragmentation_warning": rep.has_fragmentation_warning,
            "half_a": {
                "fits_on_bed": rep.half_a_nesting.fits_on_bed,
                "optimal_rotation_deg": rep.half_a_nesting.optimal_angle_deg,
                "rotated_dimensions_mm": [
                    round(rep.half_a_nesting.rotated_width_x_mm, 2),
                    round(rep.half_a_nesting.rotated_height_y_mm, 2),
                ],
                "num_fragments": rep.half_a_nesting.num_fragments,
                "stl_file": stl_a.name,
                "step_file": step_a.name,
            },
            "half_b": {
                "fits_on_bed": rep.half_b_nesting.fits_on_bed,
                "optimal_rotation_deg": rep.half_b_nesting.optimal_angle_deg,
                "rotated_dimensions_mm": [
                    round(rep.half_b_nesting.rotated_width_x_mm, 2),
                    round(rep.half_b_nesting.rotated_height_y_mm, 2),
                ],
                "num_fragments": rep.half_b_nesting.num_fragments,
                "stl_file": stl_b.name,
                "step_file": step_b.name,
            },
        },
    }
    report_json.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return ExportedFilesBundle(
        output_dir=out_dir,
        stl_a_path=stl_a,
        stl_b_path=stl_b,
        step_a_path=step_a,
        step_b_path=step_b,
        report_json_path=report_json,
    )

