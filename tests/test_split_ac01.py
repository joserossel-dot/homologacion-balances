from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import pandas as pd

from split_ac01.split_rules import (
    CAJA_DIRECT_PATTERN, CAJA_NEGATE_PATTERN,
    EFECTIVO_PATTERN, FONDO_FIJO_PATTERN, MONEDA_PATTERN,
    BILLETE_PATTERN, DIVISA_PATTERN, DINERO_PATTERN, ARQUEO_PATTERN,
    CTA_PATTERN, CHEQUE_PATTERN, SOBREGIRO_PATTERN, LINEA_CREDITO_PATTERN,
    BANK_TOKEN_MAP, BANCO_NEGATE_PATTERN,
    FONDO_MUTUO_PATTERN, INVERSION_PATTERN, VALOR_NEGOCIABLE_PATTERN,
    CORTO_PLAZO_PATTERN, DEPOSITO_PLAZO_PATTERN,
    ACCIONES_PATTERN, BONOS_PATTERN,
    has_any_token,
)

from split_ac01.split_engine import (
    AC01SplitEngine, ClassificationResult,
    load_ac01_variants,
)
from split_ac01.split_reports import generate_reports, REPORTS_DIR


# ═══════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════

@pytest.fixture
def engine() -> AC01SplitEngine:
    return AC01SplitEngine()


@pytest.fixture
def tmp_reports(tmp_path: Path) -> Path:
    return tmp_path / "split_reports"


# ═══════════════════════════════════════════
# Rule Tests — AC.01.01 Caja
# ═══════════════════════════════════════════

class TestCajaRules:
    def test_caja_direct_pattern(self):
        assert CAJA_DIRECT_PATTERN.search("CAJA GENERAL")
        assert CAJA_DIRECT_PATTERN.search("caja chica")
        assert CAJA_DIRECT_PATTERN.search("Caja Menor")
        assert CAJA_DIRECT_PATTERN.search("FONDO FIJO CAJA")
        assert not CAJA_DIRECT_PATTERN.search("trabajo")  # embedded
        assert not CAJA_DIRECT_PATTERN.search("almeja")    # embedded

    def test_caja_negate_pattern(self):
        assert CAJA_NEGATE_PATTERN.search("CAJA DE COMPENSACION")
        assert CAJA_NEGATE_PATTERN.search("compensación")
        assert CAJA_NEGATE_PATTERN.search("armado cajas")
        assert CAJA_NEGATE_PATTERN.search("ARMADO DE CAJAS")
        assert not CAJA_NEGATE_PATTERN.search("CAJA GENERAL")

    def test_efectivo_pattern(self):
        assert EFECTIVO_PATTERN.search("efectivo")
        assert EFECTIVO_PATTERN.search("EFECTIVO EN CAJA")
        assert not EFECTIVO_PATTERN.search("efectivos")  # plural not handled

    def test_fondo_fijo_pattern(self):
        assert FONDO_FIJO_PATTERN.search("fondo fijo")
        assert FONDO_FIJO_PATTERN.search("FONDOS FIJOS")
        assert FONDO_FIJO_PATTERN.search("Fondo Fijo")
        assert FONDO_FIJO_PATTERN.search("reposicion fondo fijo")
        assert not FONDO_FIJO_PATTERN.search("fondo mutuo")

    def test_moneda_pattern(self):
        assert MONEDA_PATTERN.search("moneda nacional")
        assert MONEDA_PATTERN.search("MONEDA EXTRANJERA")
        assert MONEDA_PATTERN.search("moneda extrangera")
        assert not MONEDA_PATTERN.search("moneda")  # standalone

    def test_billete_pattern(self):
        assert BILLETE_PATTERN.search("billete")
        assert BILLETE_PATTERN.search("Billetes en Cartera")
        assert BILLETE_PATTERN.search("billetes")
        assert not BILLETE_PATTERN.search("billetera")

    def test_divisa_pattern(self):
        assert DIVISA_PATTERN.search("divisa")
        assert DIVISA_PATTERN.search("DIVISAS")
        assert not DIVISA_PATTERN.search("division")

    def test_dinero_pattern(self):
        assert DINERO_PATTERN.search("dinero")
        assert DINERO_PATTERN.search("DINERO EN CAJA")
        assert not DINERO_PATTERN.search("dineros")

    def test_arqueo_pattern(self):
        assert ARQUEO_PATTERN.search("arqueo")
        assert ARQUEO_PATTERN.search("ARQUEO DE CAJA")
        assert not ARQUEO_PATTERN.search("arqueologia")


