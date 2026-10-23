"""Contrato de entrega para balances homologados.

El parser, el clasificador y la cuadratura producen señales distintas. Este
módulo las convierte en una decisión única y serializable para el cliente:

* ``NO_LEGIBLE``: no se encontraron cuentas utilizables en el documento.
* ``LECTURA_NO_RESPALDADA``: se detectaron cuentas, pero la orientación OCR no
  tiene evidencia suficiente para confiar en la lectura.
* ``EXTRACCION_NO_VALIDADA``: se leyeron datos, pero no pasan los controles
  independientes del formato de origen.
* ``REVISION_EXTRACCION_REQUERIDA``: los controles fuente concilian, pero una
  fracción acotada de importes finales fue reconstruida. Sólo se autoriza un
  paquete de revisión marcado para cotejo contra el original.
* ``FORMATO_NO_SOPORTADO``: hay lectura, pero el extractor no pertenece a una
  familia que el producto pueda declarar soportada.
* ``COBERTURA_INSUFICIENTE``: la extracción es válida, pero no alcanza el
  umbral para que un analista reciba una revisión corta.
* ``LISTO_PARA_REVISION_ANALISTA``: la extracción es válida y al menos el
  porcentaje configurado de las cuentas tiene una clasificación automática,
  sugerida con evidencia o ya confirmada por un analista. También puede
  habilitarse cuando las columnas contables finales fueron validadas pero
  existen datos auxiliares reconstruidos, siempre sólo para revisión humana.
* ``LISTO_PARA_INTEGRAR``: no quedan decisiones pendientes y la cuadratura
  homologada está certificada.

No modifica cuentas, montos ni decisiones. Es deliberadamente una capa de
lectura para que la misma decisión pueda aparecer en la interfaz, Excel y
JSON. La aceptación comercial se informa en un bloque separado: no cuenta una
confirmación humana como cobertura automática o sugerida.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from typing import Any


SCHEMA_VERSION = "1.1"
DEFAULT_REVIEW_COVERAGE = 0.60
# Este umbral responde a una pregunta distinta de ``umbral_revision``: mide
# cuánto del documento puede llegar al analista como resultado automático o
# propuesta algorítmica con evidencia. No incorpora decisiones humanas ya
# tomadas, ni siquiera si fueron propagadas dentro del mismo lote.
DEFAULT_COMMERCIAL_ASSISTED_COVERAGE = 0.60
DEFAULT_COMMERCIAL_SUGGESTION_CONFIDENCE = 0.80

# Sólo estos métodos tienen reglas de negocio acotadas y trazables que pueden
# presentarse como sugerencia comercial. La lista es deliberadamente cerrada:
# un método nuevo debe ser auditado e incorporado explícitamente antes de
# aumentar la cobertura. Los métodos automáticos sin revisión conservan su
# criterio técnico existente; esta allowlist aplica únicamente a propuestas
# que todavía requieren validación humana.
METODOS_SUGERENCIA_COMERCIAL_ADMITIDOS = frozenset({
    "contextual_accounting_suggestion",
    "contextual_credit_balance_depreciation",
    "current_result_year",
    "dictionary_exact_contra_pasivo",
    "dictionary_fuzzy",
    "regex_contextual",
})

ESTADOS = {
    "NO_LEGIBLE": "No legible",
    "LECTURA_NO_RESPALDADA": "Lectura no respaldada",
    "EXTRACCION_NO_VALIDADA": "Extracción no validada",
    "REVISION_EXTRACCION_REQUERIDA": "Revisión de extracción requerida",
    "FORMATO_NO_SOPORTADO": "Formato no soportado",
    "COBERTURA_INSUFICIENTE": "Cobertura insuficiente para revisión asistida",
    "LISTO_PARA_REVISION_ANALISTA": "Listo para revisión analista",
    "LISTO_PARA_INTEGRAR": "Listo para integrar",
}

# Los diagnósticos describen el control observado, no adjudican la causa al
# PDF. Por ejemplo, ``SUBTOTAL_NO_DETECTADO`` puede significar que el subtotal
# no existe o que OCR no logró leerlo. Esta etiqueta permite a la interfaz y a
# una integración distinguir esos casos sin ocultar la incertidumbre.
ETIQUETAS_DIAGNOSTICO = {
    "NO_EVALUADO": "Sin diagnóstico de extracción",
    "SIN_FILAS_CONTABLES": "No se detectaron filas contables",
    "SUBTOTAL_NO_DETECTADO": "No se detectó subtotal de ocho columnas",
    "INCONSISTENCIAS_MASIVAS_DE_FILA": "Inconsistencias masivas de fila",
    "FILAS_INCONSISTENTES": "Filas con identidades inconsistentes",
    "DIFERENCIA_PUNTUAL_EN_CONTROL": "Diferencia puntual en un control",
    "CONTROLES_NO_CONCILIAN": "Los controles no concilian",
    "FILA_FINAL_NO_CUADRADA": "La fila final no está cuadrada",
    "FILA_FINAL_INCOMPLETA": "La fila final está incompleta",
    "ECUACION_SUBTOTAL_NO_CONCILIA": "La ecuación del subtotal no concilia",
    "PUENTE_RESULTADO_NO_CONCILIA": "El puente de resultado no concilia",
    "CONTROLES_VALIDOS_CON_REVISION": "Controles válidos con revisión pendiente",
    "CONTROLES_VALIDADOS": "Controles validados",
    "TOTALES_FINALES_NO_DETECTADOS": "No se detectaron ambos totales finales",
    "SUBTOTALES_SECCION_NO_CONCILIAN": "Los subtotales de sección no concilian",
    "SUBTOTAL_IMPRESO_NO_VERIFICABLE": "Un subtotal impreso no se pudo verificar",
    "ECUACION_FINAL_NO_CONCILIA": "La ecuación final no concilia",
    "ECUACION_FINAL_VALIDA_CON_REVISION": "Ecuación final válida con revisión pendiente",
}


def _valor(objeto: Any, nombre: str, defecto: Any = None) -> Any:
    if isinstance(objeto, Mapping):
        return objeto.get(nombre, defecto)
    return getattr(objeto, nombre, defecto)


def _primer_atributo(
    objeto: Any, *nombres: str, defecto: Any = None,
) -> Any:
    """Lee el primer atributo presente, incluidos contratos serializados."""
    for nombre in nombres:
        valor = _valor(objeto, nombre, None)
        if valor is not None:
            return valor
    return defecto


def _lista(valor: Any) -> list[Any]:
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor]
    try:
        return list(valor)
    except TypeError:
        return [valor]


def _primer_valor(fila: Mapping[str, Any], *nombres: str) -> Any:
    for nombre in nombres:
        valor = fila.get(nombre)
        if valor is not None:
            return valor
    return None


def _importe(fila: Mapping[str, Any]) -> float | None:
    valor = _primer_valor(fila, "monto", "classification_amount", "amount")
    try:
        importe = float(valor)
    except (TypeError, ValueError):
        return None
    return importe if math.isfinite(importe) else None


def _codigo(fila: Mapping[str, Any]) -> str:
    valor = _primer_valor(
        fila, "codigo_clasificado", "final_code", "standard_code", "code",
    )
    return str(valor or "").strip()


def _requiere_revision(fila: Mapping[str, Any]) -> bool:
    return bool(
        _primer_valor(fila, "requiere_revision", "review_required", "review")
    )


def _metodo(fila: Mapping[str, Any]) -> str:
    return str(fila.get("metodo") or fila.get("method") or "").strip().lower()


def _es_decision_analista(fila: Mapping[str, Any]) -> bool:
    metodo = _metodo(fila)
    return any(token in metodo for token in ("validacion_humana", "manual", "analista"))


def _es_verdadero(valor: Any) -> bool:
    """Interpreta banderas serializadas sin aceptar ``\"false\"`` como verdad."""
    if isinstance(valor, str):
        return valor.strip().lower() in {"1", "true", "si", "sí", "yes"}
    return bool(valor)


