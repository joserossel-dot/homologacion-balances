# TECHNICAL AUDIT — Homologación de Balances

> Fecha: 2026-07-26
> Rama activa: `sprint-1-context-aware-hygiene`
> Último commit: `72e62b6` — "feat: integrar DocumentAnalyzer como capa previa al parser"

---

## 1. ARQUITECTURA REAL

### 1.1 Diagrama de flujo real del sistema

```
app_validacion.py (Streamlit UI) ──────── entrada principal
    │
    ├── parser_universal.py (ParserPDF) ── parseo PDF/Excel
    │       └── extracción texto nativo → OCR fallback → lineas
    │       └── detectar_formato_codigo / detectar_separador_miles
    │       └── parsear_linea() → CuentaRaw[]
    │
    ├── MotorHibridoLocal (LEGACY) ────── clasificación local (vía `USE_LEGACY_ENGINE=True`)
    │       └── ClasificadorCodigo (clasificador_codigo_cuenta.py)
    │       └── diccionario exacto/fuzzy (rapidfuzz)
    │       └── REGLAS_REGEX (36 patrones hardcodeados)
    │       └── ProcesadorReglasEspeciales D1-D5 (reglas_especiales.py)
    │
    ├── HomologationPipeline (NUEVO) ───── pipeline completo (vía `USE_LEGACY_ENGINE=False`)
    │       └── pipeline/homologation_pipeline.py
    │           ├── LearningEngine (gold_standard.db)
    │           ├── ClasificadorCodigo
    │           ├── Diccionario exacto/fuzzy
    │           ├── SemanticMatcher (knowledge/concept_catalog.json) [feature-flagged]
    │           ├── SemanticEngine (semantic/semantic_engine.py)
    │           ├── CMCCClassifier (pipeline/cmcc_classifier.py) [feature-flagged]
    │           ├── DecisionEngine (decision/engine.py) [feature-flagged]
    │           ├── RegexFallback (7 patrones auditados)
    │           └── ProcesadorReglasEspeciales D1-D5
    │       └── AccountAdapter (adapters/account_adapter.py)
    │       └── BalanceInterpreter (interpreters/balance_interpreter.py)
    │
    ├── SHADOW_MODE ────────────────────── ejecuta HomologationPipeline en paralelo
    │       └── shadow/shadow_logger.py
    │
    └── GoldBuilder (gold_standard/builder.py)
            └── gold_standard.db (SQLite, 187 registros)
```

### 1.2 Entradas independientes (no conectadas al flujo principal)

```
src/api/main.py (FastAPI)          ─── usa PipelineOrquestador (src/core/orquestador.py)
                                           └── orquestador.py: 46 líneas, stub mínimo
                                           └── solo imprime "Procesando: {ruta}" y retorna status ok

ui/app.py (Streamlit MVP)          ─── usa HomologationPipeline directamente
                                           └── 165 líneas, alternativa minimalista a app_validacion.py
                                           └── no vinculada al main ni visible en producción
```

---

## 2. COMPONENTES EXISTENTES

### 2.1 Núcleo del pipeline (en producción)

| Componente | Archivo | Líneas | Función principal |
|---|---|---|---|
| Streamlit UI | `app_validacion.py` | 1340 | Interfaz de usuario, carga, revisión, exportación |
| Parser PDF | `parser_universal.py` | 831 | Extracción de cuentas desde PDF/Excel |
| Clasificador código | `clasificador_codigo_cuenta.py` | — | Clasifica por código de cuenta |
| Reglas especiales | `reglas_especiales.py` | — | Reglas D1-D5 crediticias |
| HomologationPipeline | `pipeline/homologation_pipeline.py` | 634 | Pipeline completo de clasificación |
| AccountAdapter | `adapters/account_adapter.py` | — | Adaptador CuentaRaw → AccountBalance |
| BalanceInterpreter | `interpreters/balance_interpreter.py` | — | Interpreta montos y naturaleza |
| LearningEngine | `learning/engine.py` | 310 | Gold Standard exact/fuzzy matching |
| Gold Builder | `gold_standard/builder.py` | — | Persiste clasificaciones en SQLite |
| CMCC Classifier | `pipeline/cmcc_classifier.py` | — | Clasificador basado en conceptos |
| Extractor metadata | `extractor_metadata.py` | — | RUT, razón social, periodo |
| Shadow Logger | `shadow/shadow_logger.py` | — | Log comparativo legacy vs pipeline |

