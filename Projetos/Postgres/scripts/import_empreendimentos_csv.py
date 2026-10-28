#!/usr/bin/env python3
"""Gera cadastro/04_seed_controladoria.sql a partir de fontes/Empreendimentos.csv."""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.cad_parsers import (  # noqa: E402
    MELNICK_INCORPORADORA_ID,
    codigo_interno,
    parse_date,
    parse_fase,
    parse_int,
    parse_money,
    parse_tags,
    uid,
    normalize_row,
)

CSV_PATH = ROOT / "fontes" / "Empreendimentos.csv"
OUT_PATH = ROOT / "cadastro" / "04_seed_controladoria.sql"
MELNICK_INC_ID = MELNICK_INCORPORADORA_ID


def sql_str(val: str | date | None) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, date):
        return f"'{val.isoformat()}'"
    return "'" + str(val).replace("'", "''") + "'"


def sql_bool(val: bool | None) -> str:
    if val is None:
        return "NULL"
    return "true" if val else "false"


def sql_bool_default(raw: str, default: bool = False) -> str:
    from lib.cad_parsers import parse_bool

    val = parse_bool(raw)
    return "true" if (val if val is not None else default) else "false"


def sql_num(val: Decimal | int | float | None) -> str:
    if val is None:
        return "NULL"
    return str(val)


def load_rows() -> list[dict]:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for raw in reader:
            row = normalize_row({k: v for k, v in raw.items()})
            if (row.get("SPE") or "").strip():
                rows.append(row)
        return rows


