from __future__ import annotations
import sys, os, json, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from structure_engine.structure_models import (
    StructuralNode, StructuralTree, StructureTemplate,
    TemplateMatch, StructuralFamily, SectionInfo,
    StructuralSignature,
)
from structure_engine.structure_detector import StructureDetector
from structure_engine.tree_builder import TreeBuilder
from structure_engine.template_builder import TemplateBuilder
from structure_engine.template_matcher import TemplateMatcher
from structure_engine.template_repository import TemplateRepository
from structure_engine.family_detector import FamilyDetector
from structure_engine.statistics import StructureStatistics


# ========= STRUCTURAL NODE TESTS =========

class TestStructuralNode:
    def test_create_node(self):
        n = StructuralNode(original_name="Caja", structural_type="D", depth=1)
        assert n.original_name == "Caja"
        assert n.structural_type == "D"
        assert n.depth == 1

    def test_add_child(self):
        parent = StructuralNode(original_name="P", structural_type="H", depth=0)
        child = StructuralNode(original_name="C", structural_type="D", depth=1)
        parent.children.append(child)
        child.parent = parent
        assert len(parent.children) == 1
        assert child.parent is parent


# ========= STRUCTURAL TREE TESTS =========

class TestStructuralTree:
    def test_empty_tree(self):
        t = StructuralTree()
        assert t.total_nodes == 0
        assert t.signature is not None

    def test_signature(self):
        t = StructuralTree(
            source_file="test.pdf",
            total_nodes=5,
            max_depth=2,
            subtotal_count=1,
            section_count=3,
            type_sequence="HDDSD",
            code_format="PUNTO",
            column_layout="DOUBLE_COLUMN",
            level_distribution={0: 2, 1: 2, 2: 1},
        )
        sig = t.signature
        assert sig.type_sequence == "HDDSD"
        assert sig.max_depth == 2

    def test_signature_similarity_identical(self):
        s1 = StructuralSignature(type_sequence="HDDSD", max_depth=2, total_nodes=5,
                                  subtotal_ratio=0.2, section_count=3,
                                  level_distribution=((0, 2), (1, 2), (2, 1)),
                                  code_format="PUNTO", column_layout="DOUBLE")
        s2 = StructuralSignature(type_sequence="HDDSD", max_depth=2, total_nodes=5,
                                  subtotal_ratio=0.2, section_count=3,
                                  level_distribution=((0, 2), (1, 2), (2, 1)),
                                  code_format="PUNTO", column_layout="DOUBLE")
        assert s1.similarity_to(s2) >= 0.99

    def test_signature_similarity_different(self):
        s1 = StructuralSignature(type_sequence="HHHH", max_depth=0, total_nodes=4,
                                  subtotal_ratio=0.0, section_count=1,
                                  level_distribution=((0, 4),),
                                  code_format="SIN_CODIGO", column_layout="SINGLE")
        s2 = StructuralSignature(type_sequence="DDDDDDDS", max_depth=3, total_nodes=8,
                                  subtotal_ratio=0.125, section_count=3,
                                  level_distribution=((0, 2), (1, 3), (2, 2), (3, 1)),
                                  code_format="PUNTO", column_layout="DOUBLE")
        assert s1.similarity_to(s2) < 0.9


# ========= STRUCTURE DETECTOR TESTS =========

