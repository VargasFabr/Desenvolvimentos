# Atualização Órulo 2.0 → Postgres (melnick.orulo)

Pipeline paralelo ao Órulo/Supabase. Persiste no schema `orulo` do banco `melnick`.

## Estrutura

- `atualizacao_orulo.py`: orquestrador principal.
- `orulo_db.py`: conexão Postgres, fetch e upsert.
- `orulo_pipeline_utils.py`: merge, índices, deduplicação.
- `orulo_region_files.py`: status por região.
- `orulo_backup.py`: backup parquet.
- `orulo_diagnostic.py`: diagnóstico opcional.
- `migrate_from_supabase.py`: carga one-shot do Supabase.
- `sql/01_schema_orulo.sql`: DDL do schema.

## Variáveis de ambiente

Obrigatórias (Postgres local / host):

- `POSTGRES_USER`, `POSTGRES_PASS`, `POSTGRES_PORT` (default 5432)
- `ORULO_PG_DB` (default `melnick`)
- `ORULO_PG_SCHEMA` (default `orulo`)
- Credenciais Órulo: `POA_RM_CLIENT_ID` / `POA_RM_CLIENT_SECRET`, `FLN_RM_CWB_RM_ITAJAI_CLIENT_ID` / `FLN_RM_CWB_RM_ITAJAI_CLIENT_SECRET`

No Airflow (container): `POSTGRES_HOST=host.docker.internal`

Migração one-shot também precisa de `DATABASE_URL` ou `SUPABASE_HOST` / `SUPABASE_USER` / `SUPABASE_PASS`.

Opcionais:

- `ORULO_RUN_BACKUP` (`1`/`0`)
- `ORULO_RUN_DIAGNOSTIC` (`1`/`0`)
- `ORULO_BUILDING_REQUEST_DELAY`, `ORULO_TYPOLOGY_REQUEST_DELAY`

## Setup

```powershell
# 1) DDL + migração (uma vez)
$env:POSTGRES_HOST='localhost'
python ".\migrate_from_supabase.py"

# 2) ETL (paralelo ao projeto antigo)
$env:ORULO_RUN_BACKUP='0'
$env:ORULO_RUN_DIAGNOSTIC='0'
python ".\atualizacao_orulo.py"
```

## DAG Airflow

`Atualiza_Orulo_2_0` — 9h e 14h, segunda a sábado. O projeto antigo (`Atualiza_Orulo` → Supabase) continua ativo.
