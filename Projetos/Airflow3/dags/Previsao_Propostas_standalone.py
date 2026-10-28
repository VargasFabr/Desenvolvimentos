# %%
"""
Previsão de Propostas — versão standalone (sem Airflow).
Execute fora do ambiente Airflow. Mantém as mesmas funções da DAG Previsao_Propostas.

Uso:
  python Previsao_Propostas_standalone.py

Conexão PostgreSQL: variáveis no .env da raiz do repo (Desenvolvimentos/.env).
"""
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import holidays
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve()
    for p in [_root.parents[i] / ".env" for i in range(1, 6)]:
        if p.is_file():
            load_dotenv(p)
            break
    else:
        load_dotenv()
except ImportError:
    pass

# ==================== CONFIGURAÇÃO DE CONEXÃO ====================

def _get_connection_params():
    """Parâmetros a partir do .env central (OTTO_* ou POSTGRES_*)."""
    password = (
        os.getenv("OTTO_DB_PASSWORD")
        or os.getenv("OTTO_DB_PASS")
        or os.getenv("POSTGRES_PASSWORD")
        or os.getenv("POSTGRES_PASS")
        or ""
    )
    if not password:
        raise RuntimeError("Defina OTTO_DB_PASSWORD ou POSTGRES_PASSWORD no .env da raiz")
    return {
        "host": os.getenv("OTTO_DB_HOST") or os.getenv("POSTGRES_HOST") or "localhost",
        "port": os.getenv("OTTO_DB_PORT") or os.getenv("POSTGRES_PORT") or "5432",
        "dbname": os.getenv("OTTO_DB_NAME") or os.getenv("POSTGRES_DB") or "otto",
        "user": os.getenv("OTTO_DB_USER") or os.getenv("POSTGRES_USER") or "postgres",
        "password": password,
    }


def connect_to_db_Melnick():
    """Conecta ao PostgreSQL usando variáveis de ambiente (sem Airflow)."""
    try:
        params = _get_connection_params()
        conn = psycopg2.connect(**params)
        return conn
    except Exception as e:
        print("Erro ao conectar ao banco de dados:", e)
        return None


# ==================== FUNÇÕES AUXILIARES ====================

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
    except Exception as e:
        print(f"Erro ao criar tabela prev_propostas: {e}")
        conn.rollback()


def Busca_Melnick(conn):
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
        print(f"Erro ao buscar dados da query", e)
        return None
    finally:
        cur.close()


def insert_dados_Melnick(df, conn, table_name):
    cursor = conn.cursor()
    
    cursor.execute(f'TRUNCATE TABLE public.{table_name}')
    
    df_clean = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    values = [tuple(row) for row in df_clean.values]
    
    colunas_tabela = {
        'data': 'data',
        'Previsao': '"Previsao"',
        'limite_inferior': 'limite_inferior',
        'limite_superior': 'limite_superior',
        'valor': 'valor',
        'Atualizacao': '"Atualizacao"'
    }
    columns = ', '.join([colunas_tabela.get(col, col) for col in df_clean.columns])
    
    sql = f'INSERT INTO public.{table_name} ({columns}) VALUES %s'
    execute_values(cursor, sql, values)
    
    conn.commit()
    cursor.close()


def insert_metricas_modelo(conn, modelo_nome, rmse, mae, mape):
    cursor = conn.cursor()
    
    cursor.execute("SELECT EXISTS(SELECT 1 FROM public.modelos_lineares WHERE \"modelo\" = %s)", (modelo_nome,))
    modelo_existe = cursor.fetchone()[0]
    
    if modelo_existe:
        cursor.execute("DELETE FROM public.modelos_lineares WHERE \"modelo\" = %s", (modelo_nome,))
    
    rmse_float = float(rmse) if rmse is not None else None
    mae_float = float(mae) if mae is not None else None
    mape_float = float(mape) if mape is not None else None
    
    cursor.execute("""
        INSERT INTO public.modelos_lineares ("modelo", rmse, mae, mape, atualizacao)
        VALUES (%s, %s, %s, %s, %s)
    """, (modelo_nome, rmse_float, mae_float, mape_float, pd.Timestamp.today()))
    
    conn.commit()
    cursor.close()


# ==================== FUNÇÃO PRINCIPAL ====================

