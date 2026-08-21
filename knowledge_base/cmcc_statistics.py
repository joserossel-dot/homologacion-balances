"""
cmcc_statistics.py — Estadísticas y validación de la base de conocimiento CMCC.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from knowledge_base.cmcc_builder import build_knowledge_base
from knowledge_base.cmcc_models import KnowledgeBase

logger = logging.getLogger(__name__)


def load_knowledge_base(path: str | Path = "knowledge_base/cmcc_knowledge.json") -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        logger.warning("Knowledge Base no encontrada: %s", path)
        return {}
    with open(path) as f:
        return json.load(f)


def knowledge_stats(kb: KnowledgeBase | None = None) -> dict[str, Any]:
    if kb is None:
        data = load_knowledge_base()
        if not data:
            return {}
        codes = data.get("codes", {})
        families = data.get("families", [])
        meta = data.get("metadata", {})
    else:
        codes = {k: v.to_dict() for k, v in kb.codes.items()}
        families = [f.to_dict() for f in kb.families]
        meta = kb.to_dict().get("metadata", {})

    total_codes = len(codes)
    total_variantes = sum(len(c["variantes"]) for c in codes.values())
    total_registros = sum(c["frecuencia"] for c in codes.values())

    # Códigos con alta/moderada/baja confianza
    alta = sum(1 for c in codes.values() if c.get("confianza", 0) >= 0.8)
    media = sum(1 for c in codes.values() if 0.5 <= c.get("confianza", 0) < 0.8)
    baja = sum(1 for c in codes.values() if c.get("confianza", 0) < 0.5)

    # Variantes por código
    avg_variantes = round(total_variantes / total_codes, 2) if total_codes else 0

    # Por sección
    by_section: dict[str, int] = {}
    for c in codes.values():
        sec = c.get("seccion", "Desconocido")
        by_section[sec] = by_section.get(sec, 0) + 1

    # Familias
    family_codes = sum(len(f.get("miembros", [])) for f in families) if families else 0

    return {
        "total_codes": total_codes,
        "total_variantes": total_variantes,
        "total_records": total_registros,
        "avg_variantes_per_code": avg_variantes,
        "confidence_distribution": {
            "alta_>=80": alta,
            "media_50-80": media,
            "baja_<50": baja,
        },
        "by_section": dict(sorted(by_section.items(), key=lambda x: -x[1])),
        "families": [
            {
                "nombre": f.get("nombre"),
                "miembros": len(f.get("miembros", [])),
                "total_frecuencia": f.get("total_frecuencia", 0),
            }
            for f in (families or [])
        ],
    }


def generate_validation_report(
    kb: KnowledgeBase | None = None,
    output_path: str | Path = "reports/cmcc_knowledge_validation.md",
) -> str:
    if kb is None:
        build_knowledge_base()
        data = load_knowledge_base()
        meta = data.get("metadata", {})
        codes = data.get("codes", {})
        families = data.get("families", [])
    else:
        meta = kb.to_dict().get("metadata", {})
        codes = {k: v.to_dict() for k, v in kb.codes.items()}
        families = [f.to_dict() for f in kb.families]

    stats = knowledge_stats(kb)

    lines: list[str] = []
    lines.append("# CMCC Knowledge Base — Validation Report")
    lines.append("")
    lines.append(f"**Generado:** {meta.get('generated_at', 'N/A')}")
    lines.append(f"**Fuente:** `gold_standard.db`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Códigos CMCC | {stats.get('total_codes', 0)} |")
    lines.append(f"| Variantes de nombre | {stats.get('total_variantes', 0)} |")
    lines.append(f"| Registros totales | {stats.get('total_records', 0)} |")
    lines.append(f"| Variantes promedio por código | {stats.get('avg_variantes_per_code', 0)} |")
    lines.append("")
    lines.append("## Distribución de confianza")
    lines.append("")
    lines.append("| Nivel | Códigos |")
    lines.append("|-------|---------|")
    conf_dist = stats.get("confidence_distribution", {})
    lines.append(f"| Alta (≥0.80) | {conf_dist.get('alta_>=80', 0)} |")
    lines.append(f"| Media (0.50–0.80) | {conf_dist.get('media_50-80', 0)} |")
    lines.append(f"| Baja (<0.50) | {conf_dist.get('baja_<50', 0)} |")
    lines.append("")
    lines.append("## Familias CMCC")
    lines.append("")
    lines.append("| Familia | Miembros | Frecuencia total |")
    lines.append("|---------|----------|------------------|")
    for f in stats.get("families", []):
        lines.append(f"| {f.get('nombre', '')} | {f.get('miembros', 0)} | {f.get('total_frecuencia', 0)} |")
    lines.append("")
    lines.append("## Distribución por sección contable")
    lines.append("")
    lines.append("| Sección | Códigos |")
    lines.append("|---------|---------|")
    for sec, cnt in stats.get("by_section", {}).items():
        lines.append(f"| {sec} | {cnt} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Detalle por código CMCC")
    lines.append("")
    lines.append("| Código | Nombre canónico | Variantes | Frecuencia | Confianza | Sección |")
    lines.append("|--------|-----------------|-----------|------------|-----------|---------|")
    for codigo in sorted(codes.keys()):
        c = codes[codigo]
        lines.append(
            f"| {codigo} | {c.get('nombre', ''):40s} | "
            f"{len(c.get('variantes', [])):2d} | {c.get('frecuencia', 0):3d} | "
            f"{c.get('confianza', 0):.2f} | {c.get('seccion', '')} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Variantes por código (top variantes)")
    lines.append("")
    for codigo in sorted(codes.keys()):
        c = codes[codigo]
        lines.append(f"### {codigo} — {c.get('nombre', '')}")
        lines.append("")
        if c.get("variantes"):
            lines.append("| Variante | Frecuencia | Confianza |")
            lines.append("|----------|------------|-----------|")
            for v in c.get("variantes", [])[:5]:
                lines.append(f"| {v.get('nombre', ''):40s} | {v.get('frecuencia', 0):3d} | {v.get('confianza', 0):.2f} |")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Reporte generado por cmcc_statistics.py*")

    text = "\n".join(lines)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    logger.info("Reporte de validación: %s", path)
    return text
