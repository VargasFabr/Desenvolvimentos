from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

# Caminhos absolutos dentro do container Docker
BASE_PATH = "/opt/airflow/dags/AtualizaBackoffice/Melnick-Code"
PROJECT_PATH = f"{BASE_PATH}/Projetos/Hermes"
GUARD_SCRIPT = f"{PROJECT_PATH}/hermes_deps_guard.py"

with DAG(
    dag_id="Atualiza_Hermes_Deps",
    start_date=datetime(2026, 7, 31),
    schedule="0 7 * * *",  # 07:00 America/Sao_Paulo (timezone do stack)
    catchup=False,
    max_active_runs=1,
    tags=["hermes", "security"],
) as dag:

    hermes_deps_guard = BashOperator(
        task_id="hermes_deps_guard",
        do_xcom_push=False,
        execution_timeout=timedelta(minutes=45),
        bash_command=f"""
        export PYTHONUNBUFFERED=1 && \
        export HERMES_ROOT="${{HERMES_ROOT:-/opt/hermes}}" && \
        export HERMES_REPORT_DIR="/opt/airflow/data/hermes" && \
        mkdir -p "$HERMES_REPORT_DIR" && \
        python "{GUARD_SCRIPT}"
        """,
    )
