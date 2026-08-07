# PARSER_DOUBLE_COLUMN_AUDIT — Balance Clasificado de doble columna

**Fecha:** 2026-08-05
**Tipo:** Auditoría técnica SOLO LECTURA (ningún archivo modificado)
**Caso reproducible:** `datasets/STRESS/8_COLUMNS/2022-BALANCE CLASIFICADO 2022.pdf`
**Benchmark de referencia:** M5 (2660/2662, 99.92%) — congelado, NO incluido en el alcance.

---

## 1. Causa raíz

### 1.1 Primaria — `ParserPDF._extraer_lineas()` aplaná las columnas

En `parser_universal.py:868` el flujo usa `page.extract_text()`, que **fusiona en una sola línea
todos los tokens que comparten la misma línea de base vertical**, sin distinguir su coordenada `x0`:

```
top=99  | 11010 CAJAS $ 2.995.687 21010 OBLIG. BANCOS U/O FINAN. $ 1 .864.696.580
```

Las dos columnas (ACTIVO a la izquierda `x≈54–256`, PASIVO a la derecha `x≈313–530`) comparten
la misma `top`, por lo que terminan en la misma línea de texto. Todo el resto del flujo
(`parsear_linea`, `LayoutDetector`, DIE, etc.) opera sobre **líneas de texto ya fusionadas** y
no puede recuperar la separación.

Cadena completa de fallo (confirmada por ejecución):

1. `ParserPDF.parsear()` (`parser_universal.py:628`) → `_extraer_lineas()` línea 868 → líneas fusionadas.
2. `parsear_linea()` (línea 488) interpreta la línea fusionada como UNA cuenta: nombre = `11010 CAJAS $ 2.995.687 21010 OBLIG. BANCOS …`, monto = el último token derecho (o `None`/`1.0` cuando el monto se parte en `1` `.864.696.580`).
3. `"AL 31 DE DICIEMBRE DE 2022"` no calza ningún `GARBAGE_PATTERNS` → se convierte en cuenta fantasma (`monto=2022.0`, `origen=ganancia`).

### 1.2 Secundaria — `PATRON_COMPACTO` rechaza códigos de 5 dígitos

`parser_universal.py:202`: `PATRON_COMPACTO = re.compile(r'^\d{6,10}$')` **NO matchea** códigos
de 5 dígitos (`11010`, `21010`, `13010`, `12040`). Verificado:

```
11010 -> compacto(6-10)? False
detectar_formato_codigo(['11010', ...]) -> SIN_CODIGO
```

Por eso los `codigo` quedan `None` en todas las cuentas extraídas. **Nota:** el
`document_intelligence/detector.py:229` (DIE `CodePatternDetector`) usa `\b\d{4,6}\b` y SÍ
reconoce los códigos de 5 dígitos como `COMPACTO` — la discrepancia entre detectores ya existe.

### 1.3 Facilitador — `ENABLE_DYNAMIC_LAYOUT=False`

`parser_universal.py:38` desactiva la rama que usaría `LayoutDetector` / perfil de familia /
`column_order`. Aunque el layout correcto se detecta (confianza 1.0), la extracción se cae al
fallback de "últimas 4 columnas" y, además, ese fallback solo afecta el `origen_columna` — **nunca
reparte las columnas** porque la línea ya viene fusionada.

---

## 2. Módulos existentes reutilizables (NO reinventar)

