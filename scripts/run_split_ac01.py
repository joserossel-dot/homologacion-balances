from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from split_ac01.split_engine import AC01SplitEngine, load_ac01_variants
from split_ac01.split_reports import generate_reports, REPORTS_DIR


def main():
    print("=" * 60)
    print("SPRINT 27.4 — Split AC.01")
    print("=" * 60)

    print("\nCargando variantes de AC.01 desde knowledge/cmcc.json ...")
    variants = load_ac01_variants()
    print(f"  → {len(variants)} variantes cargadas")

    print("\nClasificando variantes con reglas léxicas ...")
    engine = AC01SplitEngine()
    results = engine.classify_all(variants)
    statistics = engine.compute_statistics(results)
    coverage = engine.compute_coverage(results)

    print(f"\n  Resultados:")
    print(f"    Auto-clasificadas: {statistics['auto_classified']} ({statistics['auto_classification_rate']}%)")
    print(f"    Revisión necesaria: {statistics['needs_review']}")
    print(f"\n  Distribución:")
    for code in ["AC.01.01", "AC.01.02", "AC.01.03"]:
        count = statistics["by_concept"].get(code, 0)
        print(f"    {code}: {count}")
    unk = statistics["by_concept"].get("UNCLASSIFIED", 0)
    if unk:
        print(f"    Sin clasificar: {unk}")

    print(f"\nGenerando reportes en {REPORTS_DIR} ...")
    paths = generate_reports(results, statistics, coverage)

    print(f"\n  Reportes generados:")
    for name, path in sorted(paths.items()):
        print(f"    {name}: {path}")

    print("\n" + "=" * 60)
    print("SPRINT 27.4 COMPLETADO")
    print("=" * 60)


if __name__ == "__main__":
    main()
