#!/usr/bin/env python3
"""Aplica views/*.sql no banco melnick.

Ordem: arquivos `v_*.sql` primeiro (alfabético), depois os demais
(ex.: `02_views_unidades.sql`, que depende de `v_empreendimentos_resumo`).
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

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = sorted(
    (ROOT / "views").glob("*.sql"),
    key=lambda p: (0 if p.stem.startswith("v_") else 1, p.name),
)

DOCKER = os.getenv("CAD_DOCKER", "airflow3-standalone")
PGHOST = os.getenv("POSTGRES_HOST", "host.docker.internal")
PGUSER = os.getenv("POSTGRES_USER", "postgres")
PGPASS = os.getenv("POSTGRES_PASS") or os.getenv("POSTGRES_PASSWORD") or ""
PGDB = os.getenv("POSTGRES_DB", "melnick")
if not PGPASS:
    raise SystemExit("Defina POSTGRES_PASSWORD no .env da raiz")


def apply_sql(path: Path) -> None:
    cmd = [
        "docker", "exec", "-i",
        "-e", f"PGPASSWORD={PGPASS}",
        DOCKER,
        "psql", "-h", PGHOST, "-U", PGUSER, "-d", PGDB,
        "-v", "ON_ERROR_STOP=1",
    ]
    proc = subprocess.run(cmd, input=path.read_bytes(), capture_output=True)
    if proc.returncode != 0:
        print(proc.stderr.decode("utf-8", errors="replace"))
        raise SystemExit(f"Falha ao aplicar {path.name}")


def main() -> None:
    if not VIEWS:
        raise SystemExit("Nenhum arquivo em views/")
    for sql in VIEWS:
        apply_sql(sql)
        print(f"OK: {sql.name}")
    print(f"OK: {len(VIEWS)} arquivo(s) de views aplicados")


if __name__ == "__main__":
    main()