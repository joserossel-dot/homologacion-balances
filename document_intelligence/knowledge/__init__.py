"""Document Knowledge Base (DKB) — Sprint 32.

Base de conocimiento de formatos documentales:

  - fingerprint.py      DocumentFingerprint (huella determinística)
  - document_profile.py DocumentProfile (perfil persistente)
  - matcher.py          Matcher + MatchResult (similitud 0-100, ranking Top 5)
  - clustering.py       Cluster + cluster_fingerprints (agrupación automática)
  - repository.py       DocumentKnowledgeBase (persistencia JSON + búsquedas)
  - statistics.py       Métricas agregadas

Uso rápido:

    from document_intelligence.knowledge import (
        DocumentFingerprint, DocumentKnowledgeBase, Matcher,
    )

    kb = DocumentKnowledgeBase("knowledge_base/document_kb.json")
    kb.load()
    fp = DocumentFingerprint.build(signature, lines)
    result = Matcher().match(fp, kb.profiles)
    print(result.matched_profile, result.similarity)
"""

from __future__ import annotations

from .document_profile import DocumentProfile
from .fingerprint import DocumentFingerprint
from .matcher import MatchResult, Matcher, compute_similarity
from .clustering import Cluster, build_centroid, cluster_fingerprints
from .repository import DocumentKnowledgeBase
from .statistics import compute_statistics

__all__ = [
    "DocumentFingerprint",
    "DocumentProfile",
    "Matcher",
    "MatchResult",
    "compute_similarity",
    "Cluster",
    "build_centroid",
    "cluster_fingerprints",
    "DocumentKnowledgeBase",
    "compute_statistics",
]
