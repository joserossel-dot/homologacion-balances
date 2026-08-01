# RC1 Architecture — Homologación de Balances

## 1. Core Principle

Single official flow using `DocumentContext` as the sole communication mechanism.
The pipeline must run identically from Streamlit, API, CLI, Batch, or Docker without modification.

```
INPUT → DocumentContext → pipeline → DocumentContext → OUTPUT
```

## 2. Canonical Pipeline Order

```
  ┌──────────┐
  │  INPUT   │  PDF, Excel, manual JSON
  └────┬─────┘
       ↓
  ┌──────────┐
  │  SIE     │  → DocumentIdentity, Metadata
  └────┬─────┘
       ↓
  ┌──────────┐
  │  DIE     │  → StructureData
  └────┬─────┘
       ↓
  ┌──────────┐
  │  Parser  │  → ParserData, [CuentaRaw]
  └────┬─────┘
       ↓
  ┌──────────┐
  │  KB      │  → KnowledgeData, gold_standard matches
  └────┬─────┘
       ↓
  ┌──────────┐
  │ Decision │  → PredictionData (resolved classification)
  └────┬─────┘
       ↓
  ┌──────────┐
  │ Coverage │  → Coverage report
  └────┬─────┘
       ↓
  ┌──────────┐
  │ Self QA  │  → Consistency checks
  └────┬─────┘
       ↓
  ┌──────────┐
  │ Review   │  → ReviewQueue, human corrections
  └────┬─────┘
       ↓
  ┌──────────┐
  │  Export  │  → NormalizedBalance, Excel
  └──────────┘
```

## 3. Adapter Interface

Every adapter follows:

```python
class BaseAdapter(ABC):
    @abstractmethod
    def execute(self, ctx: DocumentContext) -> DocumentContext:
        ...
```

Adapters are:
- **SIEAdapter** — Extrae identidad y metadata del documento
- **DIEAdapter** — Detecta estructura (activo/pasivo/patrimonio/resultados)
- **ParserAdapter** — Parsea PDF o Excel a cuentas raw
- **KBAdapter** — Busca en gold_standard, knowledge_base, código → cuenta
- **DecisionAdapter** — Resuelve conflictos (SM/Regex), aplica reglas especiales
- **CoverageAdapter** — Calcula % cobertura por documento
- **SelfQAAdapter** — Validación cruzada, consistencia de totales
- **ReviewAdapter** — Prepara cola de revisión humana
- **ExportAdapter** — Agrupa cuentas, genera Excel normalizado

## 4. Engine Separation

```
adapters/       → thin wrappers (no business logic)
  SIEAdapter.py
  DIEAdapter.py
  ParserAdapter.py
  KBAdapter.py
  DecisionAdapter.py
  CoverageAdapter.py
  SelfQAAdapter.py
  ReviewAdapter.py
  ExportAdapter.py

engines/        → pure business logic (no Streamlit, no I/O)
  parser_universal.py
  clasificador_codigo_cuenta.py
  reglas_especiales.py
  decision/
  learning/
  knowledge/
  validation/
  coverage/
  self_qa/
```

Adapters import engines. Engines know nothing about adapters.

## 5. DocumentContext Data Flow

```
DocumentContext {
  document_identity:  Optional[DocumentIdentity]
  metadata:           Optional[DocumentMetadata]
  structure:          Optional[StructureData]
  raw_accounts:       Optional[List[CuentaRaw]]
  parser_data:        Optional[ParserData]
  knowledge_data:     Optional[KnowledgeData]
  predictions:        Optional[PredictionData]
  validation_data:    Optional[ValidationData]
  execution:          ExecutionData  (timing, version, errors)
}
```

Each adapter reads what it needs from `ctx` and writes its output back.

## 6. Deployment Targets (all use same pipeline)

```
┌─────────────────────────────────────────────┐
│               PIPELINE V2                    │
│  orchestrator/pipeline_v2.py                 │
│  (single import, zero UI dependencies)       │
└────┬──────┬──────┬──────┬───────┬────────────┘
     │      │      │      │       │
     ▼      ▼      ▼      ▼       ▼
  Streamlit  FastAPI   CLI    Batch    Docker
  (app_v2/) (api/)  (cli/)  (batch/) (Dockerfile)
```

## 7. Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Single DocumentContext | Replaces st.session_state + ad-hoc dicts + global vars |
| Adapters are stateless | Pipeline owns state via ctx; adapters are pure functions |
| Engines never import adapters | Prevents circular deps at architecture level |
| Pipeline is UI-agnostic | Single `pip install` deployable anywhere |
| ExportAdapter as last step | Decouples normalization from UI; testable standalone |
| No inheritance in adapters | Composition over inheritance; each adapter has 1 job |
