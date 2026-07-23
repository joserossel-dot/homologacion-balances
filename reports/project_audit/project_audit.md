# Project Audit Report

**Date**: 2026-07-09
**Auditor**: Release Governance Pipeline
**Scope**: Fase 1A completion, parser hygiene, column inversion, contamination, dictionary

---

## 1. Estado de Fase 1A — ✗ INCOMPLETA

### 1.1 Archivos duplicados en disco (6 archivos)

#### 1.1.1 `pipeline/new_pipeline.py` (55 líneas)

| Propiedad | Valor |
|-----------|-------|
| Consumidores | **0** (cero imports en todo el proyecto) |
| Propósito | Pipeline simplificado: solo extrae cuentas, sin clasificación, sin diccionario, sin rules, sin learning, sin semantic, sin CMCC |
| Fuente oficial | `pipeline/homologation_pipeline.py` (284 líneas, 22 consumidores) |
| Estado | **ORPHAN** — código muerto |

#### 1.1.2 `extractors/table_extractor.py` (352 líneas)

| Propiedad | Valor |
|-----------|-------|
| Consumidores | **0** (cero imports) |
| Propósito | Extracción vía tablas para PDFs F02 con tablas detectadas. Sistema de columnas propio (debit/credit) incompatible con Activo/Pasivo/Perdida/Ganancia |
| Fuente oficial | `parser_universal.py` (638 líneas, 8 consumidores) |
| Estado | **ORPHAN** — código muerto |

#### 1.1.3 `diccionario_optimizado.json` (712 entradas, 94 KB)

| Propiedad | Valor |
|-----------|-------|
| Consumidores runtime | **0** — solo leído por `tools/dictionary_audit.py` y `tools/validate_dictionary_audit.py` (auditoría, no producción) |
| Relación | Subconjunto: todo `optimizado` está en `diccionario.json` |
| Fuente oficial | `diccionario.json` (826 entradas, 108 KB, 9 fuentes) |
| Estado | **STALE** — superado por `diccionario.json` |

#### 1.1.4 `diccionario_actualizado.json` (781 entradas, 102 KB)

| Propiedad | Valor |
|-----------|-------|
| Consumidores runtime | **0** |
| Relación | Exportación desde Streamlit app. Igual que `diccionario.json` menos 45 entradas |
| Estado | **SNAPSHOT** — export temporal sin propósito actual |

#### 1.1.5 `diccionario_backup_pre_migration_20260707.json` (108 KB)

| Propiedad | Valor |
|-----------|-------|
| Consumidores | **0** |
| Relación | **Byte-idéntico** a `diccionario.json` (diff confirma 0 diferencias) |
| Estado | **BACKUP** — debe moverse a `.backups/` o eliminarse |

#### 1.1.6 `diccionario_optimizado_backup_pre_migration_20260707.json` (94 KB)

| Propiedad | Valor |
|-----------|-------|
| Consumidores | **0** |
| Relación | **Byte-idéntico** a `diccionario_optimizado.json` |
| Estado | **BACKUP** — debe moverse o eliminarse |

### 1.2 Inconsistencia arquitectónica: `src/` vs `app_validacion.py`

`src/core/orquestador.py` define `PipelineOrquestador.procesar_analisis_completo()` pero **NO llama a `HomologationPipeline`**. Es un stub. La app real (`app_validacion.py`) usa `HomologationPipeline` directamente, creando dos caminos paralelos donde debiera haber uno.

### 1.3 Veredicto: Fase 1A INCOMPLETA

| Criterio | Estado |
|----------|--------|
| Archivos duplicados eliminados | ✗ — 6 archivos orphan aún en disco |
| Consumidores documentados | ✓ — mapeo completo existe en tools/ |
| Fuente oficial declarada | ✗ — no hay README ni marcador de deprecación |
| `src/` vs `app_validacion.py` | ✗ — dos entry points paralelos sin coordinación |

---

## 2. Estado del Parser — Filtro de Líneas Basura

### 2.1 ¿Existe filtro de líneas basura?

**Sí, mínimo.** `parser_universal.py:385-494` (`parsear_linea()`).

### 2.2 Filtros existentes (líneas exactas)

