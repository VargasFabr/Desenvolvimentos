# %%
import sys
import io
import json
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
import psycopg2 
from psycopg2.extras import execute_values
from collections import defaultdict
import os
import pytz
from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=1),
}

# 📚 Entendendo a expressão CRON do schedule:
# '0 8-18 * * *'
#  │  │   │ │ │
#  │  │   │ │ └─── Dia da semana (0-6, 0=Domingo) - * = todos
#  │  │   │ └───── Mês (1-12) - * = todos
#  │  │   └─────── Dia do mês (1-31) - * = todos
#  │  └─────────── Hora (0-23) - 8-18 = das 8h às 18h
#  └────────────── Minuto (0-59) - 0 = no minuto zero


# Timezone do Brasil
tz_brasil = pytz.timezone('America/Sao_Paulo')

dag = DAG(
    'Atualiza_PostgreSQL',
    default_args=default_args,
    description='DAG para atualizar o banco de dados PostgreSQL',
    schedule='50 8-18 * * 1-6',
    start_date=tz_brasil.localize(datetime(2025, 12, 2)),
    catchup=False,
    max_active_runs=1,
    tags=['Atualiza_PostgreSQL'],
)

# ==================== FUNÇÕES DE CONEXÃO ====================

def connect_to_db_Otto():
    """
    Conecta ao banco de dados Otto usando a conexão do Airflow.
    Retorna uma conexão psycopg2 compatível com o código existente.
    
    Requer que a conexão 'postgres_otto' esteja configurada no Airflow.
    """
    try:
        # Usa PostgresHook do Airflow com a conexão 'postgres_otto'
        hook = PostgresHook(postgres_conn_id="postgres_otto")
        conn = hook.get_conn()
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados Otto via Airflow: {e}")
        raise


def connect_to_db_Melnick():
    """
    Conecta ao banco de dados Melnick usando a conexão do Airflow.
    Retorna uma conexão psycopg2 compatível com o código existente.
    
    Requer que a conexão 'postgres' esteja configurada no Airflow.
    """
    try:
        # Usa PostgresHook do Airflow com a conexão 'postgres'
        hook = PostgresHook(postgres_conn_id="postgres")
        conn = hook.get_conn()
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados Melnick via Airflow: {e}")
        raise


# ==================== FUNÇÕES DE BUSCA ====================

def Busca_Melnick(conn, table_name):
    """
    Busca a data máxima de atualização de uma tabela no banco Melnick.
    NÃO fecha a conexão - isso deve ser feito pelo chamador.
    """
    cur = None
    try:
        if table_name == 'user_realty_access_history':
            cur = conn.cursor()
            query = f"""
                    SELECT MAX(visited_at) FROM public.{table_name}
                    """
            cur.execute(query)
            rows = cur.fetchall()
            return rows

        cur = conn.cursor()
        query = f"""
        SELECT MAX(updated_at) FROM public.{table_name}
        """
        cur.execute(query)
        rows = cur.fetchall()
        return rows
    
    except Exception as e:
        print(f"Erro ao buscar dados da tabela {table_name}:", e)
        return None
    finally:
        # Fecha apenas o cursor, não a conexão
        if cur:
            cur.close()

