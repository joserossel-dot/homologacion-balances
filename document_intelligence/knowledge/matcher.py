"""Matcher determinístico de fingerprints contra perfiles de la DKB.

NO usa IA: calcula una similitud ponderada 0–100 entre el fingerprint de un
documento y los fingerprints almacenados en la DKB.

Dimensiones y pesos:

  layout         0.15
  columns        0.15
  headers        0.10
  code           0.10
  numeric        0.10
  company        0.10
  document       0.10
  totals         0.05
  density        0.10
  partial_hash   0.05
                 ----
                 1.00
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .document_profile import DocumentProfile
from .fingerprint import DocumentFingerprint

WEIGHTS: dict[str, float] = {
    "layout": 0.15,
    "columns": 0.15,
    "headers": 0.10,
    "code": 0.10,
    "numeric": 0.10,
    "company": 0.10,
    "document": 0.10,
    "totals": 0.05,
    "density": 0.10,
    "partial_hash": 0.05,
}


@dataclass
class MatchResult:
    """Resultado del matching de un fingerprint contra la DKB."""

    matched_profile: Optional[DocumentProfile]
    similarity: float  # 0-100
    matched_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    differences: list[str] = field(default_factory=list)
    ranking: list[tuple[DocumentProfile, float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers de comparación
# ---------------------------------------------------------------------------

def _jaccard(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0  # ambos vacíos → neutro alto
    if not a or not b:
        return 0.5  # uno vacío → neutro
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb)


def _norm(s: str) -> str:
    return s.lower().strip().replace("  ", " ")


def _dim_scores(
    query: DocumentFingerprint,
    profile: DocumentProfile,
    company: str = "",
) -> dict[str, tuple[float, bool, str]]:
    """Score (0-1), is_missing, nota por dimensión."""
    pf = profile.fingerprint
    scores: dict[str, tuple[float, bool, str]] = {}

    # layout
    missing = query.layout in ("", "DESCONOCIDO") or pf.layout in ("", "DESCONOCIDO")
    scores["layout"] = (
        (1.0 if query.layout == pf.layout else 0.0),
        missing,
        f"layout: {query.layout} vs {pf.layout}",
    )

    # columns
    qc = set(query.column_names)
    pc = set(pf.column_names)
    col_missing = (not qc) or (not pc)
    scores["columns"] = (
        _jaccard(query.column_names, pf.column_names),
        col_missing,
        f"columnas: {len(qc)} vs {len(pc)}",
    )

    # headers
    hdr_missing = (not query.header_keywords) or (not pf.header_keywords)
    scores["headers"] = (
        _jaccard(query.header_keywords, pf.header_keywords),
        hdr_missing,
        f"headers: {len(set(query.header_keywords) & set(pf.header_keywords))} "
        f"comunes de {max(len(set(query.header_keywords)), 1)}",
    )

    # code
    code_missing = query.code_pattern in ("", "DESCONOCIDO") or pf.code_pattern in ("", "DESCONOCIDO")
    scores["code"] = (
        (1.0 if query.code_pattern == pf.code_pattern else 0.0),
        code_missing,
        f"código: {query.code_pattern} vs {pf.code_pattern}",
    )

    # numeric
    num_missing = query.numeric_pattern in ("", "DESCONOCIDO") or pf.numeric_pattern in ("", "DESCONOCIDO")
    scores["numeric"] = (
        (1.0 if query.numeric_pattern == pf.numeric_pattern else 0.0),
        num_missing,
        f"numérico: {query.numeric_pattern} vs {pf.numeric_pattern}",
    )

    # company
    q_company = _norm(company)
    p_company = _norm(profile.company)
    comp_missing = (not q_company) or (not p_company)
    if not comp_missing and q_company != p_company:
        variants = [_norm(v) for v in profile.known_variants]
        comp_match = q_company in variants
    else:
        comp_match = q_company == p_company
    scores["company"] = (
        (1.0 if comp_match else 0.0),
        comp_missing,
        f"empresa: '{company}' vs '{profile.company}'",
    )

    # document
    doc_missing = query.document_type in ("", "OTRO", "DESCONOCIDO") or pf.document_type in ("", "OTRO", "DESCONOCIDO")
    scores["document"] = (
        (1.0 if query.document_type == pf.document_type else 0.0),
        doc_missing,
        f"documento: {query.document_type} vs {pf.document_type}",
    )

    # totals
    q_has = query.total_patterns > 0 or query.summary_position != "NONE"
    p_has = pf.total_patterns > 0 or pf.summary_position != "NONE"
    tot_missing = (query.summary_position == "NONE" and query.total_patterns == 0) or (
        pf.summary_position == "NONE" and pf.total_patterns == 0
    )
    scores["totals"] = (
        (1.0 if q_has == p_has else 0.0),
        tot_missing,
        f"totales: {query.summary_position} vs {pf.summary_position}",
    )

    # density (promedio de desviación normalizada)
    density_sims = []
    for dim in ("table", "text", "numeric"):
        qv = getattr(query, f"{dim}_density")
        pv = getattr(pf, f"{dim}_density")
        density_sims.append(1.0 - min(1.0, abs(qv - pv)))
    density_score = sum(density_sims) / len(density_sims)
    scores["density"] = (
        density_score,
        False,
        f"densidad: tabla {query.table_density:.2f}/{pf.table_density:.2f} "
        f"texto {query.text_density:.2f}/{pf.text_density:.2f} "
        f"numérica {query.numeric_density:.2f}/{pf.numeric_density:.2f}",
    )

    # partial hash (estructura estable)
    hash_equal = bool(query.signature_hash and query.signature_hash == pf.signature_hash)
    hash_missing = (not query.signature_hash) or (not pf.signature_hash)
    scores["partial_hash"] = (
        (1.0 if hash_equal else 0.0),
        hash_missing,
        f"hash: {'igual' if hash_equal else 'distinto'}",
    )

    return scores


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def compute_similarity(
    query: DocumentFingerprint,
    profile: DocumentProfile,
    company: str = "",
) -> dict:
    """Similitud ponderada (0-100) entre query y profile."""
    dims = _dim_scores(query, profile, company)
    total = 0.0
    matched: list[str] = []
    missing: list[str] = []
    differences: list[str] = []

    for dim, weight in WEIGHTS.items():
        score, is_missing, note = dims[dim]
        total += weight * score
        if is_missing:
            missing.append(dim)
        elif score >= 0.95:
            matched.append(dim)
        elif score < 1.0:
            differences.append(note)

    return {
        "similarity": round(total * 100, 2),
        "matched_fields": matched,
        "missing_fields": missing,
        "differences": differences,
        "dimensions": {k: round(v[0], 3) for k, v in dims.items()},
    }


class Matcher:
    """Busca el perfil más similar a un fingerprint en la DKB."""

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self.weights = dict(weights or WEIGHTS)

    def similarity(
        self,
        query: DocumentFingerprint,
        profile: DocumentProfile,
        company: str = "",
    ) -> dict:
        return compute_similarity(query, profile, company)

    def match(
        self,
        query: DocumentFingerprint,
        profiles: list[DocumentProfile],
        company: str = "",
        top_n: int = 5,
    ) -> MatchResult:
        """Encuentra el mejor perfil y construye el ranking Top N."""
        scored: list[tuple[DocumentProfile, dict]] = []
        for profile in profiles:
            info = compute_similarity(query, profile, company)
            scored.append((profile, info))

        scored.sort(key=lambda t: t[1]["similarity"], reverse=True)

        ranking = [
            (profile, info["similarity"]) for profile, info in scored[:top_n]
        ]

        if not scored or scored[0][1]["similarity"] <= 0.0:
            return MatchResult(
                matched_profile=None,
                similarity=0.0,
                matched_fields=[],
                missing_fields=[],
                differences=[],
                ranking=ranking,
            )

        best_profile, best_info = scored[0]
        return MatchResult(
            matched_profile=best_profile,
            similarity=best_info["similarity"],
            matched_fields=best_info["matched_fields"],
            missing_fields=best_info["missing_fields"],
            differences=best_info["differences"],
            ranking=ranking,
        )
