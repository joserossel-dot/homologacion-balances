"""Sonda sin datos contables para verificar la persistencia efectiva on-prem."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from persistence.contracts import AuditEvent
from persistence.factory import PersistenceSettings, build_persistence


SUBJECT_ID = "0" * 32


def inspect(*, write_marker: bool = False) -> dict[str, object]:
    settings = PersistenceSettings.from_environment()
    bundle = build_persistence(settings)
    if settings.mode != "local" or not bundle.operational_enabled:
        raise RuntimeError("La sonda exige el bundle local operacional completo.")
    if bundle.audit is None:
        raise RuntimeError("Repositorio local de auditoría no disponible.")
    if write_marker:
        bundle.audit.append(AuditEvent(
            event_id=None,
            occurred_at=datetime.now(timezone.utc),
            actor_id="onprem-smoke",
            action="PERSISTENCE_PROBE",
            subject_type="installation",
            subject_id=SUBJECT_ID,
            details={"contains_accounting_data": False},
        ))
    events = bundle.audit.list_for_subject("installation", SUBJECT_ID)
    return {
        "mode": settings.mode,
        "operational_enabled": bundle.operational_enabled,
        "knowledge_healthy": bundle.knowledge.healthcheck(),
        "catalog_entries": len(bundle.knowledge.load_catalog()),
        "dictionary_entries": len(bundle.knowledge.load_dictionary()),
        "audit_markers": sum(event.action == "PERSISTENCE_PROBE" for event in events),
        "repositories": {
            name: getattr(bundle, name) is not None
            for name in (
                "documents", "executions", "audit", "users", "reports", "promotions"
            )
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-marker", action="store_true")
    args = parser.parse_args()
    print(json.dumps(inspect(write_marker=args.write_marker), sort_keys=True))


if __name__ == "__main__":
    main()
