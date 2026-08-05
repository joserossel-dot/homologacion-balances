# M5 — Auditoría Funcional del Producto

Fecha: 2026-08-03 · Tipo: SOLO AUDITORÍA (ningún archivo, DB ni código modificado) · Base: M4 (2660/2662, 99.92%) · Sucede a M2, M3 y M4.

---

## 0. Resumen ejecutivo

El producto hoy es un **motor de clasificación científico con una UI de validación**, no un producto comercial. El flujo de usuario funcional (carga → confirmación de metadata → procesamiento → revisión → balance normalizado → exportación) está **completo y operativo**, pero tiene tres problemas estructurales que le impiden ser comercializable:

1. **Cobertura baja y volátil**: 26.29% en validación comercial de 20 balances (`reports/product_validation/product_validation.md`), variando de 0% a 88% según formato. El 77% de lo clasificado proviene del **código contable original**, no de homologación semántica. Sin códigos numéricos, los balances largos caen a ~0%.
2. **La evidencia de la clasificación no llega al usuario**: el pipeline genera `reason`/`semantic_result`/`standard_code` para cada cuenta, pero la app los descarta y no los muestra ni exporta. El loop de aprendizaje humano (gold standard) está parcialmente desconectado de la cola de correcciones.
3. **Sin capacidades de producto**: no hay autenticación, multi-empresa, persistencia de resultados (solo `st.session_state`), historial, cotas, trazabilidad de auditoría por usuario, ni API utilizable. Los resultados mueren con la sesión de Streamlit.

**Bug funcional confirmado**: el exportador Excel usa `st.session_state.get("metadata")` (`app_validacion.py:1355,1431`) pero la app **nunca asigna esa clave** (solo `metadata_files` y `company_*`). Resultado: el Excel siempre sale **sin encabezado de Empresa/RUT/Período/Giro** y el nombre del archivo siempre es `Balance_Unificado-empresa-`.

**Sprint 31-32 (información documental, DKB, minería)**: implementados como **solo lectura y correctamente aislados** — no modifican resultados. La pestaña Analytics es "Work in Progress" y el dashboard de exports (`analytics/dashboard.py`) no está cableado a la UI.

---

## 1. FASE 1 — Flujo completo del usuario

### 1.1 Diagrama del flujo (lo que el usuario ve y hace)

```
1. Carga de archivos (sidebar)               app_validacion.py:273-275
     file_uploader PDF/XLS/XLSX, multi-archivo
        │
        ▼
2. Detección de metadata (solo primer archivo)  :305-313
     extraer_metadata(_extraer_lineas_encabezado) → company_rut/razon/giro
        │
        ▼
3. Formulario "Confirma los datos de la empresa"  :314-341
     RUT / Razón Social / Giro (afecta regla D2-Terrenos)
     → confirmar limpia resultados y reprocesa TODO (st.rerun)
        │
        ▼
4. Procesamiento por archivo                  :438-516
     HomologationPipeline._classify_account() por cuenta
     (code → dict → regex → learning; reglas especiales al final)
        │
        ▼
5. Propagación automática entre balances      :517-546
     (una sola vez por sesión; "propagado_automático")
        │
        ▼
6. Sidebar: lista de balances + pendientes    :548-568
        │
        ▼
7. Visor de documento (PDF imagen / Excel HTML)  :633-720
        │
        ▼
8. 8 pestañas de trabajo (col_trabajo)        :612-623
     📈 Resumen · 🔍 Cola de Revisión · 📋 Balance Normalizado ·
     📚 Diccionario · 🧠 Aprendizaje · 📊 Analytics (WIP) ·
     📖 Conocimiento Documental · 📈 Inteligencia del Dataset
```

### 1.2 Pasos del flujo — detalle y evidencia

