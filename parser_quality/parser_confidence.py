from typing import Optional

from parser_quality.candidate_validator import CandidateValidator, EvidenceResult


class ParserConfidence:
    """
    Calcula un score de confianza determinístico (0.00-1.00) para cada
    línea extraída por el parser, basado en evidencia positiva y negativa.
    """

    def __init__(self) -> None:
        self._validator = CandidateValidator()

    def calculate(
        self,
        line: str,
        name: str,
        code: Optional[str] = None,
        monto: Optional[float] = None,
        is_total: bool = False,
        requirio_ocr: bool = False,
    ) -> EvidenceResult:
        return self._validator.evaluate(
            line=line,
            name=name,
            code=code,
            monto=monto,
            is_total=is_total,
            requirio_ocr=requirio_ocr,
        )

    @staticmethod
    def determine_status(confidence: float) -> str:
        if confidence >= 0.85:
            return "ACCEPT"
        elif confidence >= 0.50:
            return "REVIEW"
        else:
            return "REJECT"
