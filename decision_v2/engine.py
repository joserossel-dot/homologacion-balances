from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from clasificador_codigo_cuenta import ClasificadorCodigo
from decision_v2.models import DecisionResultV2, Evidence
from learning.engine import LearningEngine
from semantic.matcher import SemanticMatcher

logger = logging.getLogger(__name__)

_PREFIX_TIPO: dict[str, set[str]] = {
    "ANC": {"ACTIVO"},
    "AC": {"ACTIVO"},
    "PNC": {"PASIVO"},
    "PC": {"PASIVO"},
    "PAT": {"PATRIMONIO"},
    "ER": {"PERDIDA", "GANANCIA"},
}

_EVIDENCE_WEIGHTS: dict[str, float] = {
    "code": 0.50,
    "dict_exact": 0.90,
    "dict_fuzzy": 0.60,
    "sm_tier_1": 1.00,
    "sm_tier_2": 0.95,
    "sm_tier_4": 0.60,
    "sm_tier_5": 0.50,
    "sm_tier_6": 0.40,
    "regex": 0.85,
    "gs_exact": 0.90,
    "gs_fuzzy": 0.60,
}

_PRECISION_ORDER = [
    "regex", "dict_exact", "gs_exact", "code",
    "dict_fuzzy", "gs_fuzzy", "sm_tier_4", "sm_tier_5", "sm_tier_6",
]


