# Auditoría de Arquitectura — Sprint 38 (Decision Engine)

> Documento de arquitectura SOLO análisis. No se crea, modifica ni elimina ningún archivo de código.
> El objetivo es garantizar la mantenibilidad del proyecto a 6 meses antes de decidir cómo implementar el Decision Engine.

---

## 1. Responsabilidad de cada paquete

| Paquete | LOC | Responsabilidad | Estado en producción |
|---|---|---|---|
| `decision/` | 248 | Resolución de conflictos SM vs Regex por **reglas hardcodeadas** (5 reglas, umbrales 0.95/0.70). Produce `DecisionResult` con un único `codigo_final`. | **ACTIVO** en V1 (`pipeline/homologation_pipeline.py`, flag `ENABLE_DECISION_ENGINE`) |
| `decision_v2/` | 650 | Clasificador por-cuenta tipo **weighted ensemble** (Gold Standard + código + diccionario exact/fuzzy + SemanticMatcher + Regex). Reglas R1–R10, pesos `_EVIDENCE_WEIGHTS` hardcodeados. Devuelve **un único** `final_code`. | **SOLO benchmarks** (`scripts/benchmark_decision_v2.py`, `scripts/classifier_precision.py`). NO integrado |
| `decision_engine/` | 703 | Capa de **decisión a nivel documento**: recolecta evidencia del `DocumentContext`, detecta conflictos, calcula confianza (`DEFAULT_WEIGHTS`), genera explicaciones y estadísticas. NO clasifica cuentas (consume `classified` ya resuelto). | **ACTIVO** en V2 (`adapters/decision_adapter.py` → `orchestrator/pipeline_v2.py`). 122 tests |
| `semantic/` | 1290 | **Dos subsistemas independientes**: (v1) `SemanticMatcher` catalog-driven (78 conceptos, 6 tiers fuzzy) → CMCC code; (v2) `SemanticEngine` reglas hardcodeadas (10 reglas, first-hit-wins) → metadata semántica. | v1: activo (flag `ENABLE_SEMANTIC_MATCHER`); v2: activo en KBAdapter |
| `explainability/` | 693 | Trazabilidad ex-post: `DecisionTrace`, `DecisionCode` (D001–D204), `TraceBuilder` (lee audit_data.json + shadow.xlsx), `TraceReport`, `TraceExporter`. Umbrales y heurísticas hardcodeadas. | **NO integrado**. Solo `scripts/run_decision_trace.py` y `scripts/cmcc_compatibility_report.py` |
| `evidence/` | 817 | Modelo `AccountEvidence` + `MonetaryAmounts`, builders desde shadow/parser, serialización, cobertura y reportes de auditoría. | **HUÉRFANO**. 0 consumidores de producción; solo `test_evidence.py` y `run_evidence_audit.py` |
| `context/` | 340 | `AccountContext` + `ContextBuilder`: contexto estructural/hierárquico/navegacional sobre `CuentaRaw`. Heurísticas hardcodeadas (formato, secciones, keywords). | **HUÉRFANO**. Solo `test_context_builder.py` |
| `document_context/` | 1679 | **Contexto único del documento** write-once: `DocumentContext` + modelos (`DocumentMetadata`, `StructureData`, `ParserData`, `KnowledgeData`, `ValidationData`, `PredictionData`, `ExecutionData`) + serializers/validators/merge/snapshot/statistics. | **ACTIVO y CENTRAL**: todos los adapters de V2 lo usan |
| `document_intelligence/` | 7688 | Análisis documental previo al parser: `DocumentIntelligence`, `FormatAnalyzer`, `DocumentProcessingContext`, detectores, extractores (Specialized/Universal), mining de familias (`DocumentFamily`), DKB (`DocumentFingerprint`, `DocumentProfile`), trainer, recommendation engine. `ExtractorResult.to_dict()` = `extractor_info`. | **ACTIVO** vía `DIEAdapter` en V2 (produce `die_report` + `PredictionData`) |

