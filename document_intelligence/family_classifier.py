from __future__ import annotations

import re
from .models import Family, FamilyClassification


FAMILY_SIGNATURES: list[tuple[re.Pattern, Family, str, float]] = [
    (re.compile(r"balance\s+tributario", re.IGNORECASE), Family.TRIBUTARIO, "header:tributario", 0.9),
    (re.compile(r"balance\s+general", re.IGNORECASE), Family.BALANCE_ESTANDAR, "header:balance_general", 0.7),
    (re.compile(r"auditado", re.IGNORECASE), Family.EEFF_AUDITADOS, "keyword:auditado", 0.85),
    (re.compile(r"eeff", re.IGNORECASE), Family.EEFF_AUDITADOS, "keyword:eeff", 0.8),
    (re.compile(r"cpt[_\s]?tasacion", re.IGNORECASE), Family.CPT_TASACION, "keyword:cpt_tasacion", 0.9),
    (re.compile(r"clasificado", re.IGNORECASE), Family.CLASIFICADO, "keyword:clasificado", 0.75),
]


class FamilyClassifier:

    def classify(
        self,
        raw_lines: list[str],
        section_count: int = 0,
        subtotal_count: int = 0,
        total_lines: int = 0,
        code_format: str = "",
        template_family: str | None = None,
    ) -> FamilyClassification:
        if template_family:
            try:
                return FamilyClassification(
                    family=Family(template_family),
                    confidence=0.95,
                    signals=[f"template:family={template_family}"],
                )
            except ValueError:
                pass

        text = "\n".join(raw_lines[:30]).lower()

        for pattern, family, signal, confidence in FAMILY_SIGNATURES:
            if pattern.search(text):
                return FamilyClassification(
                    family=family,
                    confidence=confidence,
                    signals=[signal],
                )

        structural_signals: list[str] = []
        if section_count >= 4 and subtotal_count >= 10:
            family = Family.EEFF_AUDITADOS
            confidence = 0.8
            structural_signals.append(f"sections>=4,subtotals>=10")
        elif section_count >= 3 and subtotal_count >= 4:
            family = Family.BALANCE_ESTANDAR
            confidence = 0.7
            structural_signals.append(f"sections>=3,subtotals>=4")
        elif code_format in ("SIN_CODIGO", "COMPACTO"):
            family = Family.TRIBUTARIO
            confidence = 0.6
            structural_signals.append(f"code_format={code_format}")
        elif total_lines <= 20:
            family = Family.BALANCE_SIMPLE
            confidence = 0.65
            structural_signals.append(f"total_lines<={total_lines}")
        elif subtotal_count >= 5:
            family = Family.CLASIFICADO
            confidence = 0.7
            structural_signals.append(f"subtotals>={subtotal_count}")
        else:
            family = Family.DESCONOCIDO
            confidence = 0.3
            structural_signals.append("no_heuristic_match")

        return FamilyClassification(
            family=family,
            confidence=round(confidence, 4),
            signals=structural_signals,
        )