| # | Paso | Dónde | Estado |
|---|---|---|---|
| 1 | Carga multi-archivo PDF/XLS/XLSX | `app_validacion.py:273-275` | ✅ OK |
| 2 | Metadata detectada solo del **primer** archivo | `:306-312` | ⚠️ Limita multi-empresa: todos los balances asumen RUT/razón del primero |
| 3 | Confirmación de datos de empresa (form, RUT/Razón/Giro) | `:317-340` | ✅ OK; **borra resultados y reprocesa todo** al confirmar (`:338-339`) |
| 4 | Clasificación cuenta a cuenta (nuevo pipeline) | `:437-516` | ✅ OK; `_classify_account` + `_rule_processor.aplicar` (`:470-484`) |
| 5 | Propagación automática entre balances | `:517-546` | ⚠️ Solo 1 vez por sesión (`propagation_done`); no re-corre al agregar archivos |
| 6 | Sidebar con pendientes por balance | `:548-568` | ✅ OK |
| 7 | Visor PDF (pdf2image/poppler, zoom/rotación/página) y Excel HTML | `:633-720` | ✅ OK; cache de imágenes **por nombre de archivo** (`:643`) |
| 8 | 8 tabs de trabajo | `:612-623` | ⚠️ Analytics "Work in Progress" (`:629-630`) |

### 1.3 Estados de la UI por punto del flujo

- Sin archivos → `st.info` + resetea resultados y muestra catálogo (`:297-303`).
- Metadata aún no confirmada → form empresa (`:305-341`).
- Archivo sin cuentas extraídas → `st.warning` + `st.stop()` (`:581-583`).
- Sin cuentas clasificadas → `st.info` (`:1300`).
- Sin pendientes → `st.success` (`:1050`).

### 1.4 Hallazgos FASE 1

- **F1.1 (bug confirmado)** — Export Excel sin metadata: `st.session_state.get("metadata")` nunca se asigna (`:1355,1431`). El nombre de archivo resultante siempre es `Balance_Unificado-empresa-` (`:1432-1434`).
- **F1.2** — La metadata es **global de sesión** (una sola empresa), no por archivo. `metadata_files[archivo.name]` existe (`:444`) pero solo para período del balance en la cabecera (`:592`); RUT/Razón/Giro vienen de `company_*` global.
- **F1.3** — Confirma datos → **pierde resultados ya revisados** (`:338-339`). Un usuario que revisó 50 cuentas y cambia el giro rehace todo sin aviso.
- **F1.4** — Propagación solo corre al inicio de sesión (`propagation_done`, `:546`); archivos nuevos agregados después no se propagan a las anteriores.
- **F1.5** — Archivos con **mismo nombre**: el segundo se omite silenciosamente (`if archivo.name not in ...`, `:439`) y el visor cachea por nombre (`:643`) → muestra las imágenes del primero.
- **F1.6** — La pestaña Revisión renderiza ~5-10 widgets por cuenta pendiente (`:1109-1294`); con cientos de cuentas, cada `rerun` regenera miles de widgets (latencia severa, sin paginación).
- **F1.7** — No hay mecanismo de deshacer ni vista "todas las cuentas" editable: al confirmar, `requiere_revision=False` y la cuenta sale de la cola (`:1276-1277`).

---

## 2. FASE 2 — Salidas (Excel / reportes / trazabilidad)

### 2.1 Exportaciones disponibles hoy

