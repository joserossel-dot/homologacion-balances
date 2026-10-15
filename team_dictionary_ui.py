"""Interfaz Streamlit para el diccionario privado de cada equipo."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from access_control import Actor, Permission, ResourceScope, Role, authorize
from local_accounts import LocalAccountError, LocalAccountStore
from team_dictionary import (
    GlobalReviewStatus,
    TeamAssignmentStatus,
    TeamDictionaryAccessError,
    TeamDictionaryError,
    TeamDictionaryStore,
)


_TEAM_STATUS_LABELS = {
    TeamAssignmentStatus.PROPOSED: "Propuesta pendiente",
    TeamAssignmentStatus.ACTIVE: "Activa en este equipo",
    TeamAssignmentStatus.REVOKED: "Revocada",
}
_REVIEW_STATUS_LABELS = {
    GlobalReviewStatus.NOT_SUBMITTED: "No enviada a revisión global",
    GlobalReviewStatus.PENDING: "Pendiente de tu revisión",
    GlobalReviewStatus.APPROVED: "Aprobada para incorporación posterior",
    GlobalReviewStatus.REJECTED: "No aprobada para incorporación",
}


def _allowed(actor: Actor, permission: Permission, team_id: str) -> bool:
    return authorize(
        actor, permission, ResourceScope(team_id=team_id),
    ).allowed


def can_view_team_dictionary(actor: Actor | None) -> bool:
    """Indica si el rol puede acceder a la vista de diccionario del equipo."""

    if actor is None:
        return False
    team_id = actor.team_id or "dictionary-review"
    return any(
        _allowed(actor, permission, team_id)
        for permission in (
            Permission.DICTIONARY_PROPOSE,
            Permission.TEAM_AUDIT_VIEW,
            Permission.GLOBAL_DICTIONARY_PROMOTION_REVIEW,
        )
    )


def _team_options(actor: Actor) -> dict[str, str]:
    if actor.role is not Role.ADMINISTRATOR:
        return {actor.team_id: actor.team_id} if actor.team_id else {}
    try:
        accounts = LocalAccountStore()
    except LocalAccountError as exc:
        st.error(f"No se pudo abrir los equipos locales: {exc}")
        return {}
    return {team.team_id: team.name for team in accounts.list_teams()}


def _selected_team(actor: Actor) -> str | None:
    options = _team_options(actor)
    if not options:
        st.info("Aún no hay un equipo disponible para el diccionario privado.")
        return None
    if actor.role is not Role.ADMINISTRATOR:
        team_id = next(iter(options))
        st.caption(f"Equipo actual: {options[team_id]}")
        return team_id
    identifiers = list(options)
    return st.selectbox(
        "Equipo cuyo diccionario desea revisar",
        identifiers,
        format_func=lambda team_id: options[team_id],
        key="team_dictionary_scope",
    )


def _catalog_codes(catalogue: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    for code, data in catalogue.items():
        if not isinstance(data, Mapping) or data.get("clasificable", True):
            codes.append(str(code))
    return sorted(codes)


def _catalog_label(catalogue: Mapping[str, Any], code: str) -> str:
    data = catalogue.get(code, {})
    name = data.get("nombre_estandar", "") if isinstance(data, Mapping) else ""
    return f"{code} · {name}" if name else code


def _render_proposal_form(
    store: TeamDictionaryStore,
    actor: Actor,
    team_id: str,
    catalogue: Mapping[str, Any],
) -> None:
    if not _allowed(actor, Permission.DICTIONARY_PROPOSE, team_id):
        return
    codes = _catalog_codes(catalogue)
    if not codes:
        st.error("No hay códigos de catálogo disponibles para crear una propuesta.")
        return
    st.subheader("Proponer una asignación para el equipo")
    st.caption(
        "La propuesta no se aplicará hasta que Jefatura la active. "
        "Tampoco modifica el diccionario original."
    )
    with st.form(f"team_dictionary_proposal_{team_id}"):
        account_name = st.text_input("Nombre de cuenta tal como aparece en el balance")
        code = st.selectbox(
            "Clasificación propuesta",
            codes,
            format_func=lambda value: _catalog_label(catalogue, value),
        )
        note = st.text_area("Fundamento o evidencia, opcional", max_chars=1000)
        submit = st.form_submit_button("Registrar propuesta")
    if submit:
        try:
            store.propose(
                actor,
                team_id=team_id,
                account_name=account_name,
                standard_code=code,
                note=note,
            )
        except (TeamDictionaryError, TeamDictionaryAccessError) as exc:
            st.error(str(exc))
        else:
            st.success("Propuesta registrada para revisión de Jefatura.")
            st.rerun()


def _assignment_rows(assignments) -> list[dict[str, Any]]:
    return [
        {
            "ID": assignment.assignment_id,
            "Cuenta": assignment.account_name,
            "Código": assignment.standard_code,
            "Estado del equipo": _TEAM_STATUS_LABELS[assignment.team_status],
            "Revisión para base": _REVIEW_STATUS_LABELS[
                assignment.global_review_status
            ],
            "Propuesto por": assignment.created_by,
            "Actualizado": assignment.updated_at,
        }
        for assignment in assignments
    ]


def _render_team_actions(
    store: TeamDictionaryStore,
    actor: Actor,
    team_id: str,
    assignments,
) -> None:
    if not assignments:
        st.caption("Este equipo todavía no tiene propuestas ni asignaciones.")
        return
    st.subheader("Asignaciones y trazabilidad")
    st.dataframe(
        pd.DataFrame(_assignment_rows(assignments)),
        use_container_width=True,
        hide_index=True,
    )
    for assignment in assignments:
        if assignment.team_status == TeamAssignmentStatus.PROPOSED and _allowed(
            actor, Permission.TEAM_DICTIONARY_ACTIVATE, team_id,
        ):
            if st.button(
                f"Activar #{assignment.assignment_id}",
                key=f"team_dictionary_activate_{assignment.assignment_id}",
            ):
                try:
                    store.activate(actor, assignment.assignment_id)
                except (TeamDictionaryError, TeamDictionaryAccessError) as exc:
                    st.error(str(exc))
                else:
                    st.success("Asignación activada sólo para este equipo.")
                    st.rerun()

        if assignment.team_status == TeamAssignmentStatus.ACTIVE:
            action_note = st.text_input(
                f"Motivo o antecedente para #{assignment.assignment_id}, opcional",
                key=f"team_dictionary_action_note_{assignment.assignment_id}",
                max_chars=1000,
            )
            action_columns = st.columns(2)
            with action_columns[0]:
                if _allowed(actor, Permission.TEAM_DICTIONARY_UNASSIGN, team_id):
                    if st.button(
                        f"Revocar #{assignment.assignment_id}",
                        key=f"team_dictionary_revoke_{assignment.assignment_id}",
                    ):
                        try:
                            store.revoke(
                                actor, assignment.assignment_id, note=action_note,
                            )
                        except (TeamDictionaryError, TeamDictionaryAccessError) as exc:
                            st.error(str(exc))
                        else:
                            st.success("Asignación revocada. El historial se conserva.")
                            st.rerun()
            with action_columns[1]:
                if (
                    assignment.global_review_status != GlobalReviewStatus.PENDING
                    and _allowed(
                        actor, Permission.TEAM_DICTIONARY_SUBMIT_GLOBAL_REVIEW, team_id,
                    )
                ):
                    if st.button(
                        f"Enviar #{assignment.assignment_id} a tu revisión",
                        key=f"team_dictionary_submit_{assignment.assignment_id}",
                    ):
                        try:
                            store.submit_for_global_review(
                                actor, assignment.assignment_id, note=action_note,
                            )
                        except (TeamDictionaryError, TeamDictionaryAccessError) as exc:
                            st.error(str(exc))
                        else:
                            st.success(
                                "Enviada a revisión administrativa. El diccionario original no cambió."
                            )
                            st.rerun()


def _render_global_review_queue(store: TeamDictionaryStore, actor: Actor) -> None:
    if not _allowed(
        actor, Permission.GLOBAL_DICTIONARY_PROMOTION_REVIEW, "global-review",
    ):
        return
    st.divider()
    st.subheader("Decisiones pendientes para el diccionario original")
    st.info(
        "Aprobar aquí no incorpora nada al diccionario original. Registra tu "
        "decisión para una incorporación posterior, explícita y auditada."
    )
    try:
        pending = store.list_pending_global_reviews(actor)
    except (TeamDictionaryError, TeamDictionaryAccessError) as exc:
        st.error(str(exc))
        return
    if not pending:
        st.caption("No hay asignaciones pendientes de tu revisión.")
        return
    for assignment in pending:
        st.markdown(
            f"**#{assignment.assignment_id} · {assignment.account_name}**  \n"
            f"Equipo: `{assignment.team_id}` · Código propuesto: `{assignment.standard_code}`"
        )
        if assignment.note:
            st.caption(f"Fundamento del equipo: {assignment.note}")
        review_note = st.text_area(
            "Análisis o fundamento de la decisión, opcional",
            key=f"team_dictionary_review_note_{assignment.assignment_id}",
            max_chars=1000,
        )
        left, right = st.columns(2)
        with left:
            approve = st.button(
                "Aprobar para incorporación posterior",
                key=f"team_dictionary_approve_{assignment.assignment_id}",
            )
        with right:
            reject = st.button(
                "No aprobar incorporación",
                key=f"team_dictionary_reject_{assignment.assignment_id}",
            )
        if approve or reject:
            try:
                store.review_for_global_promotion(
                    actor,
                    assignment.assignment_id,
                    approved=approve,
                    note=review_note,
                )
            except (TeamDictionaryError, TeamDictionaryAccessError) as exc:
                st.error(str(exc))
            else:
                st.success("La decisión quedó auditada. El diccionario original sigue sin cambios.")
                st.rerun()


def render_team_dictionary_view(
    actor: Actor,
    catalogue: Mapping[str, Any],
) -> None:
    """Muestra el ciclo de propuesta, activación y revisión administrativa."""

    try:
        store = TeamDictionaryStore()
    except TeamDictionaryError as exc:
        st.error(f"No se pudo abrir el diccionario privado por equipo: {exc}")
        return
    st.subheader("Diccionario privado por equipo")
    st.caption(
        "Cada equipo usa sus propias asignaciones sobre el diccionario base. "
        "No hay incorporación automática al diccionario original."
    )
    team_id = _selected_team(actor)
    if team_id:
        _render_proposal_form(store, actor, team_id, catalogue)
        try:
            assignments = store.list_for_team(actor, team_id)
        except (TeamDictionaryError, TeamDictionaryAccessError) as exc:
            st.error(str(exc))
        else:
            _render_team_actions(store, actor, team_id, assignments)
    _render_global_review_queue(store, actor)


__all__ = ["can_view_team_dictionary", "render_team_dictionary_view"]
