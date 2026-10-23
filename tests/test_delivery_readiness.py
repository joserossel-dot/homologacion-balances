from types import SimpleNamespace

import pytest

from delivery_readiness import evaluar_entregabilidad


def certificacion(
    estado="certificada", *, orientacion=True, razones=None,
    columnas_finales_validadas=None, diagnostico="NO_EVALUADO",
    senales_diagnostico=None, reconstrucciones_finales=None,
    reconstruccion_final_revisable=False,
):
    return SimpleNamespace(
        estado=estado,
        metodo="ocr_coordinates_8_amounts",
        orientacion_certificada=orientacion,
        razones=razones or [],
        columnas_finales_validadas=columnas_finales_validadas,
        diagnostico=diagnostico,
        senales_diagnostico=senales_diagnostico or [],
        reconstrucciones_finales=reconstrucciones_finales or [],
        reconstruccion_final_revisable=reconstruccion_final_revisable,
    )


def fila(
    nombre,
    monto,
    codigo,
    *,
    revision=False,
    compatible=True,
    metodo="diccionario_exacto",
    confianza=0.99,
    **adicionales,
):
    return {
        "nombre_original": nombre,
        "monto": monto,
        "codigo_clasificado": codigo,
        "requiere_revision": revision,
        "compatible": compatible,
        "metodo": metodo,
        "confianza": confianza,
        "es_total": False,
        **adicionales,
    }


def formato_soportado():
    return {
        "estado": "SOPORTADO",
        "id": "BALANCE_TRIBUTARIO_8_COLUMNAS_OCR",
        "familia": "Balance tributario de ocho columnas con OCR",
        "metodo": "ocr_coordinates_8_amounts",
        "mensaje": "Formato soportado para la prueba.",
    }


def test_documento_certificado_con_60_por_ciento_es_listo_para_revision():
    resultado = evaluar_entregabilidad(
        [
            fila("Caja", 100, "AC.01"),
            fila("Proveedor", 40, "PC.01", revision=True),
            fila("Capital", 60, "PAT.01", metodo="validacion_humana"),
        ],
        certificacion(),
        {"certificada": False, "cuadra": True, "motivos": ["Hay una sugerencia pendiente"]},
    )

    assert resultado["estado"] == "LISTO_PARA_REVISION_ANALISTA"
    assert resultado["exportacion_revision_permitida"] is True
    assert resultado["exportacion_final_permitida"] is False
    assert resultado["cobertura"]["cuentas"] == {
        "elegibles": 3,
        "automaticas": 1,
        "sugeridas": 1,
        "confirmadas_analista": 1,
        "sin_clasificar": 0,
        "incompatibles": 0,
        "pendientes": 1,
        "automaticas_o_sugeridas": 2,
        "cubiertas_para_revision": 3,
        "porcentaje": 1.0,
    }


def test_cuenta_incompatible_no_suma_a_la_cobertura_sugerida():
    resultado = evaluar_entregabilidad(
        [
            fila("Caja", 100, "AC.01"),
            fila("Obligación en activo", 100, "PC.01", revision=True, compatible=False),
        ],
        certificacion(),
        {"certificada": False, "cuadra": False},
    )

    assert resultado["estado"] == "COBERTURA_INSUFICIENTE"
    assert resultado["cobertura"]["cuentas"]["porcentaje"] == 0.5
    assert resultado["cobertura"]["cuentas"]["incompatibles"] == 1


def test_contrato_acepta_las_claves_del_pipeline_de_certificacion_de_corpus():
    resultado = evaluar_entregabilidad(
        [{
            "name": "Caja", "amount": 100, "code": "AC.01",
            "review": True, "compatible": True,
        }],
        {
            "state": "certificada",
            "method": "ocr_coordinates_8_amounts",
            "orientation_certified": True,
            "reasons": ["Contrato serializado"],
            "diagnosis": "DIFERENCIA_PUNTUAL_EN_CONTROL",
            "diagnostic_signals": ["DIFERENCIA_PUNTUAL_EN_CONTROL"],
        },
        {"certificada": False, "cuadra": True},
    )

    assert resultado["estado"] == "LISTO_PARA_REVISION_ANALISTA"
    assert resultado["cobertura"]["cuentas"]["sugeridas"] == 1
    assert resultado["certificacion_extraccion"]["metodo"] == "ocr_coordinates_8_amounts"
    assert resultado["certificacion_extraccion"]["orientacion_certificada"] is True
    assert resultado["certificacion_extraccion"]["diagnostico"] == "DIFERENCIA_PUNTUAL_EN_CONTROL"
    assert resultado["certificacion_extraccion"]["etiqueta_diagnostico"] == "Diferencia puntual en un control"
    assert resultado["certificacion_extraccion"]["senales_diagnostico"] == [
        "DIFERENCIA_PUNTUAL_EN_CONTROL"
    ]


