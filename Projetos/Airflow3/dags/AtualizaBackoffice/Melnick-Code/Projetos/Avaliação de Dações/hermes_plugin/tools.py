"""Handlers das tools de dações para o plugin Hermes."""
from __future__ import annotations

from typing import Any

from tools.registry import tool_error, tool_result

from .bootstrap import ensure_dacoes_runtime


def _dispatch(tool_name: str, args: dict[str, Any]) -> str:
    ensure_dacoes_runtime()
    from dacoes_hermes_tools import executar_tool

    payload = executar_tool(tool_name, args or {})
    if payload.get("status") == "ok":
        return tool_result(payload)
    message = payload.get("mensagem") or "Falha ao executar tool de dações."
    return tool_error(message, tool=payload.get("tool"), detail=payload)


def handle_listar_campos_editaveis_dacoes(args: dict, **_) -> str:
    return _dispatch("listar_campos_editaveis_dacoes", args)


def handle_buscar_dacoes(args: dict, **_) -> str:
    return _dispatch("buscar_dacoes", args)


def handle_obter_dacao(args: dict, **_) -> str:
    return _dispatch("obter_dacao", args)


def handle_editar_dacao(args: dict, **_) -> str:
    return _dispatch("editar_dacao", args)


def handle_listar_dacoes_pendentes_ia(args: dict, **_) -> str:
    return _dispatch("listar_dacoes_pendentes_ia", args)
