# DAG Previsao_Propostas — lógica de previsão idêntica a Previsao_Propostas_standalone.py.
# Requer Prophet>=1.3.0 no ambiente se estiver usando pandas 3.x (Prophet 1.2.x gera "duplicate labels").
# Imports pesados (pandas, prophet, sklearn) ficam dentro das funções para não estourar o timeout do DagBag (30s).
from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
import pytz

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

# ==================== FUNÇÕES AUXILIARES ====================

def connect_to_db_Melnick():
    try:
        # Usa PostgresHook do Airflow com a conexão 'postgres'
        hook = PostgresHook(postgres_conn_id="postgres")
        conn = hook.get_conn()
        print("[LOG] Conectado ao PostgreSQL (Melnick).")
        return conn
    except Exception as e:
        print(f"[LOG] Erro ao conectar ao banco de dados: {e}")
        return None


def criar_tabela_prev_propostas(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.prev_propostas (
                data DATE,
                "Previsao" DOUBLE PRECISION,
                limite_inferior DOUBLE PRECISION,
                limite_superior DOUBLE PRECISION,
                valor DOUBLE PRECISION,
                "Atualizacao" TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        print("[LOG] Tabela prev_propostas verificada/criada.")
    except Exception as e:
        print(f"[LOG] Erro ao criar tabela prev_propostas: {e}")
        conn.rollback()


def Busca_Melnick(conn):
    import pandas as pd

    try:
        cur = conn.cursor()
        query = """
            WITH 

            -- CTE 1: STATUS APROVADOS
            STATUS_APROVADOS AS (
            SELECT ID FROM UNIT_PROPOSAL_STATUS WHERE NAME LIKE 'Aprovada%'
            ),

            -- CTE 2: PROPOSTAS APROVADAS (NÚCLEO FILTRADO)
            PROPOSTAS_APROVADAS AS (
            SELECT 
                I.ID AS PROPOSAL_ID,
                I.CUSTOMER_ID,
                I.UNIT_ID,
                COALESCE(STATUS_HISTORY.NAME, UNIT_PROPOSAL_STATUS.NAME) AS PROPOSTA_NAME,
                COALESCE(HIST.CREATED_AT, I.CREATED_AT) AS DATA
            FROM UNIT_PROPOSAL I
            JOIN UNIT_PROPOSAL_STATUS ON UNIT_PROPOSAL_STATUS.ID = I.STATUS_ID
            LEFT JOIN LATERAL (
                SELECT STATUS_ID, CREATED_AT
                FROM UNIT_PROPOSAL_HISTORY
                WHERE PROPOSAL_ID = I.ID AND I.STATUS_ID = '10'
                ORDER BY UPDATED_AT DESC
                LIMIT 1
            ) HIST ON I.STATUS_ID = '10'
            LEFT JOIN UNIT_PROPOSAL_STATUS STATUS_HISTORY ON STATUS_HISTORY.ID = HIST.STATUS_ID
            WHERE I.IS_HISTORIC = FALSE
                AND I.STATUS_ID NOT IN ('6')
                AND I.STATUS_ID IN (SELECT ID FROM STATUS_APROVADOS)
            ),

            -- CTE 3: PROCESSOS COM RESERVAS APROVADAS
            PROCESSOS_APROVADOS AS (
            SELECT DISTINCT
                CP.ID AS PROCESS_ID,
                CP.UNIT_ID,
                CPC.CUSTOMER_ID
            FROM CUSTOMER_PROCESS CP
            INNER JOIN CUSTOMER_PROCESS_CUSTOMER CPC ON CP.ID = CPC.CUSTOMER_PROCESS_ID
            INNER JOIN UNIT_BOOKING RESERVA ON CP.ID = RESERVA.CUSTOMER_PROCESS_ID
            INNER JOIN UNIT_BOOKING_STATUS STATUS_RESERVA ON RESERVA.UNIT_BOOKING_STATUS_ID = STATUS_RESERVA.ID
            WHERE STATUS_RESERVA.NAME = 'Aprovada'
            ),

            -- CTE 4: DADOS BASE (PROPOSTAS + PROCESSOS)
            DADOS_BASE AS (
            SELECT 
                PA.PROPOSAL_ID,
                PA.CUSTOMER_ID,
                PA.DATA,
                PA.PROPOSTA_NAME
            FROM PROPOSTAS_APROVADAS PA
            INNER JOIN PROCESSOS_APROVADOS PROC 
                ON PA.CUSTOMER_ID = PROC.CUSTOMER_ID 
                AND PA.UNIT_ID = PROC.UNIT_ID
            ),

            -- CTE 5: PAGAMENTOS
            PAGAMENTOS AS (
            SELECT 
                UPP.PROPOSAL_ID,
                SUM(UPP.VALUE * ARRAY_LENGTH(UPP.PAYMENT_DISTRIBUTION, 1)) AS PROPOSTA
            FROM UNIT_PROPOSAL_PAYMENT UPP
            WHERE UPP.HOLDER = 'customer'
                AND UPP.PROPOSAL_ID IN (SELECT PROPOSAL_ID FROM DADOS_BASE)
            GROUP BY UPP.PROPOSAL_ID
            ),

            -- CTE 6: CLIENTES VÁLIDOS (FILTRO TESTE)
            CLIENTES_VALIDOS AS (
            SELECT ID, REALTOR_ID
            FROM CUSTOMER
            WHERE NAME NOT LIKE '%TESTE%'
                AND ID IN (SELECT CUSTOMER_ID FROM DADOS_BASE)
            ),

            -- CTE 7: CORRETORES VÁLIDOS (FILTRO TESTE)
            CORRETORES_VALIDOS AS (
            SELECT ID
            FROM "user"
            WHERE NAME NOT LIKE '%TESTE%'
                AND ID IN (SELECT REALTOR_ID FROM CLIENTES_VALIDOS)
            )

            -- SELECT FINAL AGREGADO
            SELECT 
            (DB.DATA AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo')::DATE AS Data,
            SUM(CAST(PAG.PROPOSTA AS FLOAT)) AS Propostas
            FROM DADOS_BASE DB
            INNER JOIN PAGAMENTOS PAG ON PAG.PROPOSAL_ID = DB.PROPOSAL_ID
            INNER JOIN CLIENTES_VALIDOS CLIENTE ON CLIENTE.ID = DB.CUSTOMER_ID
            INNER JOIN CORRETORES_VALIDOS CORRETOR ON CORRETOR.ID = CLIENTE.REALTOR_ID
            WHERE DB.PROPOSTA_NAME LIKE 'Aprovada%'
            GROUP BY (DB.DATA AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo')::DATE
            ORDER BY Data DESC;
        """
        cur.execute(query)
        colunas = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return pd.DataFrame([list(row) for row in rows], columns=colunas)
    except Exception as e:
        print(f"[LOG] Erro ao buscar dados da query: {e}")
        return None
    finally:
        cur.close()


def insert_dados_Melnick(df, conn, table_name):
    import numpy as np
    from psycopg2.extras import execute_values

    cursor = conn.cursor()
    
    # TRUNCATE TABLE para deletar dados anteriores
    cursor.execute(f'TRUNCATE TABLE public.{table_name}')
    
    # Converter DataFrame para lista de tuplas
    df_clean = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    values = [tuple(row) for row in df_clean.values]
    
    # Colunas com aspas para colunas com maiúsculas
    colunas_tabela = {
        'data': 'data',
        'Previsao': '"Previsao"',
        'limite_inferior': 'limite_inferior',
        'limite_superior': 'limite_superior',
        'valor': 'valor',
        'Atualizacao': '"Atualizacao"'
    }
    columns = ', '.join([colunas_tabela.get(col, col) for col in df_clean.columns])
    
    # Usar execute_values para inserção em lote
    sql = f'INSERT INTO public.{table_name} ({columns}) VALUES %s'
    execute_values(cursor, sql, values)
    
    conn.commit()
    cursor.close()
    print(f"[LOG] Inseridas {len(values)} linhas em public.{table_name}.")


def insert_metricas_modelo(conn, modelo_nome, rmse, mae, mape):
    import pandas as pd

    cursor = conn.cursor()
    
    # Verificar se o modelo já existe na tabela
    cursor.execute("SELECT EXISTS(SELECT 1 FROM public.modelos_lineares WHERE \"modelo\" = %s)", (modelo_nome,))
    modelo_existe = cursor.fetchone()[0]
    
    # Deletar dados anteriores do modelo apenas se já existir
    if modelo_existe:
        cursor.execute("DELETE FROM public.modelos_lineares WHERE \"modelo\" = %s", (modelo_nome,))
    
    # Converter valores numpy para tipos Python nativos
    rmse_float = float(rmse) if rmse is not None else None
    mae_float = float(mae) if mae is not None else None
    mape_float = float(mape) if mape is not None else None
    
    # Inserir novas métricas
    cursor.execute("""
        INSERT INTO public.modelos_lineares ("modelo", rmse, mae, mape, atualizacao)
        VALUES (%s, %s, %s, %s, %s)
    """, (modelo_nome, rmse_float, mae_float, mape_float, pd.Timestamp.today()))
    
    conn.commit()
    cursor.close()
    print(f"[LOG] Métricas do modelo '{modelo_nome}' salvas em modelos_lineares.")


def executar_previsao_propostas(**context):
    """
    Função principal que será executada pela DAG do Airflow.
    Executa a previsão de propostas usando Prophet.
    """
    import os

    import holidays
    import numpy as np
    import pandas as pd
    from prophet import Prophet
    from prophet.diagnostics import cross_validation, performance_metrics
    from sklearn.metrics import mean_absolute_error, root_mean_squared_error

    try:
        print("=" * 60)
        print("INICIANDO PREVISÃO DE PROPOSTAS")
        print("=" * 60)
        
        # Conectar ao banco e criar tabela
        conn = connect_to_db_Melnick()
        if not conn:
            raise Exception("Não foi possível conectar ao banco de dados")
        
        print("[LOG] Criando/verificando tabela prev_propostas...")
        criar_tabela_prev_propostas(conn)
        
        # Buscar dados
        print("[LOG] Executando query de propostas aprovadas no Melnick...")
        df = Busca_Melnick(conn)
        conn.close()
        
        if df is None or df.empty:
            raise Exception("Nenhum dado foi retornado da consulta")
        
        print(f"[LOG] Total de registros encontrados: {len(df)}")
        
        # Processar dados
        df['data'] = pd.to_datetime(df['data'])
        df['propostas'] = pd.to_numeric(df['propostas'], errors='coerce')
        
        df['vlr_smooth'] = df['propostas'].rolling(window=7, center=True).mean()
        
        Q1 = df['vlr_smooth'].quantile(0.25)
        Q3 = df['vlr_smooth'].quantile(0.75)
        
        media = df['vlr_smooth'].mean()
        std = df['vlr_smooth'].std()
        
        limite_inferior = media - 2 * std
        limite_superior = media + 2 * std
        
        print(f"Q1: {Q1}, Q3: {Q3}, Limite Inferior: {limite_inferior}, Limite Superior: {limite_superior}")
        df = df[(df['vlr_smooth'] >= limite_inferior) & (df['vlr_smooth'] <= limite_superior)].copy()
        
        print(f"[LOG] Registros após filtro de outliers: {len(df)}")
        
        col_data = 'data'
        col_valor = 'vlr_smooth'
        anos = list(range(df[col_data].min().year, df[col_data].max().year + 1))
        feriados_br = holidays.Brazil(years=anos)
        df_feriados = pd.DataFrame([
            {'ds': pd.Timestamp(data), 'holiday': str(nome)}
            for data, nome in feriados_br.items()
        ])
        df_feriados = df_feriados.drop_duplicates(subset=['ds'], keep='first').reset_index(drop=True)
        
        # Preparar dados para Prophet (uma linha por data - Prophet não aceita ds duplicados)
        df_prophet = df[[col_data, col_valor]].rename(columns={col_data: 'ds', col_valor: 'y'}).copy()
        df_prophet['ds'] = pd.to_datetime(df_prophet['ds']).dt.tz_localize(None).dt.normalize()
        df_prophet = df_prophet.groupby('ds', as_index=False)['y'].mean()
        df_prophet = df_prophet.sort_values('ds').reset_index(drop=True)
        
        # Dividir treino e teste
        split_date = df_prophet['ds'].max() - pd.Timedelta(days=30)
        treino = df_prophet[df_prophet['ds'] <= split_date].copy()
        teste = df_prophet[df_prophet['ds'] > split_date].copy()
        treino = treino.drop_duplicates(subset=['ds'], keep='first').reset_index(drop=True)
        teste = teste.drop_duplicates(subset=['ds'], keep='first').reset_index(drop=True)
        
        # DataFrame novo a partir de arrays (evita índice/duplicate labels no Prophet com pandas 2.x)
        ds_arr = pd.to_datetime(treino['ds'].values)
        y_arr = np.asarray(treino['y'], dtype=float)
        treino_fit = pd.DataFrame({'ds': ds_arr, 'y': y_arr})
        
        # Fix compatibilidade Prophet + Pandas 2.x: garantias fortes antes do fit
        treino_fit = treino_fit.copy()
        treino_fit = treino_fit.drop_duplicates(subset=['ds'])
        treino_fit = treino_fit.sort_values('ds')
        treino_fit = treino_fit.reset_index(drop=True)
        treino_fit.index = pd.RangeIndex(start=0, stop=len(treino_fit), step=1)

        print(f"[LOG] Treino: {len(treino_fit)} datas | Teste: {len(teste)} datas")

        # Treinar modelo (lógica idêntica ao Previsao_Propostas_standalone.py)
        # Workaround pandas 3.x + Airflow: Prophet/crosstab gera reindex com índice alvo duplicado;
        # pandas 3 levanta "duplicate labels". Standalone costuma usar pandas 2.x (sem esse erro).
        # Patch em Index.reindex: se falhar, monta indexer com get_loc por label (comportamento alinhado ao esperado pelo groupby/crosstab).
        print("[LOG] Treinando modelo Prophet...")
        import pandas.core.indexes.base as _idx_base
        _index_reindex_orig = _idx_base.Index.reindex

        def _loc_to_int(loc):
            if isinstance(loc, slice):
                return int(loc.start) if loc.start is not None else 0
            if isinstance(loc, (np.ndarray, pd.Index, list, tuple)):
                arr = np.asarray(loc).ravel()
                return int(arr[0]) if arr.size else -1
            return int(loc)

        def _index_reindex_tolerant(self, target, *args, **kwargs):
            try:
                return _index_reindex_orig(self, target, *args, **kwargs)
            except ValueError as e:
                msg = str(e).lower()
                if "duplicate labels" not in msg and "duplicate" not in msg:
                    raise
                if target is None:
                    raise
                try:
                    positions = []
                    for t in target:
                        try:
                            loc = self.get_loc(t)
                            positions.append(_loc_to_int(loc))
                        except (KeyError, TypeError, ValueError):
                            positions.append(-1)
                    indexer = np.asarray(positions, dtype=np.intp)
                    return (target, indexer)
                except Exception:
                    raise e

        _idx_base.Index.reindex = _index_reindex_tolerant
        try:
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                seasonality_mode='multiplicative',
                changepoint_range=1.0,
                interval_width=0.6,
            )
            model.fit(treino_fit)
        finally:
            _idx_base.Index.reindex = _index_reindex_orig
        
        print("[LOG] Modelo treinado. Gerando previsões (180 períodos)...")
        
        # Fazer previsões
        future = model.make_future_dataframe(periods=180)
        forecast = model.predict(future)
        
        # Adiciona os valores reais ao forecast
        forecast = forecast.merge(
            df_prophet[['ds', 'y']],
            on='ds',
            how='left'
        )
        forecast.rename(columns={'y': 'valor_real'}, inplace=True)
        
        # Avaliação
        print("[LOG] Calculando métricas (MAE, RMSE, MAPE)...")
        previsao_teste = forecast[['ds', 'yhat']].set_index('ds').join(teste.set_index('ds'))[['yhat', 'y']].dropna()
        
        mae = mean_absolute_error(previsao_teste['y'], previsao_teste['yhat'])
        rmse = root_mean_squared_error(previsao_teste['y'], previsao_teste['yhat'])
        mape = np.mean(np.abs((previsao_teste['y'] - previsao_teste['yhat']) / previsao_teste['y'])) * 100
        
        print(f"[LOG] RMSE: {rmse:,.2f} | MAE: {mae:,.2f} | MAPE: {mape:.2f}%")
        
        # Salvar métricas na tabela modelos_lineares
        nome_modelo = os.path.splitext(os.path.basename(__file__))[0]
        print(f"[LOG] Salvando métricas do modelo '{nome_modelo}' em modelos_lineares...")
        conn_metricas = connect_to_db_Melnick()
        if not conn_metricas:
            raise RuntimeError("[LOG] Não foi possível conectar ao PostgreSQL para salvar métricas (modelos_lineares).")
        insert_metricas_modelo(conn_metricas, nome_modelo, rmse, mae, mape)
        conn_metricas.close()
        
        # Executar validação cruzada
        print("[LOG] Executando validação cruzada (initial=540d, period=30d, horizon=90d)...")
        df_cv = cross_validation(
            model,
            initial='540days',
            period='30 days',
            horizon='90 days'
        )
        
        # Ver métricas da validação cruzada
        df_metrics = performance_metrics(df_cv)
        print("[LOG] Validação cruzada concluída.")
        
        # Preparar resultado final
        print("[LOG] Montando resultado final e gravando em prev_propostas...")
        df_resultado = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper', 'valor_real']].rename(columns={
            'ds': 'data',
            'yhat': 'previsao',
            'yhat_lower': 'limite_inferior',
            'yhat_upper': 'limite_superior',
            'valor_real': 'valor'
        })
        
        colunas_float = ['previsao', 'limite_inferior', 'limite_superior', 'valor']
        df_resultado[colunas_float] = df_resultado[colunas_float].round(4)
        
        # Garantir tipo float explícito
        for col in colunas_float:
            df_resultado[col] = df_resultado[col].astype(float)
        
        df_resultado['atualizacao'] = pd.Timestamp.today()
        df_resultado = df_resultado.replace({np.nan: None})
        df_resultado = df_resultado.replace([np.inf, -np.inf], np.nan)
        df_resultado = df_resultado.replace({np.nan: None})
        df_resultado['data'] = pd.to_datetime(df_resultado['data']).dt.date
        
        # Inserir dados no banco
        print(f"[LOG] Inserindo {len(df_resultado)} linhas em prev_propostas...")
        conn_insert = connect_to_db_Melnick()
        if not conn_insert:
            raise RuntimeError("[LOG] Não foi possível conectar ao PostgreSQL para inserir em prev_propostas.")
        insert_dados_Melnick(df_resultado, conn_insert, 'prev_propostas')
        conn_insert.close()
        
        print("=" * 60)
        print("[LOG] PREVISÃO DE PROPOSTAS CONCLUÍDA COM SUCESSO")
        print("=" * 60)
        
    except Exception as e:
        print("=" * 60)
        print(f"[LOG] ERRO ao executar previsão de propostas: {e}")
        print("=" * 60)
        import traceback
        print(traceback.format_exc())
        raise


# Timezone do Brasil
tz_brasil = pytz.timezone('America/Sao_Paulo')

with DAG(
    'Previsao_Propostas',
    default_args=default_args,
    description='DAG de previsão de propostas (disparada pela Atualiza_PostgreSQL)',
    schedule=None,  # Só executa quando disparada pelo TriggerDagRunOperator da Atualiza_PostgreSQL
    start_date=tz_brasil.localize(datetime(2025, 12, 2)),
    catchup=False,
    max_active_runs=1,
    tags=['Previsao_Propostas'],
) as dag:

    # Task principal que executa a previsão
    executar_previsao = PythonOperator(
        task_id='executar_previsao_propostas',
        python_callable=executar_previsao_propostas,
        dag=dag
    )

