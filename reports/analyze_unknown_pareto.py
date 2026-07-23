"""
Análisis Pareto de cuentas UNKNOWN después de Sprint 28.5A.

NO modifica código del pipeline. NO agrega regex.
"""

import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser_universal import ParserPDF
from pipeline.homologation_pipeline import HomologationPipeline
from pipeline.features import CMCCFeatureFlags
from app_validacion import REGLAS_COMPILADAS
from rapidfuzz import fuzz

REPORT_DIR = Path(__file__).parent
OUTPUT_JSON = REPORT_DIR / "unknown_pareto.json"
OUTPUT_MD = REPORT_DIR / "unknown_pareto.md"
OUTPUT_XLSX = REPORT_DIR / "unknown_pareto.xlsx"
ALL_ACCOUNTS_PATH = REPORT_DIR / "unknown_all_accounts.json"

STOP_WORDS = frozenset({
    'total', 'subtotal', 'neto', 's', 'o', 'de', 'la', 'el',
    'del', 'los', 'las', 'un', 'una', 'y', 'e', 'a', 'por',
    'al', 'con', 'en', 'para', 'su', 'que', 'lo',
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    'enero', 'febrero', 'mar', 'abr', 'may', 'jun', 'jul', 'ago',
    'sep', 'oct', 'nov', 'dic', 'mes', 'ano', 'anio', 'ano',
    '2010', '2011', '2012', '2013', '2014', '2015', '2016', '2017',
    '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026',
    'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x',
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
})


def recolectar_pdfs() -> list[Path]:
    raiz = next((p for p in [Path("datasets"), Path(".")] if p.exists()), Path("."))
    pdfs = []
    for grupo in ["HOLDOUT", "edge_cases", "validacion"]:
        carpeta = raiz / grupo
        if carpeta.exists():
            for f in sorted(carpeta.glob("*.pdf")):
                pdfs.append(f)
    return pdfs


def normalizar(nombre: str) -> str:
    nombre = nombre.lower().strip()
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = nombre.encode("ascii", "ignore").decode("ascii")
    nombre = re.sub(r"[^\w\s]", " ", nombre)
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre.strip()


def extract_core_words(name: str) -> list[str]:
    norm = normalizar(name)
    return [w for w in norm.split()
            if w not in STOP_WORDS
            and not re.match(r'^[\d.,]+$', w)
            and len(w) > 2]


def cluster_families(accounts: list[dict], threshold: int = 85) -> list[dict]:
    """Clustering de cuentas UNKNOWN por similitud de nombre.

    Estrategia:
    1. Agrupar por nombre exacto
    2. Fusionar grupos con token_sort_ratio >= threshold
    3. Nombre de familia = nombre más corto con mayor frecuencia
    """
    name_groups = defaultdict(list)
    for a in accounts:
        norm = normalizar(a["account_name"])
        name_groups[norm].append(a)

    unique_norms = list(name_groups.keys())
    clusters = []
    assigned = set()

    for i, norm in enumerate(unique_norms):
        if norm in assigned:
            continue
        cluster_norms = [norm]
        assigned.add(norm)
        for j in range(i + 1, len(unique_norms)):
            if unique_norms[j] in assigned:
                continue
            score = fuzz.token_sort_ratio(norm, unique_norms[j])
            if score >= threshold:
                cluster_norms.append(unique_norms[j])
                assigned.add(unique_norms[j])

        family_members = []
        for cn in cluster_norms:
            family_members.extend(name_groups[cn])

        family_name = derive_family_name(family_members, cluster_norms)
        clusters.append({"family_name": family_name, "members": family_members})

    name_to_family = {}
    for cluster in clusters:
        for m in cluster["members"]:
            key = normalizar(m["account_name"])
            name_to_family[key] = cluster["family_name"]

    family_accounts = defaultdict(list)
    for a in accounts:
        key = normalizar(a["account_name"])
        fname = name_to_family.get(key, "OTROS")
        family_accounts[fname].append(a)

    result = []
    for fname, members in family_accounts.items():
        account_names = list({m["account_name"] for m in members})
        tipos = list({m["tipo"] for m in members})
        codes = list({m["account_code"] for m in members if m["account_code"]})
        nombres_ejemplo = sorted(account_names)[:5]
        result.append({
            "family_name": fname,
            "count": len(members),
            "account_names": account_names,
            "nombres_ejemplo": nombres_ejemplo,
            "tipos": tipos,
            "codigos_ejemplo": codes[:5],
        })

    result.sort(key=lambda x: -x["count"])
    return result