**Conclusión de responsabilidades:** hay exactamente **tres capas de decisión distintas** que coexisten sin colisionar en producción:
1. **Clasificación por-cuenta** (code → dict → SM → regex, o `decision/`, o `decision_v2/`) → produce un único código por cuenta.
2. **Decisión a nivel documento** (`decision_engine/`) → agrega evidencia del contexto, decide CONTINUE/REVIEW/REJECT y genera estadísticas.
3. **Trazabilidad ex-post** (`explainability/`) → reconstruye decisiones pasadas para auditoría.

Ninguna de las tres devuelve un **ranking Top-N de candidatos por cuenta**. Ese contrato no existe hoy en ningún motor.

---

## 2. Módulos obsoletos

| Módulo | Motivo de obsolescencia |
|---|---|
| `decision/engine.py` | Motor de 5 reglas con umbrales hardcodeados (0.95/0.70). El reporte `reports/classifier_precision.md` (248 cuentas) demuestra que en conflicto SM-vs-Regex la decisión es ~50/50: las reglas 2/3 son ad-hoc y no usan la capa de conocimiento de Sprint 37. Es el eslabón más débil de V1. |
| `decision_v2/` (completo) | Benchmark experimental (59% de precisión en conflictos según `classifier_precision.md`). Usa fuentes de conocimiento viejas (diccionario.json, concept_catalog, GS auto-sembrado con 61.6% error) y NO usa `catalogo_maestro.json` ni `account_synonyms.json` ni `special_account_rules.py`. Devuelve 1 código, no Top-N. |
| `decision_engine.py` (raíz, 102 LOC) | Reglas F01–F04 para elegir extractor PDF vía `inspect_pdf.py`. **Reemplazado** por `document_intelligence` (FormatAnalyzer + ExtractorFactory + `DocumentProcessingContext`). Solo lo usa `validate_families.py`. |
| `semantic/semantic_rules.py` + `semantic_engine.py` (v2) | 10 reglas hardcodeadas (keywords, confianza 0.95). **Solapa conceptualmente con `special_account_rules.py` (19 reglas, Sprint 37)** que es la capa de conocimiento canónica y data-driven. El `SemanticEngine` no consume el catálogo ni sinónimos. |
| `semantic/semantic_catalog.py` | `SemanticCatalog` solo lo usa un test; es metadata estática IFRS/NIC sin consumidor real. |
| `explainability/trace_builder.py` (parte) | Heurísticas de confianza hardcodeadas (layout/ocr/parser/column-mapping) y dependencia de `audit_data.json` + `cmcc_shadow.xlsx`; acoplado a formato V1. |
| `context/` (completo) | Huérfano; su rol de contexto estructural es cubierto por `document_context.StructureData` (family/template/layout) en V2. `AccountContext` (jerarquía) no tiene consumidor. |
| `evidence/` (completo) | Huérfano; el reporte `_render_audit_md` admite en su propio texto "How to Integrate" que aún no está integrado. Duplica la función de `decision_engine/evidence.py`. |

---

## 3. Módulos duplicados

