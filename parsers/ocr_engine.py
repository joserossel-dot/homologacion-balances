"""Interfaz OCR pluggable + implementación Tesseract.

Envuelve las funciones de OCR del parser original.
"""

from __future__ import annotations

import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from PIL import Image

from parser_universal import (
    detectar_rotacion_osd as _detectar_rotacion_osd,
    detectar_rotacion_heuristica as _detectar_rotacion_heuristica,
    ocr_pagina as _ocr_pagina,
    TESSDATA_DIR,
)


class OcrEngine(ABC):
    @abstractmethod
    def ocr_page(self, image_path: Path, rotation: int = 0, lang: str = "spa") -> str:
        ...

    @abstractmethod
    def detect_rotation(self, image_path: Path) -> Optional[int]:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class TesseractEngine(OcrEngine):
    """Implementación con Tesseract (envuelve parser_universal)."""

    def __init__(
        self,
        tesseract_path: str | None = None,
        tessdata_dir: str | None = None,
        pdftoppm_path: str | None = None,
        dpi: int = 250,
        timeout_per_page: int = 120,
    ):
        self._tesseract = tesseract_path or "/usr/local/bin/tesseract"
        self._tessdata = tessdata_dir or TESSDATA_DIR
        self._pdftoppm = pdftoppm_path or "/usr/local/bin/pdftoppm"
        self._dpi = dpi
        self._timeout = timeout_per_page

    @property
    def name(self) -> str:
        return "tesseract"

    def ocr_page(self, image_path: Path, rotation: int = 0, lang: str = "spa") -> str:
        return _ocr_pagina(image_path, rotation)

    def detect_rotation(self, image_path: Path) -> Optional[int]:
        rot = _detectar_rotacion_osd(image_path)
        if rot is None:
            rot = _detectar_rotacion_heuristica(image_path)
        return rot

    def pdf_to_images(self, pdf_path: Path, page: int, tmpdir: Path) -> list[Path]:
        """Renderiza una página PDF a PNG."""
        prefix = tmpdir / f"pg{page}"
        subprocess.run(
            [self._pdftoppm, "-png", "-r", str(self._dpi),
             "-f", str(page), "-l", str(page),
             str(pdf_path), str(prefix)],
            capture_output=True, timeout=self._timeout,
        )
        return sorted(tmpdir.glob(f"pg{page}*.png"))

    def ocr_document(self, pdf_path: Path) -> tuple[list[str], int]:
        """OCR completo de un PDF página por página.

        Returns:
            (lineas, rotacion_aplicada)
        """
        import pdfplumber

        lineas: list[str] = []
        rotacion_global: Optional[int] = None

        with pdfplumber.open(pdf_path) as pdf:
            n_paginas = len(pdf.pages)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            for pagina in range(1, n_paginas + 1):
                imgs = self.pdf_to_images(pdf_path, pagina, tmpdir_path)
                if not imgs:
                    continue

                if rotacion_global is None:
                    rotacion_global = self.detect_rotation(imgs[0]) or 0

                texto = self.ocr_page(imgs[0], rotacion_global)
                lineas.extend(texto.split("\n"))

        return lineas, rotacion_global or 0
