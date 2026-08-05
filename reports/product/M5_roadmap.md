# M5 — Roadmap funcional del producto

Fecha: 2026-08-03 · Derivado de la auditoría `reports/product/M5_functional_audit.md` · Solo diseño — ningún archivo modificado.

---

## 0. Criterios de priorización

El roadmap ordena el trabajo por **impacto al valor comercial y riesgo de implementación**, asumiendo dos premisas de la auditoría M4/M5:

1. **La cobertura es el cuello de botella** (26.29%; 89.1% de UNKNOWN = falta de conocimiento, no de motor). Todo lo que aumente conocimiento revisable tiene retorno inmediato.
2. **La evidencia de clasificación ya existe pero no llega al usuario.** Cerrar la trazabilidad es bajo esfuerzo y alto valor de credibilidad.

Sprint = iteración de trabajo. Orden sugerido; cada fase es independiente y reversible.

---

## 1. FASE A — Correcciones rápidas de alta severidad (Sprint 1-2)

Objetivo: estabilizar la salida del producto tal como se usa hoy. **Bajo riesgo, sin tocar el motor de clasificación.**

| # | Trabajo | Hallazgo que resuelve | Resultado |
|---|---|---|---|
| A1 | Fijar metadata del Excel: leer `metadata_files[archivo_activo_name]` (o `company_*`) en `_tab_balance` en vez de `st.session_state["metadata"]` | F1.1 / F2.1 | Excel con Empresa/RUT/Período/Giro y nombre de archivo correcto |
| A2 | Envolver el loop de procesamiento de archivos en try/except con `st.error` descriptivo (por archivo, no global) | F5.1 | Sin tracebacks; un PDF corrupto no mata la sesión |
| A3 | Agregar confirmación (`st.dialog`/checkbox) antes de escribir `diccionario.json` / `catalogo_maestro.json` + backup `*.bak` previo | F5.2 | Integridad de datos base |
| A4 | `st.cache_data.clear()` tras escrituras de catálogo/diccionario | F5.3 | Nombres nuevos visibles en sesión activa |
| A5 | Reparar `reports/product_validation/product_validation.json` (regenerar o eliminar) | F2.4 | Fuente de verdad reproducible |
| A6 | Corregir `delta_color="inverse"` del descuadre de utilidad (verde ↔ rojo invertido) | F5.8 | Semántica visual correcta |

**Criterio de salida**: exportar un balance revisado a Excel con header de empresa correcto; un archivo corrupto muestra error sin crash.

---

## 2. FASE B — Trazabilidad y explicabilidad visibles (Sprint 2-3)

Objetivo: que el usuario vea **por qué** cada cuenta se clasificó como se clasificó, y que el Excel lo lleve.

| # | Trabajo | Hallazgo | Resultado |
|---|---|---|---|
| B1 | Capturar `reason` (+ `standard_code` separado) en `app_validacion.py:470-484` y guardarlos en columnas nuevas del df | F4.1 | La razón viaja con cada cuenta |
| B2 | Mostrar la razón en la cola de revisión bajo "Sugerido: {código}" | F4.1 | El analista decide con contexto |
| B3 | Agregar columnas `reason`, `standard_code`, `nota` al detalle Excel (`:1385-1407`) | F2.2 / F4.3 | Balance homologado auditable |
| B4 | Integrar `explainability/` (TraceBuilder + trace_exporter) como opción "Descargar trazabilidad" en la UI | F4.4 / F8 | Trazabilidad completa ya construida, puesta en valor |
| B5 | Mostrar `nota` de reglas especiales en revisión y resumen | F4 (gap) | Transparencia de ajustes D1-D5 |

**Criterio de salida**: un analista puede responder "¿por qué ER.13?" sin abrir el código, y exportarlo.

---

## 3. FASE C — Loop de aprendizaje funcional (Sprint 3-4)

Objetivo: que la revisión humana alimente el motor de forma medible y sin perder datos.

| # | Trabajo | Hallazgo | Resultado |
|---|---|---|---|
| C1 | Cerrar el loop `learning_queue.json` → `gold_standard.db`: revisar las 35 entradas pendientes y aplicar/descartar (botón en `_tab_aprendizaje`) | F3.1 | La cola deja de ser infraestructura muerta |
| C2 | Registro de `reviewer` real (usuario identificado de sesión) + `timestamp` en `_save_gold_standard` | F3.3 | Audit trail por quién/cuándo |
| C3 | No tragar errores: superficie de errores de `_save_gold_standard` con `st.error` (fail-loud en desarrollo, configurable) | F3.2 / F5.5 | Escrituras verificables |
| C4 | Medición por ciclo: reusar `learning_cycle_validation.md` como dashboard del impacto de cada ronda de revisión (hits/ratio/precisión) | F3.5 | El aprendizaje demuestra valor |
| C5 | (Con M4) `CREATE INDEX` en `gold_standard.normalized` y revisar full-scans | F3.4 / M4-Q2 | Escala con miles de registros |

**Criterio de salida**: una revisión en la UI incrementa `gold_records`, y en la corrida siguiente aparece como `learning_exact`.

---

## 4. FASE D — Cobertura: activar conocimiento existente (Sprint 4-6)

Objetivo: subir la cobertura real usando lo ya construido. **Es la única fase que ataca el cuello de botella de producto.**