def _confianza(fila: Mapping[str, Any]) -> float | None:
    valor = _primer_valor(fila, "confianza", "confidence")
    try:
        confianza = float(valor)
    except (TypeError, ValueError):
        return None
    return confianza if math.isfinite(confianza) else None


def _campo_traza_sugerencia(fila: Mapping[str, Any]) -> str | None:
    """Devuelve el campo de evidencia o regla no vacío de una sugerencia.

    El pipeline actual serializa su justificación como ``reason`` y, cuando
    corresponde, una regla especial como ``special_rule``. Se aceptan además
    los nombres españoles e ingleses de esos campos para contratos ya
    serializados. No se aceptan objetos ni valores numéricos: una sugerencia
    comercial debe dejar una explicación legible y auditable.
    """
    for campo in (
        "evidencia",
        "evidence",
        "regla",
        "rule",
        "razon",
        "reason",
        "special_rule",
    ):
        valor = fila.get(campo)
        if isinstance(valor, str) and valor.strip():
            return campo
    return None


def _es_propagacion(fila: Mapping[str, Any]) -> bool:
    metodo = _metodo(fila)
    origen = _primer_valor(
        fila,
        "propagacion_origen_archivo",
        "propagation_source_file",
        "propagation_source",
    )
    return (
        "propag" in metodo
        or bool(str(origen or "").strip())
        or _propagacion_historica_confirmada(fila)
    )


def _propagacion_historica_confirmada(fila: Mapping[str, Any]) -> bool:
    """Exige una bandera explícita antes de llamar histórica a una propagación."""
    return _es_verdadero(_primer_valor(
        fila,
        "propagacion_confirmada_historial",
        "propagated_from_confirmed_history",
        "historical_propagation_confirmed",
    ))


