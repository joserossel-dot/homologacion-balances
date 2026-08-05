import re
import unicodedata


def normalize(
    text: str,
    remove_accents: bool = True,
    collapse_spaces: bool = True,
    lowercase: bool = True,
    remove_symbols: bool = True,
    preserve_enye: bool = False,
) -> str:
    if text is None:
        return ""
    s = str(text)
    if lowercase:
        s = s.lower()
    s = s.strip()
    if remove_accents:
        if preserve_enye:
            s = s.replace("\u00f1", "\ue000").replace("\u00d1", "\ue001")
            s = unicodedata.normalize("NFKD", s)
            s = "".join(c for c in s if not unicodedata.combining(c))
            s = s.replace("\ue000", "\u00f1").replace("\ue001", "\u00d1")
        else:
            s = unicodedata.normalize("NFKD", s)
            s = s.encode("ascii", "ignore").decode("ascii")
    if remove_symbols:
        s = re.sub(r"[^\w\s]", " ", s)
    if collapse_spaces:
        s = re.sub(r"\s+", " ", s)
    return s.strip()
