-- ============================================================
-- ÍNDICES RECOMENDADOS PARA OTIMIZAÇÃO DA QUERY DE PROPOSTAS
-- ============================================================

-- 1. ÍNDICE NA TABELA UNIT_PROPOSAL_STATUS
-- Melhora filtros por NAME (especialmente 'Aprovada%')
CREATE INDEX IF NOT EXISTS idx_unit_proposal_status_name 
ON UNIT_PROPOSAL_STATUS(NAME);

-- Índice composto para melhorar JOINs
CREATE INDEX IF NOT EXISTS idx_unit_proposal_status_id_name 
ON UNIT_PROPOSAL_STATUS(ID, NAME);

-- 2. ÍNDICE NA TABELA UNIT_BOOKING_STATUS
-- Melhora filtros por NAME (especialmente 'Aprovada')
CREATE INDEX IF NOT EXISTS idx_unit_booking_status_name 
ON UNIT_BOOKING_STATUS(NAME);

-- Índice composto para melhorar JOINs
CREATE INDEX IF NOT EXISTS idx_unit_booking_status_id_name 
ON UNIT_BOOKING_STATUS(ID, NAME);

-- 3. ÍNDICES NA TABELA UNIT_PROPOSAL
-- Índice composto para filtros comuns
CREATE INDEX IF NOT EXISTS idx_unit_proposal_historic_status 
ON UNIT_PROPOSAL(IS_HISTORIC, STATUS_ID) 
WHERE IS_HISTORIC = FALSE AND STATUS_ID NOT IN ('6');

-- Índice para relação com customer
CREATE INDEX IF NOT EXISTS idx_unit_proposal_customer_unit 
ON UNIT_PROPOSAL(CUSTOMER_ID, UNIT_ID) 
WHERE IS_HISTORIC = FALSE;

-- Índice para melhorar ORDER BY na query principal
CREATE INDEX IF NOT EXISTS idx_unit_proposal_created_at 
ON UNIT_PROPOSAL(CREATED_AT DESC) 
WHERE IS_HISTORIC = FALSE;

-- 4. ÍNDICE NA TABELA UNIT_PROPOSAL_PAYMENT
-- Melhora agregações na CTE PAGAMENTOS
CREATE INDEX IF NOT EXISTS idx_unit_proposal_payment_holder_proposal 
ON UNIT_PROPOSAL_PAYMENT(HOLDER, PROPOSAL_ID) 
WHERE HOLDER = 'customer';

-- 5. ÍNDICE NA TABELA USER_REAL_ESTATE
-- Melhora a CTE REGISTRO
CREATE INDEX IF NOT EXISTS idx_user_real_estate_user_deleted 
ON USER_REAL_ESTATE(USER_ID, BOND_CONFIRMATION_AT DESC, ID DESC) 
WHERE DELETED_AT IS NULL;

-- 6. ÍNDICE NA TABELA UNIT_PROPOSAL_HISTORY
-- Melhora o LEFT JOIN LATERAL na CTE PROPOSTA
CREATE INDEX IF NOT EXISTS idx_unit_proposal_history_proposal_updated 
ON UNIT_PROPOSAL_HISTORY(PROPOSAL_ID, UPDATED_AT DESC, STATUS_ID);

-- 7. ÍNDICE NA TABELA CUSTOMER
-- Melhora JOINs e filtros
CREATE INDEX IF NOT EXISTS idx_customer_realtor 
ON CUSTOMER(REALTOR_ID, NAME);

-- 8. ÍNDICE NA TABELA UNIT_BOOKING
-- Melhora JOIN e filtro
CREATE INDEX IF NOT EXISTS idx_unit_booking_process_status 
ON UNIT_BOOKING(CUSTOMER_PROCESS_ID, UNIT_BOOKING_STATUS_ID);

-- 9. ÍNDICE NA TABELA CUSTOMER_PROCESS
-- Melhora JOINs múltiplos
CREATE INDEX IF NOT EXISTS idx_customer_process_unit_ure 
ON CUSTOMER_PROCESS(UNIT_ID, USER_REAL_ESTATE_ID);

-- 10. ÍNDICE NA TABELA USER_CLIENT_TEAM_PROFILE
-- Melhora o LATERAL JOIN complexo
CREATE INDEX IF NOT EXISTS idx_uctp_client_profile 
ON USER_CLIENT_TEAM_PROFILE(CLIENT_ID, CLIENT_TEAM_PROFILE_ID, ID, USER_ID) 
WHERE CLIENT_TEAM_PROFILE_ID = 'SalesExecutive';

-- 11. ÍNDICE NA TABELA SALES_EXECUTIVE_PORTFOLIO
-- Melhora os dois SELECTs dentro do LATERAL JOIN
CREATE INDEX IF NOT EXISTS idx_sep_real_estate_agency 
ON SALES_EXECUTIVE_PORTFOLIO(REAL_ESTATE_AGENCY_ID, USER_CLIENT_TEAM_PROFILE_ID);

CREATE INDEX IF NOT EXISTS idx_sep_independent_ure_agency 
ON SALES_EXECUTIVE_PORTFOLIO(INDEPENDENT_USER_REAL_ESTATE_AGENCY_ID, USER_CLIENT_TEAM_PROFILE_ID);

-- ============================================================
-- VERIFICAR ÍNDICES EXISTENTES ANTES DE CRIAR
-- ============================================================
-- Para verificar índices existentes, execute:
-- SELECT indexname, indexdef 
-- FROM pg_indexes 
-- WHERE tablename IN (
--     'unit_proposal', 'unit_proposal_status', 'unit_booking_status',
--     'unit_proposal_payment', 'user_real_estate', 'unit_proposal_history',
--     'customer', 'unit_booking', 'customer_process', 
--     'user_client_team_profile', 'sales_executive_portfolio'
-- )
-- ORDER BY tablename, indexname;

-- ============================================================
-- ANÁLISE DE IMPACTO DOS ÍNDICES
-- ============================================================
-- Após criar os índices, execute ANALYZE nas tabelas:
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
