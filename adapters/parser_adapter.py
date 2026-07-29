from __future__ import annotations

import time
from pathlib import Path

from document_context import DocumentContext
from document_context.models import ParserData
from parser_universal import ParserPDF, parsear_excel


class ParserAdapter:
    def __init__(self):
        self._parser = ParserPDF()

    def run(self, ctx: DocumentContext) -> DocumentContext:
        path = Path(ctx.source_file)
        if not path.exists():
            ctx.set_custom("parser_error", f"File not found: {path}")
            return ctx

        ext = path.suffix.lower()
        if ext in (".xlsx", ".xls"):
            try:
                from parser_universal import FormatoCodigo, ResultadoParseo
                cuentas = parsear_excel(path)
                resultado = ResultadoParseo(
                    archivo=path.name,
                    formato_codigo=FormatoCodigo.SIN_CODIGO,
                    separador_miles="",
                    requirio_ocr=False,
                    rotacion_aplicada=0,
                    cuentas=cuentas,
                )
            except Exception as e:
                ctx.set_custom("parser_error", f"Excel parse error: {e}")
                return ctx
        else:
            try:
                start = time.perf_counter()
                resultado = self._parser.parsear(path)
                elapsed = time.perf_counter() - start
            except Exception as e:
                ctx.set_custom("parser_error", f"PDF parse error: {e}")
                return ctx

        parser_data = ParserData(
            selected_parser="ParserPDF",
            parser_version="1.0.0",
            parser_time=elapsed if ext not in (".xlsx", ".xls") else 0.0,
            raw_accounts=resultado.cuentas,
        )
        ctx.set_parser(parser_data, module="parser_adapter")
        ctx.set_custom("parser_resultado", resultado)

        return ctx
