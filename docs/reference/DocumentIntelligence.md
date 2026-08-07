# DocumentIntelligence

> Paquete: `document_intelligence/` (~50 módulos, ~7.7k líneas)
> Clase principal: `DocumentIntelligence` (`document_intelligence/__init__.py:194-546`)
> Modelos: `document_intelligence/models.py`
> Entry point de análisis previo: `analyze_document_preview`
> (`document_intelligence/context.py`)

## Propósito

Motor de inteligencia documental (DIE) que analiza un PDF/Excel **antes** de
ejecutar el parser y produce un `IntelligenceReport` con predicciones sobre
tipo de documento, familia, template, parser recomendado, validaciones,
confianza, cobertura y recomendación de procesamiento. Está integrado en el
parseo V1 (`ParserPDF.parsear`) y es una etapa propia en el pipeline V2
(`DIEAdapter`).

## Responsabilidad

1. Extraer un preview del texto (PDF vía fitz/pdfplumber/PyPDF2, Excel vía
   openpyxl/pandas, txt/csv).
2. Estimar páginas, probabilidad de OCR, secciones y subtotales.
3. Clasificar tipo de documento (`DocumentClassifier`), familia
   (`FamilyClassifier`), template (`TemplateClassifier`).
4. Recomendar parser (`ParserSelector`), validaciones (`ValidationSelector`),
   confianza (`ConfidencePredictor`), cobertura KB (`_estimate_kb_coverage`).
5. Armar `DocumentProfile` y evaluar la recomendación global
   (`RecommendationEngine.evaluate`).
6. Devolver `IntelligenceReport`.

## Clase principal

### `DocumentIntelligence.__init__(template_repo_path="structure_repository.json", kb_path="knowledge_base/cmcc_knowledge.json")` (`:202-214`)

Compone 6 sub-motores: `DocumentClassifier`, `FamilyClassifier`,
`TemplateClassifier`, `ParserSelector`, `ValidationSelector`,
`ConfidencePredictor`, `RecommendationEngine`.

### `analyze(file_path) -> IntelligenceReport` (`:216-327`)

```
file_path
 │ ▼ _extract_preview (primeras 200 líneas no vacías)
 │ ▼ _estimate_pages / _estimate_ocr_probability
 │ ▼ classifier.classify(raw_lines) → document_type
 │ ▼ _build_quick_accounts (parseo "rápido" por tokens)
 │ ▼ _detect_code_format + _detect_column_layout (vía StructureDetector)
 │ ▼ family_classifier.classify(...)
 │ ▼ template_classifier.predict(...)
 │ ▼ parser_selector.recommend(...)
 │ ▼ validation_selector.recommend(...)
 │ ▼ _estimate_kb_coverage(code_format, accounts)
 │ ▼ confidence_predictor.predict(...)
 │ ▼ coverage = CoveragePrediction(...)
 │ ▼ profile = DocumentProfile(...)
 │ ▼ recommendation_engine.evaluate(profile, classification, family,
 │       template, parser_rec, validation, confidence, coverage)
 │ ▼ IntelligenceReport(profile, classification, family, template,
 │       parser, validation, confidence, coverage, recommendation)
```

### Métodos privados de estimación

- `_extract_preview` (`:332`): extrae primeras 200 líneas no vacías; fallback
  `read_text` directo si la extracción por librería falla. Nunca lanza.
- `_estimate_pages` (`:406`): PDF → fitz/PyPDF2; si no, `len(lines)//30 + 1`.
- `_estimate_ocr_probability` (`:431`): chars/página → 0.95/0.7/0.3/0.05.
- `_estimate_sections` (`:448`): cuenta keywords de sección en primeras 80
  líneas (activo, pasivo, patrimonio, resultado, ingreso, costo, gasto,
  capital); min 1.
- `_estimate_subtotals` (`:460`): regex `^(total|subtotal|suma)`.
- `_build_quick_accounts` (`:469`): primer token como código si parece número
  (isdigit o contiene `.`/`-`), resto como nombre.
- `_detect_code_format`/`_detect_column_layout` (`:491-497`): delegan en
  `structure_engine/structure_detector.py`.
- `_estimate_kb_coverage` (`:509`): según formato (PUNTO → hasta 0.95, COMPACTO
  → 0.85, GUION → 0.80, else 0.3); 0.1 si KB vacío.
