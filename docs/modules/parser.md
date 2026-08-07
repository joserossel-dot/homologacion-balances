# Módulo: Parser

> **Ubicación**: `parsers/`, `parser_universal.py`, `clasificador_codigo_cuenta.py`

## Propósito

Transformar un balance en PDF o Excel en cuentas estructuradas
(`CuentaRaw`). Convierte texto/OCR en datos accionables para la
clasificación.

## Responsabilidad

- Extraer texto (nativo o OCR) del documento.
- Detectar formato de código y separador de miles.
- Determinar orden de columnas (layout).
- Parsear cada línea → `CuentaRaw`.
- Resolver tipo de cuenta (familia) vía `AccountTypeResolver`.
- (Opcional) Enriquecer con metadata de análisis documental.

## Stack actual (dos generaciones coexistiendo)

### 1. `parser_universal.py` — `ParserPDF` (legado, usado por V1 y V2)

Ver `docs/reference/ParserPDF.md`. Es el parser que **realmente** corre en el
pipeline (V1 `homologation_pipeline.py:36,380`; V2
`adapters/parser_adapter.py`).

### 2. `parsers/` — ParserCore2 (nueva generación, integrada parcialmente)

| Archivo | Clase/Función | Líneas | Rol |
|---|---|---|---|
| `pdf_parser.py` | `ParserCore2` | 430 | Parser de 2ª generación (nuevo core) |
| `analyzer.py` | `DocumentAnalyzer` / `DocumentAnalysis` | 662 | Análisis estructural pre-parseo |
| `integration.py` | `parse_with_analysis` / `EnhancedParseResult` | 261 | Puente DocumentAnalyzer + ParserPDF |
| `config.py` | `ParserConfig` | 141 | Config jerárquica (default → toml → env) |
| `layout_detector.py` | `LayoutDetector` | 139 | Detección de layout/columnas |
| `orientation_detector.py` | — | 120 | Detección/corrección de rotación |
| `text_normalizer.py` | — | 132 | Normalización de texto |
| `ocr_engine.py` | — | 107 | Motor OCR |
| `line_parser.py` | — | 101 | Parser de línea |
| `factory.py` | `ParserFactory` | 38 | Fábrica de parsers |
| `format_detector.py` | — | 53 | Detección de formato |
| `hygiene.py` | — | 22 | Limpieza |
| `excel_parser.py` | — | 19 | Parser Excel |
| `account_type_resolver.py` | `AccountTypeResolver` | 240 | Ver `docs/reference/AccountTypeResolver.md` |

### Integración (el punto clave)

`parsers/integration.py` (ver flujo en código `:179-214`):

```
Documento
   │ ▼ DocumentAnalyzer.analyze(path) → DocumentAnalysis
   │ ▼ _analyzer.to_extraction_context(analysis) → ExtractionContext
   │ ▼ ParserPDF.parsear(path, context) → ResultadoParseo
   │ ▼ _merge_warnings(resultado, analysis)  (rotación 180°, OCR, layout bajo, sin códigos)
   ▼ EnhancedParseResult(resultado, analysis)
```

`EnhancedParseResult` (`:38-176`) envuelve el `ResultadoParseo` sin modificarlo
y expone passthrough properties (`archivo`, `cuentas`, `advertencias`, ...) +
analysis properties (`tipo_documento`, `necesita_ocr`, `orientacion_detectada`,
`confianza_global`, `formato_codigo_detectado`, `layout_confianza`, ...) +
`to_dict()` / `to_dict_flat()`.

## Flujo de parseo efectivo (V1)

```
ParserPDF.parsear(path)
   ▼ validar_archivo (firma %PDF-, tamaño>0)
   ▼ _analizar_documento → analyze_document_preview (≤3 páginas)
   ▼ _extraer_lineas → texto nativo (pdfplumber) o _ocr_documento (pdftoppm 250dpi + tesseract)
   ▼ normalizar_codigo_ocr
   ▼ detectar_formato_codigo (guion/punto/compacto/sin_codigo)
   ▼ detectar_separador_miles
   ▼ column_order (4 niveles de prioridad: layout_hint → perfil familia → LayoutDetector → ULTIMAS_COLS)
   ▼ parsear_linea (confianza 0.75 OCR / 1.0 texto)
   ▼ AccountTypeResolver (si flag o contexto confiable)
   ▼ _anotar_extractor → resultado.extractor_info
   ▼ ResultadoParseo (nunca lanza)
```

