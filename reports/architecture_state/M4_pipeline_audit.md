# M4 — Auditoría Arquitectónica del Pipeline de Clasificación

Fecha: 2026-08-03 · Tipo: SOLO AUDITORÍA (ningún archivo modificado) · Base: benchmark 2660/2662 (99.92%), 2 mismatches, 0 regresiones.

---

## 0. Resumen ejecutivo

El sistema tiene **3 pipelines de clasificación en paralelo** (V1 desplegado, V2 no desplegado, legacy MotorHibridoLocal) más **4 motores de decisión** (decision/, decision_engine/, decision_v2/, classification_engine/), **48 implementaciones de normalización de nombre**, y **~1.9M LOC en 5,054 archivos** de los cuales el núcleo real de clasificación es ~17K LOC en ~101 módulos. El grueso del código (tests 651K LOC, reports 43K, scripts 15K, paquetes completos como patterns/, parser_quality/, knowledge_base/, mappers/, ui/, observability/) es **huérfano o solo-test** y no alimenta el flujo desplegado.

**Flujo real desplegado** (Dockerfile:30 → `streamlit run app_validacion.py` → `HomologationPipeline`):
Parser → Learning Engine (gold) → código → diccionario exacto → diccionario fuzzy → regex fallback → ReglasEspeciales. Con los flags default (`pipeline/features.py:16-70`), **CMCC, DecisionEngine, SemanticMatcher y el filtro por tipo están apagados**; SemanticEngine.interpret corre siempre pero **solo genera metadata, no decide**.

**Hallazgos centrales:**
1. Dos pipelines completos (V1 desplegado vs V2 en `orchestrator/pipeline_v2.py`) con arquitecturas distintas haciendo lo mismo.
2. `MotorHibridoLocal` (legacy) duplica la cadena código→diccionario→regex de `HomologationPipeline` y sigue vivo en la pestaña Revisión de la UI.
3. 4 motores de decisión que re-implementan fuzzy de diccionario, filtro de tipo y normalización.
4. El Parser abre el mismo PDF 2–3 veces por documento y no hay caché; app_validacion en modo legacy+shadow lo parsea 2 veces completas.
5. ~48 normalizadores de nombre distintos y no interoperables (riesgo de mismatch de keys gold/diccionario).
6. Paquetes completos muertos: `mappers/`, `observability/`, `extractors/`, `knowledge_discovery/`, `architecture/`, `ui/`, `classification_engine/` (docstring confiesa "se integrará en Sprint 39" — nunca ocurrió).

---

## 1. FASE 1 — Arquitectura actual (flujo completo de clasificación)

### 1.1 Diagrama del flujo V1 desplegado

```
PDF / Excel
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ ParserPDF.parsear()  parser_universal.py:595                      │
│   validar_archivo → _analizar_documento (preview 3 pág, reabre)   │
│   → _extraer_lineas (reabre PDF completo) → [si escaneado: OCR]   │
│   → normalizar_codigo_ocr → detectar_formato_codigo               │
│   → detectar_separador_miles → layout (heurística fija)           │
│   → parsear_linea por línea → ResultadoParseo[cuntas]             │
└─────────────────────────────────────────────────────────────────┘
    │  (Excel: parsear_excel, pipeline:370)
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ AccountAdapter.from_cuenta_raw  → AccountBalance   (:422)         │
│ BalanceInterpreter  → nature, classification_amount (:423)        │
│ AccountTypeResolver.resolve(origen, codigo) → tipo   (:427)       │
└─────────────────────────────────────────────────────────────────┘
    │  si classification_amount is None → ignored (movement_only)
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ _classify_account(account_code, name, tipo)  pipeline:175         │
│                                                                    │
│  1. LearningEngine.best_match(name)  → exact/fuzzy/none  (:180)   │
│        │  SI source != none → method=learning_{exact|fuzzy}       │
│        ▼  (resultado con confianza 0.98 / 0.80–0.97)              │
│  2. CMCCClassifier.classify(name)  [si ENABLE_CMCC]   (:196)      │
│  3. Branch:                                                       │
│       A) ENABLE_DECISION_ENGINE=True (OFF default):               │
│          SemanticMatcher + regex + dict → DecisionEngine.decide   │
│       B) default first-match-wins (pipeline:227):                 │
│          code → dict_exact → dict_fuzzy → [SemanticMatcher si ON] │
│          → regex_fallback → unclassified                          │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Filtro por tipo  [ENABLE_ACCOUNT_TYPE_FILTER, OFF default] :450   │
│ ProcesadorReglasEspeciales.aplicar  reglas_especiales.py:42  :535 │
│    R1 banco negativo→PC.02, R2 terrenos→AC.05, R3 ingresos        │
│    adelantado→PC.08, R4 clientes negativo→PC.08, R5 cta socios    │
│    → final_code = adjustment.codigo_final si aplica               │
│ SemanticEngine.interpret(ab)  (SÓLO metadata, no decide)  :517    │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
Resultado final: {standard_code, final_code, confidence, method, reason,
                   semantic_result, cmcc_shadow, ...} + summary
```

