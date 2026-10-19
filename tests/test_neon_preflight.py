import json
from pathlib import Path
import sys

import scripts.neon_preflight as neon_preflight


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
    assert "poetry run python scripts/neon_preflight.py" in source
    assert "CERTIFIED_COMMIT=$GITHUB_SHA" in source


def test_preflight_compara_diccionario_usable_con_pipeline(monkeypatch, capsys):
    class FakeStore:
        enabled = True

        def healthcheck(self):
            return True

        def learning_statistics(self):
            return {"catalog_entries": 62, "dictionary_entries": 876}

        def load_dictionary(self):
            return [
                {"codigo_estandar": "AC.01"},
                {"codigo_estandar": "PC.01"},
                {"codigo_estandar": "__EXCLUIR__"},
            ]

        def dictionary_history(self, _limit):
            return []

        def conflicts(self):
            return []

    class FakePipeline:
        _dictionary = [
            {"codigo_estandar": "AC.01"},
            {"codigo_estandar": "PC.01"},
        ]

    monkeypatch.setattr(neon_preflight, "NeonKnowledgeStore", FakeStore)
    monkeypatch.setattr(neon_preflight, "HomologationPipeline", FakePipeline)
    monkeypatch.setattr(sys, "argv", ["neon_preflight.py"])

    assert neon_preflight.main() == 0
    checks, result = capsys.readouterr().out.splitlines()
    assert result == "PASS"
    assert json.loads(checks) == {
        "catalog_entries": 62,
        "conflicts_accessible": True,
        "dictionary_entries": 876,
        "history_accessible": True,
        "neon": True,
        "pipeline_dictionary_entries": 2,
        "usable_dictionary_entries": 2,
    }
