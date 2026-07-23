from __future__ import annotations

from confidence.confidence_result import ConfidenceResult, EvidenceItem


REVIEW_THRESHOLD_OPTIONAL = 0.85
REVIEW_THRESHOLD_MANDATORY = 0.95


class ConfidenceEngine:
    def evaluate(
        self,
        standard_code: str | None,
        method: str,
        base_confidence: float,
        learning_hits: int = 0,
        has_special_rule: bool = False,
        conflicts: int = 0,
    ) -> ConfidenceResult:
        evidence: list[EvidenceItem] = []
        final_confidence = base_confidence
        final_method = method

        # Learning hit override
        if learning_hits > 0:
            evidence.append(EvidenceItem(
                source="learning_engine",
                detail=f"Gold Standard match found ({learning_hits} hit(s))",
                confidence=base_confidence,
            ))

        # Method-based evidence
        method_evidence = {
            "learning_exact": ("learning_engine", "Exact match contra Gold Standard", 0.98),
            "learning_fuzzy": ("learning_engine", "Fuzzy match contra Gold Standard", base_confidence),
            "code": ("code_classifier", "Clasificación por código de cuenta", base_confidence),
            "dictionary_exact": ("dictionary", "Coincidencia exacta en diccionario", 0.98),
            "dictionary_fuzzy": ("dictionary", "Coincidencia fuzzy en diccionario", base_confidence),
            "unclassified": ("fallback", "Sin clasificación disponible", 0.0),
            "movement_only": ("filter", "Cuenta sin saldo tributario", 0.0),
        }

        method_key = method.split("+")[0]
        if method_key in method_evidence:
            src, detail, conf = method_evidence[method_key]
            if not learning_hits:
                evidence.append(EvidenceItem(source=src, detail=detail, confidence=conf))

        # Special rules adjustment
        if has_special_rule:
            evidence.append(EvidenceItem(
                source="special_rule",
                detail="Regla especial aplicada (D1-D5)",
                confidence=final_confidence,
            ))

        # Conflict penalty
        if conflicts > 0:
            final_confidence = round(final_confidence * 0.85, 4)
            evidence.append(EvidenceItem(
                source="conflict",
                detail=f"Cuenta con {conflicts} código(s) conflictivo(s) en Gold Standard",
                confidence=final_confidence,
            ))

        # Review determination
        if final_confidence >= REVIEW_THRESHOLD_MANDATORY:
            review_required = False
        elif final_confidence >= REVIEW_THRESHOLD_OPTIONAL:
            review_required = False
        else:
            review_required = True

        if method_key == "movement_only":
            review_required = True

        return ConfidenceResult(
            standard_code=standard_code,
            confidence=final_confidence,
            review_required=review_required,
            method=final_method,
            evidence=evidence,
            learning_hits=learning_hits,
            conflicts=conflicts,
        )

    def merge(
        self, classification: dict, learning_hits: int = 0, has_special_rule: bool = False, conflicts: int = 0
    ) -> ConfidenceResult:
        return self.evaluate(
            standard_code=classification.get("standard_code"),
            method=classification.get("method", ""),
            base_confidence=classification.get("confidence", 0.0),
            learning_hits=learning_hits,
            has_special_rule=has_special_rule,
            conflicts=conflicts,
        )
