"""Extractor Trainer — aprendizaje automático de formatos (Sprint 35).

`TableProfileTrainer` recibe los documentos de una familia y aprende su
perfil estructural:

  - nº de filas de encabezado, fila de inicio/fin de la tabla
  - columnas existentes y su orden (código, nombre, montos semánticos:
    activo, pasivo, pérdidas, ganancias, débitos, créditos)
  - patrón de totales, patrón de códigos, patrón numérico, layout

Cada documento se analiza con los mismos detectores del ecosistema
(FormatAnalyzer, DocumentFingerprint) y el parser de líneas de referencia
(parsear_linea) SOLO como "ground truth" de filas contables — NO se
modifica el Parser Universal.

El resultado es un `TableProfile` por familia (serializable a JSON).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from ..analyzer import FormatAnalyzer
from ..knowledge.fingerprint import DocumentFingerprint, extract_preview_lines
from .profile import (
    AMOUNT_HEADER_KEYWORDS,
    AMOUNT_ORDER,
    ColumnProfile,
    FooterProfile,
    HeaderProfile,
    TableProfile,
)

# Solo para "ground truth" de filas contables (referencia, no modifica nada).
from parser_universal import (
    PATRON_MONTOS,
    PATRON_TOTAL,
    detectar_formato_codigo,
    detectar_separador_miles,
    parsear_linea,
)


def _es_monto(token: str) -> bool:
    """True si el token es un monto (incluye OCR 'o'→'0' y '-')."""
    t = token.replace("$", "").strip()
    if t == "-":
        return True
    if t in ("o", "O"):
        t = "0"
    return bool(PATRON_MONTOS.fullmatch(t))


def _count_amounts(tokens: list[str]) -> int:
    """Nº de tokens de monto al final de la fila (como ParserPDF)."""
    n = 0
    for t in reversed(tokens):
        if _es_monto(t):
            n += 1
        else:
            break
    return n


def _majority(values: list[Any], default: Any = None) -> Any:
    """Valor más frecuente; empates resueltos por el valor menor."""
    if not values:
        return default
    counts = Counter(values)
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def _mode(values: list[int]) -> int:
    return _majority(values, default=0)


def _top_keywords(lists: list[list[str]], limit: int = 8) -> list[str]:
    """Agrega listas de keywords por frecuencia (orden estable)."""
    counts: Counter[str] = Counter()
    for items in lists:
        seen: set[str] = set()
        for k in items:
            if k not in seen:
                counts[k] += 1
                seen.add(k)
    return [k for k, _ in counts.most_common(limit)]


def _default_amount_keys(document_type: str, n: int) -> list[str]:
    """Tipos de columna de monto por defecto según nº de montos y tipo."""
    if n <= 0:
        return []
    if n == 1:
        return ["MONTO"]
    if document_type == "ESTADO_RESULTADOS":
        base = ["PERDIDA", "GANANCIA"] if n <= 2 else ["ACTIVO", "PASIVO", "PERDIDA", "GANANCIA"]
    elif document_type == "NOTAS":
        base = ["MONTO"]
    else:
        base = ["ACTIVO", "PASIVO", "PERDIDA", "GANANCIA"]
    if n <= len(base):
        return base[-n:]
    return base + ["MONTO"] * (n - len(base))


def _resolve_amount_keys(lines: list[str], table_start: int, n_amounts: int,
                         document_type: str) -> list[str]:
    """Tipos de columnas de monto: encabezados (débito/crédito, activo/
    pasivo, pérdida/ganancia) o defaults según el tipo de documento.

    Solo inspecciona las líneas de encabezado (antes de la primera fila
    contable): las filas de la tabla contienen nombres de cuenta que
    dispararían falsos positivos ("Ingresos por ventas" → ganancia).
    """
    if n_amounts <= 0:
        return []
    text = " ".join(lines[:max(table_start, 0)]).lower()
    detected: list[str] = []
    for key in AMOUNT_ORDER:
        if any(re.search(r"\b" + re.escape(v) + r"\b", text) for v in AMOUNT_HEADER_KEYWORDS[key]):
            detected.append(key)
    if len(detected) >= n_amounts:
        return detected[-n_amounts:]
    return _default_amount_keys(document_type, n_amounts)


def _summary_position(total_indices: list[int], n_lines: int) -> str:
    """TOP | MIDDLE | BOTTOM | NONE según la posición de las filas de total."""
    if not total_indices or n_lines <= 0:
        return "NONE"
    first = total_indices[0]
    last = total_indices[-1]
    if first / n_lines < 0.3:
        return "TOP"
    if last / n_lines > 0.7:
        return "BOTTOM"
    return "MIDDLE"


class TableProfileTrainer:
    """Aprende el perfil estructural de una familia documental."""

    def __init__(self, analyzer: Optional[FormatAnalyzer] = None):
        self._analyzer = analyzer or FormatAnalyzer()

    # ------------------------------------------------------------------
    # Análisis de un documento
    # ------------------------------------------------------------------

    def analyze_document(self, document) -> dict[str, Any]:
        """Analiza un documento (Path o lista de líneas) → estructura.

        Devuelve dict con: signature, fingerprint, filas contables,
        encabezado, tabla (inicio/fin), columnas, totales.
        """
        if isinstance(document, (str, Path)):
            lines = extract_preview_lines(document)
        else:
            lines = [l for l in (document or []) if l.strip()]

        if not lines:
            return {"valid": False, "signature": None, "lines": []}

        signature = self._analyzer.analyze(lines)
        fingerprint = DocumentFingerprint.build(signature, lines)

        primer_tokens = [l.split()[0] if l.split() else "" for l in lines[:60]]
        formato = detectar_formato_codigo(primer_tokens)
        muestra: list[str] = []
        for l in lines[:80]:
            muestra.extend(PATRON_MONTOS.findall(l))
        separador = detectar_separador_miles(muestra)

        rows: list[dict[str, Any]] = []
        for i, l in enumerate(lines):
            try:
                cuenta = parsear_linea(l, i, formato, separador)
            except Exception:  # noqa: BLE001 — documento atípico
                cuenta = None
            if cuenta is None:
                continue
            # Solo filas contables reales: con código, monto o total.
            # Excluye líneas de encabezado/pie sin números ("Codigo Cuenta
            # Activo Pasivo") que parsear_linea aceptaría con monto=None.
            if cuenta.codigo is not None or cuenta.monto is not None or cuenta.es_total:
                rows.append({"i": i, "cuenta": cuenta, "tokens": l.split()})

        if not rows:
            return {
                "valid": False, "signature": signature, "lines": lines,
                "rows": [], "header_rows": 0, "table_start": None,
                "table_end": None, "trailing_rows": 0, "amount_counts": {},
                "amount_mode": 0, "has_codes": False, "columns": [],
                "summary_position": fingerprint.summary_position,
                "total_rows": [], "total_keywords": [],
                "header_keywords": fingerprint.header_keywords,
                "footer_keywords": fingerprint.footer_keywords,
            }

        table_start = rows[0]["i"]
        table_end = rows[-1]["i"]
        header_rows = table_start  # líneas no contables previas a la tabla
        trailing_rows = len(lines) - 1 - table_end

        amount_counts: Counter[int] = Counter(
            _count_amounts(r["tokens"]) for r in rows
        )
        amount_mode = amount_counts.most_common(1)[0][0]
        has_codes = any(r["cuenta"].codigo is not None for r in rows)

        total_rows = [r for r in rows if r["cuenta"].es_total]
        totals_idx = [r["i"] for r in total_rows]
        total_keywords: list[str] = []
        for r in total_rows:
            m = PATRON_TOTAL.match(r["cuenta"].nombre.strip())
            if m:
                kw = m.group(0).strip().lower()
                if kw and kw not in total_keywords:
                    total_keywords.append(kw)

        amount_keys = _resolve_amount_keys(
            lines, table_start, amount_mode, signature.document_type.value,
        )

        columns: list[dict[str, Any]] = []
        if has_codes:
            columns.append({"key": "CODIGO", "side": "left", "position": 0})
        columns.append({"key": "NOMBRE", "side": "left", "position": 1 if has_codes else 0})
        for j, key in enumerate(amount_keys):
            columns.append({"key": key, "side": "right",
                            "position": len(amount_keys) - j})

        return {
            "valid": True,
            "signature": signature,
            "fingerprint": fingerprint,
            "lines": lines,
            "rows": rows,
            "header_rows": header_rows,
            "table_start": table_start,
            "table_end": table_end,
            "trailing_rows": trailing_rows,
            "amount_counts": dict(amount_counts),
            "amount_mode": amount_mode,
            "has_codes": has_codes,
            "columns": columns,
            "summary_position": fingerprint.summary_position or _summary_position(
                totals_idx, len(lines),
            ),
            "total_rows": len(total_rows),
            "total_keywords": total_keywords,
            "header_keywords": fingerprint.header_keywords,
            "footer_keywords": fingerprint.footer_keywords,
        }

    # ------------------------------------------------------------------
    # Aprendizaje del perfil de una familia
    # ------------------------------------------------------------------

    def train(
        self,
        family_id: str,
        family_name: str,
        documents: list,
    ) -> TableProfile:
        """Genera el TableProfile de la familia a partir de sus documentos.

        `documents`: lista de Path (o str) o listas de líneas de texto.
        """
        docs = [d for d in (self.analyze_document(doc) for doc in documents) if d["valid"]]
        n_parseables = len(docs)

        profile = TableProfile(family_id=family_id, family_name=family_name)
        profile.docs_total = n_parseables
        if n_parseables == 0:
            return profile

        # Núcleo coherente: solo los documentos con la estructura dominante.
        # Descarta ruido del cluster (otro tipo de documento, nº de columnas
        # dispar, etc.) que solo ensuciaría el perfil.
        def _structure(d: dict[str, Any]) -> tuple:
            return (
                d["signature"].document_type.value,
                d["signature"].layout.value,
                d["amount_mode"],
                bool(d["has_codes"]),
            )

        core_key = Counter(_structure(d) for d in docs).most_common(1)[0][0]
        core = [d for d in docs if _structure(d) == core_key]
        outliers = n_parseables - len(core)
        docs = core
        n = len(docs)
        profile.n_documents = n
        profile.docs_outliers = outliers
        if n == 0:
            return profile

        profile.layout = _majority([d["signature"].layout.value for d in docs])
        profile.document_type = _majority(
            [d["signature"].document_type.value for d in docs]
        )
        profile.code_pattern = _majority(
            [d["signature"].code_pattern.value for d in docs]
        )
        profile.numeric_pattern = _majority(
            [d["signature"].numeric_pattern.value for d in docs]
        )
        profile.header_rows = _mode([d["header_rows"] for d in docs])
        profile.table_start_row = _mode([d["table_start"] for d in docs])
        profile.table_end_row = _mode([d["table_end"] for d in docs])
        profile.summary_position = _majority(
            [d["summary_position"] for d in docs], default="NONE",
        )
        profile.confidence = round(
            sum(d["signature"].confidence for d in docs) / n, 4,
        )

        # Columnas agregadas: (key, position) ancla la columna de monto;
        # cada documento contribuye 1 por par → detection_rate <= 1.0.
        pair_counts: Counter[tuple[str, int]] = Counter()
        for d in docs:
            seen: set[tuple[str, int]] = set()
            for col in d["columns"]:
                pair = (col["key"], col["position"])
                if pair not in seen:
                    seen.add(pair)
                    pair_counts[pair] += 1

        has_codes = bool(_majority([d["has_codes"] for d in docs], default=False))
        columns: list[ColumnProfile] = []

        def _col(key: str, side: str, position: int) -> ColumnProfile:
            docs_presentes = pair_counts[(key, position)]
            return ColumnProfile(
                key=key, side=side, position=position,
                detection_rate=round(docs_presentes / n, 4),
                docs=docs_presentes,
            )

        if has_codes:
            columns.append(_col("CODIGO", "left", 0))
        columns.append(_col("NOMBRE", "left", 1 if has_codes else 0))

        max_pos = max(
            (pos for (key, pos) in pair_counts
             if key not in ("CODIGO", "NOMBRE")),
            default=0,
        )
        for pos in range(max_pos, 0, -1):
            keys = sorted(
                {k for (k, p) in pair_counts if p == pos and k not in ("CODIGO", "NOMBRE")},
                key=lambda k: (pair_counts[(k, pos)], -AMOUNT_ORDER.index(k)),
            )
            if not keys:
                continue
            best_key = keys[-1]
            columns.append(_col(best_key, "right", pos))

        profile.columns = columns
        profile.code_column = next((c for c in columns if c.key == "CODIGO"), None)
        profile.name_column = next((c for c in columns if c.key == "NOMBRE"), None)
        profile.amount_columns = sorted(
            [c for c in columns if c.side == "right"],
            key=lambda c: -c.position,
        )

        # Totales.
        profile.total_keywords = _top_keywords(
            [d["total_keywords"] for d in docs], limit=6,
        )
        amount_mode = _majority([d["amount_mode"] for d in docs], default=0)
        profile.totals_pattern = (
            f"{profile.summary_position.lower()}:{amount_mode}col"
        )

        # Encabezado / pie.
        profile.header = HeaderProfile(
            rows=profile.header_rows,
            row_counts=dict(Counter(d["header_rows"] for d in docs)),
            keywords=_top_keywords([d["header_keywords"] for d in docs]),
        )
        profile.footer = FooterProfile(
            trailing_rows=_mode([d["trailing_rows"] for d in docs]),
            totals_position=profile.summary_position,
            total_keywords=list(profile.total_keywords),
            keywords=_top_keywords([d["footer_keywords"] for d in docs]),
        )

        return profile
