#!/usr/bin/env python3
"""Sincroniza dacoes_tratado.json com o PostgreSQL (database dacoes)."""
from __future__ import annotations

import json
import logging
import os
import sys

from dacoes_pipeline_utils import PASTA_LOGS, ensure_sys_path, load_project_env, now_brt_string, resolve_data_path
from dacoes_postgres import sync_dacoes_to_postgres

ensure_sys_path()
loaded_env_files = load_project_env()

from Módulos.logs_melnick import setup_logger


def main() -> int:
    timestamp = now_brt_string()
    logger = setup_logger(
        name="AvaliacaoDacoesPostgres",
        logs_path=PASTA_LOGS,
        log_file=f"{timestamp.replace(':', '-').replace(' ', '_')} - load_postgres.log",
        level=logging.INFO,
    )
    logger.info("Arquivos .env carregados: %s", " | ".join(loaded_env_files))

    data_path = resolve_data_path()
    json_path = os.path.join(data_path, "dacoes_tratado.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"Arquivo {json_path} não encontrado. Execute scrape_dacoes.py primeiro."
        )

    result = sync_dacoes_to_postgres(json_path)
    logger.info("Carga Postgres concluída: %s", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logging.exception("Falha no load_dacoes_postgres: %s", exc)
        raise SystemExit(1) from exc