| Módulo | Ruta | Qué aporta | Estado |
|---|---|---|---|
| **DIE `FormatAnalyzer`** | `document_intelligence/analyzer.py` | Detecta `layout=VERTICAL`, `columns=[NOMBRE, MONTO]`, `code=COMPACTO` (5 díg.), `doc_type=BALANCE` con confianza 0.68 | ✅ Operativo |
| **DIE `LayoutDetector`** | `document_intelligence/detector.py:76` | Detecta secciones ACTIVO/PASIVO y `LayoutType.HORIZONTAL/VERTICAL` | ✅ Operativo |
| **DIE `ColumnDetector`** | `document_intelligence/detector.py:160` | Detecta `NOMBRE/MONTO/CODIGO` y `column_count` | ✅ Operativo |
| **`ParserSelector`** | `document_intelligence/parser_selector.py` | Recomienda parser (UNIVERSAL/CORE2/OCR) por señales | ✅ Operativo |
| **`SpecializedExtractorFactory`** | `document_intelligence/extractors/factory.py` | Selecciona extractor por fingerprint; fallback Universal | ✅ Operativo |
| **`GenericTableExtractor`** | `document_intelligence/extractors/profile_driven.py` | Aplica `layout_hint` aprendido → pasa a `ParserPDF.parsear(path, ctx)` | ✅ Operativo |
| **`ExtractionContext.layout_hint`** | `parser_universal.py:127` | Mecanismo para pasar orden de columnas al parser | ✅ Operativo |
| **`parse_with_analysis`** | `parsers/integration.py:179` | Orquesta `DocumentAnalyzer → context → ParserPDF` | ✅ Operativo |
| **`LayoutDetector` (parsers)** | `parsers/layout_detector.py` | Detecta columnas por encabezados (headers) | ✅ Operativo |
| **`DocumentAnalyzer`** | `parsers/analyzer.py` | Análisis estructural + `to_extraction_context()` | ✅ Operativo |
| **`inspect_pdf.py`** | raíz | Usa `page.extract_words()` con `x0` (prueba de concepto) | Referencia |

**Conclusión clave:** TODO el ecosistema de detección está construido y operativo. Lo que falta es
el **reparto de columnas por coordenada `x0`** al momento de extraer las líneas, y **conectar** la
detección de doble columna con la estrategia de extracción.

---

## 3. Punto exacto donde debe separarse el flujo

**En `ParserPDF._extraer_lineas()`** (`parser_universal.py:858-878`), antes de aplanar con
`page.extract_text()`. Es el ÚNICO punto del sistema donde todavía existe acceso a la información
de posición de las palabras (`page.extract_words()` con `x0/x1/top`).

Allí debe tomarse la decisión:

- **Balance simple** (1 columna de montos, o layout vertical clásico): flujo actual,
  `extract_text()` → `parsear_linea()` → **sin cambio**.
- **Balance doble columna** (ACTIVO | PASIVO lado a lado en la misma `top`, separación de x amplia):
  extraer por **palabras/posiciones** → armar **dos líneas independientes** por renglón
  (izquierda → ACTIVO, derecha → PASIVO) → dejar que `parsear_linea()` procese cada lado por
  separado (reutiliza todo el parsing de códigos/montos).

La detección "doble columna" ya se puede hacer con heurística simple sobre las palabras: contar
renglones con 2+ tokens numéricos de código en la misma `top` separados por >150px (verificado:
el caso de falla tiene 11 renglones así; los 20 HOLDOUT del benchmark tienen 0).

---

## 4. Opciones A/B/C — Recomendación

| Opción | Descripción | Veredicto |
|---|---|---|
| **A. Modificar ParserPDF** | Añadir rama de doble columna en `_extraer_lineas()` usando `extract_words()` | ⚠️ Menor superficie, pero acopla la lógica de columnas al parser legacy |
| **B. Parser especializado nuevo** | Clase `DoubleColumnParser` con extracción por `x0` | ⚠️ Es lo que la arquitectura ya prevé (extractores especializados), pero NO debe reimplementar parsing de cuentas |
| **C. Delegación automática** | Un detector marca "doble columna" y el flujo redirige | ✅ **RECOMENDADO** |

### Recomendación: **B + C combinados**, sin tocar el corazón de ParserPDF

La arquitectura del proyecto ya define exactamente este patrón en
`document_intelligence/extractors/` (Sprint 34-36):

