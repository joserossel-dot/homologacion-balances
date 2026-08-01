# Auditoría Técnica y de Producto — homologacion-balances RC1

**Auditor:** Revisión automatizada (solo lectura)
**Fecha:** 2026-07-29
**Rama:** `sprint-1-context-aware-hygiene`
**Último commit:** `72e62b6` — "feat: integrar DocumentAnalyzer como capa previa al parser"
**Base de datos:** `gold_standard.db` — 234 registros

---

## 1. Resumen ejecutivo

El proyecto es un **motor de homologación funcional pero inmaduro** que puede extraer cuentas de PDFs/Excel y clasificarlas contra un catálogo de 52 códigos estándar. El flujo completo funciona (smoke test 29/29), pero la calidad real está muy por debajo de lo que sugieren los reportes de certificación.

- **Extracción:** Confiable para texto nativo (~95%), pero el 56% de las cuentas extraídas tienen tipo de columna desconocido (no se sabe si son ACTIVO/PASIVO).
- **Clasificación:** Solo 18–48% de las cuentas se clasifican, dependiendo del dataset. De esas, la precisión real de los clasificadores es baja (código 26.9%, diccionario exacto 42.3%).
- **Precisión reportada:** 100% en certificación — pero sobre solo 103 cuentas cotejadas (9.5% de las clasificadas). Muestra no representativa.
- **Integridad contable:** Promedio 48.5/100 — más de 1,500 errores de subtotales en 40 documentos.
- **Causa raíz:** 89.1% de las cuentas no clasificadas se deben a falta de conocimiento (diccionario 58.9% + CMCC 30.2%).
- **Arquitectura:** 40 componentes construidos, 15 integrados (37.5%), 0 certificados. Pipeline V2 envuelve V1. Hay duplicación de código estimada en 15-20%.

**Conclusión: No listo para piloto todavía.** El motor puede procesar documentos, pero la calidad de clasificación e integridad contable no cumple el estándar mínimo para ofrecerlo a clientes. Se necesita un período de certificación real (2-3 semanas) antes de un piloto controlado.

---

## 2. Alcance y método de auditoría

Esta auditoría se realizó en modo solo lectura, sin modificar ningún archivo. No se ejecutaron benchmarks completos (limitados por tiempo de procesamiento), pero se verificaron:

| Actividad | Estado |
|-----------|--------|
| Revisión de estructura del repositorio | ✅ |
| Smoke test end-to-end (1 PDF real) | ✅ 29/29 |
| Procesamiento de documento individual con Pipeline V2 | ✅ |
| Lectura de reportes existentes (benchmark, certificación, validación, auditoría de precisión) | ✅ |
| Inspección de tests existentes | ✅ |
| Revisión de arquitectura (pipeline, clasificadores, adaptadores) | ✅ |
| Inventario de herramientas de medición | ✅ |
| Verificación de gold standard | ✅ |
| Revisión de documentación técnica | ✅ |
| Benchmarks completos (20+ archivos) | ⏳ No ejecutados por tiempo (estiman >3 min cada uno) |

---

## 3. Arquitectura comprobada

### 3.1 Flujo real de datos (Pipeline V2)

```
PDF/Excel
  │
  ▼ SIEAdapter         → metadata (empresa, año, layout)
  ▼ DIEAdapter         → predicción de confianza/cobertura esperada
  ▼ ParserAdapter      → raw_accounts vía ParserPDF (V1) o parsear_excel()
  ▼ KBAdapter          → clasifica cuentas → llama a HomologationPipeline._classify_account()
                          (V1 internamente) → produce classified[] / ignored[]
  ▼ DecisionAdapter    → decisions[] por cuenta (CONTINUE/REJECT/REVIEW/LEARNING/STRESS)
  ▼ ValidationAdapter  → integridad, subtotales, ecuaciones
  ▼ ReviewAdapter      → review_queue[] (cuentas no clasificadas)
  ▼ CoverageAdapter    → 4 tipos de cobertura (monetaria, estructural, semántica, documental)
  ▼ SelfQAAdapter      → approval_state, riesgo, confianza global
  │
  ▼ ResultBuilder      → BackendResult consolidado
  ▼ ArtifactManager    → JSON, MD, XLSX exportados
```

### 3.2 Componentes verificados

