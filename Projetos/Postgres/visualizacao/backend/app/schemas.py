from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EmpreendimentoCreate(BaseModel):
    cod_spe: str
    nome_comercial: str
    endereco_logradouro: str | None = None
    endereco_numero: str | None = None
    endereco_bairro: str | None = None
    endereco_cep: str | None = None
    cidade: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class EmpreendimentoUpdate(BaseModel):
    nome_comercial: str | None = None
    endereco_logradouro: str | None = None
    endereco_numero: str | None = None
    endereco_bairro: str | None = None
    endereco_cep: str | None = None
    cidade: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class EmpreendimentoOut(BaseModel):
    id: UUID
    cod_spe: str
    nome_comercial: str
    endereco_logradouro: str | None = None
    endereco_numero: str | None = None
    endereco_bairro: str | None = None
    endereco_cep: str | None = None
    cidade: str | None = None
    uf: str | None = None
    qtd_torres: int | None = None


class FaseCreate(BaseModel):
    id_empreendimento: UUID
    numero_fase: int = Field(ge=1)
    nome_fase: str | None = None
    lancamento: date | None = None
    entrega: date | None = None


class FaseOut(BaseModel):
    id: UUID
    id_empreendimento: UUID
    numero_fase: int
    nome_fase: str | None = None
    lancamento: date | None = None
    entrega: date | None = None


class TorreCreate(BaseModel):
    cod_spe: str
    nome_comercial: str | None = None
    cod_torre: str
    numero_fase: int = Field(default=1, ge=1)
    nome_torre: str | None = None
    segmento: str | None = None
    estagio: str | None = None
    tipo_empresa: str | None = None
    principal: bool = False
    permutante: bool = False
    lancamento: date | None = None
    entrega: date | None = None
    vgv_bruto: Decimal | None = None
    vgv_liquido: Decimal | None = None
    unidades_total: int | None = None
    id_orulo: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    cep: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class TorreUpdate(BaseModel):
    nome_torre: str | None = None
    segmento: str | None = None
    estagio: str | None = None
    tipo_empresa: str | None = None
    principal: bool | None = None
    permutante: bool | None = None
    lancamento: date | None = None
    entrega: date | None = None
    vgv_bruto: Decimal | None = None
    vgv_liquido: Decimal | None = None
    unidades_total: int | None = None
    id_orulo: str | None = None


class TorreOut(BaseModel):
    id_torre: UUID
    codigo_interno: str
    cod_torre: str
    nome_torre: str | None = None
    cod_spe: str
    nome_comercial: str
    numero_fase: int
    segmento: str | None = None
    estagio: str | None = None
    principal: bool
    permutante: bool
    vgv_bruto: Decimal | None = None
    vgv_liquido: Decimal | None = None
    unidades_total: int | None = None
    cidade: str | None = None


class AliasCreate(BaseModel):
    alias: str
    fonte: str = "manual"


class IdentificadorCreate(BaseModel):
    sistema: str
    id_externo: str


class BuscaItem(BaseModel):
    tipo: str
    codigo_interno: str | None = None
    cod_spe: str | None = None
    nome: str
    alias: str | None = None


class DashboardStats(BaseModel):
    empreendimentos: int
    torres: int
    fases: int


class ImportIssue(BaseModel):
    linha: int
    campo: str | None = None
    mensagem: str


class ImportPreviewRow(BaseModel):
    linha: int
    codigo_interno: str
    empreendimento: str
    spe: str
    torre: str | None = None
    cod_torre: str
    fase: int


class ImportPreviewResponse(BaseModel):
    total: int
    validos: int
    erros: list[ImportIssue]
    avisos: list[ImportIssue]
    rows: list[ImportPreviewRow]
    payload: list[dict[str, Any]] = []


class ImportConfirmRequest(BaseModel):
    rows: list[dict[str, Any]]


class UnidadeCreate(BaseModel):
    codigo_interno: str | None = None
    cod_spe: str | None = None
    cod_torre: str | None = None
    numero_fase: int = Field(default=1, ge=1)
    id_torre: UUID | None = None
    nome: str
    andar: str | None = None
    area_privativa: Decimal | None = None
    fracao_ideal: Decimal | None = None
    tipo: str | None = None
    dormitorios: int | None = None
    vagas: Decimal | None = None
    id_gc: str | None = None


class UnidadeUpdate(BaseModel):
    nome: str | None = None
    andar: str | None = None
    area_privativa: Decimal | None = None
    fracao_ideal: Decimal | None = None
    tipo: str | None = None
    dormitorios: int | None = None
    vagas: Decimal | None = None
    id_gc: str | None = None