| Función | Dónde está duplicada | Notas |
|---|---|---|
| **Normalización de nombres** | `app_validacion.normalizar_nombre()`, `pipeline/homologation_pipeline._normalize_name()`, `learning/exact_match.normalize_name()`, `semantic/normalizer.SemanticNormalizer`, `account_name_normalizer.AccountNameNormalizer` (Sprint 37, la canónica) | Ya documentado en `reports/app_health_check.md` §6.4. El único que expande abreviaciones/plurales/OCR es `AccountNameNormalizer`. |
| **Pesos de evidencia / scoring** | `decision_v2/_EVIDENCE_WEIGHTS`, `decision_engine/confidence.DEFAULT_WEIGHTS`, `decision_engine/scorer`, `semantic/scorer.TIER_WEIGHTS` | Tres sistemas de pesos incompatibles, todos hardcodeados. |
| **Recolección de evidencia** | `decision_engine/evidence.EvidenceCollector` vs `evidence/evidence_builder` vs `decision_v2._collect_evidence` | Tres formas de modelar "evidencia" con modelos distintos (`DecisionEvidence` vs `AccountEvidence` vs `Evidence`). |
| **Explicación legible** | `decision_engine/explainability.ExplanationGenerator`, `semantic/matcher.explain()`, `explainability/decision_trace.explanation` | Tres generadores de texto de explicación. |
| **Conflictos** | `decision/engine.py` (SM vs Regex), `decision_engine/conflict_resolver.py`, `decision_v2/_resolve_by_priority` | Tres resoluciones de conflicto. |
| **Clasificación por cuenta** | `pipeline/homologation_pipeline._classify_account`, `MotorHibridoLocal` (app_validacion), `decision_v2`, (futuro `classification_engine`) | Ya documentado en `reports/app_health_check.md` §6.3: `MotorHibridoLocal` vs `HomologationPipeline`. |
| **Detección de familia/layout** | `document_intelligence` (FormatSignature) vs `structure_engine.StructureDetector` vs `context.context_builder` | Tres detectores de estructura con heurísticas propias. |

**La duplicación de "evidencia" y "pesos" es la más costosa a 6 meses**: cualquier cambio de pesos debe replicarse en 2–3 sitios y los reportes de precisión difieren según el motor usado.

---

## 4. Componentes que conviene REUTILIZAR

| Componente | Por qué | Uso propuesto |
|---|---|---|
| `document_context.DocumentContext` + modelos | **Contexto único ya integrado** en todos los adapters V2; write-once, serializable, con `set_custom/get_custom`. | Es EL contrato de contexto para el nuevo engine. NO crear un contexto paralelo. |
| `document_context.models.StructureData` (family/template/column_layout/document_type) | Ya produce la familia/layout que el brief pide como capa de contexto documental. | Leer `ctx.structure` para capa de familia/layout. |
| `document_context.models.PredictionData` | Confianza/cobertura esperada del DIE. | Leer `ctx.prediction` para capa de contexto. |
| `document_intelligence.DocumentProcessingContext` | El `DocumentProcessingContext` que menciona el brief YA EXISTE (Sprint 31): `signature` (document_type/family/layout/confidence), `extractor_type`. | Es la capa `extractor_info`. No duplicar. |
| `document_intelligence.extractors.base.ExtractorResult` | `extractor_id`, `family_id`, `confidence`, `fallback_used` (`.to_dict()` = `extractor_info`). | Capa de extractor del engine. |
| `knowledge_base/document_kb.json` → `DocumentProfile` (family, recommended_extractor) | Perfiles documentales ya existentes. | Capa de perfiles. |
| `account_name_normalizer.AccountNameNormalizer` (Sprint 37) | Normalizador canónico (abreviaciones, plurales, OCR, errores digitación). | Único normalizador del engine. |
| `knowledge_base/account_synonyms.json` + `catalogo_maestro.json` + `special_account_rules.py` (Sprint 37) | Capa de conocimiento canónica del catálogo. | Fuente de candidatos (catálogo/sinónimos/reglas). |
| `decision_engine.DecisionStatisticsCollector` + `DecisionType` | Estadísticas a nivel documento ya integradas en V2. | Reutilizar para métricas/estadísticas en Sprint 39, no reimplementar. |
| `decision_engine.ConflictResolver` | Detección de conflictos entre evidencias con severidad. | Reutilizable en la capa de decisión. |

---

## 5. Componentes que NO deben reutilizarse