### 2.2 Módulos construidos pero NO conectados al flujo principal

| Componente | Archivo(s) | Líneas totales | Estado |
|---|---|---|---|
| DocumentAnalyzer | `parsers/analyzer.py` + `parsers/integration.py` | ~923 | Construido, probado (30 tests), NO integrado en app ni pipeline |
| ParserCore2 | `parsers/pdf_parser.py` | ~430 | Construido, benchmarkeado, NO usado en app/pipeline |
| SemanticEngine | `semantic/semantic_engine.py` | 39 | Importado por pipeline, feature-flagged |
| SemanticMatcher | `semantic/matcher.py` | 135 | Importado por pipeline, feature-flagged (ENABLE_SEMANTIC_MATCHER) |
| SemanticRules | `semantic/semantic_rules.py` | 214 | 10 reglas semánticas, solo usadas por SemanticEngine |
| ConfidenceEngine (v1) | `confidence/confidence_engine.py` | 85 | ORPHANED: solo importado por test |
| ConfidenceEngine (v2) | `confidence/engine.py` | 89 | ORPHANED: solo importado por test y reports/ |
| EvidenceBuilder | `evidence/evidence_builder.py` | ~200 | ORPHANED: solo tests internos |
| Explainability | `explainability/` (5 archivos) | ~200 | ORPHANED: solo tests y scripts/ |
| KnowledgeBase | `knowledge_base/` (9 archivos) | ~500 | ORPHANED: solo test_knowledge_base.py |
| ScientificValidation | `scientific_validation/` (5 archivos) | ~300 | ORPHANED: solo tests y scripts/ |
| QualityMonitoring | `quality_monitoring/` (6 archivos) | ~300 | ORPHANED: solo tests y scripts/ |
| ReleasePipeline | `release_pipeline/` (5 archivos) | ~300 | ORPHANED: solo tests y scripts/ |
| ReviewUI | `review_ui/` (7 archivos + SQLite) | ~400 | ORPHANED: 251 decisiones en DB, solo script run_human_review.py |
| GoldImport | `gold_import/` (5 archivos) | ~300 | Solo conectado indirectamente vía GoldBuilder |
| SplitAC01 | `split_ac01/` (4 archivos) | ~200 | ORPHANED: solo tests y script |
| DocumentAssessment | `assessment/document_assessment.py` | ~100 | ORPHANED: solo test |
| AccountingKnowledge | `accounting_knowledge/analyzer.py` | ~100 | ORPHANED: solo run_akb.py |
| Evaluation | `evaluation/homologation_benchmark.py` | ~200 | ORPHANED: nunca importado |
| Pipeline New | `pipeline/new_pipeline.py` | — | **DEAD CODE**: nunca importado por nadie |
| DecisionEngineV2 | `decision_v2/engine.py` | 598 | ORPHANED: solo test, no usado por pipeline |
| DecisionEngine (v1) | `decision/engine.py` | 189 | USADO por pipeline (feature-flagged ENABLE_DECISION_ENGINE) |

---

## 3. DEPENDENCIAS

### 3.1 Python (desde pyproject.toml + requirements.txt)

| Dependencia | Propósito | Versión |
|---|---|---|
| streamlit | UI | ≥1.35.0 / ^1.58.0 |
| pandas | Manejo de datos | ≥2.0.0 |
| openpyxl | Excel | ≥3.1.0 / ^3.1.5 |
| rapidfuzz | Fuzzy matching | ≥3.0.0 |
| pdfplumber | Extracción PDF | ≥0.10.0 / ^0.11 |
| pillow | Procesamiento imágenes | ≥10.0.0 |
| pdf2image | PDF → imágenes (OCR) | ≥1.17.0 |
| psycopg2-binary | PostgreSQL | ≥2.9.0 |
| pydantic | Validación datos | ^2.0 |
| fastapi | API REST | ^0.139.0 |
| uvicorn | Servidor ASGI | ^0.49.0 |

### 3.2 Sistema operativo