def _categoria_cobertura_comercial(
    fila: Mapping[str, Any],
    codigo: str,
    compatible: bool,
    *,
    umbral_confianza_sugerencia: float,
) -> str:
    """Clasifica una fila para la métrica comercial, sin modificarla.

    La cobertura comercial es deliberadamente más estricta que la cobertura
    usada para organizar la revisión. Una confirmación humana, por lote o
    propagada, puede ser útil al analista, pero no prueba automatización del
    documento que se está midiendo.
    """
    if codigo == "__EXCLUIR__":
        return "excluidas"
    if not codigo:
        return "sin_clasificar"
    if not compatible:
        return "incompatibles"

    metodo = _metodo(fila)
    if _es_propagacion(fila):
        if _propagacion_historica_confirmada(fila):
            return "asistencia_derivada_humano_historial_confirmado"
        origen = _primer_valor(
            fila,
            "propagacion_origen_archivo",
            "propagation_source_file",
            "propagation_source",
        )
        if str(origen or "").strip():
            return "asistencia_derivada_humano_lote"
        return "propagacion_sin_traza_confirmada"

    if _es_decision_analista(fila):
        if "lote" in metodo or "batch" in metodo:
            return "decisiones_humanas_lote"
        return "decisiones_humanas_individuales"

    # ``origin_fallback`` es una categoría residual desde la columna física.
    # Aunque tenga código compatible, no se presenta como sugerencia que ayude
    # al objetivo comercial: su propia regla exige revisión contable.
    if metodo == "origin_fallback":
        return "origin_fallback_en_revision"

    if not _requiere_revision(fila):
        return "automaticas_estrictas"

    if metodo not in METODOS_SUGERENCIA_COMERCIAL_ADMITIDOS:
        return "sugerencias_metodo_no_admitido"

    if _campo_traza_sugerencia(fila) is None:
        return "sugerencias_sin_evidencia_trazable"

    confianza = _confianza(fila)
    if confianza is None or confianza < umbral_confianza_sugerencia:
        return "sugerencias_confianza_insuficiente"
    return "sugeridas_automatizadas"


def _es_relevante(fila: Mapping[str, Any]) -> tuple[bool, float]:
    if bool(fila.get("es_total", False)):
        return False, 0.0
    importe = _importe(fila)
    if importe is None or importe == 0:
        return False, 0.0
    return True, abs(importe)


def _es_compatible(
    fila: Mapping[str, Any],
    codigo: str,
    compatibilidad: Callable[[Mapping[str, Any]], bool] | None,
) -> bool:
    if not codigo or codigo == "__EXCLUIR__":
        return False
    if compatibilidad is not None:
        try:
            return bool(compatibilidad(fila))
        except Exception:  # La entrega nunca debe ocultar un fallo de validación.
            return False
    return fila.get("compatible") is not False


