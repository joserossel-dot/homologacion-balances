# Parser Core 2.0 — Diseño

| Versión | Fecha | Autor |
|---------|-------|-------|
| 1.0 | 2026-07-09 | — |

---

## 1. Resumen ejecutivo

El parser actual (`parser_universal.py`, 686 líneas) es un monolito que mezcla validación,
extracción de texto nativo, pipeline OCR, detección de formato, parseo de líneas y
asignación de columnas en un solo archivo. No tiene configuración externa, usa paths
hardcodeados a binarios del sistema, y emplea una heurística fija de 4 columnas basada
en solo 12 balances de muestra. Parser Core 2.0 reemplaza este monolito por una
arquitectura modular, configurable y testeable, manteniendo los modelos de datos y
adaptadores existentes.

---

## 2. ¿Por qué cambiar?

### 2.1 Deuda técnica acumulada

| Problema | Impacto |
|----------|---------|
| **Monolito de 686 líneas** | Violación de SRP; cualquier cambio requiere entender el archivo completo |
| **Paths hardcodeados** | `/usr/local/bin/tesseract`, `/usr/local/bin/pdftoppm` — no portable fuera de macOS Homebrew |
| **Heurística de 4 columnas fija** | `ULTIMAS_COLS = [ACTIVO, PASIVO, PERDIDA, GANANCIA]` basada en 12 muestras; no valida por documento |
| **Sin sistema de errores** | Errores como strings, no tipos; no se pueden manejan por categoría |
| **Sin configuración** | Todos los thresholds y rutas están en el código fuente |
| **Sin tests unitarios del core** | `parsear_monto()`, `detectar_formato_codigo()`, `detectar_separador_miles()`, `parsear_linea()` no tienen tests |
| **Pipeline dual** | `MotorHibridoLocal` (legacy) y `HomologationPipeline` (nuevo) coexisten con flags |

### 2.2 Limitaciones funcionales

| Limitación | Consecuencia |
|------------|-------------|
| OCR secuencial por página | 120s timeout por página; documentos de 20+ páginas pueden tomar horas |
| Detección de formato global por archivo | Fallas si el documento mezcla formatos de código |
| Sin detección de moneda | No distingue CLP, UF, USD — todos los montos se tratan igual |
| Sin caché | Cada parseo re-extrae y re-OCRea el mismo archivo |
| Sin awareness multi-página | La asignación de columnas se hace línea por línea independientemente |
| Sin plugin de OCR alternativo | Solo Tesseract; no se puede usar EasyOCR, doctr, etc. |

### 2.3 Costo de no migrar

- Cada nuevo layout requiere modificar el monolito
- No se puede certificar la corrección de la asignación de columnas por documento
- El tiempo de procesamiento de OCR es un cuello de botella sin paralelización
- Los errores de parseo son difíciles de diagnosticar por falta de tipos

---

## 3. ¿Qué se reemplaza?

### 3.1 Archivos reemplazados

| Archivo actual | Reemplazo en Parser Core 2.0 |
|----------------|------------------------------|
| `parser_universal.py` (686 ln) | `parsers/` package (9 módulos, ~900 ln total) |
| `app_validacion.py` — `parsear_excel()` (1914 ln, solo la función de parseo) | `parsers/excel_parser.py` |
| — | `parsers/ocr_engine.py` (nuevo) |
| — | `parsers/layout_detector.py` (nuevo) |
| — | `parsers/config.py` (nuevo) |

### 3.2 No se reemplazan

| Componente | Razón |
|------------|-------|
| `ResultadoParseo`, `CuentaRaw`, `FormatoCodigo` | Modelos de datos estables, sin deuda |
| `AccountAdapter.from_cuenta_raw()` | Contrato de integración probado |
| `BalanceInterpreter` | Funciona sobre `AccountBalance`, no sobre el parser |
| `HomologationPipeline` | Orquestador que consume el parser, no lógica de parseo |
| `parser_quality/` | Capa de calidad ortogonal al parser base |
| `GARBAGE_PATTERNS` y `_es_linea_basura()` | Filtro probado (0 FP/0 FN en 186 docs) — se mueve a `parsers/hygiene.py` |
| `tools/layout_audit.py` | Herramienta de auditoría, no parte del parser mismo |

---

## 4. Arquitectura

### 4.1 Diagrama de paquetes