| Dependencia | Propósito |
|---|---|
| Tesseract OCR | OCR documentos escaneados |
| Poppler (pdftoppm) | Renderizado PDF → imágenes |
| PostgreSQL 16 | Base de datos (schema_minimo.sql) |

### 3.3 Base de datos

| Archivo | Tipo | Registros |
|---|---|---|
| `gold_standard.db` | SQLite | 187 gold_records |
| `gold_standard_bench.db` | SQLite | 0 registros (benchmark) |
| `review_ui/reviews.db` | SQLite | 251 review_decisions |

### 3.4 Datasets

| Recurso | Registros |
|---|---|
| `diccionario.json` | 826 entradas (823 códigos válidos) |
| `diccionario_actualizado.json` | 781 entradas (778 válidos) |
| `diccionario_optimizado.json` | 712 entradas (712 válidos) |
| `catalogo_maestro.json` | 52 códigos estándar |
| `knowledge/concept_catalog.json` | Catálogo de conceptos semánticos |
| `learning_queue.json` | Cola de correcciones humanas |
| `datasets/HOLDOUT/` | ~20+ PDFs |
| `datasets/edge_cases/` | ~100+ PDFs/Excel |
| `datasets/validacion/` | ~100+ PDFs/Excel |

---

## 4. FLUJO REAL DEL PARSER

### 4.1 Flujo de extracción (parser_universal.py:ParserPDF.parsear())

```
ParserPDF.parsear(path, context=None)
    │
    ├── 1. validar_archivo(path)
    │       └── firma PDF → %PDF-
    │       └── firma XLSX → zip + workbook.xml
    │       └── firma XLS → OLE2
    │
    ├── 2. _extraer_lineas(path, context)
    │       ├── pdfplumber.open(path) → extract_text() por página
    │       ├── si hay texto nativo:
    │       │       └── _debe_corregir_rotacion(context) → rotation_hint==180
    │       │       └── si True: _reverse_line() por cada línea
    │       │       └── return (lineas, False, 0|180)
    │       └── si NO hay texto nativo:
    │               └── _ocr_documento(path, n_paginas)
    │                   ├── pdftoppm por página
    │                   ├── detectar_rotacion_osd() → Tesseract OSD
    │                   ├── fallback: detectar_rotacion_heuristica()
    │                   ├── ocr_pagina() con rotación
    │                   └── return (lineas_ocr, True, rotacion)
    │
    ├── 3. normalizar_codigo_ocr() por línea (corrige ','→'.' en códigos)
    │
    ├── 4. detectar_formato_codigo() sobre primeros 60 tokens
    │       └── GUION | PUNTO | COMPACTO | SIN_CODIGO
    │
    ├── 5. detectar_separador_miles() sobre primeros 80 montos
    │       └── '.' o ',' según consistencia
    │
    ├── 6. Detección de layout de columnas (3 estrategias en orden):
    │       1. ExtractionContext.layout_hint (de DocumentAnalyzer) si confianza ≥ 0.8
    │       2. LayoutDetector interno (solo si ENABLE_DYNAMIC_LAYOUT=True, default: False)
    │       3. Heurística estándar: [ACTIVO, PASIVO, PERDIDA, GANANCIA]
    │
    ├── 7. parsear_linea() por cada línea:
    │       ├── Filtro GARBAGE_PATTERNS (24 patrones: URLs, teléfonos, RUTs, etc.)
    │       ├── Extraer código según FormatoCodigo
    │       ├── Extraer montos desde el final (últimos 1-4 tokens numéricos)
    │       ├── Asignar OrigenColumna según orden de columnas
    │       ├── Detectar es_total (PATRON_TOTAL)
    │       └── return CuentaRaw[]
    │
    ├── 8. [OPCIONAL] AccountTypeResolver (solo si ENABLE_ACCOUNT_TYPE_RESOLVER=True
    │       o context desde DocumentAnalyzer con confianza ≥ 0.7)
    │       └── resuelve tipo: ACTIVO|PASIVO|PATRIMONIO|PERDIDA|GANANCIA|DESCONOCIDO
    │
    └── 9. return ResultadoParseo
```

### 4.2 Flujo de clasificación (HomologationPipeline.process())

