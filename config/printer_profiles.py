"""
Catálogo de Perfis de Impressoras 3D (RN06).
Papel do Módulo: Fornecer dimensões reais de mesa e margens de segurança para validação de Auto-Nesting.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class PrinterProfile:
    """Representa o envelope de impressão de uma impressora 3D FDM."""

    id: str
    name: str
    bed_x_mm: float
    bed_y_mm: float
    bed_z_mm: float
    margin_mm: float = 5.0
    recommended_clearance_mm: float = 0.18

    @property
    def usable_x_mm(self) -> float:
        """Comprimento útil no eixo X descontando as duas margens laterais (RN06)."""
        return max(10.0, self.bed_x_mm - 2.0 * self.margin_mm)

    @property
    def usable_y_mm(self) -> float:
        """Comprimento útil no eixo Y descontando as duas margens laterais (RN06)."""
        return max(10.0, self.bed_y_mm - 2.0 * self.margin_mm)

    @property
    def display_label(self) -> str:
        return f"{self.name} ({int(self.bed_x_mm)}x{int(self.bed_y_mm)} mm)"


PRINTER_PROFILES: List[PrinterProfile] = [
    PrinterProfile(
        id="bambu_a1",
        name="Bambu Lab A1 / P1S / X1C",
        bed_x_mm=256.0,
        bed_y_mm=256.0,
        bed_z_mm=256.0,
        margin_mm=5.0,
        recommended_clearance_mm=0.18,
    ),
    PrinterProfile(
        id="bambu_a1_mini",
        name="Bambu Lab A1 Mini",
        bed_x_mm=180.0,
        bed_y_mm=180.0,
        bed_z_mm=180.0,
        margin_mm=4.0,
        recommended_clearance_mm=0.18,
    ),
    PrinterProfile(
        id="ender_3_k1",
        name="Creality Ender 3 / K1",
        bed_x_mm=220.0,
        bed_y_mm=220.0,
        bed_z_mm=250.0,
        margin_mm=5.0,
        recommended_clearance_mm=0.20,
    ),
    PrinterProfile(
        id="prusa_mk4",
        name="Prusa MK4 / MK3S+",
        bed_x_mm=250.0,
        bed_y_mm=210.0,
        bed_z_mm=220.0,
        margin_mm=5.0,
        recommended_clearance_mm=0.18,
    ),
    PrinterProfile(
        id="voron_350",
        name="Voron 2.4 / Bambu H2D",
        bed_x_mm=350.0,
        bed_y_mm=350.0,
        bed_z_mm=350.0,
        margin_mm=5.0,
        recommended_clearance_mm=0.18,
    ),
]

PRINTER_MAP: Dict[str, PrinterProfile] = {p.display_label: p for p in PRINTER_PROFILES}
DEFAULT_PRINTER: PrinterProfile = PRINTER_PROFILES[0]

