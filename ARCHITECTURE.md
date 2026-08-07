# ARCHITECTURE.md — Sistema de Homologación de Balances

Arquitectura del sistema que homologa balances tributarios chilenos (PDF/Excel) a estados
financieros normalizados, clasificados en el Catálogo Maestro de Conceptos Contables (CMCC).

**Resumen de estado:** doble vía V1 (legado, en uso por la UI) y V2 (nuevo, backend `2.0.0-rc1`).
Ver también: [`README.md`](README.md) · [`PROJECT_STATUS.md`](PROJECT_STATUS.md) ·
[`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) (documento maestro, referencia interna).

---

## 1. Visión general: doble vía (V1 y V2 coexisten)

La arquitectura es de **doble vía**: varios subsistemas legados y nuevos se superponen. Leer los
documentos de riesgo de cada módulo antes de modificar código.

```
┌────────────────────────────────────────────────────────────────────────┐
│                            DOBLE VÍA                                    │
│                                                                        │
│   V1 (LEGADO — EN USO por UI)          V2 (NUEVO — Backend 2.0.0-rc1)  │
│   ─────────────────────────────        ───────────────────────────────  │
│   pipeline/homologation_pipeline.py    orchestrator/pipeline_v2.py      │
│   + SemanticMatcher + ParserPDF        HomologationPipelineV2           │
│   usado por: UI (app_validacion.py)    + 9 adaptadores                  │
│              adapters/kb_adapter.py    usado por: backend/runner.py     │
│                                        run_pipeline_v2.py               │
│                                        FastAPI src/api/main.py          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mapa de módulos

| Directorio | Rol | Estado |
|---|---|---|
| `pipeline/` | Pipeline V1 (homologation_pipeline.py, features.py) | En uso (V1) |
| `orchestrator/` | Pipeline V2 (pipeline_v2.py, HomologationPipelineV2) | Activo (V2) |
| `parsers/` | ParserCore2 (nuevo) + legacy ParserPDF | Parcialmente integrado |
| `parsers/legacy/` | ParserPDF legacy (el que realmente corre) | En uso |
| `semantic/` | SemanticMatcher por tiers (1-6) | En uso (V1) |
| `decision/` | Decision Engine V1 (5 reglas) | OFF (`ENABLE_DECISION_ENGINE`) |
| `decision_engine/` | Decision Engine V2 documental | ACTIVO en pipeline V2 |
| `decision_v2/` | Benchmark Decision Engine (no conectado) | No integrado |
| `classification_engine/` | Motor Top-N nuevo (Sprint 39) | No integrado |
| `learning/` | Learning Engine | En uso (shadow) |
| `cmcc/` | Clasificador CMCC + rollout | En uso (shadow) |
| `review/` | Review Pipeline (paquetes humanos) | En uso |
| `document_intelligence/` | DIE: análisis previo al parseo (~50 módulos, ~7.7k líneas) | Activo (V2) |
| `adapters/` | Puente V1↔V2 (kb, parser, review) | En uso |
| `backend/` | Backend Runner (`BACKEND_VERSION="2.0.0-rc1"`) | En uso (V2) |
| `src/api/` | FastAPI (health, procesar) | En uso (V2) |
| `knowledge/` | Base de conocimiento (catálogos, gold standard, concept graph) | En uso |
| `gold_standard/` | Gold Standard + RuntimeManager (runtime_gold) | En uso |
| `validation/` | Validación de balances | En uso |
| `scripts/` | Benchmark, compatibilidad CMCC, etc. | En uso |
| `reports/` | Informes de validación y auditoría (~200 archivos) | Referencia |

---

## 3. Mapa de dependencias

```
PDF ──► parsers (ParserPDF / ParserCore2) ──► CuentaRaw
        │
        ├─► document_intelligence (DIE, análisis previo) ──► IntelligenceReport
        ▼
   semantic/ (SemanticMatcher tiers 1-6)
        ▼
   learning/ (LearningEngine: learning_exact / learning_fuzzy)
        ▼
   cmcc/ (clasificador CMCC, shadow)
        ▼
   decision_engine/ (EvidenceAggregator: Parser 30% + Knowledge 30% + Validation 20%
                     + Structure 10% + DIE 10%)
        ▼
   review/ (ReviewPipeline: score = 50 unknown + 30 conf<0.5 + extras) ──► Excel
        ▼
   adapters/kb_adapter ──► backend/ ──► src/api (FastAPI)
```

---

## 4. Pipelines

### 4.1 Pipeline V1 (`pipeline/homologation_pipeline.py`)

- Usado por la UI (`app_validacion.py`) y por `adapters/kb_adapter.py`.
- Orquesta: ParserPDF → SemanticMatcher → LearningEngine → fallback regex → revisión.
- `_REGEX_FALLBACK` usa solo **7 de 37** patrones de `config/regex_rules.py`
  (índices 16, 19, 26, 31, 34, 35, 36), auditados con 100% precisión.
- `USE_LEGACY_ENGINE = False` (default) → la UI usa HomologationPipeline nuevo.

### 4.2 Pipeline V2 (`orchestrator/pipeline_v2.py` — `HomologationPipelineV2`)

Compone **9 adaptadores**:

1. **SIE** (Source Input Extraction) — entrada
2. **DIE** (Document Intelligence Engine) — análisis previo al parseo
3. **Parser** — extracción de cuentas
4. **KB** (Knowledge Base) — clasificación
5. **Decision** — motor de decisión
6. **Validation** — validación de balance
7. **Review** — revisión humana
8. **Coverage** — métricas de cobertura
9. **SelfQA** — auto-verificación

Usado por `backend/runner.py` (BackendRunner) y `run_pipeline_v2.py`.

---

## 5. Flujo completo

```
 1. ENTRADA        Documento PDF / Excel (estado financiero de institución)
 2. DETECCIÓN      document_intelligence → IntelligenceReport / DocumentProcessingContext
 3. PARSEO         ParserPDF (legacy, en uso) o ParserCore2 (parcial):
                   layout → orientación → OCR (si escaneado) → normalización → líneas
 4. EXTRACCIÓN     CuentaRaw (cuenta contable cruda: concepto + monto + tipo)
 5. RESOLUCIÓN     AccountTypeResolver: tipo de cuenta (activo/pasivo/patrimonio/resultado)
 6. CLASIFICACIÓN  LearningEngine + SemanticMatcher + Diccionarios + Código contable
 7. HOMOLOGACIÓN   mapeo a código CMCC (shadow/producción según flags)
 8. DECISIÓN       Decision Engine V2: agregación de evidencia ponderada → código + score
 9. REVISIÓN       ReviewPipeline: score < 0.85 → paquete de revisión humana (Excel)
10. VALIDACIÓN     Validación de balance (integridad, cuadratura)
11. EXPORTACIÓN    Excel homologado + actualización de base de conocimiento (gold standard)
12. COBERTURA      Métricas de cobertura y auto-QA (pipeline V2)
```

---

## 6. Base de conocimiento

### 6.1 Archivos

| Archivo | Rol |
|---|---|
| `knowledge/cmcc.json` | Catálogo CMCC (códigos, variantes, aliases). |
| `knowledge/concept_catalog.json` | Catálogo de conceptos contables. |
| `knowledge/concept_catalog.md` | Documento del catálogo (v1.0). |
| `knowledge/gold_standard.md` | Descripción del gold standard. |
| `knowledge/semantic_clusters.json` | Clusters semánticos. |
| `gold_standard/gold_standard.db` | Base canónica del benchmark (congelada). |
| `gold_standard/gold_standard_runtime.db` | Base runtime en evolución. |

### 6.2 Runtime (`gold_standard/runtime_manager.py`)

`RuntimeManager` administra el conocimiento en evolución en tres tablas separadas:

| Tabla | Rol |
|---|---|
| `runtime_gold` | Conocimiento en evolución (espejo del gold + proveniencia). |
| `promotion_history` | Auditoría de promociones y rollbacks (quién, cuándo, qué, de dónde). |
| `metadata` | Metadatos de la base runtime. |

- La tabla `runtime_gold` incluye la columna `activa` (1/0). El método `search_runtime` filtra por
  `activa=1`; las claves desactivadas se mantienen para auditoría (107 registros: 96 activos / 11
  inactivos, depuración P6).
- **Regla dura:** la base del benchmark (2660/2662) NO se modifica desde el runtime
  (`gold_standard/promotion.py`, `app_validacion.py`). El runtime solo lee de ella.

---

## 7. Feature flags (`pipeline/features.py`)

Clase `CMCCFeatureFlags`:

| Flag | Default | Efecto |
|---|---|---|
| `ENABLE_CMCC` | `False` | Clasificación CMCC desactivada |
| `ENABLE_CMCC_SHADOW` | `True` | CMCC corre en shadow (evalúa sin influir) |
| `ENABLE_CMCC_PRODUCTION` | `False` | Producción desactivada |
| `ENABLE_CMCC_ROLLBACK` | `False` | Rollback automático desactivado |
| `CMCC_THRESHOLD` | `0.95` | Umbral para producción automática |
| `CMCC_REVIEW_THRESHOLD` | `0.85` | Umbral para revisión humana |
| `ENABLE_ACCOUNT_TYPE_FILTER` | `False` | Filtro por tipo de cuenta desactivado |
| `ENABLE_REGEX_FALLBACK` | `True` | Regex fallback activo (7 patrones auditados) |
| `ENABLE_SEMANTIC_MATCHER` | `False` | Matcher semántico desactivado por flag |
| `ENABLE_DECISION_ENGINE` | `False` | Decision Engine V1 desactivado |

> Implicación: hoy el sistema **no produce decisiones CMCC en producción**; corre en modo
> shadow/benchmark hasta que se complete el rollout.

---

## 8. Decision Engine

### 8.1 Cuatro motores coexistentes

| Motor | Ubicación | Rol | Estado |
|---|---|---|---|
| V1 (5 reglas SM vs Regex) | `decision/` | Legado | OFF |
| V2 documental | `decision_engine/` | Activo en pipeline V2 | ACTIVO |
| Benchmark | `decision_v2/` | Pruebas (no conectado) | No integrado |
| Top-N (Sprint 39) | `classification_engine/` | Nuevo | No integrado |

### 8.2 Ponderación de evidencia (V2)

`EvidenceAggregator.aggregate`: Parser 30% + Knowledge 30% + Validation 20% + Structure 10% + DIE 10%.

### 8.3 Review pipeline (puerta humana)

- Score = 50 (unknown) + 30 (confianza < 0.5) + extras por método.
- Umbral `CMCC_REVIEW_THRESHOLD = 0.85`: bajo umbral → paquete de revisión humana (Excel).

---

## 9. Frontend y API

- **UI:** `app_validacion.py` (Streamlit) — validación manual y revisión humana (`UMBRAL_REVISION=0.85`).
- **API (FastAPI):** `src/api/main.py`:
  - `GET /health` — healthcheck.
  - `POST /api/v1/analisis/procesar` — endpoint de procesamiento.

---

## 10. Decisiones arquitectónicas documentadas (ADRs)

| ADR | Asunto |
|---|---|
| ADR-001 | Motor semántico (fases del rollout). |
| ADR-002 | Migración del Decision Engine. |

Detalle en `PROJECT_CONTEXT.md §13` y en la carpeta `architecture/`.

---

## 11. Reglas de mantenimiento

1. **No escribir en el benchmark (2660/2662):** la base gold está congelada; todo aprendizaje
   evoluciona en el runtime.
2. **Leer los documentos de riesgo** de cada módulo antes de modificar código (doble vía).
3. **CMCC corre en shadow** hasta completar el rollout de 4 fases (`docs/cmcc_rollout_plan.md`).
4. Cualquier cambio arquitectónico debe quedar registrado en `CHANGELOG.md` y este documento.