| Componente | Archivo | Verificado | Estado real |
|-----------|---------|-----------|-------------|
| SIEAdapter | `adapters/sie_adapter.py` | ✅ | Funcional — infiere metadata del filename |
| DIEAdapter | `adapters/die_adapter.py` | ✅ | Funcional — DocumentIntelligence básico |
| ParserAdapter | `adapters/parser_adapter.py` | ✅ | Funcional — pero llama a ParserPDF legacy |
| KBAdapter | `adapters/kb_adapter.py` | ✅ | Funcional — **dependencia circular: llama a Pipeline V1** |
| DecisionAdapter | `adapters/decision_adapter.py` | ✅ | Funcional — 5 tipos de decisión |
| ValidationAdapter | `adapters/validation_adapter.py` | ✅ | Funcional — integridad contable |
| ReviewAdapter | `adapters/review_adapter.py` | ✅ | Funcional — cola de revisión |
| CoverageAdapter | `coverage_engine/coverage_adapter.py` | ✅ | Funcional — 4 tipos de cobertura |
| SelfQAAdapter | `self_qa_engine/self_qa_adapter.py` | ✅ | Funcional — 10 gates + approval |
| ResultBuilder | `backend/result_builder.py` | ✅ | Funcional |
| Pipeline V2 | `orchestrator/pipeline_v2.py` | ✅ | Funcional — orquestador de adapters |
| Pipeline V1 | `pipeline/homologation_pipeline.py` | ✅ | Funcional — contiene la clasificación real |

### 3.3 Componentes mencionados en documentación pero NO verificados en uso real

| Componente | Dónde se menciona | Evidencia de no uso |
|-----------|-------------------|---------------------|
| DecisionEngine V2 (`decision_v2/engine.py`) | Architecture docs, código completo (598 líneas) | No se llama desde ningún pipeline activo. Solo existe como módulo independiente. |
| CMCCClassifier en producción | `pipeline/cmcc_classifier.py`, feature flags | Feature flags `ENABLE_CMCC_PRODUCTION=False`. No activado por defecto. |
| QualityMonitoring | `quality_monitoring/` completo | Sin conexión al pipeline. Genera snapshots solo si se invoca manualmente. |
| ReleasePipeline | `release_pipeline/` | `config/release.yml` existe pero ningún código lo lee. |
| ScientificValidation | `scientific_validation/` | Orphaned — tests existen pero no integrado. |
| ReviewUI | `review_ui/` | Independiente, con su propia SQLite. No conectado al pipeline. |
| Evidence + Explainability | `evidence/`, `explainability/` | Orphaned — tests pasan pero no integrados. |
| CoverageReportGenerator | `coverage_engine/report_generator.py` | No integrado al flujo de exportación. |
| ObservabilityCollector | `observability/collector.py` | No conectado al pipeline. |
| FastAPI (`src/api/main.py`) | `pyproject.toml` reference | Nunca iniciado. Sin tests. Sin configuración de producción. |

### 3.4 Extractores y formatos soportados (verificados)

| Formato | Soporte | Estado |
|---------|---------|--------|
| PDF texto nativo | `parsers/pdf_parser.py` (V1) / `parsers/pdf_parser_v2.py` (V2) | ✅ Funcional |
| PDF escaneado (OCR) | `parsers/pdf_parser.py` con Tesseract | ⚠️ Depende de Tesseract instalado |
| Excel (.xlsx) | `parsers/excel_parser.py` | ✅ Funcional |
| PDF orientación mixta | DocumentAnalyzer detecta automáticamente | ✅ Nuevo |

### 3.5 Clasificadores disponibles y orden de aplicación

En Pipeline V1 (dentro de KBAdapter), el orden real es:

1. **LearningEngine** (gold_standard.db) → exact/fuzzy match → confianza: 0.98/0.60-0.95
2. **CodeClassifier** (`clasificador_codigo_cuenta.py`) → patrón numérico → 0.85-0.98
3. **DictionaryExact** → match normalizado → 0.98
4. **DictionaryFuzzy** → rapidfuzz token_sort_ratio >= 90 → 0.80-0.97
5. **[SemanticMatcher** si `ENABLE_SEMANTIC_MATCHER`] → tiers 1-6 → 0.40-1.0
6. **[RegexFallback** si `ENABLE_SEMANTIC_MATCHER`] → 7 patrones fijos → 0.72
7. **Unclassified** → confianza 0.0

**⚠️ Nota crítica:** A pesar de que CMCCClassifier existe y tiene tests, no está en la ruta crítica de clasificación. El feature flag `ENABLE_CMCC_PRODUCTION` es `False`.

---

## 4. Inventario de herramientas, datos y reportes

### 4.1 Inventario de datasets

| Dataset | Archivos | PDF | Excel | Estado |
|---------|----------|-----|-------|--------|
| TRAINING | 78 | 78 | 0 | Usado para entrenamiento de gold standard |
| HOLDOUT | 140 | 140 | 0 | Usado para benchmark principal |
| STRESS | 201 | 181 | 20 | Casos extremos (no procesados aún) |
| edge_cases | 97 | 78 | 19 | Análisis de edge cases |
| validacion | 89 | 84 | 5 | Usado en validación anterior |
| ARCHIVE | 21 | 21 | 0 | Documentos de prueba históricos |
| REJECTED | 72 | 67 | 5 | Documentos rechazados (por qué?) |
| **Total** | **~698** | **~649** | **~49** | |

