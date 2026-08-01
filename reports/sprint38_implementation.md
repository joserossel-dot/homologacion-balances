# Implementación — Sprint 38 (classification_engine)

> Documento de cierre de implementación. Complementa la
> `reports/sprint38_architecture_review.md` (auditoría aprobada) con el
> detalle de lo construido, el algoritmo de scoring, la configuración de
> pesos, el flujo y el inventario de archivos.

---

## 1. Resumen

Se construyó `classification_engine/`, un paquete **100% aditivo** que
clasifica cuentas contables produciendo, para cada cuenta, un **ranking
Top-N de candidatos** con score, confianza, explicación completa y
trazabilidad de todas las evidencias.

**Requisitos cumplidos (de la revisión aprobada):**

| # | Requisito | Estado |
|---|---|---|
| 1 | `classification_engine/` único motor multi-capa por cuenta | ✅ |
| 2 | No se modificaron Parser Universal, ParserPDF, HomologationPipeline, RuleProcessor, Document Intelligence, Dataset Mining, Trainer, Knowledge Base, `decision/`, `decision_v2/`, `decision_engine/` | ✅ |
| 3 | `decision/` + `decision_v2/` conceptualmente legacy | ✅ (sin tocar) |
| 4 | Reuso limitado: `DocumentProcessingContext` (read-only), `catalogo_maestro.json`, `knowledge_base/account_synonyms.json`, `special_account_rules.py`, `account_name_normalizer.py` | ✅ |
| 5 | Todos los pesos vía `WeightConfig`, sin constantes hardcodeadas en el motor | ✅ |
| 6 | Motor desacoplado, testeable sin PDFs ni Document Intelligence | ✅ (54 tests nuevos, dict plano como contexto) |
| 7 | Siempre Top N, score, confianza, explicación completa y trazabilidad | ✅ |
| 8 | Toda decisión reconstruible, sin reglas ocultas | ✅ |
| 9 | Cobertura unit+integración del motor y suite 2446 verde | ✅ |
| 10 | Deliverables finales (este documento + diagrama + algoritmos + cobertura) | ✅ |

---

## 2. Arquitectura resultante

```
                    ┌─────────────────────────────────────────────┐
                    │              classification_engine/         │
                    │                                             │
  account_name ───▶ │  CandidateGenerator  ──▶  Scorer  ──▶  TopNResult │
  account_code ──▶  │     (8 capas)              (WeightConfig)  │
  context ────────▶ │        │                        │           │
                    │        ▼                        ▼           │
                    │  EvidenceSource[]        RankedCandidate[]  │
                    │                                 │           │
                    │                                 ▼           │
                    │                            Explainer         │
                    │                        (reasons + breakdown) │
                    └─────────────────────────────────────────────┘
```

**Capas del generador de candidatos:**

| Capa | Rol | Propone código | Fuente |
|---|---|---|---|
| `code` | Clasificación por código original | ✅ | `clasificador_codigo_cuenta.ClasificadorCodigo` |
| `catalog_exact` | Match exacto de nombre normalizado | ✅ | `catalogo_maestro.json` |
| `synonyms_exact` | Match exacto contra sinónimos | ✅ | `account_synonyms.json` |
| `synonyms_fuzzy` | Match difuso (tokens + stopwords) | ✅ | `account_synonyms.json` |
| `special_rules` | Reglas especiales | ✅ | `special_account_rules.py` |
| `context` | Refuerzo por tipo de estado del documento | ❌ | `DocumentProcessingContextAdapter` |
| `extractor` | Refuerzo por extractor seleccionado | ❌ | `DocumentProcessingContextAdapter` |
| `profile` | Refuerzo por perfil documental | ❌ | `DocumentProcessingContextAdapter` |

Las capas de refuerzo **nunca crean candidatos nuevos**: solo agregan
evidencia a candidatos ya propuestos. Esto evita que un documento
"balance" fabrique códigos que no están sustentados por nombre o código.

---

## 3. Algoritmo de scoring (detallado)

Dado un candidato `C` con evidencias `E(C)`:

```
1. Por cada capa l: score_capa(C, l) = max(score de evidencias de l en C)
2. Capas usadas U = { l | score_capa(C,l) > 0  y  peso(l) > 0 }
3. Si U vacío → score_total(C) = 0
4. Si no:
      numerador   = Σ_{l∈U} peso(l) · score_capa(C,l)
      denominador = Σ_{l∈U} peso(l)
      score_bruto = numerador / denominador          (promedio ponderado)
5. Bonus de consenso:
      si |U| >= min_consensus_layers (default 2):
          score_total = min(score_bruto · consensus_bonus (default 1.10), 1.0)
6. score_total = round(score_total, 4)
7. Etiqueta de confianza: mayor (min_score, label) con score_total >= min_score
8. Ranking: orden descendente por score; empates por código+nombre (determinista)
```

**Ejemplo** — `Caja y Bancos` con código `1-01-01-02-01`:

| Capa | score | peso | contribución |
|---|---|---|---|
| code | 0.97 | 0.90 | 0.873 |
| catalog_exact | 1.00 | 1.00 | 1.000 |
| synonyms_exact | 0.95 | 0.95 | 0.902 |
| synonyms_fuzzy | 0.88 | 0.70 | 0.616 |

