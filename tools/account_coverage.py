"""account_coverage.py — Reporte de cobertura de la capa de conocimiento (Sprint 37).

Mide qué porcentaje de los nombres de cuenta REALES (gold_standard.db y
variantes observadas en el corpus) quedan cubiertos por cada capa:

  - catálogo maestro (nombre_estandar)
  - sinónimos curados (knowledge_base/account_synonyms.json)
  - reglas especiales (special_account_rules.py)
  - normalizador (claves canónicas)

Un nombre está "cubierto" si al menos una capa lo reconoce (puede asociarlo a
un concepto/código). Esto NO integra el clasificador: solo mide la cobertura de
la base de conocimiento preparada para Sprint 38.

Genera `reports/account_coverage.md` y `reports/account_coverage.json`.

Uso:
    python3 tools/account_coverage.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOGO_PATH = BASE_DIR / "catalogo_maestro.json"
SINONIMOS_PATH = BASE_DIR / "knowledge_base" / "account_synonyms.json"
GOLD_DB = BASE_DIR / "gold_standard.db"
VARIANTES_PATH = BASE_DIR / "reports" / "account_name_variants.json"
REPORTE_PATH = BASE_DIR / "reports" / "account_coverage.md"
JSON_PATH = BASE_DIR / "reports" / "account_coverage.json"

sys.path.insert(0, str(BASE_DIR))
from account_name_normalizer import AccountNameNormalizer  # type: ignore
from special_account_rules import detectar_reglas_especiales  # type: ignore

_normalizador = AccountNameNormalizer()


def _cargar_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _clave(texto: str) -> str:
    return _normalizador.clave(str(texto))


class CapasCobertura:
    """Reconocimiento de un nombre contra las distintas capas de conocimiento."""

    def __init__(self) -> None:
        self.catalogo = _cargar_json(CATALOGO_PATH)
        sinonimos = _cargar_json(SINONIMOS_PATH).get("cuentas", {})
        # claves → códigos
        self.clave_a_catalogo: Dict[str, Set[str]] = defaultdict(set)
        self.clave_a_sinonimos: Dict[str, Set[str]] = defaultdict(set)
        for codigo, entrada in self.catalogo.items():
            self.clave_a_catalogo[_clave(str(entrada.get("nombre_estandar", "")))].add(codigo)
            curado = sinonimos.get(codigo, {})
            for campo in ("sinonimos", "abreviaciones", "errores_ocr",
                          "errores_digitacion", "variantes"):
                for valor in curado.get(campo, []):
                    self.clave_a_sinonimos[_clave(str(valor))].add(codigo)

    def _set_a_codigos(self, m: Dict[str, Set[str]], clave: str) -> Set[str]:
        # match por clave exacta o por clave como subsecuencia (variantes largas)
        out: Set[str] = set()
        for k, cods in m.items():
            if clave == k:
                out |= cods
            elif k and clave and (clave in k or k in clave) and len(k) >= 4:
                out |= cods
        return out

    def cubre(self, nombre: str) -> Dict[str, Any]:
        clave = _clave(nombre)
        cat = self._set_a_codigos(self.clave_a_catalogo, clave)
        sin = self._set_a_codigos(self.clave_a_sinonimos, clave)
        reglas = detectar_reglas_especiales(str(nombre))
        reglas_cods = {r["codigo"] for r in reglas if r.get("codigo")}
        return {
            "clave": clave,
            "catalogo": sorted(cat),
            "sinonimos": sorted(sin),
            "reglas": sorted(reglas_cods),
            "reglas_concepto": [r["concepto"] for r in reglas],
            "cubierto": bool(cat or sin or reglas_cods or reglas),
        }


def _nombres_gold() -> List[str]:
    if not GOLD_DB.exists():
        return []
    con = sqlite3.connect(str(GOLD_DB))
    try:
        rows = con.execute("SELECT nombre_cuenta FROM gold_standard").fetchall()
    finally:
        con.close()
    return [r[0] for r in rows if r[0]]


def _variantes_corpus() -> List[str]:
    """Variantes observadas en el corpus (del caché del scanner)."""
    if not VARIANTES_PATH.exists():
        return []
    cache = _cargar_json(VARIANTES_PATH)
    contador: Counter = Counter()
    for doc, claves in cache.get("por_documento", {}).items():
        for clave in claves:
            contador[clave] += 1
    return [c for c, _ in contador.most_common()]


def analizar() -> Dict[str, Any]:
    capas = CapasCobertura()
    nombres_gold = _nombres_gold()
    variantes = _variantes_corpus()

    resultados_gold: List[Dict[str, Any]] = []
    for nombre in nombres_gold:
        r = capas.cubre(nombre)
        r["nombre"] = nombre
        resultados_gold.append(r)

    # variantes del corpus: usar el recuento del scanner si existe, sino 1
    if VARIANTES_PATH.exists():
        cache = _cargar_json(VARIANTES_PATH)
        frec: Counter = Counter()
        for doc, claves in cache.get("por_documento", {}).items():
            for clave in claves:
                frec[clave] += 1
    else:
        frec = Counter({c: 1 for c in variantes})

    resultados_variantes: List[Dict[str, Any]] = []
    for clave in variantes:
        r = capas.cubre(clave)
        r["nombre"] = clave
        r["frecuencia"] = frec.get(clave, 1)
        resultados_variantes.append(r)

    def _resumen(lista: List[Dict[str, Any]], min_frec: int = 1) -> Dict[str, Any]:
        if min_frec > 1:
            lista = [x for x in lista if x.get("frecuencia", 1) >= min_frec]
        n = len(lista)
        cubiertos = [x for x in lista if x["cubierto"]]
        solo_cat = [x for x in lista if x["catalogo"]]
        solo_sin = [x for x in lista if not x["catalogo"] and x["sinonimos"]]
        solo_reglas = [x for x in lista
                       if not x["catalogo"] and not x["sinonimos"] and x["reglas_concepto"]]
        no_cubiertos = sorted(
            (x for x in lista if not x["cubierto"]),
            key=lambda x: (-x.get("frecuencia", 1), x["nombre"]),
        )
        return {
            "n": n,
            "cubiertos": len(cubiertos),
            "pct_cubierto": round(100 * len(cubiertos) / n, 1) if n else 0.0,
            "solo_catalogo": len(solo_cat),
            "solo_sinonimos": len(solo_sin),
            "solo_reglas": len(solo_reglas),
            "no_cubiertos": [x["nombre"] for x in no_cubiertos[:80]],
        }

    return {
        "generado_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gold_standard": _resumen(resultados_gold),
        "variantes_corpus": _resumen(resultados_variantes, min_frec=3),
        "resultados_gold": resultados_gold,
        "resultados_variantes": resultados_variantes,
        "n_cuentas_catalogo": len(capas.catalogo),
        "n_claves_sinonimos": len(capas.clave_a_sinonimos),
    }


def _tabla_resumen(nombre: str, res: Dict[str, Any], nota: str = "") -> List[str]:
    lineas = [
        f"## {nombre}",
        "",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Nombres evaluados | {res['n']} |",
        f"| Cubiertos (al menos una capa) | {res['cubiertos']} ({res['pct_cubierto']}%) |",
        f"| — solo catálogo | {res['solo_catalogo']} |",
        f"| — catálogo no, sinónimos sí | {res['solo_sinonimos']} |",
        f"| — solo reglas especiales | {res['solo_reglas']} |",
        f"| No cubiertos | {len(res['no_cubiertos'])} |",
        "",
    ]
    if nota:
        lineas.append(f"> {nota}")
        lineas.append("")
    lineas.append("### No cubiertos (top por frecuencia, máx. 80)")
    lineas.append("")
    lineas.extend(["- (ninguno) ✓", ""] if not res["no_cubiertos"]
                  else [f"- {x}" for x in res["no_cubiertos"]] + [""])
    return lineas


def escribir_reporte(datos: Dict[str, Any]) -> None:
    lineas: List[str] = []
    lineas.append("# Cobertura de la Capa de Conocimiento — Sprint 37")
    lineas.append("")
    lineas.append(f"**Generado:** {datos['generado_at']}")
    lineas.append(f"**Cuentas en catálogo:** {datos['n_cuentas_catalogo']}")
    lineas.append(f"**Claves de sinónimos:** {datos['n_claves_sinonimos']}")
    lineas.append("")

    lineas.extend(_tabla_resumen("Cobertura gold_standard.db", datos["gold_standard"]))
    lineas.extend(_tabla_resumen(
        "Cobertura variantes del corpus",
        datos["variantes_corpus"],
        nota="Solo variantes con frecuencia ≥ 3 (el corpus incluye mucho ruido de "
             "layout/OCR; la frecuencia alta indica nombres reales de cuentas).",
    ))

    lineas.append("## Cómo se lee")
    lineas.append("")
    lineas.append("- **Cubierto**: el nombre es reconocido por catálogo, sinónimos y/o "
                  "reglas especiales (se puede asociar a un código/concepto).")
    lineas.append("- Los nombres no cubiertos son candidatos a nuevos sinónimos o a "
                  "nuevas cuentas en Sprint 38.")
    lineas.append("- Este reporte NO integra el clasificador: solo mide la base de "
                  "conocimiento generada en este sprint.")
    lineas.append("")

    REPORTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORTE_PATH.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reporte de cobertura de la capa de conocimiento")
    parser.add_argument("--json", action="store_true", help="Además escribe reports/account_coverage.json")
    args = parser.parse_args()

    datos = analizar()
    escribir_reporte(datos)
    if args.json:
        JSON_PATH.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"OK: {JSON_PATH}")
    print(f"OK: {REPORTE_PATH}")
    g = datos["gold_standard"]
    v = datos["variantes_corpus"]
    print(f"gold_standard: {g['cubiertos']}/{g['n']} cubiertos ({g['pct_cubierto']}%)")
    print(f"variantes corpus: {v['cubiertos']}/{v['n']} cubiertos ({v['pct_cubierto']}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