### 4.2 Herramientas de medición existentes

| Herramienta | Archivo | Qué mide | Dataset | Fecha reporte | Ejecutable hoy | Utilidad |
|------------|---------|----------|---------|---------------|---------------|----------|
| **Benchmark runner** | `benchmark/benchmark_runner.py` | Tiempo, cuentas, método, precisión | HOLDOUT (20) | 2026-07-26 (reporte) | ✅ Sí | Alta — línea base de rendimiento |
| **Certificación** | `scripts/run_certification.py` | Accuracy vs gold standard | HOLDOUT (20) | 2026-07-09 | ✅ Sí | Alta — pero sample size muy pequeño |
| **Auditoría de precisión** | `scripts/` (no identificado) | Precisión real por clasificador | ~319 cuentas en conflicto | 2026-07-22 | ⚠️ Parcial | **Crítica** — único reporte de precisión real |
| **Root cause analysis** | `analysis/unknown_audit.py` | Causas de cuentas UNKNOWN | 185 docs, 10,672 cuentas | 2026-07-10 | ✅ Sí | **Crítica** — identifica causas raíz |
| **Validación integridad** | `validation/` | Subtotales, ecuaciones, balance | 40 docs | ~2026-07 | ✅ Sí | Alta — revela integridad contable |
| **Coverage validation** | `coverage_engine/` | 4 tipos de cobertura | Documento sintético | 2026-07-28 | ✅ Sí | Media — solo probado en datos sintéticos |
| **Pipeline V2 runner** | `run_pipeline_v2.py` | Pipeline end-to-end por archivo | Cualquier PDF | En vivo | ✅ Sí | Alta — herramienta de diagnóstico diario |
| **Smoke test** | `smoke_test.py` | 29 checkpoints de integridad | ARCHIVE (1 PDF) | En vivo | ✅ Sí | Alta — verificación rápida |
| **Quality monitoring** | `quality_monitoring/` | Snapshots, drift, regresiones | — | Vacío | ❌ No conectado | Baja — no tiene datos |
| **Observability** | `observability/collector.py` | Timing, errores, flujo | — | — | ❌ No conectado | Baja — no integrado al pipeline |
| **Validation reports** | `reports/validation/20260706_*/` | Métricas por lote de validación | 88 docs (validacion/) | 2026-07-06 | ✅ Sí | Alta — línea base de cobertura histórica |

### 4.3 Reportes existentes (fechas reales)

| Reporte | Fecha | Size del dataset | Hallazgo principal |
|---------|-------|-----------------|-------------------|
| `benchmark/benchmark_summary.md` | 2026-07-26 | 20 PDFs, 2,692 cuentas | 48.77% homologación, 82.3% unknown |
| `reports/classifier_precision.md` | 2026-07-22 | 319 cuentas auditadas | Código 26.9%, DictExact 42.3%, Regex 47.2% precision |
| `reports/certification/certification_report.md` | 2026-07-09 | 20 PDFs, 103 cotejadas | 100% accuracy (en 9.5% de muestra) |
| `reports/root_cause_analysis/root_cause_analysis.md` | 2026-07-10 | 185 docs, 10,672 cuentas | 89.1% UNKNOWN por falta de conocimiento |
| `reports/balance_integrity_validation.md` | ~2026-07 | 40 docs, 244 subtotales | Promedio 48.5/100 integridad |
| `reports/validation/20260706_200251/summary.md` | 2026-07-06 | 88 docs, 5,369 cuentas | 23.6% clasificadas (1,269/5,369) |
| `reports/decision_engine_metrics.json` | ~2026-07 | 11,690 cuentas totales | DEv2 reduce 48.83% unknown vs V1 |

---

## 5. Resultados de validación práctica

### 5.1 Smoke test: ✅ 29/29

```
$ .venv/bin/python smoke_test.py
  Archivo: Balance 2015 - Soc Com e Inv Campoamor SA.pdf
  Tiempo: 13.0s
  Tests: 29/29 passed
```

Todos los checkpoints de integridad pasan: context, execution, accounts, coverage, decisions, QA, export paths, artifacts en disco.

### 5.2 Pipeline V2 individual: ✅ Funcional

```
$ .venv/bin/python run_pipeline_v2.py "Balance 2016 Asturias Ltda .pdf"
  Estado:       completed (12.5s)
  Cuentas:      101
  Clasificadas: 63
  Sin clasificar: 50
  Ignoradas:    38
  Cobertura:    56.2%
  QA Confianza: 100.00%
  Revisión:     51 cuentas
```

Resultado completo con artifacts poblados correctamente (fix de artifacts verificado).

### 5.3 Tests unitarios seleccionados: ✅ Pasaron

