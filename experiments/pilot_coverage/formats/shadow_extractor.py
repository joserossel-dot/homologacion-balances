"""
experiments/pilot_coverage/formats/shadow_extractor.py

Ejecutor experimental en modo sombra sobre documentos contables (Encargo A8).
Ejecuta concurrentemente y de forma no invasiva:
- E1: Extractor productivo vigente (ParserPDF / parser_universal.py).
- E2: Separador histórico (DoubleColumnExtractor / double_column.py).
- E3: Separador experimental endurecido (ExperimentalDoubleColumnExtractor).

Garantías de privacidad, aislamiento y rigor contable:
1. Cero rutas absolutas o nombres privados en código versionable.
2. Carga de rutas mediante manifiesto local gitignorado o argumentos CLI.
3. Identificador pseudonimizado determinista cerrado (hash truncado de contenido completo).
   Se rechaza cualquier texto libre arbitrario recibido en manifiestos.
4. Comparación contable exhaustiva multiconjunto (Counter) que preserva multiplicidad,
   períodos (pares periodo-monto), signos, orígenes contables y controles/subtotales.
5. Tratamiento del Orden: El orden se registra como telemetría diagnóstica (orden_distinto);
   no altera por sí solo la concordancia contable si todas las partidas son idénticas.
6. Selección real de subconjuntos de páginas sobre E1 y E3, omitiendo controladamente E2.
7. Cero importaciones a nivel superior de módulos productivos (importación diferida).
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import logging
import os
import pathlib
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("experiments.pilot_coverage.formats.shadow_extractor")

# Patrón cerrado de identificadores técnicos válidos (whitelist)
VALID_DOC_ID_REGEX = re.compile(r"^SHADOW-DOC-(?:\d{2}-)?[a-f0-9]{12}$")


def sanitizar_mensaje_privacidad(texto: str) -> str:
    """
    Elimina rutas del sistema de archivos local, nombres de archivo, nombres de usuario,
    RUTs y cualquier dato confidencial de mensajes técnicos de error o advertencia.
    """
    if not texto:
        return ""
    t = str(texto)
    # Rutas Windows (C:\... o D:\...)
    t = re.sub(r'[A-Za-z]:\\[^:\s\n,]+', '[REDACTED_PATH]', t)
    # Rutas Unix o directorios de usuario
    t = re.sub(r'/(?:Users|home)/[^/\s\n,]+(?:/[^\s\n,:]+)*', '[REDACTED_PATH]', t)
    # Nombres de archivos con extensión documental o de datos
    t = re.sub(r'[\w\-\.]+\.(?:pdf|xlsx|xls|json)', '[REDACTED_FILE]', t, flags=re.IGNORECASE)
    # RUTs chilenos y números de identificación
    t = re.sub(r'\b\d{1,2}(?:\.\d{3}){2}-[\dkK]\b|\b\d{7,8}-[\dkK]\b', '[REDACTED_RUT]', t)
    return t


def anonimizar_id_documento(ruta_pdf: pathlib.Path, indice: Optional[int] = None) -> str:
    """
    Genera un identificador pseudonimizado determinista (hash truncado de contenido)
    calculando SHA-256 en bloques de 64 KB sobre la totalidad del archivo binario.

    Nota de Trazabilidad: Un hash truncado es un identificador técnico determinista que
    puede presentar colisiones teóricas y no constituye una anonimización legal irreversible.
    """
    idx_str = f"{indice:02d}-" if indice is not None else ""
    try:
        if not ruta_pdf.exists():
            return f"SHADOW-DOC-{idx_str}NOTFOUND"
        hasher = hashlib.sha256()
        with open(ruta_pdf, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                hasher.update(chunk)
        h = hasher.hexdigest()[:12]
        return f"SHADOW-DOC-{idx_str}{h}"
    except Exception:
        return f"SHADOW-DOC-{idx_str}UNREADABLE"


def resolver_doc_id_seguro(
    ruta_pdf: pathlib.Path,
    id_candidato: Optional[str] = None,
    indice: Optional[int] = None,
) -> str:
    """
    Resuelve un identificador documental seguro.
    Si id_candidato cumple estrictamente con el formato técnico permitido
    ('SHADOW-DOC-[0-9]{2}-[a-f0-9]{12}' o 'SHADOW-DOC-[a-f0-9]{12}'), se admite.
    De lo contrario, se descarta todo texto libre recibido del manifiesto y se
    genera internamente el hash SHA-256 del contenido binario del archivo.
    Para archivos inexistentes, produce un identificador técnico genérico sin filtrar rutas.
    """
    idx_str = f"{indice:02d}-" if indice is not None else ""
    if not ruta_pdf.exists():
        return f"SHADOW-DOC-{idx_str}NOTFOUND"

    if id_candidato and isinstance(id_candidato, str) and VALID_DOC_ID_REGEX.match(id_candidato.strip()):
        return id_candidato.strip()

    return anonimizar_id_documento(ruta_pdf, indice=indice)


def _normalizar_fila(c: Any, idx: int) -> Dict[str, Any]:
    """Normaliza una fila contable para comparación multiconjunto y posicional."""
    nombre_raw = getattr(c, "nombre", None) or (c.get("nombre") if isinstance(c, dict) else "")
    nombre_norm = " ".join((nombre_raw or "").lower().split())

    codigo_raw = getattr(c, "codigo", None) or (c.get("codigo") if isinstance(c, dict) else "")
    codigo_norm = (codigo_raw or "").strip()

    monto_raw = getattr(c, "monto", None) if hasattr(c, "monto") else (c.get("monto") if isinstance(c, dict) else None)
    monto_val = float(monto_raw) if monto_raw is not None else None

    es_total_raw = getattr(c, "es_total", False) if hasattr(c, "es_total") else (c.get("es_total", False) if isinstance(c, dict) else False)
    es_total = bool(es_total_raw)

    origen_col_raw = getattr(c, "origen_columna", "activo") if hasattr(c, "origen_columna") else (c.get("origen_columna", "activo") if isinstance(c, dict) else "activo")
    origen_col = str(origen_col_raw.value if hasattr(origen_col_raw, "value") else origen_col_raw)

    montos_periodos_raw = getattr(c, "montos_periodos", {}) if hasattr(c, "montos_periodos") else (c.get("periodos", {}) if isinstance(c, dict) else {})
    periodos_dict = {
        str(k): float(v) for k, v in (montos_periodos_raw or {}).items() if v is not None
    }
    periodos_tupla = tuple(sorted((str(k), float(v)) for k, v in periodos_dict.items()))
    periodo_claves = tuple(sorted(periodos_dict.keys()))

    signo = -1 if (monto_val is not None and monto_val < 0) else (1 if (monto_val is not None and monto_val > 0) else 0)

    return {
        "posicion": idx,
        "codigo": codigo_norm,
        "nombre_norm": nombre_norm,
        "monto": monto_val,
        "es_total": es_total,
        "origen_columna": origen_col,
        "periodos": periodos_dict,
        "periodos_tupla": periodos_tupla,
        "periodo_claves": periodo_claves,
        "signo": signo,
    }


def _extraer_tuplas_cuentas(cuentas: List[Any]) -> List[Dict[str, Any]]:
    """Convierte lista de CuentaRaw a lista normalizada preservando orden."""
    return [_normalizar_fila(c, idx) for idx, c in enumerate(cuentas)]


def _extraer_lineas_paginas_pdf(ruta_pdf: pathlib.Path, paginas: List[int]) -> Optional[List[str]]:
    """Extrae líneas de texto nativo exclusivamente para las páginas seleccionadas (1-indexed)."""
    import pdfplumber
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            paginas_set = set(paginas)
            lineas: List[str] = []
            for idx, page in enumerate(pdf.pages, 1):
                if idx in paginas_set:
                    txt = page.extract_text() or ""
                    for linea in txt.split("\n"):
                        if linea.strip():
                            lineas.append(linea.strip())
            return lineas if lineas else None
    except Exception:
        return None


def comparar_extracciones(
    filas_e1: List[Dict[str, Any]],
    filas_e3: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compara dos extracciones mediante multiconjuntos (Counter) y análisis de secuencias,
    garantizando no colapsar filas duplicadas, verificar pares periodo-monto, signos,
    orígenes contables, orden y subtotales.
    """
    # 1. Separar cuentas de detalle vs controles/totales
    detalles_e1 = [f for f in filas_e1 if not f["es_total"]]
    detalles_e3 = [f for f in filas_e3 if not f["es_total"]]

    controles_e1 = [f for f in filas_e1 if f["es_total"]]
    controles_e3 = [f for f in filas_e3 if f["es_total"]]

    # 2. Multiconjunto para cuentas de detalle (llave completa: código, nombre, monto, períodos (k,v), signo, origen)
    def llave_detalle(f: Dict[str, Any]) -> Tuple:
        return (
            f["codigo"],
            f["nombre_norm"],
            f["monto"],
            f["periodos_tupla"],
            f["signo"],
            f["origen_columna"],
        )

    counter_e1 = Counter(llave_detalle(f) for f in detalles_e1)
    counter_e3 = Counter(llave_detalle(f) for f in detalles_e3)

    filas_iguales = sum((counter_e1 & counter_e3).values())
    filas_solo_e1 = sum((counter_e1 - counter_e3).values())
    filas_solo_e3 = sum((counter_e3 - counter_e1).values())

    # 3. Comparación de Controles / Subtotales (por código, nombre, monto, períodos (k,v) y signo)
    def llave_control(f: Dict[str, Any]) -> Tuple:
        return (
            f["codigo"],
            f["nombre_norm"],
            f["monto"],
            f["periodos_tupla"],
            f["signo"],
        )

    counter_ctrl_e1 = Counter(llave_control(f) for f in controles_e1)
    counter_ctrl_e3 = Counter(llave_control(f) for f in controles_e3)

    controles_coincidentes = sum((counter_ctrl_e1 & counter_ctrl_e3).values())
    controles_distintos = sum((counter_ctrl_e1 - counter_ctrl_e3).values()) + sum((counter_ctrl_e3 - counter_ctrl_e1).values())

    # 4. Diferencias de importes, signos, períodos, orígenes y orden
    importes_distintos = 0
    signos_distintos = 0
    periodos_distintos = 0
    origenes_distintos = 0
    orden_distinto = 0

    map_e1: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for f in detalles_e1:
        k = (f["codigo"], f["nombre_norm"])
        map_e1.setdefault(k, []).append(f)

    map_e3: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for f in detalles_e3:
        k = (f["codigo"], f["nombre_norm"])
        map_e3.setdefault(k, []).append(f)

    for k, lista_e3 in map_e3.items():
        if k in map_e1:
            lista_e1 = map_e1[k]
            for f3, f1 in zip(lista_e3, lista_e1):
                if f3["monto"] != f1["monto"]:
                    importes_distintos += 1
                if f3["signo"] != f1["signo"] and f3["monto"] is not None and f1["monto"] is not None:
                    signos_distintos += 1
                if f3["periodos_tupla"] != f1["periodos_tupla"]:
                    periodos_distintos += 1
                if f3["origen_columna"] != f1["origen_columna"]:
                    origenes_distintos += 1

    # Detección de orden distinto para pares concordantes
    for i, f1 in enumerate(detalles_e1):
        for j, f3 in enumerate(detalles_e3):
            if llave_detalle(f1) == llave_detalle(f3):
                if f1["posicion"] != f3["posicion"]:
                    orden_distinto += 1
                break

    n_det_e1 = len(detalles_e1)
    n_det_e3 = len(detalles_e3)

    return {
        "filas_iguales": filas_iguales,
        "filas_solo_e1": filas_solo_e1,
        "filas_solo_e3": filas_solo_e3,
        "importes_distintos": importes_distintos,
        "signos_distintos": signos_distintos,
        "periodos_distintos": periodos_distintos,
        "origenes_distintos": origenes_distintos,
        "orden_distinto": orden_distinto,
        "controles_coincidentes": controles_coincidentes,
        "controles_distintos": controles_distintos,
        "n_detalles_e1": n_det_e1,
        "n_detalles_e3": n_det_e3,
        "n_controles_e1": len(controles_e1),
        "n_controles_e3": len(controles_e3),
    }


