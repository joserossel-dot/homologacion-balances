from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd


class CMCCValidator:
    def __init__(self, high_confidence_path: str | Path,
                 concept_suggestions_path: str | Path,
                 cmcc_path: str | Path = "knowledge/cmcc.json"):
        self.hc_path = Path(high_confidence_path)
        self.cs_path = Path(concept_suggestions_path)
        self.cmcc_path = Path(cmcc_path)
        self.entries: list[dict[str, Any]] = []

    def load(self) -> None:
        hc = pd.read_excel(self.hc_path)
        cs = pd.read_excel(self.cs_path)

        cs_map: dict[str, dict] = {}
        for _, row in cs.iterrows():
            cs_map[str(row["id"])] = {
                "members_sample": str(row.get("members_sample", "")),
                "n_suggestions": int(row.get("n_members", 0)),
            }

        for _, row in hc.iterrows():
            cid = str(row["id"])
            members_str = str(row.get("members", ""))
            freq = int(row.get("frecuencia", 0))
            n_emp = int(row.get("n_empresas", 0))
            conf = float(row.get("confidence", 0))
            concept = str(row.get("suggested_concept", ""))
            monto = float(row.get("monto_acumulado", 0))
            nm = int(row.get("n_members", 0))

            variants = [v.strip() for v in members_str.split("|") if v.strip()]
            impact = round(freq * max(n_emp, 1) * conf, 2)

            code = ""
            if " — " in concept:
                parts = concept.split(" — ", 1)
                code = parts[0].strip()

            extra = cs_map.get(cid, {})
            members_sample = extra.get("members_sample", " | ".join(variants[:5]))

            self.entries.append({
                "Cluster ID": cid,
                "Concepto sugerido": concept,
                "Código sugerido": code,
                "Confianza": conf,
                "Impacto": impact,
                "Frecuencia": freq,
                "Empresas": n_emp,
                "Miembros": nm,
                "Variantes detectadas": "\n".join(variants[:15]) if variants else "",
                "Muestra variantes": members_sample[:200] if members_sample else "",
                "Monto acumulado": monto,
                "Decisión": "",
                "Código definitivo": "",
            })

        self.entries.sort(key=lambda x: -x["Impacto"])

    @property
    def total_entries(self) -> int:
        return len(self.entries)

    def top_n(self, n: int) -> list[dict[str, Any]]:
        return self.entries[:n]

    def generate_reports(self, output_dir: str | Path) -> dict[str, Path]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame(self.entries)

        # ── review_package.xlsx ──
        df.to_excel(out / "review_package.xlsx", index=False)

        # ── top100.xlsx ──
        df.head(100).to_excel(out / "top100.xlsx", index=False)

        # ── top200.xlsx ──
        df.head(200).to_excel(out / "top200.xlsx", index=False)

        # ── top400.xlsx ──
        df.head(400).to_excel(out / "top400.xlsx", index=False)

        # ── validation_statistics.json ──
        concept_counts: Counter = Counter()
        code_counts: Counter = Counter()
        impact_buckets: Counter = Counter()
        confidence_buckets: Counter = Counter()

        for e in self.entries:
            concept_counts[e["Concepto sugerido"]] += 1
            code_counts[e["Código sugerido"]] += 1
            imp = e["Impacto"]
            if imp >= 100:
                impact_buckets["100+"] += 1
            elif imp >= 50:
                impact_buckets["50-99"] += 1
            elif imp >= 20:
                impact_buckets["20-49"] += 1
            elif imp >= 10:
                impact_buckets["10-19"] += 1
            else:
                impact_buckets["0-9"] += 1
            c = e["Confianza"]
            if c >= 0.95:
                confidence_buckets["0.95-1.0"] += 1
            elif c >= 0.90:
                confidence_buckets["0.90-0.94"] += 1
            elif c >= 0.80:
                confidence_buckets["0.80-0.89"] += 1
            else:
                confidence_buckets["<0.80"] += 1

        stats = {
            "total_entries": self.total_entries,
            "total_high_confidence": len(self.entries),
            "impact_distribution": dict(impact_buckets),
            "confidence_distribution": dict(confidence_buckets),
            "top_codes": code_counts.most_common(30),
            "top_concepts": concept_counts.most_common(30),
            "max_impact": max(e["Impacto"] for e in self.entries) if self.entries else 0,
            "min_impact": min(e["Impacto"] for e in self.entries) if self.entries else 0,
            "avg_impact": round(
                sum(e["Impacto"] for e in self.entries) / len(self.entries), 2
            ) if self.entries else 0,
            "total_variants": sum(e["Miembros"] for e in self.entries),
            "total_frequency": sum(e["Frecuencia"] for e in self.entries),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        stats_path = out / "validation_statistics.json"
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        # ── review_summary.md ──
        self._generate_summary(stats, out)

        return {
            "review_package": out / "review_package.xlsx",
            "top100": out / "top100.xlsx",
            "top200": out / "top200.xlsx",
            "top400": out / "top400.xlsx",
            "validation_statistics": stats_path,
            "review_summary": out / "review_summary.md",
        }

    def _generate_summary(self, stats: dict, out: Path) -> None:
        lines = []
        lines.append("# CMCC Validation Package — Review Summary")
        lines.append("")
        lines.append(f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("")
        lines.append("## Resumen")
        lines.append("")
        lines.append(f"| Métrica | Valor |")
        lines.append(f"|---|---|")
        lines.append(f"| Clusters a validar | {stats['total_entries']:,} |")
        lines.append(f"| Variantes totales | {stats['total_variants']:,} |")
        lines.append(f"| Frecuencia total | {stats['total_frequency']:,} |")
        lines.append(f"| Impacto máximo | {stats['max_impact']:.1f} |")
        lines.append(f"| Impacto mínimo | {stats['min_impact']:.1f} |")
        lines.append(f"| Impacto promedio | {stats['avg_impact']} |")
        lines.append("")
        lines.append("## Cómo usar este paquete")
        lines.append("")
        lines.append("1. Abrir `review_package.xlsx`")
        lines.append("2. Para cada fila, revisar las variantes detectadas")
        lines.append("3. Decidir: **Aprobar** (dejar vacío), **Corregir** (cambiar código), o **Rechazar** (marcar como rechazado)")
        lines.append("4. Si se corrige, escribir el código definitivo en la columna `Código definitivo`")
        lines.append("5. Una vez completado, el archivo servirá como entrada para la incorporación masiva al CMCC")
        lines.append("")

        lines.append("## Distribución por Impacto")
        lines.append("")
        lines.append("| Rango de impacto | Clusters |")
        lines.append("|---|---|")
        for label in ["100+", "50-99", "20-49", "10-19", "0-9"]:
            cnt = stats["impact_distribution"].get(label, 0)
            if cnt > 0:
                lines.append(f"| {label} | {cnt:,} |")
        lines.append("")

        lines.append("## Distribución por Confianza")
        lines.append("")
        lines.append("| Rango de confianza | Clusters |")
        lines.append("|---|---|")
        for label in ["0.95-1.0", "0.90-0.94", "0.80-0.89", "<0.80"]:
            cnt = stats["confidence_distribution"].get(label, 0)
            if cnt > 0:
                lines.append(f"| {label} | {cnt:,} |")
        lines.append("")

        lines.append("## Top 10 Códigos sugeridos")
        lines.append("")
        lines.append("| # | Código | Clusters |")
        lines.append("|---|---|---|")
        for idx, (code, cnt) in enumerate(stats["top_codes"][:10], 1):
            if code:
                lines.append(f"| {idx} | {code} | {cnt:,} |")
        lines.append("")

        lines.append("## Top 10 Conceptos sugeridos")
        lines.append("")
        lines.append("| # | Concepto | Clusters |")
        lines.append("|---|---|---|")
        for idx, (concept, cnt) in enumerate(stats["top_concepts"][:10], 1):
            lines.append(f"| {idx} | {concept[:80]} | {cnt:,} |")
        lines.append("")

        top5 = self.entries[:5] if self.entries else []
        if top5:
            lines.append("## Top 5 clusters por impacto")
            lines.append("")
            for i, e in enumerate(top5, 1):
                lines.append(f"### {i}. {e['Cluster ID']} — {e['Concepto sugerido']}")
                lines.append(f"- Impacto: {e['Impacto']} | Confianza: {e['Confianza']} | "
                             f"Frecuencia: {e['Frecuencia']} | Empresas: {e['Empresas']}")
                lines.append(f"- Variantes ({e['Miembros']}):")
                for v in e["Variantes detectadas"].split("\n")[:5]:
                    lines.append(f"  - {v[:100]}")
                lines.append("")

        lines.append("*Ningún archivo del pipeline fue modificado. Modo revisión únicamente.*")
        lines.append("")

        (out / "review_summary.md").write_text("\n".join(lines), encoding="utf-8")
