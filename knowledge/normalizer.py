from __future__ import annotations
import re
import unicodedata


STOPWORDS_DEFAULT = {
    "de", "del", "la", "las", "los", "el", "y", "con", "para", "por",
    "al", "en", "un", "una", "a", "su", "e", "o", "que", "es", "se",
}

ABBREVIATIONS_DEFAULT = {
    "adm": "administracion",
    "depr": "depreciacion",
    "prov": "provision",
    "doc": "documento",
    "cta": "cuenta",
    "ctas": "cuentas",
    "cxc": "cuentas por cobrar",
    "cxp": "cuentas por pagar",
    "imp": "impuesto",
    "hon": "honorarios",
    "rrhh": "recursos humanos",
    "inv": "inventario",
    "merc": "mercaderias",
    "provac": "provision acreedores",
    "provext": "proveedores externos",
    "cap": "capital",
    "dep": "deposito",
    "dif": "diferencia",
    "dcto": "descuento",
    "eq": "equipo",
    "fdo": "fondo",
    "fin": "financiero",
    "gast": "gasto",
    "gest": "gestion",
    "hab": "haberes",
    "intang": "intangible",
    "mat": "materiales",
    "mob": "mobiliario",
    "mueb": "muebles",
    "patr": "patrimonio",
    "ppto": "presupuesto",
    "pto": "puesto",
    "rec": "recursos",
    "rem": "remuneracion",
    "rev": "revision",
    "rrpp": "relaciones publicas",
    "soc": "sociedad",
    "sto": "stock",
    "tes": "tesoreria",
    "util": "utilidad",
    "vta": "venta",
    "vtas": "venta",
    "cte": "corriente",
    "nac": "nacionales",
    "ext": "extranjero",
    "pps": "propiedades plantas y equipos",
}

ROMAN_NUMERALS = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
    "vii": 7, "viii": 8, "ix": 9, "x": 10,
}

SINGULAR_MAP = {
    "aciones": "acion", "adores": "ador", "antes": "ante",
    "eses": "es", "ices": "iz", "idos": "ido", "ones": "on",
    "ores": "or", "osas": "osa", "osos": "oso", "adas": "ada",
    "idas": "ida", "ndos": "ndo", "ajes": "aje", "enes": "en",
    "eres": "er", "ales": "al", "bles": "ble", "cias": "cia",
    "gias": "gia", "gios": "gio", "gues": "gue", "lias": "lia",
    "llos": "llo", "mientos": "miento", "ncias": "ncia",
    "nchos": "ncho", "ndes": "nde", "neros": "nero",
    "nios": "nio", "nones": "non", "nzas": "nza",
    "ones": "on", "ores": "or", "osas": "osa", "osos": "oso",
    "siones": "sion", "tivos": "tivo", "turas": "tura",
    "xiones": "xion", "yentes": "yente", "zones": "zon",
}


class NormalizerResult:
    def __init__(self, text: str, transformations: list[str]):
        self.text = text
        self.transformations = transformations

    def __repr__(self):
        return f"NormalizerResult(text='{self.text}', transforms={self.transformations})"


class Normalizer:
    def __init__(self, stopwords: set[str] | None = None,
                 abbreviations: dict[str, str] | None = None):
        self.stopwords = stopwords or STOPWORDS_DEFAULT
        self.abbreviations = abbreviations or ABBREVIATIONS_DEFAULT

    def normalize(self, text: str) -> NormalizerResult:
        if not text or not isinstance(text, str):
            return NormalizerResult("", ["texto_vacio"])
        original = text
        transforms = []
        text = text.strip()

        text, t = self._lowercase(text)
        if t: transforms.append(t)

        text, t = self._remove_accents(text)
        if t: transforms.append(t)

        text, t = self._remove_punctuation(text)
        if t: transforms.append(t)

        text, t = self._expand_abbreviations(text)
        if t: transforms.append(t)

        text, t = self._normalize_roman_numerals(text)
        if t: transforms.append(t)

        text, t = self._remove_multiple_spaces(text)
        if t: transforms.append(t)

        text, t = self._singularize(text)
        if t: transforms.append(t)

        text, t = self._remove_stopwords(text)
        if t: transforms.append(t)

        text = text.strip()
        if text != original.strip():
            transforms.append("texto_transformado")

        return NormalizerResult(text, transforms)

    def _lowercase(self, text: str) -> tuple[str, str | None]:
        t = text.lower()
        return (t, "lowercase") if t != text else (t, None)

    def _remove_accents(self, text: str) -> tuple[str, str | None]:
        t = unicodedata.normalize("NFKD", text)
        t = t.encode("ASCII", "ignore").decode("ASCII")
        return (t, "sin_acentos") if t != text else (t, None)

    def _remove_punctuation(self, text: str) -> tuple[str, str | None]:
        t = re.sub(r"[^\w\s]", " ", text)
        return (t, "sin_puntuacion") if t != text else (t, None)

    def _expand_abbreviations(self, text: str) -> tuple[str, str | None]:
        t = text
        changed = False
        for abbr, expansion in sorted(self.abbreviations.items(),
                                       key=lambda x: -len(x[0])):
            pattern = r'\b' + re.escape(abbr) + r'\b'
            if re.search(pattern, t):
                t = re.sub(pattern, expansion, t)
                changed = True
        return (t, "abreviaturas_expandidas") if changed else (t, None)

    def _normalize_roman_numerals(self, text: str) -> tuple[str, str | None]:
        t = text
        changed = False
        for roman, value in ROMAN_NUMERALS.items():
            pattern = r'\b' + re.escape(roman) + r'\b'
            if re.search(pattern, t):
                t = re.sub(pattern, str(value), t)
                changed = True
        return (t, "romanos_normalizados") if changed else (t, None)

    def _remove_multiple_spaces(self, text: str) -> tuple[str, str | None]:
        t = re.sub(r'\s+', ' ', text)
        return (t, "espacios_eliminados") if t != text else (t, None)

    def _singularize(self, text: str) -> tuple[str, str | None]:
        t = text
        changed = False
        words = t.split()
        for i, word in enumerate(words):
            for plural, singular in SINGULAR_MAP.items():
                if word.endswith(plural) and len(word) > len(plural) + 1:
                    words[i] = word[:-len(plural)] + singular
                    changed = True
                    break
        t = " ".join(words)
        return (t, "singularizado") if changed else (t, None)

    def _remove_stopwords(self, text: str) -> tuple[str, str | None]:
        words = text.split()
        filtered = [w for w in words if w not in self.stopwords]
        t = " ".join(filtered)
        return (t, "stopwords_eliminadas") if len(filtered) != len(words) else (t, None)
