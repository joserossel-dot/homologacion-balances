# Document Context Engine — Reporte de Validación

> Generado automáticamente al ejecutar la suite de tests.

---

## Arquitectura

```
document_context/
├── __init__.py          # Public API (DocumentContext, Serializer, Merger, Validator, Statistics)
├── models.py            # 10 dataclasses + ProcessingState enum
├── context.py           # DocumentContext (core del sistema)
├── lifecycle.py         # State machine con transiciones validades
├── snapshot.py          # Snapshot manager con diff
├── serializers.py       # JSON / dict / markdown / pickle
├── merge.py             # Merge no-destructivo (partial + dict + full)
├── validators.py        # Validador de consistencia del contexto
└── statistics.py        # Estadísticas agregadas sobre múltiples contextos
```

---

## Resumen

| Métrica | Valor |
|---------|-------|
| Tests | 100 |
| Pasados | 100 |
| Cobertura módulos | 9/9 |
| Líneas de código (código fuente) | ~1,000 |
| Líneas de código (tests) | ~1,100 |
| Dependencias externas | 0 (stdlib only) |

---

## Estructura del DocumentContext

```
DocumentContext
├── identity: DocumentIdentity (read-only)
│   ├── document_id, source_file, sha256, created_at, updated_at, version
├── metadata: DocumentMetadata | None (write-once via set_metadata)
│   ├── company, rut, year, pages, language, orientation, layout, ocr_probability
├── structure: StructureData | None (write-once via set_structure)
│   ├── family, template, document_type, sections, tree, column_layout
├── parser: ParserData | None (write-once via set_parser)
│   ├── selected_parser, parser_version, parser_time, accounts, raw_accounts, ignored_accounts
├── knowledge: KnowledgeData | None (write-once via set_knowledge)
│   ├── cmcc_matches, learning_hits, variants, dictionary_matches
├── validation: ValidationData | None (write-once via set_validation)
│   ├── integrity, subtotal_validation, equation_validation, missing_accounts, warnings, errors
├── prediction: PredictionData | None (write-once via set_prediction)
│   ├── confidence_expected, coverage_expected, estimated_time, complexity
├── execution: ExecutionData | None (write-once via set_execution)
│   ├── confidence_real, coverage_real, processing_time, review_required, status
├── custom: dict (appendable via set_custom / get_custom)
├── state: ProcessingState (NEW → IDENTIFIED → STRUCTURED → PARSED → CLASSIFIED → VALIDATED → REVIEWED → COMPLETED | FAILED)
├── events: list[LifecycleEvent] (append-only)
└── snapshots: list[ContextSnapshot] (append-only via snapshot())
```

**Regla fundamental:** Cada campo se escribe una sola vez. Un módulo no puede
modificar datos de otro módulo. Solo `custom` permite escritura múltiple.

---

## Estados y transiciones

```
NEW ──────────► IDENTIFIED ──► STRUCTURED ──► PARSED ──► CLASSIFIED ──► VALIDATED ──► REVIEWED ──► COMPLETED
  │                │               │            │             │               │              │
  └──► FAILED ◄────┴───────────────┴────────────┴─────────────┴───────────────┴──────────────┘
```

Cada transición:
1. Valida que sea permitida
2. Crea un snapshot automático del estado previo
3. Registra un LifecycleEvent en el audit trail
4. Actualiza `updated_at`

---

## Eventos (ejemplo)

| # | Timestamp | From | To | Module | Description |
|---|-----------|------|-----|--------|------------|
| 1 | 12:00:01 | NEW | IDENTIFIED | die | metadata set |
| 2 | 12:00:02 | IDENTIFIED | STRUCTURED | sie | structure set |
| 3 | 12:00:03 | STRUCTURED | PARSED | parser | parser set |
| 4 | 12:00:04 | PARSED | CLASSIFIED | kb | knowledge set |
| 5 | 12:00:05 | CLASSIFIED | VALIDATED | biv | validation set |
| 6 | 12:00:06 | VALIDATED | REVIEWED | review | review completed |
| 7 | 12:00:07 | REVIEWED | COMPLETED | system | processing completed |

---

## Snapshots (ejemplo)

