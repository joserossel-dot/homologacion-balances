"""FASE 19A — Variant Discovery Engine: find variant clusters in UNKNOWN accounts."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge.variant_discovery.engine import VariantDiscoveryEngine
from knowledge.variant_discovery.reports import generate_reports

OUTPUT_DIR = Path("reports/variant_discovery")
VALIDATION_UNCLASSIFIED = Path("reports/validation_after/20260707_220654/unclassified.xlsx")
CMCC_SHADOW = Path("reports/cmcc_shadow/cmcc_shadow.xlsx")
CMCC_PATH = Path("knowledge/cmcc.json")


def main():
    print("=" * 60)
    print("FASE 19A — Variant Discovery Engine")
    print("=" * 60)

    engine = VariantDiscoveryEngine(cmcc_path=CMCC_PATH, threshold=0.60)

    if VALIDATION_UNCLASSIFIED.exists():
        print(f"Loading UNKNOWN from {VALIDATION_UNCLASSIFIED}...")
        engine.load_unclassified(VALIDATION_UNCLASSIFIED)
        print(f"  {len(engine.accounts)} accounts loaded")

    if CMCC_SHADOW.exists():
        print(f"Loading CMCC shadow data from {CMCC_SHADOW}...")
        engine.load_cmcc_shadow(CMCC_SHADOW)
        print(f"  {len(engine.accounts)} total accounts after shadow")

    result = engine.run()

    print(f"\nGenerating reports in {OUTPUT_DIR}...")
    paths = generate_reports(result, OUTPUT_DIR)

    print(f"\nResults:")
    print(f"  Total accounts analyzed: {result['total_accounts']:,}")
    print(f"  Clusters formed:         {result['total_clusters']:,}")
    print(f"  Multi-member clusters:   {result['multi_clusters']:,}")
    print(f"  Singletons:              {result['singleton_count']:,}")
    print(f"  High confidence (≥0.70): {result['high_confidence_count']:,}")
    print(f"  Needs review:            {result['needs_review_count']:,}")

    print(f"\nGenerated files:")
    for name, p in paths.items():
        sz = p.stat().st_size
        print(f"  {name}: {p} ({sz:,} bytes)")
    md_path = OUTPUT_DIR / "clusters.md"
    if md_path.exists():
        print(f"  clusters.md: {md_path} ({md_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
