from __future__ import annotations

from pathlib import Path
from .models import ParserName, ParserRecommendation


OCR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
EXCEL_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}
PDF_EXTENSION = ".pdf"

# Based on empirical observations from existing benchmarks
ESTIMATED_TIME_MS: dict[ParserName, tuple[int, int]] = {
    ParserName.UNIVERSAL: (1500, 5000),
    ParserName.CORE2: (2000, 6000),
    ParserName.EXCEL: (500, 2000),
    ParserName.OCR: (15000, 60000),
}


class ParserSelector:

    def recommend(
        self,
        file_path: str,
        ocr_probability: float = 0.0,
        pages: int = 1,
        is_pdf_text: bool = True,
        document_type: str | None = None,
    ) -> ParserRecommendation:
        ext = Path(file_path).suffix.lower()

        if ext in EXCEL_EXTENSIONS:
            return self._recommend_excel(file_path, pages)

        if ext in OCR_EXTENSIONS:
            return self._recommend_ocr(file_path, pages, ocr_probability)

        if ext == PDF_EXTENSION:
            return self._recommend_pdf(file_path, ocr_probability, pages, is_pdf_text)

        fallback = ParserRecommendation(
            parser_name=ParserName.DESCONOCIDO,
            confidence=0.1,
            reason=f"Formato no soportado: {ext}",
            estimated_time_ms=0,
            signals=[f"unknown_extension:{ext}"],
        )
        return fallback

    def _recommend_pdf(
        self,
        file_path: str,
        ocr_probability: float,
        pages: int,
        is_pdf_text: bool,
    ) -> ParserRecommendation:
        if ocr_probability > 0.7:
            high_ocr = ocr_probability > 0.9
            return ParserRecommendation(
                parser_name=ParserName.OCR,
                confidence=0.85 if high_ocr else 0.7,
                reason="Alta probabilidad de OCR (escaneado sin texto)",
                fallback_parser=ParserName.CORE2,
                needs_ocr=True,
                estimated_time_ms=ESTIMATED_TIME_MS[ParserName.OCR][0] * max(pages, 1),
                signals=[
                    f"ocr_probability={ocr_probability:.2f}",
                    f"pages={pages}",
                ],
            )

        if not is_pdf_text and ocr_probability > 0.3:
            return ParserRecommendation(
                parser_name=ParserName.CORE2,
                confidence=0.75,
                reason="PDF con poco texto detectable, puede necesitar OCR",
                fallback_parser=ParserName.OCR,
                needs_ocr=False,
                estimated_time_ms=ESTIMATED_TIME_MS[ParserName.CORE2][0] * max(pages, 1),
                signals=[f"low_text_density,ocr_prob={ocr_probability:.2f}"],
            )

        return ParserRecommendation(
            parser_name=ParserName.UNIVERSAL,
            confidence=0.95,
            reason="PDF con texto extraíble, parser Universal recomendado",
            fallback_parser=ParserName.CORE2,
            needs_ocr=False,
            estimated_time_ms=ESTIMATED_TIME_MS[ParserName.UNIVERSAL][0] * max(pages, 1),
            signals=[f"pdf_text_available,pages={pages}"],
        )

    def _recommend_excel(self, file_path: str, pages: int) -> ParserRecommendation:
        return ParserRecommendation(
            parser_name=ParserName.EXCEL,
            confidence=0.9,
            reason="Archivo Excel detectado",
            fallback_parser=ParserName.UNIVERSAL,
            needs_ocr=False,
            estimated_time_ms=ESTIMATED_TIME_MS[ParserName.EXCEL][0],
            signals=["excel_format"],
        )

    def _recommend_ocr(
        self,
        file_path: str,
        pages: int,
        ocr_probability: float,
    ) -> ParserRecommendation:
        return ParserRecommendation(
            parser_name=ParserName.OCR,
            confidence=0.8,
            reason="Formato de imagen, requiere OCR",
            fallback_parser=None,
            needs_ocr=True,
            estimated_time_ms=ESTIMATED_TIME_MS[ParserName.OCR][0] * max(pages, 1),
            signals=[f"image_format,ocr_prob={ocr_probability:.2f}"],
        )
