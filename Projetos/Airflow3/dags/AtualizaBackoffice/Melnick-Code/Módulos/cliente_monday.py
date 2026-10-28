# CLiente para interagir com a API do Monday.com
# %%
import os
import requests
import time
import json
from datetime import date, timedelta, datetime
from typing import Any, Dict
from Módulos import mapeamento_dados
#import mapeamento_dados

__all__ = ["ClienteMonday", "parse_monday_data"]


# Tamanho de página usado em `items_page` / `items_page_by_column_values`. O Monday
# aceita até 500 por página; valores maiores reduzem o número de iterações e com isso
# a chance de um `cursor` expirar entre páginas (cursor tem TTL curto — ~60s).
MONDAY_PAGE_SIZE = 500

# Máximo de tentativas ao encontrar `CursorException` durante a paginação. Cada
# tentativa REINICIA a paginação do zero (Monday não permite "renovar" cursor).
MONDAY_CURSOR_MAX_RETRIES = 2

#--------------------------------
# LOGGER
import logging
logger = logging.getLogger("Cliente Monday")
#--------------------------------

class ClienteMonday:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.monday.com/v2"

    def _headers(self):
        # Documentação: token pessoal sem prefixo "Bearer"; OAuth exige "Bearer ".
        # API-Version: ver https://developer.monday.com/api-reference/docs/getting-started
        h: Dict[str, str] = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }
        # API-Version opcional: só envia se a env var MONDAY_API_VERSION estiver setada.
        # Deixar o servidor escolher a versão padrão evita mudar o formato de resposta
        # silenciosamente (ex.: errors como lista de strings em vez de dicts).
        ver = (os.getenv("MONDAY_API_VERSION") or "").strip()
        if ver:
            h["API-Version"] = ver
        return h

    def run_query(self, query: str, variables: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Executa uma query GraphQL na API do Monday.com.
        Args:
            query (str): A query GraphQL a ser executada.
            variables (Dict[str, Any], optional): Variáveis para a query. Padrão é um dicionário vazio.
        Returns:
            Dict[str, Any]: A resposta da API em formato JSON.
        Raises:
            Exception: Se a requisição falhar ou a resposta não puder ser convertida para JSON.
        """
        # Monta o payload da requisição
        payload: Dict[str, Any] = {"query": query}
        if variables != {}: # Apenas adiciona variáveis se existirem
            payload["variables"] = variables
        
        # Faz a requisição a API do Monday, com tratamento de erros e várias tentativas
        retries: int = 0
        max_retries: int = 3
        # Inicializa um dicionário vazio para a resposta
        response_json: Dict[str, Any] = {}
        logger.info("Enviando requisição para o Monday.com...")

        while retries < max_retries:
            try:
                logger.debug(f"Tentativa {retries + 1} de {max_retries}...")
                response: requests.Response = requests.post(self.base_url, json=payload, headers=self._headers(), timeout=30)
                logger.debug(f"Resposta recebida: {response.status_code} - {response.text}")
            
            # Lida com erros da própria requisição
            except requests.RequestException as e:
                logger.warning(f"Erro na requisição: {e}. Tentando novamente...")
                retries += 1
                time.sleep(5 * retries)  # Espera alguns segundos antes de tentar novamente
                continue # Tenta novamente em caso de erro de requisição
            except Exception as e:
                logger.critical(f"Erro inesperado na requisição: {e}")
                raise Exception(f"Erro inesperado na requisição: {e}")
            
            # Caso o status code da requisição seja 500, tenta novamente
            if response.status_code == 500: # Erro 500 do servidor, interno e não culpa do usuário, tenta de novo
                logger.warning("Erro 500 do servidor. Tentando novamente...")
                retries += 1
                time.sleep(5 * retries)  # Espera alguns segundos antes de tentar novamente
                continue  # Tenta novamente em caso de erro 500

            # Caso o status code seja diferente de 500 tentamos converter a resposta para JSON
            # Converte a resposta para JSON
            try:
                response_json: Dict[str, Any] = response.json()
            except:
                raise Exception("Erro ao converter a resposta para JSON. Resposta bruta: " + response.text)
            
            # Caso a conversão para JSON tenha sido bem-sucedida, lida com os erros específicos da API
            if response.status_code == 423:
                logger.warning("Recurso bloqueado por edição simultânea. Tentando novamente...")
                retries += 1
                time.sleep(5) # Espera alguns segundos antes de tentar novamente
                continue  # Tenta novamente em caso de recurso bloqueado

            elif response.status_code == 429:
                logger.warning("Limite de requisições atingido. Tentando novamente...")
                retries += 1
                errs_429 = response_json.get("errors") or []
                first_err = errs_429[0] if errs_429 else None
                if isinstance(first_err, dict) and "extensions" in first_err:
                    retry_in_seconds = first_err["extensions"].get("retry_in_seconds", 58) + 2
                else:
                    retry_in_seconds = 60
                time.sleep(retry_in_seconds)  # Espera o tempo sugerido antes de tentar novamente
                continue  # Tenta novamente em caso de limite de requisições

            if "errors" in response_json:
                for error in response_json["errors"]: # Itera sobre os erros e loga cada um
                    if isinstance(error, str):
                        error_message = error
                        error_code = "Código desconhecido"
                    else:
                        error_message = error.get("message", "Erro desconhecido")
                        error_code = error.get("extensions", {}).get("code", "Código desconhecido")
                    logger.error(f"Erro na resposta da API: {error_message} (Código: {error_code})")
                    logger.error(
                        f"Detalhes do erro: {error}. Resposta: {response.text}. "
                        f"Variáveis da requisição: {variables}"
                    )
                    logger.error(f"Resposta da API: {response_json}")
                    logger.error(f"Payload da requisição: {payload}")
                raise Exception(f"Erros na resposta da API: {response_json['errors']}")
            
            break  # Sai do loop se a requisição for bem-sucedida
        
        if retries >= max_retries:
            raise Exception("Número máximo de tentativas atingido. A requisição falhou.")
        
        return response_json

    def _coletar_items_paginados(
        self,
        query_inicial: str,
        query_paginacao: str,
        variables_base: Dict[str, Any],
    ) -> list:
        """
        Executa uma query inicial (com ou sem filtro) e percorre todas as páginas via
        `cursor`. Isolado em helper para permitir que `get_items` recomece do zero
        quando o Monday retorna `CursorException` (cursor não pode ser "renovado"; a
        única saída é refazer a query inteira).

        Args:
            query_inicial: Query GraphQL usada na PRIMEIRA chamada (pode incluir filtro).
            query_paginacao: Query GraphQL usada nas chamadas SUBSEQUENTES (sempre sem
                filtro, pois Monday ignora filtro quando há cursor).
            variables_base: Variáveis para a primeira chamada. NÃO é mutado — uma cópia
                é feita internamente para permitir reexecução.

        Returns:
            Lista agregada de itens de todas as páginas.
        """
        variables = dict(variables_base)
        limit = variables.get("limit", MONDAY_PAGE_SIZE)
        query_result = self.run_query(query_inicial, variables)
        result_data = query_result.get("data")
        if not result_data:
            raise Exception("A resposta da API não contém dados.")

        if "boards" in result_data:
            items = result_data["boards"][0]["items_page"]["items"]
            cursor = result_data["boards"][0]["items_page"]["cursor"]
        elif "items_page_by_column_values" in result_data:
            items = result_data["items_page_by_column_values"]["items"]
            cursor = result_data["items_page_by_column_values"]["cursor"]
        else:
            raise Exception("Formato de resposta inesperado da API.")
        logger.debug(f"cursor: {cursor}")

        # Heurística defensiva: em alguns cenários (especialmente após deleções em
        # massa), o Monday devolve um cursor NA PRIMEIRA PÁGINA mesmo quando não há
        # mais itens a paginar — e esse cursor vem já inválido, disparando
        # `CursorException`. Se a primeira página trouxe MENOS itens que `limit`, é
        # matematicamente impossível existir próxima página, então ignoramos o cursor.
        if cursor is not None and len(items) < limit:
            logger.debug(
                f"Cursor retornado mas página tem {len(items)} < limit {limit} itens. "
                "Ignorando cursor (não há próxima página possível)."
            )
            cursor = None

        # A partir da segunda chamada, Monday exige a query sem filtro/rules; limpamos
        # os campos incompatíveis de `variables` para evitar ambiguidades.
        while cursor is not None:
            logger.debug("Buscando próxima página de resultados...")
            variables.pop("filter", None)
            variables.pop("rules", None)
            variables["cursor"] = cursor

            query_result = self.run_query(query_paginacao, variables)
            result_data = query_result.get("data")
            if not result_data:
                raise Exception("A resposta da API não contém dados na paginação.")

            next_items = result_data["boards"][0]["items_page"]["items"]
            items.extend(next_items)

            cursor = result_data["boards"][0]["items_page"]["cursor"]
            logger.debug(f"Novo cursor: {cursor}")

            # Mesma heurística para páginas subsequentes: se retornou menos que limit,
            # não há próxima página (evita `CursorException` na última página "vazia").
            if cursor is not None and len(next_items) < limit:
                logger.debug(
                    f"Última página retornou {len(next_items)} < limit {limit}. "
                    "Ignorando cursor subsequente."
                )
                cursor = None

        return items

    def get_items(
            self,
            board_id: int,
            column_id: str | None = None,
            value: str | list = [],
            filter_dict: Dict[str, Any] | None = None,
            parse_data = True,
            column_mapping = True
            ) -> Dict[str, Any]:
        """
        Recupera um item de um quadro do Monday.com com base no valor de uma coluna específica ou em um filtro personalizado.
        Quando filtrando com um dicionário os filtros em mais de uma coluna são combinados com E lógico e valores em listas são combinados com OU lógico.
        Args:
            board_id (int): ID do quadro onde o item será buscado.
            column_id (str, optional): ID da coluna a ser usada para filtrar o item. Padrão é None.
            value (str, optional): Valor da coluna a ser usado para filtrar o item. Padrão é None.
            filter_dict (Dict[str, Any], optional): Dicionário de filtro personalizado. Padrão é None.
            parse_data (bool, optional): Se True, processa os dados retornados para tipos apropriados. Padrão é True.
            column_mapping (bool, optional): Se True, mapeia os IDs das colunas para seus nomes. Padrão é True.
        Returns:
            Dict[str, Any] | None: O item encontrado ou None se nenhum item corresponder
        Raises:
            ValueError: Se nenhum critério de filtro for fornecido.
        """
        if column_id is None and value == [] and filter_dict is None:
            filter_dict = {}
        elif column_id is not None and value is not None and filter_dict is None:
            # Cria o filtro básico
            filter_dict = {column_id: value}
        elif filter_dict is not None and column_id is None and value == []:
            # Usa o filtro personalizado fornecido
            pass
        elif (column_id is None or value == []) and filter_dict is None:
            raise ValueError("É necessário fornecer ambos column_id e value para o filtro básico.")
        else:
            raise ValueError("Forneça apenas column_id e value ou um filter_dict personalizado, não ambos.")
        
        # Monta a lista de filtros
        filter = [{"column_id": k, "column_values": v} for k, v in filter_dict.items()]
        
        variables = {
            "board_id": board_id,
            "limit": MONDAY_PAGE_SIZE,
            "filter": filter
        }
        
        # Query com o filtro não precisa passar o argumento cursor, ele será retornado automaticamente
        query_with_filter = """
            query FilterItems ($board_id: ID!, $filter: [ItemsPageByColumnValuesQuery!], $limit: Int) {
                items_page_by_column_values (board_id: $board_id, columns: $filter, limit: $limit)
                {
                    cursor
                    items {
                    id
                    name
                    updated_at
                    state
                    subitems {
                    column_values {
                        column {
                        id
                        type
                        }
                        text
                        value
                        ... on BoardRelationValue {
                        linked_items {
                        id
                        name
                        }
                        }
                    }
                    }
                    column_values {
                        column {
                        id
                        type
                        }
                        text
                        value
                        ... on BoardRelationValue {
                        linked_items {
                        id
                        name
                        }
                        }
                    }
                    }
                }
                }
        """
        # Query sem o filtro pode passar o argumento cursor como None na primeira chamada para retornar todos os items ou
        # pode ser usado para paginação, se pasar o cursor retornado na resposta anterior
        query_without_filter = """
            query FilterItems($board_id: [ID!], $limit: Int, $cursor: String) {
                boards(ids: $board_id) {
                    items_page(limit: $limit, cursor: $cursor) {
                    cursor
                    items {
                        id
                        name
                        updated_at
                        state
                        subitems {
                            column_values {
                            column {
                            id
                            type
                            }
                            text
                            value
                            ... on BoardRelationValue {
                            linked_items {
                            id
                            name
                            }
                            }
                        }
                        }
                        column_values {
                        column {
                            id
                            type
                        }
                        text
                        value
                        ... on BoardRelationValue {
                            linked_items {
                            id
                            name
                            }
                        }
                        }
                    }
                    }
                }
            }
        """
        # Escolhe a query correta com base na presença do filtro
        if filter_dict != {}:
            logger.debug("Usando filtro personalizado para buscar itens...")
            query = query_with_filter
        else:
            logger.debug("Buscando itens sem filtro personalizado...")
            variables.pop("filter")  # Remove o filtro das variáveis
            query = query_without_filter

        # Paginação com retry em caso de `CursorException`. Como o Monday não permite
        # renovar um cursor expirado, a única estratégia de recuperação é reiniciar a
        # query inteira do zero e iterar novamente. Em boards grandes isso é caro, mas
        # salva a execução e é raro graças ao `MONDAY_PAGE_SIZE` alto (500).
        tentativas = 0
        while True:
            try:
                items = self._coletar_items_paginados(
                    query_inicial=query,
                    query_paginacao=query_without_filter,
                    variables_base=dict(variables),  # cópia: cada tentativa precisa estado limpo
                )
                break
            except Exception as exc:
                mensagem = str(exc)
                eh_cursor_expirado = (
                    "CursorException" in mensagem or "CursorExpiredError" in mensagem
                )
                if eh_cursor_expirado and tentativas < MONDAY_CURSOR_MAX_RETRIES:
                    tentativas += 1
                    logger.warning(
                        f"Cursor de paginação expirou. Reiniciando a query do zero "
                        f"(tentativa {tentativas}/{MONDAY_CURSOR_MAX_RETRIES})."
                    )
                    continue
                raise
        
        if not items:
            logger.info("Nenhum item encontrado com os critérios fornecidos.")
            return {}

        # Se solicitado, processa os dados dos itens
        if parse_data:
            logger.debug("Processando os dados dos itens retornados...")
            processed_items = {}
            for item in items:
                parsed_item = parse_monday_data(item)
                logger.debug(f"Item processado: {parsed_item}")
                parsed_item_id = parsed_item.pop("id", None)
                if parsed_item_id is not None:
                    processed_items[parsed_item_id] = parsed_item                
            items = processed_items

        if parse_data and column_mapping:
            logger.debug("Mapeando os nomes das colunas dos itens retornados...")
            # Busca o mapeamento correto para o board_id
            mapped_items = {}
            for item_id, item_data in items.items():
                logger.debug(f"Mapeando item ID {item_id}: {item_data}")
                mapped_item = mapeamento_dados.map_dict_keys("monday", str(board_id), item_data)
                logger.debug(f"Item mapeado: {mapped_item}")
                mapped_items[item_id] = mapped_item
            items = mapped_items
            
        return items

    def get_items_updated_today_yesterday(
            self,
            board_id: int,
            parse_data = True,
            column_mapping = True,
            updater_id: str | None = None,
            exclude_updater: bool = False
            ) -> Dict[str, Any]:
        """
        Busca itens atualizados hoje e ontem, usando a coluna Last Updated.
        Implementa o filtro via items_page.query_params.rules.
        Se updater_id for informado, filtra por alteraÃ§Ãµes feitas por esse usuÃ¡rio.
        Se exclude_updater=True, retorna alteraÃ§Ãµes feitas por qualquer usuÃ¡rio EXCETO o informado.
        """
        rules = [
            {
                "column_id": "__last_updated__",
                "compare_value": ["TODAY", "YESTERDAY"],
                "operator": "any_of",
                "compare_attribute": "UPDATED_AT"
            }
        ]

        if updater_id:
            rules.append({
                "column_id": "__last_updated__",
                "compare_value": [f"person-{updater_id}"],
                "operator": "not_any_of" if exclude_updater else "any_of",
                "compare_attribute": "UPDATED_BY"
            })

        query_with_rules = """
            query GetItemsUpdatedTodayYesterday($board_id: [ID!], $limit: Int, $rules: [ItemsQueryRule!]) {
                boards(ids: $board_id) {
                    items_page(
                        limit: $limit,
                        query_params: {
                            rules: $rules
                        }
                    ) {
                        cursor
                        items {
                            id
                            name
                            state
                            subitems {
                                column_values {
                                    column {
                                        id
                                        type
                                    }
                                    text
                                    value
                                    ... on BoardRelationValue {
                                        linked_items {
                                            id
                                            name
                                        }
                                    }
                                }
                            }
                            column_values {
                                column {
                                    id
                                    type
                                }
                                text
                                value
                                ... on BoardRelationValue {
                                    linked_items {
                                        id
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """
        query_with_cursor_only = """
            query GetItemsUpdatedTodayYesterdayCursor($board_id: [ID!], $limit: Int, $cursor: String) {
                boards(ids: $board_id) {
                    items_page(
                        limit: $limit,
                        cursor: $cursor
                    ) {
                        cursor
                        items {
                            id
                            name
                            state
                            subitems {
                                column_values {
                                    column {
                                        id
                                        type
                                    }
                                    text
                                    value
                                    ... on BoardRelationValue {
                                        linked_items {
                                            id
                                            name
                                        }
                                    }
                                }
                            }
                            column_values {
                                column {
                                    id
                                    type
                                }
                                text
                                value
                                ... on BoardRelationValue {
                                    linked_items {
                                        id
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """

        variables = {
            "board_id": board_id,
            "limit": MONDAY_PAGE_SIZE,
            "rules": rules
        }

        # Paginação com retry em caso de `CursorException`. Mesma estratégia de
        # `get_items`: reiniciar a query inteira do zero quando o cursor expira
        # (Monday não permite renová-lo).
        tentativas = 0
        while True:
            try:
                items = self._coletar_items_paginados(
                    query_inicial=query_with_rules,
                    query_paginacao=query_with_cursor_only,
                    variables_base=dict(variables),
                )
                break
            except Exception as exc:
                mensagem = str(exc)
                eh_cursor_expirado = (
                    "CursorException" in mensagem or "CursorExpiredError" in mensagem
                )
                if eh_cursor_expirado and tentativas < MONDAY_CURSOR_MAX_RETRIES:
                    tentativas += 1
                    logger.warning(
                        f"Cursor de paginação expirou em `get_items_updated_today_yesterday`. "
                        f"Reiniciando a query do zero "
                        f"(tentativa {tentativas}/{MONDAY_CURSOR_MAX_RETRIES})."
                    )
                    continue
                raise

        if not items:
            logger.info("Nenhum item encontrado com atualizaÃ§Ãµes hoje ou ontem.")
            return {}

        if parse_data:
            processed_items = {}
            for item in items:
                parsed_item = parse_monday_data(item)
                parsed_item_id = parsed_item.pop("id", None)
                if parsed_item_id is not None:
                    processed_items[parsed_item_id] = parsed_item
            items = processed_items

        if parse_data and column_mapping:
            mapped_items = {}
            for item_id, item_data in items.items():
                mapped_item = mapeamento_dados.map_dict_keys("monday", str(board_id), item_data)
                mapped_items[item_id] = mapped_item
            items = mapped_items

        return items
    
    def create_item(self, board_id: int,  item_name: str, group_id: str | None = None, column_values: Dict[str, Any] = {}, create_labels_if_missing: bool = False) -> str:
        """
        Cria um novo item em um quadro do Monday.com.
        Args:
            board_id (int): ID do quadro onde o item será criado.
            item_name (str): Nome do novo item.
            group_id (str | None, optional): ID do grupo onde o item será criado. Padrão é None (grupo padrão).
            column_values (Dict[str, Any], optional): Valores das colunas do item. Padrão é um dicionário vazio.
            create_labels_if_missing (bool, optional): Se True, cria labels automaticamente se não existirem. Padrão é False.
        Returns:
            str: ID do item criado.
        Raises:
            Exception: Se a criação do item falhar.
        """
        # Confirma que o nome do item é válido
        if item_name.strip() == "" or item_name is None:
            raise ValueError("O nome do item não pode ser vazio.")
        
        if not isinstance(column_values, dict):
            raise ValueError("Os valores das colunas devem ser fornecidos em um dicionário.")
        
        if column_values == {}:
            mutation = """
                mutation CreateItem($board_id: ID!, $item_name: String!""" + (", $group_id: String!" if group_id else "") + """) {
                    create_item(
                        board_id: $board_id,
                        item_name: $item_name""" + ("""
                        group_id: $group_id""" if group_id else "") + """
                    ) {
                        id
                    }
                }
            """
            variables = {
                "board_id": board_id,
                "item_name": item_name
            }
            if group_id:
                variables["group_id"] = group_id
        else:
            try:
                column_values_string = json.dumps(column_values) # Converte o dicionário para string JSON
            except Exception as e:
                raise ValueError(f"Erro ao converter os valores das colunas para JSON: {e}")
            
            mutation = """
                mutation CreateItem($board_id: ID!, $item_name: String!, $column_values: JSON!""" + (", $group_id: String!" if group_id else "") + """) {
                    create_item(
                        board_id: $board_id,
                        item_name: $item_name,
                        column_values: $column_values,
                        create_labels_if_missing: """ + str(create_labels_if_missing).lower() + ("""
                        group_id: $group_id""" if group_id else "") + """
                    ) {
                        id
                    }
                }
            """
            variables = {
                "board_id": board_id,
                "item_name": item_name,
                "column_values": column_values_string
            }
            if group_id:
                variables["group_id"] = group_id
        
        result = self.run_query(mutation, variables)
        
        item_id = result["data"]["create_item"]["id"]
        logger.info(f"Item criado com sucesso. ID: {item_id}")
        return item_id
    
    def update_item(self, board_id: int, item_id: str, column_values: Dict[str, Any], create_labels_if_missing: bool = False) -> str:
        """
        Atualiza os valores das colunas de um item em um quadro do Monday.com.
        Args:
            board_id (int): ID do quadro onde o item está localizado.
            item_id (str): ID do item a ser atualizado.
            column_values (Dict[str, Any]): Dicionário com os IDs das colunas e seus novos valores.
        Returns:
            str: ID do item atualizado.
        """
        # Garante que o ID do item é válido
        if item_id.strip() == "" or item_id is None:
            raise ValueError("O ID do item não pode ser vazio.")
        
        # Garante que o column_values é um dicionário válido
        if not isinstance(column_values, dict) or not column_values or column_values == {}:
            raise ValueError("Os valores das colunas devem ser fornecidos em um dicionário não vazio.")
        
        try:
            column_values_string = json.dumps(column_values) # Converte o dicionário para string JSON
        except Exception as e:
            raise ValueError(f"Erro ao converter os valores das colunas para JSON: {e}")
        
        query = """
            mutation UpdateColumnsValue($board_id: ID!, $item_id: ID, $column_values: JSON!) {
            change_multiple_column_values(
                board_id: $board_id
                item_id: $item_id
                column_values: $column_values
                create_labels_if_missing: """ + str(create_labels_if_missing).lower() + """
            ) {
                id
            }
            }
        """
        variables = {
            "board_id": board_id,
            "item_id": item_id,
            "column_values": column_values_string
        }

        response = self.run_query(query=query, variables=variables)
        updated_item_id = response["data"]["change_multiple_column_values"]["id"]
        logger.info(f"Item atualizado com sucesso. ID: {updated_item_id}")
        return updated_item_id

    def delete_item(self, item_id: str) -> str:
        """
        Deleta (permanentemente) um item no Monday.com.

        Args:
            item_id (str): ID do item a ser deletado.

        Returns:
            str: ID do item deletado (confirmação vinda da API).

        Raises:
            ValueError: Se `item_id` for vazio ou None.
            Exception: Se a mutação falhar na API (ex.: item inexistente, falta de
                permissão, rate-limit). O caller é responsável por tratar/ignorar.
        """
        if item_id is None or str(item_id).strip() == "":
            raise ValueError("O ID do item não pode ser vazio.")

        query = """
            mutation DeleteItem($item_id: ID!) {
                delete_item(item_id: $item_id) {
                    id
                }
            }
        """
        variables = {"item_id": str(item_id)}
        response = self.run_query(query=query, variables=variables)
        deleted_item_id = response["data"]["delete_item"]["id"]
        logger.info(f"Item deletado com sucesso no Monday. ID: {deleted_item_id}")
        return deleted_item_id


def parse_monday_data(monday_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processa os dados de um item do Monday.com e retorna um dicionário com os valores tratados.
    Args:
        monday_item (Dict[str, Any]): O item do Monday.com a ser processado.
    Returns:
        Dict[str, Any]: Dicionário com o id da coluna como chave e o valor tratado como value.
    """
    parsed_item: Dict[str, Any] = {}

    item_id = monday_item.get("id")
    if not item_id:
        raise ValueError("O item do Monday não contém um ID válido.")
    
    parsed_item["id"] = item_id
    parsed_item["updated_at"] = monday_item.get("updated_at")  # Data de atualização do item
    # Data vem no formato "2026-02-27T20:57:55Z". Transformar para objeto datetime.datetime
    if parsed_item["updated_at"]:
        try:
            parsed_item["updated_at"] = datetime.strptime(parsed_item["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass  # Se a data não estiver no formato esperado, mantém como string
    parsed_item["name"] = monday_item.get("name")  # Nome do item
    parsed_item["state"] = monday_item.get("state")  # Estado do item (ativo, arquivado, etc.)

    # Processa os valores das colunas, com base no tipo de coluna
    column_values = monday_item.get("column_values", [])
    for column in column_values:
        column_info = column.get("column", {})
        column_id = column_info.get("id")
        column_type = column_info.get("type")
        text_value = column.get("text")
        raw_value = column.get("value")
        subitems = monday_item.get("subitems", [])
        # lista de subitems. Esta função recebe 1 item por vez.
        # Dividir essa função

        ######################################

        if not column_id:
            continue  # Pula colunas sem ID

        # Trata cada tipo de coluna
        if column_type == "text":
            # Tipo texto: valor vem como string JSON, ex: '"Valor"'
            if raw_value:
                try:
                    parsed_item[column_id] = json.loads(raw_value)
                except json.JSONDecodeError:
                    parsed_item[column_id] = text_value
            else:
                parsed_item[column_id] = None

        elif column_type == "numbers":
            # Tipo numérico: valor vem como string JSON, ex: '"1302"'
            if raw_value:
                try:
                    str_value = json.loads(raw_value)
                    # Tenta converter para float ou int
                    parsed_item[column_id] = float(str_value) if '.' in str(str_value) else int(str_value)
                except (json.JSONDecodeError, ValueError):
                    parsed_item[column_id] = text_value
            else:
                parsed_item[column_id] = None

        elif column_type == "status":
            # Tipo status: retorna o texto do status
            parsed_item[column_id] = text_value if text_value else None

        elif column_type == "date":
            # Tipo data: valor vem como JSON com date e time
            if raw_value:
                try:
                    date_obj = json.loads(raw_value)
                    date_str = date_obj.get("date")
                    time_str = date_obj.get("time")
                    if date_str and time_str:
                        parsed_item[column_id] = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                    elif date_str:
                        parsed_item[column_id] = datetime.strptime(date_str, "%Y-%m-%d")
                    else:
                        parsed_item[column_id] = None
                except json.JSONDecodeError:
                    parsed_item[column_id] = text_value
            else:
                parsed_item[column_id] = None

        elif column_type == "link":
            # Tipo link: valor vem como JSON com url e text
            if raw_value:
                try:
                    link_obj = json.loads(raw_value)
                    parsed_item[column_id] = {
                        "url": link_obj.get("url"),
                        "text": link_obj.get("text")
                    }
                except json.JSONDecodeError:
                    parsed_item[column_id] = text_value
            else:
                parsed_item[column_id] = None

        elif column_type == "email":
            # Tipo email: retorna o texto do email
            parsed_item[column_id] = text_value if text_value else None

        elif column_type == "people":
            # Tipo pessoas: retorna o texto (nomes das pessoas)
            parsed_item[column_id] = text_value if text_value else None

        elif column_type == "item_id":
            # Tipo item_id: valor vem como JSON com item_id
            if raw_value:
                try:
                    item_id_obj = json.loads(raw_value)
                    parsed_item[column_id] = item_id_obj.get("item_id")
                except json.JSONDecodeError:
                    parsed_item[column_id] = text_value
            else:
                parsed_item[column_id] = None

        elif column_type == "board_relation":
            # Tipo relação entre quadros: retorna lista de itens relacionados
            linked_items = column.get("linked_items", [])
            if linked_items:
                parsed_item[column_id] = [
                    {"id": item.get("id"), "name": item.get("name")}
                    for item in linked_items
                ]
            else:
                parsed_item[column_id] = []

        elif column_type == "last_updated":
            # Tipo última atualização: valor vem como JSON com updated_at e updater_id
            if raw_value:
                try:
                    updated_obj = json.loads(raw_value)
                    parsed_item[column_id] = {
                        "updated_at": datetime.strptime(updated_obj.get("updated_at"), "%Y-%m-%dT%H:%M:%SZ"), # Formato "2026-02-27T20:57:55Z"
                        "updater_id": updated_obj.get("updater_id")
                    }
                except json.JSONDecodeError:
                    parsed_item[column_id] = text_value
            else:
                parsed_item[column_id] = None

        elif column_type == "dropdown":
            # Tipo dropdown: retorna o texto selecionado
            text_value = text_value if text_value else None
            if text_value:
                text_values_list = text_value.split(", ")  # Supondo que múltiplas opções sejam separadas por vírgula
                parsed_item[column_id] = text_values_list
            else:
                parsed_item[column_id] = None

        elif column_type == "tags":
            # Tipo tags: retorna o texto das tags
            parsed_item[column_id] = text_value if text_value else None

        elif column_type == "file":
            # Tipo arquivo: retorna o texto (nome do arquivo)
            parsed_item[column_id] = text_value if text_value else None

        elif column_type == "subtasks":
            # Tipo subtarefas: geralmente não tem valor processável
            parsed_item[column_id] = None

        else:
            # Tipo desconhecido: usa o text como fallback
            parsed_item[column_id] = text_value

    return parsed_item

def main_1():
    # Procura o caminho para a pasta raiz do projeto
    import os
    repository_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    print(f"Caminho da pasta raiz do repositório: {repository_root}")
    project_root = os.path.abspath(os.path.join(repository_root, '..'))
    print(f"Caminho da pasta raiz do projeto: {project_root}")

    # Confirma se o .env existe na pasta raiz
    env_path = os.path.join(project_root, '.env')
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"O arquivo .env não foi encontrado na pasta raiz do projeto: {project_root}. Garanta que o arquivo exista para carregar as variáveis de ambiente necessárias.")
    # Carrega o arquivo .env localizado na pasta raiz do projeto
    from dotenv import load_dotenv
    load_dotenv(env_path) # Carrega o arquivo .env

    # Cliente do Monday
    # Confirma que a chave de API foi encontrada no .env
    api_key = os.getenv("MONDAY_API_KEY")
    if not api_key:
        raise ValueError("A variável de ambiente MONDAY_API_KEY do Monday.com não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
    
    cliente_monday = ClienteMonday(api_key=api_key)

    # Testes Monday
    board_id = 18392689606 # Exemplo de board ID

    broker_id_one = "02e10325-6bd1-4d45-896a-a1db0ab74352"
    broker_id_two = "06123769-012c-4769-b571-48359ec4aa86"

    teste = cliente_monday.get_items(
        board_id=18392689606,
        filter_dict={
            "id_corretor_teste": "02e10325-6bd1-4d45-896a-a1db0ab74352"
        }
    )

    id = cliente_monday.create_item(
        board_id=18392689606,
        item_name="William Artur Santos Werberick"
    )

    cliente_monday.update_item(
        board_id=18392689606,
        item_id=id,
        column_values={
            "id_corretor_teste": "e935ba00-284f-4277-b197-aee470196785"
        },
        create_labels_if_missing=True
    )

    cliente_monday.get_items(
        board_id=18392682833,
        column_id="pulse_id_mkv98k75",
        value="10813540125",
        column_mapping=False
    )

    cliente_monday.create_item(
        board_id=18392689606,
        item_name="Davi Augusto Biazzuz",
        column_values={
            "id_corretor_teste": "534c4fc2-dc54-4624-9444-0707cf42ae6c"
        },
        create_labels_if_missing=True
    )

    # https://melnickagencia.monday.com/boards/18392689606/pulses/10813683889

    return teste

def main():
    # Procura o caminho para a pasta raiz do projeto
    import os
    repository_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    print(f"Caminho da pasta raiz do repositório: {repository_root}")
    project_root = os.path.abspath(os.path.join(repository_root, '..'))
    print(f"Caminho da pasta raiz do projeto: {project_root}")

    # Confirma se o .env existe na pasta raiz
    env_path = os.path.join(project_root, '.env')
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"O arquivo .env não foi encontrado na pasta raiz do projeto: {project_root}. Garanta que o arquivo exista para carregar as variáveis de ambiente necessárias.")
    # Carrega o arquivo .env localizado na pasta raiz do projeto
    from dotenv import load_dotenv
    load_dotenv(env_path) # Carrega o arquivo .env

    # Cliente do Monday
    # Confirma que a chave de API foi encontrada no .env
    api_key = os.getenv("MONDAY_API_KEY")
    if not api_key:
        raise ValueError("A variável de ambiente MONDAY_API_KEY do Monday.com não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
    
    cliente_monday = ClienteMonday(api_key=api_key)

    board_id = 18392682833
    item_id = 11058759195

    get_item_query = """
        query {
            items (ids: 11103200022) {
                name
                state
                id
                board {
                id
                }
                group{
                id}
                }
        }
    """
    #item = cliente_monday.run_query(get_item_query)


    item = cliente_monday.get_items(
        board_id=board_id,
        column_id="pulse_id_mkv98k75",
        value="11058759195",
        parse_data=False,
        column_mapping=False
    )

    print(item)
    return item
    archive_item_query = """
        mutation {
            archive_item(
                item_id: 11103200022
                ) {
                id
            }
        }
    """

    #cliente_monday.run_query(archive_item_query)

    unarchive_item_query = """
        mutation {
            archive_item (item_id: 11103200022, state: active) {
                id
                state
            }
        }
    """

    #cliente_monday.run_query(unarchive_item_query)

    move_item_to_group_query = """
        mutation {
            move_item_to_group (item_id: 11103200022, group_id: "topics") {
                id
                group {
                    id
                    title
                }
            }
        }
    """
    #cliente_monday.run_query(move_item_to_group_query)

    duplicate_item_query = """
        mutation {
            duplicate_item (board_id: 18392682833, item_id: 11103200022, with_updates: true) {
                id
            }
        }
    """
    #cliente_monday.run_query(duplicate_item_query)

    move_item_to_board_query = """
        mutation {
            move_item_to_board (item_id: 11103200022, board_id: 18392689606, group_id: "topics") {
                id
            }
        }
    """
    #cliente_monday.run_query(move_item_to_board_query)

    delete_item_query = """
        mutation {
            delete_item (item_id: 11103200022) {
                id
            }
        }
    """

    #cliente_monday.run_query(delete_item_query)

    search_archive_query = """
    {
    items_page_by_column_values(state: archived, board_id: 18392689606, column_id:"pulse_id_mkv98k75", column_value:"11103200022") {
        id
        state
        board {
        id
        }
    }
    }"""

    #item_info = cliente_monday.run_query(search_archive_query)


    

if __name__ == "__main__":

    import sys
    from pathlib import Path

    # aponta para a pasta que contém "Módulos"
    project_root = Path(r"C:\Users\pedroruppenthal\Documents\Melnick Code\Melnick Code")
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


    # Teste da funÃ§Ã£o get_items_updated_today_yesterday
    import os
    from dotenv import load_dotenv

    repository_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    project_root = os.path.abspath(os.path.join(repository_root, '..'))
    env_path = os.path.join(project_root, '.env')

    if not os.path.exists(env_path):
        raise FileNotFoundError(
            f"O arquivo .env nÃ£o foi encontrado na pasta raiz do projeto: {project_root}."
        )

    load_dotenv(env_path)
    api_key = os.getenv("MONDAY_API_KEY")
    if not api_key:
        raise ValueError(
            "A variável de ambiente MONDAY_API_KEY nÃ£o foi encontrada no .env."
        )

    cliente_monday = ClienteMonday(api_key=api_key)

    # Ajuste o board_id conforme necessário
    board_id_teste = 18392682833
    itens_atualizados = cliente_monday.get_items_updated_today_yesterday(
        board_id=board_id_teste,
        parse_data=True,
        column_mapping=True
    )

    print(f"Itens atualizados hoje/ontem: {len(itens_atualizados)}")
