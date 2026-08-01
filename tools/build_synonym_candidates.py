"""build_synonym_candidates.py — Descubre variantes reales de nombres de cuentas.

Escanea el corpus (datasets/) extrayendo el texto nativo de cada documento
(PDF vía pdfplumber, XLSX vía openpyxl) y busca líneas que parezcan nombres de
cuentas. Compara cada candidato con el catálogo maestro + sinónimos curados
usando similitud por tokens (Jaccard) y agrupa las variantes por cuenta.

Genera:

  - reports/synonym_candidates.md          (reporte legible)
  - reports/synonym_candidates.json        (candidatos estructurados)
  - reports/account_name_variants.json     (caché: claves por documento)

Los candidatos marcados como `nuevo` NO están en los sinónimos curados y son
candidatos a incorporar en Sprint 38. NO modifica ningún flujo.

Uso:
    python3 tools/build_synonym_candidates.py
    python3 tools/build_synonym_candidates.py --limit 50 --threshold 0.5
    python3 tools/build_synonym_candidates.py --no-cache
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
MINING_PATH = BASE_DIR / "knowledge_base" / "document_mining.json"
CATALOGO_PATH = BASE_DIR / "catalogo_maestro.json"
SINONIMOS_PATH = BASE_DIR / "knowledge_base" / "account_synonyms.json"
CACHE_PATH = BASE_DIR / "reports" / "account_name_variants.json"
REPORTE_PATH = BASE_DIR / "reports" / "synonym_candidates.md"
JSON_PATH = BASE_DIR / "reports" / "synonym_candidates.json"

sys.path.insert(0, str(BASE_DIR))
from account_name_normalizer import AccountNameNormalizer  # type: ignore

_normalizador = AccountNameNormalizer()

# Cabeceras de sección / ruido que no son cuentas
RUIDO = {
    "activo", "activos", "pasivo", "pasivos", "patrimonio", "patrimonio neto",
    "total", "totales", "total activos", "total pasivos", "total patrimonio",
    "total pasivos y patrimonio", "total activos y pasivos", "estado", "estado de",
    "estados", "resultado", "resultados", "balance", "balances", "cuenta",
    "cuentas", "nota", "notas", "circulante", "corriente", "no corriente",
    "no circulante", "deudora", "acreedora", "del ejercicio", "ejercicio",
    "anterior", "anterior.", "hoja", "página", "pagina", "fecha", "firmas",
    "naturaleza", "codigo", "código", "cuenta 1", "cuenta 2", "empresa",
    "empresa:", "empresa ", "rut", "socio", "socios",
}


def _cargar_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Extracción de texto nativo
# ---------------------------------------------------------------------------

def _extraer_lineas(path: Path) -> List[str]:
    suffix = path.suffix.lower()
    lineas: List[str] = []
    if suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    texto = page.extract_text() or ""
                    if texto.strip():
                        lineas.extend(texto.split("\n"))
        except Exception:
            return []
    elif suffix in (".xls", ".xlsx", ".xlsm"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(c) for c in row if c is not None]
                    if cells:
                        lineas.append(" ".join(cells))
            wb.close()
        except Exception:
            return []
    return [l for l in lineas if l.strip()]


def _parte_nombre(linea: str) -> str:
    """Devuelve la porción alfabética de una línea (quita montos y códigos)."""
    tokens = linea.split()
    parte = []
    for tok in tokens:
        limpio = re.sub(r"[\d.,$%-]", "", tok)
        if limpio:
            parte.append(limpio)
    return " ".join(parte)


def _es_nombre_candidato(linea: str) -> bool:
    """Heurística: línea corta con 2-6 tokens alfabéticos, sin montos largos."""
    nombre = _parte_nombre(linea)
    tokens = nombre.split()
    if not (2 <= len(tokens) <= 6):
        return False
    if any(len(t) > 30 for t in tokens):
        return False
    # si la línea tiene una sola "palabra" alfabética no es nombre
    palabras = [t for t in tokens if t.isalpha()]
    if len(palabras) < 2:
        return False
    return True


# Tokens que denotan ruido de footnotes/layout (no son variantes de cuenta)
RUIDO_TOKENS = {
    "nota", "notas", "continuacion", "dichos", "dichas", "siguientes",
    "anexo", "anexos", "incluye", "incluyen", "comprende", "comprenden",
    "corresponde", "corresponden", "referencia", "monto", "montos",
    "reint", "sotcod", "mas", "con", "sin", "según", "segun", "total",
}
MESES = {"enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"}


def _es_variante_valida(clave: str) -> bool:
    """Descarta claves con ruido evidente (letras sueltas, repeticiones, etc.)."""
    tokens = clave.split()
    if not tokens:
        return False
    # letras sueltas (p. ej. "g", "i", "f") suelen ser índices de notas
    if any(len(t) == 1 for t in tokens):
        return False
    # artefactos de layout con todos los tokens idénticos (p. ej. "m m", "caja caja")
    if len(set(tokens)) == 1:
        return False
    if any(t in RUIDO_TOKENS for t in tokens):
        return False
    if any(t in MESES for t in tokens):
        return False
    return True


# ---------------------------------------------------------------------------
# Candidatos por documento
# ---------------------------------------------------------------------------

def _procesar_documento(path: Path) -> List[str]:
    """Líneas candidatas de un documento, con time-out de seguridad."""
    claves: List[str] = []
    lineas: List[str] = []

    import signal

    def _handler(signum, frame):  # noqa: ARG001
        raise TimeoutError(f"timeout extrayendo {path.name}")

    viejo = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(8)  # 8 s máx por documento
    try:
        lineas = _extraer_lineas(path)
        for linea in lineas:
            if not _es_nombre_candidato(linea):
                continue
            nombre = _parte_nombre(linea)
            clave = _normalizador.clave(nombre)
            if clave and clave not in RUIDO and _es_variante_valida(clave):
                claves.append(clave)
    except TimeoutError:
        pass
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, viejo)
    return claves


def extraer_candidatos(datasets_dir: Path, files: List[str],
                       limite: Optional[int] = None,
                       usar_cache: bool = True) -> Dict[str, Any]:
    """Extrae claves candidatas por documento (con caché incremental en disco)."""
    por_documento: Dict[str, List[str]] = {}
    errores: List[str] = []
    procesados = 0

    if usar_cache and CACHE_PATH.exists():
        try:
            cache = _cargar_json(CACHE_PATH)
            por_documento = cache.get("por_documento", {})
            procesados = int(cache.get("files_procesados", 0))
            errores = cache.get("errores", [])
        except Exception:
            pass

    def _guardar() -> None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "datasets_dir": str(datasets_dir),
            "files_procesados": procesados,
            "errores": errores,
            "por_documento": por_documento,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    for rel in files:
        if rel in por_documento:
            continue
        path = datasets_dir / rel
        if not path.exists():
            continue
        if limite and procesados >= limite:
            break
        claves = _procesar_documento(path)
        por_documento[rel] = claves
        procesados += 1
        if procesados % 50 == 0:
            _guardar()

    _guardar()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "datasets_dir": str(datasets_dir),
        "files_procesados": procesados,
        "errores": errores,
        "por_documento": por_documento,
    }


# ---------------------------------------------------------------------------
# Matching con el catálogo
# ---------------------------------------------------------------------------

def _tokens(clave: str) -> Set[str]:
    return set(clave.split())


def _jaccard(a: Set[str], b: Set[str]) -> float:
    inter = a & b
    union = a | b
    return len(inter) / len(union) if union else 0.0


def construir_anclas() -> Dict[str, Set[str]]:
    """Claves de referencia por cuenta (nombre oficial + sinónimos curados)."""
    catalogo = _cargar_json(CATALOGO_PATH)
    sinonimos = _cargar_json(SINONIMOS_PATH).get("cuentas", {})
    anclas: Dict[str, Set[str]] = {}
    for codigo, entrada in catalogo.items():
        claves: Set[str] = set()
        claves.add(_normalizador.clave(str(entrada.get("nombre_estandar", ""))))
        curado = sinonimos.get(codigo, {})
        for campo in ("sinonimos", "abreviaciones", "errores_ocr",
                      "errores_digitacion", "variantes"):
            for valor in curado.get(campo, []):
                claves.add(_normalizador.clave(str(valor)))
        anclas[codigo] = claves
    return anclas


def _mejor_match(clave: str, anclas: Dict[str, Set[str]],
                 threshold: float) -> Optional[Tuple[str, float]]:
    """Devuelve (codigo, similitud) del mejor match de `clave` en el catálogo."""
    tcand = _tokens(clave)
    mejor: Optional[Tuple[str, float]] = None
    for codigo, anclas_cuenta in anclas.items():
        for a in anclas_cuenta:
            ta = _tokens(a)
            sim = _jaccard(tcand, ta)
            if mejor is None or sim > mejor[1]:
                mejor = (codigo, sim)
    if mejor and mejor[1] >= threshold:
        return mejor
    return None


# ---------------------------------------------------------------------------
# Análisis y reporte
# ---------------------------------------------------------------------------

def analizar(data: Dict[str, Any], threshold: float) -> Dict[str, Any]:
    anclas = construir_anclas()
    catalogo = _cargar_json(CATALOGO_PATH)
    sinonimos = _cargar_json(SINONIMOS_PATH).get("cuentas", {})

    # (codigo, clave) -> conteo + ejemplos
    freqs: Counter = Counter()
    ejemplos: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    no_match: Counter = Counter()
    no_match_ejemplos: Dict[str, List[str]] = defaultdict(list)

    for rel, claves in data["por_documento"].items():
        for clave in claves:
            match = _mejor_match(clave, anclas, threshold)
            if match is None:
                no_match[clave] += 1
                if len(no_match_ejemplos[clave]) < 5:
                    no_match_ejemplos[clave].append(rel)
                continue
            codigo, _sim = match
            freqs[(codigo, clave)] += 1
            if len(ejemplos[(codigo, clave)]) < 5:
                ejemplos[(codigo, clave)].append(rel)

    # Agrupar por cuenta
    por_cuenta: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for (codigo, clave), n in freqs.most_common():
        curado = sinonimos.get(codigo, {})
        anclas_cuenta = anclas[codigo]
        ya_cubierto = clave in anclas_cuenta
        por_cuenta[codigo].append({
            "variante": clave,
            "frecuencia": n,
            "cubierto": ya_cubierto,
            "ejemplos": ejemplos[(codigo, clave)],
        })

    # ordenar por frecuencia
    for codigo in por_cuenta:
        por_cuenta[codigo].sort(key=lambda v: (-v["frecuencia"], v["variante"]))

    return {
        "generated_at": data["generated_at"],
        "files_procesados": data["files_procesados"],
        "threshold": threshold,
        "por_cuenta": {c: v for c, v in sorted(por_cuenta.items())},
        "sin_match": [
            {"variante": k, "frecuencia": v, "ejemplos": no_match_ejemplos[k][:5]}
            for k, v in no_match.most_common(40)
        ],
    }


def escribir_reporte(datos: Dict[str, Any]) -> None:
    catalogo = _cargar_json(CATALOGO_PATH)
    lineas: List[str] = []
    lineas.append("# Candidatos a Sinónimos — Sprint 37")
    lineas.append("")
    lineas.append(f"**Generado:** {datos['generated_at']}")
    lineas.append(f"**Documentos procesados:** {datos['files_procesados']}")
    lineas.append(f"**Umbral de similitud:** {datos['threshold']}")
    lineas.append("")

    total_variantes = sum(len(v) for v in datos["por_cuenta"].values())
    total_nuevas = sum(
        sum(1 for v in vars if not v["cubierto"]) for vars in datos["por_cuenta"].values()
    )
    lineas.append("## Resumen")
    lineas.append("")
    lineas.append(f"| Métrica | Valor |")
    lineas.append(f"|---------|-------|")
    lineas.append(f"| Cuentas con variantes detectadas | {len(datos['por_cuenta'])} |")
    lineas.append(f"| Variantes totales | {total_variantes} |")
    lineas.append(f"| Variantes NO cubiertas (candidatas) | {total_nuevas} |")
    lineas.append("")

    for codigo, variantes in datos["por_cuenta"].items():
        nombre = catalogo.get(codigo, {}).get("nombre_estandar", codigo)
        nuevas = [v for v in variantes if not v["cubierto"]]
        lineas.append(f"## {codigo} — {nombre}")
        lineas.append("")
        lineas.append("| Variante | Frec. | Estado | Ejemplos |")
        lineas.append("|----------|-------|--------|----------|")
        for v in variantes[:20]:
            estado = "✅ curado" if v["cubierto"] else "🆕 candidato"
            ejemplo = (v["ejemplos"][0] if v["ejemplos"] else "")[:60]
            lineas.append(
                f"| {v['variante']} | {v['frecuencia']} | {estado} | {ejemplo} |"
            )
        if nuevas:
            lineas.append("")
            lineas.append(
                f"*{len(nuevas)} variante(s) no curada(s): "
                f"{', '.join(v['variante'] for v in nuevas[:8])}*"
            )
        lineas.append("")

    if datos["sin_match"]:
        lineas.append("## Sin match con el catálogo (Top 40)")
        lineas.append("")
        lineas.append("| Variante | Frec. |")
        lineas.append("|----------|-------|")
        for v in datos["sin_match"]:
            lineas.append(f"| {v['variante']} | {v['frecuencia']} |")
        lineas.append("")

    REPORTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORTE_PATH.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Descubre sinónimos reales del corpus")
    parser.add_argument("--limit", type=int, default=None,
                        help="Procesar solo N documentos (para pruebas rápidas)")
    parser.add_argument("--threshold", type=float, default=0.55,
                        help="Umbral Jaccard para asignar un candidato a una cuenta")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignorar/regenerar la caché de variantes por documento")
    args = parser.parse_args()

    mining = _cargar_json(MINING_PATH)
    datasets_dir = Path(mining["datasets_dir"])
    files = [f for fam in mining.get("families", []) for f in fam.get("files", [])]
    # dedupe conservando orden
    vistos: Set[str] = set()
    files_unicos = []
    for f in files:
        if f not in vistos:
            vistos.add(f)
            files_unicos.append(f)
    files = files_unicos

    # si se limita el procesamiento, muestrear de forma espaciada para cubrir
    # distintas familias en vez de quedarse en los primeros (muchos sin texto)
    if args.limit and args.limit < len(files):
        stride = max(1, len(files) // args.limit)
        files = files[::stride][:args.limit]

    data = extraer_candidatos(datasets_dir, files, limite=args.limit,
                              usar_cache=not args.no_cache)
    datos = analizar(data, threshold=args.threshold)

    escribir_reporte(datos)
    JSON_PATH.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    print(f"OK: {REPORTE_PATH}")
    print(f"OK: {JSON_PATH}")
    print(f"Documentos: {data['files_procesados']}")
    print(f"Cuentas con variantes: {len(datos['por_cuenta'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
