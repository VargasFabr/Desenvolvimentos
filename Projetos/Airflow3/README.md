# Airflow3

Orquestração das automações da **Controladoria Comercial**. Airflow **3.1.8** standalone (Docker + LocalExecutor). O código de negócio vive em `dags/`; o Postgres do host é o destino analítico — ver [`../dados/ARCHITECTURE.md`](../dados/ARCHITECTURE.md).

| | |
|-|-|
| UI | http://localhost:8081 |
| Imagem | `airflow3-with-chromium:3.1.8` (Chromium + Node 22) |
| Metadata | SQLite em `data/airflow-meta/airflow.db` |
| Stack irmã | n8n/Chatwoot em [`../n8n/`](../n8n/) — **não** neste compose |

## Leitura por público

| Quem | Comece por |
|------|------------|
| Subir / operar | Este README |
| Arquitetura, DAGs, fluxos | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Plataforma Postgres | [`../dados/docs/inventario-postgres.md`](../dados/docs/inventario-postgres.md) |
| Editar DAGs (agente) | skill `airflow-dag-patterns` + regra `.cursor/rules/airflow-dag-patterns.mdc` |

## Objetivos dos projetos (Atualiza*)

Este projeto cobre as automações da Controladoria Comercial. Em `dags/` rodam os principais fluxos do setor:

- **Atualiza dações** — web scraping no SharePoint de dações para alimentar o Hermes Agent e servir de backup dos dados.
- **Atualiza Hermes** — foco em segurança: atualiza diariamente as CVEs; se houver quebra de dependência, antecipa os pedidos de atualização da TI.
- **Atualiza Backoffice** — integra Otto, relatório comercial e DocuSign: busca reservas e propostas no Otto, grava no Monday e acompanha assinaturas no DocuSign.
- **Atualização Órulo e Órulo 2.0** — conecta à API do Órulo (lançamentos nacionais) para captar informações de concorrentes. O 2.0 grava em `melnick.orulo`; o legado ainda aponta ao Supabase.
- **Atualiza Docu** — subprocesso do backoffice: só a atualização DocuSign → Monday.
- **Atualiza Postgres** — ETL do banco Otto (RDS) para o Postgres local (espelho no DB `otto`).
- **Previsões** — scripts de machine learning (propostas / aprovação). Atualmente não utilizados no schedule.

Schedules e destinos técnicos na tabela abaixo; detalhe em [`ARCHITECTURE.md`](ARCHITECTURE.md).

## DAGs (visão rápida)

| DAG ID | Schedule (America/Sao_Paulo) | Faz o quê | Destino principal |
|--------|------------------------------|-----------|-------------------|
| `Atualiza_PostgreSQL` | `50 8-18 * * 1-6` | ETL Otto RDS → Postgres local | DB `otto` (conn Airflow `postgres`) |
| `Atualiza_BackOffice` | `*/20 8-18 * * 1-6` | Otto → Monday (relatório comercial) | Monday.com |
| `Atualiza_Docu` | `*/15 8-18 * * 1-6` | DocuSign → Monday (contratos) | Monday.com |
| `ContratosDocusign` | `*/5 * * * *` | Apoio contratos DocuSign | Monday / arquivos |
| `Atualiza_Dacoes` | `0 9,14 * * 1-5` | Scrape SharePoint → PG | DB `dacoes` |
| `Atualiza_Orulo_2_0` | `0 9,14 * * 1-6` | API Órulo → PG | `melnick.orulo` |
| `Atualiza_Orulo` | `0 8,13 * * 1-6` | Órulo legado → Supabase | Supabase |
| `Atualiza_Hermes_Deps` | `0 7 * * *` | Guard de deps/CVEs Hermes | relatório em `data/hermes` |
| `Previsao_Propostas` | manual / trigger | ML propostas (Prophet) | DB `otto` |
| `Prev_Propostas_Aprovacao` | manual / trigger | ML aprovação | DB `otto` |
| `Sync_Media_Otto_Imagens` | manual | Baixa mídias Otto | disco + `media_otto_imagens_sync` |

Novas DAGs nascem **pausadas** (`DAGS_ARE_PAUSED_AT_CREATION=true`).

## Subir

```powershell
cd e:\Projetos\VS_Code\Melnick\PROJETOS\Airflow3
docker compose up -d
```

Senha admin (Simple Auth): `data/airflow-meta/simple_auth_manager_passwords.json.generated`.

Parar:

```powershell
docker compose down
```

## Persistência

| O quê | Onde |
|-------|------|
| Logs de task runs | `logs/` |
| Metadata (connections, variables, histórico) | `data/airflow-meta/airflow.db` |
| Senha admin | `data/airflow-meta/simple_auth_manager_passwords.json.generated` |
| Credenciais dos projetos | `dags/AtualizaBackoffice/.env` (+ Connections na UI) |
| Runtime (dações, docusign, hermes) | `data/` |
| Logs Otto (host) | `E:/Projetos/logsOtto` → `/opt/airflow/logsOtto` |
| Hermes Agent (host) | `%LOCALAPPDATA%\hermes\hermes-agent` → `/opt/hermes` |

**Não alterar** `AIRFLOW__CORE__FERNET_KEY` no `docker-compose.yaml` — descriptografa Connections/Variables existentes.

## Estrutura

```
Airflow3/
├── docker-compose.yaml      # só airflow-standalone
├── Dockerfile               # Node 22 sobre base com Chromium
├── dags/                    # arquivos DAG (descoberta Airflow)
│   ├── Atualiza_*.py …
│   └── AtualizaBackoffice/Melnick-Code/   # código de negócio
│       ├── Módulos/         # clientes Monday, Otto, Órulo, …
│       └── Projetos/        # AutoBackoffice, Dações, Orulo 2.0, Hermes, …
├── data/                    # runtime + metadata SQLite
├── logs/
├── plugins/
├── scripts/                 # ops (pause-all, clean db, …)
└── requirements.txt         # pip no start do container
```
