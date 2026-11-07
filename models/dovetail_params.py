"""
Entidade de Parâmetros Geométricos do Encaixe Dovetail (RN01 a RN05, LF04).
Papel do Módulo: Encapsular e validar matematicamente todos os parâmetros do dente rabo de andorinha.
"""

from dataclasses import dataclass
import math
from config.settings import LIMITS


@dataclass
class DovetailParams:
    """
    Parâmetros ativos do encaixe rabo de andorinha (Dovetail).
    Garante automaticamente o cumprimento de RN01, RN02, RN03, RN04 e RN05.
    """

    height_mm: float = LIMITS.ALTURA_DENTE_PADRAO_MM
    neck_width_mm: float = LIMITS.LARGURA_PESCOCO_PADRAO_MM
    angle_deg: float = LIMITS.ANGULO_DOVETAIL_PADRAO_DEG
    fillet_radius_mm: float = LIMITS.RAIO_CANTO_PADRAO_MM
    clearance_mm: float = LIMITS.FOLGA_PADRAO_MM
    margin_edge_mm: float = LIMITS.MARGEM_BORDA_MIN_MM
    margin_wall_mm: float = LIMITS.MARGEM_PAREDE_MIN_MM
    pitch_override_mm: float = 0.0  # 0.0 = Modo Isonômico Automático (P = W_head + W_neck, RN03)
    invert_side: bool = False       # Inverte sentido normal (+n vs -n) dos dentes

    def __post_init__(self) -> None:
        self.clamp_to_business_rules()

    def clamp_to_business_rules(self) -> None:
        """Aplica as restrições estritas das Regras de Negócio RN01 a RN05."""
        # RN02: 45° <= beta <= 65°
        self.angle_deg = max(
            LIMITS.ANGULO_DOVETAIL_MIN_DEG,
            min(LIMITS.ANGULO_DOVETAIL_MAX_DEG, float(self.angle_deg)),
        )
        # Limites físicos de altura e pescoço
        self.height_mm = max(
            LIMITS.ALTURA_DENTE_MIN_MM,
            min(LIMITS.ALTURA_DENTE_MAX_MM, float(self.height_mm)),
        )
        self.neck_width_mm = max(
            LIMITS.LARGURA_PESCOCO_MIN_MM,
            min(LIMITS.LARGURA_PESCOCO_MAX_MM, float(self.neck_width_mm)),
        )
        # RN01: Margens mínimas obrigatórias
        self.margin_edge_mm = max(LIMITS.MARGEM_BORDA_MIN_MM, float(self.margin_edge_mm))
        self.margin_wall_mm = max(LIMITS.MARGEM_PAREDE_MIN_MM, float(self.margin_wall_mm))

        # RN05: Folga total
        self.clearance_mm = max(
            LIMITS.FOLGA_MIN_MM,
            min(LIMITS.FOLGA_MAX_MM, float(self.clearance_mm)),
        )

        # RN04: Limitação dinâmica do raio de canto (Fillet C1)
        max_r = self.max_allowed_fillet_radius_mm
        min_r = max(LIMITS.RAIO_CANTO_MIN_MM, self.delta_offset_mm + 0.05)
        self.fillet_radius_mm = max(min_r, min(max_r, float(self.fillet_radius_mm)))

    @property
    def angle_rad(self) -> float:
        """Ângulo agudo beta em radianos."""
        return math.radians(self.angle_deg)

    @property
    def delta_s_mm(self) -> float:
        """Projeção horizontal da parede inclinada: Δs = H / tan(β) (LF04)."""
        return self.height_mm / math.tan(self.angle_rad)

    @property
    def head_width_mm(self) -> float:
        """Largura da cabeça do dente: W_head = W_neck + 2 * Δs (RN02, LF04)."""
        return self.neck_width_mm + 2.0 * self.delta_s_mm

    @property
    def min_pitch_mm(self) -> float:
        """Passo mínimo obrigatório pela RN03 (Isonomia Estrutural Macho/Fêmea)."""
        return self.head_width_mm + self.neck_width_mm

    @property
    def pitch_mm(self) -> float:
        """Passo centro-a-centro P efetivo respeitando P >= W_head + W_neck (RN03)."""
        if self.pitch_override_mm <= 0.0:
            return self.min_pitch_mm
        return max(self.min_pitch_mm, self.pitch_override_mm)

    @property
    def side_wall_length_mm(self) -> float:
        """Comprimento do segmento inclinado lateral do dente: L_wall = H / sin(β)."""
        return self.height_mm / math.sin(self.angle_rad)

    @property
    def max_allowed_fillet_radius_mm(self) -> float:
        """
        Raio máximo permitido pela RN04 para impedir auto-interseção de arcos vizinhos:
        R_max = 0.42 * min(L_seg1, L_seg2) * tan(gamma / 2)
        No vértice do trapezoide dovetail, o menor ângulo interno é gamma = beta.
        """
        valley_flat = max(self.head_width_mm, self.pitch_mm - self.neck_width_mm)
        min_seg = min(self.side_wall_length_mm, self.head_width_mm, valley_flat)
        r_max = LIMITS.FATOR_SEGURANCA_FILLET * min_seg * math.tan(self.angle_rad / 2.0)
        return max(LIMITS.RAIO_CANTO_MIN_MM, min(LIMITS.RAIO_CANTO_MAX_MM, r_max))

    @property
    def effective_fillet_radius_mm(self) -> float:
        """Raio de canto efetivo garantidamente dentro do limite analítico RN04."""
        return min(self.fillet_radius_mm, self.max_allowed_fillet_radius_mm)

    @property
    def delta_offset_mm(self) -> float:
        """Meia-folga normal δ = FOLGA_ENCAIXE / 2 aplicada a cada metade (RN05, LF04)."""
        return self.clearance_mm / 2.0

    @property
    def safety_half_span_s_mm(self) -> float:
        """Meia-largura longitudinal do envelope de proteção: W_head/2 + MARGEM_BORDA (RN01, LF02)."""
        return (self.head_width_mm / 2.0) + self.margin_edge_mm

    @property
    def normal_direction_sign(self) -> float:
        """Sinal de orientação normal (+1.0 padrão ou -1.0 invertido)."""
        return -1.0 if self.invert_side else 1.0

