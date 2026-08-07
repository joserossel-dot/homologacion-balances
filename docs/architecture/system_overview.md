# Visión General del Sistema

> Documento derivado exclusivamente del código fuente. Cualquier afirmación
> sin respaldo en el código se marca explícitamente.

## Propósito

Sistema de **homologación de balances contables chilenos**: recibe balances
tributarios en PDF o Excel, extrae las cuentas, las clasifica contra un
catálogo estándar de códigos, aplica reglas contables especiales y produce
un balance unificado con trazabilidad, validación, cobertura y autoevaluación
de calidad.

El proyecto tiene **dos pipelines de procesamiento** que coexisten:

1. **V1 — `pipeline/homologation_pipeline.py`** (`HomologationPipeline`):
   pipeline clásico, un solo flujo lineal (parseo → clasificación → reglas),
   usado por la UI Streamlit (`app_validacion.py`, `ui/app.py`), por
   `adapters/kb_adapter.py` (reutilizado dentro de V2) y por
   `validation/runner.py`.
2. **V2 — `orchestrator/pipeline_v2.py`** (`HomologationPipelineV2`):
   pipeline basado en un contexto único de documento (`DocumentContext`)
   encadenado por **adapters** (SIE → DIE → Parser → KB → Decision →
   Validation → Review → Coverage → SelfQA), usado por
   `backend/runner.py`, el CLI `run_pipeline_v2.py` y `smoke_test.py`.

Ambos comparten el mismo núcleo de clasificación por cuenta
(`HomologationPipeline._classify_account`): V2 lo reutiliza desde
`adapters/kb_adapter.py` (`kb_adapter.py:12-14`, `:110`).

## Dominio del problema

- **Entrada**: balances tributarios chilenos (PDF nativo o escaneado, o Excel).
- **Formato de códigos de cuenta**: guion (`1-01-01-02-01`), punto
  (`1.01.01.02`), compacto (`1112001`) o sin código (`parser_universal.py:64-68`).
- **Catálogo estándar**: códigos `AC.xx`, `ANC.xx`, `PC.xx`, `PNC.xx`,
  `PAT.xx`, `ER.xx` definidos en `catalogo_maestro.json` (61 códigos).
- **Salida**: balance homologado (Excel "Balance_Unificado" vía
  `app_validacion.py`), JSON con resumen y artefactos del backend.

## Flujo de alto nivel

```
PDF/Excel
   │
   ▼
1. Análisis documental (DocumentIntelligence / analyze_document_preview)
   ▼
2. Parseo (ParserPDF / parsear_excel)  ──►  list[CuentaRaw]
   ▼
3. Interpretación por cuenta (BalanceInterpreter → naturaleza + monto)
   ▼
4. Resolución de tipo (AccountTypeResolver)
   ▼
5. Clasificación por cuenta (_classify_account):
      LearningEngine (Gold Standard) → código → diccionario exacto → fuzzy
      → SemanticMatcher → RegexFallback → CMCC (opcional)
   ▼
6. Reglas especiales (ProcesadorReglasEspeciales R1-R5) → final_code
   ▼
7. (V2) Decisión por cuenta + Validación + Revisión + Cobertura + SelfQA
   ▼
8. Resultado (balance homologado, JSON, artefactos, review queue)
```

## Componentes principales

