"""Matriz de similitud fingerprint a fingerprint (Sprint 33).

SimilarityMatrix: matriz NxN entre todos los documentos del universo DKB,
guardando únicamente los Top-K vecinos por documento para evitar consumo
excesivo de memoria/almacenamiento.

Similitud usada: fingerprint puro (SIN empresa y SIN nombre de archivo),
normalizada por las dimensiones comparables de cada par.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..knowledge.document_profile import DocumentProfile
from ..knowledge.fingerprint import DocumentFingerprint
from ..knowledge.matcher import _dim_scores

# Pesos SIN dimensión empresa (solo fingerprint), normalizados a 1.0.
FINGERPRINT_WEIGHTS: dict[str, float] = {
    "layout": 0.18,
    "columns": 0.18,
    "headers": 0.10,
    "code": 0.11,
    "numeric": 0.11,
    "document": 0.10,
    "totals": 0.06,
    "density": 0.11,
    "partial_hash": 0.05,
}

SimilarityFn = Callable[[DocumentFingerprint, DocumentFingerprint], float]


def fingerprint_similarity(
    a: DocumentFingerprint,
    b: DocumentFingerprint,
) -> float:
    """Similitud 0-100 entre DOS fingerprints (sin empresa).

    Reutiliza las dimensiones del matcher de la DKB, pero:
      - excluye la dimensión 'company'
      - usa el HASH ESTRUCTURAL (partial_hash: layout/orientación/
        columnas/tipo/patrones) en lugar del signature_hash completo,
        que además incluye nº de páginas y densidades — así dos
        documentos del mismo formato con distinto largo (años/páginas)
        no se separan artificialmente
      - normaliza por las dimensiones efectivamente comparables
        (si ambas son 'DESCONOCIDO'/vacías, esa dimensión no penaliza)
    """
    shadow = DocumentProfile(
        id="__mining__", name="", company="", family="", description="",
        fingerprint=b,
    )
    dims = _dim_scores(a, shadow, company="")

    # Dimensión partial_hash: comparación estructural (independiente de
    # páginas y densidades), robusta frente a hashes desactualizados.
    a_struct = a.partial_hash()
    b_struct = b.partial_hash()
    dims["partial_hash"] = (
        1.0 if a_struct == b_struct else 0.0,
        (not a_struct) or (not b_struct),
        f"hash estructural: {'igual' if a_struct == b_struct else 'distinto'}",
    )

    total_w = 0.0
    score = 0.0
    for dim, weight in FINGERPRINT_WEIGHTS.items():
        s, is_missing, _ = dims[dim]
        if is_missing:
            continue
        total_w += weight
        score += weight * s

    if total_w <= 0.0:
        return 0.0
    return round(score / total_w * 100.0, 2)


# ---------------------------------------------------------------------------
# Documento del universo DKB
# ---------------------------------------------------------------------------

@dataclass
class DocumentRecord:
    """Documento del universo DKB con su fingerprint real (extraído del PDF)."""

    id: str
    file: str
    company: str
    family: str
    extractor: str
    document_type: str
    fingerprint: DocumentFingerprint

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file": self.file,
            "company": self.company,
            "family": self.family,
            "extractor": self.extractor,
            "document_type": self.document_type,
            "fingerprint": self.fingerprint.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentRecord":
        return cls(
            id=data["id"],
            file=data.get("file", data["id"]),
            company=data.get("company", ""),
            family=data.get("family", "DESCONOCIDO"),
            extractor=data.get("extractor", "UNKNOWN"),
            document_type=data.get("document_type", "OTRO"),
            fingerprint=DocumentFingerprint.from_dict(data.get("fingerprint", {})),
        )


# ---------------------------------------------------------------------------
# Matriz NxN con Top-K vecinos
# ---------------------------------------------------------------------------

@dataclass
class SimilarityMatrix:
    """Resultado de la matriz NxN (Top-K vecinos por documento)."""

    records: list[DocumentRecord] = field(default_factory=list)
    neighbors: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    top_k: int = 5
    pairs_computed: int = 0
    mean_similarity: float = 0.0

    def index_of(self, doc_id: str) -> int:
        for i, r in enumerate(self.records):
            if r.id == doc_id:
                return i
        raise KeyError(doc_id)

    def pair_similarity(self, id_a: str, id_b: str) -> Optional[float]:
        """Similitud A-B si están dentro del Top-K de A."""
        for other, sim in self.neighbors.get(id_a, []):
            if other == id_b:
                return sim
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "top_k": self.top_k,
            "pairs_computed": self.pairs_computed,
            "mean_similarity": self.mean_similarity,
            "records": [r.to_dict() for r in self.records],
            "neighbors": {
                doc_id: [{"id": other, "similarity": sim} for other, sim in nbrs]
                for doc_id, nbrs in self.neighbors.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimilarityMatrix":
        records = [DocumentRecord.from_dict(r) for r in data.get("records", [])]
        neighbors = {
            doc_id: [(n["id"], n["similarity"]) for n in nbrs]
            for doc_id, nbrs in data.get("neighbors", {}).items()
        }
        return cls(
            records=records,
            neighbors=neighbors,
            top_k=data.get("top_k", 5),
            pairs_computed=data.get("pairs_computed", 0),
            mean_similarity=data.get("mean_similarity", 0.0),
        )

    def to_summary_rows(self) -> list[dict[str, Any]]:
        """Una fila por documento → similarity_summary.csv."""
        rows = []
        for r in self.records:
            nbrs = self.neighbors.get(r.id, [])
            top1 = nbrs[0] if nbrs else ("", 0.0)
            mean_topk = (
                sum(s for _, s in nbrs) / len(nbrs) if nbrs else 0.0
            )
            rows.append({
                "doc_id": r.id,
                "file": r.file,
                "company": r.company,
                "n_neighbors": len(nbrs),
                "top1_neighbor": top1[0],
                "top1_similarity": top1[1],
                "mean_similarity_topk": round(mean_topk, 2),
                "pairs_computed": self.pairs_computed,
            })
        return rows


def _push(best: list[tuple[float, int]], item: tuple[float, int], top_k: int) -> None:
    """Mantiene los top-k pares ordenados en `best`."""
    best.append(item)
    best.sort(key=lambda t: (-t[0], t[1]))
    if len(best) > top_k:
        del best[top_k:]


def build_similarity_matrix(
    records: list[DocumentRecord],
    top_k: int = 5,
    similarity_fn: Optional[SimilarityFn] = None,
) -> SimilarityMatrix:
    """Construye la matriz NxN entre todos los documentos.

    Compara CADA par (i<j) una sola vez y mantiene los Top-K vecinos de
    cada documento. Determinístico: la similitud no depende del orden.
    """
    sim_fn = similarity_fn or fingerprint_similarity
    n = len(records)
    best: dict[int, list[tuple[float, int]]] = {i: [] for i in range(n)}

    pairs = 0
    total = 0.0
    for i in range(n):
        fi = records[i].fingerprint
        for j in range(i + 1, n):
            s = sim_fn(fi, records[j].fingerprint)
            pairs += 1
            total += s
            _push(best[i], (s, j), top_k)
            _push(best[j], (s, i), top_k)

    neighbors: dict[str, list[tuple[str, float]]] = {}
    for i in range(n):
        best[i].sort(reverse=True)
        neighbors[records[i].id] = [
            (records[j].id, s) for s, j in best[i]
        ]

    return SimilarityMatrix(
        records=records,
        neighbors=neighbors,
        top_k=top_k,
        pairs_computed=pairs,
        mean_similarity=round(total / max(pairs, 1), 2),
    )

