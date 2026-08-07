# P5.5 — Runtime Observability

> Sprint-1 · Knowledge Manager · Homologación de Balances
> Estado: ✅ Implementado · alcance SOLO observabilidad (sin promociones automáticas)

## Objetivo

Agregar observabilidad completa del runtime para que la app responda:

- ¿Cuántas veces se utilizó el runtime?
- ¿Cuántas veces hizo fallback al gold?
- ¿Qué porcentaje del aprendizaje está siendo usado?
- ¿Qué promociones realmente generan impacto?

## Restricciones respetadas

- **No se modifican**: `gold_standard.db`, benchmark, parser, pipeline, CMCC,
  Semantic, clasificación.
- **RuntimeManager no se modificó**: se reutilizan sus getters existentes
  (`get_runtime_statistics`, `get_runtime_coverage`, `load_history`).
- **No se promueven registros** y **no se ejecuta benchmark**.
- **No se puebla el runtime**: solo lectura.

## Arquitectura

```
LearningEngine (_metrics, en memoria)  ─┐
                                       ├─► RuntimeStatistics (fuente ÚNICA) ──► UI (Knowledge Manager)
RuntimeManager (getters, SQL interno) ─┘        ▲ "📊 Runtime Analytics"
                                                │
                          no SQL, no sqlite3 desde la UI
```

Nuevos componentes:

| Archivo | Rol |
|---|---|
| `gold_standard/runtime_stats.py` | Objeto `RuntimeStatistics`: agrega uso + eventos + cobertura; calcula derivados e impacto por promoción. |
| `app_validacion.py` | Persiste `runtime_metrics_last` en `session_state` tras procesar; nuevo tab **📊 Runtime Analytics** (`_km_runtime_analytics`). |
| `learning/engine.py` | Añade métricas de uso (solo incrementos; no cambia lógica de resolución). |
| `tests/test_runtime_statistics.py` | Tests del objeto `RuntimeStatistics`. |

`RuntimeStatistics.capture(engine|metrics, runtime, gold_db)` es el único punto
de entrada: agrega métricas de uso del `LearningEngine` (o de un snapshot
persistido) con los eventos y la cobertura del `RuntimeManager`. La UI jamás
ejecuta SQL.

## Métricas

### De uso (LearningEngine, en memoria por sesión de procesamiento)

| Métrica | Descripción |
|---|---|
| `runtime_exact_hits` | Nº de lookups resueltos por runtime exacto. |
| `runtime_fuzzy_hits` | Nº de lookups resueltos por runtime fuzzy. |
| `gold_exact_hits` | Nº de lookups resueltos por gold exacto. |
| `gold_fuzzy_hits` | Nº de lookups resueltos por gold fuzzy. |
| `runtime_miss` | Nº de lookups donde el runtime se consultó y no resolvió. |
| `fallback_to_gold` | Nº de lookups donde el runtime desplegado cedió al gold. |
| `total_requests` | Total de `best_match` invocados. |
| `runtime_hits_by_code` | Conteo de hits del runtime agrupado por código estándar (permite impacto). |

### De eventos (RuntimeManager)

`promotion_count`, `rollback_count`, `reject_count` (derivados de
`promotion_history`, nunca se borran).

### Derivadas (computadas por `RuntimeStatistics`)

- `runtime_usage_pct` / `gold_usage_pct` / `learning_used_pct`: % resuelto por
  cada capa respecto a `total_requests`.
- `fallback_pct`: % de fallbacks.
- `runtime_catalog_coverage_pct`: cobertura del catálogo runtime vs gold (del
  `get_runtime_coverage` existente).
- `impactful_promotions` / `promotion_impact`: promociones cuyo código fue
  realmente usado por el runtime.

## Nuevos tests

Todos pasan sobre DBs temporales y un `LearningEngine` en memoria. Cubren:

- Presencia de las métricas mínimas requeridas (exact/fuzzy/miss/fallback/
  rollback/reject/promotion).
- `capture` desde snapshot de métricas y desde engine.
- Derivados de cobertura (runtime/gold/uso/aprendizaje) y % fallback.
- Conteo de `fallback_to_gold` tras un miss de runtime.
- Eventos y cobertura desde `RuntimeManager` (promote/reject/rollback).
- Impacto por promoción (promoción → código → hits reales).
- Lectura sin crear la DB runtime.
- Benchmark protegido saltado si `gold_standard.db` no existe; si existe,
  verifica byte-identidad tras la captura.

`test_ui_knowledge_manager.py` se amplió: `_km_runtime_analytics` se incluye en
`KM_FUNCTIONS` y pasa la verificación de **ausencia de SQL/SQLite en la UI**.

Resultado: `test_runtime_statistics.py` → **10 passed**; suite M3–P5 → **107 passed**.

## Impacto

- La UI ahora responde las 4 preguntas del objetivo en el tab **📊 Runtime Analytics**.
- Impacto de promociones: se marca como *impactful* toda promoción cuyo código
  estándar fue usado por hits del runtime, permitiendo detectar qué
  conocimiento adoptado realmente se emplea.
- Se derivan percentiles de uso (aprendizaje empleado, cobertura runtime/gold)
  sin exponer SQL a la UI.
- Cambio aditivo y aislado: `LearningEngine` solo acumula contadores nuevos;
  `RuntimeManager` intacto; ninguna capa de clasificación/pipeline se toca.

## Confirmación de benchmark intacto

- `gold_standard.db` (trackeada en git): **sin cambios** (`git status` limpio;
  `mtime` previo a la sesión).
- Evidencia congelada del benchmark `reports/architecture_state/baseline_analysis.json`:
  **2660/2662 match**, 2 mismatches (`DISPONIBLE` AC.01 vs PC.02) — intacta.
- `gold_standard_runtime.db` **no existe**: las lecturas de observabilidad no la crean.
- No se ejecutó benchmark ni promoción alguna.
- Cero regresiones: todas los archivos de tests que importan `learning.engine`,
  `app_validacion`, `runtime_manager` o `runtime_stats` pasan
  (262 casos verificados).

## Limitaciones y alcance

- Las métricas de uso son **por sesión de procesamiento actual** (en memoria,
  persistidas a `session_state`); reflejan el último lote procesado, no un
  histórico entre reinicios.
- La sección es **solo observabilidad**: no recolecta, no promueve, no revierte.
- El impacto por promoción depende de que el runtime sea efectivamente usado
  durante el procesamiento de balances.