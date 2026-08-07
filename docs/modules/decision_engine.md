# Módulo: Motor de Decisión

> **Ubicación**: `decision/`, `decision_engine/`, `decision_v2/`,
> `classification_engine/`

## Propósito

Resolver la clasificación de una cuenta cuando **múltiples métodos producen
códigos diferentes**, decidiendo cuál usar (o si requiere revisión humana), y
—en la versión nueva— generar un ranking Top-N con score y explicación.

> ⚠️ **Coexisten 4 motores** (herencia de los Sprints 1, 37, 38). Solo
> `decision_engine/` (V2) está activo en el pipeline V2. Ver
> `reports/sprint38_architecture_review.md` para el análisis comparativo.

## Los 4 motores

| Motor | Ruta | Estado | Lógica |
|---|---|---|---|
| **V1** | `decision/` | OFF (flag `ENABLE_DECISION_ENGINE`) | 5 reglas SM vs Regex. Ver `docs/reference/DecisionEngine.md` |
| **V2 (documental)** | `decision_engine/` | **Activo en pipeline V2** | Evidencia de 5 módulos + score + conflictos + confianza ponderada |
| **Benchmark V2** | `decision_v2/` | No conectado | Pesos hardcodeados `_EVIDENCE_WEIGHTS` + consenso/prioridad/tie-break |
| **Nuevo Top-N** | `classification_engine/` | No integrado (Sprint 39) | Generación → scoring → explicación, ranking Top-N |

## `decision_engine/` (V2, activo) — flujo

### `EvidenceAggregator.aggregate(ctx) -> dict` (`aggregator.py:21-31`)

```
DocumentContext
   ▼ EvidenceCollector.collect_all(ctx) — evidencia de 5 fuentes
   │    parser, knowledge, structure, validation, die
   ▼ ConflictResolver.resolve(evidence) → list[DecisionConflict]
   ▼ Scorer.compute(evidence, ctx) → DecisionScore (5 métricas)
   ▼ ConfidenceCalculator.compute(evidence, ctx) → float
   ▼ {evidence, conflicts, score, confidence}
```

### `EvidenceCollector` (`evidence.py:11-146`)

5 fuentes con confianza por campo:
- **parser**: `selected_parser` (0.9), `total_raw` (0.8), `accounts` (0.85).
- **knowledge**: `total_matches` (0.9), `learning_hits` (0.95),
  `dictionary_matches` (0.85).
- **structure**: `family` (0.7), `template` (0.75), `layout` (0.6).
- **validation**: `has_integrity` (0.8/0.0), `errors` (0.0), `warnings` (0.3).
- **die**: `die_report` (0.5), `confidence_expected`/`coverage_expected`
  (igual a la predicción).

### `Scorer.compute` (`scorer.py:10-75`) → `DecisionScore`

| Métrica | Fórmula |
|---|---|
| `confidence` | media de `e.confidence > 0` |
| `coverage` | `len(classified) / (classified+ignored)` del ctx |
| `evidence_quality` | `(high*1.0 + medium*0.5)/total` (high ≥0.8, medium 0.4-0.8) |
| `consistency` | `1 - min(std_dev, 1)` de las confianzas |
| `learning_weight` | `min((learning_hits+dict_matches)/20, 1)` |

### `ConflictResolver` (`conflict_resolver.py:8-55`)

Agrupa por `field`; pares de evidencia de **distinta fuente** con `value`
distinto → severidad CRITICAL (ambas conf ≥0.8), HIGH (ambas ≥0.6), MEDIUM,
NONE.

### `ConfidenceCalculator` (`confidence.py:10-63`)

Pesos default `parser .30, knowledge .30, validation .20, structure .10,
die .10`; score por módulo = media de confianzas; resultado = suma ponderada
normalizada. Advertencia (no error) si los pesos no suman 1.

### Modelos (`decision_engine/models.py`)

`DecisionType`, `ConflictSeverity`, `DecisionEvidence` (`source, field,
value, confidence, detail`), `DecisionConflict`, `DecisionScore`,
`DecisionExplanation`, `DecisionStatistics`, `Decision`.

## `decision_v2/` (benchmark, no conectado) — `DecisionEngineV2.classify` (`engine.py:82-102`)

