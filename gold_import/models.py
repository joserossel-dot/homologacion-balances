from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportResult:
    total_in_template: int = 0
    reviewed_in_template: int = 0
    unreviewed_in_template: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    snapshot_before: str = ""
    snapshot_after: str = ""
    report_xlsx: str = ""
    report_md: str = ""
    reviewer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_in_template": self.total_in_template,
            "reviewed_in_template": self.reviewed_in_template,
            "unreviewed_in_template": self.unreviewed_in_template,
            "imported": self.imported,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "warnings": self.warnings,
            "snapshot_before": self.snapshot_before,
            "snapshot_after": self.snapshot_after,
            "report_xlsx": self.report_xlsx,
            "report_md": self.report_md,
            "reviewer": self.reviewer,
        }
