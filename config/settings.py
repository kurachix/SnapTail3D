"""
Configurações Globais e Constantes das Regras de Negócio (RN01 a RN12).
Papel do Módulo: Governança de parâmetros limites de engenharia, tolerâncias e diretórios padrão.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class EngineeringLimits:
    """Limites físicos e matemáticos definidos pelas Regras de Negócio (RN01-RN12)."""

    # RN01 — Preservação de Integridade Funcional (Proteção de Furos e Bordas)
    MARGEM_BORDA_MIN_MM: float = 2.5       # Margem longitudinal mínima nas pontas do dente
    MARGEM_PAREDE_MIN_MM: float = 1.6      # Margem transversal mínima além da base e topo do dente
    PASSO_VARREDURA_MM: float = 1.0        # Passo de amostragem da linha de corte (LF02/LF03)
    RAZAO_VOLUME_MACICO_MIN: float = 0.992 # Fração mínima de volume para aprovar prisma (LF02)
    FATIA_Z_OFFSET_MIN_MM: float = 0.4     # Início da fatia estrutural basal em Z
    FATIA_Z_OFFSET_MAX_MM: float = 2.9     # Fim da fatia estrutural basal em Z

    # RN02 — Travamento Mecânico Bidirecional (Geometria Dovetail)
    ANGULO_DOVETAIL_MIN_DEG: float = 45.0
    ANGULO_DOVETAIL_MAX_DEG: float = 65.0
    ANGULO_DOVETAIL_PADRAO_DEG: float = 55.0

    # Dimensões do Dente (Altura H e Pescoço W_neck)
    ALTURA_DENTE_MIN_MM: float = 2.5
    ALTURA_DENTE_MAX_MM: float = 14.0
    ALTURA_DENTE_PADRAO_MM: float = 5.0

    LARGURA_PESCOCO_MIN_MM: float = 4.0
    LARGURA_PESCOCO_MAX_MM: float = 22.0
    LARGURA_PESCOCO_PADRAO_MM: float = 8.0

    # RN04 — Eliminação de Concentradores de Tensão (Fillet Tangente C1)
    RAIO_CANTO_MIN_MM: float = 0.2
    RAIO_CANTO_MAX_MM: float = 3.0
    RAIO_CANTO_PADRAO_MM: float = 0.9
    FATOR_SEGURANCA_FILLET: float = 0.42   # R_max = 0.42 * min(L1, L2) * tan(gamma/2)
    SUBSEGMENTOS_ARCO_FALLBACK: int = 14   # LF05: Discretização fallback por arco

    # RN05 — Folga Perpendicular Uniforme (True Normal Parallel Offset)
    FOLGA_MIN_MM: float = 0.08
    FOLGA_MAX_MM: float = 0.40
    FOLGA_PADRAO_MM: float = 0.18

    # RN10 & RN11 — Corpo de Prova Rápido (Mini-Teste de Grip) e Chanfro Z
    CORPO_PROVA_LARGURA_MM: float = 28.0
    CORPO_PROVA_PROFUNDIDADE_MM: float = 22.0
    CORPO_PROVA_ALTURA_MM: float = 5.0
    CHANFRO_ELEPHANT_FOOT_MM: float = 0.4


LIMITS = EngineeringLimits()

# Presets de Folga (RN05)
CLEARANCE_PRESETS: Dict[str, float] = {
    "Justo (0.15 mm)": 0.15,
    "Bambu A1 (0.18 mm)": 0.18,
    "Folga Livre (0.23 mm)": 0.23,
}

# Pasta padrão para exportação (RN09)
DEFAULT_OUTPUT_FOLDER_NAME: str = "Cortes_Personalizados"

