# Arquitetura — stack N8N + Chatwoot

Manual técnico de referência. Compose: [`app/docker-compose.yaml`](app/docker-compose.yaml). Operação rápida: [`README.md`](README.md).

---

## 1. Sumário executivo

Stack local de **automação (n8n)** e **atendimento (Chatwoot)**, com um microserviço auxiliar (**python-img**) para conversão de imagem e reset de senha no admin Otto.

Cinco containers Docker; **Postgres fica no host Windows** (não no compose). Exposição pública via proxy da empresa na borda `200.215.210.68` → VM `192.168.210.50` (portas 5678 n8n / 3000 Chatwoot).

| Decisão | Escolha | Por quê |
|--------|---------|---------|
| Postgres fora do compose | PostgreSQL Windows em `host.docker.internal:5432` | Bancos `n8n` e `chatwoot_production` compartilhados com outras tools do host; backup/ops unificados |
| Redis no compose | container + volume `melnick_app_redis_data` | Só Chatwoot/Sidekiq precisam; isolamento da fila |
| python-img separado | FastAPI + Chromium no container | Workflows n8n não carregam Pillow/Selenium; um HTTP call resolve |
| Volumes `melnick_app_*` | Renomeados de `airflow3_*` | Stack app desacoplada do Airflow após migração |

---

## 2. Visão geral da arquitetura

```
                    Internet / WhatsApp
                            │
              ┌─────────────┴─────────────┐
              │  Borda 200.215.210.68      │
              │  backoffice01 → :5678 n8n  │
              │  backoffice02 → :3000 CW   │
              └─────────────┬─────────────┘
                            │
              VM 192.168.210.50 (Docker)
     ┌──────────────────────┼──────────────────────┐
     │                      │                      │
  ┌──▼──┐            ┌──────▼──────┐         ┌─────▼─────┐
  │ n8n │            │  Chatwoot   │         │python-img │
  │:5678│◄──HTTP────►│  :3000      │         │  :8000    │
  └──┬──┘            │  + Sidekiq  │         └─────┬─────┘
     │               └──────┬──────┘               │
     │                      │                      │
     │               ┌──────▼──────┐               │
     │               │ Redis :6379 │               │
     │               │   (DB 1)    │               │
     │               └─────────────┘               │
     │                                             │
     └────────── host.docker.internal:5432 ────────┘
                         │
              PostgreSQL Windows (host)
              ├── banco n8n
              ├── banco chatwoot_production
              └── banco otto (python-img / workflows)
```

### Serviços

| Serviço | Porta | Imagem | Depende de |
|---------|-------|--------|------------|
| n8n | 5678 | `n8nio/n8n:2.22.5` | Postgres host (`n8n`) |
| chatwoot | 3000 | `chatwoot/chatwoot:v4.11.1` | Postgres host + Redis |
| chatwoot_sidekiq | (interno) | mesma imagem Chatwoot | Postgres host + Redis |
| redis | 6379 | `redis:7` | — |
| python-img | 8000 | build local `python/` | Otto admin (HTTPS) + opcional Postgres otto |

> **Nota histórica:** docs antigas citavam um sexto serviço `chatwoot-postgres` (pgvector) e volume `melnick_app_pgdata`. Isso **não existe mais** neste compose — o Postgres migrou para o serviço Windows do host.

---

## 3. Decisões de design

### 3.1 Postgres no host, não no Docker

Containers usam `extra_hosts: host.docker.internal:host-gateway` e apontam `DB_*` / `POSTGRES_HOST` para o host. Motivos:

1. Um único Postgres Windows atende n8n, Chatwoot, Otto e o projeto `dados` (banco `melnick`).
2. Evita volume Docker órfão após a cisão da stack unificada Airflow+app.
3. Ops (backup, `psql`, pgAdmin) ficam no host.

### 3.2 Proxy HTTPS sem `FORCE_SSL` no Chatwoot

