from __future__ import annotations
import json
from collections import defaultdict
from typing import Optional
from rapidfuzz import fuzz as rapidfuzz_mod
from knowledge.discovery.similarity import SimilarityScorer, AccountNormalizer


class Cluster:
    def __init__(self, cluster_id: str, name: str):
        self.id = cluster_id
        self.name = name
        self.members: list[str] = []
        self.frecuencia: int = 0
        self.empresas: set[str] = set()
        self.confianza: float = 0.0

    def add_member(self, account: str, freq: int = 0, empresa: str = ""):
        if account not in self.members:
            self.members.append(account)
        self.frecuencia += freq
        if empresa:
            self.empresas.add(empresa)

    @property
    def n_members(self) -> int:
        return len(self.members)

    @property
    def n_empresas(self) -> int:
        return len(self.empresas)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'nombre_sugerido': self.name,
            'miembros': self.members,
            'n_variantes': len(self.members),
            'frecuencia': self.frecuencia,
            'n_empresas': len(self.empresas),
            'confianza': self.confianza,
        }


class ClusterEngine:
    def __init__(self, threshold: float = 0.70, stopwords: Optional[set[str]] = None):
        self.scorer = SimilarityScorer(stopwords)
        self.normalizer = AccountNormalizer(stopwords)
        self.threshold = threshold
        self.clusters: list[Cluster] = []
        self.singletons: list[str] = []

    def build_clusters(self, names_freq: list[tuple[str, int, str]],
                       min_cluster_size: int = 2) -> list[Cluster]:
        names = [n for n, _, _ in names_freq]
        assigned: set[int] = set()
        self.clusters = []
        self.singletons = []

        first_token_buckets: dict[str, list[int]] = defaultdict(list)
        for idx, (name, _, _) in enumerate(names_freq):
            norm = self.normalizer.normalize(name)
            if norm:
                first = norm.split()[0]
                first_token_buckets[first].append(idx)

        cluster_idx = 0
        for token, indices in first_token_buckets.items():
            if len(indices) < 2:
                continue
            for i in range(len(indices)):
                if indices[i] in assigned:
                    continue
                group = [indices[i]]
                assigned.add(indices[i])
                for j in range(i + 1, len(indices)):
                    if indices[j] in assigned:
                        continue
                    name_i = names[indices[i]]
                    name_j = names[indices[j]]
                    is_eq, score, _ = self.scorer.are_equivalent(
                        name_i, name_j, threshold=self.threshold
                    )
                    if is_eq:
                        group.append(indices[j])
                        assigned.add(indices[j])
                if len(group) >= min_cluster_size:
                    members = [(names[idx], names_freq[idx][1], names_freq[idx][2])
                               for idx in group]
                    canonical = self._infer_canonical_name(members)
                    cluster = Cluster(f"C{cluster_idx:04d}", canonical)
                    for m_name, m_freq, m_emp in members:
                        cluster.add_member(m_name, m_freq, m_emp)
                    cluster.confianza = self._compute_confidence(cluster)
                    self.clusters.append(cluster)
                    cluster_idx += 1

        # Singletons: names not in any cluster
        for idx, (name, freq, emp) in enumerate(names_freq):
            if idx not in assigned:
                self.singletons.append(name)

        self.clusters.sort(key=lambda c: -c.n_members)
        return self.clusters

    def _infer_canonical_name(self, members: list[tuple[str, int, str]]) -> str:
        name_freq = {m[0]: m[1] for m in members}
        best = max(name_freq, key=name_freq.get)
        return best

    def _compute_confidence(self, cluster: Cluster) -> float:
        base = min(1.0, cluster.n_members / 10)
        if cluster.n_members >= 10:
            base = 1.0
        elif cluster.n_members >= 5:
            base = 0.85
        elif cluster.n_members >= 3:
            base = 0.7
        else:
            base = 0.5
        freq_factor = min(1.0, cluster.frecuencia / 50)
        empresa_factor = min(1.0, cluster.n_empresas / 5)
        return round((base * 0.5 + freq_factor * 0.3 + empresa_factor * 0.2), 2)

    def find_ambiguous(self, min_overlap: float = 0.40) -> list[dict]:
        ambiguous = []
        for i, c1 in enumerate(self.clusters):
            for c2 in self.clusters[i + 1:]:
                norm1 = self.normalizer.normalize(c1.name)
                norm2 = self.normalizer.normalize(c2.name)
                if not norm1 or not norm2:
                    continue
                t1 = set(norm1.split())
                t2 = set(norm2.split())
                if not t1 or not t2:
                    continue
                jaccard = len(t1 & t2) / len(t1 | t2)
                ratio = rapidfuzz_mod.ratio(norm1, norm2) / 100.0
                if jaccard >= min_overlap or ratio >= 0.60:
                    t1_names = [m for m in c1.members[:3]]
                    t2_names = [m for m in c2.members[:3]]
                    ambiguous.append({
                        'cluster_a': c1.id,
                        'cluster_b': c2.id,
                        'nombre_a': c1.name,
                        'nombre_b': c2.name,
                        'jaccard': round(jaccard, 3),
                        'similitud': round(ratio, 3),
                        'ejemplos_a': ' | '.join(t1_names),
                        'ejemplos_b': ' | '.join(t2_names),
                    })
        ambiguous.sort(key=lambda x: -x['similitud'])
        return ambiguous