def _certificacion_resumen(certificacion: Any) -> dict[str, Any]:
    estado = str(
        _primer_atributo(certificacion, "estado", "state", defecto="")
        or "no_evaluable"
    )
    orientacion = _primer_atributo(
        certificacion,
        "orientacion_certificada",
        "orientation_certified",
    )
    razones = _lista(_primer_atributo(certificacion, "razones", "reasons"))
    metodo = str(
        _primer_atributo(certificacion, "metodo", "method", defecto="") or ""
    )
    columnas_finales_validadas = _primer_atributo(
        certificacion,
        "columnas_finales_validadas",
        "final_columns_validated",
    )
    reconstrucciones_finales = _lista(_primer_atributo(
        certificacion,
        "reconstrucciones_finales",
        "final_reconstructions",
    ))
    proporcion_finales_reconstruidos = _primer_atributo(
        certificacion,
        "proporcion_finales_reconstruidos",
        "final_reconstruction_ratio",
        defecto=0.0,
    )
    reconstruccion_final_revisable = bool(_primer_atributo(
        certificacion,
        "reconstruccion_final_revisable",
        "final_reconstruction_reviewable",
        defecto=False,
    ))
    reconstrucciones_movimientos = _lista(_primer_atributo(
        certificacion,
        "reconstrucciones_movimientos",
        "movement_reconstructions",
    ))
    proporcion_movimientos_reconstruidos = _primer_atributo(
        certificacion,
        "proporcion_movimientos_reconstruidos",
        "movement_reconstruction_ratio",
        defecto=0.0,
    )
    reconstruccion_movimientos_revisable = bool(_primer_atributo(
        certificacion,
        "reconstruccion_movimientos_revisable",
        "movement_reconstruction_reviewable",
        defecto=False,
    ))
    filas_inconsistentes = _lista(_primer_atributo(
        certificacion,
        "filas_inconsistentes",
        "inconsistent_rows",
    ))
    diagnostico = str(_primer_atributo(
        certificacion,
        "diagnostico",
        "diagnosis",
        defecto="NO_EVALUADO",
    ) or "NO_EVALUADO")
    senales_diagnostico = _lista(_primer_atributo(
        certificacion,
        "senales_diagnostico",
        "diagnostic_signals",
    ))
    control_fuente = _valor(certificacion, "source_control_quadrature", None)
    if isinstance(control_fuente, Mapping):
        ecuacion_fuente_valida = control_fuente.get("valid")
        diferencia_ecuacion_fuente = control_fuente.get("difference")
    else:
        ecuacion_fuente_valida = _primer_atributo(
            certificacion,
            "ecuacion_contable_fuente_valida",
            "source_accounting_equation_valid",
        )
        diferencia_ecuacion_fuente = _primer_atributo(
            certificacion,
            "diferencia_ecuacion_contable_fuente",
            "source_accounting_equation_difference",
        )
    # ``parcial`` no es sinónimo de extracción equivocada. Cuando el parser
    # validó las columnas finales de activo, pasivo, patrimonio y resultado
    # contra controles impresos, el paquete puede pasar a un analista aunque
    # aún contenga movimientos auxiliares reconstruidos. Nunca habilita la
    # integración definitiva: sólo reduce la revisión manual a las filas
    # señaladas por la certificación.
    apta_revision_asistida = (
        estado == "certificada"
        or (
            estado == "parcial"
            and columnas_finales_validadas is True
        )
    )
    return {
        "estado": estado,
        "metodo": metodo,
        "orientacion_certificada": orientacion,
        "razones": razones,
        "formato_validado": estado == "certificada",
        "columnas_finales_validadas": columnas_finales_validadas,
        "reconstrucciones_finales": reconstrucciones_finales,
        "proporcion_finales_reconstruidos": proporcion_finales_reconstruidos,
        "reconstruccion_final_revisable": reconstruccion_final_revisable,
        "reconstrucciones_movimientos": reconstrucciones_movimientos,
        "proporcion_movimientos_reconstruidos": (
            proporcion_movimientos_reconstruidos
        ),
        "reconstruccion_movimientos_revisable": (
            reconstruccion_movimientos_revisable
        ),
        "filas_inconsistentes": filas_inconsistentes,
        "diagnostico": diagnostico,
        "etiqueta_diagnostico": ETIQUETAS_DIAGNOSTICO.get(
            diagnostico,
            "Diagnóstico de extracción no registrado",
        ),
        "senales_diagnostico": senales_diagnostico,
        "cuadratura_fuente": {
            "validada": ecuacion_fuente_valida,
            "diferencia": diferencia_ecuacion_fuente,
        },
        "apta_revision_asistida": apta_revision_asistida,
    }


_ESTADOS_TECNICOS_BLOQUEANTES_COMERCIALES = frozenset({
    "NO_LEGIBLE",
    "LECTURA_NO_RESPALDADA",
    "EXTRACCION_NO_VALIDADA",
    "REVISION_EXTRACCION_REQUERIDA",
    "FORMATO_NO_SOPORTADO",
    "COBERTURA_INSUFICIENTE",
})


