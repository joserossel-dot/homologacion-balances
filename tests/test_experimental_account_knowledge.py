"""Safety checks for the disconnected knowledge prototype, not accounting Gold."""

from copy import deepcopy

from account_name_normalizer import AccountNameNormalizer, DEFAULT_CONFIG
from special_account_rules import SpecialAccountRules


def test_custom_configuration_does_not_change_defaults_or_other_instances():
    before = deepcopy(DEFAULT_CONFIG)
    existing = AccountNameNormalizer()
    overrides = {"abreviaciones": {"custom": "cuenta personalizada"}}
    custom = AccountNameNormalizer(overrides)
    overrides["abreviaciones"]["custom"] = "mutacion externa"

    assert custom.normalizar("CUSTOM") == "cuenta personalizada"
    assert existing.normalizar("CUSTOM") == "custom"
    assert AccountNameNormalizer().normalizar("CUSTOM") == "custom"
    assert DEFAULT_CONFIG == before


def test_configuration_sets_are_not_shared():
    first = AccountNameNormalizer()
    second = AccountNameNormalizer()
    first.config["stopwords"].add("caja")
    assert second.normalizar("Caja", quitar_stopwords=True) == "caja"
    assert "caja" not in DEFAULT_CONFIG["stopwords"]


def test_default_normalization_keeps_accounting_qualifiers():
    normalizer = AccountNameNormalizer()
    pairs = [
        ("Cuentas por cobrar", "Cuentas por pagar"),
        ("Activo corriente", "Activo no corriente"),
        ("Depreciación acumulada", "Depreciación del ejercicio"),
        ("Impuesto diferido activo", "Impuesto diferido pasivo"),
    ]
    for first, second in pairs:
        assert normalizer.normalizar(first) != normalizer.normalizar(second)
    assert normalizer.normalizar("Impuestos", plural=True) == "impuesto"


def test_experimental_detector_retains_conflicting_candidates():
    rules = SpecialAccountRules([
        {
            "codigo": code, "concepto": code, "nombre": code,
            "patrones": ["cuenta experimental"], "confianza": 0.95,
            "explicacion": "Fixture sintético", "motivo": "Conflicto",
        }
        for code in ("AC.01", "PC.01")
    ])
    assert {result["codigo"] for result in rules.detectar("Cuenta experimental")} == {
        "AC.01", "PC.01",
    }
    assert rules.detectar("Cuenta desconocida") == []
