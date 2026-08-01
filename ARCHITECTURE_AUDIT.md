# ARCHITECTURE AUDIT — homologacion-balances

> Auditoría completa del repositorio de parser de balances tributarios chilenos.
> Generado: 2026-07-26

---

## ÍNDICE

1. [Arquitectura actual](#1-arquitectura-actual)
2. [Mapa de dependencias](#2-mapa-de-dependencias)
3. [Inventario de clases y modelos](#3-inventario-de-clases-y-modelos)
4. [Flujo de datos completo](#4-flujo-de-datos-completo)
5. [Duplicaciones detectadas](#5-duplicaciones-detectadas)
6. [Código muerto](#6-código-muerto)
7. [Riesgos técnicos](#7-riesgos-técnicos)
8. [Problemas críticos](#8-problemas-críticos)
9. [Oportunidades de mejora](#9-oportunidades-de-mejora)
10. [Plan de migración — 6 fases](#10-plan-de-migracion)

---

## 1. ARQUITECTURA ACTUAL

### 1.1 Vista general

```
┌─────────────────────────────────────────────────────────────┐
│                   app_validacion.py (1340L)                  │
│               Streamlit UI + lógica de negocio               │
└────────────────────────┬────────────────────────────────────┘
                         │ llama a
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  HomologationPipeline                        │
│              pipeline/homologation_pipeline.py (634L)        │
│                                                             │
│  ParserPDF(v1) → AccountAdapter → BalanceInterpreter        │
│  → AccountTypeResolver → ClasificadorCodigo → DecisionEngine│
│  → SemanticEngine → CMCCClassifier → ReglasEspeciales       │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌─────────────────┐ ┌──────────┐ ┌──────────────┐
│  parser_universal │ │ decision │ │  semantic/   │
│  (v1, 726L)      │ │ engine   │ │  learning/   │
│  + parsers/ (v2) │ │ (v1+v2)  │ │  knowledge/  │
└─────────────────┘ └──────────┘ └──────────────┘
```

### 1.2 Sistema de parsers (dual)

**Parser V1 — `parser_universal.py`**

Un solo archivo de 726 líneas con:
- `CuentaRaw` — modelo de datos
- `ResultadoParseo` — contenedor de resultados
- `FormatoCodigo` / `OrigenColumna` — enums
- `validar_archivo()` — validación de integridad
- `detectar_formato_codigo()` — detecta guion/punto/compacto
- `detectar_separador_miles()` — detecta . o ,
- `parsear_linea()` — parser de línea individual → `CuentaRaw`
- `parsear_monto()` — conversión de string a float
- `ParserPDF` — clase orquestadora con OCR
- `verificar_cuadre_balance()` — validación contable
- Feature flags globales: `ENABLE_DYNAMIC_LAYOUT`, `ENABLE_ACCOUNT_TYPE_RESOLVER`

**Parser V2 — `parsers/` package**

8 archivos que envuelven a V1:

| Archivo | Líneas | Función |
|---------|--------|---------|
| `pdf_parser.py` | 430 | `ParserCore2` — orquesta, llama a `ParserPDF._extraer_lineas()` |
| `config.py` | 141 | `ParserConfig` — configuración TOML + env |
| `format_detector.py` | 53 | Wrapper de `detectar_formato_codigo()` |
| `hygiene.py` | 22 | Wrapper de `GARBAGE_PATTERNS` |
| `line_parser.py` | 101 | `RawAccount` — modelo espejo + wrappers |
| `layout_detector.py` | 139 | `LayoutDetector` — **única lógica original** |
| `orientation_detector.py` | 120 | **NO USADO** — detecta rotación 180° |
| `ocr_engine.py` | 107 | `TesseractEngine` — wrapper + OCR duplicado |
| `account_type_resolver.py` | 240 | `AccountTypeResolver` — **lógica original** |
| `excel_parser.py` | 20 | Wrapper de `app_validacion.parsear_excel()` |
| `factory.py` | 38 | `ParserFactory` — crea v1 o v2 |

### 1.3 Modelos de datos (5 modelos, 2 pares duplicados)

```
parser_universal.CuentaRaw      ← ORIGEN (español)
    linea, codigo, nombre, monto, origen_columna, es_total, confianza_extraccion, tipo_cuenta

parsers.line_parser.RawAccount  ← ESPEJO (inglés)
    line, code, name, amount, column_origin, is_total, extraction_confidence

models.accounting_record.AccountingRecord  ← CDM CANÓNICO
    record_id, source_file, account_code, account_name, debit, credit, balance_*, confidence

models.account_balance.AccountBalance     ← MODELO INTERMEDIO
    account_code, account_name, amounts(AccountAmounts), nature, source_*, confidence

models.account_amounts.AccountAmounts     ← ANIDADO
    debit, credit, balance_debit, balance_credit, assets, liabilities, losses, profits

models.account_nature.AccountNature       ← ENUM
    UNKNOWN, ASSET, LIABILITY, LOSS, PROFIT
```

**Flujo de conversión:** `CuentaRaw → RawAccount → AccountBalance → AccountingRecord`

Cada conversión es una copia de campos con re-nombramiento.

### 1.4 Decision Engines (2 implementaciones)

| Aspecto | `decision/` (v1) | `decision_v2/` (v2) |
|---------|------------------|---------------------|
| Archivo | `engine.py` (189L) + `models.py` (55L) | `engine.py` (598L) + `models.py` (52L) |
| Estrategia | 4 reglas secuenciales | Ponderación por consenso + 10+ reglas |
| Usado por | `HomologationPipeline` | **Nadie** |
| Madurez | Simple, probado | Sofisticado, sin uso |

### 1.5 Pipelines (2 implementaciones)

| Pipeline | Archivo | Estado |
|----------|---------|--------|
| `HomologationPipeline` | `pipeline/homologation_pipeline.py` (634L) | ACTIVO, usado por `app_validacion.py` |
| `NewPipeline` | `pipeline/new_pipeline.py` (55L) | ABANDONADO, no referenciado |

### 1.6 Feature flags

**Parser level** (en `parser_universal.py`, como constantes globales):
- `ENABLE_DYNAMIC_LAYOUT = False`
- `ENABLE_ACCOUNT_TYPE_RESOLVER = False`

**Config level** (en `parsers/config.py`, dentro de dataclasses):
- `LayoutConfig.enable_detection = True` (contradice el flag de parser_universal)
- `OcrConfig`, `DetectionConfig`, `CachingConfig` — definidos pero parcialmente usados

**Pipeline level** (en `pipeline/features.py`, `CMCCFeatureFlags`):
- 10 flags booleanos + 2 thresholds
- Controlan CMCC, SemanticMatcher, DecisionEngine, AccountTypeFilter, RegexFallback

---

## 2. MAPA DE DEPENDENCIAS

### 2.1 Dependencias entre módulos

```
app_validacion.py
├── parser_universal (ParserPDF, CuentaRaw, OrigenColumna)
├── clasificador_codigo_cuenta
├── reglas_especiales
├── gold_standard/
├── analytics/
├── extractor_metadata
├── src.db_repository

pipeline/homologation_pipeline.py
├── parser_universal (ParserPDF, FormatoCodigo, ResultadoParseo)
├── parsers.account_type_resolver (AccountTypeResolver)
├── adapters.account_adapter
├── interpreters.balance_interpreter
├── pipeline.cmcc_classifier
├── pipeline.features
├── decision.engine
├── semantic/
├── learning/
├── clasificador_codigo_cuenta
├── reglas_especiales
├── app_validacion (REGLAS_REGEX, parsear_excel)

parsers/pdf_parser.py (ParserCore2)
├── parser_universal (ParserPDF, validar_archivo, normalizar_codigo_ocr)
├── parsers.config
├── parsers.format_detector
├── parsers.line_parser
├── parsers.layout_detector
├── parsers.hygiene

parser_universal.py (independiente... casi)
├── pdfplumber
├── PIL
├── subprocess (tesseract)
├── [import diferido] parsers.layout_detector
├── [import diferido] parsers.account_type_resolver
```

### 2.2 Dependencias externas

| Dependencia | Usada por | Propósito |
|-------------|-----------|-----------|
| `pdfplumber` | `parser_universal.py` | Extraer texto nativo de PDF |
| `PIL` (Pillow) | `parser_universal.py`, `ocr_engine.py` | Rotar imágenes para OCR |
| `tesseract` (binario) | `parser_universal.py`, `ocr_engine.py` | OCR de PDFs escaneados |
| `pdftoppm` (binario) | `parser_universal.py`, `ocr_engine.py` | PDF → PNG |
| `rapidfuzz` | Pipeline, CMCC, Semantic | Fuzzy matching |
| `streamlit` | `app_validacion.py` | UI |
| `pandas` | `app_validacion.py` | DataFrames |
| `openpyxl` | `app_validacion.py` | Excel |
| `fastapi` | `src/api/` | API REST |

---

## 3. INVENTARIO DE CLASES Y MODELOS

### 3.1 Clases

| Clase | Archivo | Líneas | Estado | Propósito |
|-------|---------|--------|--------|-----------|
| `ParserPDF` | `parser_universal.py:542` | ~155 | **DUAL** (v1 real + v2 lo envuelve) | Orquestador PDF+OCR |
| `ParserCore2` | `parsers/pdf_parser.py:118` | ~312 | VIVO | Orquestador v2 (envuelve v1) |
| `LayoutDetector` | `parsers/layout_detector.py:53` | ~86 | VIVO | Detecta columnas del balance |
| `TesseractEngine` | `parsers/ocr_engine.py:39` | ~68 | **WRAPPER** | Envuelve OCR de v1 |
| `AccountTypeResolver` | `parsers/account_type_resolver.py:38` | ~202 | VIVO | Resuelve tipo de cuenta |
| `ParserFactory` | `parsers/factory.py:15` | ~23 | VIVO | Fábrica de parsers |
| `HomologationPipeline` | `pipeline/homologation_pipeline.py:29` | ~605 | VIVO | Pipeline principal |
| `NewPipeline` | `pipeline/new_pipeline.py:17` | ~38 | **MUERTO** | Pipeline alternativo abandonado |
| `CMCCClassifier` | `pipeline/cmcc_classifier.py:11` | ~76 | VIVO | Clasificador CMCC |
| `DecisionEngine` | `decision/engine.py:6` | ~183 | VIVO | Decision v1 |
| `DecisionEngineV2` | `decision_v2/engine.py:47` | ~551 | **MUERTO** | Decision v2 |
| `AccountAdapter` | `adapters/account_adapter.py:18` | ~59 | VIVO | CuentaRaw → AccountBalance |
| `BalanceInterpreter` | `interpreters/balance_interpreter.py:9` | ~44 | VIVO | Interpreta naturaleza contable |
| `ProcesadorReglasEspeciales` | `reglas_especiales.py:35` | ~262 | VIVO | 5 reglas especiales |
| `ClasificadorCodigo` | `clasificador_codigo_cuenta.py` | externo | VIVO | Clasifica por código |
| `SemanticEngine` | `semantic/semantic_engine.py` | externo | VIVO | Motor semántico |

### 3.2 Dataclasses / Modelos

| Modelo | Archivo | Campos | Propósito |
|--------|---------|--------|-----------|
| `CuentaRaw` | `parser_universal.py:77` | 8 | **MODELO ORIGEN** |
| `RawAccount` | `parsers/line_parser.py:24` | 7 | **ESPEJO INGLÉS** |
| `ResultadoParseo` | `parser_universal.py:89` | 7 | Resultado v1 |
| `ParseResult` | `parsers/pdf_parser.py:91` | 9 | Resultado v2 |
| `ParseMetrics` | `parsers/pdf_parser.py:64` | 12 | Métricas v2 |
| `DetectedLayout` | `parsers/layout_detector.py:37` | 4 | Layout detectado |
| `OrientationResult` | `parsers/orientation_detector.py:14` | 3 | Resultado orientación |
| `AccountTypeResult` | `parsers/account_type_resolver.py:30` | 5 | Tipo de cuenta resultante |
| `ParserConfig` | `parsers/config.py:57` | 4 sub-configs | Config externalizada |
| `OcrConfig` | `parsers/config.py:19` | 6 | Config OCR |
| `LayoutConfig` | `parsers/config.py:37` | 3 | Config layout |
| `AccountAmounts` | `models/account_amounts.py:8` | 8 | Montos por naturaleza |
| `AccountBalance` | `models/account_balance.py:11` | 12 | Balance de cuenta |
| `AccountingRecord` | `models/accounting_record.py:16` | 14 | CDM canónico |
| `CMCCFeatureFlags` | `pipeline/features.py:9` | 11 | Feature flags |
| `DecisionResult` | `decision/models.py:25` | 6 | Resultado decision v1 |
| `DecisionEvidence` | `decision/models.py:8` | 4 | Evidencia v1 |
| `Evidence` | `decision_v2/models.py:8` | 7 | Evidencia v2 |
| `DecisionResultV2` | `decision_v2/models.py:30` | 9 | Resultado decision v2 |
| `AjusteEspecial` | `reglas_especiales.py:27` | 5 | Ajuste de regla especial |

---

## 4. FLUJO DE DATOS COMPLETO

### 4.1 Flujo principal (app_validacion.py → HomologationPipeline)

```
PDF/Excel
    │
    ▼
ParserPDF.parsear() / parsear_excel()
    │
    ▼
list[CuentaRaw]  (en ResultadoParseo.cuentas)
    │
    ▼  (AccountAdapter.from_cuenta_raw)
AccountBalance  (con AccountAmounts anidado)
    │
    ├──► BalanceInterpreter → nature + classification_amount
    │
    ├──► AccountTypeResolver.resolve() → AccountType
    │
    ▼
HomologationPipeline._classify_account()
    ├── 1. LearningEngine.best_match() (Gold Standard)
    ├── 2. CMCCClassifier.classify() (si feature flag activo)
    ├── 3. ClasificadorCodigo.clasificar() (por código de cuenta)
    ├── 4. Diccionario exacto
    ├── 5. Diccionario fuzzy
    ├── 6. SemanticMatcher.match() (si activo)
    ├── 7. Regex fallback
    └── 8. DecisionEngine.decide() (si activo)
    │
    ▼
ProcesadorReglasEspeciales.aplicar() (R1-R5)
    │
    ▼
Resultado: {account, standard_code, final_code, confidence, method}
```

### 4.2 Flujo alternativo (ParserCore2 → ParseResult)

```
PDF
    │
    ▼
ParserCore2.parse()
    ├── validar_archivo()
    ├── ParserPDF._extraer_lineas()  ◄── ACEPCIÓN a método protegido
    ├── normalizar_codigo_ocr()
    ├── LayoutDetector.detect()
    ├── detectar_formato_codigo()
    ├── detectar_separador_miles()
    ├── parsear_todas() → list[RawAccount]
    └── ParseMetrics
    │
    ▼
ParseResult {accounts: list[RawAccount]}
```

### 4.3 Puntos donde se crean objetos CuentaRaw

1. **`parser_universal.py:527`** — `parsear_linea()` → `CuentaRaw(linea, codigo, nombre, monto, ...)`
2. **`parser_universal.py:547-551`** — `ParserPDF.parsear()` → `ResultadoParseo(cuentas=[...])`
3. **`app_validacion.py:281`** — `parsear_excel()` → `CuentaRaw(linea, codigo, nombre, monto, ...)`
4. **`parsers/line_parser.py:78`** — `raw_account_to_cuenta_raw()` → `CuentaRaw(linea=ra.line, ...)`

### 4.4 Puntos donde se crean objetos RawAccount

1. **`parsers/line_parser.py:65`** — `_cuenta_raw_to_account()` → `RawAccount(line=cr.linea, ...)`
2. **`parsers/line_parser.py:96-101`** — `parsear_todas()` → `list[RawAccount]`

---

## 5. DUPLICACIONES DETECTADAS

### 5.1 Duplicación crítica: ParserPDF ↔ ParserCore2

`ParserCore2.parse()` (pdf_parser.py:137) NO implementa parseo propio.
Llama a `ParserPDF._extraer_lineas()` (método protegido) para obtener texto,
y luego reimplementa en sus propias líneas la detección de formato, layout, etc.

**Problema:** Dos caminos de parseo que pueden divergir.
- Si se modifica `parser_universal.py`, `ParserCore2` puede romperse silenciosamente.
- Si `_extraer_lineas()` cambia su firma (retorna 2 o 3 valores), `ParserCore2` se rompe.

### 5.2 Duplicación de modelos: CuentaRaw ↔ RawAccount

```
CuentaRaw (español)      RawAccount (inglés)
──────────────────────    ──────────────────────
linea                     line
codigo                    code
nombre                    name
monto                     amount
origen_columna (enum)     column_origin (str)
es_total                  is_total
confianza_extraccion     extraction_confidence
tipo_cuenta               — (no existe)
```

Dos funciones de conversión bidireccionales en `line_parser.py:64-86`.

### 5.3 Duplicación de conversiones: CuentaRaw → AccountBalance

- `adapters/account_adapter.py:21` — `from_cuenta_raw()`
- `adapters/account_adapter.py:71` — `to_account_balance()` (alias)
- `pipelines/homologation_pipeline.py:421` — `AccountAdapter.from_cuenta_raw(cr)`
- `pipelines/new_pipeline.py:31` — `AccountAdapter.from_cuenta_raw(cr)`

### 5.4 Duplicación de mapeos

**`_LAYOUT_COLUMN_MAP`** (parser_universal.py:64):
```python
_LAYOUT_COLUMN_MAP: dict[str, OrigenColumna] = {
    "activo": ACTIVO, "pasivo": PASIVO, "perdida": PERDIDA, ...
}
```

**`_COLUMN_MAP`** (adapters/account_adapter.py:8):
```python
_COLUMN_MAP = {
    OrigenColumna.ACTIVO: "assets", OrigenColumna.PASIVO: "liabilities", ...
}
```

**`_CODE_PREFIX_TYPES`** (account_type_resolver.py:60):
```python
_CODE_PREFIX_TYPES: dict[str, AccountType] = {
    "ANC": ACTIVO, "AC": ACTIVO, "PNC": PASIVO, "PC": PASIVO, "PAT": PATRIMONIO,
}
```

**`_PREFIX_TIPO`** (homologation_pipeline.py:617):
```python
_PREFIX_TIPO: dict[str, set[str]] = {
    "ANC": {"ACTIVO"}, "AC": {"ACTIVO"}, "PNC": {"PASIVO"}, ...
}
```

**`_PREFIX_TIPO`** (decision_v2/engine.py:18): idéntico.

### 5.5 Duplicación de OCR

- `parser_universal.py:247-320` — `detectar_rotacion_osd()`, `detectar_rotacion_heuristica()`, `ocr_pagina()`, `_ocr_documento()`
- `parsers/ocr_engine.py:60-107` — `TesseractEngine.ocr_page()`, `detect_rotation()`, `ocr_documento()` (reimplementación)

### 5.6 Duplicación de hygiene

- `parser_universal.py:381-420` — `GARBAGE_PATTERNS`, `_es_linea_basura()`
- `parsers/hygiene.py:14-22` — `GARBAGE_PATTERNS = _ORIGINAL_PATTERNS`, `es_linea_basura()` (wrapper idéntico)

### 5.7 Duplicación de format_detector

- `parser_universal.py:149-210` — `detectar_formato_codigo()`, `detectar_separador_miles()`
- `parsers/format_detector.py:24-53` — funciones wrapper con `sample_size`

### 5.8 Duplicación de Decision Engines

- `decision/engine.py` (189L) — usado por pipeline
- `decision_v2/engine.py` (598L) — no usado, pero más completo

---

## 6. CÓDIGO MUERTO

### 6.1 Archivos completamente muertos

| Archivo | Líneas | Razón |
|---------|--------|-------|
| `parser_universal.py.save` | ~730 | Backup manual, versión anterior |
| `parsers/orientation_detector.py` | 120 | `detectar_orientacion_words()` nunca se llama |
| `pipeline/new_pipeline.py` | 55 | `NewPipeline` no referenciado por nada |
| `decision_v2/engine.py` | 598 | `DecisionEngineV2` no usado |
| `decision_v2/models.py` | 52 | Solo usado por v2 que no se usa |
| `decision_engine.py` | 102 | Script CLI standalone para `inspect_pdf.py`, no integrado |
| `evaluation/` | ? | Directorio no integrado en pipeline |

### 6.2 Código muerto dentro de archivos vivos

1. **`parser_universal.py:33-37`** — Feature flags `ENABLE_DYNAMIC_LAYOUT = False` y `ENABLE_ACCOUNT_TYPE_RESOLVER = False`. El código protegido por estos flags (layout detector, account type resolver) nunca se ejecuta porque los flags están en False.
2. **`parser_universal.py:326-350`** — `verificar_cuadre_balance()` — función definida pero nunca llamada desde ningún pipeline.
3. **`parsers/ocr_engine.py:80-107`** — `TesseractEngine.ocr_documento()` — duplica lógica de `ParserPDF._ocr_documento()`, no usado por `ParserCore2`.
4. **`parsers/config.py:50-53`** — `CachingConfig` — funcionalidad no implementada.
5. **`parser_universal.py:616-632`** — Código de `AccountTypeResolver` dentro de `ParserPDF.parsear()` protegido por flag en False.

### 6.3 Archivos backup/data duplicados

| Archivo | Estado |
|---------|--------|
| `diccionario.json` | ACTIVO |
| `diccionario_actualizado.json` | ¿backup? |
| `diccionario_optimizado.json` | ¿backup? |
| `diccionario_backup_pre_migration_20260707.json` | backup |
| `diccionario_optimizado_backup_pre_migration_20260707.json` | backup |
| `gold_standard.db` | ACTIVO |
| `gold_standard_bench.db` | ¿benchmark? |

---

## 7. RIESGOS TÉCNICOS

| # | Riesgo | Impacto | Probabilidad | Severidad |
|---|--------|---------|-------------|-----------|
| R1 | **ParserCore2 llama a método protegido `_extraer_lineas()`**. Si se modifica la firma (retorna 2 vs 3 valores), `ParserCore2` se rompe en runtime. | ParseResult vacío | Alta | 🔴 |
| R2 | **`CuentaRaw` y `RawAccount` desincronizados**. `RawAccount` no tiene `tipo_cuenta`. Si se agrega un campo a `CuentaRaw`, `RawAccount` queda atrás. | Datos incompletos | Media | 🟡 |
| R3 | **Feature flags contradictorios**. `ENABLE_DYNAMIC_LAYOUT=False` en v1 pero `LayoutConfig.enable_detection=True` en v2. Depende de qué parser se use. | Comportamiento impredecible | Alta | 🟡 |
| R4 | **app_validacion.py monolítico** (1340 líneas). Mezcla UI, parseo Excel, clasificación, gold standard, reglas especiales. Imposible de testear unitariamente. | Bugs en refactorización | Muy alta | 🔴 |
| R5 | **Tesseract hardcoded** (`/usr/local/share/tessdata`). No portable. Falla en Linux/Windows/Codespaces. | No funciona fuera de macOS | Alta | 🟡 |
| R6 | **`requirements.txt` y `pyproject.toml` inconsistentes**. `pyproject.toml` lista `pydantic`, `typer`, `fastapi` pero `requirements.txt` no. `requirements.txt` tiene `pillow` que pyproject no lista. | Dependencias faltantes | Media | 🟡 |
| R7 | **Sin tests de integración**. Solo hay tests unitarios de `AccountTypeResolver`. El flujo PDF → parseo → clasificación no está cubierto. | Regresiones no detectadas | Muy alta | 🔴 |
| R8 | **Dos pipelines que hacen lo mismo**. `HomologationPipeline` y `NewPipeline`. Si alguien modifica uno y no el otro, hay comportamientos divergentes. | Inconsistencia | Media | 🟡 |

---

## 8. PROBLEMAS CRÍTICOS

### P1 — Arquitectura de wrapper en cascada

```
ParserCore2.parse()
    → ParserPDF._extraer_lineas()     [método protegido]
    → parsear_todas()                  [RawAccount, no CuentaRaw]
    → LayoutDetector.detect()          [única lógica nueva]
    → detectar_formato_codigo()        [wrapper sobre v1]
    → detectar_separador_miles()       [wrapper sobre v1]
    → es_linea_basura()                [wrapper sobre v1]
```

**Problema:** `ParserCore2` no es un parser. Es un re-organizador que mezcla:
- Llamadas directas a v1 (a través de wrappers)
- Llamadas a métodos protegidos de v1
- Lógica nueva (LayoutDetector)
- Feature flags en dos sistemas distintos

**Solución:** Elegir UNA implementación y migrar todo a ella.

### P2 — Dos modelos de cuenta

`CuentaRaw` (español) y `RawAccount` (inglés) son el mismo concepto con nombres distintos.

Cada conversión entre ellos es:
- Una copia de campos (pérdida de rendimiento)
- Un punto de fallo (si se agrega un campo a uno y no al otro)
- Una complejidad innecesaria (el lector debe entender dos modelos)

**Solución:** Elegir UNO. Preferencia: `RawAccount` (inglés, alineado con `AccountingRecord`).

### P3 — Feature flags fragmentados

Los flags están en:
1. `parser_universal.py` como constantes globales
2. `parsers/config.py` como dataclasses
3. `pipeline/features.py` como `CMCCFeatureFlags`

Si quiero activar AccountTypeResolver, debo modificar:
- `parser_universal.py:37` → `ENABLE_ACCOUNT_TYPE_RESOLVER = True`
- `pipeline/homologation_pipeline.py:407` → ya lo llama directo (no usa el flag)
- `pipeline/features.py:46` → `ENABLE_ACCOUNT_TYPE_FILTER`

**Solución:** Una sola fuente de configuración.

### P4 — Importaciones circulares potenciales

`parser_universal.py` importa diferido `parsers.layout_detector` y `parsers.account_type_resolver`.
`parsers/pdf_parser.py` importa de `parser_universal`.
`parsers/__init__.py` importa de todo `parsers/`.

La red de dependencias es frágil y difícil de trazar.

---

## 9. OPORTUNIDADES DE MEJORA

### 9.1 Simplificación de arquitectura

**Estado actual:**
```
PDF → ParserPDF(v1) → CuentaRaw → RawAccount → AccountBalance → AccountingRecord
```

**Propuesta:**
```
PDF → ParserCore2 → RawAccount → AccountingRecord
```

Eliminar: `CuentaRaw`, conversiones intermedias, AccountBalance como modelo separado.

### 9.2 Unificación de configuración

**Estado actual:** 3 sistemas de flags (globales, dataclasses, environment).

**Propuesta:** Un solo `ParserConfig` (el de `parsers/config.py`) como fuente única, cargado desde TOML + env vars.

### 9.3 Eliminación de wrappers

`format_detector.py`, `hygiene.py`, `ocr_engine.py` no agregan valor.
Sus 3 líneas de lógica real pueden ir directamente donde se usan.

### 9.4 OCR pluggable

`ocr_engine.py` define una interfaz `OcrEngine(ABC)` que es correcta arquitectónicamente. Pero la implementación `TesseractEngine` duplica código de `parser_universal.py`.
La interfaz es buena, la implementación debe refactorizarse.

### 9.5 Decision engine único

`decision_v2/engine.py` tiene mejor lógica (ponderación, consenso, tie-breaking).
 migrar el pipeline a usar `DecisionEngineV2` y eliminar `decision/`.

---

## 10. PLAN DE MIGRACIÓN — 6 FASES

### Fase 1: Limpieza inicial

**Objetivo:** Eliminar todo el código muerto y duplicado evidente.

**Acciones:**
- Eliminar `parser_universal.py.save`
- Eliminar `pipeline/new_pipeline.py`
- Eliminar `parsers/orientation_detector.py`
- Eliminar `decision_v2/` completo
- Eliminar `decision_engine.py` (script standalone no integrado)
- Eliminar archivos diccionario duplicados (dejar solo `diccionario.json`)
- Revisar y limpiar `evaluation/`, `audit/`, `review/`

**Riesgo:** Mínimo. Código no referenciado.

### Fase 2: Unificación del modelo de cuenta

**Objetivo:** Un solo modelo de datos para cuentas extraídas.

**Acciones:**
1. Elegir `RawAccount` como modelo canónico (inglés, alineado con `AccountingRecord`)
2. Agregar campo `tipo_cuenta` a `RawAccount` (el que falta vs `CuentaRaw`)
3. Refactorizar `parser_universal.py` para que `parsear_linea()` retorne `RawAccount`
4. Eliminar `CuentaRaw` completamente
5. Refactorizar `AccountAdapter` para aceptar `RawAccount` directamente
6. Refactorizar `HomologationPipeline` para trabajar con `RawAccount`

**Riesgo:** Medio. Afecta a `app_validacion.py`, `parser_universal.py`, `pipeline/`, `adapters/`.

### Fase 3: Consolidación del parser

**Objetivo:** Un solo parser, sin herencia ni delegación a métodos protegidos.

**Acciones:**
1. Elegir `ParserCore2` como parser único
2. Migrar toda la lógica real de `parser_universal.py` (OCR, detección de formato, parseo de líneas) al package `parsers/`
3. Reimplementar `ParserCore2.parse()` sin llamar a `_extraer_lineas()` — implementar la extracción directamente
4. Eliminar todos los wrappers: `format_detector.py`, `hygiene.py`
5. Integrar `orientation_detector.py` (si se decide mantenerlo) en el flujo de extracción nativa
6. Eliminar `parser_universal.py` una vez migrado todo
7. Unificar feature flags en `ParserConfig`
8. Hacer `ParserConfig` la única fuente de configuración

**Riesgo:** Alto. Es el cambio más grande. Debe hacerse con cuidado y con pruebas.

### Fase 4: Unificación del pipeline

**Objetivo:** Un solo pipeline, un solo decision engine.

**Acciones:**
1. Elegir `DecisionEngineV2` como engine único (mejor lógica)
2. Migrar `HomologationPipeline` para usar `DecisionEngineV2`
3. Eliminar `decision/` (engine v1)
4. Simplificar `CMCCFeatureFlags`: eliminar flags obsoletos
5. Unificar `_CODE_PREFIX_TYPES` y `_PREFIX_TIPO` en un solo lugar
6. Unificar `_LAYOUT_COLUMN_MAP` y `_COLUMN_MAP`

**Riesgo:** Medio. La lógica de `DecisionEngineV2` es más compleja pero correcta.

### Fase 5: Refactorización de app_validacion.py

**Objetivo:** Separar UI de lógica de negocio.

**Acciones:**
1. Extraer `parsear_excel()` a `parsers/excel_parser.py` (ya existe como wrapper)
2. Extraer toda la lógica de clasificación a `HomologationPipeline`
3. Dejar `app_validacion.py` solo como UI (Streamlit)
4. Eliminar importaciones directas de `parser_universal` desde `app_validacion.py`

**Riesgo:** Alto. `app_validacion.py` es el punto de entrada principal.

### Fase 6: Robustez final

**Objetivo:** Código portable, testeable, configurable.

**Acciones:**
1. Hacer rutas de Tesseract configurables (desde `ParserConfig` + env)
2. Escribir tests de integración (PDF → ParseResult)
3. Escribir tests unitarios para `ParserCore2`
4. Verificar cobertura de tests
5. Sincronizar `requirements.txt` con `pyproject.toml`
6. Documentar arquitectura final

**Riesgo:** Bajo. Solo agrega valor.

---

## RESUMEN EJECUTIVO

El proyecto tiene una base sólida pero sufre de **arquitectura de wrapper en cascada**:
- V1 hace todo
- V2 envuelve a V1 (pero no agrega parseo real)
- Los pipelines envuelven a V1 o V2
- Los modelos se convierten entre sí sin necesidad

**Número de archivos Python:** ~45 (contando tests, scripts, tools)
**Líneas de código duplicado estimado:** ~800-1000 (15-20% del código activo)
**Archivos muertos:** 6
**Modelos duplicados:** 2 pares (CuentaRaw/RawAccount, DecisionEngine v1/v2)

**Estrategia:** Elegir lo mejor de cada implementación, migrar todo a una arquitectura lineal, eliminar duplicaciones. La prioridad es simplicidad y mantenibilidad a largo plazo.

---

*Fin del documento de auditoría.*
