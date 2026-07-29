from __future__ import annotations
import re
from .models import AccountNode, HierarchyTree


TOTAL_PATTERNS = re.compile(
    r"^(total|suma|subtotal|sumas)\s|"
    r"\s(total|suma|subtotal)\s|"
    r"\s(total|suma|subtotal)$|"
    r"^total\s|"
    r"^subtotal\s",
    re.IGNORECASE,
)

HEADER_PATTERNS = re.compile(
    r"^(activo|pasivo|patrimonio|resultado|ingresos|costos|gastos|"
    r"activo corriente|activo no corriente|pasivo corriente|pasivo no corriente|"
    r"ingresos de actividades|costos de|gastos de|"
    r"estado de situacion|estado de resultados)",
    re.IGNORECASE,
)

SUBTOTAL_NAMES = re.compile(
    r"total activo|total pasivo|total patrimonio|"
    r"total corriente|total no corriente|"
    r"total disponible|total existencias|"
    r"total cliente|total deudores|"
    r"total ingresos|total costos|total gastos|"
    r"total del activo|total del pasivo|"
    r"utilidad del ejercicio|perdida del ejercicio|"
    r"resultado del ejercicio",
    re.IGNORECASE,
)


def _infer_level(codigo: str) -> int:
    if not codigo:
        return -1
    if "." in codigo:
        return len(codigo.split("."))
    if "-" in codigo:
        return len(codigo.split("-"))
    if codigo.isdigit():
        return len(codigo) // 2
    return -1


def _infer_indent(nombre: str) -> int:
    leading = len(nombre) - len(nombre.lstrip())
    return leading


def _classify_node(nombre: str, es_total: bool, amount: float) -> tuple[bool, bool, bool]:
    nombre_stripped = nombre.strip()
    is_total = False
    is_subtotal = False
    is_header = False

    if TOTAL_PATTERNS.search(nombre_stripped) or es_total:
        is_total = True
        if re.search(r"subtotal|suma", nombre_stripped, re.IGNORECASE):
            is_subtotal = True

    if SUBTOTAL_NAMES.search(nombre_stripped):
        is_subtotal = True

    if HEADER_PATTERNS.match(nombre_stripped) and amount == 0.0:
        is_header = True

    return is_total, is_subtotal, is_header


def _section_from_name(nombre: str) -> str:
    n = nombre.strip().lower()
    if any(w in n for w in ["activo corriente", "activo circulante"]):
        return "ACTIVO_CORRIENTE"
    if any(w in n for w in ["activo no corriente", "activo fijo", "activo inmovilizado"]):
        return "ACTIVO_NO_CORRIENTE"
    if re.match(r"^activo", n):
        return "ACTIVO"
    if any(w in n for w in ["pasivo corriente", "pasivo circulante"]):
        return "PASIVO_CORRIENTE"
    if any(w in n for w in ["pasivo no corriente", "pasivo largo plazo", "exigible largo plazo"]):
        return "PASIVO_NO_CORRIENTE"
    if re.match(r"^pasivo", n):
        return "PASIVO"
    if re.match(r"^patrimonio", n):
        return "PATRIMONIO"
    if any(w in n for w in ["resultado", "estado de resultado", "ganancia", "perdida"]):
        return "RESULTADO"
    if re.match(r"^ingreso", n):
        return "INGRESOS"
    if re.match(r"^costo", n):
        return "COSTOS"
    if re.match(r"^gasto", n):
        return "GASTOS"
    return ""


def _section_from_std_code(standard_code: str | None) -> str:
    if not standard_code:
        return ""
    if standard_code.startswith("AC."):
        return "ACTIVO_CORRIENTE"
    if standard_code.startswith("ANC."):
        return "ACTIVO_NO_CORRIENTE"
    if standard_code.startswith("PC."):
        return "PASIVO_CORRIENTE"
    if standard_code.startswith("PNC."):
        return "PASIVO_NO_CORRIENTE"
    if standard_code.startswith("PAT."):
        return "PATRIMONIO"
    if standard_code.startswith("ING."):
        return "INGRESOS"
    if standard_code.startswith("COS."):
        return "COSTOS"
    if standard_code.startswith("GAS."):
        return "GASTOS"
    if standard_code.startswith("ER."):
        return "RESULTADO"
    if standard_code.startswith("RES."):
        return "RESULTADO"
    return ""


