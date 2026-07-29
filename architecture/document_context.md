# DocumentContext: El objeto central del sistema

## Filosofía

`DocumentContext` es el único contrato de datos que atraviesa todo el
pipeline. Ningún módulo necesita conocer la existencia de otros módulos;
cada uno lee los campos que necesita del contexto y escribe los campos que
produce.

Esto permite:
- Reordenar módulos sin cambiar interfaces
- Añadir nuevos módulos sin modificar existentes
- Ejecutar módulos en paralelo cuando no hay dependencias secuenciales
- Inspeccionar el estado completo del procesamiento en cualquier punto

---

## Especificación completa

```python
@dataclass
class DocumentContext:
    # ─── Identidad ───────────────────────────────────────────────
    document_id: str                    # UUID único del documento
    source_file: str                    # Ruta original del archivo
    filename: str                       # Nombre del archivo
    file_hash: str                      # SHA256 del archivo
    file_size: int                      # Tamaño en bytes
    created_at: datetime                # Momento de ingreso al sistema

    # ─── Enrutamiento (IDR) ──────────────────────────────────────
    document_type: str | None           # "balance", "resultados", "patrimonio", etc.
    family: str | None                  # "PYME", "GRANDE", "SECTOR_PUBLICO", etc.
    routing_path: str | None            # Ruta de procesamiento seleccionada
    router_version: str | None          # Versión del router que procesó

    # ─── Materia prima ───────────────────────────────────────────
    raw_lines: list[str]                # Líneas de texto extraídas del PDF/Excel
    raw_tables: list[list[list[str]]]   # Tablas detectadas (Excel)
    source_format: str | None           # "pdf", "excel", "ocr", "image"

    # ─── Estructura (SIE) ────────────────────────────────────────
    pages: int                          # Número total de páginas
    layout: dict                        # Layout de columnas detectado
    structure: StructuralTree | None    # Árbol jerárquico completo
    sections: list[SectionInfo]         # Secciones detectadas
    structural_signature: StructuralSignature | None

    # ─── Template (SIE + TemplateRepository) ─────────────────────
    template: StructureTemplate | None  # Template matched
    template_match: TemplateMatch | None  # Resultado del matching
    template_id: str | None             # ID del template usado

    # ─── Datos parseados (Parser) ────────────────────────────────
    accounts: list[AccountBalance]      # Cuentas extraídas
    parsed_at: datetime | None
    parser_version: str | None
    parse_metrics: dict | None          # Tiempo, líneas, cuentas, etc.

    # ─── Homologación (Knowledge Base CMCC) ──────────────────────
    knowledge: list[KnowledgeMatch]     # Correspondencias KB
    kb_version: str | None
    kb_name: str | None                 # "cmcc", "custom", etc.
    homologated_at: datetime | None
    homologation_stats: dict | None     # Total, matched, unmatched, etc.

    # ─── Validación (BIV) ────────────────────────────────────────
    validation: ValidationResult | None
    validated_at: datetime | None
    validation_version: str | None

    # ─── Confianza (Confidence Engine) ───────────────────────────
    confidence: ConfidenceResult | None
    confidence_version: str | None
    confidence_at: datetime | None

    # ─── Cobertura (Coverage Engine) ─────────────────────────────
    coverage: CoverageResult | None
    coverage_version: str | None
    coverage_at: datetime | None

    # ─── Revisión humana (ReviewWorkspace) ──────────────────────
    review: ReviewCandidate | None
    review_status: ReviewStatus | None
    review_history: list[HumanDecision]
    reviewed_at: datetime | None
    reviewer: str | None

    # ─── Estado del pipeline ─────────────────────────────────────
    status: ProcessingStatus            # Estado actual del procesamiento
    errors: list[ProcessingError]       # Errores ocurridos (no bloqueantes)
    warnings: list[str]                 # Advertencias
    processing_steps: list[ProcessingStep]  # Traza de pasos ejecutados
    started_at: datetime | None
    completed_at: datetime | None
    elapsed_seconds: float | None

    # ─── Extensión ───────────────────────────────────────────────
    metadata: dict                      # Metadatos adicionales (extensible)
    tags: list[str]                     # Etiquetas para clasificación
```


## Quién llena cada campo

