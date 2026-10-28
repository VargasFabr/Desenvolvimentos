from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

# Caminhos absolutos dentro do container Docker
# Agora a pasta Melnick-Code está dentro de dags
BASE_PATH = "/opt/airflow/dags/AtualizaBackoffice/Melnick-Code"
PROJECT_PATH = f"{BASE_PATH}/Projetos/AutoBackoffice"
SCRIPT_PATH = f"{PROJECT_PATH}/AutoBackoffice_2_0.py"

with DAG(
    dag_id="Atualiza_BackOffice",
    start_date=datetime(2025, 12, 29),
    schedule='*/20 8-18 * * 1-6',  # ou cron
    catchup=False,
    max_active_runs=1,
    tags=["Atualiza_BackOffice"],
) as dag:

    run_script = BashOperator(
        task_id="Atualiza_BackOffice",
        # Evita gravar a saída do bash no XCom (padrão True). Com Airflow 3 isso
        # pode gerar erro 409 "Unique constraint violation" se o mesmo XCom for
        # persistido mais de uma vez no mesmo run/task.
        do_xcom_push=False,
        bash_command=f"""
        cd "{PROJECT_PATH}" && \
        export PYTHONPATH="{BASE_PATH}:$PYTHONPATH" && \
        python "{SCRIPT_PATH}"
        """
    )
