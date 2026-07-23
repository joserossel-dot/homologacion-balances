from __future__ import annotations

import json
from typing import Any


def generate_dictionary_entries(
    rule_candidates: list[dict],
    synonyms: list[dict],
    *,
    max_per_synonym: int = 5,
) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()

    for c in rule_candidates:
        semantic_type = c.get("suggested_semantic_type", "")
        standard_code = _type_to_code(semantic_type)
        if not standard_code:
            continue

        keywords = c.get("suggested_keywords", [])
        if not keywords:
            continue

        for kw in keywords:
            norm = kw.strip().lower()
            if norm and norm not in seen:
                seen.add(norm)
                entries.append({
                    "cuenta_original": kw,
                    "codigo_estandar": standard_code,
                    "fuente": "knowledge_generator",
                    "confidence": c.get("confidence_score", 0.5),
                    "cluster_id": c.get("cluster_id", ""),
                })

    for s in synonyms:
        semantic_type = _synonym_type(s.get("group_label", ""))
        standard_code = _type_to_code(semantic_type)
        if not standard_code:
            continue

        variants = s.get("variants", [])
        for v in variants[:max_per_synonym]:
            if v and v not in seen:
                seen.add(v)
                entries.append({
                    "cuenta_original": v,
                    "codigo_estandar": standard_code,
                    "fuente": "knowledge_generator_synonyms",
                    "confidence": 0.7,
                    "cluster_id": "",
                })

    return entries


def generate_gold_standard_entries(
    rule_candidates: list[dict],
    *,
    max_per_candidate: int = 3,
) -> list[dict]:
    entries: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for c in rule_candidates:
        semantic_type = c.get("suggested_semantic_type", "")
        standard_code = _type_to_code(semantic_type)
        if not standard_code:
            continue

        examples = c.get("source_files", [])
        for ex in examples[:max_per_candidate]:
            key = (ex, semantic_type)
            if key not in seen:
                seen.add(key)
                entries.append({
                    "source_file": ex,
                    "account_code_original": "",
                    "account_name": c.get("representative", ""),
                    "account_nature": c.get("dominant_nature", ""),
                    "suggested_code": standard_code,
                    "suggested_confidence": c.get("confidence_score", 0.5),
                    "final_code": standard_code,
                    "reviewer": "knowledge_generator",
                    "review_date": "",
                    "comments": f"Sugerido por Knowledge Generator. Cluster: {c.get('cluster_id', '')}. Tipo: {semantic_type}.",
                    "usage_count": 0,
                    "last_used": "",
                })

    return entries


SEMANTIC_CODE_MAP: dict[str, str] = {
    "asset": "AC.01",
    "liability": "PC.01",
    "revenue": "ER.01",
    "expense": "ER.02",
    "contra_asset": "ANC.01",
    "contra_liability": "PNC.05",
    "contra_equity": "PAT.04",
    "equity": "PAT.01",
}


def _type_to_code(semantic_type: str) -> str | None:
    return SEMANTIC_CODE_MAP.get(semantic_type)


def _synonym_type(label: str) -> str:
    label_lower = label.lower()
    if any(kw in label_lower for kw in ("caja", "banco", "inventario", "cliente", "cuentas por cobrar", "deudor", "iva credito", "anticipo")):
        return "asset"
    if any(kw in label_lower for kw in ("proveedor", "cuentas por pagar", "acreedor", "iva debito", "remuneracion", "sueldo", "honorario")):
        return "liability"
    if any(kw in label_lower for kw in ("capital", "utilidad", "resultado", "accion", "reserva")):
        return "equity"
    if any(kw in label_lower for kw in ("gasto", "depreciacion", "amortizacion", "perdida")):
        return "expense"
    if any(kw in label_lower for kw in ("ingreso", "comision", "venta")):
        return "revenue"
    if any(kw in label_lower for kw in ("maquinaria", "terreno", "vehiculo", "mueble", "edificio", "construccion")):
        return "asset"
    if any(kw in label_lower for kw in ("leasing", "factoring", "prestamo", "credito")):
        return "liability"
    return "asset"