### 1.2 Los 3 flujos que compiten

| Flujo | Entry point | Estado |
|---|---|---|
| **V1** `HomologationPipeline.process` | `app_validacion.py:433` (default, Dockerfile:30), `ui/app.py:12` (huérfana) | **PRODUCCIÓN DESPLEGADA** |
| **V2** `HomologationPipelineV2` (9 adapters SIE→DIE→Parser→KB→Decision→Validation→Review→Coverage→SelfQA) | `run_pipeline_v2.py:23` → `backend/runner.py:31` → `orchestrator/pipeline_v2.py:41` | Funcional, **NO desplegado** (CLI) |
| **Legacy** `MotorHibridoLocal.clasificar` | `app_validacion.py:140` | Activo en pestaña Revisión (:619) y bajo SHADOW_MODE (:392-428); opt-out `USE_LEGACY_ENGINE=False` (:48) |
| `NewPipeline` | `pipeline/new_pipeline.py:17` | **Muerto** (0 importadores) |

---

## 2. FASE 2 — Detalle por etapa

### Etapa 0 · Parser — `parser_universal.py` (983 L, 21 fn, CC 152)

| Atributo | Valor |
|---|---|
| Responsabilidad | Parsear balances (PDF texto/OCR + Excel) → `list[CuentaRaw]` |
| Entradas | Path PDF/Excel |
| Salidas | `ResultadoParseo` (cuentas, formato, separador, OCR, rotación) |
| Quién lo llama | `homologation_pipeline.py:380`, `app_validacion.py:764`, `new_pipeline:25`, `adapters/parser_adapter.py:40`, DIE extractors, ~20 reportes/scripts |
| Quién lo consume | V1, V2, legacy, benchmarks |
| Utilización | 100% de los documentos (puerta de entrada) |
| Costo | Dominante. 2 aperturas pdfplumber por PDF (`:145` preview + `:865` full); escaneados → pdftoppm 250dpi + tesseract OSD + tesseract por página (subprocess). ~17 regex por línea en `_es_linea_basura` (:468) |
| Dependencias | pdfplumber, PIL, document_intelligence (preview), subprocess/tempfile (OCR) |
| Notas | Flags `ENABLE_DYNAMIC_LAYOUT`, `ENABLE_ACCOUNT_TYPE_RESOLVER` muertos (`:38,42,57`); ramas `:663-770` código inerte |

### Etapa 1 · Adapter + Interpreter — `adapters/account_adapter.py` + `interpreters/balance_interpreter.py`

| Atributo | Valor |
|---|---|
| Responsabilidad | Mapear `CuentaRaw`→`AccountBalance`; interpretar naturaleza y monto de clasificación |
| Entradas | `CuentaRaw` |
| Salidas | `AccountBalance`, `nature`, `classification_amount`, `requires_classification` |
| Quién lo llama | `homologation_pipeline.py:422-423`, `app_validacion.py:434,460`, V2 (`kb_adapter`), V2/`mappers` (muerto) |
| Consumidores | clasificación y filtro `movement_only` |
| Utilización | 100% de cuentas (por cuenta) |
| Costo | O(1) por cuenta |
| Notas | `AccountAdapter.to_account_balance` (:70-77) es alias puro de `from_cuenta_raw` |

### Etapa 2 · Type Resolver — `parsers/account_type_resolver.py` (240 L, CC 21)

| Atributo | Valor |
|---|---|
| Responsabilidad | Determinar tipo universal (ACTIVO/PASIVO/PATRIMONIO/PERDIDA/GANANCIA/DESCONOCIDO) por columna+código |
| Entradas | `origen_columna`, `codigo` |
| Salidas | `AccountTypeResult` |
| Quién lo llama | `homologation_pipeline.py:408` (por `process`), `kb_adapter.py:83` (V2) |
| Consumidores | filtro de tipo (OFF default) y metadata |
| Utilización | 100% (siempre se ejecuta, pero su resultado solo decide si el filtro está ON) |
| Costo | Trivial |
| Notas | dict lookup + startswith; sin regex/fuzzy |

### Etapa 3 · Learning Engine (Gold Standard) — `learning/engine.py` (326 L, CC 34)

