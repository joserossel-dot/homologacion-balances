from __future__ import annotations

import logging

from knowledge.financial_node import FinancialNode
from knowledge.financial_tree import FinancialTree
from knowledge.financial_graph import FinancialGraph
from knowledge.graph_builder import build_tree, build_graph
from knowledge.graph_queries import GraphQueries
from knowledge.graph_validator import GraphValidator, ValidationIssue

logging.disable(logging.CRITICAL)


# ---------------------------------------------------------------------------
# FinancialNode
# ---------------------------------------------------------------------------

def test_node_defaults():
    n = FinancialNode(code="TEST.01", name="Test Account")
    assert n.code == "TEST.01"
    assert n.name == "Test Account"
    assert n.class_ == ""
    assert n.subclass == ""
    assert n.parent_code is None
    assert n.children_codes == []
    assert n.contra_accounts == []
    assert n.semantic_types == []
    assert n.ifrs == []
    assert n.tags == []
    assert n.kpi_groups == []
    assert n.presentation_order == 0
    assert n.is_group is False
    assert n.nature == ""
    assert n.signo_normal == 1


def test_node_full_creation():
    n = FinancialNode(
        code="AC.01",
        name="Caja y Bancos",
        class_="activo",
        subclass="corriente",
        parent_code="AC",
        children_codes=["AC.01.01"],
        contra_accounts=[],
        semantic_types=["cash"],
        ifrs=["NIC 1"],
        tags=["efectivo", "liquido"],
        kpi_groups=["liquidez"],
        presentation_order=3,
        is_group=False,
        nature="deudora",
        signo_normal=1,
        description="Disponible en caja",
    )
    assert n.code == "AC.01"
    assert n.class_ == "activo"
    assert n.subclass == "corriente"
    assert n.parent_code == "AC"
    assert "liquidez" in n.kpi_groups


def test_node_to_dict():
    n = FinancialNode(code="PC.01", name="Proveedores", class_="pasivo")
    d = n.to_dict()
    assert d["code"] == "PC.01"
    assert d["class_"] == "pasivo"
    assert d["signo_normal"] == 1
    assert d["is_group"] is False


# ---------------------------------------------------------------------------
# FinancialTree
# ---------------------------------------------------------------------------

def test_tree_empty():
    tree = FinancialTree()
    assert tree.nodes == {}
    assert tree.roots == []


def test_tree_single_node():
    tree = FinancialTree()
    n = FinancialNode(code="ROOT", name="Root")
    tree.add_node(n)
    assert tree.get_node("ROOT") is n
    assert tree.roots == [n]
    assert tree.children("ROOT") == []
    assert tree.parent("ROOT") is None
    assert tree.depth("ROOT") == 0


def test_tree_add_and_remove():
    tree = FinancialTree()
    tree.add_node(FinancialNode(code="A", name="A"))
    tree.add_node(FinancialNode(code="B", name="B", parent_code="A",
                                children_codes=[]))
    tree.add_node(FinancialNode(code="C", name="C", parent_code="A",
                                children_codes=[]))
    a = tree.get_node("A")
    assert a is not None
    a.children_codes = ["B", "C"]
    assert len(tree.children("A")) == 2
    assert tree.parent("B") is a
    tree.remove_node("B")
    assert tree.get_node("B") is None
    assert len(tree.children("A")) == 1


def test_tree_ancestors_descendants():
    tree = FinancialTree()
    tree.add_node(FinancialNode(code="R", name="Root"))
    tree.add_node(FinancialNode(code="C1", name="Child1", parent_code="R",
                                children_codes=[]))
    tree.add_node(FinancialNode(code="C2", name="Child2", parent_code="C1",
                                children_codes=[]))
    r = tree.get_node("R")
    assert r is not None
    r.children_codes = ["C1"]
    c1 = tree.get_node("C1")
    assert c1 is not None
    c1.children_codes = ["C2"]
    c2 = tree.get_node("C2")
    assert c2 is not None
    assert tree.ancestors("C2") == [c1, r]
    assert tree.descendants("R") == [c1, c2]
    assert tree.siblings("C2") == []


