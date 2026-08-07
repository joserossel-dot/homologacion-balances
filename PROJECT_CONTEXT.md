# PROJECT_CONTEXT — Sistema de Homologación de Balances

> **Documento maestro técnico del proyecto.** Consolida y preserva la totalidad de la
> documentación markdown existente en el repositorio (≈200 archivos, ≈50.000 líneas),
> las decisiones arquitectónicas, los riesgos, las limitaciones y los bugs registrados.
> Este documento **no elimina información, no resume de forma pérdida y no inventa datos**;
> cada sección indica su proveniencia y las cifras citadas corresponden a sus fuentes originales.

**Fecha de consolidación:** 2026-08-02
**Fuente primaria:** directorio raíz del repositorio `homologacion-balances/`
**Formato:** 15 secciones, cada una con referencia a los documentos fuente.

---

## 1. Objetivo

**Proveniencia:** `README.md`, `SUMMARY.md`, `COMPONENT_STATUS.md`, `architecture/architecture.md`, `docs/README_ARCHITECTURE.md`.

### 1.1 Qué es el proyecto

El sistema de **homologación de balances** procesa estados financieros en PDF (emitidos por
instituciones financieras y bancos) y los convierte a una **plantilla estándar** de cuentas
contables **CMCC** (Catálogo Maestro de Cuentas Contables), con el fin de:

1. **Extraer** cuentas contables desde documentos PDF heterogéneos (diferentes instituciones,
   layouts, idiomas, formatos).
2. **Homologar** cada cuenta extraída a un código estándar del catálogo (p. ej. `AC.01`,
   `ER.04`, `PC.06`).
3. **Decidir** con evidencia qué código asignar cuando varios métodos clasificadores discrepan.
4. **Someter a revisión humana** los casos de baja confianza.
5. **Exportar** el resultado a Excel y a una base de datos de conocimiento.

### 1.2 Objetivo de este documento

- Servir como **referencia única y completa** del estado del sistema: arquitectura, flujo,
  módulos, base de conocimiento, motores de decisión, parser, deuda técnica y roadmap.
- **Preservar decisiones arquitectónicas y sus justificaciones** (ADR-001, ADR-002, historial
  de evolución).
- Documentar **riesgos, limitaciones y bugs conocidos** tal como están registrados en
  `BUG_REGISTER.md`, `STABILIZATION_BACKLOG.md` y los informes de auditoría.
- Proveer un **índice de todos los documentos fuente** (sección 15) para trazabilidad.

### 1.3 Estado sintético del proyecto (2026-08)

- El sistema es de **doble vía**: coexisten el pipeline V1 (legado, en uso por la UI) y el
  pipeline V2 (`orchestrator/pipeline_v2.py`, backend `2.0.0-rc1`).
- **La mayoría de los feature flags están APAGADOS** por defecto (ver sección 3.5). El sistema
  homologa en modo `shadow` para CMCC.
- **Cobertura global real:** ~48.77% de las cuentas extraídas se homologan; la causa raíz
  dominante es el diccionario/catálogo incompleto (RC05, 58.9% del total no clasificado).
- **Conclusión de la última auditoría RC1 (2026-07-29): "No listo para piloto todavía".**

---

## 2. Filosofía

**Proveniencia:** `architecture/architecture.md`, `docs/ADR-001-Semantic-Architecture.md`,
`docs/ADR-002-Decision-Engine.md`, `docs/modules/decision_engine.md`,
`reports/classifier_precision.md`.

### 2.1 Homologar por evidencia, no por palabras

El sistema **no clasifica cuentas por matching de palabras sueltas**. La filosofía central es
acumular **evidencia** de múltiples métodos independientes y decidir por **consenso ponderado**:

- Cada método clasificador (código contable, diccionario exacto, diccionario fuzzy, matcher
  semántico por niveles, regex fallback, learning engine) emite un voto con evidencia.
- El **Decision Engine** pondera las evidencias (Parser 30%, Knowledge 30%, Validation 20%,
  Structure 10%, DIE 10% — ponderación documentada en `reports/decision_engine_validation.md`)
  y decide el código final.
- Un clasificador individual puede tener alta precisión en un subconjunto pero **agregar ruido**
  en los casos de conflicto; la decisión combinada supera a cada clasificador individual
  (ver sección 7.8).

**Evidencia de la auditoría de precisión real** (`reports/classifier_precision.md`, 2026-07-22,
319 cuentas de conflicto SM vs Regex, 248 verificadas):

| Clasificador | Precisión en conflictos | Veredicto |
|---|---|---|
| SM Tier 2 | 100.0% | GANADOR |
| SM Tier 5 | 100.0% | GANADOR |
| SM Tier 6 | 65.1% | BORDE |
| DecisionEngine V2 | 59.3% | BORDE (mejor que individuales) |
| Diccionario Fuzzy | 58.3% | BORDE |
| SM Tier 1 | 51.6% | AGREGA RUIDO EN CONFLICTOS |
| RegexFallback | 47.2% | AGREGA RUIDO EN CONFLICTOS |
| Diccionario Exacto | 42.3% | AGREGA RUIDO |
| Gold Standard Exacto | 38.4% | AGREGA RUIDO (auto-sembrado) |
| SM Tier 4 | 27.0% | AGREGA RUIDO |
| Código Contable | 26.9% | AGREGA RUIDO |

> **Advertencia crítica de la fuente:** estos números miden **qué clasificador gana cuando hay
> conflicto**, no la precisión general. En la población total (11.690 cuentas) la precisión de
> SM Tier 1 es 100% (754/754) cuando no hay conflicto con Regex. La muestra está sesgada hacia
> casos difíciles.

### 2.2 Por qué no se clasifica por palabras (justificación)

1. **Los conceptos contables son polisémicos y contextuales.** Una misma palabra ("Provisión",
   "Caja", "Banco") puede pertenecer a distintos códigos según el contexto y el tipo de cuenta.
2. **El matching exacto pierde contra variantes** (abreviaturas, singular/plural, bancos
   específicos como "Banco BCI USD").
3. **Los catálogos contienen keywords que matchean pero asignan código incorrecto al contexto**
   (en la auditoría, 90 de 186 errores de SM Tier 1 provienen del catálogo).
4. **La precisión real de los clasificadores individuales en conflictos es baja** (26.9% a
   58.3%); solo el ensamble ponderado alcanza rendimiento útil, y aun así requiere umbral de
   revisión humana.

### 2.3 Revisión humana obligatoria

- **Umbral de confianza para decisión automática:** score ≥ **0.85** → se asigna el código sin
  revisión. Bajo 0.85 → **revisión humana**.
- `app_validacion.py:46-47`: `UMBRAL_REVISION = 0.85`, `USE_LEGACY_ENGINE = False`
  (por defecto se usa el pipeline nuevo, no el motor legado).
- `pipeline/features.py`: `CMCC_REVIEW_THRESHOLD = 0.85`; `CMCC_THRESHOLD = 0.95` para
  producción automática.
- El **Review Pipeline** genera paquetes de revisión con score de revisión
  (50 = cuenta unknown + 30 = confianza < 0.5 + extras) y formateo Excel (sección 7.7).

### 2.4 Decisiones tomadas con evidencia

- **ADR-001 – Arquitectura semántica:** adoptar matching semántico por niveles (tiers) como
  método principal de homologación, con el catálogo semántico como base.
- **ADR-002 – Decision Engine:** adoptar un motor de decisión basado en evidencia ponderada y
  consenso para resolver conflictos entre clasificadores.

