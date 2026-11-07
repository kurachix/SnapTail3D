"""
Entidade do Modelo 3D da Peça e Geometria Funcional (RN01, RN08).
Papel do Módulo: Armazenar a representação híbrida (B-Rep 3D + Contornos 2D + Furos Internos) da peça carregada.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

Point2D = Tuple[float, float]
Polygon2D = List[Point2D]


@dataclass
class HoleFeature:
    """
    Representa um furo de parafuso, rasgo oblongo ou cavidade interna da peça (RN01).
    Pode ser definido por centro/raio (circular) e/ou polígono fechado.
    """

    center: Point2D
    radius_mm: float
    polygon: Polygon2D = field(default_factory=list)
    label: str = "Furo"


@dataclass
class BoundingBox3D:
    """Caixa delimitadora 3D alinhada aos eixos (AABB)."""

    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    @property
    def size_x(self) -> float:
        return self.xmax - self.xmin

    @property
    def size_y(self) -> float:
        return self.ymax - self.ymin

    @property
    def size_z(self) -> float:
        return self.zmax - self.zmin

    @property
    def center_2d(self) -> Point2D:
        return ((self.xmin + self.xmax) * 0.5, (self.ymin + self.ymax) * 0.5)

    @property
    def corners_2d(self) -> List[Point2D]:
        """Os 4 cantos do BoundingBox no plano XY (LF01)."""
        return [
            (self.xmin, self.ymin),
            (self.xmax, self.ymin),
            (self.xmax, self.ymax),
            (self.xmin, self.ymax),
        ]


@dataclass
class PartModel:
    """
    Modelo completo da peça estrutural carregada no SnapTail3D Studio.
    Mantém o caminho original imutável (RN09) e metadados de normalização de escala (RN08).
    """

    name: str
    source_path: Optional[str]
    bbox: BoundingBox3D
    outer_contour: Polygon2D
    holes: List[HoleFeature] = field(default_factory=list)
    scale_factor_applied: float = 1.0
    scale_unit_warning: Optional[str] = None
    cq_workplane: Optional[Any] = None  # Objeto CadQuery B-Rep quando disponível
    extra_contours: List[Polygon2D] = field(default_factory=list)

    @property
    def all_outer_polygons(self) -> List[Polygon2D]:
        if self.extra_contours:
            return [self.outer_contour] + self.extra_contours
        return [self.outer_contour]

