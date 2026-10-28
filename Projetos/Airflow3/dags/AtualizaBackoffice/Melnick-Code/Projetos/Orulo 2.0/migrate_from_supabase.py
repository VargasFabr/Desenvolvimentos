"""Migração one-shot: tabelas Órulo do Supabase → melnick.orulo.*"""
from __future__ import annotations

import io
import logging
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = PROJECT_DIR.parent.parent
ENV_PATH = REPOSITORY_ROOT.parent / ".env"

sys.path.insert(0, str(REPOSITORY_ROOT))

from orulo_db import (  # noqa: E402
    TABLE_COLUMNS,
    apply_schema_sql,
    connect_melnick,
    count_table,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("OruloMigrate")

TABLES = ["buildings", "typologies", "images", "units", "units_updates"]
JSONB_COLUMNS = {
    "features",
    "associations_typologies",
    "associations_building_units",
}


def load_env() -> None:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    external = os.getenv("ORULO_SUPABASE_ENV_PATH")
    if external and os.path.exists(external):
        load_dotenv(external)


def connect_supabase() -> Any:
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if database_url:
        try:
            return psycopg2.connect(database_url)
        except Exception as exc:
            logger.warning("DATABASE_URL falhou (%s). Tentando pooler...", exc)

    host = (os.getenv("SUPABASE_HOST") or "").strip()
    user = (os.getenv("SUPABASE_USER") or "").strip()
    password = (os.getenv("SUPABASE_PASS") or "").strip()
    dbname = (os.getenv("SUPABASE_DBNAME") or "postgres").strip()
    port = int(os.getenv("SUPABASE_PORT") or "6543")
    if not host or not user or not password:
        raise RuntimeError(
            "Defina DATABASE_URL ou SUPABASE_HOST/SUPABASE_USER/SUPABASE_PASS no .env"
        )
    return psycopg2.connect(
        host=host,
        port=port,
        user=user.strip(),
        password=password,
        dbname=dbname,
    )


def _sql_expr(table_name: str, col: str) -> str:
    if col in JSONB_COLUMNS:
        return f"COALESCE(to_jsonb({col}), 'null'::jsonb)::text AS {col}"
    if col == "lock_edit":
        return f"COALESCE({col}, false) AS {col}"
    if col == "is_active":
        return f"COALESCE({col}, true) AS {col}"
    if col == "available":
        return f"COALESCE({col}, true) AS {col}"
    if table_name == "units_updates" and col == "info_source":
        return f"COALESCE({col}::text, 'orulo') AS {col}"
    if table_name == "buildings" and col == "name":
        return (
            "COALESCE(NULLIF(BTRIM(name), ''), "
            "'building_' || building_id::text) AS name"
        )
    if table_name == "units" and col == "reference":
        return f"COALESCE({col}, '') AS {col}"
    if table_name == "units_updates" and col == "updated_at":
        return f"{col}::date AS {col}"
    if col in {"address_number", "floor", "unit_end"}:
        return f"{col}::text AS {col}"
    return col


def migrate_table(source: Any, dest: Any, table_name: str) -> tuple[int, int]:
    columns = TABLE_COLUMNS[table_name]
    select_list = ", ".join(_sql_expr(table_name, col) for col in columns)

    where = ""
    if table_name == "images":
        where = "WHERE image_id IS NOT NULL"
    elif table_name == "units_updates":
        where = "WHERE updated_at IS NOT NULL"

    copy_out_sql = (
        f'COPY (SELECT {select_list} FROM public."{table_name}" {where}) '
        f"TO STDOUT WITH (FORMAT csv, NULL '\\N')"
    )
    buf = io.BytesIO()
    with source.cursor() as cur:
        cur.copy_expert(copy_out_sql, buf)

    raw = buf.getvalue()
    source_rows = raw.count(b"\n") if raw else 0

    cols_csv = ", ".join(columns)
    copy_in_sql = (
        f"COPY orulo.{table_name} ({cols_csv}) FROM STDIN WITH (FORMAT csv, NULL '\\N')"
    )
    buf.seek(0)
    with dest.cursor() as cur:
        cur.copy_expert(copy_in_sql, buf)
    dest.commit()

    dest_rows = count_table(dest, table_name)
    logger.info("%s: source~%s dest=%s", table_name, source_rows, dest_rows)
    return source_rows, dest_rows


def truncate_orulo_tables(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                orulo.units_updates,
                orulo.units,
                orulo.images,
                orulo.typologies,
                orulo.buildings
            """
        )
    conn.commit()


def main() -> None:
    load_env()
    schema_sql = PROJECT_DIR / "sql" / "01_schema_orulo.sql"

    dest = connect_melnick()
    logger.info("Aplicando DDL em melnick...")
    apply_schema_sql(dest, str(schema_sql))

    source = connect_supabase()
    logger.info("Conectado ao Supabase.")

    logger.info("Truncando schema orulo...")
    truncate_orulo_tables(dest)

    source_counts: dict[str, int] = {}
    dest_counts: dict[str, int] = {}

    for table in TABLES:
        logger.info("Migrando %s via COPY...", table)
        src_count, dst_count = migrate_table(source, dest, table)
        source_counts[table] = src_count
        dest_counts[table] = dst_count

    source.close()
    dest.close()

    logger.info("=== Contagens pós-migração ===")
    ok = True
    for table in TABLES:
        src = source_counts[table]
        dst = dest_counts[table]
        delta = src - dst
        status = "OK" if dst > 0 and abs(delta) < max(10, int(src * 0.01)) else "DIFF"
        if status != "OK":
            ok = False
        logger.info("%s: supabase~%s melnick=%s delta=%s [%s]", table, src, dst, delta, status)

    if not ok:
        raise SystemExit(1)
    logger.info("Migração concluída com sucesso.")


if __name__ == "__main__":
    main()
