from __future__ import annotations

from enum import Enum

from .signature import CodePattern, Family, FormatSignature, LayoutType


class ExtractorType(str, Enum):
    UNIVERSAL = "UNIVERSAL"
    EXCEL_SII = "EXCEL_SII"
    PDF_LIBRE = "PDF_LIBRE"
    PDF_ESTANDAR = "PDF_ESTANDAR"
    EEFF_AUDITADOS = "EEFF_AUDITADOS"
    OCR_FALLBACK = "OCR_FALLBACK"
    DESCONOCIDO = "DESCONOCIDO"
    # Sprint 31 — vocabulario de decisión de parser (FASE 3).
    # La Factory SOLO decide; la extracción usa ParserPDF existente.
    STANDARD_PARSER = "STANDARD_PARSER"
    TABLE_PARSER = "TABLE_PARSER"
    OCR_PARSER = "OCR_PARSER"
    HORIZONTAL_PARSER = "HORIZONTAL_PARSER"
    UNKNOWN = "UNKNOWN"


# Traducción decisión clásica → vocabulario de parser (FASE 3).
_PARSER_DECISION_MAP: dict[ExtractorType, ExtractorType] = {
    ExtractorType.PDF_ESTANDAR: ExtractorType.STANDARD_PARSER,
    ExtractorType.EXCEL_SII: ExtractorType.TABLE_PARSER,
    ExtractorType.EEFF_AUDITADOS: ExtractorType.TABLE_PARSER,
    ExtractorType.PDF_LIBRE: ExtractorType.STANDARD_PARSER,
    ExtractorType.OCR_FALLBACK: ExtractorType.OCR_PARSER,
    ExtractorType.UNIVERSAL: ExtractorType.STANDARD_PARSER,
    ExtractorType.DESCONOCIDO: ExtractorType.UNKNOWN,
}


class ExtractorFactory:
    def __init__(self):
        self._rules = [
            (self._rule_excel_sii, ExtractorType.EXCEL_SII, 0.95),
            (self._rule_pdf_estandar, ExtractorType.PDF_ESTANDAR, 0.90),
            (self._rule_eeff_auditados, ExtractorType.EEFF_AUDITADOS, 0.85),
            (self._rule_pdf_libre, ExtractorType.PDF_LIBRE, 0.75),
            (self._rule_ocr_fallback, ExtractorType.OCR_FALLBACK, 0.60),
        ]

    def decide(self, sig: FormatSignature) -> ExtractorType:
        best_type = ExtractorType.DESCONOCIDO
        best_weight = 0.0

        for rule_fn, extractor_type, base_weight in self._rules:
            if rule_fn(sig):
                adjusted = base_weight * sig.confidence
                if adjusted > best_weight:
                    best_weight = adjusted
                    best_type = extractor_type

        return best_type

    def decide_parser(self, sig: FormatSignature) -> ExtractorType:
        """Decide el parser dentro del vocabulario Sprint 31 (FASE 3).

        Solo decide — la extracción sigue usando ParserPDF existente.
        Vocabulario: STANDARD_PARSER | TABLE_PARSER | OCR_PARSER |
                     HORIZONTAL_PARSER | UNKNOWN
        """
        decision = self.decide(sig)
        if sig.layout == LayoutType.HORIZONTAL:
            return ExtractorType.HORIZONTAL_PARSER
        return _PARSER_DECISION_MAP.get(decision, ExtractorType.UNKNOWN)

    def decide_with_detail(self, sig: FormatSignature) -> dict:
        extractor = self.decide(sig)
        reasons = []
        for rule_fn, extractor_type, base_weight in self._rules:
            if rule_fn(sig):
                reasons.append(
                    f"{extractor_type.value} (peso={base_weight}, "
                    f"confianza={sig.confidence:.2f})"
                )

        return {
            "extractor": extractor,
            "confidence": sig.confidence,
            "reasons": reasons,
            "family": sig.family.value,
        }

    def _rule_excel_sii(self, sig: FormatSignature) -> bool:
        return sig.family == Family.EXCEL_SII

    def _rule_pdf_estandar(self, sig: FormatSignature) -> bool:
        return (
            sig.family == Family.PDF_ESTANDAR
            and sig.code_pattern in (CodePattern.PUNTO, CodePattern.GUION)
            and sig.has_headers
        )

    def _rule_eeff_auditados(self, sig: FormatSignature) -> bool:
        return (
            sig.family == Family.EEFF_AUDITADOS
            and sig.layout == LayoutType.TABULAR
            and len(sig.columns) >= 3
        )

    def _rule_pdf_libre(self, sig: FormatSignature) -> bool:
        return (
            sig.family == Family.PDF_LIBRE
            or (
                sig.layout == LayoutType.LIBRE
                and sig.code_pattern == CodePattern.SIN_CODIGO
            )
        )

    def _rule_ocr_fallback(self, sig: FormatSignature) -> bool:
        return sig.ocr_required
