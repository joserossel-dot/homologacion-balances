"""Falla explícitamente cuando pytest no descubre pruebas."""

from __future__ import annotations

import re
import subprocess
import sys


COLLECTED_PATTERN = re.compile(r"(?P<count>\d+)\s+tests?\s+collected")


def parse_collected_count(output: str) -> int:
    matches = list(COLLECTED_PATTERN.finditer(output))
    return int(matches[-1].group("count")) if matches else 0


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    print(output)
    count = parse_collected_count(output)
    print(f"collected_tests={count}")
    if result.returncode not in (0, 5):
        print(f"ERROR: pytest collection failed with exit_code={result.returncode}")
        return result.returncode
    if count == 0:
        print("ERROR: collected_tests=0; el release gate no ejecutará una suite vacía.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
