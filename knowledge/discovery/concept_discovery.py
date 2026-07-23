from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict
import pandas as pd
from knowledge.discovery.similarity import SimilarityScorer, AccountNormalizer
from knowledge.discovery.token_statistics import TokenStatistics
from knowledge.discovery.cluster_engine import ClusterEngine, Cluster
from knowledge.discovery.canonical_name import CanonicalNameGenerator


class ConceptDiscovery:
    def __init__(self, threshold: float = 0.70):
        self.scorer = SimilarityScorer()
        self.normalizer = AccountNormalizer()
        self.token_stats = TokenStatistics()
        self.engine = ClusterEngine(threshold=threshold)
        self.canonical = CanonicalNameGenerator()
        self.accounts: list[dict] = []
        self.names_freq: list[tuple[str, int, str]] = []
        self.freq_map: dict[str, int] = {}
        self.emp_map: dict[str, str] = {}
        self.all_names_set: set[str] = set()

    def load_accounts(self, top_accounts_path: str | Path,
                      diccionario_path: str | Path | None = None,
                      cmcc_path: str | Path | None = None) -> None:
        ta = pd.read_excel(top_accounts_path)
        names = ta['cuenta'].dropna().unique().tolist()
        self.freq_map = dict(zip(ta['cuenta'].astype(str), ta['frecuencia']))
        emp_col = 'empresas_distintas'
        if emp_col in ta.columns:
            self.emp_map = dict(zip(ta['cuenta'].astype(str),
                                     ta[emp_col].astype(str)))

        seen = set()
        self.accounts = []
        for n in names:
            sn = str(n)
            if sn in seen:
                continue
            seen.add(sn)
            freq = self.freq_map.get(sn, 0)
            emp = self.emp_map.get(sn, "")
            self.accounts.append({'name': sn, 'freq': freq, 'empresa': emp})
            self.names_freq.append((sn, freq, emp))

        if diccionario_path and Path(diccionario_path).exists():
            with open(diccionario_path, 'r', encoding='utf-8') as f:
                d = json.load(f)
            for entry in d:
                name = entry.get('cuenta_original', '')
                if name and name not in seen:
                    seen.add(name)
                    self.accounts.append({'name': name, 'freq': 0, 'empresa': ''})
                    self.names_freq.append((name, 0, ''))

        self.all_names_set = seen
        print(f"  Loaded {len(self.accounts)} accounts ({len(seen)} unique)")

    def run(self, min_cluster_size: int = 2) -> dict:
        print("Building clusters...")
        clusters = self.engine.build_clusters(self.names_freq,
                                              min_cluster_size=min_cluster_size)
        print(f"  Created {len(clusters)} clusters, {len(self.engine.singletons)} singletons")

        print("Computing token statistics...")
        all_names = [a['name'] for a in self.accounts]
        token_data = self.token_stats.analyze(all_names)

        print("Finding ambiguous concepts...")
        ambiguous = self.engine.find_ambiguous()

        result = {
            'clusters': clusters,
            'singletons': self.engine.singletons,
            'token_stats': token_data,
            'ambiguous': ambiguous,
            'total_accounts': len(self.all_names_set),
            'clustered_accounts': sum(c.n_members for c in clusters),
            'singleton_count': len(self.engine.singletons),
        }
        return result

    def export_cluster_graph(self) -> dict:
        nodes = []
        links = []
        for cluster in self.engine.clusters:
            node = {
                'id': cluster.id,
                'name': cluster.name,
                'n_members': cluster.n_members,
                'frequency': cluster.frecuencia,
                'confidence': cluster.confianza,
            }
            nodes.append(node)
        for i, c1 in enumerate(self.engine.clusters):
            for c2 in self.engine.clusters[i + 1:]:
                n1 = self.normalizer.normalize(c1.name)
                n2 = self.normalizer.normalize(c2.name)
                if not n1 or not n2:
                    continue
                from rapidfuzz import fuzz as rf
                sim = rf.ratio(n1, n2) / 100.0
                if sim >= 0.3:
                    links.append({
                        'source': c1.id,
                        'target': c2.id,
                        'similarity': round(sim, 3),
                    })
        return {'nodes': nodes, 'links': links}
