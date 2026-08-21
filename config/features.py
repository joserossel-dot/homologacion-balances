from __future__ import annotations

from pathlib import Path
from typing import Any


class FeatureFlags:
    def __init__(self, flags: dict[str, bool] | None = None):
        self._flags: dict[str, bool] = {
            "document_intelligence": True,
            "structure_engine": True,
            "knowledge_base": True,
            "decision_engine": True,
            "coverage_engine": True,
            "self_qa_engine": True,
            "validation": True,
            "review_workspace": True,
            "export_excel": True,
            "export_markdown": True,
            "export_json": True,
        }
        if flags:
            self._flags.update(flags)

    def is_enabled(self, name: str) -> bool:
        return self._flags.get(name, True)

    def __getattr__(self, name: str) -> bool:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._flags.get(name, True)

    def to_dict(self) -> dict[str, bool]:
        return dict(self._flags)

    @classmethod
    def load(cls, path: str | Path = "config/features.yaml") -> FeatureFlags:
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return cls({k: bool(v) for k, v in data.items()})
        except Exception:
            return cls()

    def save(self, path: str | Path = "config/features.yaml") -> None:
        import yaml
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._flags, f, default_flow_style=False, allow_unicode=True)
