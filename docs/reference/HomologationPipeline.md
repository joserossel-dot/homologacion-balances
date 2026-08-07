# HomologationPipeline

> Archivo: `pipeline/homologation_pipeline.py` (637 líneas)
> Clase: `HomologationPipeline` (`:30`)

## Propósito

Orquestador principal del pipeline V1 de homologación de balances. Procesa
un PDF o Excel, extrae cuentas, las clasifica contra un catálogo estándar,
aplica reglas especiales y produce un resumen completo con trazabilidad.
Además es el **núcleo de clasificación reutilizado por el pipeline V2** a
través de `adapters/kb_adapter.py`.

## Responsabilidad

- Parsear PDF (via `ParserPDF`) o Excel (via `parsear_excel`).
- Por cada cuenta: interpretar naturaleza, resolver tipo, clasificar con
  múltiples motores en cascada y aplicar reglas especiales.
- Recopilar métricas y contadores de cada método de clasificación.
- Exponer la clasificación por cuenta como método reutilizable
  (`_classify_account`).

## Constructor

`__init__(db_path="gold_standard.db", features: CMCCFeatureFlags | None)`
(`:31-51`):

| Atributo | Tipo | Descripción |
|---|---|---|
| `_parser` | `ParserPDF` | Parser de PDFs (`:36`) |
| `_code_classifier` | `ClasificadorCodigo` | Clasificación por código (`:37`) |
| `_rule_processor` | `ProcesadorReglasEspeciales` | Reglas R1-R5 (`:38`) |
| `_learning_engine` | `LearningEngine` | Gold Standard (`:39`) |
| `_dictionary` | `list[dict]` | `diccionario.json` sin `__EXCLUIR__` (`:40`) |
| `_semantic_engine` | `SemanticEngine` | Metadata semántica (v2) (`:41`) |
| `_cmcc_classifier` | `CMCCClassifier` | Clasificador CMCC (`:42`) |
| `_decision_engine` | `DecisionEngine` | DecisionEngine V1 (`:43`) |
| `_features` | `CMCCFeatureFlags` | Feature flags (`:44`) |
| `_semantic_matcher` | `SemanticMatcher \| None` | Se crea solo si `ENABLE_SEMANTIC_MATCHER` y existe `knowledge/concept_catalog.json` (`:45-51`) |

Constante de clase `_REGEX_FALLBACK` (`:59-62`): 7 patrones regex auditados
al 100% de precisión (índices 16, 19, 26, 31, 34, 35, 36 de `REGLAS_REGEX`
= PC.05, PC.08, PAT.02, ER.04, ER.09, ER.10, ER.11).

## Métodos principales

### Entrada principal

- `process(pdf_path) -> dict` (`:364-614`): flujo completo (ver
  `docs/architecture/processing_pipeline.md`). Devuelve `summary` con
  `classified`, `ignored` y contadores.
- `to_json(pdf_path, output_file)` (`:633-637`): escribe el resumen como JSON.

### Clasificación por cuenta (reutilizable)

- `_classify_account(account_code, account_name, account_tipo, store_cmcc_shadow=True) -> dict` (`:175-266`):
  cascada de clasificación. Devuelve dict con `standard_code`, `confidence`,
  `method`, `reason`, más `cmcc_shadow`/`cmcc_detail`/`_cmcc_score` opcionales.
- `_classify_with_decision_engine(...)` (`:268-347`): rama del DecisionEngine V1.
- `_classify_by_code` (`:108`), `_classify_by_dictionary_exact` (`:119`,
  conf 0.98), `_classify_by_dictionary_fuzzy` (`:131`, token_sort_ratio ≥90,
  conf 0.80-0.97), `_classify_by_regex` (`:154`).
- `_confidence_from_label(label, fallback)` (`:349-358`): VERY_HIGH .99 /
  HIGH .90 / MEDIUM .75 / LOW .50 / UNKNOWN 0.
- `_is_code_allowed_for_tipo(code, tipo)` (`:617-631`): mapa de prefijos
  ANC/AC/PNC/PC/PAT/ER contra ACTIVO/PASIVO/PATRIMONIO/PERDIDA/GANANCIA.

### Helpers estáticos