1. **Un `DoubleColumnExtractor`** registrado como `SpecializedExtractor` (patrón de
   `NogalesExtractor`/`AicsaExtractor` en `specialized.py`), con la mecánica de
   `GenericTableExtractor`: delega a `ParserPDF.parsear()` como base, pero **pre-ajusta** el
   problema de columnas.

2. **`SpecializedExtractorFactory`** lo selecciona automáticamente (mismo camino que hoy: si el
   fingerprint no matchea familia o falla → `UniversalExtractor` = comportamiento actual, 0 riesgo).

3. **El mínimo cambio en ParserPDF** es **una sola cosa**: que `_extraer_lineas()` acepte
   procesar por `extract_words()` cuando reciba una señal (p. ej. `context.layout_hint` o un flag
   interno `double_column=True`), produciendo las líneas ya separadas. Alternativa aún más limpia:
   el extractor genera las líneas separadas y las inyecta vía un hook/`ExtractionContext`.

**Lo que NO se debe hacer:** crear un parser desde cero que reimplemente código/monto/origen.
Todo el parsing de `CuentaRaw` (patrones, montos, totales, basura) vive en `parsear_linea()` y
`parsear_todas()` y debe reutilizarse **tal cual** para cada lado de la columna.

---

## 5. Arquitectura correcta según el proyecto

Flujo objetivo (respetando la doble vía V1/V2 y la infraestructura existente):

```
PDF
  └─► _extraer_lineas (ParserPDF)
        │
        ├─¿doble columna?  (heurística x0: 2 códigos en misma top, gap >150px)
        │      │
        │      ├─ NO  → extract_text() → líneas planas  (flujo actual, sin cambio)
        │      │
        │      └─ SÍ  → extract_words() → 2 líneas por renglón:
        │                    izq: '11010 CAJAS $ 2.995.687'
        │                    der: '21010 OBLIG. BANCOS U/O FINAN. $ 1 .864.696.580'
        ▼
   parsear_linea() / parsear_todas()   ← REUTILIZADO tal cual (código+monto+origen)
        ▼
   CuentaRaw[]  (una por lado; codigo presente; origen activo/pasivo)
        ▼
   [V1] HomologationPipeline  |  [V2] adapters/parser_adapter (ParserAdapter)
```

Principios respetados (del propio proyecto):
- "La extracción SIEMPRE la hace `ParserPDF.parsear()` como base" (`profile_driven.py:10`).
- "`UniversalExtractor` es el fallback obligatorio" (`universal.py`, `base.py`).
- "Cualquier fallo → comportamiento actual" (backward compatibility garantizada en
  `factory.py`, `profile_driven.py`, `integration.py`).

---

## 6. Archivos que quedarían afectados (y cuáles NO)

### A modificar (mínimo)

| Archivo | Cambio |
|---|---|
| `parser_universal.py` | En `_extraer_lineas()` (858): rama opcional de doble columna vía `extract_words()`. Opcional: ampliar `PATRON_COMPACTO` a 5 dígitos. |
| `document_intelligence/extractors/double_column.py` (nuevo) | `DoubleColumnExtractor` (patrón `GenericTableExtractor`) que detecta y delega con las líneas separadas. |
| `document_intelligence/extractors/__init__.py` | Registrar el nuevo extractor (patrón de `specialized.py`). |
| `parsers/integration.py` | (Opcional) exponer `parse_with_analysis` con detección de doble columna explícita. |

### NO deben tocarse (restricción del usuario)

`learning/`, runtime, benchmark (M5/2660-2662), gold, semantic, CMCC, Knowledge Manager, UI
(`app_validacion.py`), `pipeline/`, `orchestrator/`. El adaptador `adapters/parser_adapter.py`
**no cambia** (sigue llamando `ParserPDF.parsear`); solo se beneficia del fix.

---

## 7. Impacto esperado

### Positivo
- `11010 CAJAS` y `21010 OBLIG. BANCOS` → **2 cuentas separadas**, con `codigo` y `origen_columna`
  (`activo` / `pasivo`) correctos.
