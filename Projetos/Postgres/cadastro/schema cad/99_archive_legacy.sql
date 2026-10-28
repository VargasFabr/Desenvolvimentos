-- Arquiva tabelas legadas de cadastro (public → legacy)
-- Idempotente: ignora tabelas já movidas ou inexistentes

CREATE SCHEMA IF NOT EXISTS legacy;

DO $$
DECLARE
    tbl TEXT;
    tables TEXT[] := ARRAY[
        'empreendimentos', 'torres', 'unidades', 'fases',
        'incorporadoras', 'cidades', 'contas'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = tbl
        ) THEN
            EXECUTE format('ALTER TABLE public.%I SET SCHEMA legacy', tbl);
            RAISE NOTICE 'Movido public.% → legacy.%', tbl, tbl;
        END IF;
    END LOOP;
END $$;

-- Tabela de teste
DROP TABLE IF EXISTS public.data;

-- Collation warning (Windows PG upgrade)
-- ALTER DATABASE melnick REFRESH COLLATION VERSION;
