from __future__ import annotations

import re

CAJA_DIRECT_PATTERN = re.compile(
    r"(?<![a-záéíóú])caja(?![a-záéíóú])", re.IGNORECASE
)

CAJA_NEGATE_PATTERN = re.compile(
    r"\b(compensaci[oó]n|armad[o0]|armar|seguridad)\b", re.IGNORECASE
)

EFECTIVO_PATTERN = re.compile(r"\befectiv[o0]\b", re.IGNORECASE)

FONDO_FIJO_PATTERN = re.compile(
    r"\bfond[o0]s?\s*fij[o0]s?\b", re.IGNORECASE
)

MONEDA_PATTERN = re.compile(
    r"\bmoneda\s*(nacional|extranjera|extrangera)\b", re.IGNORECASE
)

BILLETE_PATTERN = re.compile(r"\bbilletes?\b", re.IGNORECASE)
DIVISA_PATTERN = re.compile(r"\bdivisas?\b", re.IGNORECASE)
DINERO_PATTERN = re.compile(r"\bdiner[o0]\b", re.IGNORECASE)
ARQUEO_PATTERN = re.compile(r"\barque[o0]\b", re.IGNORECASE)

BANK_TOKEN_MAP: dict[str, set[str]] = {
    "ac01_02": {
        "banco", "bancos", "bancaria", "bancario",
        "bco", "bcos",
        "bci", "santander", "bbva", "scotiabank",
        "itau", "corpbanca", "bice", "internacional",
        "estado", "security", "chile", "credito",
        "inversiones", "consorcio", "falabella", "ripley",
        "deutsche",
    },
}

CTA_PATTERN = re.compile(
    r"\b(cta|cuenta)\s*(\.?\s*cte|\.?\s*corriente|vista|rut|ahorro)\b",
    re.IGNORECASE,
)

CHEQUE_PATTERN = re.compile(r"\bcheque(?:s|ra(?:s)?)?\b", re.IGNORECASE)
SOBREGIRO_PATTERN = re.compile(r"\bsobregir[o0]\w*\b", re.IGNORECASE)

LINEA_CREDITO_PATTERN = re.compile(
    r"\b(l[ií]nea?\s*(de\s*)?cr[eé]dito|lineacredit)\b", re.IGNORECASE
)

BANCO_NEGATE_PATTERN = re.compile(
    r"\b(inversi[oó]n\w*|mutuo\w*)\b", re.IGNORECASE
)

FONDO_MUTUO_PATTERN = re.compile(
    r"\bfond[o0]s?\s*mutuo\w*\b", re.IGNORECASE
)

INVERSION_PATTERN = re.compile(
    r"\binversi[oó]n\w*\b", re.IGNORECASE
)

VALOR_NEGOCIABLE_PATTERN = re.compile(
    r"\bvalore?s?\s*negociables?\b", re.IGNORECASE
)

CORTO_PLAZO_PATTERN = re.compile(
    r"\bcort[o0]\s*plaz[o0]\b", re.IGNORECASE
)

DEPOSITO_PLAZO_PATTERN = re.compile(
    r"\bdep[o0]sito\w*\s*a?\s*plaz[o0]\w*\b", re.IGNORECASE
)

ACCIONES_PATTERN = re.compile(
    r"\baccion(es|ista)?\b", re.IGNORECASE
)

BONOS_PATTERN = re.compile(r"\bbon[o0]\w*\b", re.IGNORECASE)


def has_any_token(text: str, tokens: set[str]) -> set[str]:
    words = text.lower().split()
    matched: set[str] = set()
    for w in words:
        cleaned = w.strip(".,:;\"'()[]-–—/\\!¡¿?+*#@$%&=")
        if cleaned in tokens:
            matched.add(cleaned)
    return matched
