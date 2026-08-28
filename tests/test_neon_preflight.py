import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
CANDIDATE_BRANCH = "codex/mejoras-pendientes-20260826"


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
