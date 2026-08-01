"""classification_engine/decision.py — Modelos de decisión y contexto.

Modelos puros del motor de clasificación por cuenta (Sprint 38):

  - `EvidenceSource`: una pieza de evidencia producida por una capa del
    generador de candidatos. Siempre trazable: indica la capa, la fuente de
    conocimiento usada, el código propuesto, el score y el valor que la
    produjo. No hay decisiones "mágicas": todo lo que el motor decide se
    construye sobre estas piezas.
  - `Candidate`: candidato de clasificación (código + nombre) con la lista
    de evidencias que lo sustentan.
  - `RankedCandidate`: candidato ya puntuado y ordenado.
  - `TopNResult`: resultado final del motor (ranking Top N, explicación,
    confianza, fuente de decisión y evidencia completa).
  - `DocumentProcessingContextAdapter`: adapter read-only sobre el contexto
    del documento. Acepta un `DocumentContext` (document_context) o un dict
    plano (para tests sin PDFs). Expone solo lo que el motor necesita
    (family, document_type, layout, extractor_info, perfil, predicción).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Evidencia
# ---------------------------------------------------------------------------


@dataclass
class EvidenceSource:
    """Pieza de evidencia atómica de una capa de clasificación."""

    layer: str
    """Capa que produjo la evidencia (code, catalog_exact, synonyms_exact,
    synonyms_fuzzy, special_rules, context, extractor, profile)."""

    code: Optional[str]
    """Código estándar propuesto (None si la capa no propone código)."""

    score: float = 0.0
    """Confianza de esta evidencia (0-1)."""

    weight: float = 0.0
    """Peso de la capa en la agregación (tomado de WeightConfig)."""

    source: str = ""
    """Fuente de conocimiento: 'catalogo_maestro.json', 'account_synonyms.json',
    'special_account_rules.py', 'DocumentProcessingContext', ..."""

    detail: str = ""
    """Descripción legible de qué generó la evidencia."""

    matched_value: str = ""
    """Valor que produjo la coincidencia (p. ej. el sinónimo matcheado)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "code": self.code,
            "score": round(self.score, 4),
            "weight": round(self.weight, 4),
            "source": self.source,
            "detail": self.detail,
            "matched_value": self.matched_value,
        }

    def __repr__(self) -> str:  # pragma: no cover - depuración
        return (
            f"EvidenceSource(layer={self.layer}, code={self.code}, "
            f"score={self.score:.3f}, weight={self.weight:.3f})"
        )


# ---------------------------------------------------------------------------
# Candidatos
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """Candidato de clasificación con sus evidencias."""

    code: Optional[str]
    name: str = ""
    category: str = ""
    tipo_estado: str = ""
    evidence: list[EvidenceSource] = field(default_factory=list)

    def add_evidence(self, ev: EvidenceSource) -> None:
        self.evidence.append(ev)

    def has_layer(self, layer: str) -> bool:
        return any(e.layer == layer for e in self.evidence)

    def layer_scores(self) -> dict[str, float]:
        """Máximo score por capa para este candidato."""
        out: dict[str, float] = {}
        for e in self.evidence:
            out[e.layer] = max(out.get(e.layer, 0.0), e.score)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "tipo_estado": self.tipo_estado,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    def __repr__(self) -> str:  # pragma: no cover - depuración
        return f"Candidate(code={self.code}, name={self.name!r}, n_evidence={len(self.evidence)})"


@dataclass
class RankedCandidate:
    """Candidato ya puntuado y con posición en el ranking."""

    code: Optional[str]
    name: str = ""
    category: str = ""
    tipo_estado: str = ""
    score: float = 0.0
    confidence: str = "UNKNOWN"
    rank: int = 0
    evidence: list[EvidenceSource] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "tipo_estado": self.tipo_estado,
            "score": round(self.score, 4),
            "confidence": self.confidence,
            "rank": self.rank,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    def __repr__(self) -> str:  # pragma: no cover - depuración
        return f"RankedCandidate(rank={self.rank}, code={self.code}, score={self.score:.3f})"


# ---------------------------------------------------------------------------
# Resultado final
# ---------------------------------------------------------------------------


@dataclass
class ClassificationExplanation:
    """Explicación completa y reconstruible de un resultado."""

    reasons: list[str] = field(default_factory=list)
    confidence_breakdown: dict[str, float] = field(default_factory=dict)
    candidate_explanations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reasons": list(self.reasons),
            "confidence_breakdown": {
                k: round(v, 4) for k, v in self.confidence_breakdown.items()
            },
            "candidate_explanations": self.candidate_explanations,
        }


@dataclass
class TopNResult:
    """Resultado del motor para una cuenta.

    Siempre incluye ranking completo (nunca vacío): si no hay candidatos
    reales se incluye un candidato UNKNOWN (code=None) para que el resultado
    sea reconstruible y auditable.
    """

    account_code: str = ""
    account_name: str = ""
    account_tipo: str = ""
    top_n: list[RankedCandidate] = field(default_factory=list)
    confidence: str = "UNKNOWN"
    decision_source: str = "NONE"
    explanation: Optional[ClassificationExplanation] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def top_code(self) -> Optional[str]:
        return self.top_n[0].code if self.top_n else None

    @property
    def top_score(self) -> float:
        return self.top_n[0].score if self.top_n else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "account_tipo": self.account_tipo,
            "confidence": self.confidence,
            "decision_source": self.decision_source,
            "top_code": self.top_code,
            "top_score": round(self.top_score, 4),
            "top_n": [c.to_dict() for c in self.top_n],
            "explanation": self.explanation.to_dict() if self.explanation else None,
            "timestamp": self.timestamp.isoformat(),
            "extra": dict(self.extra),
        }

    def __repr__(self) -> str:  # pragma: no cover - depuración
        return (
            f"TopNResult({self.account_name!r} -> top={self.top_code} "
            f"({self.confidence}), n={len(self.top_n)})"
        )


