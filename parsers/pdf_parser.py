"""Parser Core 2.0 — orquestador principal.

Envuelve ParserPDF.print() del parser original y añade:
  - LayoutDetector
  - ParseMetrics
  - Config soport
  - Interfaz unificada ParseResult

Corre en paralelo sin modificar el parser original.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from parser_universal import (
    ParserPDF as _ParserPDF,
    FormatoCodigo,
    validar_archivo,
    normalizar_codigo_ocr,
    PATRON_MONTOS,
)

from parsers.config import ParserConfig, load_config
from parsers.format_detector import (
    detectar_formato_codigo,
    detectar_separador_miles,
    extraer_muestra_montos,
)
from parsers.line_parser import RawAccount, parsear_todas
from parsers.layout_detector import DetectedLayout, LayoutDetector


from parsers.hygiene import es_linea_basura


@dataclass
class ParseMetrics:
    """Métricas de una ejecución de parseo."""
    total_lines: int = 0
    garbage_lines: int = 0
    parsed_accounts: int = 0
    blank_lines: int = 0
    rejected_lines: int = 0
    ocr_pages: int = 0
    ocr_time_seconds: float = 0.0
    extraction_confidence: float = 0.0
    layout_confidence: float = 0.0
    format_detected: str = ""
    warnings_count: int = 0
    total_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def fields() -> list[str]:
        return list(asdict(ParseMetrics()).keys())


@dataclass
class ParseResult:
    """Resultado unificado de parseo."""
    file_name: str
    format: str
    thousands_sep: str
    used_ocr: bool
    rotation: int
    accounts: list[RawAccount]
    layout: DetectedLayout | None = None
    warnings: list[str] = field(default_factory=list)
    metrics: ParseMetrics = field(default_factory=ParseMetrics)


class ParserCore2:
    """Parser Core 2.0 — orquesta validación, extracción, detección y parseo."""

    def __init__(self, config: ParserConfig | None = None):
        self._config = config or load_config()
        self._v1_parser = _ParserPDF()
        self._layout_detector = LayoutDetector()

    def parse(self, path: str | Path) -> ParseResult:
        """Punto de entrada principal.

        1. Validación de archivo (reutiliza validar_archivo)
        2. Extracción de texto vía ParserPDF existente
        3. LayoutDetector sobre líneas extraídas
        4. Detección de formato y separador (wrap)
        5. Parseo de líneas (wrap)
        6. Ensamble de ParseResult con ParseMetrics
        """
        t0 = time.perf_counter()
        path = Path(path)

        # 1. Validar
        ok, msg = validar_archivo(path)
        if not ok:
            return ParseResult(
                file_name=path.name,
                format="sin_codigo",
                thousands_sep=".",
                used_ocr=False,
                rotation=0,
                accounts=[],
                warnings=[f"VALIDACIÓN: {msg}"],
                metrics=ParseMetrics(total_time_seconds=round(time.perf_counter() - t0, 3)),
            )

        # 2. Extraer texto vía parser original
        lineas, requirio_ocr, rotacion = self._v1_parser._extraer_lineas(path)
        if not lineas:
            return ParseResult(
                file_name=path.name,
                format="sin_codigo",
                thousands_sep=".",
                used_ocr=requirio_ocr,
                rotation=rotacion,
                accounts=[],
                warnings=["No se pudo extraer texto"],
                metrics=ParseMetrics(total_time_seconds=round(time.perf_counter() - t0, 3)),
            )

        # Normalizar OCR
        lineas = [normalizar_codigo_ocr(l) for l in lineas]

        # 3. LayoutDetector
        cfg_layout = self._config.layout
        if cfg_layout.enable_detection:
            layout = self._layout_detector.detect(lineas)
        else:
            layout = DetectedLayout(source="disabled")

        # Si el layout detectado tiene alta confianza, se podría usar
        # para modificar el orden de columnas en el parseo de línea.
        # Por ahora, se registra como métrica.

        # 4. Detectar formato y separador
        cfg_det = self._config.detection
        primer_tokens = [l.split()[0] if l.split() else "" for l in lineas[:cfg_det.code_format_sample_lines]]
        formato = detectar_formato_codigo(primer_tokens)
        muestra_montos = extraer_muestra_montos(lineas, cfg_det.separator_sample_lines)
        separador = detectar_separador_miles(muestra_montos)

        # 5. Parsear líneas
        confianza = 0.75 if requirio_ocr else 1.0
        cuentas = parsear_todas(lineas, formato, separador, confianza)

        # 6. Métricas
        total_lines_raw = len(lineas)
        total_lines_nonblank = sum(1 for l in lineas if l.strip())
        blank_count = total_lines_raw - total_lines_nonblank
        garbage_count = sum(1 for l in lineas if es_linea_basura(l) and l.strip())
        rejected = total_lines_nonblank - garbage_count - len(cuentas)

        elapsed = time.perf_counter() - t0

        metrics = ParseMetrics(
            total_lines=total_lines_nonblank,
            garbage_lines=garbage_count,
            parsed_accounts=len(cuentas),
            blank_lines=blank_count,
            rejected_lines=max(0, rejected),
            extraction_confidence=confianza,
            layout_confidence=layout.confidence,
            format_detected=formato.value,
            warnings_count=0,
            total_time_seconds=round(elapsed, 3),
        )

        warnings: list[str] = []
        if requirio_ocr:
            warnings.append(
                f"OCR (rotación={rotacion}°), confianza={confianza}"
            )
        if layout.source == "fallback" and self._config.layout.enable_detection:
            warnings.append("Layout: fallback a heurística de 4 columnas")

        return ParseResult(
            file_name=path.name,
            format=formato.value,
            thousands_sep=separador,
            used_ocr=requirio_ocr,
            rotation=rotacion,
            accounts=cuentas,
            layout=layout,
            warnings=warnings,
            metrics=metrics,
        )