# ═══════════════════════════════════════════
# Rule Tests — AC.01.02 Bancos
# ═══════════════════════════════════════════

class TestBancosRules:
    def test_cta_pattern(self):
        assert CTA_PATTERN.search("cta cte")
        assert CTA_PATTERN.search("CTA. CTE")
        assert CTA_PATTERN.search("cuenta corriente")
        assert CTA_PATTERN.search("cuenta vista")
        assert CTA_PATTERN.search("cta vista")
        assert CTA_PATTERN.search("cta rut")
        assert CTA_PATTERN.search("cta ahorro")
        assert CTA_PATTERN.search("cuenta ahorro")
        assert not CTA_PATTERN.search("cuenta por cobrar")
        assert not CTA_PATTERN.search("cta pagar")

    def test_cheque_pattern(self):
        assert CHEQUE_PATTERN.search("cheque")
        assert CHEQUE_PATTERN.search("CHEQUES")
        assert CHEQUE_PATTERN.search("chequera")
        assert not CHEQUE_PATTERN.search("chequear")

    def test_sobregiro_pattern(self):
        assert SOBREGIRO_PATTERN.search("sobregiro")
        assert SOBREGIRO_PATTERN.search("SOBREGIROS")
        assert not SOBREGIRO_PATTERN.search("sobre giro")

    def test_linea_credito_pattern(self):
        assert LINEA_CREDITO_PATTERN.search("linea de credito")
        assert LINEA_CREDITO_PATTERN.search("LÍNEA DE CRÉDITO")
        assert LINEA_CREDITO_PATTERN.search("linea credito")

    def test_bank_token_map(self):
        tokens = BANK_TOKEN_MAP.get("ac01_02", set())
        assert "banco" in tokens
        assert "bco" in tokens
        assert "bci" in tokens
        assert "santander" in tokens
        assert "itau" in tokens
        assert "corpbanca" in tokens

    def test_banco_negate_pattern(self):
        assert BANCO_NEGATE_PATTERN.search("inversiones")
        assert BANCO_NEGATE_PATTERN.search("INVERSIÓN")
        assert BANCO_NEGATE_PATTERN.search("mutuo")
        assert not BANCO_NEGATE_PATTERN.search("banco")

    def test_has_any_token(self):
        result = has_any_token("banco bci santander", {"banco", "bci"})
        assert result == {"banco", "bci"}
        assert not has_any_token("caja general", {"banco", "bci"})

    def test_bank_name_variants(self):
        tokens = BANK_TOKEN_MAP.get("ac01_02", set())
        assert "bco" in tokens
        assert "bcos" in tokens
        assert "bbva" in tokens
        assert "scotiabank" in tokens
        assert "falabella" in tokens


# ═══════════════════════════════════════════
# Rule Tests — AC.01.03 Equivalentes
# ═══════════════════════════════════════════

class TestEquivalentesRules:
    def test_fondo_mutuo_pattern(self):
        assert FONDO_MUTUO_PATTERN.search("fondo mutuo")
        assert FONDO_MUTUO_PATTERN.search("FONDOS MUTUOS")
        assert FONDO_MUTUO_PATTERN.search("Fondo Mutuo")
        assert not FONDO_MUTUO_PATTERN.search("fondo fijo")

    def test_inversion_pattern(self):
        assert INVERSION_PATTERN.search("inversion")
        assert INVERSION_PATTERN.search("inversión")
        assert INVERSION_PATTERN.search("inversiones")
        assert INVERSION_PATTERN.search("INVERSIONES")
        assert not INVERSION_PATTERN.search("inverso")

    def test_valor_negociable_pattern(self):
        assert VALOR_NEGOCIABLE_PATTERN.search("valor negociable")
        assert VALOR_NEGOCIABLE_PATTERN.search("Valores Negociables")
        assert not VALOR_NEGOCIABLE_PATTERN.search("valor libro")

    def test_corto_plazo_pattern(self):
        assert CORTO_PLAZO_PATTERN.search("corto plazo")
        assert CORTO_PLAZO_PATTERN.search("CORTO PLAZO")
        assert CORTO_PLAZO_PATTERN.search("Corto Plazo")
        assert not CORTO_PLAZO_PATTERN.search("cortoplazo")

    def test_deposito_plazo_pattern(self):
        assert DEPOSITO_PLAZO_PATTERN.search("deposito a plazo")
        assert DEPOSITO_PLAZO_PATTERN.search("DEPÓSITO A PLAZO")
        assert DEPOSITO_PLAZO_PATTERN.search("Dep. a Plazo")
        assert DEPOSITO_PLAZO_PATTERN.search("deposito plazo")
        assert not DEPOSITO_PLAZO_PATTERN.search("depreciacion")

    def test_acciones_pattern(self):
        assert ACCIONES_PATTERN.search("acciones")
        assert ACCIONES_PATTERN.search("ACCIONES")
        assert ACCIONES_PATTERN.search("accionista")
        assert not ACCIONES_PATTERN.search("accion")

    def test_bonos_pattern(self):
        assert BONOS_PATTERN.search("bonos")
        assert BONOS_PATTERN.search("BONOS")
        assert BONOS_PATTERN.search("bono")
        assert not BONOS_PATTERN.search("bonito")


