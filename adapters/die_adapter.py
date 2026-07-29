from __future__ import annotations

from pathlib import Path

from document_context import DocumentContext
from document_context.models import PredictionData


class DIEAdapter:
    def __init__(self, template_repo_path: str = "structure_repository.json", kb_path: str = "knowledge_base/cmcc_knowledge.json"):
        from document_intelligence import DocumentIntelligence
        self._engine = DocumentIntelligence(
            template_repo_path=template_repo_path,
            kb_path=kb_path,
        )

    def run(self, ctx: DocumentContext) -> DocumentContext:
        path = Path(ctx.source_file)
        if not path.exists():
            ctx.set_custom("die_error", f"File not found: {path}")
            return ctx

        report = self._engine.analyze(str(path))
        ctx.set_custom("die_report", report.to_dict() if hasattr(report, "to_dict") else str(report))

        confidence_pred = getattr(report, "confidence", None)
        confidence_expected = confidence_pred.global_score if confidence_pred is not None else 0.0

        coverage_pred = getattr(report, "coverage", None)
        coverage_expected = coverage_pred.global_pct if coverage_pred is not None else 0.0

        complexity = ""
        rec = getattr(report, "recommendation", None)
        if rec is not None:
            c = getattr(rec, "complexity", None)
            if c is not None:
                complexity = c.value if hasattr(c, "value") else str(c)

        prediction = PredictionData(
            confidence_expected=confidence_expected,
            coverage_expected=coverage_expected,
            complexity=complexity,
        )
        ctx.set_prediction(prediction, module="die_adapter")

        return ctx