| # | Trabajo | Hallazgo | Resultado |
|---|---|---|---|
| D1 | Desbloquear el release (gates de cobertura/UNKNOWN) y activar CMCC en producción con umbral 0.95, cola 0.85-0.95 (fases 1-4 del rollout CMCC) | F6.2 / F7 | +15pp de cobertura; 2,637 matches perfectos aprovechados |
| D2 | Revisión humana priorizada sobre UNKNOWN (backlog inteligente de `review_priority_report.md`: 200 revisiones → 53.24% de UNKNOWN) | F6.4 | Conocimiento donde más duele |
| D3 | Sembrar gold standard desde `reports/decision_trace` y paquetes de revisión existentes (251 decisiones en `review_ui/reviews.db`) | F3 / F6.4 | Reciclar trabajo humano ya hecho |
| D4 | Incorporar variantes del corpus (3,746 → solo 1,270 cubiertas) al diccionario/CMCC | F6.1 | Cobertura de nombres reales |
| D5 | Medir cobertura por formato y priorizar extractores por familia (recomendaciones de `document_mining_report.md` / pestaña Inteligencia) | F6.1 | Ataque dirigido a los 0%-5% |

**Criterio de salida**: cobertura global ≥50% en el set de validación comercial de 20 balances, con accuracy ≥90% sobre cotejados.

---

## 5. FASE E — Producto comercializable (Sprint 6-9)

Objetivo: convertir el motor en un producto usable por clientes.

| # | Trabajo | Hallazgo | Resultado |
|---|---|---|---|
| E1 | Persistencia de corridas: guardar resultados por ejecución (SQLite o archivos) y permitir reabrir un balance ya procesado | F6.3 | El trabajo no muere con la sesión |
| E2 | Autenticación + roles (analista/admin) — Streamlit auth o gateway | F6.3 | Quién hizo qué; base de multi-tenant |
| E3 | Multi-empresa: metadata **por archivo** (no global de sesión) y aislamiento de datos por tenant | F1.2 / F6.3 | Un analista, varias empresas |
| E4 | Pestaña Analytics real: cablear `analytics/dashboard.py` (metrics.json históricos) | F2.3 / F6.3 | Historial y benchmark visibles |
| E5 | Exportaciones profesionales: PDF certificado del balance + trazabilidad (Excel B4 + PDF) | F6.4 | Entregable al cliente |
| E6 | API con jobs/async + auth (diseño `reports/api_design.md`) o descartar el FastAPI legado | F6.3 | Integración con sistemas del cliente |
| E7 | Post-M4: consolidar la doble vía (V1+V2, 4 motores) para reducir costo de mantenimiento | M4 | Base sostenible para soporte comercial |

**Criterio de salida**: un piloto con cliente real: login, procesar N balances de una empresa, reabrir resultados, exportar balance + trazabilidad.

---

## 6. FASE F — Escala y robustez (Sprint 9+)

| # | Trabajo | Hallazgo |
|---|---|---|
| F1 | Cotas de uso / rate limiting / planes | F6.3 |
| F2 | Cola de revisión virtualizada (paginación o `st.dataframe` con editor) para cientos de cuentas | F1.6 / F5.4 |
| F3 | Detección de "documento no financiero" con aviso temprano (evitar OCR lento en PDFs basura) | F5.6 |
| F4 | Deshacer / re-editar cuentas ya confirmadas (vista "todas las cuentas") | F1.7 |
| F5 | Monitoreo de cobertura/precisión por ciclo de aprendizaje en la UI | C4 |

---

## 7. Mapa de dependencias entre fases

```
FASE A (estabilizar salida)  → desbloquea confianza en el dato
   │
   ▼
FASE B (trazabilidad)        → la revisión humana tiene contexto
   │
   ▼
FASE C (loop de aprendizaje) → la revisión alimenta el motor
   │
   ▼
FASE D (cobertura)           → ataca el cuello de botella (CMCC + conocimiento)
   │
   ▼
FASE E (producto)            → persistencia, auth, multi-empresa, dashboard
   │
   ▼
FASE F (escala)
```

- A y B son independientes entre sí (pueden ir en paralelo).
- C depende parcialmente de B (para no "aprender" razones que no se ven) y de A2 (crash-safe).
- D no depende de A-C funcionalmente, pero su **medición** depende de A5 (fuente de verdad JSON válida).
- E depende de D (un producto con 26% de cobertura no se vende) y de C (demostrar mejora).

---

## 8. Estimación de impacto

| Métrica | Hoy | Con Fase A-D | Con Fase E |
|---|---|---|---|
| Cobertura global (20 balances) | 26.29% | ≥50% (CMCC + conocimiento) | ≥50% estable |
| UNKNOWN revisable | 8,720 (URCA) | −53% con 200 revisiones priorizadas | cola gestionada |
| Trazabilidad por cuenta | No | Sí (reason + Excel) | Sí + PDF certificado |
| Pérdida de trabajo por sesión | 100% | (A) 0% en excel | persistencia completa |
| Crash por archivo corrupto | Sí | No | No |
| Ratio aprendizaje por revisión | 1.1:1 | medible por ciclo (C4) | medible y optimizable |

---

## 9. Riesgos

- **D1 (CMCC producción)** es el de mayor retorno pero toca el motor: mitigar con rollout incremental (10%→50%→100% del plan CMCC) y gates de cobertura ya existentes.
- **C1 (loop de aprendizaje)**: aplicar 35 entradas de cola sin criterio puede envenenar el gold standard → hacer revisión manual de cada entrada antes de aplicar.
- **E3 (multi-empresa)** requiere rediseñar el modelo de metadata global (F1.2) — hacerlo antes de acumular datos.
- **A2 (try/except en loop)** no debe ocultar fallos: registrar en `logs/shadow/` o `st.error` persistente.

---

*Roadmap de diseño, derivado exclusivamente de la auditoría M5. No implementa ni modifica código. Backlog detallado en `reports/product/M5_backlog.md`.*
