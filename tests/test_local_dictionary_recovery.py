from __future__ import annotations

import json
from pathlib import Path

from app_validacion import _codigo_compatible_con_origen, normalizar_nombre


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECOVERED_CODES = {
    "pagos provisionales mensuales": "AC.07",
    "agua": "ER.04",
    "electricidad": "ER.04",
    "gratificación": "ER.04",
    "aporte patronal": "ER.04",
}


def _dictionary() -> list[dict[str, str]]:
    return json.loads((PROJECT_ROOT / "diccionario.json").read_text(encoding="utf-8"))


def test_local_dictionary_retains_recovered_human_entries():
    dictionary = _dictionary()
    mapping = {
        normalizar_nombre(entry["cuenta_original"]): entry["codigo_estandar"]
        for entry in dictionary
    }

    assert len(dictionary) >= 941
    for account_name, code in RECOVERED_CODES.items():
        assert mapping[account_name] == code


def test_recovered_entries_remain_subject_to_origin_compatibility():
    assert _codigo_compatible_con_origen(
        RECOVERED_CODES["pagos provisionales mensuales"],
        "activo",
        100,
        "Pagos Provisionales Mensuales",
    )
    assert _codigo_compatible_con_origen(
        RECOVERED_CODES["aporte patronal"],
        "perdida",
        100,
        "Aporte Patronal",
    )
    assert not _codigo_compatible_con_origen(
        RECOVERED_CODES["aporte patronal"],
        "pasivo",
        100,
        "Aporte Patronal",
    )
