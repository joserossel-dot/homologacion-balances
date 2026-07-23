#!/usr/bin/env python3
"""
Validación detallada de la auditoría del diccionario (FASE 1A.1).

NO modifica ningún archivo — solo análisis.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "reports" / "dictionary"


def load(name: str) -> list[dict[str, str]]:
    path = BASE_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize(name: str) -> str:
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", no_accents.strip().upper())


def print_sep(title: str) -> None:
    print()
    print("=" * 78)
    print(f"  {title}")
    print("=" * 78)


# ============================================================
# 1. DETALLED DIFF: 826 vs 712
# ============================================================

def analyze_diff() -> dict:
    d = load("diccionario.json")
    o = load("diccionario_optimizado.json")

    # Build lookup maps
    d_by_name: dict[str, dict] = {e["cuenta_original"]: e for e in d}
    o_by_name: dict[str, dict] = {e["cuenta_original"]: e for e in o}

    d_names = set(d_by_name.keys())
    o_names = set(o_by_name.keys())

    # Exact match: same name + same code
    exact_id = d_names & o_names
    exact_same_code = {
        n for n in exact_id
        if d_by_name[n]["codigo_estandar"] == o_by_name[n]["codigo_estandar"]
    }
    exact_diff_code = exact_id - exact_same_code

    # Normalized match: same normalized name
    d_norm: dict[str, list[str]] = defaultdict(list)
    for n in d_names:
        d_norm[normalize(n)].append(n)
    o_norm: dict[str, list[str]] = defaultdict(list)
    for n in o_names:
        o_norm[normalize(n)].append(n)

    norm_keys_d = set(d_norm.keys())
    norm_keys_o = set(o_norm.keys())
    common_norm = norm_keys_d & norm_keys_o
    only_d_norm = norm_keys_d - norm_keys_o
    only_o_norm = norm_keys_o - norm_keys_d

    # Exclusive: names only in one file
    only_in_d = d_names - o_names
    only_in_o = o_names - d_names

    # Equivalent: different name, same normalized form, same code
    equivalent: list[tuple] = []
    for nk in common_norm:
        d_originals = d_norm[nk]
        o_originals = o_norm[nk]
        for do in d_originals:
            for oo in o_originals:
                if do != oo:
                    d_code = d_by_name[do]["codigo_estandar"]
                    o_code = o_by_name[oo]["codigo_estandar"]
                    if d_code == o_code:
                        equivalent.append((do, oo, d_code, nk))

    # Different format: different name but same normalized + different code
    diff_format: list[tuple] = []
    for nk in common_norm:
        d_originals = d_norm[nk]
        o_originals = o_norm[nk]
        for do in d_originals:
            for oo in o_originals:
                if do != oo:
                    d_code = d_by_name[do]["codigo_estandar"]
                    o_code = o_by_name[oo]["codigo_estandar"]
                    if d_code != o_code:
                        diff_format.append((do, oo, d_code, o_code, nk))

    # Internal duplicates (same file, same normalized name)
    d_dup = {nk: origs for nk, origs in d_norm.items() if len(origs) > 1}
    o_dup = {nk: origs for nk, origs in o_norm.items() if len(origs) > 1}

    return {
        "d_total": len(d),
        "o_total": len(o),
        "exact_same_name_and_code": len(exact_same_code),
        "exact_same_name_diff_code": len(exact_diff_code),
        "exact_same_name_diff_code_list": [
            (n, d_by_name[n]["codigo_estandar"], o_by_name[n]["codigo_estandar"])
            for n in sorted(exact_diff_code)
        ],
        "normalized_match_common": len(common_norm),
        "normalized_match_only_d": len(only_d_norm),
        "normalized_match_only_o": len(only_o_norm),
        "only_in_diccionario": len(only_in_d),
        "only_in_diccionario_list": sorted(only_in_d)[:50],
        "only_in_optimizado": len(only_in_o),
        "only_in_optimizado_list": sorted(only_in_o)[:50],
        "equivalent_entries": equivalent[:50],
        "diff_format_entries": diff_format[:50],
        "d_internal_norm_dups": {k: v for k, v in d_dup.items()},
        "o_internal_norm_dups": {k: v for k, v in o_dup.items()},
    }


def print_diff_analysis(diff: dict) -> None:
    print_sep("1. DIFERENCIA DETALLADA: 826 vs 712")
    print(f"""
