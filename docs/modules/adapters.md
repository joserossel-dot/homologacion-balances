# Módulo: Adaptadores (V2)

> **Ubicación**: `adapters/` (9 archivos) + `orchestrator/pipeline_v2.py`

## Propósito

Conectar los módulos del pipeline V2 (SIE, DIE, Parser, KB, Decision,
Validation, Review, Coverage, SelfQA) con el `DocumentContext`, de modo que
cada etapa solo lee/escribe el contexto compartido. Es el pegamento de la
arquitectura orientada a contexto.

## Responsabilidad

- Envolver cada motor (parser, DIE, clasificación, validación, etc.) en una
  clase `run(ctx) -> ctx`.
- Escribir en el `DocumentContext` los datos estructurados
  (`set_metadata`, `set_parser`, `set_knowledge`, `set_validation`,
  `set_prediction`, `set_execution`) y datos custom
  (`set_custom` para reportes).
- Convertir formatos internos (e.g. `CuentaRaw` → `AccountBalance`).

## Los adaptadores

| Adaptador | Archivo | Etapa V2 | Qué escribe |
|---|---|---|---|
| `SIEAdapter` | `sie_adapter.py:12` | SIE | `set_metadata` (company, year, layout, doc_type → IDENTIFIED) + `set_structure` (STRUCTURED) |
| `DIEAdapter` | `die_adapter.py:9` | DIE | `set_prediction` (confidence/coverage/complexity) + custom `die_report` |
| `ParserAdapter` | `parser_adapter.py:11` | Parser | `set_parser` (ParserData, PARSED) + custom `parser_resultado` |
| `KBAdapter` | `kb_adapter.py` | Knowledge | `set_knowledge` (KnowledgeData, CLASSIFIED) + custom `classified`/`ignored`/`kb_elapsed`/`pipeline_v1_result` |
| `DecisionAdapter` | `decision_adapter.py` | Decision | custom `decisions`, `decision_stats`, `decision_conflicts`, `decision_confidence_real`, `decision_coverage_real` |
| `ValidationAdapter` | `validation_adapter.py:11` | Validation | `set_validation` (VALIDATED) + custom `validation_result` |
| `ReviewAdapter` | `review_adapter.py:10` | Review | `set_execution` + `mark_reviewed` (REVIEWED) + custom `review_queue`/`review_count` |
| `CoverageAdapter` | `coverage_engine/coverage_adapter.py` | Coverage | custom `coverage`, `coverage_*`, `coverage_issues`, `weights` |
| `SelfQAAdapter` | `self_qa_engine/self_qa_adapter.py` | SelfQA | custom `self_qa`, `self_qa_*`, `gates`, `issues` |
| `AccountAdapter` | `account_adapter.py:18` | (helper) | `CuentaRaw` → `AccountBalance` |

## Detalle de los adaptadores clave

### `AccountAdapter` (`account_adapter.py:18-77`)

- `from_cuenta_raw(cuenta_raw) -> AccountBalance` (`:21`): mapea
  `origen_columna` → campo de `AccountAmounts` vía `_COLUMN_MAP` (`:8-15`)
  (ACTIVO→assets, PASIVO→liabilities, PERDIDA→losses, GANANCIA→profits,
  DEUDOR→balance_debit, ACREEDOR→balance_credit). Trazabilidad
  `source_line/source_column/raw_text`, `extractor="parser_universal"`,
  `confidence` = `confianza_extraccion`. Warning si `es_total`.
- `to_account_balance` (`:70`): alias.

### `SIEAdapter` (`sie_adapter.py:14-...`)

- `run(ctx)` → `set_metadata(IDENTIFIED)` con `_infer_company`,
  `_infer_year`, `_infer_layout`, `_infer_doc_type` (heurísticas del
  filename) + `set_structure(STRUCTURED)`.

### `ParserAdapter` (`parser_adapter.py:15-55`)