class TestStructureDetector:
    def test_detect_type_header(self):
        assert StructureDetector.detect_type("Activo", False, 0) == "H"
        assert StructureDetector.detect_type("Pasivo Corriente", False, 0) == "H"
        assert StructureDetector.detect_type("Patrimonio Neto", False, 0) == "H"

    def test_detect_type_subtotal(self):
        assert StructureDetector.detect_type("Total Activo", False, 100) == "S"
        assert StructureDetector.detect_type("SUBTOTAL", False, 50) == "S"
        assert StructureDetector.detect_type("Suma", False, 200) == "S"

    def test_detect_type_detail(self):
        assert StructureDetector.detect_type("Caja", False, 100) == "D"
        assert StructureDetector.detect_type("Banco", False, 200) == "D"

    def test_detect_type_intermediate(self):
        assert StructureDetector.detect_type("Header sin monto", False, 0) == "I"

    def test_detect_type_es_total(self):
        assert StructureDetector.detect_type("Cualquier Cosa", True, 0) == "S"

    def test_detect_section(self):
        assert StructureDetector.detect_section("Activo Corriente") == "ACTIVO_CORRIENTE"
        assert StructureDetector.detect_section("Pasivo No Corriente") == "PASIVO_NO_CORRIENTE"
        assert StructureDetector.detect_section("Resultado del Ejercicio") == "RESULTADO"
        assert StructureDetector.detect_section("", "") == ""

    def test_detect_section_by_column(self):
        assert StructureDetector.detect_section("Caja", "activo") == "ACTIVO"
        assert StructureDetector.detect_section("Proveedores", "pasivo") == "PASIVO"

    def test_detect_code_format(self):
        assert StructureDetector.detect_code_format([
            {"codigo": "1.1.01"}, {"codigo": "1.1.02"},
        ]) == "PUNTO"
        assert StructureDetector.detect_code_format([
            {"codigo": "1-01-01"}, {"codigo": "1-01-02"},
        ]) == "GUION"
        assert StructureDetector.detect_code_format([
            {"codigo": "11101"}, {"codigo": "11102"},
        ]) == "COMPACTO"
        assert StructureDetector.detect_code_format([
            {"codigo": ""}, {"codigo": ""},
        ]) == "SIN_CODIGO"

    def test_detect_column_layout(self):
        assert StructureDetector.detect_column_layout([
            {"origen_columna": "activo"}, {"origen_columna": "pasivo"},
        ]) == "DOUBLE_COLUMN"
        assert StructureDetector.detect_column_layout([
            {"origen_columna": "activo"},
        ]) == "ACTIVO"

    def test_detect_level(self):
        assert StructureDetector.detect_level("1.1.01", "") == 2
        assert StructureDetector.detect_level("1-01-01", "") == 2
        assert StructureDetector.detect_level("11101", "") == 2
        assert StructureDetector.detect_level("", "") == 0

    def test_find_repeated_patterns(self):
        seq = "HDDSHDDSHDDS"
        patterns = StructureDetector.find_repeated_patterns(seq)
        assert len(patterns) >= 1
        assert any(p[0] == "HDDS" for p in patterns)

    def test_compute_type_sequence(self):
        class MockNode:
            def __init__(self, t):
                self.structural_type = t
        nodes = [MockNode("H"), MockNode("D"), MockNode("S")]
        seq = StructureDetector.compute_type_sequence(nodes)
        assert seq == "HDS"


# ========= TREE BUILDER TESTS =========