```
HomologationPipeline.process(pdf_path)
    │
    ├── ParserPDF.parsear(path) → ResultadoParseo
    │
    ├── Por cada CuentaRaw:
    │   ├── AccountAdapter.from_cuenta_raw() → AccountBalance
    │   ├── BalanceInterpreter(ab) → nature, classification_amount
    │   ├── AccountTypeResolver.resolve() → tipo (ACTIVO/PASIVO/...)
    │   ├── Saltar si classification_amount == 0 (movement_only)
    │   │
    │   ├── _classify_account(code, name, tipo)
    │   │   ├── 1. LearningEngine.best_match() → Gold Standard (SQLite)
    │   │   ├── 2. [Si ENABLE_CMCC] CMCCClassifier.classify()
    │   │   ├── 3. [Si ENABLE_DECISION_ENGINE]
    │   │   │       └── _classify_with_decision_engine()
    │   │   │           ├── _classify_by_code()
    │   │   │           ├── _classify_by_dictionary_exact/fuzzy()
    │   │   │           ├── SemanticMatcher.match() [feature-flagged]
    │   │   │           ├── RegexFallback [feature-flagged]
    │   │   │           └── DecisionEngine.decide() → resuelve conflictos
    │   │   └── 4. [Si NO decision engine] first-match-wins:
    │   │           código → diccionario exacto → fuzzy → semántico → regex
    │   │
    │   ├── AccountTypeFilter (opcional)
    │   ├── SemanticEngine.interpret() → metadata semántica
    │   ├── ProcesadorReglasEspeciales.aplicar() → D1-D5
    │   └── Agregar a classified[]
    │
    └── return summary (dict con métricas)
```

---

## 5. COBERTURA DE PRUEBAS

### 5.1 Tests totales

| Medición | Valor |
|---|---|
| Archivos de test | 56 (15 root + 41 en tests/) |
| Tests colectados | 1165 |
| Tests verificados como PASS | ~1000+ |
| Tests FALLIDOS | 11 (todos en `tests/test_split_ac01.py`) |

### 5.2 Tests fallidos

| Test | Archivo | Error |
|---|---|---|
| `test_deposito_plazo_pattern` | `tests/test_split_ac01.py` | AssertionError |
| `test_equivalentes_variants` | `tests/test_split_ac01.py` | AssertionError |
| `test_all_files_created` | `tests/test_split_ac01.py` | AssertionError |
| `test_variant_mapping_content` | `tests/test_split_ac01.py` | AssertionError |
| `test_split_statistics_sheets` | `tests/test_split_ac01.py` | AssertionError |
| `test_review_needed_content` | `tests/test_split_ac01.py` | KeyError |
| `test_coverage_before_after_content` | `tests/test_split_ac01.py` | AssertionError |
| `test_split_report_md_content` | `tests/test_split_ac01.py` | AssertionError |
| `test_empty_queue_creates_empty_files` | `tests/test_split_ac01.py` | AssertionError |
| `test_review_needed_reason` | `tests/test_split_ac01.py` | KeyError |
| `test_report_all_dept` | `tests/test_split_ac01.py` | AssertionError |

### 5.3 Componentes sin tests

| Componente | Archivo | Riesgo |
|---|---|---|
| `app_validacion.py` (core UI) | `app_validacion.py` | **CRÍTICO** — 1340 líneas sin tests automatizados |
| `parser_universal.py` (parser core) | `parser_universal.py` | **CRÍTICO** — 831 líneas, solo probado indirectamente |
| `clasificador_codigo_cuenta.py` | `clasificador_codigo_cuenta.py` | **ALTO** — sin test directo |
| `reglas_especiales.py` | `reglas_especiales.py` | **ALTO** — sin test directo |
| `extractor_metadata.py` | `extractor_metadata.py` | **MEDIO** |
| `interpreters/balance_interpreter.py` | `interpreters/balance_interpreter.py` | **MEDIO** |
| `adapters/account_adapter.py` | `adapters/account_adapter.py` | **BAJO** (mapper simple) |
| `shadow/shadow_logger.py` | `shadow/shadow_logger.py` | **BAJO** |
| `pipeline/cmcc_classifier.py` | `pipeline/cmcc_classifier.py` | **ALTO** — solo probado indirectamente |
| `pipeline/homologation_pipeline.py` | `pipeline/homologation_pipeline.py` | **ALTO** — 634 líneas, probado en integración |
| `src/api/main.py` (FastAPI) | `src/api/main.py` | **MEDIO** — endpoint sin uso en producción |

