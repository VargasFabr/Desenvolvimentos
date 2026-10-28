"""Carga dos dados tratados da lista Daes no PostgreSQL (database dacoes)."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import execute_values

logger = logging.getLogger("AvaliacaoDacoesPostgres")

AVAL_IA_COLUMN = "aval_ia"
AVAL_IA_PENDENTE = "pendente"
AVAL_IA_AVALIADO = "avaliado"
AVAL_IA_VALUES = (AVAL_IA_PENDENTE, AVAL_IA_AVALIADO)

SYSTEM_COLUMNS = {"sharepoint_id", "created_at", "modified_at", "scraped_at", AVAL_IA_COLUMN}
RESERVED_COLUMNS = SYSTEM_COLUMNS | {"id"}


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
        "dbname": dbname or os.getenv("POSTGRES_DB", "postgres"),
    }


def connect_postgres(dbname: str | None = None) -> PgConnection:
    if os.environ.get("AIRFLOW_CTX_DAG_ID"):
        try:
            from airflow.providers.postgres.hooks.postgres import PostgresHook

            hook = PostgresHook(postgres_conn_id="postgres")
            conn_meta = hook.get_connection()
            params = _postgres_connection_params(
                dbname=dbname,
                host=conn_meta.host,
                port=conn_meta.port,
                user=conn_meta.login,
                password=conn_meta.password,
            )
            if dbname:
                return psycopg2.connect(**params)
            return hook.get_conn()
        except Exception as exc:
            logger.warning("PostgresHook falhou (%s). Tentando env...", exc)

    try:
        params = _postgres_connection_params(dbname=dbname)
        logger.info(
            "Conectando PostgreSQL em %(host)s:%(port)s db=%(dbname)s",
            params,
        )
        return psycopg2.connect(**params)
    except UnicodeDecodeError as exc:
        params = _postgres_connection_params(dbname=dbname)
        raise RuntimeError(
            "Falha de autenticação/conexão com PostgreSQL em "
            f"{params['host']}:{params['port']}. Verifique POSTGRES_USER/POSTGRES_PASS."
        ) from exc


def ensure_database_exists(database_name: str = "dacoes") -> None:
    conn = connect_postgres(dbname="postgres")
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
            if cur.fetchone():
                logger.info("Database %s já existe.", database_name)
                return
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
            logger.info("Database %s criado.", database_name)
    finally:
        conn.close()


def _infer_sql_type(values: list[Any]) -> str:
    non_null = [value for value in values if value not in (None, "")]
    if not non_null:
        return "TEXT"

    if all(isinstance(value, bool) for value in non_null):
        return "BOOLEAN"

    numeric_values: list[float] = []
    for value in non_null:
        if isinstance(value, (int, float)):
            numeric_values.append(float(value))
            continue
        text = str(value).strip().replace(".", "").replace(",", ".")
        if re.fullmatch(r"-?\d+(\.\d+)?", text):
            numeric_values.append(float(text))

    if numeric_values and len(numeric_values) == len(non_null):
        return "NUMERIC"

    date_patterns = (
        r"^\d{4}-\d{2}-\d{2}",
        r"^\d{2}/\d{2}/\d{4}",
    )
    if all(any(re.match(pattern, str(value)) for pattern in date_patterns) for value in non_null):
        return "TIMESTAMP"

    return "TEXT"


def _quote_identifier(name: str) -> str:
    safe = re.sub(r"[^0-9a-zA-Z_]+", "_", name.strip().lower())
    safe = re.sub(r"_+", "_", safe).strip("_") or "campo"
    if safe[0].isdigit():
        safe = f"col_{safe}"
    return safe


def build_column_definitions(items: list[dict[str, Any]]) -> dict[str, str]:
    column_values: dict[str, list[Any]] = {}
    for item in items:
        for key, value in item.items():
            if key in RESERVED_COLUMNS:
                continue
            column_values.setdefault(key, []).append(value)

    definitions = {column: _infer_sql_type(values) for column, values in column_values.items()}
    return definitions


def _legacy_field_columns(conn: PgConnection, table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name ~ '^field_[0-9]+$'
            """,
            (table_name,),
        )
        return {row[0] for row in cur.fetchall()}


