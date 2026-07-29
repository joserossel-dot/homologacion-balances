from __future__ import annotations
import sys
import json
import random
from pathlib import Path
from typing import Optional

from .models import ValidationResult
from .hierarchy import build_hierarchy, detect_section_boundaries
from .subtotal_validator import validate_subtotals
from .equation_validator import validate_balance_equation
from .missing_account_detector import detect_missing_accounts
from .integrity_score import compute_integrity_score
from .report_generator import ReportGenerator


class BalanceValidator:

    def __init__(self, tolerance_pct: float = 1.0):
        self.tolerance_pct = tolerance_pct
        self.report_gen = ReportGenerator()

    def validate(
        self,
        source_file: str,
        accounts_raw: list[dict],
        accounts_classified: list[dict] | None = None,
        accounts_ignored: list[dict] | None = None,
        company: str = "",
        year: int = 0,
        pages: int = 0,
        format_family: str = "",
        layout_type: str = "",
    ) -> ValidationResult:
        result = ValidationResult(
            source_file=source_file,
            company=company,
            year=year,
            pages=pages,
            format_family=format_family,
            layout_type=layout_type,
        )

        if accounts_classified is not None:
            result.accounts_classified = len(accounts_classified)
        if accounts_ignored is not None:
            result.accounts_ignored = len(accounts_ignored)

        result.accounts_total = len(accounts_raw)

        tree = build_hierarchy(accounts_raw, accounts_classified)
        result.hierarchy_tree = tree
        result.section_map = detect_section_boundaries(tree)

        result.subtotal_results = validate_subtotals(tree)

        result.equation_results = validate_balance_equation(tree)

        result.missing_candidates = detect_missing_accounts(
            result.subtotal_results,
            result.equation_results,
            tree,
            tolerance_pct=self.tolerance_pct,
        )

        result.integrity_score = compute_integrity_score(
            tree,
            result.subtotal_results,
            result.equation_results,
            result.accounts_classified,
            result.accounts_ignored,
        )

        return result

    def validate_from_pipeline(
        self,
        pipeline_result: dict,
        company: str = "",
        year: int = 0,
        pages: int = 0,
        format_family: str = "",
        layout_type: str = "",
    ) -> ValidationResult:
        source_file = pipeline_result.get("source_file", "")
        classified = pipeline_result.get("classified", [])
        ignored = pipeline_result.get("ignored", [])
        accounts_raw = classified + ignored

        return self.validate(
            source_file=source_file,
            accounts_raw=accounts_raw,
            accounts_classified=classified,
            accounts_ignored=ignored,
            company=company,
            year=year,
            pages=pages,
            format_family=format_family,
            layout_type=layout_type,
        )

    def validate_batch(
        self,
        files: list[Path],
        cache_file: str | None = None,
        skip_existing: bool = False,
        max_files: int | None = None,
    ) -> list[ValidationResult]:
        if max_files:
            files = files[:max_files]

        results = []
        cached_results = {}

        if cache_file and Path(cache_file).exists():
            cached_results = json.loads(Path(cache_file).read_text())
            print(f"Loaded {len(cached_results)} cached results")

        for f in files:
            cache_key = f.name
            if skip_existing and cache_key in cached_results:
                cached = cached_results[cache_key]
                vr = ValidationResult(**cached)
                results.append(vr)
                print(f"  [cached] {f.name}")
                continue

            try:
                result = self._process_single_file(f)
                results.append(result)
                cached_results[cache_key] = {
                    "source_file": result.source_file,
                    "accounts_total": result.accounts_total,
                    "accounts_classified": result.accounts_classified,
                    "accounts_ignored": result.accounts_ignored,
                    "format_family": result.format_family,
                    "layout_type": result.layout_type,
                    "integrity_score": {
                        "extraction_score": result.integrity_score.extraction_score,
                        "classification_score": result.integrity_score.classification_score,
                        "hierarchy_score": result.integrity_score.hierarchy_score,
                        "subtotal_score": result.integrity_score.subtotal_score,
                        "equation_score": result.integrity_score.equation_score,
                        "overall": result.integrity_score.overall,
                    } if result.integrity_score else {},
                    "subtotal_count": len(result.subtotal_results),
                    "subtotal_errors": sum(1 for sr in result.subtotal_results if not sr.passed),
                    "equation_count": len(result.equation_results),
                    "equation_errors": sum(1 for er in result.equation_results if not er.passed),
                    "missing_candidates": len(result.missing_candidates),
                }
                print(f"  [done] {f.name}")
            except Exception as e:
                print(f"  [ERROR] {f.name}: {e}")

        if cache_file:
            Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
            Path(cache_file).write_text(
                json.dumps(cached_results, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return results

    def _process_single_file(self, pdf_path: Path) -> ValidationResult:
        sys.path.insert(0, str(Path.cwd()))

        from parser_universal import ParserPDF

        parser = ParserPDF()
        raw = parser.parsear(pdf_path)

        accounts_raw = []
        for cuenta in raw.cuentas:
            accounts_raw.append({
                "linea": cuenta.linea,
                "codigo": cuenta.codigo or "",
                "nombre": cuenta.nombre,
                "monto": cuenta.monto or 0.0,
                "origen_columna": cuenta.origen_columna.value if hasattr(cuenta.origen_columna, "value") else str(cuenta.origen_columna),
                "es_total": cuenta.es_total,
            })

        classified = []
        ignored = []
        format_family = ""

        company = ""
        year = 0
        if accounts_raw:
            for raw_acct in accounts_raw:
                name = raw_acct.get("nombre", "")
                y = _extract_year(name)
                if y:
                    year = y
                    break

        return self.validate(
            source_file=pdf_path.name,
            accounts_raw=accounts_raw,
            accounts_classified=classified,
            accounts_ignored=ignored,
            company=company,
            year=year,
            format_family=format_family,
        )

    def generate_per_balance_report(self, result: ValidationResult) -> str:
        return self.report_gen.generate_per_balance_report(result)

    def generate_global_report(
        self,
        results: list[ValidationResult],
        output_path: str | Path = "reports/balance_integrity_validation.md",
    ):
        return self.report_gen.generate_global_report(results, output_path)


def _extract_year(text: str) -> int:
    import re
    years = re.findall(r"\b(19[5-9]\d|20[0-2]\d)\b", text)
    if years:
        return int(years[0])
    return 0


def select_balances(
    folder: str | Path,
    count: int = 20,
    seed: int = 42,
) -> list[Path]:
    folder = Path(folder)
    pdfs = sorted(folder.glob("*.pdf"))
    random.seed(seed)
    selected = random.sample(pdfs, min(count, len(pdfs)))
    return selected
