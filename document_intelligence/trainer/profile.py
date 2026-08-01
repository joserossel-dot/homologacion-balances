"""Perfiles estructurales aprendidos por familia documental (Sprint 35).

Modelos de datos del Extractor Trainer:

  - `ColumnProfile`: una columna de la tabla (código, nombre, montos
    semánticos: activo, pasivo, pérdidas, ganancias, débitos, créditos).
  - `HeaderProfile`: encabezado aprendido (nº de filas, keywords).
  - `FooterProfile`: pie aprendido (filas finales, keywords, totales).
  - `TableProfile`: perfil completo de una familia (layout, patrones,
    columnas, filas de tabla, totales, validación).

Convención de posición de columnas:
  - Columnas "left" (CÓDIGO / NOMBRE): `position` = índice 0-based desde
    la izquierda en la fila de datos.
  - Columnas "right" (montos): `position` = índice 1-based desde la
    derecha (1 = último token de monto). Coherente con cómo ParserPDF
    consume los montos (desde el final de la fila).

Todo es serializable a JSON (to_dict / from_dict).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Léxicos de columnas (para el aprendizaje de tipos de columna)
# ---------------------------------------------------------------------------

# Keywords de encabezado → tipo de columna de monto.
AMOUNT_HEADER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "DEBE": ("debe", "débito", "debito", "débitos", "debitos",
             "cargo", "cargos", "movimiento deudor"),
    "HABER": ("haber", "haberes", "crédito", "credito", "créditos", "creditos",
              "abono", "abonos", "movimiento acreedor"),
    "ACTIVO": ("activo", "activos"),
    "PASIVO": ("pasivo", "pasivos"),
    "PERDIDA": ("perdida", "pérdida", "perdidas", "pérdidas",
                "gasto", "gastos", "costo", "costos"),
    "GANANCIA": ("ganancia", "ganancias", "ingreso", "ingresos",
                 "venta", "ventas", "utilidad", "utilidades"),
    "SALDO": ("saldo", "saldos"),
    "MONTO": ("monto", "montos", "importe", "importes", "valor", "valores"),
}

CODE_HEADER_KEYWORDS: tuple[str, ...] = (
    "codigo", "código", "cuenta", "cta", "code", "nro", "número", "numero", "n°",
)

NAME_HEADER_KEYWORDS: tuple[str, ...] = (
    "nombre", "name", "denominacion", "denominación", "glosa",
    "detalle", "concepto", "descripcion", "descripción", "rubro",
)

# Orden canónico de columnas de monto (para desambiguar posiciones).
AMOUNT_ORDER: tuple[str, ...] = (
    "DEBE", "HABER", "ACTIVO", "PASIVO", "PERDIDA", "GANANCIA", "SALDO", "MONTO",
)

COLUMN_LABELS: dict[str, str] = {
    "CODIGO": "Código",
    "NOMBRE": "Nombre",
    "ACTIVO": "Activo",
    "PASIVO": "Pasivo",
    "PERDIDA": "Pérdidas",
    "GANANCIA": "Ganancias",
    "DEBE": "Débitos",
    "HABER": "Créditos",
    "SALDO": "Saldo",
    "MONTO": "Monto",
}


# ---------------------------------------------------------------------------
# ColumnProfile
# ---------------------------------------------------------------------------

@dataclass
class ColumnProfile:
    """Una columna de la tabla aprendida por el trainer."""

    key: str
    label: str = ""
    side: str = "left"               # "left" | "right"
    position: Optional[int] = None   # 0-based (left) / 1-based (right)
    detection_rate: float = 0.0      # fracción de documentos donde se detectó
    docs: int = 0                    # nº de documentos donde se detectó

    def __post_init__(self) -> None:
        if not self.label:
            self.label = COLUMN_LABELS.get(self.key, self.key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "side": self.side,
            "position": self.position,
            "detection_rate": round(self.detection_rate, 4),
            "docs": self.docs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColumnProfile":
        return cls(
            key=data.get("key", ""),
            label=data.get("label", ""),
            side=data.get("side", "left"),
            position=data.get("position"),
            detection_rate=data.get("detection_rate", 0.0),
            docs=data.get("docs", 0),
        )


# ---------------------------------------------------------------------------
# HeaderProfile / FooterProfile
# ---------------------------------------------------------------------------

@dataclass
class HeaderProfile:
    """Encabezado de la tabla aprendido por familia."""

    rows: int = 0                        # nº de filas de encabezado (moda)
    row_counts: dict[int, int] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)  # keywords aprendidos

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "row_counts": dict(self.row_counts),
            "keywords": list(self.keywords),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HeaderProfile":
        return cls(
            rows=data.get("rows", 0),
            row_counts={int(k): v for k, v in data.get("row_counts", {}).items()},
            keywords=list(data.get("keywords", [])),
        )


@dataclass
class FooterProfile:
    """Pie de la tabla aprendido por familia."""

    trailing_rows: int = 0               # filas no-contables al final (moda)
    totals_position: str = "NONE"        # TOP | MIDDLE | BOTTOM | NONE
    total_keywords: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trailing_rows": self.trailing_rows,
            "totals_position": self.totals_position,
            "total_keywords": list(self.total_keywords),
            "keywords": list(self.keywords),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FooterProfile":
        return cls(
            trailing_rows=data.get("trailing_rows", 0),
            totals_position=data.get("totals_position", "NONE"),
            total_keywords=list(data.get("total_keywords", [])),
            keywords=list(data.get("keywords", [])),
        )


# ---------------------------------------------------------------------------
# TableProfile
# ---------------------------------------------------------------------------

@dataclass
class TableProfile:
    """Perfil estructural completo de una familia documental."""

    family_id: str
    family_name: str = ""
    layout: str = "DESCONOCIDO"
    document_type: str = "OTRO"
    code_pattern: str = "DESCONOCIDO"
    numeric_pattern: str = "DESCONOCIDO"
    header_rows: int = 0
    table_start_row: int = 0
    table_end_row: int = 0
    columns: list[ColumnProfile] = field(default_factory=list)
    code_column: Optional[ColumnProfile] = None
    name_column: Optional[ColumnProfile] = None
    amount_columns: list[ColumnProfile] = field(default_factory=list)
    totals_pattern: str = "none"
    total_keywords: list[str] = field(default_factory=list)
    summary_position: str = "NONE"
    confidence: float = 0.0
    n_documents: int = 0
    docs_total: int = 0        # documentos parseables antes de filtrar outliers
    docs_outliers: int = 0     # excluidos por no coincidir con la estructura dominante
    header: Optional[HeaderProfile] = None
    footer: Optional[FooterProfile] = None
    validation: Optional[dict[str, Any]] = None
    generated_at: str = ""

    # ------------------------------------------------------------------
    # Acceso por tipo de columna
    # ------------------------------------------------------------------

    def column_for(self, key: str) -> Optional[ColumnProfile]:
        for col in self.amount_columns:
            if col.key == key:
                return col
        if self.code_column and self.code_column.key == key:
            return self.code_column
        if self.name_column and self.name_column.key == key:
            return self.name_column
        return None

    @property
    def activo(self) -> Optional[ColumnProfile]:
        return self.column_for("ACTIVO")

    @property
    def pasivo(self) -> Optional[ColumnProfile]:
        return self.column_for("PASIVO")

    @property
    def perdida(self) -> Optional[ColumnProfile]:
        return self.column_for("PERDIDA")

    @property
    def ganancia(self) -> Optional[ColumnProfile]:
        return self.column_for("GANANCIA")

    @property
    def debito(self) -> Optional[ColumnProfile]:
        return self.column_for("DEBE")

    @property
    def credito(self) -> Optional[ColumnProfile]:
        return self.column_for("HABER")

    @property
    def monto(self) -> Optional[ColumnProfile]:
        return self.column_for("MONTO")

    @property
    def saldo(self) -> Optional[ColumnProfile]:
        return self.column_for("SALDO")

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "family_name": self.family_name,
            "layout": self.layout,
            "document_type": self.document_type,
            "code_pattern": self.code_pattern,
            "numeric_pattern": self.numeric_pattern,
            "header_rows": self.header_rows,
            "table_start_row": self.table_start_row,
            "table_end_row": self.table_end_row,
            "columns": [c.to_dict() for c in self.columns],
            "code_column": self.code_column.to_dict() if self.code_column else None,
            "name_column": self.name_column.to_dict() if self.name_column else None,
            "amount_columns": [c.to_dict() for c in self.amount_columns],
            "totals_pattern": self.totals_pattern,
            "total_keywords": list(self.total_keywords),
            "summary_position": self.summary_position,
            "confidence": round(self.confidence, 4),
            "n_documents": self.n_documents,
            "docs_total": self.docs_total,
            "docs_outliers": self.docs_outliers,
            "header": self.header.to_dict() if self.header else None,
            "footer": self.footer.to_dict() if self.footer else None,
            "validation": self.validation,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableProfile":
        columns = [ColumnProfile.from_dict(c) for c in data.get("columns", [])]
        amount_columns = [
            ColumnProfile.from_dict(c) for c in data.get("amount_columns", [])
        ]
        return cls(
            family_id=data.get("family_id", ""),
            family_name=data.get("family_name", ""),
            layout=data.get("layout", "DESCONOCIDO"),
            document_type=data.get("document_type", "OTRO"),
            code_pattern=data.get("code_pattern", "DESCONOCIDO"),
            numeric_pattern=data.get("numeric_pattern", "DESCONOCIDO"),
            header_rows=data.get("header_rows", 0),
            table_start_row=data.get("table_start_row", 0),
            table_end_row=data.get("table_end_row", 0),
            columns=columns,
            code_column=(
                ColumnProfile.from_dict(data["code_column"])
                if data.get("code_column") else None
            ),
            name_column=(
                ColumnProfile.from_dict(data["name_column"])
                if data.get("name_column") else None
            ),
            amount_columns=amount_columns,
            totals_pattern=data.get("totals_pattern", "none"),
            total_keywords=list(data.get("total_keywords", [])),
            summary_position=data.get("summary_position", "NONE"),
            confidence=data.get("confidence", 0.0),
            n_documents=data.get("n_documents", 0),
            docs_total=data.get("docs_total", 0),
            docs_outliers=data.get("docs_outliers", 0),
            header=(
                HeaderProfile.from_dict(data["header"])
                if data.get("header") else None
            ),
            footer=(
                FooterProfile.from_dict(data["footer"])
                if data.get("footer") else None
            ),
            validation=data.get("validation"),
            generated_at=data.get("generated_at", ""),
        )
