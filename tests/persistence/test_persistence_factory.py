from __future__ import annotations

import json
from pathlib import Path

import pytest

import persistence.factory as factory_module
from persistence import PersistenceSettings, build_persistence
from persistence.contracts import (
    LocalKnowledgeRepository,
    LocalProcessPersistence,
    PromotionPolicyRepository,
)
from persistence.contracts import ValidationDecision
from persistence.local import JsonKnowledgeRepository, LegacyNeonKnowledgeAdapter


class FakeNeonStore:
    def __init__(self) -> None:
        self.validation = None

    def healthcheck(self) -> bool:
        return True

    def load_catalog(self):
        return {"AC.01": {"nombre_estandar": "Caja y Bancos"}}

    def load_dictionary(self):
        return [{"cuenta_original": "Banco", "codigo_estandar": "AC.01"}]

    def save_validation(self, **value):
        self.validation = value

    def save_validations(self, values):
        self.validation = values


def _seeds(root: Path) -> tuple[Path, Path]:
    catalog = root / "seed-catalog.json"
    dictionary = root / "seed-dictionary.json"
    catalog.write_text(json.dumps({
        "AC.01": {
            "nombre_estandar": "Caja y Bancos",
            "categoria": "activo_corriente",
            "tipo_estado": "situacion",
            "naturaleza": "activo",
        },
    }), encoding="utf-8")
    dictionary.write_text(json.dumps([{
        "cuenta_original": "Banco",
        "codigo_estandar": "AC.01",
        "fuente": "seed",
    }]), encoding="utf-8")
    return catalog, dictionary


def test_default_settings_preserve_legacy_mode() -> None:
    settings = PersistenceSettings.from_environment({})
    assert settings.mode == "legacy_neon"
    assert settings.local_root is None
    assert settings.enable_operational_in_legacy is False


def test_default_factory_wraps_existing_neon_without_operational_side_effects(
    tmp_path,
) -> None:
    store = FakeNeonStore()
    bundle = build_persistence(legacy_neon_store=store)
    assert isinstance(bundle.knowledge, LegacyNeonKnowledgeAdapter)
    assert isinstance(bundle.knowledge, LocalKnowledgeRepository)
    assert bundle.knowledge.store is store
    assert not bundle.operational_enabled
    assert bundle.promotions is None
    assert list(tmp_path.iterdir()) == []


def test_local_mode_never_instantiates_neon(monkeypatch, tmp_path) -> None:
    catalog, dictionary = _seeds(tmp_path)

    class ForbiddenNeon:
        def __init__(self, *args, **kwargs):
            raise AssertionError("El modo local intentó instanciar Neon")

    monkeypatch.setattr(factory_module, "NeonKnowledgeStore", ForbiddenNeon)
    local_root = tmp_path / "runtime"
    settings = PersistenceSettings(
        mode="local",
        local_root=local_root,
        catalog_seed=catalog,
        dictionary_seed=dictionary,
    )
    bundle = build_persistence(settings)
    assert isinstance(bundle.knowledge, JsonKnowledgeRepository)
    assert bundle.operational_enabled
    assert isinstance(bundle.promotions, PromotionPolicyRepository)
    assert isinstance(bundle.processes, LocalProcessPersistence)
    assert bundle.knowledge.healthcheck()
    assert (local_root / "operational" / "operations.db").is_file()
    assert (local_root / "knowledge" / "catalogo_maestro.json").is_file()
    assert (local_root / "knowledge" / "diccionario.json").is_file()


def test_local_seed_is_not_overwritten_on_restart(tmp_path) -> None:
    catalog, dictionary = _seeds(tmp_path)
    local_root = tmp_path / "runtime"
    settings = PersistenceSettings(
        mode="local",
        local_root=local_root,
        catalog_seed=catalog,
        dictionary_seed=dictionary,
    )
    first = build_persistence(settings)
    local_dictionary = local_root / "knowledge" / "diccionario.json"
    local_dictionary.write_text("[]", encoding="utf-8")
    second = build_persistence(settings)
    assert first.operational_enabled and second.operational_enabled
    assert second.knowledge.load_dictionary() == []
    state = json.loads((local_root / "knowledge" / "seed-state.json").read_text())
    assert state["status"] == "activated"
    history = (
        local_root / "knowledge" / "history" / "seed-history.jsonl"
    ).read_text().splitlines()
    assert len(history) == 1


