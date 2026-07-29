from __future__ import annotations

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

from review_workspace.similarity import fuzzy_score_weighted, normalizar

logger = logging.getLogger(__name__)

REVIEW_DB = Path("review_workspace/review.db")
GOLD_DB = Path("gold_standard.db")
KB_JSON = Path("knowledge_base/cmcc_knowledge.json")
REPORT_PATH = Path("reports/unknown_root_cause_analysis.md")

ORTHOGRAPHIC_VARIANT = "ORTHOGRAPHIC_VARIANT"
OCR_ERROR = "OCR_ERROR"
DICTIONARY_MISSING = "DICTIONARY_MISSING"
SEMANTIC_VARIANT = "SEMANTIC_VARIANT"
SPECIFIC_ACCOUNT = "SPECIFIC_ACCOUNT"
CLIENT_SPECIFIC = "CLIENT_SPECIFIC"
TRUNCATED_TEXT = "TRUNCATED_TEXT"
PARSER_ERROR = "PARSER_ERROR"
TOTAL_NOT_FILTERED = "TOTAL_NOT_FILTERED"
CORRUPTED_EXTRACTION = "CORRUPTED_EXTRACTION"
LIKELY_MATCH_IN_GOLD = "LIKELY_MATCH_IN_GOLD"
TRULY_NEW_ACCOUNT = "TRULY_NEW_ACCOUNT"

CATEGORIES = [
    ORTHOGRAPHIC_VARIANT, OCR_ERROR, DICTIONARY_MISSING, SEMANTIC_VARIANT,
    SPECIFIC_ACCOUNT, CLIENT_SPECIFIC, TRUNCATED_TEXT, PARSER_ERROR,
    TOTAL_NOT_FILTERED, CORRUPTED_EXTRACTION, LIKELY_MATCH_IN_GOLD,
    TRULY_NEW_ACCOUNT,
]

_SYMBOL_HEAVY = re.compile(r"[^a-zA-Z0-9áéíóúñüÁÉÍÓÚÑÜ\s\.\,\-\/]")
_REPEATED_SYMBOLS = re.compile(r"[\.\-\_\=\>\+\|\[\]\{\}\(\)\/\\]{4,}")
_PAT_TOTAL = re.compile(
    r"^(TOTAL\s|TOTALES\s|SUBTOTAL|SUB[\s-]?TOTAL|RESULTADO\s+DEL\s+EJERCICIO|"
    r"UTILIDAD\b|P[EÉ]RDIDA\b)",
    re.IGNORECASE,
)
_PAT_PAGE_FOOTER = re.compile(
    r"(P[AÁ]GINA|PAGE\s|HOJA\s|DE\s+LA\s+P[AÁ]GINA|CONTIN[UÚ]A|VIENE\s+DE)",
    re.IGNORECASE,
)
_PAT_MONTH = re.compile(
    r"(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|"
    r"OCTUBRE|NOVIEMBRE|DICIEMBRE)",
    re.IGNORECASE,
)


def _symbol_ratio(text: str) -> float:
    raw = text.strip().lower()
    if not raw:
        return 1.0
    symbols = _SYMBOL_HEAVY.findall(raw)
    return len(symbols) / max(len(raw), 1)


def _load_gold_standard(db_path: str | Path = GOLD_DB) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT codigo_estandar, nombre_cuenta, normalized FROM gold_standard"
    ).fetchall()
    conn.close()
    return [{"code": r[0], "name": r[1], "normalized": r[2]} for r in rows]


def _load_knowledge_base(kb_path: str | Path = KB_JSON) -> dict[str, Any]:
    kb_path = Path(kb_path)
    if not kb_path.exists():
        return {}
    with open(kb_path) as f:
        return json.load(f)


def _load_unknowns(db_path: str | Path = REVIEW_DB) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT account_id, empresa, archivo, nombre_original, codigo_original, "
        "monto, confidence, metodo, tipo_columna, nivel_jerarquia, account_type "
        "FROM unknown_accounts WHERE review_status='pending'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _best_match(
    name: str, candidates: list[dict[str, Any]], min_score: int = 50
) -> tuple[int, str, str]:
    if not name or not candidates:
        return 0, "", ""
    best_score = 0
    best_code = ""
    best_name = ""
    for c in candidates:
        score, _ = fuzzy_score_weighted(name, c["name"], min_score=min_score)
        if score > best_score:
            best_score = score
            best_code = c.get("code", "")
            best_name = c["name"]
    return best_score, best_code, best_name


