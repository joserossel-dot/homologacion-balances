"""audit_account_catalog.py — Auditoría del catálogo maestro de cuentas (Sprint 37).

Detecta problemas estructurales en `catalogo_maestro.json` y en la capa de
sinónimos (`knowledge_base/account_synonyms.json`):

  - duplicados (mismo nombre_estandar normalizado)
  - equivalentes (sinónimos que se solapan entre cuentas distintas)
  - demasiado genéricos (nombres de 1 token, "Otros", etc.)
  - sin uso conocido (no aparecen en gold_standard ni en reglas especiales)
  - códigos del gold_standard ausentes del catálogo
  - inconsistencias de categoría / grupo_presentacion / naturaleza
  - campos faltantes

Genera `reports/catalog_audit.md`. NO modifica el catálogo ni ningún flujo.

Uso:
    python3 tools/audit_account_catalog.py
    python3 tools/audit_account_catalog.py --json   # también escribe reports/catalog_audit.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOGO_PATH = BASE_DIR / "catalogo_maestro.json"
SINONIMOS_PATH = BASE_DIR / "knowledge_base" / "account_synonyms.json"
GOLD_DB = BASE_DIR / "gold_standard.db"
REPORTE_PATH = BASE_DIR / "reports" / "catalog_audit.md"
JSON_PATH = BASE_DIR / "reports" / "catalog_audit.json"

CATEGORIAS_VALIDAS = {
    "activo_corriente", "activo_no_corriente",
    "pasivo_corriente", "pasivo_no_corriente",
    "patrimonio", "resultado",
}
NATURALEZAS_VALIDAS = {"deudora", "acreedora"}
GRUPOS_VALIDOS = {"Activos", "Pasivos", "Patrimonio", "Ingresos",
                  "Costos", "Gastos", "Otros ingresos", "Otros egresos"}

# Palabras clave que denotan cuentas demasiado genéricas
GENERICOS = {"otros", "varias", "varios", "otras", "total"}


def _cargar_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode(
        "ascii", "ignore"
    ).decode("ascii").lower().strip()


def _cargar_gold(codes_validos: Set[str]) -> Dict[str, Any]:
    """Cuentas del gold_standard.db usadas para detectar códigos no cubiertos."""
    if not GOLD_DB.exists():
        return {"ok": False, "codigos_ausentes": [], "n_records": 0}
    con = sqlite3.connect(str(GOLD_DB))
    try:
        rows = con.execute("SELECT DISTINCT codigo_estandar FROM gold_standard").fetchall()
    finally:
        con.close()
    codigos = {r[0] for r in rows if r[0]}
    ausentes = sorted(codigos - codes_validos)
    return {"ok": True, "codigos_ausentes": ausentes, "n_records": len(codigos)}


def _cargar_reglas() -> Dict[str, int]:
    """Códigos referenciados por las reglas especiales (especiales → catálogo)."""
    sys.path.insert(0, str(BASE_DIR))
    try:
        from special_account_rules import RULES  # type: ignore
    except Exception:
        return {}
    return Counter(r.get("codigo") for r in RULES if r.get("codigo"))


def _mismatch_grupo_categoria(categoria: str, grupo: str) -> bool:
    esperado = {
        "activo_corriente": "Activos",
        "activo_no_corriente": "Activos",
        "pasivo_corriente": "Pasivos",
        "pasivo_no_corriente": "Pasivos",
        "patrimonio": "Patrimonio",
    }
    return grupo != esperado.get(categoria)


def auditar() -> Dict[str, Any]:
    catalogo = _cargar_json(CATALOGO_PATH)
    sinonimos = _cargar_json(SINONIMOS_PATH).get("cuentas", {})
    reglas = _cargar_reglas()

    duplicados: List[Dict[str, Any]] = []
    campos_faltantes: List[Dict[str, Any]] = []
    categorias_invalidas: List[str] = []
    naturalezas_invalidas: List[str] = []
    grupos_invalidos: List[str] = []
    genericos: List[Dict[str, Any]] = []
    inconsistencias_categoria_grupo: List[str] = []
    claves_sin_sinonimos: List[str] = []

    nombre_a_codigo: Dict[str, List[str]] = defaultdict(list)
    synonyms_por_codigo: Dict[str, Set[str]] = {}

    for codigo, entrada in catalogo.items():
        # duplicados por nombre normalizado
        nombre = _norm(str(entrada.get("nombre_estandar", "")))
        if nombre:
            nombre_a_codigo[nombre].append(codigo)

        # campos faltantes
        faltan = [k for k in ("codigo_estandar", "nombre_estandar", "categoria",
                              "naturaleza", "signo_normal") if not entrada.get(k)]
        if faltan:
            campos_faltantes.append({"codigo": codigo, "faltantes": faltan})

        # categoría inválida
        if entrada.get("categoria") not in CATEGORIAS_VALIDAS:
            categorias_invalidas.append(codigo)

        # naturaleza inválida
        if entrada.get("naturaleza") not in NATURALEZAS_VALIDAS:
            naturalezas_invalidas.append(codigo)

        # grupo inválido
        grupo = entrada.get("grupo_presentacion")
        if grupo and grupo not in GRUPOS_VALIDOS:
            grupos_invalidos.append(codigo)

        # inconsistencia categoria vs grupo
        if _mismatch_grupo_categoria(str(entrada.get("categoria")), str(grupo or "")):
            inconsistencias_categoria_grupo.append(codigo)

        # nombres demasiado genéricos (1 token o palabra clave)
        tokens = _norm(str(entrada.get("nombre_estandar", ""))).split()
        if len(tokens) <= 1 or (tokens and tokens[0] in GENERICOS):
            genericos.append({"codigo": codigo, "nombre": entrada.get("nombre_estandar")})

        # sin sinónimos curados
        curado = sinonimos.get(codigo)
        if curado and not any(curado.get(k) for k in ("sinonimos", "abreviaciones",
                                                      "errores_ocr", "errores_digitacion",
                                                      "variantes")):
            claves_sin_sinonimos.append(codigo)

        # sinónimos por código (todas las claves de texto)
        if curado:
            claves_texto: Set[str] = set()
            for campo in ("sinonimos", "abreviaciones", "errores_ocr",
                          "errores_digitacion", "variantes"):
                for valor in curado.get(campo, []):
                    claves_texto.add(_norm(str(valor)))
            claves_texto.add(_norm(str(entrada.get("nombre_estandar", ""))))
            synonyms_por_codigo[codigo] = claves_texto

    duplicados = [{"nombre": n, "codigos": c} for n, c in sorted(nombre_a_codigo.items())
                  if len(c) > 1]

    # solapamiento de sinónimos entre pares de cuentas distintas
    equivalentes: List[Dict[str, Any]] = []
    codigos = sorted(synonyms_por_codigo)
    for i, a in enumerate(codigos):
        for b in codigos[i + 1:]:
            comunes = synonyms_por_codigo[a] & synonyms_por_codigo[b]
            if len(comunes) >= 2:
                equivalentes.append({
                    "a": a, "b": b, "comunes": sorted(comunes),
                    "nombre_a": catalogo[a].get("nombre_estandar"),
                    "nombre_b": catalogo[b].get("nombre_estandar"),
                })

    # códigos sin uso conocido (ni gold_standard ni reglas especiales ni tests)
    gold = _cargar_gold(set(catalogo.keys()))
    usados = set(gold.get("codigos_usados", []))
    if gold.get("ok"):
        con = sqlite3.connect(str(GOLD_DB))
        try:
            usados = {r[0] for r in con.execute(
                "SELECT DISTINCT codigo_estandar FROM gold_standard").fetchall()
                if r[0]}
        finally:
            con.close()
    usados |= set(reglas.keys())
    # códigos de cálculo (clasificable:false) se usan como cuentas de cálculo
    calculo = {c for c, e in catalogo.items() if e.get("clasificable") is False}
    sin_uso = sorted(set(catalogo.keys()) - usados - calculo)
    sin_uso_info = [
        {"codigo": c, "nombre": catalogo[c].get("nombre_estandar"),
         "regla_especial": c in reglas, "en_gold": c in usados}
        for c in sin_uso
    ]

    resultado = {
        "generado_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_cuentas": len(catalogo),
        "duplicados": duplicados,
        "equivalentes": equivalentes,
        "genericos": genericos,
        "campos_faltantes": campos_faltantes,
        "categorias_invalidas": categorias_invalidas,
        "naturalezas_invalidas": naturalezas_invalidas,
        "grupos_invalidos": grupos_invalidos,
        "inconsistencias_categoria_grupo": inconsistencias_categoria_grupo,
        "claves_sin_sinonimos": claves_sin_sinonimos,
        "sin_uso": sin_uso_info,
        "gold": {
            "ok": gold.get("ok"),
            "n_records": gold.get("n_records", 0),
            "codigos_gold_ausentes_catalogo": gold.get("codigos_ausentes", []),
        },
        "reglas_especiales": {
            "n_reglas": sum(reglas.values()),
            "codigos_con_regla": sorted(reglas.keys()),
        },
    }
    return resultado


def escribir_reporte(datos: Dict[str, Any]) -> None:
    lineas: List[str] = []
    lineas.append("# Auditoría del Catálogo Maestro — Sprint 37")
    lineas.append("")
    lineas.append(f"**Generado:** {datos['generado_at']}")
    lineas.append(f"**Cuentas en catálogo:** {datos['n_cuentas']}")
    lineas.append("")

    def seccion(titulo: str, items: List[Any], encabezado: str) -> None:
        lineas.append(f"## {titulo}")
        lineas.append("")
        if not items:
            lineas.append("Sin hallazgos. ✓")
            lineas.append("")
            return
        if encabezado:
            lineas.append(f"| {encabezado} |")
            lineas.append(f"|{'-' * (len(encabezado) + 2)}|")
        for item in items:
            lineas.append(f"| {item} |")
        lineas.append("")

    # Duplicados
    items = []
    for d in datos["duplicados"]:
        items.append(f"{d['nombre']} → {', '.join(d['codigos'])}")
    seccion("Duplicados (mismo nombre_estandar)", items, "Detalle")

    # Equivalentes
    items = []
    for e in datos["equivalentes"]:
        items.append(
            f"{e['a']} ({e['nombre_a']}) ↔ {e['b']} ({e['nombre_b']}) "
            f"— comparten {len(e['comunes'])} sinónimos: {', '.join(e['comunes'][:6])}"
        )
    seccion("Equivalentes (solapamiento de sinónimos)", items, "Par de cuentas")

    # Genéricos
    items = []
    for g in datos["genericos"]:
        items.append(f"{g['codigo']} — «{g['nombre']}»")
    seccion("Cuentas demasiado genéricas", items, "Código")

    # Campos faltantes
    items = []
    for f in datos["campos_faltantes"]:
        items.append(f"{f['codigo']}: faltan {', '.join(f['faltantes'])}")
    seccion("Campos faltantes", items, "Código")

    # Categorías / naturalezas / grupos inválidos
    items = [f"categorías: {', '.join(datos['categorias_invalidas']) or '—'}",
             f"naturalezas: {', '.join(datos['naturalezas_invalidas']) or '—'}",
             f"grupos: {', '.join(datos['grupos_invalidos']) or '—'}"]
    seccion("Categorías / naturalezas / grupos inválidos", items, "Tipo")

    # Inconsistencias categoría vs grupo
    items = []
    for c in datos["inconsistencias_categoria_grupo"]:
        items.append(c)
    seccion("Inconsistencia categoría ↔ grupo_presentacion", items, "Código")

    # Sin sinónimos
    items = [f"{c}" for c in datos["claves_sin_sinonimos"]]
    seccion("Cuentas sin sinónimos curados", items, "Código")

    # Sin uso conocido
    items = []
    for s in datos["sin_uso"]:
        items.append(
            f"{s['codigo']} — «{s['nombre']}» "
            f"(gold: {'sí' if s['en_gold'] else 'no'}, regla: {'sí' if s['regla_especial'] else 'no'})"
        )
    seccion("Cuentas sin uso conocido (ni gold_standard ni reglas)", items, "Código")

    # Gold_standard ausentes
    items = [f"{c}" for c in datos["gold"]["codigos_gold_ausentes_catalogo"]]
    seccion(
        "Códigos del gold_standard ausentes del catálogo",
        items,
        "Código",
    )

    REPORTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORTE_PATH.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoría del catálogo maestro")
    parser.add_argument("--json", action="store_true",
                        help="Además del reporte, escribe reports/catalog_audit.json")
    args = parser.parse_args()

    datos = auditar()
    escribir_reporte(datos)
    if args.json:
        JSON_PATH.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"OK: {JSON_PATH}")
    print(f"OK: {REPORTE_PATH}")
    print(f"Duplicados: {len(datos['duplicados'])} | "
          f"Equivalentes: {len(datos['equivalentes'])} | "
          f"Genéricos: {len(datos['genericos'])} | "
          f"Sin uso: {len(datos['sin_uso'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
