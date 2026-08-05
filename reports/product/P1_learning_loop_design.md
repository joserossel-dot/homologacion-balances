# P1.1 — Diseño del Learning Loop: separación `gold_standard_runtime` vs `gold_standard_benchmark`

Fecha: 2026-08-03 · Tipo: DISEÑO + INFRAESTRUCTURA (sin escribir sobre la base oficial del benchmark) · Base: M5 (2660/2662, 99.92%) · Sucede a M2, M3, M4 y M5.

---

## 0. Resumen ejecutivo

El análisis de P1.1 confirmó la causa raíz del loop de aprendizaje roto (**M-3 / F3.1**): la revisión humana
escribe en `gold_records` (`_save_gold_standard`, `app_validacion.py:234-247`) pero **nunca llega a
`gold_standard`**, la tabla que lee el motor (`learning/engine.py:101`).

Al diseñar la solución de promoción `gold_records → gold_standard` se descubrió un **conflicto de
arquitectura**: la tabla `gold_standard` cumple simultáneamente dos responsabilidades incompatibles:

1. **Base de conocimiento del motor** (debe evolucionar con cada corrección humana).
2. **Dataset oficial del benchmark** (debe permanecer congelado para comparaciones históricas).

Promover los 114 registros del analista cambia `validacion_gold` de **2660/2662 (99.92%)** a
**2814/3006 (93.6%)** si no se re-clasifica, o a otro número distinto si se re-clasifica — en ningún caso
se mantiene el 2660/2662. **Esto invalida la comparación histórica** contra `baseline_results.json`,
`baseline_analysis.json` y todos los informes M2-M5.

**Decisión (P1.1 v2):** NO se promueven todavía registros a la base oficial del benchmark. Se entrega
únicamente la **infraestructura del Learning Loop** (módulo de promoción, validaciones, resolución de
conflictos, tests, UI y reporte) que escribe en una **base runtime separada** (`gold_standard_runtime.db`),
dejando el benchmark congelado. El diseño propone la separación formal de responsabilidades y un plan de
migración en fases.

---

## 1. Por qué el benchmark cambiaría

### 1.1 Evidencia cuantitativa

La tabla `gold_standard` tiene 234 filas. El feedback humano en `gold_records` (`reviewer='analista'`)
tiene 114 registros con `final_code != ''`. Comparación por `normalized` (usando la MISMA normalización
del pipeline, `core.normalizer.normalize`):

| Clasificación | Cantidad | Detalle |
|---|---|---|
| **Promovibles** (clave nueva en gold) | 108 | `(normalized, codigo)` no existe en `gold_standard` |
| Duplicados (mismo `normalized` + mismo código) | 2 | ya equivalentes en gold |
| **Conflictos** (mismo `normalized`, código distinto) | 4 | ver §1.2 |
| Palabras reservadas (`total`) | 0 | — |
| **Total** | **114** | — |

### 1.2 Conflictos detectados (normalización idéntica, código humano ≠ código gold)

| Cuenta | Código analista | Código gold existente |
|---|---|---|
| Documentos en Garantía | AC.08 | AC.03 |
| Préstamos al Personal | PC.06 | AC.01 |
| Iva Crédito Fiscal | AC.08 | AC.07 |
| Revalorización Capital Propio | PAT.02 | PAT.01 |

Estos 4 registros representan decisiones humanas que **contradicen** el gold actual. Promoverlos cambia el
lookup del motor (que prefiere revisores no-`seed_script`, `engine.py:81-85`) y del benchmark (que
construye `{normalized: codigo}` y **el último ganador reemplaza** al anterior, `analyze_baseline.py:55`).

### 1.3 Impacto simulado sobre `validacion_gold` (`analyze_baseline.py`)

Usando `baseline_results.json` (299 PDFs) tal cual, solo cambiando el diccionario gold:

| Métrica | Hoy | Con promoción (sin re-clasificar) |
|---|---|---|
| `cuentas_con_gold` | 2662 | **3006** |
| `match` | 2660 | **2814** |
| `mismatch` | 2 | **192** |

