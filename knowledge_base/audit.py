from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

KB_PATH = Path("knowledge_base/cmcc_knowledge.json")
GOLD_DB = Path("gold_standard.db")
SIMILARITY_THRESHOLD = 0.85
LOW_EVIDENCE_MAX_FREQ = 2
LOW_EVIDENCE_MAX_CONF = 0.15
INCOMPLETE_FAMILY_THRESHOLD = 3


def load_kb(path: str | Path = KB_PATH) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def audit_knowledge_base(kb_data: dict[str, Any] | None = None) -> dict[str, Any]:
    if kb_data is None:
        kb_data = load_kb()
    if not kb_data:
        return {"error": "Knowledge Base no encontrada"}

    codes = kb_data.get("codes", {})
    families = kb_data.get("families", [])
    meta = kb_data.get("metadata", {})

    findings: dict[str, Any] = {}

    findings["duplicate_codes"] = _check_duplicate_codes(codes)
    findings["repeated_variants"] = _check_repeated_variants(codes)
    findings["cross_code_variants"] = _check_cross_code_variants(codes)
    findings["low_evidence_codes"] = _check_low_evidence(codes)
    findings["incomplete_families"] = _check_incomplete_families(families)
    findings["hierarchy_inconsistencies"] = _check_hierarchy(codes, families)
    findings["similar_variants_diff_codes"] = _check_similar_variants(codes)
    findings["avg_confidence_per_code"] = _avg_confidence_per_code(codes)
    findings["avg_confidence_per_family"] = _avg_confidence_per_family(codes, families)
    findings["gold_coverage"] = _check_gold_coverage(codes)

    findings["total_codes"] = len(codes)
    findings["total_variants"] = sum(len(c["variantes"]) for c in codes.values())
    findings["total_families"] = len(families)
    findings["conflictive_variants"] = findings.get("cross_code_variants", {}).get("total_conflictive", 0) or 0
    findings["low_evidence_count"] = len(findings.get("low_evidence_codes", {}).get("codes", []))
    findings["codes_recommended_for_review"] = sorted(
        set(
            list(findings.get("low_evidence_codes", {}).get("codes", []))
            + list(findings.get("cross_code_variants", {}).get("variants", {}).keys())
        )
    )

    return findings


def _check_duplicate_codes(codes: dict[str, Any]) -> dict[str, Any]:
    conflicts = []
    for codigo, entry in codes.items():
        brothers = [c for c in codes if c != codigo and c.startswith(codigo.split(".")[0])]
        for b in brothers:
            if entry.get("nombre", "").lower() == codes[b].get("nombre", "").lower():
                conflicts.append({"codigo_a": codigo, "codigo_b": b, "nombre_compartido": entry["nombre"]})
    return {"conflicts": conflicts, "total": len(conflicts)}


def _check_repeated_variants(codes: dict[str, Any]) -> dict[str, Any]:
    variant_to_codes: defaultdict[str, list[str]] = defaultdict(list)
    for codigo, entry in codes.items():
        for v in entry.get("variantes", []):
            variant_to_codes[v["nombre"]].append(codigo)
    repeated = {k: v for k, v in variant_to_codes.items() if len(set(v)) > 1}
    return {
        "repeated": [{"variant": k, "codes": sorted(set(v))} for k, v in repeated.items()],
        "total": len(repeated),
    }


def _check_cross_code_variants(codes: dict[str, Any]) -> dict[str, Any]:
    norm_to_codes: defaultdict[str, list[str]] = defaultdict(list)
    for codigo, entry in codes.items():
        for v in entry.get("variantes", []):
            key = v["nombre"].lower().strip()
            norm_to_codes[key].append(codigo)
    cross = {k: sorted(set(v)) for k, v in norm_to_codes.items() if len(set(v)) > 1}
    return {
        "variants": cross,
        "total_conflictive": len(cross),
        "details": [{"normalized": k, "codes": v} for k, v in sorted(cross.items())],
    }


