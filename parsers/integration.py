"""Integración opcional de DocumentAnalyzer + ParserPDF.

Flujo:
  Documento → DocumentAnalyzer → ParserPDF → EnhancedParseResult

Propósito:
  Agregar metadata de análisis documental al resultado del parser
  sin modificar el código existente.

Uso:
  from parsers.integration import parse_with_analysis, EnhancedParseResult
  
  result = parse_with_analysis("balance.pdf")
  print(result.tipo_documento)
  print(result.necesita_ocr)
  print(result.confianza_global)
  
  # Acceso al resultado original
  for cuenta in result.cuentas:
      ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from parser_universal import CuentaRaw, FormatoCodigo, ParserPDF, ResultadoParseo
from parsers.analyzer import DocumentAnalysis, DocumentAnalyzer


@dataclass
class EnhancedParseResult:
    """Resultado del parseo enriquecido con metadata de análisis documental.

    Envuelve un ResultadoParseo original y agrega el análisis estructural
    del DocumentAnalyzer. No modifica el resultado original.
    """
    resultado: ResultadoParseo
    analysis: DocumentAnalysis

    # ------------------------------------------------------------------
    # Passthrough properties — acceso directo a ResultadoParseo
    # ------------------------------------------------------------------

    @property
    def archivo(self) -> str:
        return self.resultado.archivo

    @property
    def formato_codigo(self) -> FormatoCodigo:
        return self.resultado.formato_codigo

    @property
    def separador_miles(self) -> str:
        return self.resultado.separador_miles

    @property
    def requirio_ocr(self) -> bool:
        return self.resultado.requirio_ocr

    @property
    def rotacion_aplicada(self) -> int:
        return self.resultado.rotacion_aplicada

    @property
    def cuentas(self) -> list[CuentaRaw]:
        return self.resultado.cuentas

    @property
    def advertencias(self) -> list[str]:
        return self.resultado.advertencias

    # ------------------------------------------------------------------
    # Analysis metadata properties
    # ------------------------------------------------------------------

    @property
    def tipo_documento(self) -> str:
        return self.analysis.file.file_type

    @property
    def necesita_ocr(self) -> bool:
        return self.analysis.needs_ocr

    @property
    def orientacion_detectada(self) -> int:
        return self.analysis.orientation.rotation

    @property
    def orientacion_confianza(self) -> float:
        return self.analysis.orientation.confidence

    @property
    def deteccion_tabla(self) -> dict[str, Any]:
        return {
            "has_tables": self.analysis.tables.has_tables,
            "table_count": self.analysis.tables.table_count,
            "confidence": self.analysis.tables.confidence,
        }

    @property
    def formato_codigo_detectado(self) -> Optional[str]:
        return self.analysis.code.code_format

    @property
    def layout_confidence(self) -> float:
        return self.analysis.layout.confidence

    @property
    def confianza_global(self) -> float:
        return self.analysis.overall_confidence

    @property
    def tiene_texto_nativo(self) -> bool:
        return self.analysis.text.has_native_text

    @property
    def tiene_codigos(self) -> bool:
        return self.analysis.code.has_codes

    @property
    def tiene_tablas(self) -> bool:
        return self.analysis.tables.has_tables

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "archivo": self.resultado.archivo,
            "formato_codigo": self.resultado.formato_codigo.value,
            "separador_miles": self.resultado.separador_miles,
            "requirio_ocr": self.resultado.requirio_ocr,
            "rotacion_aplicada": self.resultado.rotacion_aplicada,
            "total_cuentas": len(self.resultado.cuentas),
            "advertencias": self.resultado.advertencias,
            "analysis": self.analysis.to_dict(),
        }

    def to_dict_flat(self) -> dict[str, Any]:
        """Versión plana con campos de análisis al mismo nivel."""
        return {
            "archivo": self.resultado.archivo,
            "formato_codigo": self.resultado.formato_codigo.value,
            "separador_miles": self.resultado.separador_miles,
            "requirio_ocr": self.resultado.requirio_ocr,
            "rotacion_aplicada": self.resultado.rotacion_aplicada,
            "total_cuentas": len(self.resultado.cuentas),
            "advertencias": self.resultado.advertencias,
            # Analysis metadata
            "tipo_documento": self.tipo_documento,
            "necesita_ocr": self.necesita_ocr,
            "orientacion_detectada": self.orientacion_detectada,
            "orientacion_confianza": self.orientacion_confianza,
            "tiene_texto_nativo": self.tiene_texto_nativo,
            "tiene_tablas": self.tiene_tablas,
            "tablas_detectadas": self.analysis.tables.table_count,
            "tiene_codigos": self.tiene_codigos,
            "formato_codigo_detectado": self.formato_codigo_detectado,
            "codigo_confianza": self.analysis.code.confidence,
            "separador_detectado": self.analysis.separator.separator,
            "separador_confianza": self.analysis.separator.confidence,
            "layout_columnas": self.analysis.layout.columns,
            "layout_confianza": self.layout_confidence,
            "layout_source": self.analysis.layout.source,
            "confianza_global": self.confianza_global,
            "analysis_time_ms": self.analysis.analysis_time_ms,
        }


def parse_with_analysis(
    path: str | Path,
    analyzer: Optional[DocumentAnalyzer] = None,
    parser: Optional[ParserPDF] = None,
) -> EnhancedParseResult:
    """Analiza y parsea un documento.

    1. DocumentAnalyzer analiza la estructura del documento
    2. ParserPDF.parsear() extrae las cuentas
    3. Las advertencias del análisis se agregan al resultado del parser
    4. Se retorna un EnhancedParseResult con ambos conjuntos de datos

    Args:
        path: Ruta al archivo (PDF o Excel).
        analyzer: DocumentAnalyzer a usar (nuevo por defecto).
        parser: ParserPDF a usar (nuevo por defecto).

    Returns:
        EnhancedParseResult con parseo + análisis.
    """
    path = Path(path)
    _analyzer = analyzer or DocumentAnalyzer()
    _parser = parser or ParserPDF()

    analysis = _analyzer.analyze(path)
    resultado = _parser.parsear(path)

    _merge_warnings(resultado, analysis)

    return EnhancedParseResult(resultado=resultado, analysis=analysis)


def _merge_warnings(
    resultado: ResultadoParseo,
    analysis: DocumentAnalysis,
) -> None:
    """Agrega advertencias del análisis documental al resultado del parser."""
    # Advertencias generales del análisis
    for w in analysis.warnings:
        if w not in resultado.advertencias:
            resultado.advertencias.append(w)

    # Rotación 180°
    if analysis.orientation.rotation == 180:
        w = (
            f"Documento posiblemente rotado 180° "
            f"(confianza={analysis.orientation.confidence:.2f})"
        )
        if w not in resultado.advertencias:
            resultado.advertencias.append(w)

    # OCR necesario
    if analysis.needs_ocr:
        w = "Documento requiere OCR"
        if w not in resultado.advertencias:
            resultado.advertencias.append(w)

    # Layout de baja confianza
    if analysis.layout.confidence < 0.5:
        w = (
            f"Layout de baja confianza "
            f"({analysis.layout.confidence:.2f})"
        )
        if w not in resultado.advertencias:
            resultado.advertencias.append(w)

    # Sin códigos detectados
    if not analysis.code.has_codes:
        w = "Sin códigos detectados en análisis documental"
        if w not in resultado.advertencias:
            resultado.advertencias.append(w)

    # Sin texto nativo (no cubierto por needs_ocr)
    if not analysis.text.has_native_text and not analysis.needs_ocr:
        w = "Documento sin texto nativo detectable"
        if w not in resultado.advertencias:
            resultado.advertencias.append(w)
