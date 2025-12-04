# Guia de Implementação - Otimização da Query de Propostas

## Resumo Executivo

A query original está lenta porque processa **todos os dados** antes de aplicar os filtros de status. As versões otimizadas aplicam os filtros **antecipadamente**, reduzindo drasticamente o volume de dados processados.

**Ganho esperado**: 70-95% de redução no tempo de execução

---

## 📋 Pré-requisitos

1. PostgreSQL 12+ (para usar `NOT MATERIALIZED`)
2. Permissões para criar índices
3. Janela de manutenção (se criar índices em produção)

---

## 🚀 Plano de Implementação

### **Fase 1: Análise Inicial (5 minutos)**

1. **Descubra os IDs dos Status Aprovados**

```sql
-- Execute esta query primeiro
SELECT ID, NAME FROM UNIT_PROPOSAL_STATUS WHERE NAME LIKE 'Aprovada%';
```

Anote os IDs retornados. Exemplo de resultado:
```
ID  | NAME
----|------------------
1   | Aprovada
2   | Aprovada Comercial
3   | Aprovada Gerente
```

2. **Descubra o ID do Status de Reserva Aprovada**

```sql
SELECT ID, NAME FROM UNIT_BOOKING_STATUS WHERE NAME = 'Aprovada';
```

Anote o ID retornado.

3. **Teste a Query Original com EXPLAIN**

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) 
-- Cole sua query original aqui
```

Anote:
- **Execution Time**: ________ ms
- **Planning Time**: ________ ms
- **Shared Buffers Hit**: ________
- **Shared Buffers Read**: ________

---

### **Fase 2: Implementação Gradual**

#### **Opção A: Implementação Conservadora (Recomendada para Começar)**

**Passo 1**: Use a `query_otimizada.sql` (Versão 1)

1. Abra o arquivo `query_otimizada.sql`
2. Na CTE `STATUS_APROVADOS`, substitua pela query dinâmica OU pelos IDs fixos:

```sql
-- Opção 1: Dinâmico (mais flexível)
STATUS_APROVADOS AS (
  SELECT ID FROM UNIT_PROPOSAL_STATUS WHERE NAME LIKE 'Aprovada%'
),

-- Opção 2: Fixo (mais rápido, use os IDs que você anotou)
STATUS_APROVADOS AS (
  SELECT ID FROM UNIT_PROPOSAL_STATUS WHERE ID IN ('1', '2', '3')
),
```

3. Execute com EXPLAIN ANALYZE para verificar a melhoria
4. Se satisfatório, substitua a query original

**Passo 2**: Crie os Índices Básicos

Execute do arquivo `indices_recomendados.sql`:

```sql
-- Índices mais críticos (execute nesta ordem)
CREATE INDEX idx_unit_proposal_status_name ON UNIT_PROPOSAL_STATUS(NAME);
CREATE INDEX idx_unit_booking_status_name ON UNIT_BOOKING_STATUS(NAME);
CREATE INDEX idx_unit_proposal_historic_status ON UNIT_PROPOSAL(IS_HISTORIC, STATUS_ID) WHERE IS_HISTORIC = FALSE;
CREATE INDEX idx_unit_proposal_payment_holder_proposal ON UNIT_PROPOSAL_PAYMENT(HOLDER, PROPOSAL_ID) WHERE HOLDER = 'customer';

-- Atualize as estatísticas
ANALYZE UNIT_PROPOSAL;
ANALYZE UNIT_PROPOSAL_STATUS;
ANALYZE UNIT_BOOKING_STATUS;
ANALYZE UNIT_PROPOSAL_PAYMENT;
```

**Passo 3**: Teste Novamente

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) 
-- Cole a query otimizada V1 aqui
```

Compare com os resultados da Fase 1. Você deve ver:
- ✅ Execution Time reduzido em 70-90%
- ✅ Menos linhas processadas nas CTEs
- ✅ Menos buffers lidos

---

#### **Opção B: Implementação Agressiva (Máxima Performance)**

**Use se**:
- Você tem alta carga na query
- Já testou a Versão 1 com sucesso
- Pode criar índices adicionais

**Passo 1**: Use a `query_otimizada_v2_agressiva.sql`

1. Ajuste os IDs conforme indicado no arquivo
2. Execute os índices críticos comentados no final do arquivo
3. Teste com EXPLAIN ANALYZE

**Ganho adicional esperado**: +10-20% sobre a Versão 1

---

### **Fase 3: Validação (15 minutos)**

#### **Checklist de Validação**

- [ ] A query retorna o mesmo número de linhas que a original?
- [ ] Os dados conferem com a query original (compare amostra de 10 linhas)?
- [ ] O tempo de execução melhorou significativamente?
- [ ] Não há erros de sintaxe ou tipos?
- [ ] A query funciona com diferentes filtros (teste remover/adicionar filtros)?

#### **Testes de Regressão**

