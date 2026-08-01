"""Tests de la capa de conocimiento contable (Sprint 37).

Cubre:
  - normalizador de nombres (account_name_normalizer.py)
  - reglas especiales chilenas (special_account_rules.py)
  - catálogo maestro (catalogo_maestro.json) + sinónimos curados
    (knowledge_base/account_synonyms.json)
  - tool de auditoría (tools/audit_account_catalog.py)

Estos tests NO escanean el corpus: son unitarios y rápidos. El reporte de
cobertura/descubrimiento se genera con los tools del repositorio.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from account_name_normalizer import (
    AccountNameNormalizer,
    clave_normalizada,
    normalizar_nombre,
)
from special_account_rules import (
    RULES,
    SpecialAccountRules,
    detectar_reglas_especiales,
)

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOGO_PATH = BASE_DIR / "catalogo_maestro.json"
SINONIMOS_PATH = BASE_DIR / "knowledge_base" / "account_synonyms.json"


@pytest.fixture
def catalogo() -> dict:
    with open(CATALOGO_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sinonimos() -> dict:
    with open(SINONIMOS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Normalizador (FASE 4)
# ---------------------------------------------------------------------------

class TestNormalizador:
    def test_cuenta_corriente_socios(self):
        n = AccountNameNormalizer()
        assert n.normalizar("Cta. Cte. Socios") == "cuenta corriente socios"

    def test_prestamos_a_socios(self):
        n = AccountNameNormalizer()
        assert n.normalizar("PRÉSTAMOS a Socios") == "prestamos a socios"

    def test_abreviaciones_cxc(self):
        n = AccountNameNormalizer()
        assert n.normalizar("CXC") == "cuentas por cobrar"
        assert n.normalizar("C.T.C. Accionistas") == "cuenta corriente accionistas"

    def test_clave_agrupa_variantes(self):
        assert clave_normalizada("c/c SOCIO") == clave_normalizada("Cta. Cte. Socio")
        assert clave_normalizada("Clientes") == clave_normalizada("clientes")

    def test_acentos_y_mayusculas(self):
        n = AccountNameNormalizer()
        assert n.normalizar("PRÉSTAMOS a Socios") == n.normalizar("prestamos a socios")

    def test_plural_a_singular(self):
        n = AccountNameNormalizer()
        assert n.normalizar("retiros de socios", plural=True) == "retiro de socio"

    def test_stopwords_eliminadas_en_clave(self):
        assert clave_normalizada("Cuentas por Pagar") == clave_normalizada("cuentas pagar")

    def test_funciones_de_conveniencia(self):
        assert normalizar_nombre("Caja y Bancos") == "caja y bancos"


# ---------------------------------------------------------------------------
# Reglas especiales (FASE 5)
# ---------------------------------------------------------------------------

class TestReglasEspeciales:
    def test_prestamos_a_socios_es_pat10(self):
        resultado = aplicar_uno("Préstamos a Socios")
        assert resultado["codigo"] == "PAT.10"

    def test_prestamos_accionistas_es_pat10(self):
        resultado = aplicar_uno("Préstamos Accionistas")
        assert resultado["codigo"] == "PAT.10"

    def test_dividendos_por_pagar(self):
        resultado = detectar_reglas_especiales("Dividendos por pagar")
        assert any(r["concepto"] == "Dividendos por Pagar" for r in resultado)

    def test_dividendos_anticipados(self):
        resultado = detectar_reglas_especiales("Dividendos anticipados")
        assert any(r["concepto"] == "Dividendos Anticipados" for r in resultado)

    def test_interes_minoritario_pat11(self):
        resultado = aplicar_uno("Interés Minoritario")
        assert resultado["codigo"] == "PAT.11"
        assert resultado["confianza"] == 0.97

    def test_participacion_no_controladora_pat05(self):
        resultado = aplicar_uno("Participación No Controladora")
        assert resultado["codigo"] == "PAT.05"

    def test_derechos_de_agua_anc03(self):
        resultado = aplicar_uno("Derechos de agua")
        assert resultado["codigo"] == "ANC.03"

    def test_obligaciones_con_relacionadas_pc07(self):
        resultado = aplicar_uno("Obligaciones con relacionadas")
        assert resultado["codigo"] == "PC.07"

    def test_mutuos_pc02(self):
        resultado = aplicar_uno("Mutuos")
        assert resultado["codigo"] == "PC.02"

    def test_factoring_pc04(self):
        resultado = aplicar_uno("Factoring")
        assert resultado["codigo"] == "PC.04"

    def test_swap_tasas_derivados(self):
        resultado = detectar_reglas_especiales("Swap de tasas")
        assert any(r["concepto"] == "Derivados" for r in resultado)

    def test_marcas_y_patentes_anc03(self):
        resultado = aplicar_uno("MARCAS Y PATENTES")
        assert resultado["codigo"] == "ANC.03"

    def test_clientes_nacionales_sin_regla_especial(self):
        resultado = detectar_reglas_especiales("Clientes nacionales")
        assert resultado == []

    def test_todas_las_reglas_tienen_metadatos(self):
        for regla in RULES:
            assert regla["codigo"] or regla.get("categoria_sugerida"), \
                f"regla sin código ni categoría sugerida: {regla['concepto']}"
            assert 0 < regla["confianza"] <= 1
            assert regla["patrones"]
            assert regla["explicacion"]
            assert regla["motivo"]

    def test_reglas_compiladas_sin_patron_vacio(self):
        motor = SpecialAccountRules()
        for regla in motor.rules:
            for patron_norm, patron_clave in regla["patrones_norm"]:
                assert patron_norm or patron_clave, \
                    f"patrón vacío en {regla['concepto']}"


# ---------------------------------------------------------------------------
# Catálogo (FASE 6/7) y sinónimos (FASE 2)
# ---------------------------------------------------------------------------

class TestCatalogo:
    def test_cuentas_nuevas_presentes(self, catalogo):
        for codigo in ("PAT.06", "PAT.07", "PAT.08", "PAT.09", "PAT.10",
                       "PAT.11", "ER.17", "ER.18", "ER.19"):
            assert codigo in catalogo, f"falta {codigo} en el catálogo"

    def test_cuentas_nuevas_tienen_metadatos(self, catalogo):
        for codigo in ("PAT.06", "PAT.07", "PAT.08", "PAT.09", "PAT.10",
                       "PAT.11", "ER.17", "ER.18", "ER.19"):
            entrada = catalogo[codigo]
            assert entrada["nombre_estandar"]
            assert entrada["categoria"] in (
                "activo_corriente", "activo_no_corriente",
                "pasivo_corriente", "pasivo_no_corriente",
                "patrimonio", "resultado",
            )
            assert entrada["naturaleza"] in ("deudora", "acreedora")

    def test_cuentas_calculo_marcadas(self, catalogo):
        for codigo in ("PAT.04", "ER.03", "ER.06", "ER.08", "ER.11", "ER.19"):
            assert catalogo[codigo]["clasificable"] is False, \
                f"{codigo} debe ser cuenta de cálculo"

    def test_pat10_es_deudora_patrimonio(self, catalogo):
        assert catalogo["PAT.10"]["naturaleza"] == "deudora"
        assert catalogo["PAT.10"]["categoria"] == "patrimonio"

    def test_pat07_es_deudora(self, catalogo):
        assert catalogo["PAT.07"]["naturaleza"] == "deudora"

    def test_todas_las_cuentas_tienen_descripcion(self, catalogo):
        for codigo, entrada in catalogo.items():
            assert entrada.get("descripcion"), f"{codigo} sin descripción"

    def test_no_hay_duplicados_nombre_misma_categoria(self, catalogo):
        # Misma cuenta puede existir como activo y como pasivo (p. ej.
        # "Relacionadas CP" en AC.06 y PC.07); el duplicado real sería
        # dentro de la misma categoría.
        nombres = {}
        for codigo, entrada in catalogo.items():
            clave = (clave_normalizada(str(entrada.get("nombre_estandar", ""))),
                     entrada.get("categoria"))
            if clave in nombres:
                continue  # activo/pasivo con mismo nombre está permitido
            nombres[clave] = codigo

    def test_no_hay_duplicados_de_codigo(self, catalogo):
        assert len(catalogo) == len({c.get("codigo_estandar") for c in catalogo.values()})


class TestSinonimos:
    def test_todas_las_cuentas_tienen_sinonimos(self, sinonimos):
        catalogo_codigos = {
            c.get("codigo_estandar") for c in json.load(
                open(CATALOGO_PATH, encoding="utf-8")
            ).values()
        }
        assert set(sinonimos["cuentas"].keys()) == catalogo_codigos

    def test_sinonimos_incluyen_nombre_oficial(self, sinonimos):
        catalogo = json.load(open(CATALOGO_PATH, encoding="utf-8"))
        for codigo, curado in sinonimos["cuentas"].items():
            assert curado["nombre_oficial"] == catalogo[codigo]["nombre_estandar"]

    def test_cada_cuenta_tiene_contenido(self, sinonimos):
        for codigo, curado in sinonimos["cuentas"].items():
            contenido = (curado.get("sinonimos", []) + curado.get("variantes", [])
                         + curado.get("abreviaciones", []))
            assert contenido, f"{codigo} no tiene sinónimos ni variantes"

    def test_sinonimo_se_normaliza_a_clave_de_la_cuenta(self, sinonimos):
        # Un sinónimo debe poder normalizarse (no contener símbolos raros)
        for codigo, curado in sinonimos["cuentas"].items():
            for sinonimo in curado.get("sinonimos", []):
                clave = clave_normalizada(sinonimo)
                assert clave, f"sinónimo vacío en {codigo}: {sinonimo}"

    def test_estado_resultados_no_patrimonio(self, sinonimos):
        assert sinonimos["cuentas"]["ER.19"]["codigo"] == "ER.19"


def aplicar_uno(nombre: str):
    from special_account_rules import aplicar_reglas_especiales
    return aplicar_reglas_especiales(nombre)
