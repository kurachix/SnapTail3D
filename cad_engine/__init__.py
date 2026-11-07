"""Pacote do Kernel CAD 3D, importador STEP/STL, corte sólido híbrido e gerador de corpo de prova."""

from cad_engine.grip_tester import generate_grip_test_coupom
from cad_engine.solid_cutter import CutExecutionResult, CutSolidHalf, execute_3d_cut
from cad_engine.step_loader import create_demo_structural_part, load_part_from_file

__all__ = [
    "CutExecutionResult",
    "CutSolidHalf",
    "create_demo_structural_part",
    "execute_3d_cut",
    "generate_grip_test_coupom",
    "load_part_from_file",
]