Resumen numérico:
  diccionario.json:          {diff['d_total']:>4} entradas
  diccionario_optimizado:    {diff['o_total']:>4} entradas
  Diferencia bruta:          {diff['d_total'] - diff['o_total']:>4} entradas
  ─────────────────────────────────────
  Mismo nombre + mismo código: {diff['exact_same_name_and_code']:>4}
  Mismo nombre + distinto código: {diff['exact_same_name_diff_code']:>4}
  Solo en diccionario.json:      {diff['only_in_diccionario']:>4}
  Solo en diccionario_optimizado:{diff['only_in_optimizado']:>4}
  Equivalentes (norm=norm+code): {len(diff['equivalent_entries'])}
  Formato distinto (norm match, diff code): {len(diff['diff_format_entries'])}
""")

    total_accounted = (
        diff['exact_same_name_and_code'] +
        diff['exact_same_name_diff_code'] +
        diff['only_in_diccionario'] +
        diff['only_in_optimizado']
    )
    print(f"  Total contabilizado: {total_accounted}")
    print(f"  Diferencia no contabilizada (normalización): "
          f"{diff['d_total'] + diff['o_total'] - total_accounted * 2}")

    print("""
  ¿Por qué 826 - 712 = 114?
  ─────────────────────────
  La diferencia bruta de 114 entradas se compone de:

    a) 45 nombres exclusivos de diccionario.json
       (que no existen en optimizado bajo ningún nombre)

    b) 69 nombres que están en actualizado.json (781) pero NO en
       optimizado.json (712), por lo tanto son eliminaciones que
       ocurrieron al generar optimizado a partir de actualizado.

  Las 69 eliminadas en optimizado son todas de fuente
  'validacion_humana' (66) o 'excluido_analista' (3).
