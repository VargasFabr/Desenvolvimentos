"""Prepara sys.path e variáveis de ambiente do projeto Melnick-Code."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BOOTSTRAPPED = False


def _default_melnick_code_root() -> str:
    here = Path(__file__).resolve()
    # .../Melnick-Code/Projetos/Avaliação de Dações/hermes_plugin/bootstrap.py
    if here.parent.name == "hermes_plugin":
        return str(here.parents[3])
    # Cópia em ~/.hermes/profiles/<p>/plugins/dacoes — exige MELNICK_CODE_PATH no .env
    return ""


def melnick_code_root() -> str:
    explicit = os.getenv("MELNICK_CODE_PATH", "").strip()
    if explicit:
        return explicit
    fallback = _default_melnick_code_root()
    if fallback:
        return fallback
    raise FileNotFoundError(
        "MELNICK_CODE_PATH não definido. Adicione ao .env do perfil Hermes, ex.: "
        "MELNICK_CODE_PATH=e:\\Projetos\\VS_Code\\Melnick\\PROJETOS\\Airflow3\\dags\\AtualizaBackoffice\\Melnick-Code"
    )


def dacoes_project_dir() -> str:
    return os.path.join(melnick_code_root(), "Projetos", "Avaliação de Dações")


def ensure_dacoes_runtime() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    for path in (melnick_code_root(), dacoes_project_dir()):
        if path not in sys.path:
            sys.path.insert(0, path)

    from dacoes_pipeline_utils import ensure_sys_path, load_project_env

    ensure_sys_path()
    load_project_env()
    _BOOTSTRAPPED = True


def check_dacoes_available() -> bool:
    try:
        ensure_dacoes_runtime()
    except Exception:
        return False
    required = ("DACOES", "DACOES_PASS", "POSTGRES_USER", "POSTGRES_PASS")
    return all((os.getenv(key) or "").strip() for key in required)
