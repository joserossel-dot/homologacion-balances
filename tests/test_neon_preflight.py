from pathlib import Path
import importlib.util

import pytest


PREFLIGHT_PATH = Path(__file__).parents[1] / "scripts" / "neon_preflight.py"
SPEC = importlib.util.spec_from_file_location("neon_preflight", PREFLIGHT_PATH)
assert SPEC is not None and SPEC.loader is not None
neon_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(neon_preflight)


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


def test_metricas_del_diccionario_aceptan_exclusiones_deliberadas():
    persisted_entries = [
        {"codigo_estandar": "AC.01"},
        {"codigo_estandar": "__EXCLUIR__"},
        {"codigo_estandar": "PC.01"},
    ]

    assert neon_preflight.operational_dictionary_entries(persisted_entries) == 2
    assert neon_preflight.dictionary_metrics_are_consistent(
        reported_entries=3,
        persisted_entries=persisted_entries,
        pipeline_entries=2,
    )


@pytest.mark.parametrize(
    ("reported_entries", "pipeline_entries"),
    [
        (2, 2),  # estadistica de Neon no coincide con las filas leidas
        (3, 3),  # el pipeline dejo pasar __EXCLUIR__
        (3, 1),  # el pipeline perdio una entrada operacional
    ],
)
def test_metricas_del_diccionario_fallan_ante_cualquier_desajuste(
    reported_entries, pipeline_entries
):
    persisted_entries = [
        {"codigo_estandar": "AC.01"},
        {"codigo_estandar": "__EXCLUIR__"},
        {"codigo_estandar": "PC.01"},
    ]

    assert not neon_preflight.dictionary_metrics_are_consistent(
        reported_entries=reported_entries,
        persisted_entries=persisted_entries,
        pipeline_entries=pipeline_entries,
    )
