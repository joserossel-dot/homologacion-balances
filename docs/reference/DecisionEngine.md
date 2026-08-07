# DecisionEngine

> Archivo: `decision/engine.py` (189 líneas) — clase `DecisionEngine` (`:6`)
> Modelos: `decision/models.py` — `DecisionEvidence`, `DecisionResult`

## Propósito

Resuelve conflictos entre los métodos de clasificación **SemanticMatcher
(SM)** y **RegexFallback (Regex)** cuando ambos producen resultados para la
misma cuenta. Es el motor "V1" de decisión, activado únicamente cuando
`ENABLE_DECISION_ENGINE=True` (default OFF).

> ⚠️ **Coexisten 4 motores de decisión** — este documento cubre
> `decision/` (V1). Los otros son `decision_engine/` (V2, documental, activo
> en el pipeline V2), `decision_v2/` (benchmark, pesos hardcodeados) y
> `classification_engine/` (nuevo Top-N, no integrado). Ver
> `docs/modules/decision_engine.md` y
> `reports/sprint38_architecture_review.md`.

## Responsabilidad

Evaluar 5 reglas en orden sobre la evidencia de SM y Regex y producir un
`DecisionResult` con código final, fuente de decisión, nivel de confianza,
evidencia y si requiere revisión humana.

## Reglas (evaluadas en orden) — `decide()` `decision/engine.py:20-89`

| # | Condición | Resultado | `decision_source` | Confianza |
|---|---|---|---|---|
| — | SM y Regex coinciden | Acepta SM | `SM_AND_REGEX_AGREE` | `VERY_HIGH` |
| 2 | SM score > 0.95 (y Regex distinto) | Acepta SM | `SM_HIGH_CONFIDENCE` | `VERY_HIGH` |
| 3 | Regex **exacta** y SM score < 0.70 | Acepta Regex | `REGEX_EXACT` | `HIGH` |
| — | Solo SM | Acepta SM | `SM_ONLY` | etiqueta por score |
| — | Solo Regex | Acepta Regex | `REGEX_ONLY` | `MEDIUM` |
| 5 | Ninguna regla aplica (conflicto) | `codigo_final=None`, review | `CONFLICT_UNRESOLVED` | `LOW` |
| — | Ningún método clasifica | `codigo_final=None`, review | `BOTH_UNKNOWN` | `UNKNOWN` |

La regla 4 (AccountTypeFilter) se aplica **externamente** en
`homologation_pipeline.py` (demote a unclassified), no dentro del motor.

Nota: `Rule 1` está documentada como regla de coincidencia pero se evalúa en
`_resolve_conflict` (`:107`), no directamente en `decide`.

## Métodos

| Método | Línea | Función |
|---|---|---|
| `decide(...) -> DecisionResult` | `:20` | Punto de entrada. Args: `sm_code, sm_score, sm_tier, sm_confidence, regex_code, regex_method, dict_code, dict_method, account_type, account_code`. |
| `_resolve_conflict(...)` | `:95` | Evalúa reglas 1/2/3/5 cuando ambos métodos dieron resultado. |
| `_confidence_label(score, tier) -> str` | `:179` | `≥0.95 VERY_HIGH`, `≥0.80 HIGH`, `≥0.70 MEDIUM`, else `LOW`, `None → UNKNOWN`. |

`dict_code`/`dict_method`/`account_type`/`account_code` se aceptan como args
pero **no participan** en la lógica del motor (sin uso interno).

## Modelos

### `DecisionEvidence` (`decision/models.py:7-22`)

`rule, details, score_sm, tier_sm, confidence_sm` + `to_dict()`.

### `DecisionResult` (`:25-55`)

`codigo_final, decision_source, confidence, evidence, review_required,
reason` + `to_dict()`.

- `DECISION_SOURCES` (8): `SM_AND_REGEX_AGREE, SM_HIGH_CONFIDENCE,
  REGEX_EXACT, SM_ONLY, REGEX_ONLY, CONFLICT_UNRESOLVED, BOTH_UNKNOWN,
  TYPE_FILTER_REJECTED`.
- `CONFIDENCE_LEVELS` (5): `VERY_HIGH, HIGH, MEDIUM, LOW, UNKNOWN`.

## Salida

`DecisionResult`. En `_classify_with_decision_engine`
(`homologation_pipeline.py:268-347`) el `decision_source` se mapea al método
de clasificación (`decision_agree`, `decision_sm_high`,
`decision_regex_exact`, `decision_sm_only`, `decision_regex_only`,
`decision_conflict`, `decision_unknown`) y la confianza se convierte a
numérica vía `_confidence_from_label` (VERY_HIGH .99 / HIGH .90 / MEDIUM
.75 / LOW .50 / UNKNOWN 0).

## Dependencias

Solo `decision/models.py`. Sin dependencias externas ni de framework.

## Quién lo utiliza

- `pipeline/homologation_pipeline.py` (`_classify_with_decision_engine`,
  import diferido `decision.models.DecisionResult`).
- Únicamente si `ENABLE_DECISION_ENGINE=True`.

## Riesgos técnicos

- **Sin estado y sin tests**: la clase es stateless; el motor captura
  excepciones externamente (`homologation_pipeline.py:335-338`) y devuelve
  `CONFLICT_UNRESOLVED` con `review_required=True` en fallo.
- La regla 4 documentada (AccountTypeFilter) no está implementada en el
  motor; depende del caller.
- Solo resuelve SM vs Regex; `dict_*` y `account_type` se ignoran.
- La fuente `TYPE_FILTER_REJECTED` está declarada en el modelo pero el motor
  nunca la produce (la produce el pipeline).

## Posibles mejoras futuras

- Integrar `dict_code`/`account_type` en la resolución de conflictos.
- Implementar la regla 4 dentro del motor.
- Consolidar con `decision_engine/` (V2) y `classification_engine/` (nuevo).
