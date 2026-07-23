"""Parser Core 2.0 — prototipo modular.

Convivio en paralelo con parser_universal.py.  No lo reemplaza.
"""

from parsers.config import ParserConfig, load_config
from parsers.hygiene import GARBAGE_PATTERNS, es_linea_basura
from parsers.format_detector import (
    CodeFormat,
    detectar_formato_codigo,
    detectar_separador_miles,
)
from parsers.line_parser import (
    parsear_linea,
    parsear_monto,
    normalizar_codigo_ocr,
    normalizar_token_ocr,
    RawAccount,
)
from parsers.layout_detector import DetectedLayout, LayoutDetector
from parsers.pdf_parser import ParserCore2, ParseResult, ParseMetrics
from parsers.factory import ParserFactory

__all__ = [
    "ParserConfig", "load_config",
    "GARBAGE_PATTERNS", "es_linea_basura",
    "CodeFormat", "detectar_formato_codigo", "detectar_separador_miles",
    "parsear_linea", "parsear_monto", "normalizar_codigo_ocr",
    "normalizar_token_ocr", "RawAccount",
    "DetectedLayout", "LayoutDetector",
    "ParserCore2", "ParseResult", "ParseMetrics",
    "ParserFactory",
]
