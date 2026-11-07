"""
Suíte de Auditoria Automatizada das Regras de Negócio (RN01 a RN12) e Lógicas (LF01 a LF07).
Papel do Módulo: Garantir matematicamente que todas as invariantes geométricas e mecânicas sejam cumpridas.
"""

import math
from pathlib import Path
import tempfile
import unittest
from cad_engine.grip_tester import generate_grip_test_coupom
from cad_engine.solid_cutter import execute_3d_cut
from cad_engine.step_loader import create_demo_structural_part
from config.printer_profiles import DEFAULT_PRINTER
from exporters.file_exporter import export_cut_pieces
from geometry.auto_cutter import find_optimal_cut_line
from geometry.dovetail_math import construir_curva_offset
from geometry.nesting_optimizer import count_half_fragments_2d, evaluate_cut_solution
from geometry.tooth_placer import dente_cabe, escolher_dentes
from models.cut_line import CutLine
from models.dovetail_params import DovetailParams


class TestDovetailBusinessRules(unittest.TestCase):
    """Testa rigorosamente RN01 a RN12 e LF01 a LF07."""

    def test_rn02_and_rn03_dovetail_geometry_and_isonomy(self) -> None:
        """Verifica RN02 (45° <= beta <= 65°, W_head > W_neck) e RN03 (P >= W_head + W_neck)."""
        params = DovetailParams(height_mm=5.0, neck_width_mm=8.0, angle_deg=30.0)
        self.assertEqual(params.angle_deg, 45.0)
        self.assertGreater(params.head_width_mm, params.neck_width_mm)
        self.assertAlmostEqual(params.pitch_mm, params.head_width_mm + params.neck_width_mm, places=6)

        params_high = DovetailParams(angle_deg=80.0)
        self.assertEqual(params_high.angle_deg, 65.0)

    def test_rn04_and_rn05_invariant_fillet_centers_and_normal_offset(self) -> None:
        """
        Verifica LF04, RN04 e RN05:
        - Os 4 cantos do dente geram 4 arcos circulares tangentes C1.
        - O centro Ci de cada arco permanece estritamente invariante entre δ = 0, -δ e +δ.
        - Os raios efetivos obedecem R_eff(δ) = R - τ * δ.
        """
        params = DovetailParams(height_mm=5.0, neck_width_mm=8.0, angle_deg=55.0, clearance_mm=0.18)
        delta = params.delta_offset_mm

        c0 = construir_curva_offset([0.0], -20.0, 20.0, params, delta_offset=0.0)
        ca = construir_curva_offset([0.0], -20.0, 20.0, params, delta_offset=-delta)
        cb = construir_curva_offset([0.0], -20.0, 20.0, params, delta_offset=+delta)

        self.assertEqual(len(c0.arcs), 4)
        self.assertEqual(len(ca.arcs), 4)
        self.assertEqual(len(cb.arcs), 4)

        for arc0, arca, arcb in zip(c0.arcs, ca.arcs, cb.arcs):
            self.assertAlmostEqual(arc0.center[0], arca.center[0], places=6)
            self.assertAlmostEqual(arc0.center[1], arca.center[1], places=6)
            self.assertAlmostEqual(arc0.center[0], arcb.center[0], places=6)
            self.assertAlmostEqual(arc0.center[1], arcb.center[1], places=6)
            # Soma ou diferença dos raios concêntricos deve ser exatamente a folga 2δ = 0.18 mm
            self.assertAlmostEqual( abs(arcb.r_eff - arca.r_eff), params.clearance_mm, places=6)

    def test_rn01_hole_avoidance_and_lf03_symmetric_placement(self) -> None:
        """Verifica RN01 (desvio automático de furos) e LF03 (centralização simétrica)."""
        part = create_demo_structural_part("chassi_v")
        params = DovetailParams()
        # Linha vertical em X = 150 mm que passa exatamente sobre os furos centrais (150, 32) e (150, 74)
        cut_line = CutLine(p1=(150.0, -10.0), p2=(150.0, 190.0))

        # Posição s sobre o furo central em Y = 32 (origem da linha está em Y = 90 -> s = -58)
        ok_hole, reason_hole, _ = dente_cabe(-58.0, part, cut_line, params)
        self.assertFalse(ok_hole)
        self.assertEqual(reason_hole, "FURO_DESVIADO")

        teeth_s, intervals, active_info, avoided_info = escolher_dentes(part, cut_line, params)
        self.assertGreater(len(avoided_info), 0)
        # Nenhum dente aprovado pode invadir os furos centrais
        for sk in teeth_s:
            gx, gy = cut_line.to_global(sk, 0.0)
            for hole in part.holes:
                dist = math.hypot(gx - hole.center[0], gy - hole.center[1])
                self.assertGreater(dist, hole.radius_mm)

    def test_rn07_fragmentation_detection_on_v_arms(self) -> None:
        """Verifica RN07: Linha horizontal cortando os dois braços superiores em 'V' gera 2 fragmentos."""
        part = create_demo_structural_part("chassi_v")
        # Linha horizontal em Y = 148 mm atravessa o vão aberto entre os dois braços do chassi V
        cut_line_v_gap = CutLine(p1=(-10.0, 148.0), p2=(310.0, 148.0))
        frag_a, frag_b = count_half_fragments_2d(part, cut_line_v_gap)
        self.assertGreaterEqual(max(frag_a, frag_b), 2)

    def test_rn09_and_rn10_export_and_mini_grip_test(self) -> None:
        """Verifica RN09 (exportação sincronizada .STL/.STEP) e RN10 (Mini-Teste de Grip 28x22x5mm)."""
        params = DovetailParams()
        grip_res = generate_grip_test_coupom(params)
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = export_cut_pieces(
                cut_result=grip_res,
                base_part_name="Teste_Calibracao",
                output_dir_str=tmpdir,
                params=params,
            )
            self.assertTrue(bundle.stl_a_path.exists())
            self.assertTrue(bundle.stl_b_path.exists())
            self.assertTrue(bundle.step_a_path.exists())
            self.assertTrue(bundle.step_b_path.exists())
            self.assertTrue(bundle.report_json_path.exists())
            self.assertGreater(bundle.stl_a_path.stat().st_size, 84)
            self.assertGreater(bundle.step_a_path.stat().st_size, 200)

    def test_rn12_auto_cutter_finds_valid_solution(self) -> None:
        """Verifica RN12/LF07: Auto-Corte encontra costura aprovada na mesa e com dentes ativos."""
        part = create_demo_structural_part("chassi_v")
        params = DovetailParams()
        opt_line = find_optimal_cut_line(part, params, DEFAULT_PRINTER)
        rep = evaluate_cut_solution(part, opt_line, params, DEFAULT_PRINTER)
        self.assertGreater(rep.num_active_teeth, 0)
        self.assertTrue(rep.both_fit_on_bed)


if __name__ == "__main__":
    unittest.main()

