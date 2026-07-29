from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from .models import ContextSnapshot, ProcessingState


class SnapshotManager:

    def __init__(self):
        self._snapshots: list[ContextSnapshot] = []

    @property
    def snapshots(self) -> list[ContextSnapshot]:
        return list(self._snapshots)

    @property
    def count(self) -> int:
        return len(self._snapshots)

    def create(
        self,
        label: str,
        state: ProcessingState,
        data: dict[str, Any],
    ) -> ContextSnapshot:
        snap = ContextSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            label=label,
            state=state,
            timestamp=datetime.now(timezone.utc),
            data=copy.deepcopy(data),
        )
        self._snapshots.append(snap)
        return snap

    def get(self, snapshot_id: str) -> ContextSnapshot | None:
        for s in self._snapshots:
            if s.snapshot_id == snapshot_id:
                return s
        return None

    def by_label(self, label: str) -> list[ContextSnapshot]:
        return [s for s in self._snapshots if s.label == label]

    def by_state(self, state: ProcessingState) -> list[ContextSnapshot]:
        return [s for s in self._snapshots if s.state == state]

    def last(self) -> ContextSnapshot | None:
        return self._snapshots[-1] if self._snapshots else None

    def diff(self, id_a: str, id_b: str) -> dict[str, Any]:
        snap_a = self.get(id_a)
        snap_b = self.get(id_b)
        if not snap_a or not snap_b:
            raise SnapshotNotFoundError(
                f"Snapshots no encontrados: {id_a}={snap_a is not None}, {id_b}={snap_b is not None}"
            )
        return _deep_diff(snap_a.data, snap_b.data)

    def clear(self) -> None:
        self._snapshots.clear()


def _deep_diff(a: dict, b: dict, path: str = "") -> dict[str, Any]:
    changes: dict[str, Any] = {"added": {}, "removed": {}, "changed": {}}
    all_keys = set(a.keys()) | set(b.keys())

    for key in sorted(all_keys):
        full_key = f"{path}.{key}" if path else key
        va = a.get(key)
        vb = b.get(key)

        if key not in a:
            changes["added"][full_key] = vb
        elif key not in b:
            changes["removed"][full_key] = va
        elif isinstance(va, dict) and isinstance(vb, dict):
            sub = _deep_diff(va, vb, full_key)
            if any(sub.values()):
                changes["changed"][full_key] = sub
        elif isinstance(va, list) and isinstance(vb, list):
            if va != vb:
                changes["changed"][full_key] = {"from": va, "to": vb}
        elif va != vb:
            changes["changed"][full_key] = {"from": va, "to": vb}

    return {k: v for k, v in changes.items() if v}


class SnapshotNotFoundError(Exception):
    pass
