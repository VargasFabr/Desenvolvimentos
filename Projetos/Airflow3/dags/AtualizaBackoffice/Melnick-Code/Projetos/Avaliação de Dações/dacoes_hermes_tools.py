#!/usr/bin/env python3
"""Tools Hermes para edição de dações no SharePoint."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Callable

from dacoes_pipeline_utils import ensure_sys_path, load_project_env

ensure_sys_path()
load_project_env()

from dacoes_edit_service import (
    buscar_dacoes,
    editar_dacao,
    listar_campos_editaveis,
    listar_dacoes_pendentes_ia,
    obter_dacao,
)

logger = logging.getLogger("DacoesHermesTools")

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "listar_campos_editaveis_dacoes",
        "description": "Lista os campos editáveis da lista SharePoint Dações.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "buscar_dacoes",
        "description": "Busca dações por filtros parciais (endereço, imobiliária, cidade, corretor, aval_ia).",
        "parameters": {
            "type": "object",
            "properties": {
                "sharepoint_id": {"type": "integer"},
                "endereco": {"type": "string"},
                "imobiliaria": {"type": "string"},
                "cidade": {"type": "string"},
                "corretor": {"type": "string"},
                "aval_ia": {"type": "string", "enum": ["pendente", "avaliado"]},
                "limite": {"type": "integer", "default": 20},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "obter_dacao",
        "description": "Obtém uma dação pelo sharepoint_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "sharepoint_id": {"type": "integer"},
            },
            "required": ["sharepoint_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "editar_dacao",
        "description": "Edita campos de uma dação no SharePoint e sincroniza no Postgres.",
        "parameters": {
            "type": "object",
            "properties": {
                "sharepoint_id": {"type": "integer"},
                "campos": {
                    "type": "object",
                    "description": "Objeto chave/valor com nomes amigáveis ou normalizados.",
                    "additionalProperties": True,
                },
            },
            "required": ["sharepoint_id", "campos"],
            "additionalProperties": False,
        },
    },
    {
        "name": "listar_dacoes_pendentes_ia",
        "description": "Lista dações com aval_ia = pendente no Postgres.",
        "parameters": {
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "default": 50},
            },
            "additionalProperties": False,
        },
    },
]

_TOOL_HANDLERS: dict[str, Callable[..., Any]] = {
    "listar_campos_editaveis_dacoes": lambda args: listar_campos_editaveis(),
    "buscar_dacoes": lambda args: buscar_dacoes(**args),
    "obter_dacao": lambda args: obter_dacao(int(args["sharepoint_id"])),
    "editar_dacao": lambda args: editar_dacao(int(args["sharepoint_id"]), args["campos"]),
    "listar_dacoes_pendentes_ia": lambda args: listar_dacoes_pendentes_ia(
        limite=int(args.get("limite", 50))
    ),
}


def _json_safe(value: Any) -> Any:
    """Postgres TIMESTAMP/NUMERIC → str; Hermes tool_result não aceita datetime."""
    return json.loads(json.dumps(value, default=str))


def executar_tool(tool_name: str, argumentos: dict[str, Any] | None = None) -> dict[str, Any]:
    argumentos = argumentos or {}
    if tool_name not in _TOOL_HANDLERS:
        raise ValueError(
            f"Tool desconhecida: {tool_name}. Disponíveis: {', '.join(_TOOL_HANDLERS)}"
        )
    try:
        result = _TOOL_HANDLERS[tool_name](argumentos)
        return {"status": "ok", "tool": tool_name, "resultado": _json_safe(result)}
    except Exception as exc:
        logger.exception("Falha na tool %s: %s", tool_name, exc)
        return {"status": "erro", "tool": tool_name, "mensagem": str(exc)}


def listar_tools() -> list[dict[str, Any]]:
    return TOOL_DEFINITIONS


def main() -> int:
    parser = argparse.ArgumentParser(description="Tools Hermes - Dações SharePoint")
    parser.add_argument("--tool", help="Nome da tool")
    parser.add_argument("--args", default="{}", help="JSON com argumentos da tool")
    parser.add_argument("--list-tools", action="store_true", help="Lista tools disponíveis")
    args = parser.parse_args()

    if args.list_tools:
        print(json.dumps(listar_tools(), ensure_ascii=False, indent=2))
        return 0

    if not args.tool:
        parser.error("--tool é obrigatório quando --list-tools não é usado.")

    payload = json.loads(args.args)
    result = executar_tool(args.tool, payload)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logging.exception("Falha: %s", exc)
        raise SystemExit(1) from exc
