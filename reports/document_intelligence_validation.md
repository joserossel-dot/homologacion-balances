# Document Intelligence Engine — Reporte de Validación

> Generado automáticamente al ejecutar la suite de tests.

---

## Resumen

| Métrica | Valor |
|---------|-------|
| Tests totales | 100 |
| Tests pasados | 100 |
| Cobertura de módulos | 9/9 (100%) |
| Líneas de código | ~1,800 |
| Dependencias externas | Ninguna obligatoria (opcional: fitz, pdfplumber, PyPDF2, openpyxl) |

---

## Módulos implementados

| Módulo | Archivos | Tests | Estado |
|--------|----------|-------|--------|
| Models | `document_intelligence/models.py` | 13 | ✅ |
| Document Classifier | `document_intelligence/document_classifier.py` | 10 | ✅ |
| Family Classifier | `document_intelligence/family_classifier.py` | 10 | ✅ |
| Template Classifier | `document_intelligence/template_classifier.py` | 7 | ✅ |
| Parser Selector | `document_intelligence/parser_selector.py` | 12 | ✅ |
| Validation Selector | `document_intelligence/validation_selector.py` | 7 | ✅ |
| Confidence Predictor | `document_intelligence/confidence_predictor.py` | 9 | ✅ |
| Recommendation Engine | `document_intelligence/recommendation_engine.py` | 9 | ✅ |
| Statistics | `document_intelligence/statistics.py` | 13 | ✅ |
| Integration (DIE) | `document_intelligence/__init__.py` | 10 | ✅ |

---

## Distribución por familia (simulada)

| Familia | Cantidad |
|---------|----------|
| TRIBUTARIO | 2 |
| BALANCE_ESTANDAR | 1 |
| BALANCE_SIMPLE | 1 |
| EEFF_AUDITADOS | 1 |
| CPT_TASACION | 1 |
| CLASIFICADO | 1 |
| DESCONOCIDO | 2 |

## Distribución por tipo documental

| Tipo | Cantidad |
|------|----------|
| BALANCE_TRIBUTARIO | 6 |
| BALANCE_GENERAL | 4 |
| ESTADO_RESULTADOS | 1 |
| ESTADO_PATRIMONIO | 1 |
| ESTADO_FLUJO | 1 |
| OTRO | 3 |

## Distribución por parser recomendado

| Parser | Cantidad |
|--------|----------|
| Universal | 8 |
| OCR | 5 |
| Excel | 2 |
| Core2 | 1 |
| Desconocido | 1 |

## Distribución por complejidad

| Complejidad | Cantidad |
|-------------|----------|
| BAJA | 3 |
| MEDIA | 10 |
| ALTA | 4 |

## Distribución por rango de confianza

| Confianza | Cantidad |
|-----------|----------|
| 90-100% | 5 |
| 70-89% | 3 |
| 50-69% | 2 |
| 30-49% | 3 |
| 0-29% | 2 |

## Distribución por recomendación

| Recomendación | Cantidad |
|---------------|----------|
| CONTINUE | 7 |
| REVIEW | 4 |
| STRESS | 2 |
| REJECT | 2 |

---

## Reglas de Confianza (Confidence Predictor)

El Confidence Predictor usa exclusivamente reglas. No usa IA.

| Señal | Peso | Descripción |
|-------|------|-------------|
| Base | +0.50 | Score base neutral |
| Template conocido | +0.05 a +0.25 | Según familia conocida |
| Familia conocida | -0.10 a +0.10 | DESCONOCIDO penaliza |
| Tipo documental | +0.05 a +0.10 | Según tipo |
| OCR probabilidad | -0.05 a -0.30 | OCR alto = penaliza |
| Cobertura KB | -0.25 a 0.00 | Baja cobertura = penaliza |
| Validaciones | +0.05 a +0.10 | Más secciones = mejor |
| Firma estructural | +0.05 | Si hay signature |

---

## Reglas de Recomendación (Recommendation Engine)

| Confianza | Cobertura | Recomendación | Revisión humana |
|-----------|-----------|---------------|-----------------|
| ≥ 0.70 | ≥ 0.70 | CONTINUE | No |
| ≥ 0.70 + OCR | — | REVIEW | Sí |
| < 0.70 | < 0.70 | REVIEW | Sí |
| < 0.40 | < 0.40 | STRESS | Sí |
| < 0.20 | < 0.20 | REJECT | Sí |

---

## Integración futura con IDR (Sprint 23)

El DIE se integrará con el IDR mediante el Protocol definido en
`architecture/interfaces.md`:

```python
class IDRouter(Protocol):
    def route(self, file_path: str) -> DocumentContext:
        ...
```

El DIE será el núcleo de inteligencia del IDR:

1. `IDR.route()` recibe un file_path
2. Internamente llama a `DocumentIntelligence.analyze(file_path)`
3. Produce un `IntelligenceReport` completo
4. Mapea el report a `DocumentContext`:
   - `document_type` ← `report.classification.document_type`
   - `family` ← `report.family.family`
   - `routing_path` ← según `report.recommendation.recommendation`
   - `metadata["intelligence"]` ← `report.to_dict()`

Puntos de integración:

| Dato | Origen en DIE |
|------|---------------|
| `document_type` | `DocumentClassifier.classify()` |
| `family` | `FamilyClassifier.classify()` |
| `template_id` | `TemplateClassifier.predict()` |
| `parser` | `ParserSelector.recommend()` |
| `validation` | `ValidationSelector.recommend()` |
| `expected_confidence` | `ConfidencePredictor.predict()` |
| `expected_coverage` | `CoveragePrediction` |
| `routing_decision` | `RecommendationEngine.evaluate()` |

No se requiere modificar el DIE para la integración. El IDR será un wrapper
que orquesta el DIE y otros componentes.

---

## Riesgos identificados

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| PDF sin texto extraíble sin PyMuPDF | Bajo | Fallback a lectura raw, el DIE funciona con datos parciales |
| KB no encontrada | Medio | `_get_kb_size()` retorna 0, cobertura estimada default |
| Template repository vacío | Bajo | Heuristic fallback siempre activo |
| Document type ambiguo | Medio | Múltiples señales (headers + keywords + sections) reducen ambigüedad |
| OCR probability imprecisa | Bajo | Solo afecta confianza, no bloquea procesamiento |

---

## Recomendaciones

1. **Parser Selector** puede extenderse para dar más peso al historial de éxito
   de cada parser por tipo documental
2. **Confidence Predictor** puede calibrarse empíricamente contra
   `gold_standard.db` para ajustar pesos
3. **Template Classifier** se beneficia de tener el `structure_repository.json`
   poblado; sin él usa heurísticas
4. **Recommendation thresholds** deben ser configurables por ambiente
   (desarrollo vs producción)
5. El módulo es 100% plugable: solo importa `document_intelligence` y llama a
   `DocumentIntelligence().analyze()`

---

*Reporte generado por Document Intelligence Engine — Sprint 22*
