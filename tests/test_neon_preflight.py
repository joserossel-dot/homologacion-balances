from pathlib import Path


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
    source = (Path(__file__).parents[1] / "render.yaml").read_text()
    assert "APP_RELEASE_BRANCH" in source


def test_docker_genera_fecha_de_build_para_trazabilidad():
    source = (Path(__file__).parents[1] / "Dockerfile").read_text()
    assert "date -u +%Y-%m-%dT%H:%M:%SZ > /app/.build_date" in source


def test_release_gate_exige_neon_y_registra_commit():
    source = (
        Path(__file__).parents[1] / ".github" / "workflows" / "release-gate.yml"
    ).read_text()
    assert "secrets.NEON_DATABASE_URL" in source
    assert "python scripts/neon_preflight.py" in source
    assert "CERTIFIED_COMMIT=$GITHUB_SHA" in source
