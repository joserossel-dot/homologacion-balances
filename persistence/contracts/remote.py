"""Clientes remotos del plano de control, separados de persistencia local."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


_ALLOWED_TELEMETRY_METRICS = frozenset({
    "pages",
    "accounts",
    "ocr_used",
    "manual_reviews",
    "duration_ms",
    "warnings",
    "errors",
})


@dataclass(frozen=True, slots=True)
class LicenseGrant:
    organization_id: str
    node_id: str
    issued_at: datetime
    expires_at: datetime
    grace_until: datetime
    capabilities: tuple[str, ...]
    signed_token: str


@dataclass(frozen=True, slots=True)
class MasterBundleManifest:
    version: str
    minimum_application_version: str
    maximum_application_version: str | None
    sha256: str
    signature: str
    download_reference: str


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    event_type: str
    organization_id: str
    node_id: str
    application_version: str
    master_bundle_version: str
    occurred_at: datetime
    metrics: dict[str, int | float | bool] = field(default_factory=dict)


@runtime_checkable
class LicenseClient(Protocol):
    def activate(self, *, node_id: str, activation_code: str) -> LicenseGrant: ...

    def renew(self, current_token: str) -> LicenseGrant: ...


@runtime_checkable
class MasterDataClient(Protocol):
    def latest_manifest(self, *, channel: str) -> MasterBundleManifest | None: ...

    def download(self, manifest: MasterBundleManifest) -> bytes: ...


@runtime_checkable
class TelemetryClient(Protocol):
    def send(self, event: TelemetryEvent) -> None: ...


def telemetry_as_closed_payload(event: TelemetryEvent) -> dict[str, Any]:
    """Serialización explícita; no admite campos documentales libres."""
    unknown = set(event.metrics) - _ALLOWED_TELEMETRY_METRICS
    if unknown:
        raise ValueError(
            "Métricas de telemetría no permitidas: " + ", ".join(sorted(unknown))
        )
    invalid_types = [
        name for name, value in event.metrics.items()
        if not isinstance(value, (int, float, bool))
    ]
    if invalid_types:
        raise TypeError(
            "Métricas de telemetría con tipo inválido: "
            + ", ".join(sorted(invalid_types))
        )
    return {
        "schema_version": 1,
        "event_type": event.event_type,
        "organization_id": event.organization_id,
        "node_id": event.node_id,
        "application_version": event.application_version,
        "master_bundle_version": event.master_bundle_version,
        "occurred_at": event.occurred_at.isoformat(),
        "metrics": dict(event.metrics),
    }
