from __future__ import annotations

import re
import unicodedata
from typing import Optional


STOP_WORDS: frozenset[str] = frozenset({
    'total', 'subtotal', 'neto', 'de', 'la', 'el', 'del', 'los', 'las',
    'un', 'una', 'y', 'e', 'o', 'a', 'por', 'al', 'con', 'en', 'para',
    'su', 'que', 'lo', 'no', 'se', 'entre', 'las', 'los', 'le', 'les', 'sus',
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
})

QUALIFIER_WORDS: frozenset[str] = frozenset({
    'corrientes', 'no', 'corto', 'largo', 'plazo', 'emitido', 'pagado',
    'suscrito', 'autorizado', 'social', 'emitida', 'pagada', 'suscrita',
    'autorizada', 'general', 'especifico', 'especifica', 'comun',
    'ordinarias', 'ordinario', 'neto', 'neta', 'bruto', 'bruta',
    'varios', 'varias', 'diversos', 'diversas', 'comerciales',
    'comercial', 'provicional', 'anticipado', 'diferentes',
    'financieros', 'financiero', 'permanente', 'temporales', 'temporal',
})

OCR_SUBSTITUTIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'0'), 'o'),
    (re.compile(r'1'), 'i'),
    (re.compile(r'5'), 's'),
    (re.compile(r'8'), 'b'),
    (re.compile(r'rn'), 'm'),
]


class SemanticNormalizer:
    """Normalizador de nombres de cuentas contables.

    Aplica en orden:
    1. Case folding + ASCII fold
    2. Limpieza de signos de puntuación
    3. Colapso de espacios
    4. Corrección OCR de patrones conocidos
    5. Tokenización

    NO expande abreviaturas (eso se maneja en el matcher Tier 3).
    """

    def __init__(self, catalog: Optional[list[dict]] = None):
        pass

    @staticmethod
    def normalize(name: str) -> str:
        if not name:
            return ""
        s = name.lower().strip()
        s = unicodedata.normalize("NFKD", s)
        s = s.encode("ascii", "ignore").decode("ascii")
        s = re.sub(r"[^\w\s]", " ", s)
        s = re.sub(r"\s+", " ", s)
        s = s.strip()
        for pat, repl in OCR_SUBSTITUTIONS:
            s = pat.sub(repl, s)
        return s.strip()

    @staticmethod
    def remove_noise(name: str) -> str:
        """Elimina stop words y qualifiers."""
        words = name.split()
        filtered = [
            w for w in words
            if w not in STOP_WORDS
            and w not in QUALIFIER_WORDS
            and len(w) >= 2
        ]
        return " ".join(filtered)

    @staticmethod
    def tokenize(name: str) -> list[str]:
        return [w for w in name.split() if len(w) >= 2]

    @staticmethod
    def root_word(name: str) -> Optional[str]:
        """Extrae la raíz léxica (primera palabra significativa).
        Acepta nombre normalizado o en bruto.
        """
        norm = SemanticNormalizer.normalize(name)
        cleaned = SemanticNormalizer.remove_noise(norm)
        tokens = SemanticNormalizer.tokenize(cleaned)
        return tokens[0] if tokens else None
