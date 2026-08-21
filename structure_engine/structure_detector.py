from __future__ import annotations
import re
from collections import Counter


TOTAL_PATTERNS = re.compile(
    r"^(total|suma|subtotal|sumas)\s|"
    r"\s(total|suma|subtotal)\s|"
    r"\s(total|suma|subtotal)$|"
    r"^(total|suma|subtotal|sumas)$|"
    r"^total\s|"
    r"^subtotal\s",
    re.IGNORECASE,
)

HEADER_PATTERNS = [
    (re.compile(r"^activo\s+(corriente|circulante)", re.IGNORECASE), "ACTIVO_CORRIENTE"),
    (re.compile(r"^activo\s+(no\s+corriente|fijo|inmovilizado)", re.IGNORECASE), "ACTIVO_NO_CORRIENTE"),
    (re.compile(r"^activo", re.IGNORECASE), "ACTIVO"),
    (re.compile(r"^pasivo\s+(corriente|circulante)", re.IGNORECASE), "PASIVO_CORRIENTE"),
    (re.compile(r"^pasivo\s+(no\s+corriente|largo\s+plazo)", re.IGNORECASE), "PASIVO_NO_CORRIENTE"),
    (re.compile(r"^pasivo", re.IGNORECASE), "PASIVO"),
    (re.compile(r"^patrimonio", re.IGNORECASE), "PATRIMONIO"),
    (re.compile(r"^(resultado|estado de resultado)", re.IGNORECASE), "RESULTADO"),
    (re.compile(r"^ingreso", re.IGNORECASE), "INGRESOS"),
    (re.compile(r"^costo", re.IGNORECASE), "COSTOS"),
    (re.compile(r"^gasto", re.IGNORECASE), "GASTOS"),
]

COLUMN_PATTERNS = {
    "activo": "ACTIVO",
    "pasivo": "PASIVO",
    "perdida": "PERDIDA",
    "ganancia": "GANANCIA",
    "deudor": "DEUDOR",
    "acreedor": "ACREEDOR",
}


class StructureDetector:

    @staticmethod
    def detect_type(nombre: str, es_total: bool, amount: float) -> str:
        name = nombre.strip()
        if TOTAL_PATTERNS.search(name) or es_total:
            return "S"
        for pattern, _ in HEADER_PATTERNS:
            if pattern.match(name):
                return "H"
        if amount != 0:
            return "D"
        return "I"

    @staticmethod
    def detect_section(nombre: str, column: str = "") -> str:
        name = nombre.strip()
        for pattern, section in HEADER_PATTERNS:
            if pattern.match(name):
                return section
        col_lower = column.lower().strip()
        if col_lower in COLUMN_PATTERNS:
            return COLUMN_PATTERNS[col_lower]
        return ""

    @staticmethod
    def detect_code_format(cuentas: list[dict]) -> str:
        formats: list[str] = []
        for c in cuentas:
            code = str(c.get("codigo", c.get("account_code", "")) or "")
            if not code:
                continue
            if "." in code:
                formats.append("PUNTO")
            elif "-" in code:
                formats.append("GUION")
            elif code.isdigit():
                formats.append("COMPACTO")
            else:
                formats.append("OTRO")
        if not formats:
            return "SIN_CODIGO"
        return Counter(formats).most_common(1)[0][0]

    @staticmethod
    def detect_column_layout(cuentas: list[dict]) -> str:
        columns = set()
        for c in cuentas:
            col = str(c.get("origen_columna", c.get("source_column", "")) or "").lower().strip()
            if col in COLUMN_PATTERNS:
                columns.add(COLUMN_PATTERNS[col])
        if len(columns) >= 3:
            return "MULTI_COLUMN"
        if "ACTIVO" in columns and "PASIVO" in columns:
            return "DOUBLE_COLUMN"
        if "PERDIDA" in columns and "GANANCIA" in columns:
            return "INCOME_COLUMNS"
        if "DEUDOR" in columns or "ACREEDOR" in columns:
            return "DEBIT_CREDIT"
        if columns:
            return list(columns)[0]
        return "SINGLE_COLUMN"

    @staticmethod
    def detect_level(code: str, nombre: str) -> int:
        if not code:
            indent = len(nombre) - len(nombre.lstrip())
            if indent > 0:
                return indent // 2
            return 0
        if "." in code:
            return max(0, len(code.split(".")) - 1)
        if "-" in code:
            return max(0, len(code.split("-")) - 1)
        if code.isdigit():
            return len(code) // 2
        return 0

    @staticmethod
    def find_repeated_patterns(
        type_sequence: str,
        min_length: int = 2,
        max_length: int = 20,
    ) -> list[tuple[str, int]]:
        patterns: dict[str, int] = {}
        for length in range(min_length, min(max_length + 1, len(type_sequence) // 2 + 1)):
            seen: set[str] = set()
            for i in range(len(type_sequence) - length + 1):
                sub = type_sequence[i:i + length]
                if sub in seen:
                    continue
                seen.add(sub)
                count = type_sequence.count(sub)
                if count >= 2:
                    patterns[sub] = count
        sorted_patterns = sorted(patterns.items(), key=lambda x: -x[1] * len(x[0]))
        return sorted_patterns[:20]

    @staticmethod
    def compute_type_sequence(nodes: list) -> str:
        return "".join(
            n.structural_type if hasattr(n, "structural_type") else ""
            for n in nodes
        )
