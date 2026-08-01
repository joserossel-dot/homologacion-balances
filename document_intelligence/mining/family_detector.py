"""Descubrimiento automático de familias documentales (Sprint 33).

Familia = cluster de fingerprints descubierto SIN usar la empresa ni el
nombre del PDF. Solo estructura del documento (fingerprint).

Cada familia contiene:

  - id
  - cantidad de documentos
  - similitud promedio (intra-familia, 0-100)
  - fingerprint centroide
  - layout dominante
  - columnas dominantes
  - tipo de documento dominante
  - patrón de códigos dominante
  - patrón numérico dominante
  - confianza (similitud promedio normalizada 0-1)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..knowledge import cluster_fingerprints
from ..knowledge.fingerprint import DocumentFingerprint
from .similarity_matrix import (
    DocumentRecord,
    SimilarityFn,
    fingerprint_similarity,
)


def _dominant(values: list[str], fallback: str = "DESCONOCIDO") -> str:
    counts = Counter(v for v in values if v)
    if not counts:
        return fallback
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def _dominant_list(values: list[str], limit: int = 6) -> list[str]:
    counts = Counter(values)
    return [name for name, _ in counts.most_common(limit)]


@dataclass
class DocumentFamily:
    """Familia descubierta por fingerprint (sin empresa/nombre de archivo)."""

    id: str
    documents: list[DocumentRecord] = field(default_factory=list)
    count: int = 0
    avg_similarity: float = 100.0
    centroid: Optional[DocumentFingerprint] = None
    dominant_layout: str = "DESCONOCIDO"
    dominant_columns: list[str] = field(default_factory=list)
    dominant_document_type: str = "OTRO"
    dominant_code_pattern: str = "DESCONOCIDO"
    dominant_numeric_pattern: str = "DESCONOCIDO"
    confidence: float = 1.0
    companies: list[dict[str, Any]] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    @property
    def top_company(self) -> str:
        if not self.companies:
            return ""
        return self.companies[0].get("name", "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "count": self.count,
            "avg_similarity": self.avg_similarity,
            "confidence": round(self.confidence, 4),
            "centroid": self.centroid.to_dict() if self.centroid else None,
            "dominant_layout": self.dominant_layout,
            "dominant_columns": list(self.dominant_columns),
            "dominant_document_type": self.dominant_document_type,
            "dominant_code_pattern": self.dominant_code_pattern,
            "dominant_numeric_pattern": self.dominant_numeric_pattern,
            "top_company": self.top_company,
            "companies": list(self.companies),
            "documents": [{"id": d.id, "file": d.file} for d in self.documents],
            "files": list(self.files),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentFamily":
        # Los documentos completos no se persisten en el JSON de familias;
        # se reconstruyen con fingerprints vacíos (para tablas/reportes).
        docs = [
            DocumentRecord(
                id=d["id"], file=d.get("file", d["id"]),
                company="", family="", extractor="UNKNOWN", document_type="",
                fingerprint=DocumentFingerprint(),
            )
            for d in data.get("documents", [])
        ]
        centroid_data = data.get("centroid")
        return cls(
            id=data["id"],
            documents=docs,
            count=data.get("count", len(docs)),
            avg_similarity=data.get("avg_similarity", 100.0),
            centroid=(
                DocumentFingerprint.from_dict(centroid_data)
                if centroid_data else None
            ),
            dominant_layout=data.get("dominant_layout", "DESCONOCIDO"),
            dominant_columns=list(data.get("dominant_columns", [])),
            dominant_document_type=data.get("dominant_document_type", "OTRO"),
            dominant_code_pattern=data.get("dominant_code_pattern", "DESCONOCIDO"),
            dominant_numeric_pattern=data.get("dominant_numeric_pattern", "DESCONOCIDO"),
            confidence=data.get("confidence", 1.0),
            companies=list(data.get("companies", [])),
            files=list(data.get("files", [])),
        )


def _pairwise_avg(
    records: list[DocumentRecord],
    sim_fn: SimilarityFn,
) -> float:
    """Similitud promedio dentro de un grupo de documentos."""
    n = len(records)
    if n <= 1:
        return 100.0
    total = 0.0
    pairs = 0
    for i in range(n):
        fi = records[i].fingerprint
        for j in range(i + 1, n):
            total += sim_fn(fi, records[j].fingerprint)
            pairs += 1
    return round(total / max(pairs, 1), 2)


def detect_families(
    records: list[DocumentRecord],
    threshold: float = 70.0,
    similarity_fn: Optional[SimilarityFn] = None,
) -> list[DocumentFamily]:
    """Descubre familias usando SOLO fingerprints (sin empresa/nombre).

    Reutiliza cluster_fingerprints de la DKB con la similitud fingerprint
    a fingerprint (sin empresa).

    Los documentos con fingerprint IDÉNTICO se agrupan ANTES del clustering
    (un representante por huella): así una misma huella nunca se separa en
    dos familias ni un documento queda contado dos veces (p. ej. copias del
    mismo balance en ARCHIVE/HOLDOUT/edge_cases).
    """
    sim_fn = similarity_fn or fingerprint_similarity
    orden = sorted(records, key=lambda r: r.id)

    # Huella idéntica → grupo (mantiene la integridad de cada documento).
    groups: dict[str, list[DocumentRecord]] = {}
    for r in orden:
        groups.setdefault(r.fingerprint.signature_hash, []).append(r)
    representatives = [group[0].fingerprint for group in groups.values()]

    clusters = cluster_fingerprints(
        representatives, threshold=threshold, similarity_fn=sim_fn,
    )
    _ensure_unique_cluster_ids(clusters)

    families: list[DocumentFamily] = []
    for cluster in clusters:
        members: list[DocumentRecord] = []
        for mfp in cluster.members:
            members.extend(groups.get(mfp.signature_hash, []))

        companies = Counter(r.company for r in members)
        companies = [
            {"name": name, "count": n}
            for name, n in companies.most_common(10) if name
        ]

        avg_sim = _pairwise_avg(members, sim_fn)

        families.append(DocumentFamily(
            id=cluster.id,
            documents=members,
            count=len(members),
            avg_similarity=avg_sim,
            centroid=cluster.centroid,
            dominant_layout=_dominant([m.fingerprint.layout for m in members]),
            dominant_columns=_dominant_list([
                name for m in members for name in m.fingerprint.column_names
            ]),
            dominant_document_type=_dominant(
                [m.fingerprint.document_type for m in members], fallback="OTRO",
            ),
            dominant_code_pattern=_dominant(
                [m.fingerprint.code_pattern for m in members],
            ),
            dominant_numeric_pattern=_dominant(
                [m.fingerprint.numeric_pattern for m in members],
            ),
            confidence=round(avg_sim / 100.0, 4),
            companies=companies,
            files=[r.file for r in members],
        ))

    families.sort(key=lambda f: (-f.count, f.id))
    return families


def _ensure_unique_cluster_ids(clusters: list) -> None:
    """Evita ids duplicados cuando dos centroides coinciden por hash."""
    usados: set[str] = set()
    for i, cluster in enumerate(clusters):
        base = cluster.id
        nuevo = base
        contador = 1
        while nuevo in usados:
            nuevo = f"{base}_{contador}"
            contador += 1
        if nuevo != base:
            cluster.id = nuevo
        usados.add(nuevo)
