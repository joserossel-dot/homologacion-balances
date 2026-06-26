-- =============================================================================
-- schema_minimo.sql — Esquema reducido para la app de validación
-- Solo las tablas necesarias para persistencia compartida del diccionario
-- (versión completa con todas las tablas del sistema: ver seed_catalogo.sql)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS catalogo_maestro (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_estandar VARCHAR(20) UNIQUE NOT NULL,
    nombre_estandar VARCHAR(100) NOT NULL,
    categoria       VARCHAR(40) NOT NULL,
    tipo_estado     VARCHAR(20) NOT NULL,
    naturaleza      VARCHAR(10) NOT NULL,
    signo_normal    SMALLINT NOT NULL DEFAULT 1,
    es_deuda_financiera BOOLEAN NOT NULL DEFAULT FALSE,
    es_activo_liquido  BOOLEAN NOT NULL DEFAULT FALSE,
    afecta_ebitda      BOOLEAN NOT NULL DEFAULT FALSE,
    activo          BOOLEAN NOT NULL DEFAULT TRUE
);

-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diccionario_homologacion (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cuenta_original     VARCHAR(300) NOT NULL,
    cuenta_normalizada  VARCHAR(300) NOT NULL,
    codigo_estandar     VARCHAR(20) NOT NULL REFERENCES catalogo_maestro(codigo_estandar),
    fuente              VARCHAR(50) NOT NULL DEFAULT 'manual',
    validado_humano     BOOLEAN NOT NULL DEFAULT FALSE,
    validado_por        VARCHAR(100),
    validado_en         TIMESTAMPTZ,
    frecuencia_uso      INTEGER NOT NULL DEFAULT 1,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cuenta_normalizada UNIQUE (cuenta_normalizada)
);

CREATE INDEX IF NOT EXISTS idx_diccionario_norm_trgm
    ON diccionario_homologacion USING GIN (cuenta_normalizada gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_diccionario_codigo
    ON diccionario_homologacion (codigo_estandar);

-- ─────────────────────────────────────────────────────────────────────────────
-- Log de validaciones humanas (auditoría del feedback loop)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS log_validaciones (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cuenta_original VARCHAR(300) NOT NULL,
    codigo_sugerido VARCHAR(20),
    codigo_validado VARCHAR(20) NOT NULL REFERENCES catalogo_maestro(codigo_estandar),
    metodo_sugerido VARCHAR(40),
    confianza_sugerida NUMERIC(4,3),
    fue_correccion  BOOLEAN NOT NULL DEFAULT FALSE,
    validado_por    VARCHAR(100),
    archivo_origen  VARCHAR(300),
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
