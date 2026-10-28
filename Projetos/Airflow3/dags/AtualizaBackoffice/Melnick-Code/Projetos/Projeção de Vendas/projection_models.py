from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class MonthlyPoint:
    data: str
    vendas: float = 0.0
    distratos: float = 0.0
    estoque_inicial: float = 0.0
    origem_estoque_inicial: Optional[str] = None

    @staticmethod
    def from_dict(raw: dict) -> "MonthlyPoint":
        return MonthlyPoint(
            data=str(raw.get("data", "")),
            vendas=float(raw.get("vendas", 0) or 0),
            distratos=float(raw.get("distratos", 0) or 0),
            estoque_inicial=float(raw.get("estoque_inicial", 0) or 0),
            origem_estoque_inicial=raw.get("origem_estoque_inicial"),
        )

    def to_dict(self) -> dict:
        payload = {
            "data": self.data,
            "vendas": self.vendas,
            "distratos": self.distratos,
            "estoque_inicial": self.estoque_inicial,
        }
        if self.origem_estoque_inicial is not None:
            payload["origem_estoque_inicial"] = self.origem_estoque_inicial
        return payload


@dataclass
class AnnualTotals:
    vendas: float = 0.0
    distratos: float = 0.0
    estoque_inicial: float = 0.0

    @staticmethod
    def from_dict(raw: dict) -> "AnnualTotals":
        return AnnualTotals(
            vendas=float(raw.get("vendas", 0) or 0),
            distratos=float(raw.get("distratos", 0) or 0),
            estoque_inicial=float(raw.get("estoque_inicial", 0) or 0),
        )

    def to_dict(self) -> dict:
        return {
            "vendas": self.vendas,
            "distratos": self.distratos,
            "estoque_inicial": self.estoque_inicial,
        }


@dataclass
class ProjectionSeries:
    projeto_id: str
    empreendimento_id: str
    torre_id: str
    ciclo: str
    serie: List[MonthlyPoint]
    indice_data: Dict[str, int]
    anuais: Dict[str, AnnualTotals]

    @staticmethod
    def from_dict(raw: dict) -> "ProjectionSeries":
        serie_raw = raw.get("serie", []) if isinstance(raw.get("serie"), list) else []
        serie = [MonthlyPoint.from_dict(entry) for entry in serie_raw if isinstance(entry, dict)]
        indice_data_raw = raw.get("indice_data") if isinstance(raw.get("indice_data"), dict) else {}
        if indice_data_raw is None:
            indice_data_raw = {}
        anuais_raw = raw.get("anuais") if isinstance(raw.get("anuais"), dict) else {}
        if anuais_raw is None:
            anuais_raw = {}
        anuais = {
            str(year): AnnualTotals.from_dict(values)
            for year, values in anuais_raw.items()
            if isinstance(values, dict)
        }
        indice_data: Dict[str, int] = {}
        for key, value in indice_data_raw.items():
            try:
                indice_data[str(key)] = int(value)
            except (TypeError, ValueError):
                continue

        return ProjectionSeries(
            projeto_id=str(raw.get("projeto_id", "")),
            empreendimento_id=str(raw.get("empreendimento_id", "")),
            torre_id=str(raw.get("torre_id", "")),
            ciclo=str(raw.get("ciclo", "")),
            serie=serie,
            indice_data=indice_data,
            anuais=anuais,
        )

    def to_dict(self) -> dict:
        return {
            "projeto_id": self.projeto_id,
            "empreendimento_id": self.empreendimento_id,
            "torre_id": self.torre_id,
            "ciclo": self.ciclo,
            "serie": [entry.to_dict() for entry in self.serie],
            "indice_data": self.indice_data,
            "anuais": {year: totals.to_dict() for year, totals in self.anuais.items()},
        }
