# Programa para atualização automática dos quadros do Monday com as informações
# do Backoffice, vindas do Otto e do Docusign, utilizando a API do Monday.

# Versão: 1.0

#### IMPORTAÇÔES ####
# %%
# STDLIB
import logging
import sys
import os
import json
from typing import Any, Callable, Dict, Tuple
from datetime import datetime, timedelta

# TERCEIROS
from dotenv import load_dotenv


#### CONFIGURAÇÔES ####

# Criação de um logger para registrar as atividades do script, como erros e informações importantes.

logging.basicConfig(
    level=logging.INFO, # Define o nível de log para INFO, ou seja, ele vai registrar mensagens de INFO, WARNING, ERROR e CRITICAL
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", # Define o formato das mensagens de log para incluir a data/hora, o nome do log de origem, o nível do log e a mensagem
    stream=sys.stdout # Define que as mensagens de log devem ser enviadas para a saída padrão (console)
)

logger = logging.getLogger("AutoBackoffice") # Cria um logger específico para este módulo, usando o nome do módulo como identificador

# Descobre o caminho da pasta atual onde este script está rodando,
#   para usar como referência para os arquivos de dados e logs.
dir_script = os.path.dirname(os.path.abspath(__file__))

# Monta o caminho da pasta de dados, que deve estar na mesma pasta do script.
pasta_dados = os.path.join(dir_script, "Dados")
# Garante que ela exista, e se não existir, cria a pasta.
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
from Módulos.cliente_sql import SQLClient
from Módulos.mapeamento_dados import map_dict_keys

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


