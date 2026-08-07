# Grafo de Dependencias

> Derivado de los imports reales del código. Los imports **diferidos**
> (dentro de métodos) se marcan explícitamente, ya que rompen ciclos
> potenciales y son frágiles a refactors.

## Vista por capas (V2)

```
┌─────────────────────────────────────────────────────────────┐
│ Entry points: run_pipeline_v2.py · backend/runner.py        │
│               app_validacion.py · ui/app.py · src/api       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ HomologationPipelineV2 (orchestrator/pipeline_v2.py)        │
│  encadena 9 adapters sobre DocumentContext                  │
└──┬────────┬────────┬────────┬────────┬────────┬────────┬────┘
   │        │        │        │        │        │        │
   ▼        ▼        ▼        ▼        ▼        ▼        ▼
 SIE     DIE      Parser    KB     Decision  Validation Review
Adapter  Adapter  Adapter  Adapter  Adapter   Adapter   Adapter
   │        │        │        │        │        │        │
   │        │        │        ▼        ▼        ▼        │
   │        │        │   HomologationPipeline        ┌────┤
   │        │        │   (V1 _classify_account)      │    │
   │        │        │        │                      │    │
   ▼        ▼        ▼        ▼                      ▼    ▼
CoverageAdapter ────────────────────────────────► SelfQAAdapter
   │                                                     │
   └──────────────► ctx.complete(module="pipeline_v2")    │
```

**Nota**: `CoverageAdapter` y `SelfQAAdapter` se ejecutan al final de la
cadena (líneas 51-52 de `pipeline_v2.py`), después de Review.

## Dependencias de cada paquete

| Paquete | Depende de | Detalle |
|---|---|---|
| `pipeline/homologation_pipeline.py` | `adapters/account_adapter`, `clasificador_codigo_cuenta`, `config/regex_rules`, `parser_universal` (parsear_excel, FormatoCodigo, ParserPDF, ResultadoParseo), `interpreters/balance_interpreter`, `learning/engine`, `models/account_balance`, `pipeline/cmcc_classifier`, `pipeline/features`, `reglas_especiales`, `decision/engine`, `semantic/semantic_engine`, `semantic/matcher`; diferido: `decision/models`, `parsers/account_type_resolver`, `review/cmcc_review_models` | Orquestador V1; núcleo de clasificación reutilizado por V2 |
| `parser_universal.py` | `pandas`, `pdfplumber`, `PIL`; diferido: `document_intelligence.extractors.factory`, `document_intelligence.extractors.profile_driven`, `parsers.layout_detector`, `parsers.account_type_resolver`, `document_intelligence.context` | **Ciclo potencial**: `parser_universal` importa `document_intelligence` y `parsers` a la vez que éstos importan de `parser_universal` (roto con imports diferidos) |
| `parsers/` | `parser_universal`, `parsers.config/format_detector/line_parser/layout_detector/hygiene/orientation_detector/analyzer`, `pdfplumber` | Parser v2; `DocumentAnalyzer` NO importa `document_intelligence` |
| `document_intelligence/` | `pdfplumber`, `pdf`, `openpyxl`, `pandas`; `structure_engine.structure_detector`; `parser_universal` (diferido en extractores/trainer) | Dos motores internos: `DocumentIntelligence` (legacy) y `analyze_document_preview` (Sprint 31) |
| `adapters/` | `document_context`, `document_intelligence`, `parser_universal`, `pipeline.homologation_pipeline`, `decision_engine`, `validation.balance_validator` | Cada adapter es una etapa del V2 |
| `document_context/` | stdlib (`uuid`, `hashlib`, `copy`, `datetime`) | **Núcleo sin dependencias internas** — aislado |
| `decision_engine/` | `document_context` (lee secciones + custom `die_report`) | Capa documental V2 |
| `decision/` | `semantic.models`, stdlib | Motor V1 |
| `decision_v2/` | `learning`, `clasificador_codigo_cuenta`, `diccionario`, `semantic.matcher`, `app_validacion` (regex) | Solo benchmark |
| `classification_engine/` | `account_name_normalizer`, `clasificador_codigo_cuenta`, `special_account_rules`, `catalogo_maestro.json`, `knowledge_base/account_synonyms.json` | Nuevo; desacoplado; solo tests |
| `learning/` | `gold_standard.db` (SQLite), `learning/exact_match`, `learning/fuzzy_match` (rapidfuzz) | Independiente |
| `semantic/` | `knowledge/concept_catalog.json`, `rapidfuzz`, `models.account_balance` | v1 catalog-driven; v2 reglas |
| `knowledge/` | JSON (`cmcc.json`, etc.), `rapidfuzz` | Tooling |
| `validation/` | `parser_universal`, `pipeline.homologation_pipeline`, `document_context` | Reportes + adapter |
| `coverage_engine/` | `document_context` | Solo lectura del contexto |
| `self_qa_engine/` | `document_context` | Solo lectura del contexto |
| `backend/` | `orchestrator.pipeline_v2`, `document_context` | Backend RC1 |
| `observability/` | `document_context` | Recolecta métricas |
| `src/` | `src.core.orquestador`, `src.db_repository`, `parser_universal` | API REST |
| `app_validacion.py` | `pipeline.homologation_pipeline`, `shadow`, `document_intelligence`, `review`, `parser_universal` | UI principal |

## Ciclos de dependencia (resueltos con imports diferidos)

1. `parser_universal` ↔ `document_intelligence.extractors.*`
   - `parser_universal.py:665-667, 853-855` importa `SpecializedExtractorFactory`.
   - `document_intelligence/extractors/universal.py:28` importa `ParserPDF`.
   - Roto con import dentro de método.
2. `parser_universal` ↔ `parsers.*`
   - `parser_universal.py:744, 794` importa `LayoutDetector` y `AccountTypeResolver`.
   - `parsers/pdf_parser.py` y `parsers/analyzer.py` importan `parser_universal` a nivel módulo.
   - Roto con import dentro de método.
3. `adapters/kb_adapter` → `pipeline/homologation_pipeline` → `adapters/account_adapter`
   - No es un ciclo (cadena), pero `kb_adapter` reutiliza el pipeline V1 completo.

## Dependencias externas principales

| Dependencia | Uso |
|---|---|
| `pdfplumber` | Extracción de texto nativo y tablas de PDFs |
| `pandas` | `parsear_excel`, reportes, dashboard |
| `rapidfuzz` | Matching fuzzy (diccionario, CMCC, semantic) |
| `PIL` / `pdftoppm` / `tesseract` | OCR de PDFs escaneados (subprocess) |
| `openpyxl` | Export/lectura Excel (reportes, review package) |
| `sqlite3` | `gold_standard.db`, `review_ui/reviews.db` |
| `streamlit` | UIs (`app_validacion.py`, `ui/app.py`) |
| `fastapi` / `uvicorn` | `src/api/main.py` |
| `asyncpg` (opcional) | `src/db_repository.py` (Postgres con SSL) |
| `yaml` | `config/features.py`, `config/release.yml` |

## Módulos más desacoplados

- `document_context/` — sin dependencias del resto del proyecto.
- `classification_engine/` — nuevo motor con fuentes inyectadas.
- `learning/` — depende solo del Gold Standard y rapidfuzz.

## Módulos con mayor acoplamiento

- `pipeline/homologation_pipeline.py` — depende de 12 módulos; núcleo
  reutilizado por V1, V2 (kb_adapter), backend, UI, benchmark.
- `parser_universal.py` — monolito con dependencias a casi todo el
  ecosistema vía imports diferidos.
- `adapters/kb_adapter.py` — acopla V2 al pipeline V1.
