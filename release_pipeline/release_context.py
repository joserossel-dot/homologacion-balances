from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ReleaseContext:
    release_id: str
    timestamp: str
    git_commit: str
    git_branch: str
    python_version: str
    cmcc_version: str
    dictionary_hash: str
    parser_version: str
    snapshot_id: str
    validation_dataset_version: str
    quality_snapshot: dict | None
    knowledge_snapshot: dict | None
    tests_passed: int
    tests_failed: int
    execution_time: float

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def create(
        release_id: str | None = None,
        quality_snapshot: dict | None = None,
        knowledge_snapshot: dict | None = None,
    ) -> ReleaseContext:
        rid = release_id or datetime.now(timezone.utc).strftime("REL_%Y%m%d_%H%M%S")
        git_commit = "unknown"
        git_branch = "unknown"
        try:
            r = subprocess.run(["git", "log", "--oneline", "-1"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                git_commit = r.stdout.strip()[:40]
            r2 = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                capture_output=True, text=True, timeout=5)
            if r2.returncode == 0:
                git_branch = r2.stdout.strip()
        except Exception:
            pass

        import sys
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        cmcc_hash = ""
        cmcc_path = Path("knowledge/cmcc.json")
        if cmcc_path.exists():
            try:
                with open(cmcc_path) as f:
                    cmcc_bytes = json.dumps(json.load(f), sort_keys=True).encode("utf-8")
                import hashlib
                cmcc_hash = hashlib.sha256(cmcc_bytes).hexdigest()[:16]
            except Exception:
                pass

        return ReleaseContext(
            release_id=rid,
            timestamp=datetime.now(timezone.utc).isoformat(),
            git_commit=git_commit,
            git_branch=git_branch,
            python_version=py_ver,
            cmcc_version="1.0",
            dictionary_hash=cmcc_hash,
            parser_version="3.0",
            snapshot_id=quality_snapshot.get("snapshot_id", "") if quality_snapshot else "",
            validation_dataset_version="1.0",
            quality_snapshot=quality_snapshot,
            knowledge_snapshot=knowledge_snapshot,
            tests_passed=0,
            tests_failed=0,
            execution_time=0.0,
        )
