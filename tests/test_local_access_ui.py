from local_access_ui import clear_local_work_session, local_access_enabled


def test_access_mode_requires_explicit_environment_value(monkeypatch):
    monkeypatch.delenv("LOCAL_ACCESS_MODE", raising=False)
    assert local_access_enabled() is False

    monkeypatch.setenv("LOCAL_ACCESS_MODE", "1")
    assert local_access_enabled() is True

    monkeypatch.setenv("LOCAL_ACCESS_MODE", "off")
    assert local_access_enabled() is False


def test_logout_clears_balance_workflow_but_not_unrelated_session_state():
    state = {
        "resultados": {"document.pdf": object()},
        "document_pages": {"document.pdf": [1]},
        "pilot_manifest_context": {"document": "opaque"},
        "balance_uploads": [object()],
        "diccionario": [{"cuenta_original": "Cuenta privada"}],
        "team_dictionary_context": "team-private:1:1",
        "team_dictionary_scope": "team-private",
        "other_ui_preference": "preserve",
    }

    clear_local_work_session(state)

    assert state == {"other_ui_preference": "preserve"}