| Atributo | Valor |
|---|---|
| Responsabilidad | Lookup de Gold Standard exact/fuzzy |
| Entradas | account_name |
| Salidas | `{source: exact\|fuzzy\|none, code, confidence, matched_name}` |
| Quién lo llama | `homologation_pipeline.py:180`, `decision_v2/engine.py:64` |
| Consumidores | clasificación (primera capa); decisión V2 |
| Utilización | 100% de cuentas clasificables (siempre ejecutado) |
| Costo | 2 queries SQL **full-scan sin índices** por cuenta (`engine.py:75-86` exact + `:100-102` fuzzy), filtrado en Python sobre 234 filas. Sin `CREATE INDEX` en `gold_standard.normalized` |
| Dependencias | gold_standard.db, `learning/exact_match.normalize_name`, `learning/fuzzy_match.fuzzy_score` |
| Notas | `learning/statistics.py` es stub, 0 importadores |

### Etapa 4 · Clasificador por código — `clasificador_codigo_cuenta.py` (290 L, CC 17)

| Atributo | Valor |
|---|---|
| Responsabilidad | Mapear código numérico (guion/punto/compacto) → código estándar |
| Entradas | account_code |
| Salidas | `ResultadoCodigo` (codigo_estandar, confianza) |
| Quién lo llama | `homologation_pipeline.py:109`, `app_validacion.py:160`, `decision_v2:54`, `classification_engine` |
| Consumidores | todos los motores |
| Utilización | Solo cuentas con código; **único módulo realmente compartido** (no duplicado) |
| Costo | O(mapas) |

### Etapa 5 · Diccionario exact/fuzzy — `homologation_pipeline.py:119-152`

| Atributo | Valor |
|---|---|
| Responsabilidad | Match contra `diccionario.json` (exact normalizado; fuzzy token_sort_ratio ≥90) |
| Entradas | account_name |
| Salidas | `dictionary_exact` (conf 0.98) / `dictionary_fuzzy` (0.80–0.97) |
| Quién lo llama | `_classify_account` (:230-231) y `_classify_with_decision_engine` (:277) |
| Consumidores | clasificación |
| Utilización | Cuentas no resueltas por learning/código |
| Costo | `_normalize_name` por entrada y por cada cuenta del diccionario; fuzzy O(N_dict × tokens) |
| Duplicación | Misma lógica en `app_validacion.py:164-171` (legacy) y `decision_v2` (dict reimplementado, `:180/:589-594`) |

### Etapa 6 · Semantic — `semantic/` (matcher 174 L, engine 30 L)

| Atributo | SemanticEngine | SemanticMatcher |
|---|---|---|
| Responsabilidad | Metadata semántica (tipo/naturaleza) por reglas keyword | Match por 6 tiers contra `concept_catalog.json` → código CMCC |
| Salidas | `SemanticAccount` | `SemanticMatch` (expected_cmcc, tier, score) |
| Quién lo llama | `homologation_pipeline.py:517` (siempre, métrica) | `homologation_pipeline.py:235/285` (solo si ENABLE_SEMANTIC_MATCHER) |
| ¿Decide? | **NO** — solo metadata (documentado) | SÍ, pero flag OFF por defecto |
| Costo | reglas substring | catálogo + tiers |
| Notas | `semantic/semantic_catalog.py` solo lo usa `test_semantic.py` (muerto) | — |

### Etapa 7 · CMCC — `pipeline/cmcc_classifier.py` (87 L)

| Atributo | Valor |
|---|---|
| Responsabilidad | Clasificar contra `knowledge/cmcc.json` (52 conceptos) con scoring ponderado |
| Entradas | account_name |
| Salidas | `{code, concept, score, method: cmcc_*, evidence}` |
| Quién lo llama | `homologation_pipeline.py:197` (solo si ENABLE_CMCC) |
| Utilización | **OFF en default**; solo shadow/producción bajo env |
| Costo | Recorre todas las variantes en Python por cuenta |
| Dependencias | `knowledge/normalizer.py` (único contacto prod con knowledge/) |
| Duplicación | **DUPLICA `knowledge/cmcc.py` + matcher.py + repository.py** (mismo `cmcc.json`, misma lógica, otro motor) |

### Etapa 8 · Decision Engine — `decision/engine.py` (189 L, CC no listado) + `decision_v2/`

| Atributo | decision/ (V1) | decision_v2/ |
|---|---|---|
| Responsabilidad | Resolver conflicto SM vs Regex (5 reglas) | Ensemble ponderado multi-fuente (consenso/tie-break) |
| Entradas | sm_*, regex_*, dict_*, tipo | account + evidencia |
| Quién lo llama | `homologation_pipeline.py:314` (solo ENABLE_DECISION_ENGINE, OFF) | solo `scripts/benchmark_decision_v2.py`, `scripts/classifier_precision.py` |
| Utilización | **OFF default** | **NO producción** |
| Smell | dict_code/account_type se aceptan y no se usan (:20-33) | importa `REGLAS_REGEX` desde `app_validacion` (:72) — dependencia invertida |

