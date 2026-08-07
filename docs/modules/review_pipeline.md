# Módulo: Pipeline de Revisión

> **Ubicación**: `review/`, `adapters/review_adapter.py`

## Propósito

Construir la **cola de revisión humana** para las cuentas que el pipeline no
clasificó (UNKNOWN) o clasificó con baja confianza, y generar paquetes de
trabajo (Excel/Markdown) para que un analista decida el código final.

## Responsabilidad

1. Recopilar cuentas pendientes desde el resultado del pipeline
   (`standard_code is None`, o cola CMCC con score == 1.0).
2. Priorizar con un score de revisión.
3. Generar libros Excel multi-hoja (`review_package`) y reportes
   (`review_queue.xlsx`, estadísticas, por empresa/layout/concepto).
4. (V2) Registrar el estado de revisión en el `DocumentContext`.

## Componentes

| Archivo | Rol |
|---|---|
| `cmcc_review_pipeline.py` (367) | Orquesta: corre el pipeline, extrae cola REVIEW_CMCC, genera reportes |
| `cmcc_review_models.py` | `ReviewCMCC` (entrada de la cola CMCC) |
| `review_package_builder.py` (325) | Construye el paquete Excel con 6+ hojas |
| `review_metrics.py` (176) | `compute_score`, `prioritize_accounts`, `build_pending_rows`, `build_dashboard` |
| `review_models.py` (191) | `PendingAccount`, `LowConfidenceEntry`, `GoldConflict`, `ProposedRule`, `SynonymEntry`, `GoldProposal`, `DashboardMetrics`, `account_to_pending` |
| `excel_formatter.py` (286) | Formato de hojas (tablas, filtros, dropdowns, conditional formatting) |
| `run_review_package.py` | CLI del paquete de revisión |
| `adapters/review_adapter.py` (32) | `ReviewAdapter` — integración V2 en el DocumentContext |

## Score de revisión (`PendingAccount.score`, `review_models.py:41-56`)

```
score = 50  (si método unknown/unclassified)
      + 30  (si confidence < 0.5)  |  + 15 (si confidence < 0.85)
      + min(frecuencia * 2, 20)
      + min(cantidad_empresas * 5, 25)
      + 10  (si semantic_hit)  +  5 (si learning_hit)
```

## Flujo CMCC review (`cmcc_review_pipeline.py`)

```
run_pipeline_for_review(features, label, limit)
   ▼ HomologationPipeline(gs_db, features)  [env fuerza CMCC flags = false]
   ▼ DatasetManager("datasets").discover() → archivos
   ▼ por archivo: pipeline.process() → resultados
   ▼ extract_review_queue(result)  (:55-79)
   │    por cuenta classified sin standard_code:
   │      cmcc_detail/shadow con score == 1.0 → ReviewCMCC.from_pipeline_account
   │      (NO es clasificación oficial; solo cola humana)
   ▼ compute_statistics(queue, summary)  (:139-175)
   │    top empresas/layouts/conceptos/documentos/métodos
   ▼ generate_reports → review_queue.xlsx, review_statistics.xlsx,
   │    review_by_company.xlsx, review_by_layout.xlsx, review_by_concept.xlsx
   ▼ generate_markdown → reporte con trazabilidad
```

> ⚠️ Nota: aunque `run_pipeline_for_review` fuerza
> `CMCC_ENABLE_* = false` al inicio del módulo (`:17-19`), el pipeline que
> corre adentro produce la cola CMCC solo si `ENABLE_CMCC`/`
> ENABLE_CMCC_REVIEW_PIPELINE` están activos en `features` pasadas; el
> script principal (`scripts/run_cmcc_review_pipeline.py`) es quien habilita
> esos flags. **El módulo `review/` por sí solo no activa CMCC.**

## Flujo V2 (`ReviewAdapter.run`, `adapters/review_adapter.py:14-32`)

```
ctx.get_custom("classified") → cuentas con standard_code is None
   ▼ ctx.set_custom("review_queue", unclassified)
   ▼ ctx.set_custom("review_count", N)
   ▼ ExecutionData(review_required, status="reviewed"|"has_pending")
   ▼ ctx.set_execution(...) + ctx.mark_reviewed()   (REVIEWED)
```

> ⚠️ La persistencia en `review_workspace/review.db` NO está implementada:
> `db_path` se guarda en `__init__` pero no se usa.

## Entradas

- Resultado de `HomologationPipeline.process()` (dict con `classified`).
- `DatasetManager.discover()` (datasets).
- (V2) `DocumentContext` con `classified`.

## Salidas

- Cola: `list[dict]` (`ReviewCMCC.to_dict()` / `PendingAccount`).
- Paquetes: Excel multi-hoja con columnas `PENDING_COLUMNS`
  (`review_models.py:128-140`), editable/readonly separados
  (`PENDING_EDITABLE`/`PENDING_READONLY`), dropdowns (`CLASE_VALUES`,
  `SEMANTIC_TYPE_VALUES`, `APRENDER_VALUES`, `CONTRA_CUENTA_VALUES`,
  `ALCANCE_VALUES`).
- Reportes: `reports/cmcc_review_pipeline/*.xlsx` + markdown.
- (V2) `review_queue`, `review_count`, estado `REVIEWED`.

## Dependencias

`pandas`, `openpyxl`, `pipeline.homologation_pipeline`,
`pipeline.features`, `validation.dataset_manager`, `review.*` (interno).

## Feature flags

- `ENABLE_CMCC` + `ENABLE_CMCC_REVIEW_PIPELINE` + `CMCC_REVIEW_THRESHOLD`
  (0.85) para la cola CMCC (ver `docs/architecture/feature_flags.md`).
- En V2, `ReviewAdapter` siempre corre (sin flag).

## Objetos clave

`ReviewCMCC`, `PendingAccount`, `ReviewAdapter`, `DashboardMetrics`,
`PENDING_COLUMNS`/`PENDING_EDITABLE`.

## Relaciones

- `HomologationPipeline` produce `classified`/`cmcc_shadow`/`cmcc_detail`.
- `scripts/run_cmcc_review_pipeline.py` (script principal).
- V2 `pipeline_v2.py` encadena `ReviewAdapter` tras `ValidationAdapter`.
- `ui/app.py` (pantalla de revisión) y `app_validacion.py`.

## Riesgos

1. Persistencia de revisión **no implementada** (V2): el flujo solo marca
   estado en memoria; no hay `review.db` real.
2. Cola CMCC con umbral fijo `score == 1.0` en `extract_review_queue`
   (`cmcc_review_pipeline.py:64-66`), duplicando el umbral del pipeline.
3. `sys.path.insert` + `os.environ` mutation al importar el módulo
   (`cmcc_review_pipeline.py:15-19`) — efectos globales al importar.
4. Paquete Excel complejo (6+ hojas, dropdowns, formatos) — difícil de
   mantener sin tests de UI.
5. Score de prioridad con pesos hardcodeados.

## Mejoras futuras

- Implementar persistencia real de `review.db` (V2).
- Unificar umbrales de cola CMCC (pipeline vs extract).
- Externalizar el score de prioridad a configuración.
- Mover `sys.path`/env mutations a la entrada (script) en vez del import.
