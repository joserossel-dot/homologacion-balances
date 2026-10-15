import pytest

from access_control import Actor, Permission, ResourceScope, Role, authorize


TEAM_A = "team-a"
TEAM_B = "team-b"


def test_data_entry_can_submit_own_input_in_its_team():
    actor = Actor("entry-1", Role.DATA_ENTRY, TEAM_A)
    resource = ResourceScope(team_id=TEAM_A, owner_id="entry-1")

    decision = authorize(actor, Permission.ENTRY_SUBMIT, resource)

    assert decision.allowed is True
    assert decision.requires_audit is True


@pytest.mark.parametrize(
    "resource, expected_reason",
    [
        (ResourceScope(team_id=TEAM_A, owner_id="entry-2"), "not_resource_owner"),
        (ResourceScope(team_id=TEAM_B, owner_id="entry-1"), "outside_team"),
    ],
)
def test_data_entry_cannot_edit_someone_elses_input(resource, expected_reason):
    actor = Actor("entry-1", Role.DATA_ENTRY, TEAM_A)

    decision = authorize(actor, Permission.ENTRY_EDIT_OWN, resource)

    assert decision.allowed is False
    assert decision.reason == expected_reason


def test_data_entry_cannot_classify_or_change_dictionary():
    actor = Actor("entry-1", Role.DATA_ENTRY, TEAM_A)
    resource = ResourceScope(team_id=TEAM_A, owner_id="entry-1")

    assert not authorize(actor, Permission.ACCOUNT_CLASSIFY, resource).allowed
    assert not authorize(actor, Permission.TEAM_DICTIONARY_UNASSIGN, resource).allowed


def test_analyst_can_review_team_accounts_but_cannot_remove_dictionary_mapping():
    actor = Actor("analyst-1", Role.ANALYST, TEAM_A)
    resource = ResourceScope(team_id=TEAM_A, owner_id="entry-1")

    assert authorize(actor, Permission.ACCOUNT_REVIEW, resource).allowed
    assert not authorize(actor, Permission.TEAM_DICTIONARY_UNASSIGN, resource).allowed


def test_management_can_edit_all_team_inputs_and_revoke_team_dictionary_mapping():
    actor = Actor("manager-1", Role.MANAGEMENT, TEAM_A)
    colleague_input = ResourceScope(team_id=TEAM_A, owner_id="entry-1")
    team_mapping = ResourceScope(team_id=TEAM_A)

    assert authorize(actor, Permission.ENTRY_EDIT_TEAM, colleague_input).allowed
    decision = authorize(actor, Permission.TEAM_DICTIONARY_UNASSIGN, team_mapping)
    assert decision.allowed is True
    assert decision.requires_audit is True


def test_dictionary_team_lifecycle_requires_management_or_administrator():
    analyst = Actor("analyst-1", Role.ANALYST, TEAM_A)
    manager = Actor("manager-1", Role.MANAGEMENT, TEAM_A)
    team_mapping = ResourceScope(team_id=TEAM_A)

    assert not authorize(
        analyst, Permission.TEAM_DICTIONARY_ACTIVATE, team_mapping,
    ).allowed
    assert not authorize(
        analyst, Permission.TEAM_DICTIONARY_SUBMIT_GLOBAL_REVIEW, team_mapping,
    ).allowed
    assert authorize(
        manager, Permission.TEAM_DICTIONARY_ACTIVATE, team_mapping,
    ).allowed
    assert authorize(
        manager, Permission.TEAM_DICTIONARY_SUBMIT_GLOBAL_REVIEW, team_mapping,
    ).allowed
    assert not authorize(
        manager, Permission.GLOBAL_DICTIONARY_PROMOTION_REVIEW, team_mapping,
    ).allowed


def test_management_cannot_cross_team_or_mutate_global_dictionary():
    actor = Actor("manager-1", Role.MANAGEMENT, TEAM_A)

    assert authorize(
        actor, Permission.ENTRY_EDIT_TEAM, ResourceScope(team_id=TEAM_B, owner_id="entry-2"),
    ).reason == "outside_team"
    assert not authorize(actor, Permission.GLOBAL_DICTIONARY_EDIT).allowed


def test_team_dictionary_action_fails_closed_without_team_scope():
    actor = Actor("manager-1", Role.MANAGEMENT, TEAM_A)

    decision = authorize(actor, Permission.TEAM_DICTIONARY_UNASSIGN)

    assert decision.allowed is False
    assert decision.reason == "team_scope_required"


def test_administrator_has_operational_access_across_teams_but_cannot_erase_audit():
    actor = Actor("pilot-owner-001", Role.ADMINISTRATOR)

    assert authorize(
        actor, Permission.ENTRY_EDIT_TEAM, ResourceScope(team_id=TEAM_B, owner_id="entry-2"),
    ).allowed
    assert authorize(
        actor, Permission.GLOBAL_DICTIONARY_PROMOTION_REVIEW,
        ResourceScope(team_id=TEAM_B),
    ).allowed
    assert authorize(actor, Permission.GLOBAL_DICTIONARY_EDIT).allowed
    audit_decision = authorize(actor, Permission.AUDIT_ERASE)
    assert audit_decision.allowed is False
    assert audit_decision.reason == "audit_history_is_append_only"


def test_missing_identity_is_denied_before_role_evaluation():
    decision = authorize(None, Permission.ACCOUNT_REVIEW, ResourceScope(team_id=TEAM_A))

    assert decision.allowed is False
    assert decision.reason == "identity_required"


def test_non_administrator_requires_team_identity():
    with pytest.raises(ValueError, match="team_id"):
        Actor("analyst-1", Role.ANALYST)
