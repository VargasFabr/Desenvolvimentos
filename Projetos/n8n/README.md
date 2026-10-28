# N8N + Chatwoot

Stack Docker local de automação e atendimento: **n8n**, **Chatwoot** (Rails + Sidekiq), **Redis** e **python-img** (FastAPI). O Postgres **não** roda neste compose — usa o PostgreSQL do host Windows (`host.docker.internal:5432`).

| Serviço | URL local | Papel |
|---------|-----------|--------|
| n8n | http://localhost:5678 | Workflows e webhooks |
| Chatwoot | http://localhost:3000 | Inbox / WhatsApp |
| python-img | http://localhost:8000 | JPEG + reset de senha Otto |

Borda pública: n8n → `backoffice01.melnick.com.br` · Chatwoot → `backoffice02.melnick.com.br`

## Leitura por público

| Quem | Comece por |
|------|------------|
| Subir / operar o stack | Este README |
| Arquitetura, decisões e integrações | [`ARCHITECTURE.md`](ARCHITECTURE.md) |

## Subir

Pré-requisito: Postgres Windows escutando em `localhost:5432`, com bancos `n8n` e `chatwoot_production`, e volumes Docker externos já criados (`melnick_app_chatwoot_storage`, `melnick_app_redis_data`).

```powershell
cd e:\Projetos\VS_Code\Melnick\PROJETOS\n8n\app
docker compose up -d
```

Parar (volumes e Postgres do host **persistem**):

```powershell
docker compose down
```

## Persistência

| O quê | Onde |
|-------|------|
| Workflows / credenciais n8n | Postgres host — banco `n8n` (criptografado com `N8N_ENCRYPTION_KEY`) |
| Conversas Chatwoot | Postgres host — banco `chatwoot_production` |
| Anexos Chatwoot | volume Docker `melnick_app_chatwoot_storage` |
| Cache Redis | volume Docker `melnick_app_redis_data` |
| Logs / binaryData / nodes n8n | bind mount `data/n8n/` |
| Secrets | `app/.env` — **não commitar** |

**Não alterar** `N8N_ENCRYPTION_KEY` nem `CHATWOOT_SECRET_KEY_BASE` — invalida dados já criptografados.


## Volumes Docker

| Volume | Conteúdo |
|--------|----------|
| `melnick_app_chatwoot_storage` | Anexos Active Storage do Chatwoot |
| `melnick_app_redis_data` | Persistência Redis |

Nomes `airflow3_*` eram da stack unificada com Airflow — removidos após a migração. O Postgres **não** usa volume Docker neste stack (fica no serviço Windows).


## Estrutura do repositório

```
n8n/
├── app/docker-compose.yaml   # definição dos 5 serviços
├── app/.env                  # secrets (local)
├── python/                   # imagem python-img
│   ├── app.py                # FastAPI
│   ├── reset_password.py     # Selenium → admin Otto
│   └── Dockerfile
├── data/n8n/                 # bind mount do n8n
├── ARCHITECTURE.md
└── README.md
```
