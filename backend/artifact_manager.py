from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.backend_models import BackendResult


class ArtifactManager:
    def __init__(self, base_dir: Path = Path("runs")):
        self.base_dir = Path(base_dir)

    def create_run_dir(self, source_file: str = "") -> Path:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc).strftime("%H%M%S")
        source_slug = ""
        if source_file:
            source_slug = "_" + Path(source_file).stem.replace(" ", "_")[:30]
        run_dir = self.base_dir / today / f"{now}{source_slug}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def save_json(self, run_dir: Path, name: str, data: Any) -> Path:
        path = run_dir / f"{name}.json"
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return path

    def save_markdown(self, run_dir: Path, name: str, content: str) -> Path:
        path = run_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def save_excel(self, run_dir: Path, name: str, result: BackendResult) -> Path:
        path = run_dir / f"{name}.xlsx"
        try:
            import pandas as pd
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                stats_df = pd.DataFrame([result.statistics.__dict__])
                stats_df.to_excel(writer, index=False, sheet_name="Statistics")

                coverage_df = pd.DataFrame([result.coverage]) if result.coverage else pd.DataFrame()
                if not coverage_df.empty:
                    coverage_df.to_excel(writer, index=False, sheet_name="Coverage")

                decisions_df = pd.DataFrame(result.decisions) if result.decisions else pd.DataFrame()
                if not decisions_df.empty:
                    decisions_df.to_excel(writer, index=False, sheet_name="Decisions")

                qa_df = pd.DataFrame([result.qa]) if result.qa else pd.DataFrame()
                if not qa_df.empty:
                    qa_df.to_excel(writer, index=False, sheet_name="QA")
        except Exception:
            path.write_text("Excel generation failed", encoding="utf-8")
        return path

    def save_all(self, result: BackendResult) -> dict[str, str]:
        run_dir = self.create_run_dir(result.source_file)
        paths: dict[str, str] = {}

        paths["result_json"] = str(self.save_json(run_dir, "result", result.to_dict()))
        paths["coverage_json"] = str(self.save_json(run_dir, "coverage", result.coverage))
        paths["decisions_json"] = str(self.save_json(run_dir, "decisions", result.decisions))
        paths["decision_stats_json"] = str(self.save_json(run_dir, "decision_stats", result.decision_stats))
        paths["qa_json"] = str(self.save_json(run_dir, "qa", result.qa))
        paths["execution_json"] = str(self.save_json(run_dir, "execution", {
            "status": result.execution.status,
            "elapsed_seconds": result.execution.elapsed_seconds,
            "module_timings": result.execution.module_timings,
            "errors": result.execution.errors,
        }))
        paths["logs_json"] = str(self.save_json(run_dir, "logs", result.logs))

        paths["summary_md"] = str(self.save_markdown(run_dir, "summary", self._build_summary_md(result)))
        paths["result_excel"] = str(self.save_excel(run_dir, "result_excel", result))

        result.export_paths = paths
        return paths

    def _build_summary_md(self, result: BackendResult) -> str:
        lines = [
            "# Backend Execution Summary",
            "",
            f"- **Source**: {result.source_file}",
            f"- **Timestamp**: {result.execution.start_time.isoformat()}",
            f"- **Status**: {result.execution.status}",
            f"- **Elapsed**: {result.execution.elapsed_seconds:.3f}s",
            f"- **Pipeline**: {result.pipeline_version}",
            "",
            "## Statistics",
            f"- Total accounts: {result.statistics.total_accounts}",
            f"- Classified: {result.statistics.classified}",
            f"- Unclassified: {result.statistics.unclassified}",
            f"- Ignored: {result.statistics.ignored}",
            f"- Coverage: {result.statistics.coverage_pct:.1%}",
            f"- Unknown: {result.statistics.unknown_pct:.1%}",
            f"- Learning hits: {result.statistics.learning_hits}",
            f"- QA Approved: {result.statistics.qa_approved}",
            f"- QA Confidence: {result.statistics.qa_confidence:.2%}",
            f"- Validation Score: {result.statistics.validation_score:.2%}",
            "",
            "## Module Timings",
        ]
        for mod, secs in sorted(result.execution.module_timings.items(), key=lambda x: -x[1]):
            lines.append(f"- {mod}: {secs:.3f}s")
        if result.execution.errors:
            lines.extend(["", "## Errors"])
            for err in result.execution.errors:
                lines.append(f"- [{err['module']}] {err['error']}")

        return "\n".join(lines)
