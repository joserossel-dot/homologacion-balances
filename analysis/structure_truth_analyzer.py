from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Optional

from .subtotal_trace import SubtotalTracer, SubtotalTrace
from .root_cause_classifier import RootCauseClassifier, RootCauseResult
from .statistics import StatisticsGenerator, PatternResult, FormatMatrix

from validation.models import ValidationResult, SubtotalResult


class StructureTruthAnalyzer:

    def __init__(self):
        self.tracer = SubtotalTracer()
        self.classifier = RootCauseClassifier()
        self.stats = StatisticsGenerator()

    def analyze_validation_result(
        self,
        result: ValidationResult,
        format_family: str = "",
        all_accounts: list[dict] | None = None,
    ) -> list[RootCauseResult]:
        if not result.subtotal_results:
            return []

        if all_accounts is None:
            all_accounts = []
            if result.hierarchy_tree:
                for node in result.hierarchy_tree.all_nodes:
                    all_accounts.append({
                        "nombre": node.account_name,
                        "amount": node.amount,
                        "codigo": node.account_code,
                        "linea": node.line_number,
                        "es_total": node.es_total,
                    })

        causes = []
        for sr in result.subtotal_results:
            if sr.passed:
                continue

            children_dicts = []
            for child_name in sr.children:
                for acct in all_accounts:
                    a_name = str(acct.get("nombre", acct.get("account_name", ""))).strip()
                    if a_name == child_name.strip():
                        children_dicts.append(acct)
                        break

            trace = self.tracer.build_trace(
                source_file=result.source_file,
                subtotal_name=sr.account_name,
                subtotal_line=sr.line_number,
                expected=sr.expected,
                actual=sr.actual,
                difference=sr.difference,
                pct_diff=sr.pct_diff,
                children=children_dicts or sr.children,
                all_accounts=all_accounts,
            )

            cause = self.classifier.classify(trace, all_accounts, result.subtotal_results)
            causes.append(cause)

            self.stats.add_result(trace, cause, format_family)

        return causes

    def load_validation_results_from_reports(
        self,
        reports_dir: str | Path = "reports/balance_validation_reports",
    ) -> list[ValidationResult]:
        results = []
        reports_dir = Path(reports_dir)
        for f in sorted(reports_dir.glob("*_validation.txt")):
            text = f.read_text()
            vr = ValidationResult(source_file=f.name.replace("_validation.txt", "").replace("_", " "))
            self._parse_report_text(vr, text)
            results.append(vr)
        return results

    def _parse_report_text(self, vr: ValidationResult, text: str):
        import re
        lines = text.split("\n")
        for line in lines:
            m = re.search(r"Source file:\s+(.+)", line)
            if m:
                vr.source_file = m.group(1).strip()

            m = re.search(r"Format:\s+(.+)", line)
            if m:
                vr.format_family = m.group(1).strip()

            m = re.search(r"Total accounts:\s+(\d+)", line)
            if m:
                vr.accounts_total = int(m.group(1))

            m = re.search(r"Classified:\s+(\d+)", line)
            if m:
                vr.accounts_classified = int(m.group(1))

            m = re.search(r"Pages:\s+(\d+)", line)
            if m:
                vr.pages = int(m.group(1))

            m = re.search(r"\[FAIL\]\s+(.+?):\s+expected=([\d,.]+)\s+actual=([\d,.]+)\s+diff=([\d,.]+)\s+\(([\d.]+)%\)", line)
            if m:
                name = m.group(1).strip()
                expected = float(m.group(2).replace(",", ""))
                actual = float(m.group(3).replace(",", ""))
                diff = float(m.group(4).replace(",", ""))
                pct = float(m.group(5))
                vr.subtotal_results.append(SubtotalResult(
                    account_name=name,
                    expected=expected,
                    actual=actual,
                    difference=diff,
                    pct_diff=pct,
                    passed=False,
                    line_number=0,
                ))

        vr.subtotal_results = [sr for sr in vr.subtotal_results if not sr.passed]

    def generate_report_section(
        self,
        output_path: str | Path = "reports/structure_truth_report.md",
        json_path: str | Path = "reports/structure_truth.json",
    ):
        output_path = Path(output_path)
        json_path = Path(json_path)

        lines = []
        lines.append("# Structure Truth Analyzer — Report")
        lines.append("")
        lines.append(f"Generated: {__import__('datetime').datetime.now().isoformat()}")
        lines.append("")
        lines.append("## 1. Executive Summary")
        lines.append("")
        total = self.stats.total_differences
        lines.append(f"- **Total differences analyzed:** {total}")
        lines.append(f"- **Balances contributing:** {len(set(tr.source_file for tr in self.stats.traces))}")
        lines.append("")

        cause_dist = self.stats.cause_distribution()
        lines.append("## 2. Root Cause Distribution")
        lines.append("")
        lines.append("| Cause | Count | % |")
        lines.append("|-------|-------|---|")
        for cause, count in cause_dist.items():
            pct = round(count / total * 100, 1) if total else 0
            lines.append(f"| {cause} | {count} | {pct}% |")
        lines.append("")

        matrix = self.stats.cause_by_format_matrix()
        lines.append("## 3. Distribution by Format")
        lines.append("")
        lines.append("| Format | Total | " + " | ".join(sorted(set(
            c for fm in matrix for c in fm.by_cause
        ))) + " |")
        headers = ["|--------|-------|" + "|".join("---" for _ in sorted(set(
            c for fm in matrix for c in fm.by_cause
        ))) + "|"]
        lines.extend(headers)
        for fm in matrix:
            causes_sorted = sorted(set(c for fm_ in matrix for c in fm_.by_cause))
            row = f"| {fm.format_name} | {fm.total_differences} "
            for cause in causes_sorted:
                row += f"| {fm.by_cause.get(cause, 0)} "
            lines.append(row + "|")
        lines.append("")

        patterns = self.stats.find_patterns(top_n=20)
        lines.append("## 4. Top 20 Repeated Patterns (by subtotal)")
        lines.append("")
        lines.append("| # | Subtotal | Freq | Avg Diff | Typical Cause |")
        lines.append("|---|----------|------|----------|---------------|")
        for i, p in enumerate(patterns, 1):
            lines.append(f"| {i} | {p.account_name[:45]} | {p.frequency} | {p.avg_difference:,.0f} | {p.typical_cause} |")
        lines.append("")

        conflictive = self.stats.find_conflictive_accounts(top_n=20)
        lines.append("## 5. Top 20 Conflictive Accounts")
        lines.append("")
        lines.append("| # | Account | Freq | Avg Diff | Typical Cause |")
        lines.append("|---|---------|------|----------|---------------|")
        for i, a in enumerate(conflictive, 1):
            lines.append(f"| {i} | {a.account_name[:45]} | {a.frequency} | {a.avg_difference:,.0f} | {a.typical_cause} |")
        lines.append("")

        impact = self.stats.calculate_impact_potential()
        lines.append("## 6. Impact Potential by Improvement Type")
        lines.append("")
        lines.append("| Improvement | Count | % of Total |")
        lines.append("|-------------|-------|------------|")
        labels = {
            "parser_improvement": "Parser improvement",
            "hierarchy_improvement": "Hierarchy improvement",
            "dictionary_improvement": "Dictionary improvement",
            "knowledge_base_improvement": "Knowledge Base improvement",
            "human_review": "Human review",
        }
        for key, label in labels.items():
            data = impact.get(key, {})
            lines.append(f"| {label} | {data.get('count', 0)} | {data.get('pct', 0)}% |")
        lines.append("")

        repeated_causes = self.stats.find_repeated_account_causes(top_n=20)
        lines.append("## 7. Top 20 Repeated Account-Cause Pairs")
        lines.append("")
        lines.append("| # | Account | Occurrences | Dominant Cause |")
        lines.append("|---|---------|-------------|----------------|")
        for i, rc in enumerate(repeated_causes, 1):
            lines.append(f"| {i} | {rc['account'][:45]} | {rc['total_occurrences']} | {rc['dominant_cause']} |")
        lines.append("")

        lines.append("## 8. Recommendations")
        lines.append("")
        lines.append("Based on the quantitative evidence above:")
        lines.append("")
        lines.append(f"1. **Parser improvement** could resolve {impact.get('parser_improvement', {}).get('pct', 0)}% of differences")
        lines.append(f"2. **Hierarchy improvement** could resolve {impact.get('hierarchy_improvement', {}).get('pct', 0)}% of differences")
        lines.append(f"3. **Dictionary improvement** could resolve {impact.get('dictionary_improvement', {}).get('pct', 0)}% of differences")
        lines.append(f"4. **Knowledge Base improvement** could resolve {impact.get('knowledge_base_improvement', {}).get('pct', 0)}% of differences")
        lines.append(f"5. **Human review** needed for {impact.get('human_review', {}).get('pct', 0)}% of differences")
        lines.append("")

        content = "\n".join(lines)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        json_data = {
            "metadata": {
                "total_differences": total,
                "files_analyzed": len(set(tr.source_file for tr in self.stats.traces)),
            },
            "root_cause_distribution": cause_dist,
            "format_matrix": [
                {
                    "format": fm.format_name,
                    "total": fm.total_differences,
                    "by_cause": dict(sorted(fm.by_cause.items())),
                    "files": fm.by_file,
                }
                for fm in matrix
            ],
            "top_patterns": [
                {
                    "subtotal": p.account_name,
                    "frequency": p.frequency,
                    "avg_difference": p.avg_difference,
                    "typical_cause": p.typical_cause,
                    "files": p.files,
                }
                for p in patterns
            ],
            "top_conflictive_accounts": [
                {
                    "account": a.account_name,
                    "frequency": a.frequency,
                    "avg_difference": a.avg_difference,
                    "typical_cause": a.typical_cause,
                    "files": a.files,
                }
                for a in conflictive
            ],
            "impact_potential": impact,
            "repeated_account_causes": repeated_causes,
        }

        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(json_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return content

    def load_gold_standard(self, db_path: str = "gold_standard.db") -> list[dict]:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT codigo_estandar, nombre_cuenta, normalized FROM gold_standard"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def load_kb_variants(self, kb_path: str = "knowledge_base/cmcc_knowledge.json") -> list[str]:
        path = Path(kb_path)
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        variants = []
        codes = data.get("codes", data)
        for code_key, code_data in codes.items():
            if isinstance(code_data, dict):
                for v in code_data.get("variantes", []):
                    if isinstance(v, dict):
                        variants.append(v.get("nombre", ""))
        return variants
