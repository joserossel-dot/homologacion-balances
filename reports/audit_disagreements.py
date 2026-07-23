"""Audita las 319 discrepancias entre SemanticMatcher y RegexFallback.

NO modifica el pipeline.
NO escribe reglas.
Solo genera evidencia.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from app_validacion import REGLAS_REGEX

REPORT_DIR = Path(__file__).resolve().parent
CATALOG_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "concept_catalog.json"
BENCH_PATH = REPORT_DIR / "semantic_matcher_v1.json"

OUT_JSON = REPORT_DIR / "disagreement_audit.json"
OUT_MD = REPORT_DIR / "disagreement_audit.md"
OUT_XLSX = REPORT_DIR / "disagreement_audit.xlsx"


def load_catalog():
    with open(CATALOG_PATH) as f:
        data = json.load(f)
    return {c["id"]: c for c in data["concepts"]}


def load_regex_map():
    """Retorna {regex_index: (pattern_str, code, confidence)}."""
    return {i: REGLAS_REGEX[i] for i in range(len(REGLAS_REGEX))}


def get_regex_index_for_account(account_name: str, phase1_code: str) -> int | None:
    """Encuentra qué regex de pipeline matchó esta cuenta."""
    norm = account_name.lower().strip()
    for i, (pat_str, code, conf) in enumerate(REGLAS_REGEX):
        if code == phase1_code:
            compiled = re.compile(pat_str, re.IGNORECASE | re.UNICODE)
            if compiled.search(norm):
                return i
    return None


def _find_regex_pattern(name_lower: str, rx_code: str) -> str | None:
    """Busca qué regex pattern le ganó a esta cuenta."""
    for pat_str, code, _ in REGLAS_REGEX:
        if code == rx_code:
            try:
                if re.compile(pat_str, re.IGNORECASE | re.UNICODE).search(name_lower):
                    return pat_str
            except Exception:
                continue
    return None


def classify_discrepancy(d: dict, concept: dict | None, regex_idx: int | None) -> tuple[str, str]:
    name = d["account_name"]
    sm_code = d["expected_cmcc"]
    rx_code = d["phase1_code"]
    tier = d["match_tier"]
    score = d["score"]
    sm_concept = d.get("concept_name", "")
    gold_info = d.get("tipo", "")
    name_lower = name.lower()

    regex_pat = _find_regex_pattern(name_lower, rx_code)

    # ---- Casos donde Regex claramente gana (SM se equivoca) ----
    sm_loses_map = {
        # (partial name match, rx_code, disallowed sm_concept)
        ("vehiculos", "ANC.03", "DEPRECIACION"): "SM clasifica 'vehiculos' como DEPRECIACION (concepto genérico); Regex correcto como ANC.03 (PP&E)",
        ("seguros", "ER.04", "DIFERIDOS"): "SM clasifica 'seguros' como DIFERIDOS; en contexto de balance, seguros pagados por anticipado son PC.08, pero como gasto del período son ER.04 — depende del contexto de la cuenta",
        ("seguros", "ER.04", "PROPIEDAD"): "SM clasifica 'seguros' como PROPIEDAD; Regex correcto como ER.04 (gasto)",
        ("credito senge", "AC.07", "PRESTAMOS"): "SM clasifica 'crédito sence' como PRESTAMOS (PC.02); Regex correcto como AC.07 (Crédito SENCE es activo tributario)",
        ("credito sence", "AC.07", "PRESTAMOS"): "SM clasifica 'crédito sence' como PRESTAMOS (PC.02); Regex correcto como AC.07 (Crédito SENCE es activo tributario)",
        ("combustible", "ER.04", "VEHICULOS"): "SM clasifica 'combustible' como VEHIÍCULOS; Regex correcto como ER.04 (gasto de operación)",
        ("arriendos", "ER.01", "DIFERIDOS"): "SM clasifica 'arriendos' como DIFERIDOS; arriendos como ingreso no es típico — Regex puede ser incorrecto también",
        ("resultado operacional", "ER.13", "INGRESOS"): "SM clasifica 'resultado operacional' como INGRESOS; debería ser ER.13 (Resultado neto)",
        ("otras ganancias", "ER.01", "PERDIDA"): "SM clasifica 'otras ganancias' como PERDIDA; Regex correcto como ER.01 (otros ingresos)",
        ("im correccion", "ER.14", "CORRECCION_MONE"): "SM clasifica 'im correccion monetaria' como CORRECCION_MONETARIA; 'im' = impuesto, Regex correcto como ER.14",
        ("ingresos fuera", "ER.13", "INGRESOS"): "SM clasifica 'ingresos fuera de explotacion' como INGRESOS; Regex correcto como ER.13 (fuera de explotación)",
    }
    for (pat, expected_rx, bad_sm), reason in sm_loses_map.items():
        if pat in name_lower and rx_code == expected_rx and sm_concept == bad_sm:
            return ("3", f"Concepto incorrecto: {reason}")

    # ---- Casos donde Regex claramente gana (SM mal por tier/score) ----
    # Construcciones → SM=GASTOS_MANTENCION, Rx=ANC.01 correcto
    if "construccion" in name_lower and rx_code == "ANC.01" and sm_concept in ("GASTOS_MANTENCION", "COSTOS"):
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna {sm_concept} (concepto incorrecto); Regex ANC.01 correcto")
    # Maquinaria → SM=COSTOS, Rx=ANC.01 correcto
    if ("maquinaria" in name_lower or "muebl" in name_lower) and rx_code == "ANC.01" and sm_concept in ("COSTOS", "GASTOS_MANTENCION", "DEPRECIACION"):
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna {sm_concept} (concepto incorrecto); Regex ANC.01 correcto")
    # Impuestos por recuperar → SM=IMPUESTOS (PC.05), Rx=AC.07 correcto
    if "recuper" in name_lower and rx_code == "AC.07" and sm_concept == "IMPUESTOS":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna IMPUESTOS por pagar; 'por recuperar' es activo (AC.07)")
    # Depreciacion acumulada → SM=DEPRECIACION (ER.07), Rx=ANC.01 correcto (contra-activo)
    if "depreciacion" in name_lower and rx_code == "ANC.01" and sm_concept == "DEPRECIACION" and "acumulad" in name_lower:
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna DEPRECIACION como gasto; es contra-activo no corriente")
    # Acreedores varios → SM=PROVEEDORES, Rx=PC.08 o PC.07 correcto
    if "acreedor" in name_lower and rx_code in ("PC.08", "PC.07") and sm_concept == "PROVEEDORES":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna PROVEEDORES; acreedores varios son PC.08 (Otras cuentas por pagar)")

    # ---- Más casos de Concepto incorrecto ----
    # Terrenos → SM=OBLIGACIONES, Rx=ANC.01 correcto
    if "terreno" in name_lower and sm_concept == "OBLIGACIONES" and rx_code == "ANC.01":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna OBLIGACIONES; terrenos son activo no corriente")
    # Seguros pagados por anticipado → SM=SEGUROS (gasto), Rx=AC.07 (activo)
    if "seguros" in name_lower and "paga" in name_lower and "anticip" in name_lower and rx_code == "AC.07":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna SEGUROS como gasto; seguro pagado por anticipado es activo (AC.07)")
    # Equipos computacionales → SM=GASTOS, Rx=ANC.01 correcto
    if "equip" in name_lower and "comput" in name_lower and rx_code == "ANC.01":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna GASTOS; equipos computacionales son activo no corriente")
    # Gastos pagados por anticipado → SM=GASTOS, Rx=AC.01 correcto (activo corriente)
    if "gastos" in name_lower and "paga" in name_lower and "anticip" in name_lower and rx_code == "AC.01":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna GASTOS como gasto; gasto pagado por anticipado es activo corriente")
    # Prestamos al personal → SM=PRESTAMOS (pasivo), Rx=AC.01 (activo) correcto
    if ("prestamo" in name_lower and "personal" in name_lower and rx_code == "AC.01"):
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna PRESTAMOS (pasivo); préstamos al personal son activo corriente")
    # Dividendos/provisorios → SM=DIVIDENDOS (AC.03), Rx=AC.06S (accionistas)
    if "dividendo" in name_lower and rx_code == "AC.06S" and sm_concept == "DIVIDENDOS":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna AC.03/DIVIDENDOS; dividendo provisorio es AC.06S (cuenta corriente accionistas)")
    # Aporte patronal → SM=APORTE (capital), Rx=ER.04 (gasto)
    if "aporte" in name_lower and "patron" in name_lower and rx_code == "ER.04":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna APORTE (capital); aporte patronal es gasto (ER.04)")
    # Isapres → SM=APORTE, Rx=PC.06 (remuneraciones por pagar)
    if "isapre" in name_lower and rx_code == "PC.06":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna APORTE; ISAPRES son descuentos de remuneraciones (PC.06)")
    # Agua potable → SM=PAT.01 (AGUA concepto incorrecto), Rx=ER.04 (gasto)
    if "agua" in name_lower and rx_code == "ER.04" and sm_concept == "AGUA":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna AGUA (concepto genérico mapeado a PAT.01); agua potable es gasto (ER.04)")
    # Edificios → SM=PROVISIONES, Rx=ANC.01
    if "edificio" in name_lower and rx_code == "ANC.01" and sm_concept in ("PROVISIONES", "DIFERIDOS", "OBLIGACIONES"):
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna {sm_concept}; edificios son activo no corriente (ANC.01)")
    # Gastos de importaciones → SM=ANTICIPO, Rx=ER.02 (costo de venta)
    if "importacion" in name_lower and rx_code == "ER.02":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna ANTICIPO; gastos de importación son costo (ER.02)")

    # ---- Casos donde SM claramente gana (Regex demasiado amplia) ----
    sm_wins_map = {
        ("honorarios", "ER.04"): "Regex ER.04 demasiado amplia matchea 'honorarios' como gasto; SM correcto como PC.06 (Honorarios por pagar)",
        ("remuneraciones", "ER.04"): "Regex ER.04 demasiado amplia matchea 'remuneraciones' como gasto; SM correcto como PC.06 (Remuneraciones por pagar)",
        ("sueldos", "ER.04"): "Regex ER.04 demasiado amplia; SM correcto como PC.06 (Remuneraciones por pagar)",
        ("cuentas? por pagar", "PC.07"): "Regex PC.07 demasiado amplia; SM correcto como PC.01 (Proveedores)",
        ("correccion monetaria", "ER.14"): "Regex ER.14 demasiado amplia; SM correcto como ER.11 (Corrección Monetaria como resultado)",
        ("capital autorizado", "PC.01"): "Regex PC.01 demasiado amplia; 'capital autorizado' es PAT.01 (patrimonio)",
        ("intereses percibidos", "ER.12"): "Regex ER.12 demasiado amplia; SM correcto como ER.09 (Intereses)",
        ("intereses ganados", "ER.12"): "Regex ER.12 demasiado amplia; SM correcto como ER.09 (Intereses)",
        ("intereses y reajustes", "ER.12"): "Regex ER.12 demasiado amplia; SM correcto como ER.09 (Intereses)",
        ("ingresos financieros", "ER.12"): "Regex ER.12 demasiado amplia; SM correcto como ER.09 (Intereses financieros)",
        ("materiales e insumos", "ER.02"): "Regex ER.02 demasiado amplia; SM correcto como AC.05 (Inventarios - Materiales)",
        ("impuestos a la renta", "ER.10"): "Regex ER.10 demasiado amplia; SM correcto como PC.05 (Impuestos por pagar)",
    }

    for (pat, expected_rx), reason in sm_wins_map.items():
        if re.search(pat, name_lower) and rx_code == expected_rx:
            return ("1", f"Regex demasiado amplia: {reason}")

    # ---- Documentos → AC.04 vs AC.03 ----
    if "documento" in name_lower and rx_code == "AC.03" and sm_code == "AC.04":
        return ("1", f"Regex demasiado amplia: '{name}' → AC.03 debería ser AC.04 (Documentos por cobrar)")

    # ---- Acciones → ANC.04 vs ANC.05 ----
    if "accion" in name_lower and rx_code == "ANC.05" and sm_code == "ANC.04":
        return ("1", f"Regex demasiado amplia: '{name}' → ANC.05 debería ser ANC.04 (Inversiones)")

    # ---- Prestamos bancarios → PC.02 vs ER.09 ----
    if "prestamo" in name_lower and "bancar" in name_lower and rx_code == "PC.02":
        return ("1", f"Regex demasiado amplia: '{name}' → SM da GASTOS_BANCARIOS; préstamo bancario es PC.02 (pasivo)")

    # ---- Arrendamiento → PC.03 vs PC.08 ----
    if ("arrend" in name_lower or "leasing" in name_lower) and rx_code == "PC.08" and sm_code == "PC.02":
        return ("1", f"Regex demasiado amplia: '{name}' → PC.08 debería ser PC.02 (Obligaciones por leasing)")

    # ----  Otros imponibles → no debería ser PAT.01 (capital) ----   
    if "imponible" in name_lower and rx_code == "ER.04" and sm_concept == "CAPITAL":
        return ("3", f"Concepto incorrecto: '{name}' → SM asigna CAPITAL; otros imponibles son ER.04 (gasto)")

    # ---- ER.04 genérico matchando todo ----
    if rx_code == "ER.04" and tier <= 3 and score >= 0.90:
        return ("1", f"Regex demasiado amplia: ER.04 matchea '{name}' pero SM da {sm_code}({sm_concept}) con alta confianza")

    # ---- Correccion monetaria → ER.11 vs ER.14/ER.13 ----
    if "correccion" in name_lower and rx_code in ("ER.14", "ER.13") and sm_code == "ER.11":
        return ("1", f"Regex demasiado amplia: '{name}' → {rx_code} debería ser ER.11 (Corrección Monetaria)")

    # ---- Cuentas por pagar → PC.01 vs PC.07 ----
    if re.search(r"cuentas?\s*por\s*pagar", name_lower) and rx_code == "PC.07" and sm_code == "PC.01":
        return ("1", f"Regex demasiado amplia: '{name}' → PC.07 debería ser PC.01 (Proveedores)")

    # ---- Capital → PAT.01 vs PC.01 ----
    if "capital" in name_lower and rx_code == "PC.01" and sm_code in ("PAT.01", "PAT.04"):
        return ("1", f"Regex demasiado amplia: 'capital' en '{name}' es patrimonio, no pasivo")

    # ---- Clientas → AC.03 vs AC.01 ----
    if ("cliente" in name_lower or "deudor" in name_lower) and rx_code == "AC.01" and sm_code == "AC.03":
        return ("1", f"Regex demasiado amplia: '{name}' → AC.01 debería ser AC.03 (Clientes)")

    # ---- Maquinaria → ANC.01 vs AC.01 ----
    if re.search(r"maquinaria|equipo|instalación|instalacion|muebles", name_lower) and rx_code == "AC.01" and sm_code == "ANC.01":
        return ("1", f"Regex demasiado amplia: '{name}' → AC.01 debería ser ANC.01 (Activo no corriente)")

    # ---- Inventarios → AC.05 vs AC.01 ----
    if re.search(r"existencia|inventario|material|insumo", name_lower) and rx_code == "AC.01" and sm_code == "AC.05":
        return ("1", f"Regex demasiado amplia: '{name}' → AC.01 debería ser AC.05 (Inventarios)")

    # ---- Gastos → ER.04 y SM da otra cosa ----
    if rx_code == "ER.04" and tier <= 3 and sm_code not in ("ER.04", "POR_DEFINIR"):
        return ("1", f"Regex demasiado amplia: ER.04 matchea '{name}' pero SM da {sm_code}({sm_concept})")

    # ---- Provisiones → PC.08 vs ER.04 ----
    if "provision" in name_lower and rx_code == "ER.04" and sm_code == "PC.08":
        return ("1", f"Regex demasiado amplia: 'provision' en '{name}' no debiera ser ER.04; SM da PC.08 (Diferidos)")

    # ---- Intereses → ER.09 vs ER.12 ----
    if ("interes" in name_lower or "comision" in name_lower) and rx_code == "ER.12" and sm_code == "ER.09":
        return ("1", f"Regex demasiado amplia: '{name}' → ER.12 debería ser ER.09 (Intereses)")

    # ---- PC.06 as payables ----
    if rx_code == "ER.04" and sm_code == "PC.06":
        return ("1", f"Regex demasiado amplia: ER.04 matchea '{name}' como gasto; SM correcto como PC.06")

    # ---- ER.04 → gastos misceláneos vs cuentas específicas ----
    if rx_code == "ER.04" and sm_concept in ("GASTOS", "IMPUESTOS", "PERDIDA") and tier in (1, 2):
        return ("2", f"Concepto demasiado amplio: SM asigna '{sm_concept}' a '{name}' — concepto muy genérico")

    # 5. Error OCR
    ocr_indicators = [
        r'^\s*[a-eg-z]\s+[a-z]',  # single-char prefix like "a ", "e ", "j "
        r'[0o]\s+[a-z]',
        r'\d+[a-z]{2}',
        r'[a-z]\d+',
    ]
    if any(re.search(p, name) for p in ocr_indicators):
        return ("5", f"Error OCR: nombre '{name}' tiene prefijo suelto o dígitos inesperados")

    # 6. Parser issues
    if len(name) < 4 or (any(c.isdigit() for c in name) and not any(
        kw in name_lower for kw in ["20", "31", "impuesto", "renta", "iva", "año", "a%o", "ley"]
    )):
        return ("6", f"Parser: nombre '{name}' muy corto o numérico — posible extracción incorrecta")

    # 7. Gold info contradiction
    if "Gold" in gold_info and "fuzzy" in gold_info and "digito" in gold_info:
        return ("7", f"Tipo de cuenta incorrecto: Gold dice {gold_info}")

    # 8. Error del catálogo
    if sm_code == "POR_DEFINIR":
        return ("8", f"Error del catálogo: concepto {sm_concept} no tiene código asignado")

    # ---- Casos con score bajo pero match válido por diseño (tier 4-6) ----
    # Para tier 4-6 con score 0.60-0.69, es un match válido de baja confianza.
    # Determinamos si SM es más razonable que Regex.
    if 4 <= tier <= 6 and 0.60 <= score < 0.70:
        # Casos donde la root word match apunta a concepto específico vs regex genérico
        good_sm = {
            ("intereses", "ER.12"): "SM matchea 'intereses' como ER.09 (vía root word); Regex ER.12 demasiado amplia",
            ("honorarios", "ER.04"): "SM matchea 'honorarios*' como PC.06; Regex ER.04 demasiado amplia",
            ("capital", "PC.01"): "SM matchea 'capital' como PAT.01 (patrimonio); Regex PC.01 incorrecto",
            ("maquinaria", "AC.01"): "SM matchea 'maquinaria' como ANC.01; Regex AC.01 demasiado amplia",
            ("existencia", "AC.01"): "SM matchea 'existencias' como AC.05 (inventarios); Regex AC.01 demasiado amplia",
            ("materiales", "ER.02"): "SM matchea 'materiales' como AC.05 (inventarios); Regex ER.02 demasiado amplia",
            ("impuesto", "ER.10"): "SM matchea 'impuesto' como PC.05 (por pagar); Regex ER.10 demasiado amplia",
            ("cliente", "AC.01"): "SM matchea 'cliente*' como AC.03; Regex AC.01 demasiado amplia",
            ("deudor", "AC.01"): "SM matchea 'deudor*' como AC.03; Regex AC.01 demasiado amplia",
            ("ganancia", "ER.11"): "SM matchea 'ganancia*' como PAT.04 (utilidad); Regex ER.11 demasiado amplia",
            ("utilidad", "ER.11"): "SM matchea 'utilidad' como PAT.04; Regex ER.11 demasiado amplia",
            ("aporte", "PC.01"): "SM matchea 'aporte' como PAT.01 (capital); Regex PC.01 demasiado amplia",
            ("ciento", "ER.04"): "SM matchea 'por ciento' como PC.08 (diferido); podría ser gasto o diferido",
            ("cien", "ER.04"): "SM matchea 'por cien' como PC.08; posible error de parsing",
            ("participacion", "ER.04"): "SM matchea 'participacion' como PAT (patrimonio); Regex ER.04 incorrecta",
            ("patrimonio", "PC.01"): "SM matchea 'patrimonio' como PAT; Regex PC.01 incorrecta",
            ("prestamo", "PC.01"): "SM matchea 'prestamo' como PC.02; Regex PC.01 demasiado amplia",
            ("seguro", "ER.04"): "SM matchea 'seguros*' como PC.08 (diferido); Regex ER.04 podría ser correcto — contexto dependiente",
        }
        for (kw, bad_rx), reason in good_sm.items():
            if kw in name_lower and rx_code == bad_rx:
                return ("1", f"Regex demasiado amplia: {reason}")
        return ("10", f"Caso excepcional: '{name}' → Rx={rx_code}, SM={sm_code}({sm_concept}), tier={tier}, score={score}")

    # 9. Error de RapidFuzz (score muy bajo)
    if tier >= 4 and score < 0.60:
        return ("9", f"Error de RapidFuzz: score muy bajo ({score}) en tier {tier} — posible falso positivo")

    # 4. Keyword ambigua
    ambiguous_map = {
        "otros": "Keyword 'otros' es ambigua — puede ser gasto, ingreso, activo o pasivo",
        "varias": "Keyword 'varias' es ambigua",
        "varios": "Keyword 'varios' es ambigua",
        "caja": "Keyword 'caja' es ambigua — puede ser AC.02 (efectivo) u otra cuenta",
    }
    for kw, reason in ambiguous_map.items():
        if kw in name_lower.split():
            return ("4", f"Keyword ambigua: {reason}")

    # 10. Caso excepcional - fallback
    return ("10", f"Caso excepcional: '{name}' → Rx={rx_code}, SM={sm_code}({sm_concept}), tier={tier}, score={score}")


def run_audit():
    catalog = load_catalog()
    regex_map = load_regex_map()

    with open(BENCH_PATH) as f:
        data = json.load(f)

    all_results = data["results"]
    discrepancies = [
        r for r in all_results
        if r.get("phase1_code") and r.get("expected_cmcc")
        and r["phase1_code"] != r["expected_cmcc"]
    ]

    print(f"Total discrepancias: {len(discrepancies)}")

    # ---- Clasificar cada discrepancia ----
    audit_rows = []
    category_counts: Counter[str] = Counter()
    sm_wins = 0
    regex_wins = 0
    human_needed = 0

    # Matrices
    rx_vs_sm: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    concept_conflict: Counter[str] = Counter()
    regex_conflict: Counter[str] = Counter()
    word_conflict: Counter[str] = Counter()

    for d in discrepancies:
        name = d["account_name"]
        sm_code = d["expected_cmcc"]
        rx_code = d["phase1_code"]
        sm_concept = d.get("concept_name", "")
        tier = d["match_tier"]
        score = d["score"]
        confidence = d.get("confidence", "")
        gold_info = d.get("tipo", "")

        concept = catalog.get(d.get("concept_id", ""))
        regex_idx = get_regex_index_for_account(name, rx_code)

        cat_id, reason = classify_discrepancy(d, concept, regex_idx)
        cat_labels = {
            "1": "Regex demasiado amplia",
            "2": "Concepto demasiado amplio",
            "3": "Concepto incorrecto",
            "4": "Keyword ambigua",
            "5": "Error OCR",
            "6": "Parser",
            "7": "Tipo de cuenta incorrecto",
            "8": "Error del catálogo",
            "9": "Error de RapidFuzz",
            "10": "Caso excepcional",
        }
        category = cat_labels.get(cat_id, "Desconocido")

        # Determinar ganador
        if cat_id == "1":
            who_wins = "SemanticMatcher"
            sm_wins += 1
        elif cat_id == "3":
            who_wins = "Regex"
            regex_wins += 1
        elif cat_id in ("5", "6", "7"):
            who_wins = "Indefinido (requiere revisión)"
            human_needed += 1
        elif cat_id == "8":
            who_wins = "Indefinido (requiere revisión)"
            human_needed += 1
        elif cat_id == "9":
            who_wins = "Indefinido (requiere revisión)"
            human_needed += 1
        elif cat_id == "10":
            who_wins = "Indefinido (requiere revisión)"
            human_needed += 1
        elif cat_id == "2":
            who_wins = "Indefinido (requiere revisión)"
            human_needed += 1
        elif cat_id == "4":
            who_wins = "Indefinido (requiere revisión)"
            human_needed += 1
        else:
            who_wins = "Indefinido (requiere revisión)"
            human_needed += 1

        category_counts[category] += 1
        rx_vs_sm[rx_code][sm_code] = rx_vs_sm[rx_code].get(sm_code, 0) + 1
        concept_conflict[sm_concept] += 1
        regex_conflict[rx_code] += 1
        for w in name.lower().split():
            if len(w) >= 4:
                word_conflict[w] += 1

        row = {
            "account_name": name,
            "tipo": d.get("tipo", ""),
            "account_code": d.get("account_code", ""),
            "source_file": d.get("source_file", ""),
            "sm_code": sm_code,
            "sm_concept": sm_concept,
            "sm_score": score,
            "sm_tier": tier,
            "sm_confidence": confidence,
            "regex_code": rx_code,
            "regex_index": regex_idx if regex_idx is not None else "",
            "gold_info": gold_info,
            "category": category,
            "category_id": cat_id,
            "who_wins": who_wins,
            "reason": reason,
        }
        audit_rows.append(row)

    # ---- Ensamblar salida ----
    # Matriz Rx vs SM
    all_rx = sorted(set(r["regex_code"] for r in audit_rows))
    all_sm = sorted(set(r["sm_code"] for r in audit_rows))
    matrix_rows = []
    for rx in all_rx:
        for sm in all_sm:
            cnt = rx_vs_sm[rx].get(sm, 0)
            if cnt > 0:
                matrix_rows.append({"regex_code": rx, "sm_code": sm, "count": cnt})

    output = {
        "metadata": {
            "total_discrepancies": len(audit_rows),
            "sm_wins": sm_wins,
            "regex_wins": regex_wins,
            "human_needed": human_needed,
            "categories": dict(category_counts.most_common()),
        },
        "discrepancies": audit_rows,
        "matriz_regex_vs_sm": matrix_rows,
        "top_conflict_concepts": [
            {"concept": c, "count": cnt}
            for c, cnt in concept_conflict.most_common(20)
        ],
        "top_conflict_regex": [
            {"regex_code": c, "count": cnt}
            for c, cnt in regex_conflict.most_common(20)
        ],
        "top_conflict_words": [
            {"word": w, "count": cnt}
            for w, cnt in word_conflict.most_common(30)
        ],
        "high_roi_fixes": generate_roi(audit_rows, category_counts),
    }

    with open(OUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    guardar_md(output)
    guardar_xlsx(output, audit_rows)

    print(f"  SM gana:        {sm_wins}")
    print(f"  Regex gana:     {regex_wins}")
    print(f"  Requiere review: {human_needed}")
    print(f"  Categorías:")
    for cat, cnt in category_counts.most_common():
        print(f"    {cat}: {cnt}")
    print(f"  Reportes generados en {REPORT_DIR}")


def generate_roi(audit_rows: list[dict], category_counts: Counter) -> list[dict]:
    """Genera top 20 correcciones de mayor ROI.

    ROI = (número de cuentas afectadas) × (impacto potencial)
    """
    # Agrupar por patrón de problema
    fixes: dict[str, dict] = {}

    for r in audit_rows:
        sm_concept = r["sm_concept"]
        rx_code = r["regex_code"]
        cat = r["category"]

        # Foco: regex que están matcheando cuentas que no deberían
        if cat == "Regex demasiado amplia":
            key = f"regex:{rx_code}:concept:{sm_concept}"
            if key not in fixes:
                fixes[key] = {
                    "fix": f"Ajustar regex {rx_code} para excluir cuentas del concepto {sm_concept}",
                    "type": "regex_adjustment",
                    "count": 0,
                    "avg_score": 0.0,
                    "impact": "ALTO" if rx_code in ("ER.04", "ER.02", "ER.09") else "MEDIO",
                }
            fixes[key]["count"] += 1
            fixes[key]["avg_score"] = (fixes[key]["avg_score"] * (fixes[key]["count"] - 1) + r["sm_score"]) / fixes[key]["count"]

        # Foco: conceptos amplios
        if cat == "Concepto demasiado amplio":
            key = f"wide_concept:{sm_concept}"
            if key not in fixes:
                fixes[key] = {
                    "fix": f"Subdividir concepto {sm_concept} en conceptos más específicos",
                    "type": "catalog_split",
                    "count": 0,
                    "avg_score": 0.0,
                    "impact": "ALTO",
                }
            fixes[key]["count"] += 1

        # Foco: catalog error
        if cat == "Error del catálogo":
            key = f"catalog:{sm_concept}"
            if key not in fixes:
                fixes[key] = {
                    "fix": f"Revisar entrada del catálogo para {sm_concept}",
                    "type": "catalog_fix",
                    "count": 0,
                    "avg_score": 0.0,
                    "impact": "MEDIO",
                }
            fixes[key]["count"] += 1

    result = sorted(fixes.values(), key=lambda x: -x["count"])
    for i, fix in enumerate(result, 1):
        fix["rank"] = i
    return result[:20]


def guardar_md(output: dict):
    m = output["metadata"]
    lines = [
        "# Auditoría de Discrepancias — SemanticMatcher vs RegexFallback\n",
        f"**Date:** 2026-07-22  \n",
        f"**Total discrepancias analizadas:** {m['total_discrepancies']}  \n",
        "---\n",
        "## Resumen\n",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Total discrepancias | {m['total_discrepancies']} |",
        f"| Favorecen a SemanticMatcher | {m['sm_wins']} |",
        f"| Favorecen a Regex | {m['regex_wins']} |",
        f"| Requieren revisión humana | {m['human_needed']} |",
        "",
        "## Distribución por Categoría\n",
        "| Categoría | Cuentas | % |",
        "|---|---|---|",
    ]
    for cat, cnt in sorted(m["categories"].items(), key=lambda x: -x[1]):
        pct = round(cnt / m["total_discrepancies"] * 100, 1)
        lines.append(f"| {cat} | {cnt} | {pct}% |")

    lines += [
        "",
        "## Matriz Regex vs Concepto\n",
        "| Regex Code | SM Code | Count |",
        "|---|---|---|",
    ]
    for row in output["matriz_regex_vs_sm"][:30]:
        lines.append(f"| {row['regex_code']} | {row['sm_code']} | {row['count']} |")

    lines += [
        "",
        "## Top 10 Conceptos Conflictivos\n",
        "| Concepto | Discrepancias |",
        "|---|---|",
    ]
    for tc in output["top_conflict_concepts"][:10]:
        lines.append(f"| {tc['concept']} | {tc['count']} |")

    lines += [
        "",
        "## Top 10 Regex Conflictivas\n",
        "| Regex Code | Discrepancias |",
        "|---|---|",
    ]
    for tr in output["top_conflict_regex"][:10]:
        lines.append(f"| {tr['regex_code']} | {tr['count']} |")

    lines += [
        "",
        "## Top 20 Correcciones de Mayor ROI\n",
        "| # | Corrección | Tipo | Cuentas Afectadas | Impacto |",
        "|---|---|---|---|---|",
    ]
    for fix in output["high_roi_fixes"][:20]:
        lines.append(f"| {fix.get('rank','')} | {fix['fix']} | {fix['type']} | {fix['count']} | {fix['impact']} |")

    lines += [
        "",
        "---\n*Generated by reports/audit_disagreements.py*",
    ]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))


def guardar_xlsx(output: dict, audit_rows: list[dict]):
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        # Resumen
        m = output["metadata"]
        summary = [
            {"Métrica": "Total discrepancias", "Valor": m["total_discrepancies"]},
            {"Métrica": "Favorecen SM", "Valor": m["sm_wins"]},
            {"Métrica": "Favorecen Regex", "Valor": m["regex_wins"]},
            {"Métrica": "Requieren revisión", "Valor": m["human_needed"]},
        ]
        pd.DataFrame(summary).to_excel(writer, sheet_name="Resumen", index=False)

        # Detalle
        cols = ["account_name", "sm_code", "sm_concept", "sm_score", "sm_tier",
                "regex_code", "category", "who_wins", "reason"]
        df = pd.DataFrame([{k: r.get(k, "") for k in cols} for r in audit_rows])
        df.to_excel(writer, sheet_name="Discrepancias", index=False)

        # Matriz
        if output["matriz_regex_vs_sm"]:
            pd.DataFrame(output["matriz_regex_vs_sm"]).to_excel(writer, sheet_name="Matriz Rx vs SM", index=False)

        # Top concepts
        pd.DataFrame(output["top_conflict_concepts"]).to_excel(writer, sheet_name="Top Conceptos", index=False)
        pd.DataFrame(output["top_conflict_regex"]).to_excel(writer, sheet_name="Top Regex", index=False)

        # ROI fixes
        pd.DataFrame(output["high_roi_fixes"]).to_excel(writer, sheet_name="ROI Fixes", index=False)


if __name__ == "__main__":
    run_audit()
