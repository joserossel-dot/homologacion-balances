# P2 — Knowledge Manager: Arquitectura

Fecha: 2026-08-03 · Tipo: DISEÑO (sin implementación) · Benchmark: 2660/2662 intacto · Cumple P1.1/P1.2.

---

## 1. Principios de diseño

1. **El benchmark NO se toca**: la tabla `gold_standard` (234 filas, benchmark) permanece inmutable. Todo
   conocimiento nuevo vive en el **runtime** (`gold_standard_runtime.db`).
2. **No tocar el motor**: `learning/*`, `pipeline/*`, `parser/*`, `semantic/*`, `cmcc/*`, `decision/*`,
   `decision_v2/*`, `classification_engine/*` quedan intactos. El motor sigue leyendo `gold_standard` por
   `db_path`; el Knowledge Manager prepara el runtime, y la conexión del motor al runtime es un cambio de
   **configuración** (no de código del motor).
3. **Backward compatible**: todo lo nuevo es aditivo (nuevos módulos, nuevas tablas, nuevas pestañas).
4. **Todo gobernado por aprobación**: ninguna promoción al conocimiento "activo" ocurre sin pasar por
   aprobación y registro en historial.
5. **Auditable y reversible**: versiones, batches, historial y rollback como ciudadanos de primera clase.

---

## 2. Componentes del Knowledge Manager

```
                    ┌─────────────────────────────────────────────┐
                    │              KNOWLEDGE MANAGER              │
                    │  (knowledge_manager/ — nuevo paquete)        │
                    │                                             │
                    │  ┌────────────┐   ┌──────────────────┐       │
                    │  │Knowledge   │   │ApprovalService   │       │
                    │  │Manager     │   │(aprobación)      │       │
                    │  └─────┬──────┘   └────────┬─────────┘       │
                    │        │                  │                  │
                    │  ┌─────▼──────┐    ┌──────▼───────┐          │
                    │  │Promotion   │    │Conflict      │          │
                    │  │Batch       │    │Resolver      │          │
                    │  └─────┬──────┘    └──────┬───────┘          │
                    │        │                  │                  │
                    │  ┌─────▼──────┐    ┌──────▼───────┐          │
                    │  │Knowledge   │    │(lectura pool)│          │
                    │  │Version     │    │              │          │
                    │  └─────┬──────┘    └──────┬───────┘          │
                    └────────┼──────────────────┼──────────────────┘
                             │                  │
        ┌────────────────────▼───┐      ┌───────▼──────────────────┐
        │  gold_records (fuente) │      │  learning_queue.json     │
        │  gold_standard_runtime │      │  (cola correcciones)     │
        └────────────────────────┘      └──────────────────────────┘
                             │
                    ┌────────▼─────────────┐
                    │  knowledge_meta.db   │  ← NUEVO (tablas de gobierno:
                    │  versions/batches/   │     knowledge_versions,
                    │  history/conflicts/  │     promotion_batches,
                    │  approvals)          │     promotion_history,
                    └──────────────────────┘     conflict_resolution,
                                                approval_log)
```

### 2.1 Dónde vive cada cosa

| Dato | Ubicación | Justificación |
|---|---|---|
| Conocimiento en evolución | `gold_standard_runtime.db` (P1.1) | Aislado del benchmark |
| Cola de correcciones | `learning_queue.json` (existente) | Reutilizar, no romper |
| Feedback revisado | tabla `gold_records` | Existente |
| **Gobierno (metadatos)** | **`knowledge_meta.db` (NUEVO)** | No toca `gold_standard.db` ni el motor |
| Benchmark | `gold_standard` en `gold_standard.db` | Inmutable |

> **Decisión clave:** los metadatos de gobierno (versiones, batches, aprobaciones, historial) van en una DB
> nueva `knowledge_meta.db`, NO en `gold_standard.db`, para no alterar de ninguna forma la DB del benchmark.

### 2.2 Flujo de una promoción aprobada

```
1. KnowledgeManager.pending_candidates()  → lee gold_records (final_code != '')
2. PromotionBatch.create()                → agrupa candidatos, aplica validaciones (P1.1 rules)
3. ConflictResolver.resolve(batch)        → separa AUTO / REVISION / DESCARTE (P1.2 criterios)
4. ApprovalService.submit(batch)          → crea solicitud pendiente + log
5. [Humano] aprueba en UI                 → ApprovalService.approve(batch_id, usuario)
6. PromotionBatch.apply(approved)         → escribe en gold_standard_runtime.db
7. KnowledgeVersion.snapshot(batch)       → captura versión (reutiliza GoldSnapshot logic)
8. promotion_history registra todo        → quién, cuándo, qué, resultado
```

