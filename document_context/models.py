from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


VERSION = "1.0.0"


class ProcessingState(str, Enum):
    NEW = "NEW"
    IDENTIFIED = "IDENTIFIED"
    STRUCTURED = "STRUCTURED"
    PARSED = "PARSED"
    CLASSIFIED = "CLASSIFIED"
    VALIDATED = "VALIDATED"
    REVIEWED = "REVIEWED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in (ProcessingState.COMPLETED, ProcessingState.FAILED)

    @property
    def requires_review(self) -> bool:
        return self == ProcessingState.REVIEWED

    @property
    def index(self) -> int:
        order = list(ProcessingState)
        return order.index(self) if self in order else -1


@dataclass
class DocumentIdentity:
    document_id: str = ""
    source_file: str = ""
    sha256: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_file": self.source_file,
            "sha256": self.sha256,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentIdentity:
        return cls(
            document_id=data.get("document_id", ""),
            source_file=data.get("source_file", ""),
            sha256=data.get("sha256", ""),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
            version=data.get("version", VERSION),
        )


@dataclass
class DocumentMetadata:
    company: str = ""
    rut: str = ""
    year: int = 0
    pages: int = 0
    language: str = ""
    orientation: str = ""
    layout: str = ""
    ocr_probability: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.company,
            "rut": self.rut,
            "year": self.year,
            "pages": self.pages,
            "language": self.language,
            "orientation": self.orientation,
            "layout": self.layout,
            "ocr_probability": round(self.ocr_probability, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentMetadata:
        return cls(
            company=data.get("company", ""),
            rut=data.get("rut", ""),
            year=data.get("year", 0),
            pages=data.get("pages", 0),
            language=data.get("language", ""),
            orientation=data.get("orientation", ""),
            layout=data.get("layout", ""),
            ocr_probability=float(data.get("ocr_probability", 0.0)),
        )


@dataclass
class StructureData:
    family: str = ""
    template: str = ""
    document_type: str = ""
    sections: list[dict] = field(default_factory=list)
    tree: Any = None
    column_layout: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "template": self.template,
            "document_type": self.document_type,
            "sections": self.sections,
            "tree": str(type(self.tree).__name__) if self.tree is not None else None,
            "column_layout": self.column_layout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructureData:
        return cls(
            family=data.get("family", ""),
            template=data.get("template", ""),
            document_type=data.get("document_type", ""),
            sections=data.get("sections", []),
            tree=data.get("tree"),
            column_layout=data.get("column_layout", ""),
        )


@dataclass
class ParserData:
    selected_parser: str = ""
    parser_version: str = ""
    parser_time: float = 0.0
    accounts: list[Any] = field(default_factory=list)
    raw_accounts: list[Any] = field(default_factory=list)
    ignored_accounts: list[Any] = field(default_factory=list)

    @property
    def total_accounts(self) -> int:
        return len(self.accounts)

    @property
    def total_raw(self) -> int:
        return len(self.raw_accounts)

    @property
    def total_ignored(self) -> int:
        return len(self.ignored_accounts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_parser": self.selected_parser,
            "parser_version": self.parser_version,
            "parser_time": round(self.parser_time, 4),
            "total_accounts": self.total_accounts,
            "total_raw": self.total_raw,
            "total_ignored": self.total_ignored,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParserData:
        return cls(
            selected_parser=data.get("selected_parser", ""),
            parser_version=data.get("parser_version", ""),
            parser_time=float(data.get("parser_time", 0.0)),
            accounts=data.get("accounts", []),
            raw_accounts=data.get("raw_accounts", []),
            ignored_accounts=data.get("ignored_accounts", []),
        )


@dataclass
class KnowledgeData:
    cmcc_matches: list[Any] = field(default_factory=list)
    learning_hits: list[Any] = field(default_factory=list)
    variants: list[Any] = field(default_factory=list)
    dictionary_matches: list[Any] = field(default_factory=list)

    @property
    def total_matches(self) -> int:
        return len(self.cmcc_matches) + len(self.learning_hits) + len(self.dictionary_matches)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cmcc_matches": len(self.cmcc_matches),
            "learning_hits": len(self.learning_hits),
            "variants": len(self.variants),
            "dictionary_matches": len(self.dictionary_matches),
            "total_matches": self.total_matches,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeData:
        return cls(
            cmcc_matches=data.get("cmcc_matches", []),
            learning_hits=data.get("learning_hits", []),
            variants=data.get("variants", []),
            dictionary_matches=data.get("dictionary_matches", []),
        )


@dataclass
class ValidationData:
    integrity: Any = None
    subtotal_validation: Any = None
    equation_validation: Any = None
    missing_accounts: Any = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_integrity": self.integrity is not None,
            "has_subtotal": self.subtotal_validation is not None,
            "has_equation": self.equation_validation is not None,
            "has_missing": self.missing_accounts is not None,
            "warnings": len(self.warnings),
            "errors": len(self.errors),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationData:
        return cls(
            warnings=data.get("warnings", []),
            errors=data.get("errors", []),
        )


@dataclass
class PredictionData:
    confidence_expected: float = 0.0
    coverage_expected: float = 0.0
    estimated_time: float = 0.0
    complexity: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_expected": round(self.confidence_expected, 4),
            "coverage_expected": round(self.coverage_expected, 4),
            "estimated_time": round(self.estimated_time, 2),
            "complexity": self.complexity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PredictionData:
        return cls(
            confidence_expected=float(data.get("confidence_expected", 0.0)),
            coverage_expected=float(data.get("coverage_expected", 0.0)),
            estimated_time=float(data.get("estimated_time", 0.0)),
            complexity=data.get("complexity", ""),
        )


@dataclass
class ExecutionData:
    confidence_real: float = 0.0
    coverage_real: float = 0.0
    processing_time: float = 0.0
    review_required: bool = False
    status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_real": round(self.confidence_real, 4),
            "coverage_real": round(self.coverage_real, 4),
            "processing_time": round(self.processing_time, 2),
            "review_required": self.review_required,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionData:
        return cls(
            confidence_real=float(data.get("confidence_real", 0.0)),
            coverage_real=float(data.get("coverage_real", 0.0)),
            processing_time=float(data.get("processing_time", 0.0)),
            review_required=bool(data.get("review_required", False)),
            status=data.get("status", ""),
        )


@dataclass
class ContextSnapshot:
    snapshot_id: str
    label: str
    state: ProcessingState
    timestamp: datetime
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "label": self.label,
            "state": self.state.value,
            "timestamp": self.timestamp.isoformat(),
            "data_keys": list(self.data.keys()),
        }


@dataclass
class LifecycleEvent:
    event_id: str
    timestamp: datetime
    from_state: ProcessingState | None
    to_state: ProcessingState
    module: str
    description: str
    snapshot_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "from_state": self.from_state.value if self.from_state else None,
            "to_state": self.to_state.value,
            "module": self.module,
            "description": self.description,
            "snapshot_id": self.snapshot_id,
        }


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            pass
    return datetime.now(timezone.utc)
