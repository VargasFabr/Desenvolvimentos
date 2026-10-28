# AutoBackoffice 2.0 — atualização do board duplicado de negócios no Monday (sem board
# de contas: dados de corretor/imobiliária vão como texto na página).
# Fontes: Otto (+ reservas/propostas). Não grava no board de negócios original.

# Versão: 2.0

#### IMPORTAÇÔES ####
# %%
# STDLIB
import logging
import sys
import os
import json
from typing import Any, Callable, Dict, Tuple
import time
from datetime import datetime, timedelta, timezone

# TERCEIROS
from dotenv import load_dotenv


#### CONFIGURAÇÔES ####

# Criação de um logger para registrar as atividades do script, como erros e informações importantes.

logging.basicConfig(
    level=logging.INFO, # Define o nível de log para INFO, ou seja, ele vai registrar mensagens de INFO, WARNING, ERROR e CRITICAL
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", # Define o formato das mensagens de log para incluir a data/hora, o nome do log de origem, o nível do log e a mensagem
    stream=sys.stdout # Define que as mensagens de log devem ser enviadas para a saída padrão (console)
)

logger = logging.getLogger("AutoBackoffice2_0")  # Logger distinto do AutoBackoffice 1.0

# Descobre o caminho da pasta atual onde este script está rodando,
#   para usar como referência para os arquivos de dados e logs.
dir_script = os.path.dirname(os.path.abspath(__file__))

# Pasta de dados isolada do AutoBackoffice 1.0 (cache, última atualização, empresas GC local).
pasta_dados = os.path.join(dir_script, "Dados", "AutoBackoffice_2_0")
if not os.path.exists(pasta_dados):
    os.makedirs(pasta_dados)

# Temos que adicionar o caminho da pasta raiz do repositório
#   para conseguir importar os módulos necessários.
pasta_repositorio = os.path.abspath(os.path.join(dir_script, "..", "..")) #Volta duas pastas para chegar na pasta raiz do repositório
logger.info(f"Caminho da pasta raiz do repositório: {pasta_repositorio}")

if pasta_repositorio not in sys.path:
    sys.path.append(pasta_repositorio)

# IMPORTAÇÕES LOCAIS

from Módulos.cliente_monday import ClienteMonday
from Módulos.cliente_otto import ClienteOtto, TEST_KEYS, STATUS_RESERVA, STATUS_PROPOSTA
from Módulos.mapeamento_dados import map_dict_keys

# Board de negócios do AutoBackoffice 2.0 (Monday). Mapeamento em `Módulos/mapeamento_dados.py`.
# Ambientes:
#   - prod: 18410571736
#   - dev:  18411789432
_BOARD_NEGOCIOS_2_0_POR_AMBIENTE = {
    "prod": 18410571736,
    "dev": 18411789432,
}

# Adiciona o caminho da pasta raiz do diretório para conseguir importar os módulos necessários.
dir_workspace = os.path.abspath(os.path.join(pasta_repositorio, "..")) # Volta mais uma pasta para chegar na pasta raiz do diretório, onde deve estar o arquivo .env
logger.info(f"Caminho da pasta raiz do diretório: {dir_workspace}")

# .env: pasta acima do repositório (ex.: VS Code workspace) e/ou raiz do repositório (comum no Airflow, só o clone do Melnick-Code).
# O segundo, quando existe, tem precedência (chama `load_dotenv` depois com `override=True`).
arquivo_env_pai = os.path.join(dir_workspace, ".env")
arquivo_env_repo = os.path.join(pasta_repositorio, ".env")
_env_carregados: list[str] = []
if os.path.exists(arquivo_env_pai):
    load_dotenv(arquivo_env_pai, override=True)
    _env_carregados.append(arquivo_env_pai)
else:
    logger.info(
        "Arquivo .env da pasta-pai inexistente (ok se você usar só o .env do repositório): %s",
        arquivo_env_pai,
    )
if os.path.exists(arquivo_env_repo):
    load_dotenv(arquivo_env_repo, override=True)
    _env_carregados.append(arquivo_env_repo)
if not _env_carregados:
    msg = (
        f"Nenhum .env encontrado. Crie em {arquivo_env_pai} e/ou {arquivo_env_repo}."
    )
    logger.error(msg)
    raise FileNotFoundError(msg)
logger.info("Arquivos .env carregados: %s", " | ".join(_env_carregados))

# Só agora (depois do load_dotenv) resolvemos o ambiente e o board.
# Mantém compatibilidade com variáveis antigas (ENVIRONMENT), mas prioriza a nova.
AUTOBACKOFFICE_ENVIRONMENT = (
    os.getenv("AUTOBACKOFFICE_ENVIRONMENT")
    or os.getenv("ENVIRONMENT")
    or "dev"
).strip().lower()
BOARD_NEGOCIOS_2_0 = _BOARD_NEGOCIOS_2_0_POR_AMBIENTE.get(
    AUTOBACKOFFICE_ENVIRONMENT, _BOARD_NEGOCIOS_2_0_POR_AMBIENTE["dev"]
)
logger.info(
    "--- AMBIENTE --- AutoBackoffice 2.0: %s (board NEGOCIOS=%s).",
    AUTOBACKOFFICE_ENVIRONMENT,
    BOARD_NEGOCIOS_2_0,
)

# Modo opcional: rodar apenas um item para debug (dev/prod).
# Preferencialmente por `id_monday` (pulse id). Opcionalmente por `id_negocio` (UUID do Otto).
#
# Como funciona (prioridade):
#   - Se existir variável de ambiente `AUTOBACKOFFICE_SOLO_ID_MONDAY`, ela é usada.
#   - Senão, se `AUTOBACKOFFICE_SOLO_ID_MONDAY_DEFAULT` (abaixo) estiver preenchido,
#     ela é usada.
#   - Mesma regra para `AUTOBACKOFFICE_SOLO_ID_NEGOCIO`.
#
# Em outras palavras: você pode “forçar” o solo editando o DEFAULT aqui no arquivo
# (prático no dev), mas no Airflow a variável de ambiente ainda consegue sobrescrever
# esse default sem precisar mexer no código.
#
# Importante para operação:
#   - Se você deixar `*_DEFAULT` preenchido, o SOLO vale para QUALQUER ambiente (dev e prod),
#     a menos que você sobrescreva via variável de ambiente.
#   - Para rodar o fluxo completo (sem SOLO), deixe as variáveis vazias:
#       * env vars vazias/ausentes, e
#       * `*_DEFAULT = ""` aqui no arquivo.
#   - Recomendação: em prod/Airflow, prefira setar SOLO via env var, para não depender
#     de um default hardcoded no repositório.
#
# Observação importante:
#   - `id_monday` é o ID numérico do item no Monday (ex.: 11950095889).
#   - `id_negocio` é o UUID do Otto (ex.: 8dec7ca6-f01a-4039-a5d3-09bf3fb535bf).
AUTOBACKOFFICE_SOLO_ID_MONDAY_DEFAULT ="" # "11950095889"
AUTOBACKOFFICE_SOLO_ID_NEGOCIO_DEFAULT = ""

AUTOBACKOFFICE_SOLO_ID_MONDAY = (
    (os.getenv("AUTOBACKOFFICE_SOLO_ID_MONDAY") or "").strip()
    or str(AUTOBACKOFFICE_SOLO_ID_MONDAY_DEFAULT or "").strip()
)
AUTOBACKOFFICE_SOLO_ID_NEGOCIO = (
    (os.getenv("AUTOBACKOFFICE_SOLO_ID_NEGOCIO") or "").strip()
    or str(AUTOBACKOFFICE_SOLO_ID_NEGOCIO_DEFAULT or "").strip()
)
if AUTOBACKOFFICE_SOLO_ID_MONDAY or AUTOBACKOFFICE_SOLO_ID_NEGOCIO:
    logger.info(
        "--- SOLO --- Parâmetros: id_monday=%s, id_negocio=%s (ambiente=%s, board NEGOCIOS=%s).",
        AUTOBACKOFFICE_SOLO_ID_MONDAY or "(vazio)",
        AUTOBACKOFFICE_SOLO_ID_NEGOCIO or "(vazio)",
        AUTOBACKOFFICE_ENVIRONMENT,
        BOARD_NEGOCIOS_2_0,
    )


def _normalizar_chave_monday(valor: str) -> str:
    """
    Normaliza o token:
      - remove BOM e aspas externas;
      - tira qualquer whitespace (inclusive quebras de linha internas) — um JWT
        pessoal do Monday não contém espaço.
    """
    if not valor:
        return ""
    s = valor.strip().lstrip("\ufeff")
    if len(s) >= 2 and s[0] in "\"'" and s[0] == s[-1]:
        s = s[1:-1]
    # Remove todos os whitespaces (inclui \n, \r, \t e espaços). JWTs não têm whitespace.
    return "".join(s.split())


def _obter_chave_api_monday() -> tuple[str, str]:
    """
    Resolve MONDAY_API_KEY: variável de ambiente (após load_dotenv) ou arquivo MONDAY_API_KEY_FILE.
    Retorna (chave, rótulo de origem para log — sem expor o segredo).
    """
    for nome in ("MONDAY_API_KEY", "MELNICK_MONDAY_API_KEY"):
        bruto = os.getenv(nome)
        if bruto:
            k = _normalizar_chave_monday(bruto)
            if k:
                return k, f"variável {nome}"
    path = _normalizar_chave_monday(os.getenv("MONDAY_API_KEY_FILE", ""))
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                k = _normalizar_chave_monday(f.read())
        except OSError as exc:
            raise ValueError(
                f"Não foi possível ler o arquivo MONDAY_API_KEY_FILE={path!r}: {exc}"
            ) from exc
        if k:
            return k, f"arquivo {path}"
    return "", ""

# Variáveis para este script
flags_teste = [
    "/ teste",
    "(teste)",
    " teste",
    "teste ",
    "testando",
]


#### HELPERS DE I/O ####
#
# O script é gravado em Windows (encoding default cp1252/latin-1) mas executado também
# em Airflow/Linux (encoding default utf-8). Sem forçar `encoding="utf-8"` na escrita
# e sem tolerar legados em latin-1 na leitura, caracteres acentuados quebram com
# `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 ...`.
#
# Este helper padroniza a leitura: tenta utf-8 primeiro e cai para latin-1 se o
# arquivo for legado. Quando identifica legado, re-salva em utf-8 para normalizar
# o arquivo e evitar o fallback nas próximas execuções.


def _carregar_json_resiliente(caminho: str, descricao: str) -> Any | None:
    """
    Carrega um arquivo JSON lidando com casos comuns de falha:

      - Arquivo inexistente -> retorna `None` (sem log de erro; caller decide).
      - `UnicodeDecodeError` (arquivo salvo em cp1252/latin-1 pelo Windows) -> tenta
        reabrir em latin-1, re-salva em utf-8 para normalizar e devolve o conteúdo.
      - `JSONDecodeError` (arquivo corrompido/truncado) -> loga warning e retorna `None`
        para o caller seguir sem cache, em vez de derrubar o script.

    Retorna o objeto desserializado ou `None` em caso de falha recuperável.
    """
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except UnicodeDecodeError as exc:
        logger.warning(
            f"Arquivo `{descricao}` ({caminho}) não está em UTF-8 "
            f"({exc}). Tentando `latin-1` (provavelmente legado gerado no Windows) "
            f"e renormalizando em UTF-8."
        )
        try:
            with open(caminho, "r", encoding="latin-1") as f:
                dados = json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc2:
            logger.warning(
                f"Falha também lendo `{descricao}` em latin-1: {exc2}. "
                f"Seguindo sem cache local."
            )
            return None
        try:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4, ensure_ascii=False, default=str)
            logger.info(f"Arquivo `{descricao}` renormalizado em UTF-8: {caminho}.")
        except Exception as exc3:
            logger.warning(
                f"Não foi possível renormalizar `{descricao}` em UTF-8 ({exc3}). "
                f"O fallback continuará sendo aplicado nas próximas execuções."
            )
        return dados
    except json.JSONDecodeError as exc:
        logger.warning(
            f"Arquivo JSON corrompido/invalidado em `{descricao}` ({caminho}). "
            f"Erro: {exc}. Seguindo sem cache local."
        )
        return None


