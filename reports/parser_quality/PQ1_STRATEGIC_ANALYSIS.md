# PQ-1 — ANÁLISIS ESTRATÉGICO DEL BASELINE PQ-0

**Fecha:** 2026-08-06
**Baseline congelado:** `reports/parser_quality/baselines/PQ0/` (commit `dca0655…`)
**Propósito:** decidir —con datos, no opiniones— el objetivo único del próximo sprint de mejora del parser (PQ-1).
**Fuente exclusiva:** archivos congelados `PARSER_BASELINE.md`, `parser_quality_report.md`, `parser_quality_pareto.md`, `baselines/PQ0/PQ0_dataset.csv`, `baselines/PQ0/PQ0_findings.csv`, `HISTORY.md`. No se ejecutó ninguna auditoría nueva ni se modificó ningún archivo.

---

## FASE 1 — PANORAMA GENERAL

| Métrica | Valor |
|---|---|
| Número total de PDFs | **608** |
| PDFs válidos | **594** (14 con error: `No /Root object!`, PDFs corruptos en `REJECTED`) |
| PDFs corruptos | **14** |
| PDFs vía OCR | **251 (41%)** | 357 por texto nativo |
| Tiempo promedio | **28.9 s** |
| Tiempo mediana | **12.1 s** |
| Tiempo total | **17 177.5 s (~4.8 h)** |
| Cuentas extraídas | **158 251** |
| Cuentas con código | **14 134 (8.9 %)** — 144 117 sin código |
| Cuentas con monto | **67 602 (42.7 %)** — 90 649 sin monto |
| Cobertura combinada | **25.8 %** |
| Total de hallazgos | **24 819** |

Observación crítica: **la cobertura de código (8.9 %) es la métrica más débil del sistema.** El 91.1 % de las cuentas no tiene código, lo que obliga a la homologación a depender casi exclusivamente del nombre.

---

## FASE 2 — PARETO REAL

Fuente: `PQ0_findings.csv` (conteos) + `PQ0_dataset.csv` (columnas `n_<tipo>` por PDF, para PDFs afectados y promedio por PDF).

| Ranking | Problema | Cantidad | % | Pareto acumulado | PDFs afectados | Promedio/PDF |
|---|---|---|---|---|---|---|
| 1 | SIMBOLO_RESIDUAL | 16 542 | 66.7 % | 66.7 % | 428 | 38.6 |
| 2 | TOTAL_MAL_INTERPRETADO | 3 578 | 14.4 % | 81.1 % | 487 | 7.3 |
| 3 | CODIGO_PERDIDO | 2 755 | 11.1 % | 92.2 % | 45 | 61.2 |
| 4 | HEADER_GHOST | 1 381 | 5.6 % | 97.7 % | 328 | 4.2 |
| 5 | MONTO_PARTIDO | 546 | 2.2 % | 99.9 % | 52 | 10.5 |
| 6 | CUENTA_FUSIONADA | 12 | 0.05 % | 100.0 % | 11 | 1.1 |
| 7 | FORMATO_MAL_DETECTADO | 5 | 0.02 % | 100.0 % | 5 | 1.0 |

- **Top 5** cubre **99.93 %** del Pareto.
- **Top 4** cubre **97.73 %** del Pareto.
- **Top 3** cubre **92.17 %** del Pareto.
- **Top 1 (SIMBOLO_RESIDUAL) solo** cubre **66.65 %** del total de hallazgos.
- Para superar el umbral del 95 % basta con **4 tipos** (top 4).

Lectura clave:
- **Uno solo (SIMBOLO_RESIDUAL) = 66.7 %** del ruido total, y está presente en **428 de 608 PDFs (70 % del corpus)**.
- **CODIGO_PERDIDO** es el problema más **concentrado**: solo 45 PDFs, pero **61.2 hallazgos por PDF** (un bug masivo pero limitado, tipificado como códigos pegados al nombre — p.ej. `1101-51 CAVA O BANCO…`).
- **TOTAL_MAL_INTERPRETADO** es el más **extendido** (487 PDFs, 80 %) pero con baja densidad (7.3/PDF) y alto ruido.