| Campo | Lo llena | Momento |
|---|---|---|
| `document_id` | IDR | Inicio |
| `source_file` | IDR / DatasetManager | Inicio |
| `filename` | IDR / DatasetManager | Inicio |
| `file_hash` | IDR | Inicio |
| `file_size` | IDR | Inicio |
| `created_at` | IDR | Inicio |
| `document_type` | IDR | Enrutamiento |
| `family` | IDR o SIE | Enrutamiento o estructura |
| `routing_path` | IDR | Enrutamiento |
| `raw_lines` | Parser (pre-parse) | Antes del parseo |
| `raw_tables` | Parser (pre-parse, Excel) | Antes del parseo |
| `source_format` | IDR | Enrutamiento |
| `pages` | SIE | Análisis estructural |
| `layout` | SIE | Análisis estructural |
| `structure` | SIE | Análisis estructural |
| `sections` | SIE | Análisis estructural |
| `structural_signature` | SIE | Análisis estructural |
| `template` | TemplateRepository (via SIE) | Matching |
| `template_match` | TemplateRepository (via SIE) | Matching |
| `template_id` | SIE / TemplateRepository | Matching |
| `accounts` | Parser | Post-parseo |
| `parsed_at` | Parser | Post-parseo |
| `parser_version` | Parser | Post-parseo |
| `parse_metrics` | Parser | Post-parseo |
| `knowledge` | Knowledge Base CMCC | Homologación |
| `kb_version` | Knowledge Base CMCC | Homologación |
| `kb_name` | Knowledge Base CMCC | Homologación |
| `homologated_at` | Knowledge Base CMCC | Homologación |
| `homologation_stats` | Knowledge Base CMCC | Homologación |
| `validation` | BIV | Validación |
| `validated_at` | BIV | Validación |
| `validation_version`| BIV | Validación |
| `confidence` | Confidence Engine | Evaluación |
| `confidence_version`| Confidence Engine | Evaluación |
| `confidence_at` | Confidence Engine | Evaluación |
| `coverage` | Coverage Engine | Medición |
| `coverage_version` | Coverage Engine | Medición |
| `coverage_at` | Coverage Engine | Medición |
| `review` | ReviewWorkspace | Revisión |
| `review_status` | ReviewWorkspace | Revisión |
| `review_history` | ReviewWorkspace | Revisión |
| `reviewed_at` | ReviewWorkspace | Revisión |
| `reviewer` | ReviewWorkspace | Revisión |
| `status` | Pipeline / cada módulo | Durante todo el flujo |
| `errors` | Cualquier módulo | Durante todo el flujo |
| `warnings` | Cualquier módulo | Durante todo el flujo |
| `processing_steps` | Pipeline | Durante todo el flujo |
| `started_at` | Pipeline | Inicio del pipeline |
| `completed_at` | Pipeline | Fin del pipeline |
| `elapsed_seconds` | Pipeline | Fin del pipeline |
| `metadata` | Cualquier módulo | Durante todo el flujo |
| `tags` | IDR o SIE | Enrutamiento o estructura |


## ProcessingStatus

```python
class ProcessingStatus(Enum):
    # Ciclo de vida completo
    PENDING = "PENDING"                 # En INBOX, no procesado
    ROUTING = "ROUTING"                 # IDR en progreso
    ROUTED = "ROUTED"                   # IDR completado
    ANALYZING = "ANALYZING"             # SIE en progreso
    ANALYZED = "ANALYZED"               # SIE completado
    PARSING = "PARSING"                 # Parser en progreso
    PARSED = "PARSED"                   # Parser completado
    HOMOLOGATING = "HOMOLOGATING"       # KB en progreso
    HOMOLOGATED = "HOMOLOGATED"         # KB completado
    VALIDATING = "VALIDATING"           # BIV en progreso
    VALIDATED = "VALIDATED"             # BIV completado
    CONFIDENCE = "CONFIDENCE"           # Confidence en progreso
    COVERAGE = "COVERAGE"               # Coverage en progreso
    REVIEWING = "REVIEWING"             # En revisión humana
    REVIEWED = "REVIEWED"               # Revisión completada
    COMPLETED = "COMPLETED"             # Pipeline terminado
    ERROR = "ERROR"                     # Error no recuperable
    PARTIAL = "PARTIAL"                 # Procesado parcial (con errores)
```


## ProcessingError

```python
@dataclass
class ProcessingError:
    step: str                   # Módulo que reporta el error
    code: str                   # Código de error (ej. "PARSER-001")
    message: str                # Mensaje descriptivo
    severity: str               # "error", "warning", "info"
    recoverable: bool           # True si el pipeline puede continuar
    field: str | None           # Campo del contexto afectado
    timestamp: datetime
```


## ProcessingStep

```python
@dataclass
class ProcessingStep:
    module: str                 # Nombre del módulo
    action: str                 # Acción ejecutada
    started_at: datetime
    ended_at: datetime
    elapsed: float              # Segundos
    status: str                 # "success", "error", "skipped"
    details: dict | None
```


## Reglas de uso

1. **Un campo se escribe una sola vez** por el módulo responsable. Ningún
   otro módulo debe modificar campos que no le pertenecen.

2. **Los campos son opcionales (`None`)** hasta que el módulo responsable
   los completa. Los módulos downstream deben manejar `None` sin colapsar.

3. **Los errores se acumulan**, no detienen el pipeline. Un error en
   validación no impide calcular confianza sobre los datos disponibles.

4. **processing_steps** es una bitácora de auditoría. Cada módulo agrega
   su entrada al finalizar.

5. **metadata** es un diccionario extensible para datos específicos de
   cada módulo que no justifican un campo propio.

6. **tags** permite clasificar documentos para búsqueda y filtrado
   (ej. "urgente", "revisado", "exportado").
