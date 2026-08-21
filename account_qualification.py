"""GATE 4E — Capa de account row qualification.

Capa determinística de calificación de cuentas extraídas.

La capa se ejecuta DESPUÉS de la extracción/reconstrucción y ANTES del
matching/homologación.

Regla de oro:
- No usar IA.
- No reclasificar cuentas.
- No modificar nombres.
- No modificar montos.
- No reordenar cuentas.
- Solo descartar filas cuando una regla determinística lo justifica.
- Las cuentas conservadas mantienen identidad y orden de entrada.

Reglas implementadas:

  RULE-01 EMPTY
      Descarta filas sin nombre de cuenta.

  RULE-02 FOOTER
      Descarta metadatos evidentes de encabezado/pie:
      RUT, dirección, representante legal, página, empresa, giro,
      firma, teléfono, correo, sucursal, domicilio, etc.

  RULE-03 URL
      Descarta URLs y direcciones de correo electrónico.

  RULE-04 SECTION
      Descarta encabezados/bandas de sección sin montos:
      ACTIVO, PASIVO, PATRIMONIO, CORRIENTE, LARGO PLAZO, etc.

  RULE-05 TOTAL
      Descarta filas TOTAL/SUMA/SUBTOTAL únicamente cuando no poseen
      montos propios.

  RULE-06 PERIOD_HEAD
      Descarta cabeceras de período sin montos:
      ACTUAL, ANTERIOR, SALDO, DEBE, HABER, EJERCICIO, años, etc.

  RULE-07 NOISE
      Descarta ruido evidente sin montos y sin señales contables.

  RULE-08 DEDUP
      Elimina duplicados exactos dentro de la misma ubicación lógica,
      usando nombre normalizado y montos, conservando la primera aparición.

Importante:
RULE-05 NO elimina una fila TOTAL que tenga monto.
RULE-04, RULE-06 y RULE-07 tampoco eliminan filas que tengan montos.

Esto es deliberado: una fila con monto puede representar una cuenta,
un subtotal o un total legítimo y no debe eliminarse únicamente por su texto.

La capa es pura, determinista, sin I/O y sin IA.
"""

from __future__ import annotations

import os
import re
import unicodedata


# ===========================================================================
# ACTIVACIÓN CONTROLADA DE SAFE
# ===========================================================================

SAFE_MODE_ENV = "SAFE_MODE"

_SAFE_ON_VALUES = frozenset(
    {
        "1",
        "true",
        "on",
        "yes",
        "si",
        "sí",
    }
)


def safe_mode_enabled() -> bool:
    """Indica si la calificación SAFE se habilitó explícitamente por entorno."""
    return os.environ.get(SAFE_MODE_ENV, "").strip().lower() in _SAFE_ON_VALUES


# ===========================================================================
# NORMALIZACIÓN
# ===========================================================================

_NON_ALNUM = re.compile(r"[^0-9A-Za-z]+")


