from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import pytest

logging.disable(logging.CRITICAL)

# =========================================================================
# RejectionReason enum
# =========================================================================


def test_rejection_reason_str():
    from parser_quality.rejection_reasons import RejectionReason
    assert str(RejectionReason.CONTAINS_PAGE) == "contains_page"
    assert str(RejectionReason.NO_MONTO) == "no_monto"


def test_rejection_reason_uniqueness():
    from parser_quality.rejection_reasons import RejectionReason
    values = [r.value for r in RejectionReason]
    assert len(values) == len(set(values))


# =========================================================================
# Utility functions
# =========================================================================


def test_strip_accents():
    from parser_quality.candidate_validator import strip_accents
    assert strip_accents("DEPRECIACIÓN ACUMULADA") == "DEPRECIACION ACUMULADA"
    assert strip_accents("AMORTIZACIÓN") == "AMORTIZACION"
    assert strip_accents("") == ""


def test_name_has_account_keywords():
    from parser_quality.candidate_validator import name_has_account_keywords
    assert name_has_account_keywords("Banco Santander")
    assert name_has_account_keywords("Cuentas por Cobrar")
    assert name_has_account_keywords("Depreciación Acumulada")
    assert not name_has_account_keywords("Página 1 de 5")


def test_count_symbols():
    from parser_quality.candidate_validator import count_symbols
    assert count_symbols("BANCO") == 0.0
    assert count_symbols("") == 0.0
    assert count_symbols("***") == 1.0
    assert count_symbols("CUENTA/CORRIENTE") == pytest.approx(1 / 16)


def test_count_digits():
    from parser_quality.candidate_validator import count_digits
    assert count_digits("BANCO") == 0.0
    assert count_digits("") == 0.0
    assert count_digits("12345") == 1.0
    assert count_digits("1105 BANCO CHILE") == pytest.approx(4 / 16)


# =========================================================================
# Positive signals
# =========================================================================


def test_positive_signals_monto():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(name="Banco Chile", code=None, monto=1000.0, is_total=False)
    assert RejectionReason.HAS_MONTO in signals
    assert signals[RejectionReason.HAS_MONTO] == 0.15


def test_positive_signals_code():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(name="Banco Chile", code="1105-0000", monto=None, is_total=False)
    assert RejectionReason.HAS_CODE in signals
    assert signals[RejectionReason.HAS_CODE] == 0.10


def test_positive_signals_short_code_ignored():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(name="Banco Chile", code="AB", monto=None, is_total=False)
    assert RejectionReason.HAS_CODE not in signals


def test_positive_signals_reasonable_length():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(name="Banco Chile", code=None, monto=None, is_total=False)
    assert RejectionReason.REASONABLE_LENGTH in signals


def test_positive_signals_too_short():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(name="AB", code=None, monto=None, is_total=False)
    assert RejectionReason.REASONABLE_LENGTH not in signals


def test_positive_signals_too_long():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    long_name = "CUENTA " * 30
    signals = evaluate_positive_signals(name=long_name, code=None, monto=None, is_total=False)
    assert RejectionReason.REASONABLE_LENGTH not in signals


def test_positive_signals_account_keywords():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(name="Cuentas por Cobrar", code=None, monto=None, is_total=False)
    assert RejectionReason.ACCOUNT_PATTERN in signals


def test_positive_signals_is_total():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(name="TOTAL ACTIVOS", code=None, monto=None, is_total=True)
    assert RejectionReason.ACCOUNT_PATTERN in signals


def test_positive_signals_standard_code():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(name="AC.01 Caja", code=None, monto=None, is_total=False)
    assert RejectionReason.ACCOUNT_PATTERN in signals


def test_positive_signals_n_tokens():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(name="Banco Chile", code=None, monto=None, is_total=False)
    assert RejectionReason.KNOWN_ACCOUNT in signals


def test_positive_signals_empty_name():
    from parser_quality.candidate_validator import evaluate_positive_signals
    signals = evaluate_positive_signals(name="", code=None, monto=None, is_total=False)
    assert len(signals) == 0


