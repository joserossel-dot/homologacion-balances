from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .gold_standard import GoldStandardCase, ValidationResult


class ValidationDataset:
    def __init__(self):
        self.cases: list[GoldStandardCase] = []
        self.results: list[ValidationResult] = []

    def add_case(self, case: GoldStandardCase) -> None:
        self.cases.append(case)

    def add_result(self, result: ValidationResult) -> None:
        self.results.append(result)

    def import_excel(self, path: str | Path) -> int:
        df = pd.read_excel(path)
        count = 0
        for _, row in df.iterrows():
            try:
                case = GoldStandardCase(
                    case_id=str(row.get("case_id", f"case_{count}")),
                    company=str(row.get("company", "")),
                    document=str(row.get("document", "")),
                    layout=str(row.get("layout", "")),
                    ocr_used=bool(row.get("ocr_used", False)),
                    account_name=str(row.get("account_name", "")),
                    original_amount=float(row.get("original_amount", 0)),
                    expected_code=str(row.get("expected_code", "")),
                    expected_concept=str(row.get("expected_concept", "")),
                    review_status=str(row.get("review_status", "pending")),
                    reviewer=str(row.get("reviewer", "")),
                    review_date=str(row.get("review_date", "")),
                    confidence_human=float(row.get("confidence_human", 0)),
                    comments=str(row.get("comments", "")),
                    source_document=str(row.get("source_document", "")),
                    page=int(row.get("page", 0)),
                    line=int(row.get("line", 0)),
                    decision_trace_reference=str(row.get("decision_trace_reference", "")),
                    parser_confidence=float(row.get("parser_confidence", 0)),
                    layout_confidence=float(row.get("layout_confidence", 0)),
                    column_mapping_confidence=float(row.get("column_mapping_confidence", 0)),
                    candidate_accept_rate=float(row.get("candidate_accept_rate", 0)),
                )
                self.add_case(case)
                count += 1
            except (ValueError, TypeError) as e:
                continue
        return count

    def export_excel(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = [c.to_dict() for c in self.cases]
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=GoldStandardCase.fields())
        df.to_excel(out, index=False)
        return out

    def export_csv(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = [c.to_dict() for c in self.cases]
        if rows:
            pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8")
        else:
            out.write_text(",".join(GoldStandardCase.fields()) + "\n", encoding="utf-8")
        return out

    def export_json(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cases": [c.to_dict() for c in self.cases],
            "results": [r.to_dict() for r in self.results],
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return out

    @property
    def pending(self) -> list[GoldStandardCase]:
        return [c for c in self.cases if c.review_status == "pending"]

    @property
    def reviewed(self) -> list[GoldStandardCase]:
        return [c for c in self.cases if c.review_status == "reviewed"]

    @property
    def total(self) -> int:
        return len(self.cases)

    def generate_template(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=GoldStandardCase.fields()).to_excel(out, index=False)
        return out

    def build_results_from_traces(
        self, traces_data: list[dict],
    ) -> list[ValidationResult]:
        results = []
        case_map = {c.case_id: c for c in self.cases}

        for trace in traces_data:
            case_id = trace.get("document_id", "")
            if case_id not in case_map:
                continue
            case = case_map[case_id]
            predicted = trace.get("official_classification", "UNKNOWN")
            expected = case.expected_code
            correct = predicted == expected
            decision_code = trace.get("decision_code", "")

            diff_reason = ""
            error_cat = "UNKNOWN"
            if not correct:
                if predicted == "UNKNOWN":
                    diff_reason = "System could not classify"
                    error_cat = "UNKNOWN"
                elif expected == "UNKNOWN":
                    diff_reason = "Human marked as UNKNOWN"
                    error_cat = "HUMAN"
                else:
                    diff_reason = f"Expected {expected}, got {predicted}"
                    if "Fuzzy" in decision_code:
                        error_cat = "FUZZY"
                    elif "Dictionary" in decision_code:
                        error_cat = "DICTIONARY"
                    elif "Variant" in decision_code:
                        error_cat = "CMCC"
                    elif "Shadow" in decision_code:
                        error_cat = "SHADOW"
                    else:
                        error_cat = "OTHER"

            results.append(ValidationResult(
                expected=expected,
                predicted=predicted,
                correct=correct,
                decision_type=trace.get("candidate_status", ""),
                decision_code=decision_code,
                confidence_system=trace.get("official_confidence", 0),
                confidence_human=case.confidence_human,
                difference_reason=diff_reason,
                error_category=error_cat,
                review_time_seconds=0.0,
            ))

        self.results = results
        return results
