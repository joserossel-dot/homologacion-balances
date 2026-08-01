"""Estadísticas de la DKB.

Funciones puras que computan las métricas agregadas de una lista de
DocumentProfile (usadas por el repositorio y por el report builder).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .document_profile import DocumentProfile


def compute_statistics(profiles: list[DocumentProfile]) -> dict[str, Any]:
    """Métricas agregadas sobre la lista de perfiles."""
    total_profiles = len(profiles)
    total_variants = sum(len(p.known_variants) for p in profiles)
    total_documents = sum(p.times_seen for p in profiles)

    companies = Counter()
    families = Counter()
    layouts = Counter()
    code_patterns = Counter()
    numeric_patterns = Counter()
    extractors = Counter()

    for p in profiles:
        company = (p.company or "DESCONOCIDO").strip() or "DESCONOCIDO"
        companies[company] += p.times_seen
        families[p.family] += p.times_seen
        layouts[p.fingerprint.layout] += p.times_seen
        code_patterns[p.fingerprint.code_pattern] += p.times_seen
        numeric_patterns[p.fingerprint.numeric_pattern] += p.times_seen
        extractors[p.recommended_extractor] += p.times_seen

    # Formatos únicos (por hash de identidad) y repetidos.
    hash_counts = Counter(p.fingerprint.signature_hash for p in profiles)
    repeated = [
        {
            "signature_hash": h,
            "times_seen": n,
            "profiles": [
                p.name for p in profiles if p.fingerprint.signature_hash == h
            ],
        }
        for h, n in hash_counts.items() if n > 1
    ]
    repeated.sort(key=lambda r: r["times_seen"], reverse=True)

    unknown_formats = [
        p.to_dict() for p in profiles if p.family == "DESCONOCIDO"
    ]

    return {
        "total_profiles": total_profiles,
        "total_variants": total_variants,
        "total_documents": total_documents,
        "top_companies": _top(companies, 10),
        "top_families": _top(families, 10),
        "layout_distribution": dict(layouts),
        "code_pattern_distribution": dict(code_patterns),
        "numeric_pattern_distribution": dict(numeric_patterns),
        "extractor_distribution": dict(extractors),
        "repeated_fingerprints": repeated,
        "unique_formats": len(hash_counts),
        "unknown_formats_count": len(unknown_formats),
        "unknown_formats": unknown_formats,
        "avg_confidence": round(
            sum(p.confidence for p in profiles) / max(total_profiles, 1), 4
        ),
    }


def _top(counter: Counter, n: int) -> list[dict[str, Any]]:
    return [{"name": k, "count": v} for k, v in counter.most_common(n)]
