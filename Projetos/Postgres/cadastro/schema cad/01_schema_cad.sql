-- Schema cad: cadastro master Melnick
-- Torre = entidade canônica (codigo_interno = {spe}-{cod_torre}-F{fase})

CREATE SCHEMA IF NOT EXISTS cad;

-- ---------------------------------------------------------------------------
-- Utilitários
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION cad.atualiza_atualizado_em()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cad.normalizar_texto(input TEXT)
RETURNS TEXT AS $$
BEGIN
    IF input IS NULL OR btrim(input) = '' THEN
        RETURN NULL;
    END IF;
    RETURN lower(unaccent(btrim(input)));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ---------------------------------------------------------------------------
-- Catálogo de sistemas externos
-- ---------------------------------------------------------------------------

CREATE TABLE cad.sistemas_externos (
    codigo TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    descricao TEXT
);

-- ---------------------------------------------------------------------------
-- Incorporadoras
-- ---------------------------------------------------------------------------

CREATE TABLE cad.incorporadoras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome TEXT NOT NULL,
    cnpj TEXT CHECK (
        cnpj IS NULL
        OR cnpj ~ '^((\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})|(\d{14}))$'
    ),
    tipo_empresa TEXT CHECK (tipo_empresa IS NULL OR tipo_empresa IN ('INC', 'URB', 'PERM', 'OUTRO')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_incorporadoras_atualizado
    BEFORE UPDATE ON cad.incorporadoras
    FOR EACH ROW EXECUTE FUNCTION cad.atualiza_atualizado_em();

-- ---------------------------------------------------------------------------
-- Localização
-- ---------------------------------------------------------------------------

CREATE TABLE cad.estados (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sigla TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL
);

CREATE TABLE cad.cidades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome TEXT NOT NULL,
    id_estado UUID REFERENCES cad.estados(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (nome, id_estado)
);

CREATE INDEX ON cad.cidades (id_estado);

CREATE TRIGGER trg_cidades_atualizado
    BEFORE UPDATE ON cad.cidades
    FOR EACH ROW EXECUTE FUNCTION cad.atualiza_atualizado_em();

-- ---------------------------------------------------------------------------
-- Empreendimentos (grain: 1 por SPE / cod_spe)
-- ---------------------------------------------------------------------------

CREATE TABLE cad.empreendimentos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_spe TEXT NOT NULL UNIQUE,
    nome_comercial TEXT NOT NULL,
    id_incorporadora UUID NOT NULL REFERENCES cad.incorporadoras(id),
    id_cidade UUID REFERENCES cad.cidades(id),
    endereco_logradouro TEXT,
    endereco_numero TEXT,
    endereco_bairro TEXT,
    endereco_cep TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    empresa_parceira TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON cad.empreendimentos (id_incorporadora);
CREATE INDEX ON cad.empreendimentos (id_cidade);

CREATE TRIGGER trg_empreendimentos_atualizado
    BEFORE UPDATE ON cad.empreendimentos
    FOR EACH ROW EXECUTE FUNCTION cad.atualiza_atualizado_em();

-- ---------------------------------------------------------------------------
-- Fases (grain: empreendimento + numero_fase)
-- ---------------------------------------------------------------------------

CREATE TABLE cad.fases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_empreendimento UUID NOT NULL REFERENCES cad.empreendimentos(id),
    numero_fase SMALLINT NOT NULL CHECK (numero_fase > 0),
    nome_fase TEXT,
    lancamento DATE,
    entrega DATE,
    inicio_obra DATE,
    vpl_viabilidade NUMERIC(18, 2),
    vpl_base NUMERIC(18, 2),
    perda_comite NUMERIC(18, 6),
    taxa_vpl NUMERIC(18, 6),
    taxa_juros NUMERIC(18, 6),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id_empreendimento, numero_fase)
);

CREATE INDEX ON cad.fases (id_empreendimento);

CREATE TRIGGER trg_fases_atualizado
    BEFORE UPDATE ON cad.fases
    FOR EACH ROW EXECUTE FUNCTION cad.atualiza_atualizado_em();

-- ---------------------------------------------------------------------------
-- Torres (grain: empreendimento + cod_torre + fase) — ENTIDADE CANÔNICA
-- ---------------------------------------------------------------------------

