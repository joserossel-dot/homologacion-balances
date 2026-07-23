#!/usr/bin/env python3
"""
Two-pass semantic clustering of UNKNOWN family names into accounting concepts.
Standalone analysis — does NOT modify pipeline code.
"""

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reports.analyze_unknown_pareto import normalizar
# imported for API availability even if not directly used in clustering logic
from reports.analyze_unknown_pareto import extract_core_words as _pec, match_legacy_regex as _pmr

REPORT_DIR = Path(__file__).parent
INPUT_PATH = REPORT_DIR / "unknown_pareto.json"
OUTPUT_JSON = REPORT_DIR / "semantic_clusters.json"
OUTPUT_MD = REPORT_DIR / "semantic_clusters.md"
OUTPUT_XLSX = REPORT_DIR / "semantic_clusters.xlsx"

# ——— Pass 1: stop words & qualifier words ———
STOP_WORDS = frozenset({
    'de', 'del', 'por', 'para', 'la', 'el', 'los', 'las', 'y', 'e', 'o',
    'a', 'al', 'con', 'en', 'su', 'que', 'lo', 'un', 'una',
})

QUALIFIER_WORDS = frozenset({
    'corrientes', 'no', 'corto', 'largo', 'plazo', 'emitido', 'pagado',
    'suscrito', 'autorizado', 'social', 'emitida', 'pagada', 'suscrita',
    'autorizada', 'general', 'especifico', 'especifica', 'comun',
    'ordinarias', 'ordinario', 'neto', 'neta', 'bruto', 'bruta',
    'varios', 'varias', 'diverse', 'empresarial', 'comerciales',
    'comercial', 'provicional', 'anticipado', 'diferentes',
    'financieros', 'financiero', 'permanente', 'temporales', 'temporal',
})