Los 192 mismatches por método de clasificación del pipeline: `unclassified` 136, `learning_fuzzy` 44,
`code` 7, `dictionary_exact` 2, `learning_exact` 2, `dictionary_fuzzy` 1.

**Si se re-clasificaran los 299 PDFs** (10-20 min, borrar checkpoints), el pipeline leería el gold nuevo y
re-mapearía la mayoría de los `unclassified`/`learning_fuzzy` vía `learning_exact`, pero los `code`/`dictionary`
(≈10) que clasifican por catálogo/código contable seguirían apuntando al código original, no al gold —
el número **nunca regresa a 2660/2662** y el delta no es trivial de auditar.

### 1.4 Por qué cambia la semántica, no solo los números

- `analyze_baseline.py` construye `gold = {normalized: codigo}` con **último ganador** (`:55`). Cualquier
  promoción con `normalized` duplicado **pisa** el código previo, aunque el intérprete SQL haya usado
  `ORDER BY id` (inserción = nuevo `id` más alto → gana).
- El motor (`engine.py:75-89`) hace `LEFT JOIN gold_records` y prioriza `reviewer != 'seed_script'` —
  los registros del analista tienen `reviewer='analista'`, así que pasarían al frente de la prioridad.
- El benchmark 2660/2662 es un **punto fijo** referenciado por M2, M3, M4, M5, `baseline_analysis.json`,
  `reports/pipeline_benchmark*.json` y `summary_before/after.md`. Cambiarlo rompe la cadena de trazabilidad.

---

## 2. Por qué eso invalida la comparación histórica

La cifra 2660/2662 es el producto de: `gold_standard.db` (234 filas, congelada desde el seed) +
`baseline_results.json` (299 PDFs, generado una vez con `generate_baseline.py`). Todo informe posterior
M2→M5 cita ese par como invariante. Si el gold evoluciona:

1. **El denominador cambia**: `cuentas_con_gold` deja de ser comparable entre versiones.
2. **El lookup gold cambia**: una cuenta que hoy matchea `AC.01` puede matchear `PC.02` mañana, no por
   mejora del clasificador sino por el contenido del gold.
3. **No hay versión del gold**: no existe snapshot del gold usado en cada informe → no se puede
   reproducir el 2660/2662 pasado.
4. **La mejora real queda enmascarada**: el learning loop solo aporta valor si se mide contra un gold
   estable; medirlo contra un gold móvil confunde señal (aprendizaje) y ruido (cambio de dataset).

**Conclusión:** la tabla única `gold_standard` no puede ser a la vez motor de conocimiento y dataset de
benchmark. Hay que separarlas.

---

## 3. Diseño recomendado

### 3.1 Principio

> El **conocimiento evoluciona** en una base runtime. El **benchmark permanece congelado** en una base
> snapshot. La promoción escribe SOLO en runtime. La medición siempre usa un snapshot inmutado.

### 3.2 Componentes

| Componente | Ruta / Tabla | Rol |
|---|---|---|
| `gold_standard_benchmark.db` (snapshot) | `gold_standard_bench.db` / tabla `gold_standard` | Dataset oficial del benchmark. **Inmutable para P1.1.** |
| `gold_standard_runtime.db` (nuevo) | tabla `gold_standard` (mismo schema + columnas de proveniencia) | Base de conocimiento en evolución. La escribe el módulo de promoción. |
| `gold_records` (runtime) | tabla espejo | Registro de revisiones humanas con estado de promoción. |
| `gold_standard/promotion.py` (nuevo) | módulo | Orquesta lectura de feedback → validación → conflictos → promoción idempotente en runtime. |
| `gold_standard/runtime.py` (nuevo) | módulo | Abre/crea/valida la DB runtime y su schema. |
| `learning/engine.py` (NO modificado) | — | Sigue leyendo la DB que se le pase por `db_path`. En la fase de migración se le apuntará a runtime. |
| UI (`app_validacion.py`, `_tab_aprendizaje`) | botón dry-run + aplicar | Expone la promoción sin tocar el benchmark. |

