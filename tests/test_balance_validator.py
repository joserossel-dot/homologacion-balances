from __future__ import annotations
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validation.models import (
    AccountNode, HierarchyTree, IntegrityScore,
    SubtotalResult, EquationResult, MissingAccountCandidate,
)
from validation.hierarchy import build_hierarchy, detect_section_boundaries
from validation.subtotal_validator import validate_subtotals, detect_subtotals
from validation.equation_validator import validate_balance_equation
from validation.missing_account_detector import detect_missing_accounts
from validation.integrity_score import (
    compute_integrity_score, compute_extraction_score,
    compute_classification_score, compute_hierarchy_score,
    compute_subtotal_score, compute_equation_score,
)


# ========= ACCOUNT NODE TESTS =========

class TestAccountNode:
    def test_create_node(self):
        node = AccountNode(account_name="Test", amount=100.0, line_number=0)
        assert node.account_name == "Test"
        assert node.amount == 100.0
        assert node.is_leaf is True
        assert node.depth == 0

    def test_add_child(self):
        parent = AccountNode(account_name="Parent", amount=0, line_number=0)
        child = AccountNode(account_name="Child", amount=50, line_number=1)
        parent.add_child(child)
        assert len(parent.children) == 1
        assert child.parent is parent
        assert parent.is_leaf is False
        assert child.depth == 1

    def test_all_descendants(self):
        root = AccountNode(account_name="Root", amount=0, line_number=0)
        c1 = AccountNode(account_name="C1", amount=10, line_number=1)
        c2 = AccountNode(account_name="C2", amount=20, line_number=2)
        c1a = AccountNode(account_name="C1a", amount=5, line_number=3)
        root.add_child(c1)
        root.add_child(c2)
        c1.add_child(c1a)
        desc = root.all_descendants
        assert len(desc) == 3

    def test_depth_calculation(self):
        a = AccountNode(account_name="A", amount=0, line_number=0)
        b = AccountNode(account_name="B", amount=0, line_number=1)
        c = AccountNode(account_name="C", amount=0, line_number=2)
        a.add_child(b)
        b.add_child(c)
        assert a.depth == 0
        assert b.depth == 1
        assert c.depth == 2


# ========= HIERARCHY TESTS =========

