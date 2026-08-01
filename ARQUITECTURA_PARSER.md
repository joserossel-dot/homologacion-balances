# ARQUITECTURA DEFINITIVA DEL PARSER

> Diseño arquitectónico orientado a robustez sobre elegancia.
> Prioridad: adaptarse automáticamente a cientos de formatos distintos de balances tributarios chilenos.

---

## DIAGNÓSTICO FUNCIONAL

### ¿Qué partes realmente aportan al parser?

| Componente | Aporte real | Riesgo si se toca |
|------------|-------------|-------------------|
| `parser_universal.py` (726L) | ✅ Corazón del parser. OCR, detección de formato, parseo de líneas, validación de archivos. Código probado contra cientos de PDFs. | 🔴 MÁXIMO. No tocar. |
| `parsers/layout_detector.py` | ✅ **Crítico**. Detecta columnas reales del documento. Permite que el parser se adapte a distintos layouts. | 🟡 Medio. No está en producción (flag `ENABLE_DYNAMIC_LAYOUT=False`). |
| `parsers/orientation_detector.py` | ✅ **Crítico pero no integrado**. Detecta rotación 180° por palabras invertidas. Específico para PDFs escaneados. | 🟢 Bajo. Código aislado, fácil de integrar. |
| `parsers/account_type_resolver.py` | ✅ **Crítico**. Resuelve ambigüedad de tipo de cuenta (activo/pasivo/perdida/ganancia). Usado por el pipeline de clasificación. | 🟡 Medio. Usado en producción. |
| `parsers/config.py` | ✅ **Importante**. Externaliza configuración. Permite adaptar el parser sin cambiar código. | 🟢 Bajo. No afecta parseo actual. |
| `parsers/ocr_engine.py` (interfaz) | ✅ **Buena abstracción**. Permite cambiar motor OCR sin tocar el parser. | 🟢 Bajo. No usado en producción. |
| `parsers/pdf_parser.py` (ParserCore2) | ❌ **No es un parser real**. Es un wrapper que llama a métodos protegidos de v1. No agrega capacidad de parseo. | 🟡 Medio. No afecta nada si se mantiene igual. |
| `parsers/format_detector.py` | ❌ **Wrapper puro**. Delega en `parser_universal`. No agrega lógica. | 🟢 Bajo. |
| `parsers/hygiene.py` | ❌ **Wrapper puro**. Delega en `parser_universal`. 22 líneas. | 🟢 Bajo. |
| `parsers/excel_parser.py` | ❌ **Wrapper puro**. Delega en `app_validacion`. | 🟢 Bajo. |
| `parsers/factory.py` | ❌ **Sin propósito real**. Fábrica para elegir entre v1 y v2, cuando v2 no es un parser real. | 🟢 Bajo. |
| `pipeline/homologation_pipeline.py` | ✅ **Pipeline de clasificación probado**. No es parser, es homologación. | 🟡 Medio. No tocar sin tests. |
| `app_validacion.py` | ✅ **Interfaz de usuario funcional**. Usada por operadores. Monolítica pero probada. | 🔴 MÁXIMO. No refactorizar. |
| `reglas_especiales.py` | ✅ **Reglas de negocio validadas** (R1-R5). Post-procesamiento crítico. | 🟡 Medio. |

### ¿Qué partes son wrappers sin valor?

1. `parsers/format_detector.py` — 53 líneas que llaman a `parser_universal`
2. `parsers/hygiene.py` — 22 líneas que re-exportan `GARBAGE_PATTERNS`
3. `parsers/factory.py` — 38 líneas que eligen entre v1 y v2
4. `parsers/excel_parser.py` — 20 líneas que delegan en `app_validacion`

### ¿Qué piezas son críticas para la estabilidad?

1. `parser_universal.py` — **NO TOCAR**. Es el parser probado.
2. `app_validacion.py` — **NO TOCAR**. Es la UI que usan los operadores.
3. `pipeline/homologation_pipeline.py` — **NO TOCAR sin tests de regresión**.
4. `reglas_especiales.py` — **NO TOCAR**. Reglas de negocio validadas.

### ¿Qué piezas NO deben tocarse todavía?

1. `parser_universal.py` — el corazón del proyecto
2. `app_validacion.py` — la interfaz de usuario
3. `pipeline/homologation_pipeline.py` — el pipeline que funciona
4. `models/account_balance.py` y `models/accounting_record.py` — modelos de datos usados en pipeline

---

## ARQUITECTURA DEFINITIVA

### Principio rector

El parser debe **detectar antes de parsear**.

Cada documento sigue este flujo:

