#!/usr/bin/env python3
"""
Limpa apenas o historico de execucao do SQLite do Airflow (dag_run, task_instance, etc.).

NAO apaga:
  - connection  (senhas e conexoes postgres / postgres_otto)
  - variable
  - ab_user / ab_role (usuarios do Airflow)
  - dag / serialized_dag / dag_code (cadastro das DAGs no metadata)
  - arquivos .py em dags/ (ficam no volume montado, fora deste .db)

IMPORTANTE: nenhum processo Airflow deve estar usando o arquivo .db (pare o container).
"""
from __future__ import annotations

import os
import sqlite3
import sys

DEFAULT_DB_PATH = "/opt/airflow/airflow.db"

# Apenas historico de execucao. Nunca inclua connection, variable, dag, etc.
TABLES_TO_CLEAN = [
    "log",
    "task_fail",
    "task_instance",
    "dag_run",
    "job",
    # Airflow 3 — extras de historico (ignorados se nao existirem)
    "task_instance_history",
    "dag_run_note",
    "rendered_task_instance_fields",
    "task_reschedule",
    "xcom",
]

# Tabelas criticas: aborta se o numero de linhas mudar apos a limpeza.
PRESERVED_TABLES = [
    "connection",
    "variable",
    "ab_user",
    "ab_role",
    "dag",
    "serialized_dag",
]

# Nunca permitir limpar estas tabelas, mesmo por engano na lista acima.
FORBIDDEN_TO_CLEAN = {
    "connection",
    "variable",
    "ab_user",
    "ab_role",
    "ab_permission",
    "ab_view_menu",
    "ab_permission_view",
    "ab_permission_view_role",
    "ab_register_user",
    "dag",
    "serialized_dag",
    "dag_code",
    "dag_owner_attributes",
    "slot_pool",
    "callback_request",
}


def get_existing_tables(conn: sqlite3.Connection) -> set[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return {row[0] for row in cur.fetchall()}


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    cur = conn.cursor()
    cur.execute(f'SELECT COUNT(*) FROM "{table}";')
    return int(cur.fetchone()[0])


def clean_airflow_db(db_path: str) -> int:
    if not os.path.isfile(db_path):
        print(f"ERRO: banco nao encontrado: {db_path}", file=sys.stderr)
        return 1

    blocked = FORBIDDEN_TO_CLEAN.intersection(TABLES_TO_CLEAN)
    if blocked:
        print(f"ERRO: tabelas proibidas em TABLES_TO_CLEAN: {sorted(blocked)}", file=sys.stderr)
        return 1

    print(f"Conectando: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    existing = get_existing_tables(conn)
    print(f"Tabelas no banco: {len(existing)}")

    preserved_before: dict[str, int] = {}
    for table in PRESERVED_TABLES:
        if table in existing:
            preserved_before[table] = count_rows(conn, table)
            print(f"  [preservar] {table}: {preserved_before[table]} registro(s)")

    if "connection" in preserved_before:
        print("  -> conexoes (senhas) serao mantidas intactas")

    cur.execute("PRAGMA foreign_keys = OFF;")

    cleaned = 0
    for table in TABLES_TO_CLEAN:
        if table not in existing:
            print(f"  [skip] tabela inexistente: {table}")
            continue
        n = count_rows(conn, table)
        print(f"  [clean] DELETE FROM {table} ({n} registro(s))")
        cur.execute(f'DELETE FROM "{table}";')
        cleaned += 1

    if cleaned == 0:
        print("AVISO: nenhuma tabela de historico encontrada para limpar.")

    print("Commit...")
    conn.commit()

    for table, before in preserved_before.items():
        after = count_rows(conn, table)
        if after != before:
            print(
                f"ERRO: tabela preservada '{table}' mudou ({before} -> {after}). "
                "Abortando sem VACUUM.",
                file=sys.stderr,
            )
            conn.close()
            return 1

    cur.execute("PRAGMA foreign_keys = ON;")

    print("VACUUM...")
    cur.execute("VACUUM;")
    conn.commit()

    conn.close()

    wal_file = db_path + "-wal"
    shm_file = db_path + "-shm"
    for f in (wal_file, shm_file):
        if os.path.exists(f):
            print(f"Removendo: {f}")
            try:
                os.remove(f)
            except OSError as e:
                print(f"  aviso: nao foi possivel remover {f}: {e}")

    print("Limpeza concluida. Conexoes, variaveis, usuarios e DAGs no metadata intactos.")
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = os.environ.get("AIRFLOW_DB_PATH", DEFAULT_DB_PATH)
    return clean_airflow_db(db_path)


if __name__ == "__main__":
    sys.exit(main())