def executar_previsao_propostas():
    """Executa a previsão de propostas usando Prophet (lógica idêntica à DAG)."""
    try:
        print("=" * 60)
        print("INICIANDO PREVISÃO DE PROPOSTAS (standalone)")
        print("=" * 60)
        
        conn = connect_to_db_Melnick()
        if not conn:
            raise Exception("Não foi possível conectar ao banco de dados")
        
        criar_tabela_prev_propostas(conn)
        
        df = Busca_Melnick(conn)
        conn.close()
        
        if df is None or df.empty:
            raise Exception("Nenhum dado foi retornado da consulta")
        
        print(f"Total de registros encontrados: {len(df)}")
        
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
        
        print(f"Registros após filtro: {len(df)}")
        
        col_data = 'data'
        col_valor = 'vlr_smooth'
        anos = list(range(df[col_data].min().year, df[col_data].max().year + 1))
        feriados_br = holidays.Brazil(years=anos)
        df_feriados = pd.DataFrame([
            {'ds': pd.Timestamp(data), 'holiday': str(nome)}
            for data, nome in feriados_br.items()
        ])
        df_feriados = df_feriados.drop_duplicates(subset=['ds'], keep='first').reset_index(drop=True)
        
        df_prophet = df[[col_data, col_valor]].rename(columns={col_data: 'ds', col_valor: 'y'}).copy()
        df_prophet['ds'] = pd.to_datetime(df_prophet['ds']).dt.tz_localize(None).dt.normalize()
        df_prophet = df_prophet.groupby('ds', as_index=False)['y'].mean()
        df_prophet = df_prophet.sort_values('ds').reset_index(drop=True)
        
        split_date = df_prophet['ds'].max() - pd.Timedelta(days=30)
        treino = df_prophet[df_prophet['ds'] <= split_date].copy()
        teste = df_prophet[df_prophet['ds'] > split_date].copy()
        treino = treino.drop_duplicates(subset=['ds'], keep='first').reset_index(drop=True)
        teste = teste.drop_duplicates(subset=['ds'], keep='first').reset_index(drop=True)
        
        ds_arr = pd.to_datetime(treino['ds'].values)
        y_arr = np.asarray(treino['y'], dtype=float)
        treino_fit = pd.DataFrame({'ds': ds_arr, 'y': y_arr})
        
        treino_fit = treino_fit.copy()
        treino_fit = treino_fit.drop_duplicates(subset=['ds'])
        treino_fit = treino_fit.sort_values('ds')
        treino_fit = treino_fit.reset_index(drop=True)
        treino_fit.index = pd.RangeIndex(start=0, stop=len(treino_fit), step=1)
        
        print(f"Registros de treino: {len(treino_fit)}, Registros de teste: {len(teste)}")
        
        print("Treinando modelo Prophet...")
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            seasonality_mode='multiplicative',
            changepoint_range=1.0,
            interval_width=0.6,
        )
        model.fit(treino_fit)
        
        print("Gerando previsões...")
        future = model.make_future_dataframe(periods=180)
        forecast = model.predict(future)
        
        forecast = forecast.merge(
            df_prophet[['ds', 'y']],
            on='ds',
            how='left'
        )
        forecast.rename(columns={'y': 'valor_real'}, inplace=True)
        
        previsao_teste = forecast[['ds', 'yhat']].set_index('ds').join(teste.set_index('ds'))[['yhat', 'y']].dropna()
        
        mae = mean_absolute_error(previsao_teste['y'], previsao_teste['yhat'])
        rmse = root_mean_squared_error(previsao_teste['y'], previsao_teste['yhat'])
        mape = np.mean(np.abs((previsao_teste['y'] - previsao_teste['yhat']) / previsao_teste['y'])) * 100
        
        print(f"RMSE: {rmse:,.2f}")
        print(f"MAE:  {mae:,.2f}")
        print(f"MAPE: {mape:.2f}%")
        
        nome_modelo = os.path.splitext(os.path.basename(__file__))[0]
        conn_metricas = connect_to_db_Melnick()
        if conn_metricas:
            insert_metricas_modelo(conn_metricas, nome_modelo, rmse, mae, mape)
            conn_metricas.close()
        
        print("Executando validação cruzada...")
        df_cv = cross_validation(
            model,
            initial='540days',
            period='30 days',
            horizon='90 days'
        )
        
        df_metrics = performance_metrics(df_cv)
        
        df_resultado = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper', 'valor_real']].rename(columns={
            'ds': 'data',
            'yhat': 'previsao',
            'yhat_lower': 'limite_inferior',
            'yhat_upper': 'limite_superior',
            'valor_real': 'valor'
        })
        
        colunas_float = ['previsao', 'limite_inferior', 'limite_superior', 'valor']
        df_resultado[colunas_float] = df_resultado[colunas_float].round(4)
        
        for col in colunas_float:
            df_resultado[col] = df_resultado[col].astype(float)
        
        df_resultado['atualizacao'] = pd.Timestamp.today()
        df_resultado = df_resultado.replace({np.nan: None})
        df_resultado = df_resultado.replace([np.inf, -np.inf], np.nan)
        df_resultado = df_resultado.replace({np.nan: None})
        df_resultado['data'] = pd.to_datetime(df_resultado['data']).dt.date
        
        print("Inserindo resultados no banco de dados...")
        conn_insert = connect_to_db_Melnick()
        if conn_insert:
            insert_dados_Melnick(df_resultado, conn_insert, 'prev_propostas')
            conn_insert.close()
        
        print("=" * 60)
        print("PREVISÃO DE PROPOSTAS CONCLUÍDA COM SUCESSO")
        print("=" * 60)
        
    except Exception as e:
        print("=" * 60)
        print(f"ERRO ao executar previsão de propostas: {e}")
        print("=" * 60)
        import traceback
        print(traceback.format_exc())
        raise


if __name__ == '__main__':
    executar_previsao_propostas()