| Componente | Por qué NO reutilizar |
|---|---|
| `decision/engine.py` como motor | Reglas hardcodeadas, umbrales mágicos, sin capa de conocimiento, sin Top-N. Será deprecado. |
| `decision_v2/engine.py` como base del engine | Pesos hardcodeados, fuentes de conocimiento viejas (GS con 61.6% error, diccionario 854, concept_catalog 78) que NO incluyen el catálogo de Sprint 37, devuelve 1 código, benchmark-only. Serviría como referencia de patrón de scoring, NO como base. |
| `semantic/semantic_rules.py` (10 reglas) | Duplica con `special_account_rules.py`; reglas hardcodeadas en código. |
| `explainability/trace_builder.py` heurísticas | Confianzas inventadas (layout 1.0/0.5/0.0, ocr 1.0/0.8/0.5) en lugar de confianzas reales de cada fuente. |
| `evidence/` (paquete) | Huérfano y solapado con `decision_engine/evidence.py`. No añadirlo al grafo de dependencias del engine. |
| `context/` (paquete) | Huérfano; su responsabilidad ya la cubre `document_context`. |
| `decision_engine/models.DecisionScore.weighted_total` (pesos 0.40/0.25/0.15/0.10/0.10 hardcodeados) | Los pesos del nuevo engine deben ser **parametrizables**, no heredados de este cálculo fijo. |
| `diccionario.json` como fuente primaria | 854 entradas con código `__EXCLUIR__` y formatos legacy; la fuente canónica ahora es `catalogo_maestro.json` (61 cuentas, curadas). |

---

## 6. Riesgos de crear un CUARTO motor de decisión

1. **Confusión de nombres/roles**: quedarían 4 paquetes con "decision/classification" (`decision/`, `decision_v2/`, `decision_engine/`, `classification_engine/`). Riesgo real de que un futuro desarrollador use el equivocado.
2. **Tercer sistema de pesos**: ya hay `_EVIDENCE_WEIGHTS`, `DEFAULT_WEIGHTS`, `TIER_WEIGHTS`; un 4to sin gobernanza fragmenta la calibración y hace los reportes de precisión incomparables.
3. **Tercera definición de "evidencia"**: `DecisionEvidence` vs `Evidence` vs `AccountEvidence`; un 4to modelo (`Candidate/EvidenceSource`) aumenta la conversión de tipos.
4. **Knowledge drift**: el nuevo engine consumiría `catalogo_maestro`+`account_synonyms`+`special_rules`, mientras `decision_v2` y `semantic` consumen `diccionario`+`concept_catalog`+GS. Dos catálogos divergentes (61 vs 78 vs 854) → resultados inconsistentes por motor.
5. **Ambigüedad de integración (Sprint 39)**: sin contrato claro, no se sabrá si `classification_engine` reemplaza a `_classify_account`, a `decision/`, o a la capa de decisión documental de `decision_engine/`.
6. **Costo de tests y mantenimiento**: cada motor suma su suite; ya hay 122 tests solo en `test_decision_engine.py`.

**Mitigaciones (integradas en la propuesta):**
- Contrato de responsabilidades explícito por paquete (docstring en `__init__.py` de `classification_engine/` y tabla en este documento).
- Deprecar `decision/` y `decision_v2/` con marcado visible (no borrar en este sprint).
- El nuevo engine consume **solo** la capa de conocimiento de Sprint 37 (canónica), cerrando el knowledge drift.
- Reutilizar `document_context` + `decision_engine` para estadísticas (Sprint 39), no duplicar.

---

## 7. Propuesta definitiva de arquitectura

### Rol asignado a cada paquete (contrato a 6 meses)