---

## 3. Subsistemas

### 3.1 Promoción (envuelve P1.1)

- Reutiliza `gold_standard/promotion.py` tal cual (no duplicar lógica).
- El KnowledgeManager lo invoca **solo después de aprobación** y registra el batch.

### 3.2 Rechazo

- Un candidato puede marcarse `rejected` (en `conflict_resolution` o `promotion_history`).
- Regla: registro inmutable en historial (nunca se borra, solo se actualiza estado).

### 3.3 Conflictos

- `ConflictResolver` aplica los criterios de P1.2: mismo `normalized` → códigos distintos = conflicto.
- Puede proponer una **resolución** (elegir código) que un humano confirma.

### 3.4 Versionado

- Cada promoción aprobada y aplicada genera una `knowledge_versions` con:
  - snapshot de métricas (usa lógica de `gold_import/versioning.py`)
  - diff de lo promovido
  - referencia a batch y aprobación

### 3.5 Auditoría

- `promotion_history` y `approval_log`: quién, cuándo, qué, estado, resultado.

### 3.6 Rollback

- `KnowledgeManager.rollback(version_id)`:
  - Reversa runtime a la versión anterior (snapshot almacenado).
  - El benchmark NUNCA se revierte (no se toca).
  - Inmutable: el rollback en sí se registra en historial.

### 3.7 Aprobación

- `ApprovalService`: flujo *submit → pending → approve/reject* con doble confirmación opcional.
- Por defecto: las promociones AUTO de P1.2 (106 claves, riesgo nulo) pueden aprobarse en lote; las de
  REVISIÓN (4 conflictos) exigen decisión individual.

---

## 4. Diagrama de arquitectura (texto)

```
[UI: pestaña Knowledge Manager]  (NUEVA, mockup F5)
   │  acciones: ver pendientes, aprobar, rechazar, rollback, buscar, filtrar
   ▼
[KnowledgeManager]  (NUEVO paquete knowledge_manager/)
   │  orchestrador: candidateos → batch → conflicto → aprobación → aplicar → versionar
   ├──► [PromotionBatch]  → promueve a gold_standard_runtime.db (usa promotion.py P1.1)
   ├──► [ConflictResolver] → clasifica AUTO/REVISION/DESCARTE
   ├──► [ApprovalService] → gestiona aprobaciones en knowledge_meta.db
   ├──► [KnowledgeVersion] → snapshots + diff + rollback
   └──► [Audit] → registra en promotion_history / approval_log

Fuentes de datos (solo lectura):
   gold_records (gold_standard.db)      — feedback humano
   learning_queue.json                   — cola de correcciones
Destino de escritura (solo del manager):
   gold_standard_runtime.db              — conocimiento activo en evolución
   knowledge_meta.db                     — gobierno (nuevo)
BLOQUEADO (intocable):
   gold_standard (benchmark) · learning/ · pipeline/ · parser/ · semantic/
   cmcc/ · decision/ · decision_v2/ · classification_engine/
```

---

## 5. Compatibilidad hacia atrás

| Cambio | Impacto en código existente |
|---|---|
| Nuevo paquete `knowledge_manager/` | Ninguno (aditivo) |
| Nueva DB `knowledge_meta.db` | Ninguno |
| Nueva pestaña Streamlit | Aditivo; se agrega a `st.tabs` |
| Reutiliza `promotion.py`, `runtime.py`, `GoldSnapshot` | Sin cambios a esos módulos |
| Motor sigue leyendo `gold_standard` | Sin cambios a `learning/engine.py` |

---

## 6. Restricciones cumplidas

- ✅ No modifica `learning/*`, `pipeline/*`, `parser/*`, `semantic/*`, `knowledge/*`, `cmcc/*`,
  `decision/*`, `decision_v2/*`, `classification_engine/*`, `gold_standard.db`.
- ✅ Benchmark 2660/2662 intacto (la promoción nunca escribe la tabla del benchmark).
- ✅ No elimina código existente; todo aditivo y backward compatible.
- ✅ Todo nuevo componente tendrá tests.

---

## 7. API interna (FASE 4) — diseño de clases

Nuevo paquete `knowledge_manager/`. Ninguna de estas clases modifica el motor ni el benchmark.
Se documentan responsabilidad, dependencias, métodos públicos y flujo.

### 7.1 `KnowledgeManager` (orquestador)

**Responsabilidad:** coordina todo el ciclo de vida del conocimiento (candidatos → batch → conflicto →
aprobación → aplicar → versionar → rollback).

**Dependencias:** `PromotionBatch`, `ConflictResolver`, `ApprovalService`, `KnowledgeVersion`,
`gold_standard.promotion.promote`, `gold_standard.runtime.RuntimeGoldStorage`.

