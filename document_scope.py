"""Selección explícita de páginas, sin OCR ni cambios al documento fuente."""
from io import BytesIO
import re

import pypdfium2 as pdfium


_PERIODO_BALANCE = re.compile(
    r"\bdesde\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+"
    r"hasta\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b",
    re.IGNORECASE,
)
_PIE_PAGINA_SOLO = re.compile(
    r"p[aá]gina\s+\d+\s+de\s+\d+", re.IGNORECASE,
)


def _extraer_textos_paginas(content: bytes) -> list[str]:
    """Lee el texto nativo por página sólo para sugerir alcance al usuario."""
    textos: list[str] = []
    try:
        with pdfium.PdfDocument(content) as doc:
            for page in doc:
                try:
                    textpage = page.get_textpage()
                    try:
                        textos.append(textpage.get_text_range() or "")
                    finally:
                        textpage.close()
                finally:
                    page.close()
    except Exception:
        return []
    return textos


def _es_pie_aislado(texto: str) -> bool:
    normalizado = re.sub(r"\s+", " ", texto or "").strip()
    return not normalizado or bool(
        len(normalizado) <= 80 and _PIE_PAGINA_SOLO.fullmatch(normalizado)
    )


def sugerir_periodos_balance(content: bytes) -> list[dict[str, object]]:
    """Sugiere grupos de páginas para períodos distintos sin aplicarlos.

    Sólo devuelve una sugerencia cuando el texto nativo expone al menos dos
    encabezados ``Desde ... hasta ...`` diferentes. La selección sigue siendo
    explícita: el analista debe elegirla y confirmar el formulario.
    """
    textos = _extraer_textos_paginas(content)
    encabezados: list[tuple[int, str]] = []
    for numero, texto in enumerate(textos, start=1):
        match = _PERIODO_BALANCE.search(texto)
        if match is None:
            continue
        etiqueta = f"{match.group(1)} a {match.group(2)}"
        if not encabezados or encabezados[-1][1] != etiqueta:
            encabezados.append((numero, etiqueta))
    if len(encabezados) < 2 or len({etiqueta for _, etiqueta in encabezados}) < 2:
        return []

    sugerencias: list[dict[str, object]] = []
    for indice, (inicio, etiqueta) in enumerate(encabezados):
        siguiente_inicio = (
            encabezados[indice + 1][0]
            if indice + 1 < len(encabezados) else len(textos) + 1
        )
        paginas = [
            pagina for pagina in range(inicio, siguiente_inicio)
            if not _es_pie_aislado(textos[pagina - 1])
        ]
        if paginas:
            sugerencias.append({"periodo": etiqueta, "paginas": paginas})
    return sugerencias


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
