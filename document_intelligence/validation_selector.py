from __future__ import annotations

from .models import DocumentType, Family, ValidationRecommendation


class ValidationSelector:

    def recommend(
        self,
        document_type: DocumentType | None = None,
        family: Family | None = None,
        estimated_accounts: int = 0,
        estimated_sections: int = 0,
    ) -> ValidationRecommendation:
        if document_type is None:
            return self._default_recommendation()

        type_lower = document_type.value.lower()

        if "balance" in type_lower:
            return self._for_balance(family, estimated_accounts, estimated_sections)
        elif "resultado" in type_lower:
            return self._for_resultados()
        elif "patrimonio" in type_lower:
            return self._for_patrimonio()
        elif "flujo" in type_lower:
            return self._for_flujo()
        else:
            return self._default_recommendation()

    def _for_balance(
        self,
        family: Family | None,
        estimated_accounts: int,
        estimated_sections: int,
    ) -> ValidationRecommendation:
        if family == Family.BALANCE_SIMPLE:
            return ValidationRecommendation(
                ejecutar_biv=True,
                ejecutar_equation=False,
                ejecutar_subtotales=True,
                ejecutar_missing_accounts=True,
                ejecutar_integrity=True,
                confidence=0.8,
                signals=["balance_simple:skip_equation"],
            )

        if estimated_accounts < 10:
            return ValidationRecommendation(
                ejecutar_biv=True,
                ejecutar_equation=True,
                ejecutar_subtotales=True,
                ejecutar_missing_accounts=True,
                ejecutar_integrity=True,
                confidence=0.9,
                signals=["balance_small:full_validation"],
            )

        if family == Family.TRIBUTARIO and estimated_sections < 3:
            return ValidationRecommendation(
                ejecutar_biv=True,
                ejecutar_equation=True,
                ejecutar_subtotales=True,
                ejecutar_missing_accounts=True,
                ejecutar_integrity=True,
                confidence=0.85,
                signals=["tributario_simple:full_validation"],
            )

        return ValidationRecommendation(
            ejecutar_biv=True,
            ejecutar_equation=True,
            ejecutar_subtotales=True,
            ejecutar_missing_accounts=True,
            ejecutar_integrity=True,
            confidence=0.95,
            signals=["balance_full:all_validations"],
        )

    def _for_resultados(self) -> ValidationRecommendation:
        return ValidationRecommendation(
            ejecutar_biv=True,
            ejecutar_equation=False,
            ejecutar_subtotales=True,
            ejecutar_missing_accounts=True,
            ejecutar_integrity=True,
            confidence=0.85,
            signals=["resultados:skip_equation"],
        )

    def _for_patrimonio(self) -> ValidationRecommendation:
        return ValidationRecommendation(
            ejecutar_biv=True,
            ejecutar_equation=False,
            ejecutar_subtotales=True,
            ejecutar_missing_accounts=False,
            ejecutar_integrity=True,
            confidence=0.8,
            signals=["patrimonio:skip_equation,skip_missing"],
        )

    def _for_flujo(self) -> ValidationRecommendation:
        return ValidationRecommendation(
            ejecutar_biv=True,
            ejecutar_equation=False,
            ejecutar_subtotales=True,
            ejecutar_missing_accounts=False,
            ejecutar_integrity=True,
            confidence=0.75,
            signals=["flujo:skip_equation,skip_missing"],
        )

    def _default_recommendation(self) -> ValidationRecommendation:
        return ValidationRecommendation(
            ejecutar_biv=True,
            ejecutar_equation=True,
            ejecutar_subtotales=True,
            ejecutar_missing_accounts=True,
            ejecutar_integrity=True,
            confidence=0.6,
            signals=["default:unknown_document"],
        )
