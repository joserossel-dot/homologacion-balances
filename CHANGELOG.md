# CHANGELOG — Sistema de Homologación de Balances

Historial de hitos del proyecto. Formato: hitos de conocimiento **M1–M5** y entregables de
producto **P1–P6**. La base del benchmark oficial **2660/2662 (99.92%)** permanece congelada a
lo largo de toda la evolución.

---

## 2026-08-05 — Consolidación final (documentación)

- Creación de `ARCHITECTURE.md`, `CHANGELOG.md`, `PROJECT_STATUS.md`.
- Actualización de `README.md` (portada alineada con arquitectura actual).
- Auditoría de documentación en `reports/documentation/documentation_audit.md`.
- **No** se modificó código, tests, runtime ni la base del benchmark.

## P6 — Validación del Runtime Depurado (2026-08-05)

- Estado: ✅ Validado — **0 regresiones**, `gold_standard.db` byte-idéntica (SHA-256
  `0a60334706f9a8b9…`).
- Depuración del runtime: 107 claves auditadas → **96 activas / 11 inactivas** (5 B, 3 C, 3 D).
- `RuntimeManager`: columna `activa`, métodos `set_active`/`deactivate`/`activate`,
  `get_active_keys`, `search_runtime` filtra por `activa=1`.
- Shadow (9.942 cuentas únicas): 336 nuevas homologaciones (antes 364), 297 runtime exact,
  185 runtime fuzzy. Informe: `reports/product/P6_runtime_validation.md`.

## P5.5 — Runtime Observability (2026-08-04)

- ✅ Implementado — observabilidad completa del runtime (uso, fallbacks, promociones, impacto).
- Alcance SOLO observabilidad: sin promociones automáticas.
- Informe: `reports/product/P5_5_runtime_observability.md`.

## P5 — Learning Loop Architecture (2026-08-05, commit `dca0655`)

- `feat: complete learning loop architecture (M3-P5)`.
- Cierre del loop: runtime → revisión → promoción (auditada) → conocimiento.

## P3 — Runtime de aprendizaje: `RuntimeManager` (2026-08-03)

- Implementación nueva: `gold_standard/runtime_manager.py`.
- Tres tablas: `runtime_gold` (conocimiento en evolución + proveniencia), `promotion_history`
  (auditoría de promociones/rollbacks), `metadata`.
- **Solo lectura** de la base del benchmark (2660/2662).
- Informe: `reports/product/P3_runtime_learning.md`.

## P2 — Knowledge Manager (2026-08-03)

- Arquitectura, modelo de datos, análisis del estado actual, riesgos, roadmap y mockup de UI.
- Tipo: DISEÑO (sin implementación). Benchmark intacto.
- Informes: `reports/product/P2_*.md` (7 documentos).

## P1 — Learning Loop: separación benchmark vs runtime (2026-08-03)

- **P1.1:** diseño de `gold_standard_runtime` vs `gold_standard_benchmark`.
- **P1.2:** auditoría de calidad del Knowledge Runtime (solo lectura; pool = `gold_records`, 348).
- Informes: `reports/product/P1_learning_loop_design.md`, `reports/product/P1_runtime_quality.md`.

## M5 — Auditoría y Roadmap Funcional del Producto (2026-08-03)

- Auditoría funcional completa (solo auditoría, ningún archivo modificado).
- Backlog priorizado + roadmap funcional.
- Informes: `reports/product/M5_functional_audit.md`, `M5_backlog.md`, `M5_roadmap.md`.

## M4 — Auditoría Arquitectónica del Pipeline de Clasificación (2026-08-03)

- Solo auditoría. Base: benchmark 2660/2662 (99.92%), **2 mismatches, 0 regresiones**.
- Informe: `reports/architecture_state/M4_pipeline_audit.md`.

## M3 — Refactor del Normalizador (2026-08-03)

- Introducción de `core/normalizer.py` como única implementación base (FASES 1–5).
- Migración de consumidores SIN cambio de comportamiento. Benchmark objetivo: 2660/2662.
- Informe: `reports/architecture_state/M3_report.md`.

## M2 — Normalización de diacríticos en el Learning Engine (2026-07)

- Auditoría (solo lectura) de la normalización de diacríticos.
- Informes: `reports/classifier_audit/M2_audit.md`, `reports/architecture_state/normalizer_inventory_after_m2.md`.

## M1 — Eliminación del "primer-fila-gana" del Learning Engine (2026-07)

- Eliminación del sesgo de "primera fila gana" en el Learning Engine.
- Informe: `reports/classifier_audit/M1_result.md`.

---

## Hitos previos (2026-07, contexto)

| Fecha | Hito |
|---|---|
| 2026-07-30 | Estabilización del pipeline V2 + suite de tests verde (`6c9e0ce`). |
| 2026-07-29 | Auditoría RC1 — "No listo para piloto todavía" (`AUDITORIA_RC1.md`). |
| 2026-07-27 | Validación del conocimiento CMCC contra `gold_standard.db`. |
| 2026-07-26 | Integración de `DocumentAnalyzer` (DIE) como capa previa al parseo (`72e62b6`, `e0a8933`); benchmark HOLDOUT (20 archivos, 2.692 cuentas). |
| 2026-07-24 | Checkpoint MVP de producto (`a7a4322`). |
| 2026-07-23 | Sprint 28.5: parser hardening, knowledge engine, review pipeline (`b2c24a2`). |
| 2026-07-22 | Benchmark pipeline legacy vs nuevo (`reports/pipeline_benchmark.md`). |
| 2026-07-10 | Shadow full repository (CMCC); URCA — Unified Root Cause Analysis (10.672 cuentas, 185 docs). |
| 2026-07-09 | **Certificación oficial:** HOLDOUT 20 PDFs, 100% accuracy en cuentas cotejables (103/103, κ=1.0). |
| 2026-07-07 | Primer reporte de validación (185 documentos, 10.672 cuentas). |

---

## Registro de la base del benchmark

| Ítem | Valor |
|---|---|
| Identificador | 2660/2662 (base M5) |
| Precisión | 99.92% |
| Estado | **Congelada** — el runtime solo la lee, nunca la escribe |
| Referencias | `gold_standard/promotion.py:12`, `app_validacion.py:1951` |
