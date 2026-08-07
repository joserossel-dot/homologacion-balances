# ParserPDF

> Archivo: `parser_universal.py` (1007 líneas) — clase `ParserPDF` (`:593`)
> También incluye `parsear_excel`, `ClasificadorCodigo` (en
> `clasificador_codigo_cuenta.py`), y los modelos `CuentaRaw`, `ResultadoParseo`.

## Propósito

Convierte un balance tributario en PDF (nativo o escaneado) en una lista de
cuentas (`list[CuentaRaw]`). Complementa con `parsear_excel` para archivos
Excel. Es la **primera etapa de extracción** del pipeline.

## Responsabilidad

- Validar el archivo (firma `%PDF-`, tamaño > 0).
- Extraer texto nativo con `pdfplumber`; si no hay texto → OCR con
  `pdftoppm` + `tesseract` (con detección de rotación).
- Detectar formato de código (guion/punto/compacto/sin_codigo) y separador
  de miles.
- Determinar el orden de columnas (4 niveles de prioridad).
- Parsear cada línea en `CuentaRaw` (código, nombre, monto, origen_columna,
  es_total, confianza_extraccion).
- Anotar el extractor seleccionado (`extractor_info`).

## Clase `ParserPDF`

Stateless (sin atributos de instancia). Método principal:

### `parsear(path, context: ExtractionContext | None = None) -> ResultadoParseo` (`:595-834`)

```
path
 │ ▼ 1. validar_archivo (fallo → ResultadoParseo con advertencia)
 │ ▼ 2. _analizar_documento → analyze_document_preview (nunca lanza)
 │ ▼ 3. _extraer_lineas(path, context) → (lineas, requirio_ocr, rotacion)
 │ ▼ 4. sin líneas → ResultadoParseo "No se pudo extraer texto"
 │ ▼ 5. normalizar_codigo_ocr en todas las líneas
 │ ▼ 6. detectar_formato_codigo (primeros tokens de 60 líneas)
 │ ▼ 7. detectar_separador_miles (primeras 80 líneas)
 │ ▼ 8. column_order (4 niveles de prioridad)
 │ ▼ 9. parsear_linea por línea (confianza 0.75 OCR / 1.0)
 │ ▼ 10. AccountTypeResolver (si flag o contexto confiable)
 │ ▼ 11. advertencias OCR / rotación 180°
 │ ▼ 12. _anotar_extractor → resultado.extractor_info
 │ ▼ ResultadoParseo (nunca lanza)
```

### Métodos internos

| Método | Línea | Función |
|---|---|---|
| `_anotar_extractor(resultado, detectado=None)` | `:836` | Rellena `extractor_info` vía `SpecializedExtractorFactory.detect()`. NO cambia extracción. Nunca lanza. |
| `_analizar_documento(path)` | `:866` | `analyze_document_preview(path)`. Nunca lanza. |
| `_extraer_lineas(path, context)` | `:882` | `pdfplumber.open` → `page.extract_text()`; si sin texto → OCR. |
| `_debe_corregir_rotacion(context)` | `:904` | `rotation_hint == 180` y `rotation_confidence >= 0.7`. |
| `_reverse_line(linea)` | `:913` | Invierte cada palabra (texto nativo rotado 180°). Solo texto, no coordenadas. |
| `_ocr_documento(path, n_paginas)` | `:919` | Renderiza páginas a PNG (250 dpi), detecta rotación (OSD + heurística 0/90), OCR por página. |

## `parsear_excel(file) -> list[CuentaRaw]` (`:957-977`)

`pd.read_excel(file, header=None)`; por fila: `nombre` = texto más largo,
`codigo` = primer valor numérico puro, `monto` = último número.
`origen_columna=DESCONOCIDO`, `confianza_extraccion=0.9`.
**No devuelve `ResultadoParseo`**; los callers lo envuelven.

## Modelos

### `CuentaRaw` (`:96-105`)

```
linea: int
codigo: Optional[str]
nombre: str
monto: Optional[float]
origen_columna: OrigenColumna = DESCONOCIDO
es_total: bool = False
confianza_extraccion: float = 1.0   # baja si viene de OCR
tipo_cuenta: Optional[str] = None   # AccountType resuelto
```

