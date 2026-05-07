# 🛠️ Comandos Úteis - Otimização de Query

## 📊 Análise e Diagnóstico

### 1. Descobrir IDs dos Status

```sql
-- Status de Propostas
SELECT ID, NAME 
FROM UNIT_PROPOSAL_STATUS 
WHERE NAME LIKE 'Aprovada%'
ORDER BY NAME;

-- Status de Reservas
SELECT ID, NAME 
FROM UNIT_BOOKING_STATUS 
WHERE NAME = 'Aprovada';
```

### 2. Analisar Performance da Query Original

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT TEXT)
-- Cole sua query original aqui
;
```

### 3. Ver Tempo de Execução Simples

```sql
\timing on

-- Sua query aqui

-- PostgreSQL mostrará: Time: XXX.XXX ms
```

### 4. Verificar Índices Existentes

```sql
-- Para uma tabela específica
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'unit_proposal'
ORDER BY indexname;

-- Para todas as tabelas relacionadas
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename IN (
    'unit_proposal', 
    'unit_proposal_status', 
    'unit_booking_status',
    'unit_proposal_payment', 
    'user_real_estate', 
    'unit_proposal_history',
    'customer', 
    'unit_booking', 
    'customer_process', 
    'user_client_team_profile', 
    'sales_executive_portfolio'
)
ORDER BY tablename, indexname;
```

### 5. Verificar Estatísticas das Tabelas

```sql
-- Última vez que ANALYZE foi executado
SELECT 
    schemaname,
    relname as table_name,
    last_analyze,
    last_autoanalyze,
    n_live_tup as row_count,
    n_dead_tup as dead_rows
FROM pg_stat_user_tables
WHERE relname IN (
    'unit_proposal', 
    'unit_proposal_status', 
    'unit_booking_status'
)
ORDER BY relname;
```

### 6. Tamanho das Tabelas

```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE tablename IN (
    'unit_proposal', 
    'unit_proposal_status', 
    'unit_booking_status',
    'unit_proposal_payment'
)
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 🔧 Manutenção e Otimização

### 1. Atualizar Estatísticas (Execute após criar índices)

```sql
ANALYZE UNIT_PROPOSAL;
ANALYZE UNIT_PROPOSAL_STATUS;
ANALYZE UNIT_BOOKING_STATUS;
ANALYZE UNIT_PROPOSAL_PAYMENT;
ANALYZE USER_REAL_ESTATE;
ANALYZE UNIT_PROPOSAL_HISTORY;
ANALYZE CUSTOMER;
ANALYZE UNIT_BOOKING;
ANALYZE CUSTOMER_PROCESS;
ANALYZE USER_CLIENT_TEAM_PROFILE;
ANALYZE SALES_EXECUTIVE_PORTFOLIO;
```

### 2. VACUUM para Limpar Espaço

```sql
-- Vacuum normal (não bloqueia)
VACUUM ANALYZE UNIT_PROPOSAL;

-- Vacuum full (requer lock exclusivo - use com cuidado)
-- VACUUM FULL UNIT_PROPOSAL;
```

### 3. Reindexar (se índices estiverem fragmentados)

```sql
-- Reindexar uma tabela específica
REINDEX TABLE UNIT_PROPOSAL;

-- Reindexar um índice específico
REINDEX INDEX idx_unit_proposal_historic_status;
```

### 4. Verificar Bloat (Inchaço) de Índices

```sql
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    idx_scan as index_scans
FROM pg_stat_user_indexes
JOIN pg_index USING (indexrelid)
WHERE schemaname = 'public'
  AND tablename IN (
      'unit_proposal', 
      'unit_proposal_status', 
      'unit_booking_status'
  )
ORDER BY pg_relation_size(indexrelid) DESC;
```

---

## 🧪 Testes e Validação

### 1. Comparar Contagem de Linhas

```sql
-- Query Original
SELECT COUNT(*) as total_original
FROM (
    -- Cole query original aqui
) original;

-- Query Otimizada
SELECT COUNT(*) as total_otimizada
FROM (
    -- Cole query otimizada aqui
) otimizada;

-- Devem retornar o mesmo valor!
```

### 2. Comparar Primeiras N Linhas

```sql
-- Query Original
(
    SELECT 
        ID_PROPOSTA, 
        NOME_CLIENTE, 
        DATA,
        'original' as source
    FROM (
        -- Cole query original aqui
    ) original 
    ORDER BY ID_PROPOSTA 
    LIMIT 100
)
UNION ALL
(
    SELECT 
        ID_PROPOSTA, 
        NOME_CLIENTE, 
        DATA,
        'otimizada' as source
    FROM (
        -- Cole query otimizada aqui
    ) otimizada 
    ORDER BY ID_PROPOSTA 
    LIMIT 100
)
ORDER BY ID_PROPOSTA, source;
```

### 3. Encontrar Diferenças

