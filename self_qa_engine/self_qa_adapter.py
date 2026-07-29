from __future__ import annotations

from datetime import datetime, timezone

from document_context import DocumentContext

from .quality_gate import QualityGateEvaluator
from .risk_calculator import RiskCalculator
from .confidence_engine import ConfidenceEngine
from .issue_analyzer import IssueAnalyzer
from .approval_engine import ApprovalEngine
from .recommendation_engine import RecommendationEngine
from .models import QAResult


class SelfQAAdapter:
    """Adapter de Self QA Engine para Pipeline V2.

    Recibe un DocumentContext, ejecuta todos los módulos de Self QA y
    almacena el QAResult en ctx.self_qa.
    """

    def __init__(
        self,
        gate_thresholds: dict[str, float] | None = None,
        risk_weights: dict[str, float] | None = None,
        confidence_weights: dict[str, float] | None = None,
        approval_thresholds: dict[str, float] | None = None,
    ):
        self._gate_evaluator = QualityGateEvaluator(thresholds=gate_thresholds)
        self._risk_calculator = RiskCalculator(weights=risk_weights)
        self._confidence_engine = ConfidenceEngine(weights=confidence_weights)
        self._issue_analyzer = IssueAnalyzer()
        self._approval_engine = ApprovalEngine(thresholds=approval_thresholds)
        self._recommendation_engine = RecommendationEngine()

    def run(self, ctx: DocumentContext) -> DocumentContext:
        coverage_data = ctx.get_custom("coverage", {}) or {}
        if isinstance(coverage_data, dict):
            pass
        else:
            coverage_data = {}

        decision_stats = ctx.get_custom("decision_stats", {}) or {}
        decisions = ctx.get_custom("decisions", []) or []

        coverage_issues = coverage_data.get("issues", []) if coverage_data else []

        gates = self._gate_evaluator.evaluate(
            coverage_data=coverage_data,
            decision_stats=decision_stats,
            validation_data=ctx.validation,
            structure_data=ctx.structure,
            parser_data=ctx.parser,
            knowledge_data=ctx.knowledge,
            predictions=ctx.prediction,
        )

        risk = self._risk_calculator.compute(
            coverage_data=coverage_data,
            validation_data=ctx.validation,
            parser_data=ctx.parser,
            structure_data=ctx.structure,
            decision_stats=decision_stats,
        )

        confidence = self._confidence_engine.compute(
            coverage_data=coverage_data,
            decision_stats=decision_stats,
            validation_data=ctx.validation,
            parser_data=ctx.parser,
            knowledge_data=ctx.knowledge,
            structure_data=ctx.structure,
            predictions=ctx.prediction,
        )

        issues = self._issue_analyzer.consolidate(
            coverage_issues=coverage_issues,
            validation_data=ctx.validation,
            decision_stats=decision_stats,
            parser_data=ctx.parser,
            knowledge_data=ctx.knowledge,
            decisions=decisions,
        )

        approval_state, reason = self._approval_engine.decide(
            coverage_data=coverage_data,
            gates=gates,
            issues=issues,
            risk=risk,
            confidence=confidence,
            structure_data=ctx.structure,
            parser_data=ctx.parser,
            validation_data=ctx.validation,
        )

        recommendations = self._recommendation_engine.generate(
            approval_state=approval_state,
            risk=risk,
            issues=issues,
            confidence=confidence,
            coverage_data=coverage_data,
            structure_data=ctx.structure,
        )

        result = QAResult(
            approval_state=approval_state,
            confidence=confidence,
            risk=risk,
            gates=gates,
            issues=issues,
            recommendations=recommendations,
            decision_reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        ctx.set_custom("self_qa", result.to_dict())
        ctx.set_custom("self_qa_state", result.approval_state.value)
        ctx.set_custom("self_qa_confidence", result.confidence.overall)
        ctx.set_custom("self_qa_risk", result.risk.total_risk)
        ctx.set_custom("self_qa_risk_level", result.risk.level.value)
        ctx.set_custom("self_qa_gates", [g.to_dict() for g in result.gates])
        ctx.set_custom("self_qa_issues", [i.to_dict() for i in result.issues])
        ctx.set_custom("self_qa_reason", result.decision_reason)

        return ctx
