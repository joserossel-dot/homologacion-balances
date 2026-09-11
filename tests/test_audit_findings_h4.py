import pytest
from pathlib import Path
from parser_universal import ParserPDF
from pipeline.homologation_pipeline import HomologationPipeline


def test_h4_extraer_lineas_pagina_orientada_mock():
    # Characters for 'CAJA 100' rendered with 90 deg clockwise matrix (0, 1, -1, 0)
    # Consecutive characters have bottom[i+1] == top[i]
    chars = [
        {'text': 'C', 'x0': 50.0, 'x1': 56.0, 'top': 700.0, 'bottom': 705.0, 'upright': False, 'matrix': (0.0, 1.0, -1.0, 0.0, 0, 0)},
        {'text': 'A', 'x0': 50.0, 'x1': 56.0, 'top': 695.0, 'bottom': 700.0, 'upright': False, 'matrix': (0.0, 1.0, -1.0, 0.0, 0, 0)},
        {'text': 'J', 'x0': 50.0, 'x1': 56.0, 'top': 690.0, 'bottom': 695.0, 'upright': False, 'matrix': (0.0, 1.0, -1.0, 0.0, 0, 0)},
        {'text': 'A', 'x0': 50.0, 'x1': 56.0, 'top': 685.0, 'bottom': 690.0, 'upright': False, 'matrix': (0.0, 1.0, -1.0, 0.0, 0, 0)},
        # Word space gap (> 2.0 pt gap between 685.0 and 675.0)
        {'text': '1', 'x0': 50.0, 'x1': 56.0, 'top': 670.0, 'bottom': 675.0, 'upright': False, 'matrix': (0.0, 1.0, -1.0, 0.0, 0, 0)},
        {'text': '0', 'x0': 50.0, 'x1': 56.0, 'top': 665.0, 'bottom': 670.0, 'upright': False, 'matrix': (0.0, 1.0, -1.0, 0.0, 0, 0)},
        {'text': '0', 'x0': 50.0, 'x1': 56.0, 'top': 660.0, 'bottom': 665.0, 'upright': False, 'matrix': (0.0, 1.0, -1.0, 0.0, 0, 0)},
    ]

    class MockPage:
        def __init__(self, chars):
            self.chars = chars
        def extract_text(self):
            # unrotated naive extraction sorts by top ascending
            return "001 AJAC"

    page = MockPage(chars)
    lines = ParserPDF._extraer_lineas_pagina_orientada(page)
    assert len(lines) == 1
    assert lines[0] == "CAJA 100"


def test_h4_gonzagri_pipeline_execution():
    candidate_paths = [
        Path("/Users/josealfonsorossel/AI-Projects/GitHub/ManuVaciador/datasets/TRAINING/Balance Agrícola Gonzagri Ltda.pdf"),
        Path("/Users/josealfonsorossel/AI-Projects/GitHub/VaciadorManu/datasets/TRAINING/Balance Agrícola Gonzagri Ltda.pdf"),
    ]
    pdf_path = next((p for p in candidate_paths if p.exists()), None)
    if pdf_path is None:
        pytest.skip("Balance Gonzagri PDF not present in test environment")

    pipeline = HomologationPipeline()
    res = pipeline.process(pdf_path)

    assert res["document_family"] == "coded_balance"
    assert res["requirio_ocr"] is False
    assert res["accounts_total"] > 200
    # Before H4, origin_fallback was 99.3% (277 accounts). Now it should be < 5%
    methods = [c.get("method") for c in res["classified"]]
    fallback_count = methods.count("origin_fallback")
    assert fallback_count <= 10
    # Exact + fuzzy dictionary matches should be substantial
    high_conf = sum(1 for c in res["classified"] if c.get("method") in {"dictionary_exact", "dictionary_fuzzy", "code"})
    assert high_conf >= 50
