-- Aliases agregados por torre

CREATE OR REPLACE VIEW cad.v_torre_aliases AS
SELECT
    t.id AS id_torre,
    t.codigo_interno,
    e.cod_spe,
    e.nome_comercial,
    t.nome_torre,
    string_agg(DISTINCT a.alias, ' | ' ORDER BY a.alias) AS aliases,
    array_agg(DISTINCT a.alias ORDER BY a.alias) AS aliases_array,
    count(DISTINCT a.id) AS qtd_aliases
FROM cad.torres t
JOIN cad.empreendimentos e ON e.id = t.id_empreendimento
LEFT JOIN cad.aliases a
    ON a.entidade_tipo = 'torre' AND a.entidade_id = t.id
GROUP BY t.id, t.codigo_interno, e.cod_spe, e.nome_comercial, t.nome_torre;

CREATE OR REPLACE VIEW public.v_torre_aliases AS
SELECT * FROM cad.v_torre_aliases;
