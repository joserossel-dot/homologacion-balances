from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FinancialAccount:
    account_id: str = ""
    standard_code: str = ""
    standard_name: str = ""
    class_: str = ""
    subclass: str = ""
    group: str = ""
    subgroup: str = ""
    semantic_type: str = ""
    financial_statement: str = ""
    economic_nature: str = ""
    normal_balance: str = ""
    presentation_order: int = 0
    current: bool = False
    monetary: bool = False
    taxable: bool = False
    ifrs: list[str] = field(default_factory=list)
    industry_tags: list[str] = field(default_factory=list)
    kpi_tags: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    forbidden_keywords: list[str] = field(default_factory=list)
    contra_accounts: list[str] = field(default_factory=list)
    related_accounts: list[str] = field(default_factory=list)
    validation_rules: list[str] = field(default_factory=list)
    audit_rules: list[str] = field(default_factory=list)
    learning_weight: float = 1.0
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "standard_code": self.standard_code,
            "standard_name": self.standard_name,
            "class": self.class_,
            "subclass": self.subclass,
            "group": self.group,
            "subgroup": self.subgroup,
            "semantic_type": self.semantic_type,
            "financial_statement": self.financial_statement,
            "economic_nature": self.economic_nature,
            "normal_balance": self.normal_balance,
            "presentation_order": self.presentation_order,
            "current": self.current,
            "monetary": self.monetary,
            "taxable": self.taxable,
            "ifrs": list(self.ifrs),
            "industry_tags": list(self.industry_tags),
            "kpi_tags": list(self.kpi_tags),
            "synonyms": list(self.synonyms),
            "keywords": list(self.keywords),
            "forbidden_keywords": list(self.forbidden_keywords),
            "contra_accounts": list(self.contra_accounts),
            "related_accounts": list(self.related_accounts),
            "validation_rules": list(self.validation_rules),
            "audit_rules": list(self.audit_rules),
            "learning_weight": self.learning_weight,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FinancialAccount:
        return cls(
            account_id=data.get("account_id", data.get("standard_code", "")),
            standard_code=data.get("standard_code", ""),
            standard_name=data.get("standard_name", ""),
            class_=data.get("class", ""),
            subclass=data.get("subclass", ""),
            group=data.get("group", ""),
            subgroup=data.get("subgroup", ""),
            semantic_type=data.get("semantic_type", ""),
            financial_statement=data.get("financial_statement", ""),
            economic_nature=data.get("economic_nature", ""),
            normal_balance=data.get("normal_balance", ""),
            presentation_order=data.get("presentation_order", 0),
            current=data.get("current", False),
            monetary=data.get("monetary", False),
            taxable=data.get("taxable", False),
            ifrs=data.get("ifrs", []),
            industry_tags=data.get("industry_tags", []),
            kpi_tags=data.get("kpi_tags", []),
            synonyms=data.get("synonyms", []),
            keywords=data.get("keywords", []),
            forbidden_keywords=data.get("forbidden_keywords", []),
            contra_accounts=data.get("contra_accounts", []),
            related_accounts=data.get("related_accounts", []),
            validation_rules=data.get("validation_rules", []),
            audit_rules=data.get("audit_rules", []),
            learning_weight=data.get("learning_weight", 1.0),
            status=data.get("status", "active"),
        )