def main() -> None:
    rows = load_rows()
    lines: list[str] = [
        "-- Gerado por scripts/import_empreendimentos_csv.py",
        f"-- Linhas CSV: {len(rows)}",
        "BEGIN;",
        "",
    ]

    estados = {"RS": uid("estado", "RS")}
    lines.append(
        f"INSERT INTO cad.estados (id, sigla, nome) VALUES "
        f"({sql_str(estados['RS'])}, 'RS', 'Rio Grande do Sul') ON CONFLICT (sigla) DO NOTHING;"
    )

    cidades: dict[str, str] = {}
    for row in rows:
        cidade = (row.get("Cidade") or "").strip()
        if cidade and cidade not in cidades:
            cidades[cidade] = uid("cidade", cidade)
            lines.append(
                f"INSERT INTO cad.cidades (id, nome, id_estado) VALUES "
                f"({sql_str(cidades[cidade])}, {sql_str(cidade)}, {sql_str(estados['RS'])}) "
                f"ON CONFLICT (nome, id_estado) DO NOTHING;"
            )

    by_spe: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_spe[row["SPE"].strip()].append(row)

    emp_ids: dict[str, str] = {}
    for spe, group in sorted(by_spe.items(), key=lambda x: x[0]):
        sample = group[0]
        emp_id = uid("empreendimento", spe)
        emp_ids[spe] = emp_id
        from lib.cad_parsers import parse_coord

        lat, lon = parse_coord(sample.get("Coordenada", ""))
        cidade = (sample.get("Cidade") or "").strip()
        id_cidade = sql_str(cidades[cidade]) if cidade in cidades else "NULL"
        lines.append(
            f"INSERT INTO cad.empreendimentos (id, cod_spe, nome_comercial, id_incorporadora, "
            f"id_cidade, endereco_logradouro, endereco_numero, endereco_bairro, endereco_cep, "
            f"latitude, longitude, empresa_parceira) VALUES ("
            f"{sql_str(emp_id)}, {sql_str(spe)}, {sql_str(sample['Empreendimento'].strip())}, "
            f"{sql_str(MELNICK_INC_ID)}, {id_cidade}, "
            f"{sql_str((sample.get('Logradouro') or '').strip() or None)}, "
            f"{sql_str((sample.get('Número') or '').strip() or None)}, "
            f"{sql_str((sample.get('Bairro') or '').strip() or None)}, "
            f"{sql_str((sample.get('CEP') or '').strip() or None)}, "
            f"{sql_num(lat)}, {sql_num(lon)}, NULL"
            f") ON CONFLICT (cod_spe) DO UPDATE SET nome_comercial = EXCLUDED.nome_comercial, atualizado_em = now();"
        )
        for sistema in ("gc", "controladoria"):
            lines.append(
                f"INSERT INTO cad.identificadores_externos (entidade_tipo, entidade_id, sistema, id_externo) "
                f"VALUES ('empreendimento', {sql_str(emp_id)}, '{sistema}', {sql_str(spe)}) "
                f"ON CONFLICT (sistema, id_externo) DO NOTHING;"
            )
        lines.append(
            f"INSERT INTO cad.aliases (entidade_tipo, entidade_id, alias, fonte) "
            f"VALUES ('empreendimento', {sql_str(emp_id)}, {sql_str(sample['Empreendimento'].strip())}, 'controladoria') "
            f"ON CONFLICT DO NOTHING;"
        )

    fase_ids: dict[tuple[str, int], str] = {}
    fase_keys = sorted({(r["SPE"].strip(), parse_fase(r.get("Fase", ""))) for r in rows})
    for spe, num in fase_keys:
        fid = uid("fase", f"{spe}-{num}")
        fase_ids[(spe, num)] = fid
        group = [r for r in rows if r["SPE"].strip() == spe and parse_fase(r.get("Fase", "")) == num]
        sample = group[0]
        lines.append(
            f"INSERT INTO cad.fases (id, id_empreendimento, numero_fase, nome_fase, lancamento, entrega, inicio_obra) "
            f"VALUES ({sql_str(fid)}, {sql_str(emp_ids[spe])}, {num}, {sql_str(f'Fase {num}')}, "
            f"{sql_str(parse_date(sample.get('Lançamento', '')))}, "
            f"{sql_str(parse_date(sample.get('Entrega', '')))}, "
            f"{sql_str(parse_date(sample.get('Início da obra', '')))}) "
            f"ON CONFLICT (id_empreendimento, numero_fase) DO NOTHING;"
        )

    for row in rows:
        spe = row["SPE"].strip()
        cod_torre = row["Cód. Torre"].strip()
        fase = parse_fase(row.get("Fase", ""))
        ci = codigo_interno(spe, cod_torre, fase)
        torre_id = uid("torre", ci)
        emp_id = emp_ids[spe]
        fase_id = fase_ids[(spe, fase)]
        nome_emp = row["Empreendimento"].strip()
        nome_torre = (row.get("Torre") or "").strip() or None
        tags = parse_tags(row.get("Tags", ""))
        lines.append(
            f"INSERT INTO cad.torres (id, codigo_interno, cod_torre, nome_torre, id_empreendimento, id_fase, "
            f"segmento, estagio, tipo_empresa, principal, permutante, lancamento, entrega, inicio_obra, "
            f"vgv_bruto, vgv_liquido, unidades_total, id_orulo, tags) VALUES ("
            f"{sql_str(torre_id)}, {sql_str(ci)}, {sql_str(cod_torre)}, {sql_str(nome_torre)}, "
            f"{sql_str(emp_id)}, {sql_str(fase_id)}, "
            f"{sql_str((row.get('Segmento') or '').strip() or None)}, "
            f"{sql_str((row.get('Estágio') or '').strip() or None)}, "
            f"{sql_str((row.get('Empresa') or '').strip() or None)}, "
            f"{sql_bool_default(row.get('Principal?', ''))}, "
            f"{sql_bool_default(row.get('Permutante?', ''))}, "
            f"{sql_str(parse_date(row.get('Lançamento', '')))}, "
            f"{sql_str(parse_date(row.get('Entrega', '')))}, "
            f"{sql_str(parse_date(row.get('Início da obra', '')))}, "
            f"{sql_num(parse_money(row.get('VGV Bruto', '')))}, "
            f"{sql_num(parse_money(row.get('VGV Líquido', '')))}, "
            f"{sql_num(parse_int(row.get('Unidades', '')))}, "
            f"{sql_str((row.get('ID Órulo') or '').strip() or None)}, "
            f"{sql_str(json.dumps(tags, ensure_ascii=False))}::jsonb"
            f") ON CONFLICT (codigo_interno) DO UPDATE SET nome_torre = EXCLUDED.nome_torre, atualizado_em = now();"
        )
        lines.append(
            f"INSERT INTO cad.aliases (entidade_tipo, entidade_id, alias, fonte) "
            f"VALUES ('torre', {sql_str(torre_id)}, {sql_str(nome_emp)}, 'controladoria') ON CONFLICT DO NOTHING;"
        )
        if nome_torre:
            lines.append(
                f"INSERT INTO cad.aliases (entidade_tipo, entidade_id, alias, fonte) "
                f"VALUES ('torre', {sql_str(torre_id)}, {sql_str(f'{nome_emp} {nome_torre}')}, 'controladoria') "
                f"ON CONFLICT DO NOTHING;"
            )
        orulo = (row.get("ID Órulo") or "").strip()
        if orulo:
            lines.append(
                f"INSERT INTO cad.identificadores_externos (entidade_tipo, entidade_id, sistema, id_externo) "
                f"VALUES ('torre', {sql_str(torre_id)}, 'orulo', {sql_str(orulo)}) "
                f"ON CONFLICT (sistema, id_externo) DO NOTHING;"
            )

    lines.extend(["", "COMMIT;"])
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {len(rows)} torres, {len(by_spe)} empreendimentos -> {OUT_PATH}")


if __name__ == "__main__":
    main()