def derive_family_name(members: list[dict], cluster_norms: list[str]) -> str:
    """Deriva nombre de familia: el nombre más corto y frecuente del cluster."""
    name_counter = Counter()
    for m in members:
        name_counter[normalizar(m["account_name"])] += 1

    # Preferir el nombre normalizado más corto entre los más frecuentes
    top_names = [n for n, c in name_counter.most_common()]

    for n in top_names:
        core = extract_core_words(n)
        if len(core) >= 2:
            return " ".join(core).upper()[:60]

    if top_names:
        core = extract_core_words(top_names[0])
        if core:
            return " ".join(core).upper()[:60]
        return top_names[0].upper()[:60]

    return "SIN_NOMBRE"


def match_legacy_regex(account_name: str) -> list[str]:
    """Verifica si el nombre coincide con algún patrón REGLAS_COMPILADAS."""
    norm = normalizar(account_name)
    matches = []
    for pat, cod, conf in REGLAS_COMPILADAS:
        if pat.search(norm):
            matches.append(cod)
    return matches


def estimate_difficulty(family: dict, matched_patterns: list[tuple[str, float]]) -> str:
    if matched_patterns:
        max_conf = max(conf for _, conf in matched_patterns)
        if max_conf >= 0.90:
            return "BAJA"
        return "MEDIA"
    tipos = set(family["tipos"])
    if len({t for t in tipos if t != "DESCONOCIDO"}) > 2:
        return "ALTA"
    if family["count"] > 100:
        return "ALTA"
    name = family["family_name"].lower()
    if any(kw in name for kw in ["otro", "varios", "diversos", "provision", "ajuste"]):
        return "ALTA"
    return "MEDIA"


NOISE_PATTERNS = [
    re.compile(r"^n\s+[a-z]{2,}", re.IGNORECASE),
    re.compile(r"^[:\$;%\-#@]\s?", re.IGNORECASE),
    re.compile(r"^(n/a|na|n\s*\/\s*a)\s*$", re.IGNORECASE),
    re.compile(r"^\d+\s*$"),
    re.compile(r"^(al?\s+\d+\s+de\s+)", re.IGNORECASE),
    re.compile(r"^(de\s+la\s+)?(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)", re.IGNORECASE),
    re.compile(r"^\d+\s+(de\s+)?(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)", re.IGNORECASE),
    re.compile(r"^(a|para|por|en|con|entre|sin|tras|durante|mediante)\s", re.IGNORECASE),
    re.compile(r"^(acumulado|saldo)\s+(al|a\s+la|del)", re.IGNORECASE),
    re.compile(r"^(desde|hasta|periodo|comprendido)", re.IGNORECASE),
    re.compile(r"^(nota|anexo|adjunto|ver)", re.IGNORECASE),
    re.compile(r"^(moneda|peso|d[oó]lar|euro|uf|utm)", re.IGNORECASE),
    re.compile(r"(p[aá]gina|pag\s)", re.IGNORECASE),
    re.compile(r"^\s*n[°º]?\s*\d", re.IGNORECASE),
    re.compile(r"^(box|bodega|oficina|local|ubicaci[oó]n)", re.IGNORECASE),
    re.compile(r"folio", re.IGNORECASE),
    re.compile(r"^(continuaci[oó]n|viene|siguiente)", re.IGNORECASE),
]


def is_account_name(name: str) -> bool:
    """Filtra nombres que no son cuentas contables (fechas, headers, OCR noise)."""
    norm = normalizar(name)
    if not norm or len(norm) < 3:
        return False
    core = extract_core_words(name)
    if not core:
        return False
    if len(core) == 1 and len(core[0]) <= 2:
        return False
    for pat in NOISE_PATTERNS:
        if pat.search(norm):
            return False
    return True