| Paquete | Rol (único) |
|---|---|
| `classification_engine/` **(nuevo)** | **Clasificación por-cuenta con ranking Top-N**. Genera candidatos por capa de evidencia, puntúa con pesos parametrizados, explica y devuelve ranking completo. Consume `document_context` + capa Sprint 37 + contexto/extractor/perfil documental. |
| `decision_engine/` (existente) | Decisión y estadísticas **a nivel documento** en V2 (CONTINUE/REVIEW/REJECT, conflictos, confianza global). Sin cambios. |
| `semantic/` v1 (`SemanticMatcher`) | Una capa de evidencia más dentro de `classification_engine` (opcional, vía feature flag). No tocar. |
| `semantic/` v2, `decision/`, `decision_v2/`, `evidence/`, `context/`, `decision_engine.py` (raíz) | **DEPRECADOS** (marcados, no eliminados). No son consumidos por el nuevo engine. |
| `document_context/`, `document_intelligence/` | Contrato de contexto y contexto documental / extractor_info / perfiles. Reutilizados. |

### Estructura de `classification_engine/` (aditiva, NO toca nada existente)

```
classification_engine/
  __init__.py        # API pública + docstring de responsabilidad
  candidate.py       # CandidateGenerator: catálogo exacto → sinónimos exact/fuzzy →
                     #   reglas especiales → (opcional) SemanticMatcher → código
                     #   → familia/layout → DocumentProfile → list[Candidate]
  score.py           # Scorer parametrizado: recibe dict de pesos por capa
                     #   (catálogo, sinónimos, reglas, contexto, extractor, perfil);
                     #   sin constantes rígidas; peso default configurable.
  decision.py        # Modelos: Candidate, EvidenceSource, RankedCandidate,
                     #   TopNResult, ClassificationExplanation, DocumentProcessingContextAdapter
  explainer.py       # Explicación humana por capa/peso/score (listo para auditoría)
  engine.py          # DecisionEngine: candidate → score → rank (SIEMPRE Top N) →
                     #   explain → metrics; consume DocumentContext + capa Sprint 37
  metrics.py         # Top-1/Top-N/MRR@N/cobertura/histograma de confianza → serializable
```

**Contrato de entrada/salida:**
- Entrada: `account_code`, `account_name`, `account_tipo`, y un `DocumentProcessingContextAdapter` construido desde `DocumentContext` (o un `DocumentContext` real). El adapter es una clase read-only delgada que expone `family`, `template`, `layout`, `column_layout`, `document_type`, `selected_parser`, `extractor_info`, `document_profile`, `prediction`.
- Salida: `TopNResult` con `top_n: list[RankedCandidate]` (siempre ≥1, jamás vacío), `explanation`, `confidence`, `decision_source`, `metrics`.

**Reglas de diseño:**
1. **100% aditivo**: no se modifica ningún archivo existente. El engine solo hace imports read-only.
2. **Sin reglas de negocio hardcodeadas**: toda decisión sale de `catalogo_maestro.json`, `knowledge_base/account_synonyms.json`, `special_account_rules.py`, `account_name_normalizer.py`, `DocumentContext`, `extractor_info`, `DocumentProfile` y metadata existente.
3. **Pesos parametrizados**: `score.py` acepta un `dict[str, float]` (o un objeto `WeightConfig`) y un default de referencia; nada hardcodeado en el cuerpo del engine.
4. **Top N obligatorio**: el engine devuelve ranking completo; el threshold solo etiqueta confianza, nunca descarta candidatos del ranking.
5. **Determinismo y testabilidad**: sin I/O en el engine (se inyectan data sources); el adapter de contexto permite tests sin PDF.
6. **Pruebas**: `tests/test_classification_engine.py` (nuevo, unit + integración con `DocumentContext`). Los 2446 tests existentes deben seguir verdes.

### Qué NO hace `classification_engine/` en este sprint
- NO se integra al flujo de clasificación (eso es Sprint 39).
- NO modifica `ParserPDF`, `Parser Universal`, `HomologationPipeline`, `RuleProcessor`, extractores, `document_intelligence`, dataset mining, trainer, ni la knowledge base.
- NO reemplaza ni borra `decision/`, `decision_v2/`, `decision_engine/`.

---

## 8. Justificación técnica