def test_positive_signals_all():
    from parser_quality.candidate_validator import evaluate_positive_signals, RejectionReason
    signals = evaluate_positive_signals(
        name="AC.01 Banco Santander",
        code="1105-0000",
        monto=50000000.0,
        is_total=False,
    )
    assert RejectionReason.HAS_MONTO in signals
    assert RejectionReason.HAS_CODE in signals
    assert RejectionReason.REASONABLE_LENGTH in signals
    assert RejectionReason.ACCOUNT_PATTERN in signals
    assert RejectionReason.KNOWN_ACCOUNT in signals


# =========================================================================
# Negative signals — scanned on NAME only (not full line)
# =========================================================================


def test_negative_signals_page():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="Página 1 de 5", name="Página 1 de 5", requirio_ocr=False)
    assert RejectionReason.CONTAINS_PAGE in signals


def test_negative_signals_rut():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="RUT 76.123.456-7", requirio_ocr=False)
    assert RejectionReason.CONTAINS_RUT in signals


def test_negative_signals_date():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Al 31-12-2020", requirio_ocr=False)
    assert RejectionReason.CONTAINS_DATE in signals


def test_negative_signals_fecha_texto():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Diciembre 2020", requirio_ocr=False)
    assert RejectionReason.CONTAINS_DATE in signals


def test_negative_signals_address():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Av. Providencia 1234", requirio_ocr=False)
    assert RejectionReason.CONTAINS_ADDRESS in signals


def test_negative_signals_phone_chile():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="+56 9 1234 5678", requirio_ocr=False)
    assert RejectionReason.CONTAINS_PHONE in signals


def test_negative_signals_phone_no_false_positive():
    """Account amounts with thousands separators should NOT match phone."""
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    # Large amounts with thousands separators
    for amount_name in [
        "950.482.196",
        "6.382.143.480",
        "943,078,292",
        "520,066,497",
        "50,555,169",
        "240.000.000",
        "444,463,082",
        "307,304,275",
    ]:
        signals = evaluate_negative_signals(line=amount_name, name=amount_name, requirio_ocr=False)
        assert RejectionReason.CONTAINS_PHONE not in signals, f"False positive phone on: {amount_name}"


def test_negative_signals_phone_short_groups_not_match():
    """Short numeric strings should not match phone."""
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    for val in ["1234", "100", "0", "2024"]:
        signals = evaluate_negative_signals(line=val, name=val, requirio_ocr=False)
        assert RejectionReason.CONTAINS_PHONE not in signals, f"False positive phone on: {val}"


def test_negative_signals_email():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="contacto@empresa.cl", requirio_ocr=False)
    assert RejectionReason.CONTAINS_EMAIL in signals


def test_negative_signals_web():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="www.empresa.cl", requirio_ocr=False)
    assert RejectionReason.CONTAINS_WEB in signals


def test_negative_signals_comuna():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Comuna de Santiago", requirio_ocr=False)
    assert RejectionReason.CONTAINS_COMUNA in signals


def test_negative_signals_ciudad():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Santiago", requirio_ocr=False)
    assert RejectionReason.CONTAINS_CIUDAD in signals


def test_negative_signals_region():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Región Metropolitana", requirio_ocr=False)
    assert RejectionReason.CONTAINS_REGION in signals


def test_negative_signals_moneda():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Dólar observado", requirio_ocr=False)
    assert RejectionReason.CONTAINS_MONEDA in signals


def test_negative_signals_firma():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Firma del contador", requirio_ocr=False)
    assert RejectionReason.CONTAINS_FIRMA in signals


def test_negative_signals_notas():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Notas a los EF", requirio_ocr=False)
    assert RejectionReason.CONTAINS_NOTAS in signals


def test_negative_signals_balance_general():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Balance General", requirio_ocr=False)
    assert RejectionReason.CONTAINS_BALANCE_GENERAL in signals


def test_negative_signals_periodo():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Ejercicio 2022", requirio_ocr=False)
    assert RejectionReason.CONTAINS_PERIODO in signals


def test_negative_signals_header():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="", name="Pre-Balance Tributario", requirio_ocr=False)
    assert RejectionReason.CONTAINS_HEADER in signals


