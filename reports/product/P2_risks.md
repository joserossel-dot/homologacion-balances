# P2 — Knowledge Manager: Riesgos

Fecha: 2026-08-03 · Tipo: ANÁLISIS DE RIESGOS (solo lectura).

---

## 1. Matriz de riesgos

| # | Riesgo | Prob. | Impacto | Severidad | Mitigación |
|---|---|---|---|---|---|
| R1 | Benchmark 2660/2662 alterado durante implementación/pruebas | Media | Alto | **Crítico** | `apply()` escribe SOLO en runtime; verificación obligatoria (byte-identidad de `gold_standard.db` + `analyze_baseline.py`); CI guard |
| R2 | Escribir accidentalmente la tabla `gold_standard` (benchmark) | Baja | Alto | **Crítico** | `gold_standard/promotion.py` usa `BENCHMARK_DB` como solo lectura; tests de no-modificación (P1.1) |
| R3 | Duplicar lógica de P1.1 (promotion/runtime) en `knowledge_manager/` | Media | Bajo | Medio | Envolver módulos existentes, no copiar; DRY por convención + revisión |
| R4 | Rollback que deje el runtime inconsistente | Baja | Alto | Alto | Snapshot completo (reutiliza GoldSnapshot) antes de cada versión; rollback idempotente y registrado |
| R5 | Aprobación aplicada sin estado correcto (apply sin approve) | Baja | Medio | Medio | `ApprovalService` valida transición de estado; test "no aplicar sin aprobar" |
| R6 | UI lenta con 348+ candidatos / 234+ versiones | Media | Medio | Medio | Paginación, filtros, índices en `knowledge_meta.db`; búsqueda indexada |
| R7 | `learning_queue.json` (35 entradas, 0 con `corrected_code`) en desuso → confusión | Media | Medio | Medio | KM-1 solo LEE la cola; unificación documentada; no se muta el JSON |
| R8 | Conflictos (P1.2: 4 analista-vs-gold) bloquean promoción de conceptos frecuentes | Alta | Medio | Medio | Resolución manual previa; `ConflictResolver.propose_resolution` |
| R9 | Sinónimos OCR entran al runtime como entradas separadas | Alta | Bajo | Bajo | `normalize_name` ya colapsa casing/tildes; umbral fuzzy del motor |
| R10 | Regresión silenciosa por `except: pass` heredado en `_save_gold_standard` | Media | Medio | Medio | KM registra eventos; UI del KM expone errores de forma explícita |
| R11 | `knowledge_meta.db` crece sin límite (historial inmutable) | Baja | Bajo | Bajo | Historial por diseño (auditoría); rotación opcional de eventos viejos |

---

## 2. Riesgos críticos en detalle

### R1 + R2 (un solo punto de falla: el benchmark)

El riesgo dominante de todo el proyecto es que una promoción escriba en la tabla `gold_standard`. Mitigación
de 3 capas:

1. **Capa de datos:** el módulo de promoción (P1.1) y el Knowledge Manager apuntan a
   `gold_standard_runtime.db` y `knowledge_meta.db`. La ruta `gold_standard.db` solo se abre en modo
   lectura dentro del KM.
2. **Capa de tests:** `tests/test_gold_promotion.py` verifica que la fuente no se modifica; los tests de KM
   replican el mismo patrón (benchmark byte-idéntico).
3. **Capa de verificación:** fase KM-7 ejecuta `analyze_baseline.py` (2660/2662) y `cmp` contra el backup
   M1.

### R4 (rollback)

El rollback revierte `gold_standard_runtime.db` a un snapshot. El benchmark nunca se revierte. Riesgo
residual: snapshot incompleto. Mitigación: snapshot antes de CADA versión; `diff` entre versiones para
auditar.

### R8 (conflictos pendientes)

P1.2 identificó 4 conflictos analista-vs-gold (`Documentos en Garantía`, `Préstamos al Personal`, `Iva
Crédito Fiscal`, `Revalorización Capital Propio`). Sin decisión, esos conceptos (frecuencia alta, ej. Iva
Crédito Fiscal=4) no entran al runtime. Es un riesgo de **producto** (cobertura), no de integridad.

---

## 3. Mitigaciones transversales

- **Regla de escritura única:** todo cambio al conocimiento pasa por `knowledge_manager/` y por la tabla
  `approval_log`. Nada escribe "por atajo".
- **Registro inmutable:** `promotion_history` y `approval_log` nunca se borran; se agregan eventos.
- **Tests de contrato:** fixtures reutilizan P1.1 (no-modificación de fuente, idempotencia).
- **Verificación post-fase:** cada fase KM-x termina con suite verde + confirmación de benchmark.

---

## 4. Umbrales de severidad y decisión

| Severidad | Umbral | Acción |
|---|---|---|
| Crítico | Cualquier cambio en 2660/2662 o en `gold_standard.db` | Detener, revertir, re-auditar |
| Alto | Rollback inconsistente / pérdida de historial | Detener fase, restaurar snapshot |
| Medio | Conflictos sin resolver / UI lenta / cola JSON confusa | Priorizar en backlog, no bloquea |
| Bajo | Sinónimos OCR / crecimiento de meta DB | Aceptar, documentar |
