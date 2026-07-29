from __future__ import annotations

from .models import (
    DocumentType, Family, ParserName,
    ConfidencePrediction,
)


class ConfidencePredictor:

    TEMPLATE_BOOST = {
        "BALANCE_ESTANDAR": 0.15,
        "EEFF_AUDITADOS": 0.20,
        "TRIBUTARIO": 0.10,
        "CPT_TASACION": 0.25,
        "CLASIFICADO": 0.10,
        "BALANCE_SIMPLE": 0.05,
    }

    DOCUMENT_TYPE_BOOST = {
        DocumentType.BALANCE_TRIBUTARIO: 0.10,
        DocumentType.BALANCE_GENERAL: 0.10,
        DocumentType.ESTADO_RESULTADOS: 0.08,
        DocumentType.ESTADO_PATRIMONIO: 0.05,
        DocumentType.ESTADO_FLUJO: 0.05,
    }

    def predict(
        self,
        document_type: DocumentType | None = None,
        family: Family | None = None,
        template_id: str = "",
        ocr_probability: float = 0.0,
        parser_name: str = "",
        kb_coverage_pct: float = 0.0,
        estimated_accounts: int = 0,
        estimated_sections: int = 0,
        has_signature: bool = False,
    ) -> ConfidencePrediction:
        base_score = 0.50

        known_template_boost = self._template_boost(family)
        base_score += known_template_boost

        known_family_boost = self._family_boost(family)
        base_score += known_family_boost

        doc_boost = self._document_type_boost(document_type)
        base_score += doc_boost

        ocr_penalty = self._ocr_penalty(ocr_probability)
        base_score -= ocr_penalty

        unknown_accounts_penalty = self._unknown_penalty(kb_coverage_pct)
        base_score -= unknown_accounts_penalty

        validation_boost = self._validation_boost(estimated_sections)
        base_score += validation_boost

        if has_signature:
            base_score += 0.05

        global_score = max(0.05, min(1.0, base_score))

        signals = []
        if known_template_boost > 0:
            signals.append(f"template_boost:+{known_template_boost:.2f}")
        if known_family_boost > 0:
            signals.append(f"family_boost:+{known_family_boost:.2f}")
        if ocr_penalty > 0:
            signals.append(f"ocr_penalty:-{ocr_penalty:.2f}")
        if unknown_accounts_penalty > 0:
            signals.append(f"unknown_penalty:-{unknown_accounts_penalty:.2f}")
        if validation_boost > 0:
            signals.append(f"validation_boost:+{validation_boost:.2f}")
        if doc_boost > 0:
            signals.append(f"doc_boost:+{doc_boost:.2f}")
        signals.append(f"base={0.50:.2f}")

        return ConfidencePrediction(
            global_score=round(global_score, 4),
            known_template_boost=round(known_template_boost, 4),
            known_family_boost=round(known_family_boost, 4),
            ocr_penalty=round(ocr_penalty, 4),
            unknown_accounts_penalty=round(unknown_accounts_penalty, 4),
            validation_boost=round(validation_boost, 4),
            signals=signals,
        )

    def _template_boost(self, family: Family | None) -> float:
        if family is None:
            return 0.0
        return self.TEMPLATE_BOOST.get(family.value, 0.0)

    def _family_boost(self, family: Family | None) -> float:
        if family is None:
            return 0.0
        if family == Family.DESCONOCIDO:
            return -0.10
        if family in (Family.BALANCE_ESTANDAR, Family.EEFF_AUDITADOS):
            return 0.10
        return 0.05

    def _document_type_boost(self, document_type: DocumentType | None) -> float:
        if document_type is None:
            return 0.0
        return self.DOCUMENT_TYPE_BOOST.get(document_type, 0.0)

    def _ocr_penalty(self, ocr_probability: float) -> float:
        if ocr_probability > 0.9:
            return 0.30
        elif ocr_probability > 0.7:
            return 0.20
        elif ocr_probability > 0.4:
            return 0.10
        elif ocr_probability > 0.2:
            return 0.05
        return 0.0

    def _unknown_penalty(self, kb_coverage_pct: float) -> float:
        if kb_coverage_pct > 0.9:
            return 0.0
        elif kb_coverage_pct > 0.7:
            return 0.05
        elif kb_coverage_pct > 0.5:
            return 0.10
        elif kb_coverage_pct > 0.3:
            return 0.15
        else:
            return 0.25

    def _validation_boost(self, estimated_sections: int) -> float:
        if estimated_sections >= 4:
            return 0.10
        elif estimated_sections >= 2:
            return 0.05
        return 0.0
