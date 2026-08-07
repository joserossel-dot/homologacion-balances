# Arquitectura — Homologación de Balances Tributarios

Sistema de homologación automática de balances contables chilenos (PDF/Excel
→ cuentas estandarizadas según catálogo CMCC). Este conjunto de documentos
describe la arquitectura del código, **basándose exclusivamente en el código
fuente** (todo hallazgo sin respaldo explícito se marca como tal).

> ⚠️ **Aviso de mantenimiento**: la arquitectura es de **doble vía** (V1 y V2
> coexisten). Varios subsistemas son legados superpuestos. Léanse los
> documentos de riesgo de cada módulo antes de modificar.

## Mapa de documentos

### Introducción y arquitectura general

| Documento | Contenido |
|---|---|
| `architecture/system_overview.md` | Visión global, componentes, entry points, riesgos globales |
| `architecture/dependency_graph.md` | Grafo de dependencias, ciclos, acoplamiento |
| `architecture/processing_pipeline.md` | Flujos V1, V2, DIE, por cuenta, coverage, self-qa, validación, revisión |
| `architecture/feature_flags.md` | Las 3 formas de feature flags y su estado real |

### Módulos (por área)

| Documento | Área |
|---|---|
| `modules/parser.md` | Parser (ParserPDF + ParserCore2 + integración) |
| `modules/document_intelligence.md` | Document Intelligence Engine (DIE) |
| `modules/decision_engine.md` | Los 4 motores de decisión |
| `modules/semantic_engine.md` | Capa semántica (SemanticEngine + SemanticMatcher) |
| `modules/learning_engine.md` | Gold Standard + cola de correcciones |
| `modules/classification.md` | Clasificación por código/diccionario/CMCC + Top-N |
| `modules/review_pipeline.md` | Cola de revisión humana + paquetes Excel |
| `modules/adapters.md` | Adapters del pipeline V2 |
| `modules/backend.md` | Backend V2 + API legada |

### Referencia de clases

| Documento | Clase(s) |
|---|---|
| `reference/HomologationPipeline.md` | `HomologationPipeline` (V1, orquestador) |
| `reference/ParserPDF.md` | `ParserPDF`, `CuentaRaw`, `ResultadoParseo` |
| `reference/BalanceInterpreter.md` | `BalanceInterpreter` |
| `reference/AccountTypeResolver.md` | `AccountTypeResolver`, `AccountType` |
| `reference/DecisionEngine.md` | `DecisionEngine` (V1, `decision/`) |
| `reference/SemanticEngine.md` | `SemanticEngine`, reglas semánticas |
| `reference/LearningEngine.md` | `LearningEngine` |
| `reference/CMCCClassifier.md` | `CMCCClassifier` |
| `reference/DocumentIntelligence.md` | `DocumentIntelligence` (DIE) |

### Historia y decisiones

| Documento | Contenido |
|---|---|
| `history/architecture_evolution.md` | Evolución por sprints/commits |
| `ADR-001-Semantic-Architecture.md` | Decisión: arquitectura semántica |
| `ADR-002-Decision-Engine.md` | Decisión: motor de decisión |
| `cmcc_production_design.md` / `cmcc_production_sequence.md` / `cmcc_rollout_plan.md` | Rollout del clasificador CMCC |
| `parser_core_2.0.md` | Diseño ParserCore2 |

### No escritos (pendientes/planificados)

Las carpetas `docs/flows/` y `docs/guides/` existen vacías — pendientes de
completar con diagramas de flujo y guías de uso.

## Resumen ejecutivo

- **Entrada**: PDF (nativo/OCR) o Excel → `ParserPDF`/`parsear_excel` →
  `ResultadoParseo` → `CuentaRaw`.
- **Clasificación (V1)**: cascada Gold Standard → código → diccionario
  (exacto/fuzzy) → regex audited (+ CMCC/semántico/DecisionEngine según
  flags) → reglas R1-R5.
- **Pipeline V2**: adapter chain sobre `DocumentContext` con lifecycle
  NEW→…→COMPLETED y métricas de decisión, validación, cobertura y self-qa.
- **Backends**: `BackendRunner` (V2, RC 2.0.0) y API FastAPI legada
  (`src/api/`) con PostgreSQL.
- **Estados de madurez**: V1 es el camino crítico usado por la UI; V2 está
  estable y empaquetado por `backend/`; `classification_engine/` (Top-N) está
  listo pero no integrado (Sprint 39).

## Riesgos globales (resumen)

1. Doble pipeline (V1/V2) y doble parser (ParserPDF/ParserCore2).
2. 4 motores de decisión coexistiendo; solo `decision_engine/` está activo.
3. 2 backends independientes (`backend/` vs `src/api/`).
4. Enums duplicados/incompatibles entre `document_intelligence/models.py` y
   `models.py`.
5. Monolitos (`parser_universal.py` ~1000 líneas).
6. Configuración dispersa (flags por módulo + umbrales hardcodeados).
7. Persistencia de revisión no implementada (`review.db`).

Detalles por módulo en los documentos listados arriba.
