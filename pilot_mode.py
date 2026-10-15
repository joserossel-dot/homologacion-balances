"""Shared controls for the internal no-write pilot."""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import MutableMapping


_PILOT_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class PilotTempDirectoryStatus:
    """Safe result of the pilot temporary-directory preflight.

    ``code`` is deliberately path-free so it can be rendered in a UI or a
    diagnostic without disclosing a customer-storage location.
    """

    ready: bool
    code: str


def _repository_root() -> Path:
    """Return the repository root without relying on the caller's cwd."""
    return Path(__file__).resolve().parent


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def pilot_mode_active() -> bool:
    """Return whether the process is running under the explicit pilot guard."""
    return os.environ.get("PILOT_MODE", "").strip().lower() in _PILOT_TRUE_VALUES


def validate_pilot_tempdir(
    configured: str | None = None,
    *,
    environ: MutableMapping[str, str] | None = None,
    repo_root: Path | str | None = None,
) -> PilotTempDirectoryStatus:
    """Validate the explicit, restricted temporary directory for a pilot.

    The function does not create, modify, or disclose the directory.  It
    resolves both the configured location and repository root before comparing
    them, so a symlink cannot place pilot temporaries inside the repository.
    """
    active_environ = os.environ if environ is None else environ
    raw_value = configured if configured is not None else active_environ.get(
        "PILOT_TMPDIR",
    )
    if not isinstance(raw_value, str) or not raw_value.strip():
        return PilotTempDirectoryStatus(False, "missing")

    try:
        candidate = Path(raw_value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return PilotTempDirectoryStatus(False, "unavailable")

    if not candidate.is_dir():
        return PilotTempDirectoryStatus(False, "not_directory")

    try:
        root = Path(repo_root).expanduser().resolve(strict=True) if repo_root else _repository_root()
    except (OSError, RuntimeError, ValueError):
        # The process must not fall back to an unbounded temporary location if
        # it cannot establish the repository boundary.
        return PilotTempDirectoryStatus(False, "repository_boundary_unavailable")

    if _is_within(candidate, root):
        return PilotTempDirectoryStatus(False, "inside_repository")

    try:
        mode = stat.S_IMODE(candidate.stat().st_mode)
    except OSError:
        return PilotTempDirectoryStatus(False, "unavailable")

    # A directory needs owner rwx for PDF/PNG temporaries.  Group and other
    # permissions must be absent, which accepts 0700 and restrictive variants
    # with special bits while rejecting 0750/0755 and similar modes.
    if (mode & 0o700) != 0o700 or (mode & 0o077):
        return PilotTempDirectoryStatus(False, "insecure_permissions")

    return PilotTempDirectoryStatus(True, "ready")


def configure_pilot_tempdir(
    *,
    environ: MutableMapping[str, str] | None = None,
    repo_root: Path | str | None = None,
    tempfile_module=tempfile,
) -> PilotTempDirectoryStatus:
    """Bind Python and subprocess temporary-file settings to ``PILOT_TMPDIR``.

    Outside pilot mode this is an intentional no-op.  In pilot mode no state is
    changed until the directory passes every validation, so a bad setting cannot
    redirect temporary writes to the repository or a system-default location.
    """
    if not pilot_mode_active():
        return PilotTempDirectoryStatus(True, "not_required")

    active_environ = os.environ if environ is None else environ
    status = validate_pilot_tempdir(environ=active_environ, repo_root=repo_root)
    if not status.ready:
        return status

    # Re-resolve only after validation.  The directory is not created here.
    configured = Path(active_environ["PILOT_TMPDIR"]).expanduser().resolve(
        strict=True,
    )
    destination = str(configured)
    tempfile_module.tempdir = destination
    for variable in ("TMPDIR", "TMP", "TEMP"):
        active_environ[variable] = destination
    return status
