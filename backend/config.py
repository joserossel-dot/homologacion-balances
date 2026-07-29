from __future__ import annotations

from pathlib import Path
from typing import Any

BACKEND_VERSION = "2.0.0-rc1"


class BackendConfig:
    runs_dir: Path = Path("runs")
    artifacts_enabled: bool = True
    log_level: str = "INFO"
    db_path: Path = Path("gold_standard.db")
    export_excel: bool = True
    export_markdown: bool = True
    export_json: bool = True

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.runs_dir = Path(self.runs_dir)

    @classmethod
    def default(cls) -> BackendConfig:
        return cls()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BackendConfig:
        return cls(**d)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runs_dir": str(self.runs_dir),
            "artifacts_enabled": self.artifacts_enabled,
            "log_level": self.log_level,
            "db_path": str(self.db_path),
            "export_excel": self.export_excel,
            "export_markdown": self.export_markdown,
            "export_json": self.export_json,
        }