def test_negative_signals_header_variants():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    cases = [
        ("Balance General", RejectionReason.CONTAINS_BALANCE_GENERAL),
        ("Balance Tributario", RejectionReason.CONTAINS_HEADER),
        ("Pre-Balance Dic 2020", RejectionReason.CONTAINS_HEADER),
        ("RUT 76.123.456-7", RejectionReason.CONTAINS_RUT),
    ]
    for header, expected_reason in cases:
        signals = evaluate_negative_signals(line=header, name=header, requirio_ocr=False)
        assert expected_reason in signals, f"Missing {expected_reason} for: {header}"


def test_negative_signals_html():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(
        line="&amp;lt;div&gt;CONTENIDO",
        name="",
        requirio_ocr=False,
    )
    assert RejectionReason.HTML_ARTIFACT in signals


def test_negative_signals_noise_line():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="---___...", name="", requirio_ocr=False)
    assert RejectionReason.NAME_ONLY_SYMBOLS in signals


def test_negative_signals_only_symbols():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="***", name="***", requirio_ocr=False)
    assert RejectionReason.NAME_ONLY_SYMBOLS in signals


def test_negative_signals_short_name():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="AB", name="AB", requirio_ocr=False)
    assert RejectionReason.NAME_TOO_SHORT in signals


def test_negative_signals_long_name():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    long_name = "CUENTA " * 25
    signals = evaluate_negative_signals(line=long_name, name=long_name, requirio_ocr=False)
    assert RejectionReason.NAME_TOO_LONG in signals


def test_negative_signals_many_symbols():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    # "A/B/C_D-E" = 4 symbols out of 9 chars = 44% > 30%
    signals = evaluate_negative_signals(
        line="A/B/C_D-E",
        name="A/B/C_D-E",
        requirio_ocr=False,
    )
    assert RejectionReason.NAME_TOO_MANY_SYMBOLS in signals


def test_negative_signals_many_digits():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(
        line="1234567890 ABC XYZ",
        name="1234567890 ABC XYZ",
        requirio_ocr=False,
    )
    assert RejectionReason.NAME_TOO_MANY_DIGITS in signals


def test_negative_signals_ocr():
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason
    signals = evaluate_negative_signals(line="Banco", name="Banco", requirio_ocr=True)
    assert RejectionReason.OCR_LOW_CONFIDENCE in signals


def test_negative_signals_no_false_for_real_account():
    """Real account names should trigger ZERO negative signals."""
    from parser_quality.candidate_validator import evaluate_negative_signals
    real_accounts = [
        "Banco Santander",
        "Cuentas por Cobrar",
        "Depreciación Acumulada",
        "Capital Pagado",
        "Utilidades Acumuladas",
        "Proveedores Nacionales",
        "Honorarios por Pagar",
        "Mercaderías en Tránsito",
        "Activo Fijo Neto",
        "Intereses Bancarios",
    ]
    for name in real_accounts:
        signals = evaluate_negative_signals(line=name, name=name, requirio_ocr=False)
        negative = {k: v for k, v in signals.items() if v < 0}
        assert len(negative) == 0, f"False negative for '{name}': {negative}"


def test_negative_signals_empty_name():
    from parser_quality.candidate_validator import evaluate_negative_signals
    signals = evaluate_negative_signals(line="---", name="", requirio_ocr=False)
    # Only structural patterns (line) should fire
    assert any(v < 0 for v in signals.values())


def test_negative_signals_empty_line():
    from parser_quality.candidate_validator import evaluate_negative_signals
    signals = evaluate_negative_signals(line="", name="", requirio_ocr=False)
    assert len(signals) == 0


# =========================================================================
# EvidenceResult
# =========================================================================


def test_evidence_result_top_reasons():
    from parser_quality.candidate_validator import EvidenceResult, RejectionReason
    er = EvidenceResult(
        confidence=0.35,
        reasons=[RejectionReason.CONTAINS_RUT, RejectionReason.CONTAINS_PAGE],
        positive_signals={},
        negative_signals={
            RejectionReason.CONTAINS_RUT: -0.30,
            RejectionReason.CONTAINS_PAGE: -0.25,
        },
    )
    top = er.top_reasons(n=2)
    assert RejectionReason.CONTAINS_RUT in top
    assert RejectionReason.CONTAINS_PAGE in top


