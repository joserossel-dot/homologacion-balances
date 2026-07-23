#!/usr/bin/env python3
"""
CLI para ejecutar el Parser Gatekeeper en Shadow Mode sobre todos los
documentos en datasets/.

Evalúa cada línea extraída por el parser y registra confianza, estado y
razones, SIN modificar ninguna clasificación ni el comportamiento del pipeline.

Usage:
    python3 -m parser_quality.run_parser_quality
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser_quality.gatekeeper import ParserGatekeeper
from parser_quality.parser_quality_report import ParserQualityReport
from parser_universal import ParserPDF


def discover_files(root: Path) -> list[Path]:
    ext_valid = {".pdf", ".xlsx", ".xls"}
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.suffix.lower() in ext_valid and not p.name.startswith("."):
            files.append(p)
    return sorted(files)


def main() -> None:
    datasets_root = Path(__file__).resolve().parent.parent / "datasets"
    output_dir = Path(__file__).resolve().parent.parent / "reports" / "parser_quality"

    files = discover_files(datasets_root)
    print(f"Parser Gatekeeper — Shadow Mode")
    print(f"Documentos: {len(files)}")
    print("=" * 60)

    gatekeeper = ParserGatekeeper()
    report_gen = ParserQualityReport(output_dir)

    t0 = time.time()
    ocr_count = 0
    native_count = 0

    for idx, fpath in enumerate(files):
        print(f"[{idx+1}/{len(files)}] {fpath.name} ...", end=" ", flush=True)
        ft0 = time.time()

        if fpath.suffix.lower() in (".xlsx", ".xls"):
            _process_excel(fpath, gatekeeper)
            native_count += 1
        else:
            _process_pdf(fpath, gatekeeper)

        # Count OCR vs native
        file_results = [r for r in gatekeeper.results if r.file_name == fpath.name]
        if file_results and file_results[0].requirio_ocr:
            ocr_count += 1
        elif file_results:
            native_count += 1
        else:
            native_count += 1

        elapsed = time.time() - ft0
        print(f"  {elapsed:.1f}s")

    total_time = time.time() - t0

    print(f"\nProcesados {len(files)} documentos en {total_time:.1f}s")
    print(f"Total candidatos evaluados: {len(gatekeeper.results)}")
    print()
    print("Generando reportes...")
    metrics = report_gen.generate(
        gatekeeper.results,
        ocr_count=ocr_count,
        native_count=native_count,
        total_docs=len(files),
    )
    print()
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"  ACCEPT: {metrics['accepted']} ({metrics['accepted_pct']:.1f}%)")
    print(f"  REVIEW: {metrics['review']} ({metrics['review_pct']:.1f}%)")
    print(f"  REJECT: {metrics['rejected']} ({metrics['rejected_pct']:.1f}%)")
    print(f"  Confianza promedio: {metrics['avg_confidence']:.3f}")
    print(f"  OCR confianza: {metrics['ocr']['avg_confidence']:.3f}")
    print(f"  Nativo confianza: {metrics['native']['avg_confidence']:.3f}")
    print(f"  Reportes en: {output_dir}")


def _process_pdf(fpath: Path, gatekeeper: ParserGatekeeper) -> None:
    try:
        parser = ParserPDF()
        resultado = parser.parsear(fpath)
        for c in resultado.cuentas:
            line_str = f"{c.codigo or ''} {c.nombre} {c.monto or ''}"
            gatekeeper.evaluate(
                file_name=fpath.name,
                line_number=c.linea,
                line=line_str,
                account_name=c.nombre or "",
                account_code=c.codigo,
                monto=c.monto,
                is_total=c.es_total,
                requirio_ocr=resultado.requirio_ocr,
            )
    except Exception as e:
        print(f"  [ERROR] {e}", end="")


def _process_excel(fpath: Path, gatekeeper: ParserGatekeeper) -> None:
    try:
        from app_validacion import parsear_excel
        cuentas = parsear_excel(fpath)
        for i, c in enumerate(cuentas):
            line_str = f"{c.codigo or ''} {c.nombre} {c.monto or ''}"
            gatekeeper.evaluate(
                file_name=fpath.name,
                line_number=i,
                line=line_str,
                account_name=c.nombre or "",
                account_code=c.codigo,
                monto=c.monto,
                is_total=False,
                requirio_ocr=False,
            )
    except Exception as e:
        print(f"  [ERROR] {e}", end="")


if __name__ == "__main__":
    main()
