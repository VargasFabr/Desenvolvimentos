from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

# Caminhos dentro do container Docker
BASE_PATH = "/opt/airflow/ProjetosVS/Melnick-Code"
PROJECT_PATH = f"{BASE_PATH}/Projetos/AutoBackoffice"
SCRIPT_PATH = f"{PROJECT_PATH}/AutoBackoffice.py"

with DAG(
    dag_id="Atualiza_BackOffice",
    start_date=datetime(2025, 12, 29),
    schedule='5 8-18 * * 1-6',
    catchup=False,
    tags=["Atualiza_BackOffice"],
) as dag:

    run_script = BashOperator(
        task_id="Atualiza_BackOffice",
        bash_command=f"""
        # Verifica se o diretório existe
        if [ ! -d "{PROJECT_PATH}" ]; then
            echo "ERRO: Diretório não encontrado: {PROJECT_PATH}"
            echo "Verificando estrutura de pastas..."
            ls -la /opt/airflow/ProjetosVS/ 2>/dev/null || echo "Volume ProjetosVS não montado"
            exit 1
        fi
        
        # Verifica se o arquivo existe
        if [ ! -f "{SCRIPT_PATH}" ]; then
            echo "ERRO: Arquivo não encontrado: {SCRIPT_PATH}"
            echo "Buscando arquivo AutoBackoffice.py..."
            find /opt/airflow/ProjetosVS -name "AutoBackoffice.py" -type f 2>/dev/null || echo "Arquivo não encontrado"
            exit 1
        fi
        
        # Executa o script
        cd "{PROJECT_PATH}" && \
        export PYTHONPATH="{BASE_PATH}:$PYTHONPATH" && \
        python "{SCRIPT_PATH}"
        """
    )
