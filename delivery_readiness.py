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
JSON.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from typing import Any


SCHEMA_VERSION = "1.0"
DEFAULT_REVIEW_COVERAGE = 0.60

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


def _es_decision_analista(fila: Mapping[str, Any]) -> bool:
    metodo = str(fila.get("metodo") or fila.get("method") or "").lower()
    return any(token in metodo for token in ("validacion_humana", "manual", "analista"))


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


def evaluar_entregabilidad(
    filas: Iterable[Mapping[str, Any]],
    certificacion_extraccion: Any = None,
    cuadratura_homologada: Mapping[str, Any] | None = None,
    *,
    umbral_revision: float = DEFAULT_REVIEW_COVERAGE,
    compatibilidad: Callable[[Mapping[str, Any]], bool] | None = None,
    bloqueos_finales: Iterable[str] = (),
    formato: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Devuelve la decisión única de entrega sin mutar el resultado.

    ``sugerida`` significa que existe un código compatible, pero la cuenta aún
    requiere confirmación. No se cuentan como sugeridas las cuentas sin código,
    excluidas o incompatibles con su columna de origen.
    """
    if not 0 < umbral_revision <= 1:
        raise ValueError("umbral_revision debe estar entre 0 y 1")

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

    for fila_original in filas:
        fila = dict(fila_original)
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

    return {
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
        "razones": razones_unicas,
    }