def test_tree_find_by_class():
    tree = FinancialTree()
    tree.add_node(FinancialNode(code="A.01", name="A1", class_="activo"))
    tree.add_node(FinancialNode(code="P.01", name="P1", class_="pasivo"))
    tree.add_node(FinancialNode(code="A.02", name="A2", class_="activo"))
    assert len(tree.find_by_class("activo")) == 2
    assert len(tree.find_by_class("pasivo")) == 1


def test_tree_find_by_tag():
    tree = FinancialTree()
    tree.add_node(FinancialNode(code="X", name="X", tags=["liquido"]))
    tree.add_node(FinancialNode(code="Y", name="Y", tags=["liquido", "efectivo"]))
    tree.add_node(FinancialNode(code="Z", name="Z", tags=["otros"]))
    assert len(tree.find_by_tag("liquido")) == 2
    assert len(tree.find_by_tag("efectivo")) == 1
    assert len(tree.find_by_tag("otros")) == 1


# ---------------------------------------------------------------------------
# FinancialGraph
# ---------------------------------------------------------------------------

def test_graph_empty():
    g = FinancialGraph()
    assert g.nodes == {}
    assert g.edges == []


def test_graph_add_node():
    g = FinancialGraph()
    n = FinancialNode(code="N1", name="Node 1")
    g.add_node(n)
    assert g.get_node("N1") is n


def test_graph_add_edge():
    g = FinancialGraph()
    g.add_node(FinancialNode(code="A", name="A"))
    g.add_node(FinancialNode(code="B", name="B"))
    g.add_edge("A", "B", "parent_of")
    assert g.has_edge("A", "B", "parent_of")
    assert len(g.edges) == 1


def test_graph_edge_ignores_missing_nodes():
    g = FinancialGraph()
    g.add_node(FinancialNode(code="A", name="A"))
    g.add_edge("A", "MISSING", "parent_of")
    assert len(g.edges) == 0


def test_graph_neighbors():
    g = FinancialGraph()
    g.add_node(FinancialNode(code="A", name="A"))
    g.add_node(FinancialNode(code="B", name="B"))
    g.add_node(FinancialNode(code="C", name="C"))
    g.add_edge("A", "B", "child_of")
    g.add_edge("A", "C", "child_of")
    g.add_edge("B", "C", "related")
    assert len(g.neighbors("A")) == 2
    assert len(g.neighbors("A", "child_of")) == 2
    assert len(g.neighbors("A", "parent_of")) == 0
    assert len(g.neighbors("B")) == 2  # A and C
    assert len(g.neighbors("C", "related")) == 1  # B


def test_graph_neighbors_by_relation():
    g = FinancialGraph()
    g.add_node(FinancialNode(code="X", name="X"))
    g.add_node(FinancialNode(code="Y", name="Y"))
    g.add_edge("X", "Y", "custom_rel")
    neighbors = g.neighbors_by_relation("X", "custom_rel")
    assert len(neighbors) == 1
    assert neighbors[0].code == "Y"


def test_graph_remove_node():
    g = FinancialGraph()
    g.add_node(FinancialNode(code="A", name="A"))
    g.add_node(FinancialNode(code="B", name="B"))
    g.add_edge("A", "B", "edge")
    g.remove_node("A")
    assert g.get_node("A") is None
    assert len(g.edges) == 0


def test_graph_subgraph():
    g = FinancialGraph()
    for code in ["A", "B", "C", "D"]:
        g.add_node(FinancialNode(code=code, name=code))
    g.add_edge("A", "B", "rel")
    g.add_edge("A", "C", "rel")
    g.add_edge("B", "D", "rel")
    sg = g.subgraph(["A", "B", "C"])
    assert sg.get_node("A") is not None
    assert sg.get_node("D") is None
    assert sg.has_edge("A", "B", "rel")
    assert not sg.has_edge("B", "D", "rel")


# ---------------------------------------------------------------------------
# GraphBuilder
# ---------------------------------------------------------------------------