def recreate_table(
    conn: PgConnection,
    column_defs: dict[str, str],
    table_name: str = "dacoes_itens",
) -> None:
    columns_sql = [
        sql.SQL("{} INTEGER PRIMARY KEY").format(sql.Identifier("sharepoint_id")),
        sql.SQL("{} TIMESTAMP").format(sql.Identifier("created_at")),
        sql.SQL("{} TIMESTAMP").format(sql.Identifier("modified_at")),
        sql.SQL("{} TIMESTAMP NOT NULL").format(sql.Identifier("scraped_at")),
        sql.SQL("{} TEXT NOT NULL DEFAULT {}").format(
            sql.Identifier(AVAL_IA_COLUMN),
            sql.Literal(AVAL_IA_PENDENTE),
        ),
    ]
    for column, col_type in sorted(column_defs.items()):
        columns_sql.append(
            sql.SQL("{} {}").format(sql.Identifier(column), sql.SQL(col_type))
        )

    create_stmt = sql.SQL("CREATE TABLE {} ({})").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(columns_sql),
    )
    check_name = f"{table_name}_{AVAL_IA_COLUMN}_check"

    with conn.cursor() as cur:
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table_name)))
        cur.execute(create_stmt)
        cur.execute(
            sql.SQL("ALTER TABLE {} ADD CONSTRAINT {} CHECK ({} IN ({}, {}))").format(
                sql.Identifier(table_name),
                sql.Identifier(check_name),
                sql.Identifier(AVAL_IA_COLUMN),
                sql.Literal(AVAL_IA_PENDENTE),
                sql.Literal(AVAL_IA_AVALIADO),
            )
        )
    conn.commit()
    logger.info("Tabela %s recriada com %s colunas de negócio.", table_name, len(column_defs))


