"""DocumentAnalyzer — analiza la estructura de un documento antes de parsear.

Propósito:
  Determinar qué tipo de documento tenemos y cómo debe procesarse,
  antes de invocar al parser. Esto permite al parser adaptar su
  estrategia según las características reales del documento.

Responsabilidades:
  1. Validar integridad del archivo
  2. Detectar tipo de documento (PDF nativo, PDF imagen, Excel)
  3. Detectar orientación (0°, 90°, 180°, 270°)
  4. Detectar presencia de tablas
  5. Detectar formato de código de cuenta
  6. Detectar layout de columnas
  7. Estimar confianza general del análisis

NO extrae cuentas. NO clasifica. NO homologa.
Solo responde: ¿qué documento tengo y cómo debo procesarlo?
"""

from __future__ import annotations

import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pdfplumber

from parser_universal import (
    PATRON_COMPACTO,
    PATRON_GUION,
    PATRON_MONTOS,
    PATRON_PUNTO,
    ROTATION_CORRECTION_THRESHOLD,
    ExtractionContext,
    FormatoCodigo,
    detectar_formato_codigo as _detectar_formato_codigo,
    detectar_separador_miles as _detectar_separador_miles,
    validar_archivo,
)
from parsers.layout_detector import DetectedLayout, LayoutDetector
from parsers.orientation_detector import OrientationResult, detectar_orientacion_words
from parsers.text_normalizer import normalize_text_lines


@dataclass
class FileInfo:
    file_path: str
    file_name: str
    file_type: str
    file_size_bytes: int
    is_valid: bool
    validation_message: str


@dataclass
class OrientationAnalysis:
    rotation: int
    confidence: float
    method: str
    details: str = ""


@dataclass
class TableAnalysis:
    has_tables: bool
    table_count: int
    confidence: float
    details: str = ""


@dataclass
class CodeAnalysis:
    has_codes: bool
    code_format: Optional[str]
    confidence: float
    sample_codes: list[str] = field(default_factory=list)
    details: str = ""


@dataclass
class SeparatorAnalysis:
    separator: str
    confidence: float
    details: str = ""


@dataclass
class TextAnalysis:
    has_native_text: bool
    line_count: int
    sample_lines: list[str] = field(default_factory=list)
    details: str = ""


@dataclass
class DocumentAnalysis:
    """Metadata completa de un documento.

    Cada dimensión lleva su propio nivel de confianza para que el parser
    pueda decidir cómo proceder según la calidad del análisis.
    """

    # File
    file: FileInfo = field(default_factory=lambda: FileInfo(
        file_path="", file_name="", file_type="", file_size_bytes=0,
        is_valid=False, validation_message="",
    ))

    # Text extraction capability
    text: TextAnalysis = field(default_factory=lambda: TextAnalysis(
        has_native_text=False, line_count=0,
    ))

    # Orientation (native text)
    orientation: OrientationAnalysis = field(default_factory=lambda: OrientationAnalysis(
        rotation=0, confidence=0.0, method="unknown",
    ))

    # Tables
    tables: TableAnalysis = field(default_factory=lambda: TableAnalysis(
        has_tables=False, table_count=0, confidence=0.0,
    ))

    # Code format
    code: CodeAnalysis = field(default_factory=lambda: CodeAnalysis(
        has_codes=False, code_format=None, confidence=0.0,
    ))

    # Thousand separator
    separator: SeparatorAnalysis = field(default_factory=lambda: SeparatorAnalysis(
        separator=".", confidence=0.0,
    ))

    # Column layout
    layout: DetectedLayout = field(default_factory=lambda: DetectedLayout(
        columns=["activo", "pasivo", "perdida", "ganancia"],
        confidence=0.0, source="not_analyzed",
    ))

    # Overall assessment
    needs_ocr: bool = False
    overall_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    analysis_time_ms: float = 0.0
    rotation_corrected_before_layout: bool = False
    text_normalized: bool = False
    normalization_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": {
                "path": self.file.file_path,
                "name": self.file.file_name,
                "type": self.file.file_type,
                "size_bytes": self.file.file_size_bytes,
                "is_valid": self.file.is_valid,
                "validation_message": self.file.validation_message,
            },
            "text": {
                "has_native_text": self.text.has_native_text,
                "line_count": self.text.line_count,
                "sample_lines": self.text.sample_lines[:5],
                "details": self.text.details,
            },
            "orientation": {
                "rotation": self.orientation.rotation,
                "confidence": self.orientation.confidence,
                "method": self.orientation.method,
                "details": self.orientation.details,
            },
            "tables": {
                "has_tables": self.tables.has_tables,
                "table_count": self.tables.table_count,
                "confidence": self.tables.confidence,
                "details": self.tables.details,
            },
            "code": {
                "has_codes": self.code.has_codes,
                "code_format": self.code.code_format,
                "confidence": self.code.confidence,
                "sample_codes": self.code.sample_codes[:5],
                "details": self.code.details,
            },
            "separator": {
                "separator": self.separator.separator,
                "confidence": self.separator.confidence,
                "details": self.separator.details,
            },
            "layout": self.layout.to_dict(),
            "needs_ocr": self.needs_ocr,
            "overall_confidence": self.overall_confidence,
            "warnings": self.warnings,
            "analysis_time_ms": self.analysis_time_ms,
            "rotation_corrected_before_layout": self.rotation_corrected_before_layout,
            "text_normalized": self.text_normalized,
            "normalization_actions": self.normalization_actions[:5],
        }


