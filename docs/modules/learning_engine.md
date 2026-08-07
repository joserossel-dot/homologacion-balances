# Módulo: Motor de Aprendizaje

> **Ubicación**: `learning/`

## Propósito

Capa de "memoria" del pipeline: reutilizar homologaciones pasadas (Gold
Standard) y registrar correcciones humanas para análisis posterior. Es la
**primera etapa** de la cascada de clasificación del pipeline V1.

## Responsabilidad

1. **Gold Standard** (`gold_standard.db`): buscar código estándar para un
   nombre de cuenta (exacto o fuzzy). Es la fuente de mayor confianza.
2. **Correction Queue** (`learning_queue.json`): infraestructura para
   registrar correcciones humanas (no aprendizaje automático).

## Componentes

| Archivo | Clase/Función | Líneas | Rol |
|---|---|---|---|
| `engine.py` | `LearningEngine` | 315 | Ver `docs/reference/LearningEngine.md` |
| `exact_match.py` | `normalize_name` | — | Normalización para lookups |
| `fuzzy_match.py` | `fuzzy_score` | — | Score fuzzy (rapidfuzz) |
| `models.py` | `CorrectionEntry`, `CorrectionStats` | — | Modelos de la cola |

## Flujo del Gold Standard (`best_match`, `engine.py:60-109`)

```
account_name
   ▼ normalize_name → norm
   ▼ exact: SELECT ... WHERE normalized = ? → source="exact", conf 0.98
   ▼ fuzzy: recorre toda la tabla, fuzzy_score(norm, row.normalized)
   │    si best_score >= 92 → source="fuzzy",
   │        conf = min(0.80 + (score-92)*0.01, 0.97)
   ▼ si nada → source="none" (code=None, conf 0.0)
```

**Integración en V1** (`homologation_pipeline.py:179-184`): si
`source != "none"` → la cuenta se clasifica con método
`learning_exact`/`learning_fuzzy` y **retorna** (no continúa la cascada).

## Flujo de la Correction Queue (`record`, `engine.py:140-183`)

```
record(account_name, corrected_code, ...)
   ▼ crear CorrectionEntry
   ▼ _find_matching(key) — si existe, frequency++ y actualiza timestamp
   ▼ si no, append
   ▼ _save_queue → json.dump a learning_queue.json
```

- `record_from_decision` (`:185-207`): variante de la UI de revisión; marca
  `reviewed=True`, `user="human_reviewer"`.
- `import_from_disagreements` (`:261-289`): importa discrepancias "requiere
  revisión" de un audit como entradas pendientes.
- `get_stats` (`:229-259`): conteos por usuario/etapa/razón, top 10
  correcciones, pendientes.

## Entradas

- Gold Standard: `account_name`.
- Queue: `account_name, corrected_code, original_code, reason, user,
  source_file, account_code, source_stage, reviewed`.

## Salidas

- `best_match` → dict `{source, code, confidence, matched_name}`.
- `record` → `CorrectionEntry`.
- `get_stats` → `CorrectionStats`.
- Archivos: `gold_standard.db` (lectura), `learning_queue.json` (lectura/
  escritura).

## Dependencias

`sqlite3`, `json`, `datetime`, `collections.Counter`,
`learning/exact_match.py`, `learning/fuzzy_match.py`, `learning/models.py`.
Sin deps externas de framework (rapidfuzz en fuzzy_match).

## Feature flags

Ninguna propia; el Gold Standard está **siempre activo** (sin flag).

## Objetos clave

`LearningEngine`, `CorrectionEntry`, `CorrectionStats`.

## Relaciones

- V1 `HomologationPipeline` (`_learning_engine`, `:39`): primera etapa de
  `_classify_account`.
- V2 `KBAdapter`: `KnowledgeData(learning_hits)`; también `import_from_disagreements`
  en scripts de auditoría.
- `decision_v2/DecisionEngineV2`: usa `LearningEngine.best_match` como fuente
  `gs_exact`/`gs_fuzzy`.
- Scripts `scripts/` de gold standard (build/import).

## Riesgos

1. **Nombre engañoso**: no aprende automáticamente; no modifica el pipeline
   (explícito en el docstring).
2. Fuzzy recorre toda la tabla por cuenta → O(n) por cuenta.
3. Cola en JSON mutable (concurrencia, corrupción silenciosa — se resetea a
   `[]` si el parse falla).
4. Umbrales hardcodeados: fuzzy ≥92, conf exact 0.98, fórmula de conf fuzzy.
5. `__del__` con `close()`: conexión SQLite manejada por destructor.

## Mejoras futuras

- Indexar `normalized` (FTS) para evitar scans completos.
- Mover cola a BD.
- Aprendizaje real: promover correcciones frecuentes al Gold Standard con
  validación y registrar auditoría.
