#!/usr/bin/env python3
"""Aplica scripts SQL do cadastro na ordem correta."""
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
CADASTRO = ROOT / "cadastro"

ORDER = [
    "99_archive_legacy.sql",
    "00_extensions.sql",
    "01_schema_cad.sql",
    "02_seed_sistemas.sql",
    "03_seed_incorporadoras.sql",
    "04_seed_controladoria.sql",
]

DOCKER = os.getenv("CAD_DOCKER", "airflow3-standalone")
PGHOST = os.getenv("POSTGRES_HOST", "host.docker.internal")
PGUSER = os.getenv("POSTGRES_USER", "postgres")
PGPASS = os.getenv("POSTGRES_PASS") or os.getenv("POSTGRES_PASSWORD") or ""
PGDB = os.getenv("POSTGRES_DB", "melnick")
if not PGPASS:
    raise SystemExit("Defina POSTGRES_PASSWORD no .env da raiz")


def run_sql(path: Path) -> None:
    print(f"-> {path.name} ({path.stat().st_size // 1024} KB)")
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
        raise SystemExit(f"Falha em {path.name}")
    err = proc.stderr.decode("utf-8", errors="replace")
    if err.strip():
        for line in err.splitlines():
            if "ERRO" in line or "ERROR" in line:
                print(line)


def main() -> None:
    # Recria schema cad para deploy idempotente
    reset = Path(__file__).parent / "_reset_cad.sql"
    reset.write_text("DROP SCHEMA IF EXISTS cad CASCADE;\n", encoding="utf-8")
    run_sql(reset)
    reset.unlink()

    for name in ORDER:
        path = CADASTRO / name
        if not path.exists():
            raise SystemExit(f"Arquivo ausente: {path}")
        run_sql(path)
    print("OK: todos os scripts aplicados")


if __name__ == "__main__":
    main()
