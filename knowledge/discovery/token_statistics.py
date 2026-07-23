from __future__ import annotations
from collections import Counter, defaultdict
from knowledge.discovery.similarity import AccountNormalizer
from knowledge.normalizer import STOPWORDS_DEFAULT


class TokenStatistics:
    def __init__(self, stopwords: set[str] | None = None):
        self.normalizer = AccountNormalizer(stopwords)
        self.stopwords = stopwords or STOPWORDS_DEFAULT

    def analyze(self, names: list[str]) -> dict:
        token_counter: Counter[str] = Counter()
        token_accounts: dict[str, set[str]] = defaultdict(set)
        name_lengths: list[int] = []
        token_counts: list[int] = []
        norm_map: dict[str, str] = {}

        for name in names:
            sname = str(name)
            norm = self.normalizer.normalize(sname)
            norm_map[sname] = norm
            tokens = norm.split() if norm else []
            name_lengths.append(len(sname))
            token_counts.append(len(tokens))
            for t in set(tokens):
                if t not in self.stopwords:
                    token_counter[t] += 1
                    token_accounts[t].add(sname)

        if not token_counter:
            return {
                'total_names': 0,
                'total_tokens': 0,
                'unique_tokens': 0,
                'avg_tokens_per_name': 0.0,
                'avg_name_length': 0.0,
                'top_tokens': [],
                'rare_tokens': [],
                'token_clusters': {},
                'norm_map': {},
            }

        sorted_tokens = token_counter.most_common()
        rare = [t for t, c in sorted_tokens if c <= 2]
        gte_10 = [(t, c) for t, c in sorted_tokens if c >= 10]

        first_token_clusters: dict[str, list[str]] = defaultdict(list)
        for name in names:
            sname = str(name)
            norm = norm_map.get(sname, self.normalizer.normalize(sname))
            if norm:
                first = norm.split()[0]
                first_token_clusters[first].append(sname)

        return {
            'total_names': len(names),
            'total_tokens': sum(token_counter.values()),
            'unique_tokens': len(token_counter),
            'avg_tokens_per_name': round(sum(token_counts) / max(len(token_counts), 1), 2),
            'avg_name_length': round(sum(name_lengths) / max(len(name_lengths), 1), 1),
            'top_tokens': sorted_tokens[:100],
            'rare_tokens': rare[:50],
            'high_freq_tokens': gte_10[:50],
            'first_token_clusters': dict(sorted(
                first_token_clusters.items(),
                key=lambda x: -len(x[1])
            )[:50]),
            'norm_map': norm_map,
        }
