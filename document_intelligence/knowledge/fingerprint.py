"""DocumentFingerprint — huella digital determinística de un documento.

Resume un documento en un conjunto fijo de características comparables:

  - Estructura: layout, orientación, páginas, columnas
  - Contenido: keywords de cabecera/pie, densidades (tabla/texto/número)
  - Formato: tipo de documento, patrón de código, patrón numérico
  - Totales: posición del resumen
  - signature_hash: hash SHA-1 de las características estables

Todo es serializable (to_dict / from_dict) y determinístico: el mismo
documento produce siempre el mismo fingerprint.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..signature import FormatSignature

# Palabras que no aportan identidad de formato en cabecera/pie.
_STOPWORDS = {
    "balance", "general", "desde", "hasta", "periodo", "período", "pagina",
    "página", "empresa", "razon", "razón", "social", "rut", "tributario",
    "tributarios", "clasificado", "individual", "consolidado", "de", "del",
    "el", "la", "los", "las", "en", "y", "al", "año", "2015", "2016", "2017",
    "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026",
}

_NUM_TOKEN = re.compile(r"^\d[\d.,\s]*$")


def _keyword_lower(line: str) -> list[str]:
    tokens = []
    for tok in re.findall(r"[A-Za-zÑñÁÉÍÓÚáéíóú]{4,}", line):
        low = tok.lower()
        if low not in _STOPWORDS:
            tokens.append(low)
    return tokens


@dataclass
class DocumentFingerprint:
    """Huella determinística de un documento para matching y clustering."""

    layout: str = "DESCONOCIDO"
    orientation: str = "portrait"
    page_count: int = 1
    column_count: int = 0
    column_names: list[str] = field(default_factory=list)
    header_keywords: list[str] = field(default_factory=list)
    footer_keywords: list[str] = field(default_factory=list)
    table_density: float = 0.0
    text_density: float = 0.0
    numeric_density: float = 0.0
    document_type: str = "OTRO"
    code_pattern: str = "DESCONOCIDO"
    numeric_pattern: str = "DESCONOCIDO"
    total_patterns: int = 0
    summary_position: str = "NONE"
    signature_hash: str = ""

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "layout": self.layout,
            "orientation": self.orientation,
            "page_count": self.page_count,
            "column_count": self.column_count,
            "column_names": list(self.column_names),
            "header_keywords": list(self.header_keywords),
            "footer_keywords": list(self.footer_keywords),
            "table_density": round(self.table_density, 4),
            "text_density": round(self.text_density, 4),
            "numeric_density": round(self.numeric_density, 4),
            "document_type": self.document_type,
            "code_pattern": self.code_pattern,
            "numeric_pattern": self.numeric_pattern,
            "total_patterns": self.total_patterns,
            "summary_position": self.summary_position,
            "signature_hash": self.signature_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentFingerprint":
        return cls(
            layout=data.get("layout", "DESCONOCIDO"),
            orientation=data.get("orientation", "portrait"),
            page_count=data.get("page_count", 1),
            column_count=data.get("column_count", 0),
            column_names=list(data.get("column_names", [])),
            header_keywords=list(data.get("header_keywords", [])),
            footer_keywords=list(data.get("footer_keywords", [])),
            table_density=data.get("table_density", 0.0),
            text_density=data.get("text_density", 0.0),
            numeric_density=data.get("numeric_density", 0.0),
            document_type=data.get("document_type", "OTRO"),
            code_pattern=data.get("code_pattern", "DESCONOCIDO"),
            numeric_pattern=data.get("numeric_pattern", "DESCONOCIDO"),
            total_patterns=data.get("total_patterns", 0),
            summary_position=data.get("summary_position", "NONE"),
            signature_hash=data.get("signature_hash", ""),
        )

    # ------------------------------------------------------------------
    # Hashes
    # ------------------------------------------------------------------

    def canonical_string(self) -> str:
        """Cadena canónica de las características estables."""
        return "|".join([
            self.layout,
            self.orientation,
            str(self.page_count),
            str(self.column_count),
            ",".join(sorted(self.column_names)),
            self.document_type,
            self.code_pattern,
            self.numeric_pattern,
            self.summary_position,
            f"{self.table_density:.2f}",
            f"{self.text_density:.2f}",
            f"{self.numeric_density:.2f}",
        ])

    def compute_hash(self) -> str:
        """SHA-1 de la cadena canónica (identidad de formato)."""
        self.signature_hash = hashlib.sha1(
            self.canonical_string().encode("utf-8")
        ).hexdigest()
        return self.signature_hash

    def partial_hash(self) -> str:
        """Hash solo de las características estructurales principales."""
        core = "|".join([
            self.layout,
            self.orientation,
            str(self.column_count),
            ",".join(sorted(self.column_names)),
            self.document_type,
            self.code_pattern,
            self.numeric_pattern,
        ])
        return hashlib.sha1(core.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        signature: FormatSignature,
        lines: list[str],
    ) -> "DocumentFingerprint":
        """Construye la huella desde un FormatSignature + líneas del preview."""
        no_vacias = [l for l in lines if l.strip()]
        header_lines = no_vacias[:8]
        footer_lines = no_vacias[-5:]

        header_kw = _keywords(header_lines)
        footer_kw = _keywords(footer_lines)

        densidades = _compute_densities(no_vacias)
        total_patterns = _count_total_patterns(no_vacias)
        summary_pos = _detect_summary_position(no_vacias)

        fp = cls(
            layout=signature.layout.value,
            orientation=signature.orientation,
            page_count=signature.page_count,
            column_count=len(signature.columns),
            column_names=[c.value for c in signature.columns],
            header_keywords=header_kw,
            footer_keywords=footer_kw,
            table_density=densidades["table"],
            text_density=densidades["text"],
            numeric_density=densidades["numeric"],
            document_type=signature.document_type.value,
            code_pattern=signature.code_pattern.value,
            numeric_pattern=signature.numeric_pattern.value,
            total_patterns=total_patterns,
            summary_position=summary_pos,
        )
        fp.compute_hash()
        return fp

    def with_densities(self, lines: list[str]) -> "DocumentFingerprint":
        """Recalcula densidades/keywords/totales sobre nuevas líneas."""
        no_vacias = [l for l in lines if l.strip()]
        self.header_keywords = _keywords(no_vacias[:8])
        self.footer_keywords = _keywords(no_vacias[-5:])
        d = _compute_densities(no_vacias)
        self.table_density = d["table"]
        self.text_density = d["text"]
        self.numeric_density = d["numeric"]
        self.total_patterns = _count_total_patterns(no_vacias)
        self.summary_position = _detect_summary_position(no_vacias)
        self.compute_hash()
        return self


def _keywords(lines: list[str], limit: int = 8) -> list[str]:
    seen: list[str] = []
    for line in lines:
        for tok in _keyword_lower(line):
            if tok not in seen:
                seen.append(tok)
            if len(seen) >= limit:
                return seen
    return seen


def _compute_densities(lines: list[str]) -> dict[str, float]:
    if not lines:
        return {"table": 0.0, "text": 0.0, "numeric": 0.0}

    text_lines = 0
    table_lines = 0
    total_tokens = 0
    numeric_tokens = 0

    for line in lines:
        tokens = line.split()
        if not tokens:
            continue
        total_tokens += len(tokens)
        numeric_tokens += sum(1 for t in tokens if _NUM_TOKEN.match(t))
        if any(_NUM_TOKEN.match(t) for t in tokens) and any(
            not _NUM_TOKEN.match(t) for t in tokens
        ):
            text_lines += 1
        num_fields = sum(1 for t in tokens if _NUM_TOKEN.match(t))
        if num_fields >= 2:
            table_lines += 1

    return {
        "table": round(table_lines / max(len(lines), 1), 4),
        "text": round(text_lines / max(len(lines), 1), 4),
        "numeric": round(numeric_tokens / max(total_tokens, 1), 4),
    }


_CODE_RE = re.compile(r"^\d[\d\-. ]+$")
_TOTAL_RE = re.compile(r"^(total|subtotal|suma)", re.IGNORECASE)


def _count_total_patterns(lines: list[str]) -> int:
    count = 0
    for line in lines[:80]:
        first = line.split()[0] if line.split() else ""
        if _CODE_RE.match(first):
            count += 1
    return count


def _detect_summary_position(lines: list[str]) -> str:
    idx = [i for i, l in enumerate(lines) if _TOTAL_RE.match(l.strip())]
    if not idx:
        return "NONE"
    n = len(lines)
    first = idx[0]
    last = idx[-1]
    if first / max(n, 1) < 0.3:
        return "TOP"
    if last / max(n, 1) > 0.7:
        return "BOTTOM"
    return "MIDDLE"


# ---------------------------------------------------------------------------
# Construcción directa desde un archivo
# ---------------------------------------------------------------------------

PREVIEW_MAX_PAGES = 3


def extract_preview_lines(
    path: str | Any,
    max_pages: int = PREVIEW_MAX_PAGES,
) -> list[str]:
    """Extrae líneas de preview de un PDF o Excel (texto nativo, sin OCR)."""
    from pathlib import Path

    path = Path(path)
    suffix = path.suffix.lower()
    lineas: list[str] = []

    if suffix == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            return []
        try:
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages[:max_pages]:
                    texto = page.extract_text() or ""
                    if texto.strip():
                        lineas.extend(texto.split("\n"))
        except Exception:
            return []
    elif suffix in (".xls", ".xlsx", ".xlsm"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(c) for c in row if c is not None]
                    if cells:
                        lineas.append(" ".join(cells))
                if len(lineas) >= 200:
                    break
            wb.close()
        except Exception:
            try:
                import pandas as pd
                dfs = pd.read_excel(str(path), sheet_name=None, nrows=200)
                lineas = []
                for df in dfs.values():
                    for _, row in df.iterrows():
                        cells = [str(v) for v in row if pd.notna(v)]
                        if cells:
                            lineas.append(" ".join(cells))
            except Exception:
                return []
    else:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            lineas = [l for l in text.split("\n") if l.strip()]
        except Exception:
            return []

    return [l for l in lineas if l.strip()][:200]


def fingerprint_from_file(
    path: str | Any,
    signature: Optional[FormatSignature] = None,
    max_pages: int = PREVIEW_MAX_PAGES,
) -> DocumentFingerprint:
    """Construye el fingerprint de un archivo.

    Si no se pasa un FormatSignature, lo analiza con FormatAnalyzer.
    """
    from pathlib import Path

    from ..analyzer import FormatAnalyzer

    lines = extract_preview_lines(path, max_pages=max_pages)

    if signature is None:
        signature = FormatAnalyzer().analyze(lines)

    if path.suffix.lower() == ".pdf" and signature.page_count <= 1:
        try:
            import pdfplumber
            with pdfplumber.open(str(Path(path))) as pdf:
                signature.page_count = len(pdf.pages)
        except Exception:
            pass

    return DocumentFingerprint.build(signature, lines)
