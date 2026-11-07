"""
Relatório de Validação de Engenharia, Auto-Nesting e Fragmentação (RN01, RN06, RN07).
Papel do Módulo: Consolidar diagnósticos em tempo real do corte para o HUD do Canvas e exportação.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

Point2D = Tuple[float, float]
Polygon2D = List[Point2D]


@dataclass
class ToothCandidateInfo:
    """Informações sobre um dente aprovado ou uma posição bloqueada por furo/borda."""

    s_coord: float
    global_center: Point2D
    envelope_polygon: Polygon2D
    approved: bool
    reason: str = "OK"  # "OK", "FURO_DESVIADO", "MARGEM_BORDA", "FORA_DA_PECA"


@dataclass
class HalfNestingResult:
    """Resultado do Auto-Nesting (RN06) e Detecção de Fragmentação (RN07) para uma metade."""

    half_label: str              # "Metade A" ou "Metade B"
    fits_on_bed: bool
    optimal_angle_deg: float
    rotated_width_x_mm: float
    rotated_height_y_mm: float
    usable_bed_x_mm: float
    usable_bed_y_mm: float
    num_fragments: int = 1
    polygons_2d: List[Polygon2D] = field(default_factory=list)
    rotated_polygons_2d: List[Polygon2D] = field(default_factory=list)

    @property
    def is_fragmented(self) -> bool:
        """RN07: Alerta se a metade se dividiu em 2 ou mais sólidos desconectados."""
        return self.num_fragments > 1

    @property
    def status_summary(self) -> str:
        status = "OK" if self.fits_on_bed else "EXCEDE MESA"
        frag = f" [{self.num_fragments} fragmentos!]" if self.is_fragmented else ""
        return (
            f"{self.half_label}: {status} "
            f"({self.rotated_width_x_mm:.1f}x{self.rotated_height_y_mm:.1f} mm @ {self.optimal_angle_deg:.0f}°){frag}"
        )


@dataclass
class CutValidationReport:
    """Relatório consolidado do corte atual."""

    active_teeth_s: List[float] = field(default_factory=list)
    active_teeth_info: List[ToothCandidateInfo] = field(default_factory=list)
    avoided_holes_info: List[ToothCandidateInfo] = field(default_factory=list)
    valid_intervals_s: List[Tuple[float, float]] = field(default_factory=list)
    centerline_points: List[Point2D] = field(default_factory=list)
    offset_curve_a_points: List[Point2D] = field(default_factory=list)
    offset_curve_b_points: List[Point2D] = field(default_factory=list)
    half_a_nesting: HalfNestingResult = field(
        default_factory=lambda: HalfNestingResult("Metade A", True, 0.0, 0.0, 0.0, 246.0, 246.0)
    )
    half_b_nesting: HalfNestingResult = field(
        default_factory=lambda: HalfNestingResult("Metade B", True, 0.0, 0.0, 0.0, 246.0, 246.0)
    )
    cut_angle_deg: float = 0.0

    @property
    def num_active_teeth(self) -> int:
        return len(self.active_teeth_s)

    @property
    def num_avoided_holes(self) -> int:
        return len(self.avoided_holes_info)

    @property
    def both_fit_on_bed(self) -> bool:
        """RN06: Ambas as metades devem caber na área útil da mesa."""
        return self.half_a_nesting.fits_on_bed and self.half_b_nesting.fits_on_bed

    @property
    def has_fragmentation_warning(self) -> bool:
        """RN07: Alerta se qualquer metade gerou múltiplos fragmentos desconectados."""
        return self.half_a_nesting.is_fragmented or self.half_b_nesting.is_fragmented

    @property
    def total_fragments(self) -> int:
        return self.half_a_nesting.num_fragments + self.half_b_nesting.num_fragments

    @property
    def overall_approved(self) -> bool:
        return (
            self.num_active_teeth > 0
            and self.both_fit_on_bed
            and not self.has_fragmentation_warning
        )