| Salida | Dónde | Contenido | Estado |
|---|---|---|---|
| Excel "Balance Normalizado" | `_tab_balance` `:1349-1438` | Resumen por código (Código, Cuenta Estándar, Monto M$, #Cuentas) + hoja detalle (Código Estándar, Nombre Estándar, Cód. Original, Nombre, Monto, Método, Confianza) | ✅ OK **pero sin metadata de empresa (bug F1.1)** |
| Diccionario actualizado (JSON) | sidebar `:287-295` | `diccionario_actualizado.json` (solo si hay correcciones) | ✅ OK |
| Nuevas categorías → `catalogo_maestro.json` | `:1244-1246` | escritura en disco en vivo | ⚠️ Sin backup ni confirmación |

### 2.2 Reportes offline (scripts, no UI)

- `reports/architecture_state/baseline_analysis.json` — benchmark canónico de la arquitectura (M2/M3: 2660/2662).
- `reports/unknown_pareto.{json,md,xlsx}` — Pareto de cuentas UNKNOWN (base de decisiones de conocimiento).
- `reports/account_coverage.{json,md}` — cobertura de gold_standard vs variantes del corpus.
- `reports/root_cause_unknown.md` — root cause de UNKNOWN.
- `reports/decision_trace/decision_trace.{xlsx,json,md}` — trazabilidad offline por cuenta (**no integrado a la UI**).
- `reports/human_review/*` — paquetes de revisión humana (Excel multi-hoja) generados por CLI (`review/`).

### 2.3 Trazabilidad campo a campo — generado vs expuesto

| Campo del pipeline | Se genera | ¿Llega a la UI/Excel? |
|---|---|---|
| `standard_code` | `pipeline/homologation_pipeline.py:175-266` | ❌ (la app guarda solo `codigo_clasificado` = final post-reglas) |
| `final_code` | `:541-545` | ✅ como `codigo_clasificado` (se pierde el `standard_code` previo al ajuste) |
| `confidence` | `:557` | ✅ columna `confianza` + promedio en Resumen |
| `method` | `:558` | ✅ columna `metodo` + distribución en Resumen |
| `reason` | `:559` (todas las ramas) | ❌ **nunca se lee** (`app_validacion.py:470-484`) |
| `semantic_result` | `:517` (solo en `process()`) | ❌ ni se computa (la app llama `_classify_account` directo) |
| `special_rule` / `nota` | `:560` | ❌ se guarda en df (`:501`) pero no se renderiza ni exporta |
| `source_file` / `source_page` / `nature` | `:550-566` | ❌ ausentes del Excel y de la revisión |

### 2.4 Hallazgos FASE 2

- **F2.1** — El Excel exporta **sin encabezado de empresa** por el bug F1.1 (header condicional `if meta:` nunca se cumple, `:1356`).
- **F2.2** — El Excel no incluye `reason`, `standard_code` separado, `nota`, `source_file/page`, `nature` ni `semantic_result`. La evidencia de clasificación **no viaja con la salida**.
- **F2.3** — La pestaña "Analytics Dashboard (Work in Progress)" (`:630`) deja sin exposición a `analytics/dashboard.py`, que ya sabe leer los `metrics.json` históricos (`:338-387`).
- **F2.4** — `reports/product_validation/product_validation.json` está **corrupto/truncado** (100 bytes, `JSONDecodeError` línea 4) — la fuente de verdad de la validación comercial no es reproducible desde su JSON.
- **F2.5** — No existe salida de "informe de trazabilidad" descargable desde la UI (solo Excel de balance). La capa `explainability/trace_exporter.py` existe pero es offline.

---

## 3. FASE 3 — Proceso de aprendizaje

### 3.1 Arquitectura de aprendizaje hoy

```
Revisión humana (UI)                          CLI / offline
  _save_gold_standard()  :234-247              run_audit.py
       │                                            │
       ▼                                            ▼
  gold_standard.db  (GoldBuilder.add_or_update)   learning_queue.json
  ┌────────────────────────────┐               (35 entradas, user="system",
  │ gold_records: 348 filas     │                source_stage="audit",
  │  reviewer: analista 114      │                del 2026-07-22)
  │           demo 47           │                    │
  │           seed_script 187   │                    ▼
  │ gold_standard: 234 nombres  │              ** NUNCA retroalimenta
  │ pending(final_code=''): 0   │                 el gold_standard **
  └────────────────────────────┘
       │
       ▼  (pipeline de clasificación)
  LearningEngine.best_match()  learning/engine.py:60-120
     exact (conf 0.98) / fuzzy (conf 0.80-0.97, umbral 92)
     → method=learning_{exact|fuzzy}  pipeline:180-190
```

### 3.2 Flujo del feedback humano

1. El analista confirma/clasifica en la cola → `_save_gold_standard(nombre, cod_original, codigo_final)` (`:1279, 1174, 1088`) → `GoldBuilder.add_or_update` → **write a `gold_standard.db`** (incrementa `usage_count` si la tupla `(account_name, final_code)` ya existe).
2. Opcionalmente escribe `diccionario.json` (alcance "Agregar al diccionario") y lo **persiste en disco** (`:1288-1289, 1263-1264, 1095-1097`).
3. La próxima corrida del pipeline, `best_match()` devuelve `learning_exact`/`learning_fuzzy` para cuentas iguales/normalizadas (`pipeline:180-190`).

### 3.3 El "autoaprendizaje" que se muestra en la UI

`_tab_aprendizaje` (`:1533-1563`) muestra con `GoldBuilder`:
- Registros aprendidos / coincidencias exactas / cuentas con conflicto (`:1545-1548`).
- Top 20 más aprendidas (`:1550-1555`).
- Conflictos (misma cuenta con códigos distintos) (`:1557-1561`).
- **No muestra la cola de correcciones pendientes** de `learning_queue.json`.

### 3.4 Hallazgos FASE 3

- **F3.1** — `learning_queue.json` (cola de correcciones) **no retroalimenta el gold standard** (BUG M-3, `PROJECT_CONTEXT.md:785`). Fue poblada por `run_audit` con `source_stage="audit"`, user "system", y nadie la revisa ni la aplica. `LearningEngine.record()` no se llama desde el pipeline ni desde la UI.
- **F3.2** — La revisión humana escribe **directamente en `gold_standard.db`** (gold_records 348) sin cola de aprobación previa: cada click de confirmación es definitivo. `_save_gold_standard` traga errores con `except Exception: pass` (`:246-247`).
- **F3.3** — El revisor por defecto es el literal `"analista"` (`:234`) y `source_file` usa `st.session_state.get("archivo_activo_select")` (`:242`) que puede no estar seteado → **sin audit trail de quién/cuándo**.
- **F3.4** — `gold_standard` (tabla de nombres normalizados, 234) y `gold_records` (348) no están sincronizados por índice (`learning/engine.py:75-86` hace full-scan y join sin índices — hallazgo M4).
- **F3.5** — Impacto real del aprendizaje: +5.2% de cuentas clasificadas (learning_impact_report.md), **precisión estática en 48.77%** (learning_cycle_validation.md) y ratio ~1.1 clasificaciones por revisión humana → el aprendizaje recupera poco y no mejora la precisión.
- **F3.6** — `gold_standard.db` es **byte-idéntico al backup M1** (verificado en M3) → en producción actual nadie revisa (estado seed_script + demo), el loop no está activo en la práctica.

---

## 4. FASE 4 — Explicabilidad y trazabilidad

### 4.1 Estado de la capa de explicabilidad

- **Existe**: `explainability/trace_builder.py:31-174` construye un `DecisionTrace` por cuenta (14+ campos: parser/layout/ocr/column confidences, cmcc, dictionary, decision, etc.), `explainability/decision_trace.py:42-57` tiene `explanation()` (árbol legible), `trace_exporter.py` exporta Excel/JSON/Markdown.
- **Desconectado**: la UI **nunca importa `explainability`** (0 referencias en `app_validacion.py`). Solo scripts offline (`scripts/run_decision_trace.py`, `scripts/cmcc_compatibility_report.py`) y tests lo usan.
- La pestaña Revisión solo muestra `Sugerido: **{código}**` (`:1184-1185`) — el código, sin el porqué.

### 4.2 Hallazgos FASE 4

- **F4.1** — El usuario no ve **por qué** se clasificó una cuenta. La razón existe en el pipeline (`reason`, ej. "Coincidencia fuzzy (93.3%) con 'Resultado no operacional' → ER.13") pero `app_validacion.py:470-484` la descarta.
- **F4.2** — `semantic_result` ni siquiera se computa en el flujo de la app (llama `_classify_account` directo, no `process()`).
- **F4.3** — El Excel no lleva evidencia → el "balance homologado" es inauditable sin abrir el pipeline.
- **F4.4** — `DecisionTrace`/`trace_exporter` son activos valiosos ya construidos y huérfanos: integrarlos a la UI/Excel es la vía más corta a la trazabilidad comercial.

---

## 5. FASE 5 — UX y manejo de errores

### 5.1 Fortalezas
- Estados vacíos bien cubiertos (sin archivos / sin cuentas / sin pendientes / sin clasificadas).
- Validación de archivo (firma `%PDF-`, OLE2, ZIP, bytes vacíos) con advertencias (`parser_universal.py:154-193`).
- Visor de documento robusto (PDF a imagen con fallback `pdftoppm`; Excel a HTML) con controles de página/zoom/rotación.
- Validación de cuadre de utilidad (ER.11 vs PAT.04) con 3 diagnósticos (detalle ER, signo cambiado, excluidas) (`:1444-1499`).
- Mensajes de usuario: 9 toast, 10 warning, 7 info, 4 success, 4 error.

### 5.2 Problemas

| # | Problema | Evidencia | Severidad |
|---|---|---|---|
| F5.1 | **Crash en PDF/xlsx corrupto**: el loop de procesamiento no tiene try/except → traceback de Streamlit | `:438-516`; `parsear_excel` no llama `validar_archivo` (`parser_universal.py:933-934`) | Alta |
| F5.2 | **Sin confirmación antes de escribir en disco** `diccionario.json`/`catalogo_maestro.json` (4 lugares) | `:1095-1097, 1245-1246, 1263-1264, 1288-1289` | Alta |
| F5.3 | **Cache stale**: `cargar_catalogo`/`cargar_diccionario_base` con `@st.cache_data` no se invalidan al escribir los JSON en la misma sesión (`st.cache_data.clear()` nunca se llama) | `:62-71` + escrituras | Media |
| F5.4 | **Cola de revisión no escala**: widgets por cuenta, sin paginación | `:1109-1294` | Media |
| F5.5 | **`_visor_documento` y `_save_gold_standard` tragan errores en silencio** (`except: pass`) | `:606-609`, `:246-247` | Media |
| F5.6 | Metadata de un PDF no financiero/escaneado: sin validación de "es un balance"; OCR página a página lento sin aviso | `parser_universal.py:895-926` | Media |
| F5.7 | Confirmar metadata re-procesa todo y **borra revisiones** sin aviso | `:338-339` | Media |
| F5.8 | Filtrar "Descuadre" con `delta_color="inverse"` invierte el color al revés de la convención (verde cuando descuadra) | `:1470` | Baja |

---

## 6. FASE 6 — Producto comercial

### 6.1 Cobertura real (fuente de verdad)
- Validación comercial (20 balances, 2026-07-23): **3,724 cuentas, 979 clasificadas → 26.29% global**; variación 0%→88%. Métodos: unclassified 738, code 163, fuzzy 55, dictionary 19, regex 4. **El 77% de lo clasificado es por código contable, no por homologación semántica** (`reports/product_validation/product_validation.md:5-46`).
- URCA (10,672 cuentas): 18.3% clasificadas, 89.1% de UNKNOWN es problema de conocimiento (`docs/cmcc_production_design.md:11-19`).
- Certificación holdout: 40.2% clasificadas, 103/1,083 cotejadas → accuracy 100% solo sobre lo cotejable.
- Cobertura de conocimiento: gold 234 nombres → 188 cubiertos (80.3%); variantes del corpus 3,746 → 1,270 (33.9%).

### 6.2 CMCC (clasificador de 52 conceptos)
- Diseñado para +15pp de cobertura; **2,637 cuentas (30.2% de UNKNOWN) tienen match perfecto (score=1.0) desaprovechado** (`cmcc_production_design.md:57-74`).
- **Estado: solo shadow.** Flags default `ENABLE_CMCC=False`, `ENABLE_CMCC_PRODUCTION=False` (`pipeline/features.py:16-27`). Rollout fases 1-4 "Pendiente"; release actual **BLOCKED** por gates de cobertura/UNKNOWN (`reports/release_pipeline/release_report.md:7,26-39`).
- Benchmark: coverage 34.19% sin cambio significativo.

### 6.3 Capacidades de producto — matriz

| Capacidad | Estado | Evidencia |
|---|---|---|
| Multi-empresa / tenant | ❌ No existe | `refactor_priority.md:48`; sin modelo de tenant |
| Autenticación / roles | ❌ No existe | 0 matches reales de auth/login/jwt |
| Sesiones | ⚠️ Solo `st.session_state` (por navegador, sin identidad) | `app_validacion.py:260-269` |
| Persistencia de resultados | ❌ Resultados mueren con la sesión | `app_health_check.md:353-357` |
| Seguridad | ❌ CORS `*` abierto, sin auth | `src/api/main.py:51-57` |
| Reportes descargables | ⚠️ Solo Excel de balance + diccionario JSON | `app_validacion.py:291-295, 1436-1438` |
| API | ⚠️ FastAPI legado (solo `/health` + procesar síncrono), sin uso | `src/api/main.py` |
| Historial / benchmark | ⚠️ `analytics/dashboard.py` lee metrics.json pero no está en UI | `:629-630` |
| Facturación / licencias | ❌ No existe | — |

### 6.4 Gaps comerciales críticos
1. Cobertura 18-34% no es comercializable por sí sola; el cuello de botella es **conocimiento/revisión humana, no código** (740 UNKNOWN, 425 grupos de variantes, 108 reutilizables; 20 revisiones → 7.7% de UNKNOWN, 200 → 53.24% según `review_priority_report.md`).
2. Sin trazabilidad de auditoría por usuario (revisor literal "analista", `:234`).
3. Sin persistencia → cada visita re-procesa; sin historial para demostrar mejora al cliente.
4. Doble vía sin consolidar (2 pipelines, 4 motores, 2 backends) encarece mantenimiento comercial (deuda M4).
5. Estado RC1: "No listo para piloto todavía" (`PROJECT_CONTEXT.md:725-733`); salud histórica 3/10 (mejorada por p0_fixes).

---

## 7. Ranking de hallazgos (priorizados)

| # | Hallazgo | Fase | Impacto | Esfuerzo |
|---|---|---|---|---|
| 1 | Export Excel sin metadata de empresa (bug `st.session_state["metadata"]` nunca seteado) | 2/5 | Alto (salida incorrecta) | Bajo |
| 2 | `reason`/evidencia descartada en la app; sin trazabilidad en UI ni Excel | 4 | Alto (auditabilidad) | Bajo-Medio |
| 3 | Crash en archivos corruptos (sin try/except en loop de procesamiento) | 5 | Alto (disponibilidad) | Bajo |
| 4 | Escritura de diccionario/catálogo sin confirmación ni backup | 5 | Alto (integridad) | Bajo |
| 5 | `learning_queue.json` no retroalimenta gold_standard (loop roto) | 3 | Alto (producto) | Medio |
| 6 | Cobertura 26.29%, 77% por código; conocimiento es el cuello | 6 | Crítico (producto) | Alto |
| 7 | CMCC listo (+15pp, 2,637 matches perfectos) pero solo shadow | 6 | Alto | Medio |
| 8 | `explainability/` huérfano (trazabilidad ya construida, sin integrar) | 4 | Medio | Medio |
| 9 | Cola de revisión no escala (widgets por cuenta) | 5 | Medio | Medio |
| 10 | Cache stale tras escritura de catálogo/diccionario | 5 | Medio | Bajo |
| 11 | Metadata global de sesión (una empresa); reproceso destructivo al confirmar | 1 | Medio | Medio |
| 12 | `product_validation.json` corrupto (100 bytes) | 2 | Bajo | Bajo |

---

## 8. Restricciones respetadas

✅ No se modificó ningún archivo. ✅ No se modificó SQL. ✅ No se modificó Learning Engine. ✅ No se modificó Pipeline. ✅ No se modificó UI. ✅ No se modificó CMCC. ✅ No se modificó Semantic. ✅ No se modificó Parser. ✅ No se cambió comportamiento. ✅ Benchmark se mantiene 2660/2662 (99.92%), 2 mismatches, 0 regresiones — solo auditoría.

---

*Evidencia: lectura completa de `app_validacion.py` (1,583 L), `pipeline/homologation_pipeline.py`, `learning/engine.py`, `gold_standard/builder.py`, `explainability/*`, `ui/app.py`; reportes citados en `reports/` y `docs/`; inspección de `gold_standard.db`, `learning_queue.json` y `reports/product_validation/product_validation.json`. Ver también `reports/product/M5_roadmap.md` y `reports/product/M5_backlog.md`.*