# ——— Pass 2: synonym map canonical → list of root-word stems ———
SYNONYM_MAP: dict[str, list[str]] = {
    "CAJA": ["caja", "efectivo", "disponible", "arcas"],
    "BANCOS": ["banco", "bancos", "cuenta_corriente", "cta_cte", "cta_corriente"],
    "CLIENTES": ["cliente", "clientes", "deudor", "deudores", "cobrar", "cxc", "cuentas_cobrar"],
    "PROVEEDORES": ["proveedor", "proveedores", "acreedor", "acreedores", "pagar", "cxp", "cuentas_pagar"],
    "CAPITAL": ["capital"],
    "REMUNERACIONES": ["remuneracion", "remuneraciones", "sueldo", "sueldos", "salario", "salarios", "personal",
                       "trabajador", "trabajadores"],
    "HONORARIOS": ["honorario", "honorarios"],
    "IMPUESTOS": ["impuesto", "impuestos", "iva", "tributo", "tributos", "ppm", "fiscal", "provisionales"],
    "MUEBLES": ["mueble", "muebles", "util", "utiles", "equipo", "equipos", "mobiliario", "enseres"],
    "DEPRECIACION": ["depreciacion", "depreciac", "amortizacion", "amortizac", "deterioro", "dep", "amort",
                     "depreciaciones", "amortizaciones"],
    "INVENTARIOS": ["inventario", "inventarios", "existencia", "existencias", "mercaderia", "mercaderias", "stock",
                    "materia", "insumo", "insumos", "suministro", "suministros"],
    "GASTOS": ["gasto", "gastos"],
    "INGRESOS": ["ingreso", "ingresos", "venta", "ventas", "facturacion", "factura", "giro", "facturado"],
    "COSTOS": ["costo", "costos", "costo_venta", "explotacion", "costo_explotacion", "costo_produccion"],
    "PROPIEDAD": ["propiedad", "inmueble", "edificio", "edificios", "terreno", "terrenos", "planta", "construccion",
                  "inmob", "predio", "galpon", "bodega"],
    "VEHICULOS": ["vehiculo", "vehiculos", "automotora", "auto", "automovil", "camion", "camioneta"],
    "MAQUINARIA": ["maquinaria", "maquinarias", "maquina", "maquinas"],
    "INVERSIONES": ["inversion", "inversiones", "fondo", "fondos", "accion", "acciones", "participacion",
                    "participaciones", "bonos", "mutuo", "pacto"],
    "PRESTAMOS": ["prestamo", "prestamos", "credito", "creditos"],
    "CORRECCION_MONETARIA": ["correccion", "reajuste"],
    "FLETES": ["flete", "fletes", "transporte", "envio"],
    "RESERVAS": ["reserva", "reservas", "prima", "revalorizacion", "revalorizaciones"],
    "DIVIDENDOS": ["dividendo", "dividendos", "retiro", "retiros"],
    "SEGUROS": ["seguro", "seguros", "cobertura"],
    "ARRENDAMIENTO": ["arrendamiento", "arriendo", "leasing", "renting", "arriendos"],
    "DOCUMENTOS": ["documento", "documentos", "letra", "letras", "pagare", "pagares"],
    "PATENTES": ["patente", "patentes", "permiso", "permisos", "circulacion"],
    "GASTOS_VIAJE": ["viaje", "viajes", "representacion", "viatico", "viaticos"],
    "GASTOS_MANTENCION": ["mantencion", "reparacion", "reparaciones", "mantenimiento"],
    "PROVISIONES": ["provision", "provisiones"],
    "DIFERIDOS": ["diferido", "diferidos", "anticipado", "anticipados"],
    "ACUMULADO": ["acumulado", "acumulada"],
    "RESULTADO": ["resultado", "resultante"],
    "MARGEN": ["margen"],
    "INTERESES": ["interes", "intereses", "comision", "comisiones"],
    "GASTOS_ADMIN": ["administracion", "administrativo", "administrativos", "gestion"],
    "GASTOS_VENTA": ["comercial", "mercadeo", "distribucion", "marketing", "publicidad", "propaganda"],
    "GASTOS_FINANCIEROS": ["financiero"],
    "UTILIDAD": ["utilidad", "ganancia", "excedente"],
    "PERDIDA": ["perdida", "perdidas", "deficit"],
    "PATRIMONIO": ["patrimonio", "patrimonial"],
    "ACTIVOS": ["activo", "activos"],
    "PASIVOS": ["pasivo", "pasivos"],
    "OBLIGACIONES": ["obligacion", "obligaciones"],
    "ANTICIPO": ["anticipo", "anticipos", "adelanto", "adelantos"],
    "INTANGIBLE": ["intangible", "goodwill", "marca", "marcas", "licencia", "licencias", "software", "plusvalia"],
    "MATERIALES": ["material", "materiales"],
    "SERVICIO": ["servicio", "servicios"],
    "RELACIONADAS": ["relacionada", "vinculada", "partes_relacionadas", "entidad_relacionada", "vinculadas",
                     "relacionadas"],
    "HERRAMIENTAS": ["herramienta", "herramientas"],
    "CENTRALIZACION": ["centralizacion"],
    "CONSTRUCCION": ["construccion", "obras", "obra"],
    "CERTIFICACION": ["certificacion", "certificaciones"],
    "CONTRIBUCION": ["contribucion", "contribuciones"],
    "APORTE": ["aporte", "aportes"],
    "DESCUENTO": ["descuento", "descuentos"],
    "PRODUCTOS": ["producto", "productos"],
    "CUENTA_CONTABLE": ["cuenta_contable", "codigo_cuenta"],
    "SOCIEDADES": ["sociedad", "sociedades", "filial", "filiales", "coligada", "coligadas"],
    "AGENCIA": ["agencia", "sucursal"],
    "ACCIONISTAS": ["accionista", "accionistas"],
    "RETENCION": ["retencion", "retenciones"],
    "CREDITO_FISCAL": ["credito_fiscal", "credito_iva"],
    "MONEDA_EXTRANJERA": ["extranjera", "dolares", "euro", "moneda_extranjera"],
    "ELECTRICIDAD": ["electricidad", "electrico", "luz", "energia"],
    "COMUNICACIONES": ["comunicacion", "comunicaciones", "telefono", "telefonica", "internet", "celular"],
    "AGUA": ["agua", "alcantarillado"],
    "SERVICIO_SEGURIDAD": ["seguridad", "vigilancia", "guardia"],
    "MOVILIZACION": ["movilizacion", "movilizaciones"],
    "EBITDA": ["ebitda"],
    "PAPEL": ["papel", "bolsas", "plastico", "plasticos", "embalaje"],
    "INSTALACIONES": ["instalacion", "instalaciones"],
    "ASESORIAS": ["asesoria", "asesorias", "consultoria", "consultorias"],
    "SUSCRIPCION": ["suscripcion", "suscripciones"],
    "CAPACITACION": ["capacitacion", "capacitaciones"],
    "ARRENDAMIENTO_INMUEBLE": ["arrendamiento_inmueble", "arriendo_inmueble"],
    "PATENTE_MUNICIPAL": ["patente_municipal"],
    "CONTABILIDAD": ["contabilidad", "contable", "auditoria"],
    "NOTARIAL": ["notarial", "notaria", "notario"],
    "LEGALES": ["legal", "legales", "abogado", "abogados"],
    "GASTOS_BANCARIOS": ["gastos_bancarios", "comision_bancaria", "comisiones_bancarias"],
    "DIVERSOS": ["diversos", "varios_menores"],
}

