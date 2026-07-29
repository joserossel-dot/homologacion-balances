from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from parser_universal import CuentaRaw, FormatoCodigo

from context.account_context import AccountContext

SEGMENT_RE = re.compile(r'\d+')


@dataclass
class _CodeInfo:
    """Información de código descompuesta para jerarquía."""
    index: int
    raw: CuentaRaw
    code: str
    segments: list[int]
    level: int


class ContextBuilder:
    """Construye AccountContext con jerarquía, navegación y metadata.

    Uso:
        builder = ContextBuilder()
        contexts = builder.build(cuentas, code_format=FormatoCodigo.PUNTO)
    """

    def build(
        self,
        cuentas: list[CuentaRaw],
        *,
        code_format: Optional[FormatoCodigo] = None,
        layout: Optional[list[str]] = None,
        account_types: Optional[dict[str, str]] = None,
    ) -> list[AccountContext]:
        """Construye contexto estructural para cada cuenta.

        Args:
            cuentas: Lista plana de cuentas extraídas.
            code_format: Formato de código para detección de jerarquía.
                        Si es None, se detecta automáticamente.
            layout: Columnas del layout detectado.
            account_types: Mapa de codigo -> tipo_cuenta.

        Returns:
            Lista de AccountContext en el mismo orden que cuentas.
        """
        if not cuentas:
            return []

        fmt = code_format or self._detect_format(cuentas)

        # 1. Extraer información de código para cada cuenta
        infos = [
            self._extract_code_info(i, c, fmt)
            for i, c in enumerate(cuentas)
        ]

        # 2. Construir contextos base
        contexts = [
            self._make_context(info, cuentas, layout, account_types)
            for info in infos
        ]

        # 3. Asignar relaciones jerárquicas
        self._assign_hierarchy(contexts, infos, fmt)

        # 3b. Construir rutas jerárquicas completas
        self._assign_paths(contexts, infos, fmt)

        # 4. Asignar navegación secuencial
        self._assign_navigation(contexts)

        return contexts

    # ──────────────────────────────────────────────
    # Detección de formato
    # ──────────────────────────────────────────────

    @staticmethod
    def _detect_format(cuentas: list[CuentaRaw]) -> FormatoCodigo:
        """Detecta el formato de código más común entre las cuentas."""
        counts: dict[FormatoCodigo, int] = {}
        for c in cuentas:
            if not c.codigo:
                continue
            fmt = _guess_format(c.codigo)
            if fmt:
                counts[fmt] = counts.get(fmt, 0) + 1
        if not counts:
            return FormatoCodigo.SIN_CODIGO
        return max(counts, key=counts.get)

    # ──────────────────────────────────────────────
    # Extracción de código
    # ──────────────────────────────────────────────

    @staticmethod
    def _extract_code_info(
        index: int,
        raw: CuentaRaw,
        fmt: FormatoCodigo,
    ) -> _CodeInfo:
        if not raw.codigo or fmt == FormatoCodigo.SIN_CODIGO:
            return _CodeInfo(
                index=index, raw=raw,
                code="", segments=[], level=0,
            )
        segments = _parse_segments(raw.codigo, fmt)
        return _CodeInfo(
            index=index, raw=raw,
            code=raw.codigo,
            segments=segments,
            level=len(segments),
        )

    # ──────────────────────────────────────────────
    # Contexto base
    # ──────────────────────────────────────────────

    @staticmethod
    def _make_context(
        info: _CodeInfo,
        cuentas: list[CuentaRaw],
        layout: Optional[list[str]],
        account_types: Optional[dict[str, str]],
    ) -> AccountContext:
        tipo = None
        if account_types and info.raw.codigo:
            tipo = account_types.get(info.raw.codigo)

        return AccountContext(
            raw=info.raw,
            hierarchy_level=info.level,
            section=_detect_section(info.raw, info.segments),
            layout=layout or [],
            account_type=tipo,
            path=info.code,
            position=info.index,
            confidence=info.raw.confianza_extraccion,
        )

    # ──────────────────────────────────────────────
    # Jerarquía
    # ──────────────────────────────────────────────

    @staticmethod
    def _assign_hierarchy(
        contexts: list[AccountContext],
        infos: list[_CodeInfo],
        fmt: FormatoCodigo,
    ) -> None:
        """Asigna padre, hijos, hermanos basado en códigos."""
        # Construir mapa: segments -> AccountContext
        segment_map: dict[tuple[int, ...], AccountContext] = {}
        for ctx, info in zip(contexts, infos):
            if info.segments:
                segment_map[tuple(info.segments)] = ctx

        for ctx, info in zip(contexts, infos):
            if not info.segments or info.level <= 0:
                continue

            # Padre: quitar el último segmento
            parent_segments = tuple(info.segments[:-1])
            if parent_segments in segment_map:
                parent = segment_map[parent_segments]
                ctx.parent = parent
                parent.children.append(ctx)

        # Hermanos: comparten el mismo padre
        siblings_groups: dict[Optional[tuple], list[AccountContext]] = {}
        for ctx, info in zip(contexts, infos):
            key = tuple(info.segments[:-1]) if info.segments else None
            if key not in siblings_groups:
                siblings_groups[key] = []
            siblings_groups[key].append(ctx)

        for ctx, info in zip(contexts, infos):
            key = tuple(info.segments[:-1]) if info.segments else None
            group = siblings_groups.get(key, [])
            ctx.siblings = [s for s in group if s is not ctx]

    # ──────────────────────────────────────────────
    # Rutas jerárquicas
    # ──────────────────────────────────────────────

    @staticmethod
    def _assign_paths(
        contexts: list[AccountContext],
        infos: list[_CodeInfo],
        fmt: FormatoCodigo,
    ) -> None:
        """Construye ruta jerárquica completa (ej. '1/1.1/1.1.01')."""
        # Procesar en orden de nivel (padres primero)
        sorted_contexts = sorted(
            zip(contexts, infos),
            key=lambda x: (x[1].level, x[1].index),
        )
        for ctx, _ in sorted_contexts:
            if ctx.parent:
                ctx.path = f"{ctx.parent.path}/{ctx.raw.codigo}"
            elif ctx.raw.codigo:
                ctx.path = ctx.raw.codigo

    # ──────────────────────────────────────────────
    # Navegación secuencial
    # ──────────────────────────────────────────────

    @staticmethod
    def _assign_navigation(contexts: list[AccountContext]) -> None:
        """Asigna previous_account y next_account según orden lineal."""
        for i, ctx in enumerate(contexts):
            if i > 0:
                ctx.previous_account = contexts[i - 1]
            if i < len(contexts) - 1:
                ctx.next_account = contexts[i + 1]


