from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from document_context import DocumentContext
from orchestrator.pipeline_v2 import HomologationPipelineV2

from backend.execution_manager import ExecutionManager
from backend.backend_logger import BackendLogger
from backend.backend_models import BackendResult
from backend.artifact_manager import ArtifactManager
from backend.result_builder import ResultBuilder
from backend.config import BackendConfig


class PipelineRunner:
    def __init__(
        self,
        pipeline: HomologationPipelineV2,
        execution_manager: ExecutionManager,
        logger: BackendLogger,
        artifact_manager: ArtifactManager,
        result_builder: ResultBuilder,
        config: BackendConfig | None = None,
    ):
        self._pipeline = pipeline
        self._em = execution_manager
        self._log = logger
        self._artifact_manager = artifact_manager
        self._result_builder = result_builder
        self._config = config or BackendConfig.default()

    def run(self, file_path: str | Path) -> BackendResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        self._em.start()
        self._log.info(f"Starting pipeline for {file_path}")

        try:
            self._em.module_start("pipeline_v2")
            t0 = time.perf_counter()
            ctx = self._pipeline.process(str(path))
            elapsed = time.perf_counter() - t0
            self._em.module_end("pipeline_v2", elapsed)
            self._log.info(f"Pipeline completed in {elapsed:.3f}s", module="pipeline_v2")
        except Exception as e:
            self._em.error("pipeline_v2", str(e))
            self._em.complete()
            raise

        logs = self._log.to_dict()
        export_paths: dict[str, str] = {}

        result = self._result_builder.build(ctx, self._em.metrics, logs, export_paths)

        if self._config.artifacts_enabled:
            self._em.progress(0.9, "Saving artifacts")
            try:
                self._em.module_start("artifacts")
                ta = time.perf_counter()
                export_paths = self._artifact_manager.save_all(result)
                result.export_paths = export_paths
                self._em.module_end("artifacts", time.perf_counter() - ta)
            except Exception as e:
                self._log.warning(f"Artifact save failed: {e}")

        self._em.complete()
        self._em.progress(1.0, "Done")

        return result
