from pathlib import Path

import pytest

import parser_universal
from document_intelligence.document_classifier import DocumentClassifier
from document_intelligence.models import DocumentType
from parser_universal import ExtractionContext, OrigenColumna, ParserPDF


class SyntheticDocumentParser(ParserPDF):
    """Ejecuta el flujo real del parser con extracción sintética controlada."""

    def __init__(self, lines: list[str], *, ocr: bool = False, rotation: int = 0):
        self._synthetic_lines = lines
        self._synthetic_ocr = ocr
        self._synthetic_rotation = rotation

    def _analizar_documento(self, path: Path):
        return None

    def _extraer_lineas(self, path: Path, context: ExtractionContext | None):
        return list(self._synthetic_lines), self._synthetic_ocr, self._synthetic_rotation


@pytest.fixture
def synthetic_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "balance_sintetico.pdf"
    path.write_bytes(b"%PDF-1.4\n% fixture sintetico; extraccion controlada\n")
    return path


def test_documento_estandar_recorrer_parser_completo(synthetic_pdf: Path):
    result = SyntheticDocumentParser([
        "BALANCE TRIBUTARIO",
        "11010 CAJA 1.250.000 0 0 0",
        "21010 PROVEEDORES 0 800.000 0 0",
    ]).parsear(synthetic_pdf)

    accounts = [account for account in result.cuentas if account.codigo]
    assert [account.nombre for account in accounts] == ["CAJA", "PROVEEDORES"]
    assert accounts[0].origen_columna is OrigenColumna.ACTIVO
    assert accounts[1].origen_columna is OrigenColumna.PASIVO


def test_documento_doble_columna_respeta_layout_detectado(
    synthetic_pdf: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(parser_universal, "ENABLE_DYNAMIC_LAYOUT", True)
    context = ExtractionContext(
        layout_hint=["activo", "pasivo"],
        layout_confidence=0.95,
    )
    result = SyntheticDocumentParser([
        "CUENTA ACTIVO PASIVO",
        "11010 CAJA 500.000 0",
        "21010 PROVEEDORES 0 300.000",
    ]).parsear(synthetic_pdf, context)

    accounts = [account for account in result.cuentas if account.codigo]
    assert [account.origen_columna for account in accounts] == [
        OrigenColumna.ACTIVO,
        OrigenColumna.PASIVO,
    ]
    assert any("LayoutDetector (context)" in warning for warning in result.advertencias)


def test_documento_ocr_reduce_confianza_y_deja_traza(synthetic_pdf: Path):
    result = SyntheticDocumentParser(
        ["11010 CAJA 125.000 0 0 0"], ocr=True, rotation=90,
    ).parsear(synthetic_pdf)

    assert result.requirio_ocr is True
    assert result.rotacion_aplicada == 90
    assert result.cuentas[0].confianza_extraccion == 0.75
    assert any("procesado vía OCR" in warning for warning in result.advertencias)


def test_documento_rotado_conserva_correccion_visible(synthetic_pdf: Path):
    context = ExtractionContext(rotation_hint=180, rotation_confidence=0.95)
    result = SyntheticDocumentParser(
        ["11010 CAJA 125.000 0 0 0"], rotation=180,
    ).parsear(synthetic_pdf, context)

    assert result.requirio_ocr is False
    assert result.rotacion_aplicada == 180
    assert any("corregido desde rotación 180" in warning for warning in result.advertencias)


def test_estructura_desconocida_se_clasifica_como_otro():
    classification = DocumentClassifier().classify([
        "INFORME SIN ESTRUCTURA CONTABLE",
        "texto libre sin columnas ni encabezados reconocibles",
    ])

    assert classification.document_type is DocumentType.OTRO
    assert classification.confidence <= 0.2
