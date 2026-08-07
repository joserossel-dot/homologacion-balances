# Módulo: Document Intelligence (DIE)

> **Ubicación**: `document_intelligence/` (~50 módulos, ~7.7k líneas)

## Propósito

Analizar documentos (PDF/Excel) **antes** de parsearlos y producir
recomendaciones sobre cómo procesarlos: tipo, familia, template, parser,
validaciones, confianza, cobertura y recomendación global. Es la "inteligencia
previa" del pipeline.

## Responsabilidad

1. Extraer preview de texto (fitz/pdfplumber/PyPDF2, openpyxl/pandas).
2. Clasificar tipo/familia/template de documento.
3. Recomendar parser y validaciones.
4. Predecir confianza y cobertura del conocimiento (KB).
5. Producir `IntelligenceReport` y `DocumentProcessingContext`.

## Componentes

| Capa | Módulos | Rol |
|---|---|---|
| **Motor central** | `__init__.py` (`DocumentIntelligence`), `context.py` (`analyze_document_preview`), `analyzer.py` (`FormatAnalyzer`) | Orquestan análisis y emiten reportes/contexto |
| **Clasificadores** | `document_classifier.py`, `family_classifier.py`, `template_classifier.py` | Tipo, familia y template del documento |
| **Selectores** | `parser_selector.py`, `validation_selector.py`, `confidence_predictor.py`, `recommendation_engine.py` | Recomendaciones |
| **Detectores** | `detector.py` (`BaseDetector`: Header, Layout, Column, CodePattern, NumericPattern, DocumentType) | Detección de características |
| **Firmas / repositorio** | `signature.py`, `repository.py` (`FormatRepository`) | Firma de formato y persistencia |
| **Extractores** | `extractors/` (base, factory, registry, specialized, profile_driven, universal) | Detectan extractor adecuado |
| **Knowledge Base** | `knowledge/` (fingerprint, clustering, matcher, repository, document_profile, statistics) | Base de conocimiento documental (DKB) |
| **Minería** | `mining/` (family_detector, similarity_matrix, clustering, representative_selector, coverage, reports) | Análisis de familias y representantes |
| **Trainer** | `trainer/` (trainer, profile, repository, validator) | Entrenamiento de perfiles |
| **Métricas / estadísticas** | `metrics.py`, `statistics.py` | Telemetría |

## Flujo del motor central (`DocumentIntelligence.analyze`, `:216-327`)

```
file_path
   ▼ _extract_preview (200 líneas)
   ▼ _estimate_pages / _estimate_ocr_probability
   ▼ classifier.classify(raw_lines) → document_type
   ▼ _build_quick_accounts (parseo rápido por tokens)
   ▼ _detect_code_format + _detect_column_layout (structure_engine)
   ▼ family_classifier.classify(...) → family
   ▼ template_classifier.predict(...) → template
   ▼ parser_selector.recommend(...) → parser
   ▼ validation_selector.recommend(...) → validation
   ▼ _estimate_kb_coverage(...) → kb_coverage
   ▼ confidence_predictor.predict(...) → confidence
   ▼ CoveragePrediction(...)
   ▼ DocumentProfile(...)
   ▼ recommendation_engine.evaluate(...) → recommendation
   ▼ IntelligenceReport(...)
```

## Entradas

- Ruta a archivo (PDF/XLS/XLSX/TXT/CSV).
- Para `analyze_document_preview`: PDF + opciones de preview (≤3 páginas).

## Salidas

- `IntelligenceReport` (profile, classification, family, template, parser,
  validation, confidence, coverage, recommendation).
- `DocumentProcessingContext` (consumido por `ParserPDF.parsear` y el
  pipeline V2).
- `FormatSignature` (del `FormatAnalyzer`).

## Dependencias

- Externas opcionales: `fitz` (PyMuPDF), `pdfplumber`, `PyPDF2`, `openpyxl`,
  `pandas`.
- Internas: `structure_engine` (detección de formato/layout), `models.py`
  (de negocio, parcial).
- Ciclos: `document_intelligence.extractors ↔ parser_universal` (resueltos
  con imports diferidos en `parser_universal.py:665-667, 853-855`).

## Feature flags

No tiene flags propios; se enruta vía `ENABLE_DYNAMIC_LAYOUT` (parser) y los
flags de `FeatureFlags` (`document_intelligence=True`) que no tienen
consumidores reales (ver `docs/architecture/feature_flags.md`).

## Objetos clave

`DocumentIntelligence`, `IntelligenceReport`, `DocumentProfile`,
`DocumentProcessingContext`, `FormatAnalyzer`, `FormatSignature`,
`FormatRepository`, `DocumentFingerprint`, `DocumentKnowledgeBase`,
`SpecializedExtractorFactory`, `ExtractorFactory`, `Cluster`, `Matcher`,
`DocumentFamily`, `Representative`, `SimilarityMatrix`.

## Relaciones

- V1: `ParserPDF.parsear` → `analyze_document_preview` + `ExtractorFactory`.
- V2: `DIEAdapter` → `set_prediction` + `die_report`.
- Standalone: `DocumentIntelligence().analyze(path)`.

## Riesgos

1. **Enums duplicados**: `DocumentType`/`Family` en
   `document_intelligence/models.py` ≠ `models.py` (incompatibles).
2. Heurísticas aproximadas: cobertura KB por fórmula lineal por formato, no
   medición real.
3. Doble/triple stack de librerías PDF con imports opcionales y fallos
   silenciosos.
4. `structure_engine` importado dinámicamente dentro de métodos.
5. Paquete muy grande con capas de Sprint superpuestas sin limpieza.

## Mejoras futuras

- Unificar enums con `models.py`.
- Medir cobertura KB real.
- Consolidar stack de extracción de texto.
- Documentar sub-sistemas (KB, minería, trainer, extractores) por separado
  (vista previa en `docs/reference/DocumentIntelligence.md`).
