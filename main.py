"""
Ponto de Entrada Principal — SnapTail3D / Dovetail Studio 3D.
Na raiz do repositório permanece apenas este orquestrador `main.py` (e a documentação),
enquanto cada papel do sistema está isolado em sua respectiva pasta:
  - config/     : Governança de Regras de Negócio (RN01-RN12) e Perfis de Impressora
  - models/     : Modelagem de Domínio e Entidades de Engenharia
  - geometry/   : Motor Matemático e Analítico 2D/3D (LF01, LF03, LF04, LF06, LF07)
  - cad_engine/ : Kernel CAD B-Rep / Malha 3D, Corte Híbrido (LF02, LF05) e Mini-Teste (RN10)
  - exporters/  : Persistência Imutável e Exportação Sincronizada .STL / .STEP / .JSON (RN09)
  - ui/         : Interface Gráfica Interativa Dark CAD Studio
  - tests/      : Auditoria Automatizada de Regras de Negócio e Geometria
"""

import argparse
from pathlib import Path
import sys
import unittest


def run_test_suite() -> int:
    """Executa a suíte de testes automatizados validando RN01..RN12 e LF01..LF07."""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(Path(__file__).parent / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def run_headless_demo(output_dir: str) -> int:
    """Executa um corte automático de demonstração e gera os arquivos .STL, .STEP e Mini-Teste via CLI."""
    from cad_engine.grip_tester import generate_grip_test_coupom
    from cad_engine.solid_cutter import execute_3d_cut
    from cad_engine.step_loader import create_demo_structural_part
    from config.printer_profiles import DEFAULT_PRINTER
    from exporters.file_exporter import export_cut_pieces
    from geometry.auto_cutter import find_optimal_cut_line
    from models.dovetail_params import DovetailParams

    params = DovetailParams()
    part = create_demo_structural_part("chassi_v")
    cut_line = find_optimal_cut_line(part, params, DEFAULT_PRINTER)
    cut_res = execute_3d_cut(part, cut_line, params, DEFAULT_PRINTER)

    bundle_part = export_cut_pieces(cut_res, part.name, output_dir, params, part.source_path)
    grip_res = generate_grip_test_coupom(params)
    bundle_grip = export_cut_pieces(grip_res, "MiniTeste_Grip_Calibracao", output_dir, params, None)

    print("=== SnapTail3D — Exportação Headless Concluída ===")
    print(f"Peça cortada ({cut_res.report.num_active_teeth} dentes ativos):")
    print(f"  - {bundle_part.stl_a_path}")
    print(f"  - {bundle_part.stl_b_path}")
    print(f"  - {bundle_part.step_a_path}")
    print(f"  - {bundle_part.step_b_path}")
    print(f"Mini-Teste de Grip (RN10):")
    print(f"  - {bundle_grip.stl_a_path}")
    print(f"  - {bundle_grip.stl_b_path}")
    return 0


def launch_studio_gui() -> int:
    """Inicializa a interface gráfica interativa Dark CAD Studio."""
    from ui.main_window import DovetailStudioWindow

    app = DovetailStudioWindow()
    app.mainloop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SnapTail3D — Software Interativo de Corte 3D com Encaixes Mecânicos (Dovetail Studio)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Executa a suíte de testes unitários das Regras de Negócio (RN01 a RN12).",
    )
    parser.add_argument(
        "--headless-export",
        metavar="PASTA",
        type=str,
        default=None,
        help="Executa o Auto-Corte na peça demo e exporta os arquivos .STL/.STEP sem abrir a janela.",
    )
    args = parser.parse_args()

    if args.test:
        return run_test_suite()
    if args.headless_export:
        return run_headless_demo(args.headless_export)
    return launch_studio_gui()


if __name__ == "__main__":
    sys.exit(main())

