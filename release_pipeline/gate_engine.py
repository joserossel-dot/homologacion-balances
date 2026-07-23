from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateStatus(Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@dataclass
class GateResult:
    gate_id: str
    gate_name: str
    status: GateStatus
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    report_path: str = ""

    def to_dict(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "status": self.status.value,
            "message": self.message,
            "evidence": {k: (str(v) if not isinstance(v, (int, float, bool, type(None), list, dict)) else v) for k, v in self.evidence.items()},
            "report_path": self.report_path,
        }


class GateEngine:
    def __init__(self, config: dict):
        self.config = config.get("gates", {})

    def run_all(self, context: dict) -> list[GateResult]:
        return [
            self.test_gate(context),
            self.validation_gate(context),
            self.quality_gate(context),
            self.drift_gate(context),
            self.unknown_gate(context),
            self.parser_gate(context),
            self.cmcc_gate(context),
        ]

    def test_gate(self, context: dict) -> GateResult:
        tests_passed = context.get("tests_passed", 0)
        tests_failed = context.get("tests_failed", 0)
        total = tests_passed + tests_failed
        required_pct = self.config.get("required_tests_pct", 100.0)
        actual_pct = (tests_passed / total * 100) if total > 0 else 0
        report_path = "reports/quality_monitoring/quality_monitoring.md"
        if total == 0:
            return GateResult("TEST_GATE", "Run Tests", GateStatus.FAIL,
                              "No tests executed", {"total": 0, "passed": 0, "failed": 0}, report_path)
        if tests_failed > 0:
            return GateResult("TEST_GATE", "Run Tests", GateStatus.FAIL,
                              f"{tests_failed} test(s) failed",
                              {"total": total, "passed": tests_passed, "failed": tests_failed}, report_path)
        if actual_pct < required_pct:
            return GateResult("TEST_GATE", "Run Tests", GateStatus.FAIL,
                              f"Only {actual_pct:.1f}% tests passed, required {required_pct:.0f}%",
                              {"total": total, "passed": tests_passed, "failed": tests_failed}, report_path)
        return GateResult("TEST_GATE", "Run Tests", GateStatus.PASS,
                          f"All {total} tests passed",
                          {"total": total, "passed": tests_passed, "failed": tests_failed}, report_path)

    def validation_gate(self, context: dict) -> GateResult:
        accuracy = context.get("validation_metrics", {}).get("accuracy", 1.0)
        min_accuracy = self.config.get("min_accuracy", 0.0)
        if accuracy < min_accuracy:
            return GateResult("VALIDATION_GATE", "Scientific Validation", GateStatus.FAIL,
                              f"Accuracy {accuracy:.1%} below minimum {min_accuracy:.1%}",
                              {"accuracy": accuracy, "min_accuracy": min_accuracy},
                              "reports/scientific_validation/scientific_validation_report.md")
        if accuracy < min_accuracy + 0.05:
            return GateResult("VALIDATION_GATE", "Scientific Validation", GateStatus.WARNING,
                              f"Accuracy {accuracy:.1%} near minimum threshold",
                              {"accuracy": accuracy, "min_accuracy": min_accuracy},
                              "reports/scientific_validation/scientific_validation_report.md")
        return GateResult("VALIDATION_GATE", "Scientific Validation", GateStatus.PASS,
                          f"Accuracy {accuracy:.1%} meets threshold",
                          {"accuracy": accuracy, "min_accuracy": min_accuracy},
                          "reports/scientific_validation/scientific_validation_report.md")

    def quality_gate(self, context: dict) -> GateResult:
        alerts = context.get("alerts", [])
        critical = [a for a in alerts if isinstance(a, dict) and a.get("severity") == "CRITICAL"]
        high = [a for a in alerts if isinstance(a, dict) and a.get("severity") == "HIGH"]
        max_critical = self.config.get("critical_alerts_max", 0)
        max_high = self.config.get("high_alerts_max", 3)
        report_path = "reports/quality_monitoring/quality_monitoring.md"
        if len(critical) > max_critical:
            return GateResult("QUALITY_GATE", "Quality Control", GateStatus.FAIL,
                              f"{len(critical)} critical alert(s) exceed limit of {max_critical}",
                              {"critical": len(critical), "high": len(high), "max_critical": max_critical, "max_high": max_high},
                              report_path)
        if len(high) > max_high:
            return GateResult("QUALITY_GATE", "Quality Control", GateStatus.WARNING,
                              f"{len(high)} high alert(s) exceed limit of {max_high}",
                              {"critical": len(critical), "high": len(high), "max_critical": max_critical, "max_high": max_high},
                              report_path)
        return GateResult("QUALITY_GATE", "Quality Control", GateStatus.PASS,
                          f"Alerts within limits ({len(critical)} critical, {len(high)} high)",
                          {"critical": len(critical), "high": len(high), "max_critical": max_critical, "max_high": max_high},
                          report_path)

    def drift_gate(self, context: dict) -> GateResult:
        coverage_drop = context.get("drift_metrics", {}).get("coverage_drop_pct", 0)
        max_drop = self.config.get("coverage_drop_pct", 2.0)
        report_path = "reports/quality_monitoring/quality_monitoring.md"
        if coverage_drop > max_drop:
            return GateResult("DRIFT_GATE", "Coverage Drift", GateStatus.FAIL,
                              f"Coverage dropped {coverage_drop:.1f}pp, exceeds limit of {max_drop}pp",
                              {"coverage_drop_pct": coverage_drop, "max_drop_pct": max_drop}, report_path)
        coverage_drop_warn = max_drop * 0.5
        if coverage_drop > coverage_drop_warn:
            return GateResult("DRIFT_GATE", "Coverage Drift", GateStatus.WARNING,
                              f"Coverage dropped {coverage_drop:.1f}pp, approaching limit of {max_drop}pp",
                              {"coverage_drop_pct": coverage_drop, "max_drop_pct": max_drop}, report_path)
        return GateResult("DRIFT_GATE", "Coverage Drift", GateStatus.PASS,
                          f"Coverage drift within limits ({coverage_drop:.1f}pp)",
                          {"coverage_drop_pct": coverage_drop, "max_drop_pct": max_drop}, report_path)

    def unknown_gate(self, context: dict) -> GateResult:
        unknown_growth = context.get("drift_metrics", {}).get("unknown_growth_abs", 0)
        max_growth = self.config.get("unknown_growth_abs", 500)
        unknown_growth_pct = context.get("drift_metrics", {}).get("unknown_growth_pct", 0)
        max_growth_pct = self.config.get("unknown_growth_pct", 5.0)
        report_path = "reports/quality_monitoring/quality_monitoring.md"
        if unknown_growth > max_growth:
            return GateResult("UNKNOWN_GATE", "UNKNOWN Growth", GateStatus.FAIL,
                              f"UNKNOWN grew by {unknown_growth}, exceeds limit of {max_growth}",
                              {"growth_abs": unknown_growth, "growth_pct": unknown_growth_pct,
                               "max_abs": max_growth, "max_pct": max_growth_pct}, report_path)
        if unknown_growth_pct > max_growth_pct:
            return GateResult("UNKNOWN_GATE", "UNKNOWN Growth", GateStatus.WARNING,
                              f"UNKNOWN grew {unknown_growth_pct:.1f}%, approaching limit of {max_growth_pct}%",
                              {"growth_abs": unknown_growth, "growth_pct": unknown_growth_pct,
                               "max_abs": max_growth, "max_pct": max_growth_pct}, report_path)
        return GateResult("UNKNOWN_GATE", "UNKNOWN Growth", GateStatus.PASS,
                          f"UNKNOWN growth within limits ({unknown_growth} abs, {unknown_growth_pct:.1f}%)",
                          {"growth_abs": unknown_growth, "growth_pct": unknown_growth_pct,
                           "max_abs": max_growth, "max_pct": max_growth_pct}, report_path)

    def parser_gate(self, context: dict) -> GateResult:
        parser_confidence = context.get("quality_metrics", {}).get("parser_confidence", 1.0)
        min_confidence = self.config.get("parser_confidence_min", 0.5)
        report_path = "reports/quality_monitoring/quality_monitoring.md"
        if parser_confidence < min_confidence:
            return GateResult("PARSER_GATE", "Parser Confidence", GateStatus.FAIL,
                              f"Parser confidence {parser_confidence:.2f} below minimum {min_confidence:.2f}",
                              {"parser_confidence": parser_confidence, "min_confidence": min_confidence}, report_path)
        threshold_warn = min_confidence + 0.1
        if parser_confidence < threshold_warn:
            return GateResult("PARSER_GATE", "Parser Confidence", GateStatus.WARNING,
                              f"Parser confidence {parser_confidence:.2f} near minimum threshold",
                              {"parser_confidence": parser_confidence, "min_confidence": min_confidence}, report_path)
        return GateResult("PARSER_GATE", "Parser Confidence", GateStatus.PASS,
                          f"Parser confidence {parser_confidence:.2f} meets minimum {min_confidence:.2f}",
                          {"parser_confidence": parser_confidence, "min_confidence": min_confidence}, report_path)

    def cmcc_gate(self, context: dict) -> GateResult:
        cmcc_hash = context.get("dictionary_hash", "unknown")
        expected_hash = context.get("cmcc_expected_hash", cmcc_hash)
        concept_count = context.get("cmcc_concept_count", 52)
        report_path = "knowledge/cmcc.json"
        if cmcc_hash != expected_hash:
            return GateResult("CMCC_GATE", "CMCC Integrity", GateStatus.FAIL,
                              f"CMCC hash mismatch: {cmcc_hash[:8]} != {expected_hash[:8]}",
                              {"hash": cmcc_hash, "expected": expected_hash, "concepts": concept_count}, report_path)
        if concept_count < 52:
            return GateResult("CMCC_GATE", "CMCC Integrity", GateStatus.FAIL,
                              f"CMCC concept count {concept_count} below expected 52",
                              {"concepts": concept_count, "expected": 52}, report_path)
        return GateResult("CMCC_GATE", "CMCC Integrity", GateStatus.PASS,
                          f"CMCC intact: {concept_count} concepts, hash {cmcc_hash[:8]}",
                          {"hash": cmcc_hash, "concepts": concept_count}, report_path)
