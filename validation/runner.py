from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.homologation_pipeline import HomologationPipeline
from validation.dataset_manager import DatasetManager, DatasetFile
from validation.metrics_engine import MetricsEngine
from validation.report_builder import ReportBuilder
from validation.validation_session import ValidationSession

logger = logging.getLogger(__name__)


def process_file(
    pipeline: HomologationPipeline,
    dfile: DatasetFile,
    session: ValidationSession,
) -> None:
    try:
        result = pipeline.process(dfile.path)
        result["group"] = dfile.group
        result["file_type"] = dfile.file_type
        session.merge_file_result(result)
    except Exception as exc:
        logger.exception("Error processing %s", dfile.path)
        session.add_error({
            "category": "parser" if "parse" in str(exc).lower() else "general",
            "file": str(dfile.path),
            "group": dfile.group,
            "error": str(exc),
        })


def run(
    datasets_root: str | Path,
    output_dir: str | Path = "reports/validation",
    db_path: str | Path = "gold_standard.db",
) -> dict[str, Any]:
    root = Path(datasets_root)
    if not root.is_dir():
        raise NotADirectoryError(f"Dataset root not found: {root}")

    session = ValidationSession()
    session.start_timer()

    pipeline = HomologationPipeline(str(db_path))
    manager = DatasetManager(root)
    files = manager.discover()

    logger.info("Found %d file(s) in %s", len(files), root)

    for dfile in files:
        logger.info("Processing: %s (group=%s)", dfile.path.name, dfile.group)
        process_file(pipeline, dfile, session)

    session.stop_timer()

    metrics_engine = MetricsEngine()
    metrics = metrics_engine.compute(session)

    session.metrics = metrics

    report_builder = ReportBuilder(output_dir)
    report_path = report_builder.build_all(session, metrics)

    result = {
        "session": session,
        "metrics": metrics,
        "report_path": str(report_path),
    }

    _print_summary(metrics, report_path)
    return result


def _print_summary(metrics: dict[str, Any], report_path: Path) -> None:
    print()
    print("=" * 60)
    print("VALIDACION COMPLETADA")
    print("=" * 60)
    print(f"  Documentos:     {metrics['total_documents']}  ({metrics['pdf_count']} PDF, {metrics['excel_count']} Excel)")
    print(f"  Cuentas totales: {metrics['accounts_total']}")
    print(f"  Clasificadas:   {metrics['accounts_classified']}")
    print(f"  Sin clasificar: {metrics['accounts_manual']}")
    print(f"  Learning hits:  {metrics['learning_hits']}")
    print(f"  Tiempo total:   {metrics['processing_time']:.3f}s")
    print(f"  Reportes en:    {report_path}")
    print("=" * 60)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Validation runner for homologation pipeline")
    parser.add_argument("datasets_root", help="Root directory containing dataset groups")
    parser.add_argument("--output", "-o", default="reports/validation", help="Output directory for reports")
    parser.add_argument("--db", default="gold_standard.db", help="Gold Standard database path")
    args = parser.parse_args()

    try:
        run(args.datasets_root, args.output, args.db)
    except Exception as e:
        logger.exception("Validation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
