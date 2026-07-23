import pytest
import pandas as pd
import tempfile
from pathlib import Path
from knowledge.concept import Concept
from knowledge.repository import Repository
from knowledge.normalizer import Normalizer
from knowledge.builder import Builder


@pytest.fixture
def repo():
    r = Repository("/tmp/_test_builder.json")
    r.add(Concept(id="AC.01", codigo="AC.01", nombre="Caja y Bancos",
                  categoria="activo_corriente", tipo_estado_financiero="balance",
                  sinonimos=["Efectivo", "Disponible"],
                  palabras_clave=["caja", "bancos"],
                  confidence=0.9, version="1.0.0", ultima_revision="2026-07-08"))
    r.add(Concept(id="PC.01", codigo="PC.01", nombre="Proveedores",
                  categoria="pasivo_corriente", tipo_estado_financiero="balance",
                  sinonimos=["Cuentas por Pagar"],
                  palabras_clave=["proveedores", "proveedor"],
                  confidence=0.85, version="1.0.0", ultima_revision="2026-07-08"))
    return r


def test_build_from_unclassified(repo, tmp_path):
    xlsx_path = tmp_path / "test_unclassified.xlsx"
    pd.DataFrame({
        "account_name": ["Caja General", "Proveedores Nacionales", "ZXKXYZ"],
        "source_file": ["emp1", "emp1", "emp2"],
        "source_page": [1, 1, 1],
        "classification_amount": [100.0, 200.0, 300.0],
    }).to_excel(xlsx_path, index=False)

    builder = Builder(repo, proposals_dir=tmp_path / "proposals")
    proposals = builder.build_from_unclassified(xlsx_path)

    assert len(proposals) == 3

    # Caja should match AC.01
    caja = [p for p in proposals if "Caja" in p.texto_observado][0]
    assert caja.codigo_sugerido == "AC.01"
    assert caja.score > 0

    # ZXKXYZ should have no match
    no_match = [p for p in proposals if "ZXKXYZ" in p.texto_observado][0]
    assert no_match.score == 0.0


def test_save_proposals(repo, tmp_path):
    xlsx_path = tmp_path / "test_unclassified.xlsx"
    pd.DataFrame({
        "account_name": ["Caja General"],
        "source_file": ["emp1"],
        "source_page": [1],
        "classification_amount": [100.0],
    }).to_excel(xlsx_path, index=False)

    builder = Builder(repo, proposals_dir=tmp_path / "proposals")
    proposals = builder.build_from_unclassified(xlsx_path)
    xlsx_out, json_out = builder.save_proposals(proposals, "test")

    assert xlsx_out.exists()
    assert json_out.exists()


def test_build_and_save(repo, tmp_path):
    xlsx_path = tmp_path / "test_unclassified.xlsx"
    pd.DataFrame({
        "account_name": ["Caja General"],
        "source_file": ["emp1"],
        "source_page": [1],
        "classification_amount": [100.0],
    }).to_excel(xlsx_path, index=False)

    builder = Builder(repo, proposals_dir=tmp_path / "proposals")
    xlsx_out, json_out = builder.build_and_save(xlsx_path)
    assert xlsx_out.exists()
    assert json_out.exists()


if __name__ == "__main__":
    pytest.main([__file__])
