import copy

import pytest

import app_validacion as app
from access_control import Actor, Role
from local_accounts import LocalAccountStore
from pipeline.homologation_pipeline import HomologationPipeline
from team_dictionary import (
    GlobalReviewStatus,
    TeamAssignmentStatus,
    TeamDictionaryAccessError,
    TeamDictionaryError,
    TeamDictionaryStore,
    overlay_team_dictionary,
)


def _setup(tmp_path):
    accounts = LocalAccountStore(tmp_path / "private" / "accounts.sqlite3")
    admin = accounts.bootstrap_administrator(
        "owner", "Owner", "correct horse battery staple",
    ).actor()
    team_a = accounts.create_team(admin, "Equipo A")
    team_b = accounts.create_team(admin, "Equipo B")

    accounts.request_access("ana", "Ana Analista", "password for ana 123")
    analyst_a = accounts.approve_request(
        admin, "ana", Role.ANALYST, team_a.team_id,
    ).actor()
    accounts.request_access("maria", "María Jefa", "password for maria 123")
    manager_a = accounts.approve_request(
        admin, "maria", Role.MANAGEMENT, team_a.team_id,
    ).actor()
    accounts.request_access("beto", "Beto Analista", "password for beto 123")
    analyst_b = accounts.approve_request(
        admin, "beto", Role.ANALYST, team_b.team_id,
    ).actor()
    return (
        TeamDictionaryStore(accounts.path),
        admin,
        team_a,
        team_b,
        analyst_a,
        manager_a,
        analyst_b,
    )


def test_analyst_proposes_mapping_but_it_is_not_effective_until_management_activates(tmp_path):
    store, _admin, team_a, _team_b, analyst_a, manager_a, _analyst_b = _setup(tmp_path)

    proposal = store.propose(
        analyst_a,
        team_id=team_a.team_id,
        account_name="Clientes relacionados",
        standard_code="AC.03",
        note="Verificado contra el balance del equipo.",
    )

    assert proposal.team_status == TeamAssignmentStatus.PROPOSED
    assert proposal.global_review_status == GlobalReviewStatus.NOT_SUBMITTED
    assert store.active_entries_for_team(team_a.team_id) == []
    with pytest.raises(TeamDictionaryAccessError):
        store.activate(analyst_a, proposal.assignment_id)

    activated = store.activate(manager_a, proposal.assignment_id)

    assert activated.team_status == TeamAssignmentStatus.ACTIVE
    assert store.active_entries_for_team(team_a.team_id) == [
        {
            "cuenta_original": "Clientes relacionados",
            "codigo_estandar": "AC.03",
            "fuente": f"diccionario_equipo:{team_a.team_id}",
            "nombre_normalizado": "clientes relacionados",
            "team_assignment_id": proposal.assignment_id,
            "team_id": team_a.team_id,
        },
    ]


def test_team_dictionary_permissions_do_not_cross_team_boundaries(tmp_path):
    store, _admin, team_a, team_b, analyst_a, manager_a, analyst_b = _setup(tmp_path)
    proposal_b = store.propose(
        analyst_b,
        team_id=team_b.team_id,
        account_name="Caja chica",
        standard_code="AC.01",
    )

    with pytest.raises(TeamDictionaryAccessError):
        store.activate(manager_a, proposal_b.assignment_id)
    with pytest.raises(TeamDictionaryAccessError):
        store.list_for_team(analyst_a, team_b.team_id)

    assert store.list_for_team(analyst_a, team_a.team_id) == []


def test_global_review_decision_preserves_team_mapping_and_does_not_mutate_original(tmp_path):
    store, admin, team_a, _team_b, analyst_a, manager_a, _analyst_b = _setup(tmp_path)
    proposal = store.propose(
        analyst_a,
        team_id=team_a.team_id,
        account_name="Caja",
        standard_code="AC.07",
    )
    store.activate(manager_a, proposal.assignment_id)
    submitted = store.submit_for_global_review(
        manager_a, proposal.assignment_id, note="Solicitar revisión de alcance.",
    )

    assert submitted.team_status == TeamAssignmentStatus.ACTIVE
    assert submitted.global_review_status == GlobalReviewStatus.PENDING
    original = [{"cuenta_original": "Caja", "codigo_estandar": "AC.01"}]
    original_before = copy.deepcopy(original)

    reviewed = store.review_for_global_promotion(
        admin,
        proposal.assignment_id,
        approved=True,
        note="Aprobada para una incorporación posterior.",
    )
    effective = overlay_team_dictionary(
        original, store.active_entries_for_team(team_a.team_id),
    )

    assert reviewed.team_status == TeamAssignmentStatus.ACTIVE
    assert reviewed.global_review_status == GlobalReviewStatus.APPROVED
    assert original == original_before
    assert effective[0]["codigo_estandar"] == "AC.07"
    assert effective[0]["fuente"] == f"diccionario_equipo:{team_a.team_id}"
    assert store.active_entries_for_team(team_a.team_id)[0]["codigo_estandar"] == "AC.07"