- Excel: `parsear_excel` envuelto en `ResultadoParseo`
  (`FormatoCodigo.SIN_CODIGO`). PDF: `ParserPDF.parsear(path)` con timing.
- Errores → custom `parser_error` (no lanza).
- Escribe `ParserData(selected_parser="ParserPDF", parser_version="1.0.0",
  parser_time, raw_accounts)`.

### `DIEAdapter` (`die_adapter.py:17-46`)

- `DocumentIntelligence.analyze(path)` → custom `die_report` +
  `PredictionData(confidence_expected=confidence.global_score,
  coverage_expected=coverage.global_pct, complexity=recommendation.complexity)`.
- `set_prediction` **no transiciona** el lifecycle (ver
  `docs/architecture/processing_pipeline.md`).

### `KBAdapter` (`kb_adapter.py`)

El adaptador más importante — ver `docs/architecture/processing_pipeline.md`
(sección "Flujo por cuenta en detalle"). Resumen:
- Reusa `HomologationPipeline._classify_account` (`:110`).
- `set_knowledge(KnowledgeData(cmcc_matches, learning_hits,
  dictionary_matches))` → CLASSIFIED.
- `pipeline_v1_result` para compatibilidad V1 (`:76`).

### `DecisionAdapter` (`decision_adapter.py:20-38`)

`EvidenceCollector.collect_all(ctx)` → `_determine_decision_type`
(`:87-106`) → REJECT/MANUAL_REVIEW/LEARNING/CONTINUE/STRESS. Ver
`docs/architecture/processing_pipeline.md`.

### `ValidationAdapter` (`validation_adapter.py:15-43`)

`BalanceValidator(tolerance_pct=1.0).validate(...)` →
`ValidationData(integrity, subtotal_validation, equation_validation,
missing_accounts)` + custom `validation_result`. Nota: raw accounts se
serializan con fallback `{codigo, nombre}` (los `CuentaRaw` no tienen
`to_dict()`).

## Entradas

- `DocumentContext` con datos de la etapa anterior.

## Salidas

- `DocumentContext` mutado (estado + customs). El pipeline encadena
  `adapter.run(ctx)` en orden.

## Dependencias

`document_context` (context + models), `parser_universal`, `models/`,
`pipeline.homologation_pipeline`, `validation.balance_validator`,
`document_intelligence`, `coverage_engine`, `self_qa_engine`.

## Feature flags

- Los adaptadores no tienen flags propios; heredan el comportamiento de los
  motores que envuelven (p.ej. KBAdapter usa defaults de `CMCCFeatureFlags`).

## Objetos clave

`AccountAdapter`, `SIEAdapter`, `DIEAdapter`, `ParserAdapter`, `KBAdapter`,
`DecisionAdapter`, `ValidationAdapter`, `ReviewAdapter`.

## Relaciones

- `orchestrator/pipeline_v2.py:41-55` encadena todos los adaptadores.
- `backend/runner.py` → `HomologationPipelineV2`.
- `run_pipeline_v2.py` (CLI).

## Riesgos

1. **`AccountBalance` sin `to_dict()` en `CuentaRaw`**: `ValidationAdapter`
   usa un fallback que pierde `origen_columna`, `es_total`, montos por
   columna → la validación recibe datos incompletos.
2. `ParserAdapter` marca `parser_version="1.0.0"` fijo.
3. Heurísticas de `SIEAdapter` basadas en filename (frágiles).
4. `KBAdapter` reusa `_classify_account` privado del pipeline V1
   (acoplamiento entre versiones).
5. Adapters muy delgados pero con lógica de decisión dentro (DecisionAdapter)
   — asimetría de responsabilidades.

## Mejoras futuras

- Agregar `to_dict()` a `CuentaRaw` para eliminar fallbacks.
- Versionar `parser_version` desde `ParserPDF`.
- Mover heurísticas de `SIEAdapter` a `DocumentAnalyzer`/DIE.
