from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_scientific_validation_is_not_claimed_without_an_entrypoint() -> None:
    """Una capacidad inexistente no puede presentarse como gate operativo."""
    config = yaml.safe_load((ROOT / "config" / "release.yml").read_text(
        encoding="utf-8",
    ))
    enabled = bool(config["stages"].get("scientific_validation"))
    entrypoints = tuple(ROOT.glob("scientific_validation.py")) + tuple(
        ROOT.glob("scientific_validation/**/__main__.py")
    )
    assert not enabled or entrypoints, (
        "scientific_validation está habilitada sin un entrypoint verificable"
    )