1. **El brief pide un contrato que no existe**: ningún motor actual devuelve Top-N por cuenta. `decision/` y `decision_v2/` devuelven 1 código; `decision_engine/` no clasifica cuentas. Crear `classification_engine/` **no duplica un contrato existente**; llena un vacío.
2. **El brief fija la fuente de conocimiento de Sprint 37** (`catalogo_maestro` + `account_synonyms` + `special_account_rules` + contexto documental). Ningún motor existente consume esa capa: `decision_v2` usa diccionario/concept_catalog/GS; `decision/` usa SM+regex; `decision_engine/` usa evidencia genérica del contexto. No se puede "evolucionar" un motor existente hacia el brief sin reescribir su capa de conocimiento completa, lo que equivale a crearlo.
3. **`decision_v2/` es la mejor candidata para "evolucionar"**, pero falla como base: (a) solo vive en scripts/benchmarks (nadie lo mantiene en producción), (b) pesos hardcodeados, (c) usa GS con 61.6% de error documentado, (d) devuelve 1 código, (e) su precisión en conflictos es 59%. Evolucionarla = refactor total = nuevo motor de facto.
4. **Reutilización real**: la propuesta reutiliza `document_context` (el objeto de contexto más integrado del sistema), `DocumentProcessingContext`/`ExtractorResult`/`DocumentProfile` de `document_intelligence` (ya producidos), el normalizador y la capa de conocimiento Sprint 37. Así el paquete nuevo es delgado (solo candidato→score→rank→explain→metrics) y el conocimiento vive donde ya está.
5. **Mantenibilidad a 6 meses**: se elimina la ambigüedad de 4 motores definiendo un contrato único por paquete (tabla en §7) y deprecando los muertos. El nuevo engine es el único que toca el catálogo canónico, por lo que los reportes de precisión futuros serán consistentes.
6. **Costo**: el paquete es acotado (~6 módulos, ~600–800 LOC) y 100% aditivo; el riesgo de romper los 2446 tests es ~cero porque no se toca ninguna importación existente.

---

## 9. Diagrama de dependencias

```
                     ┌───────────────────────────────────────────────┐
                     │  document_context/  (CONTEXTO ÚNICO)          │
                     │  DocumentContext, StructureData, ParserData,  │
                     │  PredictionData, KnowledgeData, ValidationData│
                     └───────────────┬───────────────────────────────┘
                                     │ lee (read-only)
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  classification_engine/   (NUEVO — por-cuenta, Top-N)                │
│  ┌────────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │
│  │ candidate  │→ │  score    │→ │ decision  │→ │ explainer │        │
│  └────────────┘  └───────────┘  └───────────┘  └───────────┘        │
│        │              ▲                                        ▲    │
│        ▼              │                                        │    │
│  ┌────────────┐   WeightConfig (parametrizado)          ┌────────────┐
│  │   engine   │─────────────────────────────────────────→│  metrics   │
│  └────────────┘                                          └────────────┘
└──────────────────────────────────────────────────────────────────────┘
   │                     │                        │
   ▼                     ▼                        ▼
┌────────────────┐ ┌──────────────────┐ ┌─────────────────────────────┐
│ Capa Sprint 37 │ │ document_intelligence (DIE)                     │
│ catalogo_maestro│ │ DocumentProcessingContext (signature:          │
│ account_synonyms│ │   family/layout/type/confidence),              │
│ special_account │ │ ExtractorResult.extractor_info,                │
│ _rules +        │ │ DocumentProfile (family, recommended_extractor)│
│ AccountName     │ └───────────────────────────────────────────────┘
│ Normalizer      │
└────────────────┘
```

**Dependencias del nuevo paquete (todas read-only):**
- `document_context` (contexto único)
- `document_intelligence` (`DocumentProcessingContext`, `ExtractorResult`, `DocumentProfile`)
- `account_name_normalizer`, `special_account_rules`, `catalogo_maestro.json`, `knowledge_base/account_synonyms.json`
- (opcional) `semantic/matcher.SemanticMatcher` como una capa de evidencia
- `decision_engine` SOLO para estadísticas/conflictos en Sprint 39 (no en el núcleo)