### Etapa 9 · Reglas especiales — `reglas_especiales.py` (297 L, CC 28)

| Atributo | Valor |
|---|---|
| Responsabilidad | 5 reglas post-proceso por nombre+código+monto+giro |
| Quién lo llama | `homologation_pipeline.py:535` (producción), `app_validacion.py:193` (legacy) |
| Utilización | 100% (siempre tras clasificar) |
| Duplicación | `special_account_rules.py` (declarativa, no ejecutada) se solapa temáticamente con **resultados inconsistentes** (Cta Socios → AC.06S vs PAT.10) |

### Etapa 10 · Salida — summary + clasificados

| Atributo | Valor |
|---|---|
| Responsabilidad | Consolidar resultados + métricas |
| Salidas | `classified[]`, `ignored[]`, summary con contadores por método |
| Consumidores | UI, benchmarks, gold_standard feedback |

---

## 3. FASE 3 — Duplicaciones detectadas

### 3.1 Normalizadores — **48 implementaciones del mismo concepto**

| Grupo | Ubicación |
|---|---|
| Familia NFKD (acentos) | `learning/exact_match.py:7`, `reports/analyze_baseline.py:56` (migrado a core), `core/normalizer.py` (M3) |
| Familia simple (regex `[^a-z0-9áéíóúñü ]`) | `pipeline/homologation_pipeline.py:76`, `decision_v2/engine.py:584` (copia), `knowledge_base/cmcc_builder.py:37` |
| Normalizador rico (abreviaciones/OCR/plurales) | `account_name_normalizer.py:295` (canónico), `knowledge/normalizer.py:96` (8 etapas) |
| Ad-hoc | `app_validacion.py:87`, `analytics/unclassified_analyzer.py:28`, `knowledge/unknown_cluster.py:23`, `explainability/trace_builder.py:188`, `src/db_repository.py:125`, `analysis/hierarchy_comparator.py:24`, `reports/run_layout_validation.py:66` |

**Riesgo**: `learning.engine` usa `learning.exact_match.normalize_name` (NFKD) para el gold, mientras el pipeline usa `_normalize_name` (sin NFKD) para el diccionario → mismatch potencial de keys entre gold y diccionario.

### 3.2 Regex de código de cuenta — **6 copias**
`parser_universal.py:200-202,408-412` · `parsers/analyzer.py` · `parsers/format_detector.py` · `extractors/table_extractor.py:38-40` · `inspect_pdf.py:22-24` · `tools/compare_extraction.py:37` (+ inline en `context/context_builder.py:234`, `clasificador_codigo_cuenta.py:200`).

### 3.3 Regex de líneas totales — **4 copias**
`parser_universal.py:423-426` · `structure_engine/structure_detector.py:6-14` · `document_intelligence/__init__.py:462` · `extractors/table_extractor.py:29-35` · `inspect_pdf.py:32`.

### 3.4 Léxicos de layout/columnas — **3-4 copias**
`parsers/layout_detector.py:21-33` vs `parsers/config.py:40-46` (mismo paquete) · `structure_engine/structure_detector.py:16-37` · `extractors/table_extractor.py:22-35` · `parser_universal.py:84-93`.

### 3.5 Corrección de rotación 180° — **3 implementaciones**
`parser_universal.py:880-893` · `parsers/analyzer.py:403-429` · `parsers/orientation_detector.py:73-120`.

### 3.6 Consultas SQL duplicadas/repetidas
- `learning/engine.py` hace **2 full-scans de gold_standard por cuenta** sin índices (`:75-86`, `:100-102`).
- `knowledge_base/cmcc_builder.py:57,72` re-lee `gold_standard`/`gold_records` (offline).
- `src/db_repository.py:60-118` (FastAPI stub) con queries separadas que no usa nadie en producción.

### 3.7 Recorridos/lecturas repetidas del mismo PDF
- Dentro de un `parsear()`: el PDF se abre **2 veces** (preview `:145` + full `:865`).
- `app_validacion` legacy+SHADOW_MODE: `_extraer_cuentas` (:361) **y** `hp_shadow.process` (:402) → **2 parses completos**.
- Pipeline V2: DIE (`document_intelligence/__init__.py:355-376`) + ParserPDF → **3 lecturas**.
- Sin caché (`parsers/config.py:51` `CachingConfig.enabled=False`, nunca implementado).

