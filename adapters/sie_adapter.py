from __future__ import annotations

import re
from pathlib import Path

from document_context import DocumentContext
from document_context.models import DocumentMetadata, StructureData

from structure_engine import StructureDetector


class SIEAdapter:
    @staticmethod
    def run(ctx: DocumentContext) -> DocumentContext:
        source = ctx.source_file
        path = Path(source)

        company = SIEAdapter._infer_company(source)
        year = SIEAdapter._infer_year(source)
        layout = SIEAdapter._infer_layout(source)

        metadata = DocumentMetadata(
            company=company,
            year=year,
            layout=layout,
        )
        ctx.set_metadata(metadata, module="sie_adapter")

        structure = StructureData(
            document_type=SIEAdapter._infer_doc_type(layout),
            column_layout=layout,
        )
        ctx.set_structure(structure, module="sie_adapter")

        return ctx

    @staticmethod
    def _infer_company(source_file: str) -> str:
        name = Path(source_file).stem
        name = re.sub(r"^[\d_]+\s*", "", name)
        name = re.sub(r"[\s_]*\d{4}.*$", "", name)
        return name.strip("_ ")[:60] or "unknown"

    @staticmethod
    def _infer_year(source_file: str) -> int:
        m = re.search(r"(\d{4})", source_file)
        return int(m.group(1)) if m else 0

    @staticmethod
    def _infer_layout(source_file: str) -> str:
        lower = source_file.lower().replace("_", " ")
        if "balance" in lower and "8 columnas" in lower:
            return "8_columnas"
        if "tributario" in lower:
            return "tributario"
        if "pre-balance" in lower or "pre balance" in lower:
            return "pre_balance"
        if "consolidado" in lower:
            return "consolidado"
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            return "excel"
        return "pdf_estandar"

    @staticmethod
    def _infer_doc_type(layout: str) -> str:
        mapping = {
            "8_columnas": "balance_8c",
            "tributario": "tributario",
            "pre_balance": "balance",
            "consolidado": "consolidado",
            "excel": "excel",
        }
        return mapping.get(layout, "balance")