### 5.4 Cobertura por tipo de test

| Tipo | Cantidad | Estado |
|---|---|---|
| Unit tests (componentes aislados) | ~800 | ✅ Mayoría pasa |
| Integration tests (pipeline real) | ~200 | ✅ Pasa (test_cmcc_integration, test_document_analyzer_integration) |
| End-to-end (app_validacion.py) | 0 | ❌ **NINGUNO** |
| UI tests (Streamlit) | 0 | ❌ **NINGUNO** |
| API tests (FastAPI) | 0 | ❌ **NINGUNO** |

---

## 6. COMPONENTES ACTIVOS (en producción)

Los siguientes componentes están efectivamente activos en `app_validacion.py`:

| Componente | Activación | Feature Flag |
|---|---|---|
| `parser_universal.py:ParserPDF` | Siempre | — |
| `clasificador_codigo_cuenta.py:ClasificadorCodigo` | Siempre (en MotorHibridoLocal y Pipeline) | — |
| `reglas_especiales.py:ProcesadorReglasEspeciales` | Siempre | — |
| `HomologationPipeline` | `USE_LEGACY_ENGINE=False` (default) | `USE_LEGACY_ENGINE` |
| `MotorHibridoLocal` | `USE_LEGACY_ENGINE=True` | `USE_LEGACY_ENGINE` |
| `GoldBuilder` | Siempre (en correcciones) | — |
| `ShadowLogger` | `SHADOW_MODE=True` (default) | `SHADOW_MODE` |
| `LearningEngine` | Siempre (dentro de Pipeline) | — |
| `REGLAS_REGEX` (36 patrones) | Siempre (en MotorHibridoLocal) | — |
| `_REGEX_FALLBACK` (7 patrones auditados) | Siempre (dentro de Pipeline) | `ENABLE_REGEX_FALLBACK` |
| `CMCCClassifier` | Feature-flagged | `ENABLE_CMCC` |
| `SemanticEngine` | Siempre (dentro de Pipeline) | — |
| `SemanticMatcher` | Feature-flagged | `ENABLE_SEMANTIC_MATCHER` |
| `DecisionEngine` | Feature-flagged | `ENABLE_DECISION_ENGINE` |
| `AccountTypeFilter` | Feature-flagged | `ENABLE_ACCOUNT_TYPE_FILTER` |

---

## 7. COMPONENTES CONSTRUIDOS PERO NO UTILIZADOS

### 7.1 Dead Code (nunca importado)

| Archivo | Tipo | Evidencia |
|---|---|---|
| `pipeline/new_pipeline.py` | Clase `NewPipeline` | No importado por ningún otro archivo en el código base. `grep -r "new_pipeline" *.py tests/ scripts/` → 0 resultados excepto su propio archivo. |
| `evaluation/homologation_benchmark.py` | Script standalone | No importado por ningún otro archivo. Solo referenciado en comentarios de `tools/validate_dictionary_audit.py` y `tools/dictionary_audit.py`. |

### 7.2 Código construido pero no integrado en app/pipeline

