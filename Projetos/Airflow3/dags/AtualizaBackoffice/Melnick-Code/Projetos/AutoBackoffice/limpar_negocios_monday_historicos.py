"""
Limpeza histórica de negócios no Monday.com.

Remove itens do board NEGOCIOS do Monday.com cuja data de referência (por padrão,
`negocio_criado_em`) seja ANTERIOR a uma data de corte configurável (por padrão,
01/01/2026), mantendo os itens no cache local `negocios_monday.json` como
histórico.

O script é dinâmico/reusável: aceita parâmetros via CLI (data de corte, campo de
data, status alvo, caminho do cache, dry-run) e pode ser agendado no Airflow
periodicamente para aliviar o volume de itens no Monday.com.

Pré-requisitos:
    - `negocios_monday.json` atualizado (rode `AutoBackoffice.py` antes, ou aponte
      o arquivo gerado pelo Airflow).
    - Variável de ambiente `MONDAY_API_KEY` no `.env` da raiz do diretório.

Exemplos:
    # Limpeza padrão (usa SÓ o cache - rápido, presume cache sincronizado):
    python limpar_negocios_monday_historicos.py

    # Simular sem deletar (auditoria):
    python limpar_negocios_monday_historicos.py --dry-run

    # Varrer TODOS os itens do Monday antes (mais lento, mas completo):
    python limpar_negocios_monday_historicos.py --varrer-monday --dry-run

    # Outra data de corte:
    python limpar_negocios_monday_historicos.py --data-corte 2025-01-01

    # Só negócios "Caiu" e "Concluído":
    python limpar_negocios_monday_historicos.py --status Caiu Concluído

    # Outro campo de data (ex.: última atualização):
    python limpar_negocios_monday_historicos.py --campo-data atualizado_em
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List

from dotenv import load_dotenv


#### LOGGING ####

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LimpezaHistoricaMonday")


#### BOOTSTRAP DE IMPORTS ####
# Reaproveita a mesma estratégia do `AutoBackoffice.py`: o script mora em
# `Projetos/AutoBackoffice/` e precisa importar `Módulos/cliente_monday.py` da raiz
# do repositório (dois níveis acima). O `.env` fica na raiz do workspace (um nível
# acima da raiz do repositório).

dir_script = os.path.dirname(os.path.abspath(__file__))
pasta_repositorio = os.path.abspath(os.path.join(dir_script, "..", ".."))
if pasta_repositorio not in sys.path:
    sys.path.append(pasta_repositorio)

from Módulos.cliente_monday import ClienteMonday  # noqa: E402

# Localização do `.env`:
#   1. Mesma convenção do `AutoBackoffice.py`: raiz do workspace (um nível acima do
#      repositório) -> `E:\Projetos\VS_Code\.env`.
#   2. Fallback p/ Airflow/containers onde o mount do `.env` fica DENTRO da raiz do
#      repo -> `<repo>/.env`.
#
# Importante: `load_dotenv` por padrão NÃO sobrescreve variáveis já existentes no
# ambiente, então se o primeiro caminho popular a variável, o fallback não "estraga"
# o valor. O log abaixo ajuda a depurar caso de token inválido (mostra só o tamanho
# e os primeiros/últimos caracteres, sem vazar o token no log).

dir_workspace = os.path.abspath(os.path.join(pasta_repositorio, ".."))
arquivo_env_workspace = os.path.join(dir_workspace, ".env")
arquivo_env_repo = os.path.join(pasta_repositorio, ".env")
env_carregado_de = None
if os.path.exists(arquivo_env_workspace):
    load_dotenv(arquivo_env_workspace)
    env_carregado_de = arquivo_env_workspace
elif os.path.exists(arquivo_env_repo):
    load_dotenv(arquivo_env_repo)
    env_carregado_de = arquivo_env_repo


def _descrever_token(valor: str | None) -> str:
    """
    Formata um resumo seguro de um token (tamanho + prefixo/sufixo) para logar sem
    vazar o segredo completo. Ajuda a detectar tokens vazios, com espaços/aspas e
    diferenciar múltiplos tokens em `.env` distintos.
    """
    if valor is None:
        return "<ausente>"
    if valor == "":
        return "<vazio>"
    n = len(valor)
    if n <= 10:
        return f"<len={n}, valor mascarado>"
    return f"<len={n}, começa com {valor[:4]!r}, termina com {valor[-4:]!r}>"


#### CONFIGURAÇÃO PADRÃO ####
# Valores padrões aplicados quando a CLI não os fornece. Alterar aqui afeta o
# comportamento "default" do script - útil quando o script é agendado sem argumentos.

CONFIG_DEFAULT: Dict[str, Any] = {
    "data_corte": datetime(2026, 3, 1),
    "campo_data_referencia": "negocio_criado_em",
    # Lista de `status_negocio` alvos; `None` = qualquer status.
    "status_negocio_any": None,
    "caminho_cache": os.path.join(dir_script, "Dados", "negocios_monday.json"),
    "regra_nome": "limpeza_historica",
    "dry_run": False,
    "varrer_monday": False,
    # ID do board NEGOCIOS. Mantido em sincronia com `AutoBackoffice.py` (IDS_BOARDS).
    "board_id_negocios": 18392682833,
}


#### HELPERS ####


def _parse_datetime(valor: Any) -> datetime | None:
    """
    Converte string ISO (`YYYY-MM-DD HH:MM:SS` ou `YYYY-MM-DD`), `datetime` ou `None`
    em `datetime`. Retorna `None` quando não consegue parsear - o caller pode decidir
    se isso deve ser tratado como "não elegível para deleção" (padrão conservador).
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor
    texto = str(valor)[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, fmt)
        except (ValueError, TypeError):
            continue
    return None


