# Módulo: Clasificación

> **Ubicación**: `clasificador_codigo_cuenta.py`, `pipeline/cmcc_classifier.py`,
> `classification_engine/`, `reglas_especiales.py`, `special_account_rules.py`

## Propósito

Determinar el **código estándar** (CMCC: AC.01, PC.05, PAT.01, ER.09, etc.)
de cada cuenta del balance usando múltiples métodos en cascada:
por código, por diccionario, por Gold Standard, semántico, CMCC y reglas
regex audited.

## Responsabilidad

1. Clasificar por **código numérico** (formato guion/punto/compacto).
2. Clasificar por **diccionario** (exacto/fuzzy).
3. Clasificar por **Gold Standard**, **CMCC** y **semántico**.
4. Aplicar **reglas especiales** (R1-R5) y **regex fallback** (7 patrones).
5. (Nuevo) Ranking Top-N con pesos configurables (`classification_engine`).

## Componentes

| Componente | Ubicación | Rol |
|---|---|---|
| `ClasificadorCodigo` | `clasificador_codigo_cuenta.py:28` | Clasificación por código (conf 0.85-0.98) |
| `CMCCClassifier` | `pipeline/cmcc_classifier.py:11` | Catálogo maestro CMCC (rapidfuzz). Ver `docs/reference/CMCCClassifier.md` |
| `LearningEngine` | `learning/engine.py` | Gold Standard. Ver `docs/reference/LearningEngine.md` |
| `SemanticMatcher` | `semantic/matcher.py` | Conceptos (6 tiers). Ver `docs/reference/SemanticEngine.md` |
| `SemanticEngine` | `semantic/semantic_engine.py` | Metadata semántica (no decide) |
| `DecisionEngine` V1 | `decision/engine.py` | Resuelve SM vs Regex. Ver `docs/reference/DecisionEngine.md` |
| Cascada V1 | `pipeline/homologation_pipeline.py:_classify_account` | Ordena los métodos (ver abajo) |
| `classification_engine/` | `engine.py`, `candidate.py`, `score.py`, `decision.py`, `explainer.py`, `metrics.py` | Motor Top-N nuevo (Sprint 39) |
| `reglas_especiales.py` / `special_account_rules.py` | — | Reglas R1-R5 post-clasificación |

## El clasificador por código (`ClasificadorCodigo`)

### `ResultadoCodigo` (`:20-25`)

`codigo_estandar, confianza, tipo_formato, razon`.

### `detectar_formato(codigo)` (`:191-202`)

- `guion` (`^\d+-\d+`), `punto` (`^\d+\.\d+`), `compacto` (`^\d{6,10}$`),
  `sin_codigo`/`desconocido`.

### `clasificar(codigo) -> ResultadoCodigo | None` (`:204-222`)

Detecta formato → `_buscar_en_mapa` con patrones compilados ordenados de más
específico a más general (`__init__:182-189`).

### Mapas (patrones → código estándar + confianza)

- `MAPEO_GUION` (`:36-104`): formatos `1-XX-YY-ZZ` (DSI/genérico),
  `2-XX` pasivo, `3-XX` patrimonio, `4-8` resultados. ~50 entradas.
- `MAPEO_COMPACTO` (`:107-144`): Wilug/Inmobiliaria (`1112001`, `2171003`,
  `4111001`, ...). ~35 entradas.
- `MAPEO_PUNTO` (`:147-180`): KAME ONE (`1.01.01.02`, `2.01.07.01`, ...).
  ~30 entradas.

Confianzas típicas: 0.85 (grupo amplio), 0.93-0.97 (patrón específico).

## La cascada de clasificación (V1, `_classify_account`)

Orden efectivo con flags default (ver `docs/architecture/feature_flags.md` y
`docs/architecture/processing_pipeline.md`):