def build_hierarchy(
    accounts_raw: list[dict],
    accounts_classified: list[dict] | None = None,
) -> HierarchyTree:
    tree = HierarchyTree()
    nodes: list[AccountNode] = []
    std_codes: dict[int, str] = {}

    if accounts_classified:
        for acct in accounts_classified:
            if isinstance(acct, dict) and "source_page" in acct:
                page = acct.get("source_page", 0)
                std_codes[page] = acct.get("standard_code") or acct.get("final_code") or ""

    for i, raw in enumerate(accounts_raw):
        if isinstance(raw, dict):
            nombre = raw.get("nombre") or raw.get("account_name") or ""
            monto = raw.get("monto") or raw.get("classification_amount") or raw.get("amount") or 0.0
            codigo = raw.get("codigo") or raw.get("account_code") or ""
            col = raw.get("origen_columna") or raw.get("source_column") or raw.get("nature") or ""
            es_total = raw.get("es_total", False)
            linea = raw.get("linea") or raw.get("source_line") or i

            if isinstance(monto, str):
                try:
                    monto = float(monto.replace(".", "").replace(",", "."))
                except ValueError:
                    monto = 0.0
            monto = float(monto or 0.0)
        else:
            nombre = str(getattr(raw, "nombre", getattr(raw, "account_name", "")))
            monto = float(getattr(raw, "monto", getattr(raw, "classification_amount", 0)) or 0.0)
            codigo = str(getattr(raw, "codigo", getattr(raw, "account_code", "")) or "")
            col = str(getattr(raw, "origen_columna", getattr(raw, "source_column", getattr(raw, "nature", ""))) or "")
            es_total = bool(getattr(raw, "es_total", False))
            linea = int(getattr(raw, "linea", getattr(raw, "source_line", i)))

        std_code = std_codes.get(linea, "")
        is_total, is_subtotal, is_header = _classify_node(nombre, es_total, monto)
        section = _section_from_name(nombre) or _section_from_std_code(std_code)

        node = AccountNode(
            account_code=codigo,
            account_name=nombre.strip(),
            amount=monto,
            level=_infer_level(codigo) if _infer_level(codigo) >= 0 else _infer_indent(nombre),
            line_number=linea,
            source_column=col,
            es_total=es_total or is_total,
            es_header=is_header,
            es_subtotal=is_subtotal,
            naturaleza=section or col,
        )
        nodes.append(node)

    _build_tree_structure(nodes, tree)
    _classify_nodes(tree)
    return tree


def _build_tree_structure(nodes: list[AccountNode], tree: HierarchyTree):
    if not nodes:
        return

    stack: list[AccountNode] = []
    prev_line = -5

    for node in nodes:
        tree.all_nodes.append(node)

        if node.line_number <= prev_line:
            gap = prev_line - node.line_number
            if gap > 1:
                node.level = 0

        indent = node.level
        if indent < 0:
            indent = 0

        while stack and stack[-1].level >= indent:
            stack.pop()

        if stack:
            parent = stack[-1]
            parent.add_child(node)
        else:
            tree.roots.append(node)

        stack.append(node)
        prev_line = node.line_number


def _classify_nodes(tree: HierarchyTree):
    for node in tree.all_nodes:
        if node.es_header:
            tree.header_nodes.append(node)
        elif node.es_total and node.es_subtotal:
            tree.subtotal_nodes.append(node)
        elif node.es_total:
            tree.total_nodes.append(node)
        elif node.is_leaf:
            tree.detail_nodes.append(node)


def detect_section_boundaries(tree: HierarchyTree) -> dict[str, list[AccountNode]]:
    sections: dict[str, list[AccountNode]] = {}
    current_section = "UNKNOWN"
    section_keywords = [
        ("ACTIVO_CORRIENTE", re.compile(r"^activo\s+(corriente|circulante)", re.IGNORECASE)),
        ("ACTIVO_NO_CORRIENTE", re.compile(r"^activo\s+(no\s+corriente|fijo|inmovilizado)", re.IGNORECASE)),
        ("ACTIVO", re.compile(r"^activo(\s|$)", re.IGNORECASE)),
        ("PASIVO_CORRIENTE", re.compile(r"^pasivo\s+(corriente|circulante)", re.IGNORECASE)),
        ("PASIVO_NO_CORRIENTE", re.compile(r"^pasivo\s+(no\s+corriente|largo\s+plazo)", re.IGNORECASE)),
        ("PASIVO", re.compile(r"^pasivo(\s|$)", re.IGNORECASE)),
        ("PATRIMONIO", re.compile(r"^patrimonio(\s|$)", re.IGNORECASE)),
        ("RESULTADO", re.compile(r"^(resultado|estado de resultado)", re.IGNORECASE)),
        ("INGRESOS", re.compile(r"^ingreso", re.IGNORECASE)),
        ("COSTOS", re.compile(r"^costo", re.IGNORECASE)),
        ("GASTOS", re.compile(r"^gasto", re.IGNORECASE)),
    ]

    for node in tree.all_nodes:
        name = node.account_name.strip()
        matched = False
        for section_name, pattern in section_keywords:
            if pattern.match(name):
                current_section = section_name
                matched = True
                break
        if not matched and (node.naturaleza and node.naturaleza in [s[0] for s in section_keywords]):
            current_section = node.naturaleza

        sections.setdefault(current_section, []).append(node)

    return sections
