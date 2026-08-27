"""Reglas compartidas de naturaleza y conciliación del estado de resultados.

No reclasifica ni modifica importes. Los códigos de resultado bidireccional
conservan el efecto de la columna física y el signo del documento.
"""
from functools import lru_cache
import json
import math
from pathlib import Path


RESULTADOS_MIXTOS = frozenset({
    "ER.13", "ER.14", "ER.15", "ER.16", "ER.20", "ER.21",
})


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


def conciliar_resultados(filas, catalogo, tolerancia=0.01):
    """Compara columnas originales con categorías asignadas, sin ER calculados."""
    origen = []
    homologado = []
    problemas = []
    declarados = {}
    for row in filas:
        if row.get("es_total", False):
            continue
        codigo = str(row.get("codigo_clasificado") or "")
        nombre = str(row.get("nombre_original") or "")
        entry = catalogo.get(codigo, {})
        # Los desgloses de atribución explican cómo se distribuye la utilidad
        # neta. Se muestran y exportan, pero no vuelven a sumarse al resultado.
        if entry.get("aditivo_resultado") is False:
            continue
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
        if codigo in {"ER.11", "PAT.04"}:
            declarados[codigo] = declarados.get(codigo, 0.0) + monto
        if not codigo.startswith("ER."):
            continue
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


def validar_reclasificacion_depreciacion(
    total, desde_costo_ventas, desde_gastos_administracion, *,
    costo_ventas_disponible=None, gastos_administracion_disponible=None,
    tolerancia=0.01,
):
    """Valida una apertura manual de depreciación incluida en otros gastos.

    La operación es una reclasificación de resultado: el total informado debe
    coincidir con las porciones retiradas de costo de ventas y administración.
    """
    valores = {
        "Depreciación total": total,
        "Porción incluida en Costo de Ventas": desde_costo_ventas,
        "Porción incluida en Gastos de Administración": desde_gastos_administracion,
    }
    normalizados = {}
    errores = []
    for etiqueta, valor in valores.items():
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            errores.append(f"{etiqueta}: importe no válido")
            continue
        if not math.isfinite(numero):
            errores.append(f"{etiqueta}: importe no finito")
        elif numero < 0:
            errores.append(f"{etiqueta}: use un importe positivo")
        normalizados[etiqueta] = numero
    if errores:
        return errores

    total_num = normalizados["Depreciación total"]
    costo_num = normalizados["Porción incluida en Costo de Ventas"]
    admin_num = normalizados["Porción incluida en Gastos de Administración"]
    if total_num <= tolerancia:
        errores.append("La depreciación total debe ser mayor que cero")
    if abs(total_num - costo_num - admin_num) > tolerancia:
        errores.append(
            "La depreciación total debe ser igual a la suma descontada de "
            "Costo de Ventas y Gastos de Administración"
        )
    for etiqueta, porcion, disponible in (
        ("Costo de Ventas", costo_num, costo_ventas_disponible),
        ("Gastos de Administración", admin_num, gastos_administracion_disponible),
    ):
        if disponible is None:
            if porcion > tolerancia:
                errores.append(f"No existe un saldo de {etiqueta} del cual descontar")
            continue
        if porcion - abs(float(disponible)) > tolerancia:
            errores.append(
                f"La porción de {etiqueta} supera su saldo homologado disponible"
            )
    return errores