#### REGRAS DE REMOÇÃO DE ITENS NO MONDAY ####
#
# Objetivo: identificar itens no cache local `negocios_monday.json` que devem ser
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
    Converte um valor de data lido do JSON (string `'YYYY-MM-DD HH:MM:SS'` ou `datetime`)
    em `datetime`. Retorna `None` se o valor for inválido/ausente.
    """
    if valor is None or valor == "":
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
        "descricao": "Negócios com status 'Caiu' criados há mais de 10 dias",
        "predicado": _regra_status_mais_antigo_que(
            campo_status="status_negocio",
            valor_status="Caiu",
            campo_data="negocio_criado_em",
            dias=10,
        ),
    },
    # Exemplo de regra futura (basta descomentar e ajustar):
    # {
    #     "nome": "concluido_mais_de_30_dias",
    #     "descricao": "Negócios 'Concluído' há mais de 30 dias",
    #     "predicado": _regra_status_mais_antigo_que(
    #         campo_status="status_negocio",
    #         valor_status="Concluído",
    #         campo_data="negocio_criado_em",
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

    for id_monday, item in negocios_monday.items():
        if not isinstance(item, dict):
            continue

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

        for id_monday, item in encontrados.items():
            if id_monday in negocios_monday:
                # Item já está no cache: preserva flags como `deletado_do_monday_em` e
                # campos extras que só o cache tem, atualizando só os campos vindos do Monday.
                cache_item = negocios_monday[id_monday]
                for k, v in item.items():
                    cache_item[k] = v
            else:
                negocios_monday[id_monday] = item
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


def criar_contas_faltantes_no_monday(
    contas: Dict[str, Dict[str, Any]],
    contas_monday: Dict[str, Dict[str, Any]],
    cliente: ClienteMonday,
    board_id: int,
    grupos_por_tipo: Dict[str, str],
) -> dict:
    """
    Para cada conta em `contas` que ainda não existe em `contas_monday`, cria o item
    correspondente no board CONTAS do Monday (no grupo certo conforme `tipo_de_conta`).
    Ao criar, o dicionário `contas_monday` é atualizado in-place com `id_monday` para
    que o próximo passo (loop de negócios) já possa usar a referência.

    Se a conta já existe em `contas_monday` (pelo `id_conta` Otto), o item é apenas pulado
    (atualização de dados existentes pode ser implementada posteriormente). Contas sem
    `id_conta` (ex.: vendedores especiais "Permutante" e "Melnick" que já vêm com
    `id_monday` hardcoded) também são ignoradas aqui, pois não precisam de criação.

    Args:
        contas: dict `{id_conta(Otto): {nome, tipo_de_conta, cpf_cnpj?, creci?, ...}}`.
        contas_monday: dict `{id_conta(Otto): {id_monday, nome, tipo_de_conta, ...}}` (mutado).
        cliente: instância de `ClienteMonday`.
        board_id: ID do board CONTAS no Monday.
        grupos_por_tipo: mapa `{tipo_de_conta: group_id}` (ex.: "Corretor" -> "group_mkyshgwh").

    Returns:
        dict com resumo: `criadas`, `ja_existentes`, `puladas_sem_id_conta`,
        `tipo_desconhecido`, `falhas`, `criadas_por_tipo`.
    """
    resumo = {
        "criadas": 0,
        "ja_existentes": 0,
        "puladas_sem_id_conta": 0,
        "tipo_desconhecido": 0,
        "falhas": 0,
        "criadas_por_tipo": {},
    }

    for id_conta, conta in contas.items():
        if not id_conta:
            resumo["puladas_sem_id_conta"] += 1
            continue

        if id_conta in contas_monday and contas_monday[id_conta].get("id_monday"):
            resumo["ja_existentes"] += 1
            logger.debug(
                f"Conta {id_conta} já existe no Monday com ID "
                f"{contas_monday[id_conta]['id_monday']}. Nada a criar."
            )
            continue

        tipo_de_conta = conta.get("tipo_de_conta")
        group_id = grupos_por_tipo.get(tipo_de_conta) if tipo_de_conta else None
        if group_id is None:
            resumo["tipo_desconhecido"] += 1
            logger.warning(
                f"Conta {id_conta} sem `tipo_de_conta` mapeado em GRUPOS_CONTAS_MONDAY "
                f"(tipo='{tipo_de_conta}'). Pulando criação."
            )
            continue

        nome = (conta.get("nome") or "NOME NÃO INFORMADO").title()

        # Monta `column_values` com os IDs de coluna do Monday (ver MONDAY_COLUMN_ID_MAP
        # em mapeamento_dados.py para o board CONTAS, id "18392694351").
        column_values: Dict[str, Any] = {
            "text_mkywmptw": str(id_conta),  # ID Otto
            "tipo_de_conta": tipo_de_conta,
        }
        cpf_cnpj = conta.get("cpf_cnpj")
        if cpf_cnpj:
            column_values["cpf_cnpj"] = cpf_cnpj
        creci = conta.get("creci")
        if creci:
            column_values["creci"] = creci

        try:
            id_monday_novo = cliente.create_item(
                board_id=board_id,
                group_id=group_id,
                item_name=nome,
                column_values=column_values,
            )
        except Exception as exc:
            resumo["falhas"] += 1
            logger.error(
                f"Falha ao criar conta {id_conta} ({tipo_de_conta} - {nome}) "
                f"no Monday: {exc}"
            )
            continue

        if not id_monday_novo:
            resumo["falhas"] += 1
            logger.error(
                f"`create_item` retornou vazio para conta {id_conta} "
                f"({tipo_de_conta} - {nome})."
            )
            continue

        contas_monday[id_conta] = {
            "id_monday": str(id_monday_novo),
            "nome": nome,
            "tipo_de_conta": tipo_de_conta,
            "documento": cpf_cnpj,
            "creci": creci,
            "id_conta": id_conta,
        }
        resumo["criadas"] += 1
        resumo["criadas_por_tipo"][tipo_de_conta] = (
            resumo["criadas_por_tipo"].get(tipo_de_conta, 0) + 1
        )
        logger.info(
            f"Conta criada no Monday: {tipo_de_conta} '{nome}' "
            f"(id_conta={id_conta}, id_monday={id_monday_novo})."
        )

    return resumo


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


def resolver_id_monday_da_conta(
    conta: Dict[str, Any] | None,
    contas_monday: Dict[str, Dict[str, Any]],
) -> str | None:
    """
    Dado um dict de conta nested no negócio (ex.: `negocio["corretor"]`), retorna
    o `id_monday` da conta correspondente.

    Prioridades:
      1. Se o próprio dict já tiver `id_monday` (caso de Permutante/Melnick hardcoded),
         usa direto.
      2. Se tiver `id_conta` (Otto), procura em `contas_monday[id_conta]["id_monday"]`.
         Essa via é a mais comum após `criar_contas_faltantes_no_monday` ter rodado.

    Retorna `None` se não conseguir resolver (caller decide se pula ou loga).
    """
    if not conta:
        return None
    id_monday_direto = conta.get("id_monday")
    if id_monday_direto:
        return str(id_monday_direto)
    id_conta = conta.get("id_conta")
    if id_conta and id_conta in contas_monday:
        id_monday_cache = contas_monday[id_conta].get("id_monday")
        if id_monday_cache:
            return str(id_monday_cache)
    return None


def _board_relation(id_monday: str | None) -> Dict[str, Any] | None:
    """
    Formata um `id_monday` no payload esperado para colunas de relacionamento (board
    relation) no Monday: `{"item_ids": ["<id>"]}`. Retorna `None` se o `id_monday`
    estiver ausente, para que o caller decida se inclui ou não o campo.
    """
    if not id_monday:
        return None
    return {"item_ids": [str(id_monday)]}


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


def montar_dados_monday_do_negocio(
    id_negocio: str,
    dados_negocio: Dict[str, Any],
    contas_monday: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Constrói o dicionário de atualização no formato Melnick (snake_case) para um
    único negócio, consumindo:
      - Os relacionamentos nested em `dados_negocio` (corretor/gerente/executivo/
        imobiliaria/vendedor) resolvidos via `contas_monday`.
      - A lista `atualizacoes` (reservas e propostas em ordem cronológica) aplicada
        sequencialmente — a mais recente sobrescreve campos equivalentes, preservando
        a semântica do `AutoBackoffice-old.py`.

    IMPORTANTE: este dict usa chaves Melnick. Para virar `column_values` do Monday,
    passe-o por `map_dict_keys("monday", str(IDS_BOARDS["NEGOCIOS"]), ..., invert_mapping=True)`.
    """
    nome_empreendimento = (dados_negocio.get("nome_empreendimento") or "").title()
    nome_torre = (dados_negocio.get("nome_torre") or "").title()
    nome_cliente = (dados_negocio.get("nome_cliente") or "").title()
    numero_unidade = dados_negocio.get("numero_unidade")

    # Propaga os nomes normalizados de volta ao dict original (o loop do main flow
    # pode precisar deles depois para o `item_name` no Monday, etc.).
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

    # Relacionamentos: cada papel vira uma coluna de board relation no Monday.
    # Se a conta não for encontrada (id_monday None), NÃO incluímos o campo — melhor
    # omitir do que mandar um relacionamento vazio e apagar o existente no Monday.
    papeis_relacionamento = [
        ("corretor", "id_corretor", "nome_corretor"),
        ("imobiliaria", "id_imobiliaria", "nome_imobiliaria"),
        ("gerente", "id_gerente", None),
        ("executivo", "id_executivo", None),
        ("vendedor", "id_vendedor", None),
    ]
    for papel, chave_relacao, chave_nome in papeis_relacionamento:
        conta = dados_negocio.get(papel)
        id_monday_conta = resolver_id_monday_da_conta(conta, contas_monday)
        rel = _board_relation(id_monday_conta)
        if rel is not None:
            update_dict[chave_relacao] = rel
        elif conta:
            logger.warning(
                f"Negócio {id_negocio}: papel '{papel}' tem conta "
                f"(id_conta={conta.get('id_conta')}, nome={conta.get('nome')}) mas sem "
                f"id_monday resolvido. Relacionamento será omitido nesta execução."
            )
        # Nome (ex.: nome_corretor/nome_imobiliaria) quando existir - o antigo só
        # populava esses dois. Os outros papéis não têm coluna de nome dedicada.
        if chave_nome and conta:
            nome_conta = (conta.get("nome") or "").title() or None
            if nome_conta:
                update_dict[chave_nome] = nome_conta

    # Itera pelas atualizações (reservas/propostas) em ordem cronológica.
    # Chaves posteriores sobrescrevem as anteriores, reproduzindo a semântica do antigo.
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


