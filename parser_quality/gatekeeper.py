from dataclasses import dataclass, field
from typing import Any, Optional

from parser_quality.candidate_validator import EvidenceResult
from parser_quality.parser_confidence import ParserConfidence
from parser_quality.rejection_reasons import RejectionReason


@dataclass
class GatekeeperResult:
    file_name: str
    line_number: int
    account_name: str
    account_code: Optional[str]
    monto: Optional[float]
    confidence: float
    status: str
    reasons: list[RejectionReason] = field(default_factory=list)
    positive_signals: dict[RejectionReason, float] = field(default_factory=dict)
    negative_signals: dict[RejectionReason, float] = field(default_factory=dict)
    requirio_ocr: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "line_number": self.line_number,
            "account_name": self.account_name,
            "account_code": self.account_code,
            "monto": self.monto,
            "confidence": self.confidence,
            "status": self.status,
            "reasons": [str(r) for r in self.reasons],
            "requirio_ocr": self.requirio_ocr,
        }


class ParserGatekeeper:
    """
    Shadow-mode gatekeeper: evalúa cada cuenta extraída por el parser
    pero NO bloquea su procesamiento. Solo registra la decisión.
    """

    def __init__(self) -> None:
        self._confidence = ParserConfidence()
        self._results: list[GatekeeperResult] = []

    def evaluate(
        self,
        file_name: str,
        line_number: int,
        line: str,
        account_name: str,
        account_code: Optional[str] = None,
        monto: Optional[float] = None,
        is_total: bool = False,
        requirio_ocr: bool = False,
    ) -> GatekeeperResult:
        evidence = self._confidence.calculate(
            line=line,
            name=account_name,
            code=account_code,
            monto=monto,
            is_total=is_total,
            requirio_ocr=requirio_ocr,
        )

        status = ParserConfidence.determine_status(evidence.confidence)

        result = GatekeeperResult(
            file_name=file_name,
            line_number=line_number,
            account_name=account_name,
            account_code=account_code,
            monto=monto,
            confidence=evidence.confidence,
            status=status,
            reasons=evidence.reasons,
            positive_signals=evidence.positive_signals,
            negative_signals=evidence.negative_signals,
            requirio_ocr=requirio_ocr,
        )

        self._results.append(result)
        return result

    @property
    def results(self) -> list[GatekeeperResult]:
        return list(self._results)

    def clear(self) -> None:
        self._results.clear()
