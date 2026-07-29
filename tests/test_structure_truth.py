from __future__ import annotations
import sys, os, json, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analysis.subtotal_trace import SubtotalTracer, SubtotalTrace
from analysis.hierarchy_comparator import HierarchyComparator, HierarchyComparison
from analysis.root_cause_classifier import RootCauseClassifier, VALID_CAUSES
from analysis.statistics import StatisticsGenerator, PatternResult, FormatMatrix
from analysis.structure_truth_analyzer import StructureTruthAnalyzer

from validation.models import SubtotalResult, ValidationResult


# ========= SUBTOTAL TRACE TESTS =========

class TestSubtotalTracer:
    def test_build_trace_basic(self):
        tracer = SubtotalTracer()
        all_accounts = [
            {"nombre": "Caja", "monto": 100, "linea": 0, "es_total": False},
            {"nombre": "Banco", "monto": 200, "linea": 1, "es_total": False},
            {"nombre": "Total Activo", "monto": 300, "linea": 2, "es_total": True},
        ]
        children = [
            {"nombre": "Caja", "amount": 100},
            {"nombre": "Banco", "amount": 200},
        ]
        trace = tracer.build_trace(
            source_file="test.pdf",
            subtotal_name="Total Activo",
            subtotal_line=2,
            expected=300,
            actual=300,
            difference=0,
            pct_diff=0,
            children=children,
            all_accounts=all_accounts,
        )
        assert trace.source_file == "test.pdf"
        assert trace.expected == 300
        assert trace.actual == 300
        assert len(trace.children_considered) == 2

    def test_build_trace_with_difference(self):
        tracer = SubtotalTracer()
        all_accounts = [
            {"nombre": "Caja", "monto": 100, "linea": 0, "es_total": False},
            {"nombre": "Banco", "monto": 50, "linea": 1, "es_total": False},
        ]
        trace = tracer.build_trace(
            source_file="test.pdf",
            subtotal_name="Total Activo",
            subtotal_line=2,
            expected=300,
            actual=150,
            difference=150,
            pct_diff=50,
            children=[],
            all_accounts=all_accounts,
        )
        assert trace.difference == 150

    def test_find_nearby_accounts(self):
        tracer = SubtotalTracer()
        all_accounts = [
            {"nombre": "A", "monto": 100, "linea": 0},
            {"nombre": "B", "monto": 200, "linea": 1},
            {"nombre": "C", "monto": 300, "linea": 2},
            {"nombre": "D", "monto": 400, "linea": 10},
        ]
        nearby = tracer._find_nearby_accounts(1, all_accounts, window=2)
        assert len(nearby) >= 2
        names = [a["nombre"] for a in nearby]
        assert "A" in names
        assert "B" in names
        assert "C" in names

    def test_find_candidates_exact(self):
        tracer = SubtotalTracer()
        all_accounts = [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Missing", "monto": 50, "linea": 1},
        ]
        candidates = tracer._find_candidates(50, all_accounts, subtotal_line=5)
        exact = [c for c in candidates if c["match_type"] == "exact"]
        assert len(exact) >= 1
        assert exact[0]["account_name"] == "Missing"

    def test_find_candidates_similar(self):
        tracer = SubtotalTracer()
        all_accounts = [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Similar", "monto": 49.5, "linea": 1},
        ]
        candidates = tracer._find_candidates(50, all_accounts, subtotal_line=5, tolerance_pct=1.0)
        similar = [c for c in candidates if c["match_type"] == "similar"]
        assert len(similar) >= 1

    def test_find_candidates_sign_flip(self):
        tracer = SubtotalTracer()
        all_accounts = [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Negativo", "monto": -50, "linea": 1},
        ]
        candidates = tracer._find_candidates(50, all_accounts, subtotal_line=5)
        sign_flip = [c for c in candidates if c["match_type"] == "sign_flip"]
        assert len(sign_flip) >= 1

    def test_find_candidates_negative_exact(self):
        tracer = SubtotalTracer()
        all_accounts = [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Deuda", "monto": -50, "linea": 1},
        ]
        candidates = tracer._find_candidates(50, all_accounts, subtotal_line=5)
        negative = [c for c in candidates if c["match_type"] in ("negative_exact", "sign_flip")]
        assert len(negative) >= 1

    def test_no_candidates(self):
        tracer = SubtotalTracer()
        all_accounts = [
            {"nombre": "Caja", "monto": 100, "linea": 0},
        ]
        candidates = tracer._find_candidates(999, all_accounts, subtotal_line=5)
        assert len(candidates) == 0

    def test_trace_has_candidates(self):
        tracer = SubtotalTracer()
        all_accounts = [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Faltante", "monto": 50, "linea": 1},
        ]
        trace = tracer.build_trace(
            source_file="t.pdf", subtotal_name="T", subtotal_line=5,
            expected=100, actual=50, difference=50, pct_diff=50,
            children=[], all_accounts=all_accounts,
        )
        assert len(trace.candidates) >= 1


