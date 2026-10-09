"""Shared controls for the internal no-write pilot."""

from __future__ import annotations

import os


_PILOT_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def pilot_mode_active() -> bool:
    """Return whether the process is running under the explicit pilot guard."""
    return os.environ.get("PILOT_MODE", "").strip().lower() in _PILOT_TRUE_VALUES