def extract_all_accounts(pdfs: list[Path]) -> list[dict]:
    """Procesa todos los PDFs y extrae todas las cuentas con su clasificación."""
    if ALL_ACCOUNTS_PATH.exists():
        print(f"Cargando cuentas desde {ALL_ACCOUNTS_PATH}...")
        with open(ALL_ACCOUNTS_PATH) as f:
            return json.load(f)

    print(f"Procesando {len(pdfs)} PDFs para extraer cuentas...")
    pipeline = HomologationPipeline(
        features=CMCCFeatureFlags(
            ENABLE_REGEX_FALLBACK=True,
            ENABLE_ACCOUNT_TYPE_FILTER=True,
        ),
    )

    all_accounts = []
    t_start = time.perf_counter()

    for i, pdf in enumerate(pdfs, 1):
        t_doc = time.perf_counter()
        try:
            result = pipeline.process(pdf)
        except Exception as e:
            print(f"  [{i}/{len(pdfs)}] ERROR: {pdf.name} — {e}")
            continue

        classified = result.get("classified", [])
        for c in classified:
            all_accounts.append({
                "account_name": c["account_name"],
                "account_code": c.get("account_code", ""),
                "standard_code": c.get("standard_code"),
                "method": c.get("method", ""),
                "source_file": c.get("source_file", pdf.name),
            })

        elapsed = time.perf_counter() - t_doc
        unknowns = sum(1 for c in classified if c.get("standard_code") is None)
        print(f"  [{i}/{len(pdfs)}] {pdf.name}: {len(classified)} cuentas, {unknowns} UNKNOWN ({elapsed:.1f}s)")

        if i % 20 == 0:
            with open(ALL_ACCOUNTS_PATH, "w") as f:
                json.dump(all_accounts, f, indent=1, ensure_ascii=False)
            print(f"  -> Checkpoint ({len(all_accounts)} cuentas)")

    with open(ALL_ACCOUNTS_PATH, "w") as f:
        json.dump(all_accounts, f, indent=1, ensure_ascii=False)

    total_time = time.perf_counter() - t_start
    print(f"Extracción: {len(all_accounts)} cuentas en {total_time:.0f}s ({total_time/60:.1f} min)")
    return all_accounts


def infer_tipo_from_name(name: str) -> str:
    """Infere tipo contable desde el nombre de cuenta usando raíces."""
    norm = normalizar(name)
    palabras = norm.split()

    activo_roots = {"caj", "banc", "efectiv", "client", "deudor", "inventari",
                    "existenci", "mercaderi", "propied", "planta", "maquinari",
                    "vehicul", "terren", "muebl", "activ", "inversion",
                    "depreciaci", "amortizaci", "intangible", "credito",
                    "document", "cobrar", "inmuebl", "edifici"}

    pasivo_roots = {"proveedor", "acreedor", "obligacion", "prestam", "pasiv",
                    "debito", "impuest", "renta", "remuneraci", "sueld",
                    "honorari", "vacaci", "gratificaci", "leas", "factor",
                    "hipotecari", "mutu"}

    patrimonio_roots = {"capital", "aport", "reserv", "prima", "emisi",
                        "utilidad", "resultad", "acumulad", "patrimoni",
                        "retenid", "accion", "social", "revalorizaci"}

    perdida_roots = {"gast", "cost", "vent", "ingres", "perdid", "utilidad",
                     "resultad", "ejercici", "period", "depreciaci", "amortizaci",
                     "interes", "comision", "administraci", "gener",
                     "comercial", "explotaci", "producci", "financier",
                     "impuest", "renta", "categoria", "margen", "viaje",
                     "representaci", "flet"}

    def match_any(word, roots):
        return any(word.startswith(r) or r.startswith(word) for r in roots)

    scores = {}
    for tipo, roots in [("ACTIVO", activo_roots), ("PASIVO", pasivo_roots),
                        ("PATRIMONIO", patrimonio_roots), ("PERDIDA", perdida_roots)]:
        scores[tipo] = sum(1 for w in palabras if match_any(w, roots))

    # Si se menciona ejercicio/periodo + utilidad/resultado → PERDIDA
    has_ejercicio = any(match_any(w, {"ejercici", "period"}) for w in palabras)
    has_utilidad = any(match_any(w, {"utilidad", "resultad"}) for w in palabras)
    if has_ejercicio and has_utilidad:
        return "PERDIDA"

    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    if scores[best] == 1:
        return best

    return "DESCONOCIDO"


def enrich_with_tipo(all_accounts: list[dict]) -> list[dict]:
    """Enriquece cada cuenta con el tipo inferido."""
    from parsers.account_type_resolver import AccountTypeResolver
    resolver = AccountTypeResolver()
    for a in all_accounts:
        tipo_result = resolver.resolve(
            origen_columna=None,
            codigo=a.get("account_code", ""),
        )
        inferred = tipo_result.account_type.value
        if inferred == "DESCONOCIDO":
            inferred = infer_tipo_from_name(a["account_name"])
        a["tipo"] = inferred
    return all_accounts


