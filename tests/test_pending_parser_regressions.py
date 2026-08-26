import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import parser_universal as p


def test_numeric_name_suffix_is_not_merged_into_debit():
    headers = ["Cuenta", "Debe", "Haber", "Deudor", "Acreedor", "Activo", "Pasivo", "Pérdidas", "Ganancias"]
    words = [{"text": text, "x0": i*100, "x1": i*100+30, "top": 10} for i, text in enumerate(headers)]
    words += [{"text": "BANCOESTADO", "x0": 0, "x1": 45, "top": 30},
              {"text": "1", "x0": 65, "x1": 69, "top": 30}]
    words += [{"text": text, "x0": (i+1)*100, "x1": (i+1)*100+30, "top": 30}
              for i, text in enumerate(["120", "20", "100", "0", "100", "0", "0", "0"])]
    lines, _ = p._extraer_tabla_balance_por_coordenadas(SimpleNamespace(extract_words=lambda **kw: words))
    assert lines == ["BANCOESTADO 1 120 20 100 0 100 0 0 0"]


def test_hierarchical_parent_requires_prefix_and_amount_evidence():
    lines = ["11012 Bancos 120 20 100 0 100 0 0 0",
             "1101201 Banco uno 70 10 60 0 60 0 0 0",
             "1101202 Banco dos 50 10 40 0 40 0 0 0"]
    accounts = [p.parsear_linea(l, i, p.FormatoCodigo.COMPACTO, ".") for i,l in enumerate(lines)]
    values = [dict(c.montos_columnas) for c in accounts]
    assert p.marcar_subtotales_jerarquicos(accounts) == 1
    assert accounts[0].es_total
    assert [c.montos_columnas for c in accounts] == values
    accounts[0].es_total = False
    accounts[1].codigo = "9999999"
    assert p.marcar_subtotales_jerarquicos(accounts) == 0
    accounts[1].codigo = "1101201"
    accounts[0].montos_columnas["debitos"] += 1
    assert p.marcar_subtotales_jerarquicos(accounts) == 0
    accounts[0].montos_columnas["creditos"] += 1
    assert p.marcar_subtotales_jerarquicos(accounts) == 1
    assert accounts[0].montos_columnas["debitos"] == 121


def test_classified_page_does_not_inherit_eight_column_geometry():
    words = []
    for row in range(6):
        words.extend([{"text": "Cuenta", "x0": 10, "x1": 80, "top": row*20},
                      {"text": "100", "x0": 500, "x1": 530, "top": row*20}])
    assert p._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words), list(range(0, 900, 100))
    ) == ([], None)


@pytest.mark.parametrize("filename,pages,finals_valid", [
    ("parque_cultural_valparaiso_2024.pdf", None, True),
    ("london38_balance.pdf", [1], True),
    ("afuminsal_2016.pdf", None, True),
    ("fundacion_arte_solidaridad_2024.pdf", None, False),
])
def test_documento_real_opcional(filename, pages, finals_valid, tmp_path):
    """Documentos privados externos: no se incorporan al repositorio."""
    folder = os.environ.get("BALANCE_REAL_TEST_DIR")
    if not folder:
        pytest.skip("Defina BALANCE_REAL_TEST_DIR para la matriz privada")
    from document_scope import select_pdf
    source = Path(folder) / filename
    content = source.read_bytes()
    path = tmp_path / filename
    path.write_bytes(select_pdf(content, pages) if pages else content)
    result = p.ParserPDF().parsear(path)
    cert = result.certificacion_extraccion
    assert (cert.estado == "certificada" or cert.columnas_finales_validadas) is finals_valid
    if filename.startswith(("parque_", "london")):
        assert cert.estado == "certificada"
        assert not any(cert.diferencias.values())
        assert not cert.filas_inconsistentes
        if filename.startswith("parque_"):
            assert cert.columnas_finales_validadas
            assert all(c.es_total for c in result.cuentas if not c.codigo and c.monto)
    elif filename.startswith("afuminsal"):
        assert cert.resultado_ejercicio == 9910945
        assert any(c.codigo == "2301001" and c.monto == 15201792 for c in result.cuentas)
    else:
        assert cert.estado == "fallida"
        assert cert.filas_inconsistentes
    assert source.read_bytes() == content