# Build reverse map: stem → canonical (first match wins for ties)
SYNONYM_LOOKUP: dict[str, str] = {}
for canonical, stems in SYNONYM_MAP.items():
    for stem in stems:
        if stem not in SYNONYM_LOOKUP:
            SYNONYM_LOOKUP[stem] = canonical


def stem_match(word: str, stem: str) -> bool:
    """Check if word and stem share a common prefix (root-level matching)."""
    min_len = min(len(word), len(stem))
    if min_len < 3:
        return word == stem
    return word[:min_len] == stem[:min_len]


def extract_root_words(name: str) -> list[str]:
    """Pass 1: extract root concept word(s) from a family name."""
    norm = normalizar(name)
    tokens = [w for w in norm.split()
              if w not in STOP_WORDS
              and not re.match(r'^[\d.,]+$', w)
              and len(w) > 2]
    # remove qualifier words; if everything would be removed, keep original tokens
    filtered = [w for w in tokens if w not in QUALIFIER_WORDS]
    return filtered if filtered else tokens


def find_concept(root_words: list[str]) -> str | None:
    """Pass 2: find the best canonical concept for a list of root words.

    Uses voting (each root word votes for matching canonicals) with tiebreakers:
    more votes > longer matching stem > alphabetical.
    """
    votes: dict[str, int] = Counter()
    max_stem_len: dict[str, int] = defaultdict(int)
    for word in root_words:
        for stem, canonical in SYNONYM_LOOKUP.items():
            if stem_match(word, stem):
                votes[canonical] += 1
                max_stem_len[canonical] = max(max_stem_len[canonical], len(stem))
    if not votes:
        return None
    return max(votes, key=lambda c: (votes[c], max_stem_len[c], c))


def classify_family(family: dict) -> str | None:
    """Classify a single family into a canonical concept. Returns None if no match."""
    name = family.get("family_name", "")
    if not name:
        return None
    roots = extract_root_words(name)
    if not roots:
        return None
    return find_concept(roots)


def assign_difficulty(concept_families: list[dict], total_count: int, family_count: int) -> str:
    """Assign difficulty BAJA/MEDIA/ALTA per the spec rules."""
    all_have_codes = all(
        f.get("expected_code") and f["expected_code"] not in ("POR_DEFINIR", "", "N/A")
        for f in concept_families
    )
    codes = {
        f["expected_code"] for f in concept_families
        if f.get("expected_code") and f["expected_code"] not in ("POR_DEFINIR", "", "N/A")
    }
    single_code = len(codes) == 1
    large_concept = total_count > 10

    if all_have_codes and single_code and large_concept:
        return "BAJA"

    mostly_no_code = sum(
        1 for f in concept_families
        if f.get("expected_code") in ("POR_DEFINIR", "", None, "N/A")
    ) >= len(concept_families) / 2

    if family_count < 5 or mostly_no_code:
        return "ALTA"

    return "MEDIA"


def assign_difficulty_to_concept(concept: dict, families_by_name: dict[str, dict]) -> str:
    """Resolve difficulty for a concept using its constituent families."""
    family_names = concept["families"]
    concept_families = [families_by_name.get(n) for n in family_names if n in families_by_name]
    if not concept_families:
        return "ALTA"
    return assign_difficulty(concept_families, concept["total_count"], concept["family_count"])