CREATE TABLE cad.torres (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_interno TEXT NOT NULL UNIQUE,
    cod_torre TEXT NOT NULL,
    nome_torre TEXT,
    id_empreendimento UUID NOT NULL REFERENCES cad.empreendimentos(id),
    id_fase UUID NOT NULL REFERENCES cad.fases(id),
    segmento TEXT,
    estagio TEXT,
    tipo_empresa TEXT,
    principal BOOLEAN NOT NULL DEFAULT false,
    permutante BOOLEAN NOT NULL DEFAULT false,
    lancamento DATE,
    entrega DATE,
    inicio_obra DATE,
    vgv_bruto NUMERIC(18, 2),
    vgv_liquido NUMERIC(18, 2),
    unidades_total INTEGER,
    unidades_permuta INTEGER,
    id_orulo TEXT,
    capa TEXT,
    m2_sugerido_im NUMERIC(18, 4),
    m2_aprovado_colan NUMERIC(18, 4),
    m2_aprovado_coin NUMERIC(18, 4),
    ano_entrega_gerencial SMALLINT,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    pct_melnick NUMERIC(8, 4),
    sobreposicao BOOLEAN,
    sobreposicao_empreendimento TEXT,
    sobreposicao_torre TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id_empreendimento, cod_torre, id_fase)
);

CREATE INDEX ON cad.torres (id_empreendimento);
CREATE INDEX ON cad.torres (id_fase);
CREATE INDEX ON cad.torres (principal) WHERE principal = true;
CREATE INDEX ON cad.torres (segmento);

CREATE TRIGGER trg_torres_atualizado
    BEFORE UPDATE ON cad.torres
    FOR EACH ROW EXECUTE FUNCTION cad.atualiza_atualizado_em();

-- ---------------------------------------------------------------------------
-- Unidades (DDL only — seed fase posterior)
-- ---------------------------------------------------------------------------

CREATE TABLE cad.unidades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_torre UUID NOT NULL REFERENCES cad.torres(id),
    id_empreendimento UUID NOT NULL REFERENCES cad.empreendimentos(id),
    nome TEXT,
    andar TEXT,
    area_privativa NUMERIC(12, 4),
    fracao_ideal NUMERIC(12, 8),
    tipo TEXT,
    dormitorios SMALLINT,
    vagas NUMERIC(6, 2),
    id_gc TEXT,
    vinculado_a UUID REFERENCES cad.unidades(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON cad.unidades (id_torre);
CREATE INDEX ON cad.unidades (id_empreendimento);
CREATE INDEX ON cad.unidades (vinculado_a);

CREATE TRIGGER trg_unidades_atualizado
    BEFORE UPDATE ON cad.unidades
    FOR EACH ROW EXECUTE FUNCTION cad.atualiza_atualizado_em();

-- ---------------------------------------------------------------------------
-- Aliases polimórficos
-- ---------------------------------------------------------------------------

CREATE TABLE cad.aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entidade_tipo TEXT NOT NULL CHECK (entidade_tipo IN ('empreendimento', 'torre', 'unidade')),
    entidade_id UUID NOT NULL,
    alias TEXT NOT NULL,
    alias_normalizado TEXT GENERATED ALWAYS AS (cad.normalizar_texto(alias)) STORED,
    fonte TEXT NOT NULL DEFAULT 'manual',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entidade_tipo, entidade_id, alias_normalizado, fonte)
);

CREATE INDEX ON cad.aliases (entidade_tipo, entidade_id);
CREATE INDEX aliases_alias_trgm ON cad.aliases USING gin (alias gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- Identificadores externos polimórficos
-- ---------------------------------------------------------------------------

CREATE TABLE cad.identificadores_externos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entidade_tipo TEXT NOT NULL CHECK (entidade_tipo IN ('empreendimento', 'torre', 'unidade')),
    entidade_id UUID NOT NULL,
    sistema TEXT NOT NULL REFERENCES cad.sistemas_externos(codigo),
    id_externo TEXT NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (sistema, id_externo),
    UNIQUE (entidade_tipo, entidade_id, sistema)
);

CREATE INDEX ON cad.identificadores_externos (entidade_tipo, entidade_id);
CREATE INDEX ON cad.identificadores_externos (sistema);
