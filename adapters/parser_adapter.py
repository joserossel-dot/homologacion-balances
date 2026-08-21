from __future__ import annotations

import time
from pathlib import Path

from document_context import DocumentContext
from document_context.models import ParserData
from parser_universal import ParserPDF, parsear_excel
from account_qualification import qualify_cuentas, safe_mode_enabled


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

        # GATE 4E: SAFE-R02+R03+R08 se aplica ÚNICAMENTE con activación
        # explícita (env SAFE_MODE ON). Con SAFE OFF el comportamiento es
        # exactamente el previo: raw_accounts == resultado.cuentas sin filtrar.
        safe_on = safe_mode_enabled()
        raw_accounts = qualify_cuentas(resultado.cuentas) if safe_on else resultado.cuentas

        parser_data = ParserData(
            selected_parser="ParserPDF",
            parser_version="1.0.0",
            parser_time=elapsed if ext not in (".xlsx", ".xls") else 0.0,
            raw_accounts=raw_accounts,
        )
        ctx.set_parser(parser_data, module="parser_adapter")
        ctx.set_custom("parser_resultado", resultado)
        ctx.set_custom("parser_raw_accounts", len(resultado.cuentas))
        ctx.set_custom("parser_raw_accounts_safe", len(raw_accounts))
        ctx.set_custom("parser_safe_mode", safe_on)

        return ctx