def Busca_Otto(conn, table_name, updated_at):
    """
    Busca dados de uma tabela no banco Otto.
    NÃO fecha a conexão - isso deve ser feito pelo chamador.
    """
    cur = None
    try:
        if table_name == 'unit' or table_name == 'unit_proposal_payment':
            cur = conn.cursor()
            query = f"""
                        SELECT * FROM public.{table_name}
                        
                        """
            cur.execute(query, ())
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]  # Obter as colunas logo após a execução da consulta
            return rows, columns 
        elif table_name == 'user_realty_access_history':
            cur = conn.cursor()
            query = f"""
                                        SELECT * FROM public.{table_name}
                                        WHERE visited_at > %s
                                        """
            cur.execute(query, (updated_at,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]  # Obter as colunas logo após a execução da consulta
            return rows, columns
        else:
            cur = conn.cursor()
            query = f"""
                        SELECT * FROM public.{table_name}
                        WHERE updated_at > %s
                        """
            cur.execute(query, (updated_at,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]  # Obter as colunas logo após a execução da consulta
            return rows, columns
    except Exception as e:
        print(f"Erro ao buscar dados da tabela {table_name}:", e)
        return None, None
    finally:
        # Fecha apenas o cursor, não a conexão
        if cur:
            cur.close()

# dados, colunas = Busca_Otto(connect_to_db_Otto(),'real_estate', '2000-01-01 00:00:00')


# ==================== FUNÇÕES DE ENUMS ====================

def listar_enums_postgresql(conn):
    """
    Lista todos os tipos ENUM definidos no banco PostgreSQL.
    Retorna um dicionário: {nome_enum: [valores]}
    """
    query = """
        SELECT n.nspname AS schema, 
               t.typname AS enum_type, 
               e.enumlabel AS enum_label
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        ORDER BY t.typname, e.enumsortorder;
    """
    
    cursor = conn.cursor()
    enums = {}
    
    try:
        cursor.execute(query)
        for schema, enum_type, enum_label in cursor.fetchall():
            full_name = f"{schema}.{enum_type}" if schema != 'public' else enum_type
            enums.setdefault(full_name, []).append(enum_label)
        return enums
    finally:
        cursor.close()


def criar_enum_se_nao_existir(conn, nome_tipo, valores_enum, schema='public'):
    """
    Cria o tipo ENUM no banco destino se não existir.
    """
    cursor = conn.cursor()
    
    try:
        # Verifica se já existe
        cursor.execute("""
            SELECT 1 
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = %s AND n.nspname = %s;
        """, (nome_tipo, schema))
        
        if cursor.fetchone():
            return  # Já existe
        
        # Cria o enum
        valores_sql = ', '.join(f"'{v}'" for v in valores_enum)
        create_sql = f'CREATE TYPE "{schema}"."{nome_tipo}" AS ENUM ({valores_sql});'
        cursor.execute(create_sql)
        conn.commit()
        print(f"✓ Enum '{nome_tipo}' criado: {valores_enum}")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Erro ao criar enum '{nome_tipo}': {e}")
    finally:
        cursor.close()


def sincronizar_enums(conn_origem, conn_destino):
    """
    Sincroniza todos os ENUMs da origem para o destino.
    """
    enums_origem = listar_enums_postgresql(conn_origem)
    
    for enum_completo, valores in enums_origem.items():
        schema, nome_enum = enum_completo.split('.') if '.' in enum_completo else ('public', enum_completo)
        criar_enum_se_nao_existir(conn_destino, nome_enum, valores, schema)


# ==================== FUNÇÕES DE METADADOS ====================

def obter_metadados_tabela(conn, nome_tabela, schema='public'):
    """
    Retorna metadados das colunas de uma tabela.
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default, udt_name
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = %s
            ORDER BY ordinal_position
        """, (nome_tabela, schema))
        
        return {
            row[0]: {
                'data_type': row[1],
                'is_nullable': row[2],
                'default': row[3],
                'udt_name': row[4]
            }
            for row in cursor.fetchall()
        }
    finally:
        cursor.close()


def obter_primary_key(conn, nome_tabela, schema='public'):
    """
    Retorna as colunas que formam a PRIMARY KEY da tabela.
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name 
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_name = %s 
                AND tc.table_schema = %s
            ORDER BY kcu.ordinal_position
        """, (nome_tabela, schema))
        
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()


def obter_constraints_unicas(conn, nome_tabela, schema='public'):
    """
    Retorna todas as constraints UNIQUE da tabela.
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT tc.constraint_name, array_agg(kcu.column_name ORDER BY kcu.ordinal_position)
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name 
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'UNIQUE'
                AND tc.table_name = %s 
                AND tc.table_schema = %s
            GROUP BY tc.constraint_name
        """, (nome_tabela, schema))
        
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        cursor.close()