---

## 3. Arquitectura completa

**Proveniencia:** `architecture/architecture.md`, `architecture/module_dependencies.md`,
`docs/architecture/system_overview.md`, `docs/architecture/dependency_graph.md`,
`docs/architecture/feature_flags.md`, `docs/README_ARCHITECTURE.md`.

### 3.1 Visión general: doble vía (V1 y V2 coexisten)

**Advertencia de `docs/README_ARCHITECTURE.md`:** la arquitectura actual es de **doble vía**;
varios subsistemas legados y nuevos **se superponen**. Leer los documentos de riesgo de cada
módulo antes de modificar código.

```
┌───────────────────────────────────────────────────────────────────────┐
│                            DOBLE VÍA                                  │
│                                                                       │
│   V1 (LEGADO — EN USO por UI)          V2 (NUEVO — Backend 2.0.0-rc1) │
│   ─────────────────────────────        ──────────────────────────────  │
│   pipeline/homologation_pipeline.py    orchestrator/pipeline_v2.py    │
│   + SemanticMatcher + ParserPDF        HomologationPipelineV2         │
│   usado por: UI (app_validacion.py)    + 9 adaptadores                │
│              adapters/kb_adapter.py    usado por: backend/runner.py   │
│                                        run_pipeline_v2.py             │
│                                        FastAPI src/api/main.py        │
└───────────────────────────────────────────────────────────────────────┘
```

### 3.2 Mapa de módulos

| Directorio | Rol | Estado |
|---|---|---|
| `pipeline/` | Pipeline V1 (homologation_pipeline.py, features.py) | En uso (V1) |
| `orchestrator/` | Pipeline V2 (pipeline_v2.py, HomologationPipelineV2) | Activo (V2) |
| `parsers/` | ParserCore2 (nuevo) + legacy ParserPDF | Parcialmente integrado |
| `parsers/legacy/` | ParserPDF legacy (el que realmente corre) | En uso |
| `semantic/` | SemanticMatcher por tiers | En uso (V1) |
| `decision/` | Decision Engine V1 (5 reglas) | OFF (flag `ENABLE_DECISION_ENGINE`) |
| `decision_engine/` | Decision Engine V2 documental | ACTIVO en pipeline V2 |
| `decision_v2/` | Benchmark Decision Engine (no conectado) | No integrado |
| `classification_engine/` | Motor Top-N nuevo (Sprint 39) | No integrado |
| `learning/` | Learning Engine | En uso (shadow) |
| `cmcc/` | Clasificador CMCC + rollout | En uso (shadow) |
| `review/` | Review Pipeline (paquetes humanos) | En uso |
| `document_intelligence/` | DIE: análisis previo al parseo (~50 módulos, ~7.7k líneas) | Activo (V2) |
| `adapters/` | Puente V1↔V2 (kb_adapter, parser_adapter, review_adapter) | En uso |
| `backend/` | Backend Runner (BACKEND_VERSION="2.0.0-rc1") | En uso (V2) |
| `src/api/` | FastAPI (health, procesar) | En uso (V2) |
| `knowledge/` | Base de conocimiento (catálogos, gold standard, concept graph) | En uso |
| `validation/` | Validación de balances | En uso |
| `scripts/` | Benchmark, compatibilidad CMCC, etc. | En uso |
| `reports/` | Informes de validación y auditoría (~200 archivos) | Referencia |

### 3.3 Mapa de dependencias (resumen)

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
   decision_engine/ (EvidenceAggregator: Parser 30% + Knowledge 30% + Validation 20% + Structure 10% + DIE 10%)
        ▼
   review/ (ReviewPipeline: score = 50 unknown + 30 conf<0.5 + extras) ──► Excel
        ▼
   adapters/kb_adapter ──► backend/ ──► src/api (FastAPI)
```

### 3.4 Pipelines

#### Pipeline V1 (`pipeline/homologation_pipeline.py`)

- Usado por la UI (`app_validacion.py`) y por `adapters/kb_adapter.py:12-14`.
- Orquesta ParserPDF → SemanticMatcher → LearningEngine → fallback regex → revisión.
- `USE_LEGACY_ENGINE = False` (default) → la UI usa HomologationPipeline nuevo, no el motor
  de validación legado.
- `_REGEX_FALLBACK` (`pipeline/homologation_pipeline.py:59-62`): usa solo **7 de 37** patrones
  de `config/regex_rules.py` (índices 16, 19, 26, 31, 34, 35, 36), auditados con 100% precisión.

#### Pipeline V2 (`orchestrator/pipeline_v2.py` — `HomologationPipelineV2`)

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

### 3.5 Feature flags (valores por defecto verificados en `pipeline/features.py`)

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
> shadow/benchmark hasta que se complete el rollout (sección 12).

### 3.6 Frontend y API

- **UI:** `app_validacion.py` (usada para validación manual y revisión).
- **API (FastAPI):** `src/api/main.py` (118 líneas):
  - `GET /health` — healthcheck.
  - `POST /api/v1/analisis/procesar` — endpoint de procesamiento.

---

## 4. Flujo completo

**Proveniencia:** `architecture/processing_flow.md`, `docs/modules/adapters.md`,
`reports/root_cause_analysis/root_cause_analysis.md`.

### 4.1 Flujo paso a paso

```
 1. ENTRADA        Documento PDF / Excel (estado financiero de institución)
 2. DETECCIÓN      document_intelligence → IntelligenceReport / DocumentProcessingContext
 3. PARSEO         ParserPDF (legacy, en uso) o ParserCore2 (parcial):
                   layout → orientación → OCR (si escaneado) → normalización de texto → líneas
 4. EXTRACCIÓN     CuentaRaw (cuenta contable cruda: concepto + monto + tipo)
 5. RESOLUCIÓN     AccountTypeResolver: determina tipo de cuenta (activo/pasivo/...)
 6. CLASIFICACIÓN  LearningEngine + SemanticMatcher + Diccionarios + Código contable
 7. HOMOLOGACIÓN   mapeo a código CMCC (shadow/producción según flags)
 8. DECISIÓN       Decision Engine V2: agregación de evidencia ponderada → código final + score
 9. REVISIÓN       ReviewPipeline: score < 0.85 → paquete de revisión humana (Excel)
