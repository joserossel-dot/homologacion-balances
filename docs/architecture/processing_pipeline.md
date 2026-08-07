# Pipeline de Procesamiento

## Pipeline V1 — `HomologationPipeline.process()`

Orquestador clásico. Código: `pipeline/homologation_pipeline.py`.

```
pdf_path (str | Path)
   │
   ▼  extensión
   ├── .xlsx/.xls ──► parsear_excel(path) ──► list[CuentaRaw]
   │                    (envuelto en ResultadoParseo, parser_universal.py:369-378)
   └── otro ──────► self._parser.parsear(path) ──► ResultadoParseo
                        (ParserPDF, parser_universal.py:380)
   │
   ▼  accounts_total = len(resultado.cuentas)
   │
   ▼  por cada CuentaRaw:
   │     1. AccountAdapter.from_cuenta_raw(cr) ──► AccountBalance      (:422)
   │     2. BalanceInterpreter(ab) ──► nature + classification_amount  (:423-425)
   │     3. AccountTypeResolver.resolve(origen_columna, codigo) ──► tipo (:427-431)
   │     4. si classification_amount es None → ignored["movement_only"] (:435-441)
   │     5. _classify_account(account_code, account_name, tipo)        (:444)
   │           (ver flujo de clasificación abajo)
   │     6. AccountTypeFilter (flag) → demote a unclassified si conflicto (:450-458)
   │     7. contadores (regex_hits, semantic_matcher_hits, decision_*)
   │     8. CMCC shadow / review queue (flags)                         (:481-515)
   │     9. SemanticEngine.interpret(ab) ──► semantic_result (reporte) (:517)
   │    10. ProcesadorReglasEspeciales.aplicar(...) ──► final_code     (:535-545)
   │    11. classified.append({...})                                   (:550-566)
   │
   ▼
summary dict (574-606):
   accounts_total, accounts_classified, accounts_ignored,
   accounts_without_dictionary_match, learning_hits/exact/fuzzy,
   fallback_classifier, semantic_total/matches/unknown/confidence_avg,
   regex_hits, semantic_matcher_hits, decision_engine_*,
   cmcc_shadow_hits, cmcc_production_hits, cmcc_review_queue,
   tipo_filtered, cmcc_feature_flags, elapsed_seconds,
   classified, ignored
```

### Flujo de clasificación por cuenta (`_classify_account`, `:175-266`)

```
account_code + account_name + account_tipo
   │
   ▼ 1. LearningEngine.best_match(name)  [Gold Standard, siempre activo]
   │      si source != "none" → method=learning_{exact|fuzzy}, RETURN
   │
   ▼ 2. CMCC (si ENABLE_CMCC): cmcc_score = CMCCClassifier.classify(name)
   │
   ▼ 3. CMCC producción (si ENABLE_CMCC_PRODUCTION y score >= THRESHOLD=0.95)
   │      → usa código CMCC, RETURN
   │
   ▼ 4. DecisionEngine V1 (si ENABLE_DECISION_ENGINE)
   │      → _classify_with_decision_engine (recolecta code/dict/SM/regex),
   │        RESUELVE con 5 reglas; RETURN
   │
   ▼ 5. [default, DE OFF] first-match-wins:
   │      code → dict_exact → dict_fuzzy  (primero que acierte)
   │
   ▼ 6. si None y ENABLE_SEMANTIC_MATCHER:
   │      SemanticMatcher.match(name, tipo) → semantic_tier
   │
   ▼ 7. si None y ENABLE_REGEX_FALLBACK (default ON):
   │      7 patrones regex auditados 100%
   │
   ▼ 8. si None → unclassified (conf 0.0)
   │
   ▼ adjunta cmcc_shadow / _cmcc_score / cmcc_detail
```

### Clasificación con DecisionEngine V1 (`_classify_with_decision_engine`, `:268-347`)

- Recolecta: `_classify_by_code`, `_classify_by_dictionary_exact|fuzzy`,
  `SemanticMatcher.match` (si flag), `_classify_by_regex` (si flag).
