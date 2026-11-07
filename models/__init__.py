"""Pacote de modelos de domínio e estruturas de dados."""

from models.cut_line import CutLine, Point2D
from models.dovetail_params import DovetailParams
from models.part_model import BoundingBox3D, HoleFeature, PartModel, Polygon2D
from models.validation_report import CutValidationReport, HalfNestingResult, ToothCandidateInfo

__all__ = [
    "BoundingBox3D",
    "CutLine",
    "CutValidationReport",
    "DovetailParams",
    "HalfNestingResult",
    "HoleFeature",
    "PartModel",
    "Point2D",
    "Polygon2D",
    "ToothCandidateInfo",
]

