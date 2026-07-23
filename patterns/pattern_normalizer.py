from __future__ import annotations

import re
import unicodedata


class PatternNormalizer:
    PUNCTUATION = set(".,-_:;()[]{}!/\\|'\"¿?¡$%&@#*+<=>^~`°")

    EXPANSION_MAP = [
        (re.compile(r"\bC\s*[xX]\s*C\b"), "CUENTAS POR COBRAR"),
        (re.compile(r"\bC\s*[xX]\s*P\b"), "CUENTAS POR PAGAR"),
    ]

    def normalize(self, name: str) -> str:
        if not name:
            return ""
        result = name.strip()
        result = self._remove_accents(result)
        result = result.upper()
        result = self._expand_cxc_cxp(result)
        result = self._replace_punctuation(result)
        result = re.sub(r"\s+", " ", result)
        result = self._strip_leading_codes(result)
        result = result.strip()
        return result

    def normalize_preserve_case(self, name: str) -> str:
        if not name:
            return ""
        result = name.strip()
        result = self._remove_accents(result)
        result = self._replace_punctuation(result)
        result = re.sub(r"\s+", " ", result)
        result = result.strip()
        return result

    def _remove_accents(self, text: str) -> str:
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def _expand_cxc_cxp(self, text: str) -> str:
        result = text
        for pattern, replacement in self.EXPANSION_MAP:
            result = pattern.sub(replacement, result)
        return result

    def _replace_punctuation(self, text: str) -> str:
        chars = []
        for c in text:
            if c in self.PUNCTUATION:
                chars.append(" ")
            else:
                chars.append(c)
        return "".join(chars)

    def _strip_leading_codes(self, text: str) -> str:
        tokens = text.split()
        while tokens and re.match(r"^\d+$", tokens[0]):
            tokens = tokens[1:]
        return " ".join(tokens)