def carregar_cache(caminho: str) -> Dict[str, Dict[str, Any]]:
    """
    Carrega o cache local do disco, com tolerância a legados em cp1252/latin-1
    (Windows) vs utf-8 (Airflow/Linux). Aborta se o arquivo não existir - rodar sem
    cache zeraria a base histórica e poderia deletar itens que ainda não foram
    espelhados localmente.
    """
    if not os.path.exists(caminho):
        raise FileNotFoundError(
            f"Cache `{caminho}` não encontrado. Rode o `AutoBackoffice.py` para gerar "
            f"o cache antes de executar esta limpeza, ou aponte `--cache` para o "
            f"arquivo correto."
        )
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except UnicodeDecodeError:
        logger.warning(
            f"Cache `{caminho}` não está em UTF-8. Tentando `latin-1` (legado Windows)."
        )
        with open(caminho, "r", encoding="latin-1") as f:
            return json.load(f)


def salvar_cache(cache: Dict[str, Any], caminho: str) -> None:
    """Persiste o cache em UTF-8 com `default=str` para serializar `datetime`."""
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4, ensure_ascii=False, default=str)


def construir_predicado(config: Dict[str, Any]) -> Callable[[Dict[str, Any]], bool]:
    """
    Monta o predicado que decide se um item do cache é elegível para deleção. As
    regras são AND e identificadas aqui para ficar simples trocar/expandir via
    configuração:

        1. Item tem `id_monday` (sem isso não há o que deletar).
        2. Item ainda não foi deletado (`deletado_do_monday_em` ausente/None).
        3. `campo_data_referencia` parseia para `datetime` válido.
        4. Valor parseado é ANTERIOR a `data_corte`.
        5. Se `status_negocio_any` for lista, o item precisa estar nela.
    """
    data_corte: datetime = config["data_corte"]
    campo_data: str = config["campo_data_referencia"]
    status_any: List[str] | None = config["status_negocio_any"]

    def predicado(item: Dict[str, Any]) -> bool:
        if not item.get("id_monday"):
            return False
        if item.get("deletado_do_monday_em"):
            return False
        data_item = _parse_datetime(item.get(campo_data))
        if data_item is None:
            return False
        if data_item >= data_corte:
            return False
        if status_any is not None and item.get("status_negocio") not in status_any:
            return False
        return True

    return predicado


