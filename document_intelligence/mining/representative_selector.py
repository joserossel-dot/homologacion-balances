"""Selección del mejor documento representante por familia (Sprint 33).

El representante de una familia es el documento con MAYOR similitud
promedio respecto al resto del cluster (el "típico" del formato).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from .family_detector import DocumentFamily
from .similarity_matrix import SimilarityFn, fingerprint_similarity


@dataclass
class Representative:
    """Documento elegido para representar a una familia."""

    family_id: str
    document_id: str
    file: str
    avg_similarity: float
    n_documents: int
    company: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "document_id": self.document_id,
            "file": self.file,
            "avg_similarity": self.avg_similarity,
            "n_documents": self.n_documents,
            "company": self.company,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Representative":
        return cls(
            family_id=data["family_id"],
            document_id=data["document_id"],
            file=data.get("file", data["document_id"]),
            avg_similarity=data.get("avg_similarity", 0.0),
            n_documents=data.get("n_documents", 0),
            company=data.get("company", ""),
        )


def _within_family_scores(
    records,
    sim_fn: SimilarityFn,
) -> dict[int, dict[int, float]]:
    """Matriz de similitud intra-familia (índices → índice → similitud)."""
    n = len(records)
    mat: dict[int, dict[int, float]] = {i: {} for i in range(n)}
    for i in range(n):
        fi = records[i].fingerprint
        for j in range(i + 1, n):
            s = sim_fn(fi, records[j].fingerprint)
            mat[i][j] = s
            mat[j][i] = s
    return mat


def select_representatives(
    families: list[DocumentFamily],
    similarity_fn: Optional[SimilarityFn] = None,
) -> list[Representative]:
    """Un representante por familia: el documento con mayor similitud
    promedio al resto del cluster.

    Tie-break determinístico: el archivo con nombre menor.
    """
    sim_fn = similarity_fn or fingerprint_similarity
    reps: list[Representative] = []

    for family in families:
        docs = sorted(family.documents, key=lambda d: d.id)
        n = len(docs)

        if n <= 1:
            avg = family.avg_similarity
            chosen = docs[0] if docs else None
        else:
            mat = _within_family_scores(docs, sim_fn)
            best_idx = 0
            best_avg = -1.0
            for i in range(n):
                scores = mat[i]
                if not scores:
                    continue
                avg_i = sum(scores.values()) / len(scores)
                if avg_i > best_avg:
                    best_avg = avg_i
                    best_idx = i
            chosen = docs[best_idx]
            avg = round(best_avg, 2)

        if chosen is None:
            continue

        reps.append(Representative(
            family_id=family.id,
            document_id=chosen.id,
            file=chosen.file,
            avg_similarity=avg,
            n_documents=n,
            company=chosen.company,
        ))

    return reps