- `"AL 31 DE DICIEMBRE DE 2022"` → se elimina (renglón sin código real / fecha de encabezado).
- Benchmark HOLDOUT M5 **no se toca**: los 20 archivos del benchmark NO son doble columna
  (verificado: 0 renglones de doble código; el caso de falla tiene 11). El fix solo se activa con
  la heurística de doble columna.
- Todos los demás formatos (vertical simple, ER, etc.): flujo inalterado (rama `NO`).

### Riesgo bajo
- Solo se modifica la extracción de líneas en el caso específico doble-columna; el parsing de
  cuentas queda intacto.
- El cambio en `PATRON_COMPACTO` (5 dígitos) podría hacer que se detecten códigos donde antes
  `SIN_CODIGO` — verificar en tests (37 tests de parsing/column existentes; suite completa verde
  actualmente).

---

## 8. Riesgos

| Riesgo | Nivel | Mitigación |
|---|---|---|
| Regresión en formatos no-doble-columna | Bajo | Rama condicionada por heurística; fallback = flujo actual exacto. |
| Falsos positivos de "doble columna" (p. ej. ER con debe/haber) | Medio | Umbral estricto: 2 códigos numéricos en misma `top` + gap x >150px + secciones ACTIVO/PASIVO presentes (reusar DIE). |
| `PATRON_COMPACTO` 5 dígitos cambie formato detectado en otros docs | Medio | Validar contra HOLDOUT M5 (2660/2662) antes de habilitar; puede dejarse opcional. |
| El extractor nuevo no sea seleccionado (family match falla) | Bajo | `UniversalExtractor` sigue como fallback obligatorio → sin cambio de comportamiento. |
| Montos partidos en tokens (`1` `.864.696.580`) | Medio | Ya ocurre hoy en el flujo universal; si la rama de columnas lo mitiga, es un bonus; no es objetivo de este fix. |

---

## 9. Plan de implementación en fases (para aprobación)

### FASE 0 — Preparación y validación del fix propuesto
1. Confirmar heurística de detección de doble columna con el caso de falla (11 renglones) y con
   los 20 HOLDOUT (0 renglones) → garantiza que el benchmark no se activa.
2. Correr suite completa de tests (estado actual verde) para tener línea base.

### FASE 1 — Mínimo en `parser_universal.py`
3. En `_extraer_lineas()`: añadir rama `_extraer_lineas_doble_columna()` usando
   `page.extract_words()`, que devuelva líneas separadas por lado.
4. Activar solo cuando un detector confirma doble columna (señal vía parámetro/flag interno).
5. Tests: caso 8_COLUMNS (cuentas separadas, códigos presentes) + HOLDOUT (sin cambios).

### FASE 2 — Conectar la detección
6. Crear `DoubleColumnExtractor` (patrón `GenericTableExtractor`) que detecte doble columna con
   `FormatAnalyzer`/DIE y deleje a `ParserPDF.parsear(path, ctx)` con las líneas separadas.
7. Registrar en `document_intelligence/extractors/`.
8. Verificar que `SpecializedExtractorFactory.detect()` lo selecciona y que el fallback universal
   sigue operando ante cualquier error.

### FASE 3 — Códigos de 5 dígitos (opcional, separado)
9. Ampliar `PATRON_COMPACTO` a 5 dígitos (alineándolo al DIE `\b\d{4,6}\b`).
10. Validar contra HOLDOUT M5: los 2660/2662 deben mantenerse idénticos.

### FASE 4 — Validación de regresión
11. Suite completa de tests (incl. `test_column_interpretation.py`, `test_generic_extractor.py`).
12. Shadow sobre dataset completo (o `datasets/PROCESSING`) comparando antes/después.
13. Confirmar que `gold_standard.db` no cambia (checksum).

---

*Fin del informe. Ningún archivo fue modificado.*