# ═══════════════════════════════════════════
# Engine Tests — Classification
# ═══════════════════════════════════════════

class TestClassification:
    def test_caja_variants(self, engine: AC01SplitEngine):
        cases = [
            ("CAJA GENERAL", "AC.01.01"),
            ("caja chica", "AC.01.01"),
            ("Caja Menor", "AC.01.01"),
            ("efectivo", "AC.01.01"),
            ("Fondo Fijo", "AC.01.01"),
            ("FONDOS FIJOS", "AC.01.01"),
            ("moneda extranjera", "AC.01.01"),
            ("MONEDA NACIONAL", "AC.01.01"),
            ("billetes", "AC.01.01"),
            ("dinero en caja", "AC.01.01"),
            ("arqueo de caja", "AC.01.01"),
        ]
        for variant, expected in cases:
            result = engine.classify_variant(variant)
            assert result.target_code == expected, (
                f"'{variant}' → {result.target_code}, expected {expected}"
            )
            assert not result.needs_review, f"'{variant}' should NOT need review"

    def test_bancos_variants(self, engine: AC01SplitEngine):
        cases = [
            ("BANCOS", "AC.01.02"),
            ("Banco Bci", "AC.01.02"),
            ("Banco Santander", "AC.01.02"),
            ("BANCO DE CHILE", "AC.01.02"),
            ("BCI N°", "AC.01.02"),
            ("cta cte", "AC.01.02"),
            ("cuenta corriente", "AC.01.02"),
            ("cta vista", "AC.01.02"),
            ("cta rut", "AC.01.02"),
            ("cheque", "AC.01.02"),
            ("CHEQUES", "AC.01.02"),
            ("sobregiro", "AC.01.02"),
            ("linea de credito", "AC.01.02"),
            ("Vale Vista Bco", "AC.01.02"),
            ("Corpbanca", "AC.01.02"),
            ("Banco Itaú", "AC.01.02"),
        ]
        for variant, expected in cases:
            result = engine.classify_variant(variant)
            assert result.target_code == expected, (
                f"'{variant}' → {result.target_code}, expected {expected}"
            )
            assert not result.needs_review, f"'{variant}' should NOT need review"

    def test_equivalentes_variants(self, engine: AC01SplitEngine):
        cases = [
            ("fondo mutuo", "AC.01.03"),
            ("FONDOS MUTUOS", "AC.01.03"),
            ("deposito a plazo", "AC.01.03"),
            ("DEPÓSITO A PLAZO", "AC.01.03"),
            ("Dep. a Plazo", "AC.01.03"),
            ("valor negociable", "AC.01.03"),
            ("Valores Negociables", "AC.01.03"),
            ("corto plazo", "AC.01.03"),
            ("inversiones", "AC.01.03"),
            ("acciones", "AC.01.03"),
            ("bonos", "AC.01.03"),
        ]
        for variant, expected in cases:
            result = engine.classify_variant(variant)
            assert result.target_code == expected, (
                f"'{variant}' → {result.target_code}, expected {expected}"
            )
            assert not result.needs_review, f"'{variant}' should NOT need review"

    def test_non_cash_variants_need_review(self, engine: AC01SplitEngine):
        cases = [
            "MERCADERIAS 741,447,371 IMPTO UNICO 2* CATEG",
            "MAQUINARIA 211376247 43.379.018",
            "Deudores por venta USD",
            "PROVISIÓN SEGURO",
            "EQUIPOS DE SEGURIDAD",
            "Propiedades, plantas y equipos, neto",
            ": IVA FUERA DE PLAZO",
            "Muebles de oficina 1,480,200",
            "ANTICIPO REMUNERACIONES",
            "PATENTES MUNICIPALES",
            "Clientes",
            "Cuentas por Pagar",
            "gastos generales",
        ]
        for variant in cases:
            result = engine.classify_variant(variant)
            assert result.needs_review, f"'{variant}' should need review (non-cash)"
            assert result.confidence == 0.0, f"'{variant}' should have 0 confidence"

    def test_caja_compensacion_blocked(self, engine: AC01SplitEngine):
        result = engine.classify_variant("CAJA DE COMPENSACION")
        assert result.needs_review, "Caja de Compensacion should need review (not cash)"

    def test_armado_cajas_blocked(self, engine: AC01SplitEngine):
        result = engine.classify_variant("ARMADO DE CAJAS")
        assert result.needs_review, "Armado de Cajas should need review (not cash)"

    def test_banco_mutuo_blocked(self, engine: AC01SplitEngine):
        result = engine.classify_variant("banco fondo mutuo")
        assert result.target_code != "AC.01.02", "Should not be bancos"

    def test_ambiguous_deposito_plazo_bancos(self, engine: AC01SplitEngine):
        result = engine.classify_variant("Dep. a Plazo Bancos")
        assert result.target_code in ("AC.01.02", "AC.01.03")
        assert result.confidence > 0

    def test_empty_variant(self, engine: AC01SplitEngine):
        result = engine.classify_variant("")
        assert result.needs_review
        assert result.confidence == 0.0

    def test_garbage_variant(self, engine: AC01SplitEngine):
        result = engine.classify_variant("12345 78901 abcdefg !!! ###")
        assert result.needs_review
        assert result.confidence == 0.0

    def test_normalizer_integration(self, engine: AC01SplitEngine):
        result = engine.classify_variant("BCÍ")
        assert result.target_code == "AC.01.02", (
            f"'BCÍ' → {result.target_code}, should be AC.01.02"
        )
        assert not result.needs_review

    def test_normalizer_reposicion_fondo_fijo(self, engine: AC01SplitEngine):
        result = engine.classify_variant("REPOSICIÓN DE FONDOS FIJOS")
        assert result.target_code == "AC.01.01", (
            f"'REPOSICIÓN DE FONDOS FIJOS' → {result.target_code}"
        )
        assert not result.needs_review


