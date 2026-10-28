# ==================== IMPORTS DO AIRFLOW ====================
from datetime import datetime, timedelta
import os
import warnings

import numpy as np
import pandas as pd
import pytz

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

from imblearn.over_sampling import SMOTE
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
warnings.filterwarnings('ignore')

# ==================== CONFIGURAÇÃO DA DAG ====================
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

tz_brasil = pytz.timezone('America/Sao_Paulo')

dag = DAG(
    'Prev_Propostas_Aprovacao',
    default_args=default_args,
    description='DAG para prever aprovação de propostas usando Machine Learning',
    schedule=None,
    max_active_runs=1,
    start_date=tz_brasil.localize(datetime(2025, 1, 1)),
    catchup=False,
    tags=['Machine_Learning', 'Previsao_Propostas'],
)




def connect_to_db_Otto():
    try:
        # Usa PostgresHook do Airflow com a conexão 'postgres'
        hook = PostgresHook(postgres_conn_id="postgres")
        conn = hook.get_conn()
        return conn
    except Exception as e:
        print("Erro ao conectar ao banco de dados:", e)
        return None

# %%
def Busca_Otto(conn, table_name):
    try:
        cur = conn.cursor()
        query = f"""
                    SELECT * FROM {table_name}
                    
                    """
        cur.execute(query)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]  # Obter as colunas logo após a execução da consulta
        return rows, columns
    except Exception as e:
        print(f"Erro ao buscar dados da tabela {table_name}:", e)
        return None, None
    finally:
        cur.close()
        conn.close()