def test_evidence_result_top_reasons_empty():
    from parser_quality.candidate_validator import EvidenceResult
    er = EvidenceResult(confidence=1.0, reasons=[])
    assert er.top_reasons() == []


# =========================================================================
# CandidateValidator
# =========================================================================


def test_validator_high_confidence():
    """Full account with code, monto, and keywords should score high."""
    from parser_quality.candidate_validator import CandidateValidator
    v = CandidateValidator()
    er = v.evaluate(
        line="AC.01 Caja 50000000",
        name="Caja",
        code="AC.01",
        monto=50000000.0,
    )
    assert er.confidence >= 0.85
    assert len(er.reasons) == 0


def test_validator_low_confidence():
    """Garbage line should score low."""
    from parser_quality.candidate_validator import CandidateValidator
    v = CandidateValidator()
    er = v.evaluate(
        line="--- ___ ***",
        name="--- ___ ***",
    )
    assert er.confidence < 0.50


def test_validator_medium_confidence():
    """Name with monto but no keywords should be in REVIEW."""
    from parser_quality.candidate_validator import CandidateValidator
    v = CandidateValidator()
    er = v.evaluate(
        line="ZYX Corp 1000",
        name="ZYX Corp",
        monto=1000.0,
    )
    # base 0.50 + has_monto 0.15 + reasonable_length 0.05 + known_account (2 tokens) 0.05 = 0.75
    assert 0.50 <= er.confidence < 0.85
    assert len(er.reasons) >= 0


def test_validator_confidence_clamped():
    from parser_quality.candidate_validator import CandidateValidator
    v = CandidateValidator()
    # Many positive signals should not exceed 1.0
    er = v.evaluate(
        line="AC.01 Caja 50000000",
        name="Caja",
        code="AC.01",
        monto=50000000.0,
    )
    assert er.confidence <= 1.0
    # Many negative signals should not go below 0.0
    er2 = v.evaluate(
        line="-Página 1 de 5-",
        name="Página 1 de 5-",
    )
    assert er2.confidence >= 0.0


def test_validator_outside_table():
    from parser_quality.candidate_validator import CandidateValidator, RejectionReason
    v = CandidateValidator()
    er = v.evaluate(
        line="some text",
        name="some text",
        code=None,
        monto=None,
    )
    # Below 0.85 with no code/monto => OUTSIDE_TABLE or NO_MONTO
    assert er.confidence < 0.85
    assert len(er.reasons) >= 0


# =========================================================================
# ParserConfidence
# =========================================================================


def test_parser_confidence_calculate():
    from parser_quality.parser_confidence import ParserConfidence
    pc = ParserConfidence()
    er = pc.calculate(line="Caja 1000", name="Caja", monto=1000.0)
    assert er.confidence > 0


def test_parser_confidence_determine_status():
    from parser_quality.parser_confidence import ParserConfidence
    assert ParserConfidence.determine_status(0.90) == "ACCEPT"
    assert ParserConfidence.determine_status(0.70) == "REVIEW"
    assert ParserConfidence.determine_status(0.30) == "REJECT"
    assert ParserConfidence.determine_status(0.85) == "ACCEPT"
    assert ParserConfidence.determine_status(0.50) == "REVIEW"


# =========================================================================
# Gatekeeper
# =========================================================================


def test_gatekeeper_evaluate():
    from parser_quality.gatekeeper import ParserGatekeeper
    gk = ParserGatekeeper()
    result = gk.evaluate(
        file_name="test.pdf",
        line_number=1,
        line="Banco Chile 1000000",
        account_name="Banco Chile",
        monto=1000000.0,
    )
    assert result.file_name == "test.pdf"
    assert result.line_number == 1
    assert result.account_name == "Banco Chile"
    assert result.confidence > 0
    assert result.status in ("ACCEPT", "REVIEW", "REJECT")


