from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

# Caminhos absolutos dentro do container Docker
BASE_PATH = "/opt/airflow/dags/AtualizaBackoffice/Melnick-Code"
PROJECT_PATH = f"{BASE_PATH}/Projetos/Avaliação de Dações"
SCRAPE_SCRIPT = f"{PROJECT_PATH}/scrape_dacoes.py"
LOAD_SCRIPT = f"{PROJECT_PATH}/load_dacoes_postgres.py"
DACOES_DATA_PATH = "/opt/airflow/data/dacoes"
POSTGRES_HOST_DOCKER = "host.docker.internal"

with DAG(
    dag_id="Atualiza_Dacoes",
    start_date=datetime(2025, 12, 29),
    schedule="0 9,14 * * 1-5",  # 9h e 14h, segunda a sexta
    catchup=False,
    max_active_runs=1,
    tags=["Atualiza_Dacoes"],
) as dag:

    scrape_dacoes = BashOperator(
        task_id="scrape_dacoes",
        do_xcom_push=False,
        bash_command=f"""
        cd "{PROJECT_PATH}" && \
        export PYTHONPATH="{BASE_PATH}:$PYTHONPATH" && \
        export DACOES_DATA_PATH="{DACOES_DATA_PATH}" && \
        python "{SCRAPE_SCRIPT}"
        """,
    )

    load_dacoes_postgres = BashOperator(
        task_id="load_dacoes_postgres",
        do_xcom_push=False,
        bash_command=f"""
        cd "{PROJECT_PATH}" && \
        export PYTHONPATH="{BASE_PATH}:$PYTHONPATH" && \
        export DACOES_DATA_PATH="{DACOES_DATA_PATH}" && \
        export POSTGRES_HOST="{POSTGRES_HOST_DOCKER}" && \
        python "{LOAD_SCRIPT}"
        """,
    )

    scrape_dacoes >> load_dacoes_postgres