# ═══════════════════════════════════════════
# Engine Tests — Statistics
# ═══════════════════════════════════════════

class TestStatistics:
    def test_empty_results(self, engine: AC01SplitEngine):
        stats = engine.compute_statistics([])
        assert stats["total_variants"] == 0
        assert stats["auto_classified"] == 0

    def test_mixed_results(self, engine: AC01SplitEngine):
        variants = ["CAJA GENERAL", "Banco Bci", "fondo mutuo", "MAQUINARIA"]
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        assert stats["total_variants"] == 4
        assert stats["auto_classified"] == 3
        assert stats["needs_review"] == 1
        assert stats["by_concept"]["AC.01.01"] == 1
        assert stats["by_concept"]["AC.01.02"] == 1
        assert stats["by_concept"]["AC.01.03"] == 1
        assert stats["UNCLASSIFIED" in stats["by_concept"]]

    def test_confidence_buckets(self, engine: AC01SplitEngine):
        variants = ["CAJA GENERAL", "Banco Bci", "Banco Crédito e Inversiones"]
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        cb = stats["confidence_buckets"]
        assert sum(cb.values()) == 3


# ═══════════════════════════════════════════
# Engine Tests — Coverage
# ═══════════════════════════════════════════

class TestCoverage:
    def test_coverage_before_after(self, engine: AC01SplitEngine):
        variants = ["CAJA GENERAL", "Banco Bci", "MAQUINARIA", "IVA"]
        results = engine.classify_all(variants)
        coverage = engine.compute_coverage(results)
        assert coverage["before"]["AC.01"] == 4
        assert coverage["before"]["concepts"] == 1
        assert coverage["after"]["auto_classified"] == 2
        assert coverage["after"]["needs_review"] == 2

    def test_coverage_all_classified(self, engine: AC01SplitEngine):
        variants = ["CAJA GENERAL", "Banco Bci", "fondo mutuo"]
        results = engine.classify_all(variants)
        cov = engine.compute_coverage(results)
        assert cov["after"]["auto_classified"] == 3
        assert cov["after"]["needs_review"] == 0


