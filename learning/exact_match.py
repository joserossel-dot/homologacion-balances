from __future__ import annotations

import re
import unicodedata


def normalize_name(name: str) -> str:
    """Normaliza nombre de cuenta para matching contra Gold Standard.

    Equivalente a HomologationPipeline._normalize_name().

    Aplica NFKD para eliminar diacríticos (M2): la normalización debe
    aplicarse en ambos lados (texto buscado y claves del gold).
    """
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9áéíóúñü ]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name
