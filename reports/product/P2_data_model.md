# P2 — Knowledge Manager: Modelo de Datos (diseño, sin implementar)

Fecha: 2026-08-03 · Tipo: DISEÑO — **no se ejecuta SQL** · Compatible con SQLite por defecto.

Todas las tablas de gobierno residen en una base nueva **`knowledge_meta.db`** (para no tocar
`gold_standard.db`). Los snapshots del conocimiento activo siguen en `gold_standard_runtime.db`.

---

## 1. `knowledge_versions`

Versión inmutable del conocimiento runtime en un momento dado (tras una promoción aprobada).

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | Identificador |
| `version` | INTEGER UNIQUE NOT NULL | Número de versión (1, 2, …) |
| `label` | TEXT | Etiqueta humana (ej. "post-p2-batch-7") |
| `batch_id` | INTEGER FK → `promotion_batches(id)` | Batch que originó la versión |
| `snapshot_json` | TEXT | Métricas + distribución del runtime (lógica reutilizada de GoldSnapshot) |
| `diff_json` | TEXT | Lista de cambios (cuenta, código, acción) vs versión previa |
| `created_by` | TEXT | Usuario que aplicó |
| `created_at` | TEXT (ISO) | Timestamp |
| `rollbacked_to` | INTEGER NULL FK → `knowledge_versions(id)` | Si fue revertida, hacia qué versión |

Inmutabilidad: una versión no se edita; solo se referencia.

---

## 2. `promotion_batches`

Agrupación de candidatos sometidos a promoción (una sesión de aprobación).

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `status` | TEXT | `pending` · `approved` · `rejected` · `applied` · `rolled_back` |
| `total_candidates` | INTEGER | Nº de candidatos capturados |
| `auto_count` | INTEGER | Clasificados AUTO |
| `review_count` | INTEGER | Clasificados REVISION |
| `discard_count` | INTEGER | Clasificados DESCARTE |
| `conflict_count` | INTEGER | Conflictos detectados |
| `created_by` | TEXT | Usuario |
| `created_at` | TEXT | ISO8601 |
| `applied_at` | TEXT NULL | Cuándo se aplicó |

Estados (flujo): `pending → approved → applied`, o `pending → rejected`, o `applied → rolled_back`.

---

## 3. `promotion_history`

Registro de auditoría de cada candidato a través de su vida.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `batch_id` | INTEGER FK → `promotion_batches(id)` | Lote |
| `source_record_id` | INTEGER NULL | id en `gold_records` |
| `account_name` | TEXT | Nombre de la cuenta |
| `normalized` | TEXT | Normalizado |
| `candidate_code` | TEXT | Código propuesto |
| `decision` | TEXT | `auto` · `approved_review` · `rejected` · `discarded` · `conflict` |
| `target_db` | TEXT | `gold_standard_runtime` |
| `event` | TEXT | `created` · `approved` · `rejected` · `applied` · `rolled_back` |
| `actor` | TEXT | Usuario/sistema |
| `timestamp` | TEXT | ISO8601 |
| `details_json` | TEXT NULL | Detalles (ej. códigos gold en conflicto) |

Regla de oro: filas de historial **nunca se borran**; solo se agregan eventos.

---

## 4. `conflict_resolution`

Decisiones tomadas para resolver conflictos (mismo nombre → códigos distintos).

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `normalized` | TEXT | Nombre en conflicto |
| `account_name` | TEXT | Texto original |
| `codes` | TEXT | Lista de códigos en disputa (JSON) |
| `chosen_code` | TEXT NULL | Código elegido (tras resolución) |
| `status` | TEXT | `open` · `resolved` · `discarded` |
| `resolution_note` | TEXT | Justificación |
| `resolved_by` | TEXT NULL | Usuario |
| `resolved_at` | TEXT NULL | ISO8601 |
| `supersedes_id` | INTEGER NULL | Si una resolución reemplaza otra |

---

## 5. `approval_log`

Registro de aprobaciones / rechazos interactivos.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `batch_id` | INTEGER FK | Lote asociado |
| `reference_type` | TEXT | `batch` · `conflict` · `version` |
| `reference_id` | INTEGER | id de la entidad aprobada |
| `action` | TEXT | `submit` · `approve` · `reject` · `rollback_request` |
| `user` | TEXT | Quién actuó |
| `comment` | TEXT | Nota |
| `timestamp` | TEXT | ISO8601 |

---

## 6. Relaciones

```
promotion_batches 1 ── n promotion_history      (historial por candidato)
promotion_batches 1 ── 1 knowledge_versions      (una versión por batch aplicado)
promotion_batches 1 ── n approval_log            (acciones de aprobación)
conflict_resolution n ── 1 promotion_batches     (conflictos pertenecen a un lote)
knowledge_versions n ── 1 knowledge_versions     (rollback: is_rolled_back_to)
```

## 7. Notas de compatibilidad SQLite

- Todas las tablas usan `INTEGER PRIMARY KEY AUTOINCREMENT`.
- FKs referenciales compatibles con `PRAGMA foreign_keys = ON`.
- Timestamps `TEXT` ISO8601 (UTC) uniformes.
- Campos "tipo" textuales con `CHECK` o validación en API (no enum SQLite).
- Se crean índices sobre: `promotion_history(batch_id)`, `promotion_history(normalized)`,
  `approval_log(batch_id)`, `knowledge_versions(version)`.