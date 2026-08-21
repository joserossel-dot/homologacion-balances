from __future__ import annotations

from .models import (
    DocumentProfile, DocumentClassification, FamilyClassification,
    TemplatePrediction, ParserRecommendation, ValidationRecommendation,
    ConfidencePrediction, CoveragePrediction,
    ProcessingRecommendation, Recommendation, Complexity,
)


_TIME_ESTIMATES = {
    Complexity.BAJA: (1.0, 3.0),
    Complexity.MEDIA: (3.0, 10.0),
    Complexity.ALTA: (10.0, 30.0),
}


class RecommendationEngine:

    def evaluate(
        self,
        profile: DocumentProfile,
        classification: DocumentClassification,
        family: FamilyClassification,
        template: TemplatePrediction | None = None,
        parser_rec: ParserRecommendation | None = None,
        validation: ValidationRecommendation | None = None,
        confidence: ConfidencePrediction | None = None,
        coverage: CoveragePrediction | None = None,
    ) -> ProcessingRecommendation:
        signals: list[str] = []

        complexity = self._estimate_complexity(profile, template, parser_rec)

        needs_ocr = parser_rec.needs_ocr if parser_rec else False
        if needs_ocr:
            signals.append("needs_ocr")

        global_score = confidence.global_score if confidence else 0.5
        coverage_pct = coverage.global_pct if coverage else 0.5

        recommendation, severity, needs_human_review, explanation = self._decide(
            global_score=global_score,
            coverage_pct=coverage_pct,
            needs_ocr=needs_ocr,
            document_type=classification.document_type.value if classification.document_type else "",
            family_name=family.family.value if family.family else "",
            template_match=template is not None,
            parser_confidence=parser_rec.confidence if parser_rec else 0.0,
            complexity=complexity,
        )

        if template:
            signals.append(f"template:{template.template_id}")

        if family.confidence < 0.5:
            signals.append(f"low_family_confidence:{family.confidence:.2f}")

        estimated_time = self._estimate_time(complexity, needs_ocr, profile.pages)

        return ProcessingRecommendation(
            recommendation=recommendation,
            explanation=explanation,
            complexity=complexity,
            estimated_time_seconds=round(estimated_time, 1),
            needs_ocr=needs_ocr,
            needs_human_review=needs_human_review,
            severity=severity,
            signals=signals,
        )

    def _estimate_complexity(
        self,
        profile: DocumentProfile,
        template: TemplatePrediction | None,
        parser_rec: ParserRecommendation | None,
    ) -> Complexity:
        if parser_rec and parser_rec.needs_ocr:
            return Complexity.ALTA

        if profile.pages > 15:
            return Complexity.ALTA
        if profile.pages > 8:
            return Complexity.MEDIA

        if profile.estimated_complexity:
            return profile.estimated_complexity

        if profile.estimated_accounts > 80:
            return Complexity.ALTA
        if profile.estimated_accounts > 30:
            return Complexity.MEDIA

        return Complexity.BAJA

    def _decide(
        self,
        global_score: float,
        coverage_pct: float,
        needs_ocr: bool,
        document_type: str,
        family_name: str,
        template_match: bool,
        parser_confidence: float,
        complexity: Complexity,
    ) -> tuple[Recommendation, str, bool, str]:
        if global_score < 0.2 or coverage_pct < 0.2:
            return (
                Recommendation.REJECT,
                "critical",
                True,
                f"Confianza ({global_score:.0%}) o cobertura ({coverage_pct:.0%}) "
                "muy baja. Documento no procesable automáticamente.",
            )

        if global_score < 0.4 or coverage_pct < 0.4:
            return (
                Recommendation.STRESS,
                "warning",
                True,
                f"Confianza ({global_score:.0%}) o cobertura ({coverage_pct:.0%}) "
                "baja. Requiere revisión humana y verificación manual.",
            )

        if global_score < 0.7 or coverage_pct < 0.7:
            return (
                Recommendation.REVIEW,
                "info",
                True,
                f"Confianza ({global_score:.0%}) o cobertura ({coverage_pct:.0%}) "
                "moderada. Procesar con revisión humana posterior.",
            )

        if needs_ocr:
            return (
                Recommendation.REVIEW,
                "info",
                True,
                "Confianza alta pero requiere OCR. Revisar calidad del texto extraído.",
            )

        if not template_match:
            return (
                Recommendation.CONTINUE,
                "info",
                False,
                "Confianza alta. Template nuevo (se registrará automáticamente).",
            )

        return (
            Recommendation.CONTINUE,
            "info",
            False,
            "Confianza y cobertura altas. Pipeline automático sin revisión.",
        )

    def _estimate_time(
        self,
        complexity: Complexity,
        needs_ocr: bool,
        pages: int,
    ) -> float:
        lo, hi = _TIME_ESTIMATES[complexity]
        base = (lo + hi) / 2

        if needs_ocr:
            base += pages * 2.0

        if complexity == Complexity.ALTA:
            base += pages * 0.3

        return base
