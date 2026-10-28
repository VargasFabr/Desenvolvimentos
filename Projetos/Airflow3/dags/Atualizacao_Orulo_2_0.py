from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

# Caminhos absolutos dentro do container Docker
BASE_PATH = "/opt/airflow/dags/AtualizaBackoffice/Melnick-Code"
PROJECT_PATH = f"{BASE_PATH}/Projetos/Orulo 2.0"
SCRIPT_PATH = f"{PROJECT_PATH}/atualizacao_orulo.py"
POSTGRES_HOST_DOCKER = "host.docker.internal"

with DAG(
    dag_id="Atualiza_Orulo_2_0",
    start_date=datetime(2025, 12, 29),
    schedule="0 9,14 * * 1-6",  # 9h e 14h, segunda a sábado (deslocado do legado)
    catchup=False,
    max_active_runs=1,
    tags=["Atualiza_Orulo_2_0", "orulo", "melnick"],
) as dag:

    run_script = BashOperator(
        task_id="Atualiza_Orulo_2_0",
        do_xcom_push=False,
        bash_command=f"""
        cd "{PROJECT_PATH}" && \
        export PYTHONPATH="{BASE_PATH}:$PYTHONPATH" && \
        export POSTGRES_HOST="{POSTGRES_HOST_DOCKER}" && \
        export ORULO_PG_DB="melnick" && \
        export ORULO_PG_SCHEMA="orulo" && \
        python "{SCRIPT_PATH}"
        """,
    )