class TestTreeBuilder:
    def test_empty(self):
        b = TreeBuilder()
        tree = b.build_tree([])
        assert tree.total_nodes == 0

    def test_simple_tree(self):
        raw = [
            {"nombre": "Activo", "monto": 0, "codigo": "1", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Caja", "monto": 100, "codigo": "1.1", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Total", "monto": 100, "codigo": "1.2", "origen_columna": "activo", "es_total": True, "linea": 2},
        ]
        b = TreeBuilder()
        tree = b.build_tree(raw)
        assert tree.total_nodes == 3
        assert tree.max_depth >= 1
        assert tree.type_sequence == "HDS"

    def test_section_detection(self):
        raw = [
            {"nombre": "Activo", "monto": 0, "codigo": "", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Caja", "monto": 100, "codigo": "", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Pasivo", "monto": 0, "codigo": "", "origen_columna": "", "es_total": False, "linea": 2},
            {"nombre": "Proveedores", "monto": 50, "codigo": "", "origen_columna": "pasivo", "es_total": False, "linea": 3},
        ]
        b = TreeBuilder()
        tree = b.build_tree(raw)
        assert tree.section_count >= 2

    def test_parent_links(self):
        raw = [
            {"nombre": "Activo", "monto": 0, "codigo": "1", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Caja", "monto": 100, "codigo": "1.1", "origen_columna": "", "es_total": False, "linea": 1},
            {"nombre": "Banco", "monto": 200, "codigo": "1.2", "origen_columna": "", "es_total": False, "linea": 2},
        ]
        b = TreeBuilder()
        tree = b.build_tree(raw)
        assert len(tree.nodes) == 3
        parent = tree.nodes[0]
        assert len(parent.children) >= 1


# ========= TEMPLATE BUILDER TESTS =========

class TestTemplateBuilder:
    def test_build_template(self):
        raw = [
            {"nombre": "Activo", "monto": 0, "codigo": "1", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Caja", "monto": 100, "codigo": "1.1", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Total", "monto": 100, "codigo": "1.2", "origen_columna": "activo", "es_total": True, "linea": 2},
        ]
        b = TreeBuilder()
        tree = b.build_tree(raw)
        template = TemplateBuilder.build_template(tree, file_name="test.pdf")
        assert template.template_id
        assert template.type_sequence == "HDS"
        assert template.total_nodes == 3
        assert "test.pdf" in template.example_files

    def test_templates_similar_identical(self):
        t1 = StructureTemplate(
            template_id="abc", type_sequence="HDS",
            signatures=[StructuralSignature(type_sequence="HDS", max_depth=1, total_nodes=3,
                                            subtotal_ratio=0.33, section_count=1,
                                            level_distribution=((0, 1), (1, 2)),
                                            code_format="PUNTO", column_layout="SINGLE")],
        )
        t2 = StructureTemplate(
            template_id="def", type_sequence="HDS",
            signatures=[StructuralSignature(type_sequence="HDS", max_depth=1, total_nodes=3,
                                            subtotal_ratio=0.33, section_count=1,
                                            level_distribution=((0, 1), (1, 2)),
                                            code_format="PUNTO", column_layout="SINGLE")],
        )
        sim = TemplateBuilder.templates_similar(t1, t2)
        assert sim >= 0.99

    def test_merge_templates(self):
        t1 = StructureTemplate(
            template_id="abc", type_sequence="HDS",
            example_files=["a.pdf"], frequency=1,
        )
        t2 = StructureTemplate(
            template_id="def", type_sequence="HDS",
            example_files=["b.pdf"], frequency=1,
        )
        merged = TemplateBuilder.merge_templates(t1, t2)
        assert merged.frequency == 2
        assert "a.pdf" in merged.example_files
        assert "b.pdf" in merged.example_files


# ========= TEMPLATE MATCHER TESTS =========

class TestTemplateMatcher:
    def test_match_exact(self):
        t = StructureTemplate(
            template_id="abc", family="TEST", name="test",
            type_sequence="HDS",
            signatures=[StructuralSignature(type_sequence="HDS", max_depth=1, total_nodes=3,
                                            subtotal_ratio=0.33, section_count=1,
                                            level_distribution=((0, 1), (1, 2)),
                                            code_format="PUNTO", column_layout="SINGLE")],
        )
        matcher = TemplateMatcher([t])

        tree = StructuralTree(
            source_file="test.pdf", total_nodes=3, max_depth=1,
            subtotal_count=1, section_count=1, type_sequence="HDS",
            code_format="PUNTO", column_layout="SINGLE",
            level_distribution={0: 1, 1: 2},
        )
        match = matcher.best_match(tree)
        assert match is not None
        assert match.similarity >= 50.0

    def test_no_match(self):
        matcher = TemplateMatcher([])
        tree = StructuralTree(type_sequence="H")
        match = matcher.best_match(tree)
        assert match is None

    def test_match_returns_sorted(self):
        t1 = StructureTemplate(
            template_id="low", type_sequence="HHHH",
            signatures=[StructuralSignature(type_sequence="HHHH", max_depth=0, total_nodes=4,
                                            subtotal_ratio=0.0, section_count=1,
                                            level_distribution=((0, 4),),
                                            code_format="SIN_CODIGO", column_layout="SINGLE")],
        )
        matcher = TemplateMatcher([t1])
        tree = StructuralTree(type_sequence="HDDS", max_depth=2, total_nodes=4,
                               subtotal_count=1, section_count=2,
                               level_distribution={0: 2, 1: 1, 2: 1},
                               code_format="PUNTO", column_layout="DOUBLE")
        match = matcher.best_match(tree, min_similarity=0.3)
        assert match is None or match.similarity < 70.0


# ========= TEMPLATE REPOSITORY TESTS =========

class TestTemplateRepository:
    def test_add_and_get(self):
        repo = TemplateRepository()
        t = StructureTemplate(template_id="abc", type_sequence="HDS")
        repo.add_template(t)
        assert repo.get("abc") is t
        assert repo.total_templates == 1

    def test_merge_on_add(self):
        repo = TemplateRepository()
        t1 = StructureTemplate(template_id="abc", type_sequence="HDS", frequency=1)
        t2 = StructureTemplate(template_id="abc", type_sequence="HDS", frequency=1)
        repo.add_template(t1)
        repo.add_template(t2)
        assert repo.total_templates == 1
        assert repo.get("abc").frequency == 2

    def test_save_load(self):
        repo = TemplateRepository()
        repo.add_template(StructureTemplate(
            template_id="abc", family="TEST", name="t1",
            type_sequence="HDS", frequency=2,
        ))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp = f.name
        try:
            repo.save(tmp)
            repo2 = TemplateRepository()
            repo2.load(tmp)
            assert repo2.total_templates == 1
            assert repo2.get("abc").frequency == 2
        finally:
            os.unlink(tmp)

    def test_empty_repo(self):
        repo = TemplateRepository()
        assert repo.total_templates == 0
        assert repo.total_files == 0


# ========= FAMILY DETECTOR TESTS =========

class TestFamilyDetector:
    def test_classify_simple(self):
        t = StructureTemplate(total_nodes=10, subtotal_count=5, max_depth=2, section_count=3)
        FamilyDetector.classify(t)
        assert t.family in ("CLASIFICADO", "BALANCE_ESTANDAR", "DESCONOCIDO")

    def test_build_families(self):
        t1 = StructureTemplate(template_id="a", family="FAM_A", type_sequence="HDS")
        t2 = StructureTemplate(template_id="b", family="FAM_A", type_sequence="HDD")
        t3 = StructureTemplate(template_id="c", family="FAM_B", type_sequence="H")
        families = FamilyDetector.build_families([t1, t2, t3])
        assert len(families) == 2
        fam_a = [f for f in families if f.name == "FAM_A"][0]
        assert len(fam_a.templates) == 2


# ========= STATISTICS TESTS =========

class TestStatistics:
    def test_tree_stats_empty(self):
        stats = StructureStatistics.tree_stats([])
        assert stats == {}

    def test_tree_stats(self):
        trees = [
            StructuralTree(total_nodes=10, max_depth=3, subtotal_count=2, section_count=3,
                           code_format="PUNTO", column_layout="SINGLE"),
            StructuralTree(total_nodes=5, max_depth=1, subtotal_count=1, section_count=1,
                           code_format="SIN_CODIGO", column_layout="DOUBLE"),
        ]
        stats = StructureStatistics.tree_stats(trees)
        assert stats["total_trees"] == 2
        assert stats["avg_depth"] == 2.0
        assert "PUNTO" in stats["code_format_dist"]

    def test_template_stats_empty(self):
        assert StructureStatistics.template_stats([]) == {}

    def test_template_stats(self):
        templates = [
            StructureTemplate(total_nodes=50, max_depth=3, family="A", frequency=2,
                              code_format="PUNTO"),
            StructureTemplate(total_nodes=10, max_depth=1, family="B", frequency=1,
                              code_format="SIN_CODIGO"),
        ]
        stats = StructureStatistics.template_stats(templates)
        assert stats["total_templates"] == 2
        assert stats["total_files"] == 3

    def test_family_stats(self):
        families = [StructuralFamily(name="A", total_members=5),
                     StructuralFamily(name="B", total_members=3)]
        stats = StructureStatistics.family_stats(families, [StructuralTree()] * 8)
        assert stats["total_families"] == 2
        assert stats["largest"] == 5
        assert stats["family_sizes"]["A"] == 5

    def test_generate_markdown_report(self):
        report = StructureStatistics.generate_markdown_report(
            {"total_trees": 5, "avg_depth": 2.0, "avg_nodes": 10.0,
             "avg_subtotals": 2.0, "avg_sections": 1.5, "max_depth": 4, "min_depth": 1,
             "code_format_dist": {"PUNTO": 3}, "column_layout_dist": {"SINGLE": 3},
             "type_complexity": {"flat": 2, "deep": 3}},
            {"total_templates": 3, "total_files": 5, "avg_frequency": 1.7,
             "family_dist": {"A": 2}, "code_format_dist": {"PUNTO": 3},
             "avg_depth": 2.0, "avg_nodes": 8.0,
             "by_complexity": {"simple": 1, "medium": 2}},
            {"total_families": 2, "largest": 3, "smallest": 2,
             "family_sizes": {"A": 3, "B": 2}, "coverage_pct": {"A": 60.0}},
            [("HDD", 5), ("HDS", 3)],
        )
        assert "Tree Statistics" in report
        assert "Template Statistics" in report
        assert "Family Statistics" in report

    def test_signature_similarity_partial(self):
        s1 = StructuralSignature(type_sequence="HDS", max_depth=1, total_nodes=3,
                                  subtotal_ratio=0.33, section_count=1,
                                  level_distribution=((0, 1), (1, 2)),
                                  code_format="PUNTO", column_layout="SINGLE")
        s2 = StructuralSignature(type_sequence="HDD", max_depth=1, total_nodes=3,
                                  subtotal_ratio=0.0, section_count=1,
                                  level_distribution=((0, 1), (1, 2)),
                                  code_format="PUNTO", column_layout="SINGLE")
        sim = s1.similarity_to(s2)
        assert 0.3 < sim < 1.0

    def test_sequence_similarity_identical(self):
        from structure_engine.structure_models import _sequence_similarity
        assert _sequence_similarity("HDS", "HDS") == 1.0

    def test_sequence_similarity_partial(self):
        from structure_engine.structure_models import _sequence_similarity
        sim = _sequence_similarity("HDS", "HDD")
        assert 0 < sim < 1

    def test_sequence_similarity_empty(self):
        from structure_engine.structure_models import _sequence_similarity
        assert _sequence_similarity("", "") == 0.0

    def test_section_overlap(self):
        from structure_engine.template_matcher import _section_overlap
        o, t = _section_overlap(["ACTIVO", "PASIVO"], ["ACTIVO", "PASIVO", "PATRIMONIO"])
        assert o == 2
        assert t >= 2

    def test_full_pipeline(self):
        raw = [
            {"nombre": "Activo", "monto": 0, "codigo": "1", "origen_columna": "", "es_total": False, "linea": 0},
            {"nombre": "Caja", "monto": 100, "codigo": "1.1", "origen_columna": "activo", "es_total": False, "linea": 1},
            {"nombre": "Total", "monto": 100, "codigo": "1.2", "origen_columna": "activo", "es_total": True, "linea": 2},
            {"nombre": "Pasivo", "monto": 0, "codigo": "2", "origen_columna": "", "es_total": False, "linea": 3},
            {"nombre": "Proveedores", "monto": 50, "codigo": "2.1", "origen_columna": "pasivo", "es_total": False, "linea": 4},
            {"nombre": "Total Pasivo", "monto": 50, "codigo": "2.2", "origen_columna": "pasivo", "es_total": True, "linea": 5},
        ]
        builder = TreeBuilder()
        tree = builder.build_tree(raw, source_file="test.pdf")
        assert tree.total_nodes == 6
        assert tree.section_count >= 2

        template = TemplateBuilder.build_template(tree, "test.pdf")
        assert template.type_sequence
        assert template.total_nodes == 6

        matcher = TemplateMatcher([template])
        match = matcher.best_match(tree)
        assert match is not None
        assert match.similarity >= 50.0
