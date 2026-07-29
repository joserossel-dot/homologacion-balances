from __future__ import annotations

import csv
import json
import logging
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from review_workspace.similarity import fuzzy_score, normalizar, agrupar_por_normalizacion
from review_workspace.pre_review_cleaner import classify, KEEP
from analysis.unknown_audit import _load_gold_standard, _load_knowledge_base, classify_unknown

logger = logging.getLogger(__name__)

REVIEW_DB = Path("review_workspace/review.db")
PRIORITIZED_CSV = Path("review_workspace/prioritized_review.csv")
REPORT_PATH = Path("reports/review_priority_report.md")


def _load_unknowns_all(db_path: str | Path = REVIEW_DB) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT account_id, empresa, archivo, nombre_original, codigo_original, "
        "monto, confidence, metodo, tipo_columna, nivel_jerarquia, account_type, periodo "
        "FROM unknown_accounts WHERE review_status='pending'"
    ).fetchall()
    conn.close()
    records = [dict(r) for r in rows]
    # Apply PreReview Cleaner filter: only KEEP records enter the backlog
    return [r for r in records if classify(r.get("nombre_original", ""), r.get("nivel_jerarquia", 0)) == KEEP]


def _infer_familia(nombre: str) -> str:
    import unicodedata
    def _no_accents(s: str) -> str:
        nfkd = unicodedata.normalize("NFKD", s)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    raw = _no_accents(nombre.upper().strip())
    if re.search(r"CAJA|BANCO|BCO\b|DISPONIBLE|EFECTIVO|CHEQUE|INVERSIONES\b", raw):
        return "AC"
    if re.search(r"CLIENTE|DEUDOR|DOCUMENTO.*COBRAR|CTA.*COBRAR|CUENTA.*COBRAR|ANTICIPO.*PROV", raw):
        return "AC"
    if re.search(r"INVENTARIO|EXISTENCIA|PRODUCTO|MATERIAL|MERCANCIA", raw):
        return "AC"
    if re.search(r"PROP.PLANTA|PROPIEDAD|INMUEBLE|MAQUINARIA|VEHICULO|MUEBLE|CONSTRUCCION|TERRENO|INSTALACION|DERECHO.*AGUA|EDIFICIO", raw):
        return "ANC"
    if re.search(r"ACTIVO.*INTANGIBLE|PATENTE|MARCA|SOFTWARE|LICENCIA", raw):
        return "ANC"
    if re.search(r"PROVEEDOR|FACTURA.*PAGAR|DOCUMENTO.*PAGAR|CTA.*PAGAR|CUENTA.*PAGAR", raw):
        return "PC"
    if re.search(r"PRESTAMO|OBLIGACION.*BANCARIA|PAGARE|BONO", raw):
        return "PC"
    if re.search(r"IMPUESTO|IVA|PPM|RETENCION", raw):
        return "PC"
    if re.search(r"REMUNERACION|HONORARIO|SUELDO|SALARIO|VACACION|FINIQUITO|PROVISION.*PERS|LEYES.*SOCIAL", raw):
        return "PC"
    if re.search(r"CAPITAL\b|RESERVA|UTILIDAD.*ACUM|RESULTADO.*ACUM|APORTE", raw):
        return "PAT"
    if re.search(r"INGRESO|VENTA|COMISION.*PERCIB|INTERES.*GAN", raw):
        return "ER"
    if re.search(r"GASTO|COSTO|REMUNERACION|SUELDO|HONORARIO|ARRlENDO|SERVICIO.*BASICO|ELECTRICIDAD|AGUA|TELEFONO|SEGURO|PATENTE|PUBLICIDAD|CORREO|IMPUEST.*GAS", raw):
        return "ER"
    return ""


