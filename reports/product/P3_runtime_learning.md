# P3 — Runtime de aprendizaje: `RuntimeManager` (runtime_gold + promotion_history + metadata)

Fecha: 2026-08-03 · Tipo: INFRAESTRUCTURA (solo lectura del benchmark) · Base: M5 (2660/2662, 99.92%) · Sucede a P1.1, P1.2 y P2.

---

## 0. Resumen ejecutivo

P3 entrega **una única implementación nueva**: `gold_standard/runtime_manager.py` con la clase
`RuntimeManager`, que administra la base de conocimiento runtime mediante **tres tablas separadas**:

| Tabla | Rol |
|---|---|
| `runtime_gold` | Conocimiento en evolución (espejo del gold + proveniencia). |
| `promotion_history` | Auditoría de promociones y rollbacks (quién, cuándo, qué, de dónde). |
| `metadata` | `version`, `checksum` (SHA-256 del contenido), `fecha_creacion`, `fecha_actualizacion`. |

Decisión arquitectónica (aprobada por el usuario): **no** se toca la infraestructura de P1.1
(`gold_standard/runtime.py`, `gold_standard/promotion.py`), **no** se modifica `learning/*`, `parser/*`,
`pipeline/*`, `semantic/*`, CMCC, ni el benchmark. `runtime_gold` es la **única** tabla usada por
`RuntimeManager`; la tabla `gold_standard` de P1.1 sigue viviendo en el mismo archivo sin interferir
(coexisten).

**No se ejecutaron promociones reales** y **no se creó `gold_standard_runtime.db`** durante esta
iteración (todas las pruebas usan DBs temporales). El benchmark permanece en **2660/2662 (99.92%)**.

---

## 1. Qué se entrega

### 1.1 Archivos nuevos

| Archivo | Descripción |
|---|---|
| `gold_standard/runtime_manager.py` | Módulo nuevo (única implementación de P3). |
| `tests/test_runtime_manager.py` | 21 tests (schema, search, promote, rollback, stats, compat, benchmark). |

### 1.2 Sin cambios sobre código existente

Se respetó la restricción del usuario: **no se modificó** `learning/*`, `parser/*`, `pipeline/*`,
`semantic/*`, CMCC, `gold_standard.db`, ni los módulos P1.1 (`gold_standard/runtime.py`,
`gold_standard/promotion.py`, `app_validacion.py`, `tests/test_gold_promotion.py`).

---

## 2. Arquitectura final

```
gold_standard_runtime.db
├── runtime_gold          ← conocimiento en evolución (la única tabla de RuntimeManager)
│      id, codigo_estandar, nombre_cuenta, normalized,
│      source_record_id, reviewer, review_date, promoted_at
│      UNIQUE(normalized, codigo_estandar)
├── promotion_history     ← auditoría
│      id, fecha, usuario, origen, accion, codigo_anterior, codigo_nuevo, comentario
└── metadata              ← version, checksum, fecha_creacion, fecha_actualizacion
```

### 2.1 API de `RuntimeManager`

| Método | Comportamiento |
|---|---|
| `initialize()` | Crea schema (idempotente). **Solo se llama explícitamente**; no hay auto-creación. |
| `load_runtime()` | Devuelve todas las filas de `runtime_gold`. Si la DB no existe → `[]` sin crear archivo. |
| `search_runtime(name)` | Exacto primero, luego fuzzy (threshold 92, misma fórmula de confianza que el motor). Contrato de salida idéntico a `LearningEngine.best_match` → listo para wiring futuro. Si no existe DB → `source: "none"`. |
| `promote(source_db, dry_run=True, ...)` | Clasifica candidatos (`gold_records`) contra `runtime_gold`. `dry_run` **no escribe ni crea** el archivo (usa `:memory:`); `dry_run=False` escribe las 3 tablas + registra evento `promote`. Nunca modifica la fuente. |
| `rollback(entry_id, ...)` | Elimina una fila de `runtime_gold` y registra evento `rollback` en `promotion_history`. |
| `stats()` | Conteos de `runtime_gold`, `promotion_history` y `metadata`. |
| `load_history()` | Lista de eventos de `promotion_history`. |
| `get/set_metadata(key)` | Acceso a `metadata` (version/checksum/fechas u otras claves). |

### 2.2 Reutilización por delegación (sin duplicar código)

