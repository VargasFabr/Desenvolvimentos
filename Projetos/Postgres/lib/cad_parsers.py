"""Parsers e normalização de linhas CSV/Excel do cadastro."""
from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
MELNICK_INCORPORADORA_ID = "19395617-559c-44c8-b738-0fca9f04141f"

EXCEL_COLUMNS = [
    "Empreendimento",
    "SPE",
    "Torre",
    "Cód. Torre",
    "Fase",
    "Segmento",
    "Estágio",
    "Empresa",
    "Principal?",
    "Permutante?",
    "Lançamento",
    "Entrega",
    "VGV Bruto",
    "VGV Líquido",
    "Unidades",
    "ID Órulo",
    "Logradouro",
    "Número",
    "Bairro",
    "Cidade",
    "CEP",
    "Coordenada",
]

HEADER_ALIASES = {
    "cod. torre": "Cód. Torre",
    "cod torre": "Cód. Torre",
    "codigo torre": "Cód. Torre",
    "id orulo": "ID Órulo",
    "id órulo": "ID Órulo",
    "vgv bruto": "VGV Bruto",
    "vgv liquido": "VGV Líquido",
    "vgv líquido": "VGV Líquido",
    "principal?": "Principal?",
    "permutante?": "Permutante?",
    "inicio da obra": "Início da obra",
    "início da obra": "Início da obra",
}


def uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{key}"))


