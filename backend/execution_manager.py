from __future__ import annotations

import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backend.backend_models import ExecutionMetrics


class ExecutionManager:
    def __init__(self):
        self._metrics = ExecutionMetrics()
        self._cancelled = threading.Event()
        self._callbacks: dict[str, list[Callable]] = {
            "start": [],
            "module_start": [],
            "module_end": [],
            "progress": [],
            "error": [],
            "complete": [],
        }

    @property
    def metrics(self) -> ExecutionMetrics:
        return self._metrics

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def on(self, event: str, callback: Callable) -> None:
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def start(self) -> None:
        self._metrics.start_time = datetime.now(timezone.utc)
        self._metrics.status = "running"
        self._emit("start")

    def module_start(self, name: str) -> None:
        self._emit("module_start", name=name)

    def module_end(self, name: str, elapsed: float, error: str | None = None) -> None:
        self._metrics.module_timings[name] = round(elapsed, 4)
        if error:
            self._metrics.errors.append({
                "module": name,
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        self._emit("module_end", name=name, elapsed=elapsed, error=error)

    def progress(self, pct: float, message: str = "") -> None:
        self._emit("progress", progress=pct, message=message)

    def error(self, module: str, msg: str) -> None:
        self._metrics.errors.append({
            "module": module,
            "error": msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._emit("error", module=module, error=msg)

    def complete(self) -> None:
        self._metrics.end_time = datetime.now(timezone.utc)
        self._metrics.elapsed_seconds = (self._metrics.end_time - self._metrics.start_time).total_seconds()
        self._metrics.status = "completed" if not self._metrics.errors else "failed"
        self._emit("complete", status=self._metrics.status)

    def cancel(self) -> None:
        self._cancelled.set()
        self._metrics.status = "cancelled"

    def rollback(self) -> None:
        self._metrics.status = "rollback"
        self._emit("complete", status="rollback")

    def _emit(self, event: str, **data) -> None:
        for cb in self._callbacks.get(event, []):
            try:
                cb(**data)
            except Exception:
                pass
