-- Torre principal por empreendimento (substituto de “nome só do emp”)

CREATE OR REPLACE VIEW cad.v_torres_principais AS
SELECT DISTINCT ON (e.id)
    t.id AS id_torre,
    t.codigo_interno,
    e.cod_spe,
    e.nome_comercial,
    t.nome_torre,
    t.segmento,
    t.estagio,
    f.numero_fase
FROM cad.empreendimentos e
JOIN cad.torres t ON t.id_empreendimento = e.id
JOIN cad.fases f ON f.id = t.id_fase
ORDER BY
    e.id,
    t.principal DESC,
    CASE WHEN t.segmento = 'Vaga' THEN 1 ELSE 0 END,
    f.numero_fase,
    t.cod_torre;

CREATE OR REPLACE VIEW public.v_torres_principais AS
SELECT * FROM cad.v_torres_principais;
