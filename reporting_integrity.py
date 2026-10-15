"""Reglas compartidas de naturaleza y conciliación del estado de resultados.

No reclasifica ni modifica importes. Los códigos de resultado bidireccional
conservan el efecto de la columna física y el signo del documento.
"""
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from parsers.account_type_resolver import (
    is_contra_asset_name,
    is_credit_balance_depreciation_name,
    is_debit_balance_financial_liability,
)


RESULTADOS_MIXTOS = frozenset({"ER.13", "ER.14", "ER.15", "ER.16"})


@lru_cache(maxsize=1)
def catalogo_local():
    with Path(__file__).with_name("catalogo_maestro.json").open(encoding="utf-8") as f:
        return json.load(f)


def tipo_resultado(codigo, catalogo=None):
    """La naturaleza prevalece sobre signo_normal (ER.18 tiene signo +1)."""
    codigo = str(codigo or "")
    if not codigo.startswith("ER."):
        return None
    if codigo in RESULTADOS_MIXTOS:
        return "mixto"
    entry = (catalogo if catalogo is not None else catalogo_local()).get(codigo, {})
    return {"acreedora": "ganancia", "deudora": "perdida"}.get(entry.get("naturaleza"))


def resultado_compatible(codigo, tipo, catalogo=None):
    tipo = str(getattr(tipo, "value", tipo) or "").lower()
    if not str(codigo or "").startswith("ER.") or tipo not in {"perdida", "ganancia"}:
        return True
    naturaleza = tipo_resultado(codigo, catalogo)
    return naturaleza == "mixto" or naturaleza == tipo


def importe_resultado_origen(origen, monto):
    origen = str(getattr(origen, "value", origen) or "").lower()
    if origen not in {"perdida", "ganancia"}:
        return None
    valor = float(monto)
    if not math.isfinite(valor):
        raise ValueError("Importe de resultado no finito")
    return valor if origen == "ganancia" else -valor


def importe_resultado_homologado(codigo, monto, origen, catalogo=None):
    tipo = tipo_resultado(codigo, catalogo)
    if tipo == "mixto":
        return importe_resultado_origen(origen, monto)
    if tipo in {"ganancia", "perdida"}:
        valor = abs(float(monto))
        return valor if tipo == "ganancia" else -valor
    return None


def conciliar_resultados(
    filas, catalogo, tolerancia=0.01, *,
    considerar_pat04_declarado: bool = True,
):
    """Compara columnas originales con categorías asignadas, sin ER calculados.

    Cuando un balance certificado contiene un puente final de resultado, una
    fila ``PAT.04`` del detalle puede ser un saldo patrimonial previo al cierre
    y no el resultado final del período. En ese contexto se conserva la fila
    para la cuadratura patrimonial, pero no se la compara como si declarara el
    resultado que el puente ya certificó.
    """
    origen = []
    homologado = []
    problemas = []
    declarados = {}
    for row in filas:
        if row.get("es_total", False):
            continue
        codigo = str(row.get("codigo_clasificado") or "")
        nombre = str(row.get("nombre_original") or "")
        try:
            monto = float(row.get("monto"))
            if not math.isfinite(monto):
                raise ValueError()
        except (ValueError, TypeError):
            problemas.append(f"{nombre}: importe ausente o inválido")
            continue
        if monto == 0:
            continue
        raw = importe_resultado_origen(row.get("origen_columna"), monto)
        if raw is not None:
            origen.append(raw)
        if codigo == "ER.11" or (
            codigo == "PAT.04" and considerar_pat04_declarado
        ):
            declarados[codigo] = declarados.get(codigo, 0.0) + (
                importe_presentacion_balance(
                    codigo, monto, nombre, row.get("origen_columna"),
                ) if codigo == "PAT.04" else monto
            )
        if not codigo.startswith("ER."):
            continue
        entry = catalogo.get(codigo, {})
        if codigo == 'ER.11' or entry.get("clasificable") is False:
            if codigo != "ER.11":
                problemas.append(f"{nombre}: asignada a una categoría calculada ({codigo})")
            continue
        importe = importe_resultado_homologado(codigo, monto, row.get("origen_columna"), catalogo)
        if importe is None:
            problemas.append(f"{nombre}: naturaleza de resultado sin definir ({codigo})")
        else:
            homologado.append(importe)
    total_origen = sum(origen) if origen else None
    total_homologado = sum(homologado) if homologado else None
    diferencia = None
    if total_origen is not None or total_homologado is not None:
        diferencia = (total_homologado or 0.0) - (total_origen or 0.0)
        if total_origen is None or total_homologado is None:
            problemas.append("No hay detalle suficiente para conciliar el resultado de forma independiente")
        elif abs(diferencia) > tolerancia:
            problemas.append(f"Resultado homologado menos resultado de origen: {diferencia:,.2f}")
    for codigo, valor in declarados.items():
        if total_homologado is not None and abs(valor - total_homologado) > tolerancia:
            problemas.append(f"{codigo} no coincide con el resultado de las categorías homologadas")
    return {
        "resultado_origen": total_origen,
        "resultado_homologado": total_homologado,
        "diferencia": diferencia,
        "problemas": problemas,
        "cuadra": not problemas,
    }