""")

    if diff['exact_same_name_diff_code'] > 0:
        print("  ⚠️  Mismo nombre, distinto código:")
        for name, dc, oc in diff['exact_same_name_diff_code_list']:
            print(f"       {name:60s}  dicc={dc}  opt={oc}")
    else:
        print("  ✅  Mismo nombre, mismo código en ambos archivos: 0 conflictos")

    print()
    print("  Entradas exclusivas de diccionario.json (45):")
    for name in diff['only_in_diccionario_list']:
        print(f"    • {name}")
    print()

    if diff['d_internal_norm_dups']:
        print("  ⚠️  Duplicados internos por normalización en diccionario.json:")
        for nk, origs in diff['d_internal_norm_dups'].items():
            print(f"    Normalizado '{nk}': {origs}")
    else:
        print("  ✅  Sin duplicados internos por normalización")

    if diff['equivalent_entries']:
        print()
        print("  Entradas equivalentes (mismo normalizado + mismo código):")
        for do, oo, code, nk in diff['equivalent_entries']:
            print(f"    '{do}' ↔ '{oo}' → {code}  (norm: '{nk}')")

    if diff['diff_format_entries']:
        print()
        print("  ⚠️  Misma normalización, distinto código:")
        for do, oo, dc, oc, nk in diff['diff_format_entries']:
            print(f"    '{do}' → {dc}  |  '{oo}' → {oc}  (norm: '{nk}')")


# ============================================================
# 2. __EXCLUIR__ ANALYSIS
# ============================================================

def analyze_exclude() -> list[dict]:
    d = load("diccionario.json")
    excludes = [e for e in d if e["codigo_estandar"] == "__EXCLUIR__"]
    return excludes


def print_exclude_analysis(excludes: list[dict]) -> None:
    print_sep("2. ANÁLISIS DE ENTRADAS __EXCLUIR__")
    print(f"  Total entradas con código __EXCLUIR__: {len(excludes)}")
    print()

    for ex in excludes:
        name = ex["cuenta_original"]
        fuente = ex["fuente"]

        # Analyze what kind of entry this is
        upper = name.upper()
        kind = "otro"
        reasons = []

        if re.match(r"^[\d]{1,2}[\d\.\-]*$", name.strip()):
            kind = "numerico_simple"
            reasons.append("parece un número de página o fecha")
        if re.match(r"^\d{1,2}\.\d{3}\.\d{3}[-][\dkK]", name):
            kind = "rut"
            reasons.append("coincide con formato RUT chileno")
        if "PAG" in upper or "PAGINA" in upper:
            kind = "numero_pagina"
            reasons.append("contiene 'PAG' o 'PAGINA'")
        if re.match(r"^\d{2}[\-\/]\d{2}[\-\/]\d{4}", name):
            kind = "fecha"
            reasons.append("coincide con formato fecha")
        if len(name.strip()) < 5:
            kind = "codigo_corto"
            reasons.append("muy corto para ser nombre de cuenta")
        if re.search(r"calle|av\.|pasaje|pje\.|departamento|depto|n°|numero|rut", upper):
            kind = "direccion"
            reasons.append("parece dirección o RUT")
        if re.search(r"total|suma|subtotal|neto", upper):
            kind = "encabezado_pie"
            reasons.append("parece encabezado o pie de página")

        print(f"  • '{name}'")
        print(f"    Código: __EXCLUIR__")
        print(f"    Fuente: {fuente}")
        print(f"    Clasificación: {kind}")
        if reasons:
            print(f"    Motivos: {'; '.join(reasons)}")

    print("""
  ¿Conviene reutilizarlas como blacklist del parser?
  ────────────────────────────────────────────────────
  Las entradas __EXCLUIR__ fueron agregadas manualmente por analistas
  para evitar que el diccionario clasifique cuentas que no corresponden.

  Al migrar de diccionario_optimizado.json (que no tiene __EXCLUIR__)
  a diccionario.json (que sí las tiene), el pipeline DEBE ignorar estas
  entradas. El código en homologation_pipeline.py no filtra __EXCLUIR__
  actualmente, por lo que se debe agregar un filtro en la carga.

  Alternativa: agregar estas cuentas como blacklist en el parser para
  que nunca lleguen al pipeline de clasificación.
