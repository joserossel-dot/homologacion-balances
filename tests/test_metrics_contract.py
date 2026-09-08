from types import SimpleNamespace
from unittest.mock import MagicMock

from validation.classification_metrics import (
    account_metrics, document_family, family_metrics, method_provenance,
)
from validation.metrics_engine import MetricsEngine
from validation.balance_validator import BalanceValidator
from validation.report_builder import ReportBuilder
from validation.prepost_balance import compare_pre_post, early_balance_state
from validation.promotion_policy import MINIMUM_EVIDENCE, evaluate_promotion
from validation.validation_session import ValidationSession
from adapters.kb_adapter import KBAdapter
from adapters.validation_adapter import ValidationAdapter
from document_context import DocumentContext
from review.cmcc_review_pipeline import _classification_totals


def test_residual_no_se_mezcla_con_clasificacion_especifica():
    rows = [
        {"standard_code": "AC.01", "method": "dictionary_exact"},
        {"standard_code": "AC.08", "method": "origin_fallback", "review_required": True},
        {"standard_code": None, "method": "unclassified"},
        {"standard_code": None, "method": "control", "is_total": True},
    ]
    metrics = account_metrics(rows)
    assert metrics == {
        "accounts_classified_specific": 1,
        "accounts_classified_residual": 1,
        "accounts_unclassified": 1,
        "accounts_pending_review": 2,
        "accounts_controls": 1,
        "accounts_total_detail": 3,
        "accounts_classified": 2,
    }
    assert method_provenance("origin_fallback") == "residual"
    assert method_provenance("dictionary_exact") == "specific"


def test_metodos_historicos_locales_conservan_procedencia_explicita():
    assert method_provenance("diccionario_exacto") == "specific"
    assert method_provenance("diccionario_fuzzy+columna") == "specific"
    assert method_provenance("columna_ambiguo") == "specific"
    assert method_provenance("origin_fallback") == "residual"
    assert method_provenance("decision_conflict") == "residual"
    assert method_provenance("sin_clasificar+filtro_columna") == "unclassified"
    residual = account_metrics([{"standard_code": "AC.08", "method": ""}])
    assert residual["accounts_classified_residual"] == 1
    assert residual["accounts_pending_review"] == 1


def test_metricas_sin_codigo_segmentan_familia_y_cobertura():
    files = [{"source_file": "ifrs.pdf", "ocr": False}]
    accounts = [
        {"source_file": "ifrs.pdf", "account_code": "", "standard_code": "AC.01",
         "method": "audited_statement_label"},
        {"source_file": "ifrs.pdf", "account_code": "", "standard_code": "AC.08",
         "method": "origin_fallback", "review_required": True},
    ]
    assert document_family(files[0], accounts) == "ifrs_no_code"
    families = family_metrics(files, accounts)
    assert families["ifrs_no_code"]["specific_coverage"] == 0.5
    assert families["ifrs_no_code"]["assigned_coverage"] == 1.0
    assert families["ifrs_no_code"]["methods"]["origin_fallback"] == 1


def test_familias_ocr_y_balance_codificado_son_excluyentes():
    coded = [{"account_code": "110101", "standard_code": "AC.01", "method": "code"}]
    assert document_family({"ocr": True}, coded) == "ocr_scanned"
    assert document_family({"ocr": False}, coded) == "coded_balance"


def test_metrics_engine_publica_contrato_unico_y_familias():
    session = ValidationSession(
        processed_files=[{"source_file": "x.pdf", "ocr": False, "accounts_controls": 2}],
        processed_accounts=[
            {"source_file": "x.pdf", "account_code": "1", "standard_code": "AC.01", "method": "code"},
            {"source_file": "x.pdf", "account_code": "", "standard_code": "AC.08", "method": "origin_fallback", "review_required": True},
        ],
    )
    metrics = MetricsEngine().compute(session)
    assert metrics["accounts_classified_specific"] == 1
    assert metrics["accounts_classified_residual"] == 1
    assert metrics["accounts_controls"] == 2
    assert metrics["accounts_total_detail"] == 2
    assert metrics["accounts_classified"] == 2
    assert metrics["families"]["coded_balance"]["specific_coverage"] == 0.5


def test_controles_reportados_y_presentes_en_filas_no_se_duplican():
    session = ValidationSession(
        processed_files=[{"source_file": "x.pdf", "accounts_controls": 1}],
        processed_accounts=[
            {"source_file": "x.pdf", "is_total": True, "method": "control"},
            {"source_file": "x.pdf", "standard_code": "AC.01", "method": "code"},
        ],
    )
    metrics = MetricsEngine().compute(session)
    assert metrics["accounts_controls"] == 1
    assert metrics["families"]["ifrs_no_code"]["accounts_controls"] == 1


