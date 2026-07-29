from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from parser_universal import CuentaRaw


@dataclass
class AccountContext:
    """Contexto estructural completo para una cuenta extraída.

    Provee navegación jerárquica (padre, hijos, hermanos) y secuencial
    (anterior, siguiente), además de metadatos de sección, layout y
    confianza.

    No modifica CuentaRaw. Es una capa de metadata adicional.
    """

    raw: CuentaRaw
    parent: Optional[AccountContext] = None
    children: list[AccountContext] = field(default_factory=list)
    siblings: list[AccountContext] = field(default_factory=list)
    previous_account: Optional[AccountContext] = None
    next_account: Optional[AccountContext] = None
    hierarchy_level: int = 0
    section: str = ""
    layout: list[str] = field(default_factory=list)
    account_type: Optional[str] = None
    path: str = ""
    position: int = 0
    confidence: float = 0.0

    def __repr__(self) -> str:
        return (
            f"AccountContext(codigo={self.raw.codigo!r}, "
            f"nombre={self.raw.nombre!r}, "
            f"level={self.hierarchy_level}, "
            f"section={self.section!r})"
        )
