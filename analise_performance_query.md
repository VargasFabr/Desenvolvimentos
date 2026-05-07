# Análise de Performance da Query de Propostas

## Problema Identificado

A query está extremamente lenta quando os filtros são aplicados:
- `PROPOSTA.NAME LIKE 'Aprovada%'`
- `STATUS_RESERVA.NAME = 'Aprovada'`

Mas rápida quando executada sem esses filtros.

## Causas Raiz do Problema

### 1. **CTEs Materializadas Processando Dados Desnecessários**

Por padrão, o PostgreSQL pode materializar CTEs, o que significa que:
- A CTE `PROPOSTA` está processando TODAS as propostas do banco
- A CTE `PAGAMENTOS` está calculando valores para TODAS as propostas
- A CTE `REGISTRO` está processando TODOS os registros de user_real_estate
- Todos os JOINs são executados com datasets completos
- **Somente no final** os filtros são aplicados

Isso resulta em:
- Processamento massivo de dados que serão descartados
- JOINs complexos desnecessários
- Alto uso de memória e I/O

### 2. **Filtros Aplicados Tardiamente**

Os filtros de status estão no WHERE da query principal, não dentro das CTEs. Isso impede que o otimizador do PostgreSQL "empurre" esses filtros para baixo na árvore de execução.

### 3. **JOINs com LATERAL Potencialmente Custosos**

A query tem vários LEFT JOIN LATERAL que são executados para cada linha:
```sql
LEFT JOIN LATERAL JSONB_ARRAY_ELEMENTS(...) AS PVR
LEFT JOIN LATERAL (SELECT STATUS_ID, CREATED_AT FROM UNIT_PROPOSAL_HISTORY ...)
LEFT JOIN LATERAL (SELECT COALESCE(...) AS USER_CLIENT_TEAM_PROFILE_ID)
```

Esses JOINs laterais são executados para todas as linhas antes da filtragem.

### 4. **Falta de Filtros nos STATUS_ID**

A CTE PROPOSTA filtra apenas:
```sql
WHERE I.IS_HISTORIC = FALSE AND I.STATUS_ID NOT IN ('6')
```

Mas não filtra pelos status que realmente interessam. O filtro `PROPOSTA.NAME LIKE 'Aprovada%'` está sendo aplicado muito tarde.

### 5. **Possível Falta de Índices**

Provavelmente faltam índices em:
- `UNIT_PROPOSAL_STATUS.NAME`
- `UNIT_BOOKING_STATUS.NAME`
- `UNIT_PROPOSAL.STATUS_ID` com filtro WHERE
- `UNIT_BOOKING.UNIT_BOOKING_STATUS_ID`

## Soluções Propostas

### Solução 1: Filtrar Dentro das CTEs (Mais Simples)

Aplicar os filtros dentro da CTE `PROPOSTA` para reduzir o dataset desde o início.

### Solução 2: Usar CTEs NOT MATERIALIZED (PostgreSQL 12+)

Forçar o PostgreSQL a não materializar as CTEs, permitindo que o otimizador faça push-down dos filtros.

### Solução 3: Adicionar Índices Específicos

Criar índices nas colunas de status e nos campos mais consultados.

### Solução 4: Refatorar para Subqueries Inline

Transformar CTEs em subqueries onde faz sentido para melhor otimização.

### Solução 5: Filtrar por STATUS_ID ao invés de NAME

Se possível, mapear os IDs dos status 'Aprovada%' e filtrar por ID na CTE PROPOSTA.

## Impacto Estimado

| Solução | Ganho Esperado | Complexidade | Risco |
|---------|----------------|--------------|-------|
| Filtrar nas CTEs | 70-90% | Baixa | Baixo |
| NOT MATERIALIZED | 60-80% | Muito Baixa | Muito Baixo |
| Adicionar Índices | 50-70% | Média | Baixo |
| Filtrar por STATUS_ID | 80-95% | Baixa | Baixo |
| Refatorar Subqueries | 70-85% | Alta | Médio |

## Recomendações Priorizadas

1. **Primeiro**: Filtrar por STATUS_ID dentro da CTE PROPOSTA
2. **Segundo**: Usar NOT MATERIALIZED nas CTEs
3. **Terceiro**: Adicionar índices nas colunas de status
4. **Quarto**: Otimizar os JOINs LATERAL se necessário
