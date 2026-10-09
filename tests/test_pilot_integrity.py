from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "pilot_integrity.py"
SPEC = importlib.util.spec_from_file_location("pilot_integrity", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
pilot_integrity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot_integrity)


def test_snapshot_protege_archivos_auxiliares_de_sqlite():
    assert "gold_standard.db-wal" in pilot_integrity.PROTECTED_ARTIFACTS
    assert "gold_standard_runtime.db-shm" in pilot_integrity.PROTECTED_ARTIFACTS
    assert "datasets/dataset_registry.db-journal" in pilot_integrity.PROTECTED_ARTIFACTS


def test_snapshot_registra_hash_sin_rutas_absolutas(tmp_path):
    (tmp_path / "diccionario.json").write_text('{"cuenta": "Caja"}', encoding="utf-8")

    snapshot = pilot_integrity.capture_snapshot(
        tmp_path,
        ("diccionario.json", "gold_standard.db"),
    )

    assert snapshot["schema_version"] == 1
    assert snapshot["artifacts"]["diccionario.json"]["state"] == "file"
    assert len(snapshot["artifacts"]["diccionario.json"]["sha256"]) == 64
    assert snapshot["artifacts"]["gold_standard.db"] == {"state": "missing"}
    assert str(tmp_path) not in json.dumps(snapshot)


def test_compare_detecta_archivo_creado_y_archivo_modificado(tmp_path):
    (tmp_path / "diccionario.json").write_text("antes", encoding="utf-8")
    baseline = pilot_integrity.capture_snapshot(
        tmp_path,
        ("diccionario.json", "learning_queue.json"),
    )

    (tmp_path / "diccionario.json").write_text("después", encoding="utf-8")
    (tmp_path / "learning_queue.json").write_text("[]", encoding="utf-8")
    observed = pilot_integrity.capture_snapshot(
        tmp_path,
        ("diccionario.json", "learning_queue.json"),
    )

    changes = pilot_integrity.compare_snapshots(baseline, observed)
    assert set(changes) == {"diccionario.json", "learning_queue.json"}
    assert changes["learning_queue.json"]["expected"] == {"state": "missing"}
    assert changes["learning_queue.json"]["observed"]["state"] == "file"


def test_verify_cli_pasa_sin_cambios_y_falla_ante_cambios(tmp_path, capsys):
    (tmp_path / "diccionario.json").write_text("estable", encoding="utf-8")
    baseline = pilot_integrity.capture_snapshot(tmp_path, ("diccionario.json",))
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    original_artifacts = pilot_integrity.PROTECTED_ARTIFACTS
    pilot_integrity.PROTECTED_ARTIFACTS = ("diccionario.json",)
    try:
        assert pilot_integrity.main([
            "--root", str(tmp_path), "verify", str(baseline_path),
        ]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "PASS"

        (tmp_path / "diccionario.json").write_text("cambió", encoding="utf-8")
        assert pilot_integrity.main([
            "--root", str(tmp_path), "verify", str(baseline_path),
        ]) == 1
        assert json.loads(capsys.readouterr().out)["status"] == "FAIL"
    finally:
        pilot_integrity.PROTECTED_ARTIFACTS = original_artifacts
