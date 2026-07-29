#!/usr/bin/env python3
"""
Sprint 20 — Structure Truth Analyzer (STA)
Runs full analysis on BIV results from Sprint 19.
"""
import sys, json, sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validation.balance_validator import BalanceValidator
from analysis.structure_truth_analyzer import StructureTruthAnalyzer


def select_balances(folder: str | Path, count: int = 20) -> list[Path]:
    folder = Path(folder)
    pdfs = sorted(folder.glob("*.pdf"))
    pdfs.sort(key=lambda f: f.stat().st_size)
    return pdfs[:count]


def load_sprint_cache() -> dict:
    cache_path = Path("reports/sprint18_cache.json")
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    return {}


def main():
    project_root = Path(__file__).resolve().parent.parent
    holdout_dir = project_root / "datasets" / "HOLDOUT"
    training_dir = project_root / "datasets" / "TRAINING"

    print("=" * 60)
    print("SPRINT 20 — Structure Truth Analyzer (STA)")
    print("=" * 60)

    sprint_cache = load_sprint_cache()
    print(f"Loaded Sprint 18 cache: {len(sprint_cache)} entries")

    holdout_files = select_balances(holdout_dir, count=20)
    training_files = select_balances(training_dir, count=20)
    all_files = holdout_files + training_files
    print(f"Selected {len(all_files)} files for analysis")

    biv_results = []
    validator = BalanceValidator(tolerance_pct=1.0)

    for f in all_files:
        try:
            meta = sprint_cache.get(f.name, {})
            result = validator._process_single_file(f)
            result.format_family = meta.get("format_family", "UNKNOWN")
            result.pages = meta.get("pages", 0)
            biv_results.append(result)
            n_errors = sum(1 for sr in result.subtotal_results if not sr.passed)
            print(f"  BIV: {f.name[:50]:50s} errors={n_errors:4d} score={result.integrity_score.overall:.1f}")
        except Exception as e:
            print(f"  ERROR: {f.name}: {e}")

    print(f"\nBIV processed: {len(biv_results)} files")
    total_errors = sum(sum(1 for sr in r.subtotal_results if not sr.passed) for r in biv_results)
    print(f"Total subtotal errors to analyze: {total_errors}")

    print("\nBuilding traces and classifying root causes...")
    analyzer = StructureTruthAnalyzer()

    gold_records = analyzer.load_gold_standard()
    kb_variants = analyzer.load_kb_variants()
    print(f"Gold standard: {len(gold_records)} records")
    print(f"KB variants: {len(kb_variants)}")

    all_accounts_cache: dict[str, list[dict]] = {}

    for result in biv_results:
        accounts = []
        if result.hierarchy_tree:
            for node in result.hierarchy_tree.all_nodes:
                accounts.append({
                    "nombre": node.account_name,
                    "amount": node.amount,
                    "codigo": node.account_code,
                    "linea": node.line_number,
                    "es_total": node.es_total,
                })
        all_accounts_cache[result.source_file] = accounts

        causes = analyzer.analyze_validation_result(
            result,
            format_family=result.format_family,
            all_accounts=accounts,
        )
        print(f"  STA: {result.source_file[:50]:50s} causes={len(causes)}")

    cause_dist = analyzer.stats.cause_distribution()
    print(f"\n{'='*60}")
    print("ROOT CAUSE DISTRIBUTION")
    print(f"{'='*60}")
    for cause, count in cause_dist.items():
        pct = round(count / max(analyzer.stats.total_differences, 1) * 100, 1)
        bar = "#" * max(1, int(pct / 2))
        print(f"  {cause:25s} {count:5d} ({pct:5.1f}%) {bar}")

    print(f"\n{'='*60}")
    print("FORMAT DISTRIBUTION")
    print(f"{'='*60}")
    for fm in analyzer.stats.cause_by_format_matrix():
        print(f"  {fm.format_name:25s} {fm.total_differences:5d} diffs")
        for cause, count in sorted(fm.by_cause.items()):
            print(f"    {cause:25s} {count}")

    impact = analyzer.stats.calculate_impact_potential()
    print(f"\n{'='*60}")
    print("IMPACT POTENTIAL")
    print(f"{'='*60}")
    labels = {
        "parser_improvement": "Parser improvement",
        "hierarchy_improvement": "Hierarchy improvement",
        "dictionary_improvement": "Dictionary improvement",
        "knowledge_base_improvement": "Knowledge Base improvement",
        "human_review": "Human review",
    }
    for key, label in labels.items():
        data = impact.get(key, {})
        print(f"  {label:30s} {data.get('count', 0):5d} ({data.get('pct', 0):5.1f}%)")

    patterns = analyzer.stats.find_patterns(top_n=20)
    print(f"\n{'='*60}")
    print("TOP 20 PATTERNS (by subtotal)")
    print(f"{'='*60}")
    for i, p in enumerate(patterns, 1):
        print(f"  {i:2d}. {p.account_name[:50]:50s} freq={p.frequency:2d} avg_diff={p.avg_difference:>10,.0f} cause={p.typical_cause}")

    conflictive = analyzer.stats.find_conflictive_accounts(top_n=20)
    print(f"\n{'='*60}")
    print("TOP 20 CONFLICTIVE ACCOUNTS")
    print(f"{'='*60}")
    for i, a in enumerate(conflictive, 1):
        print(f"  {i:2d}. {a.account_name[:50]:50s} freq={a.frequency:2d} avg_diff={a.avg_difference:>10,.0f} cause={a.typical_cause}")

    print(f"\nGenerating reports...")
    analyzer.generate_report_section(
        output_path=project_root / "reports" / "structure_truth_report.md",
        json_path=project_root / "reports" / "structure_truth.json",
    )

    print(f"\n{'='*60}")
    print("DELIVERABLES")
    print(f"{'='*60}")
    print(f"  reports/structure_truth_report.md")
    print(f"  reports/structure_truth.json")
    print(f"  analysis/ (5 files)")
    print(f"")
    print(f"  Differences analyzed: {analyzer.stats.total_differences}")
    print(f"  Root cause categories: {len(cause_dist)}")
    print(f"  Format matrices: {len(analyzer.stats.cause_by_format_matrix())}")
    print(f"  Top patterns: {len(patterns)}")
    print(f"  Top conflictive accounts: {len(conflictive)}")


if __name__ == "__main__":
    main()