**NO depende de:** `decision/`, `decision_v2/`, `evidence/`, `context/`, `explainability/`.

---

## 10. Flujo completo Parser → Contexto → Knowledge → Decision → Clasificación

### Estado actual (V2, ya integrado)

```
PDF/Excel
  │
  ▼
[SIEAdapter]      → DocumentMetadata (company/year/layout) + StructureData (family/template/layout)
  ▼
[DIEAdapter]      → die_report (IntelligenceReport) + PredictionData (confidence_expected/coverage_expected)
  ▼
[ParserAdapter]   → ParserData.raw_accounts (ResultadoParseo → CuentaRaw[])
  ▼
[KBAdapter]       → por cada CuentaRaw:
                      1. AccountAdapter.from_cuenta_raw → AccountBalance
                      2. BalanceInterpreter → classification_amount
                      3. AccountTypeResolver → account_tipo
                      4. HomologationPipeline._classify_account:
                           learning(GS) → [CMCC shadow] → [decision/ si flag] →
                           code → dict_exact → dict_fuzzy → [SemanticMatcher si flag] → regex
                      5. semantic_engine.interpret (reglas v2) → semantic_result
                      6. rule_processor.aplicar (reglas_especiales R1–R5) → ajuste final
                      → classified[] con standard_code/final_code/method/confidence
  ▼
[DecisionAdapter] → decision_engine: recoge evidencia del DocumentContext, resuelve conflictos,
                    genera Decision por cuenta, DecisionStatistics a nivel documento
                    → decisions[] + decision_stats
  ▼
[ValidationAdapter] → ValidationData (integridad/subtotal/ecuación)
  ▼
[ReviewAdapter]     → revisión humana (si aplica)
  ▼
[CoverageAdapter]   → cobertura
  ▼
[SelfQAAdapter]     → calidad/gates
  ▼
ctx.complete()
```

**Observación crítica sobre el estado actual:** la clasificación por-cuenta (`_classify_account`) es **first-match-wins secuencial** (o `decision/` con reglas 50/50 en conflictos). No hay ranking de candidatos ni evidencia multicapa combinada. Es exactamente el hueco que llena el Sprint 38.

### Flujo objetivo (con `classification_engine/`; integración en Sprint 39)

```
Parser → Contexto → Knowledge → DECISIÓN → Clasificación

[Parser]      CuentaRaw (código, nombre, tipo)
    │
    ▼
[Contexto]    DocumentContext (SIE+DIE+Parser ya poblados)
    │   DocumentProcessingContextAdapter:
    │     family, template, layout, column_layout, document_type,
    │     selected_parser, extractor_info (extractor_id/family_id/confidence),
    │     document_profile (family/recommended_extractor), prediction
    ▼
[Knowledge]   Capa Sprint 37:
    │   catalogo_maestro.json (61 cuentas) · account_synonyms.json (61/61)
    │   special_account_rules.py (19) · account_name_normalizer (canónico)
    │   (opcional) SemanticMatcher (concept_catalog) · ClasificadorCodigo
    ▼
[Decision]    classification_engine.DecisionEngine (Top-N):
    │   1. candidate.generate()   → candidatos por capa (catálogo exacto,
    │                               sinónimos exact/fuzzy, reglas, código,
    │                               contexto/familia/layout, perfil)
    │   2. score.score(candidates, weights) → score por capa + total ponderado
    │   3. decision.rank()        → ranking completo, SIEMPRE Top N
    │   4. explainer.explain()    → razones legibles por capa/peso/score
    │   5. metrics.compute()      → Top-1/Top-N/MRR/cobertura
    ▼
[Clasificación] TopNResult → (Sprint 39) el mejor candidato alimenta
                 standard_code/final_code, y el ranking completo + evidencia
                 alimenta decision_engine (documento) y la auditoría.
```