def test_cuadratura_y_cero_pendientes_habilitan_integracion():
    resultado = evaluar_entregabilidad(
        [
            fila("Caja", 100, "AC.01"),
            fila("Capital", 100, "PAT.01"),
        ],
        certificacion(),
        {"certificada": True, "cuadra": True, "diferencia": 0},
    )

    assert resultado["estado"] == "LISTO_PARA_INTEGRAR"
    assert resultado["exportacion_final_permitida"] is True


def test_cuadratura_certificada_no_habilita_integracion_con_cuenta_pendiente():
    resultado = evaluar_entregabilidad(
        [
            fila("Caja", 100, "AC.01"),
            fila("Proveedor", 100, "PC.01", revision=True),
        ],
        certificacion(),
        {"certificada": True, "cuadra": True, "diferencia": 0},
    )

    assert resultado["estado"] == "LISTO_PARA_REVISION_ANALISTA"
    assert resultado["exportacion_final_permitida"] is False


def test_extraccion_no_certificada_bloquea_aunque_haya_sugerencias():
    resultado = evaluar_entregabilidad(
        [fila("Caja", 100, "AC.01")],
        certificacion("parcial", razones=["Fila reconstruida"]),
        {"certificada": True, "cuadra": True},
    )

    assert resultado["estado"] == "EXTRACCION_NO_VALIDADA"
    assert resultado["exportacion_revision_permitida"] is False
    assert "Fila reconstruida" in resultado["razones"]


def test_extraccion_parcial_con_columnas_finales_validadas_pasa_a_revision():
    resultado = evaluar_entregabilidad(
        [fila("Caja", 100, "AC.01", revision=True)],
        certificacion(
            "parcial",
            razones=["Fila reconstruida"],
            columnas_finales_validadas=True,
        ),
        {"certificada": True, "cuadra": True},
        formato={
            "estado": "RECONOCIDO_PENDIENTE_VALIDACION",
            "id": "BALANCE_TRIBUTARIO_8_COLUMNAS_OCR",
            "familia": "Balance tributario de ocho columnas con OCR",
            "metodo": "ocr_coordinates_8_amounts",
            "mensaje": "Familia reconocida con extracción parcial.",
        },
    )

    assert resultado["estado"] == "LISTO_PARA_REVISION_ANALISTA"
    assert resultado["exportacion_revision_permitida"] is True
    assert resultado["exportacion_final_permitida"] is False
    assert resultado["certificacion_extraccion"]["apta_revision_asistida"] is True


def test_reconstruccion_final_acotada_habilita_solo_revision_de_extraccion():
    resultado = evaluar_entregabilidad(
        [fila("Caja", 100, "AC.01", revision=True)],
        certificacion(
            "parcial",
            razones=["Una cifra final fue reconstruida."],
            reconstrucciones_finales=[{
                "linea": 7, "cuenta": "Caja", "columnas": ["activo"],
                "importe": 100,
            }],
            reconstruccion_final_revisable=True,
        ),
        {"certificada": False, "cuadra": True},
    )

    assert resultado["estado"] == "REVISION_EXTRACCION_REQUERIDA"
    assert resultado["exportacion_revision_permitida"] is True
    assert resultado["exportacion_final_permitida"] is False
    assert resultado["certificacion_extraccion"][
        "reconstruccion_final_revisable"
    ] is True
    assert "cifra(s) final(es) fueron reconstruidas" in " ".join(resultado["razones"])


def test_formato_no_registrado_bloquea_aun_con_extraccion_certificada():
    resultado = evaluar_entregabilidad(
        [fila("Caja", 100, "AC.01")],
        certificacion(),
        {"certificada": True, "cuadra": True},
        formato={
            "estado": "NO_RECONOCIDO",
            "id": "",
            "familia": "",
            "metodo": "nuevo_extractor",
            "mensaje": "No existe un extractor certificado registrado para este formato.",
        },
    )

    assert resultado["estado"] == "FORMATO_NO_SOPORTADO"
    assert resultado["exportacion_revision_permitida"] is False


def test_orientacion_ocr_sin_evidencia_es_lectura_no_respaldada():
    resultado = evaluar_entregabilidad(
        [fila("Caja", 100, "AC.01")],
        certificacion(orientacion=False),
        {"certificada": True, "cuadra": True},
    )

    assert resultado["estado"] == "LECTURA_NO_RESPALDADA"


