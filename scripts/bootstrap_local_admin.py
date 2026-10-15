"""Crea el administrador inicial de las cuentas locales.

Ejecutar desde el proyecto con ``poetry run python scripts/bootstrap_local_admin.py``.
La contraseña se solicita por terminal y no se imprime ni se guarda en texto.
"""

from __future__ import annotations

from getpass import getpass

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