```
classify(name, code, tipo)
   ▼ _collect_evidence: Gold Standard → code → dict_exact → dict_fuzzy →
   │    SemanticMatcher (tiers) → regex   (cada uno con peso _EVIDENCE_WEIGHTS)
   ▼ _apply_type_filter (prefijos ANC/AC/PNC/PC/PAT/ER vs tipo)
   ▼ si sin evidencia → ALL_FILTERED
   ▼ _decide(evidence):
   │    R1: SM tier 1-2 siempre gana
   │    CONSENSUS_N: grupos ≥2, bonus 1.15/1.25 según N
   │    PRIORITY: matriz _source_rank
   │    SOLO: un único clasificador (×0.90, tier6 capped 0.50)
   │    TB1/TB2/TB3: tie-break por score → precisión histórica → tipo
   │    TB5: HUMAN_REVIEW
```

Pesos (`_EVIDENCE_WEIGHTS`, `:27-39`): code .50, dict_exact .90, dict_fuzzy
.60, sm_tier_1 1.00, sm_tier_2 .95, sm_tier_4 .60, sm_tier_5 .50, sm_tier_6
.40, regex .85, gs_exact .90, gs_fuzzy .60. `_PRECISION_ORDER` (`:41-44`):
regex > dict_exact > gs_exact > code > dict_fuzzy > gs_fuzzy > sm tiers.

## `classification_engine/` (nuevo Top-N, Sprint 39)

### `DecisionEngine.classify(name, code, context) -> TopNResult` (`engine.py:64-108`)

```
name/code
   ▼ CandidateGenerator.generate → list[Candidate]  (candidate.py)
   │    capas: code, catalog_exact, synonyms_exact, synonyms_fuzzy,
   │    special_rules (decisión) + refuerzos
   ▼ Scorer.score(candidates) → list[RankedCandidate]  (score.py:187)
   │    weights configurables vía WeightConfig (score.py:75)
   ▼ _ensure_non_empty → ranking con UNKNOWN si vacío
   ▼ rank[:top_n]
   ▼ Explainer.explain(ranked, candidates, name)  (explainer.py)
   ▼ TopNResult(top_n, confidence, decision_source, explanation, extra)
```

- `_DECISION_LAYERS` (`:31-34`): capas que "deciden" (proponen código);
  `decision_source` = capa con mayor contribución `weight*score` (`:127-137`).
- Candidato UNKNOWN garantizado: **nunca devuelve ranking vacío**.
- Integración al pipeline **pendiente para Sprint 39** (el docstring lo
  declara explícitamente).

### Modelos (`classification_engine/decision.py`)

`EvidenceSource` (:34), `Candidate` (:84), `RankedCandidate` (:120),
`ClassificationExplanation` (:154), `TopNResult` (:172),
`DocumentProcessingContextAdapter` (:246).

## Entradas y salidas

- **V1**: `(sm_code, sm_score, sm_tier, sm_confidence, regex_code,
  regex_method, dict_*, account_type, account_code)` → `DecisionResult`.
- **V2**: `DocumentContext` → `{evidence, conflicts, score, confidence}`.
- **Benchmark V2**: `(account_name, account_code, account_tipo)` →
  `DecisionResultV2` (`final_code, final_score, confidence_label,
  review_required, decision_source, evidence, consensus_count,
  conflict_count, explanation`).
- **Top-N**: `(account_name, account_code, context)` → `TopNResult`.

## Dependencias

- `decision_engine/`: `document_context` (DocumentContext y modelos
  `DocumentMetadata, ParserData, KnowledgeData, ValidationData, StructureData`).
- `decision_v2/`: `rapidfuzz`, `clasificador_codigo_cuenta`,
  `learning.engine`, `semantic.matcher`, `app_validacion` (`REGLAS_REGEX`).
- `decision/`: solo `decision.models`.
- `classification_engine/`: `classification_engine` interno.

## Riesgos

1. **4 motores coexistiendo**: mantenimiento y ambigüedad de "qué motor
   decide". Solo V2 está activo; el resto es código muerto/de referencia.
2. `decision_v2` importa `REGLAS_REGEX` **desde `app_validacion`** (módulo de
   UI) — acoplamiento inverso grave.
3. Pesos hardcodeados en `decision_v2` (`_EVIDENCE_WEIGHTS`) y default en
   `decision_engine` (`DEFAULT_WEIGHTS`); no parametrizables desde config.
4. `_apply_type_filter` en `decision_v2` usa `ev.source` como tipo en TB-3
   (probable bug: debería usar `account_tipo`).
5. `classification_engine` sin consumidores (no integrado).

## Mejoras futuras

- Consolidar los 4 motores en uno solo (recomendado: el nuevo Top-N con
  `WeightConfig` parametrizable).
- Mover pesos a configuración.
- Romper el import `decision_v2 → app_validacion`.
- Integrar `classification_engine` en el pipeline (Sprint 39).
