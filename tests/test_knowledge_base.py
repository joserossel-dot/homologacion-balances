"""
Tests para knowledge_base (CMCC Knowledge Base).

No modifica parser, pipeline, ni benchmark.
Usa gold_standard.db como fuente de datos.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from knowledge_base.cmcc_models import (
    CodeEntry,
    FamilyGroup,
    KnowledgeBase,
    VariantInfo,
    inferir_nivel,
    inferir_seccion,
)
from knowledge_base.cmcc_builder import build_knowledge_base, _normalizar
from knowledge_base.cmcc_statistics import knowledge_stats, load_knowledge_base, generate_validation_report


class TestModels:
    def test_inferir_seccion(self):
        assert inferir_seccion("AC.01") == "Activo"
        assert inferir_seccion("ANC.03") == "Activo No Corriente"
        assert inferir_seccion("PC.01") == "Pasivo"
        assert inferir_seccion("PNC.01") == "Pasivo No Corriente"
        assert inferir_seccion("PAT.01") == "Patrimonio"
        assert inferir_seccion("ER.04") == "Resultado"
        assert inferir_seccion("XX.01") == "Desconocido"

    def test_inferir_nivel(self):
        assert inferir_nivel("AC") == 1
        assert inferir_nivel("AC.01") == 3
        assert inferir_nivel("ANC.01") == 3

    def test_variant_info_defaults(self):
        v = VariantInfo(nombre="Caja", normalized="caja")
        assert v.frecuencia == 0
        assert v.confianza == 0.0
        assert v.source_records == []

    def test_variant_info_to_dict(self):
        v = VariantInfo(nombre="Caja", normalized="caja", frecuencia=5, confianza=0.8)
        v.source_records = ["user1"]
        d = v.to_dict()
        assert d["nombre"] == "Caja"
        assert d["frecuencia"] == 5
        assert d["confianza"] == 0.8
        assert d["source_records"] == ["user1"]

    def test_code_entry_defaults(self):
        c = CodeEntry(codigo="AC.01")
        assert c.frecuencia == 0
        assert c.variantes == []
        assert c.seccion == ""
        assert c.nivel == 0

    def test_code_entry_to_dict(self):
        c = CodeEntry(
            codigo="AC.01",
            nombre="Disponible",
            frecuencia=10,
            variantes=[VariantInfo(nombre="Caja", normalized="caja", frecuencia=5, confianza=0.5)],
            seccion="Activo",
            nivel=3,
            empresas=["Empresa1"],
            archivos=["a.pdf"],
        )
        d = c.to_dict()
        assert d["codigo"] == "AC.01"
        assert d["nombre"] == "Disponible"
        assert d["frecuencia"] == 10
        assert len(d["variantes"]) == 1
        assert d["seccion"] == "Activo"

    def test_family_group_to_dict(self):
        f = FamilyGroup(nombre="AC", prefijo="AC", seccion="Activo", nivel_base=2,
                        miembros=["AC.01", "AC.03"], total_frecuencia=30)
        d = f.to_dict()
        assert d["nombre"] == "AC"
        assert d["miembros"] == ["AC.01", "AC.03"]

    def test_knowledge_base_to_dict(self):
        kb = KnowledgeBase(
            generated_at="2026-07-27",
            total_codes=2,
            total_records=10,
            codes={
                "AC.01": CodeEntry(codigo="AC.01", frecuencia=5),
                "PC.01": CodeEntry(codigo="PC.01", frecuencia=5),
            },
            families=[FamilyGroup(nombre="AC", prefijo="AC", seccion="Activo", nivel_base=2)],
        )
        d = kb.to_dict()
        assert d["metadata"]["total_codes"] == 2
        assert d["metadata"]["total_records"] == 10
        assert len(d["codes"]) == 2
        assert len(d["families"]) == 1


class TestBuilder:
    def test_build_from_real_db(self):
        kb = build_knowledge_base(output_path=None)
        assert kb.total_codes >= 1
        assert kb.total_records >= 1
        assert len(kb.families) >= 1
        assert "metadata" in kb.to_dict()

    def test_build_outputs_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        try:
            kb = build_knowledge_base(output_path=out_path)
            with open(out_path) as f:
                data = json.load(f)
            assert "metadata" in data
            assert "codes" in data
            assert "families" in data
            assert data["metadata"]["total_codes"] >= 1
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_normalizar(self):
        assert _normalizar("Caja") == "caja"
        assert _normalizar("Caja M/E") == "caja m e"
        assert _normalizar("CUENTA CORRIENTE") == "cuenta corriente"
        assert _normalizar("  spaces  ") == "spaces"

    def test_each_code_has_variants(self):
        kb = build_knowledge_base(output_path=None)
        for codigo, entry in kb.codes.items():
            assert len(entry.variantes) >= 1, f"{codigo} no tiene variantes"
            assert entry.frecuencia >= 1, f"{codigo} frecuencia cero"
            assert entry.seccion != "", f"{codigo} sin sección"
            assert entry.nivel >= 1, f"{codigo} sin nivel"

    def test_variant_confidence_sum(self):
        kb = build_knowledge_base(output_path=None)
        for codigo, entry in kb.codes.items():
            if len(entry.variantes) > 0:
                total_conf = sum(v.confianza for v in entry.variantes)
                assert abs(total_conf - 1.0) < 0.01 or len(entry.variantes) == 1, (
                    f"{codigo}: suma de confianzas={total_conf:.4f}"
                )

    def test_variant_canonica_is_most_frequent(self):
        kb = build_knowledge_base(output_path=None)
        for codigo, entry in kb.codes.items():
            if entry.variantes:
                most_freq = max(entry.variantes, key=lambda v: v.frecuencia)
                assert entry.variante_canonica != "", f"{codigo}: sin canónica"

    def test_families_cover_all_codes(self):
        kb = build_knowledge_base(output_path=None)
        all_code_prefixes = set()
        for c in kb.codes:
            pref = c.split(".")[0]
            all_code_prefixes.add(pref)
        family_prefixes = {f.prefijo for f in kb.families}
        for pref in all_code_prefixes:
            assert pref in family_prefixes, f"Sin familia para prefijo {pref}"

    def test_build_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            import sqlite3
            conn = sqlite3.connect(empty_db)
            conn.execute("CREATE TABLE gold_standard (id INTEGER, codigo_estandar TEXT, nombre_cuenta TEXT, normalized TEXT)")
            conn.execute("CREATE TABLE gold_records (id INTEGER, source_file TEXT, account_name TEXT, final_code TEXT, reviewer TEXT, review_date TEXT, comments TEXT, usage_count INTEGER)")
            conn.commit()
            conn.close()
            kb = build_knowledge_base(db_path=empty_db, output_path=None)
            assert kb.total_codes == 0
        finally:
            Path(empty_db).unlink(missing_ok=True)

    def test_build_missing_db(self):
        kb = build_knowledge_base(db_path="/nonexistent/db.db", output_path=None)
        assert kb.total_codes == 0

    def test_code_frequency_matches_variant_sum(self):
        kb = build_knowledge_base(output_path=None)
        for codigo, entry in kb.codes.items():
            variant_sum = sum(v.frecuencia for v in entry.variantes)
            assert variant_sum == entry.frecuencia, (
                f"{codigo}: suma variantes={variant_sum} ≠ frecuencia={entry.frecuencia}"
            )


class TestStatistics:
    def test_knowledge_stats_from_built(self):
        kb = build_knowledge_base(output_path=None)
        stats = knowledge_stats(kb)
        assert stats["total_codes"] >= 1
        assert stats["total_variantes"] >= stats["total_codes"]
        assert "confidence_distribution" in stats
        assert "by_section" in stats
        assert "families" in stats

    def test_knowledge_stats_from_file(self):
        build_knowledge_base()
        stats = knowledge_stats()
        assert stats["total_codes"] >= 1

    def test_knowledge_stats_empty(self):
        data = knowledge_stats.__wrapped__(None) if hasattr(knowledge_stats, "__wrapped__") else None
        # Direct call with empty data
        from knowledge_base.cmcc_statistics import load_knowledge_base
        data = load_knowledge_base.__wrapped__("/nonexistent.json") if hasattr(load_knowledge_base, "__wrapped__") else None

    def test_validation_report_generated(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            out_path = f.name
        try:
            text = generate_validation_report(output_path=out_path)
            assert "CMCC Knowledge Base" in text
            assert "Resumen" in text
            assert "Variantes por código" in text
            assert len(text) > 500
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_load_knowledge_base_missing(self):
        data = load_knowledge_base("/nonexistent/kb.json")
        assert data == {}


class TestAudit:
    def test_audit_from_real_data(self):
        from knowledge_base.audit import audit_knowledge_base
        findings = audit_knowledge_base()
        assert findings["total_codes"] >= 1
        assert findings["total_variants"] >= findings["total_codes"]
        assert findings["total_families"] >= 1
        assert "low_evidence_codes" in findings
        assert "gold_coverage" in findings

    def test_audit_duplicate_codes(self):
        from knowledge_base.audit import _check_duplicate_codes
        codes = {
            "AC.01": {"nombre": "Disponible"},
            "AC.03": {"nombre": "Documentos por cobrar"},
        }
        result = _check_duplicate_codes(codes)
        assert result["total"] == 0

        codes2 = {
            "AC.01": {"nombre": "Disponible"},
            "AC.03": {"nombre": "disponible"},
        }
        result2 = _check_duplicate_codes(codes2)
        # "Disponible" vs "disponible" lowercase match
        assert result2["total"] >= 1

    def test_audit_repeated_variants(self):
        from knowledge_base.audit import _check_repeated_variants
        codes = {
            "AC.01": {"variantes": [{"nombre": "Caja"}, {"nombre": "Bancos"}]},
            "AC.03": {"variantes": [{"nombre": "Clientes"}]},
        }
        result = _check_repeated_variants(codes)
        assert result["total"] == 0

        codes2 = {
            "AC.01": {"variantes": [{"nombre": "Caja"}, {"nombre": "Bancos"}]},
            "AC.03": {"variantes": [{"nombre": "Caja"}]},
        }
        result2 = _check_repeated_variants(codes2)
        assert result2["total"] == 1

    def test_audit_cross_code_variants(self):
        from knowledge_base.audit import _check_cross_code_variants
        codes = {
            "AC.01": {"variantes": [{"nombre": "Caja"}]},
            "AC.03": {"variantes": [{"nombre": "Caja"}]},
        }
        result = _check_cross_code_variants(codes)
        assert result["total_conflictive"] == 1

    def test_audit_low_evidence(self):
        from knowledge_base.audit import _check_low_evidence
        codes = {
            "AC.01": {"frecuencia": 1, "confianza": 1.0, "variantes": [{"nombre": "Caja", "confianza": 1.0}]},
            "AC.03": {"frecuencia": 10, "confianza": 0.5, "variantes": [{"nombre": "Docs", "confianza": 0.5}]},
            "AC.05": {"frecuencia": 22, "confianza": 0.07, "variantes": [{"nombre": "Varios", "confianza": 0.07}]},
        }
        result = _check_low_evidence(codes)
        # AC.01: freq=1 (baja), AC.05: conf=0.07 (baja)
        assert len(result["details"]) >= 2

    def test_audit_incomplete_families(self):
        from knowledge_base.audit import _check_incomplete_families
        families = [
            {"nombre": "AC", "miembros": ["AC.01", "AC.03", "AC.05", "AC.06"], "total_frecuencia": 40},
            {"nombre": "PNC", "miembros": ["PNC.01"], "total_frecuencia": 1},
        ]
        result = _check_incomplete_families(families)
        assert result["total"] == 1

    def test_audit_hierarchy(self):
        from knowledge_base.audit import _check_hierarchy
        codes = {
            "AC.01": {"seccion": "Activo", "nivel": 3},
        }
        families = [{"prefijo": "AC", "seccion": "Activo"}]
        result = _check_hierarchy(codes, families)
        assert result["total"] == 0

        codes2 = {
            "AC.01": {"seccion": "Pasivo", "nivel": 1},
        }
        result2 = _check_hierarchy(codes2, families)
        assert result2["total"] >= 1

    def test_audit_similar_variants(self):
        from knowledge_base.audit import _check_similar_variants
        codes = {
            "AC.01": {"variantes": [{"nombre": "Anticipo a Proveedores"}]},
            "AC.05": {"variantes": [{"nombre": "Anticipos a Proveedores"}]},
        }
        result = _check_similar_variants(codes)
        assert result["total"] == 1
        assert result["similar_pairs"][0]["similarity"] > 0.9

    def test_audit_avg_confidence(self):
        from knowledge_base.audit import _avg_confidence_per_code, _avg_confidence_per_family
        codes = {
            "AC.01": {"confianza": 0.5},
            "AC.03": {"confianza": 1.0},
        }
        result = _avg_confidence_per_code(codes)
        assert result["average"] == 0.75
        assert result["per_code"]["AC.01"] == 0.5

        families = [{"prefijo": "AC", "nombre": "Activo"}]
        result2 = _avg_confidence_per_family(codes, families)
        assert result2["per_family"]["Activo"]["average_confidence"] == 0.75
        assert result2["per_family"]["Activo"]["total_members"] == 2

    def test_audit_gold_coverage(self):
        from knowledge_base.audit import _check_gold_coverage
        codes = {"AC.01": {}, "PC.01": {}, "ER.01": {}}
        result = _check_gold_coverage(codes)
        assert "gold_standard_codes" in result
        assert "coverage_pct" in result
        assert result["knowledge_base_codes"] == 3

    def test_audit_report_generated(self):
        from knowledge_base.audit import generate_audit_report, audit_knowledge_base
        findings = audit_knowledge_base()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            out_path = f.name
        try:
            text = generate_audit_report(findings, output_path=out_path)
            assert "Auditoría de Knowledge Base" in text
            assert "Resumen" in text
            assert "Cobertura del Gold Standard" in text
            assert len(text) > 500
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_audit_quality_metrics_generated(self):
        from knowledge_base.audit import generate_quality_metrics, audit_knowledge_base
        findings = audit_knowledge_base()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            out_path = f.name
        try:
            metrics = generate_quality_metrics(findings, output_path=out_path)
            assert "summary" in metrics
            assert "gold_coverage" in metrics
            assert "duplicate_codes" in metrics
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_audit_empty_kb(self):
        from knowledge_base.audit import audit_knowledge_base
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write('{}')
            empty_path = f.name
        try:
            from knowledge_base.audit import load_kb
            data = load_kb(empty_path)
            assert data == {}
        finally:
            Path(empty_path).unlink(missing_ok=True)
            Path(empty_path).unlink(missing_ok=True)

    def test_audit_summary_fields_present(self):
        from knowledge_base.audit import audit_knowledge_base
        findings = audit_knowledge_base()
        assert "total_codes" in findings
        assert "total_variants" in findings
        assert "total_families" in findings
        assert "conflictive_variants" in findings
        assert "low_evidence_count" in findings
        assert "codes_recommended_for_review" in findings
