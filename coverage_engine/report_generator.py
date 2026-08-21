from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    CoverageResult, CoverageStatistics, CoverageSummary,
    CoverageIssue, FAMILY_ORDER, EXPECTED_SECTIONS,
)

logger = logging.getLogger(__name__)


class CoverageReportGenerator:
    """Genera reportes de cobertura en formato Markdown."""

    def generate_full_report(
        self,
        result: CoverageResult,
        document_info: dict[str, Any] | None = None,
    ) -> str:
        lines: list[str] = []
        doc_info = document_info or {}
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        source = doc_info.get("source_file", "N/A")
        company = doc_info.get("company", "N/A")
        year = doc_info.get("year", "N/A")

        lines.append("# Coverage Validation Report")
        lines.append("")
        lines.append(f"**Generado:** {timestamp}")
        lines.append(f"**Documento:** {source}")
        lines.append(f"**Empresa:** {company}")
        lines.append(f"**Año:** {year}")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("## Resumen General")
        lines.append("")
        lines.append(f"- **Coverage Total:** {result.overall:.2%}")
        lines.append(f"- **Coverage Monetario:** {result.monetary.coverage_pct:.2%}")
        lines.append(f"- **Coverage Estructural:** {result.structural.overall:.2%}")
        lines.append(f"- **Coverage Semántico:** {result.semantic.overall:.2%}")
        lines.append(f"- **Coverage Documental:** {result.document.coverage_pct:.2%}")
        lines.append(f"- **Issues detectados:** {len(result.issues)}")
        lines.append("")
        lines.append("### Pesos aplicados")
        lines.append("")
        for key, weight in result.weights.items():
            lines.append(f"- **{key.title()}:** {weight:.0%}")
        lines.append("")

        lines.append("---")
        lines.append("")

        lines.extend(self._monetary_section(result))
        lines.extend(self._structural_section(result))
        lines.extend(self._semantic_section(result))
        lines.extend(self._document_section(result))
        lines.extend(self._issues_section(result))
        lines.extend(self._matrices_section(result))

        return "\n".join(lines)

    def _monetary_section(self, result: CoverageResult) -> list[str]:
        lines: list[str] = []
        lines.append("## Coverage Monetario")
        lines.append("")
        m = result.monetary
        lines.append(f"**Monto Total:** {m.total_amount:,.2f}")
        lines.append(f"**Monto Explicado:** {m.explained_amount:,.2f}")
        lines.append(f"**Coverage:** {m.coverage_pct:.2%}")
        lines.append("")

        lines.append("| Familia | Total | Explicado | Coverage |")
        lines.append("|---------|-------|-----------|----------|")
        for family in FAMILY_ORDER:
            data = m.by_family.get(family, {})
            total = data.get("total", 0.0)
            explained = data.get("explained", 0.0)
            cov = data.get("coverage_pct", 0.0)
            status = "✓" if cov >= 0.95 else ("⚠" if cov >= 0.8 else "✗")
            lines.append(
                f"| {family} | {total:,.2f} | {explained:,.2f} | "
                f"{status} {cov:.2%} |"
            )
        lines.append("")
        if m.coverage_pct >= 0.95:
            lines.append("**Estado:** ✓ Coverage monetario aceptable")
        elif m.coverage_pct >= 0.8:
            lines.append("**Estado:** ⚠ Coverage monetario parcial")
        else:
            lines.append("**Estado:** ✗ Coverage monetario insuficiente")
        lines.append("")
        return lines

    def _structural_section(self, result: CoverageResult) -> list[str]:
        lines: list[str] = []
        lines.append("## Coverage Estructural")
        lines.append("")
        s = result.structural
        lines.append(f"- **Subtotales esperados:** {s.subtotals_expected}")
        lines.append(f"- **Subtotales detectados:** {s.subtotals_detected}")
        lines.append(f"- **Subtotales validados:** {s.subtotals_validated}")
        lines.append(f"- **Subtotales consistentes:** {s.subtotals_consistent}")
        lines.append(f"- **Jerarquía reconstruida:** {s.hierarchy_reconstructed:.2%}")
        lines.append(f"- **Template cubierto:** {s.template_coverage:.2%}")
        lines.append(f"- **Overall:** {s.overall:.2%}")
        lines.append("")
        return lines

    def _semantic_section(self, result: CoverageResult) -> list[str]:
        lines: list[str] = []
        lines.append("## Coverage Semántico")
        lines.append("")
        s = result.semantic
        lines.append(f"- **Cuentas totales:** {s.total_accounts}")
        lines.append(f"- **Cuentas clasificadas:** {s.classified_count}")
        lines.append(f"- **Cuentas conocidas (KB):** {s.known_count}")
        lines.append(f"- **Learning hits:** {s.learning_hits}")
        lines.append(f"- **KB matches:** {s.kb_matches}")
        lines.append(f"- **Review workspace:** {s.review_workspace}")
        lines.append(f"- **Cuentas desconocidas:** {s.unknown_count}")
        lines.append(f"- **Coverage semántico:** {s.overall:.2%}")
        lines.append("")
        lines.append("| Familia | Total | Clasificadas | Coverage |")
        lines.append("|---------|------|--------------|----------|")
        for family in FAMILY_ORDER:
            data = s.by_family.get(family, {})
            total = data.get("total", 0)
            classified = data.get("classified", 0)
            cov = data.get("coverage_pct", 0.0)
            lines.append(
                f"| {family} | {total} | {classified} | {cov:.2%} |"
            )
        lines.append("")
        return lines

    def _document_section(self, result: CoverageResult) -> list[str]:
        lines: list[str] = []
        lines.append("## Coverage Documental")
        lines.append("")
        d = result.document
        lines.append(f"- **Secciones esperadas:** {len(d.expected_sections)}")
        lines.append(f"- **Secciones presentes:** {len(d.present_sections)}")
        lines.append(f"- **Secciones correctas:** {len(d.correct_sections)}")
        lines.append(f"- **No aplica:** {len(d.not_applicable_sections)}")
        lines.append(f"- **Coverage:** {d.coverage_pct:.2%}")
        lines.append("")
        lines.append("| Sección | Estado |")
        lines.append("|---------|--------|")
        for sec in EXPECTED_SECTIONS:
            status = d.section_details.get(sec, "MISSING")
            icon = {"OK": "✔", "N/A": "—", "PRESENT": "~", "MISSING": "✗"}.get(
                status, "?"
            )
            lines.append(f"| {sec} | {icon} {status} |")
        lines.append("")
        return lines

    def _issues_section(self, result: CoverageResult) -> list[str]:
        lines: list[str] = []
        if not result.issues:
            lines.append("## Issues")
            lines.append("")
            lines.append("Sin issues detectados.")
            lines.append("")
            return lines
        lines.append("## Issues Detectados")
        lines.append("")
        lines.append("| Tipo | Severidad | Impacto Monetario | Impacto Documental | Detalle |")
        lines.append("|------|-----------|-------------------|---------------------|---------|")
        for issue in result.issues:
            lines.append(
                f"| {issue.issue_type} | {issue.severity.value} | "
                f"{issue.monetary_impact:,.2f} | {issue.document_impact:.2%} | "
                f"{issue.detail} |"
            )
        lines.append("")
        return lines

    def _matrices_section(self, result: CoverageResult) -> list[str]:
        lines: list[str] = []
        lines.append("## Matrices de Cobertura")
        lines.append("")

        lines.append("### Matriz Monetaria por Familia")
        lines.append("")
        lines.append("| Familia | Coverage | Impacto |")
        lines.append("|---------|----------|---------|")
        for family in FAMILY_ORDER:
            data = result.monetary.by_family.get(family, {})
            cov = data.get("coverage_pct", 0.0)
            missing = data.get("total", 0.0) - data.get("explained", 0.0)
            lines.append(f"| {family} | {cov:.2%} | {missing:,.2f} |")
        lines.append("")

        if result.issues:
            lines.append("### Matriz de Issues")
            lines.append("")
            lines.append("| Issue | Severidad | Familia | Impacto $ |")
            lines.append("|-------|-----------|---------|-----------|")
            for issue in result.issues:
                lines.append(
                    f"| {issue.issue_type} | {issue.severity.value} | "
                    f"{issue.family} | {issue.monetary_impact:,.2f} |"
                )
            lines.append("")

        return lines

    def generate_summary_report(
        self,
        summary: CoverageSummary,
    ) -> str:
        lines: list[str] = []
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines.append("# Coverage Summary Report")
        lines.append("")
        lines.append(f"**Generado:** {timestamp}")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("## Resumen General")
        lines.append("")
        lines.append(f"- **Coverage Total:** {summary.overall:.2%}")
        lines.append(f"- **Coverage Monetario:** {summary.monetary:.2%}")
        lines.append(f"- **Coverage Estructural:** {summary.structural:.2%}")
        lines.append(f"- **Coverage Semántico:** {summary.semantic:.2%}")
        lines.append(f"- **Coverage Documental:** {summary.document:.2%}")
        lines.append(f"- **Total Issues:** {summary.total_issues}")
        lines.append(f"- **Issues Críticos:** {summary.critical_issues}")
        lines.append(f"- **Issues Altos:** {summary.high_issues}")
        lines.append("")

        if summary.top_documents:
            lines.append("## Top Documentos")
            lines.append("")
            lines.append("| Documento | Coverage |")
            lines.append("|-----------|----------|")
            for doc in summary.top_documents[:5]:
                lines.append(f"| {doc.get('name', 'N/A')} | {doc.get('score', 0):.2%} |")
            lines.append("")

        if summary.worst_documents:
            lines.append("## Peores Documentos")
            lines.append("")
            lines.append("| Documento | Coverage |")
            lines.append("|-----------|----------|")
            for doc in summary.worst_documents[:5]:
                lines.append(f"| {doc.get('name', 'N/A')} | {doc.get('score', 0):.2%} |")
            lines.append("")

        return "\n".join(lines)

    def generate_statistics_report(
        self,
        stats: CoverageStatistics,
    ) -> str:
        lines: list[str] = []
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines.append("# Coverage Statistics Report")
        lines.append("")
        lines.append(f"**Generado:** {timestamp}")
        lines.append(f"**Documentos:** {stats.total_documents}")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("## Promedios Globales")
        lines.append("")
        lines.append(f"- **Overall promedio:** {stats.overall_avg:.2%}")
        lines.append(f"- **Monetario promedio:** {stats.monetary_avg:.2%}")
        lines.append(f"- **Estructural promedio:** {stats.structural_avg:.2%}")
        lines.append(f"- **Semántico promedio:** {stats.semantic_avg:.2%}")
        lines.append(f"- **Documental promedio:** {stats.document_avg:.2%}")
        lines.append("")

        lines.append("## Percentiles (Overall)")
        lines.append("")
        lines.append(f"- **P25:** {stats.overall_p25:.2%}")
        lines.append(f"- **P50 (Mediana):** {stats.overall_median:.2%}")
        lines.append(f"- **P75:** {stats.overall_p75:.2%}")
        lines.append("")

        if stats.distribution:
            lines.append("## Distribución de Cobertura")
            lines.append("")
            lines.append("| Rango | Documentos |")
            lines.append("|-------|------------|")
            for rng, count in sorted(stats.distribution.items()):
                bar = "█" * count
                lines.append(f"| {rng} | {count} {bar} |")
            lines.append("")

        if stats.by_family:
            lines.append("## Coverage por Familia")
            lines.append("")
            lines.append("| Familia | Promedio | Documentos |")
            lines.append("|---------|----------|------------|")
            for family, data in stats.by_family.items():
                lines.append(
                    f"| {family} | {data['avg']:.2%} | {data['count']} |"
                )
            lines.append("")

        for key, label in [
            ("by_template", "Template"),
            ("by_parser", "Parser"),
            ("by_company", "Empresa"),
            ("by_year", "Año"),
        ]:
            data = getattr(stats, key, {})
            if data:
                lines.append(f"## Coverage por {label}")
                lines.append("")
                lines.append(f"| {label} | Promedio | Documentos |")
                lines.append("|--------|----------|------------|")
                for k, v in data.items():
                    lines.append(f"| {k} | {v['avg']:.2%} | {v['count']} |")
                lines.append("")

        return "\n".join(lines)

    def save_report(
        self,
        content: str,
        path: str | Path = "reports/coverage_validation.md",
    ) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        logger.info("Coverage report saved to: %s", out.resolve())
        return out
