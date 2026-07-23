from __future__ import annotations
import re
import unicodedata
from typing import Optional
from rapidfuzz import fuzz
from knowledge.normalizer import Normalizer, ABBREVIATIONS_DEFAULT, STOPWORDS_DEFAULT


class AccountNormalizer:
    def __init__(self, stopwords: Optional[set[str]] = None):
        self.normalizer = Normalizer(stopwords=stopwords)
        self.stopwords = stopwords or STOPWORDS_DEFAULT

    def normalize(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return ""
        return self.normalizer.normalize(text).text


class SimilarityScorer:
    def __init__(self, stopwords: Optional[set[str]] = None):
        self.stopwords = stopwords or STOPWORDS_DEFAULT
        self.normalizer = AccountNormalizer(stopwords)

    def token_overlap(self, tokens_a: set[str], tokens_b: set[str]) -> float:
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))

    def jaccard(self, tokens_a: set[str], tokens_b: set[str]) -> float:
        if not tokens_a or not tokens_b:
            return 0.0
        union = tokens_a | tokens_b
        if not union:
            return 0.0
        return len(tokens_a & tokens_b) / len(union)

    def rapidfuzz_ratio(self, text_a: str, text_b: str) -> float:
        if not text_a or not text_b:
            return 0.0
        a = text_a.lower().strip()
        b = text_b.lower().strip()
        return fuzz.ratio(a, b) / 100.0

    def rapidfuzz_partial(self, text_a: str, text_b: str) -> float:
        if not text_a or not text_b:
            return 0.0
        a = text_a.lower().strip()
        b = text_b.lower().strip()
        return fuzz.partial_ratio(a, b) / 100.0

    def rapidfuzz_token_sort(self, text_a: str, text_b: str) -> float:
        if not text_a or not text_b:
            return 0.0
        a = text_a.lower().strip()
        b = text_b.lower().strip()
        return fuzz.token_sort_ratio(a, b) / 100.0

    def rapidfuzz_token_set(self, text_a: str, text_b: str) -> float:
        if not text_a or not text_b:
            return 0.0
        a = text_a.lower().strip()
        b = text_b.lower().strip()
        return fuzz.token_set_ratio(a, b) / 100.0

    def abbreviation_score(self, text_a: str, text_b: str) -> float:
        score = 0.0
        a_lower = text_a.lower()
        b_lower = text_b.lower()
        for abbr, expansion in ABBREVIATIONS_DEFAULT.items():
            abbr_pat = r'\b' + re.escape(abbr) + r'\b'
            exp_pat = r'\b' + re.escape(expansion) + r'\b'
            a_has_abbr = bool(re.search(abbr_pat, a_lower))
            b_has_exp = bool(re.search(exp_pat, b_lower))
            b_has_abbr = bool(re.search(abbr_pat, b_lower))
            a_has_exp = bool(re.search(exp_pat, a_lower))
            if (a_has_abbr and b_has_exp) or (b_has_abbr and a_has_exp):
                score += 0.15
        return min(score, 1.0)

    def word_order_score(self, tokens_a: set[str], tokens_b: set[str]) -> float:
        if not tokens_a or not tokens_b:
            return 0.0
        shared = tokens_a & tokens_b
        if len(shared) < 2:
            return 0.0
        return len(shared) / max(len(tokens_a), len(tokens_b))

    def prefix_suffix_score(self, text_a: str, text_b: str) -> float:
        if not text_a or not text_b:
            return 0.0
        a = text_a.lower().strip()
        b = text_b.lower().strip()
        score = 0.0
        min_len = min(len(a), len(b))
        if min_len >= 4:
            prefix_len = 0
            for i in range(min(6, min_len)):
                if a[i] == b[i]:
                    prefix_len += 1
                else:
                    break
            score += (prefix_len / 6) * 0.3
        return min(score, 1.0)

    def combined_score(self, text_a: str, text_b: str) -> dict:
        norm_a = AccountNormalizer(self.stopwords).normalize(text_a)
        norm_b = AccountNormalizer(self.stopwords).normalize(text_b)
        tokens_a = set(norm_a.split()) if norm_a else set()
        tokens_b = set(norm_b.split()) if norm_b else set()

        scores = {
            'token_overlap': self.token_overlap(tokens_a, tokens_b),
            'jaccard': self.jaccard(tokens_a, tokens_b),
            'fuzz_ratio': self.rapidfuzz_ratio(norm_a, norm_b),
            'fuzz_partial': self.rapidfuzz_partial(norm_a, norm_b),
            'fuzz_token_sort': self.rapidfuzz_token_sort(text_a, text_b),
            'fuzz_token_set': self.rapidfuzz_token_set(text_a, text_b),
            'abbreviation': self.abbreviation_score(text_a, text_b),
            'word_order': self.word_order_score(tokens_a, tokens_b),
            'prefix_suffix': self.prefix_suffix_score(text_a, text_b),
            'norm_a': norm_a,
            'norm_b': norm_b,
        }

        weights = {
            'token_overlap': 0.15,
            'jaccard': 0.10,
            'fuzz_ratio': 0.15,
            'fuzz_partial': 0.05,
            'fuzz_token_sort': 0.15,
            'fuzz_token_set': 0.15,
            'abbreviation': 0.10,
            'word_order': 0.05,
            'prefix_suffix': 0.10,
        }

        final = sum(scores[k] * weights[k] for k in weights)
        scores['final'] = round(final, 4)
        return scores

    def are_equivalent(self, text_a: str, text_b: str,
                       threshold: float = 0.70) -> tuple[bool, float, dict]:
        scores = self.combined_score(text_a, text_b)
        if scores['final'] >= threshold:
            return True, scores['final'], scores
        if scores['fuzz_token_set'] >= 0.90:
            return True, scores['final'], scores
        if scores['abbreviation'] >= 0.45:
            return True, scores['final'], scores
        return False, scores['final'], scores
