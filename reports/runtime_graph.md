# Grafo de Ejecución en Tiempo Real

```
Leyenda:
  →  flujo de datos / llamada
  ~  dependencia circular
  ✗  error conocido
  ·  dato producido
  !  módulo no utilizado
  ⚡ ejecución condicional (feature flag)
```

---

## Grafo Completo: Flujo Actual (Legacy + Nuevo)

```
┌──────────────────────────────────────────────────────────────────┐
│                         USUARIO                                  │
│   Sube PDF/Excel → sidebar configuración → confirma metadata     │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│               _extraer_lineas_encabezado(archivo)                │
│                                                                  │
│  pdfplumber.open(tmp_pdf) → .pages[0].extract_text()            │
│  · Produces: list[str] (primeras 40 líneas)                     │
└──────────────────────┬───────────────────────────────────────────┘
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
┌──────────────────────┐ ┌──────────────────────────────────────────┐
│  extraer_metadata()  │ │      _extraer_cuentas(archivo)           │
│                      │ │                                          │
│  · MetadataEmpresa   │ │  PDF → ParserPDF.parsear()               │
│    {rut, razon,      │ │    → validar_archivo()                   │
│     periodo, giro,   │ │    → _extraer_lineas()                   │
│     confianza}       │ │      (pdfplumber | OCR)                  │
│                      │ │    → detectar_formato_codigo()           │
│  Almacenado en:      │ │    → detectar_separador_miles()          │
│  st.session_state.   │ │    → parsear_linea() × N                │
│  metadata_files[name]│ │    → AccountTypeResolver [⚡feature]     │
│                      │ │    · ResultadoParseo                     │
│                      │ │      {archivo, formato, separador,       │
│                      │ │       requirio_ocr, rotacion,            │
│                      │ │       cuentas: [CuentaRaw],              │
│                      │ │       advertencias: [str]}               │
│                      │ │                                          │
│                      │ │  Excel → parsear_excel()                 │
│                      │ │    → pd.read_excel                      │
│                      │ │    · list[CuentaRaw]                     │
└──────────────────────┘ └────────────────┬─────────────────────────┘
                                          │
                                          ▼
                ┌─────────────────────────────────────────┐
                │      FILTRO INICIAL DE CUENTAS          │
                │                                         │
                │  ¿monto None y sin código? → omitir     │
                │  ¿PATRON_NO_CUENTA? → omitir            │
                └────────────────┬────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
        ┌──────────────────────┐  ┌──────────────────────────────┐
        │ FLUJO LEGACY         │  │ FLUJO NUEVO [✗ ROTO]         │
        │ USE_LEGACY_ENGINE=T  │  │ USE_LEGACY_ENGINE=F          │
        │                      │  │                              │
        │ MotorHibridoLocal    │  │ AccountAdapter               │
        │  .clasificar(cuenta) │  │  .from_cuenta_raw()          │
        │    ├─ Por código     │  │   → AccountBalance           │
        │    ├─ Dicc exacto    │  │                              │
        │    ├─ Dicc fuzzy     │  │ BalanceInterpreter           │
        │    ├─ Regex          │  │  .nature                     │
        │    ├─ Corrección     │  │  .classification_amount      │
        │    │  por columna    │  │                              │
        │    └─ Reglas esp.    │  │ hp._classify_account()       │
        │                      │  │  → LearningEngine            │
        │  · DataFrame {       │  │  → [⚡CMCC] CMCCClassifier   │
        │    linea, cod_orig,  │  │  → [⚡DE] DecisionEngine     │
        │    nombre_orig,      │  │  → [no DE] ClasifCodigo      │
        │    monto,            │  │             → Dicc exacto    │
        │    origen_col,       │  │             → Dicc fuzzy     │
        │    es_total,         │  │             → [⚡SM] SemMatch│
        │    cod_clasif,       │  │             → Regex fallback │
        │    metodo,           │  │                              │
        │    confianza,        │  │ hp._rule_processor.aplicar() │
        │    requiere_revision,│  │                              │
        │    nota,             │  │ · DataFrame (misma estructura)│
        │    conf_extrac,      │  │                              │
        │    origen_display }  │  │ ✗ NameError: 'time'          │
        └─────────┬────────────┘  └──────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────────┐
│            SHADOW MODE (solo PDF, solo flujo legacy)            │
│                                                                  │
│  if SHADOW_MODE and .pdf:                                       │
│    HomologationPipeline.process(tmp_pdf)                        │
│    ShadowLogger.log(comparisons, match_rate)                    │
│    → logs/shadow/{id}.json [NADIE lo lee después]               │
└──────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────────┐
│               propagar_entre_balances()                         │
│                                                                  │
│  Por cada nombre normalizado, busca si algún archivo ya tiene   │
│  clasificación → la propaga a los archivos que no la tienen     │
│  · Modifica st.session_state.resultados                         │
└──────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                        UI (Streamlit)                            │
│                                                                  │
│  Sidebar: lista de archivos cargados                             │
│  Visor: _visor_documento(archivo_activo)                        │
│         PDF → pdf2image → PNG → base64 → HTML                   │
│         Excel → pandas → HTML                                   │
│                                                                  │
│  Tabs:                                                            │
│  ┌─────────────────────────────────────────────────────┐         │
│  │ Resumen │ Revisión │ Balance │ Diccionario │ Aprend │Analytics│
│  │         │          │         │             │        │  [WIP]  │
│  │ KPIs    │ Lote     │ Agrupa  │ Búsqueda    │GoldStd │         │
│  │ Métodos │ Individual│ Por cat │ Tabla       │stats   │         │
│  │         │→ gold_std│ Export  │             │Top     │         │
│  │         │→ diccion │ Excel   │             │Conflic │         │
│  │         │→ propagac│         │             │tos     │         │
│  └─────────┴──────────┴─────────┴─────────────┴────────┘         │
│                                                                  │
│  Export: download_button → Balance_Normalizado.xlsx              │
└──────────────────────────────────────────────────────────────────┘
```