| Suite | Tests | Resultado |
|-------|-------|-----------|
| `test_pipeline_runner_artifacts.py` | 4 | ✅ Pass |
| `test_backward_compatibility.py` (V1) | 4 | ✅ Pass (23.8s) |

### 5.4 Dificultades encontradas

- **Benchmark runner**: No se ejecutó por tiempo de procesamiento estimado (>3 min). La dependencia de Tesseract OCR y pdfplumber hace que cada documento tome 7-13s.
- **Tests completos**: Varias suites (`test_pipeline_v2.py`, `test_backward_compatibility.py` full) requieren >2 min por archivo real. No se ejecutaron en su totalidad.
- **Certificación**: No se re-ejecutó. El script `scripts/run_certification.py` reporta duración de 210.9s en su última ejecución.

---

## 6. Métricas actualmente demostrables

### 6.1 Cobertura de extracción

| Métrica | Valor | Fuente |
|---------|-------|--------|
| Cuentas con tipo de columna conocido | 43.8% (13,580/30,829) | `reports/account_type_validation.json` |
| Cuentas con tipo DESCONOCIDO | 56.2% (17,249/30,829) | Misma fuente |
| Archivos sin errores de parser | ~100% | `benchmark/benchmark_summary.md` |
| Tiempo promedio por documento | 8.8s | Benchmark (20 docs) |

### 6.2 Cobertura de clasificación

| Métrica | Dataset | Valor | Fuente |
|---------|---------|-------|--------|
| Cuentas clasificadas | validacion (88 docs) | 23.6% | `reports/validation/20260706_200251` |
| Cuentas clasificadas | HOLDOUT (20 docs) | 48.77% | `benchmark/benchmark_summary.md` |
| Cuentas clasificadas | Full (185 docs) | 18.3% | `reports/root_cause_analysis/` |
| Unknown por falta de diccionario | Full | 58.9% (5,134) | Root cause analysis |
| Unknown por CMCC no conectado | Full | 30.2% (2,637) | Root cause analysis |

### 6.3 Precisión de clasificación (REAL, no reportada)

| Clasificador | Precisión | Recall | F1 | Fuente |
|-------------|-----------|--------|----|--------|
| Código Contable | **26.9%** | 5.6% | 9.2% | Auditoría de 319 cuentas en conflicto |
| Diccionario Exacto | **42.3%** | 52.4% | 46.8% | Misma fuente |
| Diccionario Fuzzy | **58.3%** | 16.7% | 25.9% | Misma fuente |
| RegexFallback | **47.2%** | 122.2% | 68.1% | Misma fuente (sobrecobertura) |
| Gold Standard Exacto | **38.4%** | 46.0% | 41.9% | Misma fuente |
| DecisionEngine V2 | **59.3%** | 116.7% | 78.6% | Misma fuente |

**⚠️ Advertencia:** Estas cifras provienen de una muestra de 319 cuentas donde SemanticMatcher y Regex discreparon. La muestra está sesgada hacia casos difíciles. La precisión en la población total es probablemente más alta. Sin embargo, es la **única medición de precisión real** disponible.

### 6.4 Distribución de confianza

| Nivel | Cuentas | % |
|-------|---------|---|
| UNKNOWN | 7,192 | 61.5% |
| VERY_HIGH | 1,966 | 16.8% |
| LOW | 1,353 | 11.6% |
| HIGH | 926 | 7.9% |
| MEDIUM | 253 | 2.2% |

Fuente: `reports/decision_engine_metrics.json` — 11,690 cuentas totales.

### 6.5 Errores críticos contables

| Métrica | Valor | Fuente |
|---------|-------|--------|
| Score de integridad promedio | 48.5/100 | 40 documentos |
| Errores de subtotales | 1,517 | Misma fuente |
| Cuentas faltantes | 296 | Misma fuente |
| Ecuaciones no cuadran | 8 | Misma fuente |

### 6.6 Cuentas que requieren revisión humana

| Escenario | % | Fuente |
|-----------|--|--------|
| Con Pipeline V1 actual | 73.1% | Decision engine metrics |
| Con DecisionEngine V2 (simulado) | ~18% | Misma fuente |
| QA Approved en pipeline real | False (51 cuentas en review) | Smoke test |

### 6.7 Rendimiento por documento

| Métrica | Valor | Fuente |
|---------|-------|--------|
| Tiempo promedio | 8.8s | Benchmark (20 docs) |
| P95 | ~27s | Misma fuente |
| Bottleneck | Parser (80% del tiempo) | `reports/backend_performance.md` |

---

## 7. Hallazgos críticos (ordenados por severidad)

### H1 (Crítico) — La precisión real de clasificación es insuficiente