def test_contrato_explica_estado_resultados_separado_sin_duplicar_patrimonio():
    resultado = evaluar_entregabilidad(
        [fila("Caja", 100, "AC.01")],
        certificacion("parcial"),
        {
            "certificada": False,
            "cuadra": True,
            "resultado_derivado_incorporado": False,
        },
    )

    assert resultado["cuadratura_homologada"]["resultado_derivado_incorporado"] is False
    assert any("no se sumó por segunda vez" in razon for razon in resultado["razones"])


def test_contrato_serializa_el_cierre_fuente_usado_en_cuadratura():
    resultado = evaluar_entregabilidad(
        [fila("Caja", 100, "AC.01")],
        certificacion("certificada"),
        {
            "certificada": False,
            "cuadra": True,
            "resultado_final_fuente_incorporado": True,
            "resultado_final_fuente": 42,
        },
    )

    assert resultado["cuadratura_homologada"]["resultado_final_fuente_incorporado"] is True
    assert resultado["cuadratura_homologada"]["resultado_final_fuente"] == 42


@pytest.mark.parametrize("threshold", [0, -0.1, 1.1])
def test_umbral_invalido_falla_explicito(threshold):
    with pytest.raises(ValueError, match="umbral_revision"):
        evaluar_entregabilidad([], certificacion(), umbral_revision=threshold)


def test_aceptacion_comercial_cuenta_solo_sugerencia_algoritmica_con_evidencia():
    resultado = evaluar_entregabilidad(
        [
            fila("Caja", 100, "AC.01"),
            fila(
                "Obligación bancaria", 100, "PC.02", revision=True,
                metodo="contextual_accounting_suggestion", confianza=0.84,
                reason="Regla contextual compatible con pasivo.",
            ),
        ],
        certificacion(),
        {"certificada": False, "cuadra": True},
        formato=formato_soportado(),
    )

    comercial = resultado["aceptacion_comercial"]
    assert comercial["estado"] == "CUMPLE_CRITERIO_COMERCIAL_PARA_REVISION"
    assert comercial["cumple_umbral"] is True
    assert comercial["cobertura"]["cuentas"]["automaticas_estrictas"] == 1
    assert comercial["cobertura"]["cuentas"]["sugeridas_automatizadas"] == 1
    assert comercial["cobertura"]["cuentas"]["porcentaje"] == 1.0


def test_aceptacion_comercial_excluye_sugerencia_de_metodo_desconocido():
    resultado = evaluar_entregabilidad(
        [
            fila(
                "Propuesta nueva", 100, "PC.02", revision=True,
                metodo="modelo_experimental_no_auditado", confianza=0.99,
                reason="El modelo generó esta propuesta.",
            ),
        ],
        certificacion(),
        {"certificada": False, "cuadra": True},
        formato=formato_soportado(),
    )

    comercial = resultado["aceptacion_comercial"]
    cuentas = comercial["cobertura"]["cuentas"]
    assert cuentas["sugerencias_metodo_no_admitido"] == 1
    assert cuentas["sugeridas_automatizadas"] == 0
    assert cuentas["automaticas_o_sugeridas"] == 0
    assert comercial["estado"] == "NO_APTO_POR_COBERTURA_COMERCIAL"


def test_aceptacion_comercial_excluye_sugerencia_sin_traza_no_vacia():
    resultado = evaluar_entregabilidad(
        [
            fila(
                "Propuesta sin respaldo", 100, "PC.02", revision=True,
                metodo="contextual_accounting_suggestion", confianza=0.99,
                evidencia=" ", regla="", reason="", special_rule=None,
            ),
        ],
        certificacion(),
        {"certificada": False, "cuadra": True},
        formato=formato_soportado(),
    )

    cuentas = resultado["aceptacion_comercial"]["cobertura"]["cuentas"]
    assert cuentas["sugerencias_sin_evidencia_trazable"] == 1
    assert cuentas["sugeridas_automatizadas"] == 0


@pytest.mark.parametrize("confianza", [float("nan"), float("inf"), float("-inf")])
def test_aceptacion_comercial_excluye_sugerencia_con_confianza_no_finita(confianza):
    resultado = evaluar_entregabilidad(
        [
            fila(
                "Propuesta con confianza inválida", 100, "PC.02", revision=True,
                metodo="contextual_accounting_suggestion", confianza=confianza,
                reason="Regla contextual compatible con pasivo.",
            ),
        ],
        certificacion(),
        {"certificada": False, "cuadra": True},
        formato=formato_soportado(),
    )

    cuentas = resultado["aceptacion_comercial"]["cobertura"]["cuentas"]
    assert cuentas["sugerencias_confianza_insuficiente"] == 1
    assert cuentas["sugeridas_automatizadas"] == 0