def ejecutar_modo_sombra_documento(
    ruta_pdf: pathlib.Path,
    paginas: Optional[List[int]] = None,
    doc_id: Optional[str] = None,
    indice: Optional[int] = None,
    temp_output_dir: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    """
    Ejecuta la extracción en modo sombra comparando E1, E2 y E3 sobre un PDF.
    Aislamiento garantizado: no modifica bases de datos ni emite resultados a producción.
    """
    warnings: List[str] = []
    id_seguro = resolver_doc_id_seguro(ruta_pdf, id_candidato=doc_id, indice=indice)

    if not ruta_pdf.exists():
        return {
            "doc_id": id_seguro,
            "error": "Archivo no encontrado",
            "clasificacion": "Fallo técnico",
            "warnings": [f"[FILE_NOT_FOUND] Documento {id_seguro} no existe"],
        }

    # Importaciones diferidas protegidas
    from parser_universal import ParserPDF, ExtractionContext, CuentaRaw
    from document_intelligence.extractors.double_column import DoubleColumnExtractor
    from experiments.pilot_coverage.formats.experimental_double_column import (
        ExperimentalDoubleColumnExtractor,
    )

    # 1. Extractor Productivo Vigente (E1)
    t0 = time.perf_counter()
    e1_error = None
    cuentas_e1: List[CuentaRaw] = []
    try:
        if paginas is not None:
            lineas_pags = _extraer_lineas_paginas_pdf(ruta_pdf, paginas)
            lineas_presplit = lineas_pags if lineas_pags else ["[EMPTY_PAGE]"]
            ctx = ExtractionContext(lineas_presplit=lineas_presplit)
            res_e1 = ParserPDF().parsear(ruta_pdf, ctx)
        else:
            res_e1 = ParserPDF().parsear(ruta_pdf)
        if hasattr(res_e1, "cuentas") and isinstance(res_e1.cuentas, list):
            cuentas_e1 = res_e1.cuentas
        elif isinstance(res_e1, list):
            cuentas_e1 = res_e1
        else:
            cuentas_e1 = []
        t_e1_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as exc:
        e1_error = sanitizar_mensaje_privacidad(str(exc))
        t_e1_ms = int((time.perf_counter() - t0) * 1000)
        warnings.append(f"[E1_EXCEPTION] Error en extractor productivo: {e1_error}")

    # 2. Separador Histórico (E2)
    # DoubleColumnExtractor no soporta paginas de forma nativa. Cuando se solicitan páginas específicas,
    # se omite E2 controladamente para no comparar un documento completo contra un subconjunto.
    t_e2_ms = 0
    res_e2 = None
    fb_e2 = None
    n_e2 = None
    if paginas is not None:
        warnings.append("[E2_OMITIDO] Separador histórico no soporta selección parcial de páginas")
    else:
        t0 = time.perf_counter()
        try:
            res_e2 = DoubleColumnExtractor().extract(ruta_pdf)
            t_e2_ms = int((time.perf_counter() - t0) * 1000)
            fb_e2 = res_e2.fallback_used if res_e2 else True
            n_e2 = len(res_e2.result.cuentas) if (res_e2 and res_e2.result and hasattr(res_e2.result, "cuentas")) else (len(res_e2.result) if (res_e2 and isinstance(res_e2.result, list)) else 0)
        except Exception as exc:
            e2_error = sanitizar_mensaje_privacidad(str(exc))
            t_e2_ms = int((time.perf_counter() - t0) * 1000)
            warnings.append(f"[E2_EXCEPTION] Error en separador histórico: {e2_error}")

    # 3. Separador Experimental Endurecido (E3)
    t0 = time.perf_counter()
    e3_error = None
    res_e3 = None
    try:
        res_e3 = ExperimentalDoubleColumnExtractor().extract(ruta_pdf, paginas=paginas)
        t_e3_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as exc:
        e3_error = sanitizar_mensaje_privacidad(str(exc))
        t_e3_ms = int((time.perf_counter() - t0) * 1000)
        warnings.append(f"[E3_EXCEPTION] Error en separador experimental: {e3_error}")

    # Procesar resultados
    n_e1 = len(cuentas_e1)
    cuentas_e3_obj = res_e3.result.cuentas if (res_e3 and res_e3.result and hasattr(res_e3.result, "cuentas")) else (res_e3.result if (res_e3 and isinstance(res_e3.result, list)) else [])
    n_e3 = len(cuentas_e3_obj)
    fb_e3 = res_e3.fallback_used if res_e3 else True

    # Comparación rigurosa multiconjunto
    filas_e1_norm = _extraer_tuplas_cuentas(cuentas_e1)
    filas_e3_norm = _extraer_tuplas_cuentas(cuentas_e3_obj)
    comp = comparar_extracciones(filas_e1_norm, filas_e3_norm)

    # Decisión contable explícita de clasificación:
    # La equivalencia contable se evalúa mediante multiconjunto de partidas.
    # 'orden_distinto' se registra como telemetría diagnóstica pero no altera por sí solo la concordancia.
    hay_diferencias_contables = (
        comp["filas_solo_e1"] > 0
        or comp["filas_solo_e3"] > 0
        or comp["importes_distintos"] > 0
        or comp["signos_distintos"] > 0
        or comp["periodos_distintos"] > 0
        or comp["origenes_distintos"] > 0
        or comp["controles_distintos"] > 0
        or n_e1 != n_e3
    )

    if e1_error or e3_error:
        clasificacion = "Fallo técnico"
    elif n_e1 == 0 and n_e3 == 0:
        clasificacion = "No evaluable"
    elif hay_diferencias_contables or (not fb_e3 and n_e3 != n_e1):
        clasificacion = "Diferente, requiere revisión"
    elif not hay_diferencias_contables:
        clasificacion = "Concordante"
    else:
        clasificacion = "Diferente, requiere revisión"

    tiempo_relativo = round(t_e3_ms / max(1, t_e1_ms), 2)

    resultado_agregado = {
        "doc_id": id_seguro,
        "existe": True,
        "paginas_evaluadas": paginas if paginas is not None else "todas",
        "e1_cuentas": n_e1,
        "e2_cuentas": n_e2,
        "e2_fallback": fb_e2,
        "e3_cuentas": n_e3,
        "e3_activado": not fb_e3,
        "e3_fallback": fb_e3,
        "delta_cuentas_e3_vs_e1": n_e3 - n_e1,
        "filas_iguales": comp["filas_iguales"],
        "filas_solo_e1": comp["filas_solo_e1"],
        "filas_solo_e3": comp["filas_solo_e3"],
        "importes_distintos": comp["importes_distintos"],
        "signos_distintos": comp["signos_distintos"],
        "periodos_distintos": comp["periodos_distintos"],
        "origenes_distintos": comp["origenes_distintos"],
        "orden_distinto": comp["orden_distinto"],
        "controles_distintos": comp["controles_distintos"],
        "controles_coincidentes": comp["controles_coincidentes"],
        "advertencias": [sanitizar_mensaje_privacidad(w) for w in warnings],
        "tiempo_e1_ms": t_e1_ms,
        "tiempo_e2_ms": t_e2_ms,
        "tiempo_e3_ms": t_e3_ms,
        "tiempo_relativo": tiempo_relativo,
        "clasificacion": clasificacion,
    }

    if temp_output_dir is not None:
        temp_output_dir.mkdir(parents=True, exist_ok=True)
        out_file = temp_output_dir / f"{id_seguro}_shadow_metrics.json"
        out_file.write_text(json.dumps(resultado_agregado, indent=2))

    return resultado_agregado


def cargar_manifiesto_local(manifest_path: Optional[pathlib.Path | str] = None) -> List[Dict[str, Any]]:
    """
    Carga la lista de documentos a evaluar desde un archivo de manifiesto local no versionado.
    Registra errores técnicos sanitizados sin imprimir rutas completas del sistema de archivos.
    """
    path_to_try = None
    if manifest_path is not None:
        path_to_try = pathlib.Path(manifest_path)
    elif "SHADOW_DOCS_MANIFEST" in os.environ:
        path_to_try = pathlib.Path(os.environ["SHADOW_DOCS_MANIFEST"])
    else:
        std_manifest = PROJECT_ROOT / "shadow_manifest.local.json"
        if std_manifest.exists():
            path_to_try = std_manifest

    if path_to_try is not None and path_to_try.exists():
        try:
            with open(path_to_try, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "documentos" in data:
                return data["documentos"]
        except Exception as exc:
            logger.warning("[MANIFEST_ERROR] Error leyendo manifiesto: %s", sanitizar_mensaje_privacidad(str(exc)))

    return []


def ejecutar_modo_sombra_lote(
    rutas_o_items: Optional[List[Any]] = None,
    manifest_path: Optional[pathlib.Path | str] = None,
) -> Dict[str, Any]:
    """
    Ejecuta el modo sombra en lote sobre una lista de documentos o manifiesto local.
    Aplica política cerrada de identificadores y sanitización rigurosa.
    """
    items = rutas_o_items or cargar_manifiesto_local(manifest_path)
    resultados_docs = []

    total_concordantes = 0
    total_diferentes = 0
    total_fallos = 0
    total_no_evaluables = 0
    total_e3_activados = 0
    total_e3_fallbacks = 0

    for idx, item in enumerate(items, 1):
        if isinstance(item, (str, pathlib.Path)):
            p = pathlib.Path(item)
            pags = None
            raw_id = None
        elif isinstance(item, dict):
            p = pathlib.Path(item.get("ruta", ""))
            pags = item.get("paginas")
            raw_id = item.get("id")
        else:
            continue

        res = ejecutar_modo_sombra_documento(p, paginas=pags, doc_id=raw_id, indice=idx)
        resultados_docs.append(res)

        clasif = res.get("clasificacion")
        if clasif == "Concordante":
            total_concordantes += 1
        elif clasif == "Diferente, requiere revisión":
            total_diferentes += 1
        elif clasif == "Fallo técnico":
            total_fallos += 1
        else:
            total_no_evaluables += 1

        if res.get("e3_activado"):
            total_e3_activados += 1
        else:
            total_e3_fallbacks += 1

    return {
        "total_documentos": len(items),
        "documentos_evaluados": len(resultados_docs),
        "resumen_clasificacion": {
            "concordantes": total_concordantes,
            "diferente_requiere_revision": total_diferentes,
            "fallo_tecnico": total_fallos,
            "no_evaluable": total_no_evaluables,
        },
        "resumen_activacion_e3": {
            "activaciones_doble_columna": total_e3_activados,
            "fallbacks_seguros": total_e3_fallbacks,
        },
        "detalle_por_documento": resultados_docs,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecutor de modo sombra para validación de extractores")
    parser.add_argument("--manifest", help="Ruta a archivo de manifiesto local JSON (ignorado por Git)")
    parser.add_argument("--doc", action="append", help="Ruta a documento PDF individual")
    args = parser.parse_args()

    rutas_cli = args.doc if args.doc else None
    reporte = ejecutar_modo_sombra_lote(rutas_o_items=rutas_cli, manifest_path=args.manifest)
    print("REPORTE AGREGADO MODO SOMBRA (EJECUCIÓN LOCAL):")
    print(f"Total documentos: {reporte['total_documentos']}")
    print(f"Resumen clasificación: {reporte['resumen_clasificacion']}")
    print(f"Resumen activación E3: {reporte['resumen_activacion_e3']}")
    for d in reporte["detalle_por_documento"]:
        print(f"  [{d['doc_id']}] E1={d.get('e1_cuentas')}, E3={d.get('e3_cuentas')}, Activado={d.get('e3_activado')}, Clasif='{d.get('clasificacion')}', T_rel={d.get('tiempo_relativo')}x")