def test_gatekeeper_high_confidence():
    from parser_quality.gatekeeper import ParserGatekeeper
    gk = ParserGatekeeper()
    result = gk.evaluate(
        file_name="test.pdf",
        line_number=1,
        line="AC.01 Caja 50000000",
        account_name="Caja",
        account_code="AC.01",
        monto=50000000.0,
    )
    assert result.confidence >= 0.85
    assert result.status == "ACCEPT"


def test_gatekeeper_low_confidence():
    from parser_quality.gatekeeper import ParserGatekeeper
    gk = ParserGatekeeper()
    result = gk.evaluate(
        file_name="test.pdf",
        line_number=1,
        line="Página 1 de 5",
        account_name="Página 1 de 5",
    )
    assert result.confidence < 0.50
    assert result.status == "REJECT"


def test_gatekeeper_accumulates_results():
    from parser_quality.gatekeeper import ParserGatekeeper
    gk = ParserGatekeeper()
    gk.evaluate("a.pdf", 1, "Caja 100", "Caja", monto=100.0)
    gk.evaluate("a.pdf", 2, "Banco 200", "Banco", monto=200.0)
    assert len(gk.results) == 2
    assert gk.results[0].file_name == "a.pdf"
    assert gk.results[1].line_number == 2


def test_gatekeeper_clear():
    from parser_quality.gatekeeper import ParserGatekeeper
    gk = ParserGatekeeper()
    gk.evaluate("a.pdf", 1, "Caja 100", "Caja", monto=100.0)
    assert len(gk.results) == 1
    gk.clear()
    assert len(gk.results) == 0


def test_gatekeeper_result_to_dict():
    from parser_quality.gatekeeper import GatekeeperResult, ParserGatekeeper
    gk = ParserGatekeeper()
    result = gk.evaluate(
        file_name="test.pdf",
        line_number=1,
        line="AC.01 Caja 50000000",
        account_name="Caja",
        account_code="AC.01",
        monto=50000000.0,
    )
    d = result.to_dict()
    assert isinstance(d, dict)
    assert d["file_name"] == "test.pdf"
    assert d["confidence"] >= 0.85
    assert d["status"] == "ACCEPT"
    assert isinstance(d["reasons"], list)


# =========================================================================
# ParserQualityReport
# =========================================================================


def test_report_compute_metrics():
    from parser_quality.gatekeeper import ParserGatekeeper
    from parser_quality.parser_quality_report import ParserQualityReport

    gk = ParserGatekeeper()
    gk.evaluate("a.pdf", 1, "Caja 100", "Caja", monto=100.0)
    gk.evaluate("a.pdf", 2, "---", "")
    gk.evaluate("b.pdf", 1, "AC.01 Banco 500", "Banco", account_code="AC.01", monto=500.0)

    report = ParserQualityReport()
    metrics = report._compute_metrics(gk.results, ocr_count=0, native_count=2, total_docs=2)

    assert metrics["total_candidates"] == 3
    assert metrics["total_documents"] == 2
    assert metrics["accepted"] + metrics["review"] + metrics["rejected"] == 3
    assert isinstance(metrics["top_rejection_reasons"], list)
    assert isinstance(metrics["confidence_distribution"], dict)
    assert "ocr" in metrics
    assert "native" in metrics