def _check_low_evidence(codes: dict[str, Any]) -> dict[str, Any]:
    low = []
    for codigo, entry in codes.items():
        freq = entry.get("frecuencia", 0)
        conf = entry.get("confianza", 0)
        variants = entry.get("variantes", [])
        has_only_noise = all(v.get("confianza", 0) < 0.1 for v in variants) if variants else True
        reasons = []
        if freq <= LOW_EVIDENCE_MAX_FREQ:
            reasons.append(f"frecuencia_baja({freq})")
        if conf < LOW_EVIDENCE_MAX_CONF:
            reasons.append(f"confianza_baja({conf:.4f})")
        if freq == 1 and len(variants) == 1:
            reasons.append("registro_unico")
        if has_only_noise and freq > 0:
            reasons.append("solo_variantes_ruido")
        if reasons:
            low.append({"codigo": codigo, "frecuencia": freq, "confianza": round(conf, 4), "variantes": len(variants), "reasons": reasons})
    return {"codes": [l["codigo"] for l in low], "details": low, "total": len(low)}


def _check_incomplete_families(families: list[dict[str, Any]]) -> dict[str, Any]:
    incomplete = []
    for f in families:
        miembros = f.get("miembros", [])
        freq = f.get("total_frecuencia", 0)
        reasons = []
        if len(miembros) <= INCOMPLETE_FAMILY_THRESHOLD:
            reasons.append(f"pocos_miembros({len(miembros)})")
        if freq <= 5:
            reasons.append(f"baja_frecuencia_total({freq})")
        if reasons:
            incomplete.append({"familia": f["nombre"], "miembros": len(miembros), "total_frecuencia": freq, "reasons": reasons})
    return {"incomplete": incomplete, "total": len(incomplete)}


def _check_hierarchy(codes: dict[str, Any], families: list[dict[str, Any]]) -> dict[str, Any]:
    family_map = {f["prefijo"]: f for f in families}
    issues = []
    for codigo, entry in codes.items():
        pref = codigo.split(".")[0]
        if pref in family_map:
            expected_section = family_map[pref]["seccion"]
            actual_section = entry.get("seccion", "")
            if actual_section != expected_section:
                issues.append({
                    "codigo": codigo, "issue": "seccion_incorrecta",
                    "esperada": expected_section, "actual": actual_section,
                })
        if pref not in family_map:
            issues.append({"codigo": codigo, "issue": "sin_familia", "prefijo": pref})
        level = entry.get("nivel", 0)
        if "." in codigo and codigo.split(".")[1]:
            expected_level = 3
        elif "." in codigo:
            expected_level = 2
        else:
            expected_level = 1
        if level != expected_level:
            issues.append({
                "codigo": codigo, "issue": "nivel_incorrecto",
                "esperado": expected_level, "actual": level,
            })
    return {"issues": issues, "total": len(issues)}


def _check_similar_variants(codes: dict[str, Any]) -> dict[str, Any]:
    all_variants: list[tuple[str, str, str]] = []
    for codigo, entry in codes.items():
        for v in entry.get("variantes", []):
            all_variants.append((codigo, v["nombre"], v["nombre"].lower().strip()))

    similar_pairs = []
    seen = set()
    for i in range(len(all_variants)):
        for j in range(i + 1, len(all_variants)):
            c1, n1, norm1 = all_variants[i]
            c2, n2, norm2 = all_variants[j]
            if c1 == c2 or norm1 == norm2:
                continue
            key = tuple(sorted([norm1, norm2]))
            if key in seen:
                continue
            seen.add(key)
            ratio = SequenceMatcher(None, norm1, norm2).ratio()
            if ratio >= SIMILARITY_THRESHOLD:
                similar_pairs.append({
                    "variant_a": n1, "code_a": c1,
                    "variant_b": n2, "code_b": c2,
                    "similarity": round(ratio, 4),
                })
    similar_pairs.sort(key=lambda x: -x["similarity"])
    return {"similar_pairs": similar_pairs, "total": len(similar_pairs)}