Atrás do proxy da TI, `FORCE_SSL=true` gera loop de redirect. O compose **não** define `FORCE_SSL`; a TI deve enviar `X-Forwarded-Proto: https`. No n8n: `N8N_PROTOCOL=https`, `N8N_PROXY_HOPS=1`.

`N8N_SECURE_COOKIE=false` está temporário para acesso via `http://localhost` durante migração — trocar para `true` quando o acesso for só via HTTPS público.

### 3.3 python-img como sidecar HTTP

Em vez de nodes customizados pesados no n8n:

- **JPEG** — Pillow com degradação progressiva de qualidade até caber em `max_bytes` (workflows de mídia / WhatsApp).
- **Reset Otto** — Selenium headless no Chromium do container, chamado por `POST /reset-password` a partir de um workflow n8n.

### 3.4 Volumes externos nomeados

`chatwoot_storage` e `redis-data` são `external: true` com nomes `melnick_app_*`. Criar uma vez no host; `docker compose down` não os apaga.

---

## 4. Componentes

### 4.1 n8n

- Credenciais e workflows no Postgres (`DB_TYPE=postgresdb`).
- Bind mount [`data/n8n/`](data/n8n/) → `/home/node/.n8n`: logs de evento, `binaryData/`, nodes em `nodes/`.
- Timezone `America/Sao_Paulo`; histórico de workflow 30 dias.
- Webhooks públicos via `WEBHOOK_URL` / `N8N_EDITOR_BASE_URL` (HTTPS na borda).

### 4.2 Chatwoot + Sidekiq

- Rails em `:3000`; Sidekiq consome fila no Redis DB 1 (`redis://redis:6379/1`).
- Active Storage local em `/app/storage` → volume `melnick_app_chatwoot_storage`.
- WhatsApp: `WHATSAPP_APP_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_CONFIGURATION_ID`.
- SMTP configurável via `.env` (default porta 1025 para dev).

### 4.3 Redis

Só Chatwoot/Sidekiq. Porta 6379 publicada no host (útil para debug; em produção restrinja se necessário).

### 4.4 python-img

Código em [`python/`](python/). Imagem: Python 3.11-slim + Chromium/chromedriver ([`python/Dockerfile`](python/Dockerfile)).

| Endpoint | Função |
|----------|--------|
| `GET /health` | Healthcheck `{ "ok": true }` |
| `POST /convert/jpeg` | Arquivo (`file`) ou `url` → JPEG; params `quality`, `frame`, `max_side`, `max_bytes` |
| `POST /reset-password` | Body `{ "email": "..." }` → Selenium em `admin.beotto.com` |

Fluxo do reset ([`python/reset_password.py`](python/reset_password.py)):

1. Login admin com `OTTO_ADMIN_EMAIL` / `OTTO_ADMIN_PASSWORD`
2. Gerenciamento de usuários → busca e-mail alvo
3. Gera senha segura → preenche modal → Salvar
4. Retorna JSON com `ok`, `new_password` (se sucesso), `steps`, `ui_messages`

`CHROME_HEADLESS=0` permite depurar com janela (local). Em Docker o default é headless.

Variáveis `OTTO_DB_*` estão no compose (e `psycopg2` no requirements) para uso futuro / scripts auxiliares; o caminho atual de reset é **UI Selenium**, não SQL direto.

---

## 5. Fluxo de dados e persistência