def importe_presentacion_balance(
    codigo: str, monto: float, nombre: str,
    origen_columna: Any = None,
) -> float:
    """Aplica el signo de presentación sin alterar el importe extraído.

    Las utilidades o pérdidas acumuladas y el resultado declarado pueden
    aparecer por el lado deudor del balance tributario. En ese caso reducen el
    patrimonio, aunque su importe extraído sea positivo. Se conserva la
    columna física para no confundir ese caso con una utilidad acreedora.
    """
    origen = str(getattr(origen_columna, "value", origen_columna) or "").lower()
    if codigo == "PAT.10":
        return -abs(monto)
    if codigo == "PAT.07":
        # Capital suscrito aún no enterado es la contra-partida de PAT.06/
        # PAT.01, incluso cuando el balance tributario lo muestra físicamente
        # al lado de Activo por su naturaleza deudora.
        return -abs(monto)
    if codigo in {"PAT.03", "PAT.04"}:
        if float(monto) < 0 or origen in {"activo", "deudor"}:
            return -abs(monto)
        return abs(monto)
    if (
        codigo.startswith(("PC.", "PNC."))
        and is_debit_balance_financial_liability(nombre, origen, monto)
    ):
        # La obligación conserva la columna física ACTIVO/DEUDOR y se
        # representa como contra-pasivo. Esto evita convertirla en un pasivo
        # positivo que empeoraría la ecuación. La admisión de la categoría se
        # mantiene condicionada a revisión humana en los flujos de UI/pipeline.
        return -abs(monto)
    if codigo.startswith("ANC") and (
        is_contra_asset_name(nombre)
        or is_credit_balance_depreciation_name(nombre, origen, monto)
    ):
        return -abs(monto)
    return monto


# Nombre histórico interno preservado para consumidores que todavía lo usen.
_importe_presentacion_balance = importe_presentacion_balance


def _fila_requiere_revision(fila: dict[str, Any]) -> bool:
    return bool(
        fila.get("requiere_revision", False)
        or fila.get("review_required", False)
        or fila.get("review", False)
    )


def debe_incorporar_resultado_derivado(
    filas: Iterable[Mapping[str, Any] | Any], certificacion: Any = None,
) -> bool:
    """Decide si el resultado ER debe sumarse a la ecuación patrimonial.

    Un balance clasificado de dos columnas puede adjuntar después un estado de
    resultados separado. Cuando la ecuación física Activo = Pasivo +
    Patrimonio ya fue validada y ambos estados están explícitamente rotulados,
    volver a sumar ER duplica o contradice un patrimonio que puede incorporar
    resultados retenidos. La función no declara correcta la hoja de
    resultados: sólo evita usarla dos veces en la ecuación patrimonial.
    """
    metodo = str(getattr(certificacion, "metodo", "") or "")
    totales_finales_validos = bool(
        getattr(certificacion, "totales_finales_validos", False),
    )
    if metodo not in {
        "ocr_classified_two_columns",
        "native_classified_two_columns",
    } or not totales_finales_validos:
        return True

    estados: set[str] = set()
    for fila in filas:
        if isinstance(fila, Mapping):
            estado = fila.get("estado_financiero")
        else:
            estado = getattr(fila, "estado_financiero", None)
        estado = str(estado or "").strip().lower()
        if estado:
            estados.add(estado)
    return not {"balance", "resultados"}.issubset(estados)


