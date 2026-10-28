# %%
"""
DAG que executa sync_media_otto_images.py (pasta Melnick-Code).
Ficheiros só em subpastas não são descobertos como DAG; este ficheiro na raiz de dags/ orquestra a execução.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Timezone do Brasil (igual a AtualizaPostgreSQL3.py)
tz_brasil = pytz.timezone("America/Sao_Paulo")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=1),
}

dag = DAG(
    "Sync_Media_Otto_Imagens",
    default_args=default_args,
    description="Baixa imagens de public.media_otto (JSON midias) e grava disco + media_otto_imagens_sync",
    schedule=None,
    start_date=tz_brasil.localize(datetime(2025, 12, 2)),
    catchup=False,
    tags=["Melnick", "media_otto", "imagens", "PostgreSQL"],
)

# Pasta do script sync + .env (irmã da raiz de dags onde está este ficheiro).
MELNICK_CODE = Path(__file__).resolve().parent / "AtualizaBackoffice" / "Melnick-Code"


def sync_media_otto_images_task(**_context):
    base = MELNICK_CODE.resolve()
    if not base.is_dir():
        raise FileNotFoundError(
            f"Pasta Melnick-Code nao encontrada: {base}. "
            "Confirme que AtualizaBackoffice/Melnick-Code existe sob a mesma pasta dags."
        )
    os.chdir(base)
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))

    try:
        from dotenv import load_dotenv

        load_dotenv(base / ".env", override=False)
    except ImportError:
        pass

    from sync_media_otto_images import run

    out = os.environ.get(
        "SYNC_MEDIA_OTTO_OUTPUT_DIR",
        str(base / "data" / "media_otto_images"),
    )
    skip = os.environ.get("SYNC_MEDIA_OTTO_SKIP_EXISTING", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    limit_rows = os.environ.get("SYNC_MEDIA_OTTO_LIMIT_ROWS")
    limit_images = os.environ.get("SYNC_MEDIA_OTTO_LIMIT_IMAGES")
    rc = run(
        output_dir=Path(out),
        absolute_paths=os.environ.get("SYNC_MEDIA_OTTO_ABSOLUTE_PATHS", "").lower()
        in ("1", "true", "yes"),
        limit_rows=int(limit_rows) if limit_rows else None,
        limit_images=int(limit_images) if limit_images else None,
        dry_run=False,
        skip_existing=skip,
        batch_commit=int(os.environ.get("SYNC_MEDIA_OTTO_BATCH_COMMIT", "20")),
        quality=int(os.environ.get("SYNC_MEDIA_OTTO_QUALITY", "86")),
        max_side=int(os.environ.get("SYNC_MEDIA_OTTO_MAX_SIDE", "1600")),
        max_bytes=int(os.environ.get("SYNC_MEDIA_OTTO_MAX_BYTES", str(4_800_000))),
    )
    if rc != 0:
        raise RuntimeError(f"sync_media_otto_images terminou com codigo {rc}")


tarefa_sync_media_otto_imagens = PythonOperator(
    task_id="sync_media_otto_imagens",
    python_callable=sync_media_otto_images_task,
    dag=dag,
)
