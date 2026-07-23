from __future__ import annotations

import re


def normalize_name(name: str) -> str:
    """Normaliza nombre de cuenta para matching contra Gold Standard.

    Equivalente a HomologationPipeline._normalize_name().
    """
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9áéíóúñü ]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name
