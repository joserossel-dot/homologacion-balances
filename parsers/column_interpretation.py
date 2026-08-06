"""Interpretación contable de `origen_columna` (capa intermedia, OC-1).

Traduce el hecho de extracción (`OrigenColumna` o strings polimórficos) a
semántica contable (`es_ingreso`/`es_gasto`) sin estado global.

Acepta: OrigenColumna | str | None | "".  Nunca lanza.
"""

from parser_universal import OrigenColumna


def normalize(origen) -> OrigenColumna:
    """Normaliza cualquier representación de origen_columna a OrigenColumna."""
    if isinstance(origen, OrigenColumna):
        return origen
    if isinstance(origen, str):
        valor = origen.strip()
        try:
            return OrigenColumna(valor)
        except ValueError:
            try:
                return OrigenColumna[valor.upper()]
            except KeyError:
                return OrigenColumna.DESCONOCIDO
    return OrigenColumna.DESCONOCIDO


def es_ingreso(origen) -> bool:
    """True si la columna corresponde al lado de ingresos (GANANCIA o ACTIVO)."""
    return normalize(origen) in (OrigenColumna.GANANCIA, OrigenColumna.ACTIVO)


def es_gasto(origen) -> bool:
    """True si la columna corresponde al lado de gastos (PERDIDA o PASIVO)."""
    return normalize(origen) in (OrigenColumna.PERDIDA, OrigenColumna.PASIVO)
