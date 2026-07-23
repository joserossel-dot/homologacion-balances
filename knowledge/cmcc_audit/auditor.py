from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def _safe_int(v: Any) -> int:
    try:
        return int(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def _safe_float(v: Any) -> float:
    try:
        return float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else 0.0
    except (ValueError, TypeError, OverflowError):
        return 0.0


class CMCCAuditor:
    def __init__(
        self,
        cmcc_path: str | Path = "knowledge/cmcc.json",
        audit_path: str | Path = "reports/audit/audit_data.json",
        clusters_path: str | Path = "reports/variant_discovery/clusters.xlsx",
        top_accounts_path: str | Path = "reports/classification_gap/top_accounts.xlsx",
        shadow_path: str | Path = "reports/cmcc_shadow/cmcc_shadow.xlsx",
        calibration_dir: str | Path = "reports/cmcc_calibration",
    ):
        self.cmcc_path = Path(cmcc_path)
        self.audit_path = Path(audit_path)
        self.clusters_path = Path(clusters_path)
        self.top_accounts_path = Path(top_accounts_path)
        self.shadow_path = Path(shadow_path)
        self.calibration_dir = Path(calibration_dir)
        self.conceptos: list[dict] = []
        self.stats: dict[str, Any] = {}

    def load(self) -> None:
        with open(self.cmcc_path, encoding="utf-8") as f:
            self.conceptos = json.load(f)

        audit_accounts: list[dict] = []
        if self.audit_path.exists():
            with open(self.audit_path, encoding="utf-8") as f:
                audit_data = json.load(f)
            audit_accounts = audit_data.get("accounts", audit_data if isinstance(audit_data, list) else [])

        clusters_df = pd.DataFrame()
        if self.clusters_path.exists():
            clusters_df = pd.read_excel(self.clusters_path)

        top_accounts_df = pd.DataFrame()
        if self.top_accounts_path.exists():
            top_accounts_df = pd.read_excel(self.top_accounts_path)

        shadow_df = pd.DataFrame()
        if self.shadow_path.exists():
            shadow_df = pd.read_excel(self.shadow_path)

        calib_df = self._load_calibration()

        self._compute_stats(audit_accounts, clusters_df, top_accounts_df, shadow_df, calib_df)

    def _load_calibration(self) -> pd.DataFrame:
        results = []
        cal_files = sorted(self.calibration_dir.glob("threshold_comparison*.xlsx")) if self.calibration_dir.exists() else []
        if cal_files:
            results.append(pd.read_excel(cal_files[0]))
        combined = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
        return combined

    def _normalize_code(self, raw: str) -> str:
        if not raw or not isinstance(raw, str):
            return ""
        raw = raw.strip().upper()
        for sep in [" — ", " – ", " - ", " – ", " - "]:
            if sep in raw:
                raw = raw.split(sep)[0].strip()
            raw = raw.strip()
        return raw.upper()

    def _compute_stats(
        self,
        accounts: list[dict],
        clusters_df: pd.DataFrame,
        top_accounts_df: pd.DataFrame,
        shadow_df: pd.DataFrame,
        calib_df: pd.DataFrame,
    ) -> None:
        total_unknown = sum(1 for a in accounts if a.get("final_code") is None or a.get("method") == "unclassified")

        code_to_concept = {c["codigo"].upper(): c for c in self.conceptos}
        concept_by_code: dict[str, int] = {}
        for i, c in enumerate(self.conceptos):
            concept_by_code[c["codigo"].upper()] = i

        classified_by_code: Counter = Counter()
        classified_by_code_amount: Counter = Counter()
        companies_by_code: dict[str, set[str]] = defaultdict(set)
        freq_by_code: Counter = Counter()

        for a in accounts:
            fc = a.get("final_code")
            if fc and fc != "UNKNOWN":
                code = str(fc).upper().strip()
                classified_by_code[code] += 1
                amt = _safe_float(a.get("classification_amount", 0))
                classified_by_code_amount[code] += amt
                source = str(a.get("source_file", a.get("source_path", "")))
                companies_by_code[code].add(source)

        for a in accounts:
            fc = a.get("final_code")
            if fc and fc != "UNKNOWN":
                code = str(fc).upper().strip()
                freq_by_code[code] += 1

        cluster_by_code: Counter = Counter()
        cluster_freq_by_code: Counter = Counter()
        cluster_members_by_code: Counter = Counter()
        cluster_empresas_by_code: Counter = Counter()
        cluster_confidences: dict[str, list[float]] = defaultdict(list)
        cluster_suggested: Counter = Counter()

        if not clusters_df.empty and "suggested_concept" in clusters_df.columns:
            for _, row in clusters_df.iterrows():
                raw = str(row.get("suggested_concept", ""))
                code = self._normalize_code(raw)
                n_members = _safe_int(row.get("n_members", 1))
                freq = _safe_int(row.get("frecuencia", 0))
                n_emp = _safe_int(row.get("n_empresas", 0))
                conf = _safe_float(row.get("confidence", 0))
                if code:
                    cluster_by_code[code] += 1
                    cluster_freq_by_code[code] += freq
                    cluster_members_by_code[code] += n_members
                    cluster_empresas_by_code[code] += n_emp
                    cluster_confidences[code].append(conf)
                    cluster_suggested[raw] += 1

        shadow_by_code: Counter = Counter()
        shadow_cuenta_count: Counter = Counter()
        shadow_max_score: dict[str, float] = {}
        if not shadow_df.empty and "Código sugerido" in shadow_df.columns:
            for _, row in shadow_df.iterrows():
                code = str(row.get("Código sugerido", "")).upper().strip()
                score = _safe_float(row.get("Score", 0))
                if code:
                    shadow_by_code[code] += 1
                    shadow_cuenta_count[code] += 1
                    if code not in shadow_max_score or score > shadow_max_score[code]:
                        shadow_max_score[code] = score

        top_accounts_by_name: Counter = Counter()
        top_accounts_freq: Counter = Counter()
        if not top_accounts_df.empty and "cuenta" in top_accounts_df.columns:
            for _, row in top_accounts_df.iterrows():
                name = str(row.get("cuenta", "")).strip()
                if name:
                    top_accounts_by_name[name] += 1
                    top_accounts_freq[name] = _safe_int(row.get("frecuencia", 1))

        entries: list[dict] = []
        for c in self.conceptos:
            code = c["codigo"].upper()
            n_variants = len(c.get("variantes", []))
            n_sinonimos = len(c.get("sinonimos", []))
            n_ejemplos = len(c.get("ejemplos", []))

            classified_count = classified_by_code.get(code, 0)
            classified_amount = classified_by_code_amount.get(code, 0.0)
            n_empresas_distintas = len(companies_by_code.get(code, set()))
            frecuencia_total = freq_by_code.get(code, 0)

            n_clusters = cluster_by_code.get(code, 0)
            cluster_freq = cluster_freq_by_code.get(code, 0)
            cluster_members = cluster_members_by_code.get(code, 0)
            cluster_emp = cluster_empresas_by_code.get(code, 0)
            confs = cluster_confidences.get(code, [])
            avg_conf = round(sum(confs) / len(confs), 4) if confs else 0.0
            max_conf = max(confs) if confs else 0.0
            min_conf = min(confs) if confs else 0.0

            shadow_count = shadow_by_code.get(code, 0)

            total_knowledge = n_variants + n_sinonimos + n_ejemplos
            potential_recovery = cluster_members + shadow_count

            entries.append({
                "Código": code,
                "Nombre": c.get("nombre", ""),
                "Categoría": c.get("categoria", ""),
                "N° Variantes": n_variants,
                "N° Sinónimos": n_sinonimos,
                "N° Ejemplos": n_ejemplos,
                "Total Conocimiento": total_knowledge,
                "Empresas Distintas": n_empresas_distintas,
                "Frecuencia Total": frecuencia_total,
                "Monto Clasificado": classified_amount,
                "UNKNOWN Recuperables (Shadow)": shadow_count,
                "UNKNOWN Recuperables (Clusters)": cluster_members,
                "Recuperaciones Potenciales": potential_recovery,
                "N° Clusters": n_clusters,
                "Cluster Frecuencia": cluster_freq,
                "Cluster Empresas": cluster_emp,
                "Score Promedio": avg_conf,
                "Score Máximo": max_conf,
                "Score Mínimo": min_conf,
            })

        self.entries = entries
        self.total_unknown = total_unknown
        self._calc_indicators()
        self._detect_lists()
        self._answer_questions(cluster_freq_by_code, cluster_by_code, shadow_by_code, cluster_members_by_code)

    def _calc_indicators(self) -> None:
        entries = self.entries
        if not entries:
            return

        max_variants = max(e["N° Variantes"] for e in entries) or 1
        max_knowledge = max(e["Total Conocimiento"] for e in entries) or 1
        max_frecuencia = max(e["Frecuencia Total"] for e in entries) or 1
        max_empresas = max(e["Empresas Distintas"] for e in entries) or 1
        max_potential = max(e["Recuperaciones Potenciales"] for e in entries) or 1
        max_clusters = max(e["N° Clusters"] for e in entries) or 1

        for e in entries:
            nv = e["N° Variantes"]
            nk = e["Total Conocimiento"]
            freq = e["Frecuencia Total"]
            emp = e["Empresas Distintas"]
            pot = e["Recuperaciones Potenciales"]
            ns = e["N° Clusters"]

            coverage_score = min(100.0, round((ns / max_clusters) * 100, 1)) if ns > 0 else 0.0
            knowledge_density = round((nk / max_knowledge) * 100, 1) if nk > 0 else 0.0
            recovery_score = min(100.0, round((pot / (self.total_unknown or 1)) * 100, 1))
            ambiguity_score = round(max(0, 100 - min(100, (e.get("Score Promedio", 0) * 100))), 1)
            business_impact = round(
                (freq / (max_frecuencia or 1)) * 40
                + (emp / (max_empresas or 1)) * 35
                + (pot / (max_potential or 1)) * 25,
                1,
            )
            roi = round(business_impact / max(1, nv), 1)

            e["Coverage Score"] = coverage_score
            e["Knowledge Density"] = knowledge_density
            e["Recovery Score"] = recovery_score
            e["Ambiguity Score"] = ambiguity_score
            e["Business Impact"] = business_impact
            e["ROI Score"] = roi

    def _detect_lists(self) -> None:
        entries = self.entries
        if not entries:
            self.top10_roi = []
            self.top10_gaps = []
            self.top10_ambiguous = []
            self.top10_excess = []
            self.top10_split = []
            self.top10_newvariants = []
            self.top10_complete = []
            return

        sorted_roi = sorted(entries, key=lambda e: -e["ROI Score"])
        self.top10_roi = sorted_roi[:10]

        sorted_gaps = sorted(entries, key=lambda e: e["Coverage Score"])
        self.top10_gaps = [e for e in sorted_gaps if e["Nombre"]][:10]

        sorted_ambiguous = sorted(entries, key=lambda e: -e["Ambiguity Score"])
        self.top10_ambiguous = sorted_ambiguous[:10]

        sorted_excess = sorted(entries, key=lambda e: -(e["N° Variantes"] if e["N° Variantes"] > 10 else 0))
        self.top10_excess = sorted_excess[:10]

        sorted_split = sorted(entries, key=lambda e: -(e["N° Clusters"] if e["N° Clusters"] > 5 else 0))
        self.top10_split = sorted_split[:10]

        sorted_newvariants = sorted(
            entries, key=lambda e: -(e["UNKNOWN Recuperables (Clusters)"] + e["UNKNOWN Recuperables (Shadow)"])
        )
        self.top10_newvariants = sorted_newvariants[:10]

        sorted_complete = sorted(
            entries,
            key=lambda e: -((e["Coverage Score"] + e["Knowledge Density"] + e["Recovery Score"]) / 3),
        )
        self.top10_complete = sorted_complete[:10]

    def _answer_questions(
        self,
        cluster_freq_by_code: Counter,
        cluster_by_code: Counter,
        shadow_by_code: Counter,
        cluster_members_by_code: Counter,
    ) -> None:
        entries_sorted = sorted(self.entries, key=lambda e: -e["ROI Score"])
        self.answers: dict[str, Any] = {}

        top5_codes = [e["Código"] for e in entries_sorted[:5]]
        top10_codes = [e["Código"] for e in entries_sorted[:10]]
        top20_codes = [e["Código"] for e in entries_sorted[:20]]

        total_potential = sum(e["Recuperaciones Potenciales"] for e in self.entries) or 1
        total_unknown = self.total_unknown or 1

        top5_potential = sum(e["Recuperaciones Potenciales"] for e in entries_sorted[:5])
        top10_potential = sum(e["Recuperaciones Potenciales"] for e in entries_sorted[:10])
        top20_potential = sum(e["Recuperaciones Potenciales"] for e in entries_sorted[:20])

        self.answers["q1_most_profitable"] = [{"Código": e["Código"], "Nombre": e["Nombre"], "ROI Score": e["ROI Score"]} for e in entries_sorted[:10]]
        self.answers["q2_top5_pct"] = round(top5_potential / total_potential * 100, 1)
        self.answers["q3_top10_pct"] = round(top10_potential / total_potential * 100, 1)
        self.answers["q4_top20_pct"] = round(top20_potential / total_potential * 100, 1)

        disappearing_via_variants = sum(e["UNKNOWN Recuperables (Clusters)"] for e in self.entries)
        self.answers["q5_unknown_disappear_no_parser"] = disappearing_via_variants

        top10_current_variants = sum(e["N° Variantes"] for e in entries_sorted[:10])
        top10_cluster_members = sum(e["UNKNOWN Recuperables (Clusters)"] for e in entries_sorted[:10])
        self.answers["q6_double_variants_gain"] = {
            "current_variants": top10_current_variants,
            "estimated_new_recovery": round(top10_cluster_members * 0.6),
            "note": "Estimando 60% de recuperación si duplicamos variantes de Top 10",
        }

        max_variants = max(e["N° Variantes"] for e in self.entries) or 1
        avg_variants = sum(e["N° Variantes"] for e in self.entries) / len(self.entries) if self.entries else 0
        overrep = [e for e in self.entries if e["N° Variantes"] > avg_variants * 2 and e["Coverage Score"] > 80]
        underrep = [e for e in self.entries if e["N° Variantes"] < avg_variants * 0.5 and e["N° Clusters"] > 3]
        self.answers["q7_overrepresented"] = [
            {"Código": e["Código"], "Nombre": e["Nombre"], "N° Variantes": e["N° Variantes"], "Coverage Score": e["Coverage Score"]}
            for e in sorted(overrep, key=lambda x: -x["N° Variantes"])[:10]
        ]
        self.answers["q8_underrepresented"] = [
            {"Código": e["Código"], "Nombre": e["Nombre"], "N° Variantes": e["N° Variantes"], "N° Clusters": e["N° Clusters"]}
            for e in sorted(underrep, key=lambda x: -x["N° Clusters"])[:10]
        ]

        split_candidates = sorted(
            [e for e in self.entries if e["N° Clusters"] > 8],
            key=lambda x: -x["N° Clusters"],
        )[:10]
        self.answers["q9_split_candidates"] = [
            {"Código": e["Código"], "Nombre": e["Nombre"], "N° Clusters": e["N° Clusters"], "Variantes": e["N° Variantes"]}
            for e in split_candidates
        ]

        complete = [
            e for e in self.entries
            if e["Coverage Score"] >= 80 and e["Knowledge Density"] >= 80
        ]
        self.answers["q10_complete"] = [
            {"Código": e["Código"], "Nombre": e["Nombre"], "Coverage Score": e["Coverage Score"], "Knowledge Density": e["Knowledge Density"]}
            for e in sorted(complete, key=lambda x: -x["Coverage Score"])[:10]
        ]

    def generate_reports(self, output_dir: str | Path) -> dict[str, Path]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame(self.entries)

        # ── cmcc_audit.xlsx ──
        df.to_excel(out / "cmcc_audit.xlsx", index=False)

        # ── concept_statistics.xlsx ──
        stat_cols = [c for c in df.columns if c not in ("Categoría",)]
        df[stat_cols].to_excel(out / "concept_statistics.xlsx", index=False)

        # ── concept_heatmap.xlsx ──
        heat_cols = ["Código", "Nombre", "Coverage Score", "Knowledge Density",
                      "Recovery Score", "Ambiguity Score", "Business Impact", "ROI Score"]
        hm = df[heat_cols].copy()
        hm.to_excel(out / "concept_heatmap.xlsx", index=False)

        # ── coverage_curve.xlsx ──
        sorted_coverage = df.sort_values("Coverage Score", ascending=False)
        sorted_coverage["Acumulado"] = range(1, len(sorted_coverage) + 1)
        sorted_coverage["Pct"] = (sorted_coverage["Acumulado"] / len(sorted_coverage) * 100).round(1)
        sorted_coverage[["Código", "Nombre", "Coverage Score", "Acumulado", "Pct"]].to_excel(
            out / "coverage_curve.xlsx", index=False
        )

        # ── roi_matrix.xlsx ──
        roi_cols = ["Código", "Nombre", "Business Impact", "ROI Score",
                     "N° Variantes", "Recuperaciones Potenciales", "Coverage Score"]
        df[roi_cols].sort_values("ROI Score", ascending=False).to_excel(
            out / "roi_matrix.xlsx", index=False
        )

        # ── priority_backlog.xlsx ──
        priority = df.copy()
        priority["Prioridad"] = range(1, len(priority) + 1)
        priority.sort_values("ROI Score", ascending=False, inplace=True)
        priority.to_excel(out / "priority_backlog.xlsx", index=False)

        # ── top10_roi.xlsx ──
        pd.DataFrame(self.top10_roi).to_excel(out / "top10_roi.xlsx", index=False)

        # ── top10_gaps.xlsx ──
        pd.DataFrame(self.top10_gaps).to_excel(out / "top10_gaps.xlsx", index=False)

        # ── top10_complete.xlsx ──
        pd.DataFrame(self.top10_complete).to_excel(out / "top10_complete.xlsx", index=False)

        # ── concept_network.xlsx ──
        net_cols = ["Código", "Nombre", "Categoría", "N° Clusters", "N° Variantes",
                     "Recuperaciones Potenciales", "Business Impact", "ROI Score"]
        df[net_cols].to_excel(out / "concept_network.xlsx", index=False)

        # ── business_impact.xlsx ──
        impact_cols = ["Código", "Nombre", "Frecuencia Total", "Empresas Distintas",
                        "Monto Clasificado", "Recuperaciones Potenciales", "Business Impact", "ROI Score"]
        df[impact_cols].sort_values("Business Impact", ascending=False).to_excel(
            out / "business_impact.xlsx", index=False
        )

        # ── audit_statistics.json ──
        stats = self._build_statistics(df)
        with open(out / "audit_statistics.json", "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        # ── cmcc_audit.md ──
        self._generate_md_report(df, "cmcc_audit", out)

        # ── summary.md ──
        self._generate_summary(df, out)

        return {
            "cmcc_audit": out / "cmcc_audit.xlsx",
            "concept_statistics": out / "concept_statistics.xlsx",
            "concept_heatmap": out / "concept_heatmap.xlsx",
            "coverage_curve": out / "coverage_curve.xlsx",
            "roi_matrix": out / "roi_matrix.xlsx",
            "priority_backlog": out / "priority_backlog.xlsx",
            "top10_roi": out / "top10_roi.xlsx",
            "top10_gaps": out / "top10_gaps.xlsx",
            "top10_complete": out / "top10_complete.xlsx",
            "concept_network": out / "concept_network.xlsx",
            "business_impact": out / "business_impact.xlsx",
            "cmcc_audit_md": out / "cmcc_audit.md",
            "summary_md": out / "summary.md",
            "audit_statistics": out / "audit_statistics.json",
        }

    def _build_statistics(self, df: pd.DataFrame) -> dict:
        return {
            "total_concepts": len(df),
            "total_variants": int(df["N° Variantes"].sum()),
            "total_synonyms": int(df["N° Sinónimos"].sum()),
            "total_examples": int(df["N° Ejemplos"].sum()),
            "total_classified_frequency": int(df["Frecuencia Total"].sum()),
            "total_potential_recovery": int(df["Recuperaciones Potenciales"].sum()),
            "total_shadow": int(df["UNKNOWN Recuperables (Shadow)"].sum()),
            "total_clusters": int(df["N° Clusters"].sum()),
            "total_cluster_members": int(df["UNKNOWN Recuperables (Clusters)"].sum()),
            "total_unknown_in_audit": self.total_unknown,
            "avg_coverage_score": round(df["Coverage Score"].mean(), 1),
            "avg_knowledge_density": round(df["Knowledge Density"].mean(), 1),
            "avg_recovery_score": round(df["Recovery Score"].mean(), 1),
            "avg_ambiguity_score": round(df["Ambiguity Score"].mean(), 1),
            "avg_business_impact": round(df["Business Impact"].mean(), 1),
            "avg_roi_score": round(df["ROI Score"].mean(), 1),
            "max_roi": round(df["ROI Score"].max(), 1),
            "min_roi": round(df["ROI Score"].min(), 1),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "answers": self.answers,
        }

    def _generate_md_report(self, df: pd.DataFrame, name: str, out: Path) -> None:
        lines = ["# CMCC Coverage Audit", "",
                 f"Total conceptos analizados: **{len(df)}**", ""]
        if self.answers:
            lines.append("## Respuestas")
            lines.append("")
            a = self.answers
            lines.append(f"**1. Conceptos más rentables:**")
            for e in a.get("q1_most_profitable", [])[:5]:
                lines.append(f"- {e['Nombre']} ({e['Código']}) — ROI: {e['ROI Score']}")
            lines.append("")
            lines.append(f"**2. Top 5 concentración:** {a.get('q2_top5_pct', 0)}% del potencial de recuperación")
            lines.append(f"**3. Top 10 concentración:** {a.get('q3_top10_pct', 0)}%")
            lines.append(f"**4. Top 20 concentración:** {a.get('q4_top20_pct', 0)}%")
            lines.append("")
            lines.append(f"**5. UNKNOWN sin tocar parser:** {a.get('q5_unknown_disappear_no_parser', 0)}")
            q6 = a.get("q6_double_variants_gain", {})
            lines.append(f"**6. Duplicar variantes Top 10:** ~{q6.get('estimated_new_recovery', 0)} nuevas recuperaciones (desde {q6.get('current_variants', 0)} variantes actuales)")
            lines.append("")
            lines.append("**7. Sobrerrepresentados:**")
            for e in a.get("q7_overrepresented", [])[:5]:
                lines.append(f"- {e['Nombre']} ({e['Código']}) — {e['N° Variantes']} variantes, Coverage: {e['Coverage Score']}")
            lines.append("")
            lines.append("**8. Subrepresentados:**")
            for e in a.get("q8_underrepresented", [])[:5]:
                lines.append(f"- {e['Nombre']} ({e['Código']}) — solo {e['N° Variantes']} variantes, {e['N° Clusters']} clusters")
            lines.append("")
            lines.append("**9. Candidatos a dividir:**")
            for e in a.get("q9_split_candidates", [])[:5]:
                lines.append(f"- {e['Nombre']} ({e['Código']}) — {e['N° Clusters']} clusters, {e['Variantes']} variantes")
            lines.append("")
            lines.append("**10. Completos (no requieren trabajo):**")
            for e in a.get("q10_complete", [])[:5]:
                lines.append(f"- {e['Nombre']} ({e['Código']}) — Coverage: {e['Coverage Score']}, Knowledge: {e['Knowledge Density']}")
        lines.append("")
        lines.append("*Auditoría completada. Ningún archivo del pipeline fue modificado.*")
        (out / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")

    def _generate_summary(self, df: pd.DataFrame, out: Path) -> None:
        lines = ["# CMCC Audit — Resumen Ejecutivo", "",
                 f"**{len(df)} conceptos** | **{self.total_unknown:,} UNKNOWN** | "
                 f"**{int(df['Recuperaciones Potenciales'].sum()):,} recuperaciones potenciales**", "",
                 "## Indicadores Clave", "",
                 f"| Indicador | Promedio |",
                 f"|---|---|",
                 f"| Coverage Score | {df['Coverage Score'].mean():.1f} |",
                 f"| Knowledge Density | {df['Knowledge Density'].mean():.1f} |",
                 f"| Recovery Score | {df['Recovery Score'].mean():.1f} |",
                 f"| Ambiguity Score | {df['Ambiguity Score'].mean():.1f} |",
                 f"| Business Impact | {df['Business Impact'].mean():.1f} |",
                 f"| ROI Score | {df['ROI Score'].mean():.1f} |", "",
                 "## Matriz Concepto → Variantes → Frecuencia → UNKNOWN → Recuperables → ROI → Prioridad", "",
                 "| Concepto | Variantes | Frecuencia | UNKNOWN Recup. | ROI | Prioridad |",
                 "|---|---|---|---|---|---|"]
        top10 = sorted(self.entries, key=lambda e: -e.get("ROI Score", 0))[:10]
        for i, e in enumerate(top10, 1):
            lines.append(
                f"| {e['Nombre'][:40]} | {e['N° Variantes']} | {e['Frecuencia Total']} | "
                f"{e['Recuperaciones Potenciales']} | {e['ROI Score']} | {i} |"
            )
        lines.append("")
        lines.append("## Archivos generados")
        lines.append("")
        lines.append("| Archivo | Descripción |")
        lines.append("|---|---|")
        lines.append("| `cmcc_audit.xlsx` | Auditoría completa de los 52 conceptos |")
        lines.append("| `concept_statistics.xlsx` | Estadísticas detalladas por concepto |")
        lines.append("| `concept_heatmap.xlsx` | Matriz de indicadores compuestos |")
        lines.append("| `coverage_curve.xlsx` | Curva de cobertura acumulada |")
        lines.append("| `roi_matrix.xlsx` | ROI por concepto |")
        lines.append("| `priority_backlog.xlsx` | Backlog ordenado por prioridad |")
        lines.append("| `top10_roi.xlsx` | Top 10 mayor retorno |")
        lines.append("| `top10_gaps.xlsx` | Top 10 brechas de cobertura |")
        lines.append("| `top10_complete.xlsx` | Top 10 conceptos completos |")
        lines.append("| `concept_network.xlsx` | Red de conceptos |")
        lines.append("| `business_impact.xlsx` | Impacto de negocio por concepto |")
        lines.append("| `cmcc_audit.md` | Informe completo con respuestas |")
        lines.append("| `summary.md` | Este resumen ejecutivo |")
        lines.append("| `audit_statistics.json` | Estadísticas completas en JSON |")
        lines.append("")
        lines.append("*Modo análisis — nada fue modificado.*")
        (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
