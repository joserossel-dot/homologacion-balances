"""Orden y filtro centralizado del catálogo para la cola de clasificación manual.

Única fuente de verdad para la lista de selección de la UI (`app_validacion.py`):

- Orden de presentación por grupos: Activos, Pasivos, Patrimonio, Ingresos,
  Costos, Gastos, Otros ingresos, Otros egresos. Dentro de cada grupo se
  mantiene el **orden interno del catálogo** (el orden de las claves del JSON).
- No son seleccionables por el analista (aunque siguen existiendo en el
  catálogo para validaciones y comparaciones):
    * cuentas de cálculo marcadas con `clasificable: false`
      (p. ej. EBITDA, Margen Bruto, Resultado Operacional, Utilidad Neta,
      Resultado del Ejercicio);
    * cuentas TOTAL (nombre que comienza con "Total").

La UI no contiene listas hardcodeadas de códigos ni de nombres: todo pasa por
`opciones_clasificacion()`.
"""

from __future__ import annotations

from typing import Any, Dict, List

GRUPOS_PRESENTACION: List[str] = [
    "Activos",
    "Pasivos",
    "Patrimonio",
    "Ingresos",
    "Costos",
    "Gastos",
    "Otros ingresos",
    "Otros egresos",
]

_CATEGORIA_A_GRUPO: Dict[str, str] = {
    "activo_corriente": "Activos",
    "activo_no_corriente": "Activos",
    "pasivo_corriente": "Pasivos",
    "pasivo_no_corriente": "Pasivos",
    "patrimonio": "Patrimonio",
}

_PREFIJO_TOTAL = "total"


def grupo_presentacion(entrada: Any) -> str:
    """Grupo de presentación de una entrada del catálogo.

    Usa el atributo explícito `grupo_presentacion` del catálogo; si no está
    declarado (p. ej. categorías creadas por el analista) lo deriva de
    `categoria`. Grupos desconocidos caen al final del listado.
    """
    if not isinstance(entrada, dict):
        return ""
    grupo = str(entrada.get("grupo_presentacion") or "")
    if grupo in GRUPOS_PRESENTACION:
        return grupo
    categoria = str(entrada.get("categoria") or "")
    return _CATEGORIA_A_GRUPO.get(categoria, "")


def es_clasificable(entrada: Any) -> bool:
    """¿La cuenta puede ser seleccionada por el analista?

    False si `clasificable` es false (cuentas de cálculo) o si el nombre
    comienza con "Total" (cuentas TOTAL). El resto es seleccionable.
    """
    if not isinstance(entrada, dict):
        return False
    if entrada.get("clasificable") is False:
        return False
    nombre = str(entrada.get("nombre_estandar") or "").strip().lower()
    if nombre.startswith(_PREFIJO_TOTAL):
        return False
    return True


def _indice_grupo(grupo: str) -> int:
    try:
        return GRUPOS_PRESENTACION.index(grupo)
    except ValueError:
        return len(GRUPOS_PRESENTACION)


def opciones_clasificacion(catalogo: Dict[str, Any]) -> List[str]:
    """Códigos seleccionables, agrupados y en orden de presentación.

    Dentro de cada grupo se respeta el orden interno del catálogo (el orden
    de iteración de sus claves). Los grupos no declarados van al final.
    Es una función pura: no muta `catalogo`.
    """
    por_grupo: Dict[str, List[str]] = {g: [] for g in GRUPOS_PRESENTACION}
    desconocidos: List[str] = []
    for codigo, entrada in catalogo.items():
        if not es_clasificable(entrada):
            continue
        grupo = grupo_presentacion(entrada)
        if grupo in por_grupo:
            por_grupo[grupo].append(codigo)
        else:
            desconocidos.append(codigo)

    opciones: List[str] = []
    for grupo in GRUPOS_PRESENTACION:
        opciones.extend(por_grupo[grupo])
    opciones.extend(desconocidos)
    return opciones
