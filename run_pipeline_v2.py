#!/usr/bin/env python3
"""
run_pipeline_v2.py — Backend CLI oficial de Homologación de Balances.

Uso:
    python run_pipeline_v2.py archivo.pdf
    python run_pipeline_v2.py archivo.xlsx --no-artifacts

Ejecuta el pipeline completo:
    Document Intelligence → Structure Engine → Document Context →
    Parser → Knowledge Base → Decision Engine → Coverage Engine →
    Self QA → Validation → Review Workspace → Export

Sin dependencia de Streamlit.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.runner import BackendRunner
from backend.backend_models import BackendResult


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backend oficial de Homologación de Balances",
    )
    parser.add_argument("file", type=str, help="Archivo PDF o Excel a procesar")
    parser.add_argument("--no-artifacts", action="store_true", help="No guardar artifacts")
    parser.add_argument("--log-level", type=str, default="INFO", help="Nivel de log (DEBUG, INFO, WARNING, ERROR)")

    args = parser.parse_args()
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"ERROR: Archivo no encontrado: {file_path}", file=sys.stderr)
        sys.exit(1)

    config = {
        "log_level": args.log_level,
        "artifacts_enabled": not args.no_artifacts,
    }

    backend = BackendRunner(config=config)

    def on_progress(progress: float, message: str = "") -> None:
        bar = "█" * int(progress * 40) + "░" * (40 - int(progress * 40))
        print(f"\r[{bar}] {progress:.0%} {message}", end="", flush=True)

    backend.execution_manager.on("progress", on_progress)

    print(f"Procesando: {file_path}")
    print()

    try:
        result: BackendResult = backend.run(str(file_path))
    except Exception as e:
        print(f"\n\nERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n")
    print("=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print(f"  Estado:       {result.execution.status}")
    print(f"  Tiempo:       {result.execution.elapsed_seconds:.3f}s")
    print(f"  Cuentas:      {result.statistics.total_accounts}")
    print(f"  Clasificadas: {result.statistics.classified}")
    print(f"  Sin clasificar: {result.statistics.unclassified}")
    print(f"  Ignoradas:    {result.statistics.ignored}")
    print(f"  Cobertura:    {result.statistics.coverage_pct:.1%}")
    print(f"  Unknown:      {result.statistics.unknown_pct:.1%}")
    print(f"  Learning:     {result.statistics.learning_hits}")
    print(f"  QA Approved:  {result.statistics.qa_approved}")
    print(f"  QA Confianza: {result.statistics.qa_confidence:.2%}")
    print(f"  Conflictos:   {result.statistics.conflicts}")
    print(f"  Revisión:     {result.statistics.human_review_required} cuentas")

    if result.export_paths:
        print(f"\n  Artifacts guardados en:")
        for label, path in result.export_paths.items():
            print(f"    {label}: {path}")

    if result.execution.errors:
        print(f"\n  Errores ({len(result.execution.errors)}):")
        for err in result.execution.errors:
            print(f"    - [{err['module']}] {err['error']}")

    print()
    print(f"Pipeline: {result.pipeline_version}")


if __name__ == "__main__":
    main()
