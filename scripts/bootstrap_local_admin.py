"""Crea el administrador inicial de las cuentas locales.

Ejecutar desde el proyecto con ``poetry run python scripts/bootstrap_local_admin.py``.
La contraseña se solicita por terminal y no se imprime ni se guarda en texto.
"""

from __future__ import annotations

from getpass import getpass
from pathlib import Path
import sys


# Al ejecutar este archivo directamente, Python sólo incorpora ``scripts/`` a
# la ruta de importación. La aplicación mantiene ``local_accounts.py`` en la
# raíz del proyecto, por lo que se incorpora explícitamente antes de importar
# los componentes de acceso local.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local_accounts import LocalAccountError, LocalAccountStore, default_local_accounts_path


def main() -> int:
    store = LocalAccountStore()
    if store.has_administrator():
        print("Ya existe un administrador local activo. No se creó otra cuenta.")
        return 1

    print(f"Base privada de accesos: {default_local_accounts_path()}")
    username = input("Usuario administrador: ").strip()
    display_name = input("Nombre visible: ").strip()
    password = getpass("Contraseña: ")
    confirmation = getpass("Repita la contraseña: ")
    if password != confirmation:
        print("Las contraseñas no coinciden. No se creó ninguna cuenta.")
        return 1

    try:
        account = store.bootstrap_administrator(username, display_name, password)
    except LocalAccountError as exc:
        print(f"No se pudo crear el administrador: {exc}")
        return 1
    print(f"Administrador local creado: {account.username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
