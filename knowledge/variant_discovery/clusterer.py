from __future__ import annotations
import re
from collections import Counter, defaultdict
from typing import Any, Optional

from knowledge.normalizer import Normalizer


STOPWORDS = {
    "de", "del", "la", "las", "los", "el", "y", "e", "con",
    "para", "por", "al", "en", "un", "una", "a", "su", "o",
    "que", "es", "se",
}


def _first_token(name: str, normalizer: Normalizer) -> str:
    norm = normalizer.normalize(name).text
    tokens = [t for t in norm.split()
              if t not in STOPWORDS and len(t) > 1]
    return tokens[0] if tokens else "__empty__"


class VariantCluster:
    __slots__ = ("id", "members", "frecuencia", "empresas", "documentos",
                 "monto_acumulado", "suggested_concept", "confidence")

    def __init__(self, cluster_id: str):
        self.id = cluster_id
        self.members: list[str] = []
        self.frecuencia: int = 0
        self.empresas: set[str] = set()
        self.documentos: set[str] = set()
        self.monto_acumulado: float = 0.0
        self.suggested_concept: str = ""
        self.confidence: float = 0.0

    def add_member(self, name: str, freq: int = 1, empresa: str = "",
                   documento: str = "", monto: float = 0.0) -> None:
        if name not in self.members:
            self.members.append(name)
        self.frecuencia += freq
        if empresa:
            self.empresas.add(empresa)
        if documento:
            self.documentos.add(documento)
        self.monto_acumulado += monto

    @property
    def n_members(self) -> int:
        return len(self.members)

    @property
    def n_empresas(self) -> int:
        return len(self.empresas)

    @property
    def n_documentos(self) -> int:
        return len(self.documentos)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "n_members": self.n_members,
            "members": self.members,
            "frecuencia": self.frecuencia,
            "n_empresas": self.n_empresas,
            "empresas": sorted(self.empresas),
            "n_documentos": self.n_documentos,
            "documentos": sorted(self.documentos),
            "monto_acumulado": round(self.monto_acumulado, 2),
            "suggested_concept": self.suggested_concept,
            "confidence": self.confidence,
        }


class VariantClusterer:
    def __init__(self, threshold: float = 0.60):
        from knowledge.variant_discovery.similarity import MultiMetricScorer
        self.scorer = MultiMetricScorer()
        self.normalizer = Normalizer()
        self.threshold = threshold
        self.clusters: list[VariantCluster] = []
        self._cluster_map: dict[str, int] = {}

    def _bucket_key(self, name: str) -> str:
        norm = self.normalizer.normalize(name).text
        tokens = [t for t in norm.split()
                  if t not in STOPWORDS and len(t) > 1]
        return tokens[0] if tokens else "__empty__"

    def cluster(self, accounts: list[dict]) -> list[VariantCluster]:
        self.clusters = []
        self._cluster_map = {}

        # 1) Sort by frequency descending
        sorted_accounts = sorted(
            accounts,
            key=lambda x: -x.get("frecuencia", x.get("frequency", 0)),
        )

        # 2) Bucket by first token
        buckets: dict[str, list[dict]] = defaultdict(list)
        for acct in sorted_accounts:
            name = acct.get("account_name", acct.get("cuenta", ""))
            bk = self._bucket_key(name)
            buckets[bk].append(acct)

        # 3) Cluster within each bucket (small groups = fast)
        for bk, group in buckets.items():
            self._cluster_bucket(group)

        return self.clusters

    def _cluster_bucket(self, accounts: list[dict]) -> None:
        bucket_clusters: list[VariantCluster] = []
        for acct in accounts:
            name = acct.get("account_name", acct.get("cuenta", ""))
            freq = acct.get("frecuencia", acct.get("frequency", 1))
            empresa = acct.get("source_file", acct.get("empresa", acct.get("Documento", "")))
            documento = acct.get("source_path", acct.get("documento", empresa))
            monto = float(acct.get("classification_amount", acct.get("monto", 0.0)))

            matched = False
            for c in bucket_clusters:
                rep = c.members[0]
                eq, score = self.scorer.are_equivalent(name, rep, self.threshold)
                if eq:
                    c.add_member(name, freq, empresa, documento, monto)
                    self._cluster_map[name] = self.clusters.index(c)
                    matched = True
                    break

            if not matched:
                cid = f"VC{len(self.clusters):05d}"
                c = VariantCluster(cid)
                c.add_member(name, freq, empresa, documento, monto)
                self.clusters.append(c)
                self._cluster_map[name] = len(self.clusters) - 1
                bucket_clusters.append(c)

    def compute_confidences(self) -> None:
        for c in self.clusters:
            score = (0.3 + 0.1 * min(c.n_members, 5)
                     + 0.1 * min(c.n_empresas, 5)
                     + 0.1 * min(c.frecuencia / 10, 3))
            c.confidence = round(min(1.0, score), 4)

    def suggest_concepts(self, concept_db: list[dict]) -> None:
        from rapidfuzz import fuzz as rf
        from knowledge.normalizer import Normalizer
        nz = Normalizer()

        # Pre-normalize all concept entries
        concept_rows: list[tuple[str, str, str]] = []
        for con in concept_db:
            concept_rows.append((con["codigo"], con["nombre"],
                                 nz.normalize(con["nombre"]).text))
            for var in con.get("variantes", [])[:20]:
                concept_rows.append((con["codigo"], con["nombre"],
                                     nz.normalize(var).text))

        for c in self.clusters:
            rep = c.members[0]
            rep_norm = nz.normalize(rep).text
            best_code = ""
            best_score = 0.0
            best_name = ""

            for code, cname, target_norm in concept_rows:
                if not target_norm:
                    continue
                score = 1.0 if rep_norm == target_norm else (
                    rf.token_sort_ratio(rep_norm, target_norm) / 100.0
                )
                if score > best_score:
                    best_score = score
                    best_code = code
                    best_name = cname

            c.suggested_concept = f"{best_code} — {best_name}" if best_code else "SIN CONCEPTO"
            c.confidence = round(max(c.confidence, best_score), 4)

    def get_singletons(self) -> list[VariantCluster]:
        return [c for c in self.clusters if c.n_members == 1]

    def get_multi_member(self) -> list[VariantCluster]:
        return [c for c in self.clusters if c.n_members >= 2]

    def get_multi_member_count(self) -> int:
        return sum(1 for c in self.clusters if c.n_members >= 2)