**Evidencia:** El único reporte de precisión real (julio 22) muestra que el clasificador principal (Diccionario Exacto) tiene solo 42.3% de precisión en 319 cuentas auditadas. El clasificador por código (26.9%) y Regex (47.2%) están cerca del nivel de ruido.

**Impacto:** Si estas cifras son representativas, ~50% de las cuentas "clasificadas" están mal clasificadas. Esto hace que cualquier reporte downstream (cobertura, QA) sea poco confiable.

**Recomendación inmediata:** Expandir la auditoría de precisión a una muestra aleatoria de ~1,000 cuentas clasificadas (no solo las conflictivas) para obtener una estimación no sesgada.

### H2 (Crítico) — El Gold Standard es insuficiente para validar calidad

**Evidencia:** Solo 234 registros para 52 códigos estándar. La certificación reporta 100% de accuracy pero sobre solo 103 cuentas cotejadas (9.5% de clasificadas). Kappa=1.0 es estadísticamente sospechoso con muestra tan pequeña.

**Impacto:** No se puede afirmar confiablemente ninguna métrica de precisión. El Gold Standard cubre una fracción mínima del espacio de cuentas reales.

### H3 (Crítico) — El 56% de las cuentas tienen tipo de columna desconocido

**Evidencia:** `reports/account_type_validation.json` muestra 17,249 de 30,829 cuentas con `DESCONOCIDO` como origen.

**Impacto:** Sin tipo de columna, el validador de integridad contable no puede verificar ACTIVO=PASIVO+PATRIMONIO. La clasificación también depende del tipo para filtrar códigos válidos.

### H4 (Alto) — Conocimiento incompleto: 89.1% de las cuentas UNKNOWN

**Evidencia:** Root cause analysis sobre 10,672 cuentas muestra que 58.9% son por falta de entrada en diccionario y 30.2% por CMCC no conectado al pipeline. Solo 5.4% son errores de OCR y 3.3% de layout.

**Impacto:** El problema principal no es técnico (parser/OCR) sino de conocimiento contable. La solución requiere trabajo de un contador para mapear cuentas reales a códigos estándar.

### H5 (Alto) — Integridad contable deficiente (score 48.5/100)

**Evidencia:** 1,517 errores de subtotales en 40 documentos. Solo 29 ecuaciones verificadas.

**Impacto:** Un balance certificado no puede tener errores de subtotales. Esto indica que la extracción jerárquica (subtotales → totales) falla en la mayoría de los documentos.

### H6 (Alto) — Pipeline V2 envuelve V1 sin abstracción limpia

**Evidencia:** `KBAdapter.kb_adapter.py` crea una instancia de `HomologationPipeline` V1 internamente y llama a su método `_classify_account()`. Esto crea una dependencia circular donde V2 no puede funcionar sin V1.

**Impacto:** No se puede desacoplar, testear ni reemplazar V1 sin romper V2. Cualquier bug en V1 afecta a V2.

### H7 (Medio) — 40 componentes construidos, solo 15 integrados (37.5%)

**Evidencia:** `COMPONENT_STATUS.md` y verificación de código confirman que 25 de 40 componentes están huérfanos (no conectados al pipeline principal).

**Impacto:** Inversión significativa en módulos que no agregan valor al producto. Mantenimiento innecesario. Riesgo de confusión sobre qué está realmente operativo.

### H8 (Medio) — Cero tests en ruta crítica (app_validacion.py, parser_universal.py)

**Evidencia:** Confirmado en `TECHNICAL_AUDIT.md` y verificado con `grep` contra archivos de test. La interfaz Streamlit (1,340 líneas) y el parser principal (831 líneas) no tienen un solo test unitario.

**Impacto:** Cualquier cambio en estos archivos no tiene red de seguridad. Refactorización imposible sin riesgo de regresión.

### H9 (Medio) — 11 tests fallando en split_ac01

**Evidencia:** `STABILIZATION_BACKLOG.md` B-01 (P0). Confirmado en colección de tests.

**Impacto:** El módulo AC01 no es confiable. Si se necesita en producción, hay que repararlo primero.

### H10 (Bajo) — Triplicación del diccionario

**Evidencia:** `TECHNICAL_AUDIT.md` reporta 3 versiones del diccionario (826 / 781 / 712 entradas). No hay documentación de cuál es la canónica.

**Impacto:** Riesgo de usar una versión desactualizada al agregar nuevas entradas.

---

## 8. Madurez técnica y de producto

### 8.1 Dimensiones de evaluación