def _norm(name: str) -> str:
    """Normaliza un nombre para comparación semántica básica."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _NON_ALNUM.sub(" ", s.upper()).strip()


# ===========================================================================
# UTILIDADES
# ===========================================================================

def _has_amount(columns) -> bool:
    """Indica si la fila contiene al menos un monto no nulo."""
    return any(
        value is not None
        for value in (columns or {}).values()
    )


# ===========================================================================
# SEÑALES DE CONTENIDO
# ===========================================================================

_TOTAL_RE = re.compile(
    r"^(TOTAL|SUMA|SUBTOTAL|TOTALS|TOTALES)\b",
    re.I,
)


_FOOTER_RE = re.compile(
    r"^(R\.?\s?U\.?\s?T|RUT|DIRECCION|DIRECCION\s+[A-Z]|"
    r"REPRESENTANTE\s+LEGAL|PAGINA|PAGE|EMPRESA|GIRO|FIRMA|"
    r"RAZON\s+SOCIAL|BALANCE\s+CLASIFICADO|EEFF|INFORME|"
    r"ESTADOS\s+FINANCIEROS|MEMORIA|AUDITOR|CONTADOR|"
    r"TELEFONO|FONO|CORREO|EMAIL|SUCURSAL|DOMICILIO|"
    r"CIUDAD|REGION|COMUNA)\b",
    re.I,
)


_URL_RE = re.compile(
    r"https?://|www\.|\S+@\S+\.\S+",
    re.I,
)


# ===========================================================================
# SECCIONES CONTABLES
# ===========================================================================

_SECTION_EXACT = {
    "ACTIVO",
    "ACTIVOS",
    "PASIVO",
    "PASIVOS",
    "PATRIMONIO",
    "PATRIMONIO NETO",
    "CORRIENTE",
    "NO CORRIENTE",
    "NO-CORRIENTE",
    "NO CORRIENTES",
    "CIRCULANTE",
    "CIRCULANTES",
    "CORTO PLAZO",
    "LARGO PLAZO",
    "RESULTADO",
    "RESULTADOS",
    "INGRESOS",
    "GASTOS",
}


_SECTION_BAND_WORDS = {
    "CORRIENTE",
    "CORRIENTES",
    "NO",
    "LARGO",
    "PLAZO",
    "CIRCULANTE",
    "CIRCULANTES",
    "FIJO",
    "FIJOS",
    "OTROS",
    "PASIVO",
    "ACTIVO",
    "TOTAL",
    "Y",
    "PATRIMONIO",
    "CAPITAL",
    "RESULTADO",
    "RESULTADOS",
}


# ===========================================================================
# CABECERAS DE PERÍODO
# ===========================================================================

_PERIOD_HEAD_RE = re.compile(
    r"^(ACTUAL|ANTERIOR|ANTERIORES|SALDO|SALDOS|DEBE|DEBES|"
    r"HABER|HABERES|DEBITOS|CREDITOS|SUMAS|DEL\s+EJERCICIO|"
    r"EJERCICIO|DICIEMBRE|AL\s+\d{1,2}\s+DE|DESDE|"
    r"POR\s+EL\s+A[ÑN]O)\b",
    re.I,
)


_YEAR_HEAD_RE = re.compile(
    r"^\d{4}(\s|/|-|$)"
)


_YEAR_ONLY_RE = re.compile(
    r"^\d{4}$"
)


# ===========================================================================
# TÉRMINOS CONTABLES
# ===========================================================================

_CONTABLE_TERMS = (
    "CAJA",
    "BANCO",
    "CLIENTE",
    "PROVEEDOR",
    "DEUDOR",
    "ACREEDOR",
    "INVENTARIO",
    "EXISTENCIA",
    "IMPUESTO",
    "CAPITAL",
    "PAGAR",
    "COBRAR",
    "REMUNERACION",
    "OBLIGACION",
    "DOCUMENTO",
    "EQUIPO",
    "TERRENO",
    "EDIFICIO",
    "MAQUINARIA",
    "DEPRECIACION",
    "RESERVA",
    "UTILIDAD",
    "PERDIDA",
    "INGRESO",
    "COSTO",
    "GASTO",
    "PATRIMONIO",
    "ACCIONISTA",
    "CUENTA",
    "FINANCIER",
    "LEASING",
    "ARRENDAMIENTO",
    "PRESTAMO",
    "HIPOTECA",
    "BONO",
    "ACCION",
    "EFECTIVO",
    "EQUIVALENTE",
    "TOTAL",
    "DISPONIBLE",
    "PROVISION",
    "RETENCION",
    "INTANGIBLE",
    "PLUSVALIA",
    "GOODWILL",
    "DIVIDENDO",
    "MONEDA",
    "SEGMENTO",
    "HONORARIO",
    "SEGURO",
    "ARRIENDO",
    "COMISION",
    "INTERES",
    "SUELDO",
    "ASSET",
    "LIABILITY",
    "EQUITY",
    "CASH",
    "RECEIVABLE",
    "PAYABLE",
    "INVENTORY",
    "TAX",
    "RETAINED",
    "EARNINGS",
    "RESERVES",
    "REVENUE",
    "EXPENSE",
    "INCOME",
    "PROFIT",
    "LOSS",
    "DEPRECIATION",
    "AMORTIZATION",
    "DEBT",
    "LOAN",
    "BORROWING",
    "STOCK",
    "SHARE",
    "DIVIDEND",
    "PROVISION",
    "LEASING",
    "LEASE",
    "PREPAID",
    "ACCRUAL",
    "BANK",
    "FACTORING",
    "INSURANCE",
    "FREIGHT",
    "VESSEL",
    "MACHINER",
    "LAND",
    "BUILDING",
    "INTANGIBLE",
    "CURRENT",
    "FIXED",
    "LONG TERM",
    "SHORT TERM",
    "WITHHOLDING",
    "WAGES",
    "PAYABLES",
    "TRADE",
    "BORROW",
)


_EMBEDDED_AMOUNT = re.compile(
    r"(?:\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?)|\d{4,}"
)


def _has_contable_term(norm: str) -> bool:
    """Indica si el texto contiene alguna señal contable conocida."""
    return any(term in norm for term in _CONTABLE_TERMS)


# ===========================================================================
# RULE-01 — EMPTY
# ===========================================================================

def rule01_empty(accounts):
    """RULE-01 — Descarta filas sin texto de nombre."""
    return [
        account
        for account in accounts
        if _norm(account.get("name") or "")
    ]


# ===========================================================================
# RULE-02 — FOOTER
# ===========================================================================

def rule02_footer(accounts):
    """RULE-02 — Descarta metadatos evidentes de encabezado/pie."""
    out = []

    for account in accounts:
        name = account.get("name") or ""

        if not _norm(name):
            out.append(account)
            continue

        if _FOOTER_RE.match(name.strip()):
            continue

        out.append(account)

    return out


# ===========================================================================
# RULE-03 — URL
# ===========================================================================

def rule03_url(accounts):
    """RULE-03 — Descarta URLs y correos electrónicos."""
    return [
        account
        for account in accounts
        if not _URL_RE.search(account.get("name") or "")
    ]


# ===========================================================================
# RULE-04 — SECTION
# ===========================================================================

def rule04_section(accounts):
    """RULE-04 — Descarta bandas de sección sin montos."""
    out = []

    for account in accounts:
        name = account.get("name") or ""
        norm = _norm(name)

        # Si tiene monto, NO se elimina.
        if not norm or _has_amount(account.get("columns")):
            out.append(account)
            continue

        tokens = norm.split()

        # Encabezado exacto.
        if norm in _SECTION_EXACT:
            continue

        # Banda compuesta exclusivamente por palabras de sección.
        if (
            len(tokens) <= 8
            and all(token in _SECTION_BAND_WORDS for token in tokens)
        ):
            continue

        out.append(account)

    return out


# ===========================================================================
# RULE-05 — TOTAL
# ===========================================================================

def rule05_total(accounts):
    """RULE-05 — Descarta TOTAL/SUMA/SUBTOTAL sin monto propio."""
    out = []

    for account in accounts:
        name = account.get("name") or ""

        # IMPORTANTE:
        # Un TOTAL con monto se conserva.
        if (
            _TOTAL_RE.match(name.strip())
            and not _has_amount(account.get("columns"))
        ):
            continue

        out.append(account)

    return out


# ===========================================================================
# RULE-06 — PERIOD HEAD
# ===========================================================================

def rule06_period_head(accounts):
    """RULE-06 — Descarta cabeceras de período sin montos."""
    out = []

    for account in accounts:
        name = account.get("name") or ""
        norm = _norm(name)

        # Si tiene monto, se conserva.
        if _has_amount(account.get("columns")):
            out.append(account)
            continue

        token_count = len(norm.split())

        # Cabeceras textuales de período.
        if (
            _PERIOD_HEAD_RE.match(name.strip())
            and token_count <= 6
        ):
            continue

        # Año como encabezado.
        if (
            _YEAR_HEAD_RE.match(norm)
            and token_count <= 2
            and _YEAR_ONLY_RE.match(
                norm.split()[0] if norm.split() else ""
            )
        ):
            continue

        out.append(account)

    return out


# ===========================================================================
# RULE-07 — NOISE
# ===========================================================================

def rule07_noise(accounts):
    """RULE-07 — Descarta ruido evidente sin montos.

    Solo actúa sobre filas SIN montos.

    Se consideran señales de ruido:

    1. Algún token de longitud menor a 2 y ausencia de señales contables.
    2. Un único token sin señales contables.
    3. Ausencia simultánea de términos contables y montos embebidos.

    La regla es deliberadamente conservadora:
    una fila con monto nunca es eliminada por RULE-07.
    """

    out = []

    for account in accounts:
        name = account.get("name") or ""
        norm = _norm(name)

        # Sin nombre o con monto: conservar.
        if not norm or _has_amount(account.get("columns")):
            out.append(account)
            continue

        tokens = norm.split()

        short_token = any(
            len(token) < 2
            for token in tokens
        )

        has_contable = _has_contable_term(norm)

        has_embedded_amount = bool(
            _EMBEDDED_AMOUNT.search(name)
        )

        # Caso 1: token demasiado corto + sin señal contable.
        if (
            short_token
            and not has_contable
            and not has_embedded_amount
        ):
            continue

        # Caso 2: único token sin señal contable.
        if (
            not has_contable
            and not has_embedded_amount
            and len(tokens) <= 1
        ):
            continue

        out.append(account)

    return out


# ===========================================================================
# RULE-08 — DEDUP
# ===========================================================================

def rule08_dedup(accounts):
    """RULE-08 — Elimina duplicados exactos.

    La clave de duplicación está compuesta por:

        page + nombre normalizado + montos

    Se conserva siempre la primera aparición.

    Esto permite evitar duplicados producidos por reconstrucción A+B
    sin eliminar cuentas legítimas que aparezcan en ubicaciones distintas.
    """

    seen = set()
    out = []

    for account in accounts:
        norm = _norm(account.get("name") or "")

        if not norm:
            out.append(account)
            continue

        values = tuple(
            sorted(
                value
                for value in (account.get("columns") or {}).values()
                if value is not None
            )
        )

        key = (
            account.get("page"),
            norm,
            values,
        )

        if key in seen:
            continue

        seen.add(key)
        out.append(account)

    return out


# ===========================================================================
# CATÁLOGO DE REGLAS
# ===========================================================================

RULES = {
    "RULE-01": rule01_empty,
    "RULE-02": rule02_footer,
    "RULE-03": rule03_url,
    "RULE-04": rule04_section,
    "RULE-05": rule05_total,
    "RULE-06": rule06_period_head,
    "RULE-07": rule07_noise,
    "RULE-08": rule08_dedup,
}


RULE_ORDER = [
    "RULE-01",
    "RULE-02",
    "RULE-03",
    "RULE-04",
    "RULE-05",
    "RULE-06",
    "RULE-07",
    "RULE-08",
]


# ===========================================================================
# GATE 4E — REGLAS SAFE DE PRODUCCIÓN
# ===========================================================================

# Solo estas reglas están autorizadas por defecto en producción.
# RULE-01, RULE-04, RULE-05, RULE-06 y RULE-07 permanecen disponibles
# para laboratorio/benchmark, pero no se ejecutan implícitamente.
SAFE_RULES = [
    "RULE-02",
    "RULE-03",
    "RULE-08",
]


# ===========================================================================
# API PRINCIPAL
# ===========================================================================

def apply_rules(accounts, rule_ids):
    """Aplica las reglas indicadas en el orden recibido.

    La función:
    - conserva el orden;
    - no modifica objetos;
    - solo elimina filas;
    - falla explícitamente si se solicita una regla desconocida.
    """

    out = list(accounts)

    for rule_id in rule_ids:
        fn = RULES.get(rule_id)

        if fn is None:
            raise ValueError(
                "regla desconocida: %s" % rule_id
            )

        out = fn(out)

    return out


# ===========================================================================
# ADAPTADOR DE PRODUCCIÓN — CuentaRaw
# ===========================================================================

def _cuenta_raw_to_row(account):
    """Convierte CuentaRaw a la estructura usada por las reglas.

    CuentaRaw:
        nombre -> name
        monto  -> columns["col0"]
        linea  -> page / row_index

    La adaptación no modifica el objeto original.
    """

    return {
        "name": account.nombre,
        "columns": (
            {"col0": account.monto}
            if account.monto is not None
            else {}
        ),
        "page": getattr(account, "linea", None),
        "row_index": getattr(account, "linea", None),
    }


def qualify_cuentas(
    cuentas,
    rule_ids: list[str] | None = None,
):
    """Aplica reglas de calificación a cuentas de producción o dicts.

    Soporta:

    1. objetos CuentaRaw;
    2. dicts del laboratorio con 'name' y 'columns'.

    En ambos casos:
    - conserva el orden;
    - no modifica los objetos;
    - solo elimina filas calificadas como inválidas.

    Por defecto aplica SAFE_RULES.
    """

    if not cuentas:
        return cuentas

    if rule_ids is None:
        rule_ids = list(SAFE_RULES)
    else:
        rule_ids = list(rule_ids)

    first = cuentas[0]

    # ------------------------------------------------------------------
    # CuentaRaw
    # ------------------------------------------------------------------

    if hasattr(first, "nombre"):
        rows = [
            _cuenta_raw_to_row(account)
            for account in cuentas
        ]

        qualified_rows = apply_rules(
            rows,
            rule_ids,
        )

        kept_ids = {
            id(row)
            for row in qualified_rows
        }

        return [
            account
            for account, row in zip(cuentas, rows)
            if id(row) in kept_ids
        ]

    # ------------------------------------------------------------------
    # Dict del laboratorio
    # ------------------------------------------------------------------

    if isinstance(first, dict) and "name" in first:
        return apply_rules(
            cuentas,
            rule_ids,
        )

    # ------------------------------------------------------------------
    # Tipo desconocido
    # ------------------------------------------------------------------

    return cuentas


# ===========================================================================
# PRUEBA MANUAL
# ===========================================================================

if __name__ == "__main__":

    demo = [
        {
            "name": "Caja",
            "columns": {"col0": 100.0},
            "page": 1,
        },
        {
            "name": "www.bancoestado.cl",
            "columns": {"col0": 0.0},
            "page": 1,
        },
        {
            "name": "Total Activos",
            "columns": {"col0": 999.0},
            "page": 1,
        },
        {
            "name": "Caja",
            "columns": {"col0": 100.0},
            "page": 1,
        },
        {
            "name": "ACTIVO",
            "columns": {},
            "page": 1,
        },
        {
            "name": "2024",
            "columns": {},
            "page": 1,
        },
        {
            "name": "",
            "columns": {},
            "page": 1,
        },
    ]

    print("Registros iniciales:", len(demo))

    result = apply_rules(
        demo,
        RULE_ORDER,
    )

    print("Registros finales:", len(result))
    print()

    for index, account in enumerate(result, start=1):
        print(index, account)
