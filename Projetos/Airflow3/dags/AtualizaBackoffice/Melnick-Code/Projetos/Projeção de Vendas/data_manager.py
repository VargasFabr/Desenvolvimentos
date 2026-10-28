from dataclasses import dataclass
from typing import Dict, List, Optional

from projection_models import AnnualTotals, MonthlyPoint, ProjectionSeries


@dataclass
class Torre:
    id: str
    nome: str
    segmento: str
    total_unidades: int


@dataclass
class Empreendimento:
    id: str
    nome: str
    segmento: str
    total_unidades: int
    torres: Dict[str, Torre]


@dataclass
class ProjecaoMeta:
    id: str
    nome: str
    tipo: str
    updated_at: Optional[str]


__all__ = [
    "AnnualTotals",
    "MonthlyPoint",
    "ProjectionSeries",
    "Torre",
    "Empreendimento",
    "ProjecaoMeta",
]