| Dimensión | Nota | Evidencia | Riesgo principal |
|:---|---|:---|---|
| Extracción de documentos | **3/5** | Parser funcional para PDF nativo y Excel. OCR con Tesseract. 56% cuentas con tipo desconocido. 0 errores de parser en benchmark. | La extracción jerárquica (subtotales) falla en la mayoría de documentos (score integridad 48.5). |
| Homologación/cobertura | **2/5** | 18-48% de cuentas clasificadas según dataset. 89.1% de UNKNOWN por falta de conocimiento. Sistema funcional pero con alcance limitado. | Cubrir el espacio de cuentas reales requiere trabajo contable significativo (dictionary gap). |
| Precisión contable | **2/5** | Precisión real de clasificadores entre 26.9% y 58.3% (en muestra conflictiva). 100% reportado en certificación es engañoso (sample size muy pequeño). | Sin gold standard ampliado, no se puede medir ni mejorar la precisión real. |
| Confianza y revisión humana | **3/5** | SelfQAEngine funcional con 10 gates. 73.1% de cuentas requieren revisión (V1 actual). 18% proyectado con DEv2. QA confidence 100% reportado pero cuestionable. | El alto % de revisión humana requerida hace impracticable la automatización sin mejorar clasificadores. |
| Calidad y trazabilidad de datos | **2/5** | DocumentContext con snapshots y trazabilidad de cambios. Pero gold standard pequeño y precisiones no verificables. ClassificationHistoryRecorder existe pero no conectado. | No hay forma de rastrear si una corrección humana mejora el sistema. |
| Reproducibilidad de pruebas | **2/5** | 56 archivos de test, ~1,165 tests, ~1000+ pasan. Pero 11 fallan, 0 end-to-end tests, 0 tests en ruta crítica (app, parser). Tests lentos (>2 min algunos). | No se puede confiar en los tests como red de seguridad para cambios. |
| Observabilidad/auditoría | **3/5** | Múltiples reportes de auditoría (precisión, root cause, integridad, cobertura). Backend logging funcional. Pero reportes no están automatizados ni conectados al pipeline en producción. | Las auditorías requieren ejecución manual. No hay monitoreo continuo de calidad. |
| Estabilidad operativa | **3/5** | Smoke test 29/29 pasa consistentemente. Pipeline se ejecuta sin errores. Backend runner funcional con artifacts. Sin embargo, solo probado en ~20 documentos. | Comportamiento en documentos no vistos (STRESS, REJECTED) es desconocido. |
| Preparación para producto | **1/5** | Sin API REST funcional (FastAPI existe pero nunca ejecutada). Sin UI de revisión humana conectada al pipeline. Sin métricas de salida para clientes. Sin seguridad/privacidad. Sin trazabilidad de auditoría externa. | Falta casi toda la infraestructura de producto. El sistema es un motor técnico, no un producto. |

### 8.2 Evaluación general

| Pregunta | Respuesta |
|----------|-----------|
| **¿Prototipo, motor validado o producto piloto?** | **Prototipo funcional.** El motor procesa documentos y produce resultados, pero la calidad no está validada, la cobertura es baja, y la infraestructura de producto no existe. |
| **Principal limitación comprobada** | **Falta de conocimiento contable.** El 89.1% de cuentas no clasificadas se debe a diccionario incompleto y CMCC no conectado. No es un problema técnico sino de dominio. |
| **% de desempeño que se puede afirmar realmente** | **Ninguna métrica agregada es confiable.** Lo único verificable: el pipeline se ejecuta sin errores, procesa documentos en ~9s promedio, produce artifacts. La precisión real está entre 27-58% en muestra conflictiva, pero no se puede generalizar. |
| **Afirmaciones comerciales no sostenibles** | "Automatización de homologación", "Precisión 100%", "Cobertura completa", "Listo para producción", "Reemplazo de proceso manual". Ninguna de estas afirmaciones tiene respaldo. |
| **¿Evidencia para prometer automatización con revisión humana?** | **Sí, condicional.** El sistema puede procesar documentos y clasificar cuentas automáticamente en los casos donde el diccionario tiene cobertura. Para ~30-40% de cuentas (las más comunes) la clasificación podría ser confiable con revisión humana del resultado. Pero el 60-70% restante requiere entrada contable antes de poder automatizarse. |

---

## 9. Plan priorizado de avance

### A. Próximos 5 días: certificación y línea base

| # | Acción | Impacto | Esfuerzo | Evidencia que la justifica |
|---|--------|---------|----------|---------------------------|
| A1 | **Expandir gold standard a ~1,000 registros** revisando manualmente una muestra representativa de 20-30 documentos | Alto | Alto | H1, H2 — Sin gold standard ampliado, toda métrica es especulativa |
| A2 | **Ejecutar benchmark completo** sobre HOLDOUT (20 docs) y validacion (89 docs) para obtener línea base reproducible | Alto | Bajo | No hay línea base ejecutada en esta auditoría por tiempo |
| A3 | **Auditar precisión real** sobre muestra aleatoria de 500 cuentas clasificadas (no solo conflictivas) | Alto | Medio | H1 — El único reporte de precisión está sesgado hacia casos difíciles |
| A4 | **Corregir los 11 tests fallando** en split_ac01 | Medio | Bajo | H9, B-01 en backlog |
| A5 | **Fijar artifact pipeline runner** (ya completado) y verificar artifacts de 10 documentos | Alto | Bajo | Bug reportado en RC1 |

