from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Any


class StageStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass
class StageResult:
    stage_id: str
    stage_name: str
    status: StageStatus
    duration: float
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict:
        return {
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "status": self.status.value,
            "duration": round(self.duration, 3),
            "errors": self.errors,
            "warnings": self.warnings,
            "artifacts": {k: (str(v) if not isinstance(v, (int, float, bool, type(None), list, dict)) else v) for k, v in self.artifacts.items()},
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @staticmethod
    def make(stage_id: str, stage_name: str) -> StageResult:
        return StageResult(
            stage_id=stage_id,
            stage_name=stage_name,
            status=StageStatus.PENDING,
            duration=0.0,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    def succeed(self, artifacts: dict | None = None) -> StageResult:
        self.status = StageStatus.PASS
        self.finished_at = datetime.now(timezone.utc).isoformat()
        if artifacts:
            self.artifacts.update(artifacts)
        return self

    def fail(self, errors: list[str], artifacts: dict | None = None) -> StageResult:
        self.status = StageStatus.FAIL
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.errors = errors
        if artifacts:
            self.artifacts.update(artifacts)
        return self

    def skip(self, reason: str = "") -> StageResult:
        self.status = StageStatus.SKIPPED
        self.finished_at = datetime.now(timezone.utc).isoformat()
        if reason:
            self.warnings.append(reason)
        return self

    def error(self, msg: str) -> StageResult:
        self.status = StageStatus.ERROR
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.errors.append(msg)
        return self
