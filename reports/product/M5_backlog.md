# M5 — Backlog priorizado de producto

Fecha: 2026-08-03 · Derivado de `reports/product/M5_functional_audit.md` y `reports/product/M5_roadmap.md` · Solo diseño — ningún archivo modificado.

---

## Cómo leer este backlog

- **Prioridad** (P0/P1/P2/P3) refleja impacto × urgencia.
- **Fase** = fase del roadmap (`reports/product/M5_roadmap.md`).
- **Hallazgo** = ID en la auditoría M5 (F1.x…F6.x) o referencia cruzada a M4.
- **Evidencia** = `archivo:línea`.
- **Estimación** = T-shirt size (S/M/L) relativo.

---

## P0 — Críticos (bloquean uso confiable del producto)

| # | Tarea | Fase | Hallazgo | Evidencia | Tamaño |
|---|---|---|---|---|---|
| P0-1 | Exportar Excel con metadata correcta de la empresa: usar `metadata_files[archivo_activo]` o `company_*` en lugar de `st.session_state["metadata"]` (nunca seteado) | A | F1.1/F2.1 | `app_validacion.py:1355,1431,1432-1434` | S |
| P0-2 | Envolver el loop de procesamiento de archivos en try/except con mensaje `st.error` por archivo (hoy un PDF/xlsx corrupto produce traceback de Streamlit) | A | F5.1 | `app_validacion.py:438-516`; `parser_universal.py:933-934` | S |
| P0-3 | Confirmación + backup antes de escribir `diccionario.json` y `catalogo_maestro.json` (4 puntos de escritura en vivo sin respaldo) | A | F5.2 | `app_validacion.py:1095-1097,1245-1246,1263-1264,1288-1289` | S |
| P0-4 | `st.cache_data.clear()` tras escrituras de catálogo/diccionario (cache stale en sesión) | A | F5.3 | `app_validacion.py:62-71` + escrituras | S |
| P0-5 | Reparar o regenerar `reports/product_validation/product_validation.json` (truncado, JSON inválido) — fuente de verdad de validación comercial | A | F2.4 | `reports/product_validation/product_validation.json` (100 B) | S |
| P0-6 | Corregir semántica de color del descuadre de utilidad (`delta_color="inverse"` invierte verde/rojo) | A | F5.8 | `app_validacion.py:1470` | XS |
| P0-7 | No tragar errores en `_save_gold_standard` (`except Exception: pass`); exponer fallo | A | F3.2/F5.5 | `app_validacion.py:246-247` | S |

## P1 — Alto (valor de producto demostrable)

| # | Tarea | Fase | Hallazgo | Evidencia | Tamaño |
|---|---|---|---|---|---|
| P1-1 | Capturar y persistir `reason` (+ `standard_code` separado) por cuenta en el flujo de la app | B | F4.1 | `app_validacion.py:470-484`; `pipeline:559` | S |
| P1-2 | Mostrar `reason` en la cola de revisión (bajo "Sugerido: {código}") | B | F4.1 | `app_validacion.py:1184-1185` | S |
| P1-3 | Agregar columnas `reason`, `standard_code`, `nota` al detalle Excel del balance | B | F2.2/F4.3 | `app_validacion.py:1385-1407` | S |
| P1-4 | Integrar `explainability/` (TraceBuilder + trace_exporter) como "Descargar trazabilidad" en la UI | B | F4.4 | `explainability/trace_builder.py:31-174`, `trace_exporter.py:19-53` | M |
| P1-5 | Mostrar `nota` de reglas especiales (D1-D5) en revisión y resumen | B | F4 | `app_validacion.py:501` | S |
| P1-6 | Cerrar el loop `learning_queue.json` → `gold_standard.db`: UI para revisar/aplicar/descartar las 35 entradas | C | F3.1 | `learning/engine.py:272-300`; `learning_queue.json` | M |
| P1-7 | Reviewer real (usuario de sesión) + timestamp en `_save_gold_standard` | C | F3.3 | `app_validacion.py:234-247` | S |
| P1-8 | Desbloquear release (gates cobertura/UNKNOWN) y activar CMCC en producción (umbral 0.95 / cola 0.85-0.95) | D | F6.2/F7 | `pipeline/features.py:16-27`; `reports/release_pipeline/release_report.md:7,26-39` | M-L |
| P1-9 | Ejecutar revisión humana priorizada sobre UNKNOWN (backlog inteligente) | D | F6.4 | `reports/review_priority_report.md:8-23` | M |
| P1-10 | Reutilizar trabajo humano existente: sembrar gold desde `review_ui/reviews.db` (251 decisiones) y `reports/decision_trace` | D | F3/F6.4 | `review_ui/reviews.db` | M |
| P1-11 | Persistencia de corridas: guardar resultados por ejecución y reabrir balance procesado | E | F6.3 | `app_health_check.md:353-357` | L |

