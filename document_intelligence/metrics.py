from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from .signature import FormatSignature

if TYPE_CHECKING:
    from .context import DocumentProcessingContext


@dataclass
class DetectionMetrics:
    total_documents: int = 0
    identified: int = 0
    unidentified: int = 0
    by_family: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    by_layout: dict[str, int] = field(default_factory=dict)
    by_code_pattern: dict[str, int] = field(default_factory=dict)
    by_extractor: dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    avg_elapsed_ms: float = 0.0
    confidence_distribution: dict[str, int] = field(default_factory=lambda: {
        "0-25%": 0, "25-50%": 0, "50-75%": 0, "75-90%": 0, "90-100%": 0,
    })
    _confidence_sum: float = field(default=0.0, repr=False)
    _elapsed_sum: float = field(default=0.0, repr=False)

    def record(
        self,
        sig: FormatSignature,
        extractor_type: Optional[str] = None,
        elapsed_ms: Optional[int] = None,
    ):
        self.total_documents += 1
        if sig.is_identified:
            self.identified += 1
        else:
            self.unidentified += 1

        family_key = sig.family.value
        self.by_family[family_key] = self.by_family.get(family_key, 0) + 1

        type_key = sig.document_type.value
        self.by_type[type_key] = self.by_type.get(type_key, 0) + 1

        layout_key = sig.layout.value
        self.by_layout[layout_key] = self.by_layout.get(layout_key, 0) + 1

        code_key = sig.code_pattern.value
        self.by_code_pattern[code_key] = self.by_code_pattern.get(code_key, 0) + 1

        if extractor_type is not None:
            self.by_extractor[extractor_type] = (
                self.by_extractor.get(extractor_type, 0) + 1
            )

        self._confidence_sum += sig.confidence
        if elapsed_ms is not None:
            self._elapsed_sum += elapsed_ms

        pct = sig.confidence * 100
        if pct < 25:
            self.confidence_distribution["0-25%"] += 1
        elif pct < 50:
            self.confidence_distribution["25-50%"] += 1
        elif pct < 75:
            self.confidence_distribution["50-75%"] += 1
        elif pct < 90:
            self.confidence_distribution["75-90%"] += 1
        else:
            self.confidence_distribution["90-100%"] += 1

    def compute(self):
        if self.total_documents > 0:
            self.avg_confidence = round(
                self._confidence_sum / self.total_documents, 4
            )
            self.avg_elapsed_ms = round(
                self._elapsed_sum / self.total_documents, 2
            )

    def to_dict(self) -> dict[str, Any]:
        if self.total_documents > 0:
            avg_confidence = round(self._confidence_sum / self.total_documents, 4)
            avg_elapsed_ms = round(self._elapsed_sum / self.total_documents, 2)
        else:
            avg_confidence = 0.0
            avg_elapsed_ms = 0.0
        return {
            "total_documents": self.total_documents,
            "identified": self.identified,
            "unidentified": self.unidentified,
            "identification_rate": round(
                self.identified / max(self.total_documents, 1), 4
            ),
            "avg_confidence": avg_confidence,
            "avg_elapsed_ms": avg_elapsed_ms,
            "by_family": dict(sorted(self.by_family.items())),
            "by_type": dict(sorted(self.by_type.items())),
            "by_layout": dict(sorted(self.by_layout.items())),
            "by_code_pattern": dict(sorted(self.by_code_pattern.items())),
            "by_extractor": dict(sorted(self.by_extractor.items())),
            "confidence_distribution": self.confidence_distribution,
        }


class MetricsCollector:
    def __init__(self):
        self.metrics = DetectionMetrics()

    def record(
        self,
        sig: FormatSignature,
        extractor_type: Optional[str] = None,
        elapsed_ms: Optional[int] = None,
    ):
        self.metrics.record(sig, extractor_type=extractor_type, elapsed_ms=elapsed_ms)

    def record_context(self, context: "DocumentProcessingContext"):
        """Registra un DocumentProcessingContext completo (Sprint 31)."""
        self.metrics.record(
            context.signature,
            extractor_type=context.extractor_type.value,
            elapsed_ms=context.elapsed_ms,
        )

    def collect(self, signatures: list[FormatSignature]) -> DetectionMetrics:
        self.metrics = DetectionMetrics()
        for sig in signatures:
            self.metrics.record(sig)
        return self.metrics

    def merge(self, other: DetectionMetrics):
        self.metrics.total_documents += other.total_documents
        self.metrics.identified += other.identified
        self.metrics.unidentified += other.unidentified

        for k, v in other.by_family.items():
            self.metrics.by_family[k] = self.metrics.by_family.get(k, 0) + v
        for k, v in other.by_type.items():
            self.metrics.by_type[k] = self.metrics.by_type.get(k, 0) + v
        for k, v in other.by_layout.items():
            self.metrics.by_layout[k] = self.metrics.by_layout.get(k, 0) + v
        for k, v in other.by_code_pattern.items():
            self.metrics.by_code_pattern[k] = self.metrics.by_code_pattern.get(k, 0) + v
        for k, v in other.by_extractor.items():
            self.metrics.by_extractor[k] = self.metrics.by_extractor.get(k, 0) + v
        for k, v in other.confidence_distribution.items():
            self.metrics.confidence_distribution[k] = (
                self.metrics.confidence_distribution.get(k, 0) + v
            )
        self.metrics._confidence_sum += other._confidence_sum
        self.metrics._elapsed_sum += other._elapsed_sum