---

## FASE 3 — CLASIFICACIÓN DE PROBLEMAS

Categorías: A Extracción · B Interpretación · C Clasificación · D OCR · E Layout · F Parser · G Normalización · H Ruido.

| Problema | Categoría principal | Justificación (basada en muestras reales de `PQ0_findings.csv`) |
|---|---|---|
| SIMBOLO_RESIDUAL | **G) Normalización** (con borde en A) | Composición verificada: 52.6 % de nombres contienen `$`/`%` residuales (`M$`, `…(35%)`, OCR `REMUNERACIONESPOR…970.6050%4`); **34.2 %** son nombres **truncados en un paréntesis abierto** (`Obligaciones… corto plazo (b`). Solo 1.4 % son sufijos normativos reales (`(neto)`, `(menos)`). Es un problema de limpieza/normalización del **campo nombre**, con un componente de truncamiento que ya toca extracción. No pierde código ni monto. |
| TOTAL_MAL_INTERPRETADO | **B** Interpretación | Detecta si una línea es `total` (`es_total`). Muestras: `SUMAS SALDOS INVENTARIO RESULTADOS`, `TOTAL Página` (real) conviven con falsos positivos por la palabra "sumas" en nombres legítimos (`Utilidades retenidas (sumas códigos 5.24.51…)`). El detector mezcla real + ruido. Impacta el conteo de totales. |
| CODIGO_PERDIDO | **A** Extracción / **F** Parser | Códigos presentes en la línea cruda pero `codigo=None`; causa típica = **código concatenado a nombre** (`1101-51 CAVA O BANCO 5.719.311…`), muchas en PDFs con OCR dañado. Es la causa directa de la baja cobertura de código. |
| HEADER_GHOST | **F** Parser / **E** Layout | Cabeceras convertidas en cuentas (`Giro : SOCIEDAD INVERSIONES`, `Balance Clasificado`, `PATRIMONIO M$ M$`, `BALANCE GENERAL`). Detección limpia; poco ruido. Fuera del flujo de extracción de cifras. |
| MONTO_PARTIDO | **A** Extracción / D OCR | Montos fragmentados en una sola línea (`6 .335.323`, `3 .349.958`); casi todo en texto (543/546), asociado a formato de número con separador de mil mal leído. |
| CUENTA_FUSIONADA | **A** Extracción | Dos códigos en la misma línea cruda (línea de sub-total que junta dos cuentas). Muy raro (12). |
| FORMATO_MAL_DETECTADO | **F** Parser | El detector de formato de código (`guion/punto/compacto`) concluye que el formato declarado no coincide con lo observado en la mayoría de líneas. Rarísimo (5). |

---

## FASE 4 — RIESGO

Escala de calificación final: MUY BAJO · BAJO · MEDIO · ALTO · CRÍTICO. (Impacto sobre clasificación = daño real a la homologación; sobre benchmark = hallazgos que caen en los archivos del benchmark congelado; ver Anexo B.)

