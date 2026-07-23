from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DocumentMetrics:
    layout_confidence: float = 0.0
    ocr_confidence: float = 0.0
    parser_confidence: float = 0.0
    column_mapping_confidence: float = 0.0
    header_quality: float = 0.0
    candidate_accept_rate: float = 0.0
    contamination_rate: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "layout_confidence": self.layout_confidence,
            "ocr_confidence": self.ocr_confidence,
            "parser_confidence": self.parser_confidence,
            "column_mapping_confidence": self.column_mapping_confidence,
            "header_quality": self.header_quality,
            "candidate_accept_rate": self.candidate_accept_rate,
            "contamination_rate": self.contamination_rate,
        }


class DocumentAssessment:
    METRICS = [
        "layout_confidence",
        "ocr_confidence",
        "parser_confidence",
        "column_mapping_confidence",
        "header_quality",
        "candidate_accept_rate",
        "contamination_rate",
    ]

    def assess(self, doc: dict[str, Any]) -> DocumentMetrics:
        m = DocumentMetrics()
        m.layout_confidence = self._layout_confidence(doc)
        m.ocr_confidence = self._ocr_confidence(doc)
        m.parser_confidence = self._parser_confidence(doc)
        m.column_mapping_confidence = self._column_mapping_confidence(doc)
        m.header_quality = self._header_quality(doc)
        m.candidate_accept_rate = self._candidate_accept_rate(doc)
        m.contamination_rate = self._contamination_rate(doc)
        return m

    def _layout_confidence(self, doc: dict[str, Any]) -> float:
        group = str(doc.get("group", "")).lower()

        if not group:
            return 0.0

        compatible = str(doc.get("compatible", "")).upper()
        signature = str(doc.get("layout_signature", ""))
        risk = float(doc.get("risk_score", 0))

        if group == "validacion":
            base = 0.9
        elif group == "edge_cases":
            base = 0.5
        else:
            base = 0.3

        if compatible == "SI":
            base += 0.1
        elif compatible == "NO":
            base -= 0.2
        elif compatible == "PARCIAL":
            base -= 0.1

        if signature and signature != "SIN_HEADERS_DETECTADOS":
            base += 0.05

        if risk > 70:
            base -= 0.2
        elif risk > 50:
            base -= 0.1

        return max(0.0, min(1.0, base))

    def _ocr_confidence(self, doc: dict[str, Any]) -> float:
        file_type = str(doc.get("file_type", "")).lower()
        requirio_ocr = doc.get("requirio_ocr", None)

        if requirio_ocr is None and not file_type:
            return 0.0

        if file_type in ("xlsx", "xls"):
            return 1.0

        if requirio_ocr is None:
            requirio_ocr = False

        ocr_noise_pct = float(doc.get("ocr_noise_pct", 0))
        ocr_pages = int(doc.get("ocr_pages", 0))
        total_pages = int(doc.get("pages", 1))

        if not requirio_ocr:
            base = 0.95
            has_text = int(doc.get("total_lines", 0))
            if has_text == 0:
                base = 0.5
            return base

        base = 0.6

        if ocr_noise_pct > 50:
            base -= 0.2
        elif ocr_noise_pct > 30:
            base -= 0.1

        if total_pages > 0:
            ocr_ratio = ocr_pages / total_pages
            if ocr_ratio > 0.8:
                base += 0.1
            elif ocr_ratio < 0.3:
                base -= 0.1

        return max(0.0, min(1.0, base))

    def _parser_confidence(self, doc: dict[str, Any]) -> float:
        total = int(doc.get("accounts_total", 0))
        classified = int(doc.get("accounts_classified", 0))
        ignored = int(doc.get("accounts_ignored", 0))
        has_parser_error = bool(doc.get("parser_error", ""))

        if has_parser_error:
            return 0.1

        if total == 0:
            return 0.0

        classify_rate = classified / total if total > 0 else 0.0

        if classify_rate >= 0.5:
            base = 0.8
        elif classify_rate >= 0.3:
            base = 0.6
        elif classify_rate >= 0.1:
            base = 0.4
        else:
            base = 0.2

        if ignored > 0:
            ignored_rate = ignored / total if total > 0 else 0.0
            if ignored_rate > 0.8:
                base -= 0.2
            elif ignored_rate > 0.5:
                base -= 0.1

        return max(0.0, min(1.0, base))

    def _column_mapping_confidence(self, doc: dict[str, Any]) -> float:
        compatible = str(doc.get("compatible", "")).upper()
        num_headers = int(doc.get("num_headers", 0))
        unknown_origin_pct = float(doc.get("unknown_origin_pct", 0))
        group = str(doc.get("group", "")).lower()

        if not group:
            return 0.0

        if group == "validacion":
            base = 0.85
        else:
            base = 0.5

        if compatible == "SI":
            base += 0.15
        elif compatible == "NO":
            base -= 0.2

        if num_headers >= 4:
            base += 0.1
        elif num_headers == 0:
            base -= 0.1

        if unknown_origin_pct > 50:
            base -= 0.3
        elif unknown_origin_pct > 25:
            base -= 0.15

        return max(0.0, min(1.0, base))

    def _header_quality(self, doc: dict[str, Any]) -> float:
        signature = str(doc.get("layout_signature", ""))
        num_headers = int(doc.get("num_headers", 0))
        has_headers = signature != "" and signature != "SIN_HEADERS_DETECTADOS"

        if not has_headers or num_headers == 0:
            return 0.0

        if num_headers >= 4:
            base = 0.9
        elif num_headers >= 2:
            base = 0.6
        else:
            base = 0.3

        known_patterns = [
            "activo", "pasivo", "perdida", "ganancia",
            "deudor", "acreedor", "debe", "haber",
        ]
        sig_lower = signature.lower()
        matched = sum(1 for p in known_patterns if p in sig_lower)
        if matched >= 3:
            base += 0.1

        return max(0.0, min(1.0, base))

    def _candidate_accept_rate(self, doc: dict[str, Any]) -> float:
        accepted = int(doc.get("gatekeeper_accepted", 0))
        reviewed = int(doc.get("gatekeeper_review", 0))
        rejected = int(doc.get("gatekeeper_rejected", 0))
        total = accepted + reviewed + rejected

        if total == 0:
            classified = int(doc.get("accounts_classified", 0))
            total_accounts = int(doc.get("accounts_total", 0))
            if total_accounts > 0:
                return round(classified / total_accounts, 4)
            return 0.0

        return round(accepted / total, 4)

    def _contamination_rate(self, doc: dict[str, Any]) -> float:
        contamination_pct = float(doc.get("contamination_pct", -1))
        if contamination_pct >= 0:
            return round(contamination_pct / 100.0, 4)

        empty = int(doc.get("empty_lines", 0))
        noise = int(doc.get("other_noise_lines", 0))
        total_lines = int(doc.get("total_lines", 0))

        if total_lines == 0:
            return 0.0

        contaminated = empty + noise + int(doc.get("header_lines", 0))
        contaminated += int(doc.get("footer_lines", 0))
        contaminated += int(doc.get("date_lines", 0))
        contaminated += int(doc.get("rut_lines", 0))
        contaminated += int(doc.get("address_lines", 0))
        contaminated += int(doc.get("page_num_lines", 0))

        return round(min(contaminated / total_lines, 1.0), 4)
