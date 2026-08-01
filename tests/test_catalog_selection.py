"""Validación del catálogo de la cola de clasificación manual.

Cubre los 4 requisitos de la mejora:
  1. Orden de presentación (Activos, Pasivos, Patrimonio, Ingresos, Costos,
     Gastos, Otros ingresos, Otros egresos) manteniendo el orden interno.
  2. Las cuentas de cálculo no aparecen en la lista de selección.
  3. Las cuentas TOTAL no aparecen en la lista de selección.
  4. El resto del catálogo permanece sin cambios.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_selection import (
    GRUPOS_PRESENTACION,
    es_clasificable,
    grupo_presentacion,
    opciones_clasificacion,
)

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOGO_PATH = BASE_DIR / "catalogo_maestro.json"

# Cuentas de cálculo: deben seguir en el catálogo pero NO ser seleccionables.
CUENTAS_CALCULO = [
    "ER.03",    # Margen Bruto
    "ER.06",    # EBITDA
    "ER.08",    # Resultado Operacional (EBIT)
    "ER.11",    # Utilidad Neta
    "ER.19",    # Resultado Antes de Impuestos
    "PAT.04",   # Resultado del Ejercicio
]


@pytest.fixture
def catalogo() -> dict:
    with open(CATALOGO_PATH, encoding="utf-8") as f:
        return json.load(f)


def _grupos_opciones(catalogo: dict) -> list[str]:
    return [grupo_presentacion(catalogo[c]) for c in opciones_clasificacion(catalogo)]


class TestOrdenPresentacion:
    def test_grupos_en_orden_pedido(self, catalogo):
        grupos = _grupos_opciones(catalogo)
        indices = [GRUPOS_PRESENTACION.index(g) for g in grupos]
        assert indices == sorted(indices), (
            "los grupos deben aparecer en el orden: "
            + ", ".join(GRUPOS_PRESENTACION)
        )

    def test_aparecen_todos_los_grupos(self, catalogo):
        grupos = set(_grupos_opciones(catalogo))
        assert grupos == set(GRUPOS_PRESENTACION)

    def test_orden_interno_del_catalogo_preservado(self, catalogo):
        opciones = opciones_clasificacion(catalogo)
        for grupo in GRUPOS_PRESENTACION:
            en_opciones = [c for c in opciones
                           if grupo_presentacion(catalogo[c]) == grupo]
            en_catalogo = [c for c in catalogo.keys() if c in set(en_opciones)]
            assert en_opciones == en_catalogo, (
                f"el grupo '{grupo}' debe conservar el orden interno del catálogo"
            )

    def test_balance_activos_primero_pasivos_despues(self, catalogo):
        opciones = opciones_clasificacion(catalogo)
        activos = [c for c in opciones if grupo_presentacion(catalogo[c]) == "Activos"]
        pasivos = [c for c in opciones if grupo_presentacion(catalogo[c]) == "Pasivos"]
        assert activos and pasivos
        assert opciones.index(activos[-1]) < opciones.index(pasivos[0])


class TestExclusionCuentasCalculo:
    def test_cuentas_calculo_no_seleccionables(self, catalogo):
        opciones = opciones_clasificacion(catalogo)
        for codigo in CUENTAS_CALCULO:
            assert codigo in catalogo, "la cuenta de cálculo debe seguir en el catálogo"
            assert catalogo[codigo]["clasificable"] is False
            assert codigo not in opciones, f"{codigo} no debe ser seleccionable"

    def test_clasificable_false_excluido_en_catalogo_sintetico(self):
        catalogo = {
            "ER.99": {
                "codigo_estandar": "ER.99",
                "nombre_estandar": "EBIT",
                "categoria": "resultado",
                "clasificable": False,
                "grupo_presentacion": "Gastos",
            },
            "AC.01": {
                "codigo_estandar": "AC.01",
                "nombre_estandar": "Caja y Bancos",
                "categoria": "activo_corriente",
                "clasificable": True,
                "grupo_presentacion": "Activos",
            },
        }
        assert opciones_clasificacion(catalogo) == ["AC.01"]

    def test_entrada_sin_atributo_es_seleccionable(self):
        # categorías creadas por el analista (sin clasificable) siguen siendo
        # seleccionables por defecto.
        entrada = {"codigo_estandar": "AC.99", "nombre_estandar": "Cuenta Nueva"}
        assert es_clasificable(entrada)


class TestExclusionTotales:
    def test_nombre_total_excluido(self):
        for nombre in ["Total Activos", "Total Pasivos", "Total Patrimonio",
                       "Total Ingresos", "Total Costos", "Total Gastos"]:
            entrada = {"codigo_estandar": "TOT.01",
                       "nombre_estandar": nombre,
                       "clasificable": True}
            assert not es_clasificable(entrada), f"{nombre} no debe ser seleccionable"

    def test_total_con_clasificable_false_excluido(self):
        entrada = {"codigo_estandar": "TOT.02",
                   "nombre_estandar": "Total Activos",
                   "clasificable": False}
        assert not es_clasificable(entrada)

    def test_ninguna_cuenta_total_en_opciones_reales(self, catalogo):
        opciones = opciones_clasificacion(catalogo)
        for codigo in opciones:
            nombre = catalogo[codigo]["nombre_estandar"].lower()
            assert not nombre.startswith("total"), f"{codigo} es una cuenta TOTAL"

    def test_total_entrada_con_mayuscula_excluido(self):
        entrada = {"codigo_estandar": "TOT.03",
                   "nombre_estandar": "TOTAL ACTIVOS",
                   "clasificable": True}
        assert not es_clasificable(entrada)


class TestRestoDelCatalogoSinCambios:
    def test_seleccionables_son_catalogo_menos_calculo(self, catalogo):
        opciones = set(opciones_clasificacion(catalogo))
        esperado = set(catalogo.keys()) - set(CUENTAS_CALCULO)
        assert opciones == esperado

    def test_funcion_es_pura_no_muta_catalogo(self, catalogo):
        original = json.loads(json.dumps(catalogo))
        opciones_clasificacion(catalogo)
        opciones_clasificacion(catalogo)
        assert catalogo == original

    def test_cuentas_calculo_siguen_disponibles_para_validacion(self, catalogo):
        for codigo in CUENTAS_CALCULO:
            assert catalogo[codigo]["nombre_estandar"]
            assert "categoria" in catalogo[codigo]

    def test_entradas_seleccionables_conservan_metadatos(self, catalogo):
        for codigo in opciones_clasificacion(catalogo):
            entrada = catalogo[codigo]
            assert entrada["nombre_estandar"]
            assert entrada["categoria"]
            assert entrada["clasificable"] is True


class TestGrupoPresentacion:
    def test_derivacion_desde_categoria(self):
        entrada = {"codigo_estandar": "AC.99", "categoria": "pasivo_corriente"}
        assert grupo_presentacion(entrada) == "Pasivos"

    def test_atributo_explicito_gana_a_categoria(self):
        entrada = {"codigo_estandar": "ER.01",
                   "categoria": "resultado",
                   "grupo_presentacion": "Ingresos"}
        assert grupo_presentacion(entrada) == "Ingresos"

    def test_grupo_desconocido_al_final(self):
        catalogo = {
            "Z.01": {"nombre_estandar": "Rara", "grupo_presentacion": "Zzz",
                     "clasificable": True},
            "AC.01": {"nombre_estandar": "Caja", "categoria": "activo_corriente",
                      "clasificable": True},
        }
        assert opciones_clasificacion(catalogo) == ["AC.01", "Z.01"]

    def test_entrada_no_dict_no_clasificable(self):
        assert not es_clasificable(None)
        assert grupo_presentacion(None) == ""