# ========= HIERARCHY COMPARATOR TESTS =========

class TestHierarchyComparator:
    def test_account_exists(self):
        hc = HierarchyComparator()
        result = hc.compare("Caja", 100, 0, [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Banco", "monto": 200, "linea": 1},
        ], [])
        assert result.exists is True

    def test_account_not_found(self):
        hc = HierarchyComparator()
        result = hc.compare("NoExiste", 100, 0, [
            {"nombre": "Caja", "monto": 100, "linea": 0},
        ], [])
        assert result.exists is False

    def test_find_duplicates(self):
        hc = HierarchyComparator()
        dups = hc.find_duplicates("Caja", [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Caja", "monto": 200, "linea": 1},
            {"nombre": "Banco", "monto": 300, "linea": 2},
        ])
        assert len(dups) == 2

    def test_no_duplicates(self):
        hc = HierarchyComparator()
        dups = hc.find_duplicates("Caja", [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Banco", "monto": 200, "linea": 1},
        ])
        assert len(dups) == 1

    def test_find_in_other_sections(self):
        hc = HierarchyComparator()
        others = hc.find_in_other_sections("Caja", [
            {"nombre": "Caja Chica", "monto": 50, "linea": 0},
            {"nombre": "Banco", "monto": 200, "linea": 1},
        ])
        assert len(others) >= 1

    def test_section_classification(self):
        from analysis.hierarchy_comparator import _classify_section
        assert _classify_section("Activo Corriente") == "ACTIVO"
        assert _classify_section("Pasivo No Corriente") == "PASIVO"
        assert _classify_section("Patrimonio Neto") == "PATRIMONIO"
        assert _classify_section("Resultado del Ejercicio") == "RESULTADO"
        assert _classify_section("Ingresos por Ventas") == "INGRESOS"
        assert _classify_section("Costo de Ventas") == "COSTOS"
        assert _classify_section("Gastos de Administracion") == "GASTOS"
        assert _classify_section("Algo") == ""


# ========= ROOT CAUSE CLASSIFIER TESTS =========

