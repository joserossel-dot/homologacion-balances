"""Clustering determinístico de fingerprints → clusters de formatos.

El agrupador recibe una lista de DocumentFingerprint y descubre grupos
similares usando la misma similitud ponderada del matcher (sin IA).

Salida: lista de Cluster, cada uno con

  - id
  - centroid (fingerprint sintético promedio)
  - members (fingerprints del grupo)
  - common_features (características compartidas por todos)
  - confidence (similitud promedio contra el centroide)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .fingerprint import DocumentFingerprint

SimilarityFn = Callable[[DocumentFingerprint, DocumentFingerprint], float]

DEFAULT_THRESHOLD = 70.0


def _default_similarity(a: DocumentFingerprint, b: DocumentFingerprint) -> float:
    """Similitud fingerprint a fingerprint (sin perfil/empresa)."""
    from .document_profile import DocumentProfile
    from .matcher import compute_similarity

    # Perfil "sombra" para reutilizar compute_similarity con company vacía.
    shadow = DocumentProfile(
        id="__fp__",
        name="",
        company="",
        family="",
        description="",
        fingerprint=b,
    )
    info = compute_similarity(a, shadow, company="")
    return info["similarity"]


@dataclass
class Cluster:
    """Grupo de fingerprints con características comunes."""

    id: str
    centroid: DocumentFingerprint
    members: list[DocumentFingerprint] = field(default_factory=list)
    common_features: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "centroid": self.centroid.to_dict(),
            "members": [m.to_dict() for m in self.members],
            "common_features": dict(self.common_features),
            "confidence": round(self.confidence, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Cluster":
        return cls(
            id=data.get("id", ""),
            centroid=DocumentFingerprint.from_dict(data.get("centroid", {})),
            members=[DocumentFingerprint.from_dict(m) for m in data.get("members", [])],
            common_features=dict(data.get("common_features", {})),
            confidence=data.get("confidence", 0.0),
        )


# ---------------------------------------------------------------------------
# Centroide
# ---------------------------------------------------------------------------

def _most_common(values: list[str], fallback: str = "") -> str:
    counts: dict[str, int] = {}
    for v in values:
        if not v:
            continue
        counts[v] = counts.get(v, 0) + 1
    if not counts:
        return fallback
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def build_centroid(members: list[DocumentFingerprint]) -> DocumentFingerprint:
    """Fingerprint sintético promedio de un grupo."""
    n = len(members)
    c = DocumentFingerprint()

    c.layout = _most_common([m.layout for m in members], fallback="DESCONOCIDO")
    c.orientation = _most_common([m.orientation for m in members], fallback="portrait")
    c.page_count = round(sum(m.page_count for m in members) / n)
    c.document_type = _most_common([m.document_type for m in members], fallback="OTRO")
    c.code_pattern = _most_common([m.code_pattern for m in members], fallback="DESCONOCIDO")
    c.numeric_pattern = _most_common([m.numeric_pattern for m in members], fallback="DESCONOCIDO")
    c.summary_position = _most_common([m.summary_position for m in members], fallback="NONE")

    from collections import Counter
    col_counter: Counter = Counter()
    for m in members:
        col_counter.update(m.column_names)
    c.column_names = [name for name, _ in col_counter.most_common(6)]
    c.column_count = len(c.column_names)

    hdr_counter: Counter = Counter()
    for m in members:
        hdr_counter.update(m.header_keywords)
    c.header_keywords = [k for k, _ in hdr_counter.most_common(8)]

    c.table_density = round(sum(m.table_density for m in members) / n, 4)
    c.text_density = round(sum(m.text_density for m in members) / n, 4)
    c.numeric_density = round(sum(m.numeric_density for m in members) / n, 4)
    c.total_patterns = round(sum(m.total_patterns for m in members) / n)

    c.compute_hash()
    return c


def cluster_common_features(
    members: list[DocumentFingerprint],
) -> dict[str, Any]:
    """Características compartidas por todos los miembros del grupo."""
    common: dict[str, Any] = {}

    for key in ("layout", "orientation", "document_type", "code_pattern",
                "numeric_pattern", "summary_position"):
        values = {getattr(m, key) for m in members}
        if len(values) == 1:
            common[key] = next(iter(values))

    common["page_count"] = round(
        sum(m.page_count for m in members) / max(len(members), 1)
    )
    common["column_count"] = round(
        sum(m.column_count for m in members) / max(len(members), 1)
    )
    common["table_density"] = round(
        sum(m.table_density for m in members) / max(len(members), 1), 3
    )
    return common


def cluster_fingerprints(
    fingerprints: list[DocumentFingerprint],
    threshold: float = DEFAULT_THRESHOLD,
    similarity_fn: Optional[SimilarityFn] = None,
) -> list[Cluster]:
    """Agrupa fingerprints en clusters por similitud ≥ threshold.

    Greedy y determinístico: se procesan en orden y cada fingerprint se
    asigna al cluster cuyo centroide está más cerca (si supera el umbral);
    si no, abre un cluster nuevo.
    """
    sim_fn = similarity_fn or _default_similarity
    clusters: list[Cluster] = []

    for fp in fingerprints:
        best_cluster = None
        best_score = -1.0
        for cluster in clusters:
            score = sim_fn(fp, cluster.centroid)
            if score > best_score:
                best_score = score
                best_cluster = cluster

        if best_cluster is not None and best_score >= threshold:
            best_cluster.members.append(fp)
            best_cluster.centroid = build_centroid(best_cluster.members)
            best_cluster.common_features = cluster_common_features(best_cluster.members)
            scores = [
                sim_fn(m, best_cluster.centroid) for m in best_cluster.members
            ]
            best_cluster.confidence = round(sum(scores) / len(scores), 2)
        else:
            members = [fp]
            centroid = build_centroid(members)
            clusters.append(
                Cluster(
                    id=f"cluster_{uuid.uuid4().hex[:10]}",
                    centroid=centroid,
                    members=members,
                    common_features=cluster_common_features(members),
                    confidence=100.0,
                )
            )

    # Ids determinísticos derivados del hash del centroide.
    for i, cluster in enumerate(clusters):
        cluster.id = "cluster_" + cluster.centroid.signature_hash[:10] or f"cluster_{i}"
    return clusters


def fingerprint_stable_key(fp: DocumentFingerprint) -> str:
    """Clave estable de identidad de formato (para dedupe/contar)."""
    return fp.partial_hash()
