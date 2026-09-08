"""Validación cerrada de parámetros de despliegue on-premise."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

from persistence.factory import PersistenceSettings, build_persistence


IMMUTABLE_IMAGE = re.compile(r"^[^\s@]+@sha256:[a-f0-9]{64}$")
IMAGE_VARIABLES = (
    "APP_IMAGE_REFERENCE",
    "POSTGRES_IMAGE",
    "CADDY_IMAGE",
    "CADDY_INIT_IMAGE",
)


def validate(environment: Mapping[str, str] | None = None) -> None:
    values = os.environ if environment is None else environment
    if values.get("PERSISTENCE_MODE", "").strip().lower() != "local":
        raise ValueError("On-premise exige PERSISTENCE_MODE=local")
    root = values.get("LOCAL_PERSISTENCE_ROOT", "").strip()
    if not root or not Path(root).is_absolute():
        raise ValueError("LOCAL_PERSISTENCE_ROOT debe ser una ruta absoluta durable")
    if values.get("DATABASE_URL", "").strip():
        raise ValueError("On-premise local no permite DATABASE_URL en app/bootstrap")
    if values.get("ONPREM_JSON_FALLBACK", "disabled").strip().lower() != "disabled":
        raise ValueError("ONPREM_JSON_FALLBACK debe permanecer disabled")
    mode = values.get("ONPREM_DEPLOYMENT_MODE", "production").strip().lower()
    if mode not in {"production", "evaluation"}:
        raise ValueError("ONPREM_DEPLOYMENT_MODE debe ser production o evaluation")
    if mode == "evaluation":
        return
    mutable = [
        name for name in IMAGE_VARIABLES
        if not IMMUTABLE_IMAGE.fullmatch(values.get(name, "").strip())
    ]
    if mutable:
        raise ValueError(
            "Producción exige imágenes fijadas por digest SHA-256: "
            + ", ".join(mutable)
        )
    if values.get("AUTH_ENFORCEMENT", "deny").strip().lower() != "forward_auth":
        raise ValueError("Producción exige AUTH_ENFORCEMENT=forward_auth")
    if values.get("CADDYFILE_PATH", "./Caddyfile.production").strip() != (
        "./Caddyfile.production"
    ):
        raise ValueError("Producción exige CADDYFILE_PATH=./Caddyfile.production")
    if values.get("BACKUP_ENCRYPTION_REQUIRED", "true").strip().lower() != "true":
        raise ValueError("Producción exige BACKUP_ENCRYPTION_REQUIRED=true")


def validate_runtime_persistence(
    environment: Mapping[str, str] | None = None,
) -> None:
    settings = PersistenceSettings.from_environment(environment)
    if settings.mode != "local":
        raise ValueError("La persistencia efectiva no es local")
    bundle = build_persistence(settings)
    if not bundle.knowledge.healthcheck():
        raise ValueError("El catálogo o diccionario local no está disponible")
    missing = [
        name for name in (
            "documents", "executions", "audit", "users", "reports", "promotions",
        )
        if getattr(bundle, name) is None
    ]
    if missing:
        raise ValueError(
            "Repositorios operacionales locales no habilitados: " + ", ".join(missing)
        )


if __name__ == "__main__":
    try:
        validate()
        validate_runtime_persistence()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Preflight on-premise rechazado: {exc}") from exc
