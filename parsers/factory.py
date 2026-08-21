"""ParserFactory — crea el parser apropiado según el tipo de archivo.

Soporta versiones: "1" (parser_universal.ParserPDF) y "2" (ParserCore2).
"""

from __future__ import annotations

from pathlib import Path

from parser_universal import ParserPDF as _ParserPDF
from parsers.config import ParserConfig, load_config
from parsers.pdf_parser import ParserCore2


class ParserFactory:
    """Fábrica de parsers. Crea la versión solicitada."""

    @staticmethod
    def create_v1() -> _ParserPDF:
        """Parser original (parser_universal.ParserPDF)."""
        return _ParserPDF()

    @staticmethod
    def create_v2(config: ParserConfig | None = None) -> ParserCore2:
        """Parser Core 2.0."""
        return ParserCore2(config or load_config())

    @staticmethod
    def create(version: str = "1", config: ParserConfig | None = None):
        """Crea parser según versión.

        Args:
            version: "1" = original, "2" = Core 2.0
            config: Config opcional para v2
        """
        if version == "2":
            return ParserFactory.create_v2(config)
        return ParserFactory.create_v1()
