# COMPONENT_STATUS.md

## Estado de todos los módulos del sistema

Criterios:
- **Construido**: El código existe y es sintácticamente válido
- **Integrado**: Está importado y conectado al flujo principal (`app_validacion.py`, `HomologationPipeline`)
- **Activado**: La funcionalidad está habilitada por defecto (feature flag = True o sin flag)
- **Probado**: Tiene tests automatizados que verifican su comportamiento
- **Certificado**: Tiene validación científica, benchmark o revisión formal

---

| # | Módulo | Archivo(s) | Construido | Integrado | Activado | Probado | Certificado | Notas |
|---|---|---|---|---|---|---|---|---|
| 1 | **app_validacion.py** (UI) | `app_validacion.py` | ✅ | ✅ | ✅ | ❌ | ❌ | 1340 líneas sin tests directos |
| 2 | **ParserPDF** (legacy) | `parser_universal.py` | ✅ | ✅ | ✅ | ❌ | ❌ | 831 líneas, probado solo indirectamente |
| 3 | **ClasificadorCodigo** | `clasificador_codigo_cuenta.py` | ✅ | ✅ | ✅ | ❌ | ❌ | Sin test directo |
| 4 | **ProcesadorReglasEspeciales** | `reglas_especiales.py` | ✅ | ✅ | ✅ | ❌ | ❌ | Reglas D1-D5, sin test |
| 5 | **HomologationPipeline** | `pipeline/homologation_pipeline.py` | ✅ | ✅ | ✅ | ⚠️ Parcial | ❌ | Tests de integración existen |
| 6 | **LearningEngine** | `learning/engine.py` | ✅ | ✅ | ✅ | ✅ (10 tests) | ❌ | Gold Standard exact/fuzzy |
| 7 | **GoldBuilder** | `gold_standard/builder.py` | ✅ | ✅ | ✅ | ⚠️ Parcial | ❌ | |
| 8 | **AccountAdapter** | `adapters/account_adapter.py` | ✅ | ✅ | ✅ | ❌ | ❌ | Mapper simple |
| 9 | **BalanceInterpreter** | `interpreters/balance_interpreter.py` | ✅ | ✅ | ✅ | ❌ | ❌ | |
| 10 | **ShadowLogger** | `shadow/shadow_logger.py` | ✅ | ✅ | ✅ | ❌ | ❌ | Shadow mode default ON |
| 11 | **ExtractorMetadata** | `extractor_metadata.py` | ✅ | ✅ | ✅ | ❌ | ❌ | |
| 12 | **MotorHibridoLocal** | `app_validacion.py` | ✅ | ✅ | ❌ | ❌ | ❌ | Legacy, USE_LEGACY_ENGINE=False |
| 13 | **DecisionEngine (v1)** | `decision/engine.py` | ✅ | ✅ | ✅ | ✅ (tests) | ❌ | Feature-flagged |
| 14 | **RegexFallback** | `pipeline/homologation_pipeline.py` | ✅ | ✅ | ✅ | ❌ | ⚠️ Doc | 7 patrones "auditados" en comentario |
| 15 | **AccountTypeResolver** | `parsers/account_type_resolver.py` | ✅ | ✅ | ❌ | ✅ (36 tests) | ❌ | ENABLE_ACCOUNT_TYPE_RESOLVER=False |
| 16 | **DocumentAnalyzer** | `parsers/analyzer.py` | ✅ | ❌ | ❌ | ✅ (30 tests) | ❌ | No integrado en app/pipeline |
| 17 | **ParserCore2** | `parsers/pdf_parser.py` | ✅ | ❌ | ❌ | ❌ | ❌ | Solo benchmark scripts |
| 18 | **SemanticEngine** | `semantic/semantic_engine.py` | ✅ | ✅ | ✅ | ✅ (test_semantic.py) | ❌ | Siempre ejecutado en pipeline |
| 19 | **SemanticMatcher** | `semantic/matcher.py` | ✅ | ✅ | ❌ | ✅ (test_semantic_matcher.py) | ❌ | Feature-flagged (ENABLE_SEMANTIC_MATCHER) |
| 20 | **SemanticRules** | `semantic/semantic_rules.py` | ✅ | ✅ | ✅ | ❌ | ❌ | 10 reglas, usado por SemanticEngine |
| 21 | **CMCCClassifier** | `pipeline/cmcc_classifier.py` | ✅ | ✅ | ❌ | ✅ (16 tests) | ❌ | Feature-flagged |
| 22 | **ConfidenceEngine (v1)** | `confidence/confidence_engine.py` | ✅ | ❌ | ❌ | ✅ (test_confidence_audit.py) | ❌ | ORPHANED |
| 23 | **ConfidenceEngine (v2)** | `confidence/engine.py` | ✅ | ❌ | ❌ | ✅ (13 tests) | ❌ | ORPHANED |
| 24 | **Evidence** | `evidence/` (6 files) | ✅ | ❌ | ❌ | ✅ (test_evidence.py) | ❌ | ORPHANED |
| 25 | **Explainability** | `explainability/` (5 files) | ✅ | ❌ | ❌ | ✅ (test_decision_trace.py) | ❌ | Solo scripts |
| 26 | **KnowledgeBase** | `knowledge_base/` (9 files) | ✅ | ❌ | ❌ | ✅ (test_knowledge_base.py) | ❌ | ORPHANED |
| 27 | **ScientificValidation** | `scientific_validation/` (5 files) | ✅ | ❌ | ❌ | ✅ (54 tests) | ❌ | Solo scripts |
| 28 | **QualityMonitoring** | `quality_monitoring/` (6 files) | ✅ | ❌ | ❌ | ✅ (test_quality_monitoring.py) | ❌ | Solo scripts |
| 29 | **ReleasePipeline** | `release_pipeline/` (5 files) | ✅ | ❌ | ❌ | ✅ (test_release_pipeline.py) | ❌ | Solo scripts |
| 30 | **ReviewUI** | `review_ui/` (7 files) | ✅ | ❌ | ❌ | ✅ (61 tests) | ❌ | Solo script run_human_review.py |
| 31 | **GoldImport** | `gold_import/` (5 files) | ✅ | ⚠️ Indirecto | ⚠️ | ✅ (test_gold_import.py) | ❌ | Vía GoldBuilder |
| 32 | **SplitAC01** | `split_ac01/` (4 files) | ✅ | ❌ | ❌ | ⚠️ **11 FALLAN** | ❌ | ORPHANED |
| 33 | **DocumentAssessment** | `assessment/` | ✅ | ❌ | ❌ | ✅ (test_document_assessment.py) | ❌ | ORPHANED |
| 34 | **AccountingKnowledge** | `accounting_knowledge/` | ✅ | ❌ | ❌ | ❌ | ❌ | ORPHANED |
| 35 | **DecisionEngineV2** | `decision_v2/` (2 files) | ✅ | ❌ | ❌ | ✅ (tests) | ❌ | ORPHANED |
| 36 | **NewPipeline** | `pipeline/new_pipeline.py` | ✅ | ❌ | ❌ | ❌ | ❌ | **DEAD CODE** |
| 37 | **Evaluation** | `evaluation/homologation_benchmark.py` | ✅ | ❌ | ❌ | ❌ | ❌ | ORPHANED (standalone) |
| 38 | **FastAPI** | `src/api/main.py` | ✅ | ❌ | ❌ | ❌ | ❌ | Entrada independiente |
| 39 | **PipelineOrquestador** | `src/core/orquestador.py` | ✅ | ❌ | ❌ | ✅ (test_orquestador.py) | ❌ | Solo API (46 líneas stub) |
| 40 | **UI MVP** | `ui/app.py` | ✅ | ❌ | ❌ | ❌ | ❌ | Entrada independiente |

---

## Resumen

| Estado | Cantidad | % |
|---|---|---|
| Construido | 40/40 | 100% |
| Integrado (en flujo principal) | 15/40 | 37.5% |
| Activado por defecto | 11/40 | 27.5% |
| Probado (tests automatizados) | 17/40 | 42.5% |
| Certificado (validación formal) | 0/40 | 0% |

---

## Leyenda

| Símbolo | Significado |
|---|---|
| ✅ | Sí / Completo |
| ❌ | No / Ausente |
| ⚠️ | Parcial / Con problemas |
