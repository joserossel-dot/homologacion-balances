from __future__ import annotations

import json
from pathlib import Path

from app_validacion import _codigo_compatible_con_origen, normalizar_nombre


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECOVERED_CODES = {
    "pagos provisionales mensuales": "AC.07",
    "ppm ventas": "AC.07",
    "ppm": "AC.07",
    "prestamos bancarios": "PC.02",
    "prov impto renta": "PC.05",
    "ventas afectas": "ER.01",
    "ventas exentas": "ER.01",
    "asesoria contable": "ER.04",
    "agua": "ER.04",
    "electricidad": "ER.04",
    "gratificación": "ER.04",
    "aporte patronal": "ER.04",
}

PILOT_CERTIFIED_EXACT_CODES = {
    "disponible": "AC.01",
    "banco": "AC.01",
    "banco estado cuenta": "AC.01",
    "iva d f": "PC.05",
    "impto 2a categoria": "PC.05",
    "utilidades retenidas": "PAT.03",
    "ingresos de explotacion": "ER.01",
    "cuentas por pagar": "PC.01",
    "prestamos trabajador": "AC.07",
    "a f p capital": "PC.06",
    "isapre colmena": "PC.06",
    "fonasa": "PC.06",
    "acreedores por pagar": "PC.01",
    "revalorizac capital": "PAT.01",
    "fdo rev capital propio": "PAT.01",
    "retenciones": "PC.05",
    "gastos en personal": "ER.04",
    "gastos de bienes y servicios vinculados": "ER.04",
    "capital por enterar": "PAT.07",
    "obligaciones c p banco e inst": "PC.02",
    "obligaciones l p banco e inst": "PNC.01",
    "oblig con bco e inst financiera c p": "PC.02",
    "impuestos financieros": "ER.09",
    "comisiones financieras": "ER.09",
    "honorarios financieros": "ER.09",
}


def _dictionary() -> list[dict[str, str]]:
    return json.loads((PROJECT_ROOT / "diccionario.json").read_text(encoding="utf-8"))


def test_local_dictionary_retains_recovered_human_entries():
    dictionary = _dictionary()
    mapping = {
        normalizar_nombre(entry["cuenta_original"]): entry["codigo_estandar"]
        for entry in dictionary
    }

    assert len(dictionary) >= 948
    for account_name, code in RECOVERED_CODES.items():
        assert mapping[account_name] == code
    for account_name, code in PILOT_CERTIFIED_EXACT_CODES.items():
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
