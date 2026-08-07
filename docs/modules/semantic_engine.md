# Módulo: Motor Semántico

> **Ubicación**: `semantic/`

## Propósito

Entender el **significado** de los nombres de cuentas contables, más allá de
la coincidencia de código, para aportar metadata semántica y —en el
`SemanticMatcher`— proponer códigos homologados a partir de conceptos.

## Responsabilidad

Dos componentes con responsabilidades distintas:

1. **`SemanticEngine`**: anotar la cuenta con metadata semántica (tipo,
   estado financiero, naturaleza, presentación, lado, categoría padre) vía
   reglas de contexto por keywords.
2. **`SemanticMatcher`**: matchear el nombre de la cuenta contra un catálogo
   de conceptos (`knowledge/concept_catalog.json`) con 6 tiers de matching.

## Componentes

| Archivo | Clase/Función | Líneas | Rol |
|---|---|---|---|
| `semantic_engine.py` | `SemanticEngine` | 30 | Reglas por contexto (ver `docs/reference/SemanticEngine.md`) |
| `semantic_rules.py` | `SemanticRule`, `_context_rule`, `build_rules`, `RULES` | 244 | 10 reglas globales priorizadas |
| `semantic_context.py` | `SemanticContext` | 59 | Contexto (infiere columna y lado del balance) |
| `semantic_account.py` | `SemanticAccount` | 32 | Resultado de metadata |
| `matcher.py` | `SemanticMatcher` | 174 | Matcher de conceptos (6 tiers) |
| `models.py` | `SemanticMatch` | — | Resultado del matcher |
| `normalizer.py` | `SemanticNormalizer` | — | Normalización + raíz léxica |
| `scorer.py` | `Scorer` | — | Scoring de concepto |

## Flujo del `SemanticEngine.interpret`

```
AccountBalance
   ▼ SemanticContext.from_account (infiere source_column, balance_side)
   ▼ por regla (orden de prioridad asc):
   │    _context_rule.evaluate(ctx)
   │      ▼ keywords requeridas (grupos OR, todos requeridos)
   │      ▼ keywords prohibidas
   │      ▼ columna aceptada / naturaleza / lado / prefijo de código
   │      ▼ SemanticAccount(confianza = clamp(0.95 + modifier))
   ▼ primera regla que acierta → RETURN
   ▼ ninguna → SemanticAccount unknown (confidence 0.0)
```

## Flujo del `SemanticMatcher.match` (`matcher.py:46-81`)

```
account_name (+ account_type opcional)
   ▼ normalizar (SemanticNormalizer)
   ▼ root_word (raíz léxica)
   ▼ por cada concepto del catálogo:
   │    Scorer.evaluate_concept(norm, concept, root_word, account_type)
   ▼ mejor match con score >= 0.60 → RETURN SemanticMatch
   ▼ else → SemanticMatch UNKNOWN
```

Tiers (`matcher.py:105-106`): 1 keyword exacto, 2 sinónimo exacto, 3
abreviatura, 4 fuzzy keyword, 5 fuzzy sinónimo, 6 raíz léxica. El
`SemanticMatcher` es **independiente del pipeline** (solo conoce el catálogo,
normalizer y scorer propios).

## Entradas

- `SemanticEngine`: `AccountBalance`.
- `SemanticMatcher`: `account_name` + `account_type` opcional; catálogo
  `knowledge/concept_catalog.json`.

## Salidas

- `SemanticEngine`: `SemanticAccount` (con `to_dict()`).
- `SemanticMatcher`: `SemanticMatch` (con `is_unknown`, `concept_name`,
  `concept_id`, `match_tier`, `score`, `confidence`, `expected_cmcc`).

## Dependencias

- Internas: `semantic/` (account, context, rules, matcher, normalizer,
  scorer, models), `models/` (`AccountBalance`, `AccountNature`).
- Externas: `rapidfuzz` (en scorer de matcher), `json`.

## Feature flags

`SemanticEngine` se ejecuta **siempre** (metadata de reporte). `SemanticMatcher`
solo con `ENABLE_SEMANTIC_MATCHER=True` (default OFF). En `decision_v2/` el
matcher se instancia siempre que exista `concept_catalog.json`.

## Objetos clave

`SemanticAccount`, `SemanticContext`, `SemanticRule`, `SemanticMatch`,
`SemanticNormalizer`, `Scorer`.

## Relaciones

- `HomologationPipeline` (V1): `SemanticEngine.interpret` por cuenta →
  `semantic_result`; `SemanticMatcher.match` en `_classify_account`
  (flag).
- `KBAdapter` (V2): `SemanticEngine.interpret` (`kb_adapter.py:123`).
- `DecisionEngineV2` (benchmark): usa `SemanticMatcher.match` como fuente de
  evidencia (tiers 1/2/4/5/6 con pesos).
- `DecisionEngine` V1: resuelve conflictos SM vs Regex.
- `docs/ADR-001-Semantic-Architecture.md`: diseño de la capa semántica.

## Riesgos

1. **Keywords hardcodeadas en español** (depreciación, iva, vacaciones,
   anticipos) — cobertura limitada a esas categorías.
2. `SemanticEngine` no modifica el código final (solo reporta).
3. `_infer_source_column` depende de `account.amounts` por columna; sin
   montos por columna → `source_column="unknown"` y reglas con
   `acceptable_columns` no aplican.
4. Dos motores "semánticos" con nombres similares (`SemanticEngine` vs
   `SemanticMatcher`) — confusión en la lectura del código.
5. `SemanticMatcher` recorre **todos** los conceptos por cuenta (O(n)).

## Mejoras futuras

- Externalizar reglas y catálogos (JSON/YAML/KB).
- Indexar el catálogo de conceptos (buckets por raíz léxica).
- Conectar `semantic_type` con la cobertura semántica del V2.
- Unificar `SemanticEngine` y `SemanticMatcher` en una API común.