# ---------------------------------------------------------------------------
# DocumentProcessingContextAdapter (read-only, desacoplado)
# ---------------------------------------------------------------------------

# Mapas de hint de tipo de estado derivados de los enums de document_intelligence.
# Son data-driven (valores de los enums), no reglas de cuenta hardcodeadas.
_DOCUMENT_TYPE_TO_ESTADO: dict[str, Optional[str]] = {
    "BALANCE_TRIBUTARIO": "balance",
    "BALANCE_GENERAL": "balance",
    "ESTADO_PATRIMONIO": "balance",
    "ESTADO_RESULTADOS": "resultados",
    "ESTADO_FLUJO": None,
    "NOTAS": None,
    "OTRO": None,
}

_FAMILY_TO_ESTADO: dict[str, Optional[str]] = {
    "BALANCE_ESTANDAR": "balance",
    "TRIBUTARIO": "balance",
    "EEFF_AUDITADOS": "balance",
    "BALANCE_SIMPLE": "balance",
    "CLASIFICADO": "balance",
    "CPT_TASACION": "balance",
}


class DocumentProcessingContextAdapter:
    """Adapter read-only del contexto del documento.

    Acepta:
      - un `document_context.DocumentContext` (acceso por atributo), o
      - un dict plano (para tests sin PDFs ni Document Intelligence).

    Expone solo los campos que el motor consume. Nunca modifica el contexto
    original.
    """

    def __init__(self, context: Any = None) -> None:
        self._ctx = context

        die_report = self._read_dict(["die_report"])
        profile = self._read_dict(["die_profile", "profile"])

        self.document_type: Optional[str] = self._first_str(
            self._read(["document_type"]),
            self._read(["classification", "document_type"]),
            self._read(["profile", "document_type"]),
            self._read(["die_report", "classification", "document_type"]),
            self._read(["die_report", "profile", "document_type"]),
        )
        self.family: Optional[str] = self._first_str(
            self._read(["family"]),
            self._read(["family", "family"]),
            self._read(["die_report", "family", "family"]),
            self._read(["die_report", "profile", "family"]),
            profile.get("family"),
        )
        self.template: Optional[str] = self._first_str(
            self._read(["template"]),
            self._read(["die_report", "template", "template_name"]),
            self._read(["die_report", "template", "template_id"]),
        )
        self.layout: Optional[str] = self._first_str(
            self._read(["layout"]),
            self._read(["profile", "layout"]),
            self._read(["die_report", "profile", "layout"]),
        )
        self.column_layout: Optional[str] = self._first_str(
            self._read(["column_layout"]),
            self._read(["structure", "column_layout"]),
        )
        self.selected_parser: Optional[str] = self._first_str(
            self._read(["selected_parser"]),
            self._read(["die_report", "parser", "parser_name"]),
        )

        self.extractor_info: dict[str, Any] = dict(
            self._read_dict(["extractor_info"]) or {}
        )
        if not self.extractor_info:
            self.extractor_info = dict(
                self._read_dict(["die_report", "parser"]) or {}
            )

        self.document_profile: dict[str, Any] = dict(profile)

        self.confidence_expected: float = self._first_float(
            self._read(["confidence_expected"]),
            self._read(["die_report", "confidence", "confidence_pct"]),
        )
        self.coverage_expected: float = self._first_float(
            self._read(["coverage_expected"]),
            self._read(["die_report", "coverage", "coverage_pct"]),
        )

    # ------------------------------------------------------------------
    # Hints derivados
    # ------------------------------------------------------------------

    @property
    def tipo_estado(self) -> Optional[str]:
        """Hint de tipo de estado (balance / resultados) derivado del
        document_type o de la familia. None si no hay señal."""
        dt = (self.document_type or "").upper()
        if dt in _DOCUMENT_TYPE_TO_ESTADO:
            return _DOCUMENT_TYPE_TO_ESTADO[dt]
        fam = (self.family or "").upper()
        return _FAMILY_TO_ESTADO.get(fam)

    @property
    def has_document_context(self) -> bool:
        return bool(
            self.document_type or self.family or self.layout or self.column_layout
        )

    def is_empty(self) -> bool:
        return not self.has_document_context and not self.extractor_info and not self.document_profile

    # ------------------------------------------------------------------
    # Acceso genérico al contexto
    # ------------------------------------------------------------------

    def _read(self, path: list[str]) -> Any:
        """Lee un valor por atributo o por clave de dict."""
        node: Any = self._ctx
        if node is None:
            return None
        for part in path:
            if isinstance(node, dict):
                if part not in node:
                    return None
                node = node[part]
            else:
                if hasattr(node, part):
                    node = getattr(node, part)
                elif hasattr(node, "get_custom"):
                    # DocumentContext guarda die_report y otros datos en
                    # custom_data; el adapter es read-only y nunca escribe.
                    node = node.get_custom(part)
                else:
                    return None
            if node is None:
                return None
        return node

    def _read_dict(self, path: list[str]) -> dict[str, Any]:
        val = self._read(path)
        if isinstance(val, dict):
            return val
        return {}

    @staticmethod
    def _first_str(*values: Any) -> Optional[str]:
        for v in values:
            if v is not None and str(v).strip():
                return str(v)
        return None

    @staticmethod
    def _first_float(*values: Any) -> float:
        for v in values:
            if v is None:
                continue
            try:
                f = float(v)
                return f
            except (TypeError, ValueError):
                continue
        return 0.0