def resultado_final_fuente_certificado(certificacion: Any = None) -> float | None:
    """Devuelve el cierre fuente firmado cuando su evidencia es suficiente.

    El valor sólo se consume para cuadratura si el parser certificó el
    documento completo, validó los totales finales y validó la ecuación fuente
    entre balance y resultado. No crea una cuenta ni reemplaza la clasificación
    semántica de las filas.
    """
    if certificacion is None:
        return None

    def leer(nombre: str, defecto: Any = None) -> Any:
        if isinstance(certificacion, Mapping):
            return certificacion.get(nombre, defecto)
        return getattr(certificacion, nombre, defecto)

    if (
        str(leer("estado", "") or "") != "certificada"
        or leer("totales_finales_validos") is not True
        or leer("ecuacion_contable_fuente_valida") is not True
    ):
        return None
    tipo = str(leer("tipo_resultado", "") or "").lower()
    try:
        resultado = float(leer("resultado_ejercicio"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(resultado):
        return None
    if (
        (resultado > 0 and tipo != "utilidad")
        or (resultado < 0 and tipo != "perdida")
        or (resultado == 0 and tipo not in {"utilidad", "perdida"})
    ):
        return None
    return resultado


def certificar_cuadratura_homologada(
    filas: Iterable[dict[str, Any]],
    catalogo: dict[str, dict[str, Any]] | None = None,
    *,
    tolerancia: float = 1.0,
    compatibilidad: Callable[[dict[str, Any]], bool] | None = None,
    incluir_resultado_derivado: bool = True,
    resultado_final_fuente: float | None = None,
) -> dict[str, Any]:
    """Certifica la ecuación contable después de homologar las cuentas.

    Esta verificación no reemplaza la certificación de extracción de ocho
    columnas. Exige además cobertura completa, categorías conocidas y ausencia
    de decisiones pendientes. El resultado del período se incorpora una sola
    vez al patrimonio: se usa PAT.04 declarado si existe, o se deriva desde
    las cuentas ER conciliadas contra sus columnas originales.
    ``resultado_final_fuente`` es un cierre firmado y certificado por el
    parser. Cuando está presente, se incorpora una vez a la ecuación y se
    contrasta contra las categorías ER; una cuenta PAT.04 del detalle continúa
    como saldo patrimonial y no sustituye ese cierre.
    """
    catalogo = catalogo if catalogo is not None else catalogo_local()
    resultado_fuente = None
    if resultado_final_fuente is not None:
        try:
            candidato_resultado_fuente = float(resultado_final_fuente)
        except (TypeError, ValueError):
            candidato_resultado_fuente = float("nan")
        if math.isfinite(candidato_resultado_fuente):
            resultado_fuente = candidato_resultado_fuente
    activos = 0.0
    pasivos = 0.0
    patrimonio_sin_resultado = 0.0
    resultado_declarado = 0.0
    hay_resultado_declarado = False
    relevantes: list[dict[str, Any]] = []
    sin_clasificar: list[dict[str, Any]] = []
    codigos_invalidos: list[dict[str, Any]] = []
    incompatibles: list[dict[str, Any]] = []
    pendientes: list[dict[str, Any]] = []

    for indice, fila_original in enumerate(filas):
        fila = dict(fila_original)
        if fila.get("es_total", False):
            continue
        nombre = str(
            fila.get("nombre_original")
            or fila.get("account_name")
            or fila.get("name")
            or ""
        )
        try:
            monto = float(
                fila.get("monto", fila.get("classification_amount", fila.get("amount")))
            )
            if not math.isfinite(monto):
                raise ValueError()
        except (TypeError, ValueError):
            sin_clasificar.append({"indice": indice, "cuenta": nombre, "motivo": "importe_invalido"})
            continue
        # La tolerancia sirve para comparar ecuaciones, no para ocultar una
        # cuenta extraída. Cualquier saldo distinto de cero debe estar cubierto
        # antes de declarar completa la homologación.
        if monto == 0:
            continue
        codigo = str(
            fila.get("codigo_clasificado")
            or fila.get("final_code")
            or fila.get("code")
            or ""
        ).strip()
        item = {
            "indice": indice,
            "cuenta": nombre,
            "monto": monto,
            "codigo": codigo,
        }
        relevantes.append({
            "nombre_original": nombre,
            "monto": monto,
            # La sección contable explícita puede precisar un lado físico
            # compartido, por ejemplo PASIVO -> PATRIMONIO en un balance
            # clasificado de dos columnas. La trazabilidad de la columna
            # original permanece en la fila fuente.
            "origen_columna": (
                fila.get("origen_columna_efectiva")
                or fila.get("origen_columna", fila.get("origin", ""))
            ),
            "codigo_clasificado": codigo,
            "es_total": False,
        })
        if not codigo or codigo == "__EXCLUIR__":
            sin_clasificar.append({**item, "motivo": "sin_clasificacion"})
            continue
        if codigo not in catalogo:
            codigos_invalidos.append({**item, "motivo": "codigo_fuera_catalogo"})
            continue
        if compatibilidad is not None:
            try:
                es_compatible = bool(compatibilidad(fila))
            except Exception:
                es_compatible = False
            if not es_compatible:
                incompatibles.append({**item, "motivo": "incompatible_con_origen"})
        elif fila.get("compatible") is False:
            incompatibles.append({**item, "motivo": "incompatible_con_origen"})
        if _fila_requiere_revision(fila):
            pendientes.append(item)

        importe = importe_presentacion_balance(
            codigo, monto, nombre, fila.get("origen_columna"),
        )
        if codigo.startswith(("AC.", "ANC.")):
            activos += importe
        elif codigo.startswith(("PC.", "PNC.")):
            pasivos += importe
        elif codigo.startswith("PAT."):
            if codigo == "PAT.04" and resultado_fuente is None:
                resultado_declarado += importe
                hay_resultado_declarado = True
            else:
                patrimonio_sin_resultado += importe

    conciliacion_resultado = conciliar_resultados(
        relevantes,
        catalogo,
        tolerancia,
        considerar_pat04_declarado=resultado_fuente is None,
    )
    resultado_homologado = conciliacion_resultado["resultado_homologado"]
    if resultado_fuente is not None:
        resultado_periodo = resultado_fuente
        if resultado_homologado is None:
            conciliacion_resultado["problemas"].append(
                "No hay detalle de resultado homologado para contrastar el "
                "cierre final certificado de la fuente",
            )
        elif (
            abs(float(resultado_homologado) - resultado_fuente) > tolerancia
            and (
                conciliacion_resultado["resultado_origen"] is None
                or abs(
                    float(conciliacion_resultado["resultado_origen"])
                    - resultado_fuente,
                ) > tolerancia
            )
        ):
            conciliacion_resultado["problemas"].append(
                "Resultado homologado menos cierre final certificado de la "
                f"fuente: {float(resultado_homologado) - resultado_fuente:,.2f}",
            )
    elif hay_resultado_declarado:
        resultado_periodo = resultado_declarado
    elif incluir_resultado_derivado and resultado_homologado is not None:
        resultado_periodo = float(resultado_homologado)
    else:
        resultado_periodo = 0.0
    pasivo_mas_patrimonio = pasivos + patrimonio_sin_resultado + resultado_periodo
    diferencia = activos - pasivo_mas_patrimonio
    cuadra = abs(diferencia) <= tolerancia

    motivos: list[str] = []
    if not relevantes:
        motivos.append("No se encontraron cuentas con saldo para certificar la cuadratura homologada")
    if sin_clasificar:
        motivos.append(f"{len(sin_clasificar)} cuenta(s) con saldo sin clasificación válida")
    if codigos_invalidos:
        motivos.append(f"{len(codigos_invalidos)} código(s) fuera del catálogo")
    if incompatibles:
        motivos.append(f"{len(incompatibles)} clasificación(es) incompatible(s) con su origen")
    if pendientes:
        motivos.append(f"{len(pendientes)} cuenta(s) todavía requieren revisión")
    motivos.extend(conciliacion_resultado["problemas"])
    if not cuadra:
        motivos.append(
            "Activo menos Pasivo y Patrimonio homologados: "
            f"{diferencia:,.2f}"
        )

    return {
        "certificada": not motivos,
        "cuadra": cuadra,
        "activo": round(activos, 2),
        "pasivo": round(pasivos, 2),
        "patrimonio_sin_resultado": round(patrimonio_sin_resultado, 2),
        "resultado_periodo": round(resultado_periodo, 2),
        "resultado_derivado_incorporado": bool(
            incluir_resultado_derivado and resultado_fuente is None,
        ),
        "resultado_final_fuente_incorporado": resultado_fuente is not None,
        "resultado_final_fuente": (
            round(resultado_fuente, 2) if resultado_fuente is not None else None
        ),
        "pasivo_mas_patrimonio": round(pasivo_mas_patrimonio, 2),
        "diferencia": round(diferencia, 2),
        "filas_relevantes": len(relevantes),
        "filas_clasificadas": len(relevantes) - len(sin_clasificar),
        "sin_clasificar": sin_clasificar,
        "codigos_invalidos": codigos_invalidos,
        "incompatibles": incompatibles,
        "pendientes": pendientes,
        "resultado": conciliacion_resultado,
        "motivos": motivos,
    }