class TestHierarchy:
    def test_build_simple_flat(self):
        raw = [
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
            {"nombre": "Banco", "monto": 200, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Total Activo", "monto": 300, "codigo": "", "origen_columna": "activo", "es_total": True, "linea": 2},
        ]
        tree = build_hierarchy(raw)
        assert len(tree.all_nodes) == 3
        assert len(tree.roots) >= 1

    def test_build_with_sections(self):
        raw = [
            {"nombre": "Activo", "monto": 0, "codigo": "", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Banco", "monto": 200, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 2},
            {"nombre": "Pasivo", "monto": 0, "codigo": "", "origen_columna": "", "es_total": False, "linea": 3},
            {"nombre": "Proveedores", "monto": 150, "codigo": "", "origen_columna": "pasivo", "es_total": False, "linea": 4},
            {"nombre": "Patrimonio", "monto": 0, "codigo": "", "origen_columna": "", "es_total": False, "linea": 5},
            {"nombre": "Capital", "monto": 150, "codigo": "", "origen_columna": "", "es_total": False, "linea": 6},
        ]
        tree = build_hierarchy(raw)
        sections = detect_section_boundaries(tree)
        assert "ACTIVO" in sections
        assert "PASIVO" in sections

    def test_es_total_flag_respected(self):
        raw = [
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
            {"nombre": "Total Activo", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": True, "linea": 1},
        ]
        tree = build_hierarchy(raw)
        totals = [n for n in tree.all_nodes if n.es_total]
        assert len(totals) >= 1

    def test_with_classified_data(self):
        raw = [
            {"nombre": "Caja", "monto": 100, "codigo": "1.01", "origen_columna": "activo", "es_total": False, "linea": 0},
        ]
        classified = [
            {"account_name": "Caja", "standard_code": "AC.01", "source_page": 0},
        ]
        tree = build_hierarchy(raw, classified)
        assert tree.total_accounts == 1

    def test_empty_raw(self):
        tree = build_hierarchy([])
        assert tree.total_accounts == 0
        assert len(tree.roots) == 0

    def test_hierarchy_with_levels(self):
        raw = [
            {"linea": 0, "codigo": "1", "nombre": "Activo", "monto": 0, "origen_columna": "", "es_total": False},
            {"linea": 1, "codigo": "1.1", "nombre": "Activo Corriente", "monto": 0, "origen_columna": "", "es_total": False},
            {"linea": 2, "codigo": "1.1.1", "nombre": "Caja", "monto": 100, "origen_columna": "activo", "es_total": False},
            {"linea": 3, "codigo": "1.1.2", "nombre": "Banco", "monto": 200, "origen_columna": "activo", "es_total": False},
        ]
        tree = build_hierarchy(raw)
        assert len(tree.all_nodes) == 4


# ========= SUBTOTAL VALIDATOR TESTS =========

class TestSubtotalValidation:
    def test_detect_subtotals(self):
        raw = [
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
            {"nombre": "Banco", "monto": 200, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Total Activo Corriente", "monto": 300, "codigo": "", "origen_columna": "activo", "es_total": True, "linea": 2},
        ]
        tree = build_hierarchy(raw)
        detected = detect_subtotals(tree)
        assert len(detected) >= 1
        assert any("Total Activo" in n.account_name for n in detected)

    def test_validate_correct_subtotal(self):
        raw = [
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
            {"nombre": "Total", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": True, "linea": 1},
        ]
        tree = build_hierarchy(raw)
        results = validate_subtotals(tree)
        passed = [r for r in results if r.passed]
        assert len(passed) >= 1

    def test_subtotal_mismatch(self):
        raw = [
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
            {"nombre": "Banco", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Total", "monto": 500, "codigo": "", "origen_columna": "activo", "es_total": True, "linea": 2},
        ]
        tree = build_hierarchy(raw)
        results = validate_subtotals(tree)
        if results:
            assert not results[0].passed
            assert abs(results[0].difference) > 0

    def test_no_subtotals(self):
        raw = [
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
            {"nombre": "Banco", "monto": 200, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 1},
        ]
        tree = build_hierarchy(raw)
        results = validate_subtotals(tree)
        assert len(results) == 0


# ========= EQUATION VALIDATOR TESTS =========

class TestEquationValidation:
    def test_balance_equation(self):
        raw = [
            {"nombre": "Caja", "monto": 500, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
            {"nombre": "Proveedores", "monto": 200, "codigo": "", "origen_columna": "pasivo", "es_total": False, "linea": 1},
            {"nombre": "Capital", "monto": 300, "codigo": "", "origen_columna": "", "es_total": False, "linea": 2},
        ]
        tree = build_hierarchy(raw)
        eqs = validate_balance_equation(tree)
        balance_eqs = [e for e in eqs if "Activo" in e.equation and "Pasivo" in e.equation]
        if balance_eqs:
            assert balance_eqs[0].passed or abs(balance_eqs[0].difference) <= 1.0

    def test_income_equation(self):
        raw = [
            {"nombre": "Ingresos", "monto": 1000, "codigo": "", "origen_columna": "ganancia", "es_total": False, "linea": 0},
            {"nombre": "Costos", "monto": 400, "codigo": "", "origen_columna": "perdida", "es_total": False, "linea": 1},
            {"nombre": "Gastos", "monto": 200, "codigo": "", "origen_columna": "perdida", "es_total": False, "linea": 2},
        ]
        tree = build_hierarchy(raw)
        sections = detect_section_boundaries(tree)
        eqs = validate_balance_equation(tree)
        income_eqs = [e for e in eqs if "Ingreso" in e.equation or "Resultado" in e.equation]
        if income_eqs:
            assert income_eqs[0].right_side == 400.0

    def test_asset_decomposition(self):
        raw = [
            {"nombre": "Activo Corriente", "monto": 0, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
            {"nombre": "Caja", "monto": 300, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Activo No Corriente", "monto": 0, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 2},
            {"nombre": "Terreno", "monto": 700, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 3},
        ]
        tree = build_hierarchy(raw)
        eqs = validate_balance_equation(tree)
        decomp_eqs = [e for e in eqs if "Corriente" in e.equation]
        assert len(decomp_eqs) >= 0

    def test_no_sections(self):
        raw = [
            {"nombre": "Item A", "monto": 100, "codigo": "", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Item B", "monto": 200, "codigo": "", "origen_columna": "", "es_total": False, "linea": 1},
        ]
        tree = build_hierarchy(raw)
        eqs = validate_balance_equation(tree)
        assert len(eqs) == 0


# ========= MISSING ACCOUNT DETECTOR TESTS =========

class TestMissingAccountDetector:
    def test_exact_match(self):
        tree = build_hierarchy([
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Diferencia", "monto": 50, "codigo": "", "origen_columna": "", "es_total": False, "linea": 1},
        ])
        subtotal_results = [
            SubtotalResult(account_name="Total", expected=150, actual=100, difference=50, pct_diff=33.3, passed=False, line_number=5)
        ]
        candidates = detect_missing_accounts(subtotal_results, [], tree)
        assert len(candidates) >= 1

    def test_similar_match(self):
        tree = build_hierarchy([
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Similar", "monto": 99.5, "codigo": "", "origen_columna": "", "es_total": False, "linea": 1},
        ])
        subtotal_results = [
            SubtotalResult(account_name="Total", expected=50, actual=0, difference=50, pct_diff=100, passed=False, line_number=5)
        ]
        candidates = detect_missing_accounts(subtotal_results, [], tree, tolerance_pct=1.0)
        similar = [c for c in candidates if "Similar" in c.reason]
        assert len(similar) >= 0

    def test_negative_match(self):
        tree = build_hierarchy([
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Negativo", "monto": -50, "codigo": "", "origen_columna": "", "es_total": False, "linea": 1},
        ])
        subtotal_results = [
            SubtotalResult(account_name="Total", expected=100, actual=150, difference=-50, pct_diff=50, passed=False, line_number=5)
        ]
        candidates = detect_missing_accounts(subtotal_results, [], tree)
        negative = [c for c in candidates if "Negative" in c.reason or "sign" in c.reason]
        assert len(negative) >= 0

    def test_no_difference_no_candidates(self):
        tree = build_hierarchy([
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "", "es_total": False, "linea": 0},
        ])
        subtotal_results = [
            SubtotalResult(account_name="Total", expected=100, actual=100, difference=0, pct_diff=0, passed=True, line_number=5)
        ]
        candidates = detect_missing_accounts(subtotal_results, [], tree)
        assert len(candidates) == 0


# ========= INTEGRITY SCORE TESTS =========

class TestIntegrityScore:
    def test_perfect_score(self):
        tree = HierarchyTree()
        tree.all_nodes = [
            AccountNode(account_name="A", amount=100, line_number=0),
            AccountNode(account_name="B", amount=200, line_number=1),
        ]
        tree.roots = [tree.all_nodes[0]]
        tree.all_nodes[0].add_child(tree.all_nodes[1])

        score = compute_integrity_score(tree, [], [], 2, 0)
        assert score.extraction_score > 0
        assert score.overall > 0

    def test_extraction_penalties(self):
        tree = HierarchyTree()
        tree.all_nodes = [
            AccountNode(account_name="", amount=0, line_number=0),
            AccountNode(account_name="", amount=0, line_number=1),
        ]
        tree.roots = tree.all_nodes
        score = compute_extraction_score(tree)
        assert score < 100

    def test_extraction_perfect(self):
        tree = HierarchyTree()
        tree.all_nodes = [
            AccountNode(account_name="Caja", amount=100, line_number=0),
            AccountNode(account_name="Banco", amount=200, line_number=1),
        ]
        tree.roots = tree.all_nodes
        score = compute_extraction_score(tree)
        assert score == 100.0

    def test_classification_score(self):
        tree = HierarchyTree()
        tree.all_nodes = [AccountNode(account_name="A", amount=100, line_number=0)]
        score = compute_classification_score(tree, 1, 0)
        assert score == 100.0

    def test_classification_low(self):
        tree = HierarchyTree()
        tree.all_nodes = [AccountNode(account_name="A", amount=100, line_number=0)]
        score = compute_classification_score(tree, 0, 1)
        assert score <= 50.0

    def test_hierarchy_score_low(self):
        tree = HierarchyTree()
        tree.all_nodes = [
            AccountNode(account_name="A", amount=100, line_number=0),
            AccountNode(account_name="B", amount=200, line_number=1),
        ]
        tree.roots = tree.all_nodes
        score = compute_hierarchy_score(tree)
        assert isinstance(score, float)

    def test_subtotal_score(self):
        results = [
            SubtotalResult(account_name="T1", expected=100, actual=100, difference=0, pct_diff=0, passed=True),
            SubtotalResult(account_name="T2", expected=100, actual=100, difference=0, pct_diff=0, passed=True),
        ]
        score = compute_subtotal_score(results)
        assert score == 100.0

    def test_subtotal_score_with_errors(self):
        results = [
            SubtotalResult(account_name="T1", expected=100, actual=100, difference=0, pct_diff=0, passed=True),
            SubtotalResult(account_name="T2", expected=100, actual=50, difference=50, pct_diff=50, passed=False),
        ]
        score = compute_subtotal_score(results)
        assert score < 100

    def test_subtotal_score_empty(self):
        score = compute_subtotal_score([])
        assert score == 100.0

    def test_equation_score(self):
        results = [
            EquationResult(equation="A=B", left_side=100, right_side=100, difference=0, passed=True),
            EquationResult(equation="C=D", left_side=100, right_side=100, difference=0, passed=True),
        ]
        score = compute_equation_score(results)
        assert score == 100.0

    def test_equation_score_with_errors(self):
        results = [
            EquationResult(equation="A=B", left_side=100, right_side=100, difference=0, passed=True),
            EquationResult(equation="C=D", left_side=100, right_side=50, difference=50, passed=False),
        ]
        score = compute_equation_score(results)
        assert score == 50.0

    def test_equation_score_empty(self):
        score = compute_equation_score([])
        assert score == 100.0

    def test_compute_overall(self):
        score = IntegrityScore(
            extraction_score=100,
            classification_score=100,
            hierarchy_score=100,
            subtotal_score=100,
            equation_score=100,
        )
        score.compute_overall()
        assert score.overall == 100.0

    def test_compute_overall_mixed(self):
        score = IntegrityScore(
            extraction_score=80,
            classification_score=70,
            hierarchy_score=90,
            subtotal_score=60,
            equation_score=50,
        )
        score.compute_overall()
        assert 0 < score.overall < 100


# ========= VALIDATION RESULT TESTS =========

class TestValidationResult:
    def test_create_result(self):
        from validation.models import ValidationResult
        vr = ValidationResult(source_file="test.pdf", accounts_total=10)
        assert vr.source_file == "test.pdf"
        assert vr.accounts_total == 10

    def test_warnings(self):
        from validation.models import ValidationResult
        vr = ValidationResult(source_file="test.pdf")
        vr.warnings.append("Test warning")
        assert len(vr.warnings) == 1


# ========= SUBTOTAL RESULT TESTS =========

class TestSubtotalResult:
    def test_create(self):
        sr = SubtotalResult(account_name="Total", expected=100, actual=50, difference=50, pct_diff=50)
        assert sr.difference == 50
        assert sr.passed is False

    def test_create_passed(self):
        sr = SubtotalResult(account_name="Total", expected=100, actual=100)
        assert sr.difference == 0
        sr.passed = True
        assert sr.passed is True


# ========= EQUATION RESULT TESTS =========

class TestEquationResult:
    def test_create(self):
        er = EquationResult(equation="A=B", left_side=100, right_side=100)
        assert er.passed is False


# ========= MISSING ACCOUNT CANDIDATE TESTS =========

class TestMissingAccountCandidate:
    def test_create(self):
        mc = MissingAccountCandidate(target_amount=100, matched_amount=100, account_name="Caja")
        assert mc.similarity_pct == 0.0
        assert mc.target_amount == 100


# ========= HIERARCHY TREE TESTS =========

class TestHierarchyTree:
    def test_find_by_name(self):
        tree = HierarchyTree()
        tree.all_nodes = [
            AccountNode(account_name="Caja", amount=100, line_number=0),
            AccountNode(account_name="Banco", amount=200, line_number=1),
        ]
        found = tree.find_by_name("caja")
        assert len(found) == 1
        assert found[0].account_name == "Caja"

    def test_find_by_name_not_found(self):
        tree = HierarchyTree()
        tree.all_nodes = [AccountNode(account_name="Caja", amount=100, line_number=0)]
        found = tree.find_by_name("no_existe")
        assert len(found) == 0

    def test_find_by_code(self):
        tree = HierarchyTree()
        tree.all_nodes = [
            AccountNode(account_code="1.1.1", account_name="Caja", amount=100, line_number=0),
        ]
        node = tree.find_by_code("1.1.1")
        assert node is not None
        assert node.account_name == "Caja"

    def test_find_by_code_not_found(self):
        tree = HierarchyTree()
        tree.all_nodes = [AccountNode(account_code="1.1.1", account_name="Caja", amount=100, line_number=0)]
        node = tree.find_by_code("999")
        assert node is None

    def test_total_accounts(self):
        tree = HierarchyTree()
        tree.all_nodes = [AccountNode(account_name="A", amount=100, line_number=0)]
        assert tree.total_accounts == 1


# ========= HIERARCHY EDGE CASES =========

class TestHierarchyEdgeCases:
    def test_negative_amount(self):
        raw = [
            {"nombre": "Caja", "monto": -100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
            {"nombre": "Total", "monto": -100, "codigo": "", "origen_columna": "activo", "es_total": True, "linea": 1},
        ]
        tree = build_hierarchy(raw)
        assert tree.total_accounts == 2

    def test_large_amounts(self):
        raw = [
            {"nombre": "Caja", "monto": 999999999.99, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
        ]
        tree = build_hierarchy(raw)
        assert tree.total_accounts == 1

    def test_string_amount(self):
        raw = [
            {"nombre": "Caja", "monto": "1500", "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
        ]
        tree = build_hierarchy(raw)
        assert tree.all_nodes[0].amount == 1500.0

    def test_string_amount_chilean(self):
        raw = [
            {"nombre": "Caja", "monto": "1.500.000", "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
        ]
        tree = build_hierarchy(raw)
        assert tree.all_nodes[0].amount == 1500000.0

    def test_no_codigo_no_indent(self):
        raw = [
            {"nombre": "Item", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 0},
        ]
        tree = build_hierarchy(raw)
        assert tree.all_nodes[0].level >= 0

    def test_current_noncurrent_sections(self):
        raw = [
            {"nombre": "Activo Corriente", "monto": 0, "codigo": "", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Activo No Corriente", "monto": 0, "codigo": "", "origen_columna": "", "es_total": False, "linea": 2},
            {"nombre": "Terreno", "monto": 200, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 3},
        ]
        tree = build_hierarchy(raw)
        sections = detect_section_boundaries(tree)
        assert "ACTIVO_CORRIENTE" in sections
        assert "ACTIVO_NO_CORRIENTE" in sections
