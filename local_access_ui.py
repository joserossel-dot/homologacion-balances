"""Interfaz Streamlit para cuentas locales y aprobación administrativa."""

from __future__ import annotations

import os
from typing import MutableMapping

import pandas as pd
import streamlit as st

from access_control import Actor, Role
from local_accounts import LocalAccount, LocalAccountError, LocalAccountStore


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_ROLE_LABELS = {
    Role.DATA_ENTRY: "Ingreso de datos",
    Role.ANALYST: "Analista",
    Role.MANAGEMENT: "Jefatura",
    Role.ADMINISTRATOR: "Administrador",
}
_TEAM_ROLES = (Role.DATA_ENTRY, Role.ANALYST, Role.MANAGEMENT)
_WORKFLOW_SESSION_KEYS = (
    "resultados",
    "metadata_files",
    "document_closing_years",
    "document_metadata_confirmations",
    "document_contexts",
    "document_intel",
    "document_pages",
    "document_scope_confirmed",
    "document_scope_editing",
    "document_scope_reconfirmation_required",
    "document_year_editing",
    "document_metadata_editing",
    "extraction_pending",
    "extraction_resolved",
    "extraction_certifications",
    "extraction_revisions",
    "delivery_readiness",
    "correcciones",
    "pilot_manifest_authorizations",
    "pilot_manifest_context",
    "pilot_manifest_client_id",
    "balance_uploads",
    "diccionario",
    "team_dictionary_context",
    "team_dictionary_scope",
    "pilot_manifest_file",
    "vista_trabajo",
    "vista_trabajo_solicitada",
)


def local_access_enabled() -> bool:
    """Solo se activa con una decisión explícita de configuración."""

    return os.environ.get("LOCAL_ACCESS_MODE", "").strip().lower() in _TRUE_VALUES


def _store_or_error() -> LocalAccountStore | None:
    try:
        return LocalAccountStore()
    except LocalAccountError as exc:
        st.error(f"No se pudo abrir el control local de accesos: {exc}")
        return None


def _role_label(role: Role | None) -> str:
    return _ROLE_LABELS.get(role, "Sin rol")


def clear_local_work_session(state: MutableMapping[str, object]) -> None:
    """Elimina datos de un balance antes de que otra cuenta use la sesión."""

    for key in _WORKFLOW_SESSION_KEYS:
        state.pop(key, None)


def _end_session() -> None:
    clear_local_work_session(st.session_state)
    st.session_state.pop("local_access_username", None)
    st.session_state.pop("local_access_actor", None)


def render_local_access_gate() -> Actor | None:
    """Exige una cuenta activa antes de mostrar el flujo del balance."""

    store = _store_or_error()
    if store is None:
        return None

    username = st.session_state.get("local_access_username")
    if username:
        try:
            account = store.require_active_account(str(username))
        except LocalAccountError:
            _end_session()
        else:
            actor = account.actor()
            st.session_state["local_access_actor"] = actor
            return actor

    st.title("Acceso a Homologación de Balances")
    if not store.has_administrator():
        st.warning(
            "Aún no existe un administrador local. La aplicación no procesará "
            "balances hasta crear esa cuenta desde el equipo servidor."
        )
        st.code("poetry run python scripts/bootstrap_local_admin.py", language="bash")
        return None

    login_tab, request_tab = st.tabs(["Iniciar sesión", "Solicitar acceso"])
    with login_tab:
        with st.form("local_access_login"):
            username_input = st.text_input("Usuario", key="local_login_username")
            password_input = st.text_input(
                "Contraseña", type="password", key="local_login_password",
            )
            login = st.form_submit_button("Ingresar")
        if login:
            account = store.authenticate(username_input, password_input)
            if account is None:
                st.error("Usuario o contraseña inválidos, o acceso aún no aprobado.")
            else:
                st.session_state["local_access_username"] = account.username
                st.rerun()

    with request_tab:
        st.caption("La solicitud no otorga acceso hasta que el administrador asigne equipo y rol.")
        with st.form("local_access_request"):
            requested_username = st.text_input("Usuario solicitado")
            display_name = st.text_input("Nombre visible")
            requested_team = st.text_input("Equipo solicitado, opcional")
            requested_password = st.text_input("Contraseña", type="password")
            requested_confirmation = st.text_input("Repita la contraseña", type="password")
            request = st.form_submit_button("Enviar solicitud")
        if request:
            if requested_password != requested_confirmation:
                st.error("Las contraseñas no coinciden.")
            else:
                try:
                    store.request_access(
                        requested_username,
                        display_name,
                        requested_password,
                        requested_team,
                    )
                except LocalAccountError as exc:
                    st.error(str(exc))
                else:
                    st.success("Solicitud registrada. El administrador debe asignar rol y equipo.")
    return None


