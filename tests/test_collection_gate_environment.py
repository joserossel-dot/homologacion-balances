import subprocess
import sys

import pytest

from scripts import pytest_collection_gate as gate


@pytest.mark.parametrize("output,code,expected", [
    ("12 tests collected in 0.1s", 0, 0),
    ("no tests collected in 0.1s", 5, 1),
    ("12 tests collected in 0.1s", 2, 2),
    ("No module named pytest", 1, 1),
])
def test_gate_uses_current_environment_and_rejects_failed_collection(
    monkeypatch, output, code, expected,
):
    def run(command, **kwargs):
        assert command[:3] == [sys.executable, "-m", "pytest"]
        return subprocess.CompletedProcess(command, code, output, "")

    monkeypatch.setattr(gate.subprocess, "run", run)
    assert gate.main() == expected