def test_aceptacion_comercial_no_infla_decisiones_humanas_lote_ni_propagacion():
    resultado = evaluar_entregabilidad(
        [
            fila("Caja", 100, "AC.01"),
            fila("Banco", 100, "AC.01"),
            fila(
                "Capital", 100, "PAT.01", metodo="validacion_humana",
                confianza=1.0,
            ),
            fila(
                "Proveedor", 100, "PC.01", metodo="validacion_humana_lote",
                confianza=1.0,
            ),
            fila(
                "Honorarios", 100, "PC.05",
                metodo="validacion_humana_propagada", confianza=1.0,
                propagacion_origen_archivo="origen-del-lote.pdf",
            ),
        ],
        certificacion(),
        {"certificada": True, "cuadra": True},
        formato=formato_soportado(),
    )

    comercial = resultado["aceptacion_comercial"]
    cuentas = comercial["cobertura"]["cuentas"]
    assert resultado["estado"] == "LISTO_PARA_INTEGRAR"
    assert comercial["estado"] == "NO_APTO_POR_COBERTURA_COMERCIAL"
    assert cuentas["automaticas_estrictas"] == 2
    assert cuentas["sugeridas_automatizadas"] == 0
    assert cuentas["decisiones_humanas_individuales"] == 1
    assert cuentas["decisiones_humanas_lote"] == 1
    assert cuentas["asistencia_derivada_humano_lote"] == 1
    assert cuentas["porcentaje"] == 0.4


def test_aceptacion_comercial_expone_propagacion_historica_confirmada_aparte():
    resultado = evaluar_entregabilidad(
        [
            fila(
                "Gasto histórico", 100, "ER.04",
                metodo="dictionary_exact", confianza=1.0,
                propagacion_confirmada_historial=True,
            ),
        ],
        certificacion(),
        {"certificada": True, "cuadra": True},
        formato=formato_soportado(),
    )

    cuentas = resultado["aceptacion_comercial"]["cobertura"]["cuentas"]
    assert cuentas["asistencia_derivada_humano_historial_confirmado"] == 1
    assert cuentas["automaticas_o_sugeridas"] == 0
    assert resultado["aceptacion_comercial"]["cumple_umbral"] is False


def test_aceptacion_comercial_mantiene_origin_fallback_fuera_del_numerador():
    resultado = evaluar_entregabilidad(
        [
            fila("Caja", 100, "AC.01"),
            fila(
                "Cuenta sin homologar", 100, "AC.08", revision=True,
                metodo="origin_fallback", confianza=0.99,
            ),
        ],
        certificacion(),
        {"certificada": False, "cuadra": True},
        formato=formato_soportado(),
    )

    comercial = resultado["aceptacion_comercial"]
    cuentas = comercial["cobertura"]["cuentas"]
    assert cuentas["origin_fallback_en_revision"] == 1
    assert cuentas["sugeridas_automatizadas"] == 0
    assert cuentas["porcentaje"] == 0.5
    assert comercial["estado"] == "NO_APTO_POR_COBERTURA_COMERCIAL"


def test_aceptacion_comercial_no_sustituye_gate_de_cuadratura():
    resultado = evaluar_entregabilidad(
        [fila("Caja", 100, "AC.01"), fila("Banco", 100, "AC.01")],
        certificacion(),
        {"certificada": False, "cuadra": False},
        formato=formato_soportado(),
    )

    comercial = resultado["aceptacion_comercial"]
    assert comercial["cumple_umbral"] is True
    assert comercial["estado"] == "NO_APTO_POR_GATES_TECNICOS"
    assert comercial["gates_tecnicos"]["cuadratura_cuadra"] is False


def test_aceptacion_comercial_permite_configurar_umbral_sin_contar_humanas():
    resultado = evaluar_entregabilidad(
        [
            fila("Caja", 100, "AC.01"),
            fila("Banco", 100, "AC.01"),
            fila(
                "Capital", 100, "PAT.01", metodo="validacion_humana",
                confianza=1.0,
            ),
        ],
        certificacion(),
        {"certificada": True, "cuadra": True},
        formato=formato_soportado(),
        umbral_cobertura_comercial=0.70,
    )

    comercial = resultado["aceptacion_comercial"]
    assert comercial["umbral_cobertura"] == 0.70
    assert comercial["cobertura"]["cuentas"]["brecha_cuentas"] == 1
    assert comercial["estado"] == "NO_APTO_POR_COBERTURA_COMERCIAL"


@pytest.mark.parametrize("threshold", [0, -0.1, 1.1])
def test_umbral_comercial_invalido_falla_explicito(threshold):
    with pytest.raises(ValueError, match="umbral_cobertura"):
        evaluar_entregabilidad(
            [fila("Caja", 100, "AC.01")],
            certificacion(),
            {"certificada": True, "cuadra": True},
            formato=formato_soportado(),
            umbral_cobertura_comercial=threshold,
        )
