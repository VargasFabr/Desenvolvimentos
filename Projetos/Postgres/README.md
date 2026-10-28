# Melnick — Projeto de Dados

Hub da **stack de dados centralizada no PostgreSQL** (host Windows, porta 5432). Este repositório governa o banco analítico `melnick` (cadastro canônico, Órulo, staging) e documenta os demais bancos do mesmo Postgres usados por Airflow, n8n, Chatwoot e automações.

## Objetivo

1. **Cadastro master** — substituir chaves por nome (Excel legado) por IDs canônicos; a **torre** é a entidade de referência (`codigo_interno`, ex. `8190-001-F1`).
2. **Postgres como plataforma** — um único servidor concentra espelhos operacionais (Otto, dações, Órulo), apps (n8n/Chatwoot) e o modelo analítico (`melnick`).
3. **Consumo confiável** — BI, DAGs e UI leem views/schemas estáveis, não planilhas soltas.

## Leitura por público

| Quem | Comece por |
|------|------------|
| Operar cadastro / UI | Este README |
| Arquitetura e decisões | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Inventário vivo dos bancos | [`docs/inventario-postgres.md`](docs/inventario-postgres.md) |
| Modelo torre/SPE | [`docs/empreendimentos-MODEL.md`](docs/empreendimentos-MODEL.md) |
| Join entre fontes | [`docs/mapeamento-fontes.md`](docs/mapeamento-fontes.md) |
| Regras de nomes | [`docs/governanca-nomes.md`](docs/governanca-nomes.md) |
| Scripts SQL `cad` | [`cadastro/README.md`](cadastro/README.md) |

## Mapa rápido do Postgres (host)

| Banco | Papel | Tamanho aprox. |
|-------|--------|----------------|
| **melnick** | Hub analítico: `cad`, `orulo`, `legacy`, staging SAP | ~238 MB |
| **otto** | Espelho CRM Otto + views de negócio (`propostas`, `reservas`…) | ~1,1 GB |
| **dacoes** | Landing SharePoint (avaliação de dações) | ~14 MB |
| **n8n** | Estado do n8n (workflows/credenciais) | ~67 MB |
| **chatwoot_production** | Estado Chatwoot | ~25 MB |
| **trade** | Experimentos trading (fora do domínio comercial) | ~51 MB |
| **sap_fi** | Placeholder — **vazio** | ~8 MB |
| **postgres** | DB default do cluster (`public` limpo; sem dump Otto) | ~14 MB |

Detalhe de schemas/tabelas: [`docs/inventario-postgres.md`](docs/inventario-postgres.md).

## Estrutura deste repositório

| Pasta | Conteúdo |
|-------|----------|
| [`cadastro/`](cadastro/) | DDL e seeds SQL do schema `cad` |
| [`docs/`](docs/) | Modelo, governança, mapeamento, inventário PG |
| [`fontes/`](fontes/) | CSVs de referência (Controladoria) |
| [`scripts/`](scripts/) | Import, validação, Otto, apply views |
| [`views/`](views/) | Views de consulta (`cad` + espelhos em `public`) |
| [`visualizacao/`](visualizacao/) | App web CRUD + import/export Excel |
| [`lib/`](lib/) | Parsers/upsert compartilhados (CLI + API) |

## Conexão

- **Host:** `localhost:5432` (containers: `host.docker.internal`)
- **User típico:** `postgres` (senha via env / gerenciador de secrets — **não commitar**)
- **Database analítico:** `melnick`

O `psql` 17 está no PATH e as variáveis `PGHOST/PGPORT/PGUSER/PGDATABASE` já apontam para `melnick`; a senha vem de `%APPDATA%\postgresql\pgpass.conf`. Basta:

```powershell
psql -c "\dn"
psql -d otto -c "\dt"          # outro banco do mesmo cluster
```

Para queries ad-hoc / multi-linha, use a extensão **PostgreSQL** (Microsoft) no editor: conecte com `Ctrl+Shift+C` e rode com `Shift+Enter` (arquivo/seleção) ou `Ctrl+Shift+Enter` (statement atual).

Acentos: `PGCLIENTENCODING=UTF8` + `LANG=C` (mensagens do psql em inglês) evitam mojibake no console Windows. Para saída limpa em ferramentas, redirecione com `-o arquivo.out` e leia em UTF-8.

## Cadastro `cad` — execução

Ordem completa: [`cadastro/README.md`](cadastro/README.md).

```powershell
cd e:\Projetos\VS_Code\Melnick\PROJETOS\dados
python scripts/import_empreendimentos_csv.py
# aplicar SQLs na ordem do cadastro/README.md
python scripts/inspect_cad.py
python scripts/apply_views.py
```

Contagens atuais (seed + sync): ~134 SPEs, ~819 torres, ~35k unidades, ~1,4k aliases.

## Cadastro manual (UI)

```powershell
cd e:\Projetos\VS_Code\Melnick\PROJETOS\dados\visualizacao
copy .env.example .env
docker compose up -d
# http://localhost:5173 — UI | http://localhost:8090/docs — API
```

## Produtores externos (Airflow / n8n)

| Fonte | Destino Postgres | DAG / serviço |
|-------|------------------|---------------|
| Otto RDS (cloud) | banco `otto` | `AtualizaPostgreSQL3.py` |
| API Órulo | `melnick.orulo.*` | Orulo 2.0 (`orulo_db.py`) |
| SharePoint dações | `dacoes.dacoes_itens` | `load_dacoes_postgres.py` |
| CSV Controladoria / UI | `melnick.cad.*` | scripts + `visualizacao/` |
| n8n / Chatwoot | `n8n`, `chatwoot_production` | stack [`../n8n/`](../n8n/) |

## Fonte master (Fase 1)

[`fontes/Empreendimentos.csv`](fontes/Empreendimentos.csv) — Controladoria Comercial.