```sql
-- Linhas na original mas não na otimizada
(
    SELECT ID_PROPOSTA, NOME_CLIENTE 
    FROM (/* query original */) original
)
EXCEPT
(
    SELECT ID_PROPOSTA, NOME_CLIENTE 
    FROM (/* query otimizada */) otimizada
);

-- Linhas na otimizada mas não na original
(
    SELECT ID_PROPOSTA, NOME_CLIENTE 
    FROM (/* query otimizada */) otimizada
)
EXCEPT
(
    SELECT ID_PROPOSTA, NOME_CLIENTE 
    FROM (/* query original */) original
);

-- Se ambas retornarem 0 linhas, queries são equivalentes!
```

### 4. Testar com Diferentes Filtros

```sql
-- Teste 1: Todas as propostas aprovadas
SELECT COUNT(*) FROM (/* sua query */) WHERE STATUS_PROPOSTA LIKE 'Aprovada%';

-- Teste 2: Apenas um empreendimento
SELECT COUNT(*) FROM (/* sua query */) WHERE ID_EMPREENDIMENTO = 'XXX';

-- Teste 3: Range de datas
SELECT COUNT(*) FROM (/* sua query */) WHERE DATA BETWEEN '2024-01-01' AND '2024-12-31';

-- Teste 4: Cliente específico
SELECT COUNT(*) FROM (/* sua query */) WHERE CPF_CLIENTE = '123.456.789-00';
```

---

## 📈 Monitoramento Contínuo

### 1. Monitorar Queries Lentas

```sql
-- Queries mais lentas (requer pg_stat_statements)
SELECT 
    substring(query, 1, 100) as query_snippet,
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time,
    rows
FROM pg_stat_statements
WHERE query LIKE '%PROPOSTAS%'
  OR query LIKE '%unit_proposal%'
ORDER BY mean_exec_time DESC
LIMIT 20;
```

### 2. Monitorar Uso de Cache

```sql
-- Cache hit ratio (deve ser > 90%)
SELECT 
    sum(heap_blks_read) as heap_read,
    sum(heap_blks_hit)  as heap_hit,
    sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100 as cache_hit_ratio
FROM pg_statio_user_tables
WHERE relname IN (
    'unit_proposal', 
    'unit_proposal_status', 
    'unit_booking_status'
);
```

### 3. Monitorar Locks

```sql
-- Verificar locks ativos
SELECT 
    l.pid,
    l.mode,
    l.granted,
    a.usename,
    a.query,
    a.query_start
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE l.relation IN (
    'unit_proposal'::regclass,
    'unit_proposal_status'::regclass
)
ORDER BY a.query_start;
```

### 4. Monitorar Conexões Ativas

```sql
-- Queries ativas no momento
SELECT 
    pid,
    usename,
    application_name,
    state,
    query_start,
    state_change,
    substring(query, 1, 100) as query
FROM pg_stat_activity
WHERE state = 'active'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY query_start;
```

---

## 🎯 Comparação de Performance

### 1. Comparar Planos de Execução

```sql
-- Salvar plano da query original
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
-- Query original aqui
;
-- Salve o resultado em arquivo: plano_original.json

-- Salvar plano da query otimizada
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
-- Query otimizada aqui
;
-- Salve o resultado em arquivo: plano_otimizado.json

-- Compare usando ferramenta: https://explain.dalibo.com/
```

### 2. Benchmark Simples

```sql
-- Execute 10 vezes e tire a média

-- Query Original
\timing on
SELECT COUNT(*) FROM (/* query original */) q; -- Rodada 1
SELECT COUNT(*) FROM (/* query original */) q; -- Rodada 2
SELECT COUNT(*) FROM (/* query original */) q; -- Rodada 3
-- ... até 10

-- Query Otimizada
\timing on
SELECT COUNT(*) FROM (/* query otimizada */) q; -- Rodada 1
SELECT COUNT(*) FROM (/* query otimizada */) q; -- Rodada 2
SELECT COUNT(*) FROM (/* query otimizada */) q; -- Rodada 3
-- ... até 10

-- Calcule média e compare
```

### 3. Teste de Carga

```bash
# Usando pgbench (se disponível)
# Crie arquivo query_original.sql com a query original
# Crie arquivo query_otimizada.sql com a query otimizada

pgbench -f query_original.sql -c 10 -t 5 -n seu_banco
pgbench -f query_otimizada.sql -c 10 -t 5 -n seu_banco

# -c 10: 10 conexões simultâneas
# -t 5: 5 transações por conexão
# -n: não executar script de inicialização
```

---

## 🔍 Diagnóstico Avançado

### 1. Verificar Fragmentação de Índices

```sql
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE tablename IN ('unit_proposal', 'unit_proposal_status')
  AND attname IN ('status_id', 'name', 'is_historic')
ORDER BY tablename, attname;
```

### 2. Verificar Uso de Trabalho Temporário