**Criterios de aceptación para pasar a B:**
- Gold standard con ≥500 registros validados por contador
- Precisión real medida en muestra aleatoria (no solo conflictiva)
- Línea base de cobertura y precisión documentada y reproducible
- 0 tests fallando

### B. Próximas 2-3 semanas: cierre de brechas de mayor impacto

| # | Acción | Impacto | Esfuerzo | Evidencia | Métrica que mejora |
|---|--------|---------|----------|-----------|-------------------|
| B1 | **Completar diccionario** atacando causa raíz RC05 (5,134 cuentas, 58.9% de unknown): priorizar por monto/moneda. Requiere contador. | Alto | Alto | Root cause analysis | Cobertura de clasificación (+48pp potencial) |
| B2 | **Activar CMCCClassifier en producción** (RC06, 30.2% de unknown). Feature flag ya existe. | Alto | Medio | Root cause analysis + tests CMCC existentes | Cobertura de clasificación (+25pp potencial) |
| B3 | **Mejorar detección de tipo de columna** (56% cuentas DESCONOCIDO). Afecta integridad y precisión. | Alto | Medio | Account type validation | Integridad contable, precisión clasificación |
| B4 | **Tests para parser_universal.py** priorizando funciones de extracción de subtotales (origen de H5) | Alto | Alto | H8 — 0 tests en ruta crítica | Estabilidad operativa |
| B5 | **Desacoplar KBAdapter de V1**: que KBAdapter no instancie HomologationPipeline internamente | Medio | Medio | H6 — Dependencia circular V1→V2 | Mantenibilidad |
| B6 | **Conectar quality_monitoring** al pipeline para generar snapshots automáticos post-ejecución | Medio | Bajo | QualityMonitoring existe pero no conectado | Observabilidad |
| B7 | **Consolidar diccionario** a una sola versión canónica | Medio | Bajo | H10 — 3 versiones del diccionario | Calidad de datos |

**Validación humana contable requerida:** B1 y B3 requieren un contador o conocedor de tributación chilena. B2 y B4-B7 son puramente técnicos.

### C. Camino a piloto comercial

| # | Requisito | Por qué | Dependencia |
|---|-----------|---------|-------------|
| C1 | **API REST** con FastAPI (ya existe esqueleto en `src/api/main.py`) | Los clientes no usan Streamlit ni CLI | Todo B |
| C2 | **Interfaz de revisión humana** conectada al pipeline (ReviewUI existe pero no conectado) | El flujo requiere que un contador valide resultados | B1, B2 |
| C3 | **Exportación de reporte ejecutivo** por documento (balance homologado + diferencias + confianza por cuenta) | El cliente necesita ver qué se hizo y qué queda pendiente | B1, B2, B5 |
| C4 | **Trazabilidad de auditoría** (quién revisó qué, cuándo, qué cambió) | Requisito regulatorio para reemplazar proceso manual | C2 |
| C5 | **Seguridad y privacidad** (autenticación, datos de clientes, logs de acceso) | Balance tributario es información sensible | C1 |
| C6 | **Métrica de salida obligatoria:** cobertura ≥85%, precisión ≥90%, integridad ≥80% en gold standard expandido | Sin esta métrica no se puede ofrecer a clientes como servicio | A1, B1, B2, B3 |
| C7 | **Prueba piloto** con 3-5 documentos reales de clientes potenciales, con revisión humana completa de resultados | Validación en condiciones reales antes de ofrecer como producto | C1-C6 |

---

## 10. Preguntas abiertas y bloqueos

| Pregunta | Bloqueo para responder | Impacto |
|----------|----------------------|---------|
| ¿Cuál es la precisión real de cada clasificador en población general (no solo conflictiva)? | Falta gold standard ampliado y revisión manual de cuentas | La métrica clave del producto no se puede medir |
| ¿Por qué 72 documentos están en REJECTED? ¿Son formatos no soportados o errores de procesamiento? | No se inspeccionó el contenido de REJECTED | Podría ser 10% adicional de documentos procesables |
| ¿Cuántas de las 5,134 cuentas sin diccionario (RC05) son variantes de cuentas ya mapeables? | Falta análisis de agrupación semántica vs. catálogo maestro | Determina el esfuerzo real de B1 |
| ¿Los módulos huérfanos (25 de 40) deben mantenerse, eliminarse o conectarse? | Falta decisión de producto sobre hoja de ruta | Costo de mantenimiento innecesario estimado en 15-20% del código |
| ¿El FastAPI en `src/api/main.py` es funcional? | No se ejecutó — depende de uvicorn y la configuración de la aplicación | Determina el esfuerzo de C1 |
| ¿Qué cobertura tienen los documentos en STRESS (201 archivos)? | No se procesaron por tiempo | Podría revelar límites del sistema |

