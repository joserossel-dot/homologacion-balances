import json
from pathlib import Path

from catalog_aliases import (
    canonical_catalog_code, canonicalize_catalog, canonicalize_dictionary,
)
from catalog_selection import opciones_clasificacion


BASE_DIR = Path(__file__).resolve().parent.parent


def test_pat09_se_normaliza_a_pat03_sin_mutar_entrada():
    source = [{"cuenta_original": "Utilidades anteriores", "codigo_estandar": "PAT.09"}]

    result = canonicalize_dictionary(source)

    assert result[0]["codigo_estandar"] == "PAT.03"
    assert source[0]["codigo_estandar"] == "PAT.09"
    assert canonical_catalog_code("pat.09") == "PAT.03"


def test_catalogo_ofrece_una_sola_categoria_de_resultados_acumulados():
    catalog = json.loads((BASE_DIR / "catalogo_maestro.json").read_text(encoding="utf-8"))

    options = opciones_clasificacion(catalog)

    assert "PAT.03" in options
    assert "PAT.09" not in options
    assert catalog["PAT.03"]["nombre_estandar"] == "Resultados Acumulados"
    assert catalog["PAT.09"]["codigo_canonico"] == "PAT.03"


def test_catalogo_neon_antiguo_no_reintroduce_nombre_ni_alias_seleccionable():
    catalog = canonicalize_catalog({
        "PAT.03": {"nombre_estandar": "Utilidades Retenidas", "clasificable": True},
        "PAT.09": {"nombre_estandar": "Utilidades Ejercicios Anteriores"},
    })

    assert catalog["PAT.03"]["nombre_estandar"] == "Resultados Acumulados"
    assert catalog["PAT.09"]["clasificable"] is False
    assert catalog["PAT.09"]["codigo_canonico"] == "PAT.03"
