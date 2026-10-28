-- Busca por nome legado → codigo_interno

CREATE OR REPLACE VIEW cad.v_busca_cadastro AS
SELECT
    a.alias,
    a.alias_normalizado,
    a.fonte,
    a.entidade_tipo,
    COALESCE(t.codigo_interno, tp.codigo_interno) AS codigo_interno,
    COALESCE(e_t.cod_spe, e_e.cod_spe) AS cod_spe,
    COALESCE(e_t.nome_comercial, e_e.nome_comercial) AS nome_comercial,
    COALESCE(t.nome_torre, tp.nome_torre) AS nome_torre,
    COALESCE(t.principal, tp.principal, false) AS principal
FROM cad.aliases a
LEFT JOIN cad.torres t
    ON a.entidade_tipo = 'torre' AND a.entidade_id = t.id
LEFT JOIN cad.empreendimentos e_t
    ON t.id_empreendimento = e_t.id
LEFT JOIN cad.empreendimentos e_e
    ON a.entidade_tipo = 'empreendimento' AND a.entidade_id = e_e.id
LEFT JOIN LATERAL (
    SELECT t2.codigo_interno, t2.nome_torre, t2.principal
    FROM cad.torres t2
    WHERE t2.id_empreendimento = e_e.id AND t2.principal = true
    ORDER BY t2.cod_torre
    LIMIT 1
) tp ON a.entidade_tipo = 'empreendimento';

CREATE OR REPLACE VIEW public.v_busca_cadastro AS
SELECT * FROM cad.v_busca_cadastro;