- `_get_kb_size` (`:522`): cuenta `codes` de `kb_path` JSON.
- `_estimate_profile_complexity` (`:534`): OCR>0.7 o pages>15 o cuentas>100 →
  ALTA; pages>8 o cuentas>50 → MEDIA; else BAJA.
- `analyze_batch(file_paths) -> list[IntelligenceReport]` (`:329`).

## Modelos (`document_intelligence/models.py`)

Enums: `DocumentType`, `Family`, `Complexity` (ALTA/MEDIA/BAJA),
`Recommendation`, `ParserName`.
Dataclasses: `DocumentProfile` (`:50`), `DocumentClassification` (`:90`),
`FamilyClassification` (`:106`), `TemplatePrediction` (`:120`),
`ParserRecommendation` (`:143`), `ValidationRecommendation` (`:164`),
`ConfidencePrediction` (`:185`, prop `confidence_pct`),
`CoveragePrediction` (`:212`, prop `coverage_pct`),
`ProcessingRecommendation` (`:234`), `IntelligenceReport` (`:257`, prop
`summary()`).

> ⚠️ **Enums duplicados e incompatibles**: `document_intelligence/models.py`
> define sus propios `DocumentType`/`Family`, distintos de los de
> `models.py` (de negocio). No son intercambiables (ver
> `docs/architecture/dependency_graph.md`).

## Detectores (`document_intelligence/detector.py`)

Cadena `BaseDetector` (ABC) con 6 implementaciones:
`HeaderDetector`, `LayoutDetector` (usa `_looks_like_number`,
`_is_header_line`), `ColumnDetector`, `CodePatternDetector`,
`NumericPatternDetector`, `DocumentTypeDetector`.

## FormatAnalyzer (`analyzer.py:14-...`)

`analyze(lines)` / `analyze_text(text) -> FormatSignature`; computa
confianza global (`_compute_global_confidence`) e infiere familia
(`_infer_family`). Produce `FormatSignature` (definido en `signature.py`).

## Sub-sistemas asociados

- **Extractores** (`document_intelligence/extractors/`): `SpecializedExtractor`,
  `UniversalExtractor`, `SpecializedExtractorFactory`, `ExtractorFactory`,
  `ExtractorType`, registro vía `register_extractor*`. Los extractores
  especializados NO realizan la extracción real; la detectan y la delegan al
  parser universal (ver `docs/reference/ParserPDF.md`, `_anotar_extractor`).
- **Knowledge Base** (`knowledge/`): fingerprints, clustering, matcher,
  repository, statistics — minado de documentos (`mining/`) y trainer.
- **Trainer** (`trainer/`): perfilado y validación de repositorio.
- `repository.py`: `FormatRepository` (persistencia de firmas).
- `statistics.py`: `DocumentIntelligenceStats`.
- `factory.py`: `ExtractorFactory`, `ExtractorType`.

## Cómo se integra

- **V1** (`ParserPDF.parsear`): `analyze_document_preview` (≤3 páginas) →
  `ExtractorFactory.decide_parser`; el resultado se guarda en
  `ResultadoParseo.document_context` y `extractor_info`
  (`parser_universal.py:608-626, 866-880`).
- **V2** (`adapters/die_adapter.py`): `set_prediction` (dce_prediction) +
  custom `die_report`.
- **Standalone**: `DocumentIntelligence().analyze(path)` → `report.summary()`.

## Quién lo utiliza

`ParserPDF`, `DIEAdapter`, `scripts/` de DIE y minería, `app_validacion.py`.

## Riesgos técnicos

- **Heurísticas aproximadas**: `_build_quick_accounts`, `_estimate_*`,
  `_estimate_kb_coverage` son estimaciones; la cobertura KB es una función
  lineal por formato, no medición real.
- **Doble stack de librerías PDF** (fitz/pdfplumber/PyPDF2) con import
  opcional — fallos silenciosos.
- **`structure_engine` importado dinámicamente** dentro de métodos
  (`_detect_code_format`) — potencial ciclo/ausencia.
- **Enums duplicados** (`DocumentType`/`Family`) entre
  `document_intelligence/models.py` y `models.py`.
- Paquete muy grande (~7.7k líneas, ~50 módulos) con capas Sprint
  superpuestas (30-34) sin limpieza.

## Posibles mejoras futuras

- Unificar enums con `models.py`.
- Medir cobertura KB real en vez de estimación lineal.
- Consolidar el doble stack de librerías de extracción de texto.
- Documentar cada sub-sistema (extractores, KB, minería, trainer) por
  separado (vista prevista en `docs/modules/document_intelligence.md`).