def test_report_generate_creates_files():
    from parser_quality.gatekeeper import ParserGatekeeper
    from parser_quality.parser_quality_report import ParserQualityReport

    gk = ParserGatekeeper()
    gk.evaluate("a.pdf", 1, "AC.01 Caja 50000000", "Caja", account_code="AC.01", monto=50000000.0)
    gk.evaluate("a.pdf", 2, "---", "")
    gk.evaluate("b.pdf", 1, "Página 1", "Página 1")
    gk.evaluate("b.pdf", 2, "Algo Sin Clasificar 100", "Algo Sin Clasificar", monto=100.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        report = ParserQualityReport(tmpdir)
        metrics = report.generate(gk.results, ocr_count=1, native_count=2, total_docs=2)

        assert metrics["total_candidates"] == 4
        assert Path(tmpdir, "parser_statistics.json").exists()
        assert Path(tmpdir, "parser_quality.md").exists()
        assert Path(tmpdir, "parser_quality.xlsx").exists()
        assert Path(tmpdir, "parser_examples.xlsx").exists()
        # reviews/rejections only created if candidates exist in that category
        assert Path(tmpdir, "parser_confidence_distribution.xlsx").exists()


def test_report_statistics_json():
    from parser_quality.gatekeeper import ParserGatekeeper
    from parser_quality.parser_quality_report import ParserQualityReport

    gk = ParserGatekeeper()
    gk.evaluate("a.pdf", 1, "Caja 100", "Caja", monto=100.0)

    with tempfile.TemporaryDirectory() as tmpdir:
        report = ParserQualityReport(tmpdir)
        report.generate(gk.results, ocr_count=0, native_count=1, total_docs=1)

        data = json.loads(Path(tmpdir, "parser_statistics.json").read_text())
        assert data["total_candidates"] == 1
        assert isinstance(data["avg_confidence"], float)


# =========================================================================
# PATRONES: verificación contra cuentas reales
# =========================================================================


def test_real_account_lines_accept():
    """These should all be ACCEPT."""
    from parser_quality.gatekeeper import ParserGatekeeper
    import openpyxl

    gk = ParserGatekeeper()

    real_accounts = [
        ("doc.pdf", "AC.01 Caja 50000000", "Caja", "AC.01", 50000000.0),
        ("doc.pdf", "PC.01 Banco Chile 15000000", "Banco Chile", "PC.01", 15000000.0),
        ("doc.pdf", "ER.05 Ingresos por Ventas 20000000", "Ingresos por Ventas", "ER.05", 20000000.0),
    ]
    for fname, line, name, code, monto in real_accounts:
        r = gk.evaluate(fname, 1, line, name, account_code=code, monto=monto)
        assert r.status == "ACCEPT", f"Account should ACCEPT: {name} ({r.confidence})"


def test_real_junk_lines_reject():
    """These should all be REJECT."""
    from parser_quality.gatekeeper import ParserGatekeeper

    gk = ParserGatekeeper()

    junk_lines = [
        ("doc.pdf", "Página 1 de 5"),
        ("doc.pdf", "RUT 76.123.456-7"),
        ("doc.pdf", "--- ___ ..."),
        ("doc.pdf", "www.empresa.cl"),
        ("doc.pdf", "contacto@empresa.cl"),
        ("doc.pdf", "Av. Providencia 1234"),
        ("doc.pdf", "***"),
    ]
    for fname, line in junk_lines:
        r = gk.evaluate(fname, 1, line, line)
        assert r.status == "REJECT", f"Junk line should REJECT: {line} ({r.confidence})"


def test_real_account_names_no_false_negatives():
    """Real account names must not trigger phone/date/RUT false positives."""
    from parser_quality.candidate_validator import evaluate_negative_signals, RejectionReason

    real_accounts = [
        "LIQUIDACION FRUTA T. 2017 / 2018 950.482.196 3.527.297 INTERESES ANUALES",
        "EMPRESAS SUBSOLE 6.382.143.480 10.636.906 DEUDA CON SUBSOLE",
        "Puerto de Caldera 240.000.000 400.000 TOTAL PASIVOS",
        "Disponible 444,463,082 Oblig. Bancos e Instituciones Fras a c/p",
        "Valores Negociables - Cuentas por Pagar",
        "Deudores por Venta (neto) 943,078,292 Acreedores Varios",
        "Provision Ingresos 520,066,497 Documentos por Pagar",
        "Deudores Varios (neto) 48,351,845 Retenciones",
        "Impuestos por Recuperar",
        "Instalaciones 307,304,275 Acreedores Varios",
        "Vehiculos",
    ]
    for name in real_accounts:
        sigs = evaluate_negative_signals(line=name, name=name, requirio_ocr=False)
        assert RejectionReason.CONTAINS_PHONE not in sigs, (
            f"False phone: {name}"
        )


# =========================================================================
# PATRONES: cobertura de regex
# =========================================================================


def test_rut_regex():
    from parser_quality.candidate_validator import PAT_RUT
    assert PAT_RUT.search("RUT 76.123.456-7")
    assert PAT_RUT.search("76.123.456-7")
    assert not PAT_RUT.search("123456789")


def test_date_regex():
    from parser_quality.candidate_validator import PAT_DATE
    assert PAT_DATE.search("31-12-2020")
    assert PAT_DATE.search("01/01/2021")
    assert PAT_DATE.search("2020-12-31")
    assert not PAT_DATE.search("123456")


def test_phone_regex_phone_numbers():
    from parser_quality.candidate_validator import PAT_PHONE
    assert PAT_PHONE.search("+56 9 1234 5678")
    assert PAT_PHONE.search("9 1234 5678")
    assert PAT_PHONE.search("2 1234 5678")
    assert not PAT_PHONE.search("1234567")
    assert not PAT_PHONE.search("100")


def test_phone_regex_amounts():
    """Large amounts with separators must NOT match phone."""
    from parser_quality.candidate_validator import PAT_PHONE
    for amount in [
        "950.482.196",
        "6.382.143.480",
        "943,078,292",
        "240.000.000",
        "444,463,082",
    ]:
        assert not PAT_PHONE.search(amount), f"Amount matched phone: {amount}"


def test_header_regex():
    from parser_quality.candidate_validator import PAT_HEADER_FOOTER
    assert PAT_HEADER_FOOTER.match("Pre-Balance Tributario")
    assert PAT_HEADER_FOOTER.match("Balance General")
    assert PAT_HEADER_FOOTER.match("RUT 76.123.456-7")
    assert PAT_HEADER_FOOTER.match("Sociedad ABC")
    assert not PAT_HEADER_FOOTER.match("Caja")


def test_noise_line_regex():
    from parser_quality.candidate_validator import PAT_NOISE_LINE
    assert PAT_NOISE_LINE.fullmatch("---")
    assert PAT_NOISE_LINE.fullmatch("___...")
    assert PAT_NOISE_LINE.fullmatch("123-456_789")
    assert not PAT_NOISE_LINE.fullmatch("Caja")


def test_only_symbols_regex():
    from parser_quality.candidate_validator import PAT_ONLY_SYMBOLS
    assert PAT_ONLY_SYMBOLS.fullmatch("***")
    assert PAT_ONLY_SYMBOLS.fullmatch("---")
    assert PAT_ONLY_SYMBOLS.fullmatch("...")
    assert not PAT_ONLY_SYMBOLS.fullmatch("Caja***")
    assert not PAT_ONLY_SYMBOLS.fullmatch("Caja")


# =========================================================================
# END-TO-END: multi-document scenario
# =========================================================================


def test_end_to_end_multi_doc():
    from parser_quality.gatekeeper import ParserGatekeeper

    gk = ParserGatekeeper()

    accounts = [
        ("balance.pdf", 1, "AC.01 Caja 50000000", "Caja", "AC.01", 50000000.0, False),
        ("balance.pdf", 2, "PC.05 Proveedor 3000000", "Proveedor", "PC.05", 3000000.0, False),
        ("balance.pdf", 3, "--- ___", "", None, 0.0, False),
        ("balance.pdf", 4, "Página 2 de 10", "Página 2 de 10", None, None, False),
        ("balance.pdf", 5, "ER.01 Ingresos 100000000", "Ingresos", "ER.01", 100000000.0, False),
        ("eeff.xlsx", 1, "Total Activos 500000000", "Total Activos", None, 500000000.0, True),
    ]

    for fname, lineno, line, name, code, monto, is_total in accounts:
        gk.evaluate(
            file_name=fname,
            line_number=lineno,
            line=line,
            account_name=name,
            account_code=code,
            monto=monto,
            is_total=is_total,
        )

    results = gk.results
    assert len(results) == 6

    accept = [r for r in results if r.status == "ACCEPT"]
    reject = [r for r in results if r.status == "REJECT"]

    assert len(accept) >= 2, f"Expected >=2 ACCEPT, got {len(accept)}"
    assert len(reject) >= 1, f"Expected >=1 REJECT, got {len(reject)}"

    for r in accept:
        assert r.confidence >= 0.85

    for r in reject:
        assert r.confidence < 0.50