```
DOCUMENTO
    │
    ▼
┌──────────────────────────────────┐
│        DOCUMENT ANALYZER         │  ← NUEVO (orquestador inteligente)
│                                  │
│  1. ¿Qué tipo de documento es?   │
│     - PDF nativo / PDF imagen /  │
│       Excel / otro               │
│                                  │
│  2. ¿Cuál es su orientación?     │
│     - 0° / 90° / 180° / 270°   │
│                                  │
│  3. ¿Cuál es su estructura?      │
│     - columnas / tablas /        │
│       texto libre                │
│                                  │
│  4. ¿Cuál es su layout?          │
│     - encabezados de columna     │
│     - orden de columnas          │
│     - qué columnas existen       │
│                                  │
│  5. ¿Cuál es su formato?         │
│     - código: guión/punto/       │
│       compacto/sin código        │
│     - separador de miles         │
│     - separador decimal          │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│         TEXT EXTRACTOR           │  ← EXISTENTE (parser_universal)
│                                  │
│  - Extracción nativa (pdfplumber)│
│  - OCR (Tesseract)               │
│  - Corrección de rotación        │
│  - Extracción de tablas          │
│  → lineas: list[str]             │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│        LINE INTERPRETER          │  ← EXISTENTE (parsear_linea + mejoras)
│                                  │
│  Interpreta cada línea usando    │
│  el análisis del DocumentAnalyzer│
│                                  │
│  - reconocimiento de código      │
│  - reconocimiento de nombre      │
│  - reconocimiento de montos      │
│  - asignación de columna         │
│  - detección de totales          │
│  → RawAccount[]                  │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│       ACCOUNT RESOLVER           │  ← EXISTENTE (pipeline)
│                                  │
│  - AccountTypeResolver           │
│  - HomologationPipeline          │
│  - ReglasEspeciales              │
│  → Resultado clasificado         │
└──────────────────────────────────┘
```

### Módulos propuestos

```
parsers/
├── __init__.py              # Exporta solo lo necesario
├── analyzer.py              # NUEVO: DocumentAnalyzer (detecta estructura ANTES de parsear)
├── extractor.py             # NUEVO: unifica extracción (nativa + OCR)
├── line_interpreter.py      # NUEVO: interpreta líneas usando metadata del analyzer
├── config.py                # EXISTENTE: mantener, mejorar
├── models.py                # NUEVO: RawAccount, ParseResult, ParseMetrics (un solo lugar)
├── layout_detector.py       # EXISTENTE: mantener, mejorar detección
├── orientation_detector.py  # EXISTENTE: integrar en el flujo
├── account_type_resolver.py # EXISTENTE: mantener
├── ocr_engine.py            # EXISTENTE: mantener interfaz, limpiar implementación
│
├── parser_universal/        # CONTENEDOR: código probado, sin modificar
│   └── legacy.py            # parser_universal.py renombrado, importable como fallback
│
└── (eliminar)
    ├── format_detector.py   # Fusión en analyzer.py
    ├── hygiene.py           # Fusión en line_interpreter.py
    ├── excel_parser.py      # Fusión en extractor.py
    ├── factory.py           # Eliminar (sin propósito)
    ├── pdf_parser.py        # Reemplazar por extractor.py + analyzer.py
    └── line_parser.py       # Fusión en line_interpreter.py
```

---

## ¿QUÉ CAMBIAR Y QUÉ NO?

### SÍ cambiar (solo cuando aporte robustez)

| Cambio | Por qué mejora el parser |
|--------|--------------------------|
| Integrar `OrientationDetector` en el flujo | Permite detectar PDFs rotados 180° automáticamente |
| Activar `LayoutDetector` en producción | Hace que el parser se adapte a distintos layouts sin hardcode |
| Activar `ENABLE_DYNAMIC_LAYOUT` | Misma razón: adaptación automática |
| Mover `GARBAGE_PATTERNS` a un solo lugar | Elimina riesgo de tener dos listas que divergen |
| Unificar detección de formato en `analyzer.py` | Centraliza la lógica de "¿qué documento es?" |
| Agregar detección de tablas | Muchos balances vienen en tablas, no texto lineal |

### NO cambiar (riesgo supera beneficio)

| Lo que NO se toca | Razón |
|-------------------|-------|
| `parser_universal.py` | Corazón probado del parser. Cientos de PDFs dependen de él. |
| `app_validacion.py` | UI que usan operadores. Refactorizar = riesgo de perder funcionalidad. |
| `pipeline/homologation_pipeline.py` | Pipeline de clasificación probado. Bugs aquí = clasificaciones incorrectas. |
| `models/` existentes | Usados por pipeline. Cambiarlos = cambiar pipeline. No vale la pena. |
| `reglas_especiales.py` | Reglas de negocio validadas (R1-R5). |
| `decision/` vs `decision_v2/` | Ambos existen. El pipeline usa v1. Mientras funcione, no se toca. |
| `CuentaRaw` vs `RawAccount` | Son el mismo concepto con distinto nombre. No cambiarlos evita romper APIs. |

