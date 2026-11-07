"""
Paleta de Cores e Tokens de Design Visual — Padrão Dark CAD Studio (Seção 5.1 da Documentação).
Papel do Módulo: Centralizar cores, fontes e estilos da interface gráfica.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DarkCADTheme:
    """Tokens de cores oficiais especificados na seção 5.1 da documentação."""

    # Fundos e Superfícies
    BG_MAIN: str = "#0B0F19"         # Fundo Principal (Janela): Azul-noite profundo
    BG_PANEL: str = "#111827"        # Painéis Laterais e Containers
    BG_CARD: str = "#1E293B"         # Cards Internos e Controles
    BG_CANVAS: str = "#090D16"       # Viewport CAD 2D/3D
    BORDER_SUBTLE: str = "#334155"   # Bordas sutis de containers

    # Destaques e Ações
    ACCENT_CYAN: str = "#06B6D4"     # Ciano Técnico (Linha ativa / Folga real)
    ACCENT_BLUE: str = "#3B82F6"     # Azul Royal (Botões primários / Hover)
    ACCENT_BLUE_DARK: str = "#1D4ED8"

    # Semântica de Engenharia (Regras de Negócio)
    STATUS_OK: str = "#10B981"       # Verde Esmeralda (Dentes válidos / Aprovado na mesa)
    STATUS_OK_BG: str = "#064E3B"
    STATUS_WARN: str = "#F59E0B"     # Âmbar (Zonas de furo desviadas / Alerta)
    STATUS_WARN_BG: str = "#451A03"
    STATUS_ERR: str = "#EF4444"      # Vermelho Coral (Excede mesa / Fragmentação crítica)
    STATUS_ERR_BG: str = "#450A0A"

    # Tipografia
    TEXT_PRIMARY: str = "#F8FAFC"    # Branco Gelo
    TEXT_SECONDARY: str = "#94A3B8"  # Cinza Azulado
    TEXT_MUTED: str = "#64748B"

    # Geometria no Viewport
    PART_FILL: str = "#1E293B"
    PART_OUTLINE: str = "#94A3B8"
    HOLE_FILL: str = "#090D16"
    HOLE_OUTLINE: str = "#F59E0B"
    GRID_MAJOR: str = "#1E293B"
    GRID_MINOR: str = "#111827"

    # Fontes
    FONT_FAMILY: str = "Segoe UI"
    FONT_MONO: str = "Consolas"


THEME = DarkCADTheme()

