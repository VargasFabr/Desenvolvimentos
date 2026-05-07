# Otimizações Específicas para os Filtros de Status

## Problema Principal

Os filtros `PROPOSTA.NAME LIKE 'Aprovada%'` e `STATUS_RESERVA.NAME = 'Aprovada'` estão sendo aplicados **DEPOIS** de todo o processamento das CTEs e JOINs complexos.

## Otimizações Específicas

### 1. Filtrar por STATUS_ID Dentro da CTE PROPOSTA ⭐ (MELHOR OPÇÃO)

**Problema**: O filtro por NAME está sendo feito no final, mas na CTE já temos acesso ao STATUS_ID.

**Solução**: Identificar os IDs dos status 'Aprovada' e filtrar diretamente na CTE PROPOSTA.

```sql
-- Primeiro, descubra os IDs dos status 'Aprovada':
SELECT ID, NAME FROM UNIT_PROPOSAL_STATUS WHERE NAME LIKE 'Aprovada%';
-- Suponha que retorne: '1', '2', '3' (exemplo)

-- Então, na CTE PROPOSTA, adicione ao WHERE:
WHERE I.IS_HISTORIC = FALSE 
  AND I.STATUS_ID NOT IN ('6')
  AND I.STATUS_ID IN ('1', '2', '3')  -- IDs dos status 'Aprovada%'
```

**Impacto**: Reduz drasticamente o número de linhas processadas desde o início.

---

### 2. Aplicar Filtro de STATUS_RESERVA Antes do JOIN Principal

**Problema**: O JOIN com UNIT_BOOKING está processando todas as reservas.

**Solução**: Criar uma CTE para filtrar as reservas aprovadas primeiro.

```sql
WITH RESERVAS_APROVADAS AS (
  SELECT 
    RESERVA.ID,
    RESERVA.CUSTOMER_PROCESS_ID,
    STATUS_RESERVA.NAME
  FROM UNIT_BOOKING RESERVA
  JOIN UNIT_BOOKING_STATUS STATUS_RESERVA 
    ON RESERVA.UNIT_BOOKING_STATUS_ID = STATUS_RESERVA.ID
  WHERE STATUS_RESERVA.NAME = 'Aprovada'
)
```

Depois use essa CTE no lugar do JOIN original:

```sql
JOIN RESERVAS_APROVADAS ON PROCESSOS.ID = RESERVAS_APROVADAS.CUSTOMER_PROCESS_ID
```

**Impacto**: Reduz o número de JOINs complexos executados.

---

### 3. Usar CTEs NOT MATERIALIZED (PostgreSQL 12+)

**Problema**: CTEs materializadas impedem o push-down de filtros.

**Solução**: Adicionar NOT MATERIALIZED às CTEs que devem ser otimizadas inline.

```sql
WITH PAGAMENTOS AS NOT MATERIALIZED (
  -- query original
),
REGISTRO AS NOT MATERIALIZED (
  -- query original  
),
PROPOSTA AS NOT MATERIALIZED (
  -- query original
)
```

**Importante**: Use com cuidado. Algumas CTEs devem permanecer materializadas (como PAGAMENTOS se for referenciada múltiplas vezes).

**Impacto**: Permite que o otimizador empurre filtros para dentro das CTEs.

---

### 4. Adicionar Filtros Adicionais nas CTEs

**Na CTE PAGAMENTOS**:
```sql
-- Adicione um filtro para processar apenas propostas relevantes
WHERE UPP.HOLDER = 'customer'
  AND UPP.PROPOSAL_ID IN (
    SELECT ID FROM UNIT_PROPOSAL 
    WHERE IS_HISTORIC = FALSE 
      AND STATUS_ID NOT IN ('6')
      AND STATUS_ID IN ('1', '2', '3')  -- IDs aprovados
  )
```

**Impacto**: Reduz agregações desnecessárias.

---

### 5. Otimizar o LATERAL JOIN de SALES_EXECUTIVE_PORTFOLIO

**Problema**: O LEFT JOIN LATERAL está executando duas subqueries com COALESCE para cada linha.

**Solução**: Simplificar usando UNION ALL e DISTINCT ON.

