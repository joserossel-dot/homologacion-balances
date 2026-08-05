# P2 — Knowledge Manager: Roadmap de Implementación

Fecha: 2026-08-03 · Tipo: PLAN — sin código · Orden exacto de implementación, estimación y riesgos.

---

## 1. Fases de implementación (orden estricto)

Cada fase es incremental y verificable. Nada se salta una fase.

### Fase KM-0 — Fundación (estimación: 0.5 día)

**Objetivo:** base de datos de gobierno y convenciones.

- Crear `knowledge_manager/__init__.py` (paquete nuevo, aditivo).
- Crear `knowledge_manager/meta_store.py`: abre `knowledge_meta.db`, crea schema (Fase 3) con
  `PRAGMA foreign_keys = ON`.
- Tests: `tests/test_knowledge_meta_store.py` (schema creado, idempotente, FKs).

### Fase KM-1 — Núcleo de gobierno (estimación: 1.5 días)

**Objetivo:** tablas de gobierno + modelo de datos + APIs de bajo nivel.

- `knowledge_manager/models.py`: dataclasses `BatchRecord`, `HistoryEvent`, `ConflictRecord`,
  `VersionRecord`, `ApprovalEvent`.
- `knowledge_manager/repository.py`: CRUD por tabla (insert/select/update estado).
- `knowledge_manager/promotion_history.py`: registro inmutable de eventos.
- Tests: `tests/test_knowledge_repository.py`, `tests/test_promotion_history.py`.

### Fase KM-2 — Promoción y clasificación (estimación: 1.5 días)

**Objetivo:** envolver P1.1 sin duplicarlo.

- `knowledge_manager/promotion_batch.py` (`PromotionBatch`): create/add/status/apply/dry_run.
  - `apply()` llama a `gold_standard.promotion.promote(dry_run=False)` sobre runtime SOLO.
- `knowledge_manager/conflict_resolver.py` (`ConflictResolver`): clasifica AUTO/REVISION/DESCARTE y
  gestiona `conflict_resolution`.
- Reutiliza `_classify` de `gold_standard/promotion.py` (sin cambios).
- Tests: `tests/test_promotion_batch.py`, `tests/test_conflict_resolver.py` (idempotencia, filtros,
  no toca benchmark — espejo de P1.1).

### Fase KM-3 — Versionado y rollback (estimación: 1 día)

**Objetivo:** snapshots + rollback seguro.

- `knowledge_manager/knowledge_version.py` (`KnowledgeVersion`): snapshot/diff/rollback.
  - Snapshot reutiliza lógica de `gold_import/versioning.py` (sin modificar ese módulo).
  - Rollback restaura runtime desde snapshot almacenado; registra `rolled_back_to`.
- Tests: `tests/test_knowledge_version.py`.

### Fase KM-4 — Aprobación (estimación: 0.5 día)

**Objetivo:** flujo submit → approve/reject.

- `knowledge_manager/approval_service.py` (`ApprovalService`).
- Tests: `tests/test_approval_service.py` (no aplicar sin aprobar).

### Fase KM-5 — Orquestador (estimación: 1 día)

**Objetivo:** `KnowledgeManager` unifica todo.

- `knowledge_manager/knowledge_manager.py` (`KnowledgeManager`): pendientes, batch, aprobar, aplicar,
  rollback, búsqueda.
- Tests de integración: `tests/test_knowledge_manager.py` (ciclo completo con DBs temporales;
  verifica que el benchmark no se toca).

### Fase KM-6 — UI (estimación: 1.5 días)

**Objetivo:** pestaña `_tab_knowledge_manager` (mockup F5).

- Agregar tab al final de `st.tabs` (`app_validacion.py:614`) — sin tocar las 8 existentes.
- `_tab_knowledge_manager()` delgada; toda lógica en `knowledge_manager/`.
- Tests: `tests/test_ui_knowledge_manager.py` (importable, estructura, sin efectos sobre benchmark).

### Fase KM-7 — Verificación final (estimación: 0.5 día)

- Suite completa de tests del repo.
- Confirmar benchmark 2660/2662 (ejecutar `analyze_baseline.py`).
- Confirmar byte-identidad de `gold_standard.db`.
- Confirmar que `learning/*`, `pipeline/*`, `parser/*`, `semantic/*`, `cmcc/*`, `decision/*`,
  `decision_v2/*`, `classification_engine/*` no cambiaron.

---

## 2. Estimación total

| Fase | Días |
|---|---|
| KM-0 Fundación | 0.5 |
| KM-1 Núcleo de gobierno | 1.5 |
| KM-2 Promoción y clasificación | 1.5 |
| KM-3 Versionado y rollback | 1.0 |
| KM-4 Aprobación | 0.5 |
| KM-5 Orquestador | 1.0 |
| KM-6 UI | 1.5 |
| KM-7 Verificación final | 0.5 |
| **Total** | **~8 días-persona** |

Secuencial: KM-0 → KM-1 → KM-2 → KM-3 → KM-4 → KM-5 → KM-6 → KM-7.
KM-3 y KM-4 son independientes entre sí (pueden paralelizarse tras KM-2). KM-6 depende de KM-5.

---

## 3. Dependencias

```
KM-0 (meta_store)
  └─► KM-1 (models + repository + history)
        └─► KM-2 (promotion_batch + conflict_resolver)   ← usa gold_standard/promotion.py (P1.1)
              ├─► KM-3 (knowledge_version)               ← usa gold_import/versioning.py (lógica)
              └─► KM-4 (approval_service)
                    └─► KM-5 (knowledge_manager)
                          └─► KM-6 (UI)
                                └─► KM-7 (verificación)
```

---

## 4. Riesgos y mitigaciones

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | Romper benchmark 2660/2662 al probar | Media | Alto | `apply()` solo a runtime; verificación KM-7 obligatoria; nunca escribir tabla `gold_standard` |
| R2 | Duplicar lógica de P1.1 (promotion.py) | Media | Bajo | Envolver, no copiar; tests reutilizan fixtures de P1.1 |
| R3 | Rollback que deje runtime inconsistente | Baja | Alto | Snapshot completo antes de cada versión; rollback idempotente + registro |
| R4 | UI que escale mal con 348+ candidatos | Media | Medio | Paginación y filtros en KM-6; búsqueda indexada en repository |
| R5 | Aprobar un batch sin estado correcto | Baja | Medio | `ApprovalService` valida estado; tests "no aplicar sin aprobar" |
| R6 | Migración de `learning_queue.json` rota | Media | Medio | KM-1 solo lee la cola (no la muta); unificación en fase posterior |

---

## 5. Criterios de aceptación (DoD)

1. Benchmark **2660 / 2662 / 99.92% / 2 mismatches** tras KM-7.
2. `gold_standard.db` byte-idéntica antes/después.
3. Ningún archivo de `learning/*`, `pipeline/*`, `parser/*`, `semantic/*`, `cmcc/*`, `decision/*`,
   `decision_v2/*`, `classification_engine/*` modificado.
4. Suite de tests completa en verde (incluye los nuevos).
5. Todo cambio aditivo y backward compatible.
6. La UI del KM es una pestaña nueva; las 8 existentes intactas.
