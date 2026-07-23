from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .impact_analyzer import ImpactAnalyzer
from .knowledge_diff import KnowledgeChange, KnowledgeDiff
from .knowledge_snapshot import KnowledgeSnapshot


class EvolutionReport:
    def __init__(self, snapshot: dict, impact: dict, diff: dict):
        self.snapshot = snapshot
        self.impact = impact
        self.diff = diff

    def _snapshot_to_df(self) -> pd.DataFrame:
        variants = self.snapshot.get("variants_by_code", {})
        rows = []
        for code, vlist in sorted(variants.items()):
            rows.append({
                "concepto": code,
                "variantes": len(vlist),
                "variantes_lista": ", ".join(vlist[:10]),
                "clasificadas": self.snapshot.get("concept_counts", {}).get(code, 0),
            })
        return pd.DataFrame(rows)

    def generate_changes_xlsx(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        changes = self.impact.get("changes", [])
        df = pd.DataFrame(changes) if changes else pd.DataFrame(columns=[
            "change_id", "date", "source", "change_type", "concept",
            "old_value", "new_value", "reason", "impact_accounts",
            "impact_documents", "impact_companies", "approved",
        ])
        df.to_excel(out, index=False)
        return out

    def generate_timeline_xlsx(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = [{
            "event": "Snapshot captured",
            "timestamp": self.snapshot.get("timestamp", ""),
            "variant_count": self.snapshot.get("variant_count", 0),
            "concept_count": self.snapshot.get("concept_count", 0),
            "unknown_count": self.snapshot.get("statistics", {}).get("total_unknown", 0),
            "classify_rate": self.snapshot.get("statistics", {}).get("classify_rate", 0),
        }]
        pd.DataFrame(data).to_excel(out, index=False)
        return out

    def generate_impact_summary_xlsx(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        before = self.impact.get("snapshot_before", {})
        after = self.impact.get("snapshot_after", {})
        data = [
            {"metric": "Variant Count", "before": before.get("variant_count", 0),
             "after": after.get("variant_count", 0),
             "delta": after.get("variant_count", 0) - before.get("variant_count", 0)},
            {"metric": "UNKNOWN Count", "before": before.get("unknown_count", 0),
             "after": after.get("unknown_count", 0),
             "delta": after.get("unknown_count", 0) - before.get("unknown_count", 0)},
            {"metric": "Classify Rate", "before": before.get("classify_rate", 0),
             "after": after.get("classify_rate", 0),
             "delta": round(after.get("classify_rate", 0) - before.get("classify_rate", 0), 1)},
            {"metric": "New Accounts Classified", "before": 0,
             "after": self.impact.get("total_new_accounts", 0),
             "delta": self.impact.get("total_new_accounts", 0)},
        ]
        pd.DataFrame(data).to_excel(out, index=False)
        return out

    def generate_concept_growth_xlsx(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        gains = self.impact.get("concept_gains", {})
        variants_added = self.impact.get("variants_added", {})
        rows = []
        for code, gain in sorted(gains.items(), key=lambda x: -x[1]):
            rows.append({
                "concepto": code,
                "variantes_agregadas": variants_added.get(code, 0),
                "nuevas_cuentas": gain,
            })
        if not rows:
            rows.append({"concepto": "", "variantes_agregadas": 0, "nuevas_cuentas": 0})
        pd.DataFrame(rows).to_excel(out, index=False)
        return out

    def generate_knowledge_diff_xlsx(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        summary = self.diff.get("diff_summary", {})
        changes = self.impact.get("changes", [])
        rows = []
        for chg in changes:
            rows.append({
                "change_id": chg.get("change_id", ""),
                "concept": chg.get("concept", ""),
                "change_type": chg.get("change_type", ""),
                "new_value": chg.get("new_value", ""),
                "impact_accounts": chg.get("impact_accounts", 0),
            })
        if not rows:
            rows.append(dict.fromkeys(["change_id", "concept", "change_type", "new_value", "impact_accounts"], ""))
        pd.DataFrame(rows).to_excel(out, index=False)
        return out

    def generate_markdown(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Knowledge Evolution Report", "",
                  f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", "",
                  "## 1. Changes Summary", "",
                  f"**Total Changes:** {len(self.impact.get('changes', []))}", ""]

        changes = self.impact.get("changes", [])
        concepts_affected = set(chg.get("concept", "") for chg in changes)
        lines.append(f"**Concepts Affected:** {len(concepts_affected)}")
        lines.append(f"**Variants Added:** {sum(self.impact.get('variants_added', {}).values())}")
        lines.append(f"**Variants Removed:** 0")
        lines.append("")

        before = self.impact.get("snapshot_before", {})
        after = self.impact.get("snapshot_after", {})
        lines.append(f"**Impact on UNKNOWN:** {before.get('unknown_count', 0):,} → {after.get('unknown_count', 0):,} "
                      f"({before.get('unknown_count', 0) - after.get('unknown_count', 0):,} new classifications)")
        lines.append(f"**Impact on Coverage:** {before.get('classify_rate', 0)}% → {after.get('classify_rate', 0)}% "
                      f"({self.impact.get('diff_summary', {}).get('classify_rate_diff', 0)} pp)")
        lines.append("")

        lines.append("## 2. Top Changes by Impact")
        lines.append("")
        concept_gains = self.impact.get("concept_gains", {})
        for rank, (code, gain) in enumerate(sorted(concept_gains.items(), key=lambda x: -x[1])[:10], 1):
            lines.append(f"**{rank}. {code}:** +{gain} accounts classified")

        lines.append("")
        lines.append("## 3. Top Concepts Affected")
        lines.append("")
        for rank, code in enumerate(sorted(concepts_affected)[:15], 1):
            gain = concept_gains.get(code, 0)
            lines.append(f"{rank}. {code} — +{gain} new classifications")
        lines.append("")

        lines.append("## 4. Total Impact")
        lines.append("")
        lines.append(f"**New Exact Match:** {self.impact.get('total_new_accounts', 0)}")
        lines.append(f"**Total Companies Improved:** {self.impact.get('total_new_companies', 0)}")
        lines.append("")

        lines.append("## 5. Pending Approvals")
        lines.append("")
        pending = sum(1 for chg in changes if not chg.get("approved"))
        lines.append(f"**Changes pending approval:** {pending}")
        lines.append("")

        lines.append("## 6. Before / After Comparison")
        lines.append("")
        lines.append(f"| Metric | Before | After | Delta |")
        lines.append(f"|---|---|---|---|")
        lines.append(f"| Variants | {before.get('variant_count', 0):,} | {after.get('variant_count', 0):,} | "
                      f"{after.get('variant_count', 0) - before.get('variant_count', 0):,} |")
        lines.append(f"| UNKNOWN | {before.get('unknown_count', 0):,} | {after.get('unknown_count', 0):,} | "
                      f"{before.get('unknown_count', 0) - after.get('unknown_count', 0):,} |")
        lines.append(f"| Classify Rate | {before.get('classify_rate', 0)}% | {after.get('classify_rate', 0)}% | "
                      f"{round(after.get('classify_rate', 0) - before.get('classify_rate', 0), 1)} pp |")
        lines.append("")
        lines.append("*Simulation mode — no production files were modified.*")

        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    def generate_statistics_json(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        stats = {
            "snapshot": {
                "timestamp": self.snapshot.get("timestamp", ""),
                "cmcc_hash": self.snapshot.get("cmcc_hash", ""),
                "variant_count": self.snapshot.get("variant_count", 0),
                "concept_count": self.snapshot.get("concept_count", 0),
                "synonym_count": self.snapshot.get("synonym_count", 0),
                "rule_count": self.snapshot.get("rule_count", 0),
            },
            "impact": {
                "total_new_accounts": self.impact.get("total_new_accounts", 0),
                "total_new_companies": self.impact.get("total_new_companies", 0),
                "concept_gains": self.impact.get("concept_gains", {}),
                "variants_added": self.impact.get("variants_added", {}),
            },
            "diff": self.diff.get("diff_summary", {}),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        return out