### 3.8 Lógica de clasificación duplicada entre motores
`MotorHibridoLocal.clasificar` (`app_validacion.py:140-200`) vs `HomologationPipeline._classify_account` (`pipeline:175-266`): misma cadena código→dict exacto→fuzzy→regex con **mismos umbrales hardcodeados** (0.98, fuzzy ≥90 → `0.80+(score-90)*0.01`).

### 3.9 Motores de decisión — **4 implementaciones**
`decision/` (V1 prod, flag OFF) · `decision_engine/` (V2) · `decision_v2/` (scripts) · `classification_engine/engine.py:37` (muerto). Los 4 re-implementan normalización, fuzzy de diccionario y filtro de tipo.

### 3.10 Reglas especiales duplicadas
`reglas_especiales.py` (producción) vs `special_account_rules.py` (declarativa, solo tests/tools) — solapamiento temático con resultados inconsistentes (AC.06S vs PAT.10 para Cta. Socios).

### 3.11 Módulos muertos / nunca ejecutados

| Paquete/módulo | Estado | Evidencia |
|---|---|---|
| `mappers/` (`dataframe_mapper.py`) | Muerto | 0 importadores |
| `observability/` | Muerto | 0 importadores |
| `extractors/table_extractor.py` | Muerto | 0 importadores |
| `knowledge_discovery/` | Muerto | `__init__.py` vacío |
| `architecture/` | Muerto | solo .md/.drawio |
| `ui/app.py` | Huérfano | 0 importadores (duplica app_validacion) |
| `src/api/main.py` + `src/core/orquestador` | Stub | `procesar` solo hace print |
| `classification_engine/` | Muerto | solo `test_classification_engine.py`; docstring "se integrará en Sprint 39" (`engine.py:12`) |
| `accounting_knowledge/` | Hoja muerta | importa código prod pero nadie la importa |
| `pipeline/new_pipeline.py` | Muerto | 0 importadores |
| `learning/statistics.py` | Stub | 0 importadores |
| `semantic/semantic_catalog.py` | Solo test | `test_semantic.py:9` |
| `knowledge_base/` (10 clases exportadas) | Solo test | `tests/test_knowledge_base.py` |
| `knowledge/` (cmcc, matcher, concept, repository, builder, metrics, financial_*, graph_*) | Solo scripts/tests/reportes | el pipeline solo usa `knowledge/normalizer.py` |
| `parsers/ParserCore2`, `DocumentAnalyzer`, `ocr_engine`, `factory`, `integration` | Prototipo no conectado | `parsers/__init__.py:3` |
| `decision_v2/` | Solo benchmarks | `scripts/benchmark_decision_v2.py`, `scripts/classifier_precision.py` |

### 3.12 Flags muertos / ramas imposibles
- `parser_universal.py:38,42,57`: `ENABLE_DYNAMIC_LAYOUT`, `ENABLE_ACCOUNT_TYPE_RESOLVER`, thresholds — ramas `:663-770` código inerte.
- `parsers/config.py:51`: `CachingConfig.enabled=False` (cache nunca implementada).
- `decision/engine.py:20-33`: `dict_code`, `dict_method`, `account_type`, `account_code` se aceptan pero **nunca se usan** en `decide`.
- `_is_code_allowed` / `_is_code_allowed_for_tipo` duplicadas entre pipeline (:617-631) y decision_v2 (:258-263).

---

## 4. FASE 4 — Mapa de dependencias

### 4.1 Módulos críticos (hub central, no se deben tocar sin plan)

```
parser_universal.py (44 imports)          → soporta V1, V2, legacy, DIE, tests
pipeline/homologation_pipeline.py (33)    → clasificador central desplegado
document_context/models.py (13)           → backbone DCE del V2
models/account_balance.py (9)             → data core
knowledge/normalizer.py (6)               → normaliza CMCC
learning/engine.py (4)                    → gold standard
clasificador_codigo_cuenta.py (5)         → único módulo compartido real
config/regex_rules.py                    → REGLAS_REGEX (base de regex)
```

### 4.2 Clasificación de módulos

