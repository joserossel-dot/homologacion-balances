#!/usr/bin/env python3
"""
Parser Quality Program — Auditoría del motor de extracción (Sprint Q).

Mide la calidad REAL del parser de producción sobre TODO el corpus de PDFs.
SOLO MEDICIÓN: no modifica, no corrige, no optimiza código.

Método por documento:
  1. `ParserPDF().parsear(path)`  — exactamente el parser que usa producción
     (adapters/parser_adapter.py -> ParserPDF.parsear).
  2. `ParserPDF()._extraer_lineas(path)` — las mismas líneas en crudo que usa
     el parser, mapeadas por índice a cada CuentaRaw (para detectores por línea).
  3. Se capturan métricas por documento + detección automática de 8 problemas.

Salidas en reports/parser_quality/:
   - parser_quality_report.md       resumen ejecutivo
   - parser_quality_dataset.csv     una fila por PDF
   - parser_quality_findings.csv    una fila por problema detectado
   - parser_quality_pareto.md       problemas ordenados por impacto

Uso:
   python3 -m parser_quality.audit_parser_quality
   (añadir --limit N para depurar con pocos archivos)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from parser_universal import FormatoCodigo, ParserPDF

OUT_DIR = Path(__file__).resolve().parent  # reports/parser_quality/
DATASETS_ROOT = Path(__file__).resolve().parent.parent.parent / "datasets"

# ─────────────────────────────────────────────────────────────────────────────
# PATRONES DE DETECCIÓN
# ─────────────────────────────────────────────────────────────────────────────

# 1. Header ghosts: cabeceras convertidas en cuenta (sin código real).
_ADMIN_HEADER = re.compile(
    r'^(?:BALANCE\s*(?:GENERAL|CLASIFICADO|TRIBUTARIO|DE\s+COMPROBACION|'
    r'DE\s+SALDO)\s*$'
    r'|(?:AL|A)\s+\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚÑ]+\s+DE\s+\d{4}'
    r'|R\.?U\.?T\s*:'
    r'|\s*(?:RUT|GIRO|DOMICILIO|COMUNA|CIUDAD|TEL|FAX|EMAIL)\s*:'
    r'|(?:SUMAS|SALDOS)\s+(?:SON|IGUALES)\b'
    r'|^(?:ACTIVO|PASIVO|PATRIMONIO|RESULTADO|GANANCIAS|PERDIDAS)\s*$)',
    re.IGNORECASE,
)

# 2. Montos partidos en tokens: "3" + ".864.696.580" en la misma línea.
_SPLIT_MONTO = re.compile(
    r'\b\d{1,5}\s+[.,]\d{1,3}(?:[.,]\d{3})+|\b\d\s+\.\d{3}|\b\d{1,3}\s+\.\d{5,}|\b\d\s[.,]\d\b'
)

# 3. Símbolos residuales en nombres.
_RESIDUAL_IN_NOMBRE = re.compile(r'[\$%#@&]|[\-]{1,}\s*$|\(\s*$|\)\s*$|[\w][\-·]\s*$')

# 4/5. Código en crudo al inicio de línea.
_RAW_CODIGO = re.compile(r'^\s*(\d{4,12}(?:[.\-]\d{1,4}){1,})\s+(?!\d)', re.MULTILINE)
_RAW_COMPACTO = re.compile(r'^\s*(\d{5,10})\s+(?!\d)', re.MULTILINE)
_MULTI_CODIGO = re.compile(r'\b\d{4,10}(?:[.\-]\d{1,4}){1,}\b')

# 7. Señales de OCR mojibake / caracteres raros.
_MOJIBAKE = re.compile(
    r'Ã|Â|â€™|â€|ï¿½|\ufffd|Ã©|Ã±|Ã³|Ã­'
)

_TOTAL_KEYWORD = re.compile(r'\b(total|sumas?|sub-?total|resultado del ejercicio)\b', re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE ETIQUETADO POR LÍNEA EN CRUDO
# ─────────────────────────────────────────────────────────────────────────────

def _es_linea_con_codigo_oculto(raw: str, codigo: Optional[str]) -> bool:
    """La línea en crudo empieza con algo que parece código pero codigo=None."""
    if codigo:
        return False
    t = raw.strip()
    if not t:
        return False
    tok = t.split()[0] if t.split() else ''
    # Código con separador (guión/punto) o compacto con espacio.
    if _RAW_CODIGO.match(raw) or _RAW_COMPACTO.match(raw) or re.match(r'^\d{5,6}\b', tok):
        return True
    # Código compacto concatenado al nombre: "10260BANCO ..." (sin espacio).
    if re.match(r'^\d{4,6}[A-ZÁÉÍÓÚÑ]', tok):
        return True
    return False


def _es_cuenta_fusionada(raw: str, codigo: Optional[str]) -> bool:
    """Más de un código de cuenta en una misma línea en crudo."""
    if not raw:
        return False
    matches = _MULTI_CODIGO.findall(raw)
    if len(matches) >= 2:
        return True
    # caso: código + nombre que contiene otro número de 5-6 dígitos aislado
    return False


def _monto_partido_en_raw(raw: str) -> bool:
    return bool(_SPLIT_MONTO.search(raw))


def _simbolo_residual_en_cuenta(nombre: str) -> bool:
    return bool(_RESIDUAL_IN_NOMBRE.search(nombre or ''))


def _totales_malinterpretados(cuenta: Any, raw: str) -> bool:
    """Totales mal interpretados:
    - línea TOTAL en crudo pero es_total=False (no detectado)
    - es_total=True en cuenta que no es total real (nombre vacío / solo símbolo)
    """
    if cuenta.es_total:
        # es_total=True pero el nombre no calza ningún patrón total
        if not _TOTAL_KEYWORD.search(cuenta.nombre or ''):
            return True
        return False
    # línea en crudo dice TOTAL/SUMAS pero no se marcó como total
    if _TOTAL_KEYWORD.search(raw):
        return True
    return False


def _error_ocr_en_cuenta(cuenta: Any, requirio_ocr: bool) -> bool:
    if not requirio_ocr:
        return False
    # en OCR, confianza reducida + mojibake
    if _MOJIBAKE.search(cuenta.nombre or ''):
        return True
    if cuenta.confianza_extraccion < 0.8 and _MOJIBAKE.search(cuenta.nombre or ''):
        return True
    return False


def _formato_mal_detectado(formato: FormatoCodigo, raw_lines: list[str]) -> bool:
    """Si la mayoría de líneas con código claro son COMPACTO pero el formato
    detectado es SIN_CODIGO u otro, o viceversa."""
    n_guion = n_compacto = n_punto = 0
    for raw in raw_lines[:80]:
        m = _RAW_CODIGO.match(raw)
        if m:
            code = m.group(1)
            if '-' in code and _codigo_es_guion(code):
                n_guion += 1
            elif '.' in code:
                n_punto += 1
            else:
                n_compacto += 1
    total = n_guion + n_punto + n_compacto
    if total < 5:
        return False
    mayoritario = max(
        [('guion', n_guion), ('punto', n_punto), ('compacto', n_compacto)],
        key=lambda x: x[1],
    )[0]
    detectado = formato.value
    return detectado != mayoritario


def _codigo_es_guion(code: str) -> bool:
    return bool(re.match(r'^\d+(?:-\d+){2,6}$', code))


# ─────────────────────────────────────────────────────────────────────────────
# PROCESAMIENTO POR DOCUMENTO
# ─────────────────────────────────────────────────────────────────────────────


def _procesar_pdf(path: Path) -> Optional[dict[str, Any]]:
    parser = ParserPDF()
    t0 = time.perf_counter()
    try:
        ta = time.perf_counter()
        resultado = parser.parsear(path)
        t_parse = time.perf_counter() - ta
        ta = time.perf_counter()
        raw_lines, requirio_ocr, rotacion = parser._extraer_lineas(path)
        t_extraer = time.perf_counter() - ta
        t_total = time.perf_counter() - t0
    except Exception as exc:  # noqa: BLE001 — registrar y seguir
        return {
            "archivo": path.name,
            "grupo": path.parent.name,
            "path": str(path),
            "error": str(exc),
            "tiempo_total_ms": int((time.perf_counter() - t0) * 1000),
        }
    elapsed_ms = int(t_total * 1000)
    elapsed_parse_ms = int(t_parse * 1000)
    elapsed_extraer_ms = int(t_extraer * 1000)

    cuentas = resultado.cuentas
    sig = getattr(resultado.document_context, "signature", None) if resultado.document_context else None
    extractor = resultado.extractor_info or {}

    n_con_codigo = sum(1 for c in cuentas if c.codigo)
    n_con_monto = sum(1 for c in cuentas if c.monto is not None)
    n_totales = sum(1 for c in cuentas if c.es_total)
    n_subtotales = sum(
        1 for c in cuentas
        if c.es_total and re.search(r'sub-?total', c.nombre or '', re.I)
    )
    n_lineas_descartadas = max(0, len(raw_lines) - len(cuentas))

    fila: dict[str, Any] = {
        "archivo": path.name,
        "grupo": path.parent.name,
        "path": str(path),
        "familia_detectada": sig.family.value if sig else "",
        "extractor_utilizado": extractor.get("extractor_id", ""),
        "layout_detectado": sig.layout.value if sig else "",
        "formato_codigo": resultado.formato_codigo.value,
        "ocr_o_texto": "OCR" if requirio_ocr else "texto",
        "rotacion": rotacion,
        "n_cuentas": len(cuentas),
        "cuentas_con_codigo": n_con_codigo,
        "cuentas_sin_codigo": len(cuentas) - n_con_codigo,
        "cuentas_con_monto": n_con_monto,
        "cuentas_sin_monto": len(cuentas) - n_con_monto,
        "subtotales_detectados": n_subtotales,
        "totales_detectados": n_totales,
        "lineas_descartadas": n_lineas_descartadas,
        "tiempo_extraccion_ms": elapsed_ms,
        "tiempo_total_ms": elapsed_ms,
        "tiempo_parse_ms": elapsed_parse_ms,
        "tiempo_extraer_ms": elapsed_extraer_ms,
        "confianza_extractor": extractor.get("confidence", 0.0),
        "confianza_analisis": sig.confidence if sig else 0.0,
        "errores": 0,
        "warnings": len(resultado.advertencias),
        "extractor_fallback": extractor.get("fallback_used", True),
    }

    # ── Detección por línea (mapear CuentaRaw.linea → línea en crudo)
    findings: list[dict[str, Any]] = []
    td = time.perf_counter()
    for c in cuentas:
        raw = raw_lines[c.linea] if 0 <= c.linea < len(raw_lines) else ""
        f_id = None

        if not c.codigo and _es_linea_con_codigo_oculto(raw, c.codigo):
            findings.append({
                "tipo": "CODIGO_PERDIDO", "linea": c.linea,
                "raw": raw.strip()[:160], "nombre": (c.nombre or "")[:80],
                "codigo": c.codigo,
            })
        elif _es_cuenta_fusionada(raw, c.codigo):
            findings.append({
                "tipo": "CUENTA_FUSIONADA", "linea": c.linea,
                "raw": raw.strip()[:160], "nombre": (c.nombre or "")[:80],
                "codigo": c.codigo,
            })

        if _monto_partido_en_raw(raw):
            findings.append({
                "tipo": "MONTO_PARTIDO", "linea": c.linea,
                "raw": raw.strip()[:160], "nombre": (c.nombre or "")[:80],
                "codigo": c.codigo,
            })
        if _simbolo_residual_en_cuenta(c.nombre):
            findings.append({
                "tipo": "SIMBOLO_RESIDUAL", "linea": c.linea,
                "raw": raw.strip()[:160], "nombre": (c.nombre or "")[:80],
                "codigo": c.codigo,
            })
        if not c.codigo and _ADMIN_HEADER.match((c.nombre or "").strip()):
            findings.append({
                "tipo": "HEADER_GHOST", "linea": c.linea,
                "raw": raw.strip()[:160], "nombre": (c.nombre or "")[:80],
                "codigo": c.codigo,
            })
        if _totales_malinterpretados(c, raw):
            findings.append({
                "tipo": "TOTAL_MAL_INTERPRETADO", "linea": c.linea,
                "raw": raw.strip()[:160], "nombre": (c.nombre or "")[:80],
                "codigo": c.codigo,
            })
        if _error_ocr_en_cuenta(c, requirio_ocr):
            findings.append({
                "tipo": "ERROR_OCR", "linea": c.linea,
                "raw": raw.strip()[:160], "nombre": (c.nombre or "")[:80],
                "codigo": c.codigo,
            })

    if _formato_mal_detectado(resultado.formato_codigo, raw_lines):
        findings.append({
            "tipo": "FORMATO_MAL_DETECTADO", "linea": -1,
            "raw": "", "nombre": "", "codigo": "",
        })

    # Dedicado a no contaminar el conteo por línea: dedupe por (tipo,linea)
    uniq = {}
    for f in findings:
        uniq[(f["tipo"], f["linea"])] = f
    fila["n_findings"] = len(uniq)
    for tipo in ("HEADER_GHOST", "MONTO_PARTIDO", "SIMBOLO_RESIDUAL",
                 "CODIGO_PERDIDO", "CUENTA_FUSIONADA", "TOTAL_MAL_INTERPRETADO",
                 "ERROR_OCR", "FORMATO_MAL_DETECTADO"):
        fila[f"n_{tipo.lower()}"] = sum(1 for k in uniq if k[0] == tipo)

    fila["findings"] = list(uniq.values())
    fila["tiempo_detectores_ms"] = int((time.perf_counter() - td) * 1000)
    return fila


# ─────────────────────────────────────────────────────────────────────────────
# REPORTES
# ─────────────────────────────────────────────────────────────────────────────

FINDING_LABELS = {
    "HEADER_GHOST": "Header ghosts",
    "MONTO_PARTIDO": "Montos partidos",
    "SIMBOLO_RESIDUAL": "Símbolos residuales",
    "CODIGO_PERDIDO": "Código perdido",
    "CUENTA_FUSIONADA": "Cuentas fusionadas",
    "TOTAL_MAL_INTERPRETADO": "Totales mal interpretados",
    "ERROR_OCR": "Errores OCR",
    "FORMATO_MAL_DETECTADO": "Formato de código mal detectado",
}


def _write_dataset_csv(rows: list[dict]) -> None:
    cols = [
        "path", "archivo", "grupo", "familia_detectada", "extractor_utilizado",
        "layout_detectado", "formato_codigo", "ocr_o_texto", "rotacion",
        "n_cuentas", "cuentas_con_codigo", "cuentas_sin_codigo",
        "cuentas_con_monto", "cuentas_sin_monto", "subtotales_detectados",
        "totales_detectados", "lineas_descartadas", "tiempo_extraccion_ms", "tiempo_parse_ms",
        "tiempo_extraer_ms", "tiempo_detectores_ms",
        "confianza_extractor", "confianza_analisis", "warnings", "errores",
        "n_findings", "n_header_ghost", "n_monto_partido",
        "n_simbolo_residual", "n_codigo_perdido", "n_cuenta_fusionada",
        "n_total_mal_interpretado", "n_error_ocr",
        "n_formato_mal_detectado",
    ]
    path = OUT_DIR / "parser_quality_dataset.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    print(f"  dataset  -> {path.name} ({len(rows)} filas)")


def _write_findings_csv(all_findings: list[dict]) -> None:
    path = OUT_DIR / "parser_quality_findings.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["archivo", "grupo", "tipo", "linea", "codigo", "nombre", "raw"])
        for fnd in all_findings:
            w.writerow([
                fnd.get("archivo", ""), fnd.get("grupo", ""),
                fnd.get("tipo", ""), fnd.get("linea", ""),
                fnd.get("codigo", ""), fnd.get("nombre", ""),
                fnd.get("raw", ""),
            ])
    print(f"  findings -> {path.name} ({len(all_findings)} filas)")


def _write_pareto(pareto: list[tuple[str, int]]) -> None:
    path = OUT_DIR / "parser_quality_pareto.md"
    total = sum(n for _, n in pareto)
    lines = [
        "# Parser Quality — Pareto de problemas",
        "",
        f"**Total de hallazgos:** {total}",
        "",
        "| Problema | Conteo | % | Acumulado % |",
        "|---|---|---|---|",
    ]
    acum = 0.0
    for label, n in pareto:
        pct = (n / total * 100) if total else 0.0
        acum += pct
        lines.append(f"| {label} | {n} | {pct:.1f}% | {acum:.1f}% |")
    lines.append("")
    lines.append("## Top 10 problemas que explican el 95% de los errores")
    top = []
    acum = 0.0
    for label, n in pareto:
        if acum >= 95.0:
            break
        pct = (n / total * 100) if total else 0.0
        acum += pct
        top.append(f"  - {label} ({n}, {pct:.1f}%) — acumulado {acum:.1f}%")
    lines.extend(top or ["  - (sin datos)"])
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  pareto  -> {path.name}")


def _write_report(rows: list[dict], all_findings: list[dict]) -> None:
    total_docs = len(rows)
    con_error = sum(1 for r in rows if r.get("error"))
    n_cuentas = sum(r.get("n_cuentas", 0) for r in rows)
    n_con_codigo = sum(r.get("cuentas_con_codigo", 0) for r in rows)
    n_con_monto = sum(r.get("cuentas_con_monto", 0) for r in rows)
    ocr_docs = sum(1 for r in rows if r.get("ocr_o_texto") == "OCR")
    total_findings = len(all_findings)

    from collections import Counter
    by_type = Counter(f.get("tipo") for f in all_findings)
    pct_codigo = (n_con_codigo / n_cuentas * 100) if n_cuentas else 0.0
    pct_monto = (n_con_monto / n_cuentas * 100) if n_cuentas else 0.0

    lines = [
        "# Parser Quality Report — Resumen Ejecutivo",
        "",
        f"**Fecha:** {time.strftime('%Y-%m-%d %H:%M')}",
        f"**Documentos analizados:** {total_docs} (errores: {con_error})",
        f"**Documentos vía OCR:** {ocr_docs}",
        "",
        "## Métricas globales de extracción",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Cuentas extraídas | {n_cuentas} |",
        f"| Cuentas con código | {n_con_codigo} ({pct_codigo:.1f}%) |",
        f"| Cuentas con monto | {n_con_monto} ({pct_monto:.1f}%) |",
        f"| Hallazgos de calidad totales | {total_findings} |",
        "",
        "## Hallazgos por tipo",
        "",
        "| Problema | Conteo |",
        "|---|---|",
    ]
    for tipo in sorted(by_type, key=lambda t: -by_type[t]):
        lines.append(f"| {FINDING_LABELS.get(tipo, tipo)} | {by_type[tipo]} |")
    lines.append("")
    lines.append("## Distribución por grupo de dataset")
    lines.append("")
    lines.append("| Grupo | Docs | Cuentas | Hallazgos |")
    lines.append("|---|---|---|---|")
    by_group = {}
    for r in rows:
        g = r.get("grupo", "")
        d = by_group.setdefault(g, {"docs": 0, "cuentas": 0, "findings": 0})
        d["docs"] += 1
        d["cuentas"] += r.get("n_cuentas", 0)
        d["findings"] += r.get("n_findings", 0)
    for g in sorted(by_group):
        d = by_group[g]
        lines.append(f"| {g} | {d['docs']} | {d['cuentas']} | {d['findings']} |")
    lines.append("")

    path = OUT_DIR / "parser_quality_report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  report  -> {path.name}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def _discover_pdfs() -> list[Path]:
    pdfs: list[Path] = []
    for p in DATASETS_ROOT.rglob("*.pdf"):
        if not p.name.startswith("."):
            pdfs.append(p)
    return sorted(pdfs)


def main() -> None:
    ap = argparse.ArgumentParser(description="Parser Quality Program — auditoría")
    ap.add_argument("--limit", type=int, default=0, help="solo los primeros N (debug)")
    ap.add_argument("--resume", action="store_true",
                    help="reanudar desde el último checkpoint sin reprocesar")
    args = ap.parse_args()

    pdfs = _discover_pdfs()
    if args.limit:
        pdfs = pdfs[:args.limit]

    rows, all_findings, done = _load_checkpoint()
    if done:
        print(f"Checkpoint previo: {len(done)} documentos ya procesados.")
    pendientes = [p for p in pdfs if str(p) not in done]
    print(f"Parser Quality Program")
    print(f"Documentos: {len(pdfs)} | pendientes: {len(pendientes)}")
    print("=" * 60)

    t0 = time.perf_counter()
    n_procesados = len(rows)

    for path in pendientes:
        f = _procesar_pdf(path)
        if f is None:
            continue
        if "error" in f and not f.get("archivo"):
            f["archivo"] = path.name
            f["grupo"] = path.parent.name
        n_procesados += 1
        print(
            f"  [{n_procesados}/{len(pdfs)}] {path.name}: "
            f"{f.get('n_cuentas', 'ERR')} cuentas, "
            f"{f.get('n_findings', '-')} hallazgos "
            f"({time.perf_counter()-t0:.1f}s sesión)"
        )
        rows.append(f)
        for fnd in f.get("findings", []):
            fnd.setdefault("archivo", path.name)
            fnd.setdefault("grupo", path.parent.name)
            all_findings.append(fnd)
        if len(rows) % 25 == 0:
            _checkpoint(rows, all_findings)

    _checkpoint(rows, all_findings)
    t_total = time.perf_counter() - t0
    print(f"\nProcesados {len(rows)} documentos en {t_total:.1f}s")
    print(f"Hallazgos: {len(all_findings)}")
    print("Generando reportes...")

    _write_dataset_csv(rows)
    _write_findings_csv(all_findings)
    _write_report(rows, all_findings)

    from collections import Counter
    by_type = Counter(f.get("tipo") for f in all_findings)
    pareto = sorted(by_type.items(), key=lambda x: -x[1])
    _write_pareto(pareto)

    _resumen_final(rows, all_findings, pareto, t_total)


def _resumen_final(rows, all_findings, pareto, t_sesion):
    import statistics

    tiempos = [r.get("tiempo_total_ms", 0) / 1000 for r in rows if r.get("tiempo_total_ms") is not None]
    n_fallos = [r for r in rows if r.get("error")]
    fallas = [r for r in rows if r.get("error")]

    print("\n" + "=" * 60)
    print("RESUMEN FINAL — Parser Quality Program")
    print("=" * 60)
    if tiempos:
        print(f"Tiempo total (sesión): {t_sesion:.1f}s")
        print(f"Tiempo total (suma por doc): {sum(tiempos):.1f}s")
        print(f"Tiempo promedio por PDF: {statistics.mean(tiempos):.1f}s")
        print(f"Tiempo mediano por PDF: {statistics.median(tiempos):.1f}s")
        print(f"PDFs: {len(tiempos)} | fallos: {len(fallas)}")
    else:
        print("Sin datos de tiempo.")

    if tiempos:
        lento = sorted(zip(tiempos, [r.get('archivo', '') for r in rows if r.get('tiempo_total_ms') is not None]), reverse=True)[:20]
        print("\nLos 20 PDFs más lentos:")
        for t, a in lento:
            print(f"  {t:8.1f}s  {a}")

    total = sum(n for _, n in pareto) or 1
    acum = 0.0
    print("\nTop 10 problemas (Pareto):")
    for i, (tipo, n) in enumerate(pareto[:10], start=1):
        acum += n / total * 100
        print(f"  {i}. {FINDING_LABELS.get(tipo, tipo)}: {n} ({acum:.1f}% acumulado)")
    print(f"  → Cobertura acumulada top {min(10, len(pareto))}: {acum:.1f}%")

    if fallas:
        print("\nDocumentos no procesados:")
        for f in fallas:
            print(f"  - {f.get('archivo', '?')}: {f.get('error', '?')}")

    # persiste resumen en el reporte
    _append_resumen_a_report(rows, t_sesion, lento if tiempos else [], pareto, fallas)


def _append_resumen_a_report(rows, t_sesion, lento, pareto, fallas):
    import statistics

    tiempos = [r.get("tiempo_total_ms", 0) / 1000 for r in rows if r.get("tiempo_total_ms") is not None]
    path = OUT_DIR / "parser_quality_report.md"
    sec = ["", "## Resumen de rendimiento", ""]
    if tiempos:
        sec += [
            "| Métrica | Valor |",
            "|---|---|",
            f"| Tiempo total (suma por doc) | {sum(tiempos):.1f}s |",
            f"| Tiempo promedio por PDF | {statistics.mean(tiempos):.1f}s |",
            f"| Tiempo mediano por PDF | {statistics.median(tiempos):.1f}s |",
            f"| PDFs | {len(tiempos)} |",
            f"| Fallos | {len(fallas)} |",
            "", "### 20 PDFs más lentos", "",
            "| Tiempo (s) | Archivo |",
            "|---|---|",
        ]
        for t, a in lento:
            sec.append(f"| {t:.1f} | {a} |")
    if fallas:
        sec += ["", "### Documentos no procesados", ""]
        for f in fallas:
            sec.append(f"- {f.get('archivo', '?')}: {f.get('error', '?')}")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(sec) + "\n")


def _load_checkpoint():
    path = OUT_DIR / "_parser_quality_checkpoint.json"
    if not path.exists():
        return [], [], set()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("rows", [])
    findings = data.get("findings", [])
    done = set()
    for r in rows:
        p = r.get("path")
        if p:
            done.add(p)
    if not findings and rows:
        findings = []
        for r in rows:
            for fnd in r.get("findings", []):
                fnd.setdefault("archivo", r.get("archivo", ""))
                fnd.setdefault("grupo", r.get("grupo", ""))
                findings.append(fnd)
    return rows, findings, done


def _checkpoint(rows: list[dict], all_findings: list[dict]) -> None:
    path = OUT_DIR / "_parser_quality_checkpoint.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "version": 2,
            "rows": rows,
            "findings": all_findings,
        }, f, ensure_ascii=False)


if __name__ == "__main__":
    main()