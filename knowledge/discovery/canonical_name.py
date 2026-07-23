from __future__ import annotations
from collections import Counter
from knowledge.discovery.similarity import AccountNormalizer
from knowledge.normalizer import STOPWORDS_DEFAULT


class CanonicalNameGenerator:
    def __init__(self, stopwords: set[str] | None = None):
        self.normalizer = AccountNormalizer(stopwords)
        self.stopwords = stopwords or STOPWORDS_DEFAULT

    def generate(self, members: list[str], frequencies: dict[str, int] | None = None) -> str:
        if not members:
            return ""
        if len(members) == 1:
            return members[0]

        freqs = frequencies or {}
        norm_map: dict[str, str] = {}
        for m in members:
            norm_map[m] = self.normalizer.normalize(m)

        freq_scores: dict[str, float] = {}
        for m in members:
            f = freqs.get(m, 1)
            freq_scores[m] = f

        most_freq = max(freq_scores, key=freq_scores.get)

        intersection_tokens: set[str] | None = None
        for m in members:
            tokens = set(norm_map[m].split()) if norm_map[m] else set()
            if intersection_tokens is None:
                intersection_tokens = tokens
            else:
                intersection_tokens &= tokens

        if intersection_tokens and len(intersection_tokens) >= 1:
            common_tokens = sorted(intersection_tokens,
                                   key=lambda t: -sum(
                                       1 for m2 in members
                                       if t in (norm_map.get(m2, "") or "")
                                   ))
            tokens_used = set()
            for t in common_tokens[:3]:
                tokens_used.add(t)

            for m in members:
                norm = norm_map.get(m, "")
                mtokens = set(norm.split()) if norm else set()
                remaining = mtokens - tokens_used
                for rt in sorted(remaining):
                    tokens_used.add(rt)
                    if len(tokens_used) >= 5:
                        break
                if len(tokens_used) >= 5:
                    break

            final_tokens: list[str] = []
            for t in common_tokens:
                if t in tokens_used and t not in final_tokens:
                    final_tokens.append(t)
            for m in sorted(members, key=lambda x: -freqs.get(x, 0)):
                norm = norm_map.get(m, "")
                for t in norm.split() if norm else []:
                    if t in tokens_used and t not in final_tokens:
                        final_tokens.append(t)
                    if len(final_tokens) >= 6:
                        break
                if len(final_tokens) >= 6:
                    break

            canonical = " ".join(final_tokens[:5])
            if canonical:
                return canonical

        return most_freq

    def generate_short(self, members: list[str],
                       frequencies: dict[str, int] | None = None) -> str:
        full = self.generate(members, frequencies)
        if not full:
            return ""
        words = full.split()
        if len(words) <= 3:
            return full
        tokens = [w for w in words if w not in self.stopwords]
        return " ".join(tokens[:3]) if tokens else " ".join(words[:3])
