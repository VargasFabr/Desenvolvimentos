from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
}

with DAG(
    'orquestrador_principal',
    default_args=default_args,
    description='Orquestra execução de DAGs em sequência',
    schedule=None,  # Airflow 3 usa 'schedule' ao invés de 'schedule_interval'
    start_date=datetime(2025, 12, 1),
    catchup=False,
    tags=['orquestrador'],
) as dag:

    # Executa primeira DAG
    executar_dag1 = TriggerDagRunOperator(
        task_id='executar_primeira_dag',
        trigger_dag_id='nome_da_primeira_dag',  # ← SUBSTITUA pelo ID real da sua primeira DAG
        wait_for_completion=True,  # Aguarda terminar antes de seguir
        poke_interval=30,  # Verifica status a cada 30 segundos
        reset_dag_run=True,  # Permite executar mesmo se já rodou hoje
    )

    # Executa segunda DAG (só roda depois da primeira terminar)
    executar_dag2 = TriggerDagRunOperator(
        task_id='executar_segunda_dag',
        trigger_dag_id='nome_da_segunda_dag',  # ← SUBSTITUA pelo ID real da sua segunda DAG
        wait_for_completion=True,
        poke_interval=30,
        reset_dag_run=True,
    )

    # Define a sequência: DAG1 → DAG2
    executar_dag1 >> executar_dag2