def _render_team_creation(store: LocalAccountStore, actor: Actor) -> None:
    with st.form("local_access_create_team"):
        name = st.text_input("Nombre del equipo")
        create = st.form_submit_button("Crear equipo")
    if create:
        try:
            store.create_team(actor, name)
        except LocalAccountError as exc:
            st.error(str(exc))
        else:
            st.success("Equipo creado.")
            st.rerun()


def _team_options(store: LocalAccountStore) -> dict[str, str]:
    return {team.name: team.team_id for team in store.list_teams()}


def _render_pending_requests(store: LocalAccountStore, actor: Actor) -> None:
    pending = store.list_pending_requests(actor)
    if not pending:
        st.caption("No hay solicitudes pendientes.")
        return
    teams = _team_options(store)
    if not teams:
        st.info("Cree al menos un equipo antes de aprobar solicitudes.")
        return
    for account in pending:
        st.markdown(f"`{account.username}` · {account.display_name}")
        if account.requested_team:
            st.caption(f"Equipo solicitado: {account.requested_team}")
        left, center, right = st.columns((2, 2, 1))
        with left:
            role = st.selectbox(
                "Rol", _TEAM_ROLES, format_func=_role_label,
                key=f"pending_role_{account.username}",
            )
        with center:
            team_name = st.selectbox(
                "Equipo", list(teams), key=f"pending_team_{account.username}",
            )
        with right:
            approve = st.button("Aprobar", key=f"approve_{account.username}")
            deny = st.button("Rechazar", key=f"deny_{account.username}")
        if approve:
            try:
                store.approve_request(actor, account.username, role, teams[team_name])
            except LocalAccountError as exc:
                st.error(str(exc))
            else:
                st.success(f"Acceso aprobado para {account.username}.")
                st.rerun()
        if deny:
            try:
                store.deny_request(actor, account.username)
            except LocalAccountError as exc:
                st.error(str(exc))
            else:
                st.success(f"Solicitud rechazada para {account.username}.")
                st.rerun()


def _render_active_accounts(store: LocalAccountStore, actor: Actor) -> None:
    accounts = store.list_active_accounts(actor)
    teams = _team_options(store)
    if not accounts:
        st.caption("No hay cuentas activas.")
        return
    for account in accounts:
        if account.role is Role.ADMINISTRATOR:
            st.caption(f"`{account.username}` · Administrador")
            continue
        st.markdown(f"`{account.username}` · {account.display_name}")
        left, center, right = st.columns((2, 2, 1))
        with left:
            selected_role = st.selectbox(
                "Rol", _TEAM_ROLES,
                index=_TEAM_ROLES.index(account.role) if account.role in _TEAM_ROLES else 0,
                format_func=_role_label,
                key=f"active_role_{account.username}",
            )
        with center:
            team_names = list(teams)
            current_team_name = next(
                (name for name, team_id in teams.items() if team_id == account.team_id),
                team_names[0] if team_names else "",
            )
            selected_team = st.selectbox(
                "Equipo", team_names,
                index=team_names.index(current_team_name) if current_team_name in team_names else 0,
                key=f"active_team_{account.username}",
                disabled=not team_names,
            )
        with right:
            update = st.button("Guardar", key=f"update_{account.username}", disabled=not teams)
            disable = st.button("Deshabilitar", key=f"disable_{account.username}")
        if update:
            try:
                store.update_active_account(
                    actor, account.username, selected_role, teams[selected_team],
                )
            except LocalAccountError as exc:
                st.error(str(exc))
            else:
                st.success(f"Cuenta actualizada: {account.username}.")
                st.rerun()
        if disable:
            try:
                store.disable_account(actor, account.username)
            except LocalAccountError as exc:
                st.error(str(exc))
            else:
                st.success(f"Cuenta deshabilitada: {account.username}.")
                st.rerun()


def render_local_access_sidebar(actor: Actor) -> None:
    """Muestra sesión y administración solo a la cuenta administradora."""

    store = _store_or_error()
    if store is None:
        return
    st.divider()
    st.caption(f"Sesión local: `{actor.actor_id}` · {_role_label(actor.role)}")
    if st.button("Cerrar sesión", key="local_access_logout"):
        _end_session()
        st.rerun()
    if actor.role is not Role.ADMINISTRATOR:
        return
    with st.expander("Administrar accesos", expanded=False):
        st.caption("Las cuentas aprobadas quedan auditadas. Los roles de equipo no crean administradores.")
        _render_team_creation(store, actor)
        st.subheader("Solicitudes pendientes")
        _render_pending_requests(store, actor)
        st.subheader("Cuentas activas")
        _render_active_accounts(store, actor)
        audit = store.list_audit(actor, limit=20)
        if audit:
            st.subheader("Auditoría reciente")
            st.dataframe(pd.DataFrame(audit), use_container_width=True, hide_index=True)


__all__ = [
    "clear_local_work_session",
    "local_access_enabled",
    "render_local_access_gate",
    "render_local_access_sidebar",
]
