from __future__ import annotations
from collections import Counter
from .structure_models import StructuralTree, StructureTemplate, StructuralFamily


class StructureStatistics:

    @staticmethod
    def tree_stats(trees: list[StructuralTree]) -> dict:
        if not trees:
            return {}
        return {
            "total_trees": len(trees),
            "avg_depth": round(sum(t.max_depth for t in trees) / len(trees), 1),
            "avg_nodes": round(sum(t.total_nodes for t in trees) / len(trees), 1),
            "avg_subtotals": round(sum(t.subtotal_count for t in trees) / len(trees), 1),
            "avg_sections": round(sum(t.section_count for t in trees) / len(trees), 1),
            "max_depth": max(t.max_depth for t in trees),
            "min_depth": min(t.max_depth for t in trees),
            "code_format_dist": dict(Counter(t.code_format for t in trees).most_common()),
            "column_layout_dist": dict(Counter(t.column_layout for t in trees).most_common()),
            "type_complexity": {
                "high_section": sum(1 for t in trees if t.section_count >= 4),
                "medium_section": sum(1 for t in trees if 2 <= t.section_count < 4),
                "low_section": sum(1 for t in trees if t.section_count < 2),
                "flat": sum(1 for t in trees if t.max_depth <= 1),
                "deep": sum(1 for t in trees if t.max_depth >= 3),
            },
        }

    @staticmethod
    def template_stats(templates: list[StructureTemplate]) -> dict:
        if not templates:
            return {}
        total = sum(t.frequency for t in templates)
        return {
            "total_templates": len(templates),
            "total_files": total,
            "avg_frequency": round(total / len(templates), 1),
            "family_dist": dict(Counter(t.family for t in templates).most_common()),
            "code_format_dist": dict(Counter(t.code_format for t in templates).most_common()),
            "avg_depth": round(sum(t.max_depth for t in templates) / len(templates), 1),
            "avg_nodes": round(sum(t.total_nodes for t in templates) / len(templates), 1),
            "by_complexity": {
                "simple": sum(1 for t in templates if t.total_nodes <= 20),
                "medium": sum(1 for t in templates if 20 < t.total_nodes <= 100),
                "complex": sum(1 for t in templates if t.total_nodes > 100),
            },
        }

    @staticmethod
    def family_stats(families: list[StructuralFamily], trees: list[StructuralTree]) -> dict:
        if not families:
            return {}
        return {
            "total_families": len(families),
            "largest": max(f.total_members for f in families) if families else 0,
            "smallest": min(f.total_members for f in families) if families else 0,
            "family_sizes": {f.name: f.total_members for f in families},
            "coverage_pct": {
                f.name: round(f.total_members / max(len(trees), 1) * 100, 1)
                for f in families
            },
        }

    @staticmethod
    def generate_markdown_report(
        tree_stats: dict,
        template_stats: dict,
        family_stats: dict,
        patterns: list[tuple[str, int]],
    ) -> str:
        lines = []
        lines.append("# Structural Intelligence Engine — Statistics Report")
        lines.append("")
        lines.append("## 1. Tree Statistics")
        lines.append("")
        if tree_stats:
            lines.append(f"- Total trees built: {tree_stats.get('total_trees', 0)}")
            lines.append(f"- Avg depth: {tree_stats.get('avg_depth', 0)}")
            lines.append(f"- Avg nodes per tree: {tree_stats.get('avg_nodes', 0)}")
            lines.append(f"- Avg subtotals per tree: {tree_stats.get('avg_subtotals', 0)}")
            lines.append(f"- Avg sections per tree: {tree_stats.get('avg_sections', 0)}")
            lines.append(f"- Max depth: {tree_stats.get('max_depth', 0)}")
            lines.append(f"- Min depth: {tree_stats.get('min_depth', 0)}")
            lines.append("")
            lines.append("### Code Format Distribution")
            lines.append("")
            for fmt, cnt in tree_stats.get("code_format_dist", {}).items():
                lines.append(f"- {fmt}: {cnt}")
            lines.append("")
            lines.append("### Column Layout Distribution")
            lines.append("")
            for lay, cnt in tree_stats.get("column_layout_dist", {}).items():
                lines.append(f"- {lay}: {cnt}")
            lines.append("")

        lines.append("## 2. Template Statistics")
        lines.append("")
        if template_stats:
            lines.append(f"- Total templates: {template_stats.get('total_templates', 0)}")
            lines.append(f"- Total files covered: {template_stats.get('total_files', 0)}")
            lines.append(f"- Avg frequency per template: {template_stats.get('avg_frequency', 0)}")
            lines.append(f"- Avg depth: {template_stats.get('avg_depth', 0)}")
            lines.append(f"- Avg nodes: {template_stats.get('avg_nodes', 0)}")
            lines.append("")
            lines.append("### Family Distribution")
            lines.append("")
            for fam, cnt in template_stats.get("family_dist", {}).items():
                lines.append(f"- {fam}: {cnt}")
            lines.append("")
            lines.append("### Complexity Distribution")
            lines.append("")
            for level, cnt in template_stats.get("by_complexity", {}).items():
                lines.append(f"- {level}: {cnt}")
            lines.append("")

        lines.append("## 3. Family Statistics")
        lines.append("")
        if family_stats:
            for fam, size in family_stats.get("family_sizes", {}).items():
                cov = family_stats.get("coverage_pct", {}).get(fam, 0)
                lines.append(f"- {fam}: {size} files ({cov}%)")
            lines.append("")

        lines.append("## 4. Top Repeated Patterns")
        lines.append("")
        lines.append("| Pattern | Frequency |")
        lines.append("|---------|-----------|")
        for pat, count in patterns[:20]:
            lines.append(f"| {pat[:50]} | {count} |")
        lines.append("")

        return "\n".join(lines)
