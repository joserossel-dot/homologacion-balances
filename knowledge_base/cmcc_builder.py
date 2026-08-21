"""
cmcc_builder.py — Construye la base de conocimiento CMCC desde gold_standard.db.

Lee gold_standard.db y gold_records, agrupa por código CMCC,
detecta variantes, familias, frecuencias, confianza, secciones, empresas.

Salida: knowledge_base/cmcc_knowledge.json
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge_base.cmcc_models import (
    CodeEntry,
    FamilyGroup,
    KnowledgeBase,
    VariantInfo,
    inferir_nivel,
    inferir_seccion,
)

logger = logging.getLogger(__name__)

GOLD_DB = Path("gold_standard.db")
OUTPUT_JSON = Path("knowledge_base/cmcc_knowledge.json")

_PREFIJOS_FAMILIA = ["AC", "ANC", "PC", "PNC", "PAT", "ER"]


def _normalizar(nombre: str) -> str:
    import re
    n = nombre.lower().strip()
    n = re.sub(r"[^a-z0-9áéíóúñü ]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _hoy() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _leer_gold_standard(db_path: str | Path) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        logger.warning("Gold Standard DB no encontrado: %s", db_path)
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM gold_standard").fetchall()
    registros = [dict(r) for r in rows]

    conn.close()
    return registros


def _leer_gold_records(db_path: str | Path) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM gold_records").fetchall()
    registros = [dict(r) for r in rows]

    conn.close()
    return registros


def _elegir_canonica(variantes: list[VariantInfo]) -> str:
    if not variantes:
        return ""

    candidatas = [v for v in variantes if not v.nombre.isupper() and len(v.nombre) > 3]
    if not candidatas:
        candidatas = variantes

    return max(candidatas, key=lambda v: (v.frecuencia, len(v.nombre))).nombre


def build_knowledge_base(
    db_path: str | Path = GOLD_DB,
    output_path: str | Path | None = OUTPUT_JSON,
) -> KnowledgeBase:
    records = _leer_gold_standard(db_path)
    gold_recs = _leer_gold_records(db_path)

    if not records:
        logger.warning("No hay registros en gold_standard. Base de conocimiento vacía.")
        kb = KnowledgeBase(generated_at=_hoy(), total_codes=0, total_records=0)
        if output_path:
            _guardar(kb, Path(output_path))
        return kb

    # Index gold_records por account_name para enriquecer
    rec_by_name: dict[str, list[dict[str, Any]]] = {}
    for r in gold_recs:
        name = r.get("account_name", "").strip()
        if name:
            rec_by_name.setdefault(_normalizar(name), []).append(r)

    # Agrupar por codigo_estandar
    grupos: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        code = r.get("codigo_estandar", "").strip()
        if not code:
            continue
        grupos.setdefault(code, []).append(r)

    code_entries: dict[str, CodeEntry] = {}

    for codigo, miembros in sorted(grupos.items()):
        variantes_map: dict[str, VariantInfo] = {}
        empresas: list[str] = []
        archivos: list[str] = []
        naturaleza = ""
        usage_count = 0
        fecha_primera = ""
        fecha_ultima = ""

        for m in miembros:
            nombre = m.get("nombre_cuenta", "").strip()
            norm = _normalizar(nombre)

            if not nombre:
                continue

            if norm not in variantes_map:
                variantes_map[norm] = VariantInfo(nombre=nombre, normalized=norm)

            v = variantes_map[norm]
            v.frecuencia += 1

            # Enriquecer desde gold_records
            recs = rec_by_name.get(norm, [])
            for rec in recs:
                archivo = rec.get("source_file", "")
                if archivo:
                    archivos.append(archivo)

                reviewer = rec.get("reviewer", "")
                if reviewer and reviewer not in v.source_records:
                    v.source_records.append(reviewer)

                usos = rec.get("usage_count", 0)
                usage_count = max(usage_count, usos)

                revision = rec.get("review_date", "")
                if revision:
                    if not fecha_primera or revision < fecha_primera:
                        fecha_primera = revision
                    if not fecha_ultima or revision > fecha_ultima:
                        fecha_ultima = revision

                nat = rec.get("account_nature", "")
                if nat and not naturaleza:
                    naturaleza = nat

        # Confianza por variante: frecuencia relativa dentro del código
        total_variantes = sum(v.frecuencia for v in variantes_map.values())
        for v in variantes_map.values():
            v.confianza = v.frecuencia / total_variantes if total_variantes else 0.0

        # Extraer empresas de archivos
        for archivo in archivos:
            # Try to extract empresa from filename
            import re as _re
            for sep in [" - ", "  ", "_"]:
                parts = archivo.replace(".pdf", "").split(sep)
                for p in parts:
                    p = p.strip()
                    if p and not _re.match(r'^(Balance|EEFF|balance|BALANCE|dic|DIC|V\d|CLASIFICADO|ORIGINAL|General|GENERAL|S\.?A\.?|Ltda|SA|LTDA)\b', p):
                        if p not in empresas:
                            empresas.append(p)

        variantes_list = sorted(variantes_map.values(), key=lambda v: -v.frecuencia)

        variante_canonica = _elegir_canonica(variantes_list)
        seccion = inferir_seccion(codigo)
        nivel = inferir_nivel(codigo)

        confianza_total = sum(v.confianza * v.frecuencia for v in variantes_list) / max(total_variantes, 1)

        entry = CodeEntry(
            codigo=codigo,
            nombre=variante_canonica,
            frecuencia=total_variantes,
            variantes=variantes_list,
            seccion=seccion,
            nivel=nivel,
            empresas=list(set(empresas)),
            archivos=list(set(archivos)),
            naturaleza=naturaleza,
            usage_count=usage_count,
            fecha_primera=fecha_primera,
            fecha_ultima=fecha_ultima,
            confianza=confianza_total,
            variante_canonica=variante_canonica,
        )
        code_entries[codigo] = entry

    # Construir familias
    familias: list[FamilyGroup] = []
    for prefijo in _PREFIJOS_FAMILIA:
        miembros_familia = sorted(
            [c for c in code_entries if c.startswith(prefijo)]
        )
        if not miembros_familia:
            continue
        total_freq = sum(code_entries[c].frecuencia for c in miembros_familia)
        ejemplo = miembros_familia[0]
        seccion = code_entries[ejemplo].seccion if ejemplo in code_entries else inferir_seccion(prefijo)
        familias.append(FamilyGroup(
            nombre=prefijo,
            prefijo=prefijo,
            seccion=seccion,
            nivel_base=2,
            miembros=miembros_familia,
            total_frecuencia=total_freq,
        ))

    kb = KnowledgeBase(
        generated_at=_hoy(),
        total_codes=len(code_entries),
        total_records=len(records),
        codes=code_entries,
        families=familias,
    )

    if output_path:
        _guardar(kb, Path(output_path))

    logger.info(
        "Knowledge Base construida: %d códigos, %d registros, %d familias",
        kb.total_codes, kb.total_records, len(kb.families),
    )
    return kb


def _guardar(kb: KnowledgeBase, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(kb.to_dict(), f, ensure_ascii=False, indent=2)
    logger.info("Knowledge Base guardada: %s", path)
