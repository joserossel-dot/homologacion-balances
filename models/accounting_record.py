#!/usr/bin/env python3
"""Canonical Data Model for accounting records extracted from PDFs.

This dataclass defines the official contract shared by all extractors.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime
from typing import Any


@dataclass
class AccountingRecord:
    """Standardised accounting record extracted from a financial document."""

    # --- Identity ---
    record_id: str = ""
    source_file: str = ""
    source_page: int = 0
    source_table: int = 0
    source_row: int = 0

    # --- Account ---
    account_code: str = ""
    account_name: str = ""

    # --- Monetary values ---
    debit: float | None = None
    credit: float | None = None
    balance_debit: float | None = None
    balance_credit: float | None = None

    # --- Processing ---
    extractor: str = ""
    confidence: float = 1.0

    # --- Metadata ---
    raw_row: list[str | None] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-compatible dictionary.

        Fields with None values are included as null.
        """
        result = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "raw_row" and not value:
                result[f.name] = []
            elif f.name == "warnings" and not value:
                result[f.name] = []
            else:
                result[f.name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountingRecord:
        """Create an instance from a dictionary (inverse of to_dict)."""
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Run structural validation rules.

        Returns a list of warning / error messages (empty = valid).
        """
        errors: list[str] = []

        # --- record_id ---
        if not self.record_id:
            errors.append("record_id is required")
        elif not isinstance(self.record_id, str):
            errors.append("record_id must be a string")

        # --- source identifiers ---
        if not self.source_file:
            errors.append("source_file is required")
        if not isinstance(self.source_page, int) or self.source_page < 1:
            errors.append("source_page must be a positive integer")
        if not isinstance(self.source_table, int) or self.source_table < 0:
            errors.append("source_table must be a non-negative integer")
        if not isinstance(self.source_row, int) or self.source_row < 0:
            errors.append("source_row must be a non-negative integer")

        # --- account fields ---
        if not self.account_code and not self.account_name:
            errors.append("at least one of account_code or account_name is required")
        if self.account_code is not None and not isinstance(self.account_code, str):
            errors.append("account_code must be a string")
        if self.account_name is not None and not isinstance(self.account_name, str):
            errors.append("account_name must be a string")

        # --- monetary values ---
        for label, val in [
            ("debit", self.debit),
            ("credit", self.credit),
            ("balance_debit", self.balance_debit),
            ("balance_credit", self.balance_credit),
        ]:
            if val is not None:
                if not isinstance(val, (int, float)):
                    errors.append(f"{label} must be numeric or None")
                elif isinstance(val, float) and (val != val):  # NaN check
                    errors.append(f"{label} is NaN")

        # --- processing ---
        if not self.extractor:
            errors.append("extractor is required")
        if not isinstance(self.confidence, (int, float)):
            errors.append("confidence must be numeric")
        elif not (0.0 <= self.confidence <= 1.0):
            errors.append("confidence must be between 0.0 and 1.0")

        # --- raw_row ---
        if not isinstance(self.raw_row, list):
            errors.append("raw_row must be a list")

        # --- warnings ---
        if not isinstance(self.warnings, list):
            errors.append("warnings must be a list")

        return errors

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def generate_id(self) -> str:
        """Generate a unique record_id based on content."""
        raw = f"{self.source_file}|{self.source_page}|{self.source_table}|{self.source_row}|{self.account_code}|{datetime.utcnow().isoformat()}"
        self.record_id = uuid.uuid5(uuid.NAMESPACE_DNS, raw).hex
        return self.record_id

    def add_warning(self, message: str) -> None:
        """Append a non-blocking warning."""
        self.warnings.append(message)

    def is_empty(self) -> bool:
        """True if no meaningful data was extracted."""
        return (
            not self.account_code
            and not self.account_name
            and self.debit is None
            and self.credit is None
            and self.balance_debit is None
            and self.balance_credit is None
        )
