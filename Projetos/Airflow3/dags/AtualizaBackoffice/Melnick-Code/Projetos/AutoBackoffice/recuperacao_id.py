"""
Recuperação de negócios removidos do Monday.com (AutoBackoffice 2.0).

Recria no board NEGOCIOS um item a partir do histórico em
`Dados/AutoBackoffice_2_0/negocios_monday_2_0.json` (itens marcados com
`deletado_do_monday_em` após a regra de remoção, ex.: `caiu_mais_de_10_dias`).

Identificação do negócio (prioridade):
  1. `--id-monday` ou env `RECUPERACAO_ID_MONDAY` ou `RECUPERACAO_ID_MONDAY_DEFAULT`
  2. `--id-negocio` ou env `RECUPERACAO_ID_NEGOCIO` ou `RECUPERACAO_ID_NEGOCIO_DEFAULT`

Exemplos:
    python Projetos/AutoBackoffice/recuperacao_id.py --id-monday 11950095889
    python Projetos/AutoBackoffice/recuperacao_id.py --id-negocio 8dec7ca6-f01a-4039-a5d3-09bf3fb535bf
    python Projetos/AutoBackoffice/recuperacao_id.py --id-monday 11950095889 --dry-run

    # Via variável de ambiente (Airflow / .env):
    RECUPERACAO_ID_NEGOCIO=8dec7ca6-... python Projetos/AutoBackoffice/recuperacao_id.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Tuple

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("RecuperacaoId")

dir_script = os.path.dirname(os.path.abspath(__file__))
pasta_repositorio = os.path.abspath(os.path.join(dir_script, "..", ".."))
if pasta_repositorio not in sys.path:
    sys.path.append(pasta_repositorio)

from Módulos.cliente_monday import ClienteMonday  # noqa: E402
from Módulos.mapeamento_dados import map_dict_keys  # noqa: E402

dir_workspace = os.path.abspath(os.path.join(pasta_repositorio, ".."))
arquivo_env_workspace = os.path.join(dir_workspace, ".env")
arquivo_env_repo = os.path.join(pasta_repositorio, ".env")
if os.path.exists(arquivo_env_workspace):
    load_dotenv(arquivo_env_workspace, override=True)
elif os.path.exists(arquivo_env_repo):
    load_dotenv(arquivo_env_repo, override=True)

_BOARD_NEGOCIOS_2_0_POR_AMBIENTE = {
    "prod": 18410571736,
    "dev": 18411789432,
}
AUTOBACKOFFICE_ENVIRONMENT = (
    os.getenv("AUTOBACKOFFICE_ENVIRONMENT") or os.getenv("ENVIRONMENT") or "dev"
).strip().lower()
BOARD_NEGOCIOS_2_0 = _BOARD_NEGOCIOS_2_0_POR_AMBIENTE.get(
    AUTOBACKOFFICE_ENVIRONMENT, _BOARD_NEGOCIOS_2_0_POR_AMBIENTE["dev"]
)

CAMINHO_CACHE_DEFAULT = os.path.join(
    dir_script, "Dados", "AutoBackoffice_2_0", "negocios_monday_2_0.json"
)


######################################################################################

RECUPERACAO_ID_MONDAY_DEFAULT = "12065876834"
RECUPERACAO_ID_NEGOCIO_DEFAULT = ""


######################################################################################

CAMPOS_CACHE_IGNORADOS = frozenset(
    {
        "id_monday",
        "deletado_do_monday_em",
        "regra_remocao_aplicada",
        "recuperado_em",
        "id_monday_anterior",
        "status_item_monday",
        "atualizado_em",
        "nome_processo",
        "nome_negocio",
        "ultima_atualizacao",
    }
)


def _indexar_negocios_monday_por_id_negocio(
    itens: Dict[str, Any] | None,
) -> Dict[str, Dict[str, Any]]:
    normalizados: Dict[str, Dict[str, Any]] = {}
    for chave_original, item in (itens or {}).items():
        if not isinstance(item, dict):
            continue
        item_normalizado = dict(item)
        id_monday = item_normalizado.get("id_monday")
        if not id_monday and chave_original:
            id_monday = str(chave_original)
            item_normalizado["id_monday"] = id_monday
        id_negocio = item_normalizado.get("id_negocio")
        if not id_negocio:
            continue
        chave_id_negocio = str(id_negocio).strip()
        if chave_id_negocio:
            normalizados[chave_id_negocio] = item_normalizado
    return normalizados


def carregar_cache(caminho: str) -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(caminho):
        raise FileNotFoundError(
            f"Cache `{caminho}` não encontrado. Rode o AutoBackoffice 2.0 ao menos uma "
            f"vez para gerar o histórico local."
        )
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            bruto = json.load(f)
    except UnicodeDecodeError:
        with open(caminho, "r", encoding="latin-1") as f:
            bruto = json.load(f)
    if not isinstance(bruto, dict):
        raise ValueError(f"Cache inválido (esperado dict): {caminho}")
    return _indexar_negocios_monday_por_id_negocio(bruto)


def salvar_cache(cache: Dict[str, Any], caminho: str) -> None:
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4, ensure_ascii=False, default=str)


def _resolver_ids_alvo(args: argparse.Namespace) -> Tuple[str, str]:
    id_monday = (
        (args.id_monday or "").strip()
        or (os.getenv("RECUPERACAO_ID_MONDAY") or "").strip()
        or str(RECUPERACAO_ID_MONDAY_DEFAULT or "").strip()
    )
    id_negocio = (
        (args.id_negocio or "").strip()
        or (os.getenv("RECUPERACAO_ID_NEGOCIO") or "").strip()
        or str(RECUPERACAO_ID_NEGOCIO_DEFAULT or "").strip()
    )
    return id_monday, id_negocio


def localizar_item_no_cache(
    cache: Dict[str, Dict[str, Any]],
    id_monday: str,
    id_negocio: str,
) -> Tuple[str, Dict[str, Any]]:
    if id_monday:
        alvo = str(id_monday)
        for chave_id_negocio, item in cache.items():
            if str(item.get("id_monday") or "") == alvo:
                return chave_id_negocio, item
        raise KeyError(
            f"id_monday={alvo} não encontrado no cache. "
            f"Confirme o ID antigo gravado antes da remoção."
        )

    if id_negocio:
        chave = str(id_negocio)
        if chave in cache:
            return chave, cache[chave]
        raise KeyError(
            f"id_negocio={chave} não encontrado no cache local."
        )

    raise ValueError(
        "Informe `--id-monday` ou `--id-negocio` "
        "(ou env RECUPERACAO_ID_MONDAY / RECUPERACAO_ID_NEGOCIO)."
    )


def _resolver_nome_item(item: Dict[str, Any]) -> str:
    for chave in ("nome_processo", "nome_negocio", "name"):
        valor = (item.get(chave) or "").strip()
        if valor:
            return valor
    partes = [
        item.get("nome_empreendimento") or "Empreendimento sem nome",
        item.get("nome_torre") or "Torre sem nome",
        str(item.get("numero_unidade") or "Sem número da unidade"),
        item.get("nome_cliente") or "Cliente sem nome",
    ]
    return " | ".join(str(p) for p in partes).upper()


def _normalizar_valor_coluna(chave: str, valor: Any) -> Any | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(valor, dict):
        if "updated_at" in valor and "updater_id" in valor:
            return None
        if "labels" in valor or ("url" in valor and "text" in valor):
            return valor
        if "item_ids" in valor:
            return valor
        return valor
    if isinstance(valor, list):
        if chave == "pendencias_analise":
            return {"labels": valor}
        if valor and isinstance(valor[0], dict) and "id" in valor[0]:
            return {"item_ids": [str(x["id"]) for x in valor]}
    return valor


def montar_column_values_do_cache(
    item: Dict[str, Any],
    board_id: int,
) -> Dict[str, Any]:
    payload_melnick: Dict[str, Any] = {}
    for chave, valor in item.items():
        if chave in CAMPOS_CACHE_IGNORADOS:
            continue
        normalizado = _normalizar_valor_coluna(chave, valor)
        if normalizado is not None:
            payload_melnick[chave] = normalizado
    column_values = map_dict_keys(
        fonte="monday",
        id_mapeamento=str(board_id),
        dict_to_map=payload_melnick,
        invert_mapping=True,
    )
    return column_values


def item_ja_existe_no_monday(
    cliente: ClienteMonday,
    board_id: int,
    id_negocio: str,
) -> bool:
    existentes = cliente.get_items(
        board_id=board_id,
        column_id="customer_process_id",
        value=str(id_negocio),
    )
    return bool(existentes)


def recuperar_negocio(
    cliente: ClienteMonday,
    cache: Dict[str, Dict[str, Any]],
    chave_id_negocio: str,
    item: Dict[str, Any],
    board_id: int,
    dry_run: bool = False,
    force: bool = False,
) -> str | None:
    id_negocio = str(item.get("id_negocio") or chave_id_negocio)
    id_monday_anterior = str(item.get("id_monday") or "")

    if not item.get("deletado_do_monday_em") and not force:
        raise ValueError(
            f"Negócio {id_negocio} não possui `deletado_do_monday_em` no cache. "
            f"Parece ainda ativo ou nunca passou pela remoção automática. "
            f"Use `--force` apenas se tiver certeza."
        )

    if item_ja_existe_no_monday(cliente, board_id, id_negocio):
        raise ValueError(
            f"Já existe item no Monday com id_negocio={id_negocio}. "
            f"Abortando para evitar duplicidade."
        )

    nome_item = _resolver_nome_item(item)
    column_values = montar_column_values_do_cache(item, board_id)

    logger.info(
        "Alvo: id_negocio=%s, id_monday_anterior=%s, status=%s, "
        "deletado_em=%s, regra=%s.",
        id_negocio,
        id_monday_anterior or "(vazio)",
        item.get("status_negocio"),
        item.get("deletado_do_monday_em"),
        item.get("regra_remocao_aplicada"),
    )
    logger.info("Nome do item no Monday: %s", nome_item)
    logger.info("Colunas a enviar (%d): %s", len(column_values), list(column_values.keys()))

    if dry_run:
        logger.info("[DRY-RUN] Item NÃO foi criado no Monday.")
        return None

    novo_id_monday = cliente.create_item(
        board_id=board_id,
        item_name=nome_item,
        column_values=column_values,
        create_labels_if_missing=True,
    )

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item_atualizado = dict(item)
    if id_monday_anterior:
        item_atualizado["id_monday_anterior"] = id_monday_anterior
    item_atualizado["id_monday"] = str(novo_id_monday)
    item_atualizado["status_item_monday"] = "active"
    item_atualizado["recuperado_em"] = agora
    item_atualizado.pop("deletado_do_monday_em", None)
    item_atualizado.pop("regra_remocao_aplicada", None)
    cache[chave_id_negocio] = item_atualizado

    logger.info(
        "Negócio recuperado: id_negocio=%s, id_monday_anterior=%s, id_monday_novo=%s.",
        id_negocio,
        id_monday_anterior or "(vazio)",
        novo_id_monday,
    )
    return str(novo_id_monday)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recria no Monday.com um negócio removido, usando o cache histórico "
            "do AutoBackoffice 2.0."
        )
    )
    parser.add_argument(
        "--id-monday",
        default="",
        help=(
            "ID numérico antigo do item no Monday (antes da deleção). "
            "Prioridade sobre --id-negocio."
        ),
    )
    parser.add_argument(
        "--id-negocio",
        default="",
        help="UUID do negócio no Otto (`customer_process_id`).",
    )
    parser.add_argument(
        "--cache",
        default=CAMINHO_CACHE_DEFAULT,
        help=f"Caminho do cache local. Default: {CAMINHO_CACHE_DEFAULT}",
    )
    parser.add_argument(
        "--board-id",
        type=int,
        default=None,
        help=(
            f"Board NEGOCIOS do Monday. Default: {BOARD_NEGOCIOS_2_0} "
            f"(ambiente {AUTOBACKOFFICE_ENVIRONMENT})."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a recuperação sem criar item nem alterar o cache.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Permite recuperar mesmo sem `deletado_do_monday_em` no cache "
            "(use com cautela)."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    board_id = int(args.board_id or BOARD_NEGOCIOS_2_0)
    id_monday, id_negocio = _resolver_ids_alvo(args)

    logger.info("=" * 60)
    logger.info("Recuperação de ID — AutoBackoffice 2.0")
    logger.info("Ambiente: %s (board=%s)", AUTOBACKOFFICE_ENVIRONMENT, board_id)
    logger.info("id_monday=%s", id_monday or "(vazio)")
    logger.info("id_negocio=%s", id_negocio or "(vazio)")
    logger.info("Cache: %s", args.cache)
    logger.info("Dry-run: %s", args.dry_run)
    logger.info("Force: %s", args.force)
    logger.info("=" * 60)

    if not id_monday and not id_negocio:
        logger.error(
            "Nenhum alvo informado. Use --id-monday ou --id-negocio, "
            "ou defina RECUPERACAO_ID_MONDAY / RECUPERACAO_ID_NEGOCIO."
        )
        return 2

    chave_api = (os.getenv("MONDAY_API_KEY") or os.getenv("MELNICK_MONDAY_API_KEY") or "").strip()
    if not chave_api:
        logger.error("MONDAY_API_KEY não configurada no ambiente/.env.")
        return 2

    try:
        cache = carregar_cache(args.cache)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 2

    try:
        chave_id_negocio, item = localizar_item_no_cache(cache, id_monday, id_negocio)
    except KeyError as exc:
        logger.error("%s", exc)
        return 2

    cliente = ClienteMonday(api_key=chave_api)

    try:
        novo_id = recuperar_negocio(
            cliente=cliente,
            cache=cache,
            chave_id_negocio=chave_id_negocio,
            item=item,
            board_id=board_id,
            dry_run=args.dry_run,
            force=args.force,
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    except Exception as exc:
        logger.exception("Falha ao recuperar negócio: %s", exc)
        return 1

    if not args.dry_run and novo_id:
        try:
            salvar_cache(cache, args.cache)
            logger.info("Cache atualizado em %s.", args.cache)
        except Exception as exc:
            logger.exception(
                "Item criado no Monday (id=%s), mas falha ao salvar cache: %s",
                novo_id,
                exc,
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
