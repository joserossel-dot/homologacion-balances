# ContextBuilder Validation

**Date:** 2026-07-26
**Dataset:** `datasets/validacion/BALANCE DENHAM.pdf` (GUION format, 303 cuentas, 244 con código)

---

## Overview

`ContextBuilder.build()` recibe una lista plana de `CuentaRaw` y devuelve `list[AccountContext]` con:

- **Jerarquía**: padre, hijos, hermanos basado en códigos
- **Navegación secuencial**: cuenta anterior y siguiente
- **Metadata**: sección, layout, tipo de cuenta, nivel jerárquico
- **Ruta completa**: path jerárquico (ej. `1/1.1/1.1.01`)

---

## Ejemplo 1: Jerarquía con formato PUNTO

Dataset sintético con 9 cuentas en formato `1.1.01.01`:

| Código | Nivel | Padre | Hijos | Hermanos | Sección | Path |
|--------|-------|-------|-------|----------|---------|------|
| `1` | 1 | — | `1.1, 1.2` | `2` | activo | `1` |
| `1.1` | 2 | `1` | `1.1.01, 1.1.02` | `1.2` | activo | `1/1.1` |
| `1.1.01` | 3 | `1.1` | — | `1.1.02` | activo | `1/1.1/1.1.01` |
| `1.1.02` | 3 | `1.1` | — | `1.1.01` | activo | `1/1.1/1.1.02` |
| `1.2` | 2 | `1` | `1.2.01` | `1.1` | activo | `1/1.2` |
| `1.2.01` | 3 | `1.2` | — | — | activo | `1/1.2/1.2.01` |
| `2` | 1 | — | `2.1` | `1` | pasivo | `2` |
| `2.1` | 2 | `2` | `2.1.01` | — | pasivo | `2/2.1` |
| `2.1.01` | 3 | `2.1` | — | — | pasivo | `2/2.1/2.1.01` |

**Jerarquía correcta**: `1 → 1.1 → 1.1.01`, `1 → 1.2`, `2 → 2.1`.

---

## Ejemplo 2: Formato GUION con datos reales

Dataset real: `BALANCE DENHAM.pdf` — 244 cuentas con código formato `1-1-01-001`.

Todos los códigos tienen 4 segmentos (`d.d-dd-ddd`). No existen cuentas padre en el extracto (los totales por grupo no son extraídos como cuentas con código). Esto es esperable en datos reales donde solo las cuentas de detalle tienen código.

### Top 10 cuentas

| # | Código | Nombre | Nivel |
|---|--------|--------|-------|
| 0 | — | PACKING Y SERVICIOS RUCARAY S. | 0 |
| 1 | — | 99,539,360-3 | 0 |
| 2 | — | Balance General | 0 |
| 3 | — | Desde: enero 2016 | 0 |
| 4 | `1-1-01-001` | CAJA | 4 |
| 5 | `1-1-01-002` | CAJA MONEDA EXTRANJERA | 4 |
| 6 | `1-1-01-003` | FONDO FIJO PLANTAS | 4 |
| 7 | `1-1-01-004` | DEPOSITOS EN TRANSITO | 4 |
| 8 | `1-1-01-005` | OPERACION PENDIENTE | 4 |
| 9 | `1-1-01-006` | ASIG.FAMILIAR | 4 |

### Navegación secuencial

- Cada cuenta tiene `previous_account` y `next_account` (excepto extremos)
- Posiciones son 0-indexed secuenciales
- `path` jerárquico: cuentas sin padre tienen `path = codigo` (ej. `1-1-01-001`)

### Hermanos

Cuentas con el mismo prefijo de 3 segmentos comparten grupo de hermanos:
- `1-1-01-001` a `1-1-01-006` son hermanos (prefijo `1-1-01`)
- `1-1-02-002`, `1-1-02-003` son hermanos (prefijo `1-1-02`)

---

## Ejemplo 3: Cuentas sin código

Cuando una lista de cuentas no tiene códigos (`codigo=None`), `ContextBuilder` asigna:

- `hierarchy_level = 0`
- `parent = None`
- `children = []`
- `siblings = []`
- `section = "sin_seccion"`

Esto asegura que no se rompe con balances que no tienen códigos de cuenta detectados.

---

## Validación de campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `raw` | `CuentaRaw` | Cuenta original (sin modificar) |
| `parent` | `Optional[AccountContext]` | Padre jerárquico |
| `children` | `list[AccountContext]` | Hijos directos |
| `siblings` | `list[AccountContext]` | Hermanos (mismo padre) |
| `previous_account` | `Optional[AccountContext]` | Cuenta anterior en orden lineal |
| `next_account` | `Optional[AccountContext]` | Cuenta siguiente en orden lineal |
| `hierarchy_level` | `int` | Profundidad del código (0 = sin código) |
| `section` | `str` | Sección del balance (activo, pasivo, etc.) |
| `layout` | `list[str]` | Columnas del layout detectado |
| `account_type` | `Optional[str]` | Tipo de cuenta (de AccountTypeResolver) |
| `path` | `str` | Ruta jerárquica completa |
| `position` | `int` | Posición en la lista original |
| `confidence` | `float` | Confianza de extracción |

---

## Tests

**32 tests** en `tests/test_context_builder.py`:

| Clase | Tests | Cobertura |
|-------|-------|-----------|
| `TestJerarquiaPunto` | 9 | Niveles, padre, hijos, hermanos, secciones, paths |
| `TestJerarquiaGuion` | 2 | Formato GUION |
| `TestSinCodigo` | 4 | Sin código no rompe |
| `TestNavegacion` | 2 | previous/next, posición |
| `TestMetadata` | 4 | Layout, account_type, confianza, repr |
| `TestBorde` | 4 | Lista vacía, auto-detección, campos |
| `TestConPDFsReales` | 7 | BALANCE DENHAM.pdf real |

**Resultado**: 32/32 passed.

---

## Limitaciones conocidas

1. **Jerarquía requiere ambos niveles**: Si los códigos padre no están en la lista extraída, no se asignan padres. Esto es común: muchos PDFs solo tienen códigos en cuentas de detalle, no en totales.

2. **Códigos compactos**: El formato COMPACTO (6-10 dígitos) asume segmentos de 2 dígitos. No hay PDFs en el dataset actual con este formato para validación real.

3. **Secciones**: La detección de sección usa el primer segmento del código (1=activo, 2=pasivo, 3=patrimonio, 4=resultados). Códigos no estándar caen en `sin_seccion`.
