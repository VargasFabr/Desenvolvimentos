"""Serviço de edição de dações no SharePoint com sync no Postgres."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from dacoes_pipeline_utils import resolve_data_path
from dacoes_postgres import (
    AVAL_IA_PENDENTE,
    search_items_in_postgres,
    sync_item_after_edit,
)

logger = logging.getLogger("DacoesEditService")


@lru_cache(maxsize=1)
def _get_client():
    from Módulos.cliente_sharepoint_dacoes import build_sharepoint_client_from_env

    data_path = resolve_data_path()
    client = build_sharepoint_client_from_env(data_file_path=data_path)
    client.ensure_authenticated()
    client.fetch_field_mapping()
    client.fetch_editable_fields()
    return client


def _audit_log(entry: dict[str, Any]) -> None:
    data_path = resolve_data_path()
    log_path = os.path.join(data_path, "edicoes_dacoes.jsonl")
    os.makedirs(data_path, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def listar_campos_editaveis() -> list[dict[str, Any]]:
    client = _get_client()
    fields = client.fetch_editable_fields()
    return [
        {
            "nome": info["title"],
            "nome_normalizado": info["normalized_name"],
            "nome_interno": info["internal_name"],
            "tipo": info["type"],
            "obrigatorio": info["required"],
        }
        for info in sorted(fields.values(), key=lambda item: item["title"])
    ]


def buscar_dacoes(
    *,
    sharepoint_id: int | None = None,
    endereco: str | None = None,
    imobiliaria: str | None = None,
    cidade: str | None = None,
    corretor: str | None = None,
    aval_ia: str | None = None,
    limite: int = 20,
) -> list[dict[str, Any]]:
    if sharepoint_id is not None:
        item = obter_dacao(int(sharepoint_id))
        return [item]

    filters: dict[str, Any] = {}
    if endereco:
        filters["endereco"] = endereco
    if imobiliaria:
        filters["imobiliaria"] = imobiliaria
    if cidade:
        filters["cidade"] = cidade
    if corretor:
        filters["corretor"] = corretor

    results = search_items_in_postgres(filters=filters, aval_ia=aval_ia, limite=limite)
    if results:
        return results

    client = _get_client()
    raw_items = client.fetch_list_items()
    normalized = client.normalize_items(raw_items, client.field_mapping)
    matches: list[dict[str, Any]] = []
    for item in normalized:
        if sharepoint_id is not None and item.get("sharepoint_id") != sharepoint_id:
            continue
        if endereco and endereco.lower() not in str(item.get("endereco", "")).lower():
            continue
        if imobiliaria and imobiliaria.lower() not in str(item.get("imobiliaria", "")).lower():
            continue
        if cidade and cidade.lower() not in str(item.get("cidade", "")).lower():
            continue
        if corretor and corretor.lower() not in str(item.get("corretor", "")).lower():
            continue
        matches.append(item)
        if len(matches) >= limite:
            break
    return matches


def obter_dacao(sharepoint_id: int) -> dict[str, Any]:
    client = _get_client()
    return client.get_item(int(sharepoint_id))


def editar_dacao(sharepoint_id: int, campos: dict[str, Any]) -> dict[str, Any]:
    if not campos:
        raise ValueError("Informe ao menos um campo em 'campos'.")

    client = _get_client()
    antes = client.get_item(int(sharepoint_id))
    depois = client.update_item(int(sharepoint_id), campos)
    postgres_sync = sync_item_after_edit(int(sharepoint_id), depois)

    diff = {
        key: {"antes": antes.get(key), "depois": depois.get(key)}
        for key in campos.keys()
        if antes.get(key) != depois.get(key)
    }
    result = {
        "status": "ok",
        "sharepoint_id": int(sharepoint_id),
        "campos_alterados": diff,
        "registro_atualizado": depois,
        "postgres_sync": postgres_sync,
    }
    _audit_log(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sharepoint_id": int(sharepoint_id),
            "campos": campos,
            "diff": diff,
        }
    )
    logger.info("Dação %s editada com sucesso.", sharepoint_id)
    return result


def listar_dacoes_pendentes_ia(limite: int = 50) -> list[dict[str, Any]]:
    return search_items_in_postgres(aval_ia=AVAL_IA_PENDENTE, limite=limite)
