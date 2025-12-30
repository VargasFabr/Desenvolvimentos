from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

"""
DAG de diagnóstico para verificar se os volumes estão montados corretamente.
Execute esta DAG primeiro para diagnosticar problemas de montagem de volumes.
"""

with DAG(
    dag_id="test_volumes",
    start_date=datetime(2025, 12, 29),
    schedule=None,  # Manual apenas
    catchup=False,
    tags=["diagnostico"],
) as dag:

    check_volumes = BashOperator(
        task_id="check_volumes",
        bash_command="""
        echo "===== DIAGNÓSTICO DE VOLUMES ====="
        echo ""
        echo "1. Verificando /opt/airflow/ProjetosVS..."
        if [ -d "/opt/airflow/ProjetosVS" ]; then
            echo "✓ Volume ProjetosVS encontrado"
            echo "Conteúdo:"
            ls -la /opt/airflow/ProjetosVS/
        else
            echo "✗ Volume ProjetosVS NÃO encontrado"
        fi
        
        echo ""
        echo "2. Verificando /opt/airflow/ProjetosVS/Melnick-Code..."
        if [ -d "/opt/airflow/ProjetosVS/Melnick-Code" ]; then
            echo "✓ Diretório Melnick-Code encontrado"
            echo "Conteúdo:"
            ls -la /opt/airflow/ProjetosVS/Melnick-Code/
        else
            echo "✗ Diretório Melnick-Code NÃO encontrado"
        fi
        
        echo ""
        echo "3. Buscando AutoBackoffice.py..."
        find /opt/airflow -name "AutoBackoffice.py" -type f 2>/dev/null || echo "✗ Arquivo AutoBackoffice.py não encontrado"
        
        echo ""
        echo "4. Estrutura completa de /opt/airflow..."
        ls -la /opt/airflow/
        
        echo ""
        echo "===== FIM DO DIAGNÓSTICO ====="
        """
    )
