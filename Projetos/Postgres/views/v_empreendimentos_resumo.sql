-- Resumo por empreendimento (SPE)

CREATE OR REPLACE VIEW cad.v_empreendimentos_resumo AS
SELECT
    e.id AS id_empreendimento,
    e.cod_spe,
    e.nome_comercial,
    i.nome AS nome_incorporadora,
    c.nome AS cidade,
    est.sigla AS uf,
    count(DISTINCT f.id) AS qtd_fases,
    count(t.id) AS qtd_torres,
    count(t.id) FILTER (WHERE t.principal) AS qtd_torres_principais,
    count(t.id) FILTER (WHERE t.segmento = 'Vaga') AS qtd_torres_vaga,
    max(t.vgv_bruto) AS vgv_bruto_max_torre,
    sum(t.vgv_bruto) AS vgv_bruto_soma_torres,
    tp.codigo_interno AS torre_principal_codigo,
    tp.nome_torre AS torre_principal_nome
FROM cad.empreendimentos e
JOIN cad.incorporadoras i ON i.id = e.id_incorporadora
LEFT JOIN cad.cidades c ON c.id = e.id_cidade
LEFT JOIN cad.estados est ON est.id = c.id_estado
LEFT JOIN cad.fases f ON f.id_empreendimento = e.id
LEFT JOIN cad.torres t ON t.id_empreendimento = e.id
LEFT JOIN LATERAL (
    SELECT t2.codigo_interno, t2.nome_torre
    FROM cad.torres t2
    WHERE t2.id_empreendimento = e.id AND t2.principal = true
    ORDER BY t2.cod_torre
    LIMIT 1
) tp ON true
GROUP BY
    e.id, e.cod_spe, e.nome_comercial,
    i.nome, c.nome, est.sigla,
    tp.codigo_interno, tp.nome_torre;

CREATE OR REPLACE VIEW public.v_empreendimentos_resumo AS
SELECT * FROM cad.v_empreendimentos_resumo;