def parse_bool(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if s in ("sim", "s", "true", "1", "yes"):
        return True
    if s in ("não", "nao", "n", "false", "0", "no"):
        return False
    return None


def parse_bool_default(raw: Any, default: bool = False) -> bool:
    val = parse_bool(raw)
    return val if val is not None else default


def parse_date(raw: Any) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_money(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw))
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_int(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        return None


def parse_coord(raw: Any) -> tuple[float | None, float | None]:
    s = str(raw or "").strip().strip('"')
    if not s:
        return None, None
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None, None


def parse_tags(raw: Any) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    s = str(raw).strip()
    if not s:
        return []
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return [s]


def parse_fase(raw: Any) -> int:
    if raw is None or str(raw).strip() == "":
        return 1
    return int(float(str(raw).replace(",", ".")))


def codigo_interno(spe: str, cod_torre: str, fase: int) -> str:
    return f"{spe.strip()}-{cod_torre.strip()}-F{fase}"


def codigo_unidade(codigo_interno_torre: str, nome: str) -> str:
    """Chave de negócio da unidade: {spe}-{cod_torre}-F{fase}-{nome} (ex. 8190-001-F1-101)."""
    return f"{codigo_interno_torre.strip()}-{nome.strip()}"


def codigo_unidade_parts(spe: str, cod_torre: str, fase: int, nome: str) -> str:
    return codigo_unidade(codigo_interno(spe, cod_torre, fase), nome)


def normalize_header(name: str) -> str:
    key = name.replace("\ufeff", "").strip()
    low = key.lower()
    if "torre" in low and low.startswith("c"):
        return "Cód. Torre"
    return HEADER_ALIASES.get(low, key)


def normalize_row(raw: dict[str, Any]) -> dict[str, str]:
    return {normalize_header(k): str(v) if v is not None else "" for k, v in raw.items()}


@dataclass
class TorreImportRow:
    linha: int
    empreendimento: str
    spe: str
    torre: str | None
    cod_torre: str
    fase: int
    codigo_interno: str
    segmento: str | None = None
    estagio: str | None = None
    tipo_empresa: str | None = None
    principal: bool = False
    permutante: bool = False
    lancamento: date | None = None
    entrega: date | None = None
    inicio_obra: date | None = None
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
    tags: list = field(default_factory=list)


@dataclass
class ValidationIssue:
    linha: int
    campo: str | None
    mensagem: str
    tipo: str = "erro"  # erro | aviso


def row_dict_to_import(linha: int, row: dict[str, Any]) -> TorreImportRow:
    r = normalize_row(row)
    spe = (r.get("SPE") or "").strip()
    cod_torre = (r.get("Cód. Torre") or "").strip()
    fase = parse_fase(r.get("Fase", ""))
    lat, lon = parse_coord(r.get("Coordenada", ""))
    return TorreImportRow(
        linha=linha,
        empreendimento=(r.get("Empreendimento") or "").strip(),
        spe=spe,
        torre=(r.get("Torre") or "").strip() or None,
        cod_torre=cod_torre,
        fase=fase,
        codigo_interno=codigo_interno(spe, cod_torre, fase),
        segmento=(r.get("Segmento") or "").strip() or None,
        estagio=(r.get("Estágio") or "").strip() or None,
        tipo_empresa=(r.get("Empresa") or "").strip() or None,
        principal=parse_bool_default(r.get("Principal?", "")),
        permutante=parse_bool_default(r.get("Permutante?", "")),
        lancamento=parse_date(r.get("Lançamento", "")),
        entrega=parse_date(r.get("Entrega", "")),
        inicio_obra=parse_date(r.get("Início da obra", "")),
        vgv_bruto=parse_money(r.get("VGV Bruto", "")),
        vgv_liquido=parse_money(r.get("VGV Líquido", "")),
        unidades_total=parse_int(r.get("Unidades", "")),
        id_orulo=(r.get("ID Órulo") or "").strip() or None,
        logradouro=(r.get("Logradouro") or "").strip() or None,
        numero=(r.get("Número") or "").strip() or None,
        bairro=(r.get("Bairro") or "").strip() or None,
        cidade=(r.get("Cidade") or "").strip() or None,
        cep=(r.get("CEP") or "").strip() or None,
        latitude=lat,
        longitude=lon,
        tags=parse_tags(r.get("Tags", "")),
    )


def parse_csv_bytes(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        row = normalize_row({k: v for k, v in raw.items()})
        if (row.get("SPE") or "").strip():
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
        if (row.get("SPE") or "").strip():
            rows.append(row)
    wb.close()
    return rows


def validate_import_rows(rows: list[TorreImportRow]) -> tuple[list[TorreImportRow], list[ValidationIssue]]:
    valid: list[TorreImportRow] = []
    issues: list[ValidationIssue] = []
    spe_names: dict[str, str] = {}
    keys_seen: dict[str, int] = {}

    for item in rows:
        if not item.spe:
            issues.append(ValidationIssue(item.linha, "SPE", "SPE obrigatório"))
            continue
        if not item.cod_torre:
            issues.append(ValidationIssue(item.linha, "Cód. Torre", "Código da torre obrigatório"))
            continue
        if not item.empreendimento:
            issues.append(ValidationIssue(item.linha, "Empreendimento", "Nome do empreendimento obrigatório"))
            continue
        if item.spe in spe_names and spe_names[item.spe] != item.empreendimento:
            issues.append(
                ValidationIssue(
                    item.linha,
                    "Empreendimento",
                    f"SPE {item.spe} já usado com nome '{spe_names[item.spe]}'",
                )
            )
            continue
        spe_names[item.spe] = item.empreendimento
        if item.codigo_interno in keys_seen:
            issues.append(
                ValidationIssue(
                    item.linha,
                    "Cód. Torre",
                    f"Chave duplicada no arquivo (linha {keys_seen[item.codigo_interno]})",
                )
            )
            continue
        keys_seen[item.codigo_interno] = item.linha
        valid.append(item)
    return valid, issues


def rows_from_raw_dicts(raw_rows: list[dict[str, Any]], start_line: int = 2) -> list[TorreImportRow]:
    return [row_dict_to_import(start_line + i, r) for i, r in enumerate(raw_rows)]


if __name__ == "__main__":
    assert codigo_interno("8190", "001", 1) == "8190-001-F1"
    assert codigo_unidade("8190-001-F1", "101") == "8190-001-F1-101"
    assert codigo_unidade_parts("8190", "001", 1, "101") == "8190-001-F1-101"
