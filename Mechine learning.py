
import pyodbc
import pandas as pd
import numpy as np
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
pd.set_option('display.max_columns', None)
pd.set_option('display.expand_frame_repr', False)
# ATENÇÃO!!! CÓDICO CADASTRADO PARA RODAR AUTOMATICAMENTE NO AGENDADOR



def connect_to_db_Melnick():
    try:
        conn_sqlserver = pyodbc.connect(
            'Driver={SQL Server};'
            'Server=SRSBDOTTOHML01;'
            'Database=Otto;'
            'uid=sa;'
            r'pwd=)a:8\H\g@YyY$19e3<'
        )
        return conn_sqlserver
    except Exception as e:
        print("Erro ao conectar ao banco de dados:", e)
        return None

def Busca_Melnick(conn_sqlserver, table_name):
    try:
        cur = conn_sqlserver.cursor()
        query = f"""
        SELECT top 29181 Empreendimento, Imobiliaria, Data, Status FROM {table_name}
         WHERE Empreendimento NOT LIKE '%dação%'
          AND Empreendimento NOT LIKE '%dações%'
          AND Empreendimento NOT LIKE '%prime%'
          AND Empreendimento NOT LIKE '%locação%'
          AND Empreendimento NOT LIKE '%revenda%'
          AND Empreendimento NOT LIKE '%prontos%'
          AND Empreendimento NOT LIKE '%melnick%'
          AND Empreendimento NOT LIKE '%special%'
         
         Order by Data asc"""
        cur.execute(query)
        rows = cur.fetchall()
        return rows

    except Exception as e:
        print(f"Erro ao buscar dados da tabela {table_name}:", e)
        return None
    finally:
        cur.close()

table_name = "Pesquisas"
DBMelnick = connect_to_db_Melnick()
df = pd.DataFrame( np.array(Busca_Melnick(DBMelnick,table_name)))
df.columns = [ 'empreendimento', 'imobiliária','data', 'status']
print(df.columns)
print(df.head())

# Passo 1: Agrupar por data, empreendimento e imobiliária
grouped = (
    df.groupby(['data', 'empreendimento', 'imobiliária'])
    .size()
    .reset_index(name='pesquisas')  # Isso cria a coluna 'pesquisas'
)

# Passo 2: Gerar um dataframe com TODAS as datas para CADA combinação
todos_grupos = grouped[['empreendimento', 'imobiliária']].drop_duplicates()
datas_completas = pd.date_range(grouped['data'].min(), grouped['data'].max(), freq='D')
full_index = (
    todos_grupos.assign(key=1)
    .merge(pd.DataFrame({'data': datas_completas, 'key': 1}), on='key')
    .drop('key', axis=1)
)

full_data = full_index.merge(grouped, on=['data', 'empreendimento', 'imobiliária'], how='left').fillna({'pesquisas': 0})

# Passo 3: Loop por cada grupo para prever
resultados = []
metricas = []

for (emp, imob), grupo in full_data.groupby(['empreendimento', 'imobiliária']):
    df_prophet = grupo[['data', 'pesquisas']].rename(columns={'data': 'ds', 'pesquisas': 'y'})

    # Separar treino e teste
    df_prophet = df_prophet.sort_values('ds')
    split_date = df_prophet['ds'].max() - pd.Timedelta(days=30)
    treino = df_prophet[df_prophet['ds'] <= split_date]
    teste = df_prophet[df_prophet['ds'] > split_date]

    model = Prophet(daily_seasonality=True)
    model.fit(treino)

    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)

    # Previsões para o mesmo período de teste
    previsao_teste = forecast[['ds', 'yhat']].set_index('ds').join(teste.set_index('ds'))[['yhat', 'y']].dropna()

    # Calcular métricas
    mae = mean_absolute_error(previsao_teste['y'], previsao_teste['yhat'])
    rmse = np.sqrt(mae)

    metricas.append({
        'empreendimento': emp,
        'imobiliaria': imob,
        'mae': mae,
        'rmse': rmse
    })

    forecast['empreendimento'] = emp
    forecast['imobiliária'] = imob

    resultados.append(forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper', 'empreendimento', 'imobiliária']])

# Concatenar todos os resultados
df_resultado = pd.concat(resultados).rename(columns={'ds': 'data', 'yhat': 'previsao',
                                                     'yhat_lower': 'limite_inferior',
                                                     'yhat_upper': 'limite_superior'})
df_resultado.to_csv(r'E:\Projetos\previsao_pesquisas.txt', sep=';', index=False)
print(df_resultado.head())