**Métodos públicos:**

```
pending_candidates() -> list[dict]                # gold_records con final_code != ''
classify_candidates(candidates) -> dict           # {auto, review, discard, conflicts} (criterios P1.2)
create_batch(candidates, user) -> int             # id del promotion_batch
submit_for_approval(batch_id, user) -> int        # crea approval_log 'submit'
list_batches(status=None) -> list[dict]
batch_detail(batch_id) -> dict                    # incluye historial y conflictos
apply_batch(batch_id, user) -> VersionResult      # aprobado → promotion.promote() → version
rollback(version_id, user) -> VersionResult       # revierte runtime; registra historial
search(query, filters) -> list[dict]              # búsqueda en historial/versiones
```

**Flujo:** `pending_candidates → classify → create_batch → submit → [UI] approve → apply → version`.
Nunca llama a `promote()` sin un batch aprobado.

### 7.2 `PromotionBatch`

**Responsabilidad:** encapsula un lote de promoción y su aplicación idempotente.

**Dependencias:** `knowledge_meta.db` (tabla `promotion_batches`), `promotion_history`.

**Métodos públicos:**

```
create(candidates, user) -> int
add_candidate(batch_id, candidate, decision) -> None
set_status(batch_id, status, user) -> None
apply(batch_id) -> dict                          # llama a gold_standard.promotion.promote(dry_run=False)
                                                 # sobre gold_standard_runtime.db SOLO
dry_run(batch_id) -> dict                        # promote(dry_run=True) sin escribir
```

**Flujo:** los candidatos se registran en `promotion_history` al crearse el batch; `apply()` ejecuta la
promoción ya aprobada; es idempotente (índice único `(normalized, codigo_estandar)`).

### 7.3 `ConflictResolver`

**Responsabilidad:** clasifica candidatos y detecta/resuelve conflictos.

**Dependencias:** `knowledge_meta.db` (tabla `conflict_resolution`), `gold_standard.promotion._classify`.

**Métodos públicos:**

```
classify(candidates) -> dict                     # auto / review / discard / conflict (P1.2 criterios)
detect_conflicts(candidates) -> list[dict]       # mismo normalized → códigos distintos
propose_resolution(normalized, chosen_code, note, user) -> int
confirm_resolution(conflict_id, user) -> bool
list_open_conflicts() -> list[dict]
```

**Flujo:** `classify()` determina qué pasa automáticamente; los conflictos se listan en la UI y se
resuelven individualmente antes de re-ejecutar el batch.

### 7.4 `KnowledgeVersion`

**Responsabilidad:** crea, lee y revierte versiones del conocimiento runtime.

**Dependencias:** `knowledge_meta.db` (tabla `knowledge_versions`), `gold_standard.runtime`,
lógica de snapshot de `gold_import/versioning.py` (reutilizada, no modificada).

**Métodos públicos:**

```
snapshot(batch_id, label, user) -> int           # captura métricas + diff, crea versión
latest() -> dict | None
get(version_id) -> dict
diff(prev_id, next_id) -> dict
rollback_to(version_id, user) -> int             # reversa runtime a snapshot previo
list_all() -> list[dict]
```

**Flujo:** `snapshot()` tras cada `apply_batch()`; `rollback_to()` restaura el runtime desde el snapshot
almacenado y marca la versión actual como `rolled_back_to`.

### 7.5 `ApprovalService`

**Responsabilidad:** gobierna el flujo de aprobación (submit → approve/reject) con registro completo.

**Dependencias:** `knowledge_meta.db` (tabla `approval_log`), `promotion_batches`.

**Métodos públicos:**

```
submit(batch_id, user, comment) -> int
approve(batch_id, user, comment) -> bool
reject(batch_id, user, comment) -> bool
status(batch_id) -> dict                          # estado actual + timestamps
list_for_user(user, limit=50) -> list[dict]
```

**Flujo:** nada se aplica sin `approve()`. Las acciones quedan en `approval_log` (inmutable). Soporta
aprobación individual (conflictos REVISION) y en lote (candidatos AUTO).

### 7.6 Contrato de escritura (reglas de oro)

| Operación | Escribe en | Nunca en |
|---|---|---|
| `PromotionBatch.apply` | `gold_standard_runtime.db` | `gold_standard` (benchmark) |
| `KnowledgeVersion.snapshot` | `knowledge_meta.db` | — |
| `ApprovalService.*` | `knowledge_meta.db` | — |
| `KnowledgeManager.rollback` | `gold_standard_runtime.db` | `gold_standard` (benchmark) |
