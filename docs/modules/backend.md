# Módulo: Backend

> **Ubicación**: `backend/`, `src/api/main.py`, `run_pipeline_v2.py`

## Propósito

Capa de ejecución/empaquetado del pipeline **V2**: lanza el procesamiento,
mide tiempos por módulo, guarda artefactos, construye el resultado final
(`BackendResult`) con estadísticas, y expone una API HTTP.

## Responsabilidad

1. Orquestar `HomologationPipelineV2` con tracking de métricas.
2. Persistir artefactos de salida (Excel/Markdown/JSON) en `runs/`.
3. Construir `BackendResult` con estadísticas y QA desde el `DocumentContext`.
4. Exponer endpoints HTTP (FastAPI).

## Componentes

| Archivo | Clase | Rol |
|---|---|---|
| `runner.py` | `BackendRunner` (45) | Ensambla config, logger, managers y pipeline V2 |
| `pipeline_runner.py` | `PipelineRunner` (74) | Ejecuta el pipeline con timing + artefactos |
| `config.py` | `BackendConfig` (41) | Config (runs_dir, artifacts_enabled, log_level, db_path, exports) |
| `backend_models.py` | `ExecutionMetrics`, `BackendStatistics`, `BackendResult` (98) | Modelos de resultado |
| `execution_manager.py` | `ExecutionManager` | Métricas por módulo, errores, progreso |
| `artifact_manager.py` | `ArtifactManager` | Guarda exports en `runs/` |
| `result_builder.py` | `ResultBuilder` (87) | Construye `BackendResult` desde `DocumentContext` |
| `backend_logger.py` | `BackendLogger` | Logging estructurado |
| `src/api/main.py` | FastAPI `app` (118) | `GET /health`, `POST /api/v1/analisis/procesar` |

## Config (`BackendConfig`, `backend/config.py:6-41`)

- `BACKEND_VERSION = "2.0.0-rc1"` (`:6`) — también
  `BackendResult.pipeline_version = "2.0.0-rc1"` (`backend_models.py:58`).
- Defaults: `runs_dir=runs`, `artifacts_enabled=True`, `log_level=INFO`,
  `db_path=gold_standard.db`, exports Excel/Markdown/JSON activos.
- `from_dict`/`to_dict` para serialización.

## Flujo de ejecución (`PipelineRunner.run`, `pipeline_runner.py:35-74`)

```
file_path
   ▼ verificar existencia (FileNotFoundError)
   ▼ execution_manager.start()
   ▼ module_start("pipeline_v2") → pipeline.process(path) → module_end(timing)
   ▼ (errores → execution_manager.error + complete + raise)
   ▼ result_builder.build(ctx, metrics, logs, export_paths) → BackendResult
   ▼ si artifacts_enabled: artifact_manager.save_all(result) → export_paths
   ▼ execution_manager.complete() + progress(1.0)
   ▼ BackendResult
```

## Resultado (`BackendResult`, `backend_models.py:44-98`)

Campos: `document_context, coverage, decisions, decision_stats, qa,
validation, review, execution, statistics, logs, export_paths, source_file,
pipeline_version`.

`ResultBuilder.build` (`result_builder.py:11-87`):
- `coverage` ← `ctx.get_custom("coverage")`, `decisions` ←
  `ctx.get_custom("decisions")`, `qa` ← `ctx.get_custom("self_qa")`.
- `validation` ← `ctx.validation.to_dict()`.
- `review` ← `{pending, queue}` de `ctx.get_custom("review_queue")`.
- `statistics` ← `_build_statistics`: `total_accounts, classified, ignored,
  unclassified (standard_code is None), coverage_pct (overall), unknown_pct,
  learning_hits (method.startswith("learning_")), decision_types,
  conflicts_detected, qa_approved (approval_state), qa_confidence, qa_risk,
  human_review_required (confidence < 0.85)`.

## API HTTP (`src/api/main.py`)

> ⚠️ **Importante**: la API FastAPI **NO usa** `BackendRunner`/`PipelineV2`.
> Usa el orquestador **legado** `src/core/orquestador.PipelineOrquestador` con
> `RepositorioDiccionario` (PostgreSQL con fallback JSON). Es un path separado
> del backend V2 (ver `docs/architecture/dependency_graph.md`).

- `GET /health` (`:60`): `{status, repositorio}`.
- `POST /api/v1/analisis/procesar` (`:65-106`): recibe
  `file_carpeta` (PDF), `file_balance` (PDF), `giro_empresa` (form) → valida
  extensiones → `PipelineOrquestador.procesar_analisis_completo` →
  `resultado.to_dict()`. 400 en ValueError, 500 en otros errores.
- CORS abierto (`*`).

## Entradas

- `BackendRunner.run(file_path)` — ruta a PDF/Excel.
- HTTP: multipart con 2 PDFs + giro.

## Salidas

- `BackendResult` (`to_dict()` JSON).
- Artefactos en `runs/` (Excel/Markdown/JSON, si `artifacts_enabled`).

## Dependencias

`orchestrator.pipeline_v2`, `document_context`, `backend.*` (interno).
FastAPI (solo `src/api`), `src.core.orquestador`, `src.db_repository`.

## Feature flags

- Ninguna propia; hereda comportamiento del pipeline V2 (defaults de
  `CMCCFeatureFlags`).
- `artifacts_enabled`, `export_*` son flags de config backend (no env).

## Objetos clave

`BackendRunner`, `PipelineRunner`, `BackendResult`, `BackendConfig`,
`ResultBuilder`, `ExecutionManager`, `ArtifactManager`.

## Relaciones

- `BackendRunner` → `HomologationPipelineV2` (V2).
- `src/api/main.py` → `PipelineOrquestador` (legado, independiente).
- `run_pipeline_v2.py` (CLI de V2).
- `backend/runner.py` usado por scripts de integración/benchmark.

## Riesgos

1. **Dos "backends"**: el V2 (`backend/`) y la API FastAPI legada
   (`src/api/`) son independientes y no comparten resultado/estadísticas.
2. `src/api/main.py` muta `sys.path` (`:9-10`) y depende de `asyncpg` con
   fallback JSON.
3. `human_review_required` en `ResultBuilder` usa umbral `confidence < 0.85`
   hardcodeado (duplica `UMBRAL_REVISION` de la UI).
4. `BackendResult.document_context` retiene el contexto completo (memoria).
5. Versión RC1 (`2.0.0-rc1`) hardcodeada en 2 lugares.

## Mejoras futuras

- Unificar el path FastAPI con `BackendRunner` (V2).
- Centralizar versiones y umbrales en config.
- Serializar `document_context` explícitamente (no retener el objeto).
