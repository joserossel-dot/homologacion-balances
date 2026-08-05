from __future__ import annotations

from core.normalizer import normalize


def test_default_removes_accents_symbols_and_collapses() -> None:
    assert normalize("Vehículos") == "vehiculos"
    assert normalize("Muebles y Útiles") == "muebles y utiles"
    assert normalize("Provisión Vacaciones") == "provision vacaciones"
    assert normalize("Cta.Cte. Socios") == "cta cte socios"
    assert normalize("IVA CRÉDITO FISCAL!") == "iva credito fiscal"
    assert normalize("Caja   y  Bancos") == "caja y bancos"


def test_default_converts_enye_and_umlaut() -> None:
    assert normalize("CAÑA") == "cana"
    assert normalize("Señor") == "senor"
    assert normalize("ñandú") == "nandu"
    assert normalize("Übung") == "ubung"


def test_default_keeps_underscore_as_word_char() -> None:
    assert normalize("a_b") == "a_b"


def test_preserve_enye_keeps_n_tilde() -> None:
    assert normalize("CAÑA", preserve_enye=True) == "caña"
    assert normalize("Señor", preserve_enye=True) == "señor"


def test_remove_accents_false_keeps_accents() -> None:
    assert normalize("Vehículos", remove_accents=False) == "vehículos"
    assert normalize("Señor", remove_accents=False) == "señor"


def test_remove_symbols_false_keeps_symbols() -> None:
    assert normalize("Cta.Cte. Socios", remove_symbols=False) == "cta.cte. socios"


def test_layout_validation_mode() -> None:
    assert normalize("Cta.Cte. Socios", remove_accents=False, remove_symbols=False) == "cta.cte. socios"
    assert normalize("Señor  Pérez", remove_accents=False, remove_symbols=False) == "señor pérez"


def test_collapse_spaces_false_keeps_inner_spaces() -> None:
    assert normalize("Caja   y  Bancos", collapse_spaces=False) == "caja   y  bancos"


def test_lowercase_false_preserves_case() -> None:
    assert normalize("IVA CRÉDITO", lowercase=False) == "IVA CREDITO"


def test_empty_and_none() -> None:
    assert normalize("") == ""
    assert normalize("   ") == ""
    assert normalize(None) == ""


def test_equivalence_with_legacy_reports_family() -> None:
    probes = [
        "Vehículos", "Muebles y Útiles", "Provisión Vacaciones",
        "Corrección Monetaria", "Depreciación", "IVA CRÉDITO FISCAL!",
        "Cta.Cte. Socios", "Caja   y  Bancos", "100%", "R.P.P. y H.",
        "DISPONIBLE",
    ]
    for p in probes:
        assert normalize(p) == _legacy_ascii_normalize(p)


def _legacy_ascii_normalize(nombre: str) -> str:
    import re
    import unicodedata

    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = nombre.encode("ascii", "ignore").decode("ascii")
    nombre = re.sub(r"[^\w\s]", " ", nombre)
    return re.sub(r"\s+", " ", nombre).strip().lower()