| Categoría | Módulos |
|---|---|
| **Críticos (producción desplegada)** | `parser_universal.py`, `pipeline/homologation_pipeline.py`, `app_validacion.py`, `learning/engine.py`, `clasificador_codigo_cuenta.py`, `reglas_especiales.py`, `interpreters/balance_interpreter.py`, `adapters/account_adapter.py`, `models/`, `config/`, `gold_standard/`, `semantic/semantic_engine.py`, `pipeline/cmcc_classifier.py`, `shadow/` |
| **Críticos solo en V2 (no desplegado)** | `orchestrator/pipeline_v2.py`, `backend/`, `adapters/{sie,die,parser,kb,decision,validation,review}_adapter`, `document_context/`, `coverage_engine/`, `self_qa_engine/`, `decision_engine/`, `structure_engine/` |
| **Desacoplables** | `decision_v2/` (solo scripts), `knowledge/*` (solo `normalizer.py` llega a prod), `review/` (flag-gated), `semantic/matcher.py` (flag OFF), `pipeline/cmcc_classifier` (flag OFF) |
| **Eliminables sin impacto** | `mappers/`, `observability/`, `extractors/`, `knowledge_discovery/`, `architecture/`, `ui/`, `classification_engine/`, `pipeline/new_pipeline.py`, `src/api/`, `learning/statistics.py`, `semantic/semantic_catalog.py`, `knowledge_base/` (10 clases), `parsers/ParserCore2+analyzer+ocr_engine+factory+integration` |
| **Fusionables** | 4 motores de decisión → 1 · 2 motores CMCC (cmcc_classifier + knowledge/cmcc) → 1 · 48 normalizadores → `core/normalizer` · 2 reglas especiales (reglas_especiales + special_account_rules) → 1 · V1+V2 → 1 · legacy MotorHibridoLocal → V1 |

---

## 5. FASE 5 — Complejidad y ranking

Métricas estáticas (AST: CC total = if/for/while/except/with/boolop/match; CC/fn = CC ÷ funciones).

### Ranking por complejidad ciclomática total (módulos de producción)

| Rank | Módulo | CC | CC/fn | Líneas | Funcs | Clases |
|---|---|---|---|---|---|---|
| 1 | `app_validacion.py` | **277** | 10.26 | 1583 | 27 | 3 |
| 2 | `parser_universal.py` | **152** | 7.24 | 983 | 21 | 6 |
| 3 | `pipeline/homologation_pipeline.py` | **98** | 6.12 | 637 | 16 | 1 |
| 4 | `decision_v2/engine.py` | **77** | 4.53 | 598 | 17 | 1 |
| 5 | `knowledge/build_concept_catalog.py` | 73 | 5.21 | 787 | 14 | 0 |
| 6 | `validate_families.py` | 59 | 6.56 | 345 | 9 | 0 |
| 7 | `run_semantic_shadow.py` | 53 | 5.30 | 544 | 10 | 0 |
| 8 | `parsers/analyzer.py` | 44 | 2.59 | 662 | 17 | 8 |
| 9 | `dataset_manager.py` | 42 | 1.75 | 595 | 24 | 0 |
| 10 | `learning/engine.py` | 34 | 1.62 | 326 | 21 | 1 |
| 11 | `knowledge/knowledge_report.py` | 30 | 4.29 | 239 | 7 | 0 |
| 12 | `reglas_especiales.py` | 28 | 4.00 | 297 | 7 | 2 |
| 13 | `knowledge/normalizer.py` | 21 | 1.75 | 188 | 12 | 2 |
| 14 | `parsers/account_type_resolver.py` | 21 | 2.62 | 240 | 8 | 3 |
| 15 | `semantic/matcher.py` | 21 | 2.62 | 174 | 8 | 1 |
| 16 | `clasificador_codigo_cuenta.py` | 17 | 4.25 | 290 | 4 | 2 |
| 17 | `account_name_normalizer.py` | 15 | 1.25 | 361 | 12 | 1 |
| 18 | `knowledge/unknown_cluster.py` | 15 | 3.00 | 115 | 5 | 0 |

### Análisis por dimensión

| Dimensión | Observación |
|---|---|
| **Líneas** | `app_validacion` 1583, `parser_universal` 983, `build_concept_catalog` 787 — los 3 más grandes concentran el 45% del CC de producción |
| **CC/fn** | Los más difíciles de testear por función: `app_validacion` 10.3, `inspect_pdf` 8.5, `summarize_formats` 7.0, `parser_universal` 7.2 |
| **Acoplamiento** | `homologation_pipeline.py` 16 deps externas; `app_validacion.py` 14; `parser_universal` 17 (hub) |
| **Cohesión** | Baja en `app_validacion` (mezcla UI Streamlit + motor de clasificación + dict + gold), media en `homologation_pipeline` (orquestación + clasificación + filtro + reglas en una clase), alta en `learning/engine` y `semantic/*` |
| **Deuda técnica** | Estimada por: (1) 4 motores de decisión duplicados, (2) 48 normalizadores, (3) 6 copias de regex de código, (4) flags muertos, (5) `decision_v2`→`app_validacion` import invertido, (6) clasificador legacy duplicado |

### Hotspots
1. `app_validacion.py` — monstruo con triple rol (UI + motor + datos).
2. `parser_universal.py` — hub con OCR costoso y flags muertos.
3. `homologation_pipeline.py` — 3 caminos de clasificación dentro de un método.
4. `decision_v2/engine.py` — motor experimental con dependencia invertida.
5. `build_concept_catalog.py` — 787 L sin uso productivo.

