-- Torre completa (view principal para BI / planilhas)

CREATE OR REPLACE VIEW cad.v_torres_completas AS
SELECT
    t.id AS id_torre,
    t.codigo_interno,
    t.cod_torre,
    t.nome_torre,
    t.segmento,
    t.estagio,
    t.tipo_empresa,
    t.principal,
    t.permutante,
    t.lancamento,
    t.entrega,
    t.inicio_obra,
    t.vgv_bruto,
    t.vgv_liquido,
    t.unidades_total,
    t.unidades_permuta,
    t.id_orulo,
    t.pct_melnick,
    t.tags,
    f.id AS id_fase,
    f.numero_fase,
    f.nome_fase,
    e.id AS id_empreendimento,
    e.cod_spe,
    e.nome_comercial,
    e.endereco_logradouro,
    e.endereco_numero,
    e.endereco_bairro,
    e.endereco_cep,
    e.latitude,
    e.longitude,
    e.empresa_parceira,
    i.id AS id_incorporadora,
    i.nome AS nome_incorporadora,
    i.cnpj AS cnpj_incorporadora,
    c.nome AS cidade,
    est.sigla AS uf,
    concat_ws(' ', e.nome_comercial, t.nome_torre) AS nome_composto
FROM cad.torres t
JOIN cad.fases f ON f.id = t.id_fase
JOIN cad.empreendimentos e ON e.id = t.id_empreendimento
JOIN cad.incorporadoras i ON i.id = e.id_incorporadora
LEFT JOIN cad.cidades c ON c.id = e.id_cidade
LEFT JOIN cad.estados est ON est.id = c.id_estado;

CREATE OR REPLACE VIEW public.v_torres_completas AS
SELECT * FROM cad.v_torres_completas;
