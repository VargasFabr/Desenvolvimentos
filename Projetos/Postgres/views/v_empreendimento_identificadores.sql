-- Empreendimento: gc/spe fica no nível SPE

CREATE OR REPLACE VIEW cad.v_empreendimento_identificadores AS
SELECT
    e.id AS id_empreendimento,
    e.cod_spe,
    e.nome_comercial,
    max(ie.id_externo) FILTER (WHERE ie.sistema = 'gc') AS id_gc,
    max(ie.id_externo) FILTER (WHERE ie.sistema = 'controladoria') AS id_controladoria,
    max(ie.id_externo) FILTER (WHERE ie.sistema = 'otto') AS id_otto,
    max(ie.id_externo) FILTER (WHERE ie.sistema = 'sap') AS id_sap
FROM cad.empreendimentos e
LEFT JOIN cad.identificadores_externos ie
    ON ie.entidade_tipo = 'empreendimento' AND ie.entidade_id = e.id
GROUP BY e.id, e.cod_spe, e.nome_comercial;

CREATE OR REPLACE VIEW public.v_empreendimento_identificadores AS
SELECT * FROM cad.v_empreendimento_identificadores;
