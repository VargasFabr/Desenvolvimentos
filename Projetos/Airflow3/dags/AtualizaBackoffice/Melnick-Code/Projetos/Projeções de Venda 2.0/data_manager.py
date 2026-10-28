# Gerenciador de dados para as projeções de venda

__all__ = [
    "Torre",
    "Empreendimento",
    "Projecao",
    "Serie",
    "ItemSerie",
]

from dataclasses import dataclass
from typing import Literal, List, TypedDict

@dataclass
class Torre:
    id: int
    nome: str
    segmento: str
    total_unidades: int

@dataclass
class Empreendimento:
    id: int
    nome: str
    #segmento: str
    total_unidades: int
    torres: List[Torre]


@dataclass
class Projecao:
    id: int
    nome: str
    categoria: Literal["viabilidade", "realizado", "projecao"]
    tipo: Literal["Comitê", "Comercial", "Meta"]
    ultima_atualizacao: str # YYYY-MM-DD
    series: List[Serie]

@dataclass
class Serie:
    id_empreendimento: int
    id_torre: int
    id_projecao: int
    serie: List[ItemSerie] # Exemplo: [{"data": "2024-01", "vendas": 10}, {"data": "2024-02", "vendas": 15}]

class ItemSerie(TypedDict):
    data: str # YYYY-MM
    estoque_inicial: float
    vendas: float
    distratos: float
    estoque_final: float