```
parsers/
├── __init__.py                  # Re-exporta ParserFactory
├── config.py                    # ConfigParser — carga parser_config.toml + env vars
├── file_validator.py            # validar_archivo() — separado, testeable
├── ocr_engine.py                # OcrEngine (interfaz) + TesseractEngine (impl)
├── format_detector.py           # detectar_formato_codigo(), detectar_separador_miles()
├── line_parser.py               # parsear_linea(), parsear_monto(), normalizar_codigo_ocr()
├── hygiene.py                   # GARBAGE_PATTERNS, es_linea_basura()
├── layout_detector.py           # detectar_layout() — infiere columnas por documento
├── excel_parser.py              # parsear_excel() — extraído de app_validacion
├── pdf_parser.py                # ParserPDF — orquesta extracción + OCR + parseo
└── factory.py                   # ParserFactory — create_parser(path) -> ParserBase
```

### 4.2 Interfaz base

```python
class ParserBase(ABC):
    @abstractmethod
    def parse(self, path: Path, config: ParserConfig | None = None) -> ParseResult:
        ...

@dataclass
class ParseResult:
    file_name: str
    format: CodeFormat
    thousands_sep: str
    used_ocr: bool
    rotation: int
    accounts: list[RawAccount]
    layout: DetectedLayout | None     # Nuevo
    warnings: list[str]
    metrics: ParseMetrics              # Nuevo
```

### 4.3 Detección de layout por documento

En lugar de la heurística fija `[ACTIVO, PASIVO, PERDIDA, GANANCIA]`, el
`LayoutDetector` analiza los encabezados reales del documento:

1. Toma las primeras N líneas no-vacías antes de la primera cuenta
2. Las normaliza y compara contra un lexicon de encabezados conocidos
   (Activo, Pasivo, Pérdida, Ganancia, Deudor, Acreedor, etc.)
3. Si encuentra coincidencia → usa ese mapping
4. Si no encuentra → fallback a heurística actual (con advertencia)

Esto ya está validado por `tools/layout_audit.py` (1138 líneas) que analizó
todos los documentos y detectó los layouts reales.

```python
@dataclass
class DetectedLayout:
    columns: list[ColumnOrigin]       # Orden detectado
    confidence: float                 # 0.0-1.0
    header_source: str                # "headers", "heuristic", "fallback"
    column_map: dict[int, ColumnOrigin]  # índice → origen
```

### 4.4 OCR Engine con interfaz pluggable

```python
class OcrEngine(ABC):
    @abstractmethod
    def ocr_page(self, image_path: Path, rotation: int,
                 lang: str = "spa") -> str:
        ...

    @abstractmethod
    def detect_rotation(self, image_path: Path) -> int | None:
        ...

    @abstractmethod
    def name(self) -> str:
        ...

class TesseractEngine(OcrEngine):
    def __init__(self, tesseract_path: str | None = None,
                 tessdata_dir: str | None = None):
        self._binary = tesseract_path or _detect_tesseract()
        self._data = tessdata_dir or _detect_tessdata()
```

### 4.5 Configuración externalizada

Archivo `parser_config.toml` (en `config/` o `~/.homologacion/`):

```toml
[ocr]
engine = "tesseract"           # tesseract | easyocr | doctr
tesseract_path = "/usr/local/bin/tesseract"
tessdata_dir = "/usr/local/share/tessdata"
pdftoppm_path = "/usr/local/bin/pdftoppm"
dpi = 250
timeout_per_page = 120
lang = "spa"

[detection]
code_format_sample_lines = 60
separator_sample_lines = 80
fuzzy_threshold = 92

[layout]
enable_detection = true
fallback_to_heuristic = true

[caching]
enabled = false
cache_dir = ".parser_cache"
ttl_days = 30
```

Variables de entorno sobreescriben: `PARSER_TESSERACT_PATH`,
`PARSER_OCR_ENGINE`, `PARSER_CACHE_ENABLED`, etc.

### 4.6 ParseMetrics (nuevo)

```python
@dataclass
class ParseMetrics:
    total_lines: int
    garbage_lines: int
    parsed_accounts: int
    rejected_lines: int          # Líneas que no pasaron parseo
    ocr_pages: int
    ocr_time_seconds: float
    extraction_confidence: float  # 0.0-1.0
    layout_confidence: float      # 0.0-1.0
    format_detected: CodeFormat
    warnings_count: int
```

---

## 5. Flujo de parseo (Parser Core 2.0)

