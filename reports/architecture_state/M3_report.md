# M3 Report — Refactor del Normalizador (FASE 1–5)

Fecha: 2026-08-03. Objetivo: introducir `core/normalizer.py` como única implementación base y
migrar consumidores SIN cambio de comportamiento. Benchmark objetivo: 2660/2662 (99.92%),
2 mismatches, 0 regresiones (estado M2).

## Resultado

| Métrica | Pre-M3 (M2) | Post-M3 | Δ |
|---|---|---|---|
| Benchmark (analyze_baseline) | 2660/2662 (99.92%), 2 mismatches | 2660/2662 (99.92%), 2 mismatches | 0 |
| Hash `baseline_analysis.json` | `4ab69c2e…` | `4ab69c2e…` | idéntico |
| Suite pytest completa | 2546 passed, 0 failures | **2557 passed, 0 failures** | +11 (tests core) |
| Comparación diferencial corpus (6 migrados) | — | **17,677/17,677 equivalentes** | 0 diffs |

Cero diferencias funcionales en todos los consumidores migrados. `gold_standard.db` verificado
byte-idéntico al backup M1 (`/tmp/gold_standard_baseline.db`, 348 gold_records, 234 gold_standard)
— la DB quedó en su estado M1 correcto (los 38 registros escritos por pytest en M2 fueron restaurados).

## FASE 1 — Inventario (entregable)

`reports/architecture_state/normalizer_inventory_after_m2.md` — matriz completa de N1–N13 con
comportamiento verificado por sonda real. Corpus de comparación: `/tmp/m3_corpus.json`
(17,655 nombres; 4,875 no-ASCII; 415 con ñ; 45 con ü).

## FASE 2 — `core/normalizer.py` (nuevo)

API exacta:

```python
def normalize(text, remove_accents=True, collapse_spaces=True,
              lowercase=True, remove_symbols=True, preserve_enye=False) -> str
```

- Default = familia NFKD+ASCII (`[^\w\s]`, colapso de espacios) = N7/N10/N11.
- `preserve_enye=True`: conserva ñ literal (cubre variante N1).
- `remove_accents=False, remove_symbols=False`: familia N13 (run_layout_validation).
- `None` → `""`. Test suite propia: `tests/test_core_normalizer.py` (11 tests).

## FASE 3 — Migración (6 consumidores, todos 100% equivalentes)

| Módulo | Función | Nueva llamada |
|---|---|---|
| `analytics/unclassified_analyzer.py:29` | `_normalize_name` | `normalize(name)` |
| `reports/architecture_state/analyze_baseline.py:56` | `normalizar` | `normalize(str(nombre))` |
| `reports/run_pipeline_benchmark.py:50` | `normalizar` | `normalize(nombre)` |
| `reports/run_regex_fallback_benchmark.py:49` | `normalizar` | `normalize(nombre)` |
| `reports/analyze_unknown_pareto.py:58` | `normalizar` | `normalize(nombre)` |
| `reports/run_layout_validation.py:65` | `_normalize_name` | `normalize(n, remove_accents=False, remove_symbols=False)` |

API pública preservada (los nombres de función se conservan): `reports.analyze_unknown_pareto.normalizar`
sigue siendo importable por `reports.analyze_semantic_clusters.py:19,21`; `_normalize_name` sigue
disponible para `test_analytics.py:22` y `analytics/coverage_report.py`, `analytics/dashboard.py`.

Imports huérfanos eliminados: `re`/`unicodedata` en unclassified_analyzer, run_pipeline_benchmark,
run_regex_fallback_benchmark, run_layout_validation; `unicodedata` en analyze_unknown_pareto
(se mantuvo `import re`, usado en patrones de líneas 194+).

## DIFERENCIA FUNCIONAL DETECTADA — N8 NO migrado (regla de detención)

`knowledge/unknown_cluster.normalize_name` (N8) NO es equivalente a `core.normalize` default:

| Input | N8 (original) | core.normalize default |
|---|---|---|
| `CAÑA` | `ca a` | `cana` |
| `Señor` | `se or` | `senor` |
| `ñandú` | `andu` | `nandu` |
| `Übung` | `bung` | `ubung` |
| `a_b` | `ab` | `a_b` |
| `! (!o§N` | `o n` | `on` |

Causas: (1) N8 elimina ñ/ü por `[^a-z0-9\s]` en lugar de convertirlas (NFKD); (2) N8 conserva
`_` no, y aplica el regex de símbolos ANTES del manejo de no-ASCII, de modo que basura OCR
no-ASCII se convierte en espacio separador, mientras `core.normalize` la elimina uniendo tokens.
**Resultado: 1,032/17,677 entradas difieren.** Per regla M3 ("ante cualquier diferencia funcional
se detiene y se reporta"), **N8 permanece intacto** en `knowledge/unknown_cluster.py:23`.

Impacto: `knowledge/unknown_cluster` no forma parte del matching de producción ni del benchmark;
sus consumidores (`knowledge/synonym_detector.py:49,135`, `test_decision_trace.py`) quedan
inmutables. Migrar N8 requiere aprobación explícita para corregir ñ (mejora funcional, no refactor
neutro) — candidata a fase futura.

## FASE 4 — Verificación

- Comparación diferencial por función sobre corpus + edge cases: 6/6 **17,677/17,677 equivalentes**.
- `analyze_baseline.py` re-ejecutado post-migración: salida `baseline_analysis.json` **byte-idéntica**
  (hash `4ab69c2e080e8d88e79c65dfd5fae5af74f094d5`).
- Suite completa: **2557 passed, 0 failures, 5 warnings (2126.33s)** — incluye 11 tests nuevos de
  `test_core_normalizer.py` y todos los previos de M2.

## FASE 5 — Documentos

- `reports/architecture_state/normalizer_inventory_after_m2.md` (FASE 1).
- `reports/architecture_state/M3_report.md` (este archivo).
- `core/normalizer.py`, `core/__init__.py`, `tests/test_core_normalizer.py`.

## No modificado (per regla M3)

`learning/` (exact_match, engine), `pipeline/homologation_pipeline.py:76`, `decision_v2/engine.py:584`,
`app_validacion.py:87`, `account_name_normalizer.py:295`, `knowledge/normalizer.py:96`,
`knowledge_base/cmcc_builder.py:37`, `scripts/*`, `tools/*`, `src/db_repository.py:125`,
`knowledge/unknown_cluster.py:23` (N8, por diferencia funcional), `gold_standard.db`.

## Backup

- `/tmp/baseline_analysis_PRE_M3.json` — checkpoint de salida pre-migración.
- `/tmp/m3_corpus.json` — corpus de comparación.
- `/tmp/m3_pytest_full.log` — log completo de la suite 2557 passed.
