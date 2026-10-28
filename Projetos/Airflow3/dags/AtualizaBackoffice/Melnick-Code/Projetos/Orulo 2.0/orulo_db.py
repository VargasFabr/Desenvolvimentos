"""Conexão e I/O Postgres para o schema orulo no banco melnick."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json, RealDictCursor, execute_values

logger = logging.getLogger("OruloPostgres")

ORULO_SCHEMA = os.getenv("ORULO_PG_SCHEMA", "orulo")
ORULO_DB = os.getenv("ORULO_PG_DB", "melnick")

TABLE_COLUMNS: dict[str, list[str]] = {
    "buildings": [
        "building_id",
        "name",
        "created_at",
        "opening_date",
        "launch_date",
        "type",
        "finality",
        "status",
        "stage",
        "developer_id",
        "developer_name",
        "address_street_type",
        "address_street",
        "address_number",
        "address_area",
        "address_city",
        "address_state",
        "address_latitude",
        "address_longitude",
        "opportunity_social_housing_program",
        "default_image_url",
        "features",
        "number_of_towers",
        "number_of_floors",
        "units_per_floor",
        "lock_edit",
        "is_active",
    ],
    "typologies": [
        "building_id",
        "typology_id",
        "type",
        "private_area",
        "total_area",
        "bedrooms",
        "bathrooms",
        "suites",
        "parking",
        "total_units",
        "lock_edit",
    ],
    "images": [
        "image_id",
        "building_id",
        "type",
        "description",
        "associations_typologies",
        "associations_building_units",
        "image_type",
        "image_url",
    ],
    "units": [
        "unit_id",
        "building_id",
        "typology_id",
        "reference",
        "section",
        "floor",
        "unit_end",
        "private_area",
        "lock_edit",
    ],
    "units_updates": [
        "unit_id",
        "updated_at",
        "price",
        "available",
        "lock_edit",
        "info_source",
    ],
}

CONFLICT_COLUMNS: dict[str, list[str]] = {
    "buildings": ["building_id"],
    "typologies": ["building_id", "typology_id"],
    "images": ["image_id"],
    "units": ["unit_id"],
    "units_updates": ["unit_id", "updated_at"],
}

JSONB_COLUMNS = {
    "features",
    "associations_typologies",
    "associations_building_units",
}


def _running_in_docker() -> bool:
    return os.path.exists("/.dockerenv") or bool(os.getenv("AIRFLOW_HOME"))


def _resolve_postgres_host(fallback: str | None = None) -> str:
    explicit = (os.getenv("POSTGRES_HOST") or os.getenv("PGHOST") or "").strip()
    if explicit:
        return explicit

    fallback_host = (fallback or "").strip()
    if fallback_host and fallback_host not in {"localhost", "127.0.0.1"}:
        return fallback_host

    if _running_in_docker():
        return "host.docker.internal"

    return fallback_host or "localhost"


def _postgres_connection_params(
    dbname: str | None = None,
    *,
    host: str | None = None,
    port: str | int | None = None,
    user: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    resolved_user = (user or os.getenv("POSTGRES_USER") or os.getenv("PGUSER") or "").strip()
    resolved_password = (
        password
        or os.getenv("POSTGRES_PASS")
        or os.getenv("POSTGRES_PASSWORD")
        or os.getenv("PGPASSWORD")
        or ""
    ).strip()
    if not resolved_user or not resolved_password:
        raise RuntimeError(
            "Defina POSTGRES_USER e POSTGRES_PASS no .env ou use Airflow connection postgres."
        )

    return {
        "host": _resolve_postgres_host(host),
        "port": int(port or os.getenv("POSTGRES_PORT", "5432")),
        "user": resolved_user,
        "password": resolved_password,
        "dbname": dbname or ORULO_DB,
    }


def connect_melnick(dbname: str | None = None) -> PgConnection:
    if os.environ.get("AIRFLOW_CTX_DAG_ID"):
        try:
            from airflow.providers.postgres.hooks.postgres import PostgresHook

            hook = PostgresHook(postgres_conn_id="postgres")
            conn_meta = hook.get_connection()
            params = _postgres_connection_params(
                dbname=dbname or ORULO_DB,
                host=conn_meta.host,
                port=conn_meta.port,
                user=conn_meta.login,
                password=conn_meta.password,
            )
            return psycopg2.connect(**params)
        except Exception as exc:
            logger.warning("PostgresHook falhou (%s). Tentando env...", exc)

    params = _postgres_connection_params(dbname=dbname or ORULO_DB)
    logger.info(
        "Conectando PostgreSQL em %(host)s:%(port)s db=%(dbname)s",
        params,
    )
    return psycopg2.connect(**params)


def apply_schema_sql(conn: PgConnection, sql_path: str) -> None:
    with open(sql_path, encoding="utf-8") as handle:
        ddl = handle.read()
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


def _normalize_value(column: str, value: Any) -> Any:
    if value is None:
        return None
    if column in JSONB_COLUMNS:
        if isinstance(value, (dict, list)):
            return Json(value)
        if isinstance(value, str):
            try:
                return Json(json.loads(value))
            except (json.JSONDecodeError, TypeError):
                return Json(value)
        return Json(value)
    if isinstance(value, (datetime, date)):
        return value
    return value


def _row_tuple(table_name: str, record: dict[str, Any]) -> tuple[Any, ...]:
    columns = TABLE_COLUMNS[table_name]
    return tuple(_normalize_value(col, record.get(col)) for col in columns)


def upsert_records(
    conn: PgConnection,
    table_name: str,
    records: list[dict[str, Any]],
    *,
    batch_size: int = 300,
) -> None:
    if not records:
        return
    if table_name not in TABLE_COLUMNS:
        raise ValueError(f"Tabela desconhecida: {table_name}")

    columns = TABLE_COLUMNS[table_name]
    conflict_cols = CONFLICT_COLUMNS[table_name]
    update_cols = [c for c in columns if c not in conflict_cols]

    schema_ident = sql.Identifier(ORULO_SCHEMA)
    table_ident = sql.Identifier(table_name)
    col_idents = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
    conflict_idents = sql.SQL(", ").join(sql.Identifier(c) for c in conflict_cols)

    if update_cols:
        set_clause = sql.SQL(", ").join(
            sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(c)) for c in update_cols
        )
        conflict_sql = sql.SQL("ON CONFLICT ({}) DO UPDATE SET {}").format(
            conflict_idents, set_clause
        )
    else:
        conflict_sql = sql.SQL("ON CONFLICT ({}) DO NOTHING").format(conflict_idents)

    insert_sql = sql.SQL("INSERT INTO {}.{} ({}) VALUES %s {}").format(
        schema_ident, table_ident, col_idents, conflict_sql
    )

    safe_batch = max(1, batch_size)
    try:
        with conn.cursor() as cur:
            for start in range(0, len(records), safe_batch):
                batch = records[start : start + safe_batch]
                values = [_row_tuple(table_name, row) for row in batch]
                execute_values(cur, insert_sql.as_string(conn), values, page_size=safe_batch)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# Colunas filtradas como BIGINT (evita bigint = text no ANY)
BIGINT_FILTER_COLUMNS = {
    "building_id",
    "typology_id",
    "image_id",
    "developer_id",
}


def _coerce_filter_values(filter_column: str, filter_values: list[Any]) -> list[Any]:
    if filter_column in BIGINT_FILTER_COLUMNS:
        coerced: list[Any] = []
        for value in filter_values:
            if value is None:
                continue
            coerced.append(int(value))
        return coerced
    return [str(value) for value in filter_values if value is not None]


def fetch_by_filter_values(
    conn: PgConnection,
    table_name: str,
    filter_column: str,
    filter_values: list[Any],
    *,
    batch_size: int = 100,
) -> list[dict[str, Any]]:
    if not filter_values:
        return []
    if table_name not in TABLE_COLUMNS:
        raise ValueError(f"Tabela desconhecida: {table_name}")

    values = _coerce_filter_values(filter_column, filter_values)
    if not values:
        return []

    results: list[dict[str, Any]] = []
    safe_batch = max(1, batch_size)

    if filter_column in BIGINT_FILTER_COLUMNS:
        query = sql.SQL("SELECT * FROM {}.{} WHERE {} = ANY(%s::bigint[])").format(
            sql.Identifier(ORULO_SCHEMA),
            sql.Identifier(table_name),
            sql.Identifier(filter_column),
        )
    else:
        query = sql.SQL("SELECT * FROM {}.{} WHERE {} = ANY(%s::text[])").format(
            sql.Identifier(ORULO_SCHEMA),
            sql.Identifier(table_name),
            sql.Identifier(filter_column),
        )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for start in range(0, len(values), safe_batch):
                batch = values[start : start + safe_batch]
                cur.execute(query, (batch,))
                rows = cur.fetchall()
                results.extend(dict(row) for row in rows)
        return results
    except Exception:
        conn.rollback()
        raise


def count_table(conn: PgConnection, table_name: str) -> int:
    query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
        sql.Identifier(ORULO_SCHEMA),
        sql.Identifier(table_name),
    )
    with conn.cursor() as cur:
        cur.execute(query)
        return int(cur.fetchone()[0])
