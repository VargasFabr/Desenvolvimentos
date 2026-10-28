from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
#  dag
# Definindo argumentos padrão para a DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Definindo a DAG
dag = DAG(
    'teste_arquivo_txt',
    default_args=default_args,
    description='DAG simples para salvar arquivo txt com texto teste',
    schedule_interval=timedelta(days=1),  # Executa diariamente
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['teste'],
)

# Função que será executada pela tarefa
def salvar_arquivo_txt():
    """
    Função que salva um arquivo txt com o texto 'teste' na pasta atual
    """
    # Define o caminho do arquivo
    caminho_arquivo = os.path.join(os.getcwd(), 'teste.txt')
    
    # Salva o arquivo com o texto 'teste'
    with open(caminho_arquivo, 'w', encoding='utf-8') as arquivo:
        arquivo.write('teste')
    
    print(f'Arquivo salvo com sucesso em: {caminho_arquivo}')

# Definindo a tarefa
tarefa_salvar_arquivo = PythonOperator(
    task_id='salvar_arquivo_txt',
    python_callable=salvar_arquivo_txt,
    dag=dag,
)

# A tarefa está definida e pronta para ser executada pelo Airflow

