"""Selección explícita de páginas, sin OCR ni cambios al documento fuente."""
from io import BytesIO
import re

import pypdfium2 as pdfium


def page_count(content: bytes) -> int:
    with pdfium.PdfDocument(content) as doc:
        return len(doc)


def parse_pages(text: str, count: int) -> list[int]:
    """Páginas humanas (base 1), en orden del original y sin duplicados."""
    if not text.strip():
        raise ValueError("Indique al menos una página, por ejemplo: 1, 3-5.")
    pages = set()
    for part in text.split(","):
        match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", part)
        if not match:
            raise ValueError("Use números y rangos separados por comas: 1, 3-5.")
        start, end = int(match[1]), int(match[2] or match[1])
        if not 1 <= start <= end <= count:
            raise ValueError(f"Seleccione páginas entre 1 y {count}, en rangos ascendentes.")
        pages.update(range(start, end + 1))
    return sorted(pages)


def select_pdf(content: bytes, pages: list[int]) -> bytes:
    count = page_count(content)
    if not pages or pages != sorted(set(pages)) or any(p < 1 or p > count for p in pages):
        raise ValueError("Selección de páginas inválida.")
    if pages == list(range(1, count + 1)):
        return content
    with pdfium.PdfDocument(content) as source, pdfium.PdfDocument.new() as target:
        target.import_pages(source, [p - 1 for p in pages])
        output = BytesIO()
        target.save(output)
        return output.getvalue()


def render_page(content: bytes, page: int) -> bytes:
    """Renderiza sólo la página solicitada, también en informes extensos."""
    with pdfium.PdfDocument(content) as doc:
        if not 1 <= page <= len(doc):
            raise ValueError("Página fuera del documento.")
        pdf_page = doc[page - 1]
        try:
            bitmap = pdf_page.render(scale=2)
            try:
                image = bitmap.to_pil()
                output = BytesIO()
                image.save(output, format="PNG")
                return output.getvalue()
            finally:
                bitmap.close()
        finally:
            pdf_page.close()