## P2 — Medio (mejoran experiencia y mantenibilidad)

| # | Tarea | Fase | Hallazgo | Evidencia | Tamaño |
|---|---|---|---|---|---|
| P2-1 | Autenticación + roles (analista/admin) | E | F6.3 | `refactor_priority.md:48` | L |
| P2-2 | Multi-empresa: metadata por archivo (hoy global de sesión) + aislamiento por tenant | E | F1.2/F6.3 | `app_validacion.py:305-343` | L |
| P2-3 | Cablear `analytics/dashboard.py` a la pestaña Analytics (WIP) | E | F2.3/F6.3 | `app_validacion.py:629-630`; `analytics/dashboard.py:338-387` | M |
| P2-4 | Medición por ciclo de aprendizaje (hits/ratio/precisión) como dashboard | C | F3.5 | `reports/learning_cycle_validation.md` | M |
| P2-5 | Virtualizar la cola de revisión (paginación / dataframe con editor) | F | F1.6/F5.4 | `app_validacion.py:1109-1294` | M |
| P2-6 | Propagar entre balances al agregar archivos nuevos (hoy solo 1 vez por sesión) | A | F1.4 | `app_validacion.py:517-546` | S |
| P2-7 | Soporte de archivos con nombre duplicado (key por hash de contenido) | A | F1.5 | `app_validacion.py:355,439,643` | S |
| P2-8 | `CREATE INDEX` en `gold_standard.normalized` y revisión de full-scans | C | F3.4/M4-Q2 | `learning/engine.py:75-86,100-102` | S |
| P2-9 | Evitar reproceso destructivo al confirmar metadata (no borrar resultados revisados sin aviso) | A | F1.3/F5.7 | `app_validacion.py:338-339` | M |
| P2-10 | Deshacer / re-editar cuentas ya confirmadas (vista "todas las cuentas") | F | F1.7 | `app_validacion.py:1045-1296` | M |
| P2-11 | Reporte de cobertura por formato y extractores por familia (Inteligencia del Dataset) | D | F6.1 | `document_mining_report.md` | M |

## P3 — Bajo / futuro (cuando exista producto)

| # | Tarea | Fase | Hallazgo | Evidencia | Tamaño |
|---|---|---|---|---|---|
| P3-1 | PDF certificado del balance (además del Excel) | E | F6.4 | `app_validacion.py:1436-1438` | M |
| P3-2 | API con jobs/async + auth (diseño existente) o descartar FastAPI legado | E | F6.3 | `src/api/main.py:51-57`; `reports/api_design.md` | L |
| P3-3 | Cotas de uso / rate limiting / planes | F | F6.3 | — | M |
| P3-4 | Detección temprana de "documento no financiero" (evitar OCR lento en basura) | F | F5.6 | `parser_universal.py:895-926` | M |
| P3-5 | Consolidación V1+V2 y 4 motores de decisión (deuda M4) | E | M4 | `M4_pipeline_audit.md` §6 | L |
| P3-6 | Auditoría de seguridad de la API (CORS `*`, sin auth) | E | F6.3 | `src/api/main.py:51-57` | S |
| P3-7 | Multi-tenant completo con facturación/licencias | F | F6.3 | — | L |

---

## Distribución estimada por fase (de referencia)

| Fase | # tareas | Esfuerzo total |
|---|---|---|
| A — Estabilización | 10 | S (≈1-2 sprints) |
| B — Trazabilidad | 5 | S-M (≈1-2 sprints) |
| C — Aprendizaje | 5 | M (≈1-2 sprints) |
| D — Cobertura | 5 | M-L (≈2-3 sprints) |
| E — Producto | 7 | L (≈3-4 sprints) |
| F — Escala | 4 | M-L |

---

## Notas de dependencia

- P0-1 a P0-7 son independientes entre sí y no tocan el motor de clasificación.
- P1-1/P1-2/P1-3 (trazabilidad) deben ir juntos para que el dato fluya de pipeline → UI → Excel.
- P1-6 (loop de cola) requiere revisión manual de cada entrada antes de aplicar (riesgo de envenenar gold).
- P1-8 (CMCC producción) seguir el rollout incremental del plan CMCC (10%→50%→100%).
- P1-11, P2-1, P2-2 (persistencia/auth/multi-empresa) son prerrequisitos de cualquier piloto comercial.

---

*Backlog de diseño derivado de la auditoría M5. No implementa ni modifica código. Prioridades re-evaluables según resultados de Fase A-D.*
