#!/usr/bin/env python3
"""Validação pós-seed do schema cad."""
from __future__ import annotations

from pathlib import Path
try:
    from dotenv import load_dotenv
    for _p in [Path(__file__).resolve().parents[i] / '.env' for i in range(1, 5)]:
        if _p.is_file():
            load_dotenv(_p)
            break
except ImportError:
    pass

import os
import sys

try:
    import psycopg2
except ImportError:
    print("ERRO: psycopg2 não instalado")
    sys.exit(1)

HOST = os.getenv("POSTGRES_HOST", "localhost")
PORT = int(os.getenv("POSTGRES_PORT", "5432"))
USER = os.getenv("POSTGRES_USER", "postgres")
PASSWORD = os.getenv("POSTGRES_PASS") or os.getenv("POSTGRES_PASSWORD") or ""
DBNAME = os.getenv("POSTGRES_DB", "melnick")
if not PASSWORD:
    raise SystemExit("Defina POSTGRES_PASSWORD no .env da raiz")

EXPECTED = {
    "empreendimentos": 133,
    "torres": 818,
}


def main() -> int:
    conn = psycopg2.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD, dbname=DBNAME
    )
    cur = conn.cursor()
    ok = True

    for table, expected in EXPECTED.items():
        cur.execute(f"SELECT COUNT(*) FROM cad.{table}")
        count = cur.fetchone()[0]
        status = "OK" if count == expected else "FALHA"
        if count != expected:
            ok = False
        print(f"{status} cad.{table}: {count} (esperado {expected})")

    cur.execute(
        """
        SELECT COUNT(*) FROM cad.torres t
        LEFT JOIN cad.empreendimentos e ON e.id = t.id_empreendimento
        WHERE e.id IS NULL
        """
    )
    orphans = cur.fetchone()[0]
    print(f"{'OK' if orphans == 0 else 'FALHA'} torres sem empreendimento: {orphans}")
    ok = ok and orphans == 0

    cur.execute(
        """
        SELECT COUNT(*) FROM cad.torres t
        LEFT JOIN cad.fases f ON f.id = t.id_fase
        WHERE f.id IS NULL
        """
    )
    orphans_fase = cur.fetchone()[0]
    print(f"{'OK' if orphans_fase == 0 else 'FALHA'} torres sem fase: {orphans_fase}")
    ok = ok and orphans_fase == 0

    cur.execute("SELECT COUNT(DISTINCT cod_spe) FROM cad.empreendimentos")
    print(f"INFO SPEs distintos: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM cad.aliases")
    print(f"INFO aliases: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM cad.identificadores_externos")
    print(f"INFO identificadores_externos: {cur.fetchone()[0]}")

    cur.close()
    conn.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