### ¿Qué fusionar y qué no?

| Fusión | Estrategia |
|--------|-----------|
| `format_detector.py` → `analyzer.py` | Mover la lógica, no eliminar `format_detector` hasta que `analyzer` esté probado |
| `hygiene.py` → `line_interpreter.py` | Idem |
| `line_parser.py` → `line_interpreter.py` | Idem |
| `pdf_parser.py` → `extractor.py` + `analyzer.py` | Idem |
| `excel_parser.py` → `extractor.py` | Idem |
| `CuentaRaw` ↔ `RawAccount` | **NO fusionar**. Mantener ambos. Agregar adaptador si es necesario. |

### ¿Eliminar o preservar?

| Archivo | Decisión | Razón |
|---------|----------|-------|
| `parser_universal.py.save` | ✅ Eliminar | Backup manual, confunde |
| `new_pipeline.py` | ✅ Eliminar | Abandonado, no referenciado |
| `decision_v2/` | ⏸ Dejar | No molesta, puede usarse en el futuro |
| `parser_universal.py` | 🔒 Preservar intacto | Corazón del parser |
| Wrappers (`format_detector`, `hygiene`, etc.) | ⏸ Dejar por ahora | Eliminarlos no aporta robustez |

---

## ROADMAP POR FASES

### FASE 0: Sin cambios (aprobación del diseño)

- ✅ Diseñar arquitectura
- ✅ Documentar decisión
- ⏳ **Esperar aprobación**

---

### FASE 1: Integrar OrientationDetector en el parser

**Objetivo:** Que el parser detecte automáticamente PDFs rotados 180°.

**Cambios:**
- Modificar `parser_universal.py:_extraer_lineas()` para que llame a `detectar_orientacion_words()` en el texto extraído
- Si detecta rotación 180°, invertir líneas y palabras
- Esto NO cambia APIs. Solo mejora la detección.

**Riesgo:** Bajo. La función `detectar_orientacion_words()` no se ejecuta si no hay palabras invertidas. Si no hay match, comportamiento es idéntico al actual.

**Prueba:** Comparar output con/sin PDFs rotados 180°.

**Commit:** `feat: integrar detección de orientación 180° en extracción de texto`

---

### FASE 2: Activar LayoutDetector en producción

**Objetivo:** Que el parser detecte automáticamente el layout de columnas.

**Cambios:**
- Cambiar `ENABLE_DYNAMIC_LAYOUT = True` en `parser_universal.py`
- Monitorear si hay regresiones

**Riesgo:** Medio. `LayoutDetector` no ha sido probado en producción. Pero:
- Tiene fallback a heurística estándar si confianza < 0.5
- Cualquier detección baja se ignora automáticamente

**Prueba:** Ejecutar contra 20+ PDFs de distintas fuentes, comparar resultados.

**Commit:** `feat: activar detección dinámica de layout (ENABLE_DYNAMIC_LAYOUT=True)`

---

### FASE 3: Unificar hygiene en un solo lugar

**Objetivo:** Eliminar el riesgo de tener dos listas `GARBAGE_PATTERNS` que divergen.

**Cambios:**
- Mover `GARBAGE_PATTERNS` y `_es_linea_basura()` de `parser_universal.py` a `parsers/hygiene.py`
- En `parser_universal.py`, importar desde `parsers/hygiene`
- Esto NO cambia comportamiento. Solo cambia dónde está definido.

**Riesgo:** Mínimo. Es un refactor de importación.

**Prueba:** `python -c "from parser_universal import _es_linea_basura; print(_es_linea_basura('test'))"` debe funcionar igual.

**Commit:** `refactor: unificar GARBAGE_PATTERNS en parsers/hygiene.py como fuente única`

---

### FASE 4: Crear DocumentAnalyzer

**Objetivo:** Separar la fase de "detección" de la fase de "extracción".

**Cambios:**
- Crear `parsers/analyzer.py` con `DocumentAnalyzer`
- `DocumentAnalyzer` recibe un PDF y retorna metadata: orientación, layout, formato código, separador, tipo de estructura
- `ParserCore2` y `ParserPDF` pueden usar este analyzer
- NO modificar `parser_universal.py` — el analyzer es una capa por encima

**Riesgo:** Bajo. Código nuevo que no toca el existente.

**Commit:** `feat: agregar DocumentAnalyzer para detectar estructura del documento antes de parsear`

---

### FASE 5: Mejorar LayoutDetector

**Objetivo:** Que detecte más patrones de layout.

