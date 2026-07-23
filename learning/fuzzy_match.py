from __future__ import annotations

from rapidfuzz import fuzz


def fuzzy_score(name_a: str, name_b: str) -> int:
    """Token sort ratio entre dos nombres normalizados."""
    return fuzz.token_sort_ratio(name_a, name_b)