def _avg_confidence_per_code(codes: dict[str, Any]) -> dict[str, Any]:
    per_code = {}
    total_conf = 0.0
    for codigo, entry in sorted(codes.items()):
        conf = entry.get("confianza", 0)
        per_code[codigo] = round(conf, 4)
        total_conf += conf
    avg = round(total_conf / len(codes), 4) if codes else 0
    return {"per_code": per_code, "average": avg}


def _avg_confidence_per_family(codes: dict[str, Any], families: list[dict[str, Any]]) -> dict[str, Any]:
    per_family = {}
    for f in families:
        pref = f["prefijo"]
        member_codes = [c for c in codes if c.startswith(pref)]
        if not member_codes:
            continue
        confs = [codes[c].get("confianza", 0) for c in member_codes]
        avg = round(sum(confs) / len(confs), 4)
        per_family[f["nombre"]] = {
            "average_confidence": avg,
            "member_codes": member_codes,
            "total_members": len(member_codes),
        }
    total_avg = round(
        sum(v["average_confidence"] for v in per_family.values()) / len(per_family), 4
    ) if per_family else 0
    return {"per_family": per_family, "average": total_avg}


def _check_gold_coverage(codes: dict[str, Any]) -> dict[str, Any]:
    gold_codes: set[str] = set()
    gold_records = 0
    if GOLD_DB.exists():
        conn = sqlite3.connect(str(GOLD_DB))
        try:
            rows = conn.execute("SELECT DISTINCT codigo_estandar FROM gold_standard").fetchall()
            gold_codes = {r[0] for r in rows}
            gold_records = conn.execute("SELECT COUNT(*) FROM gold_standard").fetchall()[0][0]
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
    kb_codes = set(codes.keys())
    covered = kb_codes & gold_codes
    missing_from_kb = gold_codes - kb_codes
    extra_in_kb = kb_codes - gold_codes
    return {
        "gold_standard_codes": len(gold_codes),
        "gold_standard_records": gold_records,
        "knowledge_base_codes": len(kb_codes),
        "codes_covered": len(covered),
        "coverage_pct": round(len(covered) / len(gold_codes) * 100, 2) if gold_codes else 0,
        "missing_from_knowledge_base": sorted(missing_from_kb),
        "extra_in_knowledge_base": sorted(extra_in_kb),
        "covered_codes": sorted(covered),
    }


