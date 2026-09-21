import re
from pathlib import Path

import yaml

from scripts.neon_preflight import checks_pass, dictionary_profile


ROOT = Path(__file__).parents[1]
CANDIDATE_BRANCH = "codex/mejoras-pendientes-20260826"


def _healthy_preflight_checks():
    return {
        "neon": True,
        "catalog_entries": 62,
        "dictionary_entries": 876,
        "loaded_dictionary_entries": 876,
        "excluded_dictionary_entries": 0,
        "classifiable_dictionary_entries": 876,
        "pipeline_dictionary_entries": 876,
        "unknown_catalog_codes": 0,
        "conflicting_dictionary_names": 0,
        "protected_conflicting_dictionary_names": 0,
        "history_accessible": True,
        "conflicts_accessible": True,
    }


def test_preflight_exige_historial_y_conflictos_accesibles():
    checks = _healthy_preflight_checks()
    assert checks_pass(checks)
    for key in ("history_accessible", "conflicts_accessible"):
        unavailable = dict(checks, **{key: False})
        assert not checks_pass(unavailable)


def test_preflight_acepta_exclusiones_fuera_del_diccionario_operativo():
    checks = dict(
        _healthy_preflight_checks(),
        dictionary_entries=878,
        loaded_dictionary_entries=878,
        excluded_dictionary_entries=2,
        classifiable_dictionary_entries=876,
    )
    assert checks_pass(checks)


def test_preflight_rechaza_diferencias_operativas_y_estadisticas():
    assert not checks_pass(dict(
        _healthy_preflight_checks(), pipeline_dictionary_entries=875,
    ))
    assert not checks_pass(dict(
        _healthy_preflight_checks(), loaded_dictionary_entries=875,
    ))


def test_preflight_rechaza_codigos_desconocidos_y_nombres_conflictivos():
    assert not checks_pass(dict(
        _healthy_preflight_checks(), unknown_catalog_codes=1,
    ))
    assert not checks_pass(dict(
        _healthy_preflight_checks(), conflicting_dictionary_names=1,
    ))
    assert checks_pass(dict(
        _healthy_preflight_checks(),
        conflicting_dictionary_names=1,
        protected_conflicting_dictionary_names=1,
    ))


def test_dictionary_profile_no_expone_nombres_y_separa_exclusiones():
    dictionary = [
        {"cuenta_original": "Caja", "codigo_estandar": "AC.01"},
        {"cuenta_original": "Control privado", "codigo_estandar": "__EXCLUIR__"},
    ]
    profile = dictionary_profile(dictionary, {"AC.01": {}}, 1, 0)

    assert profile == {
        "loaded_dictionary_entries": 2,
        "excluded_dictionary_entries": 1,
        "classifiable_dictionary_entries": 1,
        "pipeline_dictionary_entries": 1,
        "unknown_catalog_codes": 0,
        "conflicting_dictionary_names": 0,
        "protected_conflicting_dictionary_names": 0,
    }
    assert "Caja" not in str(profile)
    assert "Control privado" not in str(profile)


def test_dictionary_profile_detecta_codigo_desconocido_y_conflicto():
    dictionary = [
        {"cuenta_original": "Cuenta X", "codigo_estandar": "AC.01"},
        {"cuenta_original": "cuenta-x", "codigo_estandar": "PC.01"},
        {"cuenta_original": "Otra", "codigo_estandar": "ZZ.99"},
    ]
    profile = dictionary_profile(
        dictionary, {"AC.01": {}, "PC.01": {}}, 3, 1,
    )

    assert profile["unknown_catalog_codes"] == 1
    assert profile["conflicting_dictionary_names"] == 1
    assert profile["protected_conflicting_dictionary_names"] == 1


def test_preflight_no_expone_database_url():
    source = (Path(__file__).parents[1] / "scripts" / "neon_preflight.py").read_text()
    assert "print(store.database_url" not in source
    assert "print(os.environ" not in source
    assert "DATABASE_URL no configurada" in source


def test_render_declara_secreto_sin_valor():
    source = (Path(__file__).parents[1] / "render.yaml").read_text()
    assert "key: DATABASE_URL" in source
    assert "sync: false" in source
    assert "autoDeploy: false" in source


def test_render_declara_trazabilidad_de_release():
    source = (ROOT / "render.yaml").read_text()
    assert "APP_RELEASE_BRANCH" in source


def test_configuracion_de_release_apunta_a_la_rama_candidata():
    render_source = (ROOT / "render.yaml").read_text()
    workflow_source = (
        ROOT / ".github" / "workflows" / "release-gate.yml"
    ).read_text()

    assert f"branch: {CANDIDATE_BRANCH}" in render_source
    assert f"value: {CANDIDATE_BRANCH}" in render_source
    assert f"- {CANDIDATE_BRANCH}" in workflow_source


def test_poetry_esta_fijado_en_build_y_certificacion():
    docker_source = (ROOT / "Dockerfile").read_text()
    workflow_source = (
        ROOT / ".github" / "workflows" / "release-gate.yml"
    ).read_text()
    docker_version = re.search(r"poetry==([0-9.]+)", docker_source)
    workflow_version = re.search(r"poetry==([0-9.]+)", workflow_source)

    assert docker_version is not None
    assert workflow_version is not None
    assert docker_version.group(1) == workflow_version.group(1)


def test_docker_genera_fecha_de_build_para_trazabilidad():
    source = (Path(__file__).parents[1] / "Dockerfile").read_text()
    assert "date -u +%Y-%m-%dT%H:%M:%SZ > /app/.build_date" in source


def test_dockerignore_excluye_secretos_y_artefactos_no_operativos():
    source = (ROOT / ".dockerignore").read_text().splitlines()

    assert ".env" in source
    assert ".git" in source
    assert "tests" in source
    assert "reports" in source
    assert "tmp" in source
    assert "*.pdf" in source
    assert "*.xlsx" in source


def test_release_gate_exige_neon_y_despliega_el_commit_certificado():
    source = (
        Path(__file__).parents[1] / ".github" / "workflows" / "release-gate.yml"
    ).read_text()
    assert "secrets.NEON_DATABASE_URL" in source
    assert "poetry run python scripts/neon_preflight.py" in source
    assert "CERTIFIED_COMMIT=$GITHUB_SHA" in source
    assert "secrets.RENDER_API_KEY" in source
    assert "secrets.RENDER_SERVICE_ID" in source
    assert "poetry run python scripts/deploy_certified_render.py" in source
    assert "DEPLOYED_COMMIT=$GITHUB_SHA" in source


def test_release_gate_limita_database_url_a_pasos_neon():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "release-gate.yml").read_text()
    )
    certify = workflow["jobs"]["certify"]
    assert "env" not in certify
    steps = {
        step["name"]: step for step in certify["steps"] if "name" in step
    }
    for name in ("Require Neon secret", "Verify Neon and pipeline knowledge"):
        assert steps[name]["env"]["DATABASE_URL"] == (
            "${{ secrets.NEON_DATABASE_URL }}"
        )


def test_release_manual_no_despliega_desde_otra_rama_y_revalida_head():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "release-gate.yml").read_text()
    )
    certify = workflow["jobs"]["certify"]
    assert certify["if"] == (
        "github.ref == 'refs/heads/codex/mejoras-pendientes-20260826'"
    )
    names = [step.get("name") for step in certify["steps"]]
    assert names.index("Verify signed private corpus recertification") < names.index(
        "Recheck branch head immediately before deployment"
    ) < names.index("Deploy exact certified commit to Render")
