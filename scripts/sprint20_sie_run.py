#!/usr/bin/env python3
"""
Sprint 20 — Structural Intelligence Engine (SIE)
Builds structural trees from all balances, generates templates,
detects families, and produces reports.
"""
import sys, json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structure_engine.tree_builder import TreeBuilder
from structure_engine.template_builder import TemplateBuilder
from structure_engine.template_matcher import TemplateMatcher
from structure_engine.template_repository import TemplateRepository
from structure_engine.family_detector import FamilyDetector
from structure_engine.statistics import StructureStatistics
from structure_engine.structure_detector import StructureDetector

from parser_universal import ParserPDF


def process_file(pdf_path: Path) -> list[dict]:
    parser = ParserPDF()
    raw = parser.parsear(pdf_path)
    accounts = []
    for c in raw.cuentas:
        accounts.append({
            "linea": c.linea,
            "codigo": c.codigo or "",
            "nombre": c.nombre,
            "monto": c.monto or 0.0,
            "origen_columna": c.origen_columna.value if hasattr(c.origen_columna, "value") else str(c.origen_columna),
            "es_total": c.es_total,
        })
    return accounts


def select_files(folder: str | Path, count: int = 40) -> list[Path]:
    folder = Path(folder)
    pdfs = sorted(folder.glob("*.pdf"))
    pdfs.sort(key=lambda f: f.stat().st_size)
    return pdfs[:count]


def main():
    project_root = Path(__file__).resolve().parent.parent
    holdout_dir = project_root / "datasets" / "HOLDOUT"
    training_dir = project_root / "datasets" / "TRAINING"
    report_dir = project_root / "reports"
    repo_path = project_root / "structure_repository.json"

    print("=" * 60)
    print("SPRINT 20 — Structural Intelligence Engine (SIE)")
    print("=" * 60)

    holdout_files = select_files(holdout_dir, count=30)
    training_files = select_files(training_dir, count=30)
    all_files = holdout_files + training_files
    print(f"Processing {len(all_files)} files ({len(holdout_files)} HOLDOUT + {len(training_files)} TRAINING)")

    builder = TreeBuilder()
    template_builder = TemplateBuilder()
    detector = StructureDetector()
    repo = TemplateRepository(str(repo_path))

    initial_templates = []
    trees = []
    all_patterns: Counter = Counter()

    for f in all_files:
        try:
            accounts = process_file(f)
            tree = builder.build_tree(accounts, source_file=f.name)
            trees.append(tree)

            template = template_builder.build_template(tree, file_name=f.name)
            initial_templates.append(template)

            patterns = detector.find_repeated_patterns(tree.type_sequence)
            for pat, cnt in patterns:
                all_patterns[pat] += cnt

            print(f"  tree={f.name[:45]:45s} depth={tree.max_depth} nodes={tree.total_nodes:4d} "
                  f"sections={tree.section_count} seq={tree.type_sequence[:30]}")
        except Exception as e:
            print(f"  ERROR: {f.name}: {e}")

    print(f"\nBuilt {len(trees)} trees, {len(initial_templates)} initial templates")

    cluster_threshold = 0.70
    clustered = 0
    for template in initial_templates:
        merged = False
        for existing in repo.templates:
            sim = template_builder.templates_similar(template, existing)
            if sim >= cluster_threshold:
                merged_t = template_builder.merge_templates(existing, template)
                repo.templates.remove(existing)
                repo.templates.append(merged_t)
                merged = True
                clustered += 1
                break
        if not merged:
            repo.add_template(template)

    print(f"Clustered {clustered} templates into {repo.total_templates} unique")

    fam_detector = FamilyDetector()
    for t in repo.templates:
        fam_detector.classify(t)
    families = fam_detector.build_families(repo.templates)
    repo.set_families(families)

    repo.save()
    print(f"Repository saved: {repo_path}")

    matcher = TemplateMatcher(repo.templates)
    match_stats = {"matched": 0, "unmatched": 0, "avg_similarity": 0.0}
    similarities = []
    for tree in trees:
        match = matcher.best_match(tree, min_similarity=0.3)
        if match:
            match_stats["matched"] += 1
            similarities.append(match.similarity)
        else:
            match_stats["unmatched"] += 1
    match_stats["avg_similarity"] = round(sum(similarities) / max(len(similarities), 1), 1)

    stats = StructureStatistics()
    tree_stats = stats.tree_stats(trees)
    template_stats = stats.template_stats(repo.templates)
    family_stats = stats.family_stats(families, trees)

    top_patterns = all_patterns.most_common(20)

    report_dir.mkdir(parents=True, exist_ok=True)

    stats_report = stats.generate_markdown_report(tree_stats, template_stats, family_stats, top_patterns)
    (report_dir / "structure_templates.md").write_text(stats_report, encoding="utf-8")

    repo_report_lines = []
    repo_report_lines.append("# Structure Template Repository")
    repo_report_lines.append("")
    repo_report_lines.append(f"Total templates: {repo.total_templates}")
    repo_report_lines.append(f"Total files: {repo.total_files}")
    repo_report_lines.append(f"Total families: {len(families)}")
    repo_report_lines.append("")
    repo_report_lines.append("## Templates")
    repo_report_lines.append("")
    repo_report_lines.append("| ID | Family | Nodes | Depth | Sections | Format | Freq | Example |")
    repo_report_lines.append("|-----|--------|-------|-------|----------|--------|------|---------|")
    for t in sorted(repo.templates, key=lambda x: -x.frequency):
        ex = t.example_files[0][:30] if t.example_files else ""
        repo_report_lines.append(
            f"| {t.template_id[:10]} | {t.family[:20]} | {t.total_nodes} | {t.max_depth} "
            f"| {t.section_count} | {t.code_format[:12]} | {t.frequency} | {ex} |"
        )
    repo_report_lines.append("")
    repo_report_lines.append("## Families")
    repo_report_lines.append("")
    repo_report_lines.append("| Family | Templates | Files | Avg Depth | Common Pattern |")
    repo_report_lines.append("|--------|-----------|-------|-----------|----------------|")
    for f in families:
        repo_report_lines.append(
            f"| {f.name} | {len(f.templates)} | {f.total_members} | {f.avg_depth} | {f.common_pattern[:40]} |"
        )
    repo_report_lines.append("")
    (report_dir / "template_repository.md").write_text("\n".join(repo_report_lines), encoding="utf-8")

    print(f"\n{'='*60}")
    print("DELIVERABLES")
    print(f"{'='*60}")
    print(f"  Files processed: {len(trees)}")
    print(f"  Templates generated: {repo.total_templates}")
    print(f"  Families detected: {len(families)}")
    print(f"  Template coverage: {match_stats['matched']}/{len(trees)} "
          f"({round(match_stats['matched']/max(len(trees),1)*100, 1)}%)")
    print(f"  Avg match similarity: {match_stats['avg_similarity']}%")
    print(f"")
    print(f"  Family breakdown:")
    for f in families:
        print(f"    {f.name:22s} {f.total_members:4d} files, {len(f.templates):3d} templates, "
              f"depth={f.avg_depth}")
    print(f"")
    print(f"  Reports:")
    print(f"    reports/structure_templates.md")
    print(f"    reports/template_repository.md")
    print(f"    structure_repository.json")
    print(f"")
    print(f"  Avg depth: {tree_stats.get('avg_depth', 0)}")
    print(f"  Avg nodes: {tree_stats.get('avg_nodes', 0)}")
    print(f"  Code formats: {tree_stats.get('code_format_dist', {})}")


if __name__ == "__main__":
    main()