def analyze():
    with open(INPUT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    families: list[dict] = data["pareto"]
    meta = data["metadata"]
    total_families = meta["total_families"]
    total_accounts = sum(f["count"] for f in families)

    # Build name lookup for difficulty assignment
    families_by_name: dict[str, dict] = {f["family_name"]: f for f in families}

    # ——— Step 1: Direct semantic classification ———
    concept_groups: dict[str, dict] = {}
    concept_to_expected_codes: dict[str, set[str]] = defaultdict(set)
    unclassified: list[dict] = []

    for fam in families:
        concept = classify_family(fam)
        if concept:
            if concept not in concept_groups:
                concept_groups[concept] = {
                    "concept_name": concept,
                    "total_count": 0,
                    "family_count": 0,
                    "families": [],
                    "expected_codes": set(),
                }
            group = concept_groups[concept]
            group["total_count"] += fam["count"]
            group["family_count"] += 1
            group["families"].append(fam["family_name"])
            ec = fam.get("expected_code", "")
            if ec and ec not in ("POR_DEFINIR", "", "N/A"):
                group["expected_codes"].add(ec)
                concept_to_expected_codes[concept].add(ec)
        else:
            unclassified.append(fam)

    # ——— Step 2: Expected-code fallback ———
    code_to_concept: dict[str, str] = {}
    for concept, group in concept_groups.items():
        for code in group["expected_codes"]:
            code_to_concept[code] = concept

    still_unclassified: list[dict] = []
    for fam in unclassified:
        ec = fam.get("expected_code", "")
        if ec and ec not in ("POR_DEFINIR", "", "N/A") and ec in code_to_concept:
            concept = code_to_concept[ec]
            group = concept_groups[concept]
            group["total_count"] += fam["count"]
            group["family_count"] += 1
            group["families"].append(fam["family_name"])
            group["expected_codes"].add(ec)
        else:
            still_unclassified.append(fam)
    unclassified = still_unclassified

    # ——— Step 3: Fuzzy fallback for top 500 unclassified ———
    fuzzy_candidates = sorted(unclassified, key=lambda x: -x["count"])[:500]

    # Build classified family root strings for fuzzy comparison
    classified_roots: list[tuple[str, str]] = []
    for fam in families:
        concept = classify_family(fam)
        if concept:
            roots = " ".join(extract_root_words(fam["family_name"]))
            classified_roots.append((roots, concept))
    # also include expected-code fallback families
    for fam in families:
        ec = fam.get("expected_code", "")
        if ec and ec not in ("POR_DEFINIR", "", "N/A") and ec in code_to_concept:
            concept = code_to_concept[ec]
            roots = " ".join(extract_root_words(fam["family_name"]))
            classified_roots.append((roots, concept))

    fuzzy_assigned_ids = set()
    for fam in fuzzy_candidates:
        fam_roots = " ".join(extract_root_words(fam["family_name"]))
        if not fam_roots:
            continue
        best_score = 0
        best_concept = None
        for cr, cc in classified_roots:
            if not cr:
                continue
            score = fuzz.token_sort_ratio(fam_roots, cr)
            if score > best_score:
                best_score = score
                best_concept = cc
        if best_score >= 80 and best_concept:
            group = concept_groups[best_concept]
            group["total_count"] += fam["count"]
            group["family_count"] += 1
            group["families"].append(fam["family_name"])
            fuzzy_assigned_ids.add(id(fam))

    final_unclassified = [f for f in unclassified if id(f) not in fuzzy_assigned_ids]

    # ——— Build sorted concept list ———
    sorted_concepts = sorted(concept_groups.values(), key=lambda x: -x["total_count"])
    cumulative = 0.0
    concept_rows: list[dict[str, Any]] = []
    for concept in sorted_concepts:
        pct = round(concept["total_count"] / total_accounts * 100, 2)
        cumulative += pct
        expected_codes = sorted(concept["expected_codes"]) if concept["expected_codes"] else []
        difficulty = assign_difficulty_to_concept(concept, families_by_name)
        concept_rows.append({
            "concept_name": concept["concept_name"],
            "total_count": concept["total_count"],
            "family_count": concept["family_count"],
            "families": sorted(concept["families"]),
            "expected_codes": expected_codes,
            "pct": pct,
            "cumulative_pct": round(cumulative, 2),
            "difficulty": difficulty,
        })

    unclassified_output = sorted(
        [{"family_name": f["family_name"], "count": f["count"]} for f in final_unclassified],
        key=lambda x: -x["count"],
    )

    # ——— Metadata ———
    concepts_10plus = sum(1 for c in concept_rows if c["total_count"] >= 10)
    concepts_5plus = sum(1 for c in concept_rows if c["total_count"] >= 5)
    running = 0.0
    rules_for_80 = 0
    for c in concept_rows:
        running += c["pct"]
        rules_for_80 += 1
        if running >= 80:
            break
    top10_pct = sum(c["pct"] for c in concept_rows[:10])
    top50_pct = sum(c["pct"] for c in concept_rows[:50])
    top100_pct = sum(c["pct"] for c in concept_rows[:100])

    output_metadata = {
        "total_families": total_families,
        "total_concepts": len(concept_rows),
        "total_accounts": total_accounts,
        "concepts_with_10plus": concepts_10plus,
        "concepts_with_5plus": concepts_5plus,
        "coverage_top_10": round(top10_pct, 2),
        "coverage_top_50": round(top50_pct, 2),
        "coverage_top_100": round(top100_pct, 2),
        "rules_for_80_pct": rules_for_80,
        "unclassified_families": len(unclassified_output),
    }

    output = {
        "metadata": output_metadata,
        "concepts": concept_rows,
        "unclassified": unclassified_output,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  -> {OUTPUT_JSON}")

    _guardar_md(output, concept_rows, unclassified_output, output_metadata)
    _guardar_xlsx(output, concept_rows, unclassified_output, output_metadata)

    print(
        f"Total families: {total_families} | Concepts: {len(concept_rows)} | "
        f">=10 concepts: {concepts_10plus} | Unclassified: {len(unclassified_output)}"
    )
    print(f"Coverage: Top 10 = {top10_pct}%, Top 50 = {top50_pct}%, Rules for 80% = {rules_for_80}")


def _guardar_md(output: dict, concept_rows: list[dict], unclassified_output: list[dict],
                 output_metadata: dict):
    lines = [
        "# Análisis de Clusters Semánticos — UNKNOWN",
        "",
        "**Date:** 2026-07-22  ",
        f"**Contexto:** {output_metadata['total_families']} familias UNKNOWN agrupadas en "
        f"{output_metadata['total_concepts']} conceptos contables semánticos.",
        "",
        "---",
        "## Resumen",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Total familias | {output_metadata['total_families']} |",
        f"| Total cuentas UNKNOWN | {output_metadata['total_accounts']} |",
        f"| Conceptos detectados | {output_metadata['total_concepts']} |",
        f"| Conceptos con ≥10 cuentas | {output_metadata['concepts_with_10plus']} |",
        f"| Conceptos con ≥5 cuentas | {output_metadata['concepts_with_5plus']} |",
        f"| Cobertura Top 10 | {output_metadata['coverage_top_10']}% |",
        f"| Cobertura Top 50 | {output_metadata['coverage_top_50']}% |",
        f"| Cobertura Top 100 | {output_metadata['coverage_top_100']}% |",
        f"| Reglas para cubrir 80% del gap | {output_metadata['rules_for_80_pct']} |",
        f"| Familias no clasificadas | {output_metadata['unclassified_families']} |",
        "",
        "## Ranking de Conceptos (Top 50)",
        "",
        "| Rank | Concepto | Total | Familias | % Gap | % Acum | Códigos | Dificultad |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(concept_rows[:50], 1):
        codes = ", ".join(c["expected_codes"]) if c["expected_codes"] else "—"
        lines.append(
            f"| {i} | {c['concept_name']} | {c['total_count']} | {c['family_count']} | "
            f"{c['pct']}% | {c['cumulative_pct']}% | {codes} | {c['difficulty']} |"
        )

    lines += [
        "",
        "## Análisis de Cobertura",
        "",
        f"- {output_metadata['coverage_top_10']}% del gap cubierto por los primeros 10 conceptos",
        f"- {output_metadata['coverage_top_50']}% del gap cubierto por los primeros 50 conceptos",
        f"- {output_metadata['coverage_top_100']}% del gap cubierto por los primeros 100 conceptos",
        f"- Se requieren {output_metadata['rules_for_80_pct']} conceptos (reglas semánticas) "
        f"para cubrir el 80% del gap",
        f"- {output_metadata['unclassified_families']} familias "
        f"({round(output_metadata['unclassified_families'] / output_metadata['total_families'] * 100, 1)}%) "
        f"quedan sin clasificar",
        "",
        "## Top 10 Recomendados para Próximo Sprint",
        "",
        "| # | Concepto | Total | Familias | % Gap | Dificultad | Códigos |",
        "|---|---|---|---|---|---|---|",
    ]
    scored = []
    for c in concept_rows[:30]:
        mult = {"BAJA": 2.5, "MEDIA": 1.0, "ALTA": 0.3}.get(c["difficulty"], 1.0)
        score = c["total_count"] * mult
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    for i, (_, c) in enumerate(scored[:10], 1):
        codes = ", ".join(c["expected_codes"]) if c["expected_codes"] else "—"
        lines.append(
            f"| {i} | {c['concept_name']} | {c['total_count']} | {c['family_count']} | "
            f"{c['pct']}% | {c['difficulty']} | {codes} |"
        )

    lines += [
        "",
        "---",
        "*Generated by analyze_semantic_clusters.py*",
    ]
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  -> {OUTPUT_MD}")


def _guardar_xlsx(output: dict, concept_rows: list[dict], unclassified_output: list[dict],
                   output_metadata: dict):
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        pd.DataFrame([
            {"Metrica": "Total familias", "Valor": output_metadata["total_families"]},
            {"Metrica": "Total cuentas UNKNOWN", "Valor": output_metadata["total_accounts"]},
            {"Metrica": "Total conceptos", "Valor": output_metadata["total_concepts"]},
            {"Metrica": "Conceptos >=10 cuentas", "Valor": output_metadata["concepts_with_10plus"]},
            {"Metrica": "Conceptos >=5 cuentas", "Valor": output_metadata["concepts_with_5plus"]},
            {"Metrica": "Cobertura Top 10", "Valor": f"{output_metadata['coverage_top_10']}%"},
            {"Metrica": "Cobertura Top 50", "Valor": f"{output_metadata['coverage_top_50']}%"},
            {"Metrica": "Cobertura Top 100", "Valor": f"{output_metadata['coverage_top_100']}%"},
            {"Metrica": "Reglas para 80% gap", "Valor": output_metadata["rules_for_80_pct"]},
            {"Metrica": "Familias no clasificadas", "Valor": output_metadata["unclassified_families"]},
        ]).to_excel(writer, sheet_name="Resumen", index=False)

        pd.DataFrame([
            {
                "Rank": i + 1,
                "Concepto": c["concept_name"],
                "Total Cuentas": c["total_count"],
                "Familias": c["family_count"],
                "% Gap": c["pct"],
                "% Acum": c["cumulative_pct"],
                "Codigos": ", ".join(c["expected_codes"]) if c["expected_codes"] else "",
                "Dificultad": c["difficulty"],
            }
            for i, c in enumerate(concept_rows)
        ]).to_excel(writer, sheet_name="Conceptos", index=False)

        pd.DataFrame([
            {"Familia": u["family_name"], "Cuentas": u["count"]}
            for u in unclassified_output
        ]).to_excel(writer, sheet_name="No clasificados", index=False)

        detail_rows = []
        for c in concept_rows[:20]:
            for family_name in c["families"]:
                detail_rows.append({
                    "Concepto": c["concept_name"],
                    "Familia": family_name,
                    "Total Concepto": c["total_count"],
                })
        pd.DataFrame(detail_rows).to_excel(writer, sheet_name="Detalle por concepto", index=False)

        scored = []
        for c in concept_rows[:50]:
            mult = {"BAJA": 2.5, "MEDIA": 1.0, "ALTA": 0.3}.get(c["difficulty"], 1.0)
            score = c["total_count"] * mult
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        pd.DataFrame([
            {
                "#": i + 1,
                "Concepto": c["concept_name"],
                "Total": c["total_count"],
                "Familias": c["family_count"],
                "% Gap": c["pct"],
                "Dificultad": c["difficulty"],
                "Codigos": ", ".join(c["expected_codes"]) if c["expected_codes"] else "",
                "Score": round(s, 1),
            }
            for i, (s, c) in enumerate(scored[:10])
        ]).to_excel(writer, sheet_name="Top 10 recomendados", index=False)

    print(f"  -> {OUTPUT_XLSX}")


if __name__ == "__main__":
    analyze()