| # | Label | State | Timestamp |
|---|-------|-------|-----------|
| 1 | before_identified | NEW | 12:00:01 |
| 2 | before_structured | IDENTIFIED | 12:00:02 |
| 3 | before_parsed | STRUCTURED | 12:00:03 |
| 4 | before_classified | PARSED | 12:00:04 |
| 5 | before_validated | CLASSIFIED | 12:00:05 |
| 6 | before_reviewed | VALIDATED | 12:00:06 |
| 7 | before_completed | REVIEWED | 12:00:07 |

Los snapshots son deep copies comparables vía `diff_snapshots()`.

---

## Serialización

| Formato | Método | Uso |
|---------|--------|-----|
| dict | `to_dict()` / `from_dict()` | Integración en memoria |
| JSON | `to_json()` / `from_json()` | Persistencia / API |
| JSON file | `to_json_file()` / `from_json_file()` | Archivos |
| Pickle | `to_pickle()` / `from_pickle()` | Cache binario |
| Markdown | `to_markdown()` | Reportes legibles |

---

## Merge

`ContextMerger` soporta 3 modos:

1. **`merge(target, source)`** — Fusión completa de dos contextos
2. **`merge_partial(ctx, metadata=..., structure=...)`** — Fusión por kwargs
3. **`merge_dict(ctx, {"metadata": {...}})`** — Fusión desde diccionario

Ningún merge sobreescribe campos existentes.

---

## Validación de consistencia

`ContextValidator.validate(ctx)` detecta:

| Categoría | Detecta |
|-----------|---------|
| required_field | Campos obligatorios ausentes para el estado actual |
| parser | Parser sin cuentas, parser no especificado |
| validation | Validación sin parser, errores de validación |
| lifecycle | Saltos en cadena de eventos |
| snapshot | Eventos sin snapshots correspondientes |
| completion | Completado con errores, completado sin revisión |

---

## Integración futura (Sprint 24)

El DCE se integrará con los módulos existentes SIN modificarlos:

```python
# Patrón de integración:
from document_context import DocumentContext
from document_context.models import StructureData

# 1. SIE produce StructuralTree
ctx.set_structure(StructureData(
    family=sie_result.family,
    sections=sie_result.sections,
))

# 2. DIE produce IntelligenceReport
ctx.set_prediction(PredictionData(
    confidence_expected=report.confidence.confidence_pct / 100,
    coverage_expected=report.coverage.coverage_pct / 100,
))

# 3. Parser produce list[AccountBalance]
ctx.set_parser(ParserData(
    selected_parser="Universal",
    accounts=parser_result.accounts,
))

# 4. KB produce list[KnowledgeMatch]
ctx.set_knowledge(KnowledgeData(
    cmcc_matches=kb_result,
))

# 5. Validation produce ValidationResult
ctx.set_validation(ValidationData(
    integrity=validation_result.integrity_score,
    warnings=validation_result.warnings,
))

# 6. Review Workspace produce decisiones
ctx.mark_reviewed()
```

**No se requiere modificar** SIE, DIE, Parser, KB, Validation o Review
Workspace. La adaptación ocurre en la capa de integración.

---

## Compatibilidad

| Módulo | Compatible | Sin modificar | Notas |
|--------|-----------|---------------|-------|
| SIE | ✅ | ✅ | `StructureData` recibe StructuralTree |
| DIE | ✅ | ✅ | `PredictionData` recibe IntelligenceReport |
| Parser | ✅ | ✅ | `ParserData` recibe list[AccountBalance] |
| KB | ✅ | ✅ | `KnowledgeData` recibe list[KnowledgeMatch] |
| Validation | ✅ | ✅ | `ValidationData` recibe ValidationResult |
| Review WS | ✅ | ✅ | `mark_reviewed()` activa la transición |

---

## Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Write-once impide reintentos | Bajo | Cada módulo escribe una vez; si falla, se usa `FAILED` + nuevo contexto |
| Deep copy en snapshots consume memoria | Medio | Snapshots solo almacenan dict; objetos grandes referenciados no se duplican completamente |
| Sin locks para concurrencia | Bajo | El pipeline es secuencial por documento |

---

*Reporte generado por Document Context Engine — Sprint 23*