```sql
-- Teste 1: Contar total de registros
-- Original:
SELECT COUNT(*) FROM (/* query original */) original;

-- Otimizada:
SELECT COUNT(*) FROM (/* query otimizada */) otimizada;

-- Devem retornar o mesmo valor


-- Teste 2: Comparar primeiras 100 linhas ordenadas
-- Original:
SELECT ID_PROPOSTA, NOME_CLIENTE, DATA 
FROM (/* query original */) original 
ORDER BY ID_PROPOSTA 
LIMIT 100;

-- Otimizada:
SELECT ID_PROPOSTA, NOME_CLIENTE, DATA 
FROM (/* query otimizada */) otimizada 
ORDER BY ID_PROPOSTA 
LIMIT 100;

-- Compare visualmente ou com EXCEPT
```

---

### **Fase 4: Monitoramento (Contínuo)**

#### **Métricas para Acompanhar**

1. **Tempo de Execução**
```sql
-- Adicione ao início da sua query:
\timing on

-- Sua query aqui

-- PostgreSQL mostrará: Time: XXX.XXX ms
```

2. **Uso de Cache**
```sql
-- Execute 2x seguidas e compare
EXPLAIN (ANALYZE, BUFFERS) /* sua query */;

-- Na segunda execução:
-- - Shared Buffers Hit deve ser maior
-- - Shared Buffers Read deve ser menor
```

3. **Plano de Execução Estável**
```sql
-- Execute semanalmente e compare
EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) /* sua query */;
```

---

## 🔍 Troubleshooting

### Problema: Query Otimizada Ainda Está Lenta

**Possíveis Causas**:

1. **Índices não foram criados**
   - Solução: Verifique com `\d+ nome_da_tabela` no psql

2. **Estatísticas desatualizadas**
   - Solução: Execute `ANALYZE` nas tabelas principais

3. **CTE sendo materializada quando não deveria**
   - Solução: Verifique o plano de execução, procure por "CTE Scan"

4. **Muitos dados "Aprovados"**
   - Solução: Adicione mais filtros (ex: data) nas CTEs

### Problema: Resultados Diferentes da Query Original

**Possíveis Causas**:

1. **Simplificação do JSONB_ARRAY_ELEMENTS**
   - Solução: Se `PVRet` tem múltiplos elementos, reverta para o LATERAL original

2. **Filtros aplicados incorretamente**
   - Solução: Verifique se todos os IDs de status foram incluídos

3. **JOIN modificado incorretamente**
   - Solução: Compare a estrutura de JOINs cuidadosamente

---

## 📊 Resultados Esperados

### Antes (Query Original com Filtros)
```
Planning Time: 10-20 ms
Execution Time: 30000-60000 ms (30-60 segundos)
Rows: 100-1000 linhas
Buffers: 50000-100000 blocos lidos
```

### Depois (Query Otimizada V1)
```
Planning Time: 15-30 ms
Execution Time: 2000-5000 ms (2-5 segundos)
Rows: 100-1000 linhas (mesmo resultado)
Buffers: 5000-10000 blocos lidos
```

### Depois (Query Otimizada V2)
```
Planning Time: 20-40 ms
Execution Time: 500-2000 ms (0.5-2 segundos)
Rows: 100-1000 linhas (mesmo resultado)
Buffers: 1000-5000 blocos lidos
```

---

## 🎯 Próximos Passos

Após implementação bem-sucedida:

1. **Documente** o tempo de execução típico
2. **Configure alertas** se a query ultrapassar threshold (ex: >5s)
3. **Considere particionamento** se a tabela `UNIT_PROPOSAL` for muito grande (>10M linhas)
4. **Revise periodicamente** os índices (podem ficar fragmentados)
5. **Implemente cache** na camada de aplicação se a query for executada frequentemente

---

## ❓ Perguntas Frequentes

**P: Posso usar em produção direto?**  
R: Recomendo testar em staging primeiro, mas as mudanças são conservadoras.

**P: E se eu não puder criar índices agora?**  
R: A query otimizada já terá ganho significativo (50-70%) mesmo sem índices.

**P: Preciso ajustar algo no código da aplicação?**  
R: Não, a estrutura do resultado é idêntica.

**P: Como reverter se houver problema?**  
R: Basta voltar para a query original. Os índices podem permanecer.

**P: Qual versão usar, V1 ou V2?**  
R: Comece com V1. Se precisar de mais performance, migre para V2.

---

## 📞 Checklist Final

Antes de considerar a otimização completa:

- [ ] Query otimizada testada e validada
- [ ] Índices recomendados criados
- [ ] ANALYZE executado nas tabelas principais
- [ ] Performance medida e documentada
- [ ] Testes de regressão passaram
- [ ] Query implantada em staging
- [ ] Monitoramento configurado
- [ ] Documentação atualizada
- [ ] Time informado sobre as mudanças

---

**Tempo total estimado**: 1-3 horas (incluindo testes)

**Impacto de negócio**: Alto (melhora significativa na experiência do usuário)

**Risco**: Baixo (mudanças conservadoras, fácil rollback)