def evaluar_aceptacion_comercial(
    filas: Iterable[Mapping[str, Any]],
    estado_entrega: Mapping[str, Any],
    *,
    umbral_cobertura: float = DEFAULT_COMMERCIAL_ASSISTED_COVERAGE,
    umbral_confianza_sugerencia: float = (
        DEFAULT_COMMERCIAL_SUGGESTION_CONFIDENCE
    ),
    compatibilidad: Callable[[Mapping[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """Resume si un documento alcanza el criterio comercial de asistencia.

    Este resumen no autoriza una integración ni reemplaza la revisión del
    analista. Se limita a contestar dos preguntas auditables por documento:

    * qué parte fue clasificada sin una decisión humana por cuenta;
    * si esa parte alcanza el umbral acordado sin ocultar decisiones humanas,
      propagaciones o categorías residuales.

    ``estado_entrega`` debe provenir de :func:`evaluar_entregabilidad` o de un
    contrato serializado equivalente. Los gates técnicos conservan prioridad:
    una cobertura suficiente nunca compensa extracción, formato o cuadratura
    no validados.
    """
    if not 0 < umbral_cobertura <= 1:
        raise ValueError("umbral_cobertura debe estar entre 0 y 1")
    if not 0 <= umbral_confianza_sugerencia <= 1:
        raise ValueError(
            "umbral_confianza_sugerencia debe estar entre 0 y 1"
        )

    categorias = (
        "elegibles",
        "automaticas_estrictas",
        "sugeridas_automatizadas",
        "decisiones_humanas_individuales",
        "decisiones_humanas_lote",
        "asistencia_derivada_humano_lote",
        "asistencia_derivada_humano_historial_confirmado",
        "propagacion_sin_traza_confirmada",
        "origin_fallback_en_revision",
        "sugerencias_metodo_no_admitido",
        "sugerencias_sin_evidencia_trazable",
        "sugerencias_confianza_insuficiente",
        "sin_clasificar",
        "incompatibles",
        "excluidas",
        "otras_en_revision",
    )
    cuentas = {categoria: 0 for categoria in categorias}
    importes = {categoria: 0.0 for categoria in categorias}

    for fila_original in filas:
        fila = dict(fila_original)
        relevante, importe = _es_relevante(fila)
        if not relevante:
            continue
        codigo = _codigo(fila)
        compatible = _es_compatible(fila, codigo, compatibilidad)
        categoria = _categoria_cobertura_comercial(
            fila,
            codigo,
            compatible,
            umbral_confianza_sugerencia=umbral_confianza_sugerencia,
        )
        cuentas["elegibles"] += 1
        importes["elegibles"] += importe
        cuentas[categoria] += 1
        importes[categoria] += importe

    cobertura_cuentas = (
        cuentas["automaticas_estrictas"]
        + cuentas["sugeridas_automatizadas"]
    )
    cobertura_importes = (
        importes["automaticas_estrictas"]
        + importes["sugeridas_automatizadas"]
    )
    total = cuentas["elegibles"]
    total_importe = importes["elegibles"]
    porcentaje = cobertura_cuentas / total if total else 0.0
    porcentaje_monetario = (
        cobertura_importes / total_importe if total_importe else 0.0
    )
    minimo_cuentas = math.ceil(total * umbral_cobertura) if total else 0
    brecha_cuentas = max(0, minimo_cuentas - cobertura_cuentas)
    cumple_umbral = bool(total) and porcentaje >= umbral_cobertura

    estado_tecnico = str(
        estado_entrega.get("estado_tecnico")
        or estado_entrega.get("estado")
        or ""
    )
    certificacion = dict(estado_entrega.get("certificacion_extraccion") or {})
    cuadratura = dict(estado_entrega.get("cuadratura_homologada") or {})
    formato = dict(estado_entrega.get("formato") or {})
    bloqueos_finales = [
        str(bloqueo)
        for bloqueo in estado_entrega.get("bloqueos_finales", []) or []
        if str(bloqueo)
    ]
    # ``NO_EVALUADO`` y ``RECONOCIDO_PENDIENTE_VALIDACION`` no equivalen a
    # formato soportado: para aceptación comercial se exige evidencia de un
    # perfil registrado y una extracción ya certificada.
    formato_soportado = formato.get("estado") == "SOPORTADO"
    extraccion_apta = bool(certificacion.get("apta_revision_asistida", False))
    cuadratura_cuadra = bool(cuadratura.get("cuadra", False))
    cuadratura_certificada = bool(cuadratura.get("certificada", False))

    gates_tecnicos = {
        "estado_entrega": estado_tecnico,
        "extraccion_apta_para_revision": extraccion_apta,
        "formato_soportado": formato_soportado,
        "cuadratura_cuadra": cuadratura_cuadra,
        "cuadratura_certificada": cuadratura_certificada,
        "bloqueos_finales": bloqueos_finales,
    }
    motivos: list[str] = []
    siguiente_accion: list[str] = []
    gates_superados = True

    if estado_tecnico in _ESTADOS_TECNICOS_BLOQUEANTES_COMERCIALES:
        gates_superados = False
        motivos.append(
            f"El estado técnico {estado_tecnico} no habilita aceptación comercial."
        )
    if not extraccion_apta:
        gates_superados = False
        motivos.append(
            "La extracción no está apta para revisión asistida según sus controles."
        )
    if not formato_soportado:
        gates_superados = False
        motivos.append(
            "El formato no tiene evidencia de perfil soportado para este documento."
        )
    if not cuadratura_cuadra:
        gates_superados = False
        motivos.append("La cuadratura homologada no cuadra.")
    if bloqueos_finales:
        gates_superados = False
        motivos.append("Existen bloqueos finales antes de la entrega.")

    if not gates_superados:
        estado = "NO_APTO_POR_GATES_TECNICOS"
        siguiente_accion.append(
            "Resolver primero los controles técnicos indicados por el estado de entrega."
        )
    elif not cumple_umbral:
        estado = "NO_APTO_POR_COBERTURA_COMERCIAL"
        motivos.append(
            "La cobertura automática estricta o sugerida con evidencia es "
            f"{porcentaje:.1%}; se requiere al menos {umbral_cobertura:.0%}."
        )
        siguiente_accion.append(
            "Aumentar cobertura sólo con reglas, código o diccionario auditables; "
            "no reclasificar decisiones humanas como automáticas."
        )
    elif (
        estado_tecnico == "LISTO_PARA_INTEGRAR"
        and cuadratura_certificada
    ):
        estado = "CUMPLE_CRITERIO_COMERCIAL_FINAL"
        siguiente_accion.append(
            "Emitir la salida revisada conforme al protocolo operativo vigente."
        )
    else:
        estado = "CUMPLE_CRITERIO_COMERCIAL_PARA_REVISION"
        siguiente_accion.append(
            "Entregar sólo un paquete de revisión y completar la aprobación del analista."
        )

    if cuentas["origin_fallback_en_revision"]:
        siguiente_accion.append(
            "Revisar las categorías origin_fallback por separado; no cuentan "
            "como sugerencia comercial."
        )
    if cuentas["sugerencias_metodo_no_admitido"]:
        motivos.append(
            "Hay sugerencias con un método no admitido por la allowlist comercial."
        )
        siguiente_accion.append(
            "Auditar el método antes de incorporarlo a la allowlist; no usarlo "
            "para aumentar la cobertura mientras tanto."
        )
    if cuentas["sugerencias_sin_evidencia_trazable"]:
        motivos.append(
            "Hay sugerencias sin una evidencia o regla trazable no vacía."
        )
        siguiente_accion.append(
            "Registrar la evidencia o regla que sustenta cada sugerencia antes "
            "de usarla en la cobertura comercial."
        )
    if cuentas["sugerencias_confianza_insuficiente"]:
        motivos.append(
            "Hay sugerencias con confianza inválida o bajo el umbral configurado."
        )
        siguiente_accion.append(
            "Mantener esas sugerencias en revisión hasta contar con una "
            "confianza finita y suficiente, respaldada por una regla trazable."
        )
    decisiones_humanas = (
        cuentas["decisiones_humanas_individuales"]
        + cuentas["decisiones_humanas_lote"]
    )
    if decisiones_humanas:
        siguiente_accion.append(
            "Mantener las decisiones humanas individuales o por lote fuera "
            "del indicador de automatización."
        )
    asistencias_humanas = (
        cuentas["asistencia_derivada_humano_lote"]
        + cuentas["asistencia_derivada_humano_historial_confirmado"]
        + cuentas["propagacion_sin_traza_confirmada"]
    )
    if asistencias_humanas:
        siguiente_accion.append(
            "Cotejar la evidencia de las propagaciones humanas; se informan "
            "aparte y no aumentan la cobertura comercial."
        )
    pendientes = (
        cuentas["sugeridas_automatizadas"]
        + cuentas["origin_fallback_en_revision"]
        + cuentas["sugerencias_metodo_no_admitido"]
        + cuentas["sugerencias_sin_evidencia_trazable"]
        + cuentas["sugerencias_confianza_insuficiente"]
        + cuentas["sin_clasificar"]
        + cuentas["incompatibles"]
        + cuentas["excluidas"]
        + cuentas["otras_en_revision"]
        + cuentas["propagacion_sin_traza_confirmada"]
    )
    if pendientes:
        motivos.append(
            f"{pendientes} cuenta(s) requieren revisión o decisión explícita."
        )

    return {
        "schema_version": "1.1",
        "estado": estado,
        "umbral_cobertura": umbral_cobertura,
        "umbral_confianza_sugerencia": umbral_confianza_sugerencia,
        "metrica": (
            "automaticas_estrictas_mas_sugeridas_automatizadas_con_evidencia"
        ),
        "criterio_sugerencia": {
            "metodos_admitidos": sorted(
                METODOS_SUGERENCIA_COMERCIAL_ADMITIDOS,
            ),
            "campos_trazabilidad_admitidos": [
                "evidencia",
                "evidence",
                "regla",
                "rule",
                "razon",
                "reason",
                "special_rule",
            ],
            "requiere_confianza_finita": True,
        },
        "cumple_umbral": cumple_umbral,
        "apto_para_revision_comercial": gates_superados and cumple_umbral,
        "apto_para_entrega_revisada": bool(
            gates_superados
            and cumple_umbral
            and estado_tecnico == "LISTO_PARA_INTEGRAR"
            and cuadratura_certificada
        ),
        "gates_tecnicos": gates_tecnicos,
        "cobertura": {
            "cuentas": {
                **cuentas,
                "automaticas_o_sugeridas": cobertura_cuentas,
                "fuera_del_numerador": total - cobertura_cuentas,
                "porcentaje": round(porcentaje, 4),
                "minimo_cuentas_umbral": minimo_cuentas,
                "brecha_cuentas": brecha_cuentas,
            },
            "monto_absoluto": {
                **{clave: round(valor, 2) for clave, valor in importes.items()},
                "automaticas_o_sugeridas": round(cobertura_importes, 2),
                "fuera_del_numerador": round(
                    total_importe - cobertura_importes,
                    2,
                ),
                "porcentaje": round(porcentaje_monetario, 4),
            },
        },
        "motivos": list(dict.fromkeys(motivos)),
        "siguiente_accion": list(dict.fromkeys(siguiente_accion)),
    }


def evaluar_entregabilidad(
    filas: Iterable[Mapping[str, Any]],
    certificacion_extraccion: Any = None,
    cuadratura_homologada: Mapping[str, Any] | None = None,
    *,
    umbral_revision: float = DEFAULT_REVIEW_COVERAGE,
    umbral_cobertura_comercial: float = DEFAULT_COMMERCIAL_ASSISTED_COVERAGE,
    umbral_confianza_sugerencia_comercial: float = (
        DEFAULT_COMMERCIAL_SUGGESTION_CONFIDENCE
    ),
    compatibilidad: Callable[[Mapping[str, Any]], bool] | None = None,
    bloqueos_finales: Iterable[str] = (),
    formato: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Devuelve la decisión única de entrega sin mutar el resultado.

    ``sugerida`` significa que existe un código compatible, pero la cuenta aún
    requiere confirmación. No se cuentan como sugeridas las cuentas sin código,
    excluidas o incompatibles con su columna de origen. ``umbral_revision``
    conserva la cobertura técnica para organizar la cola de revisión. El
    criterio comercial separado no incorpora decisiones humanas y se expone en
    ``aceptacion_comercial``.
    """
    if not 0 < umbral_revision <= 1:
        raise ValueError("umbral_revision debe estar entre 0 y 1")
    # Materializar el iterable una vez: el resumen técnico y el comercial deben
    # medir exactamente el mismo universo de cuentas incluso si llega un
    # generador desde un integrador.
    filas_lista = [dict(fila) for fila in filas]

    certificacion = _certificacion_resumen(certificacion_extraccion)
    cuentas = {
        "elegibles": 0,
        "automaticas": 0,
        "sugeridas": 0,
        "confirmadas_analista": 0,
        "sin_clasificar": 0,
        "incompatibles": 0,
        "pendientes": 0,
    }
    importes = {clave: 0.0 for clave in cuentas}

    for fila in filas_lista:
        relevante, importe = _es_relevante(fila)
        if not relevante:
            continue

        cuentas["elegibles"] += 1
        importes["elegibles"] += importe
        codigo = _codigo(fila)
        compatible = _es_compatible(fila, codigo, compatibilidad)
        requiere_revision = _requiere_revision(fila)

        if not codigo or codigo == "__EXCLUIR__":
            cuentas["sin_clasificar"] += 1
            importes["sin_clasificar"] += importe
            cuentas["pendientes"] += 1
            importes["pendientes"] += importe
            continue
        if not compatible:
            cuentas["incompatibles"] += 1
            importes["incompatibles"] += importe
            cuentas["pendientes"] += 1
            importes["pendientes"] += importe
            continue

        if requiere_revision:
            cuentas["sugeridas"] += 1
            importes["sugeridas"] += importe
            cuentas["pendientes"] += 1
            importes["pendientes"] += importe
        elif _es_decision_analista(fila):
            cuentas["confirmadas_analista"] += 1
            importes["confirmadas_analista"] += importe
        else:
            cuentas["automaticas"] += 1
            importes["automaticas"] += importe

    cubiertas_revision = (
        cuentas["automaticas"] + cuentas["sugeridas"]
        + cuentas["confirmadas_analista"]
    )
    importe_cubierto_revision = (
        importes["automaticas"] + importes["sugeridas"]
        + importes["confirmadas_analista"]
    )
    total = cuentas["elegibles"]
    total_importe = importes["elegibles"]
    cobertura = cubiertas_revision / total if total else 0.0
    cobertura_monetaria = (
        importe_cubierto_revision / total_importe if total_importe else 0.0
    )

    cuadratura = dict(cuadratura_homologada or {})
    cuadratura_certificada = bool(cuadratura.get("certificada", False))
    cuadratura_cuadra = bool(cuadratura.get("cuadra", False))
    resultado_derivado_incorporado = bool(
        cuadratura.get("resultado_derivado_incorporado", True),
    )
    razones_cuadratura = list(cuadratura.get("motivos", []) or [])
    bloqueos = [str(b) for b in bloqueos_finales if str(b)]
    razones: list[str] = []
    if not resultado_derivado_incorporado:
        razones.append(
            "El estado de resultados separado no se sumó por segunda vez al patrimonio."
        )
    formato_resultado = dict(formato or {
        "estado": "NO_EVALUADO",
        "id": "",
        "familia": "",
        "metodo": certificacion["metodo"],
        "mensaje": "No se evaluó un perfil de formato para este documento.",
    })

    if total == 0:
        legibilidad = "SIN_CUENTAS_UTILIZABLES"
    elif certificacion["orientacion_certificada"] is False:
        legibilidad = "ORIENTACION_NO_RESPALDADA"
    elif certificacion["orientacion_certificada"] is True:
        legibilidad = "OCR_RESPALDADO"
    else:
        legibilidad = "TEXTO_NATIVO_O_EXCEL"

    if total == 0:
        estado = "NO_LEGIBLE"
        razones.append("No se encontraron cuentas con saldo utilizables.")
    elif certificacion["orientacion_certificada"] is False:
        estado = "LECTURA_NO_RESPALDADA"
        razones.append(
            "La orientación de una o más páginas OCR no tiene evidencia suficiente."
        )
    elif not (
        certificacion["apta_revision_asistida"]
        or certificacion["reconstruccion_final_revisable"]
    ):
        estado = "EXTRACCION_NO_VALIDADA"
        razones.extend(certificacion["razones"])
        if not razones:
            razones.append(
                "La extracción no tiene controles independientes suficientes para aprobarla."
            )
    elif formato_resultado["estado"] in {"NO_RECONOCIDO", "NO_ES_BALANCE"}:
        estado = "FORMATO_NO_SOPORTADO"
        razones.append(formato_resultado["mensaje"])
    elif (
        certificacion["estado"] == "certificada"
        and cuadratura_certificada
        and cuadratura_cuadra
        and not cuentas["pendientes"]
        and not bloqueos
    ):
        estado = "LISTO_PARA_INTEGRAR"
    elif cobertura < umbral_revision:
        estado = "COBERTURA_INSUFICIENTE"
        razones.append(
            "La cobertura automática o sugerida es "
            f"{cobertura:.1%}; se requiere al menos {umbral_revision:.0%}."
        )
    elif certificacion["reconstruccion_final_revisable"]:
        estado = "REVISION_EXTRACCION_REQUERIDA"
        cantidad = len(certificacion["reconstrucciones_finales"])
        razones.append(
            "Los controles fuente concilian, pero "
            f"{cantidad} cifra(s) final(es) fueron reconstruidas desde "
            "columnas auxiliares. Deben cotejarse contra el original antes "
            "de usar el vaciado."
        )
        if cuentas["pendientes"]:
            razones.append(
                f"{cuentas['pendientes']} cuenta(s) requieren decisión o confirmación del analista."
            )
        if not cuadratura_cuadra:
            razones.append("La cuadratura homologada aún no cuadra.")
        razones.extend(razones_cuadratura)
        razones.extend(bloqueos)
    else:
        estado = "LISTO_PARA_REVISION_ANALISTA"
        if certificacion["estado"] == "parcial":
            razones.append(
                "Las columnas contables finales pasaron su control independiente; "
                "la extracción parcial exige revisión del analista antes de integrar."
            )
        if cuentas["pendientes"]:
            razones.append(
                f"{cuentas['pendientes']} cuenta(s) requieren decisión o confirmación del analista."
            )
        if not cuadratura_cuadra:
            razones.append("La cuadratura homologada aún no cuadra.")
        razones.extend(razones_cuadratura)
        razones.extend(bloqueos)

    # En estados bloqueados se conserva el motivo de extracción, sin duplicarlo.
    if estado in {
        "NO_LEGIBLE", "LECTURA_NO_RESPALDADA", "EXTRACCION_NO_VALIDADA",
        "FORMATO_NO_SOPORTADO", "COBERTURA_INSUFICIENTE",
    }:
        razones.extend(bloqueos)
        razones.extend(r for r in razones_cuadratura if r not in razones)

    razones_unicas = list(dict.fromkeys(razones))
    review_export_allowed = estado in {
        "REVISION_EXTRACCION_REQUERIDA", "LISTO_PARA_REVISION_ANALISTA",
        "LISTO_PARA_INTEGRAR",
    }

    resultado = {
        "schema_version": SCHEMA_VERSION,
        "estado": estado,
        "etiqueta": ESTADOS[estado],
        "umbral_revision": umbral_revision,
        "exportacion_final_permitida": estado == "LISTO_PARA_INTEGRAR",
        "exportacion_revision_permitida": review_export_allowed,
        "certificacion_extraccion": certificacion,
        "legibilidad": legibilidad,
        "formato": formato_resultado,
        "cuadratura_homologada": {
            "certificada": cuadratura_certificada,
            "cuadra": cuadratura_cuadra,
            "diferencia": cuadratura.get("diferencia"),
            "resultado_derivado_incorporado": resultado_derivado_incorporado,
            "resultado_final_fuente_incorporado": bool(
                cuadratura.get("resultado_final_fuente_incorporado", False),
            ),
            "resultado_final_fuente": cuadratura.get(
                "resultado_final_fuente",
            ),
        },
        "cobertura": {
            "cuentas": {
                **cuentas,
                "automaticas_o_sugeridas": (
                    cuentas["automaticas"] + cuentas["sugeridas"]
                ),
                "cubiertas_para_revision": cubiertas_revision,
                "porcentaje": round(cobertura, 4),
            },
            "monto_absoluto": {
                **{clave: round(valor, 2) for clave, valor in importes.items()},
                "cubierto_para_revision": round(importe_cubierto_revision, 2),
                "porcentaje": round(cobertura_monetaria, 4),
            },
        },
        "bloqueos_finales": bloqueos,
        "razones": razones_unicas,
    }
    resultado["aceptacion_comercial"] = evaluar_aceptacion_comercial(
        filas_lista,
        resultado,
        umbral_cobertura=umbral_cobertura_comercial,
        umbral_confianza_sugerencia=(
            umbral_confianza_sugerencia_comercial
        ),
        compatibilidad=compatibilidad,
    )
    return resultado