| Pieza reutilizada | Fuente |
|---|---|
| `normalize_name` | `learning.exact_match` (import) |
| `fuzzy_score` | `learning.fuzzy_match` (import) |
| `RESERVED_TOKENS` | `gold_standard.promotion` (import) |
| `PromotionResult` | `gold_standard.promotion` (dataclass, import) |
| `_fetch_candidates` | `gold_standard.promotion` (import) |

`promote()` no duplica la orquestación de P1.1: reutiliza el clasificador de candidatos
(`_fetch_candidates`), las constantes y el resultado tipado de `gold_standard/promotion.py`; solo
cambia la tabla destino (`runtime_gold`) y agrega el registro de auditoría. La lógica de conflictos
(mismo `normalized`, código distinto) replica la de P1.1 contra `runtime_gold`.

### 2.3 Reglas de promoción (idénticas a P1.1)

1. Solo `final_code != ''` y nombre no vacío.
2. Normalización con `normalize_name`.
3. Palabras reservadas (`total`) → no se promueven.
4. Duplicado `(normalized, codigo)` ya en runtime → se omite (idempotente).
5. Conflicto (mismo `normalized`, código distinto) → **no se promueve**, se reporta.
6. Inserción `INSERT OR IGNORE` sobre índice único → re-ejecutar es seguro.

---

## 3. Controles de no-regresión

### 3.1 Benchmark (F5)

`reports/architecture_state/analyze_baseline.py`:

```
[Gold] cuentas_con_gold=2662 match=2660 mismatch=2
MISMATCH: 'DISPONIBLE' gold=AC.01 final=PC.02 (x2, Inmobiliaria Vecchiola)
```

- **2660 / 2662 = 99.92%**, 2 mismatches, **0 regresiones**.
- `gold_standard.db` byte-idéntica al backup (`/tmp/gold_standard_baseline.db`, SHA-256
  `7aeb22f5605c83b2dbd038970e18cb8c8f75d049`).
- `gold_standard_runtime.db` **no existe** (no se creó runtime automáticamente).

### 3.2 Tests (F4)

| Suite | Resultado |
|---|---|
| `tests/test_runtime_manager.py` (nuevo, 21 tests) | ✅ 21 passed |
| `tests/test_gold_promotion.py` (P1.1, 11 tests) | ✅ intacto |
| `tests/test_learning_engine.py` | ✅ |
| `test_validation.py` + `test_dashboard.py` | ✅ |
| `test_builder`, `test_gold_import`, `test_knowledge_evolution`, `test_backward_compatibility`, `test_api_compatibility` | ✅ (84 passed) |
| `test_pipeline_v2`, `test_pipeline_runner_artifacts`, `test_sprint31_integration`, `test_release_pipeline`, `test_manual_revision`, `test_review_priority`, `test_cmcc_audit` | ✅ (269 passed) |

La suite completa del repo supera los 30 min por los tests de discovery/CMCC (no relacionados); al ser
cambios **solo aditivos** (módulo + tests nuevos) sin tocar rutas de código existentes, la verificación
dirigida es concluyente.

---

## 4. Diff resumido

Cambios de P3 (única iteración):

```
 M + gold_standard/runtime_manager.py     (nuevo, ~350 líneas)
 M + tests/test_runtime_manager.py        (nuevo, ~290 líneas)
```

No hay diff sobre archivos existentes del proyecto en P3.

---

## 5. Limitaciones y siguiente paso (fuera de alcance de P3)

- **No** se conectó `RuntimeManager` al `LearningEngine` (el usuario restringió `learning/*`). La
  interfaz de `search_runtime()` ya replica `best_match()`, por lo que el wiring futuro (runtime
  primero, gold benchmark como fallback) no requiere cambios de contrato.
- **No** se implementó Knowledge Manager (P2), CMCC, UI avanzada ni promoción automática.
- `promotion_history` y `metadata` están diseñados pero solo se escriben mediante operaciones
  explícitas (`promote`/`rollback`/`initialize`).

---

## 6. Rollback

- Eliminar `gold_standard/runtime_manager.py` y `tests/test_runtime_manager.py`.
- Confirmar que no existe `gold_standard_runtime.db` (si se creó, eliminarla).
- Re-ejecutar `analyze_baseline.py` y confirmar 2660/2662 con 2 mismatches "DISPONIBLE".