---

## Grafo del Pipeline V2 Existente (orchestrator/pipeline_v2.py)

```
HomologationPipelineV2.process(pdf_path) → DocumentContext
│
│  ctx = DocumentContext(source_file)
│    ├── identity (document_id, source_file, sha256)
│    ├── metadata = None
│    ├── structure = None
│    ├── parser = None
│    ├── knowledge = None
│    ├── validation = None
│    ├── prediction = None
│    ├── execution = None
│    ├── custom = {}   ← datos no estructurados
│    ├── lifecycle (NEW → ... → COMPLETED)
│    └── snapshots = []
│
├── 1. SIEAdapter.run(ctx)
│      → ctx.metadata = DocumentMetadata(company, year, layout)
│      → ctx.structure = StructureData(document_type, column_layout)
│      → state: NEW → IDENTIFIED
│
├── 2. DIEAdapter.run(ctx)
│      → document_intelligence.DocumentIntelligence.analyze(path)
│      → ctx.prediction = PredictionData(confidence_expected, coverage_expected, complexity)
│      → ctx.custom["die_report"]
│      → NOTA: state NO cambia (no hay transition para prediction)
│
├── 3. ParserAdapter.run(ctx)
│      → ParserPDF.parsear(path) | parsear_excel(path)
│      → ctx.parser = ParserData(selected_parser, parser_version, raw_accounts)
│      → ctx.custom["parser_resultado"] = ResultadoParseo
│      → state → PARSED
│
├── 4. KBAdapter.run(ctx)
│      → Internamente instancia HomologationPipeline (DEPENDENCIA DIRECTA)
│      → pipeline._classify_account() para cada cuenta raw
│      → ctx.knowledge = KnowledgeData(cmcc_matches, learning_hits, dictionary_matches)
│      → ctx.custom["classified"] = [{...}, ...]
│      → ctx.custom["ignored"] = [{...}, ...]
│      → state → CLASSIFIED
│
├── 5. DecisionAdapter.run(ctx)
│      → decision_engine.Decision.* (del módulo root decision_engine.py)
│      → ctx.custom["decisions"] = [Decision.to_dict(), ...]
│      → ctx.custom["decision_stats"]
│      → ctx.custom["decision_confidence_real"]
│      → ctx.custom["decision_coverage_real"]
│
├── 6. ValidationAdapter.run(ctx)
│      → validation.balance_validator.BalanceValidator.validate()
│      → ctx.validation = ValidationData(integrity, subtotal, equation, missing)
│      → ctx.custom["validation_result"]
│      → state → VALIDATED
│
├── 7. ReviewAdapter.run(ctx)
│      → Filtra cuentas sin standard_code → review_queue
│      → ctx.execution = ExecutionData(review_required, status)
│      → ctx.custom["review_queue"]
│      → state → REVIEWED
│
├── 8. CoverageAdapter.run(ctx)
│      → coverage_engine.CoverageCalculator.compute(ctx)
│      → ctx.custom["coverage"] (overall, monetary, structural, semantic, document)
│      → ctx.custom["coverage_issues"]
│      → NOTA: state NO cambia
│
└── 9. SelfQAAdapter.run(ctx)
       → self_qa_engine.QualityGateEvaluator, RiskCalculator, ConfidenceEngine
         IssueAnalyzer, ApprovalEngine, RecommendationEngine
       → ctx.custom["self_qa"] = QAResult.to_dict()
       → ctx.custom["self_qa_state"], "self_qa_confidence", etc.
       → NOTA: state NO cambia

ctx.complete()
  → state → COMPLETED
  → return ctx
```