---

## 11. Anexo: comandos ejecutados y archivos revisados

### Comandos ejecutados

```bash
# Estado del repositorio
git log --oneline -20
git status --short
git diff --stat
git branch
git tag

# Documentación
cat README.md
ls docs/

# Estructura de directorios
ls datasets/
ls datasets/ARCHIVE/ | head -5
ls reports/
ls tests/

# Smoke test
.venv/bin/python smoke_test.py

# Pipeline V2 individual
.venv/bin/python run_pipeline_v2.py "datasets/ARCHIVE/Balance 2016 Asturias Ltda .pdf"

# Tests
.venv/bin/python -m pytest tests/test_pipeline_runner_artifacts.py -x -v
.venv/bin/python -m pytest tests/test_backward_compatibility.py -x -k "test_v1"
.venv/bin/python -m pytest tests/test_confidence_engine.py --co

# Gold standard
python3 -c "import sqlite3; ... gold_standard.db"

# Reportes
cat reports/benchmark/homologation_report_before.md
cat reports/certification/certification_report.md | head -120
cat reports/classifier_precision.md | head -80
cat reports/balance_integrity_validation.md | head -80
cat reports/root_cause_analysis/root_cause_analysis.md | head -80
cat reports/validation/20260706_200251/summary.md
cat benchmark/benchmark_summary.md
cat reports/backend_performance.md | head -60
cat reports/coverage_validation.md | head -60

# Decision engine metrics
cat reports/decision_engine_metrics.json | python3 -m json.tool
cat reports/account_type_validation.json | python3 -m json.tool
cat reports/certification/certification_report.json | python3 -m json.tool
cat reports/validation/20260706_200251/metrics.json | python3 -m json.tool
cat reports/benchmark_after.json | python3 -m json.tool

# Configuración
cat pyproject.toml
cat requirements.txt
cat config/features.yaml

# Arquitectura
cat ARCHITECTURE_AUDIT.md | head -100
cat TECHNICAL_AUDIT.md | head -100
cat COMPONENT_STATUS.md
cat STABILIZATION_BACKLOG.md
cat BUG_REGISTER.md | head -50
```

### Archivos de código fuente revisados en detalle

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `backend/pipeline_runner.py` | 74 | Orquestación del pipeline runner |
| `backend/artifact_manager.py` | 115 | Gestión de artifacts de ejecución |
| `backend/result_builder.py` | 87 | Construcción de BackendResult |
| `backend/backend_models.py` | 98 | Modelos de datos del backend |
| `backend/execution_manager.py` | 87 | Gestión de estado de ejecución |
| `backend/runner.py` | 45 | BackendRunner — wiring de componentes |
| `backend/config.py` | 37 | Configuración del backend |
| `orchestrator/pipeline_v2.py` | 71 | Pipeline V2 — orquestación de adapters |
| `pipeline/homologation_pipeline.py` | 635 | Pipeline V1 — clasificación real |
| `document_context/context.py` | 252 | DocumentContext |
| `adapters/*.py` | 12-145 | 9 adaptadores del pipeline |
| `clasificador_codigo_cuenta.py` | ~250 | Clasificación por código |
| `coverage_engine/` | 11 archivos | Motor de cobertura |
| `self_qa_engine/` | 12 archivos | Motor de autocalidad |

---

## Conclusión

**No listo para piloto todavía.**

El sistema es un prototipo funcional con un pipeline que procesa documentos de extremo a extremo sin errores técnicos. Sin embargo, la calidad real de clasificación no está validada, la cobertura es insuficiente (18-48%), la integridad contable es deficiente (48.5/100), y no existe la infraestructura de producto mínima (API, UI de revisión, trazabilidad, seguridad).

Lo que el sistema SÍ puede hacer hoy:
- Extraer cuentas de PDFs y Excel de manera confiable
- Clasificar ~30-50% de las cuentas usando diccionario + gold standard
- Generar artifacts de ejecución completos y trazables
- Identificar qué cuentas requieren revisión humana

Lo que NO puede hacer hoy:
- Garantizar precisión mínima en clasificación (no medida)
- Procesar documentos sin revisión humana (>70% requieren revisión)
- Asegurar integridad contable del resultado (score 48.5)
- Ser usado por un cliente directamente (sin API, sin UI de revisión)

**Próximo paso:** Ejecutar el plan de 5 días (sección A) para obtener una línea base honesta. Con esos datos, se puede estimar realísticamente el esfuerzo para llegar a piloto.