```
1. LearningEngine.best_match(name)         [Gold Standard, siempre]
      → learning_exact | learning_fuzzy
2. CMCC (ENABLE_CMCC=False)                [shadow/off]
3. DecisionEngine V1 (ENABLE_DECISION_ENGINE=False)  [off]
4. code → dict_exact → dict_fuzzy          [default, first-match-wins]
5. SemanticMatcher (ENABLE_SEMANTIC_MATCHER=False)   [off]
6. RegexFallback (ENABLE_REGEX_FALLBACK=True): 7 patrones audited
7. unclassified (conf 0.0)
+ reglas especiales R1-R5 (post) → final_code
```

## El nuevo motor Top-N (`classification_engine/`)

Ver `docs/modules/decision_engine.md` (sección "classification_engine"). Puntos
clave:

- **Flujo**: `generate (CandidateGenerator) → score (Scorer) → explain
  (Explainer)` → `TopNResult`.
- **Capas de decisión** (`engine.py:31-34`): `code, catalog_exact,
  synonyms_exact, synonyms_fuzzy, special_rules` (las de refuerzo no deciden).
- **Pesos configurables** (`score.py:75` `WeightConfig`, `:187` `Scorer`).
- **Nunca ranking vacío**: candidato UNKNOWN garantizado
  (`_ensure_non_empty`, `engine.py:110-124`).
- **No integrado** al pipeline (Sprint 39 según docstring).

## Reglas especiales (R1-R5)

Aplicadas por `ProcesadorReglasEspeciales` tras la clasificación por cuenta
(`homologation_pipeline.py:535-545`); producen `final_code` y
`special_rule`. Se declaran en `reglas_especiales.py` /
`special_account_rules.py` (ver `docs/reference/HomologationPipeline.md`).

## Entradas

- `account_code` (código del balance) y/o `account_name` + `account_tipo`.

## Salidas

- `ResultadoCodigo` (por código).
- Dict de clasificación de cuenta: `{standard_code, confidence, method,
  reason, ...}`.
- `TopNResult` (motor nuevo).

## Dependencias

`re`, `rapidfuzz` (CMCC, fuzzy), `learning/`, `semantic/`, `decision/`,
`pipeline/features.py`, `app_validacion.py` (`REGLAS_REGEX`), `json`.

## Feature flags

`ENABLE_CMCC*`, `ENABLE_DECISION_ENGINE`, `ENABLE_SEMANTIC_MATCHER`,
`ENABLE_REGEX_FALLBACK`, `ENABLE_ACCOUNT_TYPE_FILTER`. Ver
`docs/architecture/feature_flags.md`.

## Objetos clave

`ClasificadorCodigo`, `ResultadoCodigo`, `CMCCClassifier`, `LearningEngine`,
`SemanticMatcher`, `DecisionEngine`, `CandidateGenerator`, `Scorer`,
`WeightConfig`, `TopNResult`, `ProcesadorReglasEspeciales`.

## Relaciones

- V1: `HomologationPipeline._classify_account` (toda la cascada).
- V2: `KBAdapter._classify_accounts` → reusa `_classify_account`.
- Benchmark V2: `decision_v2/DecisionEngineV2` (propia cascada de evidencia).
- `app_validacion.py` define `REGLAS_REGEX` (patrones audited).
- Scripts: `run_audit.py`, `test_dictionary_audit.py`, `test_semantic.py`.

## Riesgos

1. **Configuración de la cascada por feature flags con defaults
   desactivados**: la vía real es Gold Standard → código → diccionario →
   regex; CMCC/semántico/DecisionEngine están OFF.
2. `diccionario.json` con duplicados (`test_dictionary_audit.py` falla).
3. Múltiples fuentes de verdad para la clasificación (V1 cascada,
   `decision_v2`, `classification_engine`) sin consolidar.
4. Umbrales/confianzas hardcodeados en los mapas y en cada método.
5. `decision_v2` importa `REGLAS_REGEX` desde `app_validacion` (acoplamiento
   UI).

## Mejoras futuras

- Integrar `classification_engine` (Top-N con pesos) en el pipeline y
  consolidar las cascadas.
- Mover umbrales/confianzas a configuración.
- Auditar y limpiar `diccionario.json`.
- Romper dependencias UI (`app_validacion`).
