from __future__ import annotations

from collections import Counter
from typing import Any

from .models import (
    DocumentType, Family, ParserName, Complexity,
    IntelligenceReport,
)


class DocumentIntelligenceStats:

    def __init__(self):
        self.reports: list[IntelligenceReport] = []

    def add_report(self, report: IntelligenceReport):
        self.reports.append(report)

    def add_reports(self, reports: list[IntelligenceReport]):
        self.reports.extend(reports)

    def clear(self):
        self.reports.clear()

    @property
    def total_documents(self) -> int:
        return len(self.reports)

    def by_family(self) -> dict[str, int]:
        counts: Counter = Counter()
        for r in self.reports:
            family = r.family.family.value if r.family and r.family.family else "DESCONOCIDO"
            counts[family] += 1
        return dict(counts.most_common())

    def by_document_type(self) -> dict[str, int]:
        counts: Counter = Counter()
        for r in self.reports:
            dt = r.classification.document_type.value if r.classification.document_type else "OTRO"
            counts[dt] += 1
        return dict(counts.most_common())

    def by_template(self) -> dict[str, int]:
        counts: Counter = Counter()
        for r in self.reports:
            tname = r.profile.template or "SIN_TEMPLATE"
            counts[tname] += 1
        return dict(counts.most_common())

    def by_parser(self) -> dict[str, int]:
        counts: Counter = Counter()
        for r in self.reports:
            pname = r.parser.parser_name.value if r.parser else "NO_PARSER"
            counts[pname] += 1
        return dict(counts.most_common())

    def by_needs_ocr(self) -> dict[str, int]:
        yes = sum(1 for r in self.reports if r.recommendation and r.recommendation.needs_ocr)
        no = self.total_documents - yes
        return {"Sí": yes, "No": no}

    def by_needs_review(self) -> dict[str, int]:
        yes = sum(1 for r in self.reports if r.recommendation and r.recommendation.needs_human_review)
        no = self.total_documents - yes
        return {"Sí": yes, "No": no}

    def by_complexity(self) -> dict[str, int]:
        counts: Counter = Counter()
        for r in self.reports:
            c = r.recommendation.complexity.value if r.recommendation and r.recommendation.complexity else "N/A"
            counts[c] += 1
        return dict(counts.most_common())

    def by_confidence_range(self) -> dict[str, int]:
        ranges = Counter()
        for r in self.reports:
            if not r.confidence:
                ranges["N/A"] += 1
                continue
            pct = r.confidence.confidence_pct
            if pct >= 90:
                ranges["90-100%"] += 1
            elif pct >= 70:
                ranges["70-89%"] += 1
            elif pct >= 50:
                ranges["50-69%"] += 1
            elif pct >= 30:
                ranges["30-49%"] += 1
            else:
                ranges["0-29%"] += 1
        return dict(ranges.most_common())

    def by_recommendation(self) -> dict[str, int]:
        counts: Counter = Counter()
        for r in self.reports:
            rec = r.recommendation.recommendation.value if r.recommendation and r.recommendation.recommendation else "N/A"
            counts[rec] += 1
        return dict(counts.most_common())

    def by_coverage_range(self) -> dict[str, int]:
        ranges = Counter()
        for r in self.reports:
            if not r.coverage:
                ranges["N/A"] += 1
                continue
            pct = r.coverage.coverage_pct
            if pct >= 90:
                ranges["90-100%"] += 1
            elif pct >= 70:
                ranges["70-89%"] += 1
            elif pct >= 50:
                ranges["50-69%"] += 1
            else:
                ranges["0-49%"] += 1
        return dict(ranges.most_common())

    def avg_confidence(self) -> float:
        scores = [r.confidence.global_score for r in self.reports if r.confidence]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 4)

    def avg_coverage(self) -> float:
        scores = [r.coverage.global_pct for r in self.reports if r.coverage]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 4)

    def avg_estimated_time(self) -> float:
        times = [r.recommendation.estimated_time_seconds for r in self.reports if r.recommendation]
        if not times:
            return 0.0
        return round(sum(times) / len(times), 1)

    def total_templates_found(self) -> int:
        return len({r.profile.template for r in self.reports if r.profile.template})

    def total_parsers_used(self) -> int:
        return len({r.parser.parser_name.value for r in self.reports if r.parser})

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "by_family": self.by_family(),
            "by_document_type": self.by_document_type(),
            "by_template": self.by_template(),
            "by_parser": self.by_parser(),
            "by_needs_ocr": self.by_needs_ocr(),
            "by_needs_review": self.by_needs_review(),
            "by_complexity": self.by_complexity(),
            "by_confidence_range": self.by_confidence_range(),
            "by_recommendation": self.by_recommendation(),
            "by_coverage_range": self.by_coverage_range(),
            "avg_confidence": self.avg_confidence(),
            "avg_coverage": self.avg_coverage(),
            "avg_estimated_time": self.avg_estimated_time(),
            "total_templates_found": self.total_templates_found(),
            "total_parsers_used": self.total_parsers_used(),
        }

    def generate_markdown(self) -> str:
        d = self.to_dict()
        lines = [
            "# Document Intelligence — Reporte de Validación",
            "",
            "---",
            "",
            "## Resumen Global",
            "",
            f"| Métrica | Valor |",
            f"|---------|-------|",
            f"| Documentos procesados | {d['total_documents']} |",
            f"| Confianza promedio | {d['avg_confidence']:.1%} |",
            f"| Cobertura promedio | {d['avg_coverage']:.1%} |",
            f"| Tiempo estimado promedio | {d['avg_estimated_time']:.1f}s |",
            f"| Templates encontrados | {d['total_templates_found']} |",
            f"| Parsers utilizados | {d['total_parsers_used']} |",
            "",
            "---",
            "",
            "## Distribución por Familia",
            "",
            "| Familia | Cantidad |",
            "|---------|----------|",
        ]
        for fam, cnt in d["by_family"].items():
            pct = cnt / max(d["total_documents"], 1) * 100
            lines.append(f"| {fam} | {cnt} ({pct:.1f}%) |")

        lines += [
            "",
            "## Distribución por Tipo Documental",
            "",
            "| Tipo | Cantidad |",
            "|------|----------|",
        ]
        for dt, cnt in d["by_document_type"].items():
            lines.append(f"| {dt} | {cnt} |")

        lines += [
            "",
            "## Distribución por Template",
            "",
            "| Template | Cantidad |",
            "|----------|----------|",
        ]
        for t, cnt in d["by_template"].items():
            lines.append(f"| {t} | {cnt} |")

        lines += [
            "",
            "## Distribución por Parser Recomendado",
            "",
            "| Parser | Cantidad |",
            "|--------|----------|",
        ]
        for p, cnt in d["by_parser"].items():
            lines.append(f"| {p} | {cnt} |")

        lines += [
            "",
            "## Necesidad de OCR",
            "",
            f"| Requiere OCR | Cantidad |",
            f"|-------------|----------|",
        ]
        for k, v in d["by_needs_ocr"].items():
            lines.append(f"| {k} | {v} |")

        lines += [
            "",
            "## Necesidad de Revisión Humana",
            "",
            f"| Requiere Revisión | Cantidad |",
            f"|------------------|----------|",
        ]
        for k, v in d["by_needs_review"].items():
            lines.append(f"| {k} | {v} |")

        lines += [
            "",
            "## Distribución por Complejidad",
            "",
            "| Complejidad | Cantidad |",
            "|-------------|----------|",
        ]
        for c, cnt in d["by_complexity"].items():
            lines.append(f"| {c} | {cnt} |")

        lines += [
            "",
            "## Distribución por Rango de Confianza",
            "",
            "| Confianza | Cantidad |",
            "|-----------|----------|",
        ]
        for rng, cnt in d["by_confidence_range"].items():
            lines.append(f"| {rng} | {cnt} |")

        lines += [
            "",
            "## Distribución por Recomendación",
            "",
            "| Recomendación | Cantidad |",
            "|---------------|----------|",
        ]
        for rec, cnt in d["by_recommendation"].items():
            lines.append(f"| {rec} | {cnt} |")

        lines += ["", "---", "", "*Reporte generado por Document Intelligence Engine*"]
        return "\n".join(lines)