## Entradas

- Ruta a archivo (PDF, XLS, XLSX, TXT/CSV).
- `ExtractionContext` opcional (hints de `DocumentAnalyzer`/DIE):
  `rotation_hint, rotation_confidence, needs_ocr, layout_hint,
  layout_confidence, format_hint, confidence, analysis_source`.

## Salidas

- `ResultadoParseo`: `archivo, formato_codigo, separador_miles, requirio_ocr,
  rotacion_aplicada, cuentas, advertencias, document_context, extractor_info`.
- `list[CuentaRaw]`: `linea, codigo, nombre, monto, origen_columna, es_total,
  confianza_extraccion, tipo_cuenta`.
- `parsear_excel` devuelve `list[CuentaRaw]` directo (los callers lo envuelven).

## Dependencias

- Externas: `pandas`, `pdfplumber`, `PIL`, (OCR: `tesseract`, `pdftoppm`),
  `fitz` (en DIE).
- Internas: `parsers/account_type_resolver`, `parsers/layout_detector`,
  `document_intelligence.extractors.*` (diferidos), `structure_engine`.
- Ciclos conocidos: `parser_universal ↔ document_intelligence.extractors`
  (`parser_universal.py:665-667, 853-855` vs `extractors/universal.py:28`) y
  `parser_universal ↔ parsers` (`:744, 794` vs `parsers/*.py`) — resueltos
  con imports diferidos.

## Feature flags

`ENABLE_DYNAMIC_LAYOUT`, `ENABLE_ACCOUNT_TYPE_RESOLVER`,
`ROTATION_CORRECTION_THRESHOLD=0.7`, `LAYOUT_CONFIDENCE_THRESHOLD=0.8`,
`ACCOUNT_TYPE_CONFIDENCE_THRESHOLD=0.7` (constantes de `parser_universal.py`).
`ParserConfig` (env `PARSER_*`) para la nueva generación. Ver
`docs/architecture/feature_flags.md`.

## Objetos clave

`CuentaRaw`, `ResultadoParseo`, `FormatoCodigo`, `ExtractionContext`,
`OrigenColumna`, `EnhancedParseResult`, `DocumentAnalysis`, `ParserCore2`,
`AccountTypeResolver`, `AccountTypeResult`.

## Relaciones

- V1: `HomologationPipeline` → `ParserPDF.parsear` / `parsear_excel`.
- V2: `ParserAdapter` → `ParserPDF.parsear` (con contexto de DIE).
- DIE: `analyze_document_preview` se llama dentro de `ParserPDF.parsear`.
- `parsers/integration.parse_with_analysis` une DocumentAnalyzer + ParserPDF.

## Riesgos

1. **Dos stacks de parser** sin consolidar (V1 usa `ParserPDF`; `ParserCore2`
   y `parse_with_analysis` son nuevos pero no el camino crítico del pipeline).
2. Rutas hardcodeadas de binarios OCR (`/usr/local/bin/tesseract`,
   `/usr/local/bin/pdftoppm`, `TESSDATA_DIR`).
3. `except Exception` silencioso extendido (fallos → `logger.debug`).
4. `parsear_excel` heurístico (nombre = texto más largo, monto = último
   número).
5. Dos contextos paralelos: `ExtractionContext` vs
   `DocumentProcessingContext` — mapeo manual.
6. `_reverse_line` solo invierte texto, no coordenadas (contraste con
   `orientation_detector`).
7. **Posible bug potencial**: `parsear_linea` con monto 0 puede asignar un
   monto 0 con origen ACTIVO por fallback → cuenta ignorada por
   `movement_only` o con signo equivocado. (Requiere verificación; el test
   `test_zero_monto_*` en `tests/test_parser_universal.py` cubre casos
   relacionados.)

## Mejoras futuras

- Consolidar `ParserPDF` y `ParserCore2` en un único parser.
- Parametrizar binarios OCR (env/`shutil.which`).
- Usar `parse_with_analysis` como flujo estándar (trae metadata DIE gratis).
- Soportar layout dinámico por defecto tras validar.