def _is_corrupted(name: str) -> bool:
    raw = name.strip()
    if not raw:
        return True
    if _REPEATED_SYMBOLS.search(raw):
        return True
    if _symbol_ratio(raw) > 0.2:
        return True
    return False


def _is_ocr_error(name: str) -> bool:
    raw = name.strip()
    # Has some readable content but mixed with OCR artifacts
    ratio = _symbol_ratio(raw)
    if 0.1 < ratio <= 0.2:
        return True
    alpha = sum(1 for c in raw if c.isalpha())
    clean = len(re.sub(r"\s+", "", raw))
    if clean >= 5 and alpha > 0 and alpha / clean < 0.4:
        return True
    return False


def _is_parser_error(name: str) -> bool:
    raw = name.strip()
    if re.search(r"^[O0]\s*:", raw):
        return True
    if re.search(r"^(Nivel|Desde\s+\d|Al\s+\d|Folio)", raw, re.IGNORECASE):
        return True
    if re.search(r"\d{6,}", raw) and not re.search(r"^\d", raw):
        return True
    return False


def _is_truncated(name: str) -> bool:
    raw = name.strip()
    clean = len(re.sub(r"\s+", "", raw))
    if clean <= 2:
        return True
    words = raw.split()
    if len(words) == 1 and len(raw) <= 5 and not re.search(r"[aeiouáéíóú]", raw, re.IGNORECASE):
        return True
    return False


def _is_client_specific(name: str) -> bool:
    raw = name.strip()
    if re.search(r"RUT|R\.U\.T|RUN\b", raw, re.IGNORECASE):
        return True
    if re.search(r"\d{1,2}\.\d{3}\.\d{3}", raw):
        return True
    if re.search(r"^EMPLEADO|^TRABAJADOR|^SOCIO\b|^ACCIONISTA", raw, re.IGNORECASE):
        return True
    return False


def _is_specific_account(name: str) -> bool:
    raw = name.strip()
    if re.search(r"\b(BANCO|BCO\b|Cta\.\s+Cte|Cta\s+Cte|CUENTA\s+CORRIENTE)\b", raw, re.IGNORECASE):
        return True
    if re.search(r"\b(LEASING|FACTORING|MUTUO|PR[EÉ]STAMO)\b", raw, re.IGNORECASE):
        return True
    if re.search(r"\b(SEGUROS|CAPACITACI[OÓ]N|VI[ÁA]TICO|MOVILIZACI[OÓ]N)\b", raw, re.IGNORECASE):
        return True
    return False