- Llama `DecisionEngine.decide(sm_*, regex_*, dict_*, account_type, account_code)`.
- Mapea `decision_source` → método `decision_*`
  (`SM_AND_REGEX_AGREE`→`decision_agree`, `SM_HIGH_CONFIDENCE`→
  `decision_sm_high`, `REGEX_EXACT`→`decision_regex_exact`, `SM_ONLY`→
  `decision_sm_only`, `REGEX_ONLY`→`decision_regex_only`,
  `CONFLICT_UNRESOLVED`→`decision_conflict`, `BOTH_UNKNOWN`→
  `decision_unknown`).
- Confianza desde etiqueta: VERY_HIGH .99 / HIGH .90 / MEDIUM .75 /
  LOW .50 / UNKNOWN 0.

## Pipeline V2 — `HomologationPipelineV2.process()`

Orquestador basado en `DocumentContext` y adapters.
Código: `orchestrator/pipeline_v2.py:41-55`.

```
DocumentContext(source_file=pdf)
   │
   ▼ SIEAdapter     → set_metadata (IDENTIFIED) + set_structure (STRUCTURED)
   ▼ DIEAdapter     → set_prediction + custom "die_report"
   ▼ ParserAdapter  → set_parser (PARSED) + custom "parser_resultado"
   ▼ KBAdapter      → set_knowledge (CLASSIFIED) + custom classified/ignored
   ▼ DecisionAdapter→ custom decisions/decision_stats/decision_conflicts
   ▼ ValidationAdapter→ set_validation (VALIDATED) + custom validation_result
   ▼ ReviewAdapter  → set_execution + mark_reviewed (REVIEWED) + review_queue
   ▼ CoverageAdapter→ custom coverage/coverage_* /coverage_issues/weights
   ▼ SelfQAAdapter  → custom self_qa/self_qa_*/gates/issues
   ▼ ctx.complete(module="pipeline_v2")  → COMPLETED
```

Estados del lifecycle: `NEW → IDENTIFIED → STRUCTURED → PARSED → CLASSIFIED →
VALIDATED → REVIEWED → COMPLETED` (o `FAILED` desde cualquier estado).
`set_prediction` y `set_execution` **no** transicionan
(`document_context/context.py:141-153`, `lifecycle.py:8-18`).

### `process_to_dict()` (`pipeline_v2.py:57-71`)

Devuelve `KBAdapter.extract_v1_summary(ctx)` + `elapsed_seconds_v2`,
`dce_state`, `dce_events`, `dce_snapshots`, `dce_document_id`, `decisions`,
`decision_stats`. Objetivo: compatibilidad de salida con V1.

## Etapa Document Intelligence (dentro de ParserPDF, V1)

```
ParserPDF.parsear(path)
   │
   ▼ validar_archivo (firma %PDF-, tamaño>0)          (parser_universal.py:154-193)
   ▼ _analizar_documento → analyze_document_preview   (:608-626, 866-880)
   │     (≤3 páginas, FormatAnalyzer → FormatSignature,
   │      ExtractorFactory.decide_parser; nunca lanza)
   ▼ _extraer_lineas → texto nativo o OCR             (:628, 882-902)
   │     si sin texto: _ocr_documento (pdftoppm 250dpi + tesseract) (:919-950)
   ▼ normalizar_codigo_ocr                            (:639)
   ▼ detectar_formato_codigo + detectar_separador_miles (:641-647)
   ▼ column_order (4 niveles de prioridad)            (:649-770)
   │     context.layout_hint ≥0.8 → perfil de familia (ENABLE_DYNAMIC_LAYOUT)
   │     → LayoutDetector (ENABLE_DYNAMIC_LAYOUT) → ULTIMAS_COLS fijo
   ▼ parsear_linea por línea (confianza 0.75 OCR / 1.0) (:772-779)
   ▼ AccountTypeResolver (si flag o contexto confiable) (:781-809)
   ▼ _anotar_extractor → resultado.extractor_info     (:823-834, 836-864)
   ▼ ResultadoParseo (nunca lanza; fallos → advertencias)
```

## Flujo por cuenta en detalle (V2 KBAdapter._classify_accounts)

`adapters/kb_adapter.py:80-156`:

