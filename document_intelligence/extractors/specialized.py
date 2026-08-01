"""Scaffolds de los extractores especializados (Sprint 34 → 36).

Desde el Sprint 36 heredan de `GenericTableExtractor`: aplican el perfil
de familia aprendido en el Sprint 35 (columna de montos → column_order)
cuando la familia y la estructura del documento coinciden. Ante cualquier
incertidumbre delegan al Parser Universal (fallback obligatorio).

Familias asignadas (resultado del mining Sprint 33):

  - Nogales   → cluster_4c326713f3 (105 docs, VERTICAL/COMPACTO/ER)
  - AICSA     → cluster_0a1bebffff (18 docs, VERTICAL)
  - Gonzagri  → cluster_02e4348704 (25 docs, LIBRE/GUION)
  - Wilug     → cluster_4c326713f3 (el Balance Tributario 2022 de Wilug
                cae en esta familia según los splits casi idénticos
                detectados en el análisis de calidad)

NOTA: Wilug y Nogales comparten familia. El orden de registro da
precedencia a Nogales; la lógica de perfil usa la familia detectada, por
lo que ambos producirán el mismo resultado para esa familia.
"""

from __future__ import annotations

from .profile_driven import GenericTableExtractor
from .registry import register_extractor


@register_extractor()
class NogalesExtractor(GenericTableExtractor):
    id = "nogales"
    display_name = "Nogales"
    supported_families = ["cluster_4c326713f3"]


@register_extractor()
class AicsaExtractor(GenericTableExtractor):
    id = "aicsa"
    display_name = "AICSA"
    supported_families = ["cluster_0a1bebffff"]


@register_extractor()
class WilugExtractor(GenericTableExtractor):
    id = "wilug"
    display_name = "Wilug"
    supported_families = ["cluster_4c326713f3"]


@register_extractor()
class GonzagriExtractor(GenericTableExtractor):
    id = "gonzagri"
    display_name = "Gonzagri"
    supported_families = ["cluster_02e4348704"]
