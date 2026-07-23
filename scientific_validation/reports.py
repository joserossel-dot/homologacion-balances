from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .agreement import Agreement
from .gold_standard import GoldStandardCase, ValidationResult
from .metrics import Metrics
from .validation_dataset import ValidationDataset


class ValidationReports:
    def __init__(self, dataset: ValidationDataset, metrics: Metrics,
                 agreement: Agreement | None = None):
        self.dataset = dataset
        self.metrics = metrics
        self.agreement = agreement

    def _results_df(self) -> pd.DataFrame:
        rows = [r.to_dict() for r in self.dataset.results]
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=ValidationResult.fields())

    def generate_gold_standard_template(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.dataset.generate_template(out)
        return out

    def generate_validation_dataset(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.dataset.export_excel(out)
        return out

    def generate_validation_summary(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        s = self.metrics.summary()
        rows = [
            {"metric": "Total Cases", "value": s["total"]},
            {"metric": "Correct", "value": s["correct"]},
            {"metric": "Incorrect", "value": s["incorrect"]},
            {"metric": "Accuracy", "value": f"{s['accuracy_pct']}%"},
            {"metric": "Macro F1", "value": s["macro_f1"]},
            {"metric": "Micro F1", "value": s["micro_f1"]},
            {"metric": "Unknown Rate", "value": f"{s['unknown_rate']}%"},
        ]
        pd.DataFrame(rows).to_excel(out, index=False)
        return out

    def generate_confusion_matrix(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        cm = self.metrics.confusion_matrix()
        cm.to_excel(out, index=False)
        return out

    def generate_error_analysis(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        errors = [r for r in self.dataset.results if not r.correct]
        rows = []
        for e in errors:
            rows.append({
                "expected": e.expected,
                "predicted": e.predicted,
                "error_category": e.error_category,
                "decision_code": e.decision_code,
                "confidence_system": e.confidence_system,
                "difference_reason": e.difference_reason,
            })
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
            "expected", "predicted", "error_category", "decision_code",
            "confidence_system", "difference_reason",
        ])
        df.to_excel(out, index=False)
        return out

    def generate_agreement_report(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if self.agreement:
            s = self.agreement.summary()
            rows = [
                {"metric": "Total Ratings", "value": s["n"]},
                {"metric": "Observed Agreement", "value": f"{s['observed_agreement_pct']}%"},
                {"metric": "Cohen Kappa", "value": s["cohen_kappa"]},
                {"metric": "Kappa Interpretation", "value": s["kappa_interpretation"]},
                {"metric": "Disagreements", "value": s["disagreements"]},
            ]
        else:
            rows = [{"metric": "Agreement Data", "value": "Not available (single rater)"}]
        pd.DataFrame(rows).to_excel(out, index=False)
        return out

    def generate_precision_dashboard(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        s = self.metrics.summary()
        rows = [{"Type": "Accuracy", "Value": s["accuracy_pct"]}]
        rows.append({"Type": "Macro F1", "Value": round(s["macro_f1"] * 100, 1)})
        rows.append({"Type": "Micro F1", "Value": round(s["micro_f1"] * 100, 1)})
        for pt in s.get("per_type_precision", []):
            rows.append({
                "Type": f"Precision ({pt['decision_type']})",
                "Value": round(pt["precision"] * 100, 1),
            })
        for dc in s.get("per_decision_code", []):
            rows.append({
                "Type": f"Precision ({dc['decision_code']})",
                "Value": round(dc["precision"] * 100, 1),
            })
        pd.DataFrame(rows).to_excel(out, index=False)
        return out

    def generate_markdown(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        s = self.metrics.summary()
        lines = ["# Scientific Validation Report", "",
                  f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", "",
                  "## 1. Dataset Overview", "",
                  f"**Total Cases Reviewed:** {s['total']}",
                  f"**Pending:** {len(self.dataset.pending)}",
                  f"**Reviewed:** {len(self.dataset.reviewed)}", ""]

        if s["total"] > 0:
            lines.append("## 2. Global Metrics")
            lines.append("")
            lines.append(f"**Accuracy:** {s['accuracy_pct']}%")
            lines.append(f"**Macro F1:** {s['macro_f1']}")
            lines.append(f"**Micro F1:** {s['micro_f1']}")
            lines.append(f"**Unknown Rate:** {s['unknown_rate']}%")
            lines.append("")

            lines.append("## 3. Precision by Decision Type")
            lines.append("")
            lines.append("| Type | Count | Precision |")
            lines.append("|---|---|---|")
            for pt in s.get("per_type_precision", []):
                lines.append(f"| {pt['decision_type']} | {pt['count']} | {round(pt['precision'] * 100, 1)}% |")
            lines.append("")

            lines.append("## 4. Top Errors")
            lines.append("")
            lines.append("| Category | Count |")
            lines.append("|---|---|")
            for e in s.get("top_errors", []):
                lines.append(f"| {e['category']} | {e['count']} |")
            lines.append("")

            error_by_cat = self.metrics.error_summary().get("by_category", {})
            if error_by_cat:
                lines.append("## 5. Error Distribution")
                lines.append("")
                for cat, cnt in sorted(error_by_cat.items(), key=lambda x: -x[1]):
                    lines.append(f"- {cat}: {cnt}")
                lines.append("")

            if self.agreement:
                ag = self.agreement.summary()
                lines.append("## 6. Inter-Rater Agreement")
                lines.append("")
                lines.append(f"**Observed Agreement:** {ag['observed_agreement_pct']}%")
                lines.append(f"**Cohen Kappa:** {ag['cohen_kappa']}")
                lines.append(f"**Interpretation:** {ag['kappa_interpretation']}")
                lines.append(f"**Disagreements:** {ag['disagreements']}")
                lines.append("")

            lines.append("## 7. Next Candidates for Review")
            lines.append("")
            pending_cases = self.dataset.pending[:10]
            if pending_cases:
                lines.append("| Case ID | Account | Expected |")
                lines.append("|---|---|---|")
                for c in pending_cases:
                    lines.append(f"| {c.case_id} | {c.account_name[:40]} | {c.expected_code} |")
            else:
                lines.append("No pending cases.")
            lines.append("")
        else:
            lines.append("## Empty Dataset")
            lines.append("")
            lines.append("No validation data available. Populate the Gold Standard template and import cases.")
            lines.append("")

        lines.append("*Scientific validation framework — no production files were modified.*")
        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    def generate_statistics_json(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        s = self.metrics.summary()
        data = {
            "dataset": {
                "total": self.dataset.total,
                "pending": len(self.dataset.pending),
                "reviewed": len(self.dataset.reviewed),
            },
            "metrics": s,
            "agreement": self.agreement.summary() if self.agreement else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return out

    @staticmethod
    def generate_all(dataset: ValidationDataset, metrics: Metrics,
                     agreement: Agreement | None, output_dir: str | Path) -> dict[str, Path]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        r = ValidationReports(dataset, metrics, agreement)
        return {
            "gold_standard_template": r.generate_gold_standard_template(out_dir / "gold_standard_template.xlsx"),
            "validation_dataset": r.generate_validation_dataset(out_dir / "validation_dataset.xlsx"),
            "validation_summary": r.generate_validation_summary(out_dir / "validation_summary.xlsx"),
            "confusion_matrix": r.generate_confusion_matrix(out_dir / "confusion_matrix.xlsx"),
            "error_analysis": r.generate_error_analysis(out_dir / "error_analysis.xlsx"),
            "agreement_report": r.generate_agreement_report(out_dir / "agreement_report.xlsx"),
            "precision_dashboard": r.generate_precision_dashboard(out_dir / "precision_dashboard.xlsx"),
            "scientific_validation_md": r.generate_markdown(out_dir / "scientific_validation.md"),
            "validation_statistics": r.generate_statistics_json(out_dir / "validation_statistics.json"),
        }
