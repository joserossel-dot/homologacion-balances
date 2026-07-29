from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BackendLogger:
    def __init__(self, name: str = "backend", level: str = "INFO", log_dir: Path | None = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.handlers.clear()

        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        self.logger.addHandler(sh)

        self._log_dir = log_dir
        self._entries: list[dict[str, Any]] = []

    @property
    def log_dir(self) -> Path | None:
        return self._log_dir

    @log_dir.setter
    def log_dir(self, path: Path) -> None:
        self._log_dir = path
        self._log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(self._log_dir / "backend.log"), encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        self.logger.addHandler(fh)

    def info(self, msg: str, **extra) -> None:
        self.logger.info(msg)
        self._log("INFO", msg, extra)

    def warning(self, msg: str, **extra) -> None:
        self.logger.warning(msg)
        self._log("WARNING", msg, extra)

    def error(self, msg: str, **extra) -> None:
        self.logger.error(msg)
        self._log("ERROR", msg, extra)

    def debug(self, msg: str, **extra) -> None:
        self.logger.debug(msg)
        self._log("DEBUG", msg, extra)

    def _log(self, level: str, msg: str, extra: dict) -> None:
        self._entries.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": msg,
            "extra": extra,
        })

    def get_entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def to_dict(self) -> list[dict[str, Any]]:
        return self.get_entries()

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(self._entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
