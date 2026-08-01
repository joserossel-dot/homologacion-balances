# Backend Architecture — RC1

## Overview

The backend is the **single official execution path** for Homologación de Balances.
UI (Streamlit), API (FastAPI future), CLI (`run_pipeline_v2.py`), Batch, and Docker
**must all use exactly this same backend**.

## Directory Structure

```
backend/
├── __init__.py
├── config.py              # BackendConfig — paths, log level, feature control
├── backend_logger.py      # BackendLogger — structured logging (console + file)
├── backend_models.py      # BackendResult, BackendStatistics, ExecutionMetrics
├── pipeline_runner.py     # PipelineRunner — orchestrates HomologationPipelineV2
├── execution_manager.py   # ExecutionManager — start/finish/error/rollback/cancel/progress
├── artifact_manager.py    # ArtifactManager — saves runs/YYYY-MM-DD/HHMMSS/ artifacts
├── result_builder.py      # ResultBuilder — creates BackendResult from DocumentContext
└── runner.py              # BackendRunner — high-level entry point

observability/
├── __init__.py
└── collector.py           # ObservabilityCollector — module timings, metrics, reports

config/
├── __init__.py
├── regex_rules.py         # REGLAS_REGEX, REGLAS_COMPILADAS (shared, no circular dep)
├── features.yaml          # Feature flags (hot-reload, no recompile)
└── features.py            # FeatureFlags loader

run_pipeline_v2.py          # CLI entry point
smoke_test.py               # Integration smoke test
```

## Data Flow

```
run_pipeline_v2.py
      │
      ▼
BackendRunner
  ├── BackendConfig
  ├── BackendLogger
  ├── ExecutionManager
  ├── HomologationPipelineV2
  ├── ArtifactManager
  └── ResultBuilder
      │
      ▼
PipelineRunner.run(file_path)
  ├── ExecutionManager.start()
  ├── HomologationPipelineV2.process(path)
  │     ├── SIEAdapter
  │     ├── DIEAdapter
  │     ├── ParserAdapter
  │     ├── KBAdapter
  │     ├── DecisionAdapter
  │     ├── CoverageAdapter
  │     ├── SelfQAAdapter
  │     ├── ReviewAdapter
  │     └── ExportAdapter (via ArtifactManager)
  ├── ArtifactManager.save_all(result)
  └── ResultBuilder.build(ctx, metrics, logs) → BackendResult
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Single BackendRunner | Every client uses the same code path |
| ArtifactManager saves all outputs | Reproducibility per run |
| ExecutionManager tracks everything | Observability without instrumenting engines |
| BackendResult contains everything | Clients don't need to parse DocumentContext |
| FeatureFlags from YAML | Toggle engines without redeploy |
| No Streamlit dependency | Pure Python — runs anywhere |
