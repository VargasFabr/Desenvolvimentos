# %%
import pandas as pd
import numpy as np
import pyodbc
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import holidays
from prophet.plot import plot_cross_validation_metric
from sklearn.metrics import mean_absolute_error,root_mean_squared_error


def connect_to_db_Melnick():
    try:

        conn_sqlserver = pyodbc.connect(
            'Driver={SQL Server};'
            'Server=SRSBDOTTOPRD01;'
            'Database=Melnick;'
            'Trusted_Connection=yes;'
        )
        return conn_sqlserver
    except Exception as e:
        print("Erro ao conectar ao banco de dados:", e)
        return None


def connect_to_db_Otto():
    try:

        conn_sqlserver = pyodbc.connect(
            'Driver={SQL Server};'
            'Server=SRSBDOTTOPRD01;'
            'Database=Otto;'
            'Trusted_Connection=yes;'
        )
        return conn_sqlserver
    except Exception as e:
        print("Erro ao conectar ao banco de dados:", e)
        return None

def Busca_Melnick(conn_sqlserver):
    try:

        cur = conn_sqlserver.cursor()
        query = (f"""
        SELECT 
		Data_only as Data,
		sum(Proposta) as Propostas

        from [dbo].[Propostas]

		where Status_Proposta like 'Aprovada%'
		and Status_Reserva ='Aprovada'

        group by Data_only
        order by Data_only desc



        """)
        cur.execute(query)
        colunas = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return pd.DataFrame([list(row) for row in rows], columns = colunas)

    except Exception as e:
        print(f"Erro ao buscar dados da query", e)
        return None
    finally:
        cur.close()

def insert_dados_Melnick(df, conn_sqlserver, table_name):
    cursor = conn_sqlserver.cursor()

    for index, row in df.iterrows():
        # Converter NaN para None
        row = row.where(pd.notnull(row), None)
        # Construir e executar a query
        placeholders = ', '.join(['?'] * len(row))
        columns = ', '.join(row.index)
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(row))

    # Comitar as transações
    conn_sqlserver.commit()

    # Fechar cursor e conexão
    cursor.close()
    conn_sqlserver.close()

df = Busca_Melnick(connect_to_db_Otto())

df['Data'] = pd.to_datetime(df['Data'])
df['Propostas'] = pd.to_numeric(df['Propostas'], errors='coerce')

df['vlr_smooth'] = df['Propostas'].rolling(window=7, center=True).mean()
# df['vlr_smooth1'] = df['vlr'].ewm(span=7, adjust=False).mean()
# df['vlr_smooth2'] = df['vlr'].rolling(window=7, center=True).median()

Q1 = df['vlr_smooth'].quantile(0.25)
Q3 = df['vlr_smooth'].quantile(0.75)

media = df['vlr_smooth'].mean()
std = df['vlr_smooth'].std()

limite_inferior = media - 2 * std
limite_superior = media + 2 * std

print(Q1, Q3,  limite_inferior,limite_superior)
df = df[(df['vlr_smooth'] >= limite_inferior) & (df['vlr_smooth'] <= limite_superior)].copy()

col_data = 'Data'
col_valor = 'vlr_smooth'
anos = list(range(df[col_data].min().year, df[col_data].max().year + 1))
feriados_br = holidays.Brazil(years=anos)
df_feriados = pd.DataFrame([
    {'ds': data, 'holiday': nome}
    for data, nome in feriados_br.items()
])
# === LOOP DE PREVISÃO POR GRUPO ===
resultados = []
metricas = []


df_prophet = df[[col_data, col_valor]].rename(columns={col_data: 'ds', col_valor: 'y'}).copy()
df_prophet = df_prophet.sort_values('ds')


# Dividir treino e teste
split_date = df_prophet['ds'].max() - pd.Timedelta(days=30)
treino = df_prophet[df_prophet['ds'] <= split_date]
teste = df_prophet[df_prophet['ds'] > split_date]


model = Prophet(yearly_seasonality = True, seasonality_mode = 'multiplicative',holidays=df_feriados,
                 changepoint_range= 1.0,interval_width= 0.6)
model.fit(treino)

future = model.make_future_dataframe(periods=180)
forecast = model.predict(future)

# === Adiciona os valores reais (y) ao forecast, para os dias em que temos dados históricos ===
forecast = forecast.merge(
    df_prophet[['ds', 'y']],  # df_prophet tem os dados reais
    on='ds',
    how='left'
)
forecast.rename(columns={'y': 'valor_real'}, inplace=True)
# Avaliação
previsao_teste = forecast[['ds', 'yhat']].set_index('ds').join(teste.set_index('ds'))[['yhat', 'y']].dropna()

mae = mean_absolute_error(previsao_teste['y'], previsao_teste['yhat'])
rmse = root_mean_squared_error(previsao_teste['y'], previsao_teste['yhat'])
mape = np.mean(np.abs((previsao_teste['y'] - previsao_teste['yhat']) / previsao_teste['y'])) * 100


metricas = {'mae': mae, 'rmse': rmse, 'mape': mape}
print(f"RMSE: {rmse:,.2f}")
print(f"MAE:  {mae:,.2f}")
print(f"MAPE: {mape:.2f}%")
model.changepoints

# Executar validação cruzada
df_cv = cross_validation(
    model,
    initial='540days',  # Usa pelo menos 1 ano de dados para treino
    period='30 days',  # A cada x meses, faz uma nova previsão
    horizon='90 days'  # Testa previsões de x meses
)

# Ver métricas da validação cruzada
df_metrics = performance_metrics(df_cv)

df_resultado = forecast[['ds','yhat','yhat_lower',"yhat_upper","valor_real"]].rename(columns={
    'ds': 'data',
    'yhat': 'Previsao',
    'yhat_lower': 'limite_inferior',
    'yhat_upper': 'limite_superior',
    'valor_real': 'valor'
})

colunas_float = ['Previsao', 'limite_inferior', 'limite_superior', 'valor']
df_resultado[colunas_float] = df_resultado[colunas_float].round(4)
# Garantir tipo float explícito
for col in colunas_float:
    df_resultado[col] = df_resultado[col].astype(float)
df_resultado['Atualizacao'] = pd.Timestamp.today()
df_resultado = df_resultado.replace({np.nan: None})

df_resultado.replace([np.inf, -np.inf], np.nan, inplace=True)

insert_dados_Melnick(df_resultado, connect_to_db_Melnick(), 'Prev_Propostas')