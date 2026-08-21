from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore[assignment]

from validation.validation_session import ValidationSession

logger = logging.getLogger(__name__)

_REPORT_FILES = [
    "summary.md",
    "metrics.json",
    "benchmark.csv",
    "errors.xlsx",
    "parser_errors.xlsx",
    "unclassified.xlsx",
    "timings.csv",
]


class ReportBuilder:
    def __init__(self, base_dir: str | Path = "reports/validation") -> None:
        self._base = Path(base_dir)

    def build_all(
        self,
        session: ValidationSession,
        metrics: dict[str, Any],
        timestamp: str | None = None,
    ) -> Path:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = self._base / timestamp
        out.mkdir(parents=True, exist_ok=True)
        self._write_summary(out, session, metrics)
        self._write_metrics_json(out, metrics)
        self._write_benchmark_csv(out, session)
        self._write_errors_xlsx(out, session)
        self._write_parser_errors_xlsx(out, session)
        self._write_unclassified_xlsx(out, session)
        self._write_timings_csv(out, session)
        logger.info("Reports generated in: %s", out.resolve())
        return out

    # ------------------------------------------------------------------
    # summary.md
    # ------------------------------------------------------------------

    def _write_summary(
        self, out: Path, session: ValidationSession, metrics: dict[str, Any]
    ) -> None:
        lines: list[str] = []
        lines.append("# Reporte de Validación")
        lines.append("")
        lines.append(f"- **Fecha:** {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"- **Documentos totales:** {metrics['total_documents']}")
        lines.append(f"  - PDF: {metrics['pdf_count']}")
        lines.append(f"  - Excel: {metrics['excel_count']}")
        lines.append(f"  - OCR: {metrics['ocr_count']}")
        lines.append("")
        lines.append("## Cuentas")
        lines.append("")
        lines.append(f"- **Cuentas totales:** {metrics['accounts_total']}")
        lines.append(f"- **Clasificadas:** {metrics['accounts_classified']}")
        lines.append(f"- **Sin clasificar:** {metrics['accounts_manual']}")
        lines.append("")
        lines.append("## Métodos de clasificación")
        lines.append("")
        lines.append("| Método | Cuentas |")
        lines.append("|--------|---------|")
        for method, count in sorted(metrics.get("methods_distribution", {}).items()):
            lines.append(f"| {method} | {count} |")
        lines.append("")
        lines.append("## Tiempos")
        lines.append("")
        lines.append(f"- **Total:** {metrics['processing_time']:.3f}s")
        lines.append(f"- **Promedio por documento:** {metrics['avg_time']:.4f}s")
        lines.append(f"- **P95:** {metrics['p95_time']:.4f}s")
        lines.append("")
        lines.append("## Errores")
        lines.append("")
        lines.append(f"- **Errores de parser:** {metrics['parser_errors']}")
        lines.append(f"- **Errores totales:** {session.summary()['errors_total']}")
        lines.append(f"- **Advertencias:** {session.summary()['warnings_total']}")
        lines.append("")
        lines.append("## Distribución por grupo")
        lines.append("")
        for group, count in sorted(metrics.get("files_by_group", {}).items()):
            lines.append(f"- **{group}:** {count} documento(s)")
        lines.append("")
        (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # metrics.json
    # ------------------------------------------------------------------

    def _write_metrics_json(self, out: Path, metrics: dict[str, Any]) -> None:
        (out / "metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # benchmark.csv
    # ------------------------------------------------------------------

    def _write_benchmark_csv(self, out: Path, session: ValidationSession) -> None:
        path = out / "benchmark.csv"
        fields = [
            "source_file", "accounts_total", "accounts_classified",
            "accounts_ignored", "accounts_without_dictionary_match",
            "learning_hits", "learning_exact", "learning_fuzzy",
            "fallback_classifier", "elapsed_seconds",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for entry in session.processed_files:
                row = {k: entry.get(k, "") for k in fields}
                writer.writerow(row)

    # ------------------------------------------------------------------
    # errors.xlsx
    # ------------------------------------------------------------------

    def _write_errors_xlsx(self, out: Path, session: ValidationSession) -> None:
        if pd is None:
            logger.warning("pandas not available, skipping errors.xlsx")
            return
        path = out / "errors.xlsx"
        if not session.errors:
            pd.DataFrame([{"mensaje": "Sin errores"}]).to_excel(path, index=False)
            return
        df = pd.DataFrame(session.errors)
        df.to_excel(path, index=False)

    # ------------------------------------------------------------------
    # parser_errors.xlsx
    # ------------------------------------------------------------------

    def _write_parser_errors_xlsx(self, out: Path, session: ValidationSession) -> None:
        if pd is None:
            logger.warning("pandas not available, skipping parser_errors.xlsx")
            return
        path = out / "parser_errors.xlsx"
        parser_errs = [e for e in session.errors if e.get("category") == "parser"]
        if not parser_errs:
            pd.DataFrame([{"mensaje": "Sin errores de parser"}]).to_excel(path, index=False)
            return
        pd.DataFrame(parser_errs).to_excel(path, index=False)

    # ------------------------------------------------------------------
    # unclassified.xlsx
    # ------------------------------------------------------------------

    def _write_unclassified_xlsx(self, out: Path, session: ValidationSession) -> None:
        if pd is None:
            logger.warning("pandas not available, skipping unclassified.xlsx")
            return
        path = out / "unclassified.xlsx"
        unclassified = session.unclassified_accounts()
        if not unclassified:
            pd.DataFrame([{"mensaje": "Todas las cuentas clasificadas"}]).to_excel(
                path, index=False
            )
            return
        pd.DataFrame(unclassified).to_excel(path, index=False)

    # ------------------------------------------------------------------
    # timings.csv
    # ------------------------------------------------------------------

    def _write_timings_csv(self, out: Path, session: ValidationSession) -> None:
        path = out / "timings.csv"
        fields = ["source_file", "elapsed_seconds", "accounts_total", "accounts_classified"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for entry in session.processed_files:
                row = {k: entry.get(k, "") for k in fields}
                writer.writerow(row)

    @staticmethod
    def expected_files() -> list[str]:
        return list(_REPORT_FILES)
