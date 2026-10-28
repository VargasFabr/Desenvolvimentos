-- IDs externos por torre (colunas pivotadas)

CREATE OR REPLACE VIEW cad.v_torre_identificadores AS
SELECT
    t.id AS id_torre,
    t.codigo_interno,
    e.cod_spe,
    e.nome_comercial,
    t.nome_torre,
    gc.id_externo AS id_gc,
    max(ie.id_externo) FILTER (WHERE ie.sistema = 'orulo') AS id_orulo_ext,
    max(ie.id_externo) FILTER (WHERE ie.sistema = 'otto') AS id_otto_torre,
    otto_emp.id_externo AS id_otto_empreendimento,
    t.id_orulo AS id_orulo_campo
FROM cad.torres t
JOIN cad.empreendimentos e ON e.id = t.id_empreendimento
LEFT JOIN cad.identificadores_externos ie
    ON ie.entidade_tipo = 'torre' AND ie.entidade_id = t.id
LEFT JOIN cad.identificadores_externos gc
    ON gc.entidade_tipo = 'empreendimento' AND gc.entidade_id = e.id AND gc.sistema = 'gc'
LEFT JOIN cad.identificadores_externos otto_emp
    ON otto_emp.entidade_tipo = 'empreendimento' AND otto_emp.entidade_id = e.id AND otto_emp.sistema = 'otto'
GROUP BY
    t.id, t.codigo_interno, e.cod_spe, e.nome_comercial,
    t.nome_torre, t.id_orulo, gc.id_externo, otto_emp.id_externo;

CREATE OR REPLACE VIEW public.v_torre_identificadores AS
SELECT * FROM cad.v_torre_identificadores;
