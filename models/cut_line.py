"""
Entidade da Linha de Corte e Sistema de Coordenadas Local (LF01).
Papel do Módulo: Representar os pontos P1 e P2 traçados pelo usuário e fornecer vetores tangente (t) e normal (n).
"""

from dataclasses import dataclass
import math
from typing import Tuple

Point2D = Tuple[float, float]


@dataclass
class CutLine:
    """
    Linha de corte definida por dois pontos P1 = (x1, y1) e P2 = (x2, y2) no plano XY.
    Implementa as propriedades de direção e normal à esquerda da LF01.
    """

    p1: Point2D
    p2: Point2D
    invert_normal: bool = False

    @property
    def dx(self) -> float:
        return self.p2[0] - self.p1[0]

    @property
    def dy(self) -> float:
        return self.p2[1] - self.p1[1]

    @property
    def length_mm(self) -> float:
        return math.hypot(self.dx, self.dy)

    @property
    def angle_rad(self) -> float:
        """Ângulo α da linha de corte em radianos no intervalo (-π, π]."""
        if self.length_mm < 1e-6:
            return 0.0
        return math.atan2(self.dy, self.dx)

    @property
    def angle_deg(self) -> float:
        """Ângulo α da linha de corte em graus."""
        return math.degrees(self.angle_rad)

    @property
    def origin(self) -> Point2D:
        """Ponto médio (x0, y0) da linha de corte usado como origem s = 0."""
        return ((self.p1[0] + self.p2[0]) * 0.5, (self.p1[1] + self.p2[1]) * 0.5)

    @property
    def tangent(self) -> Point2D:
        """Vetor unitário tangente t = (cos α, sin α) (LF01)."""
        a = self.angle_rad
        return (math.cos(a), math.sin(a))

    @property
    def normal(self) -> Point2D:
        """Vetor unitário normal à esquerda n = (-sin α, cos α), ou invertido se solicitado (LF01)."""
        a = self.angle_rad
        sign = -1.0 if self.invert_normal else 1.0
        return (-math.sin(a) * sign, math.cos(a) * sign)

    def to_global(self, s: float, d: float) -> Point2D:
        """
        Converte coordenadas locais da costura (s, d) para coordenadas globais (X, Y) (LF01):
        (X, Y) = (x0 + s * tx + d * nx, y0 + s * ty + d * ny)
        """
        x0, y0 = self.origin
        tx, ty = self.tangent
        nx, ny = self.normal
        return (x0 + s * tx + d * nx, y0 + s * ty + d * ny)

    def to_local(self, x: float, y: float) -> Tuple[float, float]:
        """
        Projeta um ponto global (X, Y) para o sistema local (s, d) da linha de corte (LF01).
        """
        x0, y0 = self.origin
        dx = x - x0
        dy = y - y0
        tx, ty = self.tangent
        nx, ny = self.normal
        s = dx * tx + dy * ty
        d = dx * nx + dy * ny
        return (s, d)