def varrer_monday_e_merge_cache(
    cliente: ClienteMonday,
    cache: Dict[str, Dict[str, Any]],
    board_id: int,
) -> Dict[str, int]:
    """
    Busca TODOS os itens do board NEGOCIOS no Monday.com (com paginação interna do
    `get_items`) e mescla com o `cache` local, indexando por `id_negocio` do Otto.

    Por que: o `AutoBackoffice.py` só popula o cache com itens da janela Otto ativa
    e com itens atualizados recentemente. Negócios ANTIGOS que já saíram daquela
    janela (e não têm atualização recente) NÃO aparecem no cache - então uma
    limpeza por data baseada só no cache perde esses itens. Esta varredura resolve
    isso.

    Regras de merge:
      - Item do Monday com `id_negocio` já no cache -> atualiza os campos atuais,
        PRESERVANDO metadados de histórico (`deletado_do_monday_em`,
        `regra_remocao_aplicada`). Isso evita reprocessar itens já deletados.
      - Item do Monday com `id_negocio` novo -> adiciona no cache com o `id_monday`
        preenchido.
      - Item do Monday SEM `id_negocio` (coluna vazia no Monday) -> indexa pelo
        próprio `id_monday` com prefixo `"sem_id_negocio:"` para não colidir com
        chaves válidas. Isso permite auditar pelo log, mesmo que o predicado por
        data ainda funcione.

    Retorna estatísticas do merge.
    """
    logger.info(
        f"Varredura completa no Monday (board {board_id})... "
        f"pode levar alguns segundos dependendo do volume."
    )
    itens_monday = cliente.get_items(board_id=board_id)
    logger.info(f"Itens recebidos do Monday: {len(itens_monday)}.")

    stats = {
        "itens_monday": len(itens_monday),
        "novos_no_cache": 0,
        "atualizados_no_cache": 0,
        "sem_id_negocio": 0,
    }

    for id_monday, dados in itens_monday.items():
        id_negocio = dados.get("id_negocio")
        # Sempre força o `id_monday` presente, já que o `get_items` devolve como
        # chave do dict externo e não como campo interno.
        dados["id_monday"] = str(id_monday)

        if not id_negocio:
            stats["sem_id_negocio"] += 1
            chave_fallback = f"sem_id_negocio:{id_monday}"
            cache[chave_fallback] = dados
            continue

        id_negocio = str(id_negocio)
        if id_negocio in cache:
            existente = cache[id_negocio]
            # Preserva metadados de histórico para idempotência.
            deletado_em = existente.get("deletado_do_monday_em")
            regra_aplicada = existente.get("regra_remocao_aplicada")
            existente.update(dados)
            if deletado_em:
                existente["deletado_do_monday_em"] = deletado_em
            if regra_aplicada:
                existente["regra_remocao_aplicada"] = regra_aplicada
            stats["atualizados_no_cache"] += 1
        else:
            cache[id_negocio] = dados
            stats["novos_no_cache"] += 1

    logger.info(
        f"Merge concluído. "
        f"Itens do Monday: {stats['itens_monday']}. "
        f"Novos no cache: {stats['novos_no_cache']}. "
        f"Atualizados no cache: {stats['atualizados_no_cache']}. "
        f"Sem `id_negocio` no Monday: {stats['sem_id_negocio']}."
    )
    return stats