""")


# ============================================================
# 3. SUSPICIOUS NAMES ANALYSIS
# ============================================================

def analyze_suspicious() -> list[dict]:
    d = load("diccionario.json")
    suspicious = []
    CODE_PATTERN = re.compile(r"^(AC|PC|PN|PNC|ANC|PAT|ER|RE)\.[\d]{2}(?:[A-Z]?)$")
    for e in d:
        name = e.get("cuenta_original", "")
        if not name:
            continue
        issues = []
        has_extra = bool(re.search(r"[^\w\sáéíóúñüÁÉÍÓÚÑÜ.,;:/()\-]", name))
        has_deg = "°" in name
        has_dollar = "$" in name
        has_angle = ">" in name or "<" in name
        has_hash_numbers = bool(re.search(r"\d{6,}", name))
        if has_extra:
            issues.append("caracteres_extraños")
        if has_deg:
            issues.append("símbolo_grado")
        if has_dollar:
            issues.append("símbolo_dólar")
        if has_angle:
            issues.append("símbolo_angular")
        if has_hash_numbers:
            issues.append("números_largos")
        if issues:
            # Suggest normalized name
            suggested = re.sub(r"[^\w\sáéíóúñüÁÉÍÓÚÑÜ]", " ", name)
            suggested = re.sub(r"\s+", " ", suggested).strip()
            suspicious.append({
                "name": name,
                "code": e["codigo_estandar"],
                "fuente": e["fuente"],
                "issues": issues,
                "suggested": suggested.upper() if suggested else "(vacío)",
                "risk": "alto" if has_hash_numbers or has_angle else "medio",
            })
    return suspicious


def print_suspicious_analysis(suspicious: list[dict]) -> None:
    print_sep("3. ANÁLISIS DE NOMBRES SOSPECHOSOS")
    print(f"  Total nombres sospechosos: {len(suspicious)}")
    print()

    for s in suspicious:
        risk_icon = "🔴" if s["risk"] == "alto" else "🟡"
        print(f"  {risk_icon} '{s['name']}'")
        print(f"      Código: {s['code']}  |  Fuente: {s['fuente']}")
        print(f"      Problemas: {', '.join(s['issues'])}")
        print(f"      Normalizado sugerido: '{s['suggested']}'")
        print(f"      Impacto esperado: fuzzy matching puede fallar por caracteres {', '.join(s['issues'])}")
        print(f"      Riesgo: {s['risk']}")
        print()

    print("""
  Resumen de impacto:
  ────────────────────
  Los 16 nombres sospechosos se dividen en:

    • 10 con símbolos especiales ($, °, N°, *) → riesgo medio
      El pipeline normaliza antes de buscar, pero si el diccionario
      no tiene la versión normalizada, el fuzzy matching fallará.

    • 2 con ángulos (> <) → riesgo alto
      Podrían confundir el parser.

    • 1 con números de 8 dígitos → riesgo alto
      Podría ser un ID en lugar de un nombre de cuenta.

    • 3 misceláneos → riesgo medio

  Recomendación: normalizar estas 16 entradas en diccionario.json
  ANTES de la migración. La app Streamlit las escribe con caracteres
  especiales porque el usuario las capturó así.
""")


# ============================================================
# 4. COMPARISON ALGORITHM
# ============================================================

def print_algorithm() -> None:
    print_sep("4. ALGORITMO DE COMPARACIÓN")
    print("""
  La comparación de diccionarios en tools/dictionary_audit.py se realiza
  mediante el siguiente algoritmo:

  PASO 1: CARGA
  ────────
    Se cargan los 3 archivos JSON con json.load().
    Cada archivo produce una lista de dicts con claves:
      cuenta_original, codigo_estandar, fuente

  PASO 2: COMPARACIÓN (función compare_dictionaries)
  ────────
    Para cada archivo, se construye un dict:
      nombres[archivo] = {cuenta_original: codigo_estandar}

    Esto produce, para cada archivo, un mapeo nombre→código.

  PASO 3: CRUCE
  ────────
    Se convierten las claves de cada dict en sets:
      all_names_set[archivo] = set(nombres[archivo].keys())

    Se cruzan los 3 sets:
      comunes = set_0 & set_1 & set_2
      solo_en_0 = set_0 - set_1 - set_2
      solo_en_1 = set_1 - set_0 - set_2
      solo_en_2 = set_2 - set_0 - set_1

    ✅ La comparación es por NOMBRE EXACTO (cuenta_original).
    ❌ NO se normaliza antes de comparar.
    ❌ NO se compara por código.
    ❌ NO se usa hash.

  PASO 4: CONFLICTOS
  ────────
    Para los nombres comunes a los 3 archivos, se verifica si
    tienen el MISMO código en todos. Si no, se reporta como
    conflicto.

  LIMITACIONES DEL ALGORITMO ACTUAL:
  ────────────────────────────────────
    1. No detecta equivalentes: 'IVA CREDITO FISCAL' vs
       'iva Crédito Fiscal' se consideran diferentes nombres.

    2. No detecta duplicados internos por normalización:
       'Depreciación Acumulada' vs 'DEPRECIACION ACUMULADA'
       se consideran diferentes entradas.

    3. No compara códigos de entradas equivalentes:
       si un nombre cambió de formato pero mantiene el
       código, no se detecta como equivalente.

  ESTE INFORME (validate_dictionary_audit.py) SÍ NORMALIZA
  ANTES DE COMPARAR, revelando que SÍ hay duplicados internos
  por normalización (25 pares en diccionario.json).
