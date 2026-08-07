# Evolución de la Arquitectura

> Fuente: `git log` del repositorio + documentos existentes en `docs/`.

## Línea de tiempo (commits recientes)

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

## Fases de evolución

### 1. MVP y API (commits iniciales → `8f76e11`)

- Plataforma de homologación de balances tributarios chilenos.
- Orquestador central (`PipelineOrquestador`) + parser de balances.
- API REST con **PostgreSQL** (módulo `src/`), mucho trabajo de
  despliegue (Docker, Render, imports absolutos/relativos).

### 2. Sprint 28.5 — hardening (`b2c24a2`)

- `parser_universal.py` madura (PDF + OCR + layout).
- **Knowledge engine** y **review pipeline** (cola de revisión humana).
- `app_validacion.py` como interfaz principal Streamlit.

### 3. DocumentAnalyzer (`e0a8933`/`72e62b6`)

- Nueva capa de análisis estructural **pre-parseo**
  (`parsers/analyzer.py`, `DocumentAnalyzer`).
- Produce `ExtractionContext` para `ParserPDF.parsear`.

### 4. Sprint 1 — arquitectura context-aware (`2d16c4e`)

- `document_context/` (contexto compartido + lifecycle) y
  `orchestrator/pipeline_v2.py` (`HomologationPipelineV2`).
- **Adapter chain** (SIE→DIE→Parser→KB→Decision→Validation→Review→Coverage→
  SelfQA). Nace el pipeline V2 junto al V1.
- Parser hygiene (`parsers/` ParserCore2 + `ParserConfig`).

### 5. Stabilize V2 (`6c9e0ce`)

- Estabilización del pipeline V2; suite de tests verde.

### 6. Sprint 37 — Document Intelligence + Knowledge Base (`40aa083`)

- `document_intelligence/` (DIE): clasificadores, extractores,
  conocimiento documental, minería, trainer.
- Arquitectura de **knowledge base** (`knowledge/`, `knowledge_base/`).
- ADRs publicados: `docs/ADR-001-Semantic-Architecture.md`,
  `docs/ADR-002-Decision-Engine.md`.

### 7. Sprint 38 — Motor de clasificación (`b455813`)

- `classification_engine/`: **Top-N explicable** con `WeightConfig`
  parametrizable (candidatos → scoring → explicación).
- 4 motores de decisión coexistiendo: `decision/` (V1), `decision_engine/`
  (V2, activo), `decision_v2/` (benchmark), `classification_engine/`
  (nuevo, no integrado).
- Review técnico: `reports/sprint38_architecture_review.md`.

### 8. Documentación (`19500df`)

- Se agregó esta base de documentación técnica (estructura `docs/`).

## Arquitectura actual (estado de doble vía)

- **Pipeline V1** (`pipeline/homologation_pipeline.py`): monolítico,
  `process()` por archivo, cascada de clasificación. Usado por la UI, el
  runner de validación y (vía `KBAdapter`) el pipeline V2.
- **Pipeline V2** (`orchestrator/pipeline_v2.py`): adapter chain sobre
  `DocumentContext`, con lifecycle de estados y QA/coverage/self-qa.
- **Backend V2** (`backend/`): `BackendRunner` empaqueta V2 (RC 2.0.0).
- **API legada** (`src/api/main.py`): FastAPI sobre `PipelineOrquestador` +
  PostgreSQL (separada del backend V2).
- **DIE** (`document_intelligence/`): inteligencia previa al parser.

## Decisiones arquitectónicas documentadas

- `docs/ADR-001-Semantic-Architecture.md`: arquitectura de la capa
  semántica (SemanticEngine, SemanticMatcher, catálogo de conceptos).
- `docs/ADR-002-Decision-Engine.md`: diseño del motor de decisión.
- `docs/cmcc_production_design.md`, `cmcc_production_sequence.md`,
  `cmcc_rollout_plan.md`: diseño/plan de rollout del clasificador CMCC
  (shadow → producción con thresholds 0.95/0.85).
- `docs/parser_core_2.0.md`: diseño del ParserCore2.

## Deuda técnica acumulada (visión general)

1. **Doble pipeline** (V1/V2) con solapamiento de responsabilidades.
2. **Doble parser** (`ParserPDF` legado vs `parsers/` ParserCore2).
3. **4 motores de decisión** sin consolidar.
4. **2 backends** (V2 `backend/` vs API legada `src/api/`).
5. Enums duplicados (`document_intelligence/models.py` vs `models.py`).
6. Módulos monolíticos (`parser_universal.py` ~1000 líneas,
   `homologation_pipeline.py` ~640 líneas).
7. Acoplamientos inversos (p.ej. `decision_v2 → app_validacion`).
8. Configuración dispersa (flags por módulo, umbrales hardcodeados).
