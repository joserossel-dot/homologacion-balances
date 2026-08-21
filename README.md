# Plataforma de Homologación de Balances Tributarios Chilenos

Sistema que transforma **balances tributarios chilenos** (PDF y Excel) en estados financieros
normalizados orientados al análisis de riesgo crediticio bancario, clasificados en el
**Catálogo Maestro de Conceptos Contables (CMCC)**.

> **Benchmark oficial: 2660/2662 cuentas** · Base M5 (99.92%) — base de benchmark **congelada**.

---

## Estado del proyecto

- **Arquitectura:** doble vía V1 (legado, en uso por la UI) y V2 (nuevo, backend `2.0.0-rc1`).
- **Clasificación:** pipeline híbrido por evidencia — código de cuenta → diccionario →
  aprendizaje (`learning/`) → CMCC (shadow) → decisión → revisión humana.
- **Benchmark:** HOLDOUT de 20 PDFs certificado al **100% de accuracy** en cuentas cotejables
  (103/103, κ = 1.0). La base del benchmark (2660/2662) **no se modifica** en ejecución.
- **Estado completo:** ver [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

---

## Arquitectura

Ver [`ARCHITECTURE.md`](ARCHITECTURE.md) para el mapa de módulos, dependencias y flujo completo.
Resumen:

```
PDF ──► parsers (ParserPDF / ParserCore2) ──► CuentaRaw
        │
        ├─► document_intelligence (DIE, análisis previo) ──► IntelligenceReport
        ▼
   semantic/ (SemanticMatcher)
        ▼
   learning/ (LearningEngine: learning_exact / learning_fuzzy)
        ▼
   cmcc/ (clasificador CMCC, shadow)
        ▼
   decision_engine/ (EvidenceAggregator)
        ▼
   review/ (ReviewPipeline) ──► Excel
        ▼
   adapters/kb_adapter ──► backend/ ──► src/api (FastAPI)
```

- **V1 (legado):** `pipeline/homologation_pipeline.py` — usado por la UI.
- **V2 (nuevo):** `orchestrator/pipeline_v2.py` (`HomologationPipelineV2`) — 9 adaptadores
  (SIE, DIE, Parser, KB, Decision, Validation, Review, Coverage, SelfQA) — usado por `backend/`.

### Feature flags (`pipeline/features.py`)

| Flag | Default | Efecto |
|---|---|---|
| `ENABLE_CMCC` | `False` | Clasificación CMCC desactivada |
| `ENABLE_CMCC_SHADOW` | `True` | CMCC corre en shadow (evalúa sin influir) |
| `ENABLE_CMCC_PRODUCTION` | `False` | Producción desactivada |
| `ENABLE_REGEX_FALLBACK` | `True` | Regex fallback activo (7 patrones auditados) |
| `ENABLE_DECISION_ENGINE` | `False` | Decision Engine V1 desactivado |

---

## Base de conocimiento

- **Gold Standard:** `gold_standard/` (gold_standard.db) — conocimiento canónico.
- **Runtime:** `gold_standard/runtime_manager.py` (`RuntimeManager`) — conocimiento en evolución
  (`runtime_gold` + `promotion_history` + metadata). Administra 107 claves: **96 activas / 11
  desactivadas** (depuración P6, 2026-08-05).
- **Catálogo CMCC:** `knowledge/cmcc.json` + `knowledge/concept_catalog.md` (v1.0).
- El benchmark (2660/2662) queda **congelado**: ninguna ejecución lo escribe.

---

## Requisitos

- Python 3.12+
- PostgreSQL 16
- Tesseract OCR (idioma español) + Poppler (`pdftoppm`) — para PDFs escaneados

```bash
brew install python@3.12 postgresql@16 tesseract tesseract-lang poppler
pip3 install -r requirements.txt
```

> Los balances (PDF/Excel) no se incluyen en el repo por confidencialidad.
> Los datos de prueba viven en `datasets/` (HOLDOUT, TRAINING, PILOT, STRESS…).

---

## Ejecución

```bash
# UI de validación / revisión humana
streamlit run app_validacion.py

# Backend V2 (FastAPI) — GET /health · POST /api/v1/analisis/procesar
uvicorn src.api.main:app
```

---

## Documentación

| Documento | Contenido |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Arquitectura completa (V1/V2, módulos, flujo). |
| [`CHANGELOG.md`](CHANGELOG.md) | Historial de hitos M1–M5 y P1–P6. |
| [`PROJECT_STATUS.md`](PROJECT_STATUS.md) | Estado, roadmap, benchmark y deuda técnica. |
| [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) | Documento maestro consolidado (referencia interna). |
| [`benchmark/`](benchmark/) | Dataset HOLDOUT y resultados. |
| [`reports/product/`](reports/product/) | Informes de producto por hito (P1–P6). |

---

## Estructura del proyecto

```
├── pipeline/            # Pipeline V1 (legado, en uso por UI)
├── orchestrator/        # Pipeline V2 (HomologationPipelineV2)
├── parsers/             # ParserCore2 + legacy ParserPDF
├── semantic/            # SemanticMatcher por tiers
├── learning/            # Learning Engine
├── cmcc/                # Clasificador CMCC (shadow)
├── decision_engine/     # Decision Engine V2 documental
├── review/              # Review Pipeline (revisión humana)
├── document_intelligence/ # DIE: análisis previo al parseo
├── adapters/            # Puente V1↔V2 (kb, parser, review)
├── backend/             # Backend Runner (2.0.0-rc1)
├── src/api/             # FastAPI (health, procesar)
├── gold_standard/       # Gold Standard + RuntimeManager
├── knowledge/           # Catálogos, CMCC, concept graph
├── validation/          # Validación de balances
├── datasets/            # HOLDOUT, TRAINING, PILOT, STRESS…
├── benchmark/           # Benchmark runner y resultados
├── reports/             # Informes de validación y auditoría
└── app_validacion.py    # UI Streamlit de validación/revisión
```