def test_build_tree_has_all_nodes():
    tree = build_tree()
    expected_codes = {
        "ACTIVO", "AC", "ANC",
        "AC.01", "AC.02", "AC.03", "AC.04", "AC.05", "AC.06", "AC.06S",
        "AC.07", "AC.08", "AC.09",
        "ANC.01", "ANC.02", "ANC.03", "ANC.04", "ANC.05", "ANC.06",
        "ANC.07", "ANC.08",
        "PASIVO", "PC", "PNC",
        "PC.01", "PC.02", "PC.03", "PC.04", "PC.05", "PC.06", "PC.07", "PC.08",
        "PNC.01", "PNC.02", "PNC.03", "PNC.04", "PNC.05",
        "PATRIMONIO",
        "PAT.01", "PAT.02", "PAT.03", "PAT.04", "PAT.05",
        "RESULTADO",
        "ER.01", "ER.02", "ER.03", "ER.04", "ER.05", "ER.06", "ER.07",
        "ER.08", "ER.09", "ER.10", "ER.11", "ER.12", "ER.13", "ER.14",
        "ER.15", "ER.16",
    }
    for code in expected_codes:
        assert tree.get_node(code) is not None, f"Missing node: {code}"
    assert len(tree.nodes) >= len(expected_codes)


def test_build_tree_hierarchy():
    tree = build_tree()
    activo = tree.get_node("ACTIVO")
    assert activo is not None
    assert activo.is_group
    assert "AC" in activo.children_codes
    assert "ANC" in activo.children_codes

    ac = tree.get_node("AC")
    assert ac is not None
    assert ac.parent_code == "ACTIVO"
    assert "AC.01" in ac.children_codes
    assert "AC.09" in ac.children_codes


def test_build_tree_contra_accounts():
    tree = build_tree()
    anc01 = tree.get_node("ANC.01")
    assert anc01 is not None
    assert "depreciacion_acumulada" in anc01.contra_accounts
    anc03 = tree.get_node("ANC.03")
    assert anc03 is not None
    assert "amortizacion_acumulada" in anc03.contra_accounts


def test_build_tree_kpi_groups():
    tree = build_tree()
    liquidity_nodes = tree.find_by_kpi("liquidez")
    codes = {n.code for n in liquidity_nodes}
    assert "AC.01" in codes
    assert "AC.03" in codes
    assert "PC.01" in codes
    assert "PC.02" in codes


def test_build_tree_ifrs():
    tree = build_tree()
    nic16 = tree.find_by_tag("depreciable")
    codes = {n.code for n in nic16}
    assert "ANC.01" in codes


def test_build_graph():
    graph = build_graph()
    assert graph.get_node("ACTIVO") is not None
    assert graph.get_node("AC.01") is not None
    assert graph.get_node("ER.16") is not None


def test_build_graph_edges():
    graph = build_graph()
    assert graph.has_edge("AC.01", "AC", "parent_of") or graph.has_edge("AC", "AC.01", "child_of")
    parent_edges = [(s, t) for s, t, r in graph.edges if r == "parent_of"]
    child_edges = [(s, t) for s, t, r in graph.edges if r == "child_of"]
    assert len(parent_edges) > 0
    assert len(child_edges) > 0


# ---------------------------------------------------------------------------
# GraphQueries
# ---------------------------------------------------------------------------

def test_queries_activos_corrientes():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.activos_corrientes()
    codes = {n.code for n in nodes}
    assert "AC.01" in codes
    assert "AC.03" in codes
    assert "ANC.01" not in codes


def test_queries_activos_no_corrientes():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.activos_no_corrientes()
    codes = {n.code for n in nodes}
    assert "ANC.01" in codes
    assert "ANC.03" in codes
    assert "AC.01" not in codes


def test_queries_pasivos_corrientes():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.pasivos_corrientes()
    codes = {n.code for n in nodes}
    assert "PC.01" in codes
    assert "PC.05" in codes
    assert "PNC.01" not in codes


