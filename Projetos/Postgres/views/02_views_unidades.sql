-- View listagem empreendimentos (resumo + endereço)

CREATE OR REPLACE VIEW cad.v_empreendimentos_listagem AS
SELECT
    r.id_empreendimento,
    r.cod_spe,
    r.nome_comercial,
    r.nome_incorporadora,
    r.cidade,
    r.uf,
    r.qtd_fases,
    r.qtd_torres,
    r.qtd_torres_principais,
    r.qtd_torres_vaga,
    r.vgv_bruto_max_torre,
    r.vgv_bruto_soma_torres,
    r.torre_principal_codigo,
    r.torre_principal_nome,
    e.endereco_logradouro,
    e.endereco_numero,
    e.endereco_bairro,
    e.endereco_cep,
    e.latitude,
    e.longitude,
    e.empresa_parceira
FROM cad.v_empreendimentos_resumo r
JOIN cad.empreendimentos e ON e.id = r.id_empreendimento;

CREATE OR REPLACE VIEW public.v_empreendimentos_listagem AS
SELECT * FROM cad.v_empreendimentos_listagem;

-- Unidades completas

CREATE UNIQUE INDEX IF NOT EXISTS unidades_torre_nome_uidx
  ON cad.unidades (id_torre, lower(btrim(nome)))
  WHERE nome IS NOT NULL AND btrim(nome) <> '';

CREATE OR REPLACE VIEW cad.v_unidades_completas AS
SELECT
    u.id AS id_unidade,
    u.nome,
    u.andar,
    u.area_privativa,
    u.fracao_ideal,
    u.tipo,
    u.dormitorios,
    u.vagas,
    u.id_gc,
    u.vinculado_a,
    t.id AS id_torre,
    t.codigo_interno,
    t.cod_torre,
    t.nome_torre,
    e.id AS id_empreendimento,
    e.cod_spe,
    e.nome_comercial,
    f.numero_fase,
    t.codigo_interno || '-' || btrim(u.nome) AS codigo_unidade
FROM cad.unidades u
JOIN cad.torres t ON t.id = u.id_torre
JOIN cad.empreendimentos e ON e.id = u.id_empreendimento
JOIN cad.fases f ON f.id = t.id_fase;

CREATE OR REPLACE VIEW public.v_unidades_completas AS
SELECT * FROM cad.v_unidades_completas;
