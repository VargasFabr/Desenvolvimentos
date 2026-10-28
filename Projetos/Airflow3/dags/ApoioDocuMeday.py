from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

# Caminhos absolutos dentro do container Docker
# Agora a pasta Melnick-Code está dentro de dags
BASE_PATH = "/opt/airflow/dags/AtualizaBackoffice/Melnick-Code"
PROJECT_PATH = f"{BASE_PATH}/Projetos/AutoBackoffice"
SCRIPT_PATH = f"{PROJECT_PATH}/ContratosDocusign.py"

with DAG(
    dag_id="ContratosDocusign",
    start_date=datetime(2025, 12, 29),
    schedule='*/5 * * * *',  # ou cron
    catchup=False,
    tags=["ContratosDocusign"],
) as dag:

    run_script = BashOperator(
        task_id="ContratosDocusign",
        bash_command=f"""
        cd "{PROJECT_PATH}" && \
        export PYTHONPATH="{BASE_PATH}:$PYTHONPATH" && \
        python "{SCRIPT_PATH}"
        """
    )