```sql
LEFT JOIN LATERAL (
  SELECT DISTINCT ON (1)
    SEP.USER_CLIENT_TEAM_PROFILE_ID
  FROM (
    SELECT USER_CLIENT_TEAM_PROFILE_ID, 1 as priority
    FROM SALES_EXECUTIVE_PORTFOLIO SEP
    INNER JOIN USER_CLIENT_TEAM_PROFILE UCTP_CHECK 
      ON UCTP_CHECK.ID = SEP.USER_CLIENT_TEAM_PROFILE_ID
    WHERE SEP.REAL_ESTATE_AGENCY_ID = RS.ID
      AND UCTP_CHECK.CLIENT_ID = CLIENT.ID
      AND UCTP_CHECK.CLIENT_TEAM_PROFILE_ID = 'SalesExecutive'
    
    UNION ALL
    
    SELECT USER_CLIENT_TEAM_PROFILE_ID, 2 as priority
    FROM SALES_EXECUTIVE_PORTFOLIO SEP
    INNER JOIN USER_CLIENT_TEAM_PROFILE UCTP_CHECK 
      ON UCTP_CHECK.ID = SEP.USER_CLIENT_TEAM_PROFILE_ID
    WHERE SEP.INDEPENDENT_USER_REAL_ESTATE_AGENCY_ID = URE.ID
      AND UCTP_CHECK.CLIENT_ID = CLIENT.ID
      AND UCTP_CHECK.CLIENT_TEAM_PROFILE_ID = 'SalesExecutive'
  ) combined
  ORDER BY priority
  LIMIT 1
) SEP_UNIFICADO ON COALESCE(RS.MUST_ASSIGN_SALES_EXECUTIVE, FALSE) = TRUE
```

**Impacto**: Reduz o número de scans nas tabelas dentro do LATERAL.

---

### 6. Remover JSONB_ARRAY_ELEMENTS se Não For Essencial

**Problema**: O LATERAL JOIN com `JSONB_ARRAY_ELEMENTS` processa JSON para cada linha.

```sql
LEFT JOIN LATERAL JSONB_ARRAY_ELEMENTS(
  I.WEBHOOK_INVOCATION_RESULT_METADATA -> 'rawResponse' -> 'PVRet'
) AS PVR (VALUE) ON TRUE
```

**Análise**: 
- Se `PVRet` é um array com um único elemento na maioria dos casos, considere usar `-> 0` ao invés de `JSONB_ARRAY_ELEMENTS`.
- Se é realmente necessário iterar, considere filtrar primeiro.

**Solução Alternativa**:
```sql
-- Se você precisa apenas do primeiro elemento:
PVR.VALUE ->> 'PnvCod' AS CODIGO_GC
-- pode ser substituído por:
I.WEBHOOK_INVOCATION_RESULT_METADATA -> 'rawResponse' -> 'PVRet' -> 0 ->> 'PnvCod' AS CODIGO_GC
```

---

### 7. Criar Índice de Cobertura (Covering Index)

**Para a tabela UNIT_PROPOSAL_STATUS**:
```sql
CREATE INDEX idx_unit_proposal_status_covering 
ON UNIT_PROPOSAL_STATUS(ID) 
INCLUDE (NAME);
```

**Para a tabela UNIT_BOOKING_STATUS**:
```sql
CREATE INDEX idx_unit_booking_status_covering 
ON UNIT_BOOKING_STATUS(ID) 
INCLUDE (NAME);
```

**Impacto**: Permite index-only scans, evitando acesso à tabela.

---

## Ordem de Implementação Recomendada

1. **Passo 1** (Maior Impacto, Menor Esforço):
   - Identificar os STATUS_ID dos status 'Aprovada%'
   - Adicionar filtro `STATUS_ID IN (...)` na CTE PROPOSTA
   - Criar CTE RESERVAS_APROVADAS

2. **Passo 2** (Médio Impacto, Baixo Esforço):
   - Adicionar índices recomendados (especialmente em STATUS.NAME)
   - Executar ANALYZE nas tabelas

3. **Passo 3** (Refinar):
   - Testar com NOT MATERIALIZED
   - Otimizar LATERAL JOINs se ainda houver problemas

4. **Passo 4** (Se ainda necessário):
   - Simplificar JSONB operations
   - Considerar particionamento de tabelas grandes

---

## Medição de Performance

Antes e depois de cada mudança, execute:

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) 
-- sua query aqui
```

Compare:
- **Planning Time**: tempo de planejamento
- **Execution Time**: tempo de execução
- **Rows**: número de linhas processadas em cada etapa
- **Shared Buffers**: I/O realizado

---

## Ganho Esperado

Com as otimizações 1 e 2 implementadas:
- **Redução de tempo esperada**: 70-95%
- **Redução de I/O**: 80-90%
- **Redução de memória**: 60-80%

Se a query atualmente leva 30 segundos, deve cair para 1.5-9 segundos.
