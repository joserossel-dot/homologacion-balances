import pytest
import pandas as pd
from datetime import date
import app_validacion
from extractor_metadata import extraer_metadata, MetadataEmpresa, _es_ruido_empresa
from parser_universal import detectar_años_y_monedas


def test_extractor_filtra_ruido_erp_en_razon_social():
    lineas = [
        "KAME ONE Balance General",
        "EMPRESA: INVERSIONES SANTA ELENA SPA",
        "RUT: 76.123.456-7",
        "PERIODO: 01/01/2023 AL 31/12/2023",
    ]
    meta = extraer_metadata(lineas)
    assert meta.razon_social == "Inversiones Santa Elena Spa"
    assert meta.rut == "76.123.456-7"
    assert meta.periodo_desde == "01/01/2023"
    assert meta.periodo_hasta == "31/12/2023"
    assert meta.anio_cierre == 2023
    assert meta.periodos_detectados == ("2023",)


def test_extractor_sin_fecha_no_inventa_2026():
    lineas = [
        "SOCIEDAD DE SERVICIOS MEDICOS LIMITADA",
        "RUT: 77.890.123-4",
        "BALANCE GENERAL",
        "CUENTA                             SALDO",
        "1101 BANCO SANTANDER               500.000",
    ]
    meta = extraer_metadata(lineas)
    assert meta.razon_social == "Sociedad De Servicios Medicos Limitada"
    assert meta.rut == "77.890.123-4"
    assert meta.periodo_desde is None
    assert meta.periodo_hasta is None
    assert meta.anio_cierre is None
    assert meta.periodos_detectados == ()


def test_valores_periodo_metadata_sin_fecha_retorna_none_para_anio():
    meta = MetadataEmpresa()
    mes, anio, meses = app_validacion._valores_periodo_metadata(meta)
    assert mes == "Diciembre"
    assert anio is None
    assert meses == 12


def test_detectar_periodos_comparativos_sin_fallback_retorna_vacio():
    lineas = [
        "EMPRESA DE PRUEBA SPA",
        "RUT 76.111.222-3",
        "LISTADO DE SALDOS CONTABLES",
    ]
    periodos = app_validacion._detectar_periodos_comparativos(lineas, anio_fallback=None)
    assert periodos == ()


def test_extractor_detecta_periodo_textual_chileno():
    lineas = [
        "AGRÍCOLA EL ROBLE SPA",
        "RUT: 76.543.210-K",
        "BALANCE TRIBUTARIO",
        "COMPRENDIDO 01 DE ENERO 2022 AL 31 DE DICIEMBRE 2022",
    ]
    meta = extraer_metadata(lineas)
    assert meta.periodo_desde == "01/01/2022"
    assert meta.periodo_hasta == "31/12/2022"
    assert meta.anio_cierre == 2022
    assert meta.periodos_detectados == ("2022",)


def test_es_ruido_empresa_identifica_software_y_cabeceras():
    assert _es_ruido_empresa("KAME ONE Balance General") is True
    assert _es_ruido_empresa("SOFTLAND ERP") is True
    assert _es_ruido_empresa("DEFONTANA") is True
    assert _es_ruido_empresa("BALANCE DE OCHO COLUMNAS") is True
    assert _es_ruido_empresa("PÁGINA 1 DE 5") is True
    assert _es_ruido_empresa("AGRÍCOLA VALLE CENTRAL SPA") is False


def test_extractor_detecta_acumulado_mes_anio_y_empresa_corporativa():
    lineas = [
        "Do E Na",
        "INVERSIONES TORABUS LIMITADA",
        "Sec de Inversion y Rentistas de Capitales Mobiliarios",
        "1 Sur Nº 690 of. 1001",
        "Talca",
        "Talca",
        "76.013.372-8",
        "Balance Tributario",
        "Acumulado mes/año Diciembre/2023",
        "Moneda : Peso Chileno",
    ]
    meta = extraer_metadata(lineas)
    assert meta.razon_social == "Inversiones Torabus Limitada"
    assert meta.rut == "76.013.372-8"
    assert meta.mes_cierre == "Diciembre"
    assert meta.anio_cierre == 2023
    assert meta.periodos_detectados == ("2023",)