def compute_priorities(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gold = _load_gold_standard()
    kb_data = _load_knowledge_base()
    kb_variants: list[dict[str, Any]] = []
    if kb_data:
        for code, entry in kb_data.get("codes", {}).items():
            for v in entry.get("variantes", []):
                kb_variants.append({"code": code, "name": v["nombre"]})

    # Classify each record
    for rec in records:
        name = rec.get("nombre_original", "")
        audit = classify_unknown(name, gold, kb_variants)
        rec["_motivo"] = audit["motivo"]
        rec["_confianza"] = audit["confianza"]
        rec["_candidato"] = audit["mejor_candidato"]
        rec["_codigo_candidato"] = audit["codigo_candidato"]
        rec["_distancia"] = audit["distancia_fuzzy"]
        rec["_familia"] = _infer_familia(name)
        rec["_normalized"] = normalizar(name)

    # Group equivalent variants
    names_list = [r["nombre_original"] for r in records]
    groups = agrupar_por_normalizacion(names_list, min_score=85)

    group_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for canonical_norm, members in groups.items():
        member_names = set(m[0] for m in members)
        for rec in records:
            if normalizar(rec["nombre_original"]) in [normalizar(m[0]) for m in members]:
                if rec not in group_map[canonical_norm]:
                    group_map[canonical_norm].append(rec)

    # Compute group-level stats
    group_priorities: list[dict[str, Any]] = []
    for canonical_norm, members in group_map.items():
        if not members:
            continue
        nombres_unicos = sorted(set(m["nombre_original"] for m in members))
        empresas = set(m.get("empresa", "") for m in members if m.get("empresa", ""))
        periodos = set(m.get("periodo", "") for m in members if m.get("periodo", ""))
        archivos = set(m.get("archivo", "") for m in members)
        frecuencias = Counter(m["nombre_original"] for m in members)
        confianzas = [m.get("_confianza", 0) for m in members]
        distancias = [m.get("_distancia", 0) for m in members]
        motivos = Counter(m.get("_motivo", "") for m in members)

        best_conf = max(confianzas) if confianzas else 0
        best_dist = max(distancias) if distancias else 0
        candidato = ""
        codigo_candidato = ""
        for m in members:
            if m.get("_distancia", 0) == best_dist and m.get("_candidato"):
                candidato = m["_candidato"]
                codigo_candidato = m["_codigo_candidato"]
                break

        familias = Counter(m.get("_familia", "") for m in members)
        familia_dominante = familias.most_common(1)[0][0] if familias else ""

        total_members = len(members)
        total_empresas = len(empresas)
        total_periodos = len(periodos)
        total_archivos = len(archivos)

        freq_score = min(total_members / max(sum(1 for g in group_map for _ in group_map[g]) / max(len(group_map), 1), 1), 1.0)
        if total_members <= 1:
            freq_score = 0.0
        company_score = min(total_empresas / 10.0, 1.0)
        year_score = min(total_periodos / 6.0, 1.0)
        conf_score = best_conf

        priority = round(
            freq_score * 0.35 + company_score * 0.25 + year_score * 0.15 + conf_score * 0.25,
            4,
        )

        can_name = nombres_unicos[0] if nombres_unicos else ""
        representative = members[0] if members else {}

        group_priorities.append({
            "grupo": canonical_norm,
            "nombre_representativo": can_name,
            "variantes": "; ".join(nombres_unicos),
            "total_occurrences": total_members,
            "distinct_names": len(nombres_unicos),
            "distinct_companies": total_empresas,
            "distinct_years": total_periodos,
            "distinct_files": total_archivos,
            "familia": familia_dominante,
            "candidato_cmcc": candidato,
            "codigo_cmcc": codigo_candidato,
            "confianza_mejor": round(best_conf, 4),
            "distancia_mejor": best_dist,
            "prioridad": priority,
            "reutilizacion_esperada": round(total_members * (1 + 0.2 * total_empresas), 2),
            "motivo_dominante": motivos.most_common(1)[0][0] if motivos else "",
            "archivos": "; ".join(sorted(archivos)[:5]),
            "ejemplo_ids": "; ".join(m["account_id"] for m in members[:3]),
        })

    group_priorities.sort(key=lambda x: -x["prioridad"])
    return group_priorities


def estimate_impact(
    sorted_groups: list[dict[str, Any]], n_reviews: int
) -> dict[str, int]:
    covered_accounts: set[str] = set()
    groups_used = 0
    archivos_cubiertos: set[str] = set()
    total_unknown = sum(g["total_occurrences"] for g in sorted_groups)

    for g in sorted_groups:
        if groups_used >= n_reviews:
            break
        ids = [i.strip() for i in g["ejemplo_ids"].split(";") if i.strip()]
        covered_accounts.update(ids)
        for a in g.get("archivos", "").split("; "):
            if a.strip():
                archivos_cubiertos.add(a.strip())
        groups_used += 1

    return {
        "reviews": n_reviews,
        "groups_covered": groups_used,
        "unique_accounts_covered": len(covered_accounts),
        "archivos_cubiertos": len(archivos_cubiertos),
        "pct_of_unknown": round(len(covered_accounts) / max(total_unknown, 1) * 100, 2),
    }


def run_prioritization() -> dict[str, Any]:
    records = _load_unknowns_all()
    logger.info("Analizando %d registros UNKNOWN...", len(records))
    groups = compute_priorities(records)

    total_unknown = sum(g["total_occurrences"] for g in groups) if groups else 0

    # Estimated impacts
    impact_20 = estimate_impact(groups, 20)
    impact_50 = estimate_impact(groups, 50)
    impact_100 = estimate_impact(groups, 100)
    impact_200 = estimate_impact(groups, 200)

    return {
        "total_records": len(records),
        "total_groups": len(groups),
        "total_unknown": total_unknown,
        "groups": groups,
        "impact_20": impact_20,
        "impact_50": impact_50,
        "impact_100": impact_100,
        "impact_200": impact_200,
    }


def export_prioritized_csv(
    result: dict[str, Any],
    output_path: str | Path = PRIORITIZED_CSV,
) -> int:
    output_path = Path(output_path)
    fieldnames = [
        "prioridad", "nombre_representativo", "variantes", "total_occurrences",
        "distinct_names", "distinct_companies", "distinct_years", "distinct_files",
        "familia", "candidato_cmcc", "codigo_cmcc", "confianza_mejor",
        "distancia_mejor", "reutilizacion_esperada", "motivo_dominante",
        "archivos", "ejemplo_ids",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for g in result["groups"]:
            row = {k: g.get(k, "") for k in fieldnames}
            writer.writerow(row)
    logger.info("CSV priorizado: %s (%d grupos)", output_path, len(result["groups"]))
    return len(result["groups"])


def generate_report(
    result: dict[str, Any] | None = None,
    output_path: str | Path = REPORT_PATH,
) -> str:
    if result is None:
        result = run_prioritization()

    groups = result["groups"]
    top100 = groups[:100]
    top_groups = [g for g in groups if g["distinct_names"] > 1]

    lines: list[str] = []
    lines.append("# Backlog Inteligente de Revisión — Reporte de Prioridades")
    lines.append("")
    lines.append(f"**Generado:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**Fuente:** `{REVIEW_DB}` ({result['total_records']} registros)")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Total registros UNKNOWN | {result['total_records']} |")
    lines.append(f"| Grupos de variantes | {result['total_groups']} |")
    lines.append(f"| Grupos reutilizables (2+ variantes) | {len(top_groups)} |")
    lines.append("")

    lines.append("## Estimación de impacto por revisiones")
    lines.append("")
    lines.append("| Revisiones | Grupos cubiertos | Cuentas únicas | Archivos cubiertos | % UNKNOWN |")
    lines.append("|------------|-----------------|----------------|--------------------|-----------|")
    for impact in [result["impact_20"], result["impact_50"], result["impact_100"], result["impact_200"]]:
        lines.append(
            f"| {impact['reviews']} | {impact['groups_covered']} | "
            f"{impact['unique_accounts_covered']} | {impact['archivos_cubiertos']} | "
            f"{impact['pct_of_unknown']}% |"
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Top 100 cuentas más valiosas")
    lines.append("")
    lines.append("| # | Prioridad | Nombre | Variantes | Frecuencia | Empresas | Años | Familia | Candidato | Confianza |")
    lines.append("|---|-----------|--------|-----------|------------|----------|------|---------|-----------|-----------|")
    for i, g in enumerate(top100, 1):
        lines.append(
            f"| {i} | {g['prioridad']} | {g['nombre_representativo'][:40]} | "
            f"{g['distinct_names']} | {g['total_occurrences']} | {g['distinct_companies']} | "
            f"{g['distinct_years']} | {g['familia'] or '-'} | "
            f"{g['candidato_cmcc'][:30] or '-'} | {g['confianza_mejor']} |"
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Grupos reutilizables (2+ variantes equivalentes)")
    lines.append("")
    if top_groups:
        lines.append("| Grupo | Variantes | Frecuencia total | Empresas |")
        lines.append("|-------|-----------|-----------------|----------|")
        for g in top_groups[:30]:
            lines.append(
                f"| {g['nombre_representativo'][:40]} | {g['variantes'][:60]} | "
                f"{g['total_occurrences']} | {g['distinct_companies']} |"
            )
    else:
        lines.append("_No se encontraron grupos con múltiples variantes._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Distribución por familia probable")
    lines.append("")
    fam_counts: Counter[str] = Counter()
    for g in groups:
        fam_counts[g.get("familia", "") or "SIN_FAMILIA"] += g["total_occurrences"]
    lines.append("| Familia | Ocurrencias |")
    lines.append("|---------|-------------|")
    for fam, cnt in fam_counts.most_common():
        lines.append(f"| {fam if fam != 'SIN_FAMILIA' else 'Sin clasificar'} | {cnt} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Reporte generado por analysis/review_priority.py*")

    text = "\n".join(lines)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    logger.info("Reporte de prioridades: %s", path)
    return text


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run_prioritization()
    export_prioritized_csv(result)
    generate_report(result)
    print(f"Total records: {result['total_records']}")
    print(f"Total groups: {result['total_groups']}")
    print(f"Impact 20 reviews: {result['impact_20']['unique_accounts_covered']} accounts")
    print(f"Impact 50 reviews: {result['impact_50']['unique_accounts_covered']} accounts")
    print(f"Impact 100 reviews: {result['impact_100']['unique_accounts_covered']} accounts")
    print(f"Impact 200 reviews: {result['impact_200']['unique_accounts_covered']} accounts")
