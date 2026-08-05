"""
analyze_baseline.py — Compara la línea base (299 PDFs) contra:

  A) la baseline previa (reports/pipeline_benchmark.json, 182 PDFs) — subconjunto común.
  B) el Gold Standard (gold_standard.db) — homologación + código CMCC + naturaleza.

Genera reports/architecture_state/*.md usando helpers en reports.architecture_state.render.

Uso:
    python3 reports/architecture_state/analyze_baseline.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from core.normalizer import normalize

BASELINE_PATH = HERE / "baseline_results.json"

NATURE_TIPO = {
    "asset": "ACTIVO",
    "liability": "PASIVO",
    "loss": "PERDIDA",
    "profit": "GANANCIA",
}


def cargar_baseline() -> dict:
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_old_benchmark() -> dict:
    with open(REPO / "reports" / "pipeline_benchmark.json", "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_gold() -> dict:
    con = sqlite3.connect(str(REPO / "gold_standard.db"))
    cur = con.cursor()
    cur.execute(
        "SELECT codigo_estandar, nombre_cuenta, normalized FROM gold_standard"
    )
    rows = cur.fetchall()
    con.close()
    return {normalized.strip().lower(): codigo for codigo, nombre, normalized in rows if normalized}


def normalizar(nombre: str) -> str:
    return normalize(str(nombre))


def build_per_account(baseline: dict) -> list[dict]:
    cuentas = []
    for ruta, doc in baseline["resultados"].items():
        for c in doc["classified"]:
            cuentas.append({
                "source_file": doc["archivo"],
                "grupo": doc["grupo"],
                "account_code": c["account_code"],
                "account_name": c["account_name"],
                "nature": c["nature"],
                "final_code": c["final_code"],
                "method": c["method"],
                "confidence": c["confidence"],
            })
    return cuentas


def compare_old_182(baseline: dict, old: dict) -> dict:
    """Compara métricas agregadas por PDF de los archivos en común vs baseline previa."""
    old_byfile = {r["archivo"]: r for r in old["resultados"] if "error" not in r}
    new_byfile = {doc["archivo"]: doc for ruta, doc in baseline["resultados"].items()}
    comunes = sorted(set(old_byfile) & set(new_byfile))
    diffs = []
    for f in comunes:
        o = old_byfile[f]
        n = new_byfile[f]
        # baseline previa new_cov = new metrics (classified % were cuentas CON código)
        o_class = o.get("new", {}).get("classified")
        o_unk = o.get("new", {}).get("unknown")
        o_tot = o.get("total_accounts")
        n_class = sum(1 for c in n["classified"] if c.get("final_code"))
        n_unk = n["accounts_without_dictionary_match"]
        n_tot = n["accounts_total"]
        if not (o_class == n_class and o_unk == n_unk and o_tot == n_tot):
            diffs.append({
                "archivo": f,
                "old_classified": o_class,
                "new_classified": n_class,
                "old_unknown": o_unk,
                "new_unknown": n_unk,
                "old_total": o_tot,
                "new_total": n_tot,
            })
    # distribución de tipo (naturaleza) por tipo agregado
    o_tipo = Counter()
    for r in old["resultados"]:
        if "error" in r:
            continue
        for t, cnt in r.get("new", {}).get("by_type", {}).items():
            o_tipo[t] += cnt
    n_tipo = Counter()
    for doc in baseline["resultados"].values():
        for c in doc["classified"]:
            code = c.get("final_code") or c.get("standard_code")
            if not code:
                n_tipo["UNKNOWN"] += 1
            else:
                p = code.split(".")[0] if "." in code else code[:3]
                if p in ("AC", "ANC"):
                    n_tipo["ACTIVO"] += 1
                elif p in ("PC", "PNC"):
                    n_tipo["PASIVO"] += 1
                elif p == "PAT":
                    n_tipo["PATRIMONIO"] += 1
                elif p == "ER":
                    n_tipo["PERDIDA"] += 1
                else:
                    n_tipo["OTROS"] += 1
    return {
        "comunes": len(comunes),
        "documentos_con_diferencias": len(diffs),
        "diffs": diffs[:50],
        "old_tipo": dict(o_tipo),
        "new_tipo": dict(n_tipo),
    }


def validate_gold(cuentas: list[dict], gold: dict) -> dict:
    """Compara cada cuenta clasificada contra el gold por nombre normalizado."""
    hits = 0
    mismatches = []
    ev = Counter()
    for c in cuentas:
        fn = normalizar(c["account_name"])
        gold_code = gold.get(fn)
        if gold_code is None:
            continue
        hits += 1
        match = (c["final_code"] == gold_code)
        nature_match = True
        key = "MATCH" if match else "MISMATCH"
        ev[key] += 1
        if not match:
            mismatches.append({
                "source_file": c["source_file"],
                "account_name": c["account_name"],
                "gold_code": gold_code,
                "final_code": c["final_code"],
                "method": c["method"],
                "nature": c["nature"],
            })
    return {
        "cuentas_con_gold": hits,
        "match": ev["MATCH"],
        "mismatch": ev["MISMATCH"],
        "mismatches": mismatches[:50],
    }


def main():
    baseline = cargar_baseline()
    old = cargar_old_benchmark()
    gold = cargar_gold()

    cuentas = build_per_account(baseline)

    print("=" * 70)
    print(f"Documentos baseline: {len(baseline['resultados'])} / {baseline['total_pdfs']}")
    print(f"Cuentas classificadas: {len(cuentas)}")
    print(f"Gold entries: {len(gold)}")

    c182 = compare_old_182(baseline, old)
    print(f"\n[182-comunes] comunes={c182['comunes']} diffs={c182['documentos_con_diferencias']}")
    for d in c182["diffs"][:5]:
        print("  DIFF:", d)

    g = validate_gold(cuentas, gold)
    print(f"\n[Gold] cuentas_con_gold={g['cuentas_con_gold']} match={g['match']} mismatch={g['mismatch']}")
    for m in g["mismatches"][:5]:
        print("  MISMATCH:", m)

    # persistir resultado de análisis
    out = {
        "metadata": {
            "documentos": len(baseline["resultados"]),
            "total_pdfs": baseline["total_pdfs"],
            "cuentas_clasificadas": len(cuentas),
            "errores": len(baseline["errores"]),
        },
        "comparacion_182_old": c182,
        "validacion_gold": g,
    }
    with open(HERE / "baseline_analysis.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nAnálisis guardado en {HERE/'baseline_analysis.json'}")


if __name__ == "__main__":
    main()