| Tipo | Líneas | Mecanismo |
|------|--------|-----------|
| Líneas < 4 caracteres | 398-399 | `if len(linea) < 4: return None` |
| Basura OCR final (≤2 tokens, sin dígitos, ≤2 chars) | 426-429 | Loop descarta hasta 2 tokens finales no numéricos |
| Sin código + sin montos → nombre vacío | 431-442 | Si no hay tokens numéricos → `nombre` vacío |
| Nombre < 3 caracteres | 447-448 | `if not nombre or len(nombre) < 3: return None` |
| Normalización OCR (`o`/`O` → `0`) | 358-361, 434 | `normalizar_token_ocr()` |

### 2.3 Gaps: lo que NO se filtra

| Tipo | Ejemplo | Riesgo |
|------|---------|--------|
| Teléfonos | `+56 9 1234 5678`, `(2) 2123 4567` | Puede generar código+monto+falso nombre |
| URLs | `www.empresa.cl`, `https://...` | NO detectado |
| Páginas | `Página 1 de 15` | 11 caracteres, pasa filtro de 4 |
| Encabezados | `Balance General al 31/12/2024` | NO filtrado |
| Pies de página | `Firma del Contador`, `Ver Notas 1 a 25` | NO filtrado |
| Direcciones | `RUT: 76.123.456-7`, `Domicilio: Av. Siempre Viva 123` | RUT matchea PATRON_MONTOS |
| Texto administrativo | `Deloitte Auditores Consultores Ltda.` | NO filtrado |
| Fechas emisión | `Fecha de emisión: 15/03/2025` | NO filtrado |
| Ruido OCR largo no numérico | `\|<\|—~=\|` (≥4 chars sin código ni montos) | Solo frena si nombre < 3 |

### 2.4 Conclusión

El parser confía en que las líneas basura **accidentalmente** no generen código + nombre + montos simultáneamente. Esto es frágil. No hay una sola regex de detección de patrones específicos (teléfono, URL, RUT, página, encabezado, dirección).

---

## 3. Estado de Inversión de Columnas

### 3.1 Asunción actual

`parser_universal.py:462-463`:

```python
ULTIMAS_COLS = [OrigenColumna.ACTIVO,
                OrigenColumna.PASIVO,
                OrigenColumna.PERDIDA,
                OrigenColumna.GANANCIA]
```

El parser **asume que todo balance chileno** tiene las columnas en el orden: `Activo | Pasivo | Pérdida | Ganancia`.

### 3.2 ¿Existe detección o corrección de inversión?

**NO.** No existe ningún código que:
- Detecte que el orden real de columnas difiere de `ULTIMAS_COLS`
- Corrija columnas intercambiadas
- Detecte inversión de signo (columna "Ganancia" con valores de pérdida)

### 3.3 Evidencia cuantitativa

| Fuente | Documentos | % |
|--------|-----------|---|
| `tools/layout_audit.py` — compatibles | 58 | 31% |
| `tools/layout_audit.py` — incompatibles | 77 | **41%** |
| `tools/layout_audit.py` — parciales | 27 | 15% |
| `tools/layout_audit.py` — sin detección | 24 | 13% |
| **Total documentos** | **186** | **100%** |

**77 documentos (41%) tienen un orden de columnas incompatible** con `ULTIMAS_COLS`. El layout audit los detecta pero **no los corrige**.

### 3.4 Excel: cero detección de columnas

`app_validacion.py:355-380` (`parsear_excel()`): Todas las filas Excel se marcan con `origen_columna=DESCONOCIDO`. No hay detección de columnas para archivos Excel.

### 3.5 Impacto

`app_validacion.py:204-227` y `309-348`: La app usa `origen_columna` para **desambiguar cuentas** (e.g., `arriendos` en columna Ganancia → ingreso; en columna Pérdida → gasto). Si el orden de columnas está invertido, la desambiguación **asigna la naturaleza opuesta**.

### 3.6 Conclusión

**No existe sistema de detección ni corrección de inversión de columnas.** El layout audit es solo lectura. 41% de documentos tienen orden incompatible.

---

## 4. Estado de Contaminación

### 4.1 Contaminación medida

