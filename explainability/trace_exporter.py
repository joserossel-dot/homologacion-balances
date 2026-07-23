from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .decision_trace import DecisionTrace
from .trace_report import TraceReport


class TraceExporter:
    def __init__(self, traces: list[DecisionTrace], report: TraceReport):
        self.traces = traces
        self.report = report

    def to_dataframe(self) -> pd.DataFrame:
        rows = [t.to_dict() for t in self.traces]
        df = pd.DataFrame(rows)
        order = [
            "document_id", "company", "layout", "layout_confidence",
            "ocr_confidence", "parser_confidence", "column_mapping_confidence",
            "candidate_accept_rate", "candidate_status", "candidate_reasons",
            "normalized_name", "original_name",
            "cmcc_match", "cmcc_match_type", "cmcc_variant", "cmcc_score",
            "dictionary_match", "dictionary_source",
            "official_classification", "official_confidence",
            "shadow_classification", "shadow_confidence",
            "decision_code", "decision_description",
            "timestamp",
        ]
        return df[[c for c in order if c in df.columns]]

    def export_excel(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df = self.to_dataframe()
        df.to_excel(out, index=False)
        return out

    def export_json(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "summary": self.report.to_dict(),
            "traces": [t.to_dict() for t in self.traces],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return out

    def export_markdown(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Decision Trace Report", "",
                  f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", "",
                  "## Summary", "",
                  f"| Metric | Value |",
                  f"|---|---|",
                  f"| Total Accounts | {self.report.total:,} |",
                  f"| Classified | {self.report.total_classified:,} |",
                  f"| UNKNOWN | {self.report.total_unknown:,} |",
                  f"| Classify Rate | {round(self.report.total_classified / max(self.report.total, 1) * 100, 1)}% |",
                  "", "## Decision Code Distribution", "",
                  "| Code | Count | % |",
                  "|---|---|---|"]
        for d in self.report.decision_code_stats():
            lines.append(f"| {d['decision_code']} | {d['count']:,} | {d['percentage']}% |")

        lines.extend(["", "## Layout Distribution", "",
                       "| Layout | Total | Classified | UNKNOWN | % |",
                       "|---|---|---|---|---|"])
        for d in self.report.layout_stats():
            lines.append(
                f"| {d['layout']} | {d['count']:,} | {d['classified']:,} | "
                f"{d['unknown']:,} | {d['percentage']}% |"
            )

        lines.extend(["", "## Match Type Distribution", "",
                       "| Type | Count | % |",
                       "|---|---|---|"])
        for d in self.report.match_type_stats():
            lines.append(f"| {d['match_type']} | {d['count']:,} | {d['percentage']}% |")

        lines.extend(["", "## Parser Status", "",
                       "| Status | Count | % |",
                       "|---|---|---|"])
        for d in self.report.parser_status_stats():
            lines.append(f"| {d['status']} | {d['count']:,} | {d['percentage']}% |")

        lines.extend(["", "## Top Concepts", "",
                       "| Concept | Count |",
                       "|---|---|"])
        for c in self.report.top_concepts(15):
            lines.append(f"| {c[0]} | {c[1]:,} |")

        lines.extend(["", "## Top Documents by Volume", "",
                       "| Document | Accounts |",
                       "|---|---|"])
        for doc, cnt in self.report.top_documents(10):
            short = doc[:80]
            lines.append(f"| {short} | {cnt:,} |")

        lines.extend(["", "## Sample UNKNOWN Traces", ""])
        for t in self.report.top_unknown(5):
            lines.append("```")
            lines.append(t.explanation)
            lines.append("```")
            lines.append("")

        lines.extend(["", "## Sample Classified Traces", ""])
        for t in self.report.top_classified(5):
            lines.append("```")
            lines.append(t.explanation)
            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("*No pipeline files were modified. Shadow mode only.*")

        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    def export_technical_debt(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        r = self.report
        debt_items = []

        unknown_rate = r.total_unknown / max(r.total, 1) * 100
        if unknown_rate > 50:
            debt_items.append({
                "problema": f"{unknown_rate:.1f}% de cuentas son UNKNOWN ({r.total_unknown:,} de {r.total:,})",
                "impacto": "Alto — más de la mitad de las cuentas no se clasifican",
                "prioridad": "CRITICAL",
                "recomendacion": "Priorizar enriquecimiento de variantes CMCC para Top 10 conceptos con mayor ROI",
                "fase_sugerida": "FASE 21B — Variant Enrichment",
            })

        for ds in r.decision_code_stats():
            if ds["decision_code"] == "D201" and ds["percentage"] > 70:
                debt_items.append({
                    "problema": f"{ds['percentage']}% de cuentas (D201) no tienen variante conocida",
                    "impacto": "Alto — la causa raíz de la mayoría de UNKNOWN",
                    "prioridad": "HIGH",
                    "recomendacion": "Revisar clusters de Variant Discovery para identificar nuevas variantes",
                    "fase_sugerida": "FASE 21B — Variant Enrichment",
                })

        for ls in r.layout_stats():
            if ls.get("unknown", 0) > ls.get("classified", 0) and ls["count"] > 100:
                debt_items.append({
                    "problema": f"Layout '{ls['layout']}' tiene {ls['unknown']:,} UNKNOWN vs {ls['classified']:,} clasificados",
                    "impacto": "Medio — el layout afecta la capacidad de clasificación",
                    "prioridad": "MEDIUM",
                    "recomendacion": "Analizar si el parser necesita ajustes para este layout",
                    "fase_sugerida": "FASE 22 — Parser Optimization",
                })

        shadow_count = sum(1 for t in self.traces if t.shadow_classification and t.shadow_confidence > 0)
        if shadow_count > 0:
            debt_items.append({
                "problema": f"{shadow_count} cuentas tienen clasificación Shadow no incorporada oficialmente",
                "impacto": "Medio — ~{:.1f}% de cuentas podrían reclasificarse".format(
                    shadow_count / max(r.total, 1) * 100
                ),
                "prioridad": "HIGH",
                "recomendacion": "Revisar y promover clasificaciones Shadow con score >= 0.90",
                "fase_sugerida": "FASE 21B — Variant Enrichment",
            })

        cmcc_matches = sum(1 for t in self.traces if t.cmcc_match)
        dict_matches = sum(1 for t in self.traces if t.dictionary_match)
        if dict_matches > cmcc_matches:
            debt_items.append({
                "problema": "Dictionary matches superan a CMCC matches — posible infrautilización del CMCC",
                "impacto": "Bajo",
                "prioridad": "LOW",
                "recomendacion": "Verificar si el Learning Engine está priorizando correctamente",
                "fase_sugerida": "FASE 23 — Learning Engine Tuning",
            })

        if not debt_items:
            debt_items.append({
                "problema": "No se detectaron problemas significativos",
                "impacto": "N/A",
                "prioridad": "NONE",
                "recomendacion": "Monitoreo continuo recomendado",
                "fase_sugerida": "N/A",
            })

        lines = ["# Technical Debt Report", "",
                  f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", "",
                  "| Problema | Impacto | Prioridad | Recomendación | Fase Sugerida |",
                  "|---|---|---|---|---|"]
        for item in debt_items:
            lines.append(
                f"| {item['problema'][:80]} | {item['impacto']} | {item['prioridad']} | "
                f"{item['recomendacion'][:80]} | {item['fase_sugerida']} |"
            )
        lines.append("")
        lines.append("*No corrections were applied. This is a diagnostic-only report.*")

        out.write_text("\n".join(lines), encoding="utf-8")
        return out
