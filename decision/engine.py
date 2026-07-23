from __future__ import annotations

from decision.models import DecisionEvidence, DecisionResult


class DecisionEngine:
    """Resuelve conflictos entre SemanticMatcher y RegexFallback.

    Reglas (evaluadas en orden):
      1. SM y Regex coinciden → aceptar, VERY_HIGH
      2. SM score > 0.95 y Regex distinto → aceptar SM
      3. Regex exacta y SM < 0.70 → aceptar Regex
      4. AccountTypeFilter invalida → descartar (aplica externamente)
      5. Ninguna regla aplica → review_required=True
    """

    def __init__(self) -> None:
        pass

    def decide(
        self,
        *,
        sm_code: str | None,
        sm_score: float | None,
        sm_tier: int | None,
        sm_confidence: str | None,
        regex_code: str | None,
        regex_method: str | None,
        dict_code: str | None = None,
        dict_method: str | None = None,
        account_type: str | None = None,
        account_code: str | None = None,
    ) -> DecisionResult:
        evidence: list[DecisionEvidence] = []

        # --- Ambos métodos tienen resultado ---
        if sm_code and regex_code:
            return self._resolve_conflict(
                sm_code, sm_score, sm_tier, sm_confidence,
                regex_code, regex_method,
                evidence,
            )

        # --- Solo SM ---
        if sm_code and not regex_code:
            evidence.append(DecisionEvidence(
                rule="rule_sm_only",
                details=f"SemanticMatcher asigna {sm_code} (score={sm_score}, tier={sm_tier})",
                score_sm=sm_score,
                tier_sm=sm_tier,
                confidence_sm=sm_confidence,
            ))
            return DecisionResult(
                codigo_final=sm_code,
                decision_source="SM_ONLY",
                confidence=self._confidence_label(sm_score, sm_tier),
                evidence=evidence,
                review_required=False,
                reason=f"Aceptado por SM: {sm_code} (score={sm_score})",
            )

        # --- Solo Regex ---
        if regex_code and not sm_code:
            evidence.append(DecisionEvidence(
                rule="rule_regex_only",
                details=f"RegexFallback asigna {regex_code} (method={regex_method})",
            ))
            return DecisionResult(
                codigo_final=regex_code,
                decision_source="REGEX_ONLY",
                confidence="MEDIUM",
                evidence=evidence,
                review_required=False,
                reason=f"Aceptado por Regex: {regex_code} (method={regex_method})",
            )

        # --- Ninguno clasifica ---
        evidence.append(DecisionEvidence(
            rule="rule_both_unknown",
            details="Ningún método clasifica la cuenta",
        ))
        return DecisionResult(
            codigo_final=None,
            decision_source="BOTH_UNKNOWN",
            confidence="UNKNOWN",
            evidence=evidence,
            review_required=True,
            reason="Ambos métodos no clasifican",
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_conflict(
        self,
        sm_code: str,
        sm_score: float | None,
        sm_tier: int | None,
        sm_confidence: str | None,
        regex_code: str,
        regex_method: str | None,
        evidence: list[DecisionEvidence],
    ) -> DecisionResult:
        effective_score = sm_score if sm_score is not None else 0.0

        # Rule 1: coincidencia
        if sm_code == regex_code:
            evidence.append(DecisionEvidence(
                rule="rule_1_sm_regex_agree",
                details=f"Ambos asignan {sm_code}",
                score_sm=effective_score,
                tier_sm=sm_tier,
                confidence_sm=sm_confidence,
            ))
            return DecisionResult(
                codigo_final=sm_code,
                decision_source="SM_AND_REGEX_AGREE",
                confidence="VERY_HIGH",
                evidence=evidence,
                review_required=False,
                reason=f"SM y Regex coinciden en {sm_code}",
            )

        # Rule 2: SM con alta confianza
        if effective_score > 0.95:
            evidence.append(DecisionEvidence(
                rule="rule_2_sm_high_confidence",
                details=f"SM score {effective_score:.4f} > 0.95 asigna {sm_code}, Regex da {regex_code}",
                score_sm=effective_score,
                tier_sm=sm_tier,
                confidence_sm=sm_confidence,
            ))
            return DecisionResult(
                codigo_final=sm_code,
                decision_source="SM_HIGH_CONFIDENCE",
                confidence="VERY_HIGH",
                evidence=evidence,
                review_required=False,
                reason=f"SM score {effective_score:.4f} > 0.95 → {sm_code} (descarta Regex {regex_code})",
            )

        # Rule 3: Regex exacta y SM bajo
        is_exact = regex_method and "exact" in regex_method.lower()
        if is_exact and effective_score < 0.70:
            evidence.append(DecisionEvidence(
                rule="rule_3_regex_exact",
                details=f"Regex {regex_method} (exacta) asigna {regex_code}, SM score {effective_score:.4f} < 0.70",
                score_sm=effective_score,
                tier_sm=sm_tier,
                confidence_sm=sm_confidence,
            ))
            return DecisionResult(
                codigo_final=regex_code,
                decision_source="REGEX_EXACT",
                confidence="HIGH",
                evidence=evidence,
                review_required=False,
                reason=f"Regex exacta ({regex_method}) → {regex_code} (SM score {effective_score:.4f} < 0.70)",
            )

        # Rule 5: conflicto no resuelto
        evidence.append(DecisionEvidence(
            rule="rule_5_conflict_unresolved",
            details=f"SM={sm_code}(score={effective_score:.4f}, tier={sm_tier}) vs Regex={regex_code}({regex_method})",
            score_sm=effective_score,
            tier_sm=sm_tier,
            confidence_sm=sm_confidence,
        ))
        return DecisionResult(
            codigo_final=None,
            decision_source="CONFLICT_UNRESOLVED",
            confidence="LOW",
            evidence=evidence,
            review_required=True,
            reason=f"Conflicto no resuelto: SM={sm_code}({effective_score:.4f}) vs Regex={regex_code}",
        )

    @staticmethod
    def _confidence_label(score: float | None, tier: int | None) -> str:
        if score is None:
            return "UNKNOWN"
        if score >= 0.95:
            return "VERY_HIGH"
        if score >= 0.80:
            return "HIGH"
        if score >= 0.70:
            return "MEDIUM"
        return "LOW"
