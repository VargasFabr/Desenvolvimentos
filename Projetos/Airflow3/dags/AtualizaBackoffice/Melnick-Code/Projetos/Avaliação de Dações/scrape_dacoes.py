#!/usr/bin/env python3
"""Extrai a lista SharePoint Daes e grava JSON local tratado."""
from __future__ import annotations

import json
import logging
import sys

from dacoes_pipeline_utils import (
    PASTA_LOGS,
    ensure_sys_path,
    load_project_env,
    now_brt_string,
    resolve_data_path,
    unique_sorted,
    write_last_update,
)

ensure_sys_path()
loaded_env_files = load_project_env()

from Módulos.cliente_sharepoint_dacoes import build_sharepoint_client_from_env
from Módulos.logs_melnick import setup_logger


def collect_columns(items: list[dict]) -> list[str]:
    columns: set[str] = set()
    for item in items:
        columns.update(item.keys())
    return unique_sorted(columns)


def main() -> int:
    timestamp = now_brt_string()
    logger = setup_logger(
        name="AvaliacaoDacoes",
        logs_path=PASTA_LOGS,
        log_file=f"{timestamp.replace(':', '-').replace(' ', '_')} - scrape_dacoes.log",
        level=logging.INFO,
    )
    logger.info("Arquivos .env carregados: %s", " | ".join(loaded_env_files))

    data_path = resolve_data_path()
    logger.info("Pasta de dados: %s", data_path)

    client = build_sharepoint_client_from_env(data_file_path=data_path)
    raw_items, treated_items = client.scrape()

    update_file = write_last_update(data_path, timestamp)
    columns = collect_columns(treated_items)

    logger.info("Extração concluída: %s registros.", len(treated_items))
    logger.info("Colunas detectadas (%s): %s", len(columns), ", ".join(columns))
    if treated_items:
        logger.info("Amostra do primeiro registro: %s", json.dumps(treated_items[0], ensure_ascii=False))

    print(
        json.dumps(
            {
                "status": "ok",
                "registros": len(treated_items),
                "colunas": columns,
                "data_path": data_path,
                "ultima_atualizacao": update_file,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logging.exception("Falha no scrape_dacoes: %s", exc)
        raise SystemExit(1) from exc
