CREATE TABLE IF NOT EXISTS catalogo_maestro (
    codigo_estandar VARCHAR(20) PRIMARY KEY,
    nombre_estandar VARCHAR(100) NOT NULL,
    categoria VARCHAR(40) NOT NULL,
    tipo_estado VARCHAR(20) NOT NULL,
    naturaleza VARCHAR(20) NOT NULL,
    signo_normal SMALLINT NOT NULL DEFAULT 1,
    es_deuda_financiera BOOLEAN NOT NULL DEFAULT FALSE,
    es_activo_liquido BOOLEAN NOT NULL DEFAULT FALSE,
    afecta_ebitda BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS diccionario_homologacion (
    id BIGSERIAL PRIMARY KEY,
    cuenta_original VARCHAR(300) NOT NULL,
    cuenta_normalizada VARCHAR(300) NOT NULL UNIQUE,
    codigo_estandar VARCHAR(20) NOT NULL REFERENCES catalogo_maestro(codigo_estandar),
    fuente VARCHAR(50) NOT NULL DEFAULT 'manual',
    validado_humano BOOLEAN NOT NULL DEFAULT FALSE,
    validado_por VARCHAR(100),
    validado_en TIMESTAMPTZ,
    frecuencia_uso INTEGER NOT NULL DEFAULT 1,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diccionario_codigo
    ON diccionario_homologacion (codigo_estandar);

CREATE TABLE IF NOT EXISTS log_validaciones (
    id BIGSERIAL PRIMARY KEY,
    cuenta_original VARCHAR(300) NOT NULL,
    codigo_sugerido VARCHAR(20),
    codigo_validado VARCHAR(20) NOT NULL REFERENCES catalogo_maestro(codigo_estandar),
    metodo_sugerido VARCHAR(80),
    confianza_sugerida NUMERIC(5,4),
    fue_correccion BOOLEAN NOT NULL DEFAULT FALSE,
    validado_por VARCHAR(100),
    archivo_origen VARCHAR(300),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE log_validaciones
    ADD COLUMN IF NOT EXISTS cuenta_normalizada VARCHAR(300);

CREATE INDEX IF NOT EXISTS idx_validaciones_cuenta_norm
    ON log_validaciones (cuenta_normalizada);

CREATE TABLE IF NOT EXISTS historial_diccionario (
    id BIGSERIAL PRIMARY KEY,
    cuenta_original VARCHAR(300) NOT NULL,
    cuenta_normalizada VARCHAR(300) NOT NULL,
    codigo_anterior VARCHAR(20),
    codigo_nuevo VARCHAR(20),
    accion VARCHAR(20) NOT NULL,
    validado_por VARCHAR(100),
    archivo_origen VARCHAR(300),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_historial_cuenta_norm
    ON historial_diccionario (cuenta_normalizada, creado_en DESC);

INSERT INTO catalogo_maestro
    (codigo_estandar, nombre_estandar, categoria, tipo_estado, naturaleza, activo)
VALUES
    ('__EXCLUIR__', 'No incluir en el balance normalizado', 'exclusion',
     'control', 'neutra', FALSE)
ON CONFLICT (codigo_estandar) DO NOTHING;
