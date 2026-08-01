"""run_document_mining.py — Minería del Document Knowledge Base (Sprint 33).

Recorre datasets/, extrae fingerprints reales por documento, construye la
matriz de similitud (Top-K vecinos), descubre familias, selecciona
representantes, mide cobertura, analiza calidad y genera:

  - reports/document_mining_report.md   (dashboard)
  - reports/{families,coverage,clusters,representatives,similarity_summary}.csv
  - knowledge_base/document_mining.json (resultado completo, para la UI)

Uso:
    python tools/run_document_mining.py [--datasets datasets] [--limit N]
                                        [--threshold 70] [--top-k 5]
                                        [--cache knowledge_base/document_fingerprints.json]
                                        [--force] [--quiet]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

from document_intelligence import DocumentFingerprint, FormatAnalyzer
from document_intelligence.factory import ExtractorFactory
from document_intelligence.knowledge.fingerprint import extract_preview_lines
from document_intelligence.mining import (
    DocumentRecord,
    load_analysis_result,
    run_mining_analysis,
    save_analysis_result,
    write_csvs,
    write_dashboard_report,
)
from tools.build_document_kb import guess_company

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATASETS = BASE_DIR / "datasets"
DEFAULT_CACHE = BASE_DIR / "knowledge_base" / "document_fingerprints.json"
DEFAULT_RESULT = BASE_DIR / "knowledge_base" / "document_mining.json"
DEFAULT_REPORT = BASE_DIR / "reports" / "document_mining_report.md"
DEFAULT_CSVS = BASE_DIR / "reports"


def collect_records(
    datasets_dir: str | Path,
    cache_path: str | Path = DEFAULT_CACHE,
    limit: Optional[int] = None,
    force: bool = False,
    quiet: bool = False,
) -> tuple[list[DocumentRecord], int]:
    """Fingerprints reales de todos los documentos del dataset.

    Usa caché (document_fingerprints.json) si existe y no se fuerza el
    recálculo.
    """
    cache = Path(cache_path)
    if cache.exists() and not force:
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            records = [DocumentRecord.from_dict(r) for r in data.get("records", [])]
            if _recompute_hashes(records):
                cache.write_text(json.dumps({
                    "records": [r.to_dict() for r in records],
                    "errors": data.get("errors", 0),
                    "files_processed": data.get("files_processed", len(records)),
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }, ensure_ascii=False, indent=2), encoding="utf-8")
            if not quiet:
                print(f"✓ Caché cargada: {len(records)} documentos "
                      f"(use --force para recalcular)")
            return records, data.get("errors", 0)
        except Exception:
            pass

    root = Path(datasets_dir)
    if not root.exists():
        raise FileNotFoundError(f"Directorio de datasets no encontrado: {root}")

    archivos = sorted(
        p for p in root.rglob("*")
        if p.suffix.lower() in (".pdf", ".xls", ".xlsx", ".xlsm")
        and "desktop.ini" not in p.name.lower()
    )
    if limit:
        archivos = archivos[:limit]

    analyzer = FormatAnalyzer()
    factory = ExtractorFactory()
    records: list[DocumentRecord] = []
    errores = 0

    for path in archivos:
        try:
            lines = extract_preview_lines(path)
            signature = analyzer.analyze(lines)
            fp = DocumentFingerprint.build(signature, lines)
            if path.suffix.lower() == ".pdf" and signature.page_count <= 1:
                try:
                    import pdfplumber
                    with pdfplumber.open(str(path)) as pdf:
                        signature.page_count = len(pdf.pages)
                except Exception:
                    pass
                fp.page_count = signature.page_count
                fp.compute_hash()  # el hash se calcula DESPUÉS del override

            rel = str(path.relative_to(root)) if root in path.parents else path.name
            records.append(DocumentRecord(
                id=rel,
                file=rel,
                company=guess_company(path.name, signature.company_name),
                family=signature.family.value,
                extractor=factory.decide_parser(signature).value,
                document_type=signature.document_type.value,
                fingerprint=fp,
            ))
            if not quiet:
                print(f"  {rel}")
        except Exception as exc:  # noqa: BLE001
            errores += 1
            if not quiet:
                print(f"  ERROR {path.name}: {exc}")

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({
        "records": [r.to_dict() for r in records],
        "errors": errores,
        "files_processed": len(archivos),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    if not quiet:
        print(f"✓ Fingerprints guardados en {cache} "
              f"({len(records)} documentos, {errores} errores)")
    return records, errores


def _recompute_hashes(records: list[DocumentRecord]) -> bool:
    """Reconcilia signature_hash de cada fingerprint con sus valores reales.

    Corrige cachés generadas con el bug de page_count (hash calculado
    antes del override), sin rescanear los PDFs.

    Devuelve True si algún hash cambió (la caché debe re-guardarse).
    """
    cambiado = False
    for r in records:
        antes = r.fingerprint.signature_hash
        nuevo = r.fingerprint.compute_hash()
        if antes != nuevo:
            cambiado = True
    return cambiado


def run_mining(
    datasets_dir: str | Path = DEFAULT_DATASETS,
    cache_path: str | Path = DEFAULT_CACHE,
    result_path: str | Path = DEFAULT_RESULT,
    report_path: str | Path = DEFAULT_REPORT,
    csvs_dir: str | Path = DEFAULT_CSVS,
    limit: Optional[int] = None,
    threshold: float = 70.0,
    top_k: int = 5,
    force: bool = False,
    quiet: bool = False,
) -> dict[str, Any]:
    """Ejecuta el análisis completo y escribe report + CSVs + JSON."""
    records, errores = collect_records(
        datasets_dir, cache_path, limit=limit, force=force, quiet=quiet,
    )

    t0 = time.perf_counter()
    result = run_mining_analysis(records, threshold=threshold, top_neighbors=top_k)
    result["errors"] = errores
    result["datasets_dir"] = str(Path(datasets_dir))

    write_dashboard_report(result, report_path)
    write_csvs(result, csvs_dir)
    save_analysis_result(result, result_path)

    if not quiet:
        print(f"\n✓ Report: {report_path}")
        print(f"✓ CSVs:  {csvs_dir}")
        print(f"✓ JSON:  {result_path}")
        print(f"  Documentos: {result['n_documents']} (errores: {errores})")
        print(f"  Familias:   {result['n_families']}")
        print(f"  Pares:      {result['matrix']['pairs_computed']}")
        print(f"  Similitud media: {result['matrix']['mean_similarity']}%")
        print(f"  Cobertura Top 5:  {result['coverage']['tiers'][0]['cumulative_pct']}%")
        print(f"  Cobertura Top 10: {result['coverage']['tiers'][1]['cumulative_pct']}%")
        print(f"  Cobertura Top 20: {result['coverage']['tiers'][2]['cumulative_pct']}%")
        print(f"  Tiempo análisis: {result['elapsed_seconds']}s")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Minería documental del DKB (Sprint 33)"
    )
    parser.add_argument("--datasets", type=str, default=str(DEFAULT_DATASETS))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=70.0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--cache", type=str, default=str(DEFAULT_CACHE))
    parser.add_argument("--out", type=str, default=str(DEFAULT_RESULT))
    parser.add_argument("--report", type=str, default=str(DEFAULT_REPORT))
    parser.add_argument("--csvs", type=str, default=str(DEFAULT_CSVS))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    run_mining(
        datasets_dir=args.datasets,
        cache_path=args.cache,
        result_path=args.out,
        report_path=args.report,
        csvs_dir=args.csvs,
        limit=args.limit,
        threshold=args.threshold,
        top_k=args.top_k,
        force=args.force,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    sys.exit(main())
