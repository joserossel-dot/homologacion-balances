from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from adapters.account_adapter import AccountAdapter
from interpreters.balance_interpreter import BalanceInterpreter
from models.account_balance import AccountBalance
from parser_universal import ParserPDF, ResultadoParseo

logger = logging.getLogger(__name__)


class NewPipeline:
    def __init__(self) -> None:
        self._parser = ParserPDF()

    def parse(self, pdf_path: str | Path) -> list[dict[str, Any]]:
        start = time.perf_counter()
        path = Path(pdf_path)

        resultado: ResultadoParseo = self._parser.parsear(path)

        logger.info("cuentas leídas: %d", len(resultado.cuentas))

        output: list[dict[str, Any]] = []
        for cr in resultado.cuentas:
            ab: AccountBalance = AccountAdapter.from_cuenta_raw(cr)
            interp = BalanceInterpreter(ab)
            entry = {
                "account_code": ab.account_code,
                "account_name": ab.account_name,
                "nature": interp.nature.value,
                "classification_amount": interp.classification_amount,
                "confidence": ab.confidence,
                "warnings": interp.to_dict()["warnings"],
                "source_file": ab.source_file,
                "source_page": ab.source_page,
            }
            output.append(entry)

        elapsed = time.perf_counter() - start
        logger.info("cuentas convertidas: %d", len(output))
        logger.info("tiempo de ejecución: %.3fs", elapsed)

        return output

    def to_json(self, pdf_path: str | Path, output_file: str | Path) -> None:
        data = self.parse(pdf_path)
        path = Path(output_file)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("JSON escrito en: %s", path.resolve())