10. VALIDACIÓN     Validación de balance (integridad, cuadratura)
11. EXPORTACIÓN    Excel homologado + actualización de base de conocimiento (gold standard)
12. COBERTURA      Métricas de cobertura y auto-QA (pipeline V2)
```

### 4.2 Flujo del pipeline V1 (en uso por UI)

PDF → `ParserPDF.parse` (extrae líneas) → `HomologationPipeline` → SemanticMatcher (tiers 1-6)
→ LearningEngine → `_REGEX_FALLBACK` (7 patrones) → `AccountTypeResolver` → resultado con score
→ `app_validacion.py` compara vs `UMBRAL_REVISION=0.85` → revisión si corresponde.

### 4.3 Flujo del pipeline V2 (backend)

`backend/runner.py` (BackendRunner) → `pipeline_runner.py` (PipelineRunner) → `HomologationPipelineV2`
con 9 adaptadores → resultado `BackendResult` (`backend/backend_models.py:98`,
`pipeline_version="2.0.0-rc1"`) → `result_builder.py` (87 líneas) → `src/api/main.py`.

### 4.4 Datos de producción (URCA — Unified Root Cause Analysis, 2026-07-10)

**Población analizada:** 10.672 cuentas en 185 documentos.

| Métrica | Valor |
|---|---|
| Total cuentas | 10.672 |
| Clasificadas | 1.952 (18.3%) |
| UNKNOWN / no clasificadas | 8.720 |

**Causas raíz del NO clasificado (8.720):**

| Causa | Cuentas | % del no clasificado | Monto aprox. |
|---|---|---|---|
| RC05_DICTIONARY (concepto no está en diccionario) | 5.134 | 58.9% | USD 1.188M |
| RC06_CMCC (no mapeable al catálogo CMCC) | 2.637 | 30.2% | USD 865M |
| RC02_OCR (error de OCR / texto corrupto) | 473 | 5.4% | — |
| RC01_LAYOUT (problema de layout) | 292 | 3.3% | — |
| RC04_NORMALIZATION (normalización) | 184 | 2.1% | — |

**Simulación de impacto:** eliminar las causas raíz top-2 (RC05 + RC06) → cobertura **91.1%**;
top-3 → **95.5%**. Esto cuantifica el impacto directo de completar diccionario y catálogo CMCC.

---

## 5. Descripción técnica por módulo

**Proveniencia:** `docs/modules/*.md` (9 archivos), `docs/architecture/system_overview.md`,
inspección directa de código.

### 5.1 Parser

Ver sección 9 (detalle completo). Resumen:

- **ParserPDF** (`parsers/legacy/`, clase `ParserPDF`): el que **realmente corre** hoy, tanto en
  V1 (`pipeline/homologation_pipeline.py:36,380`) como en V2 (`adapters/parser_adapter.py`).
- **ParserCore2** (`parsers/`): nuevo parser modular, integración parcial:
  - `pdf_parser.py` — `ParserCore2` (430 líneas)
  - `analyzer.py` — `DocumentAnalyzer` (662 líneas)
  - `integration.py` (261) · `config.py` (141) · `layout_detector.py` (139)
  - `orientation_detector.py` (120) · `text_normalizer.py` (132) · `ocr_engine.py` (107)
  - `line_parser.py` (101) · `factory.py` (38)

### 5.2 Document Intelligence (DIE)

- `document_intelligence/` — **~50 módulos, ~7.7k líneas**.
- Analiza el documento **antes** del parseo y produce `IntelligenceReport` /
  `DocumentProcessingContext` (tipo de documento, familia, plantilla, selectores).
- Capas: motor central (`__init__.py`, `context.py`, `analyzer.py`), clasificadores de
  documento/familia/plantilla, selectores (parser, validation, confidence, recommendation),
  detectores (`BaseDetector`), firmas/repositorio (`FormatRepository`), extractores, DKB.
- Peso en decisión: DIE aporta 10% de la evidencia del Decision Engine V2.

### 5.3 Semantic Engine (`semantic/`)

- `SemanticMatcher` con **6 tiers** de matching:
  - Tier 1: keyword match (exacto sobre catálogo)
  - Tier 2: exacto con alta confianza (100% precisión en auditoría)
  - Tier 3: sin datos en auditoría (no participó)
  - Tier 4: fuzzy keyword match (27% precisión en conflictos — ruido)
  - Tier 5: exacto alta confianza (100% en auditoría)
  - Tier 6: fuzzy general (65.1% — borde)
- Conecta con `knowledge/concept_catalog.json`, `knowledge/cmcc.json`, `semantic_clusters.json`.

### 5.4 Learning Engine (`learning/`)

Ver sección 8. Resumen: aprende de cuentas previamente homologadas y verifica patrones;
métodos `learning_exact` / `learning_fuzzy`; en benchmark HOLDOUT aportó 101 hits
(84 exact + 17 fuzzy).

### 5.5 Classification Engine CMCC (`cmcc/`)

- Clasificador CMCC con fase de rollout en 4 fases (sección 12).
- Integrado con `pipeline/features.py` y `scripts/cmcc_benchmark.py`,
  `scripts/cmcc_compatibility_report.py`.
- Validación de conocimiento: 30 códigos, 163 variantes, 234 registros (sección 6).

### 5.6 Decision Engine

Ver sección 7 (detalle completo). Resumen de módulos:

- `decision/` — V1 (5 reglas SM vs Regex, OFF).
- `decision_engine/` — V2 **activo** en pipeline V2: `EvidenceAggregator.aggregate`,
  `evidence.py`, `conflict.py`, `confidence.py`.
- `decision_v2/` — Benchmark (no conectado): pesos hardcodeados `_EVIDENCE_WEIGHTS`,
  consenso/prioridad/tie-break; **bug TB-3** en `decision_v2/engine.py:496-528`.
- `classification_engine/` — Top-N nuevo (Sprint 39): generation → scoring → explanation.

### 5.7 Review Pipeline (`review/`)

- `cmcc_review_pipeline.py` (367 líneas) · `cmcc_review_models.py`
- `review_package_builder.py` (325) · `review_metrics.py` (176) · `review_models.py` (191)
- `excel_formatter.py` (286) · `run_review_package.py` · `adapters/review_adapter.py` (32)
- Score de revisión: 50 (unknown) + 30 (confianza < 0.5) + extras por método.

### 5.8 Adapters (`adapters/`)

- `kb_adapter.py:12-14` — usa pipeline V1.
- `parser_adapter.py` — usa ParserPDF legacy dentro de V2.
- `review_adapter.py` (32 líneas).

### 5.9 Backend (`backend/`)

- `runner.py` — `BackendRunner` (45 líneas)
- `pipeline_runner.py` — `PipelineRunner` (74)
- `config.py` — `BackendConfig` (41) con `BACKEND_VERSION = "2.0.0-rc1"`
- `backend_models.py` — (98) `BackendResult.pipeline_version = "2.0.0-rc1"`
- `execution_manager.py`, `artifact_manager.py`, `result_builder.py` (87), `backend_logger.py`

### 5.10 Validación (`validation/`)

- Validación de cuadratura e integridad de balances.
- `app_validacion.py` — UI de validación con `UMBRAL_REVISION=0.85`.
- Informe RC1: integridad contable 48.5/100 (sección 10).

---

## 6. Base de conocimiento

**Proveniencia:** `knowledge/README.md`, `knowledge/gold_standard.md`,
`reports/cmcc_knowledge_validation.md`, `reports/knowledge/knowledge_report.md`,
`knowledge/concept_catalog.md`, inspección directa de los JSON y la base SQLite.

### 6.1 Archivos de conocimiento

| Archivo | Contenido | Tamaño / métricas |
|---|---|---|
| `knowledge/cmcc.json` | Catálogo CMCC (52 registros en lista; cada uno con id, código, nombre, categoría, tipo_estado_financiero, sinónimos, abreviaturas, variantes) | 274 KB |
| `knowledge/concept_catalog.json` | Catálogo de conceptos semánticos (dict con 5 claves de nivel superior) | 242 KB |
| `knowledge/concept_graph.json` | Grafo de conceptos (red semántica) | 16.1 MB |
| `knowledge/gold_standard.json` | Gold standard de cuentas cotejadas | 934 KB |
| `knowledge/schema.json` | Esquema de la base de conocimiento | 2.7 KB |
| `catalogo_maestro.json` | Catálogo maestro (61 códigos CMCC con metadatos por código: codigo_estandar, nombre_estandar, categoria, tipo_estado, naturaleza, signo_normal, es_deuda_financiera, es_activo_liquido, afecta_ebitda, descripcion, clasificación) | raíz |
| `diccionario.json` | Diccionario de conceptos→cuentas (860 entradas) | raíz |
| `diccionario_actualizado.json` | Diccionario actualizado (781 entradas) | raíz |
| `diccionario_optimizado.json` | Diccionario optimizado (712 entradas) | raíz |
| `gold_standard.db` | Base SQLite de conocimiento validado | 234 registros |

### 6.2 Validación del conocimiento CMCC (2026-07-27, `gold_standard.db`)

`reports/cmcc_knowledge_validation.md`:

| Métrica | Valor |
|---|---|
| Códigos CMCC con conocimiento | 30 |
| Variantes registradas | 163 |
| Registros de conocimiento | 234 |
| Variantes promedio por código | 5.43 |

**Confianza del conocimiento por código:**

| Confianza | Códigos |
|---|---|
| Alta | 9 |
| Media | 2 |
| Baja | 19 |

**Distribución por familia (códigos / variantes):**

| Familia | Códigos | Variantes |
|---|---|---|
| AC (Activo Corriente) | 6 | 61 |
| ANC (Activo No Corriente) | 4 | 28 |
| PC (Pasivo Corriente) | 7 | 73 |
| PNC (Pasivo No Corriente) | 2 | 2 |
| PAT (Patrimonio) | 4 | 19 |
| ER (Estado de Resultados) | 7 | 51 |

### 6.3 Catálogo Maestro de Conceptos Contables (`knowledge/concept_catalog.md`, v1.0)

- **Total conceptos:** 78 (fuente: `reports/semantic_clusters.json`).
- Confianza: ALTA 22 · MEDIA 16 · BAJA 40.
- 40 conceptos "necesitan subdivisión" y tienen problemas de calidad (marcados ⚠️✂️).
- Top conceptos por cuentas: PROPIEDAD (541, ANC.01), DEPRECIACION (321, ER.07),
  BANCOS (320, AC.01), GASTOS (319, ER.04), IMPUESTOS (317, PC.05), PRESTAMOS (298, PC.02).

### 6.4 Cobertura del catálogo vs población (Knowledge Discovery, 2026-07-07)

`reports/knowledge/knowledge_report.md`:

| Métrica | Valor |
|---|---|
| Total cuentas analizadas | 10.672 |
| No clasificadas | 8.762 |
| Clusters semánticos | 1.168 |
| Reglas candidatas | 534 |
| Grupos sinónimos | 393 |
| Recomendaciones priorizadas | 927 |

### 6.5 Gold Standard

- `gold_standard.db` (SQLite) y `knowledge/gold_standard.json`: cuentas cotejadas contra
  ground truth para validación.
- **Advertencia de auditoría:** el gold standard **auto-sembrado no es confiable**
  (precisión Gold Standard Exacto 38.4% en conflictos; error 61.6%), ver sección 7.8.
- Solo **234 registros** validados → cobertura insuficiente para producción.

### 6.6 Riesgo de polución del conocimiento

- Diagnóstico previo (cuenta "PROMESA OFICINA 22"): los catálogos pueden **polucionarse** con
  variantes sueltas y mapeos incorrectos:
  - `concept_catalog.json`: "OFICINA"→GASTOS con tier_1 score 1.0.
  - `cmcc.json`: variantes sueltas "oficina" en ER.01/ER.02.
  - `diccionario.json`: "Promesa Edificio Cordillera (Deja) UF"→ANC.06.
- Impacto: un catálogo incorrecto produce **decisiones incorrectas con alta confianza**
  (los pesos `_EVIDENCE_WEIGHTS` dan sm_tier_1 = 1.00). Ver secciones 7.6 y 11.

---

## 7. Decision Engine

**Proveniencia:** `docs/modules/decision_engine.md`, `reports/decision_engine_validation.md`,
`reports/classifier_precision.md`, inspección de `decision_engine/`, `decision_v2/`,
`classification_engine/`.

### 7.1 Cuatro motores coexistentes

| Motor | Ubicación | Estado | Notas |
|---|---|---|---|
| V1 (decision) | `decision/` | OFF | 5 reglas SM vs Regex; flag `ENABLE_DECISION_ENGINE=False` |
| V2 documental | `decision_engine/` | **ACTIVO en pipeline V2** | `EvidenceAggregator.aggregate` |
| Benchmark V2 | `decision_v2/` | No conectado | Pesos hardcodeados `_EVIDENCE_WEIGHTS`; **bug TB-3** |
| Top-N nuevo | `classification_engine/` | No integrado | Sprint 39: generation → scoring → explanation |

### 7.2 Ponderación de evidencia (V2 documental)

`reports/decision_engine_validation.md` (Sprint 25):

| Fuente de evidencia | Peso |
|---|---|
| Parser | 30% |
| Knowledge | 30% |
| Validation | 20% |
| Structure | 10% |
| DIE (Document Intelligence) | 10% |

> **Advertencia de código:** en `decision_v2/` los pesos están hardcodeados en
> `_EVIDENCE_WEIGHTS` y **no coinciden necesariamente** con la ponderación documental del
> motor V2 activo (`decision_engine/`). El motor V2 activo es el de referencia.

### 7.3 Reglas de decisión (V1, `decision/`)

El motor V1 aplica 5 reglas que comparan SemanticMatcher (SM) vs Regex para resolver
conflictos. Está desactivado por defecto.

### 7.4 Consenso, prioridad y tie-break (benchmark `decision_v2/`)

- `decision_v2/engine.py` implementa: agregación de evidencia → consenso entre métodos →
  resolución por prioridad → tie-break.
- **Bug TB-3** (`decision_v2/engine.py:496-528`): en el tie-break se pasa `ev.source` como
  tipo de evidencia en lugar del tipo real, lo que puede producir empates mal resueltos.

### 7.5 Motor Top-N (`classification_engine/`, Sprint 39)

- Genera las N mejores hipótesis de clasificación, las puntúa y entrega explicación.
- **No integrado** al pipeline: no altera decisiones actuales.

### 7.6 Pesos y reglas especiales del diagnóstico

- `_EVIDENCE_WEIGHTS` dan a `sm_tier_1` peso **1.00**: una coincidencia de catálogo tier 1
  domina la decisión.
- Reglas especiales R1/R4/R5 del motor de decisión **fuerzan `final_code`** en ciertos
  contextos (por ejemplo, cuando la cuenta ya viene con código contable explícito).
- Consecuencia: si el catálogo está polucionado, la alta confianza se transfiere a un código
  incorrecto sin pasar a revisión.

### 7.7 Review pipeline (puerta humana)

- Score de revisión: **50** (cuenta unknown) + **30** (confianza < 0.5) + extras según método.
- `UMBRAL_REVISION = 0.85` (`app_validacion.py:46-47`): bajo 0.85 → revisión humana.
- `CMCC_REVIEW_THRESHOLD = 0.85`; `CMCC_THRESHOLD = 0.95` (producción automática).
- Genera paquetes de revisión (`review_package_builder.py`, `excel_formatter.py`).

### 7.8 Resultados reales del Decision Engine V2 (auditoría, 2026-07-22)

**Precisión en las 319 cuentas de conflicto SM vs Regex (248 verificadas):**

| Métrica | Valor |
|---|---|
| Precision | 59.3% |
| Recall | 116.7% |
| F1 | 78.6% |
| Correctas | 147 |
| Incorrectas | 101 |

- **El ensamble ponderado (DEv2) supera a cualquier clasificador individual** en conflictos
  (59% vs ~50%), pero aún comete ~41% de error en los casos difíciles.
- **Threshold óptimo recomendado por la fuente:** score ≥ 0.85 para decisión automática;
  bajo eso, revisión humana.

### 7.9 Recomendaciones de la fuente (auditoría)

1. SM Tier 1-2 deben ganar siempre cuando no hay conflicto (infalibles).
2. En conflicto SM vs Regex la decisión es 50/50 → se necesita más evidencia.
3. **El problema real es el catálogo**: 90 de 186 errores de SM T1 provienen de asignación
   incorrecta del código CMCC en el catálogo.
4. Limpiar el gold standard (auto-sembrado no confiable).
5. El DEv2 con weighted ensemble es superior a cualquier clasificador individual.
6. Threshold óptimo 0.85.

---

## 8. Learning Engine

**Proveniencia:** `docs/modules/learning_engine.md`, `reports/benchmark*`,
`reports/decision_engine_validation.md`.

### 8.1 Qué es

El `learning/` del sistema aprende de cuentas previamente homologadas (y de los patrones
verificados) para clasificar cuentas nuevas. Genera dos métodos de clasificación:

- **`learning_exact`**: coincidencia exacta contra el conocimiento aprendido.
- **`learning_fuzzy`**: coincidencia difusa contra el conocimiento aprendido.

### 8.2 Qué aprende y qué nunca aprende

**Aprende:**
- Mapeos concepto→código a partir de cuentas homologadas en documentos procesados.
- Patrones de variantes (abreviaturas, instituciones, sinónimos) descubiertos en clusters
  semánticos (1.168 clusters, sección 6.4).

**Nunca aprende (limitaciones documentadas):**
- No re-escribe el catálogo semántico en caliente; los conceptos nuevos deben pasar por
  revisión humana antes de convertirse en regla (recomendación de la auditoría).
- No aprende layout de documentos nuevos por sí solo; depende del parser y del DIE.

### 8.3 Resultados del Learning Engine en benchmark HOLDOUT (2026-07-26)

| Método | Hits |
|---|---|
| learning_exact | 84 |
| learning_fuzzy | 17 |
| **Total learning** | **101** |

- En la certificación previa (2026-07-09): learning_exact 89 (8.2%), learning_fuzzy 14 (1.3%).

### 8.4 Riesgo

- El aprendizaje de datos auto-sembrados propaga errores (gold standard no confiable,
  sección 6.5). Las reglas aprendidas deben validarse antes de integrarse a producción.

---

## 9. Parser

**Proveniencia:** `ARQUITECTURA_PARSER.md`, `docs/parser_core_2.0.md`,
`docs/modules/parser.md`, `reports/root_cause_analysis/root_cause_analysis.md`.

### 9.1 Doblе parser: legacy vs ParserCore2

- **ParserPDF** (`parsers/legacy/`): el que **realmente corre** hoy:
  - V1: `pipeline/homologation_pipeline.py:36,380`.
  - V2: `adapters/parser_adapter.py`.
- **ParserCore2** (`parsers/`): nuevo parser modular con integración **parcial**:

| Módulo | Clase | Líneas |
|---|---|---|
| `pdf_parser.py` | `ParserCore2` | 430 |
| `analyzer.py` | `DocumentAnalyzer` | 662 |
| `integration.py` | — | 261 |
| `config.py` | — | 141 |
| `layout_detector.py` | — | 139 |
| `orientation_detector.py` | — | 120 |
| `text_normalizer.py` | — | 132 |
| `ocr_engine.py` | — | 107 |
| `line_parser.py` | — | 101 |
| `factory.py` | — | 38 |

### 9.2 Etapas del parseo

1. **Layout detection** — detecta estructura del documento (tablas, columnas, secciones).
2. **Orientation detection** — detecta/corrige orientación de página.
3. **OCR** — para documentos escaneados (`ocr_engine.py`).
4. **Normalización de texto** — limpieza, unificación de caracteres (`text_normalizer.py`).
5. **Line parsing** — convierte texto en líneas/cuentas (`line_parser.py`).
6. **Análisis** — `DocumentAnalyzer` produce las cuentas extraídas.

### 9.3 Errores de parser en producción (URCA)

- **RC02_OCR:** 473 cuentas (5.4% del no clasificado) por error de OCR / texto corrupto.
- **RC01_LAYOUT:** 292 cuentas (3.3%) por problemas de layout.
- **RC04_NORMALIZATION:** 184 cuentas (2.1%) por problemas de normalización.

### 9.4 Precisión de extracción

- Benchmark HOLDOUT: precisión de extracción promedio **16.19%** (baja; el reto principal es
  la variabilidad de documentos).
- El parser correcto produce líneas de alta calidad; la baja precisión se atribuye
  principalmente a layouts variados y OCR (ver secciones 4.4 y 10.3).

---

## 10. Estado actual

**Proveniencia:** `COMPONENT_STATUS.md`, `benchmark/benchmark_summary.md`,
`reports/certification/certification_report.md`, `reports/classifier_precision.md`,
`AUDITORIA_RC1.md`, `reports/root_cause_analysis/root_cause_analysis.md`.

### 10.1 Benchmark HOLDOUT (2026-07-26, 20 archivos)

`benchmark/benchmark_summary.md`:

| Métrica | Valor |
|---|---|
| Cuentas detectadas | 2.692 |
| Homologadas | 1.251 (48.77%) |
| Unknown (no clasificadas) | 1.030 |
| Learning hits | 101 |
| Precisión extracción promedio | 16.19% |
| Confianza global promedio | 0.1611 |

**Distribución por método:**

| Método | Cuentas |
|---|---|
| code | 60 |
| dict_exact | 29 |
| dict_fuzzy | 22 |
| learning_exact | 84 |
| learning_fuzzy | 17 |
| regex | 9 |
| unclassified | 1.030 |

### 10.2 Certificación previa (2026-07-09)

- Holdout: 20 documentos, 2.692 cuentas parseadas, 1.083 clasificadas.
- Gold Standard cotejado: 103 cuentas (89 directas + 14 vía fuzzy).
- **Accuracy 100%** sobre las 103 cotejadas (Macro F1 1.0, Kappa 1.0).
- Distribución: unclassified 872 (80.5%), learning_exact 89, code 59, dictionary_exact 30,
  dictionary_fuzzy 19, learning_fuzzy 14.
- > Nota: 100% de accuracy solo en las cuentas **cotejadas**; la cobertura global sigue baja.

### 10.3 Auditoría RC1 (2026-07-29) — "No listo para piloto todavía"

- **Precisión real (319 cuentas auditadas):** Diccionario Exacto 42.3% · Código 26.9% ·
  Regex 47.2%.
- **Integridad contable:** 48.5/100.
- **Componentes:** 40 construidos · 15 integrados (37.5%) · **0 certificados**.
- **Duplicación de código estimada:** 15-20% (ver sección 11).
- `gold_standard.db`: solo 234 registros.
- Feature flags de producción: OFF (sección 3.5).

### 10.4 Estado de flags y producción

- `ENABLE_CMCC = False`, `ENABLE_CMCC_PRODUCTION = False`, `ENABLE_CMCC_SHADOW = True`.
- Backend `2.0.0-rc1`. 734 tests pasando (Sprint 26.1).
- Conclusión: el sistema está en **modo shadow/benchmark**; no emite decisiones en producción.

---

## 11. Deuda técnica

**Proveniencia:** `BUG_REGISTER.md` (2026-07-26), `STABILIZATION_BACKLOG.md`,
`AUDITORIA_RC1.md`, `docs/history/architecture_evolution.md`.

### 11.1 Resumen ejecutivo

- **33 ítems** registrados en el backlog de estabilización (6 P0, 11 P1, 11 P2, 5 P3).
- **Código sin tests:** `app_validacion.py` (1.340 líneas, el archivo más grande) y
  `parser_universal.py` (831 líneas, parser core) **no tienen ningún test**.
- **Duplicación de código estimada:** 15-20% (auditoría RC1).
- **Doble pipeline, doble parser, 4 motores de decisión, 2 backends** sin consolidar.

### 11.2 Deuda estructural (evolución de la arquitectura)

1. **Doble pipeline** (V1/V2) con solapamiento de responsabilidades.
2. **Doble parser** (`ParserPDF` legado vs `parsers/` ParserCore2).
3. **4 motores de decisión** sin consolidar.
4. **2 backends** (V2 `backend/` vs API legada `src/api/`).
5. Enums duplicados (`document_intelligence/models.py` vs `models.py`).
6. Módulos monolíticos (`parser_universal.py` ~1.000 líneas, `homologation_pipeline.py` ~640).
7. Acoplamientos inversos (p.ej. `decision_v2 → app_validacion`).
8. Configuración dispersa (flags por módulo, umbrales hardcodeados).

### 11.3 Bugs críticos (BUG_REGISTER.md, 2026-07-26)

| ID | Bug | Impacto |
|---|---|---|
| C-1 | `app_validacion.py` (1.340 líneas) sin tests | Regresiones sin detección; propagación automática (líneas 540-570) sin verificación |
| C-2 | `parser_universal.py` (831 líneas) sin tests | Regresiones de parseo/OCR/rotación no detectables |
| C-3 | Dos pipelines de clasificación sin tests de equivalencia | Legacy y nuevo pueden divergir; `SHADOW_MODE=True` sin aserciones |
| C-4 | 11 tests fallan en `test_split_ac01.py` | Módulo `split_ac01` no confiable; reportes rotos |

### 11.4 Bugs altos y medios (resumen)

- **A-1:** 8+ feature flags sin tests de combinaciones ni matriz documentada.
- **A-2:** Dead code `pipeline/new_pipeline.py` (clase `NewPipeline` nunca importada).
- **A-3:** `reglas_especiales.py` (reglas D1-D5) y `clasificador_codigo_cuenta.py` sin tests.
- **A-4:** `config/release.yml` define gates de release que **ningún código lee**.
- **A-5:** `reports/` con 5.000+ archivos sin política de retención.
- **M-1:** `gold_standard_bench.db` vacía (0 registros).
- **M-2:** 3 diccionarios inconsistentes (860 vs 781 vs 712 entradas, hasta 13.8% de diferencia).
- **M-3:** `learning_queue.json` nunca retroalimenta el Gold Standard.
- **M-4:** `review_ui/reviews.db` con 251 decisiones no visibles desde la app.
- **M-5:** 14+ archivos de test exceden timeout → suite completa no ejecutable.
- **M-6:** `pyproject.toml:20` referencia `src.cli:main` que no existe.

### 11.5 Backlog de estabilización (STABILIZATION_BACKLOG.md)

Priorización: P0 = bloqueante, P1 = alto, P2 = medio, P3 = bajo.

- **Bugs:** B-01 (P0, split_ac01), B-02 (P1, CLI inexistente), B-03 (P1, scipy faltante),
  B-04 (P2, gold_standard_bench.db vacía), B-05 (P2, learning_queue no retroalimenta),
  B-06/B-07 (P3).
- **Deuda imprescindible:** T-01/T-02/T-03 (P0, sin tests de app_validacion, parser,
  equivalencia de pipelines), T-04 a T-09 (P1), T-10 a T-15 (P2/P3).
- **Riesgos producción:** R-01 (P0, sin cobertura del flujo principal), R-02 (P0, parser sin
  tests), R-03 (P1, pipelines divergen), R-04 (P1, flags sin testear), R-05 (P1, diccionario
  inconsistente), R-06 (P2, gold standard no retroalimentado), R-07 (P2, suite no ejecutable),
  R-08 (P2, scipy), R-09 (P2, módulos orphaned: `confidence/`, `evidence/`, `knowledge_base/`,
  `accounting_knowledge/`, `assessment/` sin consumidores), R-10 (P3, FastAPI sin uso).

### 11.6 Deuda técnica del conocimiento (auditorías)

- **Catálogos polucionados** (diagnóstico "PROMESA OFICINA 22"): `concept_catalog.json`
  ("OFICINA"→GASTOS tier_1 score 1.0), `cmcc.json` (variantes sueltas "oficina" en ER.01/ER.02),
  `diccionario.json` ("Promesa Edificio Cordillera (Deja) UF"→ANC.06). Riesgo: decisiones
  incorrectas con alta confianza sin pasar a revisión.
- **Gold standard auto-sembrado no confiable** (Gold Standard Exacto 38.4% en conflictos).
- **Reglas especiales R1/R4/R5** que fuerzan `final_code` sin pasar por revisión (sección 7.6).
- **Bug TB-3** en `decision_v2/engine.py:496-528` (tie-break pasa `ev.source` como tipo).

---

## 12. Roadmap

**Proveniencia:** `architecture/roadmap.md`, `docs/cmcc_rollout_plan.md`,
`docs/ADR-001-Semantic-Architecture.md`, `docs/ADR-002-Decision-Engine.md`,
`docs/history/architecture_evolution.md`.

### 12.1 Roadmap de sprints (arquitectura objetivo)

`architecture/roadmap.md` — próximos 6 sprints:

| Sprint | Nombre | Entrega |
|---|---|---|
| 22 | Intelligent Document Router (IDR) | IDR operational |
| 23 | Confidence Engine | Sistema de confianza por cuenta y global |
| 24 | Coverage Engine | Sistema de cobertura contra KB |
| 25 | Self QA | Auto-validación del pipeline completo |
| 26 | Production Pipeline | Pipeline listo para producción |

**Sprint 22 — IDR:** Type Detector, Family Classifier, Format Detector,
DocumentContext Factory, Pipeline Integration, tests ≥90%.

**Sprint 23 — Confidence Engine:** FuzzySignal, ConsensusSignal, ValidationSignal,
KBCoverageSignal, Weighted Aggregator, Per-Account Confidence, Global Confidence,
Threshold Engine (auto_approve / require_review / critical).

**Sprint 24 — Coverage Engine:** kb_coverage_pct, missing_codes, unresolved_accounts,
Section Coverage, Recommendation Generator (auto_approve/review/add_to_kb), Prioritization.

**Sprint 25 — Self QA:** Regression Detection vs gold_standard, Quality Metrics Dashboard,
Benchmark Automation (HOLDOUT), Drift Monitoring (tipos documentales, UNKNOWNs, confianza,
tiempo), Alert System, Shadow Mode.

**Sprint 26 — Production Pipeline:** Pipeline Orchestrator
(`IDR → SIE → TemplateRepo → Parser → KB → BIV → Confidence → Coverage → Review → Export`),
Error Recovery, Progress Tracking, Structured Logging, Metrics Export, Graceful Shutdown,
CLI Final.

**Prioridades:** IDR y Confidence son críticos; Coverage y Self QA altos; Production depende
de los 4 anteriores.

### 12.2 Roadmap del ADR-001 (fases del motor semántico)

| Fase | Estado | Contenido |
|---|---|---|
| Phase 1 | ✅ Complete | ParserPDF, LayoutDetector, AccountTypeResolver, AccountTypeFilter, 182 PDFs |
| Phase 2 | ✅ Complete | HomologationPipeline, CMCCFeatureFlags, RegexFallback (7 reglas), Concept Catalog (78 conceptos) |
| Phase 3 | 🔄 In Design | SemanticNormalizer, SemanticMatcher (RapidFuzz), CMCCClassifier, benchmark, producción |
| Phase 4 | ⬜ | Human Review feedback loop, expansión automática del catálogo, threshold auto-tuning, A/B testing, active learning |
| Phase 5 | ⬜ | Dashboard de monitoreo, retraining, drift detection, multi-modal matching, self-healing |

### 12.3 Roadmap del ADR-002 (migración del Decision Engine)

- **Phase 0** (actual): DecisionEngine v1, solo SM vs Regex, 5 reglas.
- **Phase 1:** v2 corre en paralelo (ambas salidas logueadas, sin impacto).
- **Phase 2:** v2 en shadow con audit trail; v1 sigue decidiendo.
- **Phase 3:** v2 default; v1 como rollback; flag `ENABLE_DECISION_ENGINE_V2=False` (default).

### 12.4 Plan de rollout CMCC (4 fases, `docs/cmcc_rollout_plan.md`)

Cada fase tiene entry/exit criteria explícitos; ninguna empieza hasta que la anterior esté
GREEN; rollback < 1 segundo.

| Fase | Sprint | Objetivo | Estado |
|---|---|---|---|
| **Phase 0** | 26.1 | Infraestructura de flags + métricas + tests | ✅ **COMPLETA** (734 tests pass; P0.1–P0.8 entregados) |
| Phase 1 | 2 | Shadow validation (CMCC corre en todas las UNKNOWN, sin afectar clasificación) | Pendiente |
| Phase 2 | 3 | Scientific validation (HOLDOUT 20 PDFs, gold standard 103 cuentas, triple run, GO/NO-GO) | Pendiente |
| Phase 3 | 4 | Producción (staging 24h → blue/green → 10% → 50% → 100% tráfico) | Pendiente |
| Phase 4 | Ongoing | Monitoreo y tuning (threshold mensual, drift semanal, optimizaciones) | Pendiente |

**Metas Phase 2 (GO conditions):** cobertura ≥ 33.3% (+15pp vs baseline 18.3%), precisión ≥
baseline, FP < 1%, sin regresiones HIGH/CRITICAL.

**Optimizaciones a largo plazo (Phase 4):** bajar threshold a 0.90 (+500 cuentas), CMCC en
fallback fuzzy (+200), CMCC en learning (+150), deprecar diccionario fuzzy.

---

## 13. Historial arquitectónico

**Proveniencia:** `docs/history/architecture_evolution.md` (fuente: `git log`),
`docs/ADR-001-Semantic-Architecture.md`, `docs/ADR-002-Decision-Engine.md`.

### 13.1 Línea de tiempo (commits recientes)

```
1b555a8  Versión inicial — plataforma homologación balances tributarios
102ea44  Orquestador central del pipeline implementado y probado
8f76e11  API REST funcional (TaxFolderEngine, parser, Postgres SSL)
└── (serie de fixes Docker/Render/imports/rutas) ────────────────┘
b2c24a2  Sprint 28.5: parser hardening, knowledge engine, review pipeline
a7a4322  Checkpoint MVP producto antes de automatización clasificación
e0a8933  DocumentAnalyzer: análisis estructural pre-parseo
72e62b6  Integrar DocumentAnalyzer como capa previa al parser
2d16c4e  Sprint 1: context aware architecture y parser hygiene
6c9e0ce  Stabilize pipeline V2 y restaurar suite verde
b455813  Sprint 38: classification decision engine con Top-N explicable
40aa083  Sprint 37: integrar Document Intelligence y arquitectura knowledge base
19500df  docs: architecture, audits y documentación técnica
```

### 13.2 Fases de evolución

1. **MVP y API** (→ `8f76e11`): plataforma de homologación de balances tributarios chilenos,
   `PipelineOrquestador`, parser, API REST con PostgreSQL (módulo `src/`), despliegue
   (Docker, Render).
2. **Sprint 28.5 — hardening** (`b2c24a2`): `parser_universal.py` madura (PDF + OCR + layout),
   knowledge engine, review pipeline, `app_validacion.py` como UI Streamlit.
3. **DocumentAnalyzer** (`e0a8933`/`72e62b6`): capa de análisis estructural pre-parseo
   (`parsers/analyzer.py` → `ExtractionContext`).
4. **Sprint 1 — context-aware** (`2d16c4e`): `document_context/`, `orchestrator/pipeline_v2.py`
   (`HomologationPipelineV2`), adapter chain SIE→DIE→Parser→KB→Decision→Validation→Review→
   Coverage→SelfQA. Nace V2 junto a V1. Parser hygiene (ParserCore2 + `ParserConfig`).
5. **Stabilize V2** (`6c9e0ce`): suite de tests verde.
6. **Sprint 37 — DIE + Knowledge Base** (`40aa083`): `document_intelligence/` (clasificadores,
   extractores, conocimiento documental, minería, trainer), arquitectura `knowledge/`,
   `knowledge_base/`. ADRs publicados.
7. **Sprint 38 — Motor de clasificación** (`b455813`): `classification_engine/` Top-N
   explicable con `WeightConfig`; 4 motores de decisión coexistiendo.
8. **Documentación** (`19500df`): base de documentación técnica `docs/`.

### 13.3 Decisiones arquitectónicas documentadas (ADRs)

**ADR-001 (2026-07-22) — Arquitectura Semántica:**
- Problema: 182+ formatos PDF distintos, OCR variable, mapeo manual no escala.
- Meta: producir mapping cuenta→CMCC con alta precisión y recall medible, reducir UNKNOWN a
  <5% y minimizar revisión humana.
- **Decisiones:**
  1. **RapidFuzz + Concept Catalog sobre embeddings** (precisión 88-95%, 2-5ms/cuenta,
     JSON-only updates, explicable; embeddings no distinguen GASTOS_ADMIN de GASTOS_VENTA).
  2. **6-tier matching** (exact keyword 1.0 → synonym 0.95 → abbreviation 0.90 → fuzzy keyword
     0.85×ratio → fuzzy synonym 0.75×ratio → root word 0.60; type bonus ×1.10).
  3. **Concept Catalog sobre reglas hardcodeadas** (versión semver MAJOR.MINOR, JSON
     desacoplado del código).
- Fases: 1-2 completas; 3 (semántica) en diseño; 4 (learning) y 5 (mejora continua) futuras.

**ADR-002 (2026-07-22) — Decision Engine v2 (Multi-Evidence Fusion):**
- Contexto: 7 clasificadores independientes + señales extra (LearningEngine, CMCC).
- Datos de 11.696 cuentas / 182 PDFs: SM T1-2 infalibles (754 + 268 cuentas); Regex captura
  más casos SM-unknown (174); Código Contable 0% acuerdo con SM; GS exacto 35.5% acuerdo.
- **Decisiones:**
  1. **Weighted ensemble con hard-rule overrides para SM T1-2.**
  2. **Colección paralela** de evidencia (no pipeline secuencial).
  3. **Consensus bonus** (×1.15 con ≥2 clasificadores, ×1.25 con ≥3, cap 1.0) sobre max score.
  4. **Solo classifier penalty** (×0.90; SM T6 solo cap 0.50).
  5. **Shadow deployment** antes de cutover.
- Reglas R1-R12, tie-breaking TB-1 a TB-5, pesos de evidencia, casos HR-1 a HR-5,
  métricas de auditoría (Auto-decision rate ≥95%, Consensus rate ≥80%, Review rate <5%...).

---

## 14. Glosario

| Término | Definición |
|---|---|
| **CMCC** | Catálogo Maestro de Cuentas Contables (estándar de códigos, p. ej. AC.01, ER.04). |
| **Homologación** | Proceso de mapear una cuenta de un balance heterogéneo a un código CMCC estándar. |
| **UNKNOWN** | Cuenta que ningún clasificador logra homologar; va a revisión humana. |
| **V1 / V2** | Pipeline legado (monolítico, usado por UI) vs pipeline nuevo (adapter chain sobre DocumentContext). |
| **ADP / SM** | SemanticMatcher (matcher semántico por 6 tiers). |
| **Tier 1-6** | Niveles del SemanticMatcher (exact keyword → root word), con precisión decreciente. |
| **DEv2** | Decision Engine v2 (multi-evidence fusion). |
| **DIE** | Document Intelligence Engine (análisis previo al parseo). |
| **IDR** | Intelligent Document Router (Sprint 22). |
| **KB** | Knowledge Base (base de conocimiento). |
| **SIE** | Source Input Extraction (adaptador de entrada del pipeline V2). |
| **SelfQA** | Auto-verificación del pipeline. |
| **HOLDOUT** | Conjunto de 20 PDFs certificados para benchmark (no usados en entrenamiento). |
| **gold_standard.db** | Base SQLite de cuentas cotejadas contra ground truth (234 registros). |
| **URCA** | Unified Root Cause Analysis (análisis de causa raíz, 2026-07-10). |
| **RC01-RC06** | Causas raíz del no-clasificado (LAYOUT, OCR, NORMALIZATION, DICTIONARY, CMCC). |
| **TB-1 a TB-5** | Reglas de tie-break del Decision Engine v2. |
| **HR-1 a HR-5** | Casos que requieren revisión humana. |
| **R1-R12** | Reglas de decisión del DEv2 (orden de evaluación R1→R12). |
| **Shadow mode** | Modo silencioso: el clasificador corre y registra resultados sin afectar la decisión final. |
| **Backend V2** | Backend Runner (`2.0.0-rc1`) que empaqueta el pipeline V2. |
| **Feature flag** | Interruptor de configuración en `pipeline/features.py` (`CMCCFeatureFlags`). |

---

## 15. Índice de documentos originales

Este documento consolida la documentación del repositorio. Fuentes primarias por sección:

### Raíz
- `README.md` — descripción general.
- `SUMMARY.md` — resumen del proyecto.
- `COMPONENT_STATUS.md` — estado de componentes.
- `PROJECT_CONTEXT.md` — este documento.
- `BUG_REGISTER.md` — registro de bugs (2026-07-26).
- `STABILIZATION_BACKLOG.md` — backlog de estabilización (P0-P3).
- `TECHNICAL_AUDIT.md`, `ARCHITECTURE_AUDIT.md`, `AUDITORIA_RC1.md` — auditorías técnicas.
- `ARQUITECTURA_PARSER.md` — arquitectura del parser.
- `app_validacion.py` — UI de validación (1.340 líneas, sin tests).
- `parser_universal.py` — parser core (831 líneas, sin tests).

### `architecture/`
- `architecture.md` — arquitectura general.
- `processing_flow.md` — flujo de procesamiento.
- `module_dependencies.md` — dependencias de módulos.
- `document_context.md` — contexto del documento.
- `interfaces.md` — interfaces (Protocols).
- `roadmap.md` — roadmap de sprints 22-26.

### `docs/`
- `README_ARCHITECTURE.md` — mapa de la documentación de arquitectura (advierte doble vía).
- `ADR-001-Semantic-Architecture.md` — decisión de arquitectura semántica.
- `ADR-002-Decision-Engine.md` — decisión del Decision Engine v2.
- `parser_core_2.0.md` — diseño del ParserCore2.
- `cmcc_production_design.md`, `cmcc_rollout_plan.md` — diseño y rollout CMCC.
- `history/architecture_evolution.md` — evolución de la arquitectura.
- `modules/` — 9 documentos de módulos: `parser.md`, `decision_engine.md`,
  `semantic_engine.md`, `learning_engine.md`, `classification.md`, `adapters.md`,
  `backend.md`, `review_pipeline.md`, `document_intelligence.md`.
- `architecture/` — 4 documentos: `system_overview.md`, `dependency_graph.md`,
  `processing_pipeline.md`, `feature_flags.md`.
- `reference/` — 9 documentos de referencia: `ParserPDF.md`, `AccountTypeResolver.md`,
  `BalanceInterpreter.md`, `CMCCClassifier.md`, `DecisionEngine.md`,
  `DocumentIntelligence.md`, `HomologationPipeline.md`, `LearningEngine.md`,
  `SemanticEngine.md`.

### `knowledge/`
- `README.md`, `gold_standard.md`, `concept_catalog.md`, `schema.json`.
- `cmcc.json` (52 registros), `concept_catalog.json` (78 conceptos),
  `concept_graph.json` (16.1 MB), `gold_standard.json` (934 KB).
- `catalogo_maestro.json` (61 códigos) — en raíz.
- Diccionarios: `diccionario.json` (860), `diccionario_actualizado.json` (781),
  `diccionario_optimizado.json` (712).
- `gold_standard.db` — base SQLite (234 registros).

### `benchmark/`
- `README.md`, `benchmark_results.csv`, `benchmark_runner.py`, `benchmark_summary.md`,
  `dataset_manifest.csv`.

### `reports/` (~200 archivos)
- `root_cause_analysis/root_cause_analysis.md` — URCA (2026-07-10).
- `knowledge/knowledge_report.md` — discovery (2026-07-07).
- `cmcc_knowledge_validation.md` — validación conocimiento CMCC (2026-07-27).
- `decision_engine_validation.md` — validación DE (Sprint 25).
- `classifier_precision.md` — auditoría de precisión real (2026-07-22).
- `certification/certification_report.md` — certificación (2026-07-09).
- `sprint38_architecture_review.md` — review arquitectura Sprint 38.
- `cmcc_shadow_validation/`, `cmcc_benchmark/`, `cmcc_validation_final/` y demás
  subdirectorios históricos (5.000+ archivos; sin política de retención).

### Código de referencia (verificado por inspección)
- `pipeline/features.py` (CMCCFeatureFlags) · `pipeline/homologation_pipeline.py`
- `orchestrator/pipeline_v2.py` (HomologationPipelineV2)
- `parsers/` (ParserCore2) · `parsers/legacy/` (ParserPDF)
- `semantic/` · `learning/` · `cmcc/` · `decision/` · `decision_engine/` · `decision_v2/` ·
  `classification_engine/`
- `review/` · `document_intelligence/` · `adapters/` · `backend/` · `src/api/main.py`
- `config/regex_rules.py` (37 patrones; 7 usados) · `config/release.yml` (no leído)
- `reglas_especiales.py` (D1-D5) · `clasificador_codigo_cuenta.py` · `validation/`

---

*Fin del documento maestro. Este texto preserva la información de las fuentes citadas;
cualquier discrepancia de cifras entre fuentes se indica en el cuerpo del documento.*