```sql
-- Configuração atual
SHOW work_mem;
SHOW temp_buffers;

-- Queries usando disco temporário (evitar!)
SELECT 
    query,
    temp_blks_read,
    temp_blks_written
FROM pg_stat_statements
WHERE temp_blks_written > 0
ORDER BY temp_blks_written DESC
LIMIT 10;
```

### 3. Analisar Custos do Plano

```sql
EXPLAIN (ANALYZE, COSTS, BUFFERS)
-- Sua query aqui
;

-- Procure por:
-- - Alto custo em operações específicas
-- - Estimativas muito diferentes de valores reais
-- - Sorts/Hashes usando disco (temp)
```

---

## 🚨 Troubleshooting Rápido

### Problema: Query ainda lenta após otimização

```sql
-- 1. Verifique se índices foram usados
EXPLAIN (ANALYZE, BUFFERS)
-- Sua query otimizada
;
-- Procure por "Seq Scan" - deveria ser "Index Scan"

-- 2. Verifique se estatísticas estão atualizadas
SELECT 
    relname, 
    last_analyze, 
    last_autoanalyze
FROM pg_stat_user_tables
WHERE relname = 'unit_proposal';
-- Se last_analyze é NULL ou muito antigo, execute ANALYZE

-- 3. Verifique tamanho das tabelas
SELECT 
    relname,
    n_live_tup
FROM pg_stat_user_tables
WHERE relname IN ('unit_proposal', 'unit_booking');
-- Se muito grande (>10M), considere particionamento
```

### Problema: Plano de execução ruim

```sql
-- 1. Force re-planeamento
DISCARD PLANS;

-- 2. Aumente estatísticas
ALTER TABLE unit_proposal ALTER COLUMN status_id SET STATISTICS 1000;
ANALYZE unit_proposal;

-- 3. Desabilite temporariamente optimizações para testar
-- (NÃO FAÇA EM PRODUÇÃO!)
-- SET enable_seqscan = off;
-- SET enable_nestloop = off;
```

### Problema: Timeout

```sql
-- 1. Verifique timeout atual
SHOW statement_timeout;

-- 2. Aumente temporariamente (em milissegundos)
SET statement_timeout = '60000'; -- 60 segundos

-- 3. Ou desabilite para debugging (CUIDADO!)
-- SET statement_timeout = 0;
```

---

## 📝 Template de Relatório de Performance

```sql
-- Execute este bloco completo para gerar relatório

\echo '=== RELATÓRIO DE PERFORMANCE ==='
\echo ''
\echo 'Data/Hora:' 
SELECT now();
\echo ''

\echo '--- 1. CONTAGEM DE LINHAS ---'
SELECT COUNT(*) as total_linhas FROM (/* sua query */) q;
\echo ''

\echo '--- 2. TEMPO DE EXECUÇÃO ---'
\timing on
SELECT COUNT(*) FROM (/* sua query */) q;
\timing off
\echo ''

\echo '--- 3. PLANO DE EXECUÇÃO (resumido) ---'
EXPLAIN (ANALYZE, BUFFERS, SUMMARY)
/* sua query */
;
\echo ''

\echo '--- 4. USO DE CACHE ---'
SELECT 
    'Cache Hit Ratio: ' || 
    round((sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read))) * 100, 2) || '%'
FROM pg_statio_user_tables
WHERE relname = 'unit_proposal';
\echo ''

\echo '--- 5. ESTATÍSTICAS DAS PRINCIPAIS TABELAS ---'
SELECT 
    relname,
    n_live_tup as linhas,
    last_analyze
FROM pg_stat_user_tables
WHERE relname IN ('unit_proposal', 'unit_booking', 'unit_proposal_status')
ORDER BY relname;
\echo ''

\echo '=== FIM DO RELATÓRIO ==='
```

---

## 💾 Backup de Índices

```sql
-- Gerar script para recriar todos os índices
SELECT 
    'DROP INDEX IF EXISTS ' || indexname || '; ' ||
    indexdef || ';'
FROM pg_indexes 
WHERE tablename IN (
    'unit_proposal', 
    'unit_proposal_status', 
    'unit_booking_status'
)
ORDER BY tablename, indexname;

-- Salve o resultado para poder recriar índices se necessário
```

---

## 🎓 Comandos para Aprendizado

### Ver todas as tabelas relacionadas

```sql
SELECT 
    table_name,
    pg_size_pretty(pg_total_relation_size(table_name::regclass)) as size
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE '%proposal%'
  OR table_name LIKE '%booking%'
ORDER BY pg_total_relation_size(table_name::regclass) DESC;
```

### Ver todas as colunas de uma tabela

```sql
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'unit_proposal'
ORDER BY ordinal_position;
```

### Ver constraints e foreign keys

```sql
SELECT
    tc.constraint_name,
    tc.constraint_type,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
LEFT JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.table_name = 'unit_proposal';
```

---

**Dica Final**: Sempre teste em ambiente de desenvolvimento/staging antes de executar em produção! 🚀
