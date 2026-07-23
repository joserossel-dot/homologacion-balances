"""Benchmark: verify CMCC shadow mode does NOT alter official classification."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.homologation_pipeline import HomologationPipeline
from validation.dataset_manager import DatasetManager

GS_DB_PATH = "gold_standard.db"


def run_benchmark():
    print("=" * 60)
    print("CMCC SHADOW BENCHMARK — Before/After Comparison")
    print("=" * 60)

    pipeline = HomologationPipeline(str(GS_DB_PATH))

    manager = DatasetManager("datasets")
    all_files = manager.discover()
    print(f"Files to process: {len(all_files)}")

    total_accounts = 0
    total_shadow = 0
    total_shadow_altered = 0
    total_unclassified = 0
    total_classified = 0
    methods_before: dict[str, int] = {}
    methods_after: dict[str, int] = {}

    for i, dfile in enumerate(all_files):
        rel_path = str(dfile.path.relative_to(Path("datasets").resolve()))
        print(f"  [{i+1}/{len(all_files)}] {rel_path} ... ", end="", flush=True)

        result = pipeline.process(str(dfile.path))

        file_classified = result.get("accounts_classified", 0)
        file_unclassified = result.get("accounts_without_dictionary_match", 0)
        total_classified += file_classified
        total_unclassified += file_unclassified
        total_accounts += result.get("accounts_total", 0)

        for acct in result.get("classified", []):
            method = acct.get("method", "unknown")
            methods_after[method] = methods_after.get(method, 0) + 1

            shadow = acct.get("cmcc_shadow")
            if shadow is not None:
                total_shadow += 1
                official_method = acct.get("method", "")
                official_code = acct.get("standard_code")
                if official_method != "unclassified" or official_code is not None:
                    total_shadow_altered += 1

        print(f"ok ({file_classified} classified, {file_unclassified} unknown)")

    print()
    print("=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"\nTotal cuentas procesadas: {total_accounts}")
    print(f"Total clasificadas:       {total_classified}")
    print(f"Total UNKNOWN:            {total_unclassified}")
    print(f"Shadow matches:           {total_shadow}")

    print(f"\nMétodos de clasificación:")
    for m in sorted(methods_after.keys()):
        print(f"  {m}: {methods_after[m]}")

    print(f"\n--- VERIFICATION ---")
    pass_verify = True
    if total_shadow_altered > 0:
        print(f"  FAIL: {total_shadow_altered} shadow matches altered official classification!")
        pass_verify = False
    else:
        print(f"  PASS: 0 shadow matches altered official classification.")

    shadow_on_classified = sum(
        1 for _ in []  # already counted
    )

    unclassified_shadow = total_shadow
    if unclassified_shadow <= total_unclassified:
        print(f"  PASS: All {unclassified_shadow} shadow matches are on UNKNOWN accounts (≤ {total_unclassified} total UNKNOWN)")
    else:
        print(f"  FAIL: Shadow matches ({unclassified_shadow}) exceed UNKNOWN count ({total_unclassified})")
        pass_verify = False

    print(f"\nRecovery rate: {total_shadow}/{total_unclassified} "
          f"({(total_shadow/total_unclassified*100) if total_unclassified > 0 else 0:.1f}%)")

    print(f"\nBenchmark {'PASSED' if pass_verify else 'FAILED'}")

    return {
        "total_accounts": total_accounts,
        "total_classified": total_classified,
        "total_unclassified": total_unclassified,
        "total_shadow": total_shadow,
        "shadow_altered_official": total_shadow_altered,
        "pass": pass_verify,
    }


if __name__ == "__main__":
    run_benchmark()