- `_load_dictionary()` (`:68-73`): carga `diccionario.json`, filtra
  `__EXCLUIR__`.
- `_normalize_name(name)` (`:75-80`): lower + limpia no-alfanuméricos.
- `_infer_company(source_file)` (`:82-87`): empresa desde nombre de archivo.
- `_infer_layout(source_file)` (`:89-102`): layout desde nombre de archivo
  (8_columnas/tributario/pre_balance/consolidado/excel/pdf_estandar).

## Salida de `process()` — `summary` dict

`homologation_pipeline.py:574-606`:

```
source_file, accounts_total, accounts_classified, accounts_ignored,
accounts_without_dictionary_match,
learning_hits, learning_exact, learning_fuzzy, fallback_classifier,
semantic_total, semantic_matches, semantic_unknown, semantic_confidence_avg,
regex_hits, semantic_matcher_hits,
decision_engine_total, decision_engine_agreements, decision_engine_sm_high,
decision_engine_regex_exact, decision_engine_conflicts,
decision_engine_human_review,
cmcc_shadow_hits, cmcc_production_hits, cmcc_review_queue, tipo_filtered,
cmcc_feature_flags, elapsed_seconds, classified, ignored
```

Cada ítem de `classified` (`:550-566`):
`account_code, account_name, nature, classification_amount, standard_code,
final_code, confidence, method, reason, special_rule, source_file,
source_page, semantic_result, cmcc_shadow, cmcc_decision`.

Cada ítem de `ignored` (`:436-441`): `account_code, account_name,
ignored_reason` (solo `"movement_only"`: monto None).

## Dependencias

Ver `docs/architecture/dependency_graph.md`. Las principales:
`AccountAdapter`, `ClasificadorCodigo`, `REGLAS_REGEX`, `parsear_excel`,
`ParserPDF`, `BalanceInterpreter`, `LearningEngine`, `AccountBalance`,
`CMCCClassifier`, `CMCCFeatureFlags`, `ProcesadorReglasEspeciales`,
`DecisionEngine`, `SemanticEngine`, `SemanticMatcher`.
Diferidos: `decision.models.DecisionResult`,
`parsers.account_type_resolver.AccountTypeResolver`,
`review.cmcc_review_models.ReviewCMCC`.

## Quién lo utiliza

- `adapters/kb_adapter.py:12-14, 110` — V2 (clasificación).
- `app_validacion.py:47, 436` — UI principal Streamlit.
- `ui/app.py:44` — UI V1.
- `validation/runner.py` — runner de validación.
- `benchmark/benchmark_runner.py` — benchmarks.
- `scripts/` varios (benchmarks de pipeline, layout, regex).

## Feature Flags utilizadas

Todas las de `CMCCFeatureFlags` (`pipeline/features.py`). Ver
`docs/architecture/feature_flags.md`.

## Riesgos técnicos

1. **Monolito**: `process()` ocupa ~250 líneas con muchas responsabilidades
   (parseo, clasificación, reglas, métricas).
2. **Dependencia del `diccionario.json`**: los matches exacto/fuzzy dependen
   de su calidad; tiene entradas `__EXCLUIR__` y duplicados conocidos
   (fallos en `test_dictionary_audit.py`).
3. **Pesos/umbrales hardcodeados**: confianza 0.98 (exact), rango fuzzy,
   umbral ≥90, mapping de etiquetas de confianza.
4. **SemanticEngine (v2)** se ejecuta siempre por cuenta (`:517`) pero solo
   produce metadata de reporte; su resultado no afecta el código final.
5. **Posible bug potencial**: en `parsear_linea` los montos cero se saltan
   pero el fallback puede asignar un monto 0 con origen ACTIVO (ver
   `docs/modules/parser.md`).
6. En V2, `KBAdapter` usa los **defaults** de los feature flags (no pasa
   `features`), por lo que flags de entorno no aplican al pipeline V2.

## Posibles mejoras futuras

- Reemplazar la cascada de clasificación por el nuevo `classification_engine`
  (Top-N con `WeightConfig` parametrizable), según
  `reports/sprint38_architecture_review.md`.
- Mover los umbrales y pesos a configuración explícita.
- Separar el ciclo de métricas de `process()` en un recolector.
