# Inventário PostgreSQL — host Melnick

Snapshot do cluster **PostgreSQL 17** em `localhost:5432`.  
Gerado para documentação da centralização da stack de dados. **Revalidar** com as queries no final após cargas grandes.

> Não inclui senhas. Objetos de sistema (`pg_catalog`, `information_schema`) omitidos.

---

## 1. Bancos

| Banco | Tamanho | Schemas de negócio | Papel |
|-------|---------|-------------------|--------|
| `melnick` | ~238 MB | `cad`, `orulo`, `legacy`, `public` | Hub analítico + cadastro |
| `otto` | ~1,1 GB | `public` | Espelho CRM Otto + views BI |
| `postgres` | ~14 MB | `pgagent` (+ `public` vazio) | Default do cluster — dump Otto legado **removido** (2026-08-03) |
| `n8n` | ~67 MB | `public` | App n8n (~101 tabelas) |
| `trade` | ~51 MB | `public` | Experimentos trading |
| `chatwoot_production` | ~25 MB | `public` | App Chatwoot (~87 tabelas) |
| `dacoes` | ~14 MB | `public` | Landing dações SharePoint |
| `sap_fi` | ~8 MB | — | **Vazio** (placeholder) |

---

## 2. `melnick`

### 2.1 `cad` — tabelas

| Tabela | Linhas (COUNT) | Notas |
|--------|----------------|-------|
| `incorporadoras` | 2 | |
| `empreendimentos` | 134 | UNIQUE `cod_spe` |
| `fases` | 238 | |
| `torres` | 819 | Canônico; `codigo_interno` |
| `aliases` | 1 405 | |
| `identificadores_externos` | 34 930 | |
| `unidades` | 34 591 | Sync Otto + manual |
| `sistemas_externos` | 8 | Catálogo |
| `cidades` | 2 | |
| `estados` | (ref) | |

### 2.2 `cad` — views

`v_busca_cadastro`, `v_empreendimento_identificadores`, `v_empreendimentos_listagem`, `v_empreendimentos_resumo`, `v_torre_aliases`, `v_torre_identificadores`, `v_torres_completas`, `v_torres_principais`, `v_unidades_completas`

Espelhos homônimos em `public` (atalho pgAdmin/BI).

### 2.3 `orulo`

| Tabela | Linhas (COUNT) | Tamanho aprox. |
|--------|----------------|----------------|
| `buildings` | 5 211 | ~3,5 MB |
| `units` | 252 469 | ~41 MB |
| `units_updates` | 1 080 990 | ~136 MB |
| `images` | 102 374 | ~23 MB |
| `typologies` | 19 115 | ~3,5 MB |

PK típica: `building_id` / ids Órulo. Carga: Orulo 2.0 → `melnick`.

### 2.4 `legacy`

`cidades`, `contas`, `empreendimentos`, `fases`, `incorporadoras`, `torres`, `unidades` — arquivo da transição (sem drop).

### 2.5 Staging `public`

| Tabela | Linhas | Join sugerido |
|--------|--------|---------------|
| `stage_bseg_completa_despesas_comercias` | **0** | `cd_empreendimento` ↔ `cad.empreendimentos.cod_spe` |

### 2.6 Extensões

`pgcrypto`, `pg_trgm`, `unaccent`, `uuid-ossp`, `dblink`, `plpgsql`  
Foreign servers: **nenhum** configurado.

---

## 3. `otto`

### 3.1 Tabelas (principais por tamanho)

| Tabela | Papel |
|--------|--------|
| `unit_proposal_payment` | Parcelas / fluxo proposta |
| `realty_suggested_payment_unit_price` | Preços sugeridos |
| `unit_proposal` / `unit_proposal_history` | Propostas |
| `unit` | Unidades CRM |
| `media` / `realty_media` | Mídia |
| `customer` / `customer_process*` | Clientes / processos |
| `unit_booking*` | Reservas |
| `building` / `realty` / `realty_phase*` | Empreendimentos Otto |
| `user` / `user_real_estate` | Usuários / imobiliárias |
| `prev_propostas` / `prev_propostas_aprov` / `modelos_lineares` | Artefatos ML (Airflow previsões) |
| `n8n_chat_histories` / `n8n_chat_whatsapp` | Memória chat n8n |

Lista completa: 61 tabelas base em `public` (consultar `\dt` no `psql`).

### 3.2 Views de negócio

| View | Uso típico |
|------|------------|
| `propostas` | BI / backoffice |
| `reservas` / `reservas_only` | Reservas |
| `empreendimentos` | Dimensão realty |
| `visitas` | Visitas |
| `imobiliarias` / `executivos` / `acessos` | Rede de vendas |
| `pastas` / `pesquisas` / `orientacao` | Processos |
| `financiamento_propostas` | Crédito |
| `media_otto` / `total_unidades` | Apoio |

Origem ETL: Airflow `AtualizaPostgreSQL3.py` (RDS → local).

---

## 4. `dacoes`

| Tabela | PK | Linhas | Notas |
|--------|-----|--------|-------|
| `dacoes_itens` | `sharepoint_id` | ~2 842 | `aval_ia` ∈ {pendente, avaliado}; timestamps **sem** TZ |

---

## 5. Apps no mesmo cluster

| Banco | ~tabelas | Doc |
|-------|----------|-----|
| `n8n` | 101 | [`../../n8n/ARCHITECTURE.md`](../../n8n/ARCHITECTURE.md) |
| `chatwoot_production` | 87 | idem |

---

## 6. Fora do domínio comercial (registrar, não misturar)

### `trade`

`binance_klines`, `indicadores`, `memory`, `previsao*`, `trade_agent_ciclo`, `registro_contabil`.

### `sap_fi`

Sem relações de usuário — reservado.

### `postgres` (default do cluster)

Schema `public` limpo em **2026-08-03**: removidas ~179 tabelas + view do dump Otto legado (~1,2 GB → ~14 MB).  
Espelho oficial do CRM continua no DB **`otto`**. Schema `pgagent` preservado.

---

## 7. Queries para atualizar este inventário

```powershell
$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$env:PGPASSWORD = $env:MELNICK_PG_PASSWORD

& $psql -h localhost -U postgres -d postgres -c @"
SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size
FROM pg_database WHERE datistemplate = false
ORDER BY pg_database_size(datname) DESC;
"@

& $psql -h localhost -U postgres -d melnick -c @"
SELECT n.nspname AS schema,
       COUNT(*) FILTER (WHERE c.relkind = 'r') AS tables,
       COUNT(*) FILTER (WHERE c.relkind = 'v') AS views,
       pg_size_pretty(COALESCE(SUM(pg_total_relation_size(c.oid))
         FILTER (WHERE c.relkind IN ('r','m')), 0)) AS size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')
  AND c.relkind IN ('r','v','m')
GROUP BY 1 ORDER BY 1;
"@

& $psql -h localhost -U postgres -d melnick -c @"
SELECT 'torres' t, COUNT(*) FROM cad.torres
UNION ALL SELECT 'unidades', COUNT(*) FROM cad.unidades
UNION ALL SELECT 'orulo.units', COUNT(*) FROM orulo.units;
"@
```

Após cargas: `ANALYZE cad.torres; ANALYZE orulo.units;` (etc.) para estatísticas confiáveis no `pg_stat`.
