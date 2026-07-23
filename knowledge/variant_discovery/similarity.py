from __future__ import annotations
import math
import re
from collections import Counter
from typing import Optional

from rapidfuzz import fuzz as rf
from knowledge.normalizer import Normalizer


STOPWORDS = {
    "de", "del", "la", "las", "los", "el", "y", "e", "con",
    "para", "por", "al", "en", "un", "una", "a", "su", "o",
    "que", "es", "se",
}


def tokenize(text: str) -> list[str]:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = [t for t in text.split() if t not in STOPWORDS and len(t) > 1]
    return tokens


def trigrams(text: str) -> set[str]:
    t = text.lower().strip()
    return {t[i:i+3] for i in range(len(t) - 2)}


def jaccard_similarity(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def trigram_similarity(text_a: str, text_b: str) -> float:
    return jaccard_similarity(trigrams(text_a), trigrams(text_b))


def levenshtein_similarity(text_a: str, text_b: str) -> float:
    if not text_a or not text_b:
        return 0.0
    a, b = text_a.lower().strip(), text_b.lower().strip()
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    dist = _levenshtein(a, b)
    return 1.0 - (dist / max_len)


def _levenshtein(a: str, b: str) -> int:
    n, m = len(a), len(b)
    if n < m:
        a, b = b, a
        n, m = m, n
    prev = list(range(m + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(
                curr[j] + 1,
                prev[j + 1] + 1,
                prev[j] + cost,
            ))
        prev = curr
    return prev[m]


class TFIDFVectorizer:
    def __init__(self, documents: list[str]):
        self._corpus: list[list[str]] = [tokenize(d) for d in documents]
        self._vocab: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._fit()

    def _fit(self) -> None:
        df: Counter = Counter()
        for tokens in self._corpus:
            for t in set(tokens):
                df[t] += 1
        n = len(self._corpus)
        for idx, t in enumerate(sorted(set(t for doc in self._corpus for t in doc))):
            self._vocab[t] = idx
            self._idf[t] = math.log((n + 1) / (df[t] + 1)) + 1

    def transform(self, text: str) -> dict[str, float]:
        tokens = tokenize(text)
        n = len(tokens)
        tf: Counter = Counter(tokens)
        vec: dict[str, float] = {}
        for tok, cnt in tf.items():
            if tok in self._idf:
                vec[tok] = (cnt / n) * self._idf[tok]
        return vec

    def cosine_similarity(self, vec_a: dict[str, float],
                          vec_b: dict[str, float]) -> float:
        keys = set(vec_a) | set(vec_b)
        dot = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in keys)
        na = math.sqrt(sum(v*v for v in vec_a.values()))
        nb = math.sqrt(sum(v*v for v in vec_b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)


class MultiMetricScorer:
    def __init__(self, corpus: Optional[list[str]] = None):
        self.tfidf = TFIDFVectorizer(corpus or []) if corpus else None
        self.normalizer = Normalizer()

    @classmethod
    def from_names(cls, names: list[str]) -> MultiMetricScorer:
        return cls(corpus=names)

    def combined_score(self, name_a: str, name_b: str) -> float:
        norm_a = self.normalizer.normalize(name_a).text
        norm_b = self.normalizer.normalize(name_b).text

        tokens_a = set(tokenize(norm_a))
        tokens_b = set(tokenize(norm_b))

        w_jaccard = jaccard_similarity(tokens_a, tokens_b) * 0.20
        w_trigram = trigram_similarity(norm_a, norm_b) * 0.15
        w_lev = levenshtein_similarity(norm_a, norm_b) * 0.10
        w_fuzz_token = (rf.token_sort_ratio(norm_a, norm_b) / 100.0) * 0.20
        w_fuzz_set = (rf.token_set_ratio(norm_a, norm_b) / 100.0) * 0.20
        w_tfidf = 0.0
        if self.tfidf is not None:
            w_tfidf = self.tfidf.cosine_similarity(
                self.tfidf.transform(name_a),
                self.tfidf.transform(name_b),
            ) * 0.15

        return round(w_jaccard + w_trigram + w_lev + w_fuzz_token + w_fuzz_set + w_tfidf, 4)

    def are_equivalent(self, name_a: str, name_b: str,
                       threshold: float = 0.60) -> tuple[bool, float]:
        score = self.combined_score(name_a, name_b)
        if self.normalizer.normalize(name_a).text == self.normalizer.normalize(name_b).text:
            return True, 1.0
        return (score >= threshold, score)
