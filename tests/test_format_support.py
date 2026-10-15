from types import SimpleNamespace

from format_support import evaluar_formato


def cert(estado="certificada", metodo="coordinates_8_amounts"):
    return SimpleNamespace(estado=estado, metodo=metodo)


def test_formato_nativo_de_ocho_columnas_certificado_es_soportado():
    resultado = evaluar_formato(cert())

    assert resultado["estado"] == "SOPORTADO"
    assert resultado["id"] == "BALANCE_TRIBUTARIO_8_COLUMNAS_NATIVO"


def test_tabla_nativa_de_ocho_columnas_es_perfil_soportado():
    resultado = evaluar_formato(cert(metodo="native_table_8_columns"))

    assert resultado["estado"] == "SOPORTADO"
    assert resultado["id"] == "BALANCE_TRIBUTARIO_8_COLUMNAS_NATIVO"


def test_texto_nativo_validado_de_ocho_columnas_es_perfil_soportado():
    resultado = evaluar_formato(
        cert(metodo="native_text_8_columns_validated"),
    )

    assert resultado["estado"] == "SOPORTADO"
    assert resultado["id"] == "BALANCE_TRIBUTARIO_8_COLUMNAS_NATIVO"


def test_layout_nativo_lateral_certificado_es_perfil_soportado():
    resultado = evaluar_formato(cert(metodo="native_layout_8_columns"))

    assert resultado["estado"] == "SOPORTADO"
    assert resultado["id"] == "BALANCE_TRIBUTARIO_8_COLUMNAS_NATIVO"


def test_formato_reconocido_pero_con_extraccion_fallida_no_es_soportado():
    resultado = evaluar_formato(cert("fallida", "ocr_coordinates_8_amounts"))

    assert resultado["estado"] == "RECONOCIDO_PENDIENTE_VALIDACION"


def test_balance_clasificado_doble_columna_ocr_es_familia_reconocida():
    resultado = evaluar_formato(cert("parcial", "ocr_classified_two_columns"))

    assert resultado["estado"] == "RECONOCIDO_PENDIENTE_VALIDACION"
    assert resultado["id"] == "BALANCE_CLASIFICADO_DOS_COLUMNAS_OCR"


def test_balance_clasificado_doble_columna_nativo_es_familia_reconocida():
    resultado = evaluar_formato(
        cert("parcial", "native_classified_two_columns"),
    )

    assert resultado["estado"] == "RECONOCIDO_PENDIENTE_VALIDACION"
    assert resultado["id"] == "BALANCE_CLASIFICADO_DOS_COLUMNAS_NATIVO"


def test_metodo_sin_perfil_es_formato_no_reconocido():
    resultado = evaluar_formato(cert(metodo="classified_totals"))

    assert resultado["estado"] == "NO_RECONOCIDO"


def test_contrato_serializado_con_claves_en_ingles_mantiene_el_formato_soportado():
    resultado = evaluar_formato({
        "state": "certificada",
        "method": "coordinates_8_amounts",
    })

    assert resultado["estado"] == "SOPORTADO"
    assert resultado["metodo"] == "coordinates_8_amounts"


def test_contexto_no_balance_tiene_precedencia_sobre_metodo():
    contexto = SimpleNamespace(
        signature=SimpleNamespace(
            document_type=SimpleNamespace(value="ESTADO_RESULTADOS"),
        ),
    )

    resultado = evaluar_formato(cert("parcial"), contexto)

    assert resultado["estado"] == "NO_ES_BALANCE"


def test_balance_certificado_prevalece_sobre_etiqueta_documental_debil():
    """Un estado textual no invalida una tabla de ocho columnas certificada."""
    contexto = SimpleNamespace(
        signature=SimpleNamespace(
            document_type=SimpleNamespace(value="ESTADO_RESULTADOS"),
        ),
    )

    resultado = evaluar_formato(cert(), contexto)

    assert resultado["estado"] == "SOPORTADO"
    assert resultado["id"] == "BALANCE_TRIBUTARIO_8_COLUMNAS_NATIVO"


def test_contexto_otro_sin_texto_nativo_no_degrada_un_balance_reconocido():
    contexto = SimpleNamespace(
        signature=SimpleNamespace(document_type=SimpleNamespace(value="OTRO")),
    )

    resultado = evaluar_formato(cert(), contexto)

    assert resultado["estado"] == "SOPORTADO"
