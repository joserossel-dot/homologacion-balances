# Feature Flags

Existen **tres mecanismos distintos** de feature flags en el código.

## 1. `pipeline/features.py` — `CMCCFeatureFlags` (el más usado)

Registro central de flags del pipeline V1. Dataclass con defaults OFF/seguros.
Override por **variables de entorno** con prefijo `CMCC_<FLAG>` (cualquier
valor truthy: `1`, `true`, `yes`, `on`). Método `from_env()` lee el entorno;
`default()` devuelve los defaults.

| Flag | Default | Efecto en el código |
|---|---|---|
| `ENABLE_CMCC` | `False` | Master switch CMCC. Si `False`, no se ejecuta `CMCCClassifier.classify` (`homologation_pipeline.py:196-198`). |
| `ENABLE_CMCC_SHADOW` | `True` | Si `True` y `ENABLE_CMCC`, CMCC corre en shadow mode sobre cuentas UNKNOWN; resultado en `cmcc_shadow`, nunca afecta `standard_code` (`:443`). |
| `ENABLE_CMCC_PRODUCTION` | `False` | Si `True` y score ≥ `CMCC_THRESHOLD`, CMCC escribe `standard_code`/`final_code` (`:202-213`). |
| `ENABLE_CMCC_ROLLBACK` | `False` | Si `True`, desactiva todos los flags CMCC en `__post_init__` (`features.py:72-76`). |
| `CMCC_THRESHOLD` | `0.95` | Umbral mínimo para aceptar CMCC en producción (`:202`). |
| `CMCC_REVIEW_THRESHOLD` | `0.85` | Scores entre este y `CMCC_THRESHOLD` van a revisión humana (`:490`). |
| `ENABLE_CMCC_REVIEW_PIPELINE` | `False` | Si `True`, cuentas UNKNOWN con score CMCC == 1.0 se agregan a `REVIEW_CMCC` queue (`:497-515`). REVIEW_CMCC NO es clasificación. |
| `ENABLE_ACCOUNT_TYPE_FILTER` | `False` | Si `True`, valida `standard_code` contra el tipo resuelto (prefijos AC/ANC/PC/PNC/PAT/ER vs ACTIVO/PASIVO/PATRIMONIO/PERDIDA/GANANCIA); si contradicen → demote a unclassified (`:450-458`). También usado en `kb_adapter.py:116-121`. |
| `ENABLE_REGEX_FALLBACK` | `True` | Si `True`, los 7 patrones regex auditados (100% precisión) se aplican como última etapa de clasificación tras dict fuzzy (`:249, 293`). |
| `ENABLE_SEMANTIC_MATCHER` | `False` | Si `True`, `SemanticMatcher` corre después de dict fuzzy y antes de regex (`:46-51, 234-247, 284-290`). Carga `knowledge/concept_catalog.json`. |
| `ENABLE_DECISION_ENGINE` | `False` | Si `True`, enruta `_classify_account` por `_classify_with_decision_engine` (DecisionEngine V1, 5 reglas) en vez de first-match-wins (`:215-224`). |

Nota: con los defaults (OFF en casi todo), la clasificación efectiva es:
**Gold Standard → código → diccionario exacto → diccionario fuzzy → regex
fallback**, con reglas especiales R1-R5 como post-procesamiento.

## 2. `parser_universal.py` — constantes de módulo (no override por env)

Flags globales mutables en runtime (los tests y reportes los modifican).

| Flag | Default | Efecto |
|---|---|---|
| `ENABLE_DYNAMIC_LAYOUT` | `False` | Si `True`, ParserPDF usa perfil de familia / LayoutDetector para el orden de columnas; si `False`, heurística fija `ULTIMAS_COLS` (`parser_universal.py:38`). |
| `ENABLE_ACCOUNT_TYPE_RESOLVER` | `False` | Si `True`, ejecuta `AccountTypeResolver` tras el parseo (`:42`). |
| `ROTATION_CORRECTION_THRESHOLD` | `0.7` | Umbral de confianza para corregir rotación 180° sobre texto nativo (`:46`). |
| `LAYOUT_CONFIDENCE_THRESHOLD` | `0.8` | Umbral para usar `context.layout_hint` como orden de columnas (`:52`). |
| `ACCOUNT_TYPE_CONFIDENCE_THRESHOLD` | `0.7` | Umbral para activar resolver desde contexto (`:57`). |

## 3. `config/features.py` — `FeatureFlags` (carga YAML, casi sin consumidores)

Clase con flags default `True` y override vía `config/features.yaml` (si
existe). Métodos `is_enabled(name)`, `__getattr__`, `to_dict`, `load`,
`save`.

Flags declarados: `document_intelligence`, `structure_engine`,
`knowledge_base`, `decision_engine`, `coverage_engine`, `self_qa_engine`,
`validation`, `review_workspace`, `export_excel`, `export_markdown`,
`export_json`.

**Hallazgo**: no se encontró ningún consumidor real de `is_enabled()` ni de
`.document_intelligence` en el runtime (el gating real del pipeline usa las
constantes de `parser_universal.py` y `CMCCFeatureFlags`). El mecanismo
`config/features.py` aparece **inactivo/sin consumir**.

## Configuración adicional

- `parsers/config.py` — `ParserConfig` con jerarquía default → 
  `parser_config.toml` → env `PARSER_*` (OCR, detección, layout, caching).
  Ejemplos: `PARSER_OCR_ENGINE`, `PARSER_OCR_DPI=250`,
  `PARSER_DETECTION_CODE_FORMAT_SAMPLE_LINES=60`,
  `PARSER_LAYOUT_ENABLE_DETECTION=True`.
- `config/release.yml` — gates del release pipeline (no es feature flag de
  runtime; son umbrales de calidad para `release_pipeline/`).

## Flags en V2 (importante)

`KBAdapter` construye `HomologationPipeline(db_path=...)` **sin pasar
`features`** (`kb_adapter.py:12-14`), por lo que **el pipeline V2 usa siempre
los defaults de `CMCCFeatureFlags`**. Las variables de entorno `CMCC_*` no
afectan a V2.