```
raw_accounts (de ctx.parser.raw_accounts)
   │
   ▼ por cuenta:
   │   AccountAdapter.from_cuenta_raw → AccountBalance
   │   BalanceInterpreter → nature + classification_amount
   │   AccountTypeResolver.resolve(origen_columna, codigo) → tipo
   │   if classification_amount is None → ignored
   │   HomologationPipeline._classify_account(code, name, tipo)  (:110)
   │   filtro account_type (flag) → demote                 (:116-121)
   │   SemanticEngine.interpret → semantic_result          (:123)
   │   ProcesadorReglasEspeciales.aplicar → final_code     (:124-128)
   │   classified.append({...})
   │
   ▼ set_custom("classified", classified_filtered)
   ▼ set_custom("ignored", ignored)
   ▼ set_custom("kb_elapsed", ...)
   ▼ set_custom("pipeline_v1_result", summary_v1)          (:76)
   ▼ set_knowledge(KnowledgeData(cmcc_matches, learning_hits, dictionary_matches))
```

## Decisiones a nivel documento (DecisionAdapter)

`adapters/decision_adapter.py:20-38`:
- `EvidenceCollector.collect_all(ctx)` recoge evidencia de 5 fuentes
  (parser, knowledge, structure, validation, die).
- Por cada cuenta de `classified`: resolver conflictos, score, explicación,
  y `_determine_decision_type` (`:87-106`):
  - method `ignored` → `REJECT`
  - method `unclassified` → `MANUAL_REVIEW`
  - method `learning_*` → `LEARNING`
  - conflicto CRÍTICO → `MANUAL_REVIEW`
  - confidence ≥ 0.7 y weighted_total ≥ 0.6 → `CONTINUE`
  - confidence ≥ 0.4 → `STRESS`
  - else → `MANUAL_REVIEW`
- Escribe `decisions`, `decision_stats`, `decision_conflicts`,
  `decision_confidence_real`, `decision_coverage_real`.

## Cobertura (CoverageAdapter)

`coverage_engine/coverage_calculator.py:54-107`: 4 coberturas + overall
ponderado:
- **Monetaria** (`monetary_coverage.py`): monto explicado por cuentas
  clasificadas; issue `unexplained_amount` (HIGH <0.8, MEDIUM <0.95).
- **Estructural** (`structural_coverage.py`): presencia de subtotales,
  jerarquía, secciones; issues `inconsistent_subtotal` (CRITICAL) y
  `hierarchy_incomplete` (MEDIUM).
- **Semántica** (`semantic_coverage.py`): known/learning/kb/unknown por
  familia; cov = known/total.
- **Documental** (`document_coverage.py`): secciones del documento
  (N/A/OK/PRESENT/MISSING); issues `section_missing` (HIGH),
  `section_incorrect` (MEDIUM).

## SelfQA (SelfQAAdapter)

`self_qa_engine/self_qa_adapter.py:37-126`: gates → riesgo → confianza →
issues → aprobación → recomendaciones.
- **Gates** (`quality_gate.py`): monetary .95, structural .85, semantic .80,
  document .90, decision_confidence .70, validation_integrity .80,
  parser_success .50, structure_valid .50, knowledge_presence .30,
  die_confidence .50.
- **Cadena de aprobación** (`approval_engine.py:104-182`):
  FAILED → REJECTED → STRESS → LEARNING → APPROVED →
  APPROVED_WITH_WARNINGS → MANUAL_REVIEW.

## Validación (ValidationAdapter)

`adapters/validation_adapter.py:15-43`: `BalanceValidator(tolerance_pct=1.0)`
produce `ValidationData(integrity, subtotal_validation, equation_validation,
missing_accounts)`. Internamente usa `hierarchy.py`, `subtotal_validator.py`,
`equation_validator.py`, `missing_account_detector.py`, `integrity_score.py`.

## Revisión (ReviewAdapter)

`adapters/review_adapter.py:14-32`: las cuentas con `standard_code is None`
van a `review_queue`; escribe `review_count`, `set_execution` y
`mark_reviewed`. Nota: la persistencia en `review.db` no está implementada
(solo se guarda `db_path` en `__init__`).
