from __future__ import annotations

from knowledge.financial_graph import FinancialGraph
from knowledge.financial_node import FinancialNode
from knowledge.financial_tree import FinancialTree


_ACCOUNTS: list[dict[str, object]] = [
    {"code": "ACTIVO", "name": "Activo", "class_": "activo", "subclass": "", "is_group": True, "nature": "deudora", "presentation_order": 1},
    {"code": "AC", "name": "Activo Corriente", "class_": "activo", "subclass": "corriente", "parent_code": "ACTIVO", "is_group": True, "nature": "deudora", "presentation_order": 2},
    {"code": "AC.01", "name": "Caja y Bancos", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "tags": ["efectivo", "liquido"], "kpi_groups": ["liquidez"], "presentation_order": 3, "description": "Disponible en caja y cuentas bancarias"},
    {"code": "AC.02", "name": "Inversiones Corto Plazo", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "tags": ["inversiones", "liquido"], "kpi_groups": ["liquidez"], "presentation_order": 4},
    {"code": "AC.03", "name": "Clientes", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "tags": ["deudores", "comercial"], "kpi_groups": ["liquidez", "rotacion"], "presentation_order": 5, "description": "Deudores por ventas al crédito"},
    {"code": "AC.04", "name": "Documentos por Cobrar", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "tags": ["deudores", "comercial"], "kpi_groups": ["liquidez", "rotacion"], "presentation_order": 6},
    {"code": "AC.05", "name": "Inventarios", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "tags": ["existencias"], "kpi_groups": ["liquidez", "rotacion"], "presentation_order": 7},
    {"code": "AC.06", "name": "Relacionadas CP", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "tags": ["partes_relacionadas"], "kpi_groups": ["partes_relacionadas"], "presentation_order": 8},
    {"code": "AC.06S", "name": "Cta. Cte. Socios / Retiros (Activo)", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "semantic_types": ["contra_equity"], "tags": ["socios", "partes_relacionadas"], "kpi_groups": ["partes_relacionadas", "ajuste_patrimonial"], "presentation_order": 9},
    {"code": "AC.07", "name": "Otras Cuentas por Cobrar CP", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "tags": ["deudores"], "kpi_groups": ["liquidez", "otros"], "presentation_order": 10},
    {"code": "AC.08", "name": "Otros Activos Corrientes", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "tags": ["otros"], "kpi_groups": ["liquidez", "otros"], "presentation_order": 11},
    {"code": "AC.09", "name": "Activos Biológicos CP", "class_": "activo", "subclass": "corriente", "parent_code": "AC", "nature": "deudora", "signo_normal": 1, "tags": ["biologicos", "agricola"], "kpi_groups": ["liquidez", "biologicos"], "presentation_order": 12},
    {"code": "ANC", "name": "Activo No Corriente", "class_": "activo", "subclass": "no_corriente", "parent_code": "ACTIVO", "is_group": True, "nature": "deudora", "presentation_order": 13},
    {"code": "ANC.01", "name": "Activo Fijo", "class_": "activo", "subclass": "no_corriente", "parent_code": "ANC", "nature": "deudora", "signo_normal": 1, "contra_accounts": ["depreciacion_acumulada"], "semantic_types": ["ppe"], "tags": ["propiedad_planta_equipo", "depreciable"], "kpi_groups": ["inversion", "depreciacion"], "ifrs": ["NIC 16"], "presentation_order": 14, "description": "Propiedades, planta y equipo"},
    {"code": "ANC.02", "name": "Propiedades de Inversión", "class_": "activo", "subclass": "no_corriente", "parent_code": "ANC", "nature": "deudora", "signo_normal": 1, "tags": ["inversiones", "inmobiliario"], "kpi_groups": ["inversion"], "ifrs": ["NIC 40"], "presentation_order": 15},
    {"code": "ANC.03", "name": "Intangibles", "class_": "activo", "subclass": "no_corriente", "parent_code": "ANC", "nature": "deudora", "signo_normal": 1, "contra_accounts": ["amortizacion_acumulada"], "semantic_types": ["intangible"], "tags": ["intangible", "amortizable"], "kpi_groups": ["inversion", "depreciacion"], "ifrs": ["NIC 38"], "presentation_order": 16},
    {"code": "ANC.04", "name": "Inversiones Permanentes", "class_": "activo", "subclass": "no_corriente", "parent_code": "ANC", "nature": "deudora", "signo_normal": 1, "tags": ["inversiones"], "kpi_groups": ["inversion"], "presentation_order": 17},
    {"code": "ANC.05", "name": "Relacionadas LP", "class_": "activo", "subclass": "no_corriente", "parent_code": "ANC", "nature": "deudora", "signo_normal": 1, "tags": ["partes_relacionadas"], "kpi_groups": ["partes_relacionadas"], "presentation_order": 18},
    {"code": "ANC.06", "name": "Otros Activos No Corrientes", "class_": "activo", "subclass": "no_corriente", "parent_code": "ANC", "nature": "deudora", "signo_normal": 1, "tags": ["otros"], "kpi_groups": ["otros"], "presentation_order": 19},
    {"code": "ANC.07", "name": "Activos Biológicos LP", "class_": "activo", "subclass": "no_corriente", "parent_code": "ANC", "nature": "deudora", "signo_normal": 1, "tags": ["biologicos", "agricola"], "kpi_groups": ["biologicos"], "presentation_order": 20},
    {"code": "ANC.08", "name": "Plusvalía (Goodwill)", "class_": "activo", "subclass": "no_corriente", "parent_code": "ANC", "nature": "deudora", "signo_normal": 1, "tags": ["intangible", "plusvalia"], "kpi_groups": ["inversion"], "ifrs": ["NIIF 3"], "presentation_order": 21},
    {"code": "PASIVO", "name": "Pasivo", "class_": "pasivo", "subclass": "", "is_group": True, "nature": "acreedora", "presentation_order": 22},
    {"code": "PC", "name": "Pasivo Corriente", "class_": "pasivo", "subclass": "corriente", "parent_code": "PASIVO", "is_group": True, "nature": "acreedora", "presentation_order": 23},
    {"code": "PC.01", "name": "Proveedores", "class_": "pasivo", "subclass": "corriente", "parent_code": "PC", "nature": "acreedora", "signo_normal": 1, "tags": ["comercial", "proveedores"], "kpi_groups": ["liquidez", "rotacion"], "presentation_order": 24, "description": "Acreedores comerciales"},
    {"code": "PC.02", "name": "Obligaciones Bancarias CP", "class_": "pasivo", "subclass": "corriente", "parent_code": "PC", "nature": "acreedora", "signo_normal": 1, "tags": ["deuda_financiera"], "kpi_groups": ["endeudamiento", "liquidez"], "presentation_order": 25},
    {"code": "PC.03", "name": "Leasing CP", "class_": "pasivo", "subclass": "corriente", "parent_code": "PC", "nature": "acreedora", "signo_normal": 1, "tags": ["deuda_financiera", "leasing"], "kpi_groups": ["endeudamiento"], "ifrs": ["NIIF 16"], "presentation_order": 26},
    {"code": "PC.04", "name": "Factoring", "class_": "pasivo", "subclass": "corriente", "parent_code": "PC", "nature": "acreedora", "signo_normal": 1, "tags": ["deuda_financiera", "factoring"], "kpi_groups": ["endeudamiento"], "presentation_order": 27},
    {"code": "PC.05", "name": "Impuestos por Pagar", "class_": "pasivo", "subclass": "corriente", "parent_code": "PC", "nature": "acreedora", "signo_normal": 1, "tags": ["fiscal", "impuestos"], "kpi_groups": ["liquidez", "fiscal"], "presentation_order": 28, "description": "Obligaciones tributarias"},
    {"code": "PC.06", "name": "Remuneraciones por Pagar", "class_": "pasivo", "subclass": "corriente", "parent_code": "PC", "nature": "acreedora", "signo_normal": 1, "tags": ["remuneraciones", "personal"], "kpi_groups": ["liquidez"], "presentation_order": 29},
    {"code": "PC.07", "name": "Relacionadas CP", "class_": "pasivo", "subclass": "corriente", "parent_code": "PC", "nature": "acreedora", "signo_normal": 1, "tags": ["partes_relacionadas"], "kpi_groups": ["partes_relacionadas"], "presentation_order": 30},
    {"code": "PC.08", "name": "Otros Pasivos Corrientes", "class_": "pasivo", "subclass": "corriente", "parent_code": "PC", "nature": "acreedora", "signo_normal": 1, "tags": ["otros"], "kpi_groups": ["liquidez", "otros"], "presentation_order": 31},
    {"code": "PNC", "name": "Pasivo No Corriente", "class_": "pasivo", "subclass": "no_corriente", "parent_code": "PASIVO", "is_group": True, "nature": "acreedora", "presentation_order": 32},
    {"code": "PNC.01", "name": "Obligaciones Bancarias LP", "class_": "pasivo", "subclass": "no_corriente", "parent_code": "PNC", "nature": "acreedora", "signo_normal": 1, "tags": ["deuda_financiera"], "kpi_groups": ["endeudamiento", "solvencia"], "presentation_order": 33},
    {"code": "PNC.02", "name": "Leasing LP", "class_": "pasivo", "subclass": "no_corriente", "parent_code": "PNC", "nature": "acreedora", "signo_normal": 1, "tags": ["deuda_financiera", "leasing"], "kpi_groups": ["endeudamiento", "solvencia"], "ifrs": ["NIIF 16"], "presentation_order": 34},
    {"code": "PNC.03", "name": "Bonos", "class_": "pasivo", "subclass": "no_corriente", "parent_code": "PNC", "nature": "acreedora", "signo_normal": 1, "tags": ["deuda_financiera", "bonos"], "kpi_groups": ["endeudamiento", "solvencia"], "presentation_order": 35},
    {"code": "PNC.04", "name": "Relacionadas LP", "class_": "pasivo", "subclass": "no_corriente", "parent_code": "PNC", "nature": "acreedora", "signo_normal": 1, "tags": ["partes_relacionadas"], "kpi_groups": ["partes_relacionadas", "solvencia"], "presentation_order": 36},
    {"code": "PNC.05", "name": "Otros Pasivos LP", "class_": "pasivo", "subclass": "no_corriente", "parent_code": "PNC", "nature": "acreedora", "signo_normal": 1, "tags": ["otros"], "kpi_groups": ["solvencia", "otros"], "presentation_order": 37},
    {"code": "PATRIMONIO", "name": "Patrimonio", "class_": "patrimonio", "subclass": "", "is_group": True, "nature": "acreedora", "presentation_order": 38},
    {"code": "PAT.01", "name": "Capital", "class_": "patrimonio", "subclass": "", "parent_code": "PATRIMONIO", "nature": "acreedora", "signo_normal": 1, "tags": ["capital", "aporte"], "kpi_groups": ["solvencia", "rentabilidad"], "presentation_order": 39},
    {"code": "PAT.02", "name": "Reservas", "class_": "patrimonio", "subclass": "", "parent_code": "PATRIMONIO", "nature": "acreedora", "signo_normal": 1, "tags": ["reservas"], "kpi_groups": ["solvencia"], "presentation_order": 40},
    {"code": "PAT.03", "name": "Utilidades Retenidas", "class_": "patrimonio", "subclass": "", "parent_code": "PATRIMONIO", "nature": "acreedora", "signo_normal": 1, "tags": ["resultados_acumulados"], "kpi_groups": ["solvencia", "rentabilidad"], "presentation_order": 41},
    {"code": "PAT.04", "name": "Resultado del Ejercicio", "class_": "patrimonio", "subclass": "", "parent_code": "PATRIMONIO", "nature": "acreedora", "signo_normal": 1, "tags": ["resultado"], "kpi_groups": ["rentabilidad"], "presentation_order": 42},
    {"code": "PAT.05", "name": "Participaciones No Controladoras", "class_": "patrimonio", "subclass": "", "parent_code": "PATRIMONIO", "nature": "acreedora", "signo_normal": 1, "tags": ["no_controladora", "minoritarios"], "kpi_groups": ["solvencia"], "ifrs": ["NIIF 10"], "presentation_order": 43},
    {"code": "RESULTADO", "name": "Resultado", "class_": "resultado", "subclass": "", "is_group": True, "nature": "deudora", "presentation_order": 44},
    {"code": "ER.01", "name": "Ventas", "class_": "resultado", "subclass": "ingresos", "parent_code": "RESULTADO", "nature": "acreedora", "signo_normal": 1, "semantic_types": ["revenue"], "tags": ["ingresos", "operacional"], "kpi_groups": ["rentabilidad", "eficiencia"], "ifrs": ["NIIF 15"], "presentation_order": 45},
    {"code": "ER.02", "name": "Costo de Ventas", "class_": "resultado", "subclass": "costos", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": -1, "semantic_types": ["expense"], "tags": ["costos", "operacional"], "kpi_groups": ["rentabilidad", "eficiencia"], "presentation_order": 46},
    {"code": "ER.03", "name": "Margen Bruto", "class_": "resultado", "subclass": "subtotal", "parent_code": "RESULTADO", "is_group": True, "nature": "acreedora", "signo_normal": 1, "tags": ["subtotal"], "kpi_groups": ["rentabilidad"], "presentation_order": 47},
    {"code": "ER.04", "name": "Gastos de Administración", "class_": "resultado", "subclass": "gastos", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": -1, "semantic_types": ["expense"], "tags": ["gastos", "operacional", "administracion"], "kpi_groups": ["rentabilidad", "eficiencia"], "presentation_order": 48},
    {"code": "ER.05", "name": "Gastos de Venta", "class_": "resultado", "subclass": "gastos", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": -1, "semantic_types": ["expense"], "tags": ["gastos", "operacional", "ventas"], "kpi_groups": ["rentabilidad", "eficiencia"], "presentation_order": 49},
    {"code": "ER.06", "name": "EBITDA", "class_": "resultado", "subclass": "subtotal", "parent_code": "RESULTADO", "is_group": True, "nature": "acreedora", "signo_normal": 1, "tags": ["subtotal", "ebitda"], "kpi_groups": ["rentabilidad", "eficiencia"], "presentation_order": 50},
    {"code": "ER.07", "name": "Depreciación y Amortización", "class_": "resultado", "subclass": "gastos", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": -1, "semantic_types": ["expense"], "tags": ["gastos", "no_efectivo", "depreciacion"], "kpi_groups": ["rentabilidad", "depreciacion"], "ifrs": ["NIC 16", "NIC 38"], "presentation_order": 51},
    {"code": "ER.08", "name": "Resultado Operacional", "class_": "resultado", "subclass": "subtotal", "parent_code": "RESULTADO", "is_group": True, "nature": "acreedora", "signo_normal": 1, "tags": ["subtotal"], "kpi_groups": ["rentabilidad"], "presentation_order": 52},
    {"code": "ER.09", "name": "Gastos Financieros", "class_": "resultado", "subclass": "gastos", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": -1, "semantic_types": ["expense"], "tags": ["gastos", "financiero"], "kpi_groups": ["rentabilidad", "endeudamiento"], "ifrs": ["NIC 23"], "presentation_order": 53},
    {"code": "ER.10", "name": "Impuesto a la Renta", "class_": "resultado", "subclass": "gastos", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": -1, "semantic_types": ["expense"], "tags": ["gastos", "fiscal", "impuestos"], "kpi_groups": ["rentabilidad", "fiscal"], "presentation_order": 54},
    {"code": "ER.11", "name": "Utilidad Neta", "class_": "resultado", "subclass": "subtotal", "parent_code": "RESULTADO", "is_group": True, "nature": "acreedora", "signo_normal": 1, "tags": ["subtotal"], "kpi_groups": ["rentabilidad"], "presentation_order": 55},
    {"code": "ER.12", "name": "Ingresos Financieros", "class_": "resultado", "subclass": "ingresos", "parent_code": "RESULTADO", "nature": "acreedora", "signo_normal": 1, "semantic_types": ["revenue"], "tags": ["ingresos", "financiero"], "kpi_groups": ["rentabilidad"], "ifrs": ["NIIF 9"], "presentation_order": 56},
    {"code": "ER.13", "name": "Otras Ganancias y Pérdidas", "class_": "resultado", "subclass": "otros", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": 1, "tags": ["otros", "no_operacional"], "kpi_groups": ["rentabilidad", "otros"], "presentation_order": 57},
    {"code": "ER.14", "name": "Corrección Monetaria y Reajustes", "class_": "resultado", "subclass": "otros", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": 1, "tags": ["reajustes", "no_operacional"], "kpi_groups": ["rentabilidad"], "presentation_order": 58},
    {"code": "ER.15", "name": "Diferencias de Cambio", "class_": "resultado", "subclass": "otros", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": 1, "tags": ["moneda_extranjera", "no_operacional"], "kpi_groups": ["rentabilidad"], "presentation_order": 59},
    {"code": "ER.16", "name": "Resultado Método Participación", "class_": "resultado", "subclass": "otros", "parent_code": "RESULTADO", "nature": "deudora", "signo_normal": 1, "tags": ["inversiones", "no_operacional"], "kpi_groups": ["rentabilidad"], "ifrs": ["NIC 28"], "presentation_order": 60},
]


def build_tree() -> FinancialTree:
    tree = FinancialTree()
    for data in _ACCOUNTS:
        node = FinancialNode(
            code=data["code"],
            name=data["name"],
            class_=data.get("class_", ""),
            subclass=data.get("subclass", ""),
            parent_code=data.get("parent_code"),
            children_codes=[],
            contra_accounts=data.get("contra_accounts", []),
            semantic_types=data.get("semantic_types", []),
            ifrs=data.get("ifrs", []),
            tags=data.get("tags", []),
            kpi_groups=data.get("kpi_groups", []),
            presentation_order=data.get("presentation_order", 0),
            is_group=data.get("is_group", False),
            nature=data.get("nature", ""),
            signo_normal=data.get("signo_normal", 1),
            description=data.get("description", ""),
        )
        tree.add_node(node)

    for data in _ACCOUNTS:
        parent_code = data.get("parent_code")
        code = data["code"]
        if parent_code:
            parent = tree.get_node(parent_code)
            if parent is not None and code not in parent.children_codes:
                parent.children_codes.append(code)

    return tree


def build_graph() -> FinancialGraph:
    tree = build_tree()
    graph = FinancialGraph()
    for node in tree.nodes.values():
        graph.add_node(node)

    for node in tree.nodes.values():
        if node.parent_code:
            graph.add_edge(node.code, node.parent_code, "parent_of")

    for node in tree.nodes.values():
        for child_code in node.children_codes:
            graph.add_edge(node.code, child_code, "child_of")

    return graph