| Problema | Impacto clasificación | Impacto benchmark¹ | Riesgo regresión | Complejidad | Dependencias | Riesgo introducir errores | Calificación |
|---|---|---|---|---|---|---|---|
| SIMBOLO_RESIDUAL | **Alto** (nombres sucios degradan el matching de concepto (homologación)) | **Alto** (948 hallazgos en los 20 archivos del benchmark) | MEDIO | MEDIA | Detector a recalibrar | MEDIO (si se reescribe nombre) | **ALTO** (por volumen; riesgo controlable normalizando solo el nombre) |
| TOTAL_MAL_INTERPRETADO | MEDIO (totales que entran como cuentas contaminen la clasificación) | MEDIO (225 en benchmark) | MEDIO | MEDIA | Detector ruidoso | MEDIO | MEDIO |
| CODIGO_PERDIDO | **Alto** (sin código la homologación es por nombre) | **Alto** (189 en benchmark; VFC/H en HOLDOUT/validación) | ALTO | ALTA (OCR/concatendación) | Depende de calidad OCR + parsing | ALTO | **ALTO** |
| HEADER_GHOST | BAJO (pocas cuentas falsas) | BAJO (84) | BAJO | BAJA | Detector estable | BAJO | BAJO |
| MONTO_PARTIDO | BAJO | BAJO (18) | BAJO | MEDIA | Formato numérico | BAJO | BAJO |
| CUENTA_FUSIONADA | MUY BAJO | MUY BAJO (3) | BAJO | ALTA | — | MEDIO | BAJO |
| FORMATO_MAL_DETECTADO | MUY BAJO | MUY BAJO (3) | BAJO | MEDIA | — | BAJO | MUY BAJO |

¹ Ver Anexo: **1470 hallazgos** provienen de los 20 archivos del benchmark congelado. El tipo más expuesto es SIMBOLO_RESIDUAL (948), luego TOTAL_MAL (225), CODIGO_PERDIDO (189), HEADER_GHOST (84).
² En la práctica la homologación usa el nombre cuando no hay código; nombre con `$`/`(b…` condiciona el matching exacto.

---

## FASE 5 — ESFUERZO vs IMPACTO

| Problema | Esfuerzo¹ | Impacto² | Justificación |
|---|---|---|---|
| SIMBOLO_RESIDUAL | **M** | **Muy alto** (abarca 66.7 % del Pareto en 70 % de los PDFs) | Normalización de nombre + recalibrar detector. |
| CODIGO_PERDIDO | **XL** (OCR + families distintas) | **Medio** (11.1 %, 45 PDFs, pero sube cobertura) | Gran densidad pero pocos PDFs y difícil genericidad. |
| TOTAL_MAL_INTERPRETADO | **M** | **Medio** (14.4 %; muy ruidoso) | El detector genera ruido propio. |
| HEADER_GHOST | **S** | **Bajo-Medio** (5.6 %) | Esfuerzo bajo, impacto moderado. |
| MONTO_PARTIDO | **M** | **Bajo** | Poco volumen (546). |
| CUENTA_FUSIONADA | **L** | **Muy bajo** | 12 hallazgos. |
| FORMATO_MAL_DETECTADO | **S** | **Muy bajo** (5) | Ligeramente. |

¹ Esfuerzo: XS, S, M, L, XL. ² Impacto: Muy alto, Alto, Medio, Bajo, Muy bajo.

---

## FASE 6 — PRIORIZACIÓN

| Prioridad | Problema | Impacto | Esfuerzo | Riesgo | Ganancia esperada |
|---|---|---|---|---|---|
| **1** | **SIMBOLO_RESIDUAL** | Muy alto | M | ALTO (benchmark) | −66.7 % hallazgos (24 819 → ~8.3 k); nombres limpios → mejora homologación; 70 % corpus |
| 2 | CODIGO_PERDIDO | Alto (cobertura) | L | ALTO | −11.1 %; sube cobertura de código (8.9 %), pero solo 45 PDFs |
| 3 | TOTAL_MAL_INTERPRETADO | Medio | M | MEDIO | −14.4 %; mejora conteo de totales; detector a corregir |
| 4 | HEADER_GHOST | Bajo-Medio | S | BAJO | −5.6 %; pocas cuentas falsas |
| 5-7 | MONTO/FUSION/FORMATO | Bajo–Muy bajo | S–L | BAJO | <2.3 % combinado; pago bajo |

---

## FASE 7 — RECOMENDACIÓN (ÚNICO OBJETIVO)

> **PQ-1 debe enfocarse exclusivamente en SIMBOLO_RESIDUAL (Normalización del nombre de cuenta).**