| Métrica | Valor |
|---------|-------|
| Contaminación promedio por documento | **17.2%** |
| Documentos OCR | 74 (39.8%) |
| Confianza parser promedio (OCR) | 0.569 |
| Confianza parser promedio (texto nativo) | 0.625 |
| Rechazos por `ocr_low_confidence` | **1,548** (causa #1) |
| Rechazos por `name_too_many_digits` | 827 (#2) |
| Rechazos por `name_too_many_symbols` | 598 (#4) |

### 4.2 Documentos con contaminación > 50%

| Documento | Contaminación |
|-----------|--------------|
| balance cm 2016 | **64.5%** |
| cm 2015 | **61.8%** |
| Xpovin | **59.8%** |
| cm 2017 | **54.5%** |
| Chillan.xlsx | **44.4%** |

### 4.3 Entradas `__EXCLUIR__` en diccionario (basura OCR que llegó a producción)

| Cuenta original | Detalle |
|----------------|---------|
| `Intereses Créditos Bancarios 54,399,278 10] 54,399,278 0 : 0 o 54,399,278 [0]` | OCR garbage con montos embebidos, brackets, pipes, colons |
| `Ejercicio Local 2022 Página:` | Artefacto de encabezado de página |
| `Al 31 de diciembre del` | Fragmento de fecha |

### 4.4 Sistemas de detección existentes

| Sistema | Capa | Propósito |
|---------|------|-----------|
| `tools/layout_audit.py` | Línea | Mide contaminación por documento |
| `parser_quality/gatekeeper.py` | Candidato | Rechaza candidatos contaminados (30,022 evaluados) |
| `quality_monitoring/` | Pipeline | Monitorea cobertura y drift |
| `explainability/enums.py` | Traza | `D102 = "OCR Reject"` como categoría de error |

### 4.5 Conclusión

Contaminación moderada (17.2%) pero significativa. Monitoreada pero **no corregida automáticamente**. 1,548 rechazos por OCR indican que el parser podría capturar más cuentas con mejor limpieza.

---

## 5. Estado del Diccionario

### 5.1 Inventario

| Archivo | Entradas | Códigos únicos | Fuentes | Estado |
|---------|:--------:|:--------------:|:-------:|--------|
| **`diccionario.json`** | **826** | **49** | **9** | **CANÓNICO** |
| `diccionario_actualizado.json` | 781 | 49 | 8 | Snapshot (stale) |
| `diccionario_optimizado.json` | 712 | 46 | 6 | Stale |
| `catalogo_maestro.json` | 52 códigos × 10 sub-entradas | — | — | Taxonomía de referencia |

### 5.2 Migración

**Completa.** Todo código productivo ya usa `diccionario.json`:

| Consumidor | Archivo usado |
|------------|--------------|
| `pipeline/homologation_pipeline.py:42` | `diccionario.json` |
| `src/db_repository.py:70` | `diccionario.json` |
| `app_validacion.py` | `diccionario.json` |
| `cargar_datos.py:51` | `diccionario.json` |
| `evaluation/homologation_benchmark.py:17` | `diccionario.json` |

### 5.3 Calidad

| Indicador | Valor |
|-----------|-------|
| Conflictos cross-file (mismo nombre, distinto código) | **0** |
| Duplicados exactos | **0** |
| Códigos inválidos | **0** |
| Entradas vacías | **0** |
| Pares duplicados fuzzy (solo acentos/mayúsculas) | 25 — **todos mismo código, 0 impacto funcional** |
| Conflictos internos (misma normalización, código diferente) | **2** — preexistentes, no bloqueantes |
| Entradas `__EXCLUIR__` | 3 — correctamente filtradas por pipeline |

### 5.4 Cobertura potencial no explotada

`diccionario.json` tiene 114 entradas que NO están en `diccionario_optimizado.json` (el que usaba el pipeline antes de la migración). Estimar **+6–10% de cobertura adicional** ya disponible pero quizás no reflejada en benchmarks anteriores.

### 5.5 Conclusión

**Diccionario en buen estado.** Migración completa. Sin conflictos bloqueantes. 826 entradas, 49 códigos únicos, 9 fuentes.

---

## Resumen Ejecutivo

| Área | Estado | Prioridad |
|------|--------|-----------|
| Fase 1A | **✗ INCOMPLETA** — 6 orphan files, 2 entry points | ALTA |
| Filtro líneas basura | **✗ MÍNIMO** — solo 2 filtros (longitud), sin regex de patrones | ALTA |
| Inversión de columnas | **✗ INEXISTENTE** — 41% documentos incompatibles, sin detección ni corrección | ALTA |
| Contaminación | **⚠ MONITOREADA** — 17.2% promedio, 1,548 rechazos OCR, no corregida automáticamente | MEDIA |
| Diccionario | **✓ COMPLETO** — 826 entradas, migración hecha, 0 conflictos | BAJA |
