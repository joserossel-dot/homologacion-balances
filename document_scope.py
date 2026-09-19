"""Selección explícita de páginas, sin OCR ni cambios al documento fuente."""
from io import BytesIO
import re

import pypdfium2 as pdfium


def contar_paginas_pdf(source) -> tuple[int, list[str]]:
    """Obtiene el número de páginas comprobable con respaldo entre pdfplumber y PDFium."""
    advertencias = []
    count_plumber = 0
    count_pdfium = 0
    error_plumber = None
    error_pdfium = None

    try:
        import pdfplumber
        if isinstance(source, (str, bytes)):
            if isinstance(source, str):
                with pdfplumber.open(source) as p:
                    count_plumber = len(p.pages)
            else:
                with pdfplumber.open(BytesIO(source)) as p:
                    count_plumber = len(p.pages)
        elif hasattr(source, "__fspath__"):
            with pdfplumber.open(str(source)) as p:
                count_plumber = len(p.pages)
        elif hasattr(source, "read") and hasattr(source, "seek"):
            pos = source.tell()
            with pdfplumber.open(source) as p:
                count_plumber = len(p.pages)
            source.seek(pos)
    except Exception as e:
        error_plumber = str(e)

    try:
        if isinstance(source, (str, bytes)):
            with pdfium.PdfDocument(source) as doc:
                count_pdfium = len(doc)
        elif hasattr(source, "__fspath__"):
            with pdfium.PdfDocument(str(source)) as doc:
                count_pdfium = len(doc)
        elif hasattr(source, "getvalue"):
            with pdfium.PdfDocument(source.getvalue()) as doc:
                count_pdfium = len(doc)
        elif hasattr(source, "read") and hasattr(source, "seek"):
            pos = source.tell()
            content = source.read()
            source.seek(pos)
            with pdfium.PdfDocument(content) as doc:
                count_pdfium = len(doc)
    except Exception as e:
        error_pdfium = str(e)

    if count_plumber > 0 and count_pdfium > 0:
        if count_plumber != count_pdfium:
            advertencias.append(
                f"Discrepancia en conteo de páginas: pdfplumber reportó {count_plumber} y PDFium reportó {count_pdfium}; se conserva {max(count_plumber, count_pdfium)}."
            )
        return max(count_plumber, count_pdfium), advertencias

    if count_pdfium > 0:
        if count_plumber == 0 and not error_plumber:
            advertencias.append(
                f"Lector principal reportó 0 páginas; PDFium recuperó {count_pdfium} páginas válidas."
            )
        return count_pdfium, advertencias

    if count_plumber > 0:
        return count_plumber, advertencias

    if error_plumber or error_pdfium:
        advertencias.append(
            f"No fue posible determinar el número de páginas: pdfplumber ({error_plumber or 'sin páginas'}), PDFium ({error_pdfium or 'sin páginas'})."
        )
    return 0, advertencias


def page_count(content: bytes) -> int:
    count, _ = contar_paginas_pdf(content)
    return count



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
