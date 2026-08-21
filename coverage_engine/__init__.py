"""Coverage Engine (CE).

Mide cuánto del documento fue realmente comprendido por el sistema.
NO clasifica cuentas. NO toma decisiones. NO modifica resultados.

Produce métricas objetivas de cobertura:
- Monetary Coverage
- Structural Coverage
- Semantic Coverage
- Document Coverage
"""

from .models import (
    CoverageType, CoverageSeverity, CoverageIssue,
    MonetaryCoverage, StructuralCoverage, SemanticCoverage,
    DocumentCoverage, CoverageResult, CoverageStatistics,
    CoverageSummary, family_from_code,
    DEFAULT_COVERAGE_WEIGHTS, FAMILY_ORDER, EXPECTED_SECTIONS,
)
from .monetary_coverage import MonetaryCoverageCalculator
from .structural_coverage import StructuralCoverageCalculator
from .semantic_coverage import SemanticCoverageCalculator
from .document_coverage import DocumentCoverageCalculator
from .coverage_calculator import CoverageCalculator
from .coverage_statistics import CoverageStatisticsCollector
from .report_generator import CoverageReportGenerator
from .coverage_adapter import CoverageAdapter

__all__ = [
    "CoverageType",
    "CoverageSeverity",
    "CoverageIssue",
    "MonetaryCoverage",
    "StructuralCoverage",
    "SemanticCoverage",
    "DocumentCoverage",
    "CoverageResult",
    "CoverageStatistics",
    "CoverageSummary",
    "family_from_code",
    "DEFAULT_COVERAGE_WEIGHTS",
    "FAMILY_ORDER",
    "EXPECTED_SECTIONS",
    "MonetaryCoverageCalculator",
    "StructuralCoverageCalculator",
    "SemanticCoverageCalculator",
    "DocumentCoverageCalculator",
    "CoverageCalculator",
    "CoverageStatisticsCollector",
    "CoverageReportGenerator",
    "CoverageAdapter",
]