def guess_expected_code(family: dict, matched_patterns: list[tuple[str, float]]) -> str:
    if matched_patterns:
        best = max(matched_patterns, key=lambda x: x[1])
        return best[0]

    tipos = set(family["tipos"])
    name_lower = family["family_name"].lower()

    tipo_to_code = {
        "ACTIVO": "AC",
        "PASIVO": "PC",
        "PATRIMONIO": "PAT",
        "PERDIDA": "ER",
        "GANANCIA": "ER",
    }

    # Keywords to codes
    kw_to_code = [
        (["caja", "banco", "efectivo", "disponible"], "AC.01"),
        (["inversiones", "fondo", "mutuo", "deposito", "pacto"], "AC.02"),
        (["cliente", "deudor", "cobrar", "cxc"], "AC.03"),
        (["documento", "cobrar", "letra", "pagare"], "AC.04"),
        (["inventario", "existencia", "mercaderia", "stock", "materia"], "AC.05"),
        (["relacionada", "parte", "vinculada"], "AC.06"),
        (["iva", "impuesto", "recuperar", "ppm", "proveedor"], "AC.07"),
        (["gasto", "anticipado", "pagado", "adelantado"], "AC.07"),
        (["activo", "fijo", "propiedad", "planta", "inmueble", "edificio"], "ANC.01"),
        (["depreciacion", "amortizacion", "deterioro"], "ANC.02"),
        (["intangible", "goodwill", "marca", "patente", "licencia", "software"], "ANC.03"),
        (["inversiones", "permanente", "largo", "plazo", "acciones", "sociedad"], "ANC.04"),
        (["proveedor", "acreedor", "pagar", "comercial"], "PC.01"),
        (["obligacion", "banco", "prestamo", "credito", "mutuo", "hipotecario"], "PC.02"),
        (["leasing", "arriendo", "financiero"], "PC.03"),
        (["factoring"], "PC.04"),
        (["iva", "impuesto", "pagar", "debito", "renta", "tributo"], "PC.05"),
        (["remuneracion", "sueldo", "vacacion", "honorario", "gratificacion"], "PC.06"),
        (["relacionada", "parte", "vinculada", "cp", "corriente"], "PC.07"),
        (["anticipo", "cliente", "ingreso", "percibido", "diferido", "pasivo", "corriente"], "PC.08"),
        (["obligacion", "largo", "plazo", "banco", "mutuo", "hipotecario"], "PNC.01"),
        (["capital", "aporte", "social", "accion", "suscrito", "pagado"], "PAT.01"),
        (["reserva", "prima", "emision", "revalorizacion"], "PAT.02"),
        (["utilidad", "resultado", "acumulado", "retenido", "perdida", "acumulada"], "PAT.03"),
        (["resultado", "ejercicio", "utilidad", "perdida", "periodo"], "PAT.04"),
        (["venta", "ingreso", "facturacion", "giro"], "ER.01"),
        (["costo", "venta", "explotacion", "produccion"], "ER.02"),
        (["gasto", "administracion", "general", "gestion", "oficina"], "ER.04"),
        (["gasto", "venta", "comercial", "marketing", "distribucion"], "ER.05"),
        (["depreciacion", "amortizacion"], "ER.07"),
        (["gasto", "financiero", "interes", "comision", "banco"], "ER.09"),
        (["impuesto", "renta", "categoria"], "ER.10"),
        (["utilidad", "neta", "resultado", "neto", "ganancia", "neta"], "ER.11"),
    ]

    for keywords, code in kw_to_code:
        if all(kw in name_lower for kw in keywords):
            return code
        if any(kw in name_lower for kw in keywords):
            code_prefix = code.split(".")[0]
            tipo_match = {
                "AC": "ACTIVO", "ANC": "ACTIVO",
                "PC": "PASIVO", "PNC": "PASIVO",
                "PAT": "PATRIMONIO", "ER": "PERDIDA",
            }
            expected = tipo_match.get(code_prefix, "")
            if expected in tipos or "DESCONOCIDO" in tipos:
                return code

    return "POR_DEFINIR"


