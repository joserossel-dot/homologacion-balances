from pathlib import Path

import parser_universal as parser
from scripts.certify_local_corpus import (
    _account_snapshot,
    _document_family,
    _family_metrics,
    build_corpus_measurement,
)
from scripts.pytest_collection_gate import parse_collected_count


def test_detecta_linea_fusionada_entre_dos_glosas():
    reasons = parser.detectar_linea_sospechosa(
        "CAJA 5.519,080 PROVEEDORES", mediana_longitud=20,
    )
    assert "multiples_glosas_separadas_por_monto" in reasons


def test_negativo_legitimo_no_es_linea_fusionada():
    reasons = parser.detectar_linea_sospechosa(
        "Gastos financieros (1.200)", mediana_longitud=20,
    )
    assert reasons == []
    account = parser.parsear_linea(
        "Gastos financieros (1.200)", 1, parser.FormatoCodigo.SIN_CODIGO, ".",
    )
    assert account is not None
    parser.marcar_cuenta_sospechosa(account, account.nombre, reasons)
    assert account.monto == -1200
    assert account.requiere_revision_extraccion is False


def test_cuenta_sospechosa_baja_confianza_y_bloquea_revision_automatica():
    account = parser.CuentaRaw(1, None, "Caja 5.519,080 Proveedores", 5519080)
    parser.marcar_cuenta_sospechosa(
        account, account.nombre, ["multiples_glosas_separadas_por_monto"],
    )
    snapshot = _account_snapshot([account], {
        "rows": [{"line": 1, "code": "AC.01", "review": False}],
    })
    assert account.confianza_extraccion == 0.35
    assert snapshot[0]["requires_review"] is True
    assert snapshot[0]["extraction_review_reasons"]


def test_rut_y_direccion_no_se_confunden_con_monto_incrustado():
    for name in ("Rut 17.783.780-6", "NEVERIA 4.600 OFICINA"):
        account = parser.CuentaRaw(1, None, name, 0)
        parser.marcar_cuenta_sospechosa(account, name, [])
        assert account.requiere_revision_extraccion is False


def test_ocr_requerido_sin_runtime_es_fallido_explicito(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(parser, "validar_archivo", lambda path: (True, "OK"))
    monkeypatch.setattr(parser.ParserPDF, "_analizar_documento", lambda self, path: None)
    monkeypatch.setattr(parser, "extraer_encabezados_documento_pdf", lambda path: [])
    monkeypatch.setattr(
        parser, "verificar_runtime_ocr",
        lambda: {"available": False, "error": "Falta idioma spa."},
    )
    monkeypatch.setattr(
        parser.ParserPDF, "_extraer_lineas", lambda self, path, context: ([], True, 0),
    )
    result = parser.ParserPDF().parsear(pdf)
    assert result.certificacion_extraccion.estado == "fallida"
    assert result.certificacion_extraccion.metodo == "ocr_runtime_gate"
    assert any("Falta idioma spa" in reason for reason in result.certificacion_extraccion.razones)


def test_contrato_de_familias_cubre_rutas_requeridas():
    coded = [parser.CuentaRaw(1, "110101", "Caja", 100)]
    ifrs = [parser.CuentaRaw(1, None, "Cash and cash equivalents", 100)]
    audited_classification = {
        "rows": [{"method": "audited_statement_label", "code": "AC.01"}],
        "classified": 1, "automatic": 1, "review": 0,
    }
    assert _document_family(coded, requires_ocr=False, classification={"rows": []}) == "codificado"
    assert _document_family(ifrs, requires_ocr=True, classification={"rows": []}) == "escaneado_ocr"
    assert _document_family(
        ifrs, requires_ocr=False, classification=audited_classification,
    ) == "ifrs_sin_codigo"
    metrics = _family_metrics(
        ifrs, requires_ocr=False, classification=audited_classification,
    )
    assert metrics["audited_statement_label_rows"] == 1


def test_medicion_corpus_tiene_denominador_hash_y_orden_determinista():
    rows = [
        {"file": "b.pdf", "sha256": "b" * 64, "status": "ok", "raw_accounts": 2,
         "certification": {"state": "certificada"}, "family_metrics": {"family": "codificado"}},
        {"file": "a.pdf", "sha256": "a" * 64, "status": "error"},
    ]
    measurement = build_corpus_measurement(rows)
    assert measurement["denominator_documents"] == 2
    assert measurement["successful_documents"] == 1
    assert [row["file"] for row in measurement["documents"]] == ["a.pdf", "b.pdf"]


def test_collection_gate_reports_zero_explicitly():
    assert parse_collected_count("no tests collected in 0.01s") == 0
    assert parse_collected_count("1052 tests collected in 3.1s") == 1052


def test_dockerfiles_fijan_versiones_oficiales_debian_bookworm():
    root = Path(__file__).resolve().parents[1]
    dockerfiles = [
        (root / "Dockerfile").read_text(encoding="utf-8"),
        (root / "deployment/onprem/Dockerfile").read_text(encoding="utf-8"),
    ]
    for dockerfile in dockerfiles:
        assert "ARG PYTHON_BUILD_IMAGE=python:3.12-slim-bookworm" in dockerfile
        assert "ARG TESSERACT_OCR_VERSION=5.3.0-2" in dockerfile
        assert "ARG TESSERACT_SPA_VERSION=1:4.1.0-2" in dockerfile
        assert '"tesseract-ocr=${TESSERACT_OCR_VERSION}"' in dockerfile
        assert '"tesseract-ocr-spa=${TESSERACT_SPA_VERSION}"' in dockerfile
        assert "PYTHON_BUILD_IMAGE con `python:...@sha256:<digest verificado>`" in dockerfile
        # No se registra un digest sin haberlo resuelto para cada arquitectura.
        assert "ARG PYTHON_BUILD_IMAGE=python:3.12-slim-bookworm@sha256:" not in dockerfile


def test_evaluacion_onprem_no_puede_cambiar_a_trixie_con_pins_bookworm():
    root = Path(__file__).resolve().parents[1]
    compose = (root / "deployment/onprem/docker-compose.evaluation.yml").read_text(
        encoding="utf-8",
    )
    env_example = (root / "deployment/onprem/.env.example").read_text(encoding="utf-8")
    for content in (compose, env_example):
        assert "python:3.12-slim-bookworm" in content
        assert "python:3.12-slim\n" not in content
        assert "TESSERACT_OCR_VERSION" in content
        assert "TESSERACT_SPA_VERSION" in content
    assert compose.count("TESSERACT_OCR_VERSION: ${TESSERACT_OCR_VERSION:-5.3.0-2}") == 2
    assert compose.count("TESSERACT_SPA_VERSION: ${TESSERACT_SPA_VERSION:-1:4.1.0-2}") == 2