class DecisionEngineV2:
    def __init__(
        self,
        concept_catalog_path: str | Path = "knowledge/concept_catalog.json",
        dictionary_path: str | Path = "diccionario.json",
        gold_standard_db: str | Path = "gold_standard.db",
    ) -> None:
        self._code_classifier = ClasificadorCodigo()
        raw_dict = self._load_dictionary(dictionary_path)
        # Pre-compute normalized names for O(1) exact lookup and fast fuzzy
        self._dict_exact: dict[str, dict[str, str]] = {}
        self._dict_fuzzy_entries: list[tuple[str, str, str]] = []
        for entry in raw_dict:
            norm = self._normalize_name(entry["cuenta_original"])
            self._dict_exact[norm] = entry
            self._dict_fuzzy_entries.append((norm, entry["cuenta_original"], entry["codigo_estandar"]))

        self._learning_engine = LearningEngine(gold_standard_db)
        self._semantic_matcher: SemanticMatcher | None = None
        cc_path = Path(concept_catalog_path)
        if cc_path.exists():
            self._semantic_matcher = SemanticMatcher(str(cc_path))
        else:
            logger.warning("Concept catalog not found at %s", cc_path)

        from app_validacion import REGLAS_REGEX
        self._regex_patterns: list[tuple[re.Pattern, str, float]] = [
            (re.compile(p, re.IGNORECASE | re.UNICODE), c, f)
            for p, c, f in REGLAS_REGEX
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self,
        account_name: str,
        account_code: str | None = None,
        account_tipo: str | None = None,
        tipo: str | None = None,
    ) -> DecisionResultV2:
        effective_tipo = account_tipo or tipo
        evidence = self._collect_evidence(account_name, account_code, effective_tipo)
        evidence = self._apply_type_filter(evidence, effective_tipo)
        if not evidence:
            return DecisionResultV2(
                final_code=None,
                final_score=0.0,
                confidence_label="UNKNOWN",
                review_required=True,
                decision_source="ALL_FILTERED",
                evidence=[],
                explanation="Todas las evidencias fueron filtradas por tipo de cuenta",
            )
        return self._decide(evidence)

    def classify_from_cached(
        self,
        account_name: str,
        account_code: str,
        account_tipo: str | None = None,
    ) -> DecisionResultV2:
        return self.classify(account_name, account_code, account_tipo)

    # ------------------------------------------------------------------
    # Evidence collection
    # ------------------------------------------------------------------

    def _collect_evidence(
        self,
        account_name: str,
        account_code: str | None,
        account_tipo: str | None,
    ) -> list[Evidence]:
        evidence: list[Evidence] = []

        # 1. Gold Standard (checked first in pipeline)
        gs = self._learning_engine.best_match(account_name)
        if gs["source"] != "none":
            source_key = f"gs_{gs['source']}"
            evidence.append(Evidence(
                source=source_key,
                proposed_code=gs["code"],
                score=gs["confidence"],
                weight=self._weight(source_key),
                tier=0,
                method=gs["source"],
                explanation=f"Gold Standard ({gs['source']}): {gs['matched_name']} -> {gs['code']}",
            ))

        # 2. Code classifier
        if account_code:
            code_result = self._code_classifier.clasificar(account_code)
            if code_result is not None:
                evidence.append(Evidence(
                    source="code",
                    proposed_code=code_result.codigo_estandar,
                    score=code_result.confianza,
                    weight=self._weight("code"),
                    tier=0,
                    method=f"code_{code_result.tipo_formato}",
                    explanation=code_result.razon,
                ))

        # 3. Dictionary exact (O(1) hash lookup)
        norm = self._normalize_name(account_name)
        if norm in self._dict_exact:
            entry = self._dict_exact[norm]
            evidence.append(Evidence(
                source="dict_exact",
                proposed_code=entry["codigo_estandar"],
                score=0.98,
                weight=self._weight("dict_exact"),
                tier=0,
                method="dictionary_exact",
                explanation=f"Coincidencia exacta diccionario -> {entry['codigo_estandar']}",
            ))

        # 4. Dictionary fuzzy (first-word prefix filter for speed)
        if norm not in self._dict_exact:
            best_score = 0
            best_match = ("", "", "")
            first_word = norm.split()[0] if norm else ""
            candidates = (
                self._dict_fuzzy_entries if len(first_word) < 3
                else [e for e in self._dict_fuzzy_entries if e[0].startswith(first_word)]
            ) or self._dict_fuzzy_entries[:500]
            for dnorm, orig, code in candidates:
                score = fuzz.token_sort_ratio(norm, dnorm)
                if score > best_score:
                    best_score = score
                    best_match = (dnorm, orig, code)
            if best_score >= 90:
                score_val = best_score
                conf = min(0.80 + (score_val - 90) * 0.01, 0.97)
                evidence.append(Evidence(
                    source="dict_fuzzy",
                    proposed_code=best_match[2],
                    score=round(conf, 4),
                    weight=self._weight("dict_fuzzy"),
                    tier=0,
                    method=f"dictionary_fuzzy_{best_score}",
                    explanation=f"Fuzzy {best_score}% con '{best_match[1]}' -> {best_match[2]}",
                ))

        # 5. SemanticMatcher
        if self._semantic_matcher is not None:
            sm_result = self._semantic_matcher.match(account_name, account_tipo)
            if not sm_result.is_unknown:
                tier_key = f"sm_tier_{sm_result.match_tier}"
                evidence.append(Evidence(
                    source=tier_key,
                    proposed_code=sm_result.expected_cmcc,
                    score=sm_result.score,
                    weight=self._weight(tier_key),
                    tier=sm_result.match_tier,
                    method=f"semantic_tier_{sm_result.match_tier}",
                    explanation=(
                        f"SemanticMatcher: {sm_result.concept_name} -> {sm_result.expected_cmcc} "
                        f"(tier={sm_result.match_tier}, score={sm_result.score:.4f})"
                    ),
                ))

        # 6. Regex fallback
        if account_name:
            rnorm = self._normalize_name(account_name)
            effective_tipo_check = self._normalize_tipo(account_tipo)
            for pat, cod, conf in self._regex_patterns:
                if pat.search(rnorm):
                    if effective_tipo_check and effective_tipo_check not in ("DESCONOCIDO",) and not self._code_allowed_for_tipo(cod, effective_tipo_check):
                        continue
                    evidence.append(Evidence(
                        source="regex",
                        proposed_code=cod,
                        score=conf,
                        weight=self._weight("regex"),
                        tier=0,
                        method=f"regex_pattern",
                        explanation=f"Regex audited -> {cod}",
                    ))
                    break

        return evidence

    # ------------------------------------------------------------------
    # Type filter
    # ------------------------------------------------------------------

    def _apply_type_filter(
        self, evidence: list[Evidence], account_tipo: str | None,
    ) -> list[Evidence]:
        effective = self._normalize_tipo(account_tipo)
        if not effective or effective == "DESCONOCIDO":
            return evidence
        filtered: list[Evidence] = []
        for ev in evidence:
            if ev.proposed_code and self._code_allowed_for_tipo(ev.proposed_code, effective):
                filtered.append(ev)
        return filtered

    @staticmethod
    def _normalize_tipo(tipo: str | None) -> str | None:
        if not tipo:
            return None
        t = tipo.strip().upper()
        if t in ("ACTIVO", "PASIVO", "PATRIMONIO", "PERDIDA", "GANANCIA", "DESCONOCIDO"):
            return t
        # Descriptive strings like "Sin coincidencia en código ni diccionario"
        return "DESCONOCIDO"

    @staticmethod
    def _code_allowed_for_tipo(code: str, tipo: str) -> bool:
        for prefix, allowed in _PREFIX_TIPO.items():
            if code.startswith(prefix):
                return tipo in allowed
        return True

    # ------------------------------------------------------------------
    # Decision logic
    # ------------------------------------------------------------------

    def _decide(self, evidence: list[Evidence]) -> DecisionResultV2:
        # R1: SM T1-T2 always wins
        for ev in evidence:
            if ev.source in ("sm_tier_1", "sm_tier_2") and ev.proposed_code:
                return self._build_result(
                    final_code=ev.proposed_code,
                    score=ev.score,
                    label="VERY_HIGH",
                    review=False,
                    source=f"SM_TIER_{ev.tier}_WINS",
                    evidence=evidence,
                    consensus_count=1,
                    conflict_count=0,
                    explanation=f"SM Tier {ev.tier} siempre gana: {ev.proposed_code}",
                )

        # Group evidence by proposed code
        groups: dict[str, list[Evidence]] = {}
        for ev in evidence:
            if ev.proposed_code:
                groups.setdefault(ev.proposed_code, []).append(ev)

        if not groups:
            return self._build_result(
                final_code=None, score=0.0, label="UNKNOWN",
                review=True, source="ALL_UNKNOWN",
                evidence=evidence,
                explanation="Ningun clasificador propone un codigo",
            )

        # Find consensus groups (size >= 2)
        consensus = {code: g for code, g in groups.items() if len(g) >= 2}

        if consensus:
            # Pick the best consensus group by total weighted score
            best_code = max(
                consensus,
                key=lambda c: sum(e.score * e.weight for e in consensus[c]),
            )
            best_group = consensus[best_code]
            total_score = sum(e.score * e.weight for e in best_group)
            total_weight = sum(e.weight for e in best_group)
            final_score = total_score / total_weight if total_weight > 0 else 0.0

            # Consensus bonus
            n_consensus = len(best_group)
            if n_consensus >= 3:
                final_score = min(final_score * 1.25, 1.0)
            elif n_consensus >= 2:
                final_score = min(final_score * 1.15, 1.0)

            label, review = self._score_to_confidence(final_score)
            total_conflicts = sum(len(g) for c, g in groups.items() if c != best_code)

            return self._build_result(
                final_code=best_code,
                score=final_score,
                label=label,
                review=review,
                source=f"CONSENSUS_{n_consensus}",
                evidence=evidence,
                consensus_count=n_consensus,
                conflict_count=total_conflicts,
                explanation=f"Consenso {best_code} ({n_consensus} clasificadores, score={final_score:.4f})",
            )

        # No consensus: priority matrix resolution (R3-R8)
        resolved = self._resolve_by_priority(evidence, groups)
        if resolved is not None:
            final_code, final_score, source = resolved
            label, review = self._score_to_confidence(final_score)
            return self._build_result(
                final_code=final_code,
                score=final_score,
                label=label,
                review=review,
                source=source,
                evidence=evidence,
                consensus_count=1,
                conflict_count=len(evidence) - 1,
                explanation=f"Prioridad resuelta: {final_code} via {source}",
            )

        # Solo classifier (R9)
        if len(groups) == 1:
            code = next(iter(groups))
            ev = groups[code][0]
            score = ev.score * ev.weight * 0.90
            if ev.source == "sm_tier_6":
                score = min(score, 0.50)
            label, review = self._score_to_confidence(score)
            return self._build_result(
                final_code=code,
                score=score,
                label=label,
                review=review,
                source=f"SOLO_{ev.source.upper()}",
                evidence=evidence,
                consensus_count=1,
                conflict_count=0,
                explanation=f"Unico clasificador: {code} via {ev.source} (score={score:.4f})",
            )

        # Multiple classifiers, all disagree, no priority winner -> tie-breaking (R10)
        return self._resolve_tie_break(evidence, groups)

    def _resolve_by_priority(
        self,
        evidence: list[Evidence],
        groups: dict[str, list[Evidence]],
    ) -> tuple[str, float, str] | None:
        codes = list(groups.keys())
        if len(codes) < 2:
            return None

        for i, code_a in enumerate(codes):
            for code_b in codes[i + 1:]:
                ev_a = groups[code_a][0]
                ev_b = groups[code_b][0]
                winner = self._priority_winner(ev_a, ev_b)
                if winner == "tie":
                    continue
                loser_code = code_b if winner == code_a else code_a
                loser_count = sum(1 for c, g in groups.items() if c == loser_code)
                if loser_count > 0:
                    groups.pop(loser_code, None)
                    if len(groups) == 1:
                        final = next(iter(groups))
                        ev_all = groups[final]
                        total_score = sum(e.score * e.weight for e in ev_all)
                        total_weight = sum(e.weight for e in ev_all)
                        fs = total_score / total_weight if total_weight > 0 else 0.0
                        return final, fs, f"PRIORITY_{ev_all[0].source.upper()}"
                    codes = list(groups.keys())

        return None

    def _priority_winner(self, a: Evidence, b: Evidence) -> str:
        a_rank = self._source_rank(a.source)
        b_rank = self._source_rank(b.source)
        if a_rank < b_rank:
            return a.proposed_code or "tie"
        if b_rank < a_rank:
            return b.proposed_code or "tie"
        if a.score > b.score:
            return a.proposed_code or "tie"
        if b.score > a.score:
            return b.proposed_code or "tie"
        return "tie"

    def _source_rank(self, source: str) -> int:
        TIER_MAP: dict[str, int] = {
            "sm_tier_1": 1,
            "sm_tier_2": 1,
            "regex": 2,
            "dict_exact": 2,
            "gs_exact": 2,
            "code": 3,
            "dict_fuzzy": 3,
            "sm_tier_4": 3,
            "gs_fuzzy": 4,
            "sm_tier_5": 4,
            "sm_tier_6": 5,
        }
        return TIER_MAP.get(source, 9)

    def _resolve_tie_break(
        self, evidence: list[Evidence], groups: dict[str, list[Evidence]],
    ) -> DecisionResultV2:
        # TB-1: highest score wins
        best_code = max(
            groups,
            key=lambda c: max(e.score for e in groups[c]),
        )
        best_score = max(e.score for e in groups[best_code])
        second_score = sorted(
            [max(e.score for e in g) for c, g in groups.items() if c != best_code],
            reverse=True,
        )
        if second_score and abs(best_score - second_score[0]) > 0.05:
            ev = groups[best_code][0]
            fs = sum(e.score * e.weight for e in groups[best_code])
            fw = sum(e.weight for e in groups[best_code])
            final_score = (fs / fw) if fw > 0 else 0.0
            label, review = self._score_to_confidence(final_score)
            return self._build_result(
                final_code=best_code,
                score=final_score,
                label=label,
                review=review,
                source=f"TB1_SCORE_{ev.source.upper()}",
                evidence=evidence,
                consensus_count=1,
                conflict_count=len(groups) - 1,
                explanation=f"TB-1 (score): {best_code} gana con score={best_score:.4f}",
            )

        # TB-2: historical precision
        sorted_sources = {
            src for ev in evidence for src in [ev.source]
        }
        best_precision = None
        for prec_src in _PRECISION_ORDER:
            if prec_src in sorted_sources:
                best_precision = prec_src
                break
        if best_precision:
            for code, group in groups.items():
                if any(e.source == best_precision for e in group):
                    ev = group[0]
                    fs = sum(e.score * e.weight for e in group)
                    fw = sum(e.weight for e in group)
                    final_score = (fs / fw) if fw > 0 else 0.0
                    label, review = self._score_to_confidence(final_score)
                    return self._build_result(
                        final_code=code,
                        score=final_score,
                        label=label,
                        review=review,
                        source=f"TB2_PRECISION_{best_precision.upper()}",
                        evidence=evidence,
                        consensus_count=1,
                        conflict_count=len(groups) - 1,
                        explanation=f"TB-2 (precision): {best_precision} gana",
                    )

        # TB-3: account type match
        for code, group in groups.items():
            for ev in group:
                if ev.proposed_code and self._code_allowed_for_tipo(
                    ev.proposed_code, ev.source,
                ):
                    # Check if others don't match type
                    others_dont_match = True
                    for c2, g2 in groups.items():
                        if c2 == code:
                            continue
                        if any(
                            e2.proposed_code
                            and self._code_allowed_for_tipo(e2.proposed_code, ev.source)
                            for e2 in g2
                        ):
                            others_dont_match = False
                            break
                    if others_dont_match:
                        fs = sum(e.score * e.weight for e in group)
                        fw = sum(e.weight for e in group)
                        final_score = (fs / fw) if fw > 0 else 0.0
                        label, review = self._score_to_confidence(final_score)
                        return self._build_result(
                            final_code=code,
                            score=final_score,
                            label=label,
                            review=review,
                            source="TB3_TYPE_MATCH",
                            evidence=evidence,
                            consensus_count=1,
                            conflict_count=len(groups) - 1,
                            explanation=f"TB-3 (tipo): {code} coincide con tipo de cuenta",
                        )

        # TB-5: human review escalation
        return self._build_result(
            final_code=None,
            score=0.0,
            label="UNKNOWN",
            review=True,
            source="TB5_HUMAN_REVIEW",
            evidence=evidence,
            consensus_count=0,
            conflict_count=len(groups),
            explanation="TB-5: Sin resolucion por score/precision/tipo -> revision humana",
        )

    @staticmethod
    def _score_to_confidence(score: float) -> tuple[str, bool]:
        if score >= 0.95:
            return "VERY_HIGH", False
        if score >= 0.85:
            return "HIGH", False
        if score >= 0.70:
            return "MEDIUM", False
        if score >= 0.50:
            return "LOW", True
        return "UNKNOWN", True

    def _build_result(
        self,
        final_code: str | None,
        score: float,
        label: str,
        review: bool,
        source: str,
        evidence: list[Evidence],
        consensus_count: int,
        conflict_count: int,
        explanation: str,
    ) -> DecisionResultV2:
        return DecisionResultV2(
            final_code=final_code,
            final_score=score,
            confidence_label=label,
            review_required=review,
            decision_source=source,
            evidence=evidence,
            consensus_count=consensus_count,
            conflict_count=conflict_count,
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_name(name: str) -> str:
        name = name.lower().strip()
        name = re.sub(r"[^a-z0-9áéíóúñü ]+", " ", name)
        return re.sub(r"\s+", " ", name).strip()

    @staticmethod
    def _load_dictionary(path: str | Path) -> list[dict[str, str]]:
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [e for e in data if e.get("codigo_estandar") != "__EXCLUIR__"]

    @staticmethod
    def _weight(source: str) -> float:
        return _EVIDENCE_WEIGHTS.get(source, 0.50)