class TestRootCauseClassifier:
    def test_valid_causes(self):
        expected = [
            "MISSING_ACCOUNT", "WRONG_PARENT", "WRONG_SECTION",
            "WRONG_LEVEL", "DUPLICATED_ACCOUNT", "SIGN_ERROR",
            "OCR_ERROR", "PARSER_EXTRACTION", "SPECIAL_BALANCE", "UNKNOWN",
        ]
        assert VALID_CAUSES == expected

    def test_special_balance_detection(self):
        classifier = RootCauseClassifier()
        assert classifier.is_special_balance("NOTA 1 - Activo")
        assert classifier.is_special_balance("ANEXO ACTIVO FIJO")
        assert classifier.is_special_balance("INFORME TASACION")
        assert classifier.is_special_balance("CPT TASACION")
        assert not classifier.is_special_balance("Total Activo Corriente")

    def test_classify_sign_error(self):
        classifier = RootCauseClassifier()
        from analysis.subtotal_trace import SubtotalTrace
        trace = SubtotalTrace(
            source_file="t.pdf", subtotal_name="Total", subtotal_line=5,
            expected=100, actual=150, difference=-50, pct_diff=50,
            candidates=[{"account_name": "Negativo", "amount": -50, "line": 1,
                         "match_type": "sign_flip", "similarity": 100.0}],
        )
        result = classifier.classify(trace, [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Negativo", "monto": -50, "linea": 1},
        ], [])
        assert result.cause == "SIGN_ERROR"

    def test_classify_wrong_parent(self):
        classifier = RootCauseClassifier()
        from analysis.subtotal_trace import SubtotalTrace
        trace = SubtotalTrace(
            source_file="t.pdf", subtotal_name="Total", subtotal_line=5,
            expected=100, actual=50, difference=50, pct_diff=50,
            candidates=[{"account_name": "Caja", "amount": 50, "line": 1,
                         "match_type": "exact", "similarity": 100.0}],
        )
        result = classifier.classify(trace, [
            {"nombre": "Caja", "monto": 50, "linea": 1},
        ], [])
        assert result.cause == "WRONG_PARENT"

    def test_classify_unknown(self):
        classifier = RootCauseClassifier()
        from analysis.subtotal_trace import SubtotalTrace
        trace = SubtotalTrace(
            source_file="t.pdf", subtotal_name="Total", subtotal_line=5,
            expected=100, actual=10, difference=90, pct_diff=90,
        )
        result = classifier.classify(trace, [], [])
        assert result.cause == "UNKNOWN"

    def test_classify_duplicated(self):
        classifier = RootCauseClassifier()
        from analysis.subtotal_trace import SubtotalTrace
        trace = SubtotalTrace(
            source_file="t.pdf", subtotal_name="Total", subtotal_line=5,
            expected=200, actual=100, difference=100, pct_diff=50,
            children_found=[
                {"nombre": "Caja", "amount": 100, "linea": 0},
                {"nombre": "Caja", "amount": 100, "linea": 1},
            ],
        )
        result = classifier.classify(trace, [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Caja", "monto": 100, "linea": 1},
            {"nombre": "Banco", "monto": 100, "linea": 2},
        ], [])
        assert result.cause == "DUPLICATED_ACCOUNT"

    def test_classify_missing_account(self):
        classifier = RootCauseClassifier()
        from analysis.subtotal_trace import SubtotalTrace
        trace = SubtotalTrace(
            source_file="t.pdf", subtotal_name="Total", subtotal_line=5,
            expected=100, actual=50, difference=50, pct_diff=50,
            children_considered=[
                {"nombre": "Caja", "amount": 50, "linea": 0, "es_total": False},
                {"nombre": "Faltante", "amount": 50, "linea": 1, "es_total": True},
            ],
            children_found=[
                {"nombre": "Caja", "amount": 50, "linea": 0},
            ],
            excluded_accounts=[
                {"nombre": "Faltante", "amount": 50, "linea": 1, "es_total": True},
            ],
            candidates=[],
        )
        result = classifier.classify(trace, [], [])
        assert result.cause == "MISSING_ACCOUNT"

    def test_small_diff_is_parser_extraction(self):
        classifier = RootCauseClassifier()
        from analysis.subtotal_trace import SubtotalTrace
        trace = SubtotalTrace(
            source_file="t.pdf", subtotal_name="Total", subtotal_line=5,
            expected=1000000, actual=999000, difference=1000, pct_diff=0.1,
            children_found=[{"nombre": "Caja", "amount": 999000, "linea": 0}],
            candidates=[],
        )
        result = classifier.classify(trace, [{"nombre": "Caja", "monto": 999000, "linea": 0}], [])
        assert result.cause == "PARSER_EXTRACTION"