def test_queries_pasivos_no_corrientes():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.pasivos_no_corrientes()
    codes = {n.code for n in nodes}
    assert "PNC.01" in codes
    assert "PNC.03" in codes
    assert "PC.01" not in codes


def test_queries_patrimonio():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.patrimonio()
    codes = {n.code for n in nodes}
    assert "PAT.01" in codes
    assert "PAT.03" in codes
    assert "PAT.04" in codes


def test_queries_gastos():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.gastos()
    codes = {n.code for n in nodes}
    assert "ER.02" in codes
    assert "ER.04" in codes
    assert "ER.07" in codes
    assert "ER.09" in codes


def test_queries_ingresos():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.ingresos()
    codes = {n.code for n in nodes}
    assert "ER.01" in codes
    assert "ER.12" in codes


def test_queries_contra_activos():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.contra_activos()
    codes = {n.code for n in nodes}
    assert "ANC.01" in codes
    assert "ANC.03" in codes


def test_queries_cuentas_por_tag():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.cuentas_por_tag("deuda_financiera")
    codes = {n.code for n in nodes}
    assert "PC.02" in codes
    assert "PNC.01" in codes


def test_queries_cuentas_ifrs():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.cuentas_ifrs("NIC 16")
    codes = {n.code for n in nodes}
    assert "ANC.01" in codes


def test_queries_cuentas_kpi():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.cuentas_kpi("endeudamiento")
    codes = {n.code for n in nodes}
    assert "PC.02" in codes
    assert "PNC.01" in codes
    assert "PNC.03" in codes


def test_queries_activos_totales():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.activos_totales()
    assert len(nodes) >= 17


def test_queries_pasivos_totales():
    tree = build_tree()
    graph = build_graph()
    q = GraphQueries(graph, tree)
    nodes = q.pasivos_totales()
    assert len(nodes) >= 13


# ---------------------------------------------------------------------------
# GraphValidator
# ---------------------------------------------------------------------------

def _make_validator():
    tree = build_tree()
    graph = build_graph()
    return GraphValidator(graph, tree)


def test_validation_issue_creation():
    issue = ValidationIssue(
        severity="error",
        code="TEST_CODE",
        message="Test message",
        account_name="Test Account",
        expected="X",
        found="Y",
    )
    assert issue.severity == "error"
    assert issue.code == "TEST_CODE"


def test_validate_contra_asset_in_income():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Depreciación Acumulada",
        classified_code="ANC.01",
        source_column="perdida",
        semantic_type="contra_asset",
    )
    has_contra = any(i.code == "CONTRA_ASSET_IN_INCOME" for i in issues)
    assert has_contra, "Should detect contra asset in income statement"


def test_validate_contra_asset_in_balance_ok():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Depreciación Acumulada",
        classified_code="ANC.01",
        source_column="activo",
        semantic_type="contra_asset",
    )
    has_contra = any(i.code == "CONTRA_ASSET_IN_INCOME" for i in issues)
    assert not has_contra, "Contra asset in balance sheet should be valid"


def test_validate_asset_in_liability_column():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Caja",
        classified_code="AC.01",
        source_column="pasivo",
        semantic_type="asset",
    )
    has_mismatch = any(i.code == "ASSET_IN_LIABILITY_COLUMN" for i in issues)
    assert has_mismatch


def test_validate_liability_in_asset_column():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Proveedores",
        classified_code="PC.01",
        source_column="activo",
        semantic_type="liability",
    )
    has_mismatch = any(i.code == "LIABILITY_IN_ASSET_COLUMN" for i in issues)
    assert has_mismatch


def test_validate_asset_in_liability_ok():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Caja",
        classified_code="AC.01",
        source_column="activo",
        semantic_type="asset",
    )
    has_mismatch = any(i.code == "ASSET_IN_LIABILITY_COLUMN" for i in issues)
    assert not has_mismatch


def test_validate_iva_debito_en_activo():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="IVA Débito Fiscal",
        classified_code="PC.05",
        source_column="activo",
        semantic_type="liability",
    )
    has_iva = any(i.code == "IVA_DEBITO_EN_ACTIVO" for i in issues)
    assert has_iva


