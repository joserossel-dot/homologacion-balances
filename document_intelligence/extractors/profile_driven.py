"""GenericTableExtractor — extracción por perfil de familia (Sprint 36).

Consume los perfiles aprendidos en el Sprint 35 (`TableProfile`) para
producir el **orden de columnas** (`layout_hint`/`column_order`) que el
Parser Universal usa cuando el documento coincide con una familia con
perfil confiable.

Reglas de oro:

  - La extracción SIEMPRE la hace `ParserPDF.parsear()` como base
    (nunca un parser nuevo).
  - `UniversalExtractor` es el fallback obligatorio: perfil ausente,
    estructura distinta, cobertura baja o cualquier error → extracción
    universal idéntica.
  - Nunca lanza excepción.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from .base import ExtractorResult, FAMILIA_DESCONOCIDA, SpecializedExtractor

logger = logging.getLogger("document_intelligence.extractors.profile_driven")

# Keys de columna del perfil → strings de `layout_hint` (los mismos keys que
# `_LAYOUT_COLUMN_MAP` del parser). MONTO se vuelve "saldo" (desconocido)
# para conservar la posición en el orden de columnas sin inventar semántica.
_KEY_TO_HINT = {
    "ACTIVO": "activo",
    "PASIVO": "pasivo",
    "PERDIDA": "perdida",
    "GANANCIA": "ganancia",
    "DEBE": "deudor",
    "HABER": "acreedor",
    "SALDO": "saldo",
    "MONTO": "saldo",
}

# Cobertura mínima (Sprint 35, validación sobre la familia completa) para
# aplicar un perfil. Por debajo se usa el universal.
MIN_COBERTURA = 0.5

_PROFILES_PATH = "knowledge_base/extractor_profiles.json"


# ---------------------------------------------------------------------------
# Helper puro: perfil → layout_hint
# ---------------------------------------------------------------------------

def layout_hint_for_profile(profile) -> Optional[list[str]]:
    """layout_hint (izquierda→derecha) desde las columnas de monto del perfil.

    Devuelve None si el perfil no tiene al menos 2 columnas de monto con
    semántica aprovechable (p. ej. un ER de 1 sola columna MONTO, o un
    perfil donde todas las columnas son MONTO/saldo): en esos casos el
    perfil no mejora la heurística estándar del universal.
    """
    if profile is None:
        return None
    amounts = sorted(profile.amount_columns, key=lambda c: -c.position)
    hints = [h for h in (_KEY_TO_HINT.get(c.key) for c in amounts) if h is not None]
    if len(hints) < 2 or not any(h != "saldo" for h in hints):
        return None
    return hints


# ---------------------------------------------------------------------------
# Helper puro: ¿la estructura del documento coincide con el perfil?
# ---------------------------------------------------------------------------

def estructura_coincide(profile, lines: list[str]) -> bool:
    """El documento comparte la estructura aprendida por el perfil.

    Compara nº de columnas de monto, presencia de códigos y layout usando
    los mismos detectores del ecosistema (TableProfileTrainer).
    """
    if profile is None or not lines:
        return False
    try:
        from ..trainer import TableProfileTrainer
        s = TableProfileTrainer().analyze_document(lines)
    except Exception:  # noqa: BLE001 — fallback deliberado
        return False
    if not s.get("valid"):
        return False

    n_amounts = max((c.position for c in profile.amount_columns), default=0)
    if s.get("amount_mode", 0) != n_amounts:
        return False
    if (profile.code_column is not None) != bool(s.get("has_codes")):
        return False
    p_layout = profile.layout
    if p_layout not in ("DESCONOCIDO",):
        sig = s.get("signature")
        if sig is not None and sig.layout.value != p_layout:
            return False
    return True


# ---------------------------------------------------------------------------
# Carga de perfiles (con caché)
# ---------------------------------------------------------------------------

_cache: Optional[tuple[str, dict[str, Any]]] = None


def _cargar_perfiles() -> dict[str, Any]:
    """Perfiles familia_id → TableProfile (caché por mtime+tamaño)."""
    global _cache
    try:
        from ..trainer import ProfileRepository
    except Exception as exc:  # noqa: BLE001
        logger.debug("Trainer no disponible (%s); sin perfiles.", exc)
        return {}
    path = Path(_PROFILES_PATH)
    try:
        key = f"{path.stat().st_mtime_ns}:{path.stat().st_size}"
    except OSError:
        return {}
    if _cache and _cache[0] == key:
        return _cache[1]
    perfiles = ProfileRepository(path).load()
    _cache = (key, perfiles)
    return perfiles


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------

def profile_layout_hint(
    path: Path | str,
    context: Any = None,
    family_id: Optional[str] = None,
    lines: Optional[list[str]] = None,
    min_coverage: float = MIN_COBERTURA,
) -> Optional[list[str]]:
    """Orden de columnas aprendido para el documento, o None.

    Detección de familia: usa `family_id` si se da; si no, delega en
    `SpecializedExtractorFactory.detect()` (misma decisión que el parser).
    Nunca lanza: cualquier fallo → None (→ universal).
    """
    if family_id in (None, "", FAMILIA_DESCONOCIDA):
        try:
            from .factory import SpecializedExtractorFactory
            info = SpecializedExtractorFactory().detect(path, context)
            family_id = info.get("family_id", FAMILIA_DESCONOCIDA)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Detección de familia falló (%s); universal.", exc)
            return None

    profile = _cargar_perfiles().get(family_id or "")
    if profile is None or profile.n_documents <= 0:
        return None

    val = profile.validation or {}
    if min_coverage and val.get("coverage", 1.0) < min_coverage:
        return None

    if lines is None:
        try:
            from ..knowledge.fingerprint import extract_preview_lines
            lines = extract_preview_lines(path)
        except Exception:  # noqa: BLE001
            return None
    if not estructura_coincide(profile, lines):
        return None

    return layout_hint_for_profile(profile)


class GenericTableExtractor(SpecializedExtractor):
    """Extractor que aplica el perfil de su familia al Parser Universal.

    Los scaffolds del Sprint 34 (Nogales, AICSA, ...) lo usan como base:
    con perfil confiable marcan `fallback_used=False`; ante cualquier
    incertidumbre delegan al universal (`fallback_used=True`).
    """

    id = "generic_profile"
    display_name = "Extractor por Perfil"
    supported_families: list[str] = []

    def extract(self, path: Path, context: Any = None) -> ExtractorResult:
        from .factory import SpecializedExtractorFactory

        try:
            info = SpecializedExtractorFactory().detect(path, context)
        except Exception:  # noqa: BLE001
            info = {
                "family_id": FAMILIA_DESCONOCIDA,
                "confidence": 0.0,
                "fallback_used": True,
            }
        family_id = info.get("family_id", FAMILIA_DESCONOCIDA)
        confidence = info.get("confidence", 0.0)

        hint = profile_layout_hint(path, context, family_id=family_id)
        if hint is None:
            return self.delegate_to_universal(
                path, context,
                family_id="" if family_id in ("", FAMILIA_DESCONOCIDA) else family_id,
                confidence=confidence,
            )

        # Perfil aplicable → pasar el orden aprendido vía layout_hint del
        # contexto (prioridad 1 de ParserPDF, confianza suficiente).
        from parser_universal import ExtractionContext, ParserPDF

        ctx = ExtractionContext(layout_hint=hint, layout_confidence=1.0)
        if context is not None:
            for attr in ("rotation_hint", "rotation_confidence",
                         "needs_ocr", "format_hint", "confidence"):
                v = getattr(context, attr, None)
                if v is not None:
                    setattr(ctx, attr, v)

        t0 = time.perf_counter()
        try:
            resultado = ParserPDF().parsear(path, ctx)
        except Exception as exc:  # noqa: BLE001 — fallback obligatorio
            logger.debug("Parseo con perfil falló (%s); universal.", exc)
            return self.delegate_to_universal(
                path, context,
                family_id="" if family_id in ("", FAMILIA_DESCONOCIDA) else family_id,
                confidence=confidence,
            )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        return ExtractorResult(
            extractor_id=self.id,
            display_name=self.display_name,
            family_id=family_id,
            confidence=confidence,
            elapsed_ms=elapsed_ms,
            fallback_used=False,
            result=resultado,
        )
