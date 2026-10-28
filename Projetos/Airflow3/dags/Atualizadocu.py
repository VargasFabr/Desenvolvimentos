from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

# Caminhos absolutos dentro do container Docker
# Agora a pasta Melnick-Code está dentro de dags
BASE_PATH = "/opt/airflow/dags/AtualizaBackoffice/Melnick-Code"
PROJECT_PATH = f"{BASE_PATH}/Projetos/AutoBackoffice"
SCRIPT_PATH = f"{PROJECT_PATH}/AutoDocu.py"

with DAG(
    dag_id="Atualiza_Docu",
    start_date=datetime(2025, 12, 29),
    schedule='*/15 8-18 * * 1-6',  # ou cron
    catchup=False,
    max_active_runs=1,
    tags=["Atualiza_Docu"],
) as dag:

    run_script = BashOperator(
        task_id="Atualiza_Docu",
        # Evita gravar stdout inteiro no XCom (logs do AutoDocu estouram limite/serialização).
        do_xcom_push=False,
        bash_command=f"""
        cd "{PROJECT_PATH}" && \
        export PYTHONPATH="{BASE_PATH}:$PYTHONPATH" && \
        python "{SCRIPT_PATH}"
        """
    )