| Paquete | Rol | Estado (deducido de quién lo usa) |
|---|---|---|
| `parser_universal.py` | ParserPDF, parsear_excel, modelos CuentaRaw/ResultadoParseo | Activo en V1 y V2 |
| `parsers/` | Parser v2 (ParserCore2), DocumentAnalyzer, OCR, layout | Paralelo al v1; `ParserCore2` en benchmark/uso selectivo |
| `document_intelligence/` | Análisis pre-parseo: firma, familia, plantilla, extractor | Activo (DIEAdapter en V2; preview en ParserPDF) |
| `pipeline/` | HomologationPipeline + CMCCClassifier + feature flags | Activo (V1 y núcleo de V2) |
| `orchestrator/` | HomologationPipelineV2 (cadena de adapters) | Activo (backend V2) |
| `adapters/` | 7 adapters + AccountAdapter (etapas del V2) | Activo |
| `document_context/` | DocumentContext (contexto único write-once) | Activo y central en V2 |
| `decision/` | DecisionEngine V1 (5 reglas SM vs Regex) | Activo tras flag `ENABLE_DECISION_ENGINE` (default OFF) |
| `decision_engine/` | Decisión a nivel documento (V2, 122 tests) | Activo (DecisionAdapter) |
| `decision_v2/` | Benchmark experimental por-cuenta (weighted ensemble) | Solo benchmark |
| `classification_engine/` | Motor Top-N por cuenta (Sprint 38) | Nuevo, no integrado aún |
| `learning/` | LearningEngine (Gold Standard SQLite) | Activo (primera etapa de clasificación) |
| `semantic/` | SemanticMatcher v1 + SemanticEngine v2 | v1 tras flag OFF; v2 reporte siempre |
| `knowledge/` | CMCC + descubrimiento de conocimiento | Infraestructura/tooling |
| `validation/` | BalanceValidator, ecuación, subtotales, integridad | Activo (ValidationAdapter + runner) |
| `coverage_engine/` | 4 coberturas (monetaria, estructural, semántica, documental) | Activo (CoverageAdapter) |
| `self_qa_engine/` | Autoevaluación (gates, riesgo, aprobación) | Activo (SelfQAAdapter) |
| `review/` + `review_ui/` | Revisión humana (Excel package + SQLite) | Activo (tooling/UI) |
| `backend/` | Backend V2 (runner, artefactos, resultados) | Activo (RC1) |
| `observability/` | Recolección de métricas por ejecución | Activo |
| `release_pipeline/` | Gates de release (tests, drift, regresión) | Activo (tooling) |
| `app_validacion.py` | UI Streamlit principal (8 tabs) | Activo |
| `ui/app.py` | UI Streamlit V1 minimal | Activo |
| `src/` | API REST (FastAPI) + orquestador + repositorio | API |
| `accounting_knowledge/`, `gold_standard/`, `gold_import/`, `evidence/`, `explainability/`, `context/`, `structure_engine/`, `analytics/`, `analysis/`, `assessment/`, `audit/`, `evaluation/`, `extractors/`, `integration/`, `mappers/`, `models/`, `parser_quality/`, `patterns/`, `quality_monitoring/`, `scientific_validation/`, `shadow/`, `split_ac01/` | Módulos de apoyo, tooling, validación y reportes | Variable |

## Entrada y salida

**Entradas**
- `str | Path` del PDF/Excel (V1 y V2 aceptan ambos).
- Opcional: `features` (`CMCCFeatureFlags`) y `db_path` para el Gold Standard.
- En V2: `decision_weights`, `coverage_weights`, `qa_gate_thresholds`
  opcionales (`orchestrator/pipeline_v2.py:22-29`).

**Salidas**
- V1: `dict` resumen con `classified`, `ignored`, contadores y
  `cmcc_review_queue` (`homologation_pipeline.py:574-606`). Método
  `to_json(pdf_path, output_file)` escribe el JSON.
- V2: `DocumentContext` con secciones write-once y `custom_data`
  (`classified`, `decisions`, `coverage`, `self_qa`, ...). Método
  `process_to_dict()` devuelve dict V1-compatible + métricas DCE
  (`pipeline_v2.py:57-71`).
- UI: balance homologado en Excel y review queue.

## Punto de entrada real

No fue posible determinar un único "punto de entrada de producción" a partir
del código, porque conviven varios lanzadores:

- **CLI principal V2**: `run_pipeline_v2.py` (usa `HomologationPipelineV2`).
- **Backend**: `backend/runner.py` → `BackendRunner.run(pdf)`.
- **UI Streamlit**: `app_validacion.py` (app principal) y `ui/app.py` (V1).
- **API HTTP**: `src/api/main.py` (FastAPI, `POST /api/v1/analisis/procesar`).

## Riesgos técnicos globales

1. **Dos pipelines** (V1 y V2) con lógica de clasificación duplicada
   parcialmente (V2 reutiliza `_classify_account` de V1, pero la decisión
   documental y la validación son propias de V2).
2. **Cuatro motores de decisión** coexistentes: `decision/` (V1),
   `decision_engine/` (V2 documental), `decision_v2/` (benchmark) y
   `classification_engine/` (nuevo Top-N). Documentado en
   `reports/sprint38_architecture_review.md`.
3. **Vocabularios de enums duplicados**: `document_intelligence/signature.py`
   vs `document_intelligence/models.py` definen `DocumentType` y `Family`
   incompatibles entre sí.
4. **Pesos y umbrales hardcodeados** en varios motores
   (`decision_v2/_EVIDENCE_WEIGHTS`, `decision_engine/confidence.py`,
   `semantic/scorer.py`), frente al `WeightConfig` parametrizable del nuevo
   `classification_engine`.
5. **Datos de conocimiento variados**: `diccionario.json` (con
   `__EXCLUIR__`), `gold_standard.db` (con errores documentados),
   `catalogo_maestro.json`, `knowledge_base/account_synonyms.json`,
   `knowledge/cmcc.json`; no todos los motores usan las mismas fuentes.

## Decisiones de arquitectura documentadas

- `docs/ADR-001-Semantic-Architecture.md`
- `docs/ADR-002-Decision-Engine.md`
- `reports/sprint38_architecture_review.md` (auditoría con opciones y
  recomendación de unificar en `classification_engine/`)
