from __future__ import annotations

from pathlib import Path

from document_context import DocumentContext
from document_context.models import ValidationData

from validation.balance_validator import BalanceValidator


class ValidationAdapter:
    def __init__(self, tolerance_pct: float = 1.0):
        self._validator = BalanceValidator(tolerance_pct=tolerance_pct)

    def run(self, ctx: DocumentContext) -> DocumentContext:
        classified = ctx.get_custom("classified", [])
        ignored = ctx.get_custom("ignored", [])
        metadata = ctx.metadata

        raw_accounts = []
        if ctx.parser and ctx.parser.raw_accounts:
            raw_accounts = [r.to_dict() if hasattr(r, "to_dict") else {"codigo": getattr(r, "codigo", ""), "nombre": getattr(r, "nombre", "")} for r in ctx.parser.raw_accounts]

        vr = self._validator.validate(
            source_file=Path(ctx.source_file).name,
            accounts_raw=raw_accounts,
            accounts_classified=classified,
            accounts_ignored=ignored,
            company=metadata.company if metadata else "",
            year=metadata.year if metadata else 0,
            pages=metadata.pages if metadata else 0,
        )

        validation = ValidationData(
            integrity=vr.integrity_score if hasattr(vr, "integrity_score") else None,
            subtotal_validation=vr.subtotal_results if hasattr(vr, "subtotal_results") else None,
            equation_validation=vr.equation_results if hasattr(vr, "equation_results") else None,
            missing_accounts=vr.missing_candidates if hasattr(vr, "missing_candidates") else None,
        )
        ctx.set_validation(validation, module="validation_adapter")
        ctx.set_custom("validation_result", vr)

        return ctx
