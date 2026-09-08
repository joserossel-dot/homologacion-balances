"""Inicializa y comprueba la persistencia local durable on-premise."""

from __future__ import annotations

from persistence.factory import PersistenceSettings, build_persistence


def main() -> None:
    settings = PersistenceSettings.from_environment()
    if settings.mode != "local":
        raise RuntimeError("El bootstrap on-premise exige PERSISTENCE_MODE=local.")
    bundle = build_persistence(settings)
    if not bundle.knowledge.healthcheck() or not bundle.operational_enabled:
        raise RuntimeError("La persistencia local no habilitó todos sus repositorios.")
    catalog_count = len(bundle.knowledge.load_catalog())
    dictionary_count = len(bundle.knowledge.load_dictionary())
    print(
        "Base local inicializada: "
        f"catalogo={catalog_count}, diccionario={dictionary_count}, "
        f"version={settings.master_bundle_version}, operacional=habilitado."
    )


if __name__ == "__main__":
    main()
