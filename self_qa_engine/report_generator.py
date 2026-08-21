from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    QAResult, QASummary, ApprovalState,
)

logger = logging.getLogger(__name__)


class QaReportGenerator:
    """Genera reportes de Self QA en formato Markdown."""

    def generate_full_report(
        self,
        result: QAResult,
        document_info: dict[str, Any] | None = None,
    ) -> str:
        lines: list[str] = []
        doc_info = document_info or {}
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        source = doc_info.get("source_file", "N/A")
        company = doc_info.get("company", "N/A")
        year = doc_info.get("year", "N/A")

        state_icons = {
            ApprovalState.APPROVED: "✅",
            ApprovalState.APPROVED_WITH_WARNINGS: "⚠️",
            ApprovalState.MANUAL_REVIEW: "🔍",
            ApprovalState.LEARNING: "📚",
            ApprovalState.STRESS: "🔴",
            ApprovalState.REJECTED: "❌",
            ApprovalState.FAILED: "💥",
        }
        state_icon = state_icons.get(result.approval_state, "❓")

        lines.append("# Self QA Validation Report")
        lines.append("")
        lines.append(f"**Generado:** {timestamp}")
        lines.append(f"**Documento:** {source}")
        lines.append(f"**Empresa:** {company}")
        lines.append(f"**Año:** {year}")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append(f"## Estado: {state_icon} {result.approval_state.value}")
        lines.append("")
        lines.append(f"**Decisión:** {result.decision_reason}")
        lines.append("")

        lines.append("---")
        lines.append("")

        lines.append("## Confianza")
        lines.append("")
        c = result.confidence
        lines.append(f"- **Overall:** {c.overall:.2%}")
        lines.append(f"- **Coverage:** {c.coverage:.2%}")
        lines.append(f"- **Decision:** {c.decision:.2%}")
        lines.append(f"- **Validation:** {c.validation:.2%}")
        lines.append(f"- **Parser:** {c.parser:.2%}")
        lines.append(f"- **Knowledge:** {c.knowledge:.2%}")
        lines.append(f"- **Structure:** {c.structure:.2%}")
        lines.append(f"- **DIE:** {c.die:.2%}")
        lines.append("")

        lines.append("## Riesgo")
        lines.append("")
        r = result.risk
        risk_icons = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}
        risk_icon = risk_icons.get(r.level.value, "⚪")
        lines.append(f"- **Total:** {r.total_risk:.1f}/100 {risk_icon} ({r.level.value})")
        lines.append(f"- **Documental:** {r.document_risk:.1f}")
        lines.append(f"- **Estructural:** {r.structural_risk:.1f}")
        lines.append(f"- **Monetario:** {r.monetary_risk:.1f}")
        lines.append(f"- **Semántico:** {r.semantic_risk:.1f}")
        lines.append(f"- **Operacional:** {r.operational_risk:.1f}")
        lines.append("")

        lines.append("## Quality Gates")
        lines.append("")
        lines.append("| Gate | Estado | Score | Umbral | Detalle |")
        lines.append("|------|--------|-------|--------|---------|")
        for gate in result.gates:
            icon = "✅" if gate.passed else "❌"
            lines.append(
                f"| {gate.name} | {icon} | {gate.score:.2%} | "
                f"{gate.weight:.0%} | {gate.detail} |"
            )
        lines.append("")

        if result.issues:
            lines.append("## Issues Detectados")
            lines.append("")
            lines.append("| Fuente | Tipo | Severidad | Impacto | Detalle |")
            lines.append("|--------|------|-----------|---------|---------|")
            for iss in result.issues:
                sev_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "ℹ️"}
                sev_icon = sev_icons.get(iss.severity, "⚪")
                lines.append(
                    f"| {iss.source} | {iss.issue_type} | {sev_icon} {iss.severity} | "
                    f"{iss.impact:.2f} | {iss.detail} |"
                )
            lines.append("")

        if result.recommendations:
            lines.append("## Recomendaciones")
            lines.append("")
            for i, rec in enumerate(result.recommendations, 1):
                lines.append(f"{i}. **{rec.message}**")
                for action in rec.actions:
                    lines.append(f"   - {action}")
            lines.append("")

        return "\n".join(lines)

    def generate_summary_report(self, summary: QASummary) -> str:
        lines: list[str] = []
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines.append("# Self QA Summary Report")
        lines.append("")
        lines.append(f"**Generado:** {timestamp}")
        lines.append(f"**Documentos procesados:** {summary.total_documents}")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("## Distribución por Estado")
        lines.append("")
        total = summary.total_documents or 1
        lines.append("| Estado | Cantidad | % |")
        lines.append("|--------|----------|---|")
        for state, count in [
            ("APPROVED", summary.approved),
            ("APPROVED_WITH_WARNINGS", summary.approved_with_warnings),
            ("MANUAL_REVIEW", summary.manual_review),
            ("LEARNING", summary.learning),
            ("STRESS", summary.stress),
            ("REJECTED", summary.rejected),
            ("FAILED", summary.failed),
        ]:
            pct = count / total * 100
            lines.append(f"| {state} | {count} | {pct:.1f}% |")
        lines.append("")

        lines.append("## Promedios Globales")
        lines.append("")
        lines.append(f"- **Confianza promedio:** {summary.avg_confidence:.2%}")
        lines.append(f"- **Riesgo promedio:** {summary.avg_risk:.1f}/100 ({summary.avg_risk_level.value})")
        lines.append("")

        for key, label in [
            ("by_template", "Template"),
            ("by_parser", "Parser"),
            ("by_company", "Empresa"),
            ("by_family", "Familia"),
            ("by_year", "Año"),
        ]:
            data = getattr(summary, key, {})
            if data:
                lines.append(f"## Distribución por {label}")
                lines.append("")
                lines.append(f"| {label} | Confianza Promedio | Documentos |")
                lines.append("|--------|-------------------|------------|")
                for k, v in sorted(data.items()):
                    lines.append(
                        f"| {k} | {v['avg_confidence']:.2%} | {v['count']} |"
                    )
                lines.append("")

        return "\n".join(lines)

    def save_report(
        self,
        content: str,
        path: str | Path = "reports/self_qa_validation.md",
    ) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        logger.info("Self QA report saved to: %s", out.resolve())
        return out