**¿Por qué?**
1. Es **66.65 % del Pareto** (16 542 de 24 819) — el mayor lever único disponible; resolverlo reduce los hallazgos totales a ~8 277 (−66.7 %) en un solo sprint.
2. Afecta a **428/608 PDFs (70 % del corpus)** — la remediación más amplia salvo TOTAL_MAL, y con **4.6× más** volumen.
3. Causa identificable y depurable en datos (52.6 % símbolos `$`/`%`; 34.2 % nombres truncados en paréntesis), **sin tocar la extracción de código ni de monto** — el cambio se limita al **campo nombre**.
4. Nombres limpios impactan directamente el objetivo del proyecto (homologación/clasificación por nombre, crítica porque la cobertura de código es solo 8.9 %).

**¿Qué porcentaje del Pareto elimina?** Hasta **66.7 %** (u ≥ 55–60% si se calibra el detector en paralelo). Precisa que el detector `SIMBOLO_RESIDUAL` se recalibre para que el conteo refleje suciedad real y no sufijos legítimos (1.4 %).

**¿Por qué no CODIGO_PERDIDO (el del mayor impacto en cobertura )?**
- CODIGO_PERDIDO=11.1 % de hallazgos y solo **45 PDFs (7 % corpus)**; SIMBOLO_RESIDUAL asciende a 66.7 % en 428 PDFs.
- CODIGO depende de **OCR/familia** (complejidad ALTA, riesgo de regresión ALTO) y toca archivos **VFCH/CASA** dentro del benchmark congelado (mayor riesgo de romperlo).
- SIMBOLO es **normalización pura del nombre** (no altera la extracción de código ni de montos), por lo que el riesgo de romper el benchmark es la de MENOR entre los big three (aunque expuesto por volumen: 948 hallazgos).

**¿Qué riesgo tiene?** Riesgo ALTO por exposición al benchmark (948 hallazgos en los 20 archivos), mitigado si la normalización **conserva código y monto intactos** y solo limpia el nombre — y se valida con el benchmark.

**Módulos que toca (limitado):**
- Capa de **normalización del nombre** en el parser (resultado de extracción).
- Detector `SIMBOLO_RESIDUAL` del auditor (precisión).

**Módulos que NO toca:** parsing de código/monto, detección de layout, OCR, extracción de columnas, homologación, Runtime, Learning, benchmark.

**Mejora esperada:** hallazgos 24 819 → ≤ 8 300; nombres limpios; **cobertura de código y monto sin regresión** (≥8.9 %, ≥42.7 %); métricas de clasificación por nombre mejoran (a validar con benchmark).

---

## FASE 8 — PLAN DEL SPRINT PQ-1

**Objetivo:** normalizar el campo nombre de la extracción para eliminar símbolos residuales y el truncamiento en paréntesis, sin variar código ni monto, ni romper el benchmark.

**Archivos que probablemente cambiarán**
- Capa que produce el nombre de la `CuentaRaw` (normalización de nombre) — probablemente dentro del flujo de extracción/procesador de línea.
- Auditor: patrón `SIMBOLO_RESIDUAL` (recalibrar para separar suciedad real de sufijos legítimos).
- Documentos del sprint (este análisis + actualizar `HISTORY.md` con PQ-1).

**Archivos protegidos (no se tocan en análisis/medición; solo si lo autoriza el plan de mejora y con approval)**
- `gold_standard/runtime_manager.py` (Runtime), `learning/*`, `benchmark/*` (manifest y resultados congelados), conjuntos gold.
- En este sprint NO se tocan: parsing de código, detección de layout, columnas, OCR.

**Pruebas necesarias**
- Unidad: normalizador de nombre sobre casos reales de `PQ0_findings.csv` (`M$`, `$`, `35%)`, nombre truncado en `(`).
- Regresión: `tests/test_parser_quality_tools.py` + `tests/test_freeze_pq0.py` (18 tests) seguir verde.
- Auditoría completa con `--resume` y freeze del baseline.
- `compare` + `gate` contra baseline PQ-0.

