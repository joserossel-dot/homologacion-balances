# LearningEngine

> Archivo: `learning/engine.py` (315 líneas) — clase `LearningEngine`
> Modelos: `learning/models.py` (`CorrectionEntry`, `CorrectionStats`)
> Ayudantes: `learning/exact_match.py` (`normalize_name`),
> `learning/fuzzy_match.py` (`fuzzy_score`)

## Propósito

Capa de "aprendizaje" basada en un **Gold Standard** (SQLite) + una **cola de
correcciones** humanas (JSON). Es la **primera etapa** de la cascada de
clasificación del pipeline V1: si una cuenta ya fue homologada correctamente
antes, se reutiliza ese resultado.

> Aclaración del propio docstring (`learning/engine.py:1-14`): el nombre
> "Learning" es engañoso. **No hay aprendizaje automático ni modificación
> automática del pipeline.** La cola de correcciones es solo infraestructura
> para registrar correcciones humanas.

## Responsabilidad

- **Gold Standard**: dado un nombre de cuenta, buscar en `gold_standard.db`
  (tabla `gold_standard` con columnas `codigo_estandar, nombre_cuenta,
  normalized`) un match exacto o fuzzy del nombre normalizado.
- **Correction Queue**: registrar, listar y estadificar correcciones humanas
  en `learning_queue.json` (raíz del repo por default).

## Clase

### `__init__(db_path="gold_standard.db", queue_path=None)` (`:41-54`)

- `_db_path`, `_queue_path` (default `<repo>/learning_queue.json`), `_queue`
  (cargada en `_load_queue`), `_conn` (SQLite lazy).

### Gold Standard

| Método | Línea | Función |
|---|---|---|
| `best_match(account_name) -> dict` | `:60` | Envuelve `_best_match_impl` con try/except → en fallo devuelve `source="none"`. Nunca lanza. |
| `_best_match_impl(name)` | `:67` | 1) exact match por `normalized` → `source="exact"`, conf 0.98. 2) fuzzy sobre toda la tabla; si `score >= 92` → `source="fuzzy"`, conf `min(0.80 + (score-92)*0.01, 0.97)`. Else `source="none"`. |
| `close()` / `__del__` | `:116-122` | Cierra la conexión SQLite. |

### Correction Queue

| Método | Línea | Función |
|---|---|---|
| `record(account_name, corrected_code, ...) -> CorrectionEntry` | `:140` | Registra una corrección; si existe una con la misma `key`, incrementa `frequency` y actualiza `timestamp`/`reason` en lugar de duplicar. |
| `record_from_decision(account_name, corrected_code, decision, ...)` | `:185` | Igual que `record` pero marca `reviewed=True`, `user="human_reviewer"` y extrae `source_stage`/`original_code` de un dict de decisión. |
| `get_pending()` | `:209` | Entradas `reviewed=False`. |
| `get_by_user(user)` / `get_by_account(name)` | `:212-217` | Filtros. |
| `get_most_frequent(limit=20)` | `:219` | Orden por `frequency` desc. |
| `mark_reviewed(index) -> bool` | `:222` | Marca revisada y guarda. |
| `get_stats() -> CorrectionStats` | `:229` | Totales, cuentas únicas, top correcciones, conteos por usuario/etapa/razón, pendientes. |
| `import_from_disagreements(audit_path, user)` | `:261` | Importa discrepancias "Indefinido (requiere revisión)" de un archivo de auditoría como correcciones pendientes. |

### Modelos

`CorrectionEntry` (de `learning/models.py`): `account_name, corrected_code,
original_code, reason, user, timestamp, source_file, account_code,
source_stage, reviewed, frequency` + `key` + `to_dict()`/`from_dict`.
`CorrectionStats`: `total_entries, unique_accounts, top_corrections, by_user,
by_source_stage, by_reason, pending_review`.

## Salida de `best_match`

Dict con `source` (`"exact" | "fuzzy" | "none"`), `code`, `confidence`,
`matched_name`. En el pipeline (`homologation_pipeline.py:179-184`), si
`source != "none"` la cuenta se clasifica con método
`learning_exact`/`learning_fuzzy` y **retorna** (no continúa la cascada).

## Dependencias

`sqlite3`, `json`, `datetime`, `learning/exact_match.py`,
`learning/fuzzy_match.py`, `learning/models.py`. Sin deps externas de
framework.

## Quién lo utiliza

- `pipeline/homologation_pipeline.py` (LearningEngine en `:39`, `_classify_account`).
- `adapters/kb_adapter.py` (V2: KnowledgeData learning_hits).
- `scripts/` de gold standard.

## Riesgos técnicos

- El lookup fuzzy **recorre toda la tabla** por cada cuenta (`:89-98`) — O(n)
  por cuenta sin índice; puede ser lento con tablas grandes.
- `fuzzy_score` umbral 92 hardcodeado; confianza derivada de la fórmula.
- La cola es un **JSON mutable** en la raíz del repo: riesgo de
  concurrencia/corrupción (se pisa con `json.dump`).
- `__del__` con `close()`: si hay conexión abierta en shutdown, podría
  loguear warning (manejo ya defensivo con try/except en `best_match`).

## Posibles mejoras futuras

- Indexar `normalized` en SQLite y limitar fuzzy a un índice (FTS).
- Mover la cola de correcciones a la BD en lugar de JSON.
- Implementar aprendizaje real (promover correcciones frecuentes al Gold
  Standard con validación).