---

## 6. FASE 6 — Pipeline V2 propuesto (DISEÑO, NO implementar)

### 6.1 Arquitectura objetivo (solo diseño)

```
┌────────────────────────────────────────────────────────────────┐
│ CORE (único)                                                    │
│  core/normalizer.py      ← normalización única (M3 ya creó)     │
│  core/classifier.py      ← cadena: learning → código → dict →   │
│                             regex (fusiona los 4 motores)       │
│  core/rules.py           ← reglas especiales únicas             │
│  core/decision.py        ← decisión final única (evidencia)     │
└────────────────────────────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────────────────────────────┐
│ pipeline/ (V2 único — orquesta capas por DOCUMENTO)              │
│   ParserAdapter → parse + caché de parseo por hash archivo       │
│   Interpreter  → nature/amount                                   │
│   Classifier   → core/classifier (por cuenta)                    │
│   Adjuster     → core/rules                                      │
│   Verifier     → filtro de tipo (data-driven, no flag muerto)    │
└────────────────────────────────────────────────────────────────┘
   │
   ▼
UI (Streamlit app_validacion) → usa SOLO el pipeline; sin motor propio.
```

### 6.2 Qué desaparecería

| Eliminar | Motivo |
|---|---|
| `MotorHibridoLocal` (legacy) | duplica V1; su pestaña Revisión pasa a usar el pipeline |
| `orchestrator/pipeline_v2.py` + `backend/` + 9 adapters V2 | fusión con V1; el V2 real es el pipeline único |
| `decision_v2/` | experimental, no producción |
| `classification_engine/` | nunca integrado |
| `ui/app.py` | duplica app_validacion |
| `src/api/`, `src/core/orquestador` | stub sin implementar |
| `mappers/`, `observability/`, `extractors/`, `knowledge_discovery/`, `architecture/` | 0 importadores |
| `pipeline/new_pipeline.py` | 0 importadores |
| `semantic/semantic_catalog.py`, `learning/statistics.py`, `knowledge_base/` (10 clases) | solo tests |
| `parsers/ParserCore2`, `analyzer`, `ocr_engine`, `factory`, `integration` | prototipo no conectado |

### 6.3 Qué se fusionaría

| Fusión | Resultado |
|---|---|
| decision/ + decision_engine/ + decision_v2/ + classification_engine/ → `core/decision` | 1 motor de evidencia |
| `pipeline/cmcc_classifier.py` + `knowledge/cmcc.py`+matcher+repository → `core/cmcc` | 1 motor CMCC |
| 48 normalizadores → `core/normalizer` (M3 en curso) | 1 normalización |
| `reglas_especiales.py` + `special_account_rules.py` → `core/rules` | 1 conjunto de reglas (resolver AC.06S vs PAT.10) |
| V1 `homologation_pipeline.py` + V2 `orchestrator/pipeline_v2.py` → `pipeline/` único | 1 orquestador |
| 6 copias de regex de código + 4 de totales + 3 léxicos → `parsers/patterns.py` | 1 fuente de patrones |

### 6.4 Interfaces que cambiarían

- **Entrada**: un único `Pipeline.run(document_path) -> DocumentResult` (hoy: `process` V1, `BackendRunner.run` V2, `MotorHibridoLocal.clasificar`).
- **Método de clasificación**: un `Classifier.classify(name, code, tipo) -> Evidence[]` que devuelve **evidencia múltiple** (en lugar de first-match-wins en 3 lugares).
- **Resultado**: `final_code` derivado de evidencia + reglas (hoy duplicado en 4 motores).
- **Parser**: `Parser.parse(path, *, use_cache=True)` con caché por hash (hoy 2-3 lecturas por documento).

### 6.5 Impacto estimado

| Métrica | Hoy | V2 | Δ |
|---|---|---|---|
| LOC núcleo clasificación | ~17,100 | ~9,000–10,500 | −40% |
| Motores de decisión | 4 | 1 | −3 |
| Normalizadores | 48 | 1 | −47 |
| Pipelines de clasificación | 3 | 1 | −2 |
| Lecturas de PDF por doc | 2–3 | 1 (cacheado) | −60% |
| Paquetes de producción activos | ~20 | ~8 | −60% |

### 6.6 Riesgos