# ═══════════════════════════════════════════
# Report Tests
# ═══════════════════════════════════════════

class TestReports:
    def test_all_files_created(self, engine: AC01SplitEngine, tmp_reports: Path):
        variants = ["CAJA GENERAL", "Banco Bci", "fondo mutuo", "MAQUINARIA", "IVA"]
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        coverage = engine.compute_coverage(results)
        paths = generate_reports(results, stats, coverage, output_dir=str(tmp_reports))

        expected = [
            "variant_mapping.xlsx",
            "split_statistics.xlsx",
            "coverage_before_after.xlsx",
            "review_needed.xlsx",
            "split_report.md",
        ]
        for name in expected:
            assert name in paths, f"Missing report: {name}"
            assert paths[name].exists(), f"File missing: {paths[name]}"

    def test_variant_mapping_content(self, engine: AC01SplitEngine, tmp_reports: Path):
        variants = ["CAJA GENERAL", "MAQUINARIA"]
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        coverage = engine.compute_coverage(results)
        paths = generate_reports(results, stats, coverage, output_dir=str(tmp_reports))
        df = pd.read_excel(paths["variant_mapping.xlsx"])
        assert len(df) == 2
        caja_row = df[df["variant"] == "CAJA GENERAL"].iloc[0]
        assert caja_row["target_code"] == "AC.01.01"
        assert caja_row["needs_review"] == "NO"
        maq_row = df[df["variant"] == "MAQUINARIA"].iloc[0]
        assert maq_row["target_code"] == "UNCLASSIFIED"
        assert maq_row["needs_review"] == "SI"

    def test_split_statistics_sheets(self, engine: AC01SplitEngine, tmp_reports: Path):
        variants = ["CAJA GENERAL", "Banco Bci", "MAQUINARIA"]
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        coverage = engine.compute_coverage(results)
        paths = generate_reports(results, stats, coverage, output_dir=str(tmp_reports))

        xls = pd.ExcelFile(paths["split_statistics.xlsx"])
        assert "by_concept" in xls.sheet_names
        assert "confidence_buckets" in xls.sheet_names
        assert "matched_rules" in xls.sheet_names

    def test_review_needed_content(self, engine: AC01SplitEngine, tmp_reports: Path):
        variants = ["CAJA GENERAL", "MAQUINARIA", "IVA FUERA DE PLAZO"]
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        coverage = engine.compute_coverage(results)
        paths = generate_reports(results, stats, coverage, output_dir=str(tmp_reports))
        df = pd.read_excel(paths["review_needed.xlsx"])
        assert len(df) == 2  # MAQUINARIA + IVA
        assert all(df["needs_review"] == "SI")

    def test_coverage_before_after_content(self, engine: AC01SplitEngine, tmp_reports: Path):
        variants = ["CAJA GENERAL", "Banco Bci", "MAQUINARIA"]
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        coverage = engine.compute_coverage(results)
        paths = generate_reports(results, stats, coverage, output_dir=str(tmp_reports))
        df = pd.read_excel(paths["coverage_before_after.xlsx"])
        total_row = df[df["metric"] == "Total variants"].iloc[0]
        assert total_row["before"] == 3
        assert total_row["after"] == 3

    def test_split_report_md_content(self, engine: AC01SplitEngine, tmp_reports: Path):
        variants = ["CAJA GENERAL", "Banco Bci", "fondo mutuo", "MAQUINARIA"]
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        coverage = engine.compute_coverage(results)
        paths = generate_reports(results, stats, coverage, output_dir=str(tmp_reports))
        md = paths["split_report.md"].read_text()
        assert "SPRINT 27.4" not in md  # Not in the report
        assert "Resumen" in md
        assert "Caja" in md
        assert "Bancos" in md
        assert "Equivalentes" in md
        assert "Riesgos" in md

    def test_empty_queue_creates_empty_files(self, engine: AC01SplitEngine, tmp_reports: Path):
        results = engine.classify_all([])
        stats = engine.compute_statistics(results)
        coverage = engine.compute_coverage(results)
        paths = generate_reports(results, stats, coverage, output_dir=str(tmp_reports))
        df = pd.read_excel(paths["variant_mapping.xlsx"])
        assert len(df) == 0

    def test_review_needed_reason(self, engine: AC01SplitEngine, tmp_reports: Path):
        variants = ["MAQUINARIA", "CAJA GENERAL"]
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        coverage = engine.compute_coverage(results)
        paths = generate_reports(results, stats, coverage, output_dir=str(tmp_reports))
        df = pd.read_excel(paths["review_needed.xlsx"])
        maq_row = df[df["variant"] == "MAQUINARIA"].iloc[0]
        assert "reglas" in str(maq_row["review_reason"]).lower()