def ensure_aval_ia_column(conn: PgConnection, table_name: str = "dacoes_itens") -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, AVAL_IA_COLUMN),
        )
        column_exists = cur.fetchone() is not None

        if not column_exists:
            cur.execute(
                sql.SQL(
                    "ALTER TABLE {} ADD COLUMN {} TEXT NOT NULL DEFAULT {}"
                ).format(
                    sql.Identifier(table_name),
                    sql.Identifier(AVAL_IA_COLUMN),
                    sql.Literal(AVAL_IA_PENDENTE),
                )
            )
            cur.execute(
                sql.SQL("UPDATE {} SET {} = {}").format(
                    sql.Identifier(table_name),
                    sql.Identifier(AVAL_IA_COLUMN),
                    sql.Literal(AVAL_IA_AVALIADO),
                )
            )
            logger.info(
                "Coluna %s criada; registros existentes marcados como %s.",
                AVAL_IA_COLUMN,
                AVAL_IA_AVALIADO,
            )

        cur.execute(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conname = %s
            """,
            (f"{table_name}_{AVAL_IA_COLUMN}_check",),
        )
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL(
                    "ALTER TABLE {} ADD CONSTRAINT {} CHECK ({} IN ({}, {}))"
                ).format(
                    sql.Identifier(table_name),
                    sql.Identifier(f"{table_name}_{AVAL_IA_COLUMN}_check"),
                    sql.Identifier(AVAL_IA_COLUMN),
                    sql.Literal(AVAL_IA_PENDENTE),
                    sql.Literal(AVAL_IA_AVALIADO),
                )
            )
    conn.commit()


def ensure_table(
    conn: PgConnection,
    items: list[dict[str, Any]],
    table_name: str = "dacoes_itens",
    *,
    recreate_on_legacy_schema: bool = True,
) -> dict[str, str]:
    column_defs = build_column_definitions(items)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        table_exists = cur.fetchone() is not None

    legacy_columns = _legacy_field_columns(conn, table_name) if table_exists else set()
    desired_columns = set(column_defs.keys())
    has_legacy_schema = bool(legacy_columns)
    missing_desired = desired_columns - set(
        _list_table_columns(conn, table_name) if table_exists else []
    )

    if (
        recreate_on_legacy_schema
        and table_exists
        and (has_legacy_schema or missing_desired)
    ):
        logger.info(
            "Schema legado detectado em %s (colunas field_*=%s). Recriando tabela...",
            table_name,
            len(legacy_columns),
        )
        recreate_table(conn, column_defs, table_name=table_name)
        return column_defs

    if not table_exists:
        recreate_table(conn, column_defs, table_name=table_name)
        return column_defs

    with conn.cursor() as cur:
        existing = set(_list_table_columns(conn, table_name))

        for column, col_type in column_defs.items():
            if column not in existing:
                alter_stmt = sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} {}").format(
                    sql.Identifier(table_name),
                    sql.Identifier(column),
                    sql.SQL(col_type),
                )
                cur.execute(alter_stmt)
    conn.commit()
    return column_defs


def _list_table_columns(conn: PgConnection, table_name: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        return [row[0] for row in cur.fetchall()]


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _coerce_value(value: Any, sql_type: str) -> Any:
    if value in (None, ""):
        return None
    if sql_type == "BOOLEAN":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "sim", "yes"}
    if sql_type == "NUMERIC":
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip().replace(".", "").replace(",", ".")
        return float(text) if text else None
    if sql_type == "TIMESTAMP":
        return _parse_timestamp(value)
    return str(value)


def upsert_items(
    conn: PgConnection,
    items: list[dict[str, Any]],
    column_defs: dict[str, str],
    table_name: str = "dacoes_itens",
) -> int:
    if not items:
        return 0

    scraped_at = datetime.utcnow()
    data_columns = ["sharepoint_id", "created_at", "modified_at", "scraped_at"] + sorted(column_defs)
    rows: list[tuple[Any, ...]] = []

    for item in items:
        sharepoint_id = item.get("sharepoint_id")
        if sharepoint_id is None:
            continue
        row = [
            int(sharepoint_id),
            _parse_timestamp(item.get("created_at")),
            _parse_timestamp(item.get("modified_at")),
            scraped_at,
        ]
        for column in sorted(column_defs):
            value = item.get(column)
            row.append(_coerce_value(value, column_defs[column]))
        rows.append(tuple(row))

    insert_columns = sql.SQL(", ").join(sql.Identifier(col) for col in data_columns)
    update_columns = [
        col for col in data_columns if col not in {"sharepoint_id", AVAL_IA_COLUMN}
    ]
    update_sql = sql.SQL(", ").join(
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
        for col in update_columns
    )
    query = sql.SQL(
        "INSERT INTO {} ({}) VALUES %s ON CONFLICT ({}) DO UPDATE SET {}"
    ).format(
        sql.Identifier(table_name),
        insert_columns,
        sql.Identifier("sharepoint_id"),
        update_sql,
    )

    with conn.cursor() as cur:
        execute_values(cur, query.as_string(conn), rows, page_size=200)
    conn.commit()
    return len(rows)


def sync_item_fields(
    conn: PgConnection,
    sharepoint_id: int,
    fields: dict[str, Any],
    *,
    table_name: str = "dacoes_itens",
    mark_avaliado: bool = True,
) -> int:
    if not fields and not mark_avaliado:
        return 0

    existing_columns = set(_list_table_columns(conn, table_name))
    assignments: list[sql.Composable] = []
    values: list[Any] = []

    for column, value in fields.items():
        if column in RESERVED_COLUMNS or column not in existing_columns:
            continue
        assignments.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
        values.append(value)

    if mark_avaliado and AVAL_IA_COLUMN in existing_columns:
        assignments.append(sql.SQL("{} = %s").format(sql.Identifier(AVAL_IA_COLUMN)))
        values.append(AVAL_IA_AVALIADO)

    if not assignments:
        return 0

    values.append(int(sharepoint_id))
    query = sql.SQL("UPDATE {} SET {} WHERE {} = %s").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(assignments),
        sql.Identifier("sharepoint_id"),
    )
    with conn.cursor() as cur:
        cur.execute(query.as_string(conn), values)
        updated = cur.rowcount
    conn.commit()
    return updated


def mark_avaliado(
    conn: PgConnection,
    sharepoint_id: int,
    *,
    table_name: str = "dacoes_itens",
) -> int:
    return sync_item_fields(
        conn,
        sharepoint_id,
        {},
        table_name=table_name,
        mark_avaliado=True,
    )


def get_item_from_postgres(
    sharepoint_id: int,
    *,
    database_name: str = "dacoes",
    table_name: str = "dacoes_itens",
) -> dict[str, Any] | None:
    conn = connect_postgres(dbname=database_name)
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT * FROM {} WHERE {} = %s").format(
                    sql.Identifier(table_name),
                    sql.Identifier("sharepoint_id"),
                ),
                (int(sharepoint_id),),
            )
            row = cur.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))
    finally:
        conn.close()


def search_items_in_postgres(
    filters: dict[str, Any] | None = None,
    *,
    aval_ia: str | None = None,
    limite: int = 20,
    database_name: str = "dacoes",
    table_name: str = "dacoes_itens",
) -> list[dict[str, Any]]:
    filters = filters or {}
    conn = connect_postgres(dbname=database_name)
    try:
        existing_columns = set(_list_table_columns(conn, table_name))
        clauses: list[sql.Composable] = []
        values: list[Any] = []

        if aval_ia:
            clauses.append(sql.SQL("{} = %s").format(sql.Identifier(AVAL_IA_COLUMN)))
            values.append(aval_ia)

        for key, value in filters.items():
            if value in (None, ""):
                continue
            column = _quote_identifier(str(key))
            if column not in existing_columns:
                continue
            clauses.append(
                sql.SQL("CAST({} AS TEXT) ILIKE %s").format(sql.Identifier(column))
            )
            values.append(f"%{value}%")

        where_sql = sql.SQL(" AND ").join(clauses) if clauses else sql.SQL("TRUE")
        query = sql.SQL("SELECT * FROM {} WHERE {} ORDER BY {} DESC LIMIT %s").format(
            sql.Identifier(table_name),
            where_sql,
            sql.Identifier("sharepoint_id"),
        )
        values.append(int(limite))

        with conn.cursor() as cur:
            cur.execute(query.as_string(conn), values)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def sync_item_after_edit(
    sharepoint_id: int,
    item: dict[str, Any],
    *,
    database_name: str = "dacoes",
    table_name: str = "dacoes_itens",
) -> dict[str, Any]:
    ensure_database_exists(database_name)
    conn = connect_postgres(dbname=database_name)
    try:
        ensure_aval_ia_column(conn, table_name=table_name)
        ensure_table(conn, [item], table_name=table_name, recreate_on_legacy_schema=False)

        fields_to_sync = {
            key: value
            for key, value in item.items()
            if key not in RESERVED_COLUMNS
        }
        updated = sync_item_fields(
            conn,
            sharepoint_id,
            fields_to_sync,
            table_name=table_name,
            mark_avaliado=True,
        )
        return {
            "sharepoint_id": sharepoint_id,
            "linhas_atualizadas": updated,
            "aval_ia": AVAL_IA_AVALIADO,
        }
    finally:
        conn.close()


def load_json_file(json_path: str) -> list[dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Arquivo JSON inválido: {json_path}")
    return data


def sync_dacoes_to_postgres(
    json_path: str,
    database_name: str = "dacoes",
    table_name: str = "dacoes_itens",
) -> dict[str, Any]:
    items = load_json_file(json_path)
    ensure_database_exists(database_name)
    conn = connect_postgres(dbname=database_name)
    try:
        column_defs = ensure_table(conn, items, table_name=table_name)
        ensure_aval_ia_column(conn, table_name=table_name)
        inserted = upsert_items(conn, items, column_defs, table_name=table_name)
        return {
            "database": database_name,
            "table": table_name,
            "registros": inserted,
            "colunas": sorted(column_defs.keys()) + [AVAL_IA_COLUMN],
        }
    finally:
        conn.close()
