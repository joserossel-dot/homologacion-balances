"""AccountTypeResolver — determina el tipo de cuenta universal permitido.

Responsabilidad única: dado origen_columna + layout detectado + reglas contables,
determinar el universo de tipos de cuenta válidos para cada cuenta.

NO clasifica. NO usa regex. NO usa fuzzy matching. NO usa CMCC.

Output: AccountType (ACTIVO | PASIVO | PATRIMONIO | PERDIDA | GANANCIA | DESCONOCIDO)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from parser_universal import OrigenColumna


class AccountType(str, Enum):
    ACTIVO = "ACTIVO"
    PASIVO = "PASIVO"
    PATRIMONIO = "PATRIMONIO"
    PERDIDA = "PERDIDA"
    GANANCIA = "GANANCIA"
    DESCONOCIDO = "DESCONOCIDO"


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
