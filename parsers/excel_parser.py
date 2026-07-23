"""Parser de archivos Excel.

Envuelve app_validacion.parsear_excel().
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app_validacion import parsear_excel as _parsear_excel
from parser_universal import CuentaRaw

from parsers.line_parser import RawAccount, _cuenta_raw_to_account


def parsear_excel(path: str | Path) -> list[RawAccount]:
    """Parsea un archivo Excel y retorna RawAccount[]."""
    cr_list: list[CuentaRaw] = _parsear_excel(path)
    return [_cuenta_raw_to_account(cr) for cr in cr_list]