def _indexar_negocios_monday_por_id_negocio(
    itens: Dict[str, Any] | None,
    origem: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Normaliza caches/retornos do Monday para a chave do fluxo: `id_negocio` do Otto.

    `ClienteMonday.get_items(...)` retorna `{id_item_monday: item}`. Se usarmos esse
    dicionário direto, uma reexecução com data para trás não encontra
    `negocios_monday.get(id_negocio)` e cria item duplicado. Este helper preserva o
    `id_monday` dentro do item e reindexa por `id_negocio`.
    """
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
            logger.debug(
                f"{origem}: item Monday {id_monday or chave_original} sem `id_negocio`; "
                f"mantendo fora do cache de sincronização."
            )
            continue

        chave_id_negocio = str(id_negocio).strip()
        if not chave_id_negocio:
            continue

        existente = normalizados.get(chave_id_negocio)
        if existente:
            logger.warning(
                f"{origem}: mais de um item Monday para id_negocio={chave_id_negocio} "
                f"(mantendo id_monday={item_normalizado.get('id_monday')}, "
                f"substituindo id_monday={existente.get('id_monday')})."
            )
        normalizados[chave_id_negocio] = item_normalizado

    return normalizados


#### REGRAS DE REMOÇÃO DE ITENS NO MONDAY ####
#
# Objetivo: identificar itens no cache local `negocios_monday_2_0.json` que devem ser
# DELETADOS do Monday (liberando espaço/conexões), mas mantidos no JSON como histórico.
#
# Regras importantes de comportamento:
#   - O JSON continua sendo o histórico completo: nenhum registro é removido do dicionário.
#   - O campo `status_item_monday` NÃO é alterado pelo script (mudá-lo equivaleria a arquivar no Monday).
#   - O item deletado ganha apenas dois metadados novos no JSON:
#       * `deletado_do_monday_em`: timestamp da deleção.
#       * `regra_remocao_aplicada`: nome da regra que casou (auditoria).
#     O campo `deletado_do_monday_em` serve como flag idempotente: na próxima execução,
#     itens que já o possuem são pulados (evita tentar deletar de novo algo inexistente).
#
# Para adicionar uma nova regra (ex.: "Concluído" + 30 dias) basta acrescentar um novo
# dict na lista `REGRAS_REMOCAO_MONDAY` abaixo. A função orquestradora não muda.


def _parse_data_item(valor: Any) -> datetime | None:
    """
    Converte um valor de data lido do JSON (string `'YYYY-MM-DD HH:MM:SS'`, `datetime`
    ou dict `ultima_atualizacao` com chave `updated_at`) em `datetime`.
    Retorna `None` se o valor for inválido/ausente.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, dict):
        # Coluna Monday `pulse_updated_mkve9evf` → `ultima_atualizacao` ("Última atualização").
        updated_at = valor.get("updated_at")
        if updated_at is not None:
            return _parse_data_item(updated_at)
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(valor, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(valor)
        except ValueError:
            return None
    return None


def _regra_status_mais_antigo_que(
    campo_status: str,
    valor_status: str,
    campo_data: str,
    dias: int,
) -> Callable[[Dict[str, Any], datetime], bool]:
    """
    Gera um predicado (função) para uso em `REGRAS_REMOCAO_MONDAY`.

    O predicado retorna `True` quando:
      - `item[campo_status] == valor_status`, E
      - a diferença entre `agora` e `item[campo_data]` for **maior que** `dias`.

    Se a data do item for ausente/inválida, o predicado retorna `False` (item seguro).
    """
    def _predicado(item: Dict[str, Any], agora: datetime) -> bool:
        if item.get(campo_status) != valor_status:
            return False
        data_item = _parse_data_item(item.get(campo_data))
        if data_item is None:
            return False
        return (agora - data_item).days > dias
    return _predicado


# Lista de regras ativas. A ordem importa: a primeira regra que casar é registrada.
REGRAS_REMOCAO_MONDAY: list[dict] = [
    {
        "nome": "caiu_mais_de_10_dias",
        "descricao": "Negócios com status 'Caiu' sem última atualização há mais de 10 dias",
        "predicado": _regra_status_mais_antigo_que(
            campo_status="status_negocio",
            valor_status="Caiu",
            campo_data="ultima_atualizacao",
            dias=10,
        ),
    },
    # Exemplo de regra futura (basta descomentar e ajustar):
    # {
    #     "nome": "concluido_mais_de_30_dias",
    #     "descricao": "Negócios 'Concluído' sem última atualização há mais de 30 dias",
    #     "predicado": _regra_status_mais_antigo_que(
    #         campo_status="status_negocio",
    #         valor_status="Concluído",
    #         campo_data="ultima_atualizacao",
    #         dias=30,
    #     ),
    # },
]


def aplicar_regras_remocao_monday(
    negocios_monday: Dict[str, Any],
    cliente: ClienteMonday,
    regras: list[dict],
    agora: datetime | None = None,
) -> dict:
    """
    Aplica a lista de `regras` ao dicionário `negocios_monday` (chave = id do item do Monday).

    Para cada item que casar com alguma regra:
      1. Executa `cliente.delete_item(item_id)` no Monday.
      2. Adiciona `deletado_do_monday_em` e `regra_remocao_aplicada` no item do JSON.
      3. NÃO altera `status_item_monday` nem remove o item do dicionário.

    Itens que já possuem `deletado_do_monday_em` são pulados (idempotente, evita re-delete).
    Em caso de erro no delete, o item não recebe a flag e será reavaliado na próxima execução.

    Args:
        negocios_monday: dicionário `{id_monday: item}` (mutado in-place).
        cliente: instância de `ClienteMonday`.
        regras: lista de regras no formato `{"nome": str, "descricao": str, "predicado": Callable}`.
        agora: `datetime` de referência (default: `datetime.now()`), útil para testes.

    Returns:
        dict com resumo: `deletados`, `falhas`, `pulados_ja_deletados`, `por_regra`.
    """
    agora = agora or datetime.now()
    agora_str = agora.strftime("%Y-%m-%d %H:%M:%S")
    resumo = {
        "deletados": 0,
        "falhas": 0,
        "pulados_ja_deletados": 0,
        "por_regra": {},
    }

    for chave_cache, item in negocios_monday.items():
        if not isinstance(item, dict):
            continue

        id_monday = item.get("id_monday") or chave_cache

        if item.get("deletado_do_monday_em"):
            resumo["pulados_ja_deletados"] += 1
            continue

        regra_casada = next(
            (r for r in regras if r["predicado"](item, agora)),
            None,
        )
        if regra_casada is None:
            continue

        nome_regra = regra_casada["nome"]
        try:
            cliente.delete_item(item_id=str(id_monday))
            item["deletado_do_monday_em"] = agora_str
            item["regra_remocao_aplicada"] = nome_regra
            resumo["deletados"] += 1
            resumo["por_regra"][nome_regra] = resumo["por_regra"].get(nome_regra, 0) + 1
            logger.info(
                f"Item {id_monday} deletado no Monday pela regra '{nome_regra}'. "
                f"JSON mantido como histórico."
            )
        except Exception as exc:
            resumo["falhas"] += 1
            logger.warning(
                f"Falha ao deletar item {id_monday} no Monday (regra '{nome_regra}'): {exc}. "
                f"Será reavaliado na próxima execução."
            )

    return resumo


# Filtros da "varredura profunda": busca-se direto no Monday (paginado) todos os itens
# que casam com cada combinação de coluna/valor, mergeia no cache local e depois aplica
# `REGRAS_REMOCAO_MONDAY`. Isso pega itens antigos do Monday que nunca entraram no cache
# (ex.: "Caiu" de vários meses atrás). Para adicionar uma nova varredura futura basta
# acrescentar outro dict aqui.
#
# `column_id` é o ID da coluna NO MONDAY (ver `MONDAY_COLUMN_ID_MAP` em mapeamento_dados.py).
# `value` é o label/valor exibido no Monday.
FILTROS_VARREDURA_REMOCAO_MONDAY: list[dict] = [
    {
        "descricao": "Todos os negócios com status 'Caiu' no board de NEGOCIOS",
        "column_id": "status",  # coluna 'status_negocio' no mapeamento
        "value": "Caiu",
    },
    # Exemplo futuro:
    # {
    #     "descricao": "Todos os negócios 'Concluído' no board de NEGOCIOS",
    #     "column_id": "status",
    #     "value": "Concluído",
    # },
]


def varredura_e_remocao_monday(
    negocios_monday: Dict[str, Any],
    cliente: ClienteMonday,
    board_id: int,
    filtros: list[dict],
    regras: list[dict],
    agora: datetime | None = None,
) -> dict:
    """
    Faz uma "varredura profunda" no Monday para cada entrada em `filtros`: busca paginado
    todos os itens que batem com (column_id, value), mergeia no cache local `negocios_monday`
    e, ao final, aplica `REGRAS_REMOCAO_MONDAY` sobre o cache atualizado.

    Garante que itens antigos do Monday (que nunca entraram no cache local via Otto/atualizados
    hoje) sejam avaliados pelas regras de remoção.

    Args:
        negocios_monday: cache local (mutado in-place com itens recém trazidos do Monday).
        cliente: instância de `ClienteMonday`.
        board_id: ID do board a varrer.
        filtros: lista de `{"descricao", "column_id", "value"}`.
        regras: lista de regras para aplicar após a varredura.
        agora: datetime de referência (default: `datetime.now()`).

    Returns:
        dict com `itens_trazidos_por_filtro`, `novos_no_cache` e o resumo retornado
        por `aplicar_regras_remocao_monday`.
    """
    agora = agora or datetime.now()
    resumo_varredura = {
        "itens_trazidos_por_filtro": {},
        "novos_no_cache": 0,
    }

    for filtro in filtros:
        descricao = filtro.get("descricao") or f"{filtro['column_id']}={filtro['value']}"
        logger.info(f"Varredura profunda no Monday: {descricao}...")

        try:
            encontrados = cliente.get_items(
                board_id=board_id,
                column_id=filtro["column_id"],
                value=filtro["value"],
            )
        except Exception as exc:
            logger.warning(
                f"Falha ao buscar itens no Monday para filtro '{descricao}': {exc}. "
                f"Pulando este filtro."
            )
            resumo_varredura["itens_trazidos_por_filtro"][descricao] = 0
            continue

        total = len(encontrados)
        resumo_varredura["itens_trazidos_por_filtro"][descricao] = total
        logger.info(f"Varredura '{descricao}': {total} item(ns) encontrado(s) no Monday.")

        encontrados_por_negocio = _indexar_negocios_monday_por_id_negocio(
            encontrados,
            origem=f"varredura {descricao}",
        )

        for id_negocio, item in encontrados_por_negocio.items():
            if id_negocio in negocios_monday:
                # Item já está no cache: preserva flags como `deletado_do_monday_em` e
                # campos extras que só o cache tem, atualizando só os campos vindos do Monday.
                cache_item = negocios_monday[id_negocio]
                for k, v in item.items():
                    cache_item[k] = v
            else:
                negocios_monday[id_negocio] = item
                resumo_varredura["novos_no_cache"] += 1

    logger.info(
        f"Varredura finalizada. Novos itens adicionados ao cache: "
        f"{resumo_varredura['novos_no_cache']}. Aplicando regras de remoção..."
    )

    resumo_remocao = aplicar_regras_remocao_monday(
        negocios_monday=negocios_monday,
        cliente=cliente,
        regras=regras,
        agora=agora,
    )
    resumo_varredura["remocao"] = resumo_remocao
    return resumo_varredura


#### HELPERS DE MONTAGEM DE DADOS DE NEGÓCIO PARA O MONDAY (Fase B) ####
#
# Estes helpers convertem um "negocio" (formato interno do script, com entidades nested
# como `corretor`, `imobiliaria`, `vendedor` e a lista `atualizacoes`) em um dicionário
# com CHAVES PADRONIZADAS MELNICK (snake_case) pronto para ser mapeado para os IDs de
# coluna do Monday via `map_dict_keys(..., invert_mapping=True)`.
#
# Separar isso em funções puras facilita:
#   - Testes unitários.
#   - Adicionar detecção de conflitos / diff vs. Monday (Fase C) sem poluir o loop.
#   - Reaproveitar a montagem em outros scripts (ex.: tarefas Airflow dedicadas).


def _fmt_datetime(valor: Any) -> str | None:
    """
    Converte um `datetime` (ou string já no formato esperado) em `'YYYY-MM-DD HH:MM:SS'`.
    Retorna `None` para valores vazios ou inválidos. Usado para serializar campos de
    data/hora antes de enviar ao Monday (que espera string).
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    # Se já vier como string, devolve como está (o Monday valida o formato)
    return str(valor)


def _coerce_float(valor: Any) -> float | None:
    """Converte `Decimal`/`int`/`str` em `float`, devolvendo `None` se o valor é vazio."""
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def processar_atualizacao_reserva(update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converte uma entrada de `atualizacoes` do tipo `"reserva"` em um dict parcial de
    campos Melnick prontos para compor `dados_monday_do_negocio`. Regras idênticas às
    do `AutoBackoffice-old.py` (linhas ~1035-1079):

      - Status desconhecido ou `"Cancelada"` mantém status anterior (não escreve chave).
      - Se `posicao_fila > 1`, força status para `"Na fila"`.
      - `status_integracao_reserva` vai como `None` se o bloco `resultado_integracao_reserva`
        existir mas estiver vazio — isso permite limpar o campo no Monday quando a
        integração deixa de existir (ex.: cancelamento + nova reserva).
    """
    dados_update: Dict[str, Any] = update.get("dados") or {}
    id_reserva = update.get("id")

    resultado: Dict[str, Any] = {}

    status_id = dados_update.get("id_status_reserva") or 0
    status_label = STATUS_RESERVA.get(status_id, "Status desconhecido")

    if status_label == "Status desconhecido":
        logger.error(
            f"Status de reserva desconhecido (id={status_id}) para reserva ID {id_reserva}."
        )
    elif status_label == "Cancelada":
        logger.debug(f"Reserva ID {id_reserva} cancelada. Mantendo status anterior.")
    else:
        posicao_fila = dados_update.get("posicao_fila")
        if posicao_fila is not None and posicao_fila > 1:
            status_label = "Na fila"
        resultado["status_reserva"] = status_label

    # Integração da reserva (Sucesso/Falha) - pode ser explicitamente limpa
    integracao = dados_update.get("resultado_integracao_reserva")
    if integracao is None:
        resultado["status_integracao_reserva"] = None
    else:
        status_integracao = integracao.get("status")
        if status_integracao is not None:
            resultado["status_integracao_reserva"] = status_integracao

    resultado["posicao_fila"] = dados_update.get("posicao_fila")
    resultado["data_reserva"] = _fmt_datetime(dados_update.get("reserva_criada_em"))
    resultado["data_comeco_reserva"] = _fmt_datetime(dados_update.get("inicio_primeira_posicao"))
    resultado["link_reserva"] = {
        "url": f"https://admin.beotto.com/reserva/{id_reserva}",
        "text": "Link da Reserva",
    }
    return resultado


def processar_atualizacao_proposta(
    update: Dict[str, Any],
    id_negocio: str,
) -> Dict[str, Any]:
    """
    Converte uma entrada de `atualizacoes` do tipo `"proposta"` em um dict parcial de
    campos Melnick. Regras equivalentes ao `AutoBackoffice-old.py` (linhas ~1082-1140):

      - `"Cancelada"` e `"Não enviada"` mantêm status anterior (não escreve chave).
      - Tenta extrair `numero_proposta_gc` e `perda_vpl` de `rawResponse.PVRet[0]`,
        capturando erros estruturais para não derrubar o loop.
      - `link_proposta` usa o `id_negocio` (e não o `id_proposta`) — é assim no antigo.
    """
    dados_update: Dict[str, Any] = update.get("dados") or {}
    id_proposta = update.get("id")

    resultado: Dict[str, Any] = {}

    status_id = dados_update.get("id_status_proposta") or 0
    status_label = STATUS_PROPOSTA.get(status_id, "Status desconhecido")

    if status_label == "Status desconhecido":
        logger.error(
            f"Status de proposta desconhecido (id={status_id}) para proposta ID {id_proposta}."
        )
    elif status_label == "Cancelada":
        logger.debug(f"Proposta ID {id_proposta} cancelada. Mantendo status anterior.")
    elif status_label == "Não enviada":
        logger.debug(f"Proposta ID {id_proposta} ainda não enviada.")
    else:
        resultado["status_proposta"] = status_label

    integracao = dados_update.get("resultado_integracao_proposta")
    if integracao:
        status_integracao = integracao.get("status")
        if status_integracao is not None:
            resultado["status_integracao_proposta"] = status_integracao

        # `rawResponse.PVRet[0]` pode não existir em certos cenários de falha; usar try/except
        # evita derrubar o loop por uma estrutura inesperada.
        try:
            pv_ret = (integracao.get("rawResponse") or {}).get("PVRet") or [{}]
            primeiro = pv_ret[0] if pv_ret else {}
            numero_pv = primeiro.get("PnvCod")
            if numero_pv:
                resultado["numero_proposta_gc"] = numero_pv
            perda_vpl_str = primeiro.get("PnvPdaVPL")
            if perda_vpl_str is not None:
                resultado["perda_vpl"] = _coerce_float(perda_vpl_str)
        except (KeyError, IndexError, TypeError, ValueError):
            logger.debug(
                f"Não foi possível extrair numero_proposta_gc/perda_vpl da proposta "
                f"ID {id_proposta}."
            )

    resultado["data_proposta"] = _fmt_datetime(dados_update.get("proposta_enviada_em"))
    resultado["proposta_criada_em"] = _fmt_datetime(dados_update.get("proposta_criada_em"))
    resultado["valor_proposta"] = _coerce_float(dados_update.get("valor_proposta"))
    resultado["valor_comissao"] = _coerce_float(dados_update.get("valor_comissao"))
    resultado["valor_liquido"] = _coerce_float(dados_update.get("valor_liquido"))
    resultado["percentual_financiado"] = _coerce_float(dados_update.get("percentual_financiado"))
    resultado["percentual_comissao"] = _coerce_float(dados_update.get("percentual_comissao"))
    resultado["link_proposta"] = {
        "url": f"https://admin.beotto.com/proposta/{id_negocio}",
        "text": "Link da Proposta",
    }
    return resultado


def _texto_titulo_opcional(*candidatos: Any) -> str | None:
    """Primeiro candidato não vazio vira string `.strip().title()` ou None."""
    for v in candidatos:
        if v is None:
            continue
        if isinstance(v, dict):
            v = v.get("nome")
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s.title()
    return None


def montar_dados_monday_do_negocio(
    id_negocio: str,
    dados_negocio: Dict[str, Any],
) -> Dict[str, Any]:
    """
    AutoBackoffice 2.0: monta o dict Melnick sem relacionamentos com o board CONTAS.
    Corretor e imobiliária vão nas colunas de texto `nome_corretor` e
    `nome_imobiliaria` e `nome_executivos`, lendo nested (`corretor`/`imobiliaria`/
    `executivo`) ou chaves raiz quando ainda existirem.
    """
    nome_empreendimento = (dados_negocio.get("nome_empreendimento") or "").title()
    nome_torre = (dados_negocio.get("nome_torre") or "").title()
    nome_cliente = (dados_negocio.get("nome_cliente") or "").title()
    numero_unidade = dados_negocio.get("numero_unidade")

    dados_negocio["nome_empreendimento"] = nome_empreendimento
    dados_negocio["nome_torre"] = nome_torre
    dados_negocio["nome_cliente"] = nome_cliente

    update_dict: Dict[str, Any] = {
        "id_negocio": id_negocio,
        "negocio_criado_em": _fmt_datetime(dados_negocio.get("negocio_criado_em")),
        "id_unidade": dados_negocio.get("id_unidade"),
        "nome_empreendimento": nome_empreendimento or None,
        "nome_torre": nome_torre or None,
        "numero_unidade": numero_unidade,
        "nome_cliente": nome_cliente or None,
        "documento_cliente": dados_negocio.get("documento_cliente"),
    }

    nome_corretor_txt = _texto_titulo_opcional(
        dados_negocio.get("corretor"),
        dados_negocio.get("nome_corretor"),
    )
    if nome_corretor_txt:
        update_dict["nome_corretor"] = nome_corretor_txt

    nome_imob_txt = _texto_titulo_opcional(
        dados_negocio.get("imobiliaria"),
        dados_negocio.get("nome_imobiliaria"),
    )
    if nome_imob_txt:
        update_dict["nome_imobiliaria"] = nome_imob_txt

    nome_executivo_txt = _texto_titulo_opcional(
        dados_negocio.get("executivo"),
        dados_negocio.get("nome_executivo"),
        dados_negocio.get("nome_executivos"),
    )
    if nome_executivo_txt:
        update_dict["nome_executivos"] = nome_executivo_txt

    for update in dados_negocio.get("atualizacoes", []) or []:
        tipo = update.get("tipo")
        if tipo == "reserva":
            update_dict.update(processar_atualizacao_reserva(update))
        elif tipo == "proposta":
            update_dict.update(processar_atualizacao_proposta(update, id_negocio))
        else:
            logger.debug(
                f"Negócio {id_negocio}: atualização de tipo desconhecido '{tipo}' ignorada."
            )

    return update_dict


#### HELPERS DE SINCRONIZAÇÃO (Fase C) ####
#
# Estes helpers cobrem:
#   - Comparação de valores (diff) entre o dict de envio (formato Monday) e o cache
#     local `negocios_monday[id]` (formato leitura do Monday), que usam representações
#     diferentes para board relations, links e labels.
#   - Detecção de cruzamentos (mesmo cliente + mesma unidade), com reatribuição
#     automática quando o corretor é o mesmo e sinalização via label quando é
#     diferente.
#   - Conversão do dict Melnick (envio) para o formato cache após operações bem
#     sucedidas, mantendo o cache local em sincronia com o Monday sem precisar
#     refazer `get_items`.


def _extrair_item_ids_para_diff(valor: Any) -> set | None:
    """
    Extrai o conjunto de IDs de um valor de `board_relation` em qualquer formato:

      - Formato de ENVIO ao Monday: `{"item_ids": ["x", "y"]}`.
      - Formato de LEITURA do Monday (cache): `[{"id": "x", "name": "..."}, ...]`.

    Retorna `None` quando o valor não é um board relation - o caller usa isso para
    decidir se aplica a comparação específica de relacionamento ou a genérica.
    """
    if isinstance(valor, dict) and "item_ids" in valor:
        return {str(x) for x in (valor.get("item_ids") or [])}
    if isinstance(valor, list):
        ids = []
        for item in valor:
            if isinstance(item, dict) and "id" in item:
                ids.append(str(item["id"]))
        # Só consideramos "board relation" se todos os itens tinham `id`; caso
        # contrário é uma lista comum (ex.: `labels`) e devolvemos None.
        return set(ids) if ids or valor == [] else None
    return None


def _eh_vazio_para_diff(valor: Any) -> bool:
    """Considera `None`, string vazia, lista vazia e dict vazio como equivalentes."""
    return valor is None or valor == "" or valor == [] or valor == {}


def _valores_iguais_para_diff(valor_a: Any, valor_b: Any) -> bool:
    """
    Compara dois valores levando em conta as diferenças estruturais entre o dict de
    ENVIO (construído pela Fase B) e o dict de LEITURA armazenado no cache. Evita
    updates redundantes no Monday quando os valores são semanticamente iguais mas
    sintaticamente diferentes.
    """
    if _eh_vazio_para_diff(valor_a) and _eh_vazio_para_diff(valor_b):
        return True

    ids_a = _extrair_item_ids_para_diff(valor_a)
    ids_b = _extrair_item_ids_para_diff(valor_b)
    if ids_a is not None or ids_b is not None:
        if ids_a is None or ids_b is None:
            return False
        return ids_a == ids_b

    # Dicts: comparação estrutural direta (ex.: `{"url": "...", "text": "..."}`,
    # `{"labels": ["Cruzamento"]}`). Aqui precisamos tratar um caso especial: no
    # cache, `pendencias_analise` pode vir como lista simples `["Cruzamento"]` ou
    # como dict `{"labels": [...]}` dependendo do parser. Normalizamos ambos.
    if isinstance(valor_a, dict) and "labels" in valor_a and isinstance(valor_b, list):
        return set(valor_a.get("labels") or []) == set(str(x) for x in valor_b)
    if isinstance(valor_b, dict) and "labels" in valor_b and isinstance(valor_a, list):
        return set(valor_b.get("labels") or []) == set(str(x) for x in valor_a)

    if isinstance(valor_a, dict) and isinstance(valor_b, dict):
        return valor_a == valor_b

    # Números vindos do Otto vs cache podem estar em tipos diferentes (float vs
    # string numérica); tenta comparar numericamente antes da comparação estrita.
    if isinstance(valor_a, (int, float)) or isinstance(valor_b, (int, float)):
        try:
            return float(valor_a) == float(valor_b)
        except (TypeError, ValueError):
            pass

    return valor_a == valor_b


def calcular_diff_colunas_melnick(
    update_melnick: Dict[str, Any],
    negocio_monday_atual: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Retorna apenas as chaves de `update_melnick` cujos valores diferem de
    `negocio_monday_atual` (cache local). Esse diff alimenta `update_item` para
    economizar chamadas de API e respeitar rate limits do Monday.

    Importante: o diff é feito ANTES do `map_dict_keys`, porque as chaves Melnick
    são as mesmas do cache (snake_case). Depois do diff, aplicamos `map_dict_keys`
    só nas chaves alteradas.
    """
    diff: Dict[str, Any] = {}
    for chave, novo_valor in update_melnick.items():
        valor_atual = negocio_monday_atual.get(chave)
        if not _valores_iguais_para_diff(novo_valor, valor_atual):
            diff[chave] = novo_valor
    return diff


def _nome_corretor_normalizado_para_cruzamento(d: Dict[str, Any]) -> str:
    """2.0: usa coluna de texto; fallback ao nome no relacionamento antigo do cache."""
    n = (d.get("nome_corretor") or "").strip().lower()
    if n:
        return n
    rel = d.get("id_corretor")
    if isinstance(rel, list) and rel:
        first = rel[0]
        if isinstance(first, dict) and first.get("name"):
            return str(first["name"]).strip().lower()
    return ""


def detectar_cruzamento(
    id_negocio: str,
    update_melnick: Dict[str, Any],
    negocios_monday: Dict[str, Dict[str, Any]],
) -> Tuple[str | None, Dict[str, Any] | None, str | None]:
    """
    Mesma ideia do fluxo 1.0, porém compara corretor pelo **nome** (`nome_corretor`),
    já que o 2.0 não envia `id_corretor` (board relation com CONTAS).
    """
    documento = update_melnick.get("documento_cliente")
    id_unidade = update_melnick.get("id_unidade")
    if not documento or not id_unidade:
        return None, None, None

    nome_corretor_atual = _nome_corretor_normalizado_para_cruzamento(update_melnick)
    if not nome_corretor_atual:
        return None, None, None

    tem_corretor_diferente = False

    for outro_id, dados_cache in negocios_monday.items():
        if outro_id == id_negocio:
            continue
        if dados_cache.get("documento_cliente") != documento:
            continue
        if dados_cache.get("id_unidade") != id_unidade:
            continue

        nome_outro = _nome_corretor_normalizado_para_cruzamento(dados_cache)
        if not nome_outro:
            logger.debug(
                f"Cruzamento parcial: negócio {outro_id} tem mesmo cliente+unidade que "
                f"{id_negocio} mas sem nome de corretor no cache. Ignorando conflito."
            )
            continue

        if nome_corretor_atual == nome_outro:
            id_monday_reatribuicao = dados_cache.get("id_monday")
            if id_monday_reatribuicao:
                logger.info(
                    f"Cruzamento: negócio {id_negocio} corresponde ao item "
                    f"{id_monday_reatribuicao} (mesmo cliente+unidade+corretor que "
                    f"negócio {outro_id}). Reatribuindo em vez de criar novo."
                )
                return str(id_monday_reatribuicao), None, str(outro_id)
            continue
        tem_corretor_diferente = True

    if tem_corretor_diferente:
        logger.warning(
            f"Cruzamento: negócio {id_negocio} tem mesmo cliente+unidade que outro "
            f"com corretor diferente. Marcando pendencias_analise=Cruzamento."
        )
        return None, {"pendencias_analise": {"labels": ["Cruzamento"]}}, None

    return None, None, None


def _update_melnick_para_cache(
    update_melnick: Dict[str, Any],
    dados_negocio: Dict[str, Any],
    nome_processo: str | None,
    id_monday: str,
) -> Dict[str, Any]:
    """
    Converte um dict no formato de ENVIO (saída da Fase B) para o formato usado
    pelo cache `negocios_monday[id]` (leitura do Monday). Principais ajustes:

      - `{"item_ids": ["x"]}` vira `[{"id": "x", "name": "<nome do contato>"}]`
        (usando o nome presente em `dados_negocio[<papel>]["nome"]`, quando houver).
      - `{"labels": [...]}` é mantido como está (compatível com ambos os formatos na
        prática, já que a leitura pode ser lista simples ou dict).
      - Demais valores (strings, números, links com `url/text`) são copiados direto.

    Também propaga `id_monday` e `status_item_monday`, garantindo que uma próxima
    execução identifique o item como existente e ativo, sem depender de novo
    `get_items` do board.
    """
    papeis_com_nome = {
        "id_corretor": "corretor",
        "id_imobiliaria": "imobiliaria",
        "id_gerente": "gerente",
        "id_executivo": "executivo",
        "id_vendedor": "vendedor",
    }

    resultado: Dict[str, Any] = {
        "id_monday": str(id_monday),
        "status_item_monday": "active",
    }
    if nome_processo:
        resultado["nome_processo"] = nome_processo

    for chave, valor in update_melnick.items():
        if (
            chave in papeis_com_nome
            and isinstance(valor, dict)
            and "item_ids" in valor
        ):
            papel = papeis_com_nome[chave]
            conta = dados_negocio.get(papel) or {}
            nome = (conta.get("nome") or "").strip() if isinstance(conta, dict) else ""
            resultado[chave] = [
                {"id": str(item_id), "name": nome}
                for item_id in (valor.get("item_ids") or [])
            ]
        else:
            resultado[chave] = valor
    return resultado


def sincronizar_negocios_com_monday(
    negocios_para_sincronizar: Dict[str, Dict[str, Any]],
    negocios_monday: Dict[str, Dict[str, Any]],
    negocios: Dict[str, Dict[str, Any]],
    cliente: ClienteMonday,
    board_id: int,
) -> Dict[str, int]:
    """
    Orquestra create/update dos negócios no board NEGOCIOS do Monday. Para cada
    pacote preparado pela Fase B:

      1. Detecta cruzamento (mesmo cliente+unidade em outro negócio já no Monday):
         - Se o corretor também bate, reaproveita o `id_monday` do conflito.
         - Se o corretor é diferente, adiciona `pendencias_analise=Cruzamento`.
      2. Se ainda sem `id_item_monday` -> `create_item` (grupo padrão).
         Caso contrário -> calcula diff em chaves Melnick e chama `update_item`
         apenas com as colunas alteradas.
      3. Atualiza `negocios_monday[id_negocio]` em memória após sucesso, de forma
         que a próxima iteração (mesma execução) já veja o estado novo - importante
         pra detecção de cruzamentos dentro da própria rodada.

    Falhas em um negócio NÃO interrompem os demais: a exceção é logada e o resumo
    contabiliza em `falhas`.
    """
    resumo = {
        "total": 0,
        "criados": 0,
        "atualizados": 0,
        "sem_alteracao": 0,
        "reatribuidos": 0,
        "cruzamentos_detectados": 0,
        "falhas": 0,
    }
    total = len(negocios_para_sincronizar)
    full_update_on_reassign = (os.getenv("AUTOBACKOFFICE_FULL_UPDATE_ON_REASSIGN") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
        "sim",
    )

    for indice, (id_negocio, pacote) in enumerate(negocios_para_sincronizar.items(), start=1):
        resumo["total"] += 1
        # Cópia defensiva: podemos mutar (adicionar `pendencias_analise` no cruzamento)
        # sem afetar o pacote original caso o caller queira reutilizá-lo.
        update_melnick: Dict[str, Any] = dict(pacote.get("update_melnick") or {})
        id_item_monday: str | None = pacote.get("id_item_monday")
        nome_processo: str = pacote.get("nome_processo") or ""
        dados_negocio = negocios.get(id_negocio, {})

        # 1) Cruzamento
        id_reatribuicao, pendencias, id_negocio_dono_cache = detectar_cruzamento(
            id_negocio=id_negocio,
            update_melnick=update_melnick,
            negocios_monday=negocios_monday,
        )
        if pendencias:
            update_melnick.update(pendencias)
            resumo["cruzamentos_detectados"] += 1
        if id_reatribuicao and not id_item_monday:
            id_item_monday = id_reatribuicao
            resumo["reatribuidos"] += 1

        try:
            # 2) Create
            if not id_item_monday:
                # Regra herdada do fluxo antigo: só criar negócio quando já houver
                # ao menos um status de reserva/proposta no payload.
                if (
                    "status_reserva" not in update_melnick
                    and "status_proposta" not in update_melnick
                ):
                    resumo["sem_alteracao"] += 1
                    logger.info(
                        f"({indice}/{total}) Negócio {id_negocio}: sem "
                        f"`status_reserva` e `status_proposta`. "
                        f"Criação no Monday adiada."
                    )
                    continue

                if not nome_processo.strip():
                    logger.error(
                        f"({indice}/{total}) Negócio {id_negocio}: sem `nome_processo` "
                        f"- impossível criar item no Monday. Pulando."
                    )
                    resumo["falhas"] += 1
                    continue

                update_monday = map_dict_keys(
                    fonte="monday",
                    id_mapeamento=str(board_id),
                    dict_to_map=update_melnick,
                    invert_mapping=True,
                )
                if not update_monday:
                    logger.error(
                        f"({indice}/{total}) Negócio {id_negocio}: nenhum campo mapeável "
                        f"após `map_dict_keys`. Pulando criação."
                    )
                    resumo["falhas"] += 1
                    continue

                novo_id = cliente.create_item(
                    board_id=board_id,
                    item_name=nome_processo,
                    column_values=update_monday,
                )
                negocios_monday[id_negocio] = _update_melnick_para_cache(
                    update_melnick=update_melnick,
                    dados_negocio=dados_negocio,
                    nome_processo=nome_processo,
                    id_monday=novo_id,
                )
                resumo["criados"] += 1
                logger.info(
                    f"({indice}/{total}) Negócio {id_negocio} criado no Monday "
                    f"(id_monday={novo_id})."
                )
                continue

            # 3) Update com diff
            reatribuindo = bool(id_negocio_dono_cache) and (id_negocio_dono_cache != id_negocio)
            if reatribuindo:
                cache_atual = negocios_monday.get(str(id_negocio_dono_cache)) or {}
                if cache_atual.get("id_monday") and str(cache_atual.get("id_monday")) != str(id_item_monday):
                    logger.warning(
                        "Cruzamento: cache baseline não aponta para o mesmo id_monday "
                        "(id_negocio=%s, dono_cache=%s, id_item_monday=%s, cache_id_monday=%s). "
                        "Fazendo diff contra cache do id_negocio atual.",
                        id_negocio,
                        id_negocio_dono_cache,
                        id_item_monday,
                        cache_atual.get("id_monday"),
                    )
                    cache_atual = negocios_monday.get(id_negocio) or {}
            else:
                cache_atual = negocios_monday.get(id_negocio) or {}

            if reatribuindo and full_update_on_reassign:
                diff_melnick = dict(update_melnick)
            else:
                diff_melnick = calcular_diff_colunas_melnick(update_melnick, cache_atual)
            if not diff_melnick:
                resumo["sem_alteracao"] += 1
                logger.info(
                    f"({indice}/{total}) Negócio {id_negocio}: sem alterações "
                    f"(id_monday={id_item_monday})."
                )
                continue

            diff_monday = map_dict_keys(
                fonte="monday",
                id_mapeamento=str(board_id),
                dict_to_map=diff_melnick,
                invert_mapping=True,
            )
            if not diff_monday:
                # O diff só tem chaves que não têm coluna correspondente no Monday
                # (ex.: campos internos). Consideramos "sem alteração" para o Monday,
                # mas ainda atualizamos o cache para refletir a mudança interna.
                resumo["sem_alteracao"] += 1
                logger.debug(
                    f"({indice}/{total}) Negócio {id_negocio}: diff Melnick só contém "
                    f"chaves sem mapeamento Monday ({list(diff_melnick.keys())}). "
                    f"Ignorando chamada update_item."
                )
            else:
                cliente.update_item(
                    board_id=board_id,
                    item_id=str(id_item_monday),
                    column_values=diff_monday,
                )
                resumo["atualizados"] += 1
                logger.info(
                    f"({indice}/{total}) Negócio {id_negocio} atualizado no Monday "
                    f"(id_monday={id_item_monday}, colunas={list(diff_monday.keys())})."
                )

            # Merge do diff sobre o cache (mesmo quando só houve chaves internas)
            cache_atualizado = dict(cache_atual)
            cache_atualizado.update(
                _update_melnick_para_cache(
                    update_melnick=diff_melnick,
                    dados_negocio=dados_negocio,
                    nome_processo=nome_processo or cache_atual.get("nome_processo"),
                    id_monday=id_item_monday,
                )
            )
            negocios_monday[id_negocio] = cache_atualizado
            if reatribuindo:
                # Evita dois id_negocio no cache apontando para o mesmo item do Monday.
                antigo = negocios_monday.get(str(id_negocio_dono_cache)) or {}
                if str(antigo.get("id_monday") or "") == str(id_item_monday):
                    antigo_atualizado = dict(antigo)
                    antigo_atualizado["id_monday"] = None
                    antigo_atualizado["reatribuido_para_id_negocio"] = str(id_negocio)
                    antigo_atualizado["reatribuido_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    negocios_monday[str(id_negocio_dono_cache)] = antigo_atualizado
                    logger.info(
                        "Cruzamento: cache do negócio %s desassociado do id_monday=%s (reatribuído para %s).",
                        id_negocio_dono_cache,
                        id_item_monday,
                        id_negocio,
                    )

        except Exception as exc:
            resumo["falhas"] += 1
            logger.exception(
                f"({indice}/{total}) Negócio {id_negocio}: falha ao sincronizar com o "
                f"Monday: {exc}. Prosseguindo com os demais."
            )

    return resumo


########


#### CLIENTES ####


# Cliente Monday

# Busca as variáveis de ambiente necessárias para o cliente do Monday
chave_api_monday, origem_chave_monday = _obter_chave_api_monday()
if not chave_api_monday:
    raise ValueError(
        "Chave do Monday ausente. Defina MONDAY_API_KEY (ou MELNICK_MONDAY_API_KEY) no .env do "
        "repositório ou da pasta-pai, ou MONDAY_API_KEY_FILE com caminho a um ficheiro só com o token. "
        "No Airflow, confirme o token no Web UI (Admin → Variables) se exporta no bash_task, ou no .env em "
        f"{arquivo_env_repo!r}."
    )

# Cria a instância do cliente do Monday
cliente_monday = ClienteMonday(api_key=chave_api_monday)
# Prévia segura do token (só primeiros/últimos 3 chars) para distinguir tokens carregados
# em ambientes diferentes (dev/prod/servidor Airflow) sem expor o segredo no log.
_previa_chave_monday = (
    f"{chave_api_monday[:3]}...{chave_api_monday[-3:]}" if len(chave_api_monday) >= 8 else "(curta demais)"
)
# Tokens pessoais do Monday são JWTs (3 segmentos separados por '.') com ~150–170 chars.
_qtd_pontos_chave = chave_api_monday.count(".")
if _qtd_pontos_chave != 2 or not (100 <= len(chave_api_monday) <= 200):
    logger.warning(
        "Token do Monday fora do formato típico de JWT pessoal "
        "(%d caracteres, %d ponto(s), esperado 2). "
        "Suspeite de token duplicado/concatenado, quebra de linha dentro do valor no .env, "
        "ou de estar usando um token que não é o pessoal.",
        len(chave_api_monday),
        _qtd_pontos_chave,
    )
logger.info(
    "Cliente do Monday criado (chave: %d caracteres, %d ponto(s), prévia: %s, origem: %s).",
    len(chave_api_monday),
    _qtd_pontos_chave,
    _previa_chave_monday,
    origem_chave_monday,
)

# Teste imediato do token: evita falhar 10 minutos depois no meio do pipeline.
# Em caso de NOT_AUTHENTICATED aqui, a chave carregada no ambiente não vale na API do Monday.
try:
    _me = cliente_monday.run_query("query { me { id name email } }")
    _dados_me = (_me or {}).get("data", {}).get("me") or {}
    logger.info(
        "Autenticação no Monday OK. Usuário do token: id=%s, nome=%s, email=%s.",
        _dados_me.get("id"),
        _dados_me.get("name"),
        _dados_me.get("email"),
    )
except Exception as _exc:
    logger.error(
        "Falha na autenticação contra a API do Monday com o token atual "
        "(chave: %d caracteres, prévia: %s, origem: %s). "
        "Checklist: (1) token não revogado/expirado em monday.com → Admin → API; "
        "(2) .env do servidor aponta para o mesmo token que funciona localmente; "
        "(3) não há variável MONDAY_API_KEY exportada no worker/container sobrescrevendo o .env. "
        "Erro original: %s",
        len(chave_api_monday),
        _previa_chave_monday,
        origem_chave_monday,
        _exc,
    )
    raise

# Cliente Otto

# Busca as variáveis de ambiente necessárias para o cliente do Otto
usuario_otto = os.getenv("OTTO_DB_USER")
senha_otto = os.getenv("OTTO_DB_PASSWORD")
if not usuario_otto or not senha_otto:
    raise ValueError("As variáveis de ambiente 'OTTO_DB_USER' e 'OTTO_DB_PASSWORD' não foram encontradas. Por favor, defina-as no arquivo .env.")
logger.info("Variáveis de ambiente para o cliente do Otto encontradas com sucesso.")

# Cria a instância do cliente do Otto
cliente_otto = ClienteOtto(user=usuario_otto, password=senha_otto)
logger.info("Cliente do Otto criado com sucesso.")

# AutoBackoffice 2.0 não usa banco SQL nem empresas GC (sem vendedor como item em CONTAS).

#### DATA DE ATUALIZAÇÃO ####

ultimos_dias_para_atualizar = 1

# Hora desta execução, sempre com timezone explícita. Isso evita o bug clássico de
# usar `datetime.now()` (naive) e tratar como BRT: se o servidor (ex.: worker do
# Airflow) está em UTC, o naive devolve UTC e, ao somar +3 h depois, o filtro do
# Otto vai para 3 h no futuro - resultado: propostas/reservas recentes ficam fora
# da janela `WHERE updated_at >= %s` e o Monday acaba sem atualização.
# Tanto AutoBackoffice-old.py quanto AutoDocu.py já usam este padrão.
current_time_utc = datetime.now(timezone.utc)
# Buffer de 60 s para evitar perder updates gravados no Otto exatamente no segundo
# do corte. A idempotência do AutoBackoffice 2.0 (diff por coluna, detecção de
# cruzamento, cache indexado por `id_negocio`) garante que reprocessar 1 minuto
# antes não duplica nada no Monday.
current_time_utc = current_time_utc - timedelta(seconds=60)
# Hora em UTC-3 (BRT). Usada para logar e para gravar o checkpoint do arquivo, que
# por convenção do projeto sempre fica em BRT.
current_time_brt = current_time_utc.astimezone(timezone(timedelta(hours=-3)))

# Log explícito do TZ do servidor: se este log mostrar `UTC` em prod e `BRT/`
# `America/Sao_Paulo` no dev local, é mais fácil diagnosticar incoerências de
# janela de tempo entre as duas pontas.
try:
    _tz_local_name = time.tzname[time.daylight] if time.daylight else time.tzname[0]
    _offset_local_segundos = -time.altzone if time.daylight else -time.timezone
    _offset_local_horas = _offset_local_segundos / 3600.0
    logger.info(
        f"Timezone do servidor: {_tz_local_name} (UTC{_offset_local_horas:+.1f}). "
        f"Hora atual UTC: {current_time_utc.strftime('%Y-%m-%d %H:%M:%S')} (UTC). "
        f"Hora atual BRT: {current_time_brt.strftime('%Y-%m-%d %H:%M:%S')} (UTC-3)."
    )
except Exception as exc:
    logger.debug(f"Não foi possível inspecionar `time.tzname/timezone`: {exc}.")

# Mantemos `hora_atual_local` apontando para o BRT, que é o formato gravado no
# arquivo de checkpoint - assim qualquer outro trecho que ainda use a variável
# continua semanticamente coerente (BRT, sem TZ explícita).
hora_atual_local = current_time_brt.replace(tzinfo=None)

# Antes de começar a atualização, vamos ler o arquivo de data da última atualização, se ele existir
arquivo_hora_atualizacao = os.path.join(
    pasta_dados, "ultima_atualizacao_autobackoffice_2_0.txt"
)
if os.path.exists(arquivo_hora_atualizacao):
    try:
        with open(arquivo_hora_atualizacao, "r", encoding="utf-8") as f:
            ultima_atualizacao_local_string = f.read().strip() # Lê a data como string do arquivo (UTC-3)
            try:
                ultima_atualizacao_local = datetime.strptime(ultima_atualizacao_local_string, "%Y-%m-%d %H:%M:%S") # Tenta converter a string para um objeto datetime (UTC-3)
                logger.info(f"Data da última atualização lida do arquivo: {ultima_atualizacao_local_string} (UTC-3)")
            except ValueError:
                logger.error(f"Formato de data inválido no arquivo: {ultima_atualizacao_local_string}. Buscando últimos 30 dias de dados.")
                ultima_atualizacao_local = hora_atual_local - timedelta(days=ultimos_dias_para_atualizar) # Se o formato for inválido, usa uma data padrão (30 dias atrás, UTC-3)
    except Exception as e:
        logger.error(f"Erro ao ler o arquivo de data de última atualização: {e}. Buscando últimos 30 dias de dados.")
        ultima_atualizacao_local = hora_atual_local - timedelta(days=ultimos_dias_para_atualizar) # Se houver um erro ao ler o arquivo, usa uma data padrão (30 dias atrás, UTC-3)

else: # Caso o arquivo não exista, define uma data padrão (30 dias atrás)
    ultima_atualizacao_local = hora_atual_local - timedelta(days=ultimos_dias_para_atualizar)
    logger.info(f"Arquivo de data de última atualização não encontrado. Buscando últimos 30 dias de dados.")

# A data só será salva no final do negocio, após a atualização ser concluída com sucesso, para garantir
#   que na próxima execução o script busque os dados a partir da última atualização real.

# As datas usadas no código devem estar em UTC, que é o formato que o Otto e o Monday usam.
# A data lida do arquivo está em UTC-3 e precisa ser convertida para UTC.
# Conversão TZ-aware: independente do TZ do servidor onde isso roda, sempre marca
# o valor lido como BRT (UTC-3) e converte para UTC para o filtro do Otto.
ultima_atualizacao_utc = (
    ultima_atualizacao_local
    .replace(tzinfo=timezone(timedelta(hours=-3)))
    .astimezone(timezone.utc)
)
ultima_atualizacao_utc_string = ultima_atualizacao_utc.strftime('%Y-%m-%d %H:%M:%S')
logger.info(f"Data de última atualização convertida para UTC: {ultima_atualizacao_utc_string} (UTC)")


#### EMPRESAS GC (omitido no 2.0) ####
empresas_gc: Dict[str, Any] = {}


#### ATUALIZAÇÕES OTTO ####

# Negocios
logger.info(f"Buscando negócios no Otto com data de última atualização a partir de: {ultima_atualizacao_utc_string} (UTC)")
negocios = cliente_otto.get_processes(after_date=ultima_atualizacao_utc_string)

logger.info(f"Total de negocios obtidos do Otto: {len(negocios)}")

""" Formato do dicionário processes:
{
    id_negocio (str): {
        'negocio_criado_em': datetime,
        'negocio_atualizado_em': datetime,
        'id_corretor': str,
        'cargo_corretor': str,
        'nome_corretor': str,
        'creci_corretor': str,
        'cpf_corretor': str,
        'id_gerente': str,
        'nome_gerente': str,
        'id_executivo': str,
        'nome_executivo': str,
        'id_imobiliaria': str,
        'nome_imobiliaria': str,
        'id_unidade': str,
        'numero_unidade': str,
        'id_integracao_unidade': str,
        'flag_permuta': bool,
        'valor_unidade': float,
        'resultado_integracao_unidade': dict,
        'id_torre': str,
        'nome_torre': str,
        'id_integracao_torre': str,
        'id_empreendimento': str,
        'nome_empreendimento': str,
        'id_integracao_empreendimento': str,
        'nome_incorporadora': str,
        'id_cliente': str,
        'nome_cliente': str,
        'cpf_cliente': str,
        'cnpj_cliente': str
    }
}
"""

# Organiza os negócios por data da última atualização, com a mais antiga primeiro
negocios: Dict[str, Dict[str, Any]] = dict(sorted(negocios.items(), key=lambda x: x[1]['negocio_atualizado_em']))

# Reservas
reservas: Dict[str, Dict[str, Any]] = cliente_otto.get_bookings(after_date=ultima_atualizacao_utc_string)
logger.info(f"Total de reservas obtidas do Otto: {len(reservas)}")

""" Formato do dicionário bookings:
{
    id_reserva (str): {
        'id_negocio': str,
        'reserva_criada_em': datetime,
        'reserva_atualizada_em': datetime,
        'id_status_reserva': str,
        'posicao_fila': int,
        'inicio_primeira_posicao': datetime,
        'fim_primeira_posicao': datetime,
        'resultado_integracao_reserva': dict
    }
}
"""

# Organiza as reservas por data da última atualização, com a mais antiga primeiro
reservas: Dict[str, Dict[str, Any]] = dict(sorted(reservas.items(), key=lambda x: x[1]['reserva_atualizada_em']))

# Propostas
propostas: Dict[str, Dict[str, Any]] = cliente_otto.get_proposals(after_date=ultima_atualizacao_utc_string)
logger.info(f"Total de propostas obtidas do Otto: {len(propostas)}")

""" Formato do dicionário proposals:
{
    id_proposta (str): {
        'id_negocio': str,
        'proposta_enviada_em': datetime,
        'id_status_proposta': str,
        'proposta_criada_em': datetime,
        'proposta_atualizada_em': datetime,
        'id_cliente': str,
        'proposta_entregue_em': datetime,
        'resultado_integracao_proposta': dict
    }
}
"""

# Organiza as propostas por data da última atualização, com a mais antiga primeiro
propostas: Dict[str, Dict[str, Any]] = dict(sorted(propostas.items(), key=lambda x: x[1]['proposta_atualizada_em']))

# Indexa reservas e propostas por id_negocio para evitar loops duplos
reservas_por_negocio: Dict[str, list[Dict[str, Any]]] = {}
for reserva in reservas.values():
    id_negocio_reserva = reserva.get("id_negocio")
    if not id_negocio_reserva:
        continue
    # Garante que existe uma lista para este id_negocio e adiciona a reserva nela.
    # setdefault cria a chave com uma lista vazia caso ela ainda não exista.
    reservas_por_negocio.setdefault(id_negocio_reserva, []).append(reserva)

propostas_por_negocio: Dict[str, list[Dict[str, Any]]] = {}
for proposta in propostas.values():
    id_negocio_proposta = proposta.get("id_negocio")
    if not id_negocio_proposta:
        continue
    propostas_por_negocio.setdefault(id_negocio_proposta, []).append(proposta)

# Junção das reservas e propostas com os respectivos negócios, mantendo a ordem de atualização
# Cria uma lista de atualizações dentro de cada negocio em ordem de data de atualização, contendo o tipo de atualização (reserva ou proposta) e os dados correspondentes
negocios_tratados = {}
for id_negocio, negocio in negocios.items():

    # Negócios sem cliente ou com cliente que são testes devem ser retirados da atualização
    id_cliente = negocio.get("id_cliente")
    if id_cliente is None:
        # Sem cliente então não é necessário atualizar o negócio
        continue

    nome_cliente = negocio.get("nome_cliente", "").lower()
    documento_cliente = negocio.get("cpf_cliente") or negocio.get("cnpj_cliente") or ""

    if not documento_cliente:
        # Se não houver documento do cliente, pula este negócio
        logger.warning(f"Negócio ignorado por não ter documento do cliente.")
        continue
    else:
        negocio["documento_cliente"] = documento_cliente

    if any(flag in nome_cliente for flag in flags_teste):
        # Se o nome do cliente contiver alguma das flags de teste, pula este negócio
        logger.warning(f"Negócio ignorado por conter flag de teste no nome do cliente: {nome_cliente}")
        continue

    negocio.pop("id_corretor", None)
    nome_corretor = (negocio.get("nome_corretor", "") or "").lower()

    if not (negocio.get("nome_corretor") or "").strip():
        logger.warning("Negócio ignorado por não ter nome do corretor.")
        continue

    if any(flag in nome_corretor for flag in flags_teste):
        logger.warning(
            f"Negócio ignorado por conter flag de teste no nome do corretor: {nome_corretor}"
        )
        continue

    negocio["corretor"] = {
        "nome": negocio.pop("nome_corretor"),
        "creci": negocio.pop("creci_corretor"),
        "cpf_cnpj": negocio.pop("cpf_corretor"),
    }

    # 2.0: papéis vão ao Monday só como texto; não exigir id_* do Otto para manter o nome.
    negocio.pop("id_gerente", None)
    nome_gerente = negocio.pop("nome_gerente", None)
    if nome_gerente and str(nome_gerente).strip():
        negocio["gerente"] = {"nome": nome_gerente}

    negocio.pop("id_executivo", None)
    nome_executivo = negocio.pop("nome_executivo", None)
    if nome_executivo and str(nome_executivo).strip():
        negocio["executivo"] = {"nome": nome_executivo}

    negocio.pop("id_imobiliaria", None)
    nome_imobiliaria = negocio.pop("nome_imobiliaria", None)
    if nome_imobiliaria and str(nome_imobiliaria).strip():
        negocio["imobiliaria"] = {"nome": nome_imobiliaria}

    negocio.pop("id_integracao_empreendimento", None)
    # DECIDIR: Outras regras de retirada do negócio das atualizações?

    negocio['atualizacoes'] = [] # Cria uma nova chave 'atualizacoes' para armazenar as atualizações de reserva e proposta

    # Verifica se há reservas associadas a este negócio e adiciona à lista de atualizações
    for reserva in reservas_por_negocio.get(id_negocio, []):
        negocio['atualizacoes'].append({
            'tipo': 'reserva',
            'dados': reserva,
            'data_atualizacao': reserva['reserva_atualizada_em']
        })

    # Verifica se há propostas associadas a este negócio e adiciona à lista de atualizações
    for proposta in propostas_por_negocio.get(id_negocio, []):
        negocio['atualizacoes'].append({
            'tipo': 'proposta',
            'dados': proposta,
            'data_atualizacao': proposta['proposta_atualizada_em']
        })

    # Ordena as atualizações dentro do negocio pela data de atualização, da mais antiga para a mais recente
    negocio['atualizacoes'] = sorted(negocio['atualizacoes'], key=lambda x: x['data_atualizacao'])

    # Salva o negócio no dicionário temporário
    negocios_tratados[id_negocio] = negocio

negocios = negocios_tratados

""" Formato do dicionário negocios após tratamento:
{
    'id_negocio'(str): {
        'negocio_criado_em': datetime.datetime(2026, 3, 7, 13, 36, 35, 235652),
        'negocio_atualizado_em': datetime.datetime(2026, 3, 7, 13, 36, 35, 235652),
        'cargo_corretor': 'Realtor',
        'cnpj_imobiliaria': '32.681.486/0001-67',
        'creci_imobiliaria': '25432J',
        'id_unidade': '06ed1fb2-ce88-405f-b805-b226b02d635d',
        'numero_unidade': '1309',
        'id_integracao_unidade': '13090017870',
        'valor_unidade': Decimal('956968.20'),
        'flag_permuta': False,
        'resultado_integracao_unidade': {'codTorre': '001',
        'codUnidade': '1309',
        'idTipoUnidade': 'A',
        'codEmpreendimento': 7870},
        'id_torre': '9f80cd28-620d-48ed-a853-75c7c0483726',
        'nome_torre': 'Torre Única + Unidades A',
        'id_integracao_torre': '0017870',
        'id_empreendimento': '8e8b9c5a-cf31-4d28-847b-4f563d9ed247',
        'nome_empreendimento': 'GO CARLOS GOMES',
        'nome_incorporadora': 'Melnick',
        'id_cliente': None,
        'nome_cliente': None,
        'cpf_cliente': None,
        'cnpj_cliente': None,
        'atualizacoes': [{'tipo': 'proposta',
        'dados': {'id_negocio': '003b0bc2-8337-4262-855a-eca29116522f',
            'proposta_enviada_em': None,
            'id_status_proposta': 6,
            'proposta_criada_em': datetime.datetime(2026, 3, 7, 13, 36, 35, 235652),
            'proposta_atualizada_em': datetime.datetime(2026, 3, 7, 13, 36, 55, 669871),
            'id_cliente': None,
            'proposta_entregue_em': datetime.datetime(2024, 11, 29, 0, 0),
            'resultado_integracao_proposta': None,
            'valor_proposta': Decimal('644158.42000000'),
            'ato': Decimal('287090.46000000'),
            'percentual_financiado': Decimal('55.4300'),
            'percentual_comissao': Decimal('6.0000'),
            'valor_comissao': None,
            'valor_liquido': Decimal('644158.42000000')},
        'data_atualizacao': datetime.datetime(2026, 3, 7, 13, 36, 55, 669871)}],
        'corretor': {'id_conta': '20d4c7f5-6f16-4e8b-bf63-414bfffba388',
        'nome': 'Nathan Candido Fortes',
        'creci': '076525f',
        'cpf_cnpj': '033.888.690-73'},
        'gerente': {'id_conta': 'c573a51d-5bde-481c-90c1-4d53d030c401',
        'nome': 'Franciely Fraga'},
        'executivo': {'id_conta': '90612dfc-5860-4438-aca9-5712e978d2b2',
        'nome': 'Juliana da Rosa Pereira'},
        'imobiliaria': {'id_conta': 'fe2113cd-4506-4720-9ace-ac8731c7e718',
        'nome': 'Urban Company (Porto Alegre)'},
        'vendedor': {'nome': 'Melnick Even Pavoï¿½Empreendimento Imobiliï¿½rio Ltda.',
        'id_conta': '7870',
        'cpf_cnpj': '35.504.198/0001-25',
        'tipo_de_conta': 'Vendedor'}}
}

"""
logger.info(f"Negócios válidos para atualização: {len(negocios)}")
#### ITENS MONDAY ####


arquivo_negocios_monday = os.path.join(pasta_dados, "negocios_monday_2_0.json")
negocios_monday_carregados = _carregar_json_resiliente(
    caminho=arquivo_negocios_monday,
    descricao="negocios_monday_2_0.json",
) or {}
negocios_monday_carregados = _indexar_negocios_monday_por_id_negocio(
    negocios_monday_carregados,
    origem="cache local negocios_monday_2_0.json",
)
if negocios_monday_carregados:
    logger.info(
        f"Negócios do Monday carregados com sucesso. "
        f"Total de negócios do Monday carregados: {len(negocios_monday_carregados)}"
    )
else:
    logger.info(
        "Cache `negocios_monday_2_0.json` ausente/inválido. Será reconstruído a partir "
        "do Monday nesta execução e regravado ao final."
    )

# SOLO: resolve alvo (preferindo id_monday) e filtra `negocios` (Otto) para 1 item.
_solo_id_negocio_resolvido = ""
if AUTOBACKOFFICE_SOLO_ID_MONDAY:
    alvo_monday = str(AUTOBACKOFFICE_SOLO_ID_MONDAY)
    for _id_negocio, _item in (negocios_monday_carregados or {}).items():
        if str((_item or {}).get("id_monday") or "") == alvo_monday:
            _solo_id_negocio_resolvido = str(_id_negocio)
            break
    if not _solo_id_negocio_resolvido:
        logger.error(
            "--- SOLO --- id_monday=%s não foi encontrado no cache local %s. "
            "Rode uma vez sem SOLO para popular o cache ou confirme o id_monday no board %s.",
            alvo_monday,
            arquivo_negocios_monday,
            BOARD_NEGOCIOS_2_0,
        )
        raise SystemExit(1)
elif AUTOBACKOFFICE_SOLO_ID_NEGOCIO:
    _solo_id_negocio_resolvido = str(AUTOBACKOFFICE_SOLO_ID_NEGOCIO)

if _solo_id_negocio_resolvido:
    if _solo_id_negocio_resolvido in negocios_tratados:
        negocios = {_solo_id_negocio_resolvido: negocios_tratados[_solo_id_negocio_resolvido]}
        logger.info(
            "--- SOLO --- Negócios filtrados: 1 (id_negocio=%s, id_monday=%s).",
            _solo_id_negocio_resolvido,
            AUTOBACKOFFICE_SOLO_ID_MONDAY or "(n/a)",
        )
    else:
        logger.error(
            "--- SOLO --- id_negocio=%s não foi encontrado na janela Otto desta execução. "
            "Ajuste a data de última atualização (ou amplie a janela) e tente novamente.",
            _solo_id_negocio_resolvido,
        )
        raise SystemExit(1)


# TODO: Implementar save e load de uma cópia dos dados locais do Monday, salvando
#       uma cópia em um arquivo JSON ou em um banco de dados local.
#       Caso seja um banco de dados local, criar o banco e o esquema.
#       Também rodar uma busca de itens com atualizações recentes para fazer o update
#       dos dados locais.

# Negócios
# Carrega o board completo e indexa por `id_negocio` para evitar falso "inexistente"
# em reprocessamentos de janela (data para trás), que pode gerar duplicidade.
negocios_monday = cliente_monday.get_items(
    board_id=BOARD_NEGOCIOS_2_0,
)
negocios_monday = _indexar_negocios_monday_por_id_negocio(
    negocios_monday,
    origem="busca Monday board completo",
)
ids_negocios_otto = set(negocios.keys())
negocios_monday = {
    id_negocio: item
    for id_negocio, item in negocios_monday.items()
    if id_negocio in ids_negocios_otto
}
logger.info(
    f"Negócios encontrados no Monday para a janela Otto: {len(negocios_monday)} "
    f"(de {len(ids_negocios_otto)} negócios Otto na execução)."
)

negocios_monday_atualizados_hoje = cliente_monday.get_items_updated_today_yesterday(
    board_id=BOARD_NEGOCIOS_2_0,
    parse_data=True,
    column_mapping=True
)
negocios_monday_atualizados_hoje = _indexar_negocios_monday_por_id_negocio(
    negocios_monday_atualizados_hoje,
    origem="busca Monday atualizados hoje/ontem",
)

logger.info(f"Negócios atualizados hoje: {len(negocios_monday_atualizados_hoje)}")

#  atualiza o dicionario negocios_monday_carregados com os novos negocios atualizados hoje e o negocios_monday
negocios_monday_carregados.update(negocios_monday_atualizados_hoje)
negocios_monday_carregados.update(negocios_monday)
negocios_monday = negocios_monday_carregados
logger.info(f"Negócios do Monday atualizados com sucesso. Total de negócios do Monday atualizados: {len(negocios_monday)}")


# Varredura profunda + remoção:
#   1) busca direto no Monday todos os itens que casam com `FILTROS_VARREDURA_REMOCAO_MONDAY`
#      (ex.: status 'Caiu'), pegando inclusive itens antigos que nunca entraram no cache;
#   2) mergeia no cache local `negocios_monday`;
#   3) aplica `REGRAS_REMOCAO_MONDAY` no cache atualizado, deletando no Monday quem casar
#      (JSON permanece como histórico, status_item_monday NÃO é alterado).
logger.info(
    f"Varredura profunda + remoção no Monday "
    f"({len(FILTROS_VARREDURA_REMOCAO_MONDAY)} filtro(s), "
    f"{len(REGRAS_REMOCAO_MONDAY)} regra(s) ativa(s))..."
)
resumo_limpeza = varredura_e_remocao_monday(
    negocios_monday=negocios_monday,
    cliente=cliente_monday,
    board_id=BOARD_NEGOCIOS_2_0,
    filtros=FILTROS_VARREDURA_REMOCAO_MONDAY,
    regras=REGRAS_REMOCAO_MONDAY,
)
resumo_remocao = resumo_limpeza["remocao"]
logger.info(
    f"Varredura/remoção concluída. "
    f"Itens por filtro: {resumo_limpeza['itens_trazidos_por_filtro']}. "
    f"Novos no cache: {resumo_limpeza['novos_no_cache']}. "
    f"Deletados: {resumo_remocao['deletados']}. "
    f"Falhas: {resumo_remocao['falhas']}. "
    f"Já deletados anteriormente (pulados): {resumo_remocao['pulados_ja_deletados']}. "
    f"Por regra: {resumo_remocao['por_regra']}."
)

""" Formato do dicionário negocios_monday:
{
    "id_monday"(str): {
        'atualizado_em'(datetime): datetime.datetime(2026, 2, 27, 20, 50, 58),
        'nome_negocio'(str): 'SEEN MENINO DEUS | TORRE ÚNICA | 603 | FRANCIELI IUNG IZOLANI',
        'status_item_monday'(str): 'active',
        'status_negocio'(str): 'Caiu',
        'id_envelope': None,
        'negocio_criado_em': '2025-12-23 12:58:14',
        'id_negocio': 'd79698bd-afb3-4464-bf85-904f2e897416',
        'id_unidade': '30f862ae-28a8-4cd4-a6a6-d27eb784d4ef',
        'nome_empreendimento': 'Seen Menino Deus',
        'nome_torre': 'Torre Única',
        'numero_unidade': 603,
        'status_reserva': 'Na fila',
        'posicao_fila': None,
        'status_integracao_reserva': 'Sucesso',
        'nome_cliente': 'Francieli Iung Izolani',
        'nome_corretor': 'Vinicius Dal Castel',
        'nome_imobiliaria': 'Imobiliária Castel',
        'data_comeco_reserva': '2026-02-10 16:40:21',
        'ultima_atualizacao'(dict): {'updated_at': datetime.datetime(2026, 2, 27, 20, 50, 58), 'updater_id': '43582856'}
        'status_proposta': 'Não aprovada',
        'data_proposta': '2025-12-23 13:01:35',
        'perda_vpl': None,
        'desconto_politica': None,
        'percentual_financiado': None,
        'status_integracao_proposta': 'Sucesso',
        'valor_proposta': None,
        'valor_comissao': None,
        'valor_liquido': None,
        'numero_proposta_gc': 453290,
        'link_reserva': {'url': 'https://admin.beotto.com/reserva/dc4f3e4e-3ae0-4569-a89b-3fdf44755936',
        'text': 'Link da Reserva'},
        'link_proposta': {'url': 'https://admin.beotto.com/proposta/d79698bd-afb3-4464-bf85-904f2e897416',
        'text': 'Link da Proposta'},
        'percentual_comissao': None,
        'status_integracao_docusign': None,
        'nome_contrato': None,
        'status_emissao': None,
        'status_contrato': None,
        'pendencias_analise': None,
        'link_contrato': None,
        'documento_cliente': '014.011.550-14',
        'data_reserva': '2025-12-23 14:12:11',
        'proposta_criada_em': '2025-12-23 12:58:14',
        'status_analise_credito': None,
        'pendencias_credito': None,
        'status_pasta': 'Sem Pasta',
        'id_imobiliaria': [{'id': '10843682077', 'name': 'Imobiliária Castel'}],
        'id_corretor': [{'id': '10843673077', 'name': 'Vinicius Dal Castel'}],
        'id_vendedor': [{'id': '10843311624', 'name': 'Melnick'}],
        'id_gerente': [],
        'id_executivo': [{'id': '10989040264', 'name': 'Rodrigo Freitas Reyes'}]
    }
}
"""

####
def criar_pendencia(id_monday, pendencia):
    cliente_monday.update_item(
        board_id=BOARD_NEGOCIOS_2_0,
        item_id=id_monday,
        column_values={"pendencias_analise": {"labels": [pendencia]}},
        create_labels_if_missing=True
    )
###


# Troca as chaves dos dicionários para usar o ID do negocio como chave, para facilitar a comparação
temp_negocios_monday = {} # Cria um dicionário temporário para armazenar os itens do Monday com o ID do negocio como chave


def _chave_ordenacao_data(valor: Any) -> str:
    """
    Converte `datetime`/string/None em uma string ordenável (formato ISO-like), para
    comparar datas de atualização vindas de fontes heterogêneas (cache JSON em string,
    `get_items` do Monday em datetime, itens novos/legados sem a chave). Itens sem data
    viram string vazia e são considerados "mais antigos" na comparação.
    """
    if valor is None or valor == "":
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    return str(valor)


for id_item, item in negocios_monday.items():

    # Proteções: itens vindos do merge podem estar sem `id_negocio` ou `atualizado_em`
    # (ex.: entradas antigas do cache, ou itens trazidos pela varredura profunda sem a
    # coluna populada no Monday). Usar `.get` evita KeyError e mantém o loop defensivo.
    id_negocio = item.get('id_negocio')
    if not id_negocio:
        logger.debug(
            f"Item {id_item} no Monday sem `id_negocio` preenchido. Ignorando no loop "
            f"de deduplicação."
        )
        continue

    negocio_monday_atualizado_em = item.get('atualizado_em')

    if id_negocio in temp_negocios_monday:

        negocio_duplicado_atualizado_em = temp_negocios_monday[id_negocio].get('atualizado_em')

        id_monday_1 = temp_negocios_monday[id_negocio].get("id_monday")
        id_monday_2 = item.get("id_monday")
        logger.warning(
            f"ID de negocio duplicado encontrado no Monday: {id_negocio}. "
            f"Há mais de um item no Monday com o mesmo ID de negocio do Otto, o que pode causar problemas de comparação. "
            f"ID do item 1: {id_monday_1}, ID do item 2: {id_monday_2}. "
            f"Verifique os dados no Monday para resolver essa duplicidade."
        )

        # Compara as datas de atualização dos itens duplicados para identificar qual é o
        # mais recente. `_chave_ordenacao_data` normaliza `None`/`datetime`/`str` antes
        # da comparação, evitando `TypeError: '>' not supported between NoneType and ...`.
        if _chave_ordenacao_data(negocio_monday_atualizado_em) > _chave_ordenacao_data(negocio_duplicado_atualizado_em):
            # Adicionamos uma tag de duplicado ao item mais antigo, para facilitar a identificação e resolução dessa questão no Monday
            id_negocio_duplicado = temp_negocios_monday[id_negocio].get("id_monday")
            pendencias_duplicado = temp_negocios_monday[id_negocio].get('pendencias_analise', [])
            if not id_negocio_duplicado:
                logger.warning(
                    f"Não foi possível identificar `id_monday` do item duplicado mais antigo para id_negocio={id_negocio}. "
                    f"Pulando criação de pendência."
                )
            elif pendencias_duplicado is not None and "Duplicado" in pendencias_duplicado:
                logger.info(
                    f"A pendência de 'Duplicado' já existe para o item com ID {id_negocio_duplicado} no Monday, "
                    f"não será criada novamente."
                )
            else:
                criar_pendencia(id_negocio_duplicado, "Duplicado")
                logger.info(f"A pendência de 'Duplicado' foi criada para o item com ID {id_negocio_duplicado} no Monday")

            # Substitui o negocio do monday sendo no dicionário temp pelo novo, mais recente
            temp_negocios_monday[id_negocio] = dict(item)
            logger.info(
                f"O item com id_monday={item.get('id_monday')} é mais recente que o item com id_monday={id_negocio_duplicado} "
                f"para o negocio com ID {id_negocio}, então o item mais recente foi mantido."
            )

        else:
            # Apenas salva um log, mantendo o negocio do monday já existente no dicionário temp, que é o mais recente
            logger.info(
                f"O item com id_monday={temp_negocios_monday[id_negocio].get('id_monday')} é mais recente que o item com id_monday={item.get('id_monday')} "
                f"para o negocio com ID {id_negocio}, então o item mais recente foi mantido."
            )

            # Adicionamos uma tag de duplicado para o item mais antigo, para facilitar a identificação e resolução dessa questão no Monday
            pendencias_item = item.get('pendencias_analise', [])
            id_monday_item = item.get("id_monday")
            if not id_monday_item:
                logger.warning(
                    f"Não foi possível identificar `id_monday` do item duplicado mais antigo para id_negocio={id_negocio}. "
                    f"Pulando criação de pendência."
                )
            elif pendencias_item is not None and "Duplicado" in pendencias_item:
                logger.info(
                    f"A pendência de 'Duplicado' já existe para o item com ID {id_monday_item} no Monday, "
                    f"não será criada novamente."
                )
            else:
                criar_pendencia(id_monday_item, "Duplicado") # Cria uma pendência de "Duplicado" para os itens que têm o mesmo ID de negocio, para facilitar a identificação e resolução dessa questão no Monday
                logger.info(f"A pendência de 'Duplicado' foi criada para o item com ID {id_monday_item} no Monday")


    else:
        # Primeiro item para este id_negocio: mantém no dicionário final.
        # `negocios_monday` já está indexado por `id_negocio`, então `id_item` aqui tende a ser o UUID do Otto.
        # Só usamos `id_item` como fallback de `id_monday` se ele parecer um id numérico de pulse.
        item_base = dict(item)
        if not item_base.get("id_monday"):
            id_item_str = str(id_item)
            if id_item_str.isdigit():
                item_base["id_monday"] = id_item_str
        temp_negocios_monday[id_negocio] = item_base

    # DECIDIR:
    # Decidir qual será o negócio considerado como o original,
    # por que só um negocio do monday pode ser colocado com a chave do ID do negocio do Otto,
    # e os outros terão que ser considerados como duplicados.
    # Atualmente estamos seguindo com o critério de manter o mais recente como o "original", e marcar o mais antigo como "duplicado", mas isso pode ser ajustado conforme a necessidade.

negocios_monday = temp_negocios_monday # Substitui o dicionário original pelo temporário, que agora tem o ID do negocio como chave
# Agora temos um dicionário de negocios do Monday com o ID do negocio do Otto como chave, o que facilita a comparação entre os dados do Otto e do Monday para cada negocio.

""" Novo formato do dicionário negocios_monday após troca de chaves:
{
    'id_negocio'(str): {
        'atualizado_em'(datetime): datetime.datetime(2026, 2, 27, 20, 50, 58),
        'nome_negocio'(str): 'SEEN MENINO DEUS | TORRE ÚNICA | 603 | FRANCIELI IUNG IZOLANI',
        'status_item_monday'(str): 'active',
        'status_negocio'(str): 'Caiu',
        'id_envelope': None,
        'negocio_criado_em': '2025-12-23 12:58:14',
        'id_negocio': 'd79698bd-afb3-4464-bf85-904f2e897416',
        'id_unidade': '30f862ae-28a8-4cd4-a6a6-d27eb784d4ef',
        'nome_empreendimento': 'Seen Menino Deus',
        'nome_torre': 'Torre Única',
        'numero_unidade': 603,
        'status_reserva': 'Na fila',
        'posicao_fila': None,
        'status_integracao_reserva': 'Sucesso',
        'nome_cliente': 'Francieli Iung Izolani',
        'nome_corretor': 'Vinicius Dal Castel',
        'nome_imobiliaria': 'Imobiliária Castel',
        'data_comeco_reserva': '2026-02-10 16:40:21',
        'ultima_atualizacao'(dict): {'updated_at': datetime.datetime(2026, 2, 27, 20, 50, 58), 'updater_id': '43582856'}
        'status_proposta': 'Não aprovada',
        'data_proposta': '2025-12-23 13:01:35',
        'perda_vpl': None,
        'desconto_politica': None,
        'percentual_financiado': None,
        'status_integracao_proposta': 'Sucesso',
        'valor_proposta': None,
        'valor_comissao': None,
        'valor_liquido': None,
        'numero_proposta_gc': 453290,
        'link_reserva': {'url': 'https://admin.beotto.com/reserva/dc4f3e4e-3ae0-4569-a89b-3fdf44755936',
        'text': 'Link da Reserva'},
        'link_proposta': {'url': 'https://admin.beotto.com/proposta/d79698bd-afb3-4464-bf85-904f2e897416',
        'text': 'Link da Proposta'},
        'percentual_comissao': None,
        'status_integracao_docusign': None,
        'nome_contrato': None,
        'status_emissao': None,
        'status_contrato': None,
        'pendencias_analise': None,
        'link_contrato': None,
        'documento_cliente': '014.011.550-14',
        'data_reserva': '2025-12-23 14:12:11',
        'proposta_criada_em': '2025-12-23 12:58:14',
        'status_analise_credito': None,
        'pendencias_credito': None,
        'status_pasta': 'Sem Pasta',
        'id_imobiliaria': [{'id': '10843682077', 'name': 'Imobiliária Castel'}],
        'id_corretor': [{'id': '10843673077', 'name': 'Vinicius Dal Castel'}],
        'id_vendedor': [{'id': '10843311624', 'name': 'Melnick'}],
        'id_gerente': [],
        'id_executivo': [{'id': '10989040264', 'name': 'Rodrigo Freitas Reyes'}]
    },
}


"""

# AutoBackoffice 2.0: sem board CONTAS nem criação de contas.

# Cruzamentos

# TODO: Busca no Monday itens com o mesmo cliente na mesma unidade, para identificar possíveis negócios relacionados
#       ou duplicados, que podem inclusive serem cruzamentos caso o corretor for diferente
#       Agora temos que iterar pelos negócios do Otto e comparar com os negócios do Monday para
#       identificar quais negócios precisam ser criados ou atualizados no Monday

logger.info(
    f"Iniciando montagem dos dados de {len(negocios)} negócio(s) para envio ao Monday "
    f"(board NEGOCIOS={BOARD_NEGOCIOS_2_0})."
)

# Contadores de diagnóstico desta etapa. Útil para confirmar nos logs o que cada execução
# efetivamente preparou (antes de existir lógica de create/update, isso já permite comparar
# o que o Otto trouxe com o que o Monday recebeu).
resumo_negocios = {
    "total": 0,
    "ja_existe_no_monday": 0,
    "novos_no_monday": 0,
    "falhas_montagem": 0,
}

# Guarda os dicionários montados para uso na Fase C (diff + create/update).
# Chave = id_negocio (Otto); valor = dict com 'id_item_monday', 'update_melnick' e
# 'update_monday' (colunas já mapeadas para ID Monday).
negocios_para_sincronizar: Dict[str, Dict[str, Any]] = {}

for id_negocio, dados_negocio in negocios.items():
    resumo_negocios["total"] += 1
    logger.info(f"Processando negócio com ID {id_negocio}")

    # 1) Descobre se já existe no Monday (pelo cache local - confiável após o merge
    #    com os negócios trazidos por `varredura_e_remocao_monday` e pelo get_items
    #    principal).
    negocio_monday = negocios_monday.get(id_negocio)
    if negocio_monday:
        id_item_monday = negocio_monday.get("id_monday")
        resumo_negocios["ja_existe_no_monday"] += 1
        logger.info(
            f"Negócio {id_negocio}: já existe no Monday (id_item={id_item_monday}). "
            f"Fase C fará o diff e o update."
        )
    else:
        id_item_monday = None
        resumo_negocios["novos_no_monday"] += 1
        logger.info(
            f"Negócio {id_negocio}: inexistente no Monday. Fase C criará um novo item."
        )

    # 2) Monta o dicionário em chaves Melnick (snake_case) a partir de `dados_negocio`
    #    (2.0: sem relacionamentos com board de contas).
    try:
        update_melnick = montar_dados_monday_do_negocio(
            id_negocio=id_negocio,
            dados_negocio=dados_negocio,
        )
    except Exception as exc:
        resumo_negocios["falhas_montagem"] += 1
        logger.exception(
            f"Falha ao montar dados do negócio {id_negocio} para o Monday: {exc}. "
            f"Negócio será ignorado nesta execução."
        )
        continue

    # 3) Monta também o `nome_processo` (usado como `item_name` na criação). O antigo
    #    combinava Empreendimento|Torre|Unidade|Cliente em UPPER.
    nome_processo = " | ".join(
        [
            dados_negocio.get("nome_empreendimento") or "Empreendimento sem nome",
            dados_negocio.get("nome_torre") or "Torre sem nome",
            str(dados_negocio.get("numero_unidade") or "Sem número da unidade"),
            dados_negocio.get("nome_cliente") or "Cliente sem nome",
        ]
    ).upper()

    # 4) Converte as chaves Melnick para IDs de coluna do Monday. Apenas campos com
    #    mapeamento cadastrado são mantidos.
    update_monday = map_dict_keys(
        fonte="monday",
        id_mapeamento=str(BOARD_NEGOCIOS_2_0),
        dict_to_map=update_melnick,
        invert_mapping=True,
    )

    logger.debug(
        f"Negócio {id_negocio}: dict Melnick = {update_melnick}"
    )
    logger.debug(
        f"Negócio {id_negocio}: dict Monday (column_values) = {update_monday}"
    )

    negocios_para_sincronizar[id_negocio] = {
        "id_item_monday": id_item_monday,
        "nome_processo": nome_processo,
        "update_melnick": update_melnick,
        "update_monday": update_monday,
    }

logger.info(
    f"Montagem concluída. Total: {resumo_negocios['total']}. "
    f"Já no Monday: {resumo_negocios['ja_existe_no_monday']}. "
    f"A criar: {resumo_negocios['novos_no_monday']}. "
    f"Falhas de montagem: {resumo_negocios['falhas_montagem']}."
)

#### SINCRONIZAÇÃO COM O MONDAY (Fase C) ####
# Cria/atualiza os itens de negócio no board NEGOCIOS com base em `negocios_para_sincronizar`,
# aplicando detecção de cruzamento e diff por coluna para minimizar chamadas de API.

logger.info(
    f"Iniciando sincronização de {len(negocios_para_sincronizar)} negócio(s) com o Monday "
    f"(board NEGOCIOS={BOARD_NEGOCIOS_2_0})."
)
resumo_sync = sincronizar_negocios_com_monday(
    negocios_para_sincronizar=negocios_para_sincronizar,
    negocios_monday=negocios_monday,
    negocios=negocios,
    cliente=cliente_monday,
    board_id=BOARD_NEGOCIOS_2_0,
)
logger.info(
    f"Sincronização concluída. "
    f"Total: {resumo_sync['total']}. "
    f"Criados: {resumo_sync['criados']}. "
    f"Atualizados: {resumo_sync['atualizados']}. "
    f"Sem alteração: {resumo_sync['sem_alteracao']}. "
    f"Reatribuídos (cruzamento mesmo corretor): {resumo_sync['reatribuidos']}. "
    f"Cruzamentos sinalizados: {resumo_sync['cruzamentos_detectados']}. "
    f"Falhas: {resumo_sync['falhas']}."
)

# Persiste o cache atualizado em disco, para que a próxima execução já enxergue os
# novos `id_monday` criados e os campos sincronizados (evita reprocessar do zero em
# caso de falha parcial subsequente).
try:
    os.makedirs(os.path.dirname(arquivo_negocios_monday), exist_ok=True)
    with open(arquivo_negocios_monday, "w", encoding="utf-8") as f:
        json.dump(negocios_monday, f, indent=4, ensure_ascii=False, default=str)
    logger.info(
        f"Cache `negocios_monday_2_0.json` salvo após sincronização ({len(negocios_monday)} itens)."
    )
except Exception as exc:
    logger.error(
        f"Falha ao salvar o cache `negocios_monday_2_0.json` ({arquivo_negocios_monday}): "
        f"{exc}. As próximas execuções podem reprocessar itens recém-criados."
    )


#### FINALIZAÇÃO ####

# Grava a data/hora (UTC-3) desta execução como "última atualização" APENAS após o fluxo
# ter chegado até aqui sem exceção. Assim, em caso de falha no meio do script, a janela
# do Otto na próxima execução continua cobrindo o período que ainda não foi processado
# (idempotência: melhor reprocessar do que perder atualizações).
# IMPORTANTE: gravamos `current_time_brt`, que veio de `datetime.now(timezone.utc)` e
# foi convertido para BRT explicitamente. Não usar `datetime.now()` aqui - se o
# servidor estiver em UTC, gravaríamos UTC achando que é BRT e a próxima execução
# pesquisaria a janela errada (3 h no futuro).
try:
    checkpoint_brt_string = current_time_brt.strftime("%Y-%m-%d %H:%M:%S")
    with open(arquivo_hora_atualizacao, "w", encoding="utf-8") as f:
        f.write(checkpoint_brt_string)
    logger.info(
        f"Última atualização salva em {arquivo_hora_atualizacao}: "
        f"{checkpoint_brt_string} (UTC-3)."
    )
except Exception as exc:
    logger.error(
        f"Falha ao gravar o arquivo de última atualização ({arquivo_hora_atualizacao}): "
        f"{exc}. A próxima execução pode reprocessar a mesma janela."
    )

logger.info("AutoBackoffice 2.0 concluído.")