```
ParserFactory.create_parser(path)
│
├─ .pdf → PDFParser
│   ├─ file_validator.validate(path)
│   ├─ extraer_lineas()
│   │   ├─ pdfplumber pages → texto nativo
│   │   └─ si vacío → ocr_engine.ocr_documento()
│   ├─ format_detector.detectar_formato()
│   ├─ format_detector.detectar_separador()
│   ├─ layout_detector.detectar_layout()    ← NUEVO
│   └─ line_parser.parsear_todas()
│       ├─ hygiene.es_linea_basura()
│       ├─ extraer código + nombre + montos
│       ├─ layout_detector.asignar_columna(linea)
│       └─ RawAccount
│
└─ .xlsx/.xls → ExcelParser
    └─ parsear_excel() → RawAccount[]
```

---

## 6. ¿Qué riesgos?

### 6.1 Riesgos técnicos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| **Regresión en parseo** de documentos existentes | Alta | Alto | Shadow mode: ambos parsers ejecutados en paralelo; diff de salida |
| **LayoutDetector falle** en documentos sin encabezados | Media | Medio | Fallback automático a heurística actual + advertencia |
| **Config TOML mal formada** en producción | Baja | Medio | Validación del schema al cargar; fallback a defaults duros |
| **OCR Engine plugin no disponible** | Baja | Medio | Engine por defecto siempre compilado (Tesseract) |

### 6.2 Riesgos de migración

| Riesgo | Mitigación |
|--------|------------|
| **Pipeline legacy (MotorHibridoLocal)** sigue usando parser viejo | No se reemplaza MotorHibridoLocal en esta fase; solo el parser que consume |
| **Documentos procesados parcialmente** durante migración | Shadow mode completo por 1 ciclo de ejecución |
| **Paths de Tesseract cambian** en CI/CD | `_detect_tesseract()` busca en `$PATH`, `$TESSERACT_PATH`, y rutas comunes |
| **ResultadoParseo cambia de lugar** | Se mantiene import desde `parsers` como re-export |

### 6.3 No-riesgos (explícitamente fuera de alcance)

- No se cambian los modelos de datos (`CuentaRaw`, `AccountBalance`)
- No se cambia la firma de `HomologationPipeline.process()`
- No se modifica el pipeline de clasificación
- No se modifica la capa de calidad (`parser_quality/`)

---

## 7. ¿Qué pruebas?

### 7.1 Tests unitarios (nuevos)

| Módulo | Tests | Cobertura esperada |
|--------|-------|--------------------|
| `test_hygiene.py` | Existentes (38) + 10 nuevos | 100% patrones + edge cases |
| `test_format_detector.py` | 15 tests | Formatos, separadores, casos mixtos |
| `test_line_parser.py` | 25 tests | `parsear_monto()`, `parsear_linea()`, `normalizar_codigo_ocr()` |
| `test_file_validator.py` | 10 tests | PDF, XLSX, XLS, corruptos, 0 bytes |
| `test_excel_parser.py` | 8 tests | Columnas, montos, nombres |
| `test_layout_detector.py` | 12 tests | Encabezados, fallback, confianza |
| `test_config.py` | 8 tests | TOML, env vars, defaults, merge |
| `test_ocr_engine.py` | 6 tests | Interfaz, TesseractEngine mockeado |

### 7.2 Tests de integración

| Escenario | Descripción |
|-----------|-------------|
| **Shadow mode diff** | Ambos parsers procesan los 186 documentos; diff de salida debe ser idéntico |
| **Holdout certification** | Re-ejecutar `run_certification.py` contra nuevo parser; métricas deben ≥ las actuales |
| **DocumentAssessment** | Re-calcular métricas con nuevo parser; comparar distribución |
| **OCR vs nativo** | Documentos mixtos (nativo + OCR) producen mismo número de cuentas |

### 7.3 Tests de regresión

Se identifican 10 documentos "canarios" del holdout que cubren:

- Código guion, punto, compacto, sin código
- OCR nativo y escaneado
- Columnas estándar (Activo/Pasivo/Pérdida/Ganancia)
- Columnas atípicas (Deudor/Acreedor)
- Excel nativo
- Documentos con alta tasa de basura

Estos 10 documentos deben producir **exactamente las mismas cuentas** antes y después.

### 7.4 Benchmark

`scripts/benchmark_parser_hygiene.py` se extiende para comparar:

- Tiempo total de parseo (viejo vs nuevo)
- Throughput de OCR (secuencial vs paralelo)
- Precisión de detección de columnas (contra layout_audit.json)

---

## 8. ¿Qué estrategia de migración?

### 8.1 Shadow mode (Semana 1-2)