def recomendar_top_10(family_rows: list[dict]) -> list[dict]:
    """Recomienda 10 familias con mejor relación riesgo/recuperación."""
    scored = []
    for fr in family_rows:
        mult = 1.0
        if fr["difficulty"] == "BAJA":
            mult *= 2.5
        elif fr["difficulty"] == "MEDIA":
            mult *= 1.0
        else:
            mult *= 0.3

        n_tipos = len(fr["tipos"].split(", "))
        if n_tipos <= 1:
            mult *= 1.5
        elif n_tipos == 2:
            mult *= 1.0
        else:
            mult *= 0.5

        if fr["regex_legacy"] != "N/A":
            mult *= 2.0

        score = fr["count"] * mult
        scored.append((score, fr))

    scored.sort(key=lambda x: -x[0])
    return [fr for _, fr in scored[:10]]


def analyze():
    pdfs = recolectar_pdfs()
    print(f"Encontrados {len(pdfs)} PDFs")

    all_accounts = extract_all_accounts(pdfs)
    all_accounts = enrich_with_tipo(all_accounts)

    unknown_accounts = [a for a in all_accounts if a["standard_code"] is None]
    classified_accounts = [a for a in all_accounts if a["standard_code"] is not None]

    # Filtrar noise (fechas, headers, OCR garbage)
    unknown_filtered = [a for a in unknown_accounts if is_account_name(a["account_name"])]
    noise_count = len(unknown_accounts) - len(unknown_filtered)

    print(f"\nTotal: {len(all_accounts)} | Classified: {len(classified_accounts)} | UNKNOWN: {len(unknown_accounts)} | Noise filtrado: {noise_count}")

    families = cluster_families(unknown_filtered, threshold=85)
    total_unknown = len(unknown_accounts)
    cumulative = 0
    family_rows = []

    for i, fam in enumerate(families, 1):
        pct = round(fam["count"] / total_unknown * 100, 2)
        cumulative += pct

        legacy_codes = set()
        legacy_confs = []
        for name in fam["account_names"]:
            matches = match_legacy_regex(name)
            for c in matches:
                legacy_codes.add(c)
                for pat, cod, conf in REGLAS_COMPILADAS:
                    if cod == c:
                        legacy_confs.append((cod, conf))
                        break

        expected = guess_expected_code(fam, legacy_confs)
        difficulty = estimate_difficulty(fam, legacy_confs)

        family_rows.append({
            "rank": i,
            "family_name": fam["family_name"],
            "count": fam["count"],
            "pct": pct,
            "cumulative_pct": round(cumulative, 2),
            "tipos": ", ".join(sorted(fam["tipos"])),
            "nombres_ejemplo": "; ".join(fam["nombres_ejemplo"]),
            "regex_legacy": ", ".join(sorted(legacy_codes)) if legacy_codes else "N/A",
            "expected_code": expected,
            "difficulty": difficulty,
        })

    output = {
        "metadata": {
            "total_pdfs": len(pdfs),
            "total_accounts": len(all_accounts),
            "classified": len(classified_accounts),
            "unknown_bruto": len(unknown_accounts),
            "unknown_filtrado": total_unknown,
            "ruido_filtrado": noise_count,
            "unknown_pct": round(total_unknown / len(all_accounts) * 100, 2) if all_accounts else 0,
            "total_families": len(families),
            "families_with_10plus": sum(1 for f in family_rows if f["count"] >= 10),
            "families_with_5plus": sum(1 for f in family_rows if f["count"] >= 5),
        },
        "por_tipo": por_tipo_breakdown(unknown_filtered),
        "pareto": family_rows,
        "top_10_recomendado": recomendar_top_10(family_rows),
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    guardar_md(output)
    guardar_xlsx(output, unknown_filtered)

    print(f"\nFamilias: {len(families)} | >=10 cuentas: {output['metadata']['families_with_10plus']} | >=5: {output['metadata']['families_with_5plus']}")
    for fr in family_rows[:10]:
        print(f"  #{fr['rank']} {fr['family_name']}: {fr['count']} ({fr['pct']}%) [{fr['expected_code']}] {fr['difficulty']} regex={fr['regex_legacy']}")


def por_tipo_breakdown(unknown_accounts: list[dict]) -> dict:
    by_type = Counter()
    for a in unknown_accounts:
        by_type[a.get("tipo", "DESCONOCIDO")] += 1
    total = sum(by_type.values())
    return {
        t: {"count": cnt, "pct": round(cnt / total * 100, 2) if total else 0}
        for t, cnt in sorted(by_type.items(), key=lambda x: -x[1])
    }


def guardar_md(output: dict):
    lines = [
        "# Unknown Accounts Pareto — Post Sprint 28.5A\n",
        f"**Date:** 2026-07-22  \n",
        f"**Contexto:** {output['metadata']['unknown_filtrado']} cuentas UNKNOWN (tras filtrar {output['metadata']['ruido_filtrado']} ruido de parseo) después de migrar 7 reglas regex con precisión 100%.\n",
        "---\n",
        "## Resumen\n",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Total cuentas extraídas | {output['metadata']['total_accounts']} |",
        f"| Clasificadas | {output['metadata']['classified']} |",
        f"| UNKNOWN (bruto) | {output['metadata']['unknown_bruto']} |",
        f"| Ruido filtrado (fechas/headers) | {output['metadata']['ruido_filtrado']} |",
        f"| UNKNOWN (neto analizable) | {output['metadata']['unknown_filtrado']} ({output['metadata']['unknown_pct']}%) |",
        f"| Familias detectadas | {output['metadata']['total_families']} |",
        f"| Familias con ≥10 cuentas | {output['metadata']['families_with_10plus']} |",
        f"| Familias con ≥5 cuentas | {output['metadata']['families_with_5plus']} |",
        "",
        "## UNKNOWN por tipo de cuenta\n",
        "| Tipo | Cuentas | % del total UNKNOWN |",
        "|---|---|---|",
    ]
    for t, v in output["por_tipo"].items():
        lines.append(f"| {t} | {v['count']} | {v['pct']}% |")

    lines += [
        "",
        "## Pareto — Top 50 Familias\n",
        "| Rank | Familia | Count | % | % Acum | Tipos | Código Esperado | Regex Legacy | Dificultad |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fr in output["pareto"][:50]:
        lines.append(
            f"| {fr['rank']} | {fr['family_name']} | {fr['count']} | {fr['pct']}% | "
            f"{fr['cumulative_pct']}% | {fr['tipos']} | {fr['expected_code']} | "
            f"{fr['regex_legacy']} | {fr['difficulty']} |"
        )

    lines += [
        "",
        "## Top 10 Recomendados (menor riesgo, mayor impacto)\n",
        "| # | Familia | Count | Código | Dificultad | Regex | Razón |",
        "|---|---|---|---|---|---|",
    ]
    for i, fr in enumerate(output["top_10_recomendado"], 1):
        reason = f"Tiene regex legacy ({fr['regex_legacy']}), tipo único" if fr["regex_legacy"] != "N/A" else f"Alta frecuencia sin regex legacy"
        lines.append(
            f"| {i} | {fr['family_name']} | {fr['count']} | {fr['expected_code']} | "
            f"{fr['difficulty']} | {fr['regex_legacy']} | {reason} |"
        )

    lines += [
        "",
        "---\n*Generated by analyze_unknown_pareto.py*",
    ]
    with open(OUTPUT_MD, "w") as f:
        f.write("\n".join(lines))


def guardar_xlsx(output: dict, unknown_filtered: list[dict]):
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        m = output["metadata"]
        pd.DataFrame([
            {"Metrica": "Total PDFs", "Valor": m["total_pdfs"]},
            {"Metrica": "Total cuentas", "Valor": m["total_accounts"]},
            {"Metrica": "Classified", "Valor": m["classified"]},
            {"Metrica": "UNKNOWN bruto", "Valor": m["unknown_bruto"]},
            {"Metrica": "Ruido filtrado", "Valor": m["ruido_filtrado"]},
            {"Metrica": "UNKNOWN neto", "Valor": m["unknown_filtrado"]},
            {"Metrica": "Familias", "Valor": m["total_families"]},
            {"Metrica": "Familias >=10", "Valor": m["families_with_10plus"]},
        ]).to_excel(writer, sheet_name="Resumen", index=False)

        pd.DataFrame([
            {"Tipo": t, "Count": v["count"], "%": v["pct"]}
            for t, v in output["por_tipo"].items()
        ]).to_excel(writer, sheet_name="Por tipo", index=False)

        pd.DataFrame(output["pareto"]).to_excel(writer, sheet_name="Pareto", index=False)
        pd.DataFrame(output["top_10_recomendado"]).to_excel(writer, sheet_name="Top 10", index=False)

        pd.DataFrame([
            {"account_name": a["account_name"], "account_code": a["account_code"],
             "tipo": a["tipo"], "source_file": a["source_file"]}
            for a in unknown_filtered
        ]).to_excel(writer, sheet_name="Todas UNKNOWN", index=False)


if __name__ == "__main__":
    analyze()