def generate_audit_report(findings: dict[str, Any] | None = None, output_path: str | Path = "reports/knowledge_audit.md") -> str:
    if findings is None:
        findings = audit_knowledge_base()
    lines: list[str] = []
    lines.append("# Auditoría de Knowledge Base CMCC")
    lines.append("")
    lines.append(f"**Generado:** `{__import__('datetime').datetime.now().isoformat()}`")
    lines.append(f"**Fuente:** `{KB_PATH}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Total códigos CMCC | {findings.get('total_codes', 0)} |")
    lines.append(f"| Total variantes | {findings.get('total_variants', 0)} |")
    lines.append(f"| Total familias | {findings.get('total_families', 0)} |")
    lines.append(f"| Variantes conflictivas | {findings.get('conflictive_variants', 0)} |")
    lines.append(f"| Códigos con baja evidencia | {findings.get('low_evidence_count', 0)} |")
    lines.append(f"| Códigos recomendados para revisión | {len(findings.get('codes_recommended_for_review', []))} |")
    lines.append("")

    rec = findings.get("codes_recommended_for_review", [])
    if rec:
        lines.append("**Códigos recomendados para revisión:** " + ", ".join(rec))
        lines.append("")

    total_issues = (
        findings.get("duplicate_codes", {}).get("total", 0)
        + findings.get("repeated_variants", {}).get("total", 0)
        + findings.get("cross_code_variants", {}).get("total_conflictive", 0)
        + findings.get("low_evidence_codes", {}).get("total", 0)
        + findings.get("incomplete_families", {}).get("total", 0)
        + findings.get("hierarchy_inconsistencies", {}).get("total", 0)
        + findings.get("similar_variants_diff_codes", {}).get("total", 0)
    )
    lines.append(f"**Problemas totales detectados:** {total_issues}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 1. Códigos CMCC duplicados")
    lines.append("")
    dc = findings.get("duplicate_codes", {})
    if dc.get("conflicts"):
        lines.append("| Código A | Código B | Nombre compartido |")
        lines.append("|----------|----------|-------------------|")
        for c in dc["conflicts"]:
            lines.append(f"| {c['codigo_a']} | {c['codigo_b']} | {c['nombre_compartido']} |")
    else:
        lines.append("_Sin duplicados._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 2. Variantes repetidas")
    lines.append("")
    rv = findings.get("repeated_variants", {})
    if rv.get("repeated"):
        lines.append("| Variante | Códigos |")
        lines.append("|----------|---------|")
        for r in rv["repeated"]:
            lines.append(f"| {r['variant']} | {', '.join(r['codes'])} |")
    else:
        lines.append("_Sin variantes repetidas exactas._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 3. Variantes asignadas a distintos códigos")
    lines.append("")
    cv = findings.get("cross_code_variants", {})
    if cv.get("details"):
        lines.append("| Normalizado | Códigos |")
        lines.append("|-------------|---------|")
        for d in cv["details"]:
            lines.append(f"| `{d['normalized']}` | {', '.join(d['codes'])} |")
    else:
        lines.append("_Sin variantes cross-code._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 4. Códigos con muy poca evidencia")
    lines.append("")
    le = findings.get("low_evidence_codes", {})
    if le.get("details"):
        lines.append("| Código | Frecuencia | Confianza | Variantes | Razones |")
        lines.append("|--------|------------|-----------|-----------|---------|")
        for d in le["details"]:
            lines.append(f"| {d['codigo']} | {d['frecuencia']} | {d['confianza']} | {d['variantes']} | {', '.join(d['reasons'])} |")
    else:
        lines.append("_Sin códigos con baja evidencia._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 5. Familias incompletas")
    lines.append("")
    inc = findings.get("incomplete_families", {})
    if inc.get("incomplete"):
        lines.append("| Familia | Miembros | Frecuencia total | Razones |")
        lines.append("|---------|----------|------------------|---------|")
        for f in inc["incomplete"]:
            lines.append(f"| {f['familia']} | {f['miembros']} | {f['total_frecuencia']} | {', '.join(f['reasons'])} |")
    else:
        lines.append("_Todas las familias tienen cobertura adecuada._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 6. Inconsistencias de jerarquía")
    lines.append("")
    hi = findings.get("hierarchy_inconsistencies", {})
    if hi.get("issues"):
        lines.append("| Código | Problema | Esperado | Actual |")
        lines.append("|--------|----------|----------|--------|")
        for iss in hi["issues"]:
            lines.append(f"| {iss['codigo']} | {iss['issue']} | {iss.get('esperado', 'N/A')} | {iss.get('actual', 'N/A')} |")
    else:
        lines.append("_Sin inconsistencias de jerarquía._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 7. Variantes extremadamente similares con distinto código")
    lines.append("")
    sv = findings.get("similar_variants_diff_codes", {})
    if sv.get("similar_pairs"):
        lines.append("| Variante A | Código A | Variante B | Código B | Similitud |")
        lines.append("|------------|----------|------------|----------|-----------|")
        for p in sv["similar_pairs"][:30]:
            lines.append(f"| {p['variant_a']} | {p['code_a']} | {p['variant_b']} | {p['code_b']} | {p['similarity']} |")
        if len(sv["similar_pairs"]) > 30:
            lines.append(f"*... y {len(sv['similar_pairs']) - 30} pares más*")
    else:
        lines.append("_Sin variantes extremadamente similares entre distintos códigos._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 8. Confianza promedio por código")
    lines.append("")
    ac = findings.get("avg_confidence_per_code", {})
    lines.append(f"**Promedio general:** {ac.get('average', 0)}")
    lines.append("")
    lines.append("| Código | Confianza |")
    lines.append("|--------|-----------|")
    per_code = ac.get("per_code", {})
    for codigo in sorted(per_code):
        lines.append(f"| {codigo} | {per_code[codigo]} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 9. Confianza promedio por familia")
    lines.append("")
    af = findings.get("avg_confidence_per_family", {})
    lines.append(f"**Promedio general:** {af.get('average', 0)}")
    lines.append("")
    lines.append("| Familia | Confianza promedio | Miembros |")
    lines.append("|---------|-------------------|----------|")
    per_family = af.get("per_family", {})
    for fname in sorted(per_family):
        fd = per_family[fname]
        lines.append(f"| {fname} | {fd['average_confidence']} | {fd['total_members']} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 10. Cobertura del Gold Standard")
    lines.append("")
    gc = findings.get("gold_coverage", {})
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Códigos en Gold Standard | {gc.get('gold_standard_codes', 0)} |")
    lines.append(f"| Códigos en Knowledge Base | {gc.get('knowledge_base_codes', 0)} |")
    lines.append(f"| Códigos cubiertos | {gc.get('codes_covered', 0)} |")
    lines.append(f"| Cobertura | {gc.get('coverage_pct', 0)}% |")
    lines.append(f"| Registros en Gold Standard | {gc.get('gold_standard_records', 0)} |")
    lines.append("")
    if gc.get("missing_from_knowledge_base"):
        lines.append("**Códigos en Gold Standard pero NO en KB:** " + ", ".join(gc["missing_from_knowledge_base"]))
        lines.append("")
    if gc.get("extra_in_knowledge_base"):
        lines.append("**Códigos en KB pero NO en Gold Standard:** " + ", ".join(gc["extra_in_knowledge_base"]))
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Resumen de problemas")
    lines.append("")
    lines.append("| Categoría | Total |")
    lines.append("|-----------|-------|")
    lines.append(f"| Códigos duplicados | {findings.get('duplicate_codes', {}).get('total', 0)} |")
    lines.append(f"| Variantes repetidas | {findings.get('repeated_variants', {}).get('total', 0)} |")
    lines.append(f"| Variantes cross-code | {findings.get('cross_code_variants', {}).get('total_conflictive', 0)} |")
    lines.append(f"| Códigos baja evidencia | {findings.get('low_evidence_codes', {}).get('total', 0)} |")
    lines.append(f"| Familias incompletas | {findings.get('incomplete_families', {}).get('total', 0)} |")
    lines.append(f"| Inconsistencias jerarquía | {findings.get('hierarchy_inconsistencies', {}).get('total', 0)} |")
    lines.append(f"| Variantes similares cross-code | {findings.get('similar_variants_diff_codes', {}).get('total', 0)} |")
    lines.append("")
    lines.append(f"*Auditoría generada por knowledge_base/audit.py*")

    text = "\n".join(lines)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    logger.info("Reporte de auditoría: %s", path)
    return text


