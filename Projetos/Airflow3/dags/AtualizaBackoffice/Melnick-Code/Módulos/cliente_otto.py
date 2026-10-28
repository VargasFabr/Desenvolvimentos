# Cliente para conexão com banco de dados em PostgreSQL do Otto
# %%
import os

import psycopg2
from typing import List, Dict, Any

#--------------------------------
# LOGGER
import logging
logger = logging.getLogger("Cliente Otto")
#--------------------------------

# Pedaços de strings que devem ser considerados como teste e não como processo real,
# para evitar que processos de teste sejam considerados na análise dos dados.

TEST_KEYS = [
    "/ teste",
    "(teste)",
    " teste",
    "teste ",
    "testando",
]

# Dicionário de status de propostas e reservas do Otto
# Nome no otto no comentário, para com o nome do status no Monday

STATUS_PROPOSTA = {
    11:"Aprovada", # Aprovada com ajuste no pagamento
    12:"Aprovada", # Aprovada com ajuste
    10:"Cancelada",
    9: "Vendida",
    6: "Não enviada",
    7: "Em alteração",
    1: "Aguardando análise",
    3: "Aprovada",
    8: "Aprovada", # Aprovada com ajustes na comissão
    2: "Em análise",
    4: "Ajustes", # Precisa de ajustes
    5: "Não aprovada",
    0: "Sem proposta" # Sem proposta
}

STATUS_RESERVA = { 
    6:"Vendida", # Vendida
    5:"Precisa de ajustes", # Precisa de ajustes
    1:"Aguardando aprovação", # Aguardando aprovação
    2:"Aprovada", # Aprovada
    4:"Cancelada", # Cancelada
    3:"Não aprovada", # Não aprovada
    0: "Sem reserva" # Sem reserva
}

