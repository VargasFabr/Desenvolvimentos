#!/usr/bin/env python3
"""Importa unidades do banco Otto → cad.unidades (upsert por torre + número)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2

from lib.otto_unidades import preview_otto_sync, sync_otto_units


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spe", help="Importar apenas um SPE")
    parser.add_argument("--dry-run", action="store_true", help="Só preview, não grava")
    args = parser.parse_args()

    melnick = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        dbname=os.getenv("POSTGRES_DB", "melnick"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASS", os.getenv("POSTGRES_PASSWORD", "")),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
    )
    if args.dry_run:
        stats = preview_otto_sync(melnick, args.spe)
        print(f"Otto total: {stats.total_otto}")
        print(f"Mapeadas (torre no cad): {stats.mapeadas}")
        print(f"Sem torre no cad: {stats.sem_torre}")
        print(f"Erro parse SPE/torre: {stats.parse_erro}")
    else:
        stats = sync_otto_units(melnick, args.spe)
        print(f"Importados: {stats.importados} / {stats.total_otto} unidades Otto")
        print(f"Sem torre no cad: {stats.sem_torre}")
    melnick.close()


if __name__ == "__main__":
    main()