def generate_quality_metrics(findings: dict[str, Any] | None = None, output_path: str | Path = "knowledge_base/quality_metrics.json") -> dict[str, Any]:
    if findings is None:
        findings = audit_knowledge_base()
    metrics = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "source": str(KB_PATH),
        "summary": {
            "total_codes": findings.get("total_codes", 0),
            "total_variants": findings.get("total_variants", 0),
            "total_families": findings.get("total_families", 0),
            "conflictive_variants": findings.get("conflictive_variants", 0),
            "low_evidence_codes": findings.get("low_evidence_count", 0),
            "codes_recommended_for_review": findings.get("codes_recommended_for_review", []),
        },
        "duplicate_codes": findings.get("duplicate_codes", {}),
        "repeated_variants": findings.get("repeated_variants", {}),
        "cross_code_variants": findings.get("cross_code_variants", {}),
        "low_evidence_codes": findings.get("low_evidence_codes", {}),
        "incomplete_families": findings.get("incomplete_families", {}),
        "hierarchy_inconsistencies": findings.get("hierarchy_inconsistencies", {}),
        "similar_variants_diff_codes": findings.get("similar_variants_diff_codes", {}),
        "avg_confidence_per_code": findings.get("avg_confidence_per_code", {}),
        "avg_confidence_per_family": findings.get("avg_confidence_per_family", {}),
        "gold_coverage": findings.get("gold_coverage", {}),
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    logger.info("Quality metrics: %s", path)
    return metrics