def test_only_administrator_can_decide_a_pending_global_review(tmp_path):
    store, admin, team_a, _team_b, analyst_a, manager_a, _analyst_b = _setup(tmp_path)
    proposal = store.propose(
        analyst_a,
        team_id=team_a.team_id,
        account_name="Impuesto por recuperar",
        standard_code="AC.12",
    )
    store.activate(manager_a, proposal.assignment_id)
    store.submit_for_global_review(manager_a, proposal.assignment_id)

    with pytest.raises(TeamDictionaryAccessError):
        store.review_for_global_promotion(
            manager_a, proposal.assignment_id, approved=False,
        )

    rejected = store.review_for_global_promotion(
        admin, proposal.assignment_id, approved=False, note="Falta respaldo.",
    )

    assert rejected.global_review_status == GlobalReviewStatus.REJECTED
    assert rejected.team_status == TeamAssignmentStatus.ACTIVE


def test_revocation_is_audited_and_allows_a_replacement_proposal(tmp_path):
    store, admin, team_a, _team_b, analyst_a, manager_a, _analyst_b = _setup(tmp_path)
    proposal = store.propose(
        analyst_a,
        team_id=team_a.team_id,
        account_name="Honorarios por pagar",
        standard_code="PC.08",
    )
    store.activate(manager_a, proposal.assignment_id)
    revoked = store.revoke(manager_a, proposal.assignment_id, note="Nueva evidencia.")

    replacement = store.propose(
        analyst_a,
        team_id=team_a.team_id,
        account_name="Honorarios por pagar",
        standard_code="PC.09",
    )
    audit_events = [
        event["event_type"] for event in store.list_audit(admin, team_a.team_id)
    ]

    assert revoked.team_status == TeamAssignmentStatus.REVOKED
    assert replacement.team_status == TeamAssignmentStatus.PROPOSED
    assert audit_events[:4] == [
        "TEAM_DICTIONARY_PROPOSED",
        "TEAM_DICTIONARY_REVOKED",
        "TEAM_DICTIONARY_ACTIVATED",
        "TEAM_DICTIONARY_PROPOSED",
    ]


def test_open_assignment_cannot_be_duplicated_within_a_team(tmp_path):
    store, _admin, team_a, _team_b, analyst_a, _manager_a, _analyst_b = _setup(tmp_path)
    store.propose(
        analyst_a,
        team_id=team_a.team_id,
        account_name="IVA Crédito Fiscal",
        standard_code="AC.12",
    )

    with pytest.raises(TeamDictionaryError, match="Ya existe"):
        store.propose(
            analyst_a,
            team_id=team_a.team_id,
            account_name=" iva   Crédito fiscal ",
            standard_code="AC.05",
        )


def test_app_composes_only_the_authenticated_team_dictionary(monkeypatch):
    base = [{"cuenta_original": "Caja", "codigo_estandar": "AC.01"}]

    class StubStore:
        def active_entries_for_team(self, team_id):
            assert team_id == "team-a"
            return [{"cuenta_original": "Caja", "codigo_estandar": "AC.07"}]

        def revision_token_for_team(self, team_id):
            assert team_id == "team-a"
            return "1:2"

    monkeypatch.setattr(app, "TeamDictionaryStore", StubStore)

    effective, context = app._diccionario_efectivo_para_actor_local(
        base, Actor("ana", Role.ANALYST, "team-a"),
    )

    assert base == [{"cuenta_original": "Caja", "codigo_estandar": "AC.01"}]
    assert effective[0]["codigo_estandar"] == "AC.07"
    assert context == "team:team-a:1:2"


def test_team_dictionary_entries_precede_base_entries_for_matching_priority():
    effective = overlay_team_dictionary(
        [
            {"cuenta_original": "Caja", "codigo_estandar": "AC.01"},
            {"cuenta_original": "Caja mayor", "codigo_estandar": "AC.02"},
        ],
        [
            {
                "cuenta_original": "Caja equipo",
                "codigo_estandar": "AC.07",
                "fuente": "diccionario_equipo:team-a",
            },
        ],
    )

    assert [entry["cuenta_original"] for entry in effective] == [
        "Caja equipo", "Caja", "Caja mayor",
    ]


def test_new_pipeline_uses_injected_effective_team_dictionary(monkeypatch, tmp_path):
    def should_not_load_original_dictionary():
        raise AssertionError("The injected team dictionary must be used instead.")

    monkeypatch.setattr(
        HomologationPipeline,
        "_load_dictionary",
        staticmethod(should_not_load_original_dictionary),
    )
    pipeline = HomologationPipeline(
        db_path=tmp_path / "gold.db",
        dictionary_entries=[
            {"cuenta_original": "Cuenta interna", "codigo_estandar": "AC.07"},
        ],
    )

    result = pipeline._classify_by_dictionary_exact("Cuenta interna")

    assert result is not None
    assert result["standard_code"] == "AC.07"
