"""Verifica y registra el runtime OCR sin depender de la aplicación web."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


KNOWN_TESSDATA_DIRS = (
    Path("/usr/local/share/tessdata"),
    Path("/usr/share/tesseract-ocr/5/tessdata"),
    Path("/usr/share/tesseract-ocr/4.00/tessdata"),
)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=20)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_language_model(language: str) -> Path | None:
    candidates: list[Path] = []
    prefix = os.environ.get("TESSDATA_PREFIX")
    if prefix:
        candidates.append(Path(prefix))
    candidates.extend(KNOWN_TESSDATA_DIRS)
    for directory in candidates:
        model = directory / f"{language}.traineddata"
        if model.is_file():
            return model.resolve()
    return None


def inspect_ocr_runtime(binary: str = "tesseract") -> dict:
    """Devuelve evidencia determinista de binario, idiomas y modelo spa."""
    resolved = shutil.which(binary)
    evidence = {
        "schema_version": 1,
        "available": False,
        "binary": resolved or "",
        "version": "",
        "languages": [],
        "spa_available": False,
        "spa_model_sha256": "",
        "packages": {},
        "error": "",
    }
    if not resolved:
        evidence["error"] = "No se encontró el binario tesseract en PATH."
        return evidence
    version = _run([resolved, "--version"])
    if version.returncode != 0:
        evidence["error"] = (version.stderr or version.stdout).strip()[:500]
        return evidence
    evidence["version"] = (version.stdout or version.stderr).splitlines()[0].strip()
    languages = _run([resolved, "--list-langs"])
    if languages.returncode != 0:
        evidence["error"] = (languages.stderr or languages.stdout).strip()[:500]
        return evidence
    listed = [
        line.strip() for line in languages.stdout.splitlines()[1:]
        if line.strip()
    ]
    evidence["languages"] = sorted(set(listed))
    evidence["spa_available"] = "spa" in evidence["languages"]
    model = _find_language_model("spa")
    if model:
        evidence["spa_model_sha256"] = _sha256(model)
    dpkg = shutil.which("dpkg-query")
    if dpkg:
        packages = _run([
            dpkg, "-W", "-f=${Package}=${Version}\n",
            "tesseract-ocr", "tesseract-ocr-spa",
        ])
        if packages.returncode == 0:
            evidence["packages"] = dict(
                line.split("=", 1) for line in packages.stdout.splitlines()
                if "=" in line
            )
    evidence["available"] = bool(evidence["spa_available"])
    if not evidence["spa_available"]:
        evidence["error"] = "Tesseract está instalado, pero no ofrece el idioma spa."
    elif not evidence["spa_model_sha256"]:
        evidence["error"] = "No se pudo localizar spa.traineddata para registrar su hash."
        evidence["available"] = False
    return evidence


def compare_runtime(current: dict, expected: dict) -> list[str]:
    differences = []
    for key in ("version", "spa_model_sha256", "packages"):
        if current.get(key) != expected.get(key):
            differences.append(
                f"{key}: actual={current.get(key)!r}, esperado={expected.get(key)!r}"
            )
    return differences


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--require-spa", action="store_true")
    args = parser.parse_args()
    current = inspect_ocr_runtime()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(current, ensure_ascii=False, sort_keys=True))
    if args.require_spa and not current["available"]:
        print(f"ERROR OCR: {current['error']}")
        return 1
    if args.compare:
        expected = json.loads(args.compare.read_text(encoding="utf-8"))
        differences = compare_runtime(current, expected)
        if differences:
            print("ERROR OCR: el runtime difiere del registrado en la imagen:")
            for difference in differences:
                print(f"- {difference}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