def obter_colunas_unicas(conn, tabela, schema='public'):
    """
    Retorna as colunas que fazem parte de constraints UNIQUE ou PRIMARY KEY.
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT tc.constraint_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name 
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
                AND tc.table_name = %s 
                AND tc.table_schema = %s
            ORDER BY kcu.ordinal_position
        """, (tabela, schema))
        
        constraints = defaultdict(list)
        for nome, coluna in cursor.fetchall():
            constraints[nome].append(coluna)
        
        # Retorna a primeira constraint encontrada
        return list(constraints.values())[0] if constraints else []
    finally:
        cursor.close()


# ==================== FUNÇÕES DE TABELAS ====================

def tabela_existe(conn, nome_tabela, schema='public'):
    """
    Verifica se uma tabela existe no banco.
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = %s 
                AND table_name = %s
            );
        """, (schema, nome_tabela))
        
        return cursor.fetchone()[0]
    finally:
        cursor.close()


def criar_tabela_com_colunas(conn, nome_tabela, metadados_origem, primary_key, schema='public'):
    """
    Cria uma tabela no banco destino com base nos metadados da origem.
    """
    cursor = conn.cursor()
    
    try:
        # Monta as definições de colunas
        colunas_def = []
        for coluna, props in metadados_origem.items():
            tipo = props['udt_name'].upper()
            nullable = "" if props['is_nullable'] == 'YES' else "NOT NULL"
            colunas_def.append(f'"{coluna}" {tipo} {nullable}')
        
        # Adiciona PRIMARY KEY se existir
        if primary_key:
            pk_cols = ', '.join(f'"{col}"' for col in primary_key)
            colunas_def.append(f'PRIMARY KEY ({pk_cols})')
        
        # Cria a tabela
        create_sql = f"""
            CREATE TABLE "{schema}"."{nome_tabela}" (
                {', '.join(colunas_def)}
            );
        """
        
        cursor.execute(create_sql)
        conn.commit()
        
        pk_info = f" com PK({', '.join(primary_key)})" if primary_key else " (sem PK)"
        print(f"✓ Tabela '{nome_tabela}' criada com {len(metadados_origem)} colunas{pk_info}")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Erro ao criar tabela '{nome_tabela}': {e}")
        raise
    finally:
        cursor.close()


def criar_constraints_unicas(conn, nome_tabela, constraints, schema='public'):
    """
    Cria constraints UNIQUE na tabela destino.
    """
    cursor = conn.cursor()
    
    try:
        for constraint_name, colunas in constraints.items():
            cols = ', '.join(f'"{col}"' for col in colunas)
            alter_sql = f"""
                ALTER TABLE "{schema}"."{nome_tabela}" 
                ADD CONSTRAINT "{constraint_name}" UNIQUE ({cols});
            """
            cursor.execute(alter_sql)
            print(f"  + Constraint UNIQUE '{constraint_name}' criada")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        print(f"⚠ Erro ao criar constraints em '{nome_tabela}': {e}")
    finally:
        cursor.close()


