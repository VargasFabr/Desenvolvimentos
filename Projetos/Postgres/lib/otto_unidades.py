"""Fetch e mapeamento de unidades Otto → cad.unidades."""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from lib.cad_parsers import codigo_interno
from lib.unidade_parsers import UnidadeImportRow

OTTO_FETCH_SQL = """
SELECT
    u.id::text AS otto_unit_id,
    u.number,
    u.floor,
    u.useful_area,
    u.rooms,
    u.parking_space_quantity,
    u.integration_id,
    b.integration_id AS building_integration_id,
    b.id::text AS otto_building_id,
    r.integration_id AS realty_integration_id,
    ut.name AS unit_type
FROM unit u
JOIN building b ON b.id = u.building_id
JOIN realty r ON r.id = b.realty_id
LEFT JOIN unit_type ut ON ut.id = u.unit_type_id
WHERE r.integration_id IS NOT NULL
  AND btrim(r.integration_id) <> ''
  AND u.number IS NOT NULL
  AND btrim(u.number) <> ''
"""


def otto_dsn() -> dict[str, Any]:
    password = os.getenv("OTTO_DB_PASS") or os.getenv("OTTO_DB_PASSWORD") or ""
    return {
        "host": os.getenv("OTTO_DB_HOST", "localhost"),
        "port": int(os.getenv("OTTO_DB_PORT", "5432")),
        "dbname": os.getenv("OTTO_DB_NAME", "otto"),
        "user": os.getenv("OTTO_DB_USER", "postgres"),
        "password": password,
        "connect_timeout": int(os.getenv("OTTO_DB_CONNECT_TIMEOUT", "10")),
    }


def parse_spe(realty_integration_id: str | None) -> str | None:
    if not realty_integration_id:
        return None
    spe = str(realty_integration_id).split("|")[0].strip()
    return spe or None


def parse_cod_torre(building_integration_id: str | None, spe: str) -> str | None:
    bid = (building_integration_id or "").strip()
    if not bid or not spe or not bid.endswith(spe):
        return None
    cod = bid[: -len(spe)]
    return cod if cod else None


def _cod_torre_candidates(cod: str) -> list[str]:
    c = cod.strip()
    if not c:
        return []
    out = [c]
    stripped = c.lstrip("0") or "0"
    if stripped not in out:
        out.append(stripped)
    padded = stripped.zfill(3)
    if padded not in out:
        out.append(padded)
    return out


@dataclass
class OttoSyncStats:
    total_otto: int = 0
    mapeadas: int = 0
    sem_torre: int = 0
    parse_erro: int = 0
    importados: int = 0
    erros: list[dict[str, Any]] | None = None


def fetch_otto_units(spe_filter: str | None = None) -> list[dict[str, Any]]:
    cfg = otto_dsn()
    if not cfg["password"]:
        raise RuntimeError("Configure OTTO_DB_PASSWORD ou OTTO_DB_PASS")
    sql = OTTO_FETCH_SQL
    params: list[Any] = []
    if spe_filter:
        sql += " AND split_part(r.integration_id, '|', 1) = %s"
        params.append(spe_filter.strip())
    sql += " ORDER BY r.integration_id, b.integration_id, u.number"
    conn = psycopg2.connect(**cfg)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def otto_row_to_import(row: dict[str, Any], linha: int, torre_index: dict[str, tuple[str, str, str]]) -> UnidadeImportRow | None:
    spe = parse_spe(row.get("realty_integration_id"))
    cod_raw = parse_cod_torre(row.get("building_integration_id"), spe or "")
    if not spe or not cod_raw:
        return None
    codigo_interno_torre = None
    cod_torre = cod_raw
    for cand in _cod_torre_candidates(cod_raw):
        ci = codigo_interno(spe, cand, 1)
        if ci in torre_index:
            codigo_interno_torre = ci
            cod_torre = cand
            break
    if not codigo_interno_torre:
        for cand in _cod_torre_candidates(cod_raw):
            key = f"{spe}|{cand}"
            if key in torre_index:
                codigo_interno_torre = torre_index[key][2]
                cod_torre = cand
                break
    if not codigo_interno_torre:
        return None

    useful = row.get("useful_area")
    return UnidadeImportRow(
        linha=linha,
        spe=spe,
        cod_torre=cod_torre,
        fase=1,
        codigo_interno_torre=codigo_interno_torre,
        nome=str(row["number"]).strip(),
        andar=str(row["floor"]) if row.get("floor") is not None else None,
        area_privativa=Decimal(str(useful)) if useful is not None else None,
        tipo=(row.get("unit_type") or "").strip() or None,
        dormitorios=int(row["rooms"]) if row.get("rooms") is not None else None,
        vagas=Decimal(str(row["parking_space_quantity"])) if row.get("parking_space_quantity") is not None else None,
        id_gc=(row.get("integration_id") or "").strip() or None,
        otto_unit_id=row.get("otto_unit_id"),
    )


def load_torre_index(cur) -> dict[str, tuple[str, str, str]]:
    """codigo_interno e spe|cod_torre → (id_torre, id_emp, codigo_interno)."""
    cur.execute(
        """
        SELECT t.id::text, t.id_empreendimento::text, t.codigo_interno, t.cod_torre, e.cod_spe
        FROM cad.torres t
        JOIN cad.empreendimentos e ON e.id = t.id_empreendimento
        """
    )
    index: dict[str, tuple[str, str, str]] = {}
    for r in cur.fetchall():
        tid, eid, ci, ct, spe = r["id"], r["id_empreendimento"], r["codigo_interno"], r["cod_torre"], r["cod_spe"]
        index[ci] = (tid, eid, ci)
        index[f"{spe}|{ct}"] = (tid, eid, ci)
    return index


def preview_otto_sync(melnick_conn, spe_filter: str | None = None) -> OttoSyncStats:
    rows = fetch_otto_units(spe_filter)
    stats = OttoSyncStats(total_otto=len(rows), erros=[])
    with melnick_conn.cursor(cursor_factory=RealDictCursor) as cur:
        torre_index = load_torre_index(cur)
    for i, row in enumerate(rows, start=1):
        item = otto_row_to_import(row, i, torre_index)
        if item is None:
            if not parse_spe(row.get("realty_integration_id")) or not parse_cod_torre(
                row.get("building_integration_id"), parse_spe(row.get("realty_integration_id")) or ""
            ):
                stats.parse_erro += 1
            else:
                stats.sem_torre += 1
        else:
            stats.mapeadas += 1
    return stats


def sync_otto_units(melnick_conn, spe_filter: str | None = None) -> OttoSyncStats:
    from lib.unidade_service import upsert_otto_unidade_row

    rows = fetch_otto_units(spe_filter)
    stats = OttoSyncStats(total_otto=len(rows), erros=[])
    with melnick_conn:
        with melnick_conn.cursor(cursor_factory=RealDictCursor) as cur:
            torre_index = load_torre_index(cur)
            for i, row in enumerate(rows, start=1):
                item = otto_row_to_import(row, i, torre_index)
                if item is None:
                    if not parse_spe(row.get("realty_integration_id")):
                        stats.parse_erro += 1
                    else:
                        stats.sem_torre += 1
                    continue
                torre = torre_index.get(item.codigo_interno_torre)
                if not torre:
                    stats.sem_torre += 1
                    continue
                id_torre, id_emp, _ = torre
                upsert_otto_unidade_row(cur, item, id_torre, id_emp)
                stats.importados += 1
    stats.mapeadas = stats.importados
    return stats
