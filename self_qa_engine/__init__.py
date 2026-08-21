"""Self QA Engine (SQA).

Último motor lógico del sistema. Decide automáticamente si un documento
puede continuar, debe revisarse, debe enviarse a aprendizaje o debe rechazarse.

Toda decisión se basa EXCLUSIVAMENTE en la evidencia generada por los módulos
existentes. NO utiliza IA. NO modifica resultados.
"""

from .models import (
    RiskLevel, ApprovalState, QualityGate, QAIssue, QARisk,
    QAConfidence, QARecommendation, QAResult, QASummary,
    DEFAULT_GATE_THRESHOLDS, DEFAULT_CONFIDENCE_WEIGHTS, DEFAULT_RISK_WEIGHTS,
    risk_level_from_score, risk_score_from_coverage,
)
from .quality_gate import QualityGateEvaluator
from .risk_calculator import RiskCalculator
from .issue_analyzer import IssueAnalyzer
from .approval_engine import ApprovalEngine
from .recommendation_engine import RecommendationEngine
from .confidence_engine import ConfidenceEngine
from .statistics import QAStatisticsCollector
from .report_generator import QaReportGenerator
from .self_qa_adapter import SelfQAAdapter

__all__ = [
    "RiskLevel", "ApprovalState", "QualityGate", "QAIssue", "QARisk",
    "QAConfidence", "QARecommendation", "QAResult", "QASummary",
    "DEFAULT_GATE_THRESHOLDS", "DEFAULT_CONFIDENCE_WEIGHTS", "DEFAULT_RISK_WEIGHTS",
    "risk_level_from_score", "risk_score_from_coverage",
    "QualityGateEvaluator", "RiskCalculator", "IssueAnalyzer",
    "ApprovalEngine", "RecommendationEngine", "ConfidenceEngine",
    "QAStatisticsCollector", "QaReportGenerator", "SelfQAAdapter",
]
