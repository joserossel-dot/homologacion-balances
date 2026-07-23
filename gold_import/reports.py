from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from gold_import.models import ImportResult
from gold_import.validator import ValidationResult


class ImportReport:
    def __init__(
        self,
        result: ImportResult,
        snap_before: dict[str, Any],
        snap_after: dict[str, Any],
        validation: ValidationResult,
        output_dir: str = "reports/gold_import",
    ):
        self.result = result
        self.snap_before = snap_before
        self.snap_after = snap_after
        self.validation = validation
        self.output_dir = Path(output_dir)

    def export_xlsx(self) -> str:
        path = self.output_dir / "import_report.xlsx"
        rows = [
            {"metric": "Total en template", "value": self.result.total_in_template},
            {"metric": "Revisadas (con gold_standard_code)", "value": self.result.reviewed_in_template},
            {"metric": "No revisadas (gold_standard_code vacío)", "value": self.result.unreviewed_in_template},
            {"metric": "Importadas como nuevas", "value": self.result.imported},
            {"metric": "Actualizadas (ya existían)", "value": self.result.updated},
            {"metric": "Omitidas", "value": self.result.skipped},
            {"metric": "", "value": ""},
            {"metric": "Registros antes de importar", "value": self.snap_before.get("total_records", 0)},
            {"metric": "Registros después de importar", "value": self.snap_after.get("total_records", 0)},
            {"metric": "Revisados antes", "value": self.snap_before.get("reviewed_records", 0)},
            {"metric": "Revisados después", "value": self.snap_after.get("reviewed_records", 0)},
            {"metric": "Conflictos antes", "value": self.snap_before.get("statistics", {}).get("conflicts", 0)},
            {"metric": "Conflictos después", "value": self.snap_after.get("statistics", {}).get("conflicts", 0)},
            {"metric": "Códigos únicos antes", "value": self.snap_before.get("unique_codes", 0)},
            {"metric": "Códigos únicos después", "value": self.snap_after.get("unique_codes", 0)},
        ]

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="Resumen")

            if self.validation.errors:
                errs = pd.DataFrame([e.to_dict() for e in self.validation.errors])
                errs.to_excel(writer, index=False, sheet_name="Errores")

            before_codes = pd.DataFrame(
                sorted(self.snap_before.get("code_distribution", {}).items(), key=lambda x: -x[1]),
                columns=["codigo", "count"],
            )
            if not before_codes.empty:
                before_codes.to_excel(writer, index=False, sheet_name="Distribucion_Antes")

            after_codes = pd.DataFrame(
                sorted(self.snap_after.get("code_distribution", {}).items(), key=lambda x: -x[1]),
                columns=["codigo", "count"],
            )
            if not after_codes.empty:
                after_codes.to_excel(writer, index=False, sheet_name="Distribucion_Despues")

            if self.result.errors:
                err_list = pd.DataFrame([{"error": e} for e in self.result.errors])
                err_list.to_excel(writer, index=False, sheet_name="Errores_Import")

        return str(path)

    def export_md(self) -> str:
        lines = []
        lines.append("# Reporte de Importación — Gold Standard")
        lines.append("")
        lines.append(f"**Fecha:** {self.snap_after.get('timestamp', '')[:19]}")
        lines.append(f"**Revisor:** {self.result.reviewer}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Resumen de Importación")
        lines.append("")
        lines.append("| Métrica | Valor |")
        lines.append("|---------|-------|")
        lines.append(f"| Filas en template | {self.result.total_in_template} |")
        lines.append(f"| Revisadas | {self.result.reviewed_in_template} |")
        lines.append(f"| No revisadas | {self.result.unreviewed_in_template} |")
        lines.append(f"| Importadas como nuevas | {self.result.imported} |")
        lines.append(f"| Actualizadas | {self.result.updated} |")
        lines.append(f"| Omitidas | {self.result.skipped} |")
        lines.append("")
        lines.append("## Comparación Antes / Después")
        lines.append("")
        lines.append("| Métrica | Antes | Después | Diferencia |")
        lines.append("|---------|-------|---------|------------|")
        b4 = self.snap_before
        af = self.snap_after
        for key, label in [
            ("total_records", "Total registros"),
            ("reviewed_records", "Revisados"),
            ("unique_codes", "Códigos únicos"),
        ]:
            bv = b4.get(key, 0)
            av = af.get(key, 0)
            diff = av - bv
            sign = "+" if diff > 0 else ""
            lines.append(f"| {label} | {bv} | {av} | {sign}{diff} |")

        codes_before = set(b4.get("code_distribution", {}).keys())
        codes_after = set(af.get("code_distribution", {}).keys())
        new_codes = codes_after - codes_before
        if new_codes:
            lines.append("")
            lines.append("### Nuevos códigos incorporados")
            lines.append("")
            for c in sorted(new_codes):
                count = af.get("code_distribution", {}).get(c, 0)
                lines.append(f"- `{c}` ({count} registros)")

        before_conflicts = b4.get("conflicts", [])
        after_conflicts = af.get("conflicts", [])
        if after_conflicts:
            lines.append("")
            lines.append("### Conflictos detectados")
            lines.append("")
            lines.append("| Cuenta | Códigos en conflicto |")
            lines.append("|--------|---------------------|")
            for c in after_conflicts:
                lines.append(f"| {c.get('account_name', '')} | `{c.get('codes', '')}` |")

        if self.validation.errors:
            lines.append("")
            lines.append("## Errores de Validación")
            lines.append("")
            for e in self.validation.errors:
                lines.append(f"- Fila {e.row}: **{e.field}** — {e.message} `{e.value}`")

        if self.validation.warnings:
            lines.append("")
            lines.append("## Advertencias")
            lines.append("")
            for w in self.validation.warnings:
                lines.append(f"- {w}")

        if self.result.errors:
            lines.append("")
            lines.append("## Errores de Importación")
            lines.append("")
            for e in self.result.errors:
                lines.append(f"- {e}")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Snapshots")
        lines.append("")
        lines.append(f"- Antes: `{self.result.snapshot_before}`")
        lines.append(f"- Después: `{self.result.snapshot_after}`")
        lines.append(f"- Reporte XLSX: `{self.result.report_xlsx}`")

        path = self.output_dir / "import_report.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