def diagnosticar_predicado(
    cache: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
) -> None:
    """
    Emite logs com a contagem de itens rejeitados por CADA regra do predicado,
    facilitando entender por que poucos itens são elegíveis. Rodar isso no início do
    `limpar_negocios_historicos` deixa evidente se o cache está "vazio" (muitos
    sem `id_monday`) ou se o filtro de data/status está excluindo demais.
    """
    campo_data = config["campo_data_referencia"]
    data_corte: datetime = config["data_corte"]
    status_any: List[str] | None = config["status_negocio_any"]

    total = len(cache)
    sem_id_monday = 0
    ja_deletados = 0
    data_invalida = 0
    data_posterior = 0
    status_fora = 0
    elegiveis = 0

    for item in cache.values():
        if not item.get("id_monday"):
            sem_id_monday += 1
            continue
        if item.get("deletado_do_monday_em"):
            ja_deletados += 1
            continue
        d = _parse_datetime(item.get(campo_data))
        if d is None:
            data_invalida += 1
            continue
        if d >= data_corte:
            data_posterior += 1
            continue
        if status_any is not None and item.get("status_negocio") not in status_any:
            status_fora += 1
            continue
        elegiveis += 1

    logger.info(
        f"Diagnóstico do predicado (campo={campo_data}, corte={data_corte:%Y-%m-%d}): "
        f"total={total}, "
        f"sem id_monday={sem_id_monday}, "
        f"já deletados={ja_deletados}, "
        f"data inválida/vazia={data_invalida}, "
        f"data >= corte={data_posterior}, "
        f"fora dos status alvo={status_fora}, "
        f"ELEGÍVEIS={elegiveis}."
    )