def executar_previsao_propostas():
    print("=" * 60)
    print("INICIANDO PIPELINE DE PREVISÃO DE PROPOSTAS")
    print("=" * 60)

    linhas, colunas = Busca_Otto(connect_to_db_Otto(), "Financiamento_propostas")
    linhas2, colunas2 = Busca_Otto(connect_to_db_Otto(), "propostas")

    df = pd.DataFrame(linhas, columns=colunas)
    df2 = pd.DataFrame(linhas2, columns=colunas2)

    df3 = df2[['Área', 'codempreendimento', 'comissao', 'data', 'desconto_nominal', 'id_proposta',
     'perda_vpl', 'preÇo_tabela', 'proposta', 'quartos', 'status_proposta']].copy()

    df_final = df.merge(df3, left_on='proposal_id', right_on='id_proposta', how='inner')
    df_final = df_final.drop(columns=['total_proposta','proposal_id'])

    # Transformar status_proposta em valores numéricos
    def categorizar_status(status):
        status_lower = str(status).lower()
        
        # Aprovada → 1
        if status_lower.startswith('aprovada'):
            return 1
        # Não aprovada → 0
        elif 'não aprovada' in status_lower or 'nao aprovada' in status_lower:
            return 0
        # Em alteração, Em análise, Aguardando → 2
        elif status_lower.startswith('aguardando') or 'em alteração' in status_lower or 'em análise' in status_lower or 'em analise' in status_lower:
            return 2
        else:
            return 3  # default para casos não previstos

    df_final['status_proposta'] = df_final['status_proposta'].apply(categorizar_status)

    colunas_numericas = [ 'af', 'ato', 'dação', 'fgts','financiamento' ,'mensais', 'mensais-af', 'opção_de_dação',
               'reforço', 'reforço-anual-af', 'reforço-semestral-af', 'registro-itbi-af', 'subsídio','percentual_ato', 'percentual_financiamento', 'percentual_reforco',
               'Área', 'codempreendimento', 'comissao', 'desconto_nominal', 'preÇo_tabela', 'status_proposta']

    for col in colunas_numericas:
        df_final[col] = pd.to_numeric(df_final[col], errors='coerce')

    # Conversão de datas
    for c in [ 'data']:
        df_final[c] = pd.to_datetime(df_final[c], errors='coerce')

    df_final['ano_venda'] = (df_final['data'].dt.year).astype(int)
    df_final['mes_venda'] = (df_final['data'].dt.month).astype(int)
    df_final['trimestre_venda'] = (df_final['data'].dt.quarter).astype(int)
    df_final['semana_venda'] = (df_final['data'].dt.isocalendar().week).astype(int)

    def preencher_preco_por_empreendimento(df, coluna_preco='preÇo_tabela', coluna_grupo='codempreendimento', verbose=True):
        """
        Preenche valores 0 ou NaN na coluna de preço com a média do empreendimento.
        """
        df = df.copy()
        
        # Contar antes
        zeros_antes = (df[coluna_preco] == 0).sum()
        nulos_antes = df[coluna_preco].isna().sum()
        
        if verbose:
            print(f"Antes: {zeros_antes} zeros, {nulos_antes} nulos")
        
        # Substituir 0 por NaN
        df[coluna_preco] = df[coluna_preco].replace(0, np.nan)
        
        # Calcular média por empreendimento
        media_por_empreendimento = df.groupby(coluna_grupo)[coluna_preco].transform('mean')
        
        # Preencher NaN com a média do empreendimento
        df[coluna_preco] = df[coluna_preco].fillna(media_por_empreendimento)
        
        # Contar depois
        zeros_depois = (df[coluna_preco] == 0).sum()
        nulos_depois = df[coluna_preco].isna().sum()
        
        if verbose:
            print(f"Depois: {zeros_depois} zeros, {nulos_depois} nulos")
            
            # Se ainda houver nulos, são empreendimentos sem nenhum preço válido
            if nulos_depois > 0:
                print(f"\n⚠️ {nulos_depois} registros sem preenchimento (empreendimentos sem preço válido)")
        
        df['percentual_proposta'] = df['proposta'] / df['preÇo_tabela']
        return df
    
    df_final = preencher_preco_por_empreendimento(df_final)

    df_final = df_final.dropna()

    df_final.drop(columns=['data', 'reforço-semestral-af','fgts','registro-itbi-af','subsídio'], errors='ignore',inplace=True)

    # 1. Remover todas as linhas com status_proposta = 3
    df_final_limpo = df_final[df_final['status_proposta'] != 3].copy()

    # 2. df_projecao: apenas linhas com status_proposta = 2 (Em análise/Aguardando)
    df_projecao = df_final_limpo[df_final_limpo['status_proposta'] == 2].copy()
    df_projecao = df_projecao[df_projecao['ano_venda'] >= 2026]
    # 3. df_treino: apenas linhas com status_proposta = 0 ou 1 (Não aprovada e Aprovada)
    df_treino = df_final_limpo[df_final_limpo['status_proposta'].isin([0, 1])].copy()

    target = 'status_proposta'

    # Lista de colunas para remover (adicione aqui as colunas que você quer remover)
    colunas_para_remover = [target, 'id_proposta']  # Exemplo: removendo target e id_proposta

    X = df_treino.drop(colunas_para_remover, axis=1, errors='ignore')  # errors='ignore' evita erro se coluna não existir
    y = df_treino[target]

    # Separar variáveis numéricas e categóricas
    num_cols = X.select_dtypes(include=['int64', 'float64']).columns

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    smote = SMOTE(random_state=42)
    X_train_res, y_train_res = smote.fit_resample(X_train, y_train)

    preprocess = ColumnTransformer([
        ('num', StandardScaler(), num_cols)
    ])

    xgb = XGBClassifier(
        objective='binary:logistic',
        eval_metric='auc',
        random_state=42,
        n_jobs=-1
    )

    param_grid = { 'clf__max_depth': [3, 5, 7, 9],
                   'clf__n_estimators': [200,500],
                     'clf__learning_rate': [0.01, 0.03, 0.05, 0.1],
                       'clf__subsample': [0.8], 
                       'clf__colsample_bytree': [0.8],
                         'clf__scale_pos_weight': [2.5, 3] }

    pipe = Pipeline([
        ('prep', preprocess),
        ('clf', xgb)
    ])

    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    grid = GridSearchCV(
        pipe,
        param_grid=param_grid,
        scoring='roc_auc',
        cv=cv,
        n_jobs=-1,
        verbose=2
    )

    grid.fit(X_train_res, y_train_res)

    best_model = grid.best_estimator_

    y_pred = best_model.predict(X_test)
    y_prob = best_model.predict_proba(X_test)[:, 1]

    # 3. gerar previsões
    y_pred_novos = best_model.predict(df_projecao)
    y_prob_novos = best_model.predict_proba(df_projecao)[:, 1]

    # 4. salvar
    df_projecao['Prob_Aprovacao'] = y_prob_novos
    df_projecao['Prev_Aprovacao'] = y_pred_novos

    # Preparar dados para inserir no PostgreSQL
    df_postgres = pd.DataFrame({
        'id_proposta': df_projecao['id_proposta'].astype(str),
        'Prev_Aprovacao': df_projecao['Prev_Aprovacao'].astype(str),
        'Prob_Aprovacao': df_projecao['Prob_Aprovacao'].astype(float)
    })
    df_postgres.drop_duplicates(inplace=True)
    def inserir_dados_postgres(df, tabela='prev_propostas_aprov'):
        """
        Conecta ao banco PostgreSQL, limpa a tabela e insere novos dados
        """
        conn = None
        try:
            # 1. Conectar ao banco
            conn = connect_to_db_Otto()
            if conn is None:
                print("❌ Erro: Não foi possível conectar ao banco de dados")
                return False
            
            cur = conn.cursor()
            print("✅ Conectado ao banco de dados")
            
            # 2. Verificar se a tabela existe e limpar
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{tabela}'
                );
            """)
            tabela_existe = cur.fetchone()[0]
            
            if tabela_existe:
                cur.execute(f"DELETE FROM {tabela};")
                print(f"🗑️  Tabela '{tabela}' limpa com sucesso")
            else:
                # Criar tabela se não existir
                cur.execute(f"""
                    CREATE TABLE {tabela} (
                        id_proposta TEXT,
                        prev_aprovacao TEXT,
                        prob_aprovacao NUMERIC
                    );
                """)
                print(f"📋 Tabela '{tabela}' criada com sucesso")
            
            # 3. Inserir dados
            registros_inseridos = 0
            for idx, row in df.iterrows():
                cur.execute(f"""
                    INSERT INTO {tabela} (id_proposta, prev_aprovacao, prob_aprovacao)
                    VALUES (%s, %s, %s)
                """, (row['id_proposta'], row['Prev_Aprovacao'], row['Prob_Aprovacao']))
                registros_inseridos += 1
            
            # 4. Commit
            conn.commit()
            print(f"✅ {registros_inseridos} registros inseridos com sucesso!")
            
            # 5. Verificar inserção
            cur.execute(f"SELECT COUNT(*) FROM {tabela};")
            total = cur.fetchone()[0]
            print(f"📊 Total de registros na tabela: {total}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao inserir dados: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                cur.close()
                conn.close()
                print("🔌 Conexão fechada")

    ok = inserir_dados_postgres(df_postgres)
    if not ok:
        raise RuntimeError("Falha ao inserir dados na tabela prev_propostas_aprov.")


# ==================== DEFINIR TASK ====================
task_executar_previsao = PythonOperator(
    task_id='executar_previsao_propostas',
    python_callable=executar_previsao_propostas,
    dag=dag,
)
