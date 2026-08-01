from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocumentType(str, Enum):
    BALANCE = "BALANCE"
    ESTADO_RESULTADOS = "ESTADO_RESULTADOS"
    ESTADO_PATRIMONIO = "ESTADO_PATRIMONIO"
    ESTADO_FLUJO = "ESTADO_FLUJO"
    NOTAS = "NOTAS"
    OTRO = "OTRO"


class Family(str, Enum):
    PDF_ESTANDAR = "PDF_ESTANDAR"
    EXCEL_SII = "EXCEL_SII"
    PDF_LIBRE = "PDF_LIBRE"
    EEFF_AUDITADOS = "EEFF_AUDITADOS"
    BALANCE_SIMPLE = "BALANCE_SIMPLE"
    CLASIFICADO = "CLASIFICADO"
    DESCONOCIDO = "DESCONOCIDO"


class LayoutType(str, Enum):
    VERTICAL = "VERTICAL"
    HORIZONTAL = "HORIZONTAL"
    TABULAR = "TABULAR"
    LIBRE = "LIBRE"
    DESCONOCIDO = "DESCONOCIDO"


class CodePattern(str, Enum):
    GUION = "GUION"
    PUNTO = "PUNTO"
    COMPACTO = "COMPACTO"
    NUMERICO = "NUMERICO"
    SIN_CODIGO = "SIN_CODIGO"
    DESCONOCIDO = "DESCONOCIDO"


class NumericPattern(str, Enum):
    CHILENO = "CHILENO"
    DECIMAL = "DECIMAL"
    ENTERO = "ENTERO"
    PARENTESIS = "PARENTESIS"
    SIGNO = "SIGNO"
    DESCONOCIDO = "DESCONOCIDO"


class ColumnType(str, Enum):
    CODIGO = "CODIGO"
    NOMBRE = "NOMBRE"
    DEBE = "DEBE"
    HABER = "HABER"
    ACTIVO = "ACTIVO"
    PASIVO = "PASIVO"
    PERDIDA = "PERDIDA"
    GANANCIA = "GANANCIA"
    MONTO = "MONTO"
    SALDO = "SALDO"
    DESCONOCIDO = "DESCONOCIDO"


@dataclass
class FormatSignature:
    document_type: DocumentType = DocumentType.OTRO
    family: Family = Family.DESCONOCIDO
    confidence: float = 0.0
    layout: LayoutType = LayoutType.DESCONOCIDO
    orientation: str = "portrait"
    columns: list[ColumnType] = field(default_factory=list)
    code_pattern: CodePattern = CodePattern.DESCONOCIDO
    numeric_pattern: NumericPattern = NumericPattern.DESCONOCIDO
    has_tables: bool = False
    has_headers: bool = False
    has_totals: bool = False
    has_subtotals: bool = False
    ocr_required: bool = False
    company_name: str = ""
    page_count: int = 1
    estimated_accounts: int = 0
    estimated_sections: int = 0

    @property
    def is_identified(self) -> bool:
        return self.family != Family.DESCONOCIDO and self.confidence > 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type.value,
            "family": self.family.value,
            "confidence": round(self.confidence, 4),
            "layout": self.layout.value,
            "orientation": self.orientation,
            "columns": [c.value for c in self.columns],
            "code_pattern": self.code_pattern.value,
            "numeric_pattern": self.numeric_pattern.value,
            "has_tables": self.has_tables,
            "has_headers": self.has_headers,
            "has_totals": self.has_totals,
            "has_subtotals": self.has_subtotals,
            "ocr_required": self.ocr_required,
            "company_name": self.company_name,
            "page_count": self.page_count,
            "estimated_accounts": self.estimated_accounts,
            "estimated_sections": self.estimated_sections,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FormatSignature:
        return cls(
            document_type=DocumentType(data.get("document_type", "OTRO")),
            family=Family(data.get("family", "DESCONOCIDO")),
            confidence=data.get("confidence", 0.0),
            layout=LayoutType(data.get("layout", "DESCONOCIDO")),
            orientation=data.get("orientation", "portrait"),
            columns=[ColumnType(c) for c in data.get("columns", [])],
            code_pattern=CodePattern(data.get("code_pattern", "DESCONOCIDO")),
            numeric_pattern=NumericPattern(data.get("numeric_pattern", "DESCONOCIDO")),
            has_tables=data.get("has_tables", False),
            has_headers=data.get("has_headers", False),
            has_totals=data.get("has_totals", False),
            has_subtotals=data.get("has_subtotals", False),
            ocr_required=data.get("ocr_required", False),
            company_name=data.get("company_name", ""),
            page_count=data.get("page_count", 1),
            estimated_accounts=data.get("estimated_accounts", 0),
            estimated_sections=data.get("estimated_sections", 0),
        )

    def summary(self) -> str:
        parts = [
            f"Documento: {self.document_type.value}",
            f"Familia:   {self.family.value}",
            f"Layout:    {self.layout.value} / {self.orientation}",
            f"Códigos:   {self.code_pattern.value}",
            f"Números:   {self.numeric_pattern.value}",
            f"Columnas:  {[c.value for c in self.columns]}",
            f"Confianza: {self.confidence:.0%}",
        ]
        if self.has_tables:
            parts.append("Tablas:    Sí")
        if self.has_headers:
            parts.append("Headers:   Sí")
        if self.has_totals:
            parts.append("Totales:   Sí")
        if self.has_subtotals:
            parts.append("Subtotales: Sí")
        if self.ocr_required:
            parts.append("OCR:       Requerido")
        if self.company_name:
            parts.append(f"Empresa:   {self.company_name}")
        return "\n".join(parts)
