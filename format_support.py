"""Registro pequeño y explícito de formatos que el producto puede declarar soportados.

La detección visual de una familia no basta para prometer una extracción. Un
formato sólo aparece como soportado cuando el extractor usado está registrado y
la extracción de ese documento pasó su control independiente.
"""

from __future__ import annotations

from typing import Any, Mapping


FORMAT_PROFILES: dict[str, dict[str, str]] = {
    "coordinates_8_amounts": {
        "id": "BALANCE_TRIBUTARIO_8_COLUMNAS_NATIVO",
        "familia": "Balance tributario de ocho columnas",
    },
    "native_table_8_columns": {
        "id": "BALANCE_TRIBUTARIO_8_COLUMNAS_NATIVO",
        "familia": "Balance tributario de ocho columnas",
    },
    "native_text_8_columns_validated": {
        "id": "BALANCE_TRIBUTARIO_8_COLUMNAS_NATIVO",
        "familia": "Balance tributario de ocho columnas",
    },
    "native_layout_8_columns": {
        "id": "BALANCE_TRIBUTARIO_8_COLUMNAS_NATIVO",
        "familia": "Balance tributario de ocho columnas",
    },
    "ocr_coordinates_8_amounts": {
        "id": "BALANCE_TRIBUTARIO_8_COLUMNAS_OCR",
        "familia": "Balance tributario de ocho columnas con OCR",
    },
    "ocr_classified_two_columns": {
        "id": "BALANCE_CLASIFICADO_DOS_COLUMNAS_OCR",
        "familia": "Balance clasificado de dos columnas con OCR",
    },
    "native_classified_two_columns": {
        "id": "BALANCE_CLASIFICADO_DOS_COLUMNAS_NATIVO",
        "familia": "Balance clasificado de dos columnas con texto nativo",
    },
    "excel_8_columns": {
        "id": "BALANCE_TRIBUTARIO_8_COLUMNAS_EXCEL",
        "familia": "Balance tributario de ocho columnas en Excel",
    },
}

# ``OTRO`` es el valor por defecto del analizador cuando no existe texto
# nativo, algo habitual en un PDF escaneado. No es evidencia de que el archivo
# no sea un balance. En cambio, estos tipos son estados financieros parciales
# identificados explícitamente y no alcanzan para emitir un balance
# homologado de Activo = Pasivo + Patrimonio.
DOCUMENT_TYPES_NOT_BALANCE = {
    "ESTADO_RESULTADOS",
    "ESTADO_PATRIMONIO",
    "ESTADO_FLUJO",
    "NOTAS",
}


def _valor(objeto: Any, nombre: str, defecto: Any = None) -> Any:
    if isinstance(objeto, Mapping):
        return objeto.get(nombre, defecto)
    return getattr(objeto, nombre, defecto)


def _primer_atributo(
    objeto: Any, *nombres: str, defecto: Any = None,
) -> Any:
    for nombre in nombres:
        valor = _valor(objeto, nombre, None)
        if valor is not None:
            return valor
    return defecto


def _tipo_documental(contexto: Any) -> str:
    firma = _valor(contexto, "signature")
    tipo = _valor(firma, "document_type")
    return str(_valor(tipo, "value", tipo) or "")


def evaluar_formato(certificacion: Any = None, contexto_documental: Any = None) -> dict[str, Any]:
    """Describe si el formato está soportado, sin alterar la extracción."""
    estado_extraccion = str(
        _primer_atributo(certificacion, "estado", "state", defecto="")
        or "no_evaluable"
    )
    metodo = str(
        _primer_atributo(certificacion, "metodo", "method", defecto="") or ""
    )
    tipo_documental = _tipo_documental(contexto_documental)

    perfil = FORMAT_PROFILES.get(metodo)

    # La certificación de una tabla completa de ocho columnas con totales
    # finales validados es evidencia más específica que una etiqueta
    # documental basada en texto. Esto evita degradar un balance tributario
    # certificado cuando su encabezado o sus cuentas contienen la palabra
    # "resultados". La etiqueta documental sigue bloqueando documentos
    # parciales o no certificados.
    if perfil is not None and estado_extraccion == "certificada":
        return {
            "estado": "SOPORTADO",
            "id": perfil["id"],
            "familia": perfil["familia"],
            "metodo": metodo,
            "mensaje": "El formato está soportado y este documento pasó sus controles de extracción.",
        }

    if tipo_documental in DOCUMENT_TYPES_NOT_BALANCE:
        return {
            "estado": "NO_ES_BALANCE",
            "id": "",
            "familia": "",
            "metodo": metodo,
            "mensaje": "El análisis documental no lo identifica como balance.",
        }

    if perfil is None:
        return {
            "estado": "NO_RECONOCIDO",
            "id": "",
            "familia": "",
            "metodo": metodo,
            "mensaje": "No existe un extractor certificado registrado para este formato.",
        }

    estado = "RECONOCIDO_PENDIENTE_VALIDACION"
    mensaje = (
        "Se reconoció una familia soportada, pero este documento no pasó "
        "todavía los controles de extracción."
    )
    return {
        "estado": estado,
        "id": perfil["id"],
        "familia": perfil["familia"],
        "metodo": metodo,
        "mensaje": mensaje,
    }