# ========= STATISTICS TESTS =========

class TestStatistics:
    def test_empty_stats(self):
        stats = StatisticsGenerator()
        assert stats.total_differences == 0
        assert stats.cause_distribution() == {}

    def test_add_result(self):
        stats = StatisticsGenerator()
        from analysis.subtotal_trace import SubtotalTrace, RootCauseResult
        trace = SubtotalTrace(source_file="t.pdf")
        cause = RootCauseResult(cause="MISSING_ACCOUNT")
        stats.add_result(trace, cause, "TEST_FORMAT")
        assert stats.total_differences == 1

    def test_cause_distribution(self):
        stats = StatisticsGenerator()
        from analysis.subtotal_trace import SubtotalTrace, RootCauseResult
        for c in ["MISSING_ACCOUNT", "WRONG_PARENT", "MISSING_ACCOUNT"]:
            stats.add_result(SubtotalTrace(source_file="t.pdf"), RootCauseResult(cause=c), "")
        dist = stats.cause_distribution()
        assert dist["MISSING_ACCOUNT"] == 2
        assert dist["WRONG_PARENT"] == 1

    def test_format_distribution(self):
        stats = StatisticsGenerator()
        from analysis.subtotal_trace import SubtotalTrace, RootCauseResult
        stats.add_result(SubtotalTrace(source_file="a.pdf"), RootCauseResult(cause="A"), "FMT1")
        stats.add_result(SubtotalTrace(source_file="b.pdf"), RootCauseResult(cause="B"), "FMT2")
        stats.add_result(SubtotalTrace(source_file="c.pdf"), RootCauseResult(cause="C"), "FMT1")
        dist = stats.format_distribution()
        assert dist["FMT1"] == 2
        assert dist["FMT2"] == 1

    def test_cause_by_format_matrix(self):
        stats = StatisticsGenerator()
        from analysis.subtotal_trace import SubtotalTrace, RootCauseResult
        stats.add_result(SubtotalTrace(source_file="a.pdf"), RootCauseResult(cause="MISSING_ACCOUNT"), "FMT1")
        stats.add_result(SubtotalTrace(source_file="b.pdf"), RootCauseResult(cause="WRONG_PARENT"), "FMT2")
        matrix = stats.cause_by_format_matrix()
        assert len(matrix) == 2

    def test_find_patterns(self):
        stats = StatisticsGenerator()
        from analysis.subtotal_trace import SubtotalTrace, RootCauseResult
        for i in range(3):
            tr = SubtotalTrace(
                source_file=f"f{i}.pdf",
                subtotal_name="Total Activo Corriente",
                difference=100,
            )
            rc = RootCauseResult(cause="MISSING_ACCOUNT")
            stats.add_result(tr, rc, "FMT")
        patterns = stats.find_patterns(top_n=10)
        assert len(patterns) >= 1
        assert patterns[0].frequency == 3

    def test_calculate_impact(self):
        stats = StatisticsGenerator()
        from analysis.subtotal_trace import SubtotalTrace, RootCauseResult
        causes = ["MISSING_ACCOUNT", "WRONG_PARENT", "OCR_ERROR",
                   "DUPLICATED_ACCOUNT", "SPECIAL_BALANCE", "UNKNOWN"]
        for i, c in enumerate(causes):
            stats.add_result(SubtotalTrace(source_file=f"f{i}.pdf"), RootCauseResult(cause=c), "")
        impact = stats.calculate_impact_potential()
        assert impact["parser_improvement"]["count"] == 1
        assert impact["hierarchy_improvement"]["count"] == 1
        assert impact["dictionary_improvement"]["count"] == 1
        assert impact["knowledge_base_improvement"]["count"] == 1
        assert impact["human_review"]["count"] == 2

    def test_find_conflictive_accounts(self):
        stats = StatisticsGenerator()
        from analysis.subtotal_trace import SubtotalTrace, RootCauseResult
        for i in range(3):
            tr = SubtotalTrace(
                source_file=f"f{i}.pdf",
                subtotal_name="Total",
                children_considered=[
                    {"nombre": "Caja", "amount": 100},
                    {"nombre": "Banco", "amount": 200},
                ],
                difference=50,
            )
            rc = RootCauseResult(cause="MISSING_ACCOUNT")
            stats.add_result(tr, rc, "")
        conflictive = stats.find_conflictive_accounts(top_n=10)
        assert len(conflictive) >= 2

    def test_find_repeated_account_causes(self):
        stats = StatisticsGenerator()
        from analysis.subtotal_trace import SubtotalTrace, RootCauseResult
        for i in range(3):
            tr = SubtotalTrace(
                source_file=f"f{i}.pdf",
                subtotal_name="Total",
                children_considered=[
                    {"nombre": "Caja", "amount": 100},
                ],
            )
            rc = RootCauseResult(cause="WRONG_PARENT")
            stats.add_result(tr, rc, "")
        repeated = stats.find_repeated_account_causes(top_n=10)
        assert len(repeated) >= 1
        assert repeated[0]["account"] == "Caja"

    def test_cross_reference_gold_standard(self):
        stats = StatisticsGenerator()
        gs = [{"account_name": "Caja"}, {"account_name": "Banco"}]
        kb = ["Caja chica"]
        ref = stats.cross_reference_gold_standard(["Caja", "NoExiste"], gs, kb)
        assert ref["Caja"]["in_gold_standard"] is True
        assert ref["NoExiste"]["in_gold_standard"] is False