**Cómo validar**
1. Auditoriar PQ-1 sobre el mismo corpus 608.
2. `parser_quality_compare.py --baseline baselines/PQ0 --current reports/parser_quality` → el diff debe mostrar **SIMBOLO_RESIDUAL −(alta)** y ningún otro tipo arriba.
3. `parser_quality_gate.py --baseline baselines/PQ0` → **PASS**.

**Métricas que DEBEN mejorar**
- SIMBOLO_RESIDUAL: 16 542 → objetivo ≤ 3 300 (−80 %).
- Hallazgos totales: 24 819 → ≤ 9 928 (−60 %).
- (Opcional) precisión del detector SIMBOLO (reducción de falso positive).

**Métricas que NO pueden empeorar**
- Cobertura de código (≥8.9 %) y de monto (≥42.7 %).
- Ningún otro tipo de hallazgo aumenta.
- Benchmark: sin regresión (no menos válida la precisión de homología).

---

## FASE 9 — CRITERIOS DE ACEPTACIÓN (aprobado == todo lo siguiente)

- ✓ **Benchmark sin regresión** — re-ejecutado: precisión de extracción/homologación del benchmark congelado no menor que PQ-0. *Nota gerencial: si los 20 archivos mejoran (nombre limpio), el fichero `benchmark_results.csv` cambiará; se congela de nuevo SOLO tras aprobación y nunca si regresara.*
- ✓ **Cobertura** ≥ PQ-0: código ≥ 8.9 %, monto ≥ 42.7 %, combinada ≥ 25.8 %.
- ✓ **SIMBOLO_RESIDUAL disminuye al menos 80 %** (≤ 3 308).
- ✓ **Hallazgos totales disminuyen al menos 60 %** (≤ 9 928), sin que ningún otro tipo aumente.
- ✓ Sin nuevas regresiones por archivo; sin nuevos PDFs con errores críticos.
- ✓ **Compare PASS** (diff: SIMBOLO baja, resto plano/mejora).
- ✓ **Gate PASS.**
- ✓ Tests (18) pasan.
- ✓ Hash de ficheros protegidos (extractores, Learning, Runtime, gold) sin cambios no autorizados.

---

## ANEXO — Exposición del benchmark congelado (fuente: `benchmark/dataset_manifest.csv` = 20 archivos)

Hallazgos totales en los 20 archivos del benchmark: **1470** (de 24 819), concentrado en 4 tipos.

| Tipo | En benchmark |
|---|---|
| SIMBOLO_RESIDUAL | 948 |
| TOTAL_MAL_INTERPRETADO | 225 |
| CODIGO_PERDIDO | 189 |
| HEADER_GHOST | 84 |
| MONTO_PARTIDO | 18 |
| CUENTA_FUSIONADA | 3 |
| FORMATO_MAL_DETECTADO | 3 |

Implicación: **ningún fix de parser puede pretender dejar `benchmark_results.csv` byte-igual**, porque los 20 archivos tienen hallazgos reales que mejorarían. Por eso el criterio correcto es "sin regresión" + re-congelado aprobado, no igualdad de hash literal.

---

## DECISIÓN EJECUTIVA

> **PQ-1 debe enfocarse exclusivamente en normalizar el NOMBRE de las cuentas para eliminar símbolos residuales y el truncamiento en paréntesis (problema SIMBOLO_RESIDUAL).**

Es la mejor inversión porque: (1) es el **mayor bloque del Pareto (66.7 %) con el alcance más amplio (70 % del corpus)**, (2) ataca la causa en un campo **continuamente relevante y de menor riesgo** (nombre, no código/monto/OCR), (3) mejora la **homologación** — el objetivo de fondo, dado que la cobertura de código es solo **8.9 %** —, y (4) deja en próximos sprints los problemas concentrados y técnicamente caros (CODIGO_PERDIDO / OCR) ya con un corpus con métricas y PDFs limpios. Queda descartada toda implementación en esta fase: no se corrigió nada; este documento solo define el objetivo del próximo sprint.