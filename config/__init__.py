"""Pacote de configuração, limites de engenharia e perfis de impressoras."""

from config.printer_profiles import DEFAULT_PRINTER, PRINTER_MAP, PRINTER_PROFILES, PrinterProfile
from config.settings import CLEARANCE_PRESETS, DEFAULT_OUTPUT_FOLDER_NAME, LIMITS, EngineeringLimits

__all__ = [
    "CLEARANCE_PRESETS",
    "DEFAULT_OUTPUT_FOLDER_NAME",
    "DEFAULT_PRINTER",
    "EngineeringLimits",
    "LIMITS",
    "PRINTER_MAP",
    "PRINTER_PROFILES",
    "PrinterProfile",
]

