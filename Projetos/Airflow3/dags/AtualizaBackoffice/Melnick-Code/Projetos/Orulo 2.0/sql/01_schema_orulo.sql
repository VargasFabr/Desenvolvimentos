-- Schema orulo: espelho do pipeline Órulo (ex-Supabase) no banco melnick
CREATE SCHEMA IF NOT EXISTS orulo;

-- ---------------------------------------------------------------------------
-- buildings
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orulo.buildings (
    building_id BIGINT PRIMARY KEY,
    name TEXT,
    created_at DATE,
    opening_date DATE,
    launch_date DATE,
    type TEXT,
    finality TEXT,
    status TEXT,
    stage TEXT,
    developer_id BIGINT,
    developer_name TEXT,
    address_street_type TEXT,
    address_street TEXT,
    address_number TEXT,
    address_area TEXT,
    address_city TEXT,
    address_state TEXT,
    address_latitude DOUBLE PRECISION,
    address_longitude DOUBLE PRECISION,
    opportunity_social_housing_program BOOLEAN,
    default_image_url TEXT,
    features JSONB,
    number_of_towers BIGINT,
    number_of_floors BIGINT,
    units_per_floor BIGINT,
    lock_edit BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_orulo_buildings_city ON orulo.buildings (address_city);
CREATE INDEX IF NOT EXISTS idx_orulo_buildings_developer ON orulo.buildings (developer_id);

-- ---------------------------------------------------------------------------
-- typologies
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orulo.typologies (
    building_id BIGINT NOT NULL,
    typology_id BIGINT NOT NULL,
    type TEXT,
    private_area NUMERIC,
    total_area NUMERIC,
    bedrooms BIGINT,
    bathrooms BIGINT,
    suites BIGINT,
    parking NUMERIC,
    total_units BIGINT,
    lock_edit BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (building_id, typology_id)
);

CREATE INDEX IF NOT EXISTS idx_orulo_typologies_building ON orulo.typologies (building_id);

-- ---------------------------------------------------------------------------
-- images
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orulo.images (
    image_id BIGINT PRIMARY KEY,
    building_id BIGINT NOT NULL,
    type TEXT,
    description TEXT,
    associations_typologies JSONB,
    associations_building_units JSONB,
    image_type TEXT,
    image_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_orulo_images_building ON orulo.images (building_id);

-- ---------------------------------------------------------------------------
-- units
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orulo.units (
    unit_id TEXT PRIMARY KEY,
    building_id BIGINT NOT NULL,
    typology_id BIGINT NOT NULL,
    reference TEXT,
    section TEXT,
    floor TEXT,
    unit_end TEXT,
    private_area NUMERIC,
    lock_edit BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_orulo_units_building ON orulo.units (building_id);
CREATE INDEX IF NOT EXISTS idx_orulo_units_typology ON orulo.units (building_id, typology_id);

-- ---------------------------------------------------------------------------
-- units_updates (histórico preço/disponibilidade)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orulo.units_updates (
    unit_id TEXT NOT NULL,
    updated_at DATE NOT NULL,
    price NUMERIC,
    available BOOLEAN,
    lock_edit BOOLEAN NOT NULL DEFAULT false,
    info_source TEXT,
    PRIMARY KEY (unit_id, updated_at)
);

CREATE INDEX IF NOT EXISTS idx_orulo_units_updates_unit ON orulo.units_updates (unit_id);
