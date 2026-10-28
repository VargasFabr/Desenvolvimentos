"""Parsers e validação de import Excel/CSV de unidades."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from lib.cad_parsers import codigo_interno, normalize_header, normalize_row, parse_fase

EXCEL_COLUMNS = [
    "SPE",
    "Cód. Torre",
    "Fase",
    "Unidade",
    "Andar",
    "Área privativa",
    "Fração ideal",
    "Tipo",
    "Dormitórios",
    "Vagas",
    "ID GC",
]


@dataclass
class UnidadeImportRow:
    linha: int
    spe: str
    cod_torre: str
    fase: int
    codigo_interno_torre: str
    nome: str
    andar: str | None = None
    area_privativa: Decimal | None = None
    fracao_ideal: Decimal | None = None
    tipo: str | None = None
    dormitorios: int | None = None
    vagas: Decimal | None = None
    id_gc: str | None = None
    otto_unit_id: str | None = None


@dataclass
class ValidationIssue:
    linha: int
    campo: str | None
    mensagem: str
    tipo: str = "erro"


def _dec(raw: Any) -> Decimal | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return Decimal(str(raw).replace(",", "."))
    except InvalidOperation:
        return None


def _int(raw: Any) -> int | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(float(str(raw).replace(",", ".")))
    except ValueError:
        return None


def row_dict_to_import(linha: int, row: dict[str, Any]) -> UnidadeImportRow:
    r = normalize_row(row)
    spe = (r.get("SPE") or "").strip()
    cod_torre = (r.get("Cód. Torre") or "").strip()
    fase = parse_fase(r.get("Fase", ""))
    return UnidadeImportRow(
        linha=linha,
        spe=spe,
        cod_torre=cod_torre,
        fase=fase,
        codigo_interno_torre=codigo_interno(spe, cod_torre, fase),
        nome=(r.get("Unidade") or "").strip(),
        andar=(r.get("Andar") or "").strip() or None,
        area_privativa=_dec(r.get("Área privativa", "")),
        fracao_ideal=_dec(r.get("Fração ideal", "")),
        tipo=(r.get("Tipo") or "").strip() or None,
        dormitorios=_int(r.get("Dormitórios", "")),
        vagas=_dec(r.get("Vagas", "")),
        id_gc=(r.get("ID GC") or "").strip() or None,
    )


def parse_csv_bytes(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        row = normalize_row({k: v for k, v in raw.items()})
        if (row.get("SPE") or "").strip() and (row.get("Unidade") or "").strip():
            rows.append(row)
    return rows


def parse_excel_bytes(content: bytes) -> list[dict[str, str]]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return []
    headers: list[str] | None = None
    rows: list[dict[str, str]] = []
    for i, row_cells in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [normalize_header(str(c or "")) for c in row_cells]
            continue
        if not headers:
            break
        row = {headers[j]: str(v) if v is not None else "" for j, v in enumerate(row_cells) if j < len(headers)}
        if (row.get("SPE") or "").strip() and (row.get("Unidade") or "").strip():
            rows.append(row)
    wb.close()
    return rows


def validate_import_rows(rows: list[UnidadeImportRow]) -> tuple[list[UnidadeImportRow], list[ValidationIssue]]:
    valid: list[UnidadeImportRow] = []
    issues: list[ValidationIssue] = []
    keys: dict[str, int] = {}
    for item in rows:
        if not item.spe:
            issues.append(ValidationIssue(item.linha, "SPE", "SPE obrigatório"))
            continue
        if not item.cod_torre:
            issues.append(ValidationIssue(item.linha, "Cód. Torre", "Código da torre obrigatório"))
            continue
        if not item.nome:
            issues.append(ValidationIssue(item.linha, "Unidade", "Nome da unidade obrigatório"))
            continue
        key = f"{item.codigo_interno_torre}|{item.nome.lower()}"
        if key in keys:
            issues.append(
                ValidationIssue(item.linha, "Unidade", f"Duplicado no arquivo (linha {keys[key]})")
            )
            continue
        keys[key] = item.linha
        valid.append(item)
    return valid, issues


def rows_from_raw_dicts(raw_rows: list[dict[str, Any]], start_line: int = 2) -> list[UnidadeImportRow]:
    return [row_dict_to_import(start_line + i, r) for i, r in enumerate(raw_rows)]