### 3.3 Flujo objetivo (fase final)

```
usuario corrige (UI) ──► gold_records.runtime (final_code != '')
                                 │
            gold_standard/promotion.py: promote(remote=benchmark? no, local=runtime)
                                 │
                                 ▼
              gold_standard_runtime.db (knowledge en evolución)
                                 │
                 pipeline lee db_path=gold_standard_runtime.db
                                 │
              benchmark  SIEMPRE lee gold_standard_bench.db (snapshot)
```

### 3.4 Reglas de promoción (validaciones)

El módulo `promotion.py` aplica, en orden, las siguientes reglas a cada candidato (`gold_records` con
`final_code != ''`):

1. **Candidatos**: solo `final_code != ''`. Sin código corregido → se omite.
2. **Normalización**: `learning.exact_match.normalize_name` (idéntica salida a `core.normalizer.normalize`
   en casos de prueba; misma que usa el motor en `engine.py:72`).
3. **Palabras reservadas**: cuentas cuyo `normalized` contenga el token `total` (subtotales del balance)
   NO se promueven. Configurable.
4. **Duplicado**: si `(normalized, codigo)` ya existe en runtime → se omite (idempotente).
5. **Conflicto**: si `normalized` ya existe en runtime con OTRO código → **no se promueve**; se reporta
   como conflicto para resolución manual.
6. **Inserción**: `INSERT OR IGNORE` sobre índice único `(normalized, codigo_estandar)` → re-ejecutar es
   seguro.

### 3.5 Mecanismo de congelamiento del benchmark

- La base snapshot (`gold_standard_bench.db`) se congela en su estado actual (234 filas, baseline 2660/2662).
- La promoción NO la toca nunca (path hardcodeado como `BENCHMARK_DB` inmutable en `promotion.py`).
- Para un nuevo ciclo de benchmark se genera un **nuevo snapshot versionado** (ej. `gold_standard_v2.db`)
  con su propio `baseline_analysis.json`, en vez de mutar el gold actual.

### 3.6 Alternativas consideradas

| Alternativa | Evaluación |
|---|---|
| **A) Tabla única con columna `frozen`/`is_benchmark`** | Rechazada: el dict `{normalized: codigo}` del benchmark no puede filtrar por columna sin cambiar `analyze_baseline.py` (no permitido) y los `id` se comparten, mezclando prioridades del motor. |
| **B) Vista `gold_standard_benchmark` sobre la misma DB** | Rechazada: `analyze_baseline.py` lee la tabla por nombre; una vista exigiría tocar el script o renombrar, y la promoción seguiría viviendo en el mismo archivo físico. |
| **C) Dos archivos `.db` separados (elegido)** | Aceptada: aislamiento físico total, cero cambios a `analyze_baseline.py`, `engine.py` apuntable por `db_path` sin modificar su código. |
| **D) Un solo archivo con `ATTACH DATABASE`** | Posible variante de C; se documenta como evolución si se quiere un solo binario. |

---

## 4. Plan de migración (fases)

### Fase 0 — Infraestructura (P1.1, entregada en este reporte)

- [x] Análisis de causa raíz y simulación de impacto (este documento).
- [x] `gold_standard/runtime.py` — schema runtime (tabla `gold_standard` con columnas extra: `source_record_id`,
      `reviewer`, `review_date`, `promoted_at`; índice único `(normalized, codigo_estandar)`).
- [x] `gold_standard/promotion.py` — API `promote(source_db, runtime_db, dry_run=True)` + CLI `--dry-run`/`--apply`.
- [x] Tests (`tests/test_gold_promotion.py`).
- [x] Botón en UI `_tab_aprendizaje` (dry-run + aplicar) apuntando a runtime.
- [x] Verificación: benchmark `gold_standard_bench.db` y `gold_standard.db` NO modificados; suite de tests verde.