# ═══════════════════════════════════════════
# Load / Integration Tests
# ═══════════════════════════════════════════

class TestLoadVariants:
    def test_load_from_cmcc_json(self):
        variants = load_ac01_variants()
        assert len(variants) == 1105

    def test_load_with_custom_path(self, tmp_path: Path):
        fake_data = [
            {"id": "AC.01", "variantes": ["v1", "v2", "v3"]},
            {"id": "AC.02", "variantes": ["v4"]},
        ]
        fake_path = tmp_path / "test_cmcc.json"
        with open(fake_path, "w") as f:
            json.dump(fake_data, f)
        variants = load_ac01_variants(str(fake_path))
        assert variants == ["v1", "v2", "v3"]

    def test_load_ac01_not_found(self, tmp_path: Path):
        fake_data = [{"id": "AC.02", "variantes": ["v1"]}]
        fake_path = tmp_path / "empty.json"
        with open(fake_path, "w") as f:
            json.dump(fake_data, f)
        assert load_ac01_variants(str(fake_path)) == []


class TestFullPipeline:
    def test_classify_all_1105(self, engine: AC01SplitEngine):
        variants = load_ac01_variants()
        results = engine.classify_all(variants)
        assert len(results) == 1105
        stats = engine.compute_statistics(results)
        assert stats["total_variants"] == 1105
        assert stats["auto_classified"] + stats["needs_review"] == 1105
        coverage = engine.compute_coverage(results)
        assert coverage["total_variants"] == 1105
        assert coverage["before"]["AC.01"] == 1105

    def test_deterministic_classification(self, engine: AC01SplitEngine):
        v = "Dep. a Plazo Bancos"
        r1 = engine.classify_variant(v)
        r2 = engine.classify_variant(v)
        assert r1.target_code == r2.target_code
        assert r1.confidence == r2.confidence
        assert r1.needs_review == r2.needs_review

    def test_report_all_dept(self, engine: AC01SplitEngine, tmp_reports: Path):
        variants = load_ac01_variants()
        results = engine.classify_all(variants)
        stats = engine.compute_statistics(results)
        coverage = engine.compute_coverage(results)
        paths = generate_reports(results, stats, coverage, output_dir=str(tmp_reports))
        expected = [
            "variant_mapping.xlsx", "split_statistics.xlsx",
            "coverage_before_after.xlsx", "review_needed.xlsx",
            "split_report.md",
        ]
        for name in expected:
            assert name in paths
        df_map = pd.read_excel(paths["variant_mapping.xlsx"])
        assert len(df_map) == 1105
        df_review = pd.read_excel(paths["review_needed.xlsx"])
        assert len(df_review) == stats["needs_review"]


# ═══════════════════════════════════════════
# Regression Tests — Pipeline Immutability
# ═══════════════════════════════════════════

class TestPipelineImmutability:
    def test_cmcc_json_not_modified(self, engine: AC01SplitEngine):
        with open("knowledge/cmcc.json") as f:
            original = json.load(f)
        variants = load_ac01_variants()
        results = engine.classify_all(variants)
        with open("knowledge/cmcc.json") as f:
            after = json.load(f)
        assert original == after, "cmcc.json was modified!"

    def test_no_dictionary_modification(self, engine: AC01SplitEngine):
        dict_paths = [
            "diccionario_optimizado.json",
            "diccionario.json",
        ]
        originals = {}
        for p in dict_paths:
            if os.path.exists(p):
                with open(p) as f:
                    originals[p] = json.load(f)
        variants = load_ac01_variants()
        _ = engine.classify_all(variants)
        for p in dict_paths:
            if p in originals:
                with open(p) as f:
                    after = json.load(f)
                assert originals[p] == after, f"{p} was modified!"