class DocumentAnalyzer:
    """Analiza un documento y determina sus características estructurales.

    Uso:
        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze("balance_2024.pdf")
        print(analysis.to_dict())
    """

    def __init__(self) -> None:
        self._layout_detector = LayoutDetector()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, path: str | Path) -> DocumentAnalysis:
        """Analiza un documento y retorna metadata estructural.

        Args:
            path: Ruta al archivo (PDF o Excel).

        Returns:
            DocumentAnalysis con todas las dimensiones detectadas.
        """
        inicio = time.perf_counter()
        path = Path(path)
        result = DocumentAnalysis()

        # 1. Validar archivo
        result.file = self._analyze_file(path)
        if not result.file.is_valid:
            result.warnings.append(result.file.validation_message)
            result.analysis_time_ms = round((time.perf_counter() - inicio) * 1000, 1)
            return result

        # 2. Analizar según tipo
        if result.file.file_type in ("pdf",):
            self._analyze_pdf(result, path)
        elif result.file.file_type in ("xlsx", "xls"):
            self._analyze_excel(result, path)

        # 3. Calcular confianza general
        result.overall_confidence = self._compute_overall_confidence(result)

        result.analysis_time_ms = round((time.perf_counter() - inicio) * 1000, 1)
        return result

    def to_extraction_context(self, analysis: DocumentAnalysis) -> ExtractionContext:
        """Convierte un DocumentAnalysis a ExtractionContext para ParserPDF.

        Extrae las pistas más relevantes del análisis estructural
        para que ParserPDF pueda adaptar su estrategia de extracción
        sin tener que re-analizar el documento.
        """
        return ExtractionContext(
            rotation_hint=analysis.orientation.rotation,
            rotation_confidence=analysis.orientation.confidence,
            needs_ocr=analysis.needs_ocr if analysis.needs_ocr else None,
            layout_hint=list(analysis.layout.columns) if analysis.layout.confidence >= 0.5 else None,
            layout_confidence=analysis.layout.confidence,
            format_hint=(
                FormatoCodigo(analysis.code.code_format)
                if analysis.code.code_format
                else None
            ),
            confidence=analysis.overall_confidence,
            analysis_source="DocumentAnalyzer",
        )

    # ------------------------------------------------------------------
    # File analysis
    # ------------------------------------------------------------------

    def _analyze_file(self, path: Path) -> FileInfo:
        is_valid, msg = validar_archivo(path)
        suffix = path.suffix.lower().lstrip(".")
        return FileInfo(
            file_path=str(path),
            file_name=path.name,
            file_type=suffix if suffix in ("pdf", "xlsx", "xls") else suffix,
            file_size_bytes=path.stat().st_size,
            is_valid=is_valid,
            validation_message=msg,
        )

    # ------------------------------------------------------------------
    # PDF analysis
    # ------------------------------------------------------------------

    def _analyze_pdf(self, result: DocumentAnalysis, path: Path) -> None:
        """Analiza un PDF en múltiples dimensiones."""
        try:
            with pdfplumber.open(path) as pdf:
                n_paginas = len(pdf.pages)

                # Recopilar texto nativo de todas las páginas
                todas_lineas: list[str] = []
                todas_words: list[dict] = []
                tabla_info: list[bool] = []

                for page in pdf.pages:
                    texto = page.extract_text() or ""
                    if texto.strip():
                        todas_lineas.extend(texto.split("\n"))

                    words = page.extract_words() or []
                    todas_words.extend(words)

                    tables = page.extract_tables() or []
                    tabla_info.append(len(tables) > 0)

                # 2a. Text hygiene — normalizar líneas antes de cualquier análisis
                #     para que LayoutDetector y demás analizadores reciban texto
                #     más limpio (OCR spacing, espacios múltiples, invisibles).
                lineas_normalizadas, norm_actions = normalize_text_lines(
                    todas_lineas,
                )
                result.text_normalized = len(lineas_normalizadas) != len(todas_lineas) or \
                    lineas_normalizadas != todas_lineas
                result.normalization_actions = norm_actions

                # 2b. Text analysis (sobre líneas normalizadas)
                self._analyze_text(result, lineas_normalizadas)

                # 2c. Orientation (native text — original words, no afectado por normalización)
                self._analyze_orientation_native(result, todas_words)

                # 2d. Rotation normalization — si hay rotación 180° con suficiente
                #     confianza, corregir líneas ANTES de layout/códigos/separador.
                lineas_analisis = self._normalize_lines(
                    lineas_normalizadas, result.orientation,
                )
                result.rotation_corrected_before_layout = (
                    lineas_analisis is not lineas_normalizadas
                )

                # 2e. Tables
                self._analyze_tables(result, tabla_info)

                # 2f. Code format (sobre líneas normalizadas + rotación)
                self._analyze_code_format(result, lineas_analisis)

                # 2g. Separator (sobre líneas normalizadas + rotación)
                self._analyze_separator(result, lineas_analisis)

                # 2h. Layout (sobre líneas normalizadas + rotación)
                self._analyze_layout(result, lineas_analisis)

                # 2i. OCR necessity
                self._analyze_ocr_necessity(result, lineas_analisis, n_paginas)

        except Exception as e:
            result.warnings.append(f"Error analizando PDF: {e}")

    # ------------------------------------------------------------------
    # Excel analysis
    # ------------------------------------------------------------------

    def _analyze_excel(self, result: DocumentAnalysis, path: Path) -> None:
        """Analiza un archivo Excel."""
        try:
            import pandas as pd

            if result.file.file_type == "xlsx":
                try:
                    dfs = pd.read_excel(path, sheet_name=None)
                    todas_lineas: list[str] = []
                    for sheet_name, df in dfs.items():
                        for row in df.astype(str).values:
                            linea = " ".join(str(v) for v in row if str(v) != "nan")
                            if linea.strip():
                                todas_lineas.append(linea)
                except Exception:
                    result.warnings.append("No se pudieron leer todas las hojas del Excel")
                    return
            else:
                result.warnings.append("Formato Excel no soportado")
                return

            result.text = TextAnalysis(
                has_native_text=True,
                line_count=len(todas_lineas),
                sample_lines=todas_lineas[:10],
                details=f"Excel con {len(todas_lineas)} líneas extraídas",
            )

            self._analyze_code_format(result, todas_lineas)
            self._analyze_separator(result, todas_lineas)
            self._analyze_layout(result, todas_lineas)

        except ImportError:
            result.warnings.append("pandas no disponible para análisis Excel")
        except Exception as e:
            result.warnings.append(f"Error analizando Excel: {e}")

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_lines(
        lineas: list[str],
        orientation: OrientationAnalysis,
    ) -> list[str]:
        """Normaliza líneas para análisis si hay rotación 180°.

        Cuando un PDF está rotado 180°, pdfplumber extrae palabras con
        caracteres invertidos (e.g. "ovitca" → "activo"). Esta función
        revierte cada palabra para que LayoutDetector y demás analizadores
        reciban texto con orientación correcta.

        Si no hay rotación o la confianza es insuficiente, retorna las
        líneas originales sin modificar.

        Returns:
            (lineas_normalizadas, fue_corregido)
        """
        if (
            orientation.rotation == 180
            and orientation.confidence >= ROTATION_CORRECTION_THRESHOLD
        ):
            return [
                " ".join(w[::-1] for w in l.split())
                for l in lineas
            ]
        return lineas

    # ------------------------------------------------------------------
    # Analysis dimensions
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze_text(result: DocumentAnalysis, lineas: list[str]) -> None:
        result.text = TextAnalysis(
            has_native_text=len(lineas) > 0,
            line_count=len(lineas),
            sample_lines=lineas[:10],
            details=f"{len(lineas)} líneas extraídas de texto nativo"
            if lineas else "Sin texto nativo disponible",
        )

    @staticmethod
    def _analyze_orientation_native(
        result: DocumentAnalysis, words: list[dict],
    ) -> None:
        if not words:
            result.orientation = OrientationAnalysis(
                rotation=0, confidence=0.0, method="no_words",
                details="Sin palabras para analizar orientación",
            )
            return

        orient_result: OrientationResult = detectar_orientacion_words(words)
        result.orientation = OrientationAnalysis(
            rotation=orient_result.rotation,
            confidence=orient_result.confidence,
            method="word_inversion" if orient_result.rotation == 180 else "native",
            details=orient_result.reason,
        )
        if orient_result.rotation == 180:
            result.warnings.append(
                f"Documento detectado con rotación 180° "
                f"(confianza={orient_result.confidence:.2f})"
            )

    @staticmethod
    def _analyze_tables(result: DocumentAnalysis, tabla_info: list[bool]) -> None:
        paginas_con_tablas = sum(1 for t in tabla_info if t)
        result.tables = TableAnalysis(
            has_tables=paginas_con_tablas > 0,
            table_count=paginas_con_tablas,
            confidence=min(1.0, paginas_con_tablas / max(len(tabla_info), 1) * 2),
            details=(
                f"{paginas_con_tablas}/{len(tabla_info)} páginas con tablas"
                if tabla_info else "Sin tablas detectadas"
            ),
        )

    @staticmethod
    def _analyze_code_format(
        result: DocumentAnalysis, lineas: list[str],
    ) -> None:
        if not lineas:
            return

        # Tomar primeros tokens como candidatos a código
        tokens_muestra: list[str] = []
        for l in lineas[:60]:
            tokens = l.strip().split()
            if tokens:
                tokens_muestra.append(tokens[0])

        if not tokens_muestra:
            return

        formato = _detectar_formato_codigo(tokens_muestra)

        # Detectar si realmente hay códigos (no solo sin_codigo)
        tiene_codigos = formato != FormatoCodigo.SIN_CODIGO

        # Recopilar ejemplos de códigos encontrados
        codigos_ejemplo: list[str] = []
        for t in tokens_muestra:
            if t and not t.isalpha() and len(t) >= 3:
                if codigos_ejemplo.count(t) < 2:
                    codigos_ejemplo.append(t)
                    if len(codigos_ejemplo) >= 10:
                        break

        # Confianza: si el formato dominante tiene >= 40% de la muestra
        total = len(tokens_muestra)
        if total > 0:
            conteo = sum(1 for t in tokens_muestra if t and not t.isalpha())
            confianza = min(1.0, conteo / max(total, 1) * 1.5)
        else:
            confianza = 0.0

        result.code = CodeAnalysis(
            has_codes=tiene_codigos,
            code_format=formato.value if tiene_codigos else None,
            confidence=round(confianza, 2),
            sample_codes=codigos_ejemplo[:5],
            details=(
                f"Códigos detectados: {formato.value} "
                f"(confianza={confianza:.2f})"
                if tiene_codigos
                else "No se detectaron códigos de cuenta"
            ),
        )

    @staticmethod
    def _analyze_separator(
        result: DocumentAnalysis, lineas: list[str],
    ) -> None:
        if not lineas:
            return

        muestra_montos: list[str] = []
        for l in lineas[:80]:
            muestra_montos.extend(PATRON_MONTOS.findall(l))

        if not muestra_montos:
            return

        sep = _detectar_separador_miles(muestra_montos)

        # Calcular confianza: qué tan consistente es la detección
        puntos = sum(1 for m in muestra_montos if "." in m)
        comas = sum(1 for m in muestra_montos if "," in m)
        total_con_sep = puntos + comas
        if total_con_sep > 0:
            max_sep = max(puntos, comas)
            confianza = min(1.0, max_sep / total_con_sep * 1.2)
        else:
            confianza = 0.5

        result.separator = SeparatorAnalysis(
            separator=sep,
            confidence=round(confianza, 2),
            details=(
                f"Separador de miles: '{sep}' "
                f"(confianza={confianza:.2f}, "
                f"{puntos} puntos, {comas} comas)"
            ),
        )

    def _analyze_layout(
        self, result: DocumentAnalysis, lineas: list[str],
    ) -> None:
        if not lineas:
            return
        result.layout = self._layout_detector.detect(lineas)

    @staticmethod
    def _analyze_ocr_necessity(
        result: DocumentAnalysis, lineas: list[str], n_paginas: int,
    ) -> None:
        needs_ocr = (
            n_paginas > 0
            and len(lineas) < n_paginas * 3
        )
        result.needs_ocr = needs_ocr
        if needs_ocr:
            result.warnings.append(
                f"Documento probablemente escaneado: "
                f"{len(lineas)} líneas para {n_paginas} páginas "
                f"(esperadas ~{n_paginas * 15})"
            )

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_overall_confidence(result: DocumentAnalysis) -> float:
        """Estima la confianza general del análisis.

        Combina las confianzas individuales ponderando más
        las dimensiones críticas (texto, código, layout).
        """
        if not result.file.is_valid:
            return 0.0

        pesos = {
            "text": 0.25,
            "code": 0.20,
            "separator": 0.10,
            "layout": 0.20,
            "orientation": 0.10,
            "tables": 0.05,
            "file": 0.10,
        }

        confianza = 0.0

        # Text: si tiene texto nativo, alta confianza
        text_conf = 0.8 if result.text.has_native_text else 0.2
        confianza += text_conf * pesos["text"]

        # Code
        confianza += result.code.confidence * pesos["code"]

        # Separator
        confianza += result.separator.confidence * pesos["separator"]

        # Layout
        confianza += result.layout.confidence * pesos["layout"]

        # Orientation
        confianza += result.orientation.confidence * pesos["orientation"]

        # Tables
        confianza += result.tables.confidence * pesos["tables"]

        # File (si es válido)
        confianza += 1.0 * pesos["file"]

        return round(confianza, 2)

    # ------------------------------------------------------------------
    # CLI de prueba
    # ------------------------------------------------------------------


def main():
    import json
    import sys

    if len(sys.argv) < 2:
        print("Uso: python -m parsers.analyzer <ruta_al_documento>")
        sys.exit(1)

    analyzer = DocumentAnalyzer()
    result = analyzer.analyze(sys.argv[1])
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