---

## Comparación: Orden de Ejecución V1 vs V2

```
V1 (app_validacion.py)                              V2 (orchestrator/pipeline_v2.py)
══════════════════════                               ════════════════════════════════

1. Extraer metadata (encabezado)                     1. SIE → metadata + structure
2. Parsear documento                                 2. DIE → predicción
3. Clasificar (MotorHibridoLocal /                   3. Parser → parsear
   HomologationPipeline)                             4. KB → clasificar
4. [Shadow mode: pipeline completo + comparación]    5. Decision → resolver conflictos
5. Propagar entre balances                           6. Validation → validar balance
6. Mostrar UI                                        7. Review → cola revisión
7. Revisión humana                                   8. Coverage → cobertura
8. Exportar Excel                                    9. Self QA → calidad
                                                     10. Complete → COMPLETED

DIFERENCIAS CLAVE:
- V2 usa DocumentContext como único contrato
- V2 escribe-once (cada sección solo se asigna una vez)
- V2 no tiene UI (puede ejecutarse desde cualquier lado)
- V2 no tiene propagación entre balances
- V2 no tiene Shadow Mode
- V2 no exporta Excel (eso es responsabilidad de UI)
```

---

## Módulos No Conectados en el Grafo Real

```
document_intelligence/ ──→ Solo usado por DIEAdapter en V2
                              NO usado en V1
                              
structure_engine/ ──────→ Solo usado por SIEAdapter en V2
                              NO usado en V1

document_context/ ──────→ Solo usado por V2
                              NO usado en V1

knowledge_base/ ────────→ NO usado ni en V1 ni en V2
                              KBAdapter usa HomologationPipeline, NO knowledge_base/

validation/ ────────────→ Solo usado por ValidationAdapter en V2
                              En V1: validación inline (_validar_cuadre_utilidad)

coverage_engine/ ───────→ Solo usado por CoverageAdapter en V2
                              NO usado en V1

self_qa_engine/ ────────→ Solo usado por SelfQAAdapter en V2
                              NO usado en V1

review_workspace/ ──────→ NO usado ni en V1 ni en V2
                              ReviewAdapter no usa review_workspace/

decision/ (engine.py) ──→ Usado por HomologationPipeline si ENABLE_DECISION_ENGINE
                              NO usado por el V2 (V2 usa decision_engine.py root)

decision_engine.py(root) → Usado por DecisionAdapter en V2
                              NO usado en V1

dataset_manager.py ─────→ NO usado (CLI independiente)

src/core/orquestador.py → NO usado (stub)

context/ ───────────────→ NO usado (predecesor de document_context/)
```
