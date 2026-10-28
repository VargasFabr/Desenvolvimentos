"""Utilitários de ambiente, caminhos e timestamps para o projeto Avaliação de Dações."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Iterable

from dotenv import load_dotenv

DIR_SCRIPT = os.path.dirname(os.path.abspath(__file__))
PASTA_DADOS = os.path.join(DIR_SCRIPT, "Dados")
PASTA_LOGS = os.path.join(DIR_SCRIPT, "Logs")
PASTA_REPOSITORIO = os.path.abspath(os.path.join(DIR_SCRIPT, "..", ".."))
DIR_WORKSPACE = os.path.abspath(os.path.join(PASTA_REPOSITORIO, ".."))

ENV_CANDIDATES: tuple[str, ...] = (
    os.getenv("DOTENV_PATH", ""),
    r"e:\Projetos\VS_Code\.env",
    os.path.join(DIR_WORKSPACE, ".env"),
    os.path.join(PASTA_REPOSITORIO, ".env"),
)

_WRITABLE_DATA_FALLBACKS = (
    "/opt/airflow/data/dacoes",
)


def ensure_sys_path() -> None:
    if PASTA_REPOSITORIO not in sys.path:
        sys.path.append(PASTA_REPOSITORIO)


def load_project_env() -> list[str]:
    loaded: list[str] = []
    for candidate in ENV_CANDIDATES:
        if candidate and os.path.exists(candidate):
            load_dotenv(candidate, override=True)
            if candidate not in loaded:
                loaded.append(candidate)
    if not loaded:
        raise FileNotFoundError(
            "Nenhum .env encontrado. Configure DOTENV_PATH ou crie o arquivo em "
            f"{ENV_CANDIDATES[1]} / {ENV_CANDIDATES[2]} / {ENV_CANDIDATES[3]}."
        )
    return loaded


def _is_writable_dir(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, ".write_test")
        with open(test_file, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(test_file)
        return True
    except OSError:
        return False


def resolve_data_path(preferred_path: str | None = None) -> str:
    preferred = preferred_path or PASTA_DADOS
    candidates: list[str] = []
    env_override = os.getenv("DACOES_DATA_PATH")
    if env_override:
        candidates.append(env_override)
    candidates.append(preferred)
    candidates.extend(_WRITABLE_DATA_FALLBACKS)
    candidates.append(os.path.join(tempfile.gettempdir(), "melnick_dacoes"))

    for path in candidates:
        if _is_writable_dir(path):
            return path

    os.makedirs(preferred, exist_ok=True)
    return preferred


def now_brt_string() -> str:
    current_time_utc = datetime.now(timezone.utc) - timedelta(seconds=5)
    current_time_brt = current_time_utc.astimezone(timezone(timedelta(hours=-3)))
    return current_time_brt.strftime("%Y-%m-%d %H:%M:%S")


def write_last_update(data_path: str, timestamp: str | None = None) -> str:
    os.makedirs(data_path, exist_ok=True)
    value = timestamp or now_brt_string()
    file_path = os.path.join(data_path, "ultima_atualizacao.txt")
    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write(value)
    return file_path


def read_last_update(data_path: str) -> str | None:
    file_path = os.path.join(data_path, "ultima_atualizacao.txt")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def require_env(*keys: str) -> dict[str, str]:
    missing = [key for key in keys if not os.getenv(key)]
    if missing:
        raise ValueError(
            f"Variáveis de ambiente ausentes: {', '.join(missing)}. Verifique o .env."
        )
    return {key: os.getenv(key, "") for key in keys}


def unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value})