| Archivo | Uso real |
|---|---|
| `parsers/analyzer.py` (DocumentAnalyzer) | Solo importado por `parsers/integration.py` y tests. `app_validacion.py` y `homologation_pipeline.py` NO lo usan. |
| `parsers/integration.py` (parse_with_analysis) | Solo importado por tests (`test_document_analyzer_integration.py`). |
| `parsers/pdf_parser.py` (ParserCore2) | Solo usado por `parsers/factory.py` y scripts de benchmark. No usado por app ni pipeline. |
| `confidence/` (ambos engines) | No importado por `homologation_pipeline.py` ni `app_validacion.py`. El pipeline usa `decision.engine.DecisionEngine`. |
| `evidence/` (6 archivos) | Solo tests internos. |
| `explainability/` (5 archivos) | Solo tests y scripts/ (run_decision_trace.py, cmcc_compatibility_report.py). |
| `knowledge_base/` (9 archivos) | Solo test_knowledge_base.py. |
| `scientific_validation/` (5 archivos) | Solo tests y scripts/. |
| `quality_monitoring/` (6 archivos) | Solo tests y scripts/. |
| `release_pipeline/` (5 archivos) | Solo tests y scripts/. |
| `review_ui/` (7 archivos + DB) | Solo tests y script run_human_review.py. 251 decisiones en DB nunca visibles desde app. |
| `split_ac01/` (4 archivos) | Solo tests (11 fallan) y script. |
| `assessment/` (1 archivo) | Solo test_document_assessment.py. |
| `accounting_knowledge/` (2 archivos) | Solo run_akb.py (dentro del mismo paquete). |
| `decision_v2/` (2 archivos) | Solo tests. El pipeline usa decision/engine.py (v1). |
| `src/core/orquestador.py` (PipelineOrquestador) | Solo usado por `src/api/main.py` (FastAPI) y `test_orquestador.py`. No usado por app. |
| `src/api/main.py` (FastAPI) | Entrada independiente, no importada por nadie. |
| `ui/app.py` (Streamlit MVP) | Entrada independiente, no importada por nadie. |

### 7.3 Feature flags inactivos por defecto

| Flag | Archivo | Default | Propósito |
|---|---|---|---|
| `ENABLE_DYNAMIC_LAYOUT` | `parser_universal.py:15` | `False` | LayoutDetector para orden de columnas |
| `ENABLE_ACCOUNT_TYPE_RESOLVER` | `parser_universal.py:20` | `False` | Resolver tipo de cuenta post-parseo |
| `ENABLE_CMCC` | `pipeline/features.py` | `False` (inferido del código) | Clasificador CMCC |
| `ENABLE_SEMANTIC_MATCHER` | `pipeline/features.py` | `False` | SemanticMatcher en pipeline |
| `ENABLE_DECISION_ENGINE` | `pipeline/features.py` | `True` (inferido del código) | DecisionEngine para conflictos |
| `ENABLE_REGEX_FALLBACK` | `pipeline/features.py` | `True` | 7 regex auditados |
| `ENABLE_CMCC_PRODUCTION` | `pipeline/features.py` | `False` | Usar CMCC como clasificador primario |
| `USE_LEGACY_ENGINE` | `app_validacion.py:20` | `False` | Usar MotorHibridoLocal vs Pipeline |

---

## 8. HALLAZGOS ADICIONALES

### 8.1 Inconsistencias en diccionarios

| Archivo | Entradas | Diferencia con diccionario.json |
|---|---|---|
| `diccionario.json` (canonical) | 826 | — |
| `diccionario_actualizado.json` | 781 | -45 entradas |
| `diccionario_optimizado.json` | 712 | -114 entradas (13.8% menos) |

No hay documentación sobre cuál es el diccionario fuente de verdad. `cargar_datos.py` usa `diccionario.json`, pero existen 3 versiones divergentes.

### 8.2 Base de datos Gold Standard

- `gold_standard.db`: 187 registros en tabla `gold_standard`, 187 en `gold_records`
- `gold_standard_bench.db`: 0 registros (benchmark vacío)
- `reports/cmcc_validation_final/`: ~200+ archivos JSON de baseline (caché de validación)

### 8.3 Archivos huérfanos en root

| Archivo | Tamaño | Propósito | Estado |
|---|---|---|---|
| `analyze_formats.py` | — | Análisis de formatos | Standalone |
| `inspect_pdf.py` | — | Inspección PDF | Standalone |
| `run_semantic_shadow.py` | — | Shadow semántico | Standalone |
| `run_audit.py` | — | Auditoría | Standalone |
| `summarize_formats.py` | — | Resumen formatos | Standalone |
| `validate_families.py` | — | Validación familias | Standalone |
| `analysis_legacy_gap.md` | — | Gap analysis legacy | Documento |
| `format_statistics.md` | — | Estadísticas formatos | Documento |
| `validation_report.md` | — | Reporte validación | Documento |

### 8.4 Archivos de configuración sin archivo destino

- `config/release.yml`: Define gates para release 2.0, pero no hay código que lo lea.
- `pyproject.toml` menciona `[tool.poetry.scripts]` con `carpeta-tributaria = "src.cli:main"`, pero `src/cli.py` no existe.