# ──────────────────────────────────────────────
# Funciones auxiliares
# ──────────────────────────────────────────────

def _guess_format(codigo: str) -> Optional[FormatoCodigo]:
    """Adivina el formato de un código de cuenta."""
    if re.match(r'^\d+(\.\d+)+$', codigo):
        return FormatoCodigo.PUNTO
    if re.match(r'^\d+(-\d+)+$', codigo):
        return FormatoCodigo.GUION
    if re.match(r'^\d{6,10}$', codigo):
        return FormatoCodigo.COMPACTO
    return None


def _parse_segments(codigo: str, fmt: FormatoCodigo) -> list[int]:
    """Descompone un código en segmentos numéricos."""
    if fmt == FormatoCodigo.PUNTO:
        parts = codigo.split(".")
    elif fmt == FormatoCodigo.GUION:
        parts = codigo.split("-")
    elif fmt == FormatoCodigo.COMPACTO:
        # Compacto: cada 2 dígitos es un segmento
        # "110101" → ["11", "01", "01"]
        parts = [codigo[i:i+2] for i in range(0, len(codigo), 2)]
    else:
        return []
    return [int(p) for p in parts if p.lstrip("-").isdigit()]


def _detect_section(
    raw: CuentaRaw,
    segments: list[int],
) -> str:
    """Detecta la sección del balance según el código o el nombre."""
    if not segments:
        return "sin_seccion"

    primer_segmento = segments[0]

    # Mapeo por primer dígito del código
    if primer_segmento == 1:
        return "activo"
    elif primer_segmento == 2:
        return "pasivo"
    elif primer_segmento == 3:
        return "patrimonio"
    elif primer_segmento == 4:
        return "resultados"
    elif primer_segmento == 5:
        return "cuentas_orden"

    # Fallback: detectar por nombre
    nombre = raw.nombre.lower()
    for word, section in _SECTION_KEYWORDS:
        if word in nombre:
            return section

    return "sin_seccion"


_SECTION_KEYWORDS: list[tuple[str, str]] = [
    ("activo", "activo"),
    ("pasivo", "pasivo"),
    ("patrimonio", "patrimonio"),
    ("capital", "patrimonio"),
    ("resultado", "resultados"),
    ("ingreso", "resultados"),
    ("gasto", "resultados"),
    ("perdida", "resultados"),
    ("ganancia", "resultados"),
    ("cuenta de orden", "cuentas_orden"),
]