def classify_unknown(
    name: str,
    gold_entries: list[dict[str, Any]],
    kb_variants: list[dict[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "motivo": DICTIONARY_MISSING,
        "confianza": 0.0,
        "mejor_candidato": "",
        "codigo_candidato": "",
        "distancia_fuzzy": 0,
        "existe_en_gold": False,
        "existe_en_kb": False,
    }

    if not name or not name.strip():
        result["motivo"] = CORRUPTED_EXTRACTION
        return result

    # 1. CORRUPTED_EXTRACTION
    if _is_corrupted(name):
        result["motivo"] = CORRUPTED_EXTRACTION
        return result

    # 2. CLIENT_SPECIFIC (before OCR — RUT patterns look symbol-heavy)
    if _is_client_specific(name):
        result["motivo"] = CLIENT_SPECIFIC
        return result

    # 3. PARSER_ERROR (before OCR — "O:" patterns look OCR-ish)
    if _is_parser_error(name):
        result["motivo"] = PARSER_ERROR
        return result

    # 4. OCR_ERROR
    if _is_ocr_error(name):
        result["motivo"] = OCR_ERROR
        return result

    # 5. TOTAL_NOT_FILTERED
    if _PAT_TOTAL.match(name.strip().upper()):
        result["motivo"] = TOTAL_NOT_FILTERED
        return result

    if _PAT_PAGE_FOOTER.search(name):
        result["motivo"] = TOTAL_NOT_FILTERED
        return result

    # 5. Fuzzy against Gold Standard
    gold_score, gold_code, gold_name = _best_match(name, gold_entries, min_score=50)
    result["existe_en_gold"] = gold_score >= 50
    result["distancia_fuzzy"] = gold_score

    if gold_score >= 90:
        result["mejor_candidato"] = gold_name
        result["codigo_candidato"] = gold_code
        result["confianza"] = gold_score / 100.0
        if gold_score >= 95:
            result["motivo"] = ORTHOGRAPHIC_VARIANT
        else:
            result["motivo"] = LIKELY_MATCH_IN_GOLD
        return result

    # 6. Fuzzy against Knowledge Base
    kb_score, kb_code, kb_name = _best_match(name, kb_variants, min_score=50)
    result["existe_en_kb"] = kb_score >= 50
    if kb_score > gold_score:
        result["distancia_fuzzy"] = kb_score
        result["mejor_candidato"] = kb_name
        result["codigo_candidato"] = kb_code
        result["confianza"] = kb_score / 100.0
    else:
        result["confianza"] = max(gold_score, 0) / 100.0

    if kb_score >= 90:
        if not result["mejor_candidato"]:
            result["mejor_candidato"] = kb_name
            result["codigo_candidato"] = kb_code
        result["motivo"] = LIKELY_MATCH_IN_GOLD
        return result

    if gold_score >= 75:
        result["mejor_candidato"] = gold_name
        result["codigo_candidato"] = gold_code
        result["confianza"] = gold_score / 100.0
        result["motivo"] = SEMANTIC_VARIANT
        return result

    if kb_score >= 75:
        result["mejor_candidato"] = kb_name
        result["codigo_candidato"] = kb_code
        result["confianza"] = kb_score / 100.0
        result["motivo"] = SEMANTIC_VARIANT
        return result

    # 7. TRUNCATED_TEXT
    if _is_truncated(name):
        result["motivo"] = TRUNCATED_TEXT
        return result

    # 8. CLIENT_SPECIFIC
    if _is_client_specific(name):
        result["motivo"] = CLIENT_SPECIFIC
        return result

    # 9. SPECIFIC_ACCOUNT
    if _is_specific_account(name):
        result["motivo"] = SPECIFIC_ACCOUNT
        return result

    # 10. Check if it looks like a real account name
    raw = name.strip()
    words = raw.split()
    alpha = sum(1 for c in raw if c.isalpha())
    if len(words) >= 2 and alpha > 5:
        result["motivo"] = TRULY_NEW_ACCOUNT
        return result

    if len(words) >= 1 and alpha > 3:
        result["motivo"] = DICTIONARY_MISSING
        return result

    result["motivo"] = DICTIONARY_MISSING
    return result


def run_audit() -> dict[str, Any]:
    unknowns = _load_unknowns()
    gold = _load_gold_standard()
    kb_data = _load_knowledge_base()

    kb_variants: list[dict[str, Any]] = []
    if kb_data:
        for code, entry in kb_data.get("codes", {}).items():
            for v in entry.get("variantes", []):
                kb_variants.append({"code": code, "name": v["nombre"]})

    results: list[dict[str, Any]] = []
    for u in unknowns:
        name = u.get("nombre_original", "")
        audit = classify_unknown(name, gold, kb_variants)
        results.append({
            "account_id": u["account_id"],
            "archivo": u["archivo"],
            "empresa": u["empresa"],
            "nombre_original": name,
            "motivo": audit["motivo"],
            "confianza": audit["confianza"],
            "mejor_candidato": audit["mejor_candidato"],
            "codigo_candidato": audit["codigo_candidato"],
            "distancia_fuzzy": audit["distancia_fuzzy"],
            "existe_en_gold": audit["existe_en_gold"],
            "existe_en_kb": audit["existe_en_kb"],
        })

    cause_counts: dict[str, int] = Counter(r["motivo"] for r in results)

    name_freq: Counter[str] = Counter(r["nombre_original"] for r in results)

    orthographic = [r for r in results if r["motivo"] == ORTHOGRAPHIC_VARIANT]
    orthographic.sort(key=lambda x: -x["distancia_fuzzy"])

    recoverable = [
        r for r in results
        if r["motivo"] in (ORTHOGRAPHIC_VARIANT, LIKELY_MATCH_IN_GOLD, SEMANTIC_VARIANT)
        and r["distancia_fuzzy"] >= 80
    ]
    recoverable.sort(key=lambda x: -x["distancia_fuzzy"])

    total_auto = sum(
        v for k, v in cause_counts.items()
        if k in (ORTHOGRAPHIC_VARIANT, LIKELY_MATCH_IN_GOLD, SEMANTIC_VARIANT)
    )

    return {
        "total": len(results),
        "cause_distribution": dict(cause_counts.most_common()),
        "top_100_accounts": [(name, freq) for name, freq in name_freq.most_common(100)],
        "top_50_orthographic": [
            {
                "nombre": r["nombre_original"],
                "candidato": r["mejor_candidato"],
                "codigo": r["codigo_candidato"],
                "distancia": r["distancia_fuzzy"],
                "archivo": r["archivo"],
            }
            for r in orthographic[:50]
        ],
        "top_50_recoverable": [
            {
                "nombre": r["nombre_original"],
                "candidato": r["mejor_candidato"],
                "codigo": r["codigo_candidato"],
                "distancia": r["distancia_fuzzy"],
                "archivo": r["archivo"],
            }
            for r in recoverable[:50]
        ],
        "total_auto_recoverable": total_auto,
        "pct_auto_recoverable": round(total_auto / len(results) * 100, 2) if results else 0,
    }


def generate_report(
    audit_result: dict[str, Any] | None = None,
    output_path: str | Path = REPORT_PATH,
) -> str:
    if audit_result is None:
        audit_result = run_audit()

    lines: list[str] = []
    lines.append("# Auditoría de UNKNOWN — Análisis de Causa Raíz")
    lines.append("")
    lines.append(f"**Generado:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**Fuente:** `{REVIEW_DB}` ({audit_result['total']} registros)")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Total UNKNOWN analizados | {audit_result['total']} |")
    lines.append(f"| Recuperables automáticamente | {audit_result['total_auto_recoverable']} |")
    lines.append(f"| Porcentaje recuperable | {audit_result['pct_auto_recoverable']}% |")
    lines.append("")

    lines.append("## Distribución por causa raíz")
    lines.append("")
    lines.append("| Causa | Cantidad | % |")
    lines.append("|-------|----------|---|")
    dist = audit_result["cause_distribution"]
    for cause, count in dist.items():
        pct = round(count / audit_result["total"] * 100, 2)
        lines.append(f"| {cause} | {count} | {pct}% |")
    lines.append("")

    lines.append("## Estimación de recuperación automática")
    lines.append("")
    lines.append("| Categoría recuperable | Estimación |")
    lines.append("|----------------------|------------|")
    for cause in (ORTHOGRAPHIC_VARIANT, LIKELY_MATCH_IN_GOLD, SEMANTIC_VARIANT):
        cnt = dist.get(cause, 0)
        pct = round(cnt / audit_result["total"] * 100, 2) if audit_result["total"] else 0
        lines.append(f"| {cause} | {cnt} ({pct}%) |")
    lines.append(f"| **Total recuperable** | **{audit_result['total_auto_recoverable']} ({audit_result['pct_auto_recoverable']}%)** |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Top 100 cuentas más repetidas")
    lines.append("")
    lines.append("| # | Nombre | Frecuencia |")
    lines.append("|---|--------|------------|")
    for i, (name, freq) in enumerate(audit_result["top_100_accounts"][:100], 1):
        lines.append(f"| {i} | {name} | {freq} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Top 50 variantes ortográficas (score ≥ 95)")
    lines.append("")
    lines.append("| # | Nombre UNKNOWN | Candidato Gold | Código | Distancia | Archivo |")
    lines.append("|---|----------------|----------------|--------|-----------|---------|")
    for i, entry in enumerate(audit_result["top_50_orthographic"][:50], 1):
        lines.append(
            f"| {i} | {entry['nombre']} | {entry['candidato']} | "
            f"{entry['codigo']} | {entry['distancia']} | {entry['archivo']} |"
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Top 50 candidatos recuperables automáticamente")
    lines.append("")
    lines.append("| # | Nombre UNKNOWN | Mejor candidato | Código | Distancia | Archivo |")
    lines.append("|---|----------------|-----------------|--------|-----------|---------|")
    for i, entry in enumerate(audit_result["top_50_recoverable"][:50], 1):
        lines.append(
            f"| {i} | {entry['nombre']} | {entry['candidato']} | "
            f"{entry['codigo']} | {entry['distancia']} | {entry['archivo']} |"
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Reporte generado por analysis/unknown_audit.py*")

    text = "\n".join(lines)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    logger.info("Reporte: %s", path)
    return text


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run_audit()
    generate_report(result)
    print(f"Total: {result['total']}")
    print(f"Auto-recoverable: {result['total_auto_recoverable']} ({result['pct_auto_recoverable']}%)")
    print("Distribución:")
    for cause, count in result["cause_distribution"].items():
        print(f"  {cause}: {count}")