**Criterio de aceptación del Sprint 38:** el engine queda funcional, testeado y desacoplado. Devuelve `TopNResult` siempre, con explicación y métricas. Los 2446 tests existentes permanecen verdes. No hay integración al flujo (Sprint 39). Ningún archivo existente es modificado.

---

## Recomendación final (Opción A vs Opción B)

### Opción A — Crear un nuevo paquete `classification_engine/` completamente independiente
### Opción B — Evolucionar alguno de los motores existentes

**RECOMENDACIÓN: OPCIÓN A**, con la salvedad de que el nuevo paquete reutiliza `document_context`, `document_intelligence` y la capa Sprint 37 (no es "independiente de todo el sistema", sino independiente de los motores de decisión existentes).

**Justificación firme:**
1. **No existe un motor que haga Top-N por cuenta.** Crear uno nuevo no es duplicar un contrato existente; es llenar un vacío real.
2. **Ningún motor existente consume la capa de conocimiento que el brief exige** (`catalogo_maestro` + `account_synonyms` + `special_rules`). Evolucionar `decision_v2/` (la única candidata B viable) implicaría reescribir su capa de conocimiento completa, sus pesos, su salida (Top-N en vez de 1 código) y sacarlo de benchmarks a producción: eso es crear un motor nuevo de facto, con el lastre de un modelo GS con 61.6% de error y precisión 59%.
3. **Los motores existentes tienen pesos y umbrales hardcodeados**; el brief exige pesos parametrizados. Reutilizarlos ataría el nuevo motor a constantes rígidas o obligaría a refactorizar código en producción (rompe el requisito "100% aditivo").
4. **El riesgo de "4to motor" (§6) se mitiga con un contrato claro** (§7) y deprecando `decision/` y `decision_v2/`. El costo de la opción A es bajo (~600–800 LOC aditivas); el costo de la opción B es refactorizar código en producción con riesgo de romper 2446 tests.
5. **Mantenibilidad a 6 meses**: la opción A deja un solo motor de clasificación canónico que consume el catálogo canónico, con pesos gobernados y contrato Top-N único. La opción B deja un motor híbrido mezclando fuentes viejas y nuevas, imposible de calibración consistente.

### Versión mejorada del Sprint 38 (ajustes al diseño original del brief)

1. **`DocumentProcessingContext`**: NO crear uno nuevo. Reutilizar el que ya existe en `document_intelligence/context.py` y exponer un **adapter read-only** (`DocumentProcessingContextAdapter`) dentro de `classification_engine/decision.py` que lo lee desde `DocumentContext`. Mantiene el engine puro y testeable sin PDF.
2. **Módulo `metrics.py`**: el brief lo pide; se añade Top-1/Top-N/MRR@N/cobertura. En Sprint 39 se puede conectar a `decision_engine.DecisionStatisticsCollector` (estadísticas a nivel documento) sin duplicar.
3. **Pesos**: `score.py` acepta `WeightConfig` (dict por capa: catálogo, sinónimos, reglas, código, contexto/familia, layout, extractor, perfil). Default de referencia parametrizado, calibrable post-hoc, no constantes en el cuerpo.
4. **Deprecación**: marcar `decision/` y `decision_v2/` como deprecados (comentario en su `__init__` o docstring) — no eliminarlos ni modificarlos.
5. **Alcance de capas**: las capas obligatorias del engine son catálogo exacto, sinónimos (exact/fuzzy), reglas especiales, código, familia/layout (contexto), extractor_info y perfil documental. `SemanticMatcher` queda opcional vía flag para no acoplar el núcleo.

**Decisión tomada: OPCIÓN A. El Sprint 38 procede a implementar `classification_engine/` como se describe en §7, reutilizando contexto y conocimiento existentes y deprecando los motores duplicados.**

> Pendiente de aprobación del usuario antes de escribir cualquier código.
