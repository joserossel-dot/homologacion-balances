#!/usr/bin/env python3
"""Run Knowledge Evolution & Impact Analysis — simulate changes in shadow mode."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge_evolution.knowledge_snapshot import KnowledgeSnapshot
from knowledge_evolution.impact_analyzer import ImpactAnalyzer
from knowledge_evolution.evolution_report import EvolutionReport


def main():
    snapshot = KnowledgeSnapshot()
    data = snapshot.capture()
    print(f"Snapshot: {data['concept_count']} concepts, {data['variant_count']} variants, "
          f"{data['statistics']['total_unknown']} UNKNOWN")

    analyzer = ImpactAnalyzer(data)

    new_variants = {
        "AC.01": ["caja general", "banco estado cta cte", "caja 1", "caja 2",
                   "efectivo en caja", "depositos bancarios", "saldo bancario"],
        "ER.01": ["ingresos operacionales", "ingresos brutos", "ventas netas",
                   "ingresos por ventas", "ingresos de explotacion"],
        "PC.01": ["proveedores nacionales", "proveedores del exterior",
                   "acreedores comerciales", "cuentas por pagar comerciales"],
        "ER.04": ["gastos administrativos", "gastos generales", "gastos de oficina",
                   "gastos de administracion y ventas"],
        "ANC.01": ["activo fijo neto", "propiedades planta", "equipos",
                    "maquinarias y equipos", "instalaciones"],
    }

    impact = analyzer.simulate_bulk(new_variants)
    diff = {"diff_summary": impact.get("diff_summary", {})}

    print(f"\nSimulation Results:")
    print(f"  Variants added: {sum(len(v) for v in new_variants.values())}")
    print(f"  New accounts classified: {impact['total_new_accounts']}")
    print(f"  New companies impacted: {impact['total_new_companies']}")

    report = EvolutionReport(data, impact, diff)

    output_dir = "reports/knowledge_evolution"

    files = [
        ("knowledge_timeline.xlsx", report.generate_timeline_xlsx(f"{output_dir}/knowledge_timeline.xlsx")),
        ("knowledge_changes.xlsx", report.generate_changes_xlsx(f"{output_dir}/knowledge_changes.xlsx")),
        ("impact_summary.xlsx", report.generate_impact_summary_xlsx(f"{output_dir}/impact_summary.xlsx")),
        ("concept_growth.xlsx", report.generate_concept_growth_xlsx(f"{output_dir}/concept_growth.xlsx")),
        ("knowledge_diff.xlsx", report.generate_knowledge_diff_xlsx(f"{output_dir}/knowledge_diff.xlsx")),
        ("knowledge_evolution.md", report.generate_markdown(f"{output_dir}/knowledge_evolution.md")),
        ("knowledge_statistics.json", report.generate_statistics_json(f"{output_dir}/knowledge_statistics.json")),
    ]

    print(f"\nAll outputs generated in {output_dir}/")
    for name, path in files:
        size = path.stat().st_size
        print(f"  {name}: {size:,} bytes")

    print("\nDone.")


if __name__ == "__main__":
    main()
