"""
Detector de orientación para PDFs con texto nativo.

Detecta páginas rotadas usando palabras clave invertidas
en extracción pdfplumber.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrientationResult:
    rotation: int
    confidence: float
    reason: str


# Texto que aparece al leer PDF girado 180°
INVERTED_MARKERS = {
    "ovitca": "activo",
    "ovisap": "pasivo",
    "atneuC": "cuenta",
    "erbmoN": "nombre",
    "sotidérc": "créditos",
    "sotibéd": "débitos",
    "aicnanaG": "ganancia",
    "adidreP": "perdida",
}


def detectar_orientacion_words(words: list[dict]) -> OrientationResult:
    """
    Detecta orientación usando palabras extraídas.
    """

    if not words:
        return OrientationResult(
            rotation=0,
            confidence=0,
            reason="sin palabras"
        )

    textos = " ".join(
        str(w.get("text", ""))
        for w in words[:150]
    ).lower()


    encontrados = 0

    for marca in INVERTED_MARKERS:
        if marca.lower() in textos:
            encontrados += 1


    if encontrados >= 2:
        return OrientationResult(
            rotation=180,
            confidence=min(1.0, encontrados / 5),
            reason=f"marcadores invertidos encontrados: {encontrados}"
        )


    return OrientationResult(
        rotation=0,
        confidence=0.9,
        reason="orientación normal"
    )


def corregir_words_rotadas(
    words: list[dict],
    rotation: int
) -> list[dict]:
    """
    Corrige coordenadas de palabras para páginas rotadas.

    Actualmente soporta 180 grados.
    """

    if rotation != 180:
        return words

    if not words:
        return words

    max_x = max(
        float(w.get("x1", 0))
        for w in words
    )

    max_y = max(
        float(w.get("bottom", 0))
        for w in words
    )

    corregidas = []

    for w in words:
        nuevo = w.copy()

        nuevo["x0"] = max_x - float(w["x1"])
        nuevo["x1"] = max_x - float(w["x0"])

        nuevo["top"] = max_y - float(w["bottom"])
        nuevo["bottom"] = max_y - float(w["top"])

        nuevo["text"] = w["text"][::-1]

        corregidas.append(nuevo)

    return sorted(
        corregidas,
        key=lambda x: (
            round(x["top"]),
            x["x0"]
        )
    )