def test_fila_excluida_no_es_detalle_ni_pendiente():
    metrics = account_metrics([{
        "codigo_clasificado": "__EXCLUIR__", "metodo": "excluido_analista",
    }])
    assert metrics["accounts_total_detail"] == 0
    assert metrics["accounts_unclassified"] == 0
    assert metrics["accounts_pending_review"] == 0


def test_adapter_de_validacion_conserva_contrato_y_familia_del_pipeline():
    pipeline_result = {
        "source_file": "x.pdf", "document_family": "ifrs_no_code",
        "accounts_total": 2, "accounts_classified": 1,
        "accounts_classified_specific": 0, "accounts_classified_residual": 1,
        "accounts_unclassified": 0, "accounts_pending_review": 1,
        "accounts_controls": 1, "accounts_total_detail": 1,
        "classified": [{
            "account_name": "Otros activos", "standard_code": "AC.08",
            "method": "origin_fallback", "classification_amount": 100,
            "review_required": True,
        }],
        "ignored": [{"account_name": "Total activos", "is_total": True}],
    }
    result = BalanceValidator().validate_from_pipeline(pipeline_result)
    assert result.format_family == "ifrs_no_code"
    assert result.accounts_classified_specific == 0
    assert result.accounts_classified_residual == 1
    assert result.accounts_pending_review == 1
    assert result.accounts_controls == 1
    assert result.integrity_score.classification_score == 0.0


def test_kb_adapter_publica_contrato_sin_inflar_unclassified_ni_controles(tmp_path):
    source = tmp_path / "x.pdf"
    source.write_bytes(b"pdf")
    ctx = DocumentContext(str(source))
    ctx.set_custom("parser_resultado", SimpleNamespace(requirio_ocr=True))
    classified = [
        {"source_file": source.name, "standard_code": "AC.01", "method": "dictionary_exact"},
        {"source_file": source.name, "standard_code": "AC.08", "method": "origin_fallback"},
        {"source_file": source.name, "standard_code": None, "method": "unclassified"},
    ]
    ignored = [
        {"method": "control", "is_total": True},
        {"method": "ignored", "ignored_reason": "movement_only"},
    ]
    summary = KBAdapter._build_v1_summary(
        ctx, classified, ignored, accounts_total=5,
    )
    assert summary["accounts_classified"] == 2
    assert summary["accounts_classified_specific"] == 1
    assert summary["accounts_classified_residual"] == 1
    assert summary["accounts_unclassified"] == 1
    assert summary["accounts_pending_review"] == 2
    assert summary["accounts_controls"] == 1
    assert summary["accounts_total_detail"] == 3
    assert summary["document_family"] == "ocr_scanned"


def test_kb_adapter_infiere_balance_codificado_aunque_la_fila_quede_ignorada(tmp_path):
    source = tmp_path / "x.pdf"
    source.write_bytes(b"pdf")
    ctx = DocumentContext(str(source))
    ctx.set_custom("parser_resultado", SimpleNamespace(requirio_ocr=False))
    summary = KBAdapter._build_v1_summary(
        ctx,
        [],
        [{
            "account_code": "110101",
            "account_name": "Cuenta con movimiento sin saldo",
            "method": "ignored",
            "ignored_reason": "movement_only",
        }],
        accounts_total=1,
    )
    assert summary["document_family"] == "coded_balance"


def test_validation_adapter_entrega_resultado_canonico_al_validador():
    ctx = MagicMock()
    ctx.source_file = "/tmp/x.pdf"
    ctx.parser = SimpleNamespace(raw_accounts=[])
    ctx.metadata = None
    custom = {
        "classified": [{"standard_code": "AC.08", "method": "origin_fallback"}],
        "ignored": [{"method": "control", "is_total": True}],
        "pipeline_v1_result": {
            "accounts_classified_specific": 0,
            "accounts_classified_residual": 1,
            "accounts_unclassified": 0,
            "accounts_pending_review": 1,
            "accounts_controls": 1,
            "accounts_total_detail": 1,
            "accounts_classified": 1,
            "document_family": "ifrs_no_code",
        },
    }
    ctx.get_custom.side_effect = lambda key, default=None: custom.get(key, default)
    adapter = ValidationAdapter()
    adapter._validator = MagicMock()
    adapter._validator.validate_from_pipeline.return_value = SimpleNamespace(
        integrity_score=None, subtotal_results=[], equation_results=[], missing_candidates=[],
    )
    adapter.run(ctx)
    payload = adapter._validator.validate_from_pipeline.call_args.args[0]
    assert payload["accounts_classified_specific"] == 0
    assert payload["accounts_classified_residual"] == 1
    assert payload["accounts_controls"] == 1
    assert payload["document_family"] == "ifrs_no_code"