Nota: no tiene `to_dict()` (usado por `validation_adapter` con fallback).

### `ResultadoParseo` (`:108-123`)

```
archivo, formato_codigo: FormatoCodigo, separador_miles: str,
requirio_ocr: bool, rotacion_aplicada: int,
cuentas: list[CuentaRaw], advertencias: list[str],
document_context: Optional[Any]  (DocumentProcessingContext),
extractor_info: Optional[dict]
```

### `FormatoCodigo` (`:64-68`)

`GUION` ("guion", `1-01-01-02-01`), `PUNTO` ("punto"), `COMPACTO`
("compacto", `1112001`), `SIN_CODIGO` ("sin_codigo").

### `ExtractionContext` (`:126-147`)

Contrato que `DocumentAnalyzer` produce para `parsear`:
`rotation_hint, rotation_confidence, needs_ocr, layout_hint,
layout_confidence, format_hint, confidence, analysis_source`.

### `OrigenColumna` (`:71-79`)

`ACTIVO, PASIVO, PERDIDA, GANANCIA, DEUDOR, ACREEDOR, DESCONOCIDO`.

## Dependencias

- Externas: `pandas`, `pdfplumber`, `PIL`.
- Diferidas (para romper ciclos): `document_intelligence.extractors.factory`,
  `document_intelligence.extractors.profile_driven`,
  `parsers.layout_detector`, `parsers.account_type_resolver`,
  `document_intelligence.context`.
- Clasificador por código: `clasificador_codigo_cuenta.ClasificadorCodigo`
  (módulo separado con `MAPEO_GUION/MAPEO_COMPACTO/MAPEO_PUNTO`).

## Quién lo utiliza

`pipeline/homologation_pipeline.py:36, 370, 380`; `adapters/parser_adapter.py`
(8, 13, 25, 40); `pipeline/new_pipeline.py`; `app_validacion.py` (762, 767);
`document_intelligence/extractors/universal.py:28`; `ui/app.py` (vía pipeline);
scripts de benchmark y tests.

## Feature Flags

- `ENABLE_DYNAMIC_LAYOUT` (default `False`): activa detección de layout por
  perfil de familia / `LayoutDetector` (y la detección anticipada de
  extractor). Ver `docs/architecture/feature_flags.md`.
- `ENABLE_ACCOUNT_TYPE_RESOLVER` (default `False`).
- Umbrales: `ROTATION_CORRECTION_THRESHOLD=0.7`,
  `LAYOUT_CONFIDENCE_THRESHOLD=0.8`,
  `ACCOUNT_TYPE_CONFIDENCE_THRESHOLD=0.7`.

## Riesgos técnicos

1. **Monolito de 1007 líneas**; `parsear()` ~240 líneas con múltiples
   responsabilidades.
2. **Rutas hardcodeadas** de binarios: `TESSDATA_DIR='/usr/local/share/tessdata'`,
   `/usr/local/bin/tesseract`, `/usr/local/bin/pdftoppm`.
3. **Patrón `except Exception` + `noqa: BLE001`** extendido: fallos se
   tragan a nivel `logger.debug`.
4. **`_reverse_line` solo invierte texto, no coordenadas**; en contraste,
   `orientation_detector.corregir_words_rotadas` sí corrige coordenadas.
5. **`parsear_excel` heurístico**: nombre = texto más largo, monto = último
   número; frágil para balances con varias columnas.
6. **Dos contextos paralelos**: `ExtractionContext` (parser_universal) vs
   `DocumentProcessingContext` (document_intelligence) — mapeo manual.
7. **Timeout de OCR**: OSD 60s, heurística 90s, OCR 120s/página; OCR
   secuencial página por página.
8. `detectar_rotacion_osd`/`detectar_rotacion_heuristica` capturan
   excepciones con `except Exception: pass` → si tesseract no está, OCR
   devuelve líneas vacías silenciosamente.

## Posibles mejoras futuras

- Unificar con `parsers/` (ParserCore2 + `ParserConfig`) o elegir una vía.
- Parametrizar rutas de binarios (env/`shutil.which`).
- Manejo de errores explícito en lugar de `except Exception` silencioso.
- Agregar `to_dict()` a `CuentaRaw` (hoy `validation_adapter` pierde datos).
