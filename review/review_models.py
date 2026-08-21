from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingAccount:
    priority: int = 0
    empresa: str = ""
    rut: str = ""
    giro: str = ""
    year: str = ""
    archivo: str = ""
    pagina: int = 0
    codigo_original: str = ""
    nombre_cuenta: str = ""
    activo: float = 0.0
    pasivo: float = 0.0
    patrimonio: float = 0.0
    perdida: float = 0.0
    ganancia: float = 0.0
    monto_original: float = 0.0
    monto_absoluto: float = 0.0
    naturaleza: str = ""
    metodo: str = ""
    confidence: float = 0.0
    learning_hit: bool = False
    semantic_hit: bool = False
    semantic_type: str = ""
    semantic_rule: str = ""
    codigo_sugerido: str = ""
    cuenta_sugerida: str = ""
    frecuencia: int = 1
    cantidad_empresas: int = 1
    ultima_aparicion: str = ""
    observaciones: str = ""
    source_path: str = ""
    source_group: str = ""

    @property
    def score(self) -> float:
        s = 0.0
        if self.metodo == "unknown" or self.metodo in ("unclassified", ""):
            s += 50.0
        if self.confidence < 0.5:
            s += 30.0
        elif self.confidence < 0.85:
            s += 15.0
        s += min(self.frecuencia * 2.0, 20.0)
        s += min(self.cantidad_empresas * 5.0, 25.0)
        if self.semantic_hit:
            s += 10.0
        if self.learning_hit:
            s += 5.0
        return round(s, 1)


@dataclass
class LowConfidenceEntry:
    empresa: str = ""
    cuenta: str = ""
    metodo: str = ""
    confidence: float = 0.0
    clasificacion_actual: str = ""
    semantic_type: str = ""
    learning_hit: bool = False
    codigo_sugerido: str = ""
    source_path: str = ""


@dataclass
class GoldConflict:
    cantidad: int = 0
    empresas: list[str] = field(default_factory=list)
    historial: list[str] = field(default_factory=list)
    account_name: str = ""
    codes: list[str] = field(default_factory=list)


@dataclass
class ProposedRule:
    priority: int = 0
    patron: str = ""
    frecuencia: int = 0
    empresas: int = 0
    codigo_sugerido: str = ""
    confianza: float = 0.0
    cluster_id: str = ""
    action: str = ""


@dataclass
class SynonymEntry:
    canonical: str = ""
    synonym: str = ""
    frecuencia: int = 0
    source_label: str = ""


@dataclass
class GoldProposal:
    cuenta: str = ""
    codigo: str = ""
    empresas: str = ""
    uso: int = 0
    confianza: float = 0.0
    comments: str = ""


@dataclass
class DashboardMetrics:
    total_cuentas: int = 0
    clasificadas: int = 0
    unknown: int = 0
    learning: int = 0
    semantic: int = 0
    codigo: int = 0
    diccionario: int = 0
    cobertura_pct: float = 0.0
    confianza_promedio: float = 0.0
    top_empresas: list[tuple[str, int]] = field(default_factory=list)
    top_cuentas: list[tuple[str, int]] = field(default_factory=list)
    top_montos: list[tuple[str, float]] = field(default_factory=list)
    top_reglas: list[tuple[str, int]] = field(default_factory=list)


PENDING_COLUMNS: list[str] = [
    "Prioridad", "Empresa", "RUT Empresa", "Giro", "Año",
    "Archivo", "Página", "Código Original", "Nombre Cuenta Original",
    "Activo", "Pasivo", "Patrimonio", "Pérdida", "Ganancia",
    "Monto Original", "Monto Absoluto", "Naturaleza", "Método utilizado",
    "Confidence", "Learning Hit", "Semantic Hit", "Semantic Type",
    "Semantic Rule", "Código sugerido", "Cuenta sugerida",
    "Frecuencia", "Cantidad Empresas", "Última aparición",
    "Observaciones automáticas",
    "Código Final", "Nombre Final", "Clase", "Subclase", "Rubro",
    "Subrubro", "Tipo Semántico", "Contra Cuenta", "Aprender",
    "Alcance", "Justificación", "Observaciones",
]

PENDING_EDITABLE: list[str] = [
    "Código Final", "Nombre Final", "Clase", "Subclase", "Rubro",
    "Subrubro", "Tipo Semántico", "Contra Cuenta", "Aprender",
    "Alcance", "Justificación", "Observaciones",
]

PENDING_READONLY: list[str] = [
    c for c in PENDING_COLUMNS if c not in PENDING_EDITABLE
]

CLASE_VALUES: list[str] = [
    "", "Activo", "Pasivo", "Patrimonio", "Ingreso", "Gasto",
]

SEMANTIC_TYPE_VALUES: list[str] = [
    "", "asset", "liability", "contra_asset", "contra_liability",
    "equity", "expense", "revenue",
]

APRENDER_VALUES: list[str] = ["", "Sí", "No"]

CONTRA_CUENTA_VALUES: list[str] = ["", "Sí", "No"]

ALCANCE_VALUES: list[str] = ["", "Global", "Empresa", "ERP"]


def account_to_pending(a: dict, freq: int = 1, num_empresas: int = 1) -> PendingAccount:
    semantic = a.get("semantic_result", {}) or {}
    amounts = a.get("classification_amount", 0.0) or 0.0
    return PendingAccount(
        empresa=a.get("source_group", ""),
        archivo=a.get("source_file", ""),
        pagina=a.get("source_page", 0) or 0,
        codigo_original=a.get("account_code", ""),
        nombre_cuenta=a.get("account_name", ""),
        monto_original=amounts,
        monto_absoluto=abs(amounts),
        naturaleza=a.get("nature", ""),
        metodo=a.get("method", "unknown"),
        confidence=a.get("confidence", 0.0) or 0.0,
        semantic_hit=semantic.get("semantic_type", "unknown") != "unknown",
        semantic_type=semantic.get("semantic_type", ""),
        semantic_rule=semantic.get("matched_rule", ""),
        codigo_sugerido=a.get("standard_code", "") or a.get("final_code", "") or "",
        frecuencia=freq,
        cantidad_empresas=num_empresas,
        source_path=a.get("source_path", ""),
        source_group=a.get("source_group", ""),
        observaciones=a.get("reason", ""),
    )
