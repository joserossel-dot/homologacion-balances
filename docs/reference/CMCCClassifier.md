# CMCCClassifier

> Archivo: `pipeline/cmcc_classifier.py` (87 líneas) — clase `CMCCClassifier`
> Datos: `knowledge/cmcc.json` (catálogo de conceptos homologados, con
> `nombre`, `codigo`, `sinonimos`, `abreviaturas`, `variantes`)
> Normalización: `knowledge/normalizer.py` (`Normalizer`)

## Propósito

Clasifica un nombre de cuenta contra el **Catálogo Maestro CMCC** (Chile)
usando matching difuso ponderado (rapidfuzz). Es la fuente de homologación de
"más alto nivel" del proyecto, pero **está desactivada por defecto**
(`ENABLE_CMCC=False`).

## Responsabilidad

Dado un nombre de cuenta, encontrar el concepto CMCC más parecido y devolver
su código, score de similitud y evidencia (variante que hizo match).

## Clase

### `__init__(cmcc_path="knowledge/cmcc.json")` (`:12-18`)

- `normalizer = Normalizer()`, carga `cmcc.json`, construye
  `_concepts_by_name` (nombre → concepto) y `_all_variants` (lista plana de
  `(variante_normalizada, variante_original, codigo, fuente)`).
- Fuentes de variantes (`_build_index`, `:20-33`): `nombre`, `sinonimo`,
  `abreviatura`, `variante`.

### `classify(account_name) -> dict` (`:35-72`)

```
name
 │ ▼ normalizar (Normalizer)
 │ ▼ si vacío → {code: None, method: "none", evidence: "empty_input|empty_after_normalization"}
 │ ▼ por cada variante: score = _score(norm_input, norm_variant)
 │     si score > best["score"] → actualiza best
 │ ▼ si best["score"] > 0 → devuelve best
 │ else → {code: None, method: "cmcc_none", evidence: ["no_match"]}
```

`_score(a, b)` (`:74-84`): pondera
`exact*0.4 + token_sort*0.3 + token_set*0.2 + partial*0.1` (rapidfuzz).
Match exacto → score 1.0.

### `classify_batch(names) -> list[dict]` (`:86`)

Itera `classify` sobre la lista.

## Salida de `classify`

```
{score: float (0-1), code: str|None, concept: str|None,
 matched_variant: str|None, matched_concept: str|None,
 method: "cmcc_<fuente>|cmcc_none|none", evidence: list[str]}
```

## Cómo se integra en el pipeline (V1)

En `homologation_pipeline.py` (`_classify_account`, ver
`docs/reference/HomologationPipeline.md`):

- Solo si `ENABLE_CMCC=True`: `cmcc_score = cmcc_classifier.classify(name)`.
- Si `ENABLE_CMCC_PRODUCTION=True` y `score >= CMCC_THRESHOLD (0.95)` →
  usa el código CMCC y **retorna** (fuente `cmcc_production`).
- Si no, guarda `cmcc_shadow`/`cmcc_detail`/`_cmcc_score` en la cuenta
  (shadow mode, default `ENABLE_CMCC_SHADOW=True`).
- Entre `CMCC_REVIEW_THRESHOLD (0.85)` y el umbral de producción, o con
  score == 1.0 en cuentas UNKNOWN, puede ir a la cola de revisión CMCC
  (`ENABLE_CMCC_REVIEW_PIPELINE`, default OFF).
- Si `ENABLE_ACCOUNT_TYPE_FILTER=True`, el código CMCC se valida contra el
  tipo resuelto; contradicción → demote a unclassified.

## Dependencias

`rapidfuzz`, `knowledge/normalizer.py`. Sin otras deps internas.

## Quién lo utiliza

- `pipeline/homologation_pipeline.py` (`_cmcc_classifier`, `:42`).
- `docs/cmcc_production_design.md`, `cmcc_production_sequence.md`,
  `cmcc_rollout_plan.md` documentan el diseño de producción/rollout.

## Riesgos técnicos

- El `_build_index` hace un lookup lineal `next(c for c in self.concepts ...)`
  por cada variante mejorada (`:56-64`) — O(concepts) por variante; el
  clasificador es cuadrático en tamaño de catálogo.
- Los thresholds (0.95 producción / 0.85 revisión) viven en los flags, no en
  el clasificador.
- Sin límite de scoring mínimo interno: cualquier score > 0 devuelve match
  (el pipeline filtra por umbrales).
- `classify` no distingue variantes ambiguas entre conceptos distintos con
  mismo código.

## Posibles mejoras futuras

- Indexar variantes por bucket/trie en lugar de scan lineal.
- Mover umbrales a configuración del clasificador.
- Devolver Top-N candidatos (alineado con `classification_engine/`).