# ========= STRUCTURE TRUTH ANALYZER TESTS =========

class TestStructureTruthAnalyzer:
    def test_analyze_empty_result(self):
        analyzer = StructureTruthAnalyzer()
        vr = ValidationResult(source_file="t.pdf")
        causes = analyzer.analyze_validation_result(vr)
        assert len(causes) == 0

    def test_analyze_with_failed_subtotals(self):
        analyzer = StructureTruthAnalyzer()
        vr = ValidationResult(source_file="t.pdf", accounts_total=3)
        vr.subtotal_results = [
            SubtotalResult(
                account_name="Total", passed=False,
                expected=100, actual=50, difference=50, pct_diff=50,
                children=["Caja"],
            ),
        ]
        all_accounts = [
            {"nombre": "Caja", "amount": 50, "linea": 0, "es_total": False},
        ]
        causes = analyzer.analyze_validation_result(vr, all_accounts=all_accounts)
        assert len(causes) == 1
        assert causes[0].cause in VALID_CAUSES

    def test_analyze_skips_passed(self):
        analyzer = StructureTruthAnalyzer()
        vr = ValidationResult(source_file="t.pdf")
        vr.subtotal_results = [
            SubtotalResult(
                account_name="Total", passed=True,
                expected=100, actual=100, difference=0, pct_diff=0,
            ),
        ]
        causes = analyzer.analyze_validation_result(vr)
        assert len(causes) == 0

    def test_generate_report_empty(self):
        analyzer = StructureTruthAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            md_path = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_path = f.name
        try:
            analyzer.generate_report_section(md_path, json_path)
            assert os.path.exists(md_path)
            assert os.path.exists(json_path)
            content = open(md_path).read()
            assert "Executive Summary" in content
        finally:
            os.unlink(md_path)
            os.unlink(json_path)

    def test_load_gold_standard(self):
        analyzer = StructureTruthAnalyzer()
        gs = analyzer.load_gold_standard()
        assert len(gs) > 0
        assert "codigo_estandar" in gs[0]
        assert "nombre_cuenta" in gs[0]

    def test_load_kb_variants(self):
        analyzer = StructureTruthAnalyzer()
        kb = analyzer.load_kb_variants()
        assert len(kb) > 0