def detectar_cruzamento(
    id_negocio: str,
    update_melnick: Dict[str, Any],
    negocios_monday: Dict[str, Dict[str, Any]],
) -> Tuple[str | None, Dict[str, Any] | None]:
    """
    Replica a lógica de conflito do `AutoBackoffice-old.py` (linhas ~894-953) sobre o
    cache `negocios_monday`. Busca outros negócios com mesmo `documento_cliente` +
    `id_unidade` e retorna:

      - `(id_monday_reatribuicao, None)` quando encontra um item com o MESMO corretor.
        O caller deve tratar o negócio como update do item existente (o Otto apenas
        renumerou; não queremos criar duplicata no Monday).
      - `(None, {"pendencias_analise": {"labels": ["Cruzamento"]}})` quando encontra
        item com corretor DIFERENTE - sinaliza o negócio no Monday sem bloquear o
        fluxo.
      - `(None, None)` quando não há conflitos ou falta `documento_cliente`/
        `id_unidade` para análise confiável.

    Observações:
      - Na ausência de `id_corretor` no `update_melnick`, abortamos a verificação
        para evitar falsos positivos (reatribuir cegamente seria perigoso).
      - Se houver múltiplos conflitos do mesmo corretor, usamos o primeiro encontrado.
    """
    documento = update_melnick.get("documento_cliente")
    id_unidade = update_melnick.get("id_unidade")
    if not documento or not id_unidade:
        return None, None

    id_corretor_atual_set = _extrair_item_ids_para_diff(update_melnick.get("id_corretor"))
    if not id_corretor_atual_set:
        return None, None

    tem_corretor_diferente = False

    for outro_id, dados_cache in negocios_monday.items():
        if outro_id == id_negocio:
            continue
        if dados_cache.get("documento_cliente") != documento:
            continue
        if dados_cache.get("id_unidade") != id_unidade:
            continue

        corretor_conflito = _extrair_item_ids_para_diff(dados_cache.get("id_corretor"))
        if not corretor_conflito:
            # Sem corretor no conflito, não dá pra decidir. Log e segue.
            logger.debug(
                f"Cruzamento parcial: negócio {outro_id} tem mesmo cliente+unidade que "
                f"{id_negocio} mas está sem corretor no cache. Ignorando conflito."
            )
            continue

        if id_corretor_atual_set & corretor_conflito:
            id_monday_reatribuicao = dados_cache.get("id_monday")
            if id_monday_reatribuicao:
                logger.info(
                    f"Cruzamento: negócio {id_negocio} corresponde ao item "
                    f"{id_monday_reatribuicao} (mesmo cliente+unidade+corretor que "
                    f"negócio {outro_id}). Reatribuindo em vez de criar novo."
                )
                return str(id_monday_reatribuicao), None
            # Reatribuição sem id_monday não tem como funcionar; segue procurando.
            continue
        else:
            tem_corretor_diferente = True

    if tem_corretor_diferente:
        logger.warning(
            f"Cruzamento: negócio {id_negocio} tem mesmo cliente+unidade que outro "
            f"com corretor diferente. Marcando pendencias_analise=Cruzamento."
        )
        return None, {"pendencias_analise": {"labels": ["Cruzamento"]}}

    return None, None


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

    for indice, (id_negocio, pacote) in enumerate(negocios_para_sincronizar.items(), start=1):
        resumo["total"] += 1
        # Cópia defensiva: podemos mutar (adicionar `pendencias_analise` no cruzamento)
        # sem afetar o pacote original caso o caller queira reutilizá-lo.
        update_melnick: Dict[str, Any] = dict(pacote.get("update_melnick") or {})
        id_item_monday: str | None = pacote.get("id_item_monday")
        nome_processo: str = pacote.get("nome_processo") or ""
        dados_negocio = negocios.get(id_negocio, {})

        # 1) Cruzamento
        id_reatribuicao, pendencias = detectar_cruzamento(
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
            cache_atual = negocios_monday.get(id_negocio) or {}
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

IDS_BOARDS = {
    "NEGOCIOS": 18392682833,
    "CONTAS": 18392694351,
}

# Grupos dentro do board CONTAS, usados na criação de novos itens.
# Cada tipo de conta entra no seu grupo visual correspondente.
# Se novos tipos forem introduzidos, basta acrescentar aqui.
GRUPOS_CONTAS_MONDAY: Dict[str, str] = {
    "Corretor": "group_mkyshgwh",
    "Imobiliária": "group_title",
    "Gerente": "group_mm02915k",
    "Executivo": "group_mm02f9e9",
    "Vendedor": "group_mkywb4t3",
}


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


# Cliente SQL

sql_server = os.getenv("SQL_SERVER", "")
sql_database = os.getenv("SQL_DATABASE", "")
sql_user = os.getenv("SQL_USER", "")
sql_password = os.getenv("SQL_PASS", "")

# Levanta um erro com as variáveis de ambiente que não foram encontradas, para garantir que o usuário saiba quais variáveis estão faltando e possa corrigi-las antes de rodar o script.
variaveis_sql = {
    "SQL_SERVER": sql_server,
    "SQL_DATABASE": sql_database,
    "SQL_USER": sql_user,
    "SQL_PASS": sql_password
}
variaveis_sql_faltando = []

for var, value in variaveis_sql.items():
    if value is None or value == "":
        variaveis_sql_faltando.append(var) # Adiciona as variáveis faltando ao dicionário de variáveis faltando

if variaveis_sql_faltando != []:
    variaveis_faltando = ", ".join(variaveis_sql_faltando)
    raise ValueError(f"As seguintes variáveis de ambiente para o cliente SQL não foram encontradas ou estão vazias: {variaveis_faltando}. Por favor, defina-as no arquivo .env.")

# Cria o cliente SQL com as variáveis de ambiente encontradas
cliente_sql = None
try:
    cliente_sql = SQLClient(
        server=sql_server,
        database=sql_database,
        username=sql_user,
        password=sql_password
    )
    cliente_sql.connect()
    logger.info("Cliente SQL criado e conectado com sucesso.")
except Exception as e:
    logger.error(f"Erro ao criar ou conectar o cliente SQL: {e}")
    raise
finally:
    if cliente_sql is not None and cliente_sql.connection:
        cliente_sql.disconnect()
        logger.info("Cliente SQL desconectado com sucesso após o teste de conexão.")


#### DATA DE ATUALIZAÇÃO ####

ultimos_dias_para_atualizar = 1
# Busca a hora atual em UTC-3, que é o fuso horário de São Paulo, onde a Melnick está localizada.
# A data salva e lida do arquivo é sempre em UTC-3.
hora_atual_local = datetime.now()

# Antes de começar a atualização, vamos ler o arquivo de data da última atualização, se ele existir
arquivo_hora_atualizacao = os.path.join(pasta_dados, "ultima_atualizacao_autobackoffice.txt")
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
ultima_atualizacao_utc = ultima_atualizacao_local + timedelta(hours=3) # Converte a data lida do arquivo de UTC-3 para UTC
ultima_atualizacao_utc_string = ultima_atualizacao_utc.strftime('%Y-%m-%d %H:%M:%S')
logger.info(f"Data de última atualização convertida para UTC: {ultima_atualizacao_utc_string} (UTC)")


#### ATUALIZAÇÃO EMPRESAS GC ####

####
def normalizar_cnpj(valor):
    if not valor:
        return None
    # Remove tudo que nao for digito
    digitos = "".join(ch for ch in str(valor) if ch.isdigit())
    if len(digitos) != 14:
        return None
    return f"{digitos[0:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:14]}"


def transformar_lista_em_dict(lista_empresas):
    """
    Transforma uma lista de dicionários de empresas GC em um dicionário com o ID da empresa como chave, para facilitar a comparação entre as empresas GC do SQL e as empresas GC locais.

    Args:
        lista_empresas (list): Lista de dicionários, onde cada dicionário representa uma empresa GC, com uma chave "id_empresa_gc" que contém o ID da empresa.

    Returns:
        dict: Dicionário onde as chaves são os IDs das empresas GC e os valores são os dicionários originais das empresas.
    """
    dict_empresas = {}

    for empresa in lista_empresas:
        esta_empresa = {}

        for coluna, valor in empresa.items():
            # Limpa o nome da coluna dos colchetes e espaços, para facilitar o acesso aos dados
            nome_coluna = coluna.strip("[]").strip().lower() # Remove os colchetes e espaços, e deixa o nome da coluna em minúsculo para facilitar o acesso aos dados
            esta_empresa[nome_coluna] = str(valor).strip().title() # Converte o valor para string, remove espaços e coloca em formato title case para padronizar os dados

        cd_empreendimento = esta_empresa.pop("cd_empreendimento", None) # Remove o ID do empreendimento do dicionário da empresa, para usar como chave no dicionário final
        cnpj = esta_empresa.get("cnpj", "0") # Busca o CNPJ da empresa, e se não existir, define como "0" para evitar problemas de comparação com as empresas GC locais, que podem ter o CNPJ como "0" ou vazio

        if cnpj is None or cnpj == "" or cnpj == "0":
            logger.warning(f"Empresa GC código {cd_empreendimento} encontrada sem CNPJ. Ela não será salva e nem carregada no dicionário de empresas GC.")
            continue # Se o CNPJ for vazio, nulo ou "0", ignora essa empresa, pois o CNPJ é um dado importante para a identificação da empresa e para a comparação com as empresas GC locais, e sem ele pode causar problemas de comparação e identificação de atualizações.
        else:
            esta_empresa["cnpj"] = normalizar_cnpj(cnpj) # Normaliza o CNPJ para facilitar a comparação com as empresas GC locais, que podem ter o CNPJ em formatos diferentes

        if cd_empreendimento is not None:
            dict_empresas[cd_empreendimento] = esta_empresa
        else:
            logger.warning(f"Empresa GC encontrada sem ID de empreendimento (cd_empreendimento), ela será ignorada: {empresa}")

    return dict_empresas

""" Formato do resultado da consulta SQL para as empresas GC:
    [
        {
            "[cd_empreendimento]": 1220,
            "[nm_empresa]": "LIONFISH EVEN EMPREEN IMO",
            "[segmento]": "Economico",
            "[grupo_economico]": "Remanescentes",
            "[cnpj]": "0"
        },
    ]
"""

# Caso a conecão com o cliente SQL tenha sido bem-sucedida, busca as empresas GC do SQL, que são necessárias para comparar com as empresas GC locais e identificar se houve alguma atualização ou nova empresa GC criada no SQL que precisa ser atualizada no Monday.
if cliente_sql is None:
    logger.error("Cliente SQL não está disponível. Não será possível obter as empresas GC do SQL.")
    logger.info("Apenas empresas salvas localmente serão carregadas")
    empresas_gc_sql = None
else:
    cliente_sql.connect() # Conecta ao SQL para buscar as empresas GC, e depois desconecta para evitar deixar a conexão aberta
    empresas_gc_sql = cliente_sql.execute_query("SELECT * FROM dbo.Empresas_GC")
    empresas_gc_sql_comparativo = empresas_gc_sql.copy() if empresas_gc_sql is not None else None # Cria uma cópia da lista original de empresas GC do SQL para usar como base de comparação, já que a lista original será transformada em dicionário e não terá mais a estrutura original para comparação
    empresas_gc_sql = transformar_lista_em_dict(empresas_gc_sql) if empresas_gc_sql is not None else None
    if empresas_gc_sql is not None:
        logger.info(f"Empresas GC obtidas do SQL e transformadas em dicionário com sucesso. Total de empresas GC do SQL: {len(empresas_gc_sql)}")
    else:
        logger.warning("Nenhuma empresa GC obtida do SQL. Verifique se a consulta SQL está correta e se a conexão com o banco de dados está funcionando. A partir disso, apenas empresas salvas localmente serão carregadas.")

""" Formato do empresas_gc depois de tranformado em dicionário:
    "8180": {
        "nm_empresa": "LIONFISH EVEN EMPREEN IMO",
        "segmento": "Economico",
        "grupo_economico": "Remanescentes",
        "cnpj": "0"
    },
"""


# Busca o arquivo de empresas GC salvas localmente, para comparar com as empresas GC vindas do SQL e identificar se houve alguma atualização ou nova empresa GC criada no SQL que precisa ser atualizada no Monday.
pasta_empresas_gc = os.path.join(pasta_dados, "Empresas Empreendimentos")
os.makedirs(pasta_empresas_gc, exist_ok=True) # Garante que a pasta para salvar as empresas GC exista, e se não existir, cria a pasta

arquivo_empresas_gc = os.path.join(pasta_empresas_gc, "empresas_gc.json")
empresas_gc_local = _carregar_json_resiliente(
    caminho=arquivo_empresas_gc,
    descricao="empresas_gc.json",
)
if empresas_gc_local is not None:
    logger.info(
        f"Arquivo de empresas GC local encontrado e carregado com sucesso. "
        f"Total de empresas GC locais: {len(empresas_gc_local)}"
    )
else:
    logger.info(
        "Arquivo de empresas GC local ausente/inválido. Ele será regravado ao final da "
        "atualização, servindo de base de comparação para as próximas execuções."
    )

if cliente_sql is None and empresas_gc_local is None:
    raise ValueError(
        "Cliente SQL indisponível e arquivo local de empresas GC não encontrado. "
        "Não é possível continuar sem dados de empresas GC. "
        "Verifique a conexão com o SQL ou o arquivo local antes de buscar Otto/Monday."
    )

if empresas_gc_sql is not None and empresas_gc_local is not None:
    # Compara as empresas GC do SQL com as empresas GC locais para identificar se houve alguma atualização ou nova empresa GC criada no SQL que precisa ser atualizada no Monday, e salva as empresas GC atualizadas em um novo dicionário, para usar posteriormente na atualização dos negócios do Monday, já que os dados das empresas GC estão relacionados aos negócios.
    empresas_gc_atualizadas = {}
    empresas_gc_atualizadas.update(empresas_gc_local) # Começa o dicionário de empresas GC atualizadas com as empresas GC locais, e depois vai atualizar com as empresas GC do SQL que são novas ou atualizadas, para garantir que o dicionário de empresas GC atualizadas tenha todas as empresas GC locais, e as empresas GC do SQL que são novas ou atualizadas, para usar posteriormente na atualização dos negócios do Monday, já que os dados das empresas GC estão relacionados aos negócios.
    empresas_gc_atualizadas.update(empresas_gc_sql) # Atualiza o dicionário de empresas GC atualizadas com as empresas GC do SQL, para garantir que o dicionário de empresas GC atualizadas tenha todas as empresas GC do SQL, e as empresas GC locais que não foram atualizadas, para usar posteriormente na atualização dos negócios do Monday, já que os dados das empresas GC estão relacionados aos negócios.

    logger.info(f"Total de empresas GC novas ou atualizadas encontradas: {len(empresas_gc_atualizadas)}")
elif empresas_gc_sql is not None and empresas_gc_local is None:
    empresas_gc_atualizadas = empresas_gc_sql
    logger.info(f"Não foi possível comparar as empresas GC do SQL com as empresas GC locais, já que o arquivo de empresas GC local não foi encontrado. O dicionário de empresas GC atualizadas será criado apenas com as empresas GC do SQL. Total de empresas GC do SQL: {len(empresas_gc_sql)}")
elif empresas_gc_sql is None and empresas_gc_local is not None:
    empresas_gc_atualizadas = empresas_gc_local
    logger.info(f"Não foi possível comparar as empresas GC do SQL com as empresas GC locais, já que nenhuma empresa GC foi obtida do SQL. O dicionário de empresas GC atualizadas será criado apenas com as empresas GC locais. Total de empresas GC locais: {len(empresas_gc_local)}")
else:
    empresas_gc_atualizadas = None
    logger.warning("Nenhuma empresa GC obtida do SQL e nenhum arquivo de empresas GC local encontrado. O dicionário de empresas GC atualizadas não será criado, o que pode causar problemas na atualização dos negócios do Monday, já que os dados das empresas GC estão relacionados aos negócios.")

if empresas_gc_atualizadas is None:
    raise ValueError("O dicionário de empresas GC atualizadas não foi criado, já que nenhuma empresa GC foi obtida do SQL e nenhum arquivo de empresas GC local foi encontrado. Isso pode causar problemas na atualização dos negócios do Monday, já que os dados das empresas GC estão relacionados aos negócios. Verifique se a conexão com o SQL está funcionando e se o arquivo de empresas GC local está presente para resolver esse problema.")
else:
    empresas_gc: Dict[str, Any] = empresas_gc_atualizadas # Define o dicionário de empresas GC como o dicionário de empresas GC atualizadas, para usar posteriormente na atualização dos negócios do Monday, já que os dados das empresas GC estão relacionados aos negócios.

# Salva o dicionário de empresas GC atualizadas em um arquivo JSON, para ter um registro
# das empresas GC atualizadas e para usar como base de comparação na próxima execução
# do script. `encoding="utf-8"` evita que o Windows grave em cp1252 e o arquivo fique
# ilegível no Airflow/Linux (que lê como utf-8 por padrão).
with open(arquivo_empresas_gc, "w", encoding="utf-8") as f:
    # `empresas_gc_atualizadas` pode conter campos `datetime` vindos do SQL.
    # O `default=str` garante que datetime/date/etc sejam serializados para JSON.
    json.dump(empresas_gc_atualizadas, f, indent=4, ensure_ascii=False, default=str)
    logger.info(f"Dicionário de empresas GC atualizado salvo em arquivo JSON com sucesso: {arquivo_empresas_gc}")


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

# Inicializa lista de contas relacionadas aos negócios para depois fazer a busca no Monday
contas: Dict[str, Dict[str, Any]] = {} # Usamos um set para evitar contas duplicadas, já que vários negócios podem estar relacionados à mesma conta

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

    # Adiciona os CPFs e CNPJs das contas relacionadas ao negócio ao set de contas
    id_corretor = negocio.pop("id_corretor")
    nome_corretor = negocio.get("nome_corretor", "").lower()

    # Negócios sem corretor ou com corretor que são testes devem ser retirados da atualização, já que o corretor é um dado importante para a identificação do negócio e para a comparação com os negócios do Monday, e sem ele pode causar problemas de comparação e identificação de atualizações.
    if not id_corretor:
        # Se não houver corretor, pula este negócio
        logger.warning(f"Negócio ignorado não ter id do corretor.")
        continue

    elif any(flag in nome_corretor for flag in flags_teste):
        logger.warning(f"Negócio ignorado por conter flag de teste no nome do corretor: {nome_corretor}")
        continue

    else:
        negocio["corretor"] = {
            "id_conta": id_corretor,
            "nome": negocio.pop("nome_corretor"),
            #"cargo": negocio.pop("cargo_corretor"),
            "creci": negocio.pop("creci_corretor"),
            "cpf_cnpj": negocio.pop("cpf_corretor"),
            "tipo_de_conta": "Corretor",
        }
        contas[id_corretor] = negocio["corretor"] # Adiciona o corretor ao dicionário de contas, usando o ID do corretor como chave, para evitar contas duplicadas, já que vários negócios podem estar relacionados ao mesmo corretor
    
    id_gerente = negocio.pop("id_gerente")
    if id_gerente:
        negocio["gerente"] = {
            "id_conta": id_gerente,
            "nome": negocio.pop("nome_gerente"),
            "tipo_de_conta": "Gerente",
        }
        contas[id_gerente] = negocio["gerente"] # Adiciona o gerente ao dicionário de contas, usando o ID do gerente como chave, para evitar contas duplicadas, já que vários negócios podem estar relacionados ao mesmo gerente
    
    id_executivo = negocio.pop("id_executivo")
    if id_executivo:
        negocio["executivo"] = {
            "id_conta": id_executivo,
            "nome": negocio.pop("nome_executivo"),
            "tipo_de_conta": "Executivo",
        }
        contas[id_executivo] = negocio["executivo"] # Adiciona o executivo ao dicionário de contas, usando o ID do executivo como chave, para evitar contas duplicadas, já que vários negócios podem estar relacionados ao mesmo executivo

    id_imobiliaria = negocio.pop("id_imobiliaria")
    if id_imobiliaria:
        negocio["imobiliaria"] = {
            "id_conta": id_imobiliaria,
            "nome": negocio.pop("nome_imobiliaria"),
            "tipo_de_conta": "Imobiliária",
        }
        contas[id_imobiliaria] = negocio["imobiliaria"] # Adiciona a imobiliária ao dicionário de contas, usando o ID da imobiliária como chave, para evitar contas duplicadas, já que vários negócios podem estar relacionados à mesma imobiliária

    string_id_integracao_empreendimento: str = negocio.pop("id_integracao_empreendimento")
    flag_permuta = negocio.get("flag_permuta", False) # Busca a flag de permuta do negócio, e se não existir, define como False para evitar problemas de comparação com os negócios do Monday, que podem não ter essa informação, já que a flag de permuta é uma informação nova que pode não estar presente em todos os negócios do Otto, e sem ela pode causar problemas de comparação e identificação de atualizações.

    if flag_permuta:
        logger.info(f"Negócio é uma permuta e terá como vendedor o item 'Permutante' com ID 10843314010")
        negocio["vendedor"] = {
            "nome": "Permutante",
            "id_monday": 10843314010
        }
    else:
        # Caso não for permuta, busca os dados do empreendimento para cadastrar como vendedor
        if string_id_integracao_empreendimento:
            id_integracao_empreendimento: str | list[str] = string_id_integracao_empreendimento.strip().split("|") # Remove espaços em branco do ID de integração do empreendimento e divide pelo caractere "|" em uma lista
            id_empreendimento_gc = id_integracao_empreendimento[0] if len(id_integracao_empreendimento) > 0 else None # O ID do empreendimento GC é o primeiro item da lista, se existir
        else:
            id_empreendimento_gc = None
            
        if id_empreendimento_gc:
            empresa_empreendimento_gc = empresas_gc.get(id_empreendimento_gc) # Busca a empresa GC correspondente ao ID do empreendimento GC no dicionário de empresas GC, para obter os dados da empresa GC relacionada ao empreendimento do negócio, já que os dados da empresa GC estão relacionados aos negócios e são importantes para a identificação e comparação dos negócios com os itens do Monday
        else:
            empresa_empreendimento_gc = None

        if empresa_empreendimento_gc and id_empreendimento_gc:
            negocio["vendedor"] = {
                "nome": empresa_empreendimento_gc.get("nm_empresa"),
                "id_conta": id_empreendimento_gc,
                "cpf_cnpj": empresa_empreendimento_gc.get("cnpj"),
                "tipo_de_conta": "Vendedor"
            }
            contas[id_empreendimento_gc] = negocio["vendedor"] # Adiciona o empreendimento ao dicionário de contas, usando o ID do empreendimento GC como chave, para evitar contas duplicadas, já que vários negócios podem estar relacionados ao mesmo empreendimento GC
        else:
            # Caso nenhum dado do empreendimento seja encontrado, define o vendedor como "Melnick" com ID Monday 10843311624
            negocio["vendedor"] = {
                "nome": "Melnick",
                "id_monday": 10843311624
            }        

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


arquivo_negocios_monday = os.path.join(pasta_dados, "negocios_monday.json")
negocios_monday_carregados = _carregar_json_resiliente(
    caminho=arquivo_negocios_monday,
    descricao="negocios_monday.json",
) or {}
if negocios_monday_carregados:
    logger.info(
        f"Negócios do Monday carregados com sucesso. "
        f"Total de negócios do Monday carregados: {len(negocios_monday_carregados)}"
    )
else:
    logger.info(
        "Cache `negocios_monday.json` ausente/inválido. Será reconstruído a partir "
        "do Monday nesta execução e regravado ao final."
    )


# TODO: Implementar save e load de uma cópia dos dados locais do Monday, salvando
#       uma cópia em um arquivo JSON ou em um banco de dados local.
#       Caso seja um banco de dados local, criar o banco e o esquema.
#       Também rodar uma busca de itens com atualizações recentes para fazer o update
#       dos dados locais.

# Negocios
# Busca os itens no Monday com ID de negocio no Otto entre os com atualizações




negocios_monday = cliente_monday.get_items(
    board_id=IDS_BOARDS["NEGOCIOS"],
    column_id="customer_process_id",
    value=[id_negocio for id_negocio in negocios.keys()]
)

negocios_monday_atualizados_hoje = cliente_monday.get_items_updated_today_yesterday(
    board_id=IDS_BOARDS["NEGOCIOS"],
    parse_data=True,
    column_mapping=True
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
    board_id=IDS_BOARDS["NEGOCIOS"],
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

# Salva o dicionário negocios_monday_carregados em um arquivo JSON.
# `encoding="utf-8"` + `ensure_ascii=False` garantem compatibilidade entre Windows
# (cp1252 default) e Airflow/Linux (utf-8 default).
with open(arquivo_negocios_monday, "w", encoding="utf-8") as f:
    # `negocios_monday` pode conter campos `datetime` (ex.: `negocio_criado_em`).
    # O `default=str` evita o erro "Object of type datetime is not JSON serializable".
    json.dump(negocios_monday, f, indent=4, ensure_ascii=False, default=str)
    logger.info(f"Negócios do Monday salvos com sucesso em {arquivo_negocios_monday}")


####
def criar_pendencia(id_monday, pendencia):
    cliente_monday.update_item(
        board_id=IDS_BOARDS["NEGOCIOS"],
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

        logger.warning(f"ID de negocio duplicado encontrado no Monday: {id_negocio}. Há mais de um item no Monday com o mesmo ID de negocio do Otto, o que pode causar problemas de comparação. ID do item 1: {temp_negocios_monday[id_negocio]['id_monday']}, ID do item 2: {id_item}. Verifique os dados no Monday para resolver essa duplicidade.")

        # Compara as datas de atualização dos itens duplicados para identificar qual é o
        # mais recente. `_chave_ordenacao_data` normaliza `None`/`datetime`/`str` antes
        # da comparação, evitando `TypeError: '>' not supported between NoneType and ...`.
        if _chave_ordenacao_data(negocio_monday_atualizado_em) > _chave_ordenacao_data(negocio_duplicado_atualizado_em):
            # Adicionamos uma tag de duplicado ao item mais antigo, para facilitar a identificação e resolução dessa questão no Monday
            id_negocio_duplicado = temp_negocios_monday[id_negocio]['id_monday']
            pendencias_duplicado = temp_negocios_monday[id_negocio].get('pendencias_analise', [])
            if pendencias_duplicado is not None and "Duplicado" in pendencias_duplicado:
                logger.info(f"A pendência de 'Duplicado' já existe para o item com ID {id_negocio_duplicado} no Monday, não será criada novamente.")
            else:
                criar_pendencia(id_negocio_duplicado, "Duplicado")
                logger.info(f"A pendência de 'Duplicado' foi criada para o item com ID {id_negocio_duplicado} no Monday")

            # Substitui o negocio do monday sendo no dicionário temp pelo novo, mais recente
            temp_negocios_monday[id_negocio] = item
            temp_negocios_monday[id_negocio]['id_monday'] = id_item # Adiciona o ID do item do Monday como uma nova chave dentro do dicionário do negocio, para facilitar o acesso posteriormente
            logger.info(f"O item com ID {id_item} é mais recente que o item com ID {temp_negocios_monday[id_negocio]['id_monday']} para o negocio com ID {id_negocio}, então o item com ID {id_item} foi mantido como o item do Monday para esse negocio.")

        else:
            # Apenas salva um log, mantendo o negocio do monday já existente no dicionário temp, que é o mais recente
            logger.info(f"O item com ID {temp_negocios_monday[id_negocio]['id_monday']} é mais recente que o item com ID {id_item} para o negocio com ID {id_negocio}, então o item com ID {temp_negocios_monday[id_negocio]['id_monday']} foi mantido como o item do Monday para esse negocio.")

            # Adicionamos uma tag de duplicado para o item mais antigo, para facilitar a identificação e resolução dessa questão no Monday
            pendencias_item = item.get('pendencias_analise', [])
            if pendencias_item is not None and "Duplicado" in pendencias_item:
                logger.info(f"A pendência de 'Duplicado' já existe para o item com ID {id_item} no Monday, não será criada novamente.")
            else:
                criar_pendencia(id_item, "Duplicado") # Cria uma pendência de "Duplicado" para os itens que têm o mesmo ID de negocio, para facilitar a identificação e resolução dessa questão no Monday
                logger.info(f"A pendência de 'Duplicado' foi criada para o item com ID {id_item} no Monday")


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

# Contas
contas_monday = cliente_monday.get_items(
    board_id=IDS_BOARDS["CONTAS"],
    column_id="text_mkywmptw",
    value=[id_conta for id_conta in contas.keys()]
)

""" Formato do dicionário contas_monday:
{
    "id_monday"(str): {
        'nome': 'Housin 360',
        'tipo_de_conta': 'Imobiliária',
        'documento': '28.007.960/0001-00',
        'creci': '13180609',
        'id_conta': 'b88789f2-0c81-4f48-a776-77212365a29d'
    },
}

"""

# Troca as chaves dos dicionários para usar o ID da conta como chave, para facilitar a comparação
temp_contas_monday = {} # Cria um dicionário temporário para armazenar

for id_item, item in contas_monday.items():

    id_conta = item['id_conta']

    if id_conta in temp_contas_monday:

        logger.warning(f"ID de conta duplicado encontrado no Monday: {id_conta}. Há mais de um item no Monday com o mesmo ID de conta, o que pode causar problemas de comparação. ID do item 1: {temp_contas_monday[id_conta]['id_monday']}, ID do item 2: {id_item}. Verifique os dados no Monday para resolver essa duplicidade.")

    # Substitui a conta do monday sendo no dicionário temp pelo novo, mais recente
    temp_contas_monday[id_conta] = item
    temp_contas_monday[id_conta]['id_monday'] = id_item # Adiciona o ID do item do Monday como uma nova chave dentro do dicionário da conta, para facilitar o acesso posteriormente

# Substitui o dicionário original pelo temporário, que agora tem o ID da conta como chave
contas_monday = temp_contas_monday

""" Novo formato do dicionário contas_monday após troca de chaves:
{
    'id_conta'(str): {
        'id_monday': '10843682077',
        'nome': 'Housin 360',
        'tipo_de_conta': 'Imobiliária',
        'documento': '28.007.960/0001-00',
        'creci': '13180609'
    },
}
"""

# Com as contas carregadas do Monday, criamos no Monday as contas que ainda não existem,
# para depois usar os `id_monday` dessas contas como relacionamento nos negócios.
# A função atualiza `contas_monday` in-place com as contas recém-criadas, garantindo
# que o loop de negócios logo adiante encontre todas as referências.

logger.info(
    f"Criando contas faltantes no Monday "
    f"(board CONTAS={IDS_BOARDS['CONTAS']}, total de contas a processar: {len(contas)})..."
)
resumo_contas = criar_contas_faltantes_no_monday(
    contas=contas,
    contas_monday=contas_monday,
    cliente=cliente_monday,
    board_id=IDS_BOARDS["CONTAS"],
    grupos_por_tipo=GRUPOS_CONTAS_MONDAY,
)
logger.info(
    f"Criação de contas concluída. Criadas: {resumo_contas['criadas']}. "
    f"Já existentes: {resumo_contas['ja_existentes']}. "
    f"Sem id_conta: {resumo_contas['puladas_sem_id_conta']}. "
    f"Tipo desconhecido: {resumo_contas['tipo_desconhecido']}. "
    f"Falhas: {resumo_contas['falhas']}. "
    f"Por tipo: {resumo_contas['criadas_por_tipo']}."
)

# Cruzamentos

# TODO: Busca no Monday itens com o mesmo cliente na mesma unidade, para identificar possíveis negócios relacionados
#       ou duplicados, que podem inclusive serem cruzamentos caso o corretor for diferente
#       Agora temos que iterar pelos negócios do Otto e comparar com os negócios do Monday para
#       identificar quais negócios precisam ser criados ou atualizados no Monday

logger.info(
    f"Iniciando montagem dos dados de {len(negocios)} negócio(s) para envio ao Monday "
    f"(board NEGOCIOS={IDS_BOARDS['NEGOCIOS']})."
)

# Contadores de diagnóstico desta etapa. Útil para confirmar nos logs o que cada execução
# efetivamente preparou (antes de existir lógica de create/update, isso já permite comparar
# o que o Otto trouxe com o que o Monday recebeu).
resumo_negocios = {
    "total": 0,
    "ja_existe_no_monday": 0,
    "novos_no_monday": 0,
    "com_relacionamento_pendente": 0,
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
    #    + relacionamentos resolvidos via `contas_monday`.
    try:
        update_melnick = montar_dados_monday_do_negocio(
            id_negocio=id_negocio,
            dados_negocio=dados_negocio,
            contas_monday=contas_monday,
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
    nome_processo = "|".join(
        [
            dados_negocio.get("nome_empreendimento") or "Empreendimento sem nome",
            dados_negocio.get("nome_torre") or "Torre sem nome",
            str(dados_negocio.get("numero_unidade") or "Sem número da unidade"),
            dados_negocio.get("nome_cliente") or "Cliente sem nome",
        ]
    ).upper()

    # Aviso quando algum papel obrigatório ficou sem id_monday resolvido - isso ajuda
    # a detectar casos em que a conta chegou do Otto mas a criação no Monday falhou.
    papeis_presentes = [p for p in ("corretor", "imobiliaria", "gerente", "executivo", "vendedor") if dados_negocio.get(p)]
    papeis_mapeados = [p for p, chave in {
        "corretor": "id_corretor",
        "imobiliaria": "id_imobiliaria",
        "gerente": "id_gerente",
        "executivo": "id_executivo",
        "vendedor": "id_vendedor",
    }.items() if chave in update_melnick]
    if len(papeis_mapeados) < len(papeis_presentes):
        resumo_negocios["com_relacionamento_pendente"] += 1
        pendentes = set(papeis_presentes) - set(papeis_mapeados)
        logger.warning(
            f"Negócio {id_negocio}: relacionamento(s) pendente(s) no Monday para "
            f"papéis {sorted(pendentes)} (conta(s) presentes mas sem id_monday)."
        )

    # 4) Converte as chaves Melnick para IDs de coluna do Monday. Apenas campos com
    #    mapeamento cadastrado são mantidos; o resto (ex.: papéis sem id_monday) é
    #    automaticamente filtrado.
    update_monday = map_dict_keys(
        fonte="monday",
        id_mapeamento=str(IDS_BOARDS["NEGOCIOS"]),
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
    f"Com relacionamento pendente: {resumo_negocios['com_relacionamento_pendente']}. "
    f"Falhas de montagem: {resumo_negocios['falhas_montagem']}."
)

#### SINCRONIZAÇÃO COM O MONDAY (Fase C) ####
# Cria/atualiza os itens de negócio no board NEGOCIOS com base em `negocios_para_sincronizar`,
# aplicando detecção de cruzamento e diff por coluna para minimizar chamadas de API.

logger.info(
    f"Iniciando sincronização de {len(negocios_para_sincronizar)} negócio(s) com o Monday "
    f"(board NEGOCIOS={IDS_BOARDS['NEGOCIOS']})."
)
resumo_sync = sincronizar_negocios_com_monday(
    negocios_para_sincronizar=negocios_para_sincronizar,
    negocios_monday=negocios_monday,
    negocios=negocios,
    cliente=cliente_monday,
    board_id=IDS_BOARDS["NEGOCIOS"],
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
        f"Cache `negocios_monday.json` salvo após sincronização ({len(negocios_monday)} itens)."
    )
except Exception as exc:
    logger.error(
        f"Falha ao salvar o cache `negocios_monday.json` ({arquivo_negocios_monday}): "
        f"{exc}. As próximas execuções podem reprocessar itens recém-criados."
    )


#### FINALIZAÇÃO ####

# Grava a data/hora (UTC-3) desta execução como "última atualização" APENAS após o fluxo
# ter chegado até aqui sem exceção. Assim, em caso de falha no meio do script, a janela
# do Otto na próxima execução continua cobrindo o período que ainda não foi processado
# (idempotência: melhor reprocessar do que perder atualizações).
try:
    with open(arquivo_hora_atualizacao, "w", encoding="utf-8") as f:
        f.write(hora_atual_local.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(
        f"Última atualização salva em {arquivo_hora_atualizacao}: "
        f"{hora_atual_local.strftime('%Y-%m-%d %H:%M:%S')} (UTC-3)."
    )
except Exception as exc:
    logger.error(
        f"Falha ao gravar o arquivo de última atualização ({arquivo_hora_atualizacao}): "
        f"{exc}. A próxima execução pode reprocessar a mesma janela."
    )

logger.info("AutoBackoffice concluído.")
