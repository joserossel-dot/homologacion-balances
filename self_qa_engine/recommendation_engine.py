from __future__ import annotations

from typing import Any

from .models import ApprovalState, QARisk, QARecommendation


class RecommendationEngine:
    """Genera recomendaciones entendibles para el usuario.

    Basadas en el estado de aprobación, riesgo, issues y confianza.
    """

    def generate(
        self,
        approval_state: ApprovalState,
        risk: QARisk | None = None,
        issues: list[Any] | None = None,
        confidence: Any | None = None,
        coverage_data: dict[str, Any] | None = None,
        structure_data: Any = None,
    ) -> list[QARecommendation]:
        recommendations: list[QARecommendation] = []

        state_rec = self._state_recommendation(approval_state, coverage_data)
        if state_rec:
            recommendations.append(state_rec)

        risk_recs = self._risk_recommendations(risk)
        recommendations.extend(risk_recs)

        issue_recs = self._issue_recommendations(issues)
        recommendations.extend(issue_recs)

        coverage_recs = self._coverage_recommendations(coverage_data)
        recommendations.extend(coverage_recs)

        return recommendations

    def _state_recommendation(
        self,
        state: ApprovalState,
        coverage_data: dict[str, Any] | None = None,
    ) -> QARecommendation | None:
        if state == ApprovalState.APPROVED:
            return QARecommendation(
                message="Documento aprobado para exportación automática.",
                actions=["Exportar documento", "Archivar en sistema"],
            )
        if state == ApprovalState.APPROVED_WITH_WARNINGS:
            return QARecommendation(
                message="Documento aprobado con advertencias. Revisar antes de exportar.",
                actions=["Revisar advertencias", "Exportar con supervisión"],
            )
        if state == ApprovalState.MANUAL_REVIEW:
            return QARecommendation(
                message="Documento requiere revisión manual por personal calificado.",
                actions=["Asignar revisor", "Revisar cuentas no clasificadas",
                         "Verificar subtotales"],
            )
        if state == ApprovalState.LEARNING:
            return QARecommendation(
                message="Documento enviado al Gold Standard para aprendizaje.",
                actions=["Agregar al Gold Standard", "Actualizar Knowledge Base"],
            )
        if state == ApprovalState.STRESS:
            return QARecommendation(
                message="Documento en STRESS. Formato no estándar. Requiere análisis profundo.",
                actions=["Análisis estructural detallado",
                         "Verificar integridad del PDF",
                         "Considerar OCR alternativo"],
            )
        if state == ApprovalState.REJECTED:
            return QARecommendation(
                message="Documento rechazado. No cumple criterios mínimos de calidad.",
                actions=["Verificar si corresponde a un balance",
                         "Revisar formato y legibilidad",
                         "Contactar al proveedor del documento"],
            )
        if state == ApprovalState.FAILED:
            return QARecommendation(
                message="Documento falló en el procesamiento. Error grave detectado.",
                actions=["Verificar archivo de origen",
                         "Reintentar con otro parser",
                         "Contactar soporte técnico"],
            )
        return None

    def _risk_recommendations(
        self, risk: QARisk | None,
    ) -> list[QARecommendation]:
        result: list[QARecommendation] = []
        if risk is None:
            return result
        if risk.monetary_risk >= 50:
            result.append(QARecommendation(
                message=(
                    f"Riesgo monetario alto ({risk.monetary_risk:.0f}/100). "
                    "Revisar montos no explicados."
                ),
                actions=["Verificar cuentas con montos faltantes",
                         "Revisar totales por familia"],
            ))
        if risk.structural_risk >= 50:
            result.append(QARecommendation(
                message=(
                    f"Riesgo estructural alto ({risk.structural_risk:.0f}/100). "
                    "Verificar jerarquía de cuentas."
                ),
                actions=["Revisar subtotales",
                         "Verificar árbol jerárquico"],
            ))
        if risk.operational_risk >= 50:
            result.append(QARecommendation(
                message=(
                    f"Riesgo operacional alto ({risk.operational_risk:.0f}/100). "
                    "Errores de parser o validación."
                ),
                actions=["Revisar errores de parser",
                         "Verificar validación de balance"],
            ))
        return result

    def _issue_recommendations(
        self, issues: list[Any] | None,
    ) -> list[QARecommendation]:
        result: list[QARecommendation] = []
        if not issues:
            return result
        critical = [i for i in issues if getattr(i, "severity", "") == "CRITICAL"]
        if critical:
            result.append(QARecommendation(
                message=(
                    f"{len(critical)} issue(s) crítico(s) detectado(s). "
                    "Requieren atención inmediata."
                ),
                actions=["Resolver issues críticos antes de continuar"],
            ))
        return result

    def _coverage_recommendations(
        self, coverage_data: dict[str, Any] | None,
    ) -> list[QARecommendation]:
        result: list[QARecommendation] = []
        if not coverage_data:
            return result
        monetary = coverage_data.get("monetary", {}) or {}
        cov = float(monetary.get("coverage_pct", 0.0))
        total = float(monetary.get("total_amount", 0.0))
        explained = float(monetary.get("explained_amount", 0.0))
        if total > 0 and (total - explained) > 100000:
            result.append(QARecommendation(
                message=(
                    f"Diferencia significativa en cobertura monetaria: "
                    f"${total - explained:,.0f} no explicado."
                ),
                actions=["Identificar cuentas con montos faltantes",
                         "Verificar totales de familia"],
            ))
        return result
