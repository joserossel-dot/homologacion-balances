"""Contexto de procesamiento documental (Sprint 31).

`DocumentProcessingContext` agrupa todo lo que la etapa de análisis
documental produce ANTES de que el parser comience a extraer cuentas:

  - signature:      FormatSignature producido por FormatAnalyzer
  - extractor_type: decisión de ExtractorFactory (solo decide, no extrae)
  - processing_notes: notas del análisis
  - warnings:       advertencias (p. ej. fallo del analyzer)
  - confidence:     confianza global del análisis
  - elapsed_ms:     tiempo que tardó el análisis

Además expone helpers de serialización y de presentación (logging y UI).

La función `analyze_document_preview()` es la puerta de entrada: lee solo
las primeras páginas del PDF, analiza, decide extractor y mide tiempo.
NUNCA lanza excepción: si algo falla devuelve un Context con la advertencia
correspondiente (backward compatibility — el parser sigue funcionando igual).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .analyzer import FormatAnalyzer
from .factory import ExtractorFactory, ExtractorType
from .signature import FormatSignature

logger = logging.getLogger("document_intelligence.context")

# Cuántas páginas del PDF se leen para el análisis (solo texto nativo, sin OCR).
PREVIEW_MAX_PAGES = 3

# Cabeceras legibles para la UI (FASE 5).
_DOCUMENT_TYPE_LABELS = {
    "BALANCE": "Balance Tributario",
    "ESTADO_RESULTADOS": "Estado de Resultados",
    "ESTADO_PATRIMONIO": "Estado de Patrimonio",
    "ESTADO_FLUJO": "Estado de Flujo",
    "NOTAS": "Notas",
    "OTRO": "Otro",
}


@dataclass
class DocumentProcessingContext:
    """Contexto generado por la etapa de análisis documental."""

    pdf_path: Path
    signature: FormatSignature
    extractor_type: ExtractorType
    processing_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    elapsed_ms: int = 0

    # ------------------------------------------------------------------
    # Presentación
    # ------------------------------------------------------------------

    def to_log_block(self) -> str:
        """Bloque multi-línea para logging (FASE 4)."""
        sig = self.signature
        lines = [
            "------------------------------------------------",
            f"Documento: {self.pdf_path.name}",
            f"Tipo: {sig.document_type.value}",
            f"Familia: {sig.family.value}",
            f"Layout: {sig.layout.value} / {sig.orientation}",
            f"Orientación: {sig.orientation}",
            f"Columnas: {[c.value for c in sig.columns]}",
            f"Patrón código: {sig.code_pattern.value}",
            f"Patrón numérico: {sig.numeric_pattern.value}",
            f"Confianza: {sig.confidence:.0%}",
            f"Extractor seleccionado: {self.extractor_type.value}",
            f"Tiempo análisis: {self.elapsed_ms} ms",
            "------------------------------------------------",
        ]
        return "\n".join(lines)

    def ui_summary(self) -> dict[str, str]:
        """Resumen plano para la sección de UI (FASE 5)."""
        sig = self.signature
        return {
            "Documento": _DOCUMENT_TYPE_LABELS.get(
                sig.document_type.value, sig.document_type.value
            ),
            "Familia": sig.family.value,
            "Formato": f"PDF {sig.layout.value}",
            "Columnas": str(len(sig.columns)),
            "Layout": sig.layout.value,
            "OCR": "Sí" if sig.ocr_required else "No",
            "Extractor": self.extractor_type.value,
            "Confianza": f"{sig.confidence:.0%}",
        }

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "pdf_path": str(self.pdf_path),
            "signature": self.signature.to_dict(),
            "extractor_type": self.extractor_type.value,
            "processing_notes": list(self.processing_notes),
            "warnings": list(self.warnings),
            "confidence": round(self.confidence, 4),
            "elapsed_ms": self.elapsed_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentProcessingContext":
        return cls(
            pdf_path=Path(data.get("pdf_path", ".")),
            signature=FormatSignature.from_dict(data.get("signature", {})),
            extractor_type=ExtractorType(data.get("extractor_type", "DESCONOCIDO")),
            processing_notes=list(data.get("processing_notes", [])),
            warnings=list(data.get("warnings", [])),
            confidence=data.get("confidence", 0.0),
            elapsed_ms=data.get("elapsed_ms", 0),
        )


# ---------------------------------------------------------------------------
# Helper público: análisis previo al parseo
# ---------------------------------------------------------------------------

def _extraer_preview(
    path: Path,
    max_pages: int = PREVIEW_MAX_PAGES,
) -> list[str]:
    """Lee solo las primeras páginas del PDF (texto nativo, sin OCR)."""
    try:
        import pdfplumber
    except ImportError:
        return []

    lineas: list[str] = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages[:max_pages]:
                texto = page.extract_text() or ""
                if texto.strip():
                    lineas.extend(texto.split("\n"))
    except Exception:
        return []
    return lineas


def analyze_document_preview(
    path: str | Path,
    analyzer: Optional[FormatAnalyzer] = None,
    factory: Optional[ExtractorFactory] = None,
    max_pages: int = PREVIEW_MAX_PAGES,
) -> DocumentProcessingContext:
    """Analiza un PDF y produce el DocumentProcessingContext.

    Flujo:
      1. Lee el preview (primeras páginas, texto nativo)
      2. FormatAnalyzer genera el FormatSignature
      3. ExtractorFactory decide el extractor (NO extrae todavía)
      4. Se mide el tiempo total

    Nunca lanza excepción. Si el analyzer falla se retorna un Context con
    family DESCONOCIDO, extractor DESCONOCIDO y la advertencia registrada
    (FASE 7 — backward compatibility).
    """
    path = Path(path)
    t0 = time.perf_counter()

    processing_notes: list[str] = []
    warnings: list[str] = []

    lineas = _extraer_preview(path, max_pages=max_pages)
    if not lineas:
        processing_notes.append(
            "No se pudo extraer texto nativo del preview — "
            "el análisis documental queda DESCONOCIDO."
        )

    try:
        _analyzer = analyzer or FormatAnalyzer()
        sig = _analyzer.analyze(lineas)
    except Exception as exc:  # noqa: BLE001 — fallback deliberado
        logger.debug("FormatAnalyzer falló: %s", exc, exc_info=True)
        sig = FormatSignature()
        warnings.append(f"FormatAnalyzer falló: {exc}")

    try:
        _factory = factory or ExtractorFactory()
        extractor_type = _factory.decide_parser(sig)
    except Exception as exc:  # noqa: BLE001
        logger.debug("ExtractorFactory falló: %s", exc, exc_info=True)
        extractor_type = ExtractorType.UNKNOWN
        warnings.append(f"ExtractorFactory falló: {exc}")

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return DocumentProcessingContext(
        pdf_path=path,
        signature=sig,
        extractor_type=extractor_type,
        processing_notes=processing_notes,
        warnings=warnings,
        confidence=sig.confidence,
        elapsed_ms=elapsed_ms,
    )