def test_local_knowledge_changes_live_only_in_durable_root(tmp_path) -> None:
    catalog_seed, dictionary_seed = _seeds(tmp_path)
    original_catalog_seed = catalog_seed.read_bytes()
    original_dictionary_seed = dictionary_seed.read_bytes()
    local_root = tmp_path / "runtime"
    settings = PersistenceSettings(
        mode="local", local_root=local_root,
        catalog_seed=catalog_seed, dictionary_seed=dictionary_seed,
    )
    first = build_persistence(settings)
    first.knowledge.save_catalog_entry({
        "codigo_estandar": "ER.90",
        "nombre_estandar": "Resultado no controlador",
        "categoria": "resultado",
        "tipo_estado": "resultados",
        "naturaleza": "ganancia",
    })
    first.knowledge.save_validation(ValidationDecision(
        account_name="Resultado atribuible no controlador",
        validated_code="ER.90",
        source="validacion_humana",
        reviewer="supervisor-1",
        add_to_dictionary=True,
    ))

    reopened = build_persistence(settings)
    assert "ER.90" in reopened.knowledge.load_catalog()
    assert any(
        row["cuenta_original"] == "Resultado atribuible no controlador"
        for row in reopened.knowledge.load_dictionary()
    )
    assert catalog_seed.read_bytes() == original_catalog_seed
    assert dictionary_seed.read_bytes() == original_dictionary_seed


def test_changed_local_seed_is_recorded_pending_without_overwrite(tmp_path) -> None:
    catalog, dictionary = _seeds(tmp_path)
    local_root = tmp_path / "runtime"
    settings = PersistenceSettings(
        mode="local", local_root=local_root,
        catalog_seed=catalog, dictionary_seed=dictionary,
        master_bundle_version="v1",
    )
    build_persistence(settings)
    local_dictionary = local_root / "knowledge" / "diccionario.json"
    local_dictionary.write_text("[]", encoding="utf-8")
    dictionary.write_text(json.dumps([{
        "cuenta_original": "Otra", "codigo_estandar": "AC.01", "fuente": "v2",
    }]), encoding="utf-8")
    build_persistence(PersistenceSettings(
        mode="local", local_root=local_root,
        catalog_seed=catalog, dictionary_seed=dictionary,
        master_bundle_version="v2",
    ))
    assert json.loads(local_dictionary.read_text()) == []
    events = [json.loads(line) for line in (
        local_root / "knowledge" / "history" / "seed-history.jsonl"
    ).read_text().splitlines()]
    assert [event["status"] for event in events] == ["activated", "update_pending"]


def test_legacy_mode_can_enable_only_new_operational_storage(tmp_path) -> None:
    settings = PersistenceSettings(
        mode="legacy_neon",
        local_root=tmp_path / "operational-runtime",
        enable_operational_in_legacy=True,
    )
    store = FakeNeonStore()
    bundle = build_persistence(settings, legacy_neon_store=store)
    assert isinstance(bundle.knowledge, LegacyNeonKnowledgeAdapter)
    assert bundle.operational_enabled
    assert bundle.knowledge.store is store
    assert isinstance(bundle.promotions, PromotionPolicyRepository)
    assert isinstance(bundle.processes, LocalProcessPersistence)


@pytest.mark.parametrize("mode", ["remote", "neon", "sqlite"])
def test_unknown_modes_fail_closed(mode) -> None:
    with pytest.raises(ValueError, match="PERSISTENCE_MODE inválido"):
        PersistenceSettings.from_environment({"PERSISTENCE_MODE": mode})


def test_local_mode_requires_explicit_root() -> None:
    with pytest.raises(ValueError, match="LOCAL_PERSISTENCE_ROOT"):
        PersistenceSettings.from_environment({"PERSISTENCE_MODE": "local"})


def test_invalid_boolean_fails_closed() -> None:
    with pytest.raises(ValueError, match="booleano"):
        PersistenceSettings.from_environment({
            "ENABLE_OPERATIONAL_PERSISTENCE": "sometimes",
        })


def test_no_credentials_are_defined_by_factory() -> None:
    source = (Path(factory_module.__file__)).read_text(encoding="utf-8")
    forbidden = (
        "POSTGRES_PASSWORD=",
        "DATABASE_URL=postgres",
        "LICENSE_KEY=",
        "API_TOKEN=",
    )
    assert not any(value in source for value in forbidden)