| Dado | Armazenamento | Notas |
|------|---------------|-------|
| Workflows / credenciais n8n | Postgres `n8n` | Criptografia depende de `N8N_ENCRYPTION_KEY` |
| Conversas / contatos Chatwoot | Postgres `chatwoot_production` | Mesmo user/senha do `.env` (`CHATWOOT_DB_*`) |
| Anexos Chatwoot | volume `melnick_app_chatwoot_storage` | |
| Filas / cache Chatwoot | Redis volume `melnick_app_redis_data` | DB index 1 |
| Logs / binary n8n | `data/n8n/` | Não contém workflows (esses estão no PG) |
| SQLite `E:\Programas\n8n\` | — | **Obsoleto** — arquivo morto |

---

## 6. Pontos de integração

| Sistema | Direção | Como |
|---------|---------|------|
| WhatsApp (Meta) | → Chatwoot | Credenciais `WHATSAPP_*` no compose |
| Otto admin (web) | python-img → | Selenium HTTPS `admin.beotto.com` |
| Otto Postgres | n8n / tools → | `host.docker.internal:5432`, banco `otto` |
| Webhooks n8n | externos → n8n | URL HTTPS pública (`N8N_WEBHOOK_URL`) |
| Airflow3 | paralelo | [`../Airflow3/`](../Airflow3/) — batch/DAGs; não compartilha este compose |
| Túneis EC2 | ops | `E:\Projetos\VS_Code\N8N\tunnels\` — SSH Postgres AWS (fora do compose) |

---

## 7. Deploy e operação

### Subir / parar

```powershell
cd e:\Projetos\VS_Code\Melnick\PROJETOS\n8n\app
docker compose up -d
docker compose down          # volumes externos e PG host permanecem
docker compose logs -f n8n   # exemplo
```

### Pré-requisitos

1. Postgres Windows com bancos `n8n` e `chatwoot_production`
2. Volumes: `docker volume create melnick_app_chatwoot_storage` e `melnick_app_redis_data` (se ainda não existirem)
3. `app/.env` preenchido (nunca versionar)

### Rebuild do python-img

```powershell
cd e:\Projetos\VS_Code\Melnick\PROJETOS\n8n\app
docker compose build python-img
docker compose up -d python-img
```

### Checklist pós-migração / proxy

- [ ] TI envia `X-Forwarded-Proto: https`
- [ ] `N8N_SECURE_COOKIE=true` quando localhost HTTP deixar de ser necessário
- [ ] `FRONTEND_URL` / `N8N_EDITOR_BASE_URL` / `WEBHOOK_URL` batem com os hostnames públicos

---

## 8. Segurança

| Item | Prática |
|------|---------|
| Secrets | Só em `app/.env` |
| Encryption keys | Não rotacionar sem plano de re-criptografia |
| python-img `/reset-password` | Expõe capacidade admin Otto — restrinja quem chama (rede / auth no n8n) |
| Redis publicado em 6379 | Em host compartilhado, considere não publicar a porta |
| Credenciais Otto no container | Env vars; não logar senhas retornadas em canais inseguros |

---

## 9. Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| n8n ou Chatwoot não sobe | Postgres host fora / firewall | Testar `localhost:5432`; conferir user/senha no `.env` |
| Credenciais n8n ilegíveis | `N8N_ENCRYPTION_KEY` mudou | Restaurar a key original do backup do `.env` |
| Loop de redirect no Chatwoot HTTPS | `FORCE_SSL` ou proxy sem `X-Forwarded-Proto` | Não usar `FORCE_SSL`; ajustar proxy |
| `python-img` reset falha no Chrome | Sem headless / Chromium | Conferir logs; `CHROME_HEADLESS=1`; rebuild imagem |
| Volume “not found” no compose | Volume externo ausente | `docker volume create melnick_app_…` |
| Cookie / login n8n estranho em HTTP | `N8N_SECURE_COOKIE` | Temporariamente `false` em localhost |

---

## 10. Glossário e caminhos

| Termo | Significado |
|-------|-------------|
| Borda | Proxy/firewall da empresa que publica hostnames `backoffice0x` |
| Stack app | Este compose (n8n + Chatwoot), oposto às DAGs do Airflow3 |
| python-img | Sidecar FastAPI de mídia + automação Otto |
| `melnick_app_*` | Prefixo dos volumes Docker pós-migração |

| Caminho | Conteúdo |
|---------|----------|
| `app/docker-compose.yaml` | Definição dos serviços |
| `app/.env` | Secrets |
| `python/app.py` | API FastAPI |
| `python/reset_password.py` | Automação Selenium Otto |
| `data/n8n/` | Estado local do processo n8n |