def test_validate_iva_debito_en_pasivo_ok():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="IVA Débito Fiscal",
        classified_code="PC.05",
        source_column="pasivo",
        semantic_type="liability",
    )
    has_iva = any(i.code == "IVA_DEBITO_EN_ACTIVO" for i in issues)
    assert not has_iva


def test_validate_iva_credito_en_pasivo():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="IVA Crédito Fiscal",
        classified_code="AC.07",
        source_column="pasivo",
        semantic_type="asset",
    )
    has_iva = any(i.code == "IVA_CREDITO_EN_PASIVO" for i in issues)
    assert has_iva


def test_validate_iva_credito_en_activo_ok():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="IVA Crédito Fiscal",
        classified_code="AC.07",
        source_column="activo",
        semantic_type="asset",
    )
    has_iva = any(i.code == "IVA_CREDITO_EN_PASIVO" for i in issues)
    assert not has_iva


def test_validate_utilidad_retenida_como_gasto():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Utilidad Retenida",
        classified_code="PAT.03",
        source_column="perdida",
        semantic_type="expense",
    )
    has_issue = any(i.code == "UTILIDAD_RETENIDA_COMO_GASTO" for i in issues)
    assert has_issue


def test_validate_utilidad_retenida_ok():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Utilidad Retenida",
        classified_code="PAT.03",
        source_column="pasivo",
        semantic_type="unknown",
    )
    has_issue = any(i.code == "UTILIDAD_RETENIDA_COMO_GASTO" for i in issues)
    assert not has_issue


def test_validate_resultado_acumulado_como_gasto():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Resultado Acumulado",
        classified_code="PAT.03",
        source_column="perdida",
        semantic_type="expense",
    )
    has_issue = any(i.code == "UTILIDAD_RETENIDA_COMO_GASTO" for i in issues)
    assert has_issue


def test_validate_capital_como_activo():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Capital",
        classified_code="PAT.01",
        source_column="activo",
        semantic_type="unknown",
    )
    has_issue = any(i.code == "CAPITAL_COMO_ACTIVO" for i in issues)
    assert has_issue


def test_validate_capital_en_patrimonio_ok():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Capital",
        classified_code="PAT.01",
        source_column="pasivo",
        semantic_type="unknown",
    )
    has_issue = any(i.code == "CAPITAL_COMO_ACTIVO" for i in issues)
    assert not has_issue


def test_validate_unknown_code_no_crash():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Cuenta Desconocida",
        classified_code="ZZ.99",
        source_column="activo",
        semantic_type="unknown",
    )
    assert issues == []


def test_validate_multiple_issues():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Depreciación Acumulada",
        classified_code="ANC.01",
        source_column="perdida",
        semantic_type="contra_asset",
    )
    codes = {i.code for i in issues}
    assert "CONTRA_ASSET_IN_INCOME" in codes
    assert "ASSET_IN_LIABILITY_COLUMN" not in codes


def test_validate_no_issues():
    v = _make_validator()
    issues = v.validate_semantic_classification(
        account_name="Caja",
        classified_code="AC.01",
        source_column="activo",
        semantic_type="asset",
    )
    assert issues == []


# ---------------------------------------------------------------------------
# Integration: validator + semantic engine consistency
# ---------------------------------------------------------------------------

def test_validator_depreciacion_en_perdidas():
    tree = build_tree()
    graph = build_graph()
    v = GraphValidator(graph, tree)

    issues = v.validate_semantic_classification(
        account_name="Depreciación Acumulada",
        classified_code="ANC.01",
        source_column="perdida",
        semantic_type="contra_asset",
    )
    codes = {i.code for i in issues}
    assert "CONTRA_ASSET_IN_INCOME" in codes


# ---------------------------------------------------------------------------
# Run guard
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    this = sys.modules[__name__]
    passed = 0
    failed = 0
    for name in sorted(dir(this)):
        if name.startswith("test_"):
            try:
                getattr(this, name)()
                print(f"  \u2713 {name}")
                passed += 1
            except Exception as e:
                print(f"  \u2717 {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
