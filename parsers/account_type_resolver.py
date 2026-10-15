"""AccountTypeResolver — determina el tipo de cuenta universal permitido.

Responsabilidad única: dado origen_columna + layout detectado + reglas contables,
determinar el universo de tipos de cuenta válidos para cada cuenta.

NO clasifica. NO usa regex. NO usa fuzzy matching. NO usa CMCC.

Output: AccountType (ACTIVO | PASIVO | PATRIMONIO | PERDIDA | GANANCIA | DESCONOCIDO)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Optional

from parser_universal import OrigenColumna


def is_contra_asset_name(name: str | None) -> bool:
    """True para cuentas acreedoras que reducen activos no corrientes."""
    normalized = re.sub(r"\s+", " ", str(name or "").lower()).strip()
    return any(
        re.search(pattern, normalized)
        for pattern in (
            # Los planes contables usan tanto la palabra completa como la
            # abreviatura ``DEP. ACUMULADA``. Ambas identifican un
            # contra-activo sólo junto a ``acumulada``; ``dep.`` aislado no
            # basta para alterar la naturaleza de una cuenta.
            r"\bdep(?:reciaci[oó]n(?:es)?)?\.?\s+acumulad[ao]s?\b",
            r"amortizaci[oó]n(?:es)? acumulada",
            r"deterioro acumulado",
        )
    )


def is_debit_balance_financial_liability(
    name: str | None,
    origen_columna: Any = None,
    monto: Any = None,
) -> bool:
    """Reconoce una obligación bancaria con saldo deudor físico.

    La regla es deliberadamente estrecha: identifica solamente glosas de
    obligaciones con bancos e instituciones financieras que el documento
    muestra en ACTIVO o DEUDOR. No cambia por sí sola la clasificación ni el
    importe; el flujo que la use debe conservar la columna fuente y exigir
    confirmación humana antes de cerrar el documento.
    """
    origen = str(getattr(origen_columna, "value", origen_columna) or "").lower()
    if origen not in {"activo", "deudor"}:
        return False
    try:
        if monto is not None and float(monto) < 0:
            return False
    except (TypeError, ValueError):
        return False

    normalized = re.sub(
        r"[^a-z0-9áéíóúñü]+", " ", str(name or "").lower(),
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return bool(
        re.search(r"\boblig(?:aci[oó]n(?:es)?)?\b", normalized)
        and re.search(r"\b(?:bco(?:s)?|banco(?:s)?)\b", normalized)
        and re.search(
            r"\b(?:inst(?:ituci[oó]n(?:es)?)?|financier[ao]s?)\b",
            normalized,
        )
    )


def is_credit_balance_depreciation_name(
    name: str | None,
    origen_columna: Any = None,
    monto: Any = None,
) -> bool:
    """Reconoce depreciación con saldo acreedor como contra-activo.

    Un gasto por depreciación se espera en PÉRDIDA. La misma glosa ubicada en
    PASIVO o ACREEDOR representa el saldo crediticio acumulado del activo en
    un balance de comprobación. Se exige el origen físico para no cambiar la
    naturaleza de las depreciaciones de resultado.
    """
    origen = str(getattr(origen_columna, "value", origen_columna) or "").lower()
    if origen not in {"pasivo", "acreedor"}:
        return False
    try:
        if monto is not None and float(monto) < 0:
            return False
    except (TypeError, ValueError):
        return False

    normalized = re.sub(
        r"[^a-z0-9áéíóúñü]+", " ", str(name or "").lower(),
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return bool(
        re.match(r"^dep(?:reciaci[oó]n(?:es)?)?\b", normalized)
        or (
            re.match(r"^de\b", normalized)
            and re.search(r"\bejer", normalized)
        )
    )


def is_capital_pending_name(name: str | None) -> bool:
    """Reconoce el capital suscrito pendiente como contra-patrimonio.

    A diferencia de un aporte o capital pagado, el capital por enterar es la
    porción no pagada por los accionistas y reduce el patrimonio. Se mantiene
    una expresión restringida para no tratar cualquier palabra ``capital``
    como una contra-cuenta.
    """
    normalized = re.sub(r"\s+", " ", str(name or "").lower()).strip()
    return bool(re.search(
        r"\bcapital\s+(?:por\s+enterar|no\s+(?:enterado|pagado)|"
        r"pendiente\s+de\s+enterar)\b",
        normalized,
    ))


def is_patrimonial_reserve_name(name: str | None) -> bool:
    """True para reservas de patrimonio, no para provisiones de activos."""
    normalized = re.sub(r"\s+", " ", str(name or "").lower()).strip()
    if not re.search(r"\breserva(?:s)?\b", normalized):
        return False
    return not re.search(
        r"incobrable|dudoso|obsolesc|inventario|provisi[oó]n|depreciaci[oó]n",
        normalized,
    )


_RESULTADO_ANUAL_RE = re.compile(
    r"\bresultado(?:s)?\s+(?:del\s+)?a(?:ñ|n)o\s+"
    r"(?P<year>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_RESULTADO_ACUMULADO_2402_RE = re.compile(r"^2402-")


def result_year_from_name(name: str | None) -> int | None:
    """Devuelve el año de una glosa explícita ``RESULTADO AÑO YYYY``.

    No infiere años desde cualquier número de la cuenta: la forma acotada
    permite distinguir el resultado de un ejercicio identificado del resto de
    las glosas contables.
    """
    normalized = re.sub(r"\s+", " ", str(name or "").lower()).strip()
    match = _RESULTADO_ANUAL_RE.search(normalized)
    return int(match.group("year")) if match else None


def is_accumulated_result_2402_code(account_code: str | None) -> bool:
    """True sólo para la familia fuente 2402- de resultados acumulados."""
    normalized_code = re.sub(r"\s+", "", str(account_code or ""))
    return bool(_RESULTADO_ACUMULADO_2402_RE.match(normalized_code))


def is_historical_accumulated_result_name(
    name: str | None,
    *,
    account_code: str | None,
    closing_year: int | str | None,
) -> bool:
    """Reconoce un resultado histórico de la familia 2402 como PAT.03.

    La excepción exige tres evidencias simultáneas: una etiqueta explícita de
    resultado anual, un año anterior al cierre confirmado y el código fuente
    ``2402-`` cuyo plan identifica resultados acumulados. Sin cualquiera de
    ellas no cambia la naturaleza física de la cuenta.
    """
    result_year = result_year_from_name(name)
    try:
        confirmed_closing_year = int(closing_year) if closing_year is not None else None
    except (TypeError, ValueError):
        return False
    if confirmed_closing_year is None or not (1900 <= confirmed_closing_year <= 2200):
        return False
    return bool(
        result_year is not None
        and result_year < confirmed_closing_year
        and is_accumulated_result_2402_code(account_code)
    )


def is_accumulated_result_name(
    name: str | None,
    *,
    account_code: str | None = None,
    closing_year: int | str | None = None,
) -> bool:
    """True para resultados acumulados patrimoniales con evidencia suficiente."""
    normalized = re.sub(r"\s+", " ", str(name or "").lower()).strip()
    explicit_accumulated = bool(re.search(
        r"\b(?:resultado(?:s)?|utilidad(?:es)?|ganancia(?:s)?|p[eé]rdida(?:s)?)\s+"
        r"(?:acumulad[ao]s?|retenid[ao]s?|de\s+ejercicios?\s+anteriores?)\b",
        normalized,
    ))
    return explicit_accumulated or is_historical_accumulated_result_name(
        name,
        account_code=account_code,
        closing_year=closing_year,
    )


def is_current_result_name(name: str | None) -> bool:
    """Reconoce el resultado del ejercicio como componente patrimonial.

    La condición se limita a rótulos explícitos de utilidad, pérdida,
    ganancia o resultado del período. No alcanza cuentas de ingresos o gastos
    que mencionen el ejercicio dentro de una glosa más extensa.
    """
    normalized = re.sub(
        r"[^a-z0-9áéíóúñü]+", " ", str(name or "").lower(),
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return bool(re.search(
        r"\b(?:utilidad|p[eé]rdida|ganancia|resultado)"
        r"(?:\s+(?:o\s+)?(?:utilidad|p[eé]rdida|ganancia))?"
        r"\s+del\s+ejercicio\b",
        normalized,
    ))


class AccountType(str, Enum):
    ACTIVO = "ACTIVO"
    PASIVO = "PASIVO"
    PATRIMONIO = "PATRIMONIO"
    PERDIDA = "PERDIDA"
    GANANCIA = "GANANCIA"
    DESCONOCIDO = "DESCONOCIDO"


def account_type_from_explicit_section(section: str | None) -> AccountType | None:
    """Convierte una sección contable observada en un tipo de cuenta.

    La sección se usa sólo cuando proviene de una cabecera explícita del
    documento. No intenta deducir la naturaleza a partir del nombre de una
    cuenta ni reemplaza la columna física extraída.
    """
    normalized = re.sub(r"\s+", " ", str(section or "").lower()).strip()
    return {
        "activo": AccountType.ACTIVO,
        "pasivo": AccountType.PASIVO,
        "patrimonio": AccountType.PATRIMONIO,
        "perdida": AccountType.PERDIDA,
        "ganancia": AccountType.GANANCIA,
    }.get(normalized)


@dataclass
class AccountTypeResult:
    account_type: AccountType
    allowed_types: list[AccountType] = field(default_factory=list)
    confidence: float = 1.0
    method: str = "origen_columna"
    note: str = ""


class AccountTypeResolver:
    """Resuelve el tipo de cuenta universal desde origen_columna + layout + reglas.

    Flujo:
      1. Derivar tipo(s) permitido(s) desde origen_columna (regla base)
      2. Si hay ambigüedad, resolver con layout detectado y prefijo de código
      3. Si persiste ambigüedad, usar fallback documentado
    """

    _ORIGEN_TO_TYPES: dict[OrigenColumna, tuple[AccountType, ...]] = {
        OrigenColumna.ACTIVO: (AccountType.ACTIVO,),
        OrigenColumna.PASIVO: (AccountType.PASIVO, AccountType.PATRIMONIO),
        OrigenColumna.PERDIDA: (AccountType.PERDIDA,),
        OrigenColumna.GANANCIA: (AccountType.GANANCIA,),
        OrigenColumna.DEUDOR: (AccountType.ACTIVO, AccountType.PERDIDA),
        OrigenColumna.ACREEDOR: (AccountType.PASIVO, AccountType.GANANCIA),
        OrigenColumna.DESCONOCIDO: (
            AccountType.ACTIVO, AccountType.PASIVO,
            AccountType.PATRIMONIO, AccountType.PERDIDA, AccountType.GANANCIA,
        ),
    }

    _CODE_PREFIX_TYPES: dict[str, AccountType] = {
        "ANC": AccountType.ACTIVO,
        "AC": AccountType.ACTIVO,
        "PNC": AccountType.PASIVO,
        "PC": AccountType.PASIVO,
        "PAT": AccountType.PATRIMONIO,
    }

    def resolve(
        self,
        origen_columna: OrigenColumna,
        codigo: Optional[str] = None,
        layout_columns: Optional[list[str]] = None,
    ) -> AccountTypeResult:
        allowed = self._origen_to_types(origen_columna)
        if len(allowed) == 1:
            return AccountTypeResult(
                account_type=allowed[0],
                allowed_types=list(allowed),
                confidence=1.0,
                method="origen_columna",
            )
        if not allowed:
            return AccountTypeResult(
                account_type=AccountType.DESCONOCIDO,
                allowed_types=[],
                confidence=0.0,
                method="empty",
            )
        return self._resolve_ambiguous(allowed, origen_columna, codigo, layout_columns)

    def _origen_to_types(self, origen: OrigenColumna) -> tuple[AccountType, ...]:
        return self._ORIGEN_TO_TYPES.get(origen, (AccountType.DESCONOCIDO,))

    def _resolve_ambiguous(
        self,
        allowed: tuple[AccountType, ...],
        origen: OrigenColumna,
        codigo: Optional[str] = None,
        layout_columns: Optional[list[str]] = None,
    ) -> AccountTypeResult:
        if origen == OrigenColumna.PASIVO:
            return self._resolve_pasivo(allowed, codigo, layout_columns)
        if origen == OrigenColumna.DEUDOR:
            return self._resolve_deudor(allowed, codigo)
        if origen == OrigenColumna.ACREEDOR:
            return self._resolve_acreedor(allowed, codigo)
        if origen == OrigenColumna.DESCONOCIDO:
            return self._resolve_desconocido(allowed, codigo)
        return AccountTypeResult(
            account_type=allowed[0],
            allowed_types=list(allowed),
            confidence=0.5,
            method="fallback",
        )

    def _resolve_pasivo(
        self,
        allowed: tuple[AccountType, ...],
        codigo: Optional[str] = None,
        layout_columns: Optional[list[str]] = None,
    ) -> AccountTypeResult:
        if layout_columns and "patrimonio" in layout_columns:
            code_type = self._match_code_prefix(codigo)
            if code_type == AccountType.PATRIMONIO:
                return AccountTypeResult(
                    account_type=AccountType.PATRIMONIO,
                    allowed_types=list(allowed),
                    confidence=0.95,
                    method="layout+code_prefix",
                    note="Layout tiene columna 'patrimonio' y código comienza con PAT",
                )
        return AccountTypeResult(
            account_type=AccountType.PASIVO,
            allowed_types=list(allowed),
            confidence=0.9,
            method="origen_columna",
            note="Columna pasivo/patrimonio sin evidencia de patrimonio",
        )

    def _resolve_deudor(
        self,
        allowed: tuple[AccountType, ...],
        codigo: Optional[str] = None,
    ) -> AccountTypeResult:
        if codigo:
            code_type = self._match_code_prefix(codigo)
            if code_type in (AccountType.ACTIVO, AccountType.PASIVO):
                if code_type == AccountType.PASIVO:
                    return AccountTypeResult(
                        account_type=AccountType.PASIVO,
                        allowed_types=list(allowed),
                        confidence=0.85,
                        method="code_prefix",
                        note=f"Código {codigo} en columna deudora con prefijo de pasivo",
                    )
                return AccountTypeResult(
                    account_type=AccountType.ACTIVO,
                    allowed_types=list(allowed),
                    confidence=0.85,
                    method="code_prefix",
                    note=f"Código {codigo} en columna deudora con prefijo de activo",
                )
            if codigo.startswith("ER"):
                return AccountTypeResult(
                    account_type=AccountType.PERDIDA,
                    allowed_types=list(allowed),
                    confidence=0.80,
                    method="code_prefix",
                    note=f"Código {codigo} en columna deudora → naturaleza deudora",
                )
        return AccountTypeResult(
            account_type=AccountType.ACTIVO,
            allowed_types=list(allowed),
            confidence=0.60,
            method="origen_columna_fallback",
            note="Columna deudora sin código → asume activo",
        )

    def _resolve_acreedor(
        self,
        allowed: tuple[AccountType, ...],
        codigo: Optional[str] = None,
    ) -> AccountTypeResult:
        if codigo:
            code_type = self._match_code_prefix(codigo)
            if code_type in (AccountType.PASIVO, AccountType.PATRIMONIO):
                return AccountTypeResult(
                    account_type=code_type,
                    allowed_types=list(allowed),
                    confidence=0.85,
                    method="code_prefix",
                    note=f"Código {codigo} en columna acreedora con prefijo {code_type.value}",
                )
            if codigo.startswith("ER"):
                return AccountTypeResult(
                    account_type=AccountType.GANANCIA,
                    allowed_types=list(allowed),
                    confidence=0.80,
                    method="code_prefix",
                    note=f"Código {codigo} en columna acreedora → naturaleza acreedora",
                )
        return AccountTypeResult(
            account_type=AccountType.PASIVO,
            allowed_types=list(allowed),
            confidence=0.60,
            method="origen_columna_fallback",
            note="Columna acreedora sin código → asume pasivo",
        )

    def _resolve_desconocido(
        self,
        allowed: tuple[AccountType, ...],
        codigo: Optional[str] = None,
    ) -> AccountTypeResult:
        if codigo:
            code_type = self._match_code_prefix(codigo)
            if code_type:
                return AccountTypeResult(
                    account_type=code_type,
                    allowed_types=list(allowed),
                    confidence=0.70,
                    method="code_prefix",
                    note=f"Origen desconocido resuelto por código {codigo} → {code_type.value}",
                )
        return AccountTypeResult(
            account_type=AccountType.DESCONOCIDO,
            allowed_types=list(allowed),
            confidence=0.50,
            method="origen_columna",
            note="Origen y código desconocidos",
        )

    @staticmethod
    def _match_code_prefix(codigo: Optional[str]) -> Optional[AccountType]:
        if not codigo:
            return None
        for prefix, atype in AccountTypeResolver._CODE_PREFIX_TYPES.items():
            if codigo.startswith(prefix):
                return atype
        return None