def test_cmcc_review_reporta_cobertura_especifica_y_asignada_por_separado():
    totals = _classification_totals({
        "accounts_total": 5, "accounts_total_detail": 3,
        "accounts_classified_specific": 1, "accounts_classified_residual": 1,
        "accounts_unclassified": 1, "accounts_pending_review": 2,
        "accounts_controls": 1, "accounts_classified": 2,
    })
    assert totals == {
        "input": 5, "detail": 3, "specific": 1, "residual": 1,
        "assigned": 2, "unclassified": 1, "pending": 2, "controls": 1,
    }


def test_validation_session_no_pierde_campos_canonicos_al_integrar_resultado():
    session = ValidationSession()
    result = {
        "source_file": "x.pdf", "classified": [],
        "accounts_classified": 2, "accounts_classified_specific": 1,
        "accounts_classified_residual": 1, "accounts_unclassified": 1,
        "accounts_pending_review": 2, "accounts_controls": 3,
        "accounts_total_detail": 3, "document_family": "ifrs_no_code",
        "balance_reconciliation": {"classification_degradation": False},
        "export_blocked_by_classification_degradation": False,
    }
    session.merge_file_result(result)
    entry = session.processed_files[0]
    for key in (
        "accounts_classified_specific", "accounts_classified_residual",
        "accounts_unclassified", "accounts_pending_review", "accounts_controls",
        "accounts_total_detail", "document_family", "balance_reconciliation",
    ):
        assert entry[key] == result[key]


def test_reporte_validacion_propaga_contrato_y_familias(tmp_path):
    session = ValidationSession(
        processed_files=[{"source_file": "x.pdf", "ocr": True, "accounts_controls": 1}],
        processed_accounts=[
            {"source_file": "x.pdf", "standard_code": "AC.01", "method": "code"},
            {"source_file": "x.pdf", "standard_code": "AC.08", "method": "origin_fallback",
             "review_required": True},
        ],
    )
    metrics = MetricsEngine().compute(session)
    out = ReportBuilder(tmp_path).build_all(session, metrics, timestamp="fixed")
    summary = out.joinpath("summary.md").read_text(encoding="utf-8")
    benchmark = out.joinpath("benchmark.csv").read_text(encoding="utf-8")
    assert "Clasificadas específicas:** 1" in summary
    assert "Clasificadas residuales:** 1" in summary
    assert "ocr_scanned" in summary
    assert "accounts_classified_specific" in benchmark


def test_pre_post_bloquea_degradacion_y_lista_cambio_responsable():
    cert = SimpleNamespace(
        totales_finales_validos=True,
        diferencias={"activo_menos_pasivo_patrimonio": 0},
    )
    accounts = [
        {"account_name": "Banco", "classification_amount": 100,
         "nature": "activo", "final_code": "PC.08", "method": "origin_fallback"},
        {"account_name": "Capital", "classification_amount": 100,
         "nature": "pasivo", "final_code": "PAT.01", "method": "dictionary_exact"},
    ]
    result = compare_pre_post(cert, accounts, late_difference=-200, tolerance=0)
    assert result["classification_degradation"] is True
    assert result["responsible_changes"][0]["account"] == "Banco"
    assert result["responsible_changes"][0]["impact"] == -200


def test_pre_post_no_inventa_contrato_temprano_ausente():
    assert early_balance_state(SimpleNamespace()).get("available") is False
    result = compare_pre_post(SimpleNamespace(), [], late_difference=100)
    assert result["classification_degradation"] is False


def test_promocion_default_exige_supervisor_evidencia_y_sin_conflictos():
    denied = evaluate_promotion(
        supervisor="", evidence=set(), conflicts=1, approved=False,
    )
    assert not denied.allowed
    assert denied.reversible
    allowed = evaluate_promotion(
        supervisor="supervisor", evidence=set(MINIMUM_EVIDENCE),
        conflicts=0, approved=True,
    )
    assert allowed.allowed
    assert allowed.expires_in_days == 365
