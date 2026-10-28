# Scripts SQL — schema `cad`

DDL e seeds do cadastro master no banco **`melnick`**. Contexto da plataforma: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

## Ordem de execução

```powershell
cd e:\Projetos\VS_Code\Melnick\PROJETOS\dados
$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$env:PGPASSWORD = $env:MELNICK_PG_PASSWORD

# Via psql do host (recomendado)
Get-Content "cadastro\schema cad\99_archive_legacy.sql" -Raw | & $psql -h localhost -U postgres -d melnick
Get-Content "cadastro\schema cad\00_extensions.sql" -Raw | & $psql -h localhost -U postgres -d melnick
Get-Content "cadastro\schema cad\01_schema_cad.sql" -Raw | & $psql -h localhost -U postgres -d melnick
Get-Content "cadastro\schema cad\02_seed_sistemas.sql" -Raw | & $psql -h localhost -U postgres -d melnick
Get-Content "cadastro\schema cad\03_seed_incorporadoras.sql" -Raw | & $psql -h localhost -U postgres -d melnick

python scripts/import_empreendimentos_csv.py
Get-Content "cadastro\schema cad\04_seed_controladoria.sql" -Raw | & $psql -h localhost -U postgres -d melnick

python scripts/inspect_cad.py
python scripts/apply_views.py
```

Alternativa via container Airflow (se preferir):

```powershell
$env:PGPASSWORD = $env:MELNICK_PG_PASSWORD
Get-Content "cadastro\schema cad\00_extensions.sql" -Raw |
  docker exec -i -e PGPASSWORD=$env:PGPASSWORD airflow3-standalone `
    psql -h host.docker.internal -U postgres -d melnick
```

| # | Arquivo | Descrição |
|---|---------|-----------|
| 0 | `99_archive_legacy.sql` | Move tabelas legadas `public` → `legacy` |
| 1 | `00_extensions.sql` | pgcrypto, unaccent, pg_trgm, … |
| 2 | `01_schema_cad.sql` | DDL schema `cad` |
| 3 | `02_seed_sistemas.sql` | Catálogo de sistemas externos |
| 4 | `03_seed_incorporadoras.sql` | Melnick + Zulckhan |
| 5 | `04_seed_controladoria.sql` | **Gerado** por `scripts/import_empreendimentos_csv.py` |

## Validação

```powershell
python scripts/inspect_cad.py
```

Esperado (ordem de grandeza): ~134 empreendimentos, ~819 torres, 0 orphans.  
Unidades e identificadores crescem com sync Otto (fase 2) — ver [`../docs/inventario-postgres.md`](../docs/inventario-postgres.md).