**Cambios:**
- Agregar más variantes al `HEADER_LEXICON` (basado en balances reales)
- Mejorar detección de columnas cuando hay mezcla de idiomas
- Agregar detección de "Debe/Haber" (formato clásico chileno)
- Agregar detección de columnas de saldo

**Riesgo:** Bajo. Son adiciones al lexicon, no cambios estructurales.

**Prueba:** Tests unitarios con headers reales de balances.

**Commit:** `feat: expandir HEADER_LEXICON con variantes de balances reales`

---

### FASE 6: Agregar detección de tablas

**Objetivo:** Detectar cuando el PDF tiene estructura de tabla y extraer filas completas.

**Cambios:**
- En `DocumentAnalyzer`, detectar si el PDF tiene tablas detectables por pdfplumber
- Si hay tablas, extraer filas completas (no líneas sueltas)
- Fusionar con extracción de texto normal

**Riesgo:** Medio. Nueva funcionalidad que no afecta el flujo existente.

**Prueba:** PDFs con tabla de balance de 8 columnas.

**Commit:** `feat: detección y extracción de tablas en PDFs estructurados`

---

### FASE 7: Limpieza de archivos basura

**Objetivo:** Eliminar lo que literalmente no se usa y nadie referencia.

**Cambios:**
- Eliminar `parser_universal.py.save`
- Eliminar `pipeline/new_pipeline.py`
- Eliminar `decision_engine.py` (script standalone)
- Eliminar archivos diccionario duplicados

**Riesgo:** Mínimo. `git rm` de no-referenciados.

**Commit:** `chore: eliminar archivos huérfanos (.save, new_pipeline, diccionarios backup)`

---

### FASE 8: Unificación de feature flags

**Objetivo:** Un solo sistema de configuración externalizado.

**Cambios:**
- Mover feature flags de `parser_universal.py` a `ParserConfig`
- `parser_universal.py` lee de `ParserConfig`
- Las constantes globales se mantienen como defaults, pero el parser puede configurarse externamente

**Riesgo:** Medio. Cambia cómo se configuran los flags, pero no el comportamiento por defecto.

**Commit:** `feat: unificar feature flags en ParserConfig como fuente única de configuración`

---

### FASE 9: OCR pluggable

**Objetivo:** Poder cambiar de motor OCR sin modificar el parser.

**Cambios:**
- Migrar `parser_universal.py` para usar la interfaz `OcrEngine`
- Implementación default: `TesseractEngine`
- Configurable desde `ParserConfig`

**Riesgo:** Alto. Toca el corazón del parser. Requiere tests de regresión.

**Prueba:** Ejecutar contra todos los PDFs de prueba, comparar output antes/después.

**Commit:** `feat: hacer OCR pluggable mediante interfaz OcrEngine`

---

## CRITERIO DE DECISIÓN POR FASE

Cada fase debe pasar este checklist antes de implementarse:

```
□ ¿Mejora la robustez del parser?
□ ¿Reduce bugs potenciales?
□ ¿Mejora detección automática?
□ ¿Mejora OCR?
□ ¿Mejora interpretación de layouts?
□ ¿Mejora clasificación?
□ ¿El proyecto sigue funcionando después del cambio?
□ ¿El cambio es pequeño y reversible?
```

Si la respuesta es NO a las primeras 6 preguntas, la fase no se hace.

---

## MAPA DE TRANSICIÓN

```
ESTADO ACTUAL:
parser_universal.py (v1, 726L, monolítico pero probado)
    └── parsers/ (v2, 11 archivos, wrappers + layout + resolver)

ESTADO FUTURO:
parser_universal.py (intacto, como fallback de emergencia)
    └── parsers/
        ├── config.py               (unificado)
        ├── models.py               (modelos de datos)
        ├── analyzer.py             (DocumentAnalyzer — NUEVO)
        ├── extractor.py            (extracción unificada)
        ├── line_interpreter.py     (interpretación de líneas)
        ├── layout_detector.py      (mejorado)
        ├── orientation_detector.py (integrado)
        ├── account_type_resolver.py (intacto)
        └── ocr_engine.py           (pluggable)
```

La transición es gradual. Cada fase es independiente. En cualquier momento se puede hacer rollback.

---

## LO QUE NUNCA SE DEBE HACER

1. ❌ Refactorizar `parser_universal.py` "porque es feo".
2. ❌ Cambiar nombres de modelos que funcionan.
3. ❌ Eliminar `CuentaRaw` "porque RawAccount es más moderno".
4. ❌ Migrar `app_validacion.py` a una arquitectura limpia.
5. ❌ Fusionar `decision/` y `decision_v2/` "para tener uno solo".
6. ❌ Hacer cambios que requieran modificar todos los archivos del proyecto.
7. ❌ Refactorizar por refactorizar.

---

*Documento de arquitectura — versión 2026-07-26*