# ========= SUBTOTAL TRACE DATACLASS TESTS =========

class TestSubtotalTraceDataclass:
    def test_defaults(self):
        trace = SubtotalTrace()
        assert trace.source_file == ""
        assert trace.expected == 0.0
        assert len(trace.candidates) == 0

    def test_with_values(self):
        trace = SubtotalTrace(
            source_file="test.pdf", subtotal_name="Total",
            expected=100, actual=50, difference=50, pct_diff=50,
            candidates=[{"account_name": "Test", "amount": 50}],
        )
        assert trace.difference == 50


# ========= ROOT CAUSE RESULT TESTS =========

class TestRootCauseResult:
    def test_defaults(self):
        from analysis.subtotal_trace import RootCauseResult
        r = RootCauseResult()
        assert r.cause == ""
        assert r.certainty == 0.0


# ========= HIERARCHY COMPARISON DATACLASS TESTS =========

class TestHierarchyComparison:
    def test_defaults(self):
        hc = HierarchyComparison()
        assert hc.exists is False
        assert hc.correct_level is None


# ========= PATTERN RESULT DATACLASS TESTS =========

class TestPatternResult:
    def test_defaults(self):
        p = PatternResult()
        assert p.frequency == 0

    def test_with_values(self):
        p = PatternResult(
            account_name="Total Activo", frequency=5,
            avg_difference=100, typical_cause="WRONG_PARENT",
        )
        assert p.frequency == 5


# ========= FORMAT MATRIX TESTS =========

class TestFormatMatrix:
    def test_defaults(self):
        fm = FormatMatrix()
        assert fm.total_differences == 0
        assert fm.by_cause == {}


# ========= EDGE CASE TESTS =========

class TestEdgeCases:
    def test_empty_all_accounts(self):
        tracer = SubtotalTracer()
        trace = tracer.build_trace(
            source_file="t.pdf", subtotal_name="T", subtotal_line=0,
            expected=100, actual=0, difference=100, pct_diff=100,
            children=[], all_accounts=[],
        )
        assert len(trace.candidates) == 0

    def test_negative_difference(self):
        tracer = SubtotalTracer()
        trace = tracer.build_trace(
            source_file="t.pdf", subtotal_name="T", subtotal_line=0,
            expected=0, actual=100, difference=-100, pct_diff=100,
            children=[], all_accounts=[],
        )
        assert trace.difference == -100

    def test_zero_difference(self):
        tracer = SubtotalTracer()
        trace = tracer.build_trace(
            source_file="t.pdf", subtotal_name="T", subtotal_line=0,
            expected=100, actual=100, difference=0, pct_diff=0,
            children=[], all_accounts=[],
        )
        assert trace.difference == 0

    def test_large_difference(self):
        tracer = SubtotalTracer()
        all_accounts = [{"nombre": "Caja", "monto": 999999999, "linea": 0}]
        candidates = tracer._find_candidates(999999999, all_accounts, subtotal_line=1)
        assert len(candidates) >= 1

    def test_mixed_case_name_matching(self):
        hc = HierarchyComparator()
        result = hc.compare("CAJA", 100, 0, [
            {"nombre": "Caja", "monto": 100, "linea": 0},
        ], [])
        assert result.exists is True

    def test_fuzzy_name_matching(self):
        hc = HierarchyComparator()
        result = hc.compare("Total Activo Corriente", 0, 0, [
            {"nombre": "Caja", "monto": 100, "linea": 0},
            {"nombre": "Banco", "monto": 200, "linea": 1},
        ], [])
        assert result.exists is False

    def test_special_balance_various(self):
        classifier = RootCauseClassifier()
        assert classifier.is_special_balance("NOTA 1")
        assert classifier.is_special_balance("ANEXO 1")
        assert classifier.is_special_balance("INVENTARIO FISICO")
        assert not classifier.is_special_balance("Activo")