def adicionar_colunas_faltantes(conn, nome_tabela, metadados_origem, schema='public'):
    """
    Adiciona colunas que existem na origem mas não no destino.
    """
    cursor = conn.cursor()
    
    try:
        # Busca colunas existentes no destino
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
        """, (schema, nome_tabela))
        
        colunas_existentes = {row[0] for row in cursor.fetchall()}
        
        # Adiciona colunas faltantes
        for coluna, props in metadados_origem.items():
            if coluna not in colunas_existentes:
                tipo = props['udt_name'].upper()
                alter_sql = f'ALTER TABLE "{schema}"."{nome_tabela}" ADD COLUMN "{coluna}" {tipo};'
                cursor.execute(alter_sql)
                print(f"  + Coluna '{coluna}' ({tipo}) adicionada")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Erro ao adicionar colunas em '{nome_tabela}': {e}")
        raise
    finally:
        cursor.close()


def preparar_tabela_destino(conn_origem, conn_destino, nome_tabela, metadados_origem, schema='public'):
    """
    Garante que a tabela existe no destino e tem todas as colunas e constraints necessárias.
    """
    if not tabela_existe(conn_destino, nome_tabela, schema):
        print(f"→ Criando tabela '{nome_tabela}'...")
        
        # Obter PRIMARY KEY da origem
        primary_key = obter_primary_key(conn_origem, nome_tabela, schema)
        
        # Criar tabela com PK
        criar_tabela_com_colunas(conn_destino, nome_tabela, metadados_origem, primary_key, schema)
        
        # Criar constraints UNIQUE adicionais
        constraints_unicas = obter_constraints_unicas(conn_origem, nome_tabela, schema)
        if constraints_unicas:
            criar_constraints_unicas(conn_destino, nome_tabela, constraints_unicas, schema)
    else:
        adicionar_colunas_faltantes(conn_destino, nome_tabela, metadados_origem, schema)


# ==================== FUNÇÕES DE UPSERT ====================

def sanitizar_valor(valor, tipo_coluna=None):
    """
    Sanitiza valores para INSERT/UPSERT.
    Evita pd.isna em sequências. Trata JSON/JSONB e arrays.
    """
    # 1) Arrays (list/tuple/ndarray/Series) — tratar antes de qualquer pd.isna
    if isinstance(valor, (list, tuple, np.ndarray, pd.Series)):
        # Converter np.ndarray/Series para lista
        if isinstance(valor, (np.ndarray, pd.Series)):
            try:
                valor = valor.tolist()
            except Exception:
                valor = list(valor)
        seq = []
        for v in valor:
            # nulos por item
            if v is None or v is pd.NaT:
                seq.append(None)
                continue
            try:
                # só usar pd.isna em escalares
                if (isinstance(v, (float, int, str)) and pd.isna(v)):  # str 'NaN' não é isna; ok
                    seq.append(None)
                    continue
            except Exception:
                pass

            # item JSON em colunas json/jsonb[]
            if tipo_coluna and tipo_coluna.lower() in ('_jsonb', '_json'):
                if isinstance(v, (dict, list, tuple)):
                    seq.append(json.dumps(v))
                else:
                    seq.append(v)
            else:
                seq.append(v)

        # array vazio ou todos None → retornar []
        return [] if not seq or all(x is None for x in seq) else list(seq)

    # 2) JSON/JSONB escalar
    if tipo_coluna and tipo_coluna.lower() in ('jsonb', 'json'):
        if valor is None or valor is pd.NaT:
            return None
        if isinstance(valor, (dict, list, tuple)):
            return json.dumps(valor)
        if isinstance(valor, (int, float, bool)):
            return json.dumps(valor)
        if isinstance(valor, str):
            try:
                json.loads(valor)  # já é JSON válido
                return valor
            except Exception:
                return json.dumps(valor)
        return json.dumps(valor)

    # 3) Escalares comuns
    if valor is None or valor is pd.NaT:
        return None
    try:
        # só usar pd.isna em escalares
        if isinstance(valor, (float, int, str)) and pd.isna(valor):
            return None
    except Exception:
        pass

    # dict/tuple em coluna não-JSON → serializa
    if isinstance(valor, (dict, tuple)):
        return json.dumps(valor)

    return valor


def sanitizar_valor_seguro(valor, tipo_coluna=None):
    """
    Wrapper seguro para registrar avisos quando a sanitização falhar.
    """
    try:
        return sanitizar_valor(valor, tipo_coluna)
    except Exception as e:
        print(f"  ⚠ Erro ao sanitizar valor {valor}: {e}")
        return None


def upsert_dados_em_massa(dados, colunas, conn_destino, nome_tabela, conn_origem, schema='public'):
    """
    Realiza upsert em massa na tabela destino.
    - Cria a tabela se não existir.
    - Cria colunas faltantes.
    - Cria constraint UNIQUE(id) se necessário.
    - Executa INSERT ... ON CONFLICT corretamente.
    """
    if not dados:
        print(f"⚠ Nenhum dado para inserir em '{nome_tabela}'")
        return

    cursor = conn_destino.cursor()
    try:
        # 1. Obter metadados da origem
        metadados_origem = obter_metadados_tabela(conn_origem, nome_tabela, schema)

        # 2. Garantir que a tabela existe e está atualizada
        preparar_tabela_destino(conn_origem, conn_destino, nome_tabela, metadados_origem, schema)

        # 3. Criar tabela temporária para staging
        staging_table = f"{nome_tabela}_staging"
        col_defs = [f'"{col}" {metadados_origem[col]["udt_name"].upper()}' for col in colunas]
        cursor.execute(f'DROP TABLE IF EXISTS {staging_table};')
        cursor.execute(f'CREATE TEMP TABLE {staging_table} ({", ".join(col_defs)});')

        # 4. Sanitizar dados conforme tipo da coluna
        tipos_colunas = {col: metadados_origem[col]["udt_name"] for col in colunas}
        dados_sanitizados = []
        for linha in dados:
            linha_sanitizada = tuple(sanitizar_valor_seguro(v, tipos_colunas.get(colunas[i])) for i, v in enumerate(linha))
            dados_sanitizados.append(linha_sanitizada)

        # 5. Inserir dados na staging
        insert_stmt = f"""
            INSERT INTO {staging_table} ({', '.join([f'"{c}"' for c in colunas])})
            VALUES %s
        """
        execute_values(cursor, insert_stmt, dados_sanitizados)

        # 6. Garantir que há chave de conflito válida
        chave_unica = obter_colunas_unicas(conn_destino, nome_tabela, schema)
        if not chave_unica:
            chave_unica = obter_primary_key(conn_destino, nome_tabela, schema)

        # 6.1. Aplicar chave personalizada se não houver PK/UNIQUE
        if not chave_unica:
            chave_custom = CHAVES_PERSONALIZADAS.get(nome_tabela)
            if chave_custom and all(c in colunas for c in chave_custom):
                constraint_name = f"{nome_tabela}_{'_'.join(chave_custom)}_unique"
                try:
                    cursor.execute(
                        f'ALTER TABLE "{schema}"."{nome_tabela}" '
                        f'ADD CONSTRAINT "{constraint_name}" UNIQUE ({", ".join([f"\"{c}\"" for c in chave_custom])});'
                    )
                    conn_destino.commit()
                    print(f"  + Constraint UNIQUE composta criada: {constraint_name}")
                except psycopg2.errors.DuplicateObject:
                    conn_destino.rollback()
                except Exception as e:
                    conn_destino.rollback()
                    print(f"  ⚠ Falha ao criar UNIQUE composta em '{nome_tabela}': {e}")
                finally:
                    chave_unica = chave_custom

        # Fallbacks seguros
        if not chave_unica:
            # Se houver 'id', cria UNIQUE(id)
            if 'id' in colunas:
                print(f"⚠ Nenhuma constraint UNIQUE/PK em '{nome_tabela}'. Criando UNIQUE(id)...")
                try:
                    cursor.execute(
                        f'ALTER TABLE "{schema}"."{nome_tabela}" ADD CONSTRAINT "{nome_tabela}_id_unique" UNIQUE ("id");'
                    )
                    conn_destino.commit()
                    chave_unica = ['id']
                except psycopg2.errors.DuplicateObject:
                    conn_destino.rollback()
                    chave_unica = ['id']
                except Exception as e:
                    conn_destino.rollback()
                    print(f"  ⚠ Falha ao criar UNIQUE(id): {e}")
                    # Não foi possível criar UNIQUE(id). Vamos inserir sem ON CONFLICT
                    chave_unica = []
                    print(f"⚠ Nenhuma constraint disponível em '{nome_tabela}'. Inserindo sem ON CONFLICT.")
            else:
                # Sem coluna 'id' e sem UNIQUE/PK: inserir sem ON CONFLICT
                chave_unica = []
                print(f"⚠ Nenhuma constraint encontrada em '{nome_tabela}'. Inserindo sem ON CONFLICT.")

        # 7. Montar SQL de carga (UPSERT se houver chave; caso contrário, INSERT simples)
        insert_cols = ', '.join([f'"{col}"' for col in colunas])
        base_insert_select = f"INSERT INTO \"{schema}\".\"{nome_tabela}\" ({insert_cols}) SELECT * FROM {staging_table}"

        if chave_unica:
            colunas_conflito = ', '.join(f'"{col}"' for col in chave_unica)
            update_cols = [col for col in colunas if col not in chave_unica]
            if update_cols:
                update_set = ', '.join(f'"{col}" = EXCLUDED."{col}"' for col in update_cols)
                upsert_sql = f"""
                    {base_insert_select}
                    ON CONFLICT ({colunas_conflito})
                    DO UPDATE SET {update_set};
                """
            else:
                # Nada para atualizar (todas as colunas fazem parte do conflito) → DO NOTHING
                upsert_sql = f"""
                    {base_insert_select}
                    ON CONFLICT ({colunas_conflito})
                    DO NOTHING;
                """
        else:
            # Sem UNIQUE/PK e sem possibilidade de criá-la: executar INSERT simples
            print(f"⚠ Nenhuma UNIQUE/PK disponível para '{nome_tabela}'. Executando INSERT sem ON CONFLICT.")
            upsert_sql = base_insert_select + ";"

        # 8. Executar UPSERT com segurança

        if nome_tabela == 'unit_proposal_payment':
            cursor.execute(f'TRUNCATE TABLE "{schema}"."{nome_tabela}";')
            conn_destino.commit()
        cursor.execute(f'ALTER TABLE "{schema}"."{nome_tabela}" DISABLE TRIGGER ALL;')
        conn_destino.commit()

        cursor.execute(upsert_sql)
        conn_destino.commit()

        cursor.execute(f'ALTER TABLE "{schema}"."{nome_tabela}" ENABLE TRIGGER ALL;')
        conn_destino.commit()

        print(f"✓ Upsert concluído: {len(dados)} registros em '{nome_tabela}' (chave usada: {chave_unica})")

    except Exception as e:
        conn_destino.rollback()
        print(f"✗ Erro no upsert de '{nome_tabela}': {e}")
        import traceback
        print(traceback.format_exc())
        raise
    finally:
        cursor.close()


# ==================== SCRIPT PRINCIPAL ====================

# Lista de tabelas a sincronizar
TABELAS = [
    'building', 'city', 'client', 'credit_analysis', 'credit_analysis_status',
    'credit_analysis_status_history', 'customer', 'customer_process',
    'customer_process_customer', 'customer_process_document', 'document_type',
    'real_estate', 'real_estate_developer', 'realty', 'realty_company',
    'realty_infrastructure_item', 'realty_payment_plan_installment',
    'realty_payment_plan_installment_unit', 'realty_phase', 'realty_phase_status',
    'realty_phase_status_step', 'realty_status', 'realty_suggested_payment',
    'realty_suggested_payment_flow_item', 'realty_suggested_payment_unit_price',
    'sales_executive_portfolio', 'state', 'unit', 'unit_booking',
    'unit_booking_status', 'unit_booking_status_history', 'unit_proposal',
    'unit_proposal_collaboration_user', 'unit_proposal_commission',
    'unit_proposal_history', 'unit_proposal_payment', 'unit_proposal_payment_type',
    'unit_proposal_status', 'unit_status', 'unit_type', 'unit_visit',
    'unit_visit_status', 'user', 'user_client_team_profile', 'user_real_estate',
    'user_realty_access_history', 'folder','folder_customer','client_event', 'folder_status', 'folder_status_history',
    'realty_description_unit','realty_media','media','realty_description_building'
]
# TABELAS = ['client_event']  

# Chaves únicas personalizadas por tabela (quando a origem não expõe PK/UNIQUE)
CHAVES_PERSONALIZADAS = {
    'customer_process_customer': ['customer_id', 'customer_process_id'],
}

def normalizar_data(data):
    """
    Normaliza o valor de data retornado por Busca_Melnick.
    Retorna uma string de data válida ou a data padrão.
    
    Busca_Melnick retorna fetchall() que é uma lista de tuplas:
    - Com dados: [(datetime(...),)]
    - Sem dados: [(None,)]
    """
    data_padrao = '2000-01-01 00:00:00'
    
    if data is None:
        return data_padrao
    
    # Se data for uma lista (resultado de fetchall), pega a primeira tupla
    if isinstance(data, list):
        if len(data) > 0:
            data = data[0]  # Pega a primeira tupla: (datetime(...),) ou (None,)
        else:
            return data_padrao
    
    # Se data for uma tupla (resultado de fetchone ou primeiro elemento da lista)
    if isinstance(data, tuple):
        if len(data) > 0:
            data = data[0]  # Pega o valor dentro da tupla: datetime(...) ou None
        else:
            return data_padrao
    
    # Se for None após extrair da tupla
    if data is None:
        return data_padrao
    
    # Se for string mas não parece uma data válida
    if isinstance(data, str):
        # Se for apenas um número ou string curta, usa data padrão
        if len(data) < 10 or data.isdigit():
            return data_padrao
        return data
    
    # Se for datetime, converte para string
    if isinstance(data, (datetime, date)):
        return data.strftime('%Y-%m-%d %H:%M:%S')
    
    # Caso padrão
    return data_padrao

def atualizar_postgresql(**context):
    """
    Função principal que será executada pela DAG do Airflow.
    Sincroniza dados do banco Otto para o banco Melnick.
    """
    try:
        # Captura logs para salvar em arquivo também
        output = io.StringIO()
        
        start_time = datetime.now()
        print(f'=== INÍCIO: {start_time} ===\n')
        output.write(f'=== INÍCIO: {start_time} ===\n\n')
        
        # Sincronizar ENUMs primeiro
        print('→ Sincronizando ENUMs...')
        output.write('→ Sincronizando ENUMs...\n')
        try:
            conn_otto = connect_to_db_Otto()
            conn_melnick = connect_to_db_Melnick()
            sincronizar_enums(conn_otto, conn_melnick)
            output.write('✓ ENUMs sincronizados com sucesso\n')
            conn_otto.close()
            conn_melnick.close()
        except Exception as e:
            print(f'⚠ Aviso ao sincronizar ENUMs: {e}')
            output.write(f'⚠ Aviso ao sincronizar ENUMs: {e}\n')
        print()
        output.write('\n')
    
        # Processar cada tabela
        
        for idx, table_name in enumerate(TABELAS, 1):
            tempo_inicio = datetime.now()
            print(f'→ Processando: {table_name}')
            output.write(f'→ Processando: {table_name}\n')
            
            try:
                # Buscar data da última sincronização
                data_raw = None
                conn_melnick_busca = None
                try:
                    conn_melnick_busca = connect_to_db_Melnick()
                    data_raw = Busca_Melnick(conn_melnick_busca, table_name)
                    conn_melnick_busca.close()
                except Exception as e:
                    print(f'  ⚠ Tabela não existe no destino (será criada): {e}')
                    output.write(f'  ⚠ Tabela não existe no destino (será criada): {e}\n')
                    if conn_melnick_busca:
                        try:
                            conn_melnick_busca.close()
                        except:
                            pass
                
                # Normalizar a data
                data = normalizar_data(data_raw)
                
                # Buscar dados da origem
                conn_otto_busca = None
                try:
                    conn_otto_busca = connect_to_db_Otto()
                    dados, colunas = Busca_Otto(conn_otto_busca, table_name, data)
                    conn_otto_busca.close()
                except Exception as e:
                    if conn_otto_busca:
                        try:
                            conn_otto_busca.close()
                        except:
                            pass
                    raise
                
                if not dados:
                    print(f'  ⚠ Nenhum dado novo encontrado na origem')
                    output.write(f'  ⚠ Nenhum dado novo encontrado na origem\n')
                    tempo_decorrido = datetime.now() - tempo_inicio
                    print(f'  Tempo: {tempo_decorrido}\n')
                    output.write(f'  Tempo: {tempo_decorrido}\n\n')
                    continue
                
                print(f'  Encontrados {len(dados)} registros para sincronizar')
                output.write(f'  Encontrados {len(dados)} registros para sincronizar\n')
                
                # Realizar upsert
                try:
                    conn_melnick_upsert = connect_to_db_Melnick()
                    conn_otto_upsert = connect_to_db_Otto()
                    upsert_dados_em_massa(
                        dados, colunas, 
                        conn_melnick_upsert, 
                        table_name, 
                        conn_otto_upsert, 
                        schema='public'
                    )
                    conn_melnick_upsert.close()
                    conn_otto_upsert.close()
                except Exception as e:
                    if 'conn_melnick_upsert' in locals():
                        try:
                            conn_melnick_upsert.close()
                        except:
                            pass
                    if 'conn_otto_upsert' in locals():
                        try:
                            conn_otto_upsert.close()
                        except:
                            pass
                    raise
                
                tempo_decorrido = datetime.now() - tempo_inicio
                print(f'  Tempo: {tempo_decorrido}\n')
                output.write(f'  Tempo: {tempo_decorrido}\n\n')
                
            except Exception as e:
                print(f'✗ Erro: {e}')
                output.write(f'✗ Erro: {e}\n')
                import traceback
                error_details = traceback.format_exc()
                print(f'  Detalhes: {error_details}')
                output.write(f'  Detalhes: {error_details}\n')
                tempo_decorrido = datetime.now() - tempo_inicio
                print(f'  Tempo: {tempo_decorrido}\n')
                output.write(f'  Tempo: {tempo_decorrido}\n\n')
        
        # Salvar log
        end_time = datetime.now()
        tempo_total = end_time - start_time
        
        # Usa caminho dentro do container Docker que será mapeado para a pasta local
        # Funciona tanto no Docker (/opt/airflow/logsOtto) quanto localmente (E:\Projetos\logsOtto)
        
        # if os.path.exists('/opt/airflow/logsOtto'):
        #     # Dentro do container Docker
        #     log_dir = '/opt/airflow/logsOtto'
        # else:
        #     # Executando localmente
        #     log_dir = r'E:\Projetos\logsOtto'
        
        # # Garante que o diretório existe
        # os.makedirs(log_dir, exist_ok=True)
        
        # log_filename = os.path.join(log_dir, f'log_{start_time:%Y-%m-%d--%H-%M-%S}--{end_time:%Y-%m-%d--%H-%M-%S}.txt')
        
        # # Salva o log em arquivo
        # try:
        #     with open(log_filename, 'w', encoding='utf-8') as f:
        #         f.write(output.getvalue())
        #     print(f'Log salvo em: {log_filename}')
        # except Exception as e:
        #     print(f'Erro ao salvar log em arquivo: {e}')
        
        output.close()
        
        print(f'\n=== CONCLUÍDO ===')
        print(f'Tempo total: {tempo_total}')
        # print(f'Log salvo em: {log_filename}')
        
    except Exception as e:
        # Se houver erro antes de criar o logger, usar print
        print("=" * 60)
        print("ERRO CRÍTICO na execução da função!")
        print("=" * 60)
        print(f"Erro: {str(e)}")
        print(f"Tipo: {type(e).__name__}")
        import traceback
        print(traceback.format_exc())
        raise


# Definindo as tarefas do Airflow
tarefa_atualizar_postgresql = PythonOperator(
    task_id='atualizar_postgresql',
    python_callable=atualizar_postgresql,
    dag=dag,
)

# # Disparar a DAG de previsão de propostas após terminar
# tarefa_disparar_previsao = TriggerDagRunOperator(
#     task_id='disparar_previsao_propostas',
#     trigger_dag_id='Prev_Propostas_Aprovacao',
#     wait_for_completion=False,  # Não aguarda a conclusão
#     dag=dag,
# )

# # Disparar a DAG Previsao_Propostas após terminar (igual ao Prev_Propostas_Aprovacao)
# tarefa_disparar_previsao_propostas = TriggerDagRunOperator(
#     task_id='disparar_previsao_propostas_dag',
#     trigger_dag_id='Previsao_Propostas',
#     wait_for_completion=False,
#     dag=dag,
# )

# Definir a ordem de execução
tarefa_atualizar_postgresql 
tarefa_atualizar_postgresql 