def limpar_negocios_historicos(
    cliente: ClienteMonday,
    cache: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, int]:
    """
    Percorre o cache aplicando o predicado. Para cada item elegível:

      - Em modo normal: chama `cliente.delete_item` e anota no cache
        `deletado_do_monday_em` (timestamp atual) + `regra_remocao_aplicada` (rótulo
        da execução) para permitir auditoria e evitar reprocesso em execuções futuras.
      - Em `dry_run`: apenas loga o que seria feito, sem tocar no Monday nem no cache.

    Uma falha pontual (ex.: item já deletado remotamente) não derruba o batch inteiro
    - é logada como `falhas` no resumo e o loop continua com os próximos itens.
    """
    predicado = construir_predicado(config)
    regra_nome: str = config["regra_nome"]
    campo_data: str = config["campo_data_referencia"]
    dry_run: bool = config["dry_run"]

    resumo = {
        "total_avaliados": 0,
        "ja_deletados_pulados": 0,
        "elegiveis": 0,
        "deletados": 0,
        "falhas": 0,
    }

    for id_negocio, item in cache.items():
        resumo["total_avaliados"] += 1

        if item.get("deletado_do_monday_em"):
            resumo["ja_deletados_pulados"] += 1
            continue

        if not predicado(item):
            continue

        resumo["elegiveis"] += 1
        id_monday = str(item["id_monday"])
        data_item = item.get(campo_data)
        status_item = item.get("status_negocio")

        if dry_run:
            logger.info(
                f"[DRY-RUN] Elegível: id_monday={id_monday}, id_negocio={id_negocio}, "
                f"{campo_data}={data_item}, status={status_item}."
            )
            continue

        try:
            cliente.delete_item(id_monday)
            item["deletado_do_monday_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            item["regra_remocao_aplicada"] = regra_nome
            resumo["deletados"] += 1
            logger.info(
                f"Item deletado no Monday: id_monday={id_monday}, "
                f"id_negocio={id_negocio}, {campo_data}={data_item}, status={status_item}. "
                f"JSON mantido como histórico."
            )
        except Exception as exc:
            resumo["falhas"] += 1
            logger.exception(
                f"Falha ao deletar id_monday={id_monday} (id_negocio={id_negocio}): "
                f"{exc}. Prosseguindo com os próximos."
            )

    return resumo


#### CLI ####


def parse_args() -> argparse.Namespace:
    """
    Define os argumentos de linha de comando. Os defaults refletem `CONFIG_DEFAULT`
    e podem ser sobrescritos a cada execução sem alterar o código-fonte - importante
    para uso manual ad-hoc (dry-run, cortes pontuais) sem comprometer o cron/Airflow.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Remove do Monday.com itens de negócio anteriores a uma data de corte, "
            "mantendo-os em `negocios_monday.json` como histórico."
        )
    )
    parser.add_argument(
        "--data-corte",
        default=CONFIG_DEFAULT["data_corte"].strftime("%Y-%m-%d"),
        help=(
            "Data de corte no formato YYYY-MM-DD. Negócios com "
            "`campo_data_referencia` ANTERIOR serão deletados. Default: "
            f"{CONFIG_DEFAULT['data_corte']:%Y-%m-%d}."
        ),
    )
    parser.add_argument(
        "--campo-data",
        default=CONFIG_DEFAULT["campo_data_referencia"],
        help=(
            "Campo do cache usado como referência de data. Ex.: "
            "`negocio_criado_em`, `atualizado_em`, `data_reserva`, "
            "`proposta_criada_em`. Default: "
            f"{CONFIG_DEFAULT['campo_data_referencia']}."
        ),
    )
    parser.add_argument(
        "--status",
        nargs="*",
        default=None,
        metavar="STATUS",
        help=(
            "Lista de `status_negocio` alvos (separados por espaço). Ex.: "
            "--status Caiu Concluido. Default: qualquer status."
        ),
    )
    parser.add_argument(
        "--cache",
        default=None,
        help=(
            "Caminho customizado para o arquivo `negocios_monday.json`. Default: "
            f"{CONFIG_DEFAULT['caminho_cache']}."
        ),
    )
    parser.add_argument(
        "--regra-nome",
        default=CONFIG_DEFAULT["regra_nome"],
        help=(
            "Rótulo gravado em `regra_remocao_aplicada` para cada item deletado. Útil "
            "para auditoria e para diferenciar execuções. Default: "
            f"{CONFIG_DEFAULT['regra_nome']}."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Apenas simula: lista os itens elegíveis sem chamar a API nem salvar o "
            "cache. Recomendado na primeira execução para auditar."
        ),
    )
    parser.add_argument(
        "--varrer-monday",
        action="store_true",
        help=(
            "Antes de aplicar o predicado, faz varredura COMPLETA do board NEGOCIOS "
            "no Monday e mescla com o cache. Útil quando negócios antigos "
            "não estão no cache (caso do `AutoBackoffice.py` rodando só na janela "
            "Otto atual). Mais lento mas captura todos os itens históricos."
        ),
    )
    parser.add_argument(
        "--board-id",
        type=int,
        default=CONFIG_DEFAULT["board_id_negocios"],
        help=(
            "ID do board NEGOCIOS no Monday.com. Default: "
            f"{CONFIG_DEFAULT['board_id_negocios']}."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    config = dict(CONFIG_DEFAULT)
    try:
        config["data_corte"] = datetime.strptime(args.data_corte, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Data inválida: `{args.data_corte}`. Use formato YYYY-MM-DD.")
        return 2

    config["campo_data_referencia"] = args.campo_data
    config["status_negocio_any"] = list(args.status) if args.status else None
    if args.cache:
        config["caminho_cache"] = args.cache
    config["regra_nome"] = args.regra_nome
    config["dry_run"] = args.dry_run
    config["varrer_monday"] = args.varrer_monday
    config["board_id_negocios"] = args.board_id

    logger.info("=" * 60)
    logger.info("Limpeza Histórica de Negócios no Monday.com")
    logger.info(f"Data de corte (exclusiva): {config['data_corte']:%Y-%m-%d}")
    logger.info(f"Campo de data: {config['campo_data_referencia']}")
    logger.info(f"Status alvos: {config['status_negocio_any'] or 'qualquer'}")
    logger.info(f"Cache: {config['caminho_cache']}")
    logger.info(f"Regra (tag): {config['regra_nome']}")
    logger.info(f"Dry-run: {config['dry_run']}")
    logger.info(f"Varrer Monday antes: {config['varrer_monday']}")
    logger.info(f"Board ID: {config['board_id_negocios']}")
    logger.info("=" * 60)

    try:
        cache = carregar_cache(config["caminho_cache"])
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 2

    logger.info(f"Cache carregado com {len(cache)} item(ns).")

    # Log de diagnóstico do `.env`: mostra DE ONDE o token foi carregado, o que ajuda
    # a identificar casos em que dois `.env` coexistem (um correto na workspace e um
    # vazio/antigo na raiz do repo) e o fallback acaba pegando o errado.
    if env_carregado_de:
        logger.info(f"`.env` carregado de: {env_carregado_de}")
    else:
        logger.warning(
            "Nenhum `.env` encontrado em "
            f"{arquivo_env_workspace!r} nem em {arquivo_env_repo!r}. "
            "Confiando apenas em variáveis já presentes no ambiente."
        )

    chave_api_monday_raw = os.getenv("MONDAY_API_KEY")
    # `.strip()` protege contra espaços/quebras de linha acidentais no `.env` — causa
    # comum de `NOT_AUTHENTICATED` mesmo com a variável "definida".
    chave_api_monday = chave_api_monday_raw.strip() if chave_api_monday_raw else ""
    logger.info(f"MONDAY_API_KEY: {_descrever_token(chave_api_monday)}")
    if not chave_api_monday:
        logger.error(
            "Variável `MONDAY_API_KEY` não configurada no ambiente/`.env`. "
            "Abortando para evitar chamadas não autenticadas."
        )
        return 2

    cliente = ClienteMonday(api_key=chave_api_monday)

    # Quando solicitado, varre o Monday e mescla no cache ANTES do predicado.
    # Isso garante que itens antigos (fora da janela Otto atual do AutoBackoffice)
    # também sejam considerados. Em execuções frequentes com cache atualizado,
    # a varredura é dispensável e evita latência extra.
    if config["varrer_monday"]:
        varrer_monday_e_merge_cache(
            cliente=cliente,
            cache=cache,
            board_id=int(config["board_id_negocios"]),
        )

    # Diagnóstico PRÉ-execução: explica por que cada item foi (ou não) selecionado.
    # Roda mesmo em dry-run, para auditoria rápida.
    diagnosticar_predicado(cache=cache, config=config)

    resumo = limpar_negocios_historicos(cliente=cliente, cache=cache, config=config)

    logger.info("-" * 60)
    logger.info(
        "Resumo: "
        f"avaliados={resumo['total_avaliados']}, "
        f"elegíveis={resumo['elegiveis']}, "
        f"deletados={resumo['deletados']}, "
        f"falhas={resumo['falhas']}, "
        f"já deletados anteriormente (pulados)={resumo['ja_deletados_pulados']}."
    )

    # Persiste o cache quando houve alteração de estado relevante:
    #   - Deletou ao menos 1 item, OU
    #   - Fez varredura do Monday (enriqueceu o cache com itens novos/atualizados).
    # Em dry-run, o cache é mantido intacto por design (o usuário pode auditar e
    # rodar de verdade depois sem "contaminar" o arquivo).
    precisa_salvar = not config["dry_run"] and (
        resumo["deletados"] > 0 or config["varrer_monday"]
    )
    if precisa_salvar:
        try:
            salvar_cache(cache, config["caminho_cache"])
            logger.info(f"Cache atualizado salvo em {config['caminho_cache']}.")
        except Exception as exc:
            logger.exception(
                f"Falha ao salvar o cache ({config['caminho_cache']}): {exc}. "
                f"Os itens foram deletados no Monday mas não foram marcados localmente, "
                f"o que pode causar retrabalho na próxima execução."
            )
            return 1
    else:
        if config["dry_run"]:
            motivo = "dry-run"
        elif resumo["deletados"] == 0:
            motivo = "nenhum item deletado"
        else:
            motivo = "sem necessidade"
        logger.info(f"Cache não foi modificado ({motivo}).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
