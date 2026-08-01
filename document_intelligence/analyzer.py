from __future__ import annotations

from .detector import (
    CodePatternDetector,
    ColumnDetector,
    DocumentTypeDetector,
    HeaderDetector,
    LayoutDetector,
    NumericPatternDetector,
)
from .signature import CodePattern, Family, FormatSignature, LayoutType


class FormatAnalyzer:
    def __init__(self):
        self.detectors = [
            ("headers", HeaderDetector()),
            ("layout", LayoutDetector()),
            ("columns", ColumnDetector()),
            ("code_pattern", CodePatternDetector()),
            ("numeric_pattern", NumericPatternDetector()),
            ("document_type", DocumentTypeDetector()),
        ]

    def analyze(self, lines: list[str]) -> FormatSignature:
        if not lines:
            return FormatSignature()

        results: dict[str, dict] = {}
        for name, detector in self.detectors:
            try:
                results[name] = detector.detect(lines)
            except Exception:
                results[name] = {}

        sig = FormatSignature()

        hdr = results.get("headers", {})
        sig.has_headers = hdr.get("has_headers", False)
        sig.company_name = hdr.get("company_name", "")
        sig.has_totals = any(
            l.strip().lower().startswith(("total", "subtotal", "suma"))
            for l in lines[:80]
        )

        lyt = results.get("layout", {})
        sig.layout = lyt.get("layout", sig.layout)
        sig.orientation = lyt.get("orientation", sig.orientation)

        col = results.get("columns", {})
        sig.columns = col.get("columns", [])

        cp = results.get("code_pattern", {})
        sig.code_pattern = cp.get("code_pattern", sig.code_pattern)

        np_ = results.get("numeric_pattern", {})
        sig.numeric_pattern = np_.get("numeric_pattern", sig.numeric_pattern)

        dt = results.get("document_type", {})
        sig.document_type = dt.get("document_type", sig.document_type)

        sig.confidence = self._compute_global_confidence(results)

        sig.family = self._infer_family(sig)

        return sig

    def analyze_text(self, text: str) -> FormatSignature:
        lines = [l for l in text.split("\n") if l.strip()]
        return self.analyze(lines)

    def _compute_global_confidence(self, results: dict[str, dict]) -> float:
        confidences = [
            v.get("confidence", 0.0)
            for v in results.values()
            if isinstance(v, dict)
        ]
        if not confidences:
            return 0.0
        n = len(confidences)
        if n == 0:
            return 0.0
        base = sum(confidences) / n
        high_count = sum(1 for c in confidences if c >= 0.8)
        boost = high_count * 0.05
        return min(0.99, base + boost)

    def _infer_family(self, sig: FormatSignature) -> Family:
        if sig.code_pattern in (CodePattern.PUNTO, CodePattern.GUION) and sig.has_headers and sig.has_totals:
            return Family.PDF_ESTANDAR

        if sig.layout == LayoutType.TABULAR and len(sig.columns) >= 3:
            return Family.EEFF_AUDITADOS

        if sig.layout == LayoutType.HORIZONTAL and sig.code_pattern in (CodePattern.PUNTO, CodePattern.GUION):
            return Family.CLASIFICADO

        if sig.code_pattern == CodePattern.SIN_CODIGO and len(sig.columns) <= 2:
            return Family.BALANCE_SIMPLE

        if sig.ocr_required:
            return Family.PDF_LIBRE

        return Family.DESCONOCIDO