```
ParserPDF.parsear()                   ParserCore2.parse()
         │                                      │
         └─────────── Comparator ───────────────┘
                           │
                    ┌──────┴──────┐
                    │              │
               Match OK       Diff detected
                    │              │
                 silent        log + alert
```

- Ambos parsers coexisten
- `ParserFactory.create_parser()` decide cuál usar según flag
- `PARSER_CORE_VERSION=1` (default) o `PARSER_CORE_VERSION=2`
- Un cron job procesa todos los documentos con v2, compara con v1
- Se recolectan diffs durante 1 ciclo completo de ejecución

### 8.2 Feature flags

```python
# config.py o variable de entorno
PARSER_CORE_VERSION = os.getenv("PARSER_CORE_VERSION", "1")

# En HomologationPipeline.__init__():
if PARSER_CORE_VERSION == "2":
    self._parser = ParserFactory.create_parser_v2()
else:
    self._parser = ParserPDF()
```

### 8.3 Rollout por etapas

| Etapa | Duración | Acción | Validación |
|-------|----------|--------|------------|
| **0 — Preparación** | Semana 1 | Escribir todos los módulos, tests unitarios, benchmarks | Todos los tests unitarios pasan |
| **1 — Shadow** | Semana 2-3 | Activar v2 en shadow mode para todos los documentos | 0 diffs en documentos canarios |
| **2 — Beta** | Semana 4 | Activar v2 para holdout únicamente | Certificación holdout con v2 ≥ v1 |
| **3 — Gradual** | Semana 5 | 10% → 50% → 100% de documentos nuevos usan v2 | Monitoreo de alertas de diff |
| **4 — Limpieza** | Semana 6 | Remover `ParserPDF`, renombrar v2 a `ParserPDF` | Test suite completo |

### 8.4 Rollback

- Si en cualquier etapa se detecta una regresión: `PARSER_CORE_VERSION=1`
- El shadow mode debe permanecer disponible por al menos 1 mes post-migración
- Los logs de diff se guardan en `reports/parser_diff/` con timestamp

### 8.5 Criterios de GO

| Criterio | Medición |
|----------|----------|
| 0 diffs en shadow mode sobre 186 documentos | Comparator output |
| Tests de regresión pasan en 10 documentos canarios | `pytest tests/test_parser_regression.py` |
| Accuracy de certificación holdout ≥ 99% | `run_certification.py` |
| Tiempo de parseo no superior al actual (con caché desactivado) | Benchmark |
| LayoutDetector no produce falsos negativos en documentos con encabezados | `layout_audit.py` cross-check |

---

## 9. Hitos y entregables

| Hito | Fecha estimada | Entregable |
|------|---------------|------------|
| H1 — Diseño aprobado | Día 0 | Este documento |
| H2 — Módulos escritos | Día 5 | `parsers/` package con 9 módulos + tests |
| H3 — Shadow mode operativo | Día 10 | Comparator ejecutándose en CI |
| H4 — Cero diffs en canarios | Día 15 | Log de shadow mode sin alerts |
| H5 — Certificación holdout ≥ 99% | Día 20 | `reports/certification/certification_report.md` |
| H6 — Rollout 100% | Día 30 | Parser v1 deprecado, v2 como default |
| H7 — Limpieza | Día 35 | `parser_universal.py` eliminado, todo apunta a `parsers/` |

---

## 10. Costo estimado

| Recurso | Días-hombre |
|---------|-------------|
| Implementación de módulos | 5 |
| Tests unitarios | 3 |
| Shadow mode + comparator | 2 |
| LayoutDetector + integración con layout_audit | 2 |
| Configuración + OCR Engine interfaz | 1 |
| Documentación | 1 |
| **Total** | **14 días-hombre** |

---

## Apéndice A: Comparativa parser actual vs 2.0

| Aspecto | Actual (v1) | Propuesto (v2) |
|---------|-------------|----------------|
| Archivos | 1 (`parser_universal.py`) | 9 módulos en `parsers/` |
| Líneas totales | ~686 | ~900 |
| Configuración | Hardcodeada | TOML + env vars |
| OCR | Tesseract fijo | Interfaz pluggable |
| Columnas | Heurística fija 4 cols | Detección por documento |
| Tests del core | 0 (solo hygiene) | ~90 tests |
| Caché | No | Opcional por hash |
| OCR paralelo | No | Sí (ThreadPool) |
| Errores | Strings | Tipos enumerados |
| Pipeline legacy | Sigue existiendo | Unificado |
