from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from .models import ProcessingState, LifecycleEvent


_ALLOWED_TRANSITIONS: dict[ProcessingState, list[ProcessingState]] = {
    ProcessingState.NEW: [ProcessingState.IDENTIFIED, ProcessingState.FAILED],
    ProcessingState.IDENTIFIED: [ProcessingState.STRUCTURED, ProcessingState.FAILED],
    ProcessingState.STRUCTURED: [ProcessingState.PARSED, ProcessingState.FAILED],
    ProcessingState.PARSED: [ProcessingState.CLASSIFIED, ProcessingState.FAILED],
    ProcessingState.CLASSIFIED: [ProcessingState.VALIDATED, ProcessingState.FAILED],
    ProcessingState.VALIDATED: [ProcessingState.REVIEWED, ProcessingState.FAILED],
    ProcessingState.REVIEWED: [ProcessingState.COMPLETED, ProcessingState.FAILED],
    ProcessingState.COMPLETED: [],
    ProcessingState.FAILED: [],
}

STATE_REQUIRED_DATA: dict[ProcessingState, list[str]] = {
    ProcessingState.NEW: [],
    ProcessingState.IDENTIFIED: ["identity", "metadata"],
    ProcessingState.STRUCTURED: ["identity", "metadata", "structure"],
    ProcessingState.PARSED: ["identity", "metadata", "structure", "parser"],
    ProcessingState.CLASSIFIED: ["identity", "metadata", "structure", "parser", "knowledge"],
    ProcessingState.VALIDATED: ["identity", "metadata", "structure", "parser", "knowledge", "validation"],
    ProcessingState.REVIEWED: ["identity", "metadata", "structure", "parser", "knowledge", "validation"],
    ProcessingState.COMPLETED: ["identity", "metadata", "structure", "parser", "knowledge", "validation"],
    ProcessingState.FAILED: ["identity"],
}


class LifecycleManager:

    def __init__(self):
        self._state: ProcessingState = ProcessingState.NEW
        self._events: list[LifecycleEvent] = []
        self._event_counter: int = 0

    @property
    def state(self) -> ProcessingState:
        return self._state

    @property
    def events(self) -> list[LifecycleEvent]:
        return list(self._events)

    @property
    def can_transition(self) -> bool:
        return not self._state.is_terminal

    def transition(
        self,
        to_state: ProcessingState,
        module: str = "",
        description: str = "",
        snapshot_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LifecycleEvent:
        if to_state == ProcessingState.FAILED:
            return self._create_event(to_state, module, description, snapshot_id, metadata)

        allowed = _ALLOWED_TRANSITIONS.get(self._state, [])
        if not allowed:
            raise LifecycleError(
                f"No se puede transicionar desde estado terminal {self._state.value}"
            )
        if to_state not in allowed:
            raise LifecycleError(
                f"Transición inválida: {self._state.value} → {to_state.value}. "
                f"Permitidas: {[s.value for s in allowed]}"
            )

        return self._create_event(to_state, module, description, snapshot_id, metadata)

    def _create_event(
        self,
        to_state: ProcessingState,
        module: str,
        description: str,
        snapshot_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> LifecycleEvent:
        from_state = self._state
        self._event_counter += 1
        event = LifecycleEvent(
            event_id=f"evt_{self._event_counter}_{datetime.now(timezone.utc).timestamp():.0f}",
            timestamp=datetime.now(timezone.utc),
            from_state=from_state if from_state != to_state else None,
            to_state=to_state,
            module=module,
            description=description,
            snapshot_id=snapshot_id,
            metadata=metadata or {},
        )
        self._events.append(event)
        self._state = to_state
        return event

    def last_event(self) -> LifecycleEvent | None:
        return self._events[-1] if self._events else None

    def events_by_module(self, module: str) -> list[LifecycleEvent]:
        return [e for e in self._events if e.module == module]

    def events_since(self, timestamp: datetime) -> list[LifecycleEvent]:
        return [e for e in self._events if e.timestamp >= timestamp]

    def required_data_for_state(self, state: ProcessingState | None = None) -> list[str]:
        target = state or self._state
        return STATE_REQUIRED_DATA.get(target, [])

    def reset(self) -> None:
        self._state = ProcessingState.NEW
        self._events.clear()
        self._event_counter = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self._state.value,
            "total_events": len(self._events),
            "events": [e.to_dict() for e in self._events],
        }


class LifecycleError(Exception):
    pass