| Riesgo | Mitigación |
|---|---|
| Cambiar resultados (benchmark 2660/2662) | Todo cambio gated por diff de baseline; cada fusión verifica hashes idénticos (proceso M3) |
| Unificación de normalizadores altera match gold/diccionario | Migrar por familias con prueba diferencial sobre corpus (M3 ya lo hizo) |
| Reglas especiales inconsistentes (AC.06S vs PAT.10) | Decidir comportamiento canónico ANTES de fusionar; verificar contra gold |
| V2 desplegado = alto riesgo funcional | Mantener V1 como ground truth; V2 solo shadow hasta igualar exactamente |
| Eliminar paquetes con tests que los ejercitan | Conservar tests como archivo; eliminar solo al mover funcionalidad a core |
| `app_validacion` como monolito UI+motor | Separar UI de motor primero (refactor de bajo riesgo) |

### 6.7 Orden recomendado de migración

1. **Consolidar normalización** (M3: `core/normalizer` ya creado; extender a las 12 familias restantes, una a una con diff).
2. **Extraer motor de clasificación fuera de `app_validacion`** (bajo riesgo, no cambia resultados).
3. **Fusionar `reglas_especiales` + `special_account_rules`** (definir canónico antes).
4. **Unificar diccionario/learning a una cadena única** (eliminar duplicado legacy `MotorHibridoLocal.clasificar`).
5. **Caché de parseo + reducir re-lecturas del PDF** (ganancia de costo sin cambio de resultado).
6. **Unificar motores de decisión en `core/decision`** (high-risk; shadow-first).
7. **Desactivar/eliminar paquetes muertos** (bajo riesgo; conservar tests como referencia).
8. **Fusionar V1+V2 en pipeline único** (último paso, alto riesgo, requiere paridad total).

---

## 7. FASE 7 — Quick Wins y Hotspots

### Quick Wins (bajo riesgo, alto valor)

| # | Acción | Riesgo | Impacto |
|---|---|---|---|
| Q1 | Caché de parseo por hash de archivo (elimina 2-3 re-lecturas por PDF) | Bajo | −60% tiempo parseo |
| Q2 | Añadir `CREATE INDEX` en `gold_standard.normalized` (2 full-scans por cuenta hoy) | Bajo | −N × scan |
| Q3 | Eliminar paquetes muertos (`mappers/`, `observability/`, `extractors/`, `knowledge_discovery/`, `architecture/`, `ui/`, `src/api/`, `new_pipeline.py`, `statistics.py`, `semantic_catalog.py`) | Bajo | −LOC masivo, −confusión |
| Q4 | Eliminar flags muertos (`ENABLE_DYNAMIC_LAYOUT`, `ENABLE_ACCOUNT_TYPE_RESOLVER`) y ramas inertes `parser_universal.py:663-770` | Bajo | −código inerte |
| Q5 | Separar UI de motor en `app_validacion` (mover motor a `core/`) | Bajo | desbloquea todo lo demás |
| Q6 | Unificar la tabla de fuentes de decisión (eliminar params muertos de `decision.decide`: dict_code, account_type, account_code) | Bajo | −confusión API |

### Cambios de bajo riesgo
- Q1–Q6 (ver arriba) + migración de normalizadores familia-por-familia (proceso M3 ya validado).

### Cambios de alto riesgo
- Unificar motores de decisión (4→1).
- Fusionar pipelines V1+V2.
- Unificar CMCC (cmcc_classifier + knowledge/cmcc).
- Resolver inconsistencia de reglas especiales.

### Estimación de reducción de código
- Eliminación de muertos: ~15–20% del LOC de producción (paquetes muertos completos).
- Fusión de duplicados (motores, normalizadores, regex): −30–40% del núcleo de clasificación (~17K → ~10K).
- **Reducción neta estimada del núcleo: ~40–45%** (más los paquetes muertos eliminados).

### Estimación de reducción de complejidad
- `app_validacion` CC 277 → ~120 (extraído el motor) al separar UI.
- `homologation_pipeline` CC 98 → ~45 (single-path classifier).
- Eliminación de 4 motores de decisión duplicados → −40% CC agregado de decisión.
- **CC agregado del núcleo estimado: −45–55%** tras V2.

---

## 8. Restricciones respetadas

✅ No se modificó ningún archivo. ✅ No se modificó SQL. ✅ No se modificó Learning Engine. ✅ No se modificó Pipeline. ✅ No se modificó CMCC. ✅ No se modificó Semantic. ✅ No se modificó Parser. ✅ No se cambió comportamiento. ✅ Benchmark se mantiene 2660/2662 (99.92%), 2 mismatches, 0 regresiones — solo auditoría.

---

*Métricas estáticas generadas con AST (CC = if/for/while/except/with/boolop/match). Conteo de archivos/LOC con scripts de lectura. Evidencia de imports con grep en todo el repo. Backups de datos previos en `/tmp/baseline_analysis_PRE_M3.json`, `/tmp/m4_metrics.json`.*