### Fase 1 — Poblar runtime y validar en paralelo (recomendado)

- [ ] Ejecutar `python3 -m gold_standard.promotion --dry-run` sobre el `gold_records` actual.
- [ ] Revisar y resolver los 4 conflictos de forma manual (decisión de negocio, no de código).
- [ ] Aplicar promoción a `gold_standard_runtime.db`.
- [ ] Comparar cobertura runtime vs benchmark (shadow) sin afectar resultados.

### Fase 2 — Apuntar el pipeline a runtime

- [ ] Cambiar el `db_path` del `LearningEngine` a runtime (config, no código del motor).
- [ ] Re-correr pipeline y medir contra el snapshot benchmark (denominador estable).

### Fase 3 — Nuevo ciclo de benchmark versionado

- [ ] Congelar un snapshot `gold_standard_vN.db` cuando el conocimiento se estabilice.
- [ ] Generar nuevo `baseline_analysis.json` versionado; conservar los anteriores.

---

## 5. Impacto

| Área | Impacto |
|---|---|
| Benchmark 2660/2662 | **Ninguno** — P1.1 no toca `gold_standard.db` ni `gold_standard_bench.db`. Se verificó byte-idéntico. |
| Motor (`learning/engine.py`) | **Ninguno** — no se modifica; lee la DB por `db_path`. |
| Pipeline / Parser / CMCC / Semantic | **Ninguno** — fuera del alcance. |
| UI | Bajo — se agrega una sección en `_tab_aprendizaje` con dry-run y botón de aplicar a runtime. |
| Tests | Nuevos tests aislados en `tests/test_gold_promotion.py` con DBs temporales. |
| `gold_standard_runtime.db` | Nuevo archivo (no existe aún); se crea bajo demanda. |

### 5.1 Dependencias / imports

- `gold_standard/promotion.py` importa: `sqlite3`, `dataclasses`, `argparse`, `Path`,
  `learning.exact_match.normalize_name`, `gold_standard.runtime`.
- No importa `learning/engine.py` (restricción P1.1 respetada).
- `app_validacion.py` importa `promotion` y `runtime` (código nuevo permitido).

---

## 6. Rollback

- **Módulo nuevo**: eliminar `gold_standard/promotion.py`, `gold_standard/runtime.py`,
  `tests/test_gold_promotion.py` y revertir el bloque agregado en `_tab_aprendizaje`.
- **DBs**: eliminar `gold_standard_runtime.db` (si se creó). Restaurar `gold_standard.db` desde
  `/tmp/gold_standard_baseline.db` (backup M1, byte-idéntico) y `gold_standard_bench.db` desde su estado
  previo si hiciera falta.
- **Verificación de rollback**: re-ejecutar `reports/architecture_state/analyze_baseline.py` y confirmar
  `validacion_gold` = 2660 match / 2662 con 2 mismatches "DISPONIBLE".

---

## 7. Entregables de P1.1 (esta iteración)

| Archivo | Descripción |
|---|---|
| `reports/product/P1_learning_loop_design.md` | Este documento (causa raíz, evidencia, diseño, plan, impacto, rollback). |
| `gold_standard/runtime.py` | Gestión de la DB runtime (schema + validación). |
| `gold_standard/promotion.py` | Módulo de promoción con validaciones, conflictos y CLI. |
| `tests/test_gold_promotion.py` | Tests: idempotencia, duplicados, conflictos, filtros (`total`, `final_code=''`), no toca benchmark. |
| `app_validacion.py` (bloque nuevo) | Botones dry-run / aplicar en `_tab_aprendizaje` apuntando a runtime. |

**Fuera de alcance (consciente):** promover registros a `gold_standard.db` (benchmark), modificar
`learning/engine.py`, pipeline, Parser, CMCC o Semantic. Todo lo anterior se documenta como fases futuras
(§4) sujetas a aprobación.
