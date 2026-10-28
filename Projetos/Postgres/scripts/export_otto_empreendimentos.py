#!/usr/bin/env python3
"""
Fase 2: cruza Otto (realty/building) com cad.empreendimentos via integration_id = cod_spe.
Gera SQL de identificadores_externos otto — não recria cadastro.

Uso:
    python export_otto_empreendimentos.py [--output cadastro/05_seed_otto_ids.sql]
"""
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

import argparse
import os
import sys
import uuid
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("ERRO: psycopg2 necessário")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

OTTO_HOST = os.getenv("OTTO_RDS_HOST") or os.getenv("OTTO_DB_HOST") or ""
OTTO_DB = os.getenv("OTTO_RDS_DB") or os.getenv("OTTO_DB_NAME") or ""
OTTO_USER = os.getenv("OTTO_RDS_USER") or os.getenv("OTTO_DB_USER") or ""
OTTO_PASS = os.getenv("OTTO_RDS_PASSWORD") or os.getenv("OTTO_DB_PASS") or os.getenv("OTTO_DB_PASSWORD") or ""

MELNICK_HOST = os.getenv("POSTGRES_HOST", "localhost")
MELNICK_USER = os.getenv("POSTGRES_USER", "postgres")
MELNICK_PASS = os.getenv("POSTGRES_PASS") or os.getenv("POSTGRES_PASSWORD") or ""
MELNICK_DB = os.getenv("POSTGRES_DB", "melnick")

if not MELNICK_PASS:
    raise SystemExit("Defina POSTGRES_PASSWORD no .env da raiz")
if not OTTO_HOST or not OTTO_PASS:
    raise SystemExit("Defina OTTO_RDS_HOST e OTTO_RDS_PASSWORD no .env")


def sql_str(val: str) -> str:
    return "'" + val.replace("'", "''") + "'"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(ROOT / "cadastro" / "05_seed_otto_ids.sql"),
        help="Arquivo SQL de saída",
    )
    args = parser.parse_args()

    if not OTTO_USER or not OTTO_PASS:
        print(
            "Configure OTTO_DB_USER e OTTO_DB_PASS para conectar ao RDS Otto.\n"
            "Exemplo:\n"
            "  $env:OTTO_DB_USER='...'; $env:OTTO_DB_PASS='...'\n"
            "  python scripts/export_otto_empreendimentos.py"
        )
        sys.exit(1)

    otto = psycopg2.connect(
        host=OTTO_HOST, database=OTTO_DB, user=OTTO_USER, password=OTTO_PASS, port=5432
    )
    melnick = psycopg2.connect(
        host=MELNICK_HOST, database=MELNICK_DB, user=MELNICK_USER, password=MELNICK_PASS, port=5432
    )

    oc = otto.cursor()
    mc = melnick.cursor()

    mc.execute("SELECT id, cod_spe FROM cad.empreendimentos")
    spe_to_id = {row[1]: str(row[0]) for row in mc.fetchall()}

    oc.execute(
        """
        SELECT id::text, integration_id, name
        FROM realty
        WHERE integration_id IS NOT NULL AND integration_id <> ''
        ORDER BY name
        """
    )
    realties = oc.fetchall()

    lines = [
        "-- Gerado por export_otto_empreendimentos.py (fase 2)",
        "BEGIN;",
    ]
    matched = 0
    unmatched = []

    for otto_id, integration_id, name in realties:
        spe = str(integration_id).strip() if integration_id else None
        if not spe or spe not in spe_to_id:
            unmatched.append((otto_id, integration_id, name))
            continue
        emp_id = spe_to_id[spe]
        lines.append(
            f"INSERT INTO cad.identificadores_externos (entidade_tipo, entidade_id, sistema, id_externo) "
            f"VALUES ('empreendimento', {sql_str(emp_id)}, 'otto', {sql_str(otto_id)}) "
            f"ON CONFLICT (sistema, id_externo) DO NOTHING;"
        )
        matched += 1

    # Buildings → torres (match por integration_id parcial + nome — heurística)
    oc.execute(
        """
        SELECT b.id::text, b.integration_id, b.name, r.integration_id AS spe
        FROM building b
        JOIN realty r ON r.id = b.realty_id
        WHERE r.integration_id IS NOT NULL
        """
    )
    for b_id, b_int, b_name, spe in oc.fetchall():
        spe = str(spe).strip()
        mc.execute(
            """
            SELECT t.id::text FROM cad.torres t
            JOIN cad.empreendimentos e ON e.id = t.id_empreendimento
            WHERE e.cod_spe = %s AND (t.nome_torre ILIKE %s OR t.cod_torre = %s)
            LIMIT 1
            """,
            (spe, b_name, str(b_int or "")),
        )
        row = mc.fetchone()
        if row:
            lines.append(
                f"INSERT INTO cad.identificadores_externos (entidade_tipo, entidade_id, sistema, id_externo) "
                f"VALUES ('torre', {sql_str(row[0])}, 'otto', {sql_str(b_id)}) "
                f"ON CONFLICT (sistema, id_externo) DO NOTHING;"
            )

    lines.append("COMMIT;")
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Empreendimentos Otto matched: {matched}/{len(realties)}")
    print(f"Unmatched Otto realty: {len(unmatched)}")
    if unmatched[:5]:
        for u in unmatched[:5]:
            print(f"  - {u[2]} (integration_id={u[1]})")
    print(f"SQL → {args.output}")

    oc.close()
    mc.close()
    otto.close()
    melnick.close()


if __name__ == "__main__":
    main()
