from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any


@dataclass
class MonetaryAmounts:
    assets: float | None = None
    liabilities: float | None = None
    losses: float | None = None
    profits: float | None = None
    debit: float | None = None
    credit: float | None = None
    balance_debit: float | None = None
    balance_credit: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MonetaryAmounts:
        if not data:
            return cls()
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})


@dataclass
class AccountEvidence:
    record_id: str = ""

    # -- Source provenance --
    source_file: str = ""
    source_group: str = ""
    source_page: int = 0
    sheet_name: str = ""
    row_number: int = 0
    column_number: int = 0

    # -- Company --
    company_name: str = ""
    company_rut: str = ""
    company_business: str = ""
    year: str = ""

    # -- Parsing --
    parser_used: str = ""
    ocr_used: str = ""
    document_type: str = ""

    # -- Account identifiers --
    original_account_code: str = ""
    clean_account_code: str = ""
    original_account_name: str = ""
    clean_account_name: str = ""

    # -- Classification --
    classification_method: str = ""
    classification_confidence: float = 0.0
    learning_hit: bool = False
    semantic_hit: bool = False
    semantic_rule: str = ""
    semantic_type: str = ""
    dictionary_match: str = ""
    gold_standard_match: str = ""
    final_code: str = ""
    final_confidence: float = 0.0

    # -- Monetary amounts (preserved from source) --
    monetary: MonetaryAmounts = field(default_factory=MonetaryAmounts)
    classification_amount: float = 0.0
    currency: str = "CLP"
    sign: str = ""
    expected_side: str = ""

    # -- Context --
    context_before: list[dict] = field(default_factory=list)
    context_after: list[dict] = field(default_factory=list)
    raw_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- Source reference --
    source_path: str = ""
    source_raw: dict[str, Any] | None = None

    # -- Validation --
    warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        result = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "monetary":
                result[f.name] = value.to_dict()
            elif f.name == "context_before":
                result[f.name] = list(value) if value else []
            elif f.name == "context_after":
                result[f.name] = list(value) if value else []
            elif f.name == "metadata":
                result[f.name] = dict(value) if value else {}
            elif f.name == "source_raw":
                result[f.name] = value
            elif f.name == "warnings":
                result[f.name] = list(value) if value else []
            else:
                result[f.name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountEvidence:
        valid = {f.name for f in fields(cls)}
        filtered = {}
        for k, v in data.items():
            if k in valid:
                filtered[k] = v
        monetary_data = filtered.pop("monetary", None) or filtered.pop("amounts", None)
        instance = cls(**{k: v for k, v in filtered.items() if k != "amounts"})
        if isinstance(monetary_data, dict):
            instance.monetary = MonetaryAmounts.from_dict(monetary_data)
        return instance

    @property
    def is_complete(self) -> bool:
        return bool(
            self.source_file
            and self.source_page > 0
            and self.company_name
            and self.original_account_name
        )

    @property
    def has_amounts(self) -> bool:
        m = self.monetary
        return any(
            x is not None and x != 0.0
            for x in [m.assets, m.liabilities, m.losses, m.profits, m.debit, m.credit]
        )

    @property
    def has_context(self) -> bool:
        return bool(self.context_before or self.context_after)

    @property
    def coverage_score(self) -> float:
        score = 0.0
        total = 18
        if self.source_file:
            score += 1
        if self.source_page > 0:
            score += 1
        if self.company_name:
            score += 1
        if self.company_rut:
            score += 1
        if self.company_business:
            score += 1
        if self.year:
            score += 1
        if self.original_account_name:
            score += 1
        if self.clean_account_name:
            score += 1
        if self.has_amounts:
            score += 1
        if self.classification_amount != 0.0:
            score += 1
        if self.parser_used:
            score += 1
        if self.document_type:
            score += 1
        if self.sheet_name:
            score += 1
        if self.row_number > 0:
            score += 1
        if self.has_context:
            score += 1
        if self.classification_method:
            score += 1
        if self.final_code:
            score += 1
        if self.metadata:
            score += 1
        return round(score / total * 100, 1)

    def missing_fields(self) -> list[str]:
        missing = []
        checks = {
            "source_file": self.source_file,
            "source_page > 0": self.source_page > 0,
            "company_name": self.company_name,
            "company_rut": self.company_rut,
            "company_business": self.company_business,
            "year": self.year,
            "original_account_name": self.original_account_name,
            "clean_account_name": self.clean_account_name,
            "monetary_amounts": self.has_amounts,
            "classification_amount": self.classification_amount != 0.0,
            "parser_used": self.parser_used,
            "document_type": self.document_type,
            "sheet_name": self.sheet_name,
            "row_number > 0": self.row_number > 0,
            "context (before/after)": self.has_context,
            "classification_method": bool(self.classification_method),
            "final_code": bool(self.final_code),
        }
        for label, ok in checks.items():
            if not ok:
                missing.append(label)
        return missing