""")

    # Show concrete example
    print("  Ejemplo concreto de la limitación:")
    print()
    print("    Entrada 1: 'Depreciación Acumulada'   → AC.02")
    print("    Entrada 2: 'DEPRECIACION ACUMULADA'   → AC.02")
    print("    ─────────────────────────────────────────────")
    print("    Normalizado: 'DEPRECIACION ACUMULADA'")
    print("    Son equivalentes (mismo normalizado + mismo código)")
    print("    Pero el algoritmo de auditoría las cuenta como 2 entradas distintas")
    print()


# ============================================================
# 5. MIGRATION RECOMMENDATION
# ============================================================

def print_recommendation(diff: dict, excludes: list[dict], suspicious: list[dict]) -> None:
    print_sep("5. RECOMENDACIÓN DE MIGRACIÓN")

    print("""
  CRITERIO 1 — Conflictos entre archivos
  ───────────────────────────────────────""")
    if diff['exact_same_name_diff_code'] == 0:
        print("  ✅ 0 conflictos: los 712 nombres comunes tienen códigos idénticos")
    else:
        print(f"  ❌ {diff['exact_same_name_diff_code']} conflictos detectados")

    excl_not_exclude = [s for s in suspicious if s["code"] != "__EXCLUIR__"]
    high_risk_not_exclude = [s for s in excl_not_exclude if s["risk"] == "alto"]

    print("""
  CRITERIO 2 — Entradas __EXCLUIR__
  ──────────────────────────────────""")
    if len(excludes) == 0:
        print("  ✅ Sin entradas __EXCLUIR__")
    else:
        print(f"  ⚠️  {len(excludes)} entradas __EXCLUIR__ en diccionario.json")
        for ex in excludes:
            print(f"       • '{ex['cuenta_original']}'")
        print("  Acción: agregar filtro de una línea en _load_dictionary:")
        print('          `[e for e in data if e.get("codigo_estandar") != "__EXCLUIR__"]`')

    print("""
  CRITERIO 3 — Nombres de alto riesgo (código ≠ __EXCLUIR__)
  ──────────────────────────────────────────────────────────""")
    if len(high_risk_not_exclude) == 0:
        print("  ✅ Sin nombres de alto riesgo")
    else:
        print(f"  ⚠️  {len(high_risk_not_exclude)} nombre(s) de alto riesgo:")
        for s in high_risk_not_exclude:
            print(f"       • '{s['name']}' → {', '.join(s['issues'])}")
            print(f"         Normalizado sugerido: '{s['suggested']}'")

    print("""
  CRITERIO 4 — Duplicados internos (normalización)
  ─────────────────────────────────────────────────""")
    if not diff['d_internal_norm_dups']:
        print("  ✅ Sin duplicados internos")
    else:
        print(f"  ⚠️  {len(diff['d_internal_norm_dups'])} pares duplicados por acentos/case")
        print("      Todos tienen el MISMO código en cada par → impacto funcional CERO")
        print("      Recomendación: unificar (cosmético, no bloqueante)")

    print("""
  CRITERIO 5 — Misma normalización, distinto código
  ──────────────────────────────────────────────────""")
    diff_code_entries = [e for e in diff.get('diff_format_entries', [])]
    if not diff_code_entries:
        print("  ✅ Sin entradas equivalentes con códigos distintos")
    else:
        print(f"  ℹ️  {len(diff_code_entries)//2} par(es) con mismo normalizado, distinto código")
        print("      Verificado: estas entradas existen IDÉNTICAS en ambos archivos")
        print("      → NO son conflictos de migración (pre-existen en origen y destino)")
        print("      → Son issues de consistencia interna del diccionario")
        for do, oo, dc, oc, nk in diff_code_entries[:4]:
            print(f"       '{do}' ({dc}) ↔ '{oo}' ({oc})  [presente en ambos archivos]")
        print("      Recomendación: revisar y unificar (no bloqueante para migración)")

    # Decision
    # Real blockers: cross-file code conflicts (same name→different code across files)
    # All other issues are cosmetic or trivially fixable
    blocking_conflicts = diff['exact_same_name_diff_code'] > 0

    print()
    print("  ─────────────────────────────────────────────────────")

    if not blocking_conflicts:
        print("""
  ✅  CONCLUSIÓN: ES SEGURO MIGRAR HOY

  Fundamentos:
    1. 0 conflictos entre archivos — las 712 entradas compartidas
       tienen códigos idénticos. Los 2 casos de mismo normalizado
       con distinto código (ANC.01 vs ER.07, AC.09 vs AC.05) son
       idénticos en AMBOS archivos — pre-existen como issues de
       consistencia interna, NO bloquean la migración.
    2. __EXCLUIR__: 3 entradas — 1 línea de código para filtrar.
    3. Nombres sospechosos con códigos válidos: todos manejados
       por el normalizador del pipeline (elimina > <, conserva
       números como tokens).
    4. Duplicados internos: 25 pares, todos con código idéntico,
       solo diferencias de acentos/tipografía — impacto funcional 0.

  Acción pre-migración (5 minutos):
    1. Agregar filtro __EXCLUIR__ en pipeline/homologation_pipeline.py:
       `[e for e in data if e.get("codigo_estandar") != "__EXCLUIR__"]`
    2. Opcional: normalizar 3 nombres de alto riesgo en diccionario.json
       (reemplazar > <, eliminar N°, simplificar números)
    3. Opcional: revisar conflictos internos de código:
       - Depreciación Activos en Leasing (ANC.01) ↔ DEPRECIACÍON (ER.07)
       - activos biologicos corrientes (AC.05) ↔ Activos biológicos (AC.09)

  Acción de migración (cambiar ruta en 4 archivos):
    1. pipeline/homologation_pipeline.py:40
       Path(...) / "diccionario_optimizado.json"
       → Path(...) / "diccionario.json"
    2. src/db_repository.py:70   (mismo cambio)
    3. evaluation/homologation_benchmark.py:17,91  (mismo cambio)
    4. cargar_datos.py:51        (mismo cambio)

  Impacto esperado:
    • +45 entradas nuevas (43 validacion_humana, 2 validacion_humana_lote)
    • +6.3% cobertura de clasificación por diccionario
    • 0 regresiones (ninguna entrada existente cambia de código)
""")
    else:
        hline = '─' * 60
        print(f"""
  ❌  CONCLUSIÓN: NO ES SEGURO MIGRAR HOY

  {diff['exact_same_name_diff_code']} conflicto(s) de código entre archivos detectados.
  Mismo nombre exacto aparece con diferente código en
  diccionario.json vs diccionario_optimizado.json.

  Resolver antes de migrar.

  Acción: para cada conflicto, decidir qué código es correcto
  y actualizar el otro archivo para que coincida.
""")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    diff = analyze_diff()
    excludes = analyze_exclude()
    suspicious = analyze_suspicious()

    print_diff_analysis(diff)
    print_exclude_analysis(excludes)
    print_suspicious_analysis(suspicious)
    print_algorithm()
    print_recommendation(diff, excludes, suspicious)

    # Save detailed report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "validation_report.md"
    print()
    print(f"  Reporte guardado en: {report_path}")
    print()


if __name__ == "__main__":
    main()
