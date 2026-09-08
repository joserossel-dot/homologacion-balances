from __future__ import annotations

from pathlib import Path
import re

from scripts.audit_module_usage import build_inventory


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs" / "architecture" / "module_pruning_plan.md"


def test_pruning_plan_covers_every_current_static_orphan_once() -> None:
    report = build_inventory(ROOT)
    expected = set(report["findings"]["orphan_modules"])
    text = PLAN.read_text(encoding="utf-8")
    table = text.split("## Revisión por módulo", 1)[1].split(
        "## Lote seguro potencial", 1,
    )[0]
    documented = re.findall(r"^\| `([^`]+)` \|", table, flags=re.MULTILINE)
    assert len(documented) == len(set(documented))
    assert set(documented) == expected


def test_eliminable_modules_match_the_declared_potential_batch() -> None:
    text = PLAN.read_text(encoding="utf-8")
    table = text.split("## Revisión por módulo", 1)[1].split(
        "## Lote seguro potencial", 1,
    )[0]
    eliminable = {
        module
        for module, action in re.findall(
            r"^\| `([^`]+)` \|.*\| \*\*(ELIMINABLE|CONSERVAR|DECISIÓN HUMANA)\*\* \|$",
            table,
            flags=re.MULTILINE,
        )
        if action == "ELIMINABLE"
    }
    assert eliminable == {
        "learning.statistics",
        "pipeline.new_pipeline",
        "semantic.semantic_catalog",
        "src.api",
    }
