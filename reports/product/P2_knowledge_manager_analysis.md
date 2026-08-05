# P2 — Knowledge Manager: Análisis del estado actual

Fecha: 2026-08-03 · Tipo: AUDITORÍA SOLO LECTURA — ningún archivo modificado · Base: P1.1 + P1.2 · Benchmark: 2660/2662 (99.92%).

---

## 1. Alcance de la auditoría

Se analizaron los siguientes componentes (solo lectura):

| Componente | Archivos | Rol |
|---|---|---|
| `gold_standard/` | `models.py` (37 L), `storage.py` (73 L), `builder.py` (199 L), `exporter.py` (40 L), `runtime.py` (86 L), `promotion.py` (254 L) | Persistencia y promoción del conocimiento |
| `learning_queue.json` | raíz (35 entradas) | Cola de correcciones humanas (JSON) |
| `gold_records` | tabla en `gold_standard.db` (348 filas) | Feedback humano revisado |
| `gold_standard` (tabla) | tabla en `gold_standard.db` (234 filas) | Conocimiento que lee el motor |
| `gold_import/` | `validator.py`, `importer.py`, `versioning.py`, `reports.py`, `models.py` | Importación por plantilla (reutilizable) |

---

## 2. Flujo completo del conocimiento hoy

```
USUARIO (UI Streamlit)
   │ 1. corrigen en la cola de revisión
   ▼
_save_gold_standard()  app_validacion.py:234-247
   │ 2. GoldBuilder.add_or_update()
   ▼
gold_records  (tabla, 348 filas)  ◄── PUNTO DE ESCRITURA #1 (UI)
   │
   │ (P1.1: promoción NO activa en prod; dry-run solo)
   ▼
gold_standard_runtime.db  (P1.1 infra, no poblado)
   │
   │ (FASE FUTURA P1.1-fase2: apuntar motor)
   ▼
gold_standard  (tabla, 234 filas)  ◄── PUNTO DE LECTURA (motor)  engine.py:101
   │
   ▼
LearningEngine.best_match()  → pipeline → benchmark 2660/2662
```

### 2.1 Ruta alternativa (importación por plantilla)

```
gold_import/importer.py  → import_gold_standard()  → gold_records + snapshot
```

### 2.2 Ruta de la cola de correcciones (JSON)

```
LearningEngine.record()  → learning_queue.json  (35 entradas)
   └─ hoy: NADIE la lee para retroalimentar gold (BUG M-3 / F3.1)
```

---

## 3. Puntos de escritura (write paths)

| # | Punto | Archivo | Línea | Escribe en | Riesgo |
|---|---|---|---|---|---|
| W1 | `_save_gold_standard` | `app_validacion.py` | 234-247 | `gold_records` | Traga errores (`except: pass`) — escritura silenciosa |
| W2 | `import_gold_standard` | `gold_import/importer.py` | — | `gold_records` | Escritura por lote desde plantilla |
| W3 | `promote()` | `gold_standard/promotion.py` | — | `gold_standard_runtime.db` (no el benchmark) | Segura por diseño (P1.1) |
| W4 | `GoldBuilder.add_or_update` | `gold_standard/builder.py` | 58-64 | `gold_records` | Solo runtime de escritura, no gold_standard |

> **Conclusión:** hoy **nada** escribe la tabla `gold_standard` (234 filas) fuera del seed. El feedback del
> usuario termina en `gold_records`, desconectado de lo que lee el motor. Este es el vacío que llena el
> Knowledge Manager.

## 4. Puntos de lectura (read paths)

| # | Punto | Archivo | Línea | Lee de | Uso |
|---|---|---|---|---|---|
| R1 | `LearningEngine._best_match_impl` | `learning/engine.py` | 75-120 | `gold_standard` | Exacto + fuzzy del motor |
| R2 | `analyze_baseline.cargar_gold` | `reports/architecture_state/analyze_baseline.py` | 47-55 | `gold_standard` | Benchmark 2660/2662 |
| R3 | `GoldBuilder.statistics/list_all` | `gold_standard/builder.py` | 169-198 | `gold_records` | Pestaña Aprendizaje |
| R4 | `run_audit._detect_gs_conflicts` | `run_audit.py` | 378 | `gold_standard` | Auditoría |

> **R2 es el punto crítico:** el benchmark construye `{normalized: codigo}` con último-ganador. Cualquier
> cambio en `gold_standard` afecta la cifra 2660/2662. Por eso la promoción escribe SOLO en runtime.

## 5. Dependencias

```
app_validacion.py ──► gold_standard.builder ──► gold_standard.storage ──► gold_standard.db
                    └─► gold_standard.promotion ──► gold_standard.runtime ──► gold_standard_runtime.db
                    └─► learning.engine (lectura gold_standard)
gold_import ──► gold_standard.builder (snapshot) + gold_standard.db
```

- `gold_standard/runtime.py` y `promotion.py` (P1.1) importan `learning.exact_match.normalize_name`
  (solo lectura, sin tocar el motor).
- No hay ciclo circular; el motor NO importa `gold_standard/*`.

## 6. Riesgos identificados

| # | Riesgo | Severidad | Mitigación |
|---|---|---|---|
| R1 | Escritura silenciosa W1 (except: pass) → feedback perdido sin aviso | Alta | KnowledgeManager con validación y logging explícito |
| R2 | `learning_queue.json` huérfano (35 entradas, 0 con `corrected_code`) | Alta | KnowledgeManager debe unificar cola + gold_records |
| R3 | Conflicto benchmark/gold (P1.1): misma tabla = dataset + motor | Alta | Separación runtime/benchmark ya diseñada (P1.1) |
| R4 | Sin versionado: no se puede reproducir un gold anterior | Media | Tabla `knowledge_versions` (Fase 3) |
| R5 | Sin auditoría de quién/qué/cuándo se promueve | Media | Tabla `promotion_history` + `approval_log` |
| R6 | Rollback manual e irreversible (solo backup M1) | Media | Snapshots versionados + API de rollback |
| R7 | Duplicados y sinónimos OCR en el pool (P1.2: 81 dups, 91 pares) | Baja | Índice único + validaciones previas a promoción |

## 7. Oportunidades

1. **Reutilizar `gold_import/versioning.py`** (`GoldSnapshot`) como base para versionado — ya captura
   métricas, distribuciones y conflictos con tests (`tests/test_gold_import.py:119`).
2. **Promotion module P1.1 ya separa runtime/benchmark** — el KnowledgeManager lo envuelve, no lo duplica.
3. **Pool de conocimiento validado (P1.2)**: 106 claves promovibles, 96% consistente → base de datos limpia
   para alimentar el manager.
4. **Modelo `CorrectionEntry` (JSON) y `GoldRecord` (SQLite)** son compatibles → unificación de cola +
   gold_records viable sin romper backward compatibility.

---

## 8. Conclusión

El sistema tiene la infraestructura de **persistencia** (builder/storage) y de **promoción** (P1.1) pero le
falta la **capa de gobierno**: no hay cola unificada, ni versionado, ni aprobación, ni auditoría, ni
rollback. El Knowledge Manager (Fase 2+) cubre exactamente ese vacío sin tocar el algoritmo, el benchmark
ni el clasificador.
