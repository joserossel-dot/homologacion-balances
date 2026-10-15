import tempfile
from pathlib import Path

import app_validacion as app
from pilot_mode import configure_pilot_tempdir, pilot_mode_active, validate_pilot_tempdir


def test_pilot_mode_recognizes_explicit_values(monkeypatch):
    for value in ("1", "true", "TRUE", " yes ", "on"):
        monkeypatch.setenv("PILOT_MODE", value)
        assert pilot_mode_active()
        assert app._modo_piloto_activo()
        assert not app._shadow_mode_activo()

    for value in ("", "0", "false", "off", "pilot"):
        monkeypatch.setenv("PILOT_MODE", value)
        assert not pilot_mode_active()


def test_pilot_persistence_functions_do_not_instantiate_neon(monkeypatch):
    monkeypatch.setenv("PILOT_MODE", "1")

    def should_not_be_called():
        raise AssertionError("Neon must not be instantiated for a pilot write")

    monkeypatch.setattr(app, "NeonKnowledgeStore", should_not_be_called)

    assert app._persistir_validacion(
        nombre="Clientes",
        codigo="AC.03",
        fuente="validacion_humana",
        agregar_diccionario=True,
    )
    assert app._persistir_validaciones_lote([])
    assert app._persistir_catalogo({"codigo_estandar": "AC.99"})


def test_pilot_keeps_operational_dictionary_read_only(monkeypatch):
    monkeypatch.setenv("PILOT_MODE", "1")

    class ReadOnlyStore:
        enabled = True

        def load_dictionary(self):
            return [{"cuenta_original": "Clientes", "codigo_estandar": "AC.03"}]

    monkeypatch.setattr(app, "NeonKnowledgeStore", ReadOnlyStore)
    app.cargar_diccionario_base.clear()
    try:
        assert app.cargar_diccionario_base() == [
            {"cuenta_original": "Clientes", "codigo_estandar": "AC.03"}
        ]
    finally:
        app.cargar_diccionario_base.clear()


def _repo_and_secure_temp(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repository"
    repo_root.mkdir()
    secure_tmp = tmp_path / "controlled-temporary"
    secure_tmp.mkdir()
    secure_tmp.chmod(0o700)
    return repo_root, secure_tmp


def test_pilot_tmpdir_is_required_and_invalid_setting_changes_nothing(
        monkeypatch, tmp_path,
):
    monkeypatch.setenv("PILOT_MODE", "1")
    repo_root, _secure_tmp = _repo_and_secure_temp(tmp_path)
    environment = {"TMPDIR": "before", "TMP": "before", "TEMP": "before"}

    status = configure_pilot_tempdir(environ=environment, repo_root=repo_root)

    assert not status.ready
    assert status.code == "missing"
    assert environment == {"TMPDIR": "before", "TMP": "before", "TEMP": "before"}


def test_pilot_tmpdir_rejects_nonexistent_path(monkeypatch, tmp_path):
    monkeypatch.setenv("PILOT_MODE", "1")
    repo_root, _secure_tmp = _repo_and_secure_temp(tmp_path)
    environment = {"PILOT_TMPDIR": str(tmp_path / "does-not-exist")}

    status = configure_pilot_tempdir(environ=environment, repo_root=repo_root)

    assert not status.ready
    assert status.code == "unavailable"
    assert "TMPDIR" not in environment


def test_pilot_tmpdir_rejects_a_regular_file(monkeypatch, tmp_path):
    monkeypatch.setenv("PILOT_MODE", "1")
    repo_root, _secure_tmp = _repo_and_secure_temp(tmp_path)
    not_a_directory = tmp_path / "not-a-directory"
    not_a_directory.write_text("not a directory")

    status = validate_pilot_tempdir(
        str(not_a_directory), repo_root=repo_root,
    )

    assert not status.ready
    assert status.code == "not_directory"


def test_pilot_tmpdir_rejects_group_or_other_permissions(monkeypatch, tmp_path):
    monkeypatch.setenv("PILOT_MODE", "1")
    repo_root, secure_tmp = _repo_and_secure_temp(tmp_path)
    secure_tmp.chmod(0o755)

    status = validate_pilot_tempdir(str(secure_tmp), repo_root=repo_root)

    assert not status.ready
    assert status.code == "insecure_permissions"


def test_pilot_tmpdir_rejects_a_directory_inside_repository(monkeypatch, tmp_path):
    monkeypatch.setenv("PILOT_MODE", "1")
    repo_root, _secure_tmp = _repo_and_secure_temp(tmp_path)
    inside_repository = repo_root / "temporary"
    inside_repository.mkdir()
    inside_repository.chmod(0o700)

    status = validate_pilot_tempdir(str(inside_repository), repo_root=repo_root)

    assert not status.ready
    assert status.code == "inside_repository"


def test_pilot_tmpdir_configures_python_and_subprocess_temporaries(
        monkeypatch, tmp_path,
):
    monkeypatch.setenv("PILOT_MODE", "1")
    repo_root, secure_tmp = _repo_and_secure_temp(tmp_path)
    environment = {"PILOT_TMPDIR": str(secure_tmp)}
    monkeypatch.setattr(tempfile, "tempdir", None)

    status = configure_pilot_tempdir(environ=environment, repo_root=repo_root)

    assert status.ready
    assert status.code == "ready"
    assert tempfile.tempdir == str(secure_tmp.resolve())
    assert environment["TMPDIR"] == str(secure_tmp.resolve())
    assert environment["TMP"] == str(secure_tmp.resolve())
    assert environment["TEMP"] == str(secure_tmp.resolve())
    with tempfile.NamedTemporaryFile() as generated:
        assert Path(generated.name).parent == secure_tmp.resolve()


def test_nonpilot_tmpdir_configuration_is_a_noop(monkeypatch, tmp_path):
    monkeypatch.delenv("PILOT_MODE", raising=False)
    repo_root, secure_tmp = _repo_and_secure_temp(tmp_path)
    environment = {"PILOT_TMPDIR": str(secure_tmp), "TMPDIR": "before"}
    monkeypatch.setattr(tempfile, "tempdir", "before")

    status = configure_pilot_tempdir(environ=environment, repo_root=repo_root)

    assert status.ready
    assert status.code == "not_required"
    assert tempfile.tempdir == "before"
    assert environment == {"PILOT_TMPDIR": str(secure_tmp), "TMPDIR": "before"}


def test_main_blocks_pilot_before_any_upload_or_processing_when_tmpdir_is_invalid(
        monkeypatch,
):
    monkeypatch.setenv("PILOT_MODE", "1")
    monkeypatch.delenv("PILOT_TMPDIR", raising=False)
    errors: list[str] = []
    reached_title: list[bool] = []
    monkeypatch.setattr(
        app.st, "error", lambda message, *args, **kwargs: errors.append(message),
    )
    monkeypatch.setattr(
        app.st, "title", lambda *args, **kwargs: reached_title.append(True),
    )

    app.main()

    assert reached_title == []
    assert len(errors) == 1
    assert "PILOT_TMPDIR" not in errors[0]
    assert "/" not in errors[0]