score_bruto = (0.873+1.000+0.902+0.616)/(0.90+1.00+0.95+0.70) = 3.391/3.55 ≈ 0.9553.
Con 4 capas ≥ 2 → bonus 1.10 → 1.0508 → min(1.0508, 1.0) = **1.000** → `EXACT`.

**Principios:**
- El umbral de confianza **etiqueta** pero **nunca descarta candidatos**: el
  ranking siempre devuelve Top-N completo.
- Score se normaliza por la suma de pesos de las capas que aportan
  evidencia → comparable entre candidatos con distinto número de capas.
- Determinista: sin aleatoriedad, empates resueltos canónicamente.

---

## 4. WeightConfig (documentación de pesos)

`WeightConfig` es el único lugar donde viven los pesos y umbrales.
Serializable a JSON y sobrescribible parcialmente vía `from_dict`/`from_json`.

| Campo | Default | Descripción |
|---|---|---|
| `weights.code` | 0.90 | Clasificación por código |
| `weights.catalog_exact` | 1.00 | Match exacto catálogo (máxima prioridad) |
| `weights.synonyms_exact` | 0.95 | Match exacto sinónimos |
| `weights.synonyms_fuzzy` | 0.70 | Match difuso sinónimos |
| `weights.special_rules` | 0.90 | Reglas especiales |
| `weights.context` | 0.55 | Refuerzo contextual |
| `weights.extractor` | 0.40 | Refuerzo por extractor |
| `weights.profile` | 0.40 | Refuerzo por perfil |
| `fuzzy_threshold` | 0.88 | Score de match difuso aceptado |
| `consensus_bonus` | 1.10 | Factor multiplicativo por consenso |
| `min_consensus_layers` | 2 | Capas mínimas para consenso |
| `confidence_thresholds` | EXACT≥0.95, VERY_HIGH≥0.85, HIGH≥0.70, MEDIUM≥0.50, LOW≥0.30, UNKNOWN≥0.00 | Etiquetas |
| `top_n` | 5 | Tamaño del ranking |

---

## 5. Trazabilidad y reconstrucción

Cada `EvidenceSource` registra: `layer`, `code`, `score`, `weight`,
`source` (archivo de conocimiento), `detail` (por qué) y `matched_value`
(el valor que produjo la coincidencia). Con esto:

- El `TopNResult.to_dict()` contiene toda la evidencia de todos los
  candidatos → auditable y reconstruible sin re-ejecutar el motor.
- `ClassificationExplanation` expone `reasons` legibles, el
  `confidence_breakdown` por capa y `candidate_explanations`.
- Si no hay candidatos reales, el motor devuelve un candidato `UNKNOWN`
  (code=None) → el resultado nunca está vacío y el fallo es visible.

---

## 6. Inventario de archivos

### Creados
| Archivo | Contenido |
|---|---|
| `classification_engine/__init__.py` | API pública + versión |
| `classification_engine/decision.py` | Modelos + `DocumentProcessingContextAdapter` |
| `classification_engine/score.py` | `WeightConfig` + `Scorer` |
| `classification_engine/candidate.py` | `KnowledgeLoader` + `CandidateGenerator` |
| `classification_engine/explainer.py` | `Explainer` |
| `classification_engine/metrics.py` | `MetricsResult` + `compute_metrics` |
| `classification_engine/engine.py` | `DecisionEngine` (orquestador) |
| `tests/test_classification_engine.py` | 54 tests (unit + integración) |
| `reports/sprint38_implementation.md` | Este documento |

### Modificados
| Archivo | Cambio |
|---|---|
| *(ninguno de los módulos protegidos)* | — |

### No modificados (por mandato)
Parser Universal, ParserPDF, HomologationPipeline, RuleProcessor,
Document Intelligence, Dataset Mining, Trainer, Knowledge Base,
`decision/`, `decision_v2/`, `decision_engine/`, `diccionario.json`,
`gold_standard.db`.

---

## 7. Cobertura

`tests/test_classification_engine.py` — 54 tests:
- `KnowledgeLoader`: carga, degradación por archivo faltante/JSON inválido.
- Modelos: `Candidate`, `RankedCandidate`, `TopNResult`, `EvidenceSource`.
- `DocumentProcessingContextAdapter`: dict plano, `DocumentContext` real,
  nunca escribe en el contexto.
- `WeightConfig`: defaults, validación, from_dict/from_json, límites.
- `Scorer`: ponderación, consenso, orden, etiquetas de confianza.
- `CandidateGenerator`: las 8 capas, límites, desactivación, contexto.
- `Explainer`: reasons, breakdown, UNKNOWN.
- `DecisionEngine` end-to-end: exacto, por código, UNKNOWN, top_n, pesos
  custom, serialización completa.
- `Metrics`: top-1/top-5/MRR/coverage/distribución.

---

## 8. Siguiente paso (Sprint 39)

Integrar `DecisionEngine` en el flujo de clasificación V2:
- Sustituir la decisión por-cuenta en `adapters/kb_adapter.py`
  (hoy `HomologationPipeline._classify_account`) por el nuevo motor.
- Escribir el ranking Top-N en `DocumentContext` para que
  `decision_engine/` a nivel documento lo consuma.
- Calibrar `WeightConfig` contra `gold_standard` (con las advertencias
  documentadas de calidad del GS) y regenerar reportes de precisión.