class ClienteOtto:
    def __init__(self, user: str, password: str):
        self.host = os.getenv("OTTO_RDS_HOST") or os.getenv("OTTO_DB_HOST") or ""
        self.database = os.getenv("OTTO_RDS_DB") or os.getenv("OTTO_DB_NAME") or "otto_prod"
        self.user = user
        self.password = password
        self.port = int(os.getenv("OTTO_RDS_PORT") or os.getenv("OTTO_DB_PORT") or "5432")
        if not self.host:
            raise ValueError("Defina OTTO_RDS_HOST (ou OTTO_DB_HOST) no .env")
    
    def connect(self):
        """Estabelece a conexão com o banco de dados."""
        self.connection = psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password,
            port=self.port
        )
        self.cursor = self.connection.cursor()
        logger.debug("Conexão com o banco de dados estabelecida.")
    
    def close(self):
        """Fecha a conexão com o banco de dados."""
        if self.connection:
            self.connection.close()
            logger.debug("Conexão com o banco de dados fechada.")
        else:
            logger.debug("Nenhuma conexão ativa para fechar.")

    def run_query(self, query: str, variables: tuple = ()) -> List[Dict[str, Any]]:
        """
        Executa uma consulta SQL e retorna os resultados como uma lista de dicionários.
        Args:
            query (str): Consulta SQL a ser executada.
            variables (tuple): Variáveis para a consulta SQL. Padrão é uma tupla vazia.
        Returns:
            List[Dict[str, Any]]: Lista de dicionários contendo as linhas retornadas pela consulta.
        """
        self.connect()
        try:
            # Executa a consulta
            self.cursor.execute(query, variables)
            # Obtém os resultados
            rows = self.cursor.fetchall()
            columns = self.cursor.description
            if columns is not None:
                columns = [col.name for col in columns]
            else:
                raise ValueError("Nenhuma coluna retornada na consulta.")
            # Monta a lista de dicionários
            result = [{columns[i]: row[i] for i in range(len(columns))} for row in rows]
        except Exception as e:
            raise e
        finally:
            self.close()
        return result

    def run_query_with_date_filter(self, table: str, after_date: str, date_column: str = "updated_at", id_column: str = "id") -> Dict[str, Dict[str, Any]]:
        """
        Obtém as linhas da tabela com o valor da coluna de data após uma data específica.
        Args:
            table (str): Nome da tabela no banco de dados.
            after_date (str): Data no formato 'YYYY-MM-DD hh:mm:ss' para filtrar atualizações. Fuso é o UTC, fazer a conversão se necessário.
            date_column (str): Nome da coluna de data para filtrar. Padrão é 'updated_at'.
            id_column (str): Nome da coluna de ID para usar como chave no dicionário retornado. Padrão é 'id'.
        Returns:
            Dict[str, Dict[str, Any]]: Dicionário de dicionários contendo as linhas filtradas e com o valor da coluna id como chave.
        """
        self.connect()

        # Monta a consulta SQL com filtro de data
        query = f"""SELECT * FROM {table} WHERE {date_column} >= %s;"""

        try:            
            # Executa a consulta
            self.cursor.execute(query, (after_date,))
            # Transforma o resultado em um dicionário de dicionários
            # A chave é o id do processo e as chaves internas são os nomes das colunas
            # Não repete a coluna id dentro do dicionário interno
            rows = self.cursor.fetchall()
            columns = self.cursor.description
            if columns is not None:
                columns = [col.name for col in columns]
            else:
                raise ValueError("Nenhuma coluna retornada na consulta.")
            # Monta o dicionário final
            result = {row[columns.index(id_column)]: {columns[i]: row[i] for i in range(len(columns)) if columns[i] != id_column} for row in rows}
        except Exception as e:
            raise e
        finally:
            self.close()
        return result
    
    def get_customer_process_updates(self, after_date: str, ids_list: List[str] = []) -> Dict[str, Dict[str, Any]]:
        """
        Obtém atualizações de processos de clientes com atualização após uma data específica ou com ids específicos.
        Args:
            after_date (str): Data no formato 'YYYY-MM-DD hh:mm:ss' para filtrar atualizações. Fuso é o UTC, fazer a conversão se necessário.
            ids_list (List[str]): Lista de IDs de processos de clientes para filtrar. Padrão é uma lista vazia.
        Returns:
            Dict[str, Dict[str, Any]]: Dicionário de dicionários contendo as linhas filtradas e com o valor da coluna id como chave.
        """
        if not ids_list or len(ids_list) == 0:
            query = """
                SELECT *
                FROM customer_process
                WHERE updated_at >= %s
                """
            variables = (after_date,)
        else:
            query = """
                SELECT *
                FROM customer_process
                WHERE updated_at >= %s
                OR id IN %s;
                """
            variables = (after_date, tuple(ids_list))
        self.connect()
        try:            
            # Executa a consulta
            self.cursor.execute(query, variables)
            # Transforma o resultado em um dicionário de dicionários
            # A chave é o id do processo e as chaves internas são os nomes das colunas
            # Não repete a coluna id dentro do dicionário interno
            rows = self.cursor.fetchall()
            columns = self.cursor.description
            if columns is not None:
                columns = [col.name for col in columns]
            else:
                raise ValueError("Nenhuma coluna retornada na consulta.")
            # Monta o dicionário final
            result = {row[columns.index('id')]: {columns[i]: row[i] for i in range(len(columns)) if columns[i] != 'id'} for row in rows}
        except Exception as e:
            raise e
        finally:
            self.close()
        return result
    
    def get_table_by_ids(self, table: str, ids_list: List[str], id_column: str = "id") -> Dict[str, Dict[str, Any]]:
        """
        Obtém linhas de uma tabela específica com IDs fornecidos.
        Args:
            table (str): Nome da tabela no banco de dados.
            ids_list (List[str]): Lista de IDs para filtrar as linhas.
            id_column (str): Nome da coluna de ID para usar como chave no dicionário retornado. Padrão é 'id'.
        Returns:
            Dict[str, Dict[str, Any]]: Dicionário de dicionários contendo as linhas filtradas e com o valor da coluna id como chave.
        """
        if not ids_list or len(ids_list) == 0:
            return {}
        
        query = f"""SELECT * FROM {table} WHERE {id_column} IN %s;"""
        variables = (tuple(ids_list),)

        self.connect()
        try:            
            # Executa a consulta
            self.cursor.execute(query, variables)
            # Transforma o resultado em um dicionário de dicionários
            rows = self.cursor.fetchall()
            columns = self.cursor.description
            if columns is not None:
                columns = [col.name for col in columns]
            else:
                raise ValueError("Nenhuma coluna retornada na consulta.")
            # Monta o dicionário final
            result = {row[columns.index(id_column)]: {columns[i]: row[i] for i in range(len(columns)) if columns[i] != id_column} for row in rows}
        except Exception as e:
            raise e
        finally:
            self.close()
        return result
    
    def get_proposals(self, after_date: str) -> Dict[str, Any]:
        """
        Obtém propostas atualizadas após uma data específica.
        Args:
            after_date (str): Data no formato 'YYYY-MM-DD hh:mm:ss' para filtrar atualizações. Fuso é o UTC, fazer a conversão se necessário.
        Returns:
            List[Dict[str, Any]]: Lista de dicionários contendo as propostas atualizadas.
        """
        query = """
            WITH resumo_pagamentos AS (
                SELECT
                    proposal_id,
                    SUM(value * array_length(payment_distribution, 1)) AS proposta,
                    SUM(CASE WHEN payment_type_id = 3 THEN value ELSE 0 END) AS ato
                FROM unit_proposal_payment
                WHERE holder = 'customer'
                GROUP BY proposal_id
            )
            SELECT
                up.customer_process_id AS id_negocio,
                up.id AS id_proposta,
                up.sent_to_revision_at AS proposta_enviada_em,
                up.status_id AS id_status_proposta,
                up.created_at AS proposta_criada_em,
                up.updated_at AS proposta_atualizada_em,
                up.customer_id AS id_cliente,
                up.delivery_date AS proposta_entregue_em,
                up.webhook_invocation_result_metadata AS resultado_integracao_proposta,
                p.proposta AS valor_proposta,
                p.ato AS ato,
                (up.financing_percent * 100) AS percentual_financiado,
                (up.calculated_commission_percent * 100) AS percentual_comissao,
                upc.commission_value AS valor_comissao,
                COALESCE(p.proposta - upc.commission_value, p.proposta) AS valor_liquido
            FROM unit_proposal up
            LEFT JOIN resumo_pagamentos p
                ON up.id = p.proposal_id
            LEFT JOIN unit_proposal_commission upc
                ON up.current_commission_id = upc.id
            WHERE up.updated_at >= %s
            ORDER BY up.updated_at ASC
        """
        self.connect()
        try:
            self.cursor.execute(query, (after_date,))
            rows = self.cursor.fetchall()
            columns = self.cursor.description
            if columns is not None:
                columns = [col.name for col in columns]
            else:
                raise ValueError("Nenhuma coluna retornada na consulta.")
            # Monta um dicionário com o id_proposta como chave, sem repetir dentro do dicionário interno
            result = {row[columns.index("id_proposta")]: {columns[i]: row[i] for i in range(len(columns)) if columns[i] != "id_proposta"} for row in rows}
        except Exception as e:
            raise e
        finally:
            self.close()
        return result
    
    def get_bookings(self, after_date: str) -> Dict[str, Any]:
        """
        Obtém reservas atualizadas após uma data específica.
        Args:
            after_date (str): Data no formato 'YYYY-MM-DD hh:mm:ss' para filtrar atualizações. Fuso é o UTC, fazer a conversão se necessário.
        Returns:
            List[Dict[str, Any]]: Lista de dicionários contendo as reservas atualizadas.
        """
        query = """
            SELECT
            customer_process_id as id_negocio,
            id as id_reserva,
            created_at as reserva_criada_em,
            updated_at as reserva_atualizada_em,
            unit_booking_status_id as id_status_reserva,
            queue_position as posicao_fila,
            first_position_start_at as inicio_primeira_posicao,
            first_position_end_at as fim_primeira_posicao,
            webhook_invocation_result_metadata as resultado_integracao_reserva
            FROM unit_booking
            WHERE updated_at >= %s
            ORDER BY updated_at ASC
        """
        self.connect()
        try:
            self.cursor.execute(query, (after_date,))
            rows = self.cursor.fetchall()
            columns = self.cursor.description
            if columns is not None:
                columns = [col.name for col in columns]
            else:
                raise ValueError("Nenhuma coluna retornada na consulta.")
            # Monta o dicionário com o id_reserva como chave, sem repetir dentro do dicionário interno
            result = {row[columns.index("id_reserva")]: {columns[i]: row[i] for i in range(len(columns)) if columns[i] != "id_reserva"} for row in rows}
        except Exception as e:
            raise e
        finally:
            self.close()
        return result
    
    def get_processes(self, after_date: str) -> Dict[str, Any]:
        """
        Obtém processos de clientes atualizados após uma data específica.
        Args:
            after_date (str): Data no formato 'YYYY-MM-DD hh:mm:ss' para filtrar atualizações. Fuso é o UTC, fazer a conversão se necessário.
        Returns:
            List[Dict[str, Any]]: Lista de dicionários contendo os processos de clientes atualizados.
        """
        query = """
            SELECT
                customer_process.id AS id_negocio,
                customer_process.created_at AS negocio_criado_em,
                customer_process.updated_at AS negocio_atualizado_em,

                -- CORRETOR
                customer_process.realtor_id AS id_corretor,
                user_real_estate.real_estate_team_profile_id AS cargo_corretor,
                corretor.name AS nome_corretor,
                corretor.creci AS creci_corretor,
                corretor.cpf AS cpf_corretor,
                
                -- GERENTE
                    gerente.id   AS id_gerente,
                    gerente.name AS nome_gerente,

                -- EXECUTIVO
                -- Regra de negócio Melnick: alguns corretores acumulam o papel de executivo
                -- (lista de UUIDs abaixo). Para esses, o próprio corretor é considerado o
                -- executivo, independentemente do que vier do portfólio. Para os demais,
                -- vale a regra da query Pastas.sql: o LATERAL JOIN abaixo busca o executivo
                -- na carteira (agência primeiro, corretor independente depois) quando a
                -- imobiliária está marcada com must_assign_sales_executive=TRUE.
                CASE
                    WHEN corretor.id IN (
                        'e442332f-8309-4623-aeb2-1e65758fdd2e',
                        '90612dfc-5860-4438-aca9-5712e978d2b2',
                        'f7371cb7-b514-4e52-826d-63e8fd73f90f',
                        '28b93527-b6b4-4e93-89e3-27c08c9acc4c',
                        '537f1a7d-7c67-48b1-a946-b33e30cbfa2c',
                        'd7c9c777-6088-4398-b6fa-f189e98b31e2',
                        'b31e33c8-190a-4c61-99be-fe16be16a776',
                        '7865072e-5c7c-48c8-ba80-43ec6cae958c'
                    )
                    THEN corretor.id
                    ELSE executivo.id
                END AS id_executivo,

                CASE
                    WHEN corretor.id IN (
                        'e442332f-8309-4623-aeb2-1e65758fdd2e',
                        '90612dfc-5860-4438-aca9-5712e978d2b2',
                        'f7371cb7-b514-4e52-826d-63e8fd73f90f',
                        '28b93527-b6b4-4e93-89e3-27c08c9acc4c',
                        '537f1a7d-7c67-48b1-a946-b33e30cbfa2c',
                        'd7c9c777-6088-4398-b6fa-f189e98b31e2',
                        'b31e33c8-190a-4c61-99be-fe16be16a776',
                        '7865072e-5c7c-48c8-ba80-43ec6cae958c'
                    )
                    THEN corretor.name
                    ELSE executivo.name
                END AS nome_executivo,


                -- IMOBILIÁRIA
                real_estate.id AS id_imobiliaria,
                real_estate.name AS nome_imobiliaria,
                real_estate.cnpj AS cnpj_imobiliaria,
                real_estate.creci AS creci_imobiliaria,

                -- UNIDADE
                customer_process.unit_id AS id_unidade,
                unit.number AS numero_unidade,
                unit.integration_id AS id_integracao_unidade,
                unit.price AS valor_unidade,
                unit.is_exchangeable AS flag_permuta,
                unit.integration_metadata AS resultado_integracao_unidade,

                -- TORRE
                building.id AS id_torre,
                building.name AS nome_torre,
                building.integration_id AS id_integracao_torre,

                -- EMPREENDIMENTO
                realty.id AS id_empreendimento,
                realty.name AS nome_empreendimento,
                realty.integration_id AS id_integracao_empreendimento,

                -- INCORPORADORA
                real_estate_developer.name AS nome_incorporadora,

                -- CLIENTE
                customer_process_customer.customer_id AS id_cliente,
                customer.name AS nome_cliente,
                customer.cpf AS cpf_cliente,
                customer.cnpj AS cnpj_cliente

            FROM customer_process

            LEFT JOIN customer_process_customer
                ON customer_process.id = customer_process_customer.customer_process_id
            AND customer_process_customer.owner = TRUE

            LEFT JOIN customer
                ON customer_process_customer.customer_id = customer.id

            -- BASE DO CORRETOR / IMOBILIÁRIA
            LEFT JOIN user_real_estate user_real_estate
                ON customer_process.user_real_estate_id = user_real_estate.id

            LEFT JOIN real_estate
                ON user_real_estate.real_estate_id = real_estate.id

            LEFT JOIN "user" corretor
                ON customer_process.realtor_id = corretor.id

            -- GERENTE
            LEFT JOIN user_real_estate gerente1
                ON user_real_estate.id = gerente1.id

            LEFT JOIN user_real_estate gerente2
                ON gerente1.managed_by_user_real_estate_id = gerente2.id

            LEFT JOIN "user" gerente
                ON gerente2.user_id = gerente.id

            -- UNIDADE / EMPREENDIMENTO
            LEFT JOIN unit
                ON customer_process.unit_id = unit.id

            LEFT JOIN building
                ON unit.building_id = building.id

            LEFT JOIN realty
                ON building.realty_id = realty.id

            LEFT JOIN real_estate_developer
                ON realty.real_estate_developer_id = real_estate_developer.id

            -- EXECUTIVO (mesma regra da view PROPOSTAS)
            LEFT JOIN LATERAL (
                SELECT
                    COALESCE(
                        (
                            SELECT sep.user_client_team_profile_id
                            FROM sales_executive_portfolio sep
                            JOIN user_client_team_profile uctp_check
                                ON uctp_check.id = sep.user_client_team_profile_id
                            WHERE sep.real_estate_agency_id = real_estate.id
                            AND uctp_check.client_id = realty.client_id
                            AND uctp_check.client_team_profile_id = 'SalesExecutive'
                            ORDER BY
                                COALESCE(sep.updated_at, sep.created_at) DESC NULLS LAST,
                                sep.id DESC
                            LIMIT 1
                        ),
                        (
                            SELECT sep.user_client_team_profile_id
                            FROM sales_executive_portfolio sep
                            JOIN user_client_team_profile uctp_check
                                ON uctp_check.id = sep.user_client_team_profile_id
                            WHERE sep.independent_user_real_estate_agency_id = user_real_estate.id
                            AND uctp_check.client_id = realty.client_id
                            AND uctp_check.client_team_profile_id = 'SalesExecutive'
                            ORDER BY
                                COALESCE(sep.updated_at, sep.created_at) DESC NULLS LAST,
                                sep.id DESC
                            LIMIT 1
                        )
                    ) AS user_client_team_profile_id
            ) sep_unificado
                ON COALESCE(real_estate.must_assign_sales_executive, FALSE) = TRUE

            LEFT JOIN user_client_team_profile uctp
                ON uctp.id = sep_unificado.user_client_team_profile_id
            AND uctp.client_team_profile_id = 'SalesExecutive'
            AND uctp.client_id = realty.client_id

            LEFT JOIN "user" executivo
                ON executivo.id = uctp.user_id

            WHERE
                customer_process.updated_at >= %s
                OR customer_process.id IN (
                    SELECT customer_process_id
                    FROM unit_proposal
                    WHERE updated_at >= %s

                    UNION

                    SELECT customer_process_id
                    FROM unit_booking
                    WHERE updated_at >= %s
                )

            ORDER BY customer_process.updated_at ASC;

        """
        self.connect()
        try:
            self.cursor.execute(query, (after_date, after_date, after_date))
            rows = self.cursor.fetchall()
            columns = self.cursor.description
            if columns is not None:
                columns = [col.name for col in columns]
            else:
                raise ValueError("Nenhuma coluna retornada na consulta.")
            # Monta o dicionário com o id_negocio como chave, sem repetir dentro do dicionário interno
            result = {row[columns.index("id_negocio")]: {columns[i]: row[i] for i in range(len(columns)) if columns[i] != "id_negocio"} for row in rows}
        except Exception as e:
            raise e
        finally:
            self.close()
        return result
    
    def get_units(self, ids_list: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Obtém unidades com IDs fornecidos, incluindo informações de torre, empreendimento e incorporadora.
        Args:
            ids_list (List[str]): Lista de IDs de unidades para filtrar.
        Returns:
            Dict[str, Dict[str, Any]]: Dicionário de dicionários contendo as unidades filtradas e com o valor da coluna id como chave.
        """
        if not ids_list or len(ids_list) == 0:
            return {}
        
        query = """
            SELECT
                unit.number as unit_number,
                unit.id as unit_id,
                unit.integration_id as unit_integration_id,
                unit.price,
                unit.integration_metadata as unit_integration_metadata,
                building.name as tower_name,
                building.integration_id as tower_integration_id,
                realty.name as development_name,
                realty.integration_id as development_integration_id,
                real_estate_developer.name as developer_name
            FROM unit
            INNER JOIN building ON unit.building_id = building.id
            INNER JOIN realty ON building.realty_id = realty.id
            INNER JOIN real_estate_developer ON realty.real_estate_developer_id = real_estate_developer.id
            WHERE unit.id IN %s;
        """
        variables = (tuple(ids_list),)

        self.connect()
        try:
            self.cursor.execute(query, variables)
            rows = self.cursor.fetchall()
            columns = self.cursor.description
            if columns is not None:
                columns = [col.name for col in columns]
            else:
                raise ValueError("Nenhuma coluna retornada na consulta.")
            # Monta o dicionário final com unit_id como chave, sem repetir dentro do dicionário interno
            result = {row[columns.index('unit_id')]: {columns[i]: row[i] for i in range(len(columns)) if columns[i] != 'unit_id'} for row in rows}
        except Exception as e:
            raise e
        finally:
            self.close()
        return result

def main():
    # Procura o caminho para a pasta raiz do projeto
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

    # Confirma que as variáveis de ambiente necessárias existem
    user = os.getenv("OTTO_DB_USER")
    password = os.getenv("OTTO_DB_PASSWORD")
    if not user or not password:
        raise ValueError("As variáveis de ambiente OTTO_DB_USER e OTTO_DB_PASSWORD não foram encontradas nas variáveis de ambiente. Verifique o arquivo .env.")
    
    cliente_otto = ClienteOtto(user=user, password=password)

    # # Teste de obtenção de atualizações de propostas
    after_date = "2025-12-17 11:00:00"
    processes = cliente_otto.get_processes(after_date=after_date)
    return processes
    

if __name__ == "__main__":
    processes = main()