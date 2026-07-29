from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.pipeline_v2 import HomologationPipelineV2

from backend.config import BackendConfig
from backend.backend_logger import BackendLogger
from backend.execution_manager import ExecutionManager
from backend.artifact_manager import ArtifactManager
from backend.result_builder import ResultBuilder
from backend.pipeline_runner import PipelineRunner
from backend.backend_models import BackendResult


class BackendRunner:
    def __init__(self, config: BackendConfig | dict[str, Any] | None = None):
        if isinstance(config, dict):
            self.config = BackendConfig.from_dict(config)
        elif config is None:
            self.config = BackendConfig.default()
        else:
            self.config = config

        self.logger = BackendLogger(level=self.config.log_level)
        self.execution_manager = ExecutionManager()
        self.artifact_manager = ArtifactManager(self.config.runs_dir)
        self.result_builder = ResultBuilder()

        self.pipeline = HomologationPipelineV2(
            db_path=str(self.config.db_path),
        )

        self.runner = PipelineRunner(
            pipeline=self.pipeline,
            execution_manager=self.execution_manager,
            logger=self.logger,
            artifact_manager=self.artifact_manager,
            result_builder=self.result_builder,
            config=self.config,
        )

    def run(self, file_path: str | Path) -> BackendResult:
        return self.runner.run(file_path)
