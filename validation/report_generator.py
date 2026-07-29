from __future__ import annotations
from .models import ValidationResult, IntegrityScore
from pathlib import Path


class ReportGenerator:

    @staticmethod
    def generate_per_balance_report(result: ValidationResult) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append(f"BALANCE INTEGRITY VALIDATION REPORT")
        lines.append("=" * 70)
        lines.append(f"")
        lines.append(f"Source file:  {result.source_file}")
        if result.company:
            lines.append(f"Company:      {result.company}")
        if result.year:
            lines.append(f"Year:         {result.year}")
        lines.append(f"Pages:        {result.pages}")
        lines.append(f"Format:       {result.format_family}")
        lines.append(f"Layout:       {result.layout_type}")
        lines.append(f"")

        lines.append(f"--- Account Summary ---")
        lines.append(f"  Total accounts:    {result.accounts_total}")
        lines.append(f"  Classified:        {result.accounts_classified}")
        lines.append(f"  Ignored:           {result.accounts_ignored}")
        lines.append(f"")

        if result.hierarchy_tree:
            ht = result.hierarchy_tree
            lines.append(f"--- Hierarchy ---")
            lines.append(f"  Root nodes:     {len(ht.roots)}")
            lines.append(f"  Total nodes:    {len(ht.all_nodes)}")
            lines.append(f"  Header nodes:   {len(ht.header_nodes)}")
            lines.append(f"  Subtotal nodes: {len(ht.subtotal_nodes)}")
            lines.append(f"  Detail accounts: {len(ht.detail_nodes)}")
            lines.append(f"")

        if result.subtotal_results:
            lines.append(f"--- Subtotal Validation ---")
            passed_st = sum(1 for r in result.subtotal_results if r.passed)
            total_st = len(result.subtotal_results)
            lines.append(f"  Verified:  {passed_st}/{total_st}")
            for sr in result.subtotal_results:
                status = "OK" if sr.passed else "FAIL"
                lines.append(
                    f"  [{status}] {sr.account_name}: "
                    f"expected={sr.expected:,.0f} actual={sr.actual:,.0f} "
                    f"diff={sr.difference:,.0f} ({sr.pct_diff:.1f}%)"
                )
            lines.append(f"")

        if result.equation_results:
            lines.append(f"--- Equation Validation ---")
            passed_eq = sum(1 for r in result.equation_results if r.passed)
            total_eq = len(result.equation_results)
            lines.append(f"  Verified:  {passed_eq}/{total_eq}")
            for er in result.equation_results:
                status = "OK" if er.passed else "FAIL"
                lines.append(f"  [{status}] {er.equation}")
                lines.append(f"           left={er.left_side:,.0f} right={er.right_side:,.0f} diff={er.difference:,.0f}")
            lines.append(f"")

        if result.missing_candidates:
            lines.append(f"--- Missing Account Candidates ---")
            for mc in result.missing_candidates[:10]:
                lines.append(
                    f"  Amount={mc.target_amount:,.0f} → matched '{mc.account_name}' "
                    f"({mc.matched_amount:,.0f}, {mc.similarity_pct:.0f}%) "
                    f"L{mc.line_number}: {mc.reason}"
                )
            if len(result.missing_candidates) > 10:
                lines.append(f"  ... and {len(result.missing_candidates) - 10} more")
            lines.append(f"")

        if result.integrity_score:
            s = result.integrity_score
            lines.append(f"--- Integrity Score ---")
            lines.append(f"  Extraction:       {s.extraction_score:.1f}/100")
            lines.append(f"  Classification:   {s.classification_score:.1f}/100")
            lines.append(f"  Hierarchy:        {s.hierarchy_score:.1f}/100")
            lines.append(f"  Subtotal:         {s.subtotal_score:.1f}/100")
            lines.append(f"  Equation:         {s.equation_score:.1f}/100")
            lines.append(f"  ─────────────────────────")
            lines.append(f"  OVERALL:          {s.overall:.1f}/100")
            lines.append(f"")

        if result.warnings:
            lines.append(f"--- Warnings ---")
            for w in result.warnings:
                lines.append(f"  {w}")
            lines.append(f"")

        lines.append("=" * 70)
        return "\n".join(lines)

    @staticmethod
    def generate_global_report(all_results: list[ValidationResult], output_path: str | Path):
        lines = []
        lines.append("# Balance Integrity Validation — Global Report")
        lines.append("")
        lines.append(f"Balances analyzed: {len(all_results)}")
        lines.append("")

        total_st_verified = 0
        total_st_errors = 0
        total_eq_verified = 0
        total_missing = 0
        scores = []

        for r in all_results:
            if r.integrity_score:
                scores.append(r.integrity_score.overall)
            total_st_verified += sum(1 for sr in r.subtotal_results if sr.passed)
            total_st_errors += sum(1 for sr in r.subtotal_results if not sr.passed)
            total_eq_verified += len(r.equation_results)
            total_missing += len(r.missing_candidates)

        lines.append(f"Total subtotals verified: {total_st_verified}")
        lines.append(f"Total subtotal errors:    {total_st_errors}")
        lines.append(f"Total equations verified: {total_eq_verified}")
        lines.append(f"Total missing candidates: {total_missing}")
        lines.append("")

        if scores:
            avg_score = sum(scores) / len(scores)
            lines.append(f"Average Integrity Score:  {avg_score:.1f}/100")
            lines.append(f"Min Integrity Score:      {min(scores):.1f}/100")
            lines.append(f"Max Integrity Score:      {max(scores):.1f}/100")
            lines.append("")

            sorted_results = sorted(
                [(r, r.integrity_score.overall if r.integrity_score else 0) for r in all_results],
                key=lambda x: x[1],
            )

            lines.append("## Ranking (worst first)")
            lines.append("")
            lines.append("| # | File | Score | Subtotals | Equations | Missing |")
            lines.append("|---|------|-------|-----------|-----------|---------|")
            for rank, (r, sc) in enumerate(sorted_results, 1):
                st_ok = sum(1 for sr in r.subtotal_results if sr.passed)
                st_fail = sum(1 for sr in r.subtotal_results if not sr.passed)
                eq_ok = sum(1 for er in r.equation_results if er.passed)
                eq_fail = sum(1 for er in r.equation_results if not er.passed)
                lines.append(
                    f"| {rank} | {Path(r.source_file).name[:40]} | {sc:.1f} "
                    f"| {st_ok}/{st_fail} | {eq_ok}/{eq_fail} "
                    f"| {len(r.missing_candidates)} |"
                )
            lines.append("")

        families: dict[str, list[float]] = {}
        for r in all_results:
            fam = r.format_family or "UNKNOWN"
            families.setdefault(fam, [])
            if r.integrity_score:
                families[fam].append(r.integrity_score.overall)

        lines.append("## Families by Average Integrity")
        lines.append("")
        lines.append("| Family | Count | Avg Score |")
        lines.append("|--------|-------|-----------|")
        for fam, fam_scores in sorted(families.items(), key=lambda x: sum(x[1]) / len(x[1])):
            avg = sum(fam_scores) / len(fam_scores)
            lines.append(f"| {fam} | {len(fam_scores)} | {avg:.1f} |")
        lines.append("")

        main_causes: dict[str, int] = {}
        for r in all_results:
            for sr in r.subtotal_results:
                if not sr.passed:
                    cause = "Subtotal mismatch"
                    main_causes[cause] = main_causes.get(cause, 0) + 1
            for er in r.equation_results:
                if not er.passed:
                    cause = "Equation mismatch"
                    main_causes[cause] = main_causes.get(cause, 0) + 1
            if r.missing_candidates:
                cause = "Missing accounts"
                main_causes[cause] = main_causes.get(cause, 0) + len(r.missing_candidates)

        lines.append("## Main Causes of Differences")
        lines.append("")
        for cause, count in sorted(main_causes.items(), key=lambda x: -x[1]):
            lines.append(f"- {cause}: {count}")
        lines.append("")

        if all_results:
            worst = sorted_results[0][0]
            lines.append("## Worst Balance Details")
            lines.append("")
            lines.append(f"**{Path(worst.source_file).name}**")
            lines.append(f"- Score: {worst.integrity_score.overall:.1f}/100" if worst.integrity_score else "")
            lines.append(f"- Total accounts: {worst.accounts_total}")
            lines.append(f"- Classified: {worst.accounts_classified}")
            lines.append(f"- Subtotal errors: {sum(1 for sr in worst.subtotal_results if not sr.passed)}")
            lines.append(f"- Equation errors: {sum(1 for er in worst.equation_results if not er.passed)}")
            lines.append(f"- Missing candidates: {len(worst.missing_candidates)}")
            lines.append("")

        content = "\n".join(lines)

        if output_path:
            Path(output_path).write_text(content, encoding="utf-8")

        return content
