"""
parser_universal.py

Parser universal de balances tributarios chilenos (Excel y PDF).

Pipeline:
  1. Detectar tipo de archivo (xlsx/xls/pdf) y validar integridad
  2. PDF: intentar extracción de texto nativo
  3. Si no hay texto nativo → OCR con detección automática de rotación
  4. Detectar formato de código de cuenta (guion/punto/compacto/sin_codigo)
  5. Detectar separador de miles (punto vs coma)
  6. Parsear líneas → lista de CuentaRaw con código, nombre, monto,
     y columna de origen (activo/pasivo/pérdida/ganancia) cuando exista
"""

import csv
import io
import logging
import math
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import pdfplumber
from PIL import Image


logger = logging.getLogger("parser_universal")

RAW_MONETARY_COLUMNS = (
    "debitos", "creditos", "saldo_deudor", "saldo_acreedor",
    "activo", "pasivo", "perdida", "ganancia",
)


def _sin_acentos(texto: str) -> str:
    return ''.join(
        char for char in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(char)
    )


def detectar_años_y_monedas(lineas: list[str]) -> tuple[list[str], list[str]]:
    años = []
    monedas = []
    patron_año = re.compile(r'\b(20\d{2})\b')

    for l in lineas[:60]:
        l_norm = _sin_acentos(l).lower()
        matches = patron_año.findall(l_norm)
        for m in matches:
            if m not in años:
                años.append(m)
        if 'actual' in l_norm and 'actual' not in años:
            años.append('actual')
        if 'anterior' in l_norm and 'anterior' not in años:
            años.append('anterior')
        if 'acumulado' in l_norm and 'acumulado' not in años:
            años.append('acumulado')

        # Scan tokens in order to preserve header column order
        tokens_lower = [t.lower() for t in l.split()]
        for t in tokens_lower:
            if any(w in t for w in ('usd', 'dolar', 'us$', 'dolares')):
                if 'USD' not in monedas:
                    monedas.append('USD')
            elif any(w in t for w in ('clp', 'peso', 'clp$', 'pesos')):
                if 'CLP' not in monedas:
                    monedas.append('CLP')

    if not monedas:
        for l in lineas[:60]:
            if '$' in l:
                monedas.append('CLP')
                break
    return años, monedas


def _normalizar_ruido_terminal_monetario(linea: str) -> str:
    """Quita sólo puntuación OCR pegada al último importe de una fila.

    Un sufijo como ``0!`` no representa una novena columna ni un signo
    contable. La regla es intencionalmente estrecha: no toca puntuación
    separada, símbolos monetarios ni tokens que incluyan otros caracteres
    (por ejemplo, ``12%``).
    """
    return re.sub(r"(?<=\d)[!¿:]+(?=\s*$)", "", linea)


def split_side_by_side(
    line: str,
    *,
    permitir_corte_con_ocho_columnas: bool = False,
) -> list[str]:
    """Separa tablas laterales cuando la estructura no es ambigua.

    Una fila sin código que contiene un número en su propia glosa tiene el
    mismo patrón textual que dos tablas adyacentes. Con ocho columnas finales,
    la opción segura es conservarla completa por defecto. El llamador puede
    solicitar el corte candidato y validar después que ambos fragmentos traen
    códigos contables independientes.
    """
    # Usa el texto saneado para decidir el corte y para los fragmentos que se
    # entregan al parseo. Si no hay corte, conserva ``line`` sin modificar.
    tokens = _normalizar_ruido_terminal_monetario(line).split()
    if len(tokens) < 6:
        return [line]

    # Una fila tributaria completa ya trae ocho celdas monetarias al final.
    # Guiones internos de la glosa ("Préstamo JL - CP", por ejemplo) forman
    # el patrón textual T-N-T-N y antes se confundían con dos tablas paralelas.
    # Si las ocho columnas están presentes, la fila es canónica y no se parte.
    trailing_amounts = 0
    terminal_noise = True
    for token in reversed(tokens):
        cleaned = token.replace("$", "").strip()
        if (
            cleaned in {"-", "—", "−", "o", "O"}
            or re.fullmatch(r"-?\(?\d[\d.,]*\)?", cleaned)
        ):
            trailing_amounts += 1
            terminal_noise = False
            continue
        # Tesseract puede dejar una marca de escaneo al final de una fila
        # completa (por ejemplo ``!`` o ``¿``). No es una celda ni parte de
        # la glosa: al ignorarla aquí se preservan las ocho posiciones ya
        # observadas, sin agregar ni alterar importes. Sólo se omite mientras
        # sea estrictamente terminal: una puntuación entre dos grupos conserva
        # la señal de que podrían ser tablas paralelas.
        if (
            terminal_noise
            and cleaned
            and not re.search(r"[A-Za-z0-9]", cleaned)
        ):
            continue
        break
    # Classify tokens
    types = []
    for t in tokens:
        t_stripped = t.replace('$', '').replace('(', '').replace(')', '').strip(' .-–—−,[]')
        is_num = False
        if re.search(r'\d', t_stripped) or t in ('-', '—', '−') or t_stripped in ('', '-', '—', '−'):
            is_num = True
        types.append('N' if is_num else 'T')

    # Collapsed groups
    groups = []  # list of (type, start_idx, end_idx)
    current_type = None
    start_idx = 0
    for idx, t_type in enumerate(types):
        if t_type != current_type:
            if current_type is not None:
                groups.append((current_type, start_idx, idx))
            current_type = t_type
            start_idx = idx
    if current_type is not None:
        groups.append((current_type, start_idx, len(types)))

    # Build the collapsed pattern string
    pattern = "".join(g[0] for g in groups)

    # Check if we have a side-by-side transition 'TNTN'. Se calcula el corte
    # antes de decidir que ocho importes finales vuelven canónica a la fila:
    # un escaneo de dos zonas puede contener una segunda tabla completa al
    # lado derecho.
    split_token_idx = -1
    if "TNTN" in pattern:
        t_count = 0
        for g_idx, (g_type, g_start, g_end) in enumerate(groups):
            if g_type == 'T':
                t_count += 1
                if t_count == 2:
                    split_token_idx = g_start
                    break
        if split_token_idx != -1:
            # Check if the token immediately preceding split_token_idx is a code
            if split_token_idx > 0:
                prev_tok = tokens[split_token_idx - 1]
                if re.match(r'^\d+[\d.\-]*$', prev_tok) and len(prev_tok) >= 3:
                    split_token_idx -= 1

    if trailing_amounts >= len(RAW_MONETARY_COLUMNS):
        if not permitir_corte_con_ocho_columnas:
            return [line]
        # La protección original conserva una fila tributaria canónica con
        # guiones internos en la glosa. Sólo se deja pasar el corte cuando la
        # porción izquierda termina en un importe observado, no en un guion o
        # marcador OCR, y no parece el patrón de una cuenta codificada cuyo
        # nombre contiene un número ("Cuenta 10 CP", por ejemplo).
        left_ends_in_amount = (
            split_token_idx > 0
            and bool(re.fullmatch(
                r"-?\(?\d[\d.,]*\)?",
                tokens[split_token_idx - 1].replace("$", "").strip(),
            ))
        )
        left_amount_digits = (
            len(re.sub(r"\D", "", tokens[split_token_idx - 1]))
            if left_ends_in_amount else 0
        )

        def parece_codigo_cuenta(token: str) -> bool:
            candidato = token.strip()
            return bool(re.fullmatch(
                r"(?:\d{3,}|\d{1,2}(?:[.\-/]\d{1,3}){2,})",
                candidato,
            ))

        def inicia_fila_descriptiva(index: int) -> bool:
            """Evita cortar dentro de las ocho celdas de una fila canónica."""
            if index >= len(tokens):
                return False
            candidato = tokens[index].strip()
            letras = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ]", "", candidato)
            if len(letras) >= 2:
                return True
            if not parece_codigo_cuenta(candidato) or index + 1 >= len(tokens):
                return False
            letras_siguiente = re.sub(
                r"[^A-Za-zÁÉÍÓÚÑáéíóúñ]", "", tokens[index + 1],
            )
            return len(letras_siguiente) >= 2

        corte_lateral_observado = (
            left_ends_in_amount
            and left_amount_digits >= 2
            and inicia_fila_descriptiva(split_token_idx)
            and not (
                parece_codigo_cuenta(tokens[0])
                and not parece_codigo_cuenta(tokens[split_token_idx])
            )
        )
        if not corte_lateral_observado:
            return [line]

    if split_token_idx != -1:
        left_line = " ".join(tokens[:split_token_idx]).strip(' .-–—−')
        right_line = " ".join(tokens[split_token_idx:]).strip(' .-–—−')
        return [left_line, right_line]

    return [line]


def asociar_lineas_verticales(lineas: list[str]) -> list[str]:
    new_lines = []
    skip = False

    for idx in range(len(lineas)):
        if skip:
            skip = False
            continue

        l_curr = lineas[idx].strip()
        if not l_curr:
            new_lines.append("")
            continue

        has_digits_curr = re.search(r'\d{3,}', l_curr)

        if not has_digits_curr and idx + 1 < len(lineas):
            l_next = lineas[idx + 1].strip()
            cleaned_next = re.sub(r'[\d\s.,$()\-—−_\[\]]', '', l_next)

            if cleaned_next == "" and l_next and re.search(r'\d', l_next):
                merged = f"{l_curr} {l_next}"
                new_lines.append(merged)
                skip = True
                continue

        new_lines.append(lineas[idx])

    return new_lines




def _extraer_tabla_balance_8_columnas(page) -> list[str]:
    """Reconstruye tablas nativas donde los guiones preservan columnas vacías.

    ``extract_text`` colapsa esas celdas y desplaza el monto hacia Ganancia.
    ``extract_tables`` conserva las nueve celdas (nombre + ocho importes), por
    lo que se emite una línea canónica compatible con ``parsear_linea``.
    """
    esperados = [
        'nombre', 'debitos', 'creditos', 'saldo deudor', 'saldo acreedor',
        'activo', 'pasivo', 'perdida', 'ganancia',
    ]
    for tabla in page.extract_tables() or []:
        for indice, fila in enumerate(tabla):
            if not fila or len(fila) != 9:
                continue
            encabezados = [
                re.sub(r'\s+', ' ', _sin_acentos(str(celda or '')).lower()).strip()
                for celda in fila
            ]
            if encabezados != esperados:
                continue

            lineas: list[str] = []
            for datos in tabla[indice + 1:]:
                if not datos or len(datos) != 9:
                    continue
                nombre = re.sub(r'\s+', ' ', str(datos[0] or '')).strip()
                if not nombre:
                    continue
                montos = [
                    '0' if str(celda or '').strip() in ('', '-')
                    else re.sub(r'\s+', '', str(celda))
                    for celda in datos[1:]
                ]
                lineas.append(f"{nombre} {' '.join(montos)}")
            if lineas:
                return lineas
    return []


def _agrupar_palabras_por_linea(words: list[dict], tolerancia: float = 2.5) -> list[list[dict]]:
    """Agrupa palabras por coordenada vertical sin depender de bordes de tabla."""
    grupos: list[list[dict]] = []
    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        if not grupos or abs(float(word["top"]) - float(grupos[-1][0]["top"])) > tolerancia:
            grupos.append([word])
        else:
            grupos[-1].append(word)
    return grupos


_HEADER_ALIASES = {
    "nombre": {"CUENTA", "CUENTAS", "NOMBRE", "DESCRIPCION", "DETALLE"},
    "debitos": {"DEBITOS", "DEBITO", "DEBE", "DCHE", "PEBITOS", "DEBIT0S"},
    "creditos": {"CREDITOS", "CREDITO", "HABER"},
    "saldo_deudor": {"DEUDOR", "SDEUDOR", "SALDODEUDOR"},
    "saldo_acreedor": {"ACREEDOR", "ACREEEDOR", "SACREEDOR", "SALDOACREEDOR", "VERCEDOR", "VERVEDOR"},
    "activo": {"ACTIVO", "ACTIVOS", "ACLIVO"},
    "pasivo": {"PASIVO", "PASIVOS", "PASIWO", "PASIVA", "PATRIMONIO"},
    "perdida": {"PERDIDA", "PERDIDAS"},
    "ganancia": {"GANANCIA", "GANANCIAS"},
}


def _extraer_tabla_balance_por_coordenadas(
    page, column_centers: Optional[list[float]] = None,
    *, incluir_evidencia_celdas: bool = False,
) -> tuple:
    """Extrae Cuenta + ocho importes usando encabezados y geometría.

    Acepta documentos con o sin código y sinónimos comunes de encabezado. El
    layout detectado se puede reutilizar en páginas continuadas sin encabezado.
    """
    def resultado(
        lineas_resultado: list[str],
        centros_resultado: Optional[list[float]],
        evidencias_resultado: list[dict[str, Any]],
    ) -> tuple:
        if incluir_evidencia_celdas:
            return lineas_resultado, centros_resultado, evidencias_resultado
        return lineas_resultado, centros_resultado

    try:
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
    except Exception:
        return resultado([], column_centers, [])
    grupos = _agrupar_palabras_por_linea(words)
    header_words: list[dict] | None = None
    detected: dict[str, dict] = {}
    for start in range(len(grupos)):
        for window_size in (1, 2, 3):
            window = grupos[start:start + window_size]
            if len(window) != window_size:
                continue
            if float(window[-1][0]["top"]) - float(window[0][0]["top"]) > 18:
                continue
            combined = [word for group in window for word in group]
            normalized = {
                re.sub(
                    r"[^A-Z]", "",
                    _sin_acentos(str(word.get("text", ""))).upper(),
                ): word
                for word in combined
            }
            matches: dict[str, dict] = {}
            for key, aliases in _HEADER_ALIASES.items():
                for alias in aliases:
                    if alias in normalized:
                        matches[key] = normalized[alias]
                        break
            # A usable geometric table needs both the account-label column and
            # every monetary column. OCR can recognize the numeric headers
            # while losing the left-most ``CUENTA`` label; treating that as a
            # complete header used to raise KeyError below and abort parsing.
            if "nombre" in matches and all(
                key in matches for key in RAW_MONETARY_COLUMNS
            ):
                header_words = combined
                detected = matches
                break
        if header_words:
            break
    if not header_words and not column_centers:
        return resultado([], None, [])

    inherited_amount_distance: Optional[float] = None
    continuation_body_start_top: Optional[float] = None
    if not header_words and column_centers:
        # No heredar una tabla de ocho columnas al comenzar otro estado de
        # una sola columna (p. ej. balance tributario seguido del clasificado).
        # Una continuación auténtica, sin embargo, puede imprimir sólo los
        # importes no nulos en cada fila. Para distinguir ambos casos no basta
        # contar valores por fila: exigimos varias filas dispersas y cobertura
        # de al menos seis de las ocho posiciones monetarias heredadas.
        numeric_counts = []
        sparse_rows = 0
        observed_amount_columns: set[int] = set()
        sparse_candidate_indices: list[int] = []
        anchored_counts_by_group: dict[int, int] = {}
        inherited_amount_centers = list(column_centers)[1:]
        if len(inherited_amount_centers) != len(RAW_MONETARY_COLUMNS):
            return resultado([], column_centers, [])
        minimum_gap = min(
            right - left
            for left, right in zip(
                inherited_amount_centers, inherited_amount_centers[1:],
            )
        )
        max_inherited_distance = minimum_gap * 0.48
        inherited_amount_distance = max_inherited_distance
        for group_index, group in enumerate(grupos):
            if not any(re.search(r"[A-Za-z]", str(w["text"])) for w in group):
                continue
            amounts_in_group = []
            anchored_amounts = 0
            for word in group:
                token = normalizar_token_ocr(str(word["text"]))
                if not PATRON_MONTOS.fullmatch(token):
                    continue
                xmid = (float(word["x0"]) + float(word["x1"])) / 2
                nearest = min(
                    range(len(inherited_amount_centers)),
                    key=lambda index: abs(xmid - inherited_amount_centers[index]),
                )
                if abs(xmid - inherited_amount_centers[nearest]) <= max_inherited_distance:
                    observed_amount_columns.add(nearest)
                    anchored_amounts += 1
                amounts_in_group.append(word)
            amount_count = len(amounts_in_group)
            numeric_counts.append(amount_count)
            anchored_counts_by_group[group_index] = anchored_amounts
            if 4 <= anchored_amounts <= 5:
                sparse_rows += 1
                sparse_candidate_indices.append(group_index)
        sparse_eight_column_continuation = (
            sparse_rows >= 3 and len(observed_amount_columns) >= 6
        )
        if sparse_eight_column_continuation:
            # Empieza en la primera fila que demuestra ser parte de la grilla,
            # no en los metadatos o encabezados OCR que preceden la tabla. Se
            # recuperan también las filas inmediatamente anteriores que tienen
            # uno a tres importes anclados: una cuenta válida puede comenzar
            # con menos valores impresos que las filas posteriores.
            first_body_index = min(sparse_candidate_indices)
            while first_body_index > 0:
                previous_index = first_body_index - 1
                previous_top = float(grupos[previous_index][0]["top"])
                current_top = float(grupos[first_body_index][0]["top"])
                if (
                    anchored_counts_by_group.get(previous_index, 0) < 1
                    or current_top - previous_top > 24
                ):
                    break
                first_body_index = previous_index
            continuation_body_start_top = float(grupos[first_body_index][0]["top"])
        if (
            sum(1 <= n <= 4 for n in numeric_counts) >= 5
            and not any(n >= 6 for n in numeric_counts)
            and not sparse_eight_column_continuation
        ):
            return resultado([], None, [])

    if header_words:
        ordered = [detected["nombre"]] + [detected[key] for key in RAW_MONETARY_COLUMNS]
        centers = [
            (float(word["x0"]) + float(word["x1"])) / 2
            for word in ordered
        ]
    else:
        centers = list(column_centers or [])
    if len(centers) != 9:
        return resultado([], column_centers, [])
    name_center = centers[0]
    amount_centers = centers[1:]
    text_boundary = (name_center + amount_centers[0]) / 2
    header_bottom = max(float(w["top"]) for w in header_words) if header_words else -1.0
    lineas: list[str] = []
    evidencias_celdas: list[dict[str, Any]] = []
    control_fisico_pendiente: Optional[dict[str, Any]] = None
    for indice_grupo, grupo in enumerate(grupos):
        if float(grupo[0]["top"]) <= header_bottom + 1.5:
            continue
        if (
            continuation_body_start_top is not None
            and float(grupo[0]["top"]) < continuation_body_start_top
        ):
            continue
        text_words: list[dict] = []
        amount_cells: list[list[dict]] = [[] for _ in range(8)]
        # Cuando están presentes los ocho importes completos, sus posiciones
        # distinguen los números de una glosa ("BANCOESTADO 1", "Art. 42").
        ordered_group = sorted(grupo, key=lambda w: float(w["x0"]))
        tail = ordered_group[-8:]
        full_amount_tail = (
            len(ordered_group) > 8
            and all(PATRON_MONTOS.fullmatch(normalizar_token_ocr(str(w["text"])))
                    for w in tail)
            and all(min(range(8), key=lambda j: abs(
                (float(w["x0"]) + float(w["x1"])) / 2 - amount_centers[j]
            )) == i for i, w in enumerate(tail))
        )
        tail_boundary = float(tail[0]["x0"]) if full_amount_tail else text_boundary
        for word in grupo:
            token = str(word["text"]).strip()
            xmid = (float(word["x0"]) + float(word["x1"])) / 2
            token_normalizado = normalizar_token_ocr(token).replace("$", "")
            es_monto = token == "-" or bool(PATRON_MONTOS.fullmatch(token_normalizado))
            # En tablas escaneadas Tesseract suele leer el cero aislado como
            # pequeños glifos sin dígitos (``o``, ``]``, ``»``...). Sólo los
            # aceptamos dentro de la vecindad de una columna monetaria para no
            # convertir palabras legítimas del nombre en importes.
            distancia_columna = min(abs(xmid - center) for center in amount_centers)
            es_cero_en_celda = (
                distancia_columna <= 32
                and _es_token_cero_ocr_en_celda(token)
            )
            if es_cero_en_celda:
                es_monto = True
            nearest = min(
                range(len(amount_centers)),
                key=lambda index: abs(xmid - amount_centers[index]),
            )
            if (
                not es_monto
                or float(word["x1"]) < tail_boundary
                or (
                    inherited_amount_distance is not None
                    and abs(xmid - amount_centers[nearest])
                    > inherited_amount_distance
                )
            ):
                text_words.append(word)
                continue
            amount_cells[nearest].append(word)
        text_tokens = [str(w["text"]) for w in sorted(text_words, key=lambda w: w["x0"])]
        code = ""
        if text_tokens and re.fullmatch(r"\d{4,10}|\d+(?:[.-]\d+){1,}", text_tokens[0]):
            code = text_tokens.pop(0)
        name = " ".join(text_tokens).strip()
        amounts = []
        celdas_evidencia: list[Optional[dict[str, Any]]] = []
        for cell in amount_cells:
            token = "".join(str(w["text"]) for w in sorted(cell, key=lambda w: w["x0"])).strip()
            token_normalizado = normalizar_token_ocr(token).replace("$", "")
            amounts.append(
                token_normalizado
                if token != "-" and PATRON_MONTOS.fullmatch(token_normalizado)
                else "0"
            )
            if not cell:
                celdas_evidencia.append(None)
                continue
            celdas_evidencia.append({
                "token": token,
                "bbox": (
                    min(float(w["x0"]) for w in cell),
                    min(float(w.get("image_top", w["top"])) for w in cell),
                    max(float(w["x1"]) for w in cell),
                    max(float(w.get("image_bottom", w["top"])) for w in cell),
                ),
            })
        if name:
            name = _normalizar_etiqueta_control_ocr(name, celdas_evidencia)
        if not header_words and not any(amount_cells):
            # Sin cabecera detectada, una glosa sin importe posicionado no
            # constituye evidencia suficiente de una cuenta. Evita incorporar
            # metadatos iniciales y leyendas de pie de página como cuentas.
            control_fisico_pendiente = None
            continue
        if not name:
            if control_fisico_pendiente is not None:
                anteriores = control_fisico_pendiente["celdas"]
                indices_anteriores = {
                    indice for indice, celda in enumerate(anteriores)
                    if celda is not None
                }
                indices_actuales = {
                    indice for indice, celda in enumerate(celdas_evidencia)
                    if celda is not None
                }
                if (
                    len(indices_anteriores) == 4
                    and len(indices_actuales) == 4
                    and not indices_anteriores.intersection(indices_actuales)
                    and indices_anteriores.union(indices_actuales)
                    == set(range(len(RAW_MONETARY_COLUMNS)))
                ):
                    importes_anteriores = control_fisico_pendiente["importes"]
                    importes_combinados = [
                        importes_anteriores[indice]
                        if anteriores[indice] is not None else amounts[indice]
                        for indice in range(len(RAW_MONETARY_COLUMNS))
                    ]
                    celdas_combinadas = [
                        anteriores[indice] or celdas_evidencia[indice]
                        for indice in range(len(RAW_MONETARY_COLUMNS))
                    ]
                    indice_linea = int(control_fisico_pendiente["indice"])
                    nombre_control = str(control_fisico_pendiente["nombre"])
                    linea_combinada = (
                        f"{nombre_control} {' '.join(importes_combinados)}"
                    )
                    lineas[indice_linea] = linea_combinada
                    evidencias_celdas[indice_linea] = {
                        "linea": linea_combinada,
                        "celdas": celdas_combinadas,
                    }
                    control_fisico_pendiente = None
                    continue
            siguiente_texto = ""
            for siguiente_grupo in grupos[indice_grupo + 1:]:
                candidato = _texto_palabras_ocr(siguiente_grupo)
                if re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", candidato):
                    siguiente_texto = candidato
                    break
            if not (
                _fila_subtotal_anonima(" ".join(amounts))
                and _es_puente_resultado(siguiente_texto)
                and all(amount_cells)
            ):
                control_fisico_pendiente = None
                continue
            # Algunos formatos dejan el subtotal de ocho columnas sin rótulo
            # justo antes del resultado del ejercicio. La etiqueta sólo
            # identifica ese control observado; no completa ni altera cifras.
            name = "SUBTOTAL SIN ETIQUETA"
        prefix = f"{code} " if code else ""
        linea = f"{prefix}{name} {' '.join(amounts)}"
        lineas.append(linea)
        evidencias_celdas.append({
            "linea": linea,
            "celdas": celdas_evidencia,
        })
        nombre_control = _sin_acentos(name).lower().strip()
        if (
            re.match(r"^(?:total(?:es)?|sub[-\s]?total(?:es)?)\b", nombre_control)
            and sum(celda is not None for celda in celdas_evidencia) == 4
        ):
            control_fisico_pendiente = {
                "indice": len(lineas) - 1,
                "nombre": name,
                "importes": list(amounts),
                "celdas": list(celdas_evidencia),
            }
        else:
            control_fisico_pendiente = None
        # Un control final completo delimita la tabla de esta página. Todo lo
        # que queda después son firmas, notas o metadatos que no deben entrar
        # como cuentas. La condición exige los ocho valores físicos y un
        # rótulo final inequívoco, por lo que no corta subtotales intermedios.
        if _es_control_final_ocho_columnas(name, celdas_evidencia):
            break
    return resultado(lineas, centers, evidencias_celdas)


def _extraer_tabla_balance_10_columnas_por_coordenadas(
    page, column_centers: Optional[list[float]] = None,
) -> tuple[list[str], Optional[list[float]]]:
    """Alias compatible para la estrategia general de ocho montos."""
    return _extraer_tabla_balance_por_coordenadas(page, column_centers)


def _es_balance_tributario(texto: str) -> bool:
    """Identifica el encabezado de la tabla tributaria canónica."""
    normalizado = re.sub(r"\s+", " ", _sin_acentos(texto or "")).lower()
    return "balance tributario" in normalizado


def _es_balance_clasificado_suplementario(
    texto: str,
    ya_hay_balance_tributario_ocho_columnas: bool,
) -> bool:
    """Evita duplicar un anexo clasificado después de su tabla canónica.

    Un archivo puede adjuntar un ``BALANCE CLASIFICADO`` detallado después de
    un balance tributario de ocho columnas del mismo período. Sólo se omite
    ese anexo cuando la tabla tributaria completa ya fue extraída en el mismo
    documento. Un balance clasificado que sea el único estado disponible no
    se descarta.
    """
    if not ya_hay_balance_tributario_ocho_columnas:
        return False
    normalizado = re.sub(r"\s+", " ", _sin_acentos(texto or "")).lower()
    return "balance clasificado" in normalizado


def _es_estado_resultado(texto: str) -> bool:
    normalizado = re.sub(r"\s+", " ", _sin_acentos(texto or "")).lower()
    return "estado de resultado" in normalizado


# ``pdfplumber`` puede devolver los glifos de un PDF lateral como palabras
# invertidas y columnas verticales, aun cuando el archivo tiene texto nativo.
# Estos rótulos son reversos exactos de encabezados contables. Exigir ambos
# identificadores principales y varios adicionales evita activar el respaldo
# por una glosa aislada o por un OCR deficiente.
_NATIVE_SIDEWAYS_REVERSED_HEADERS = frozenset({
    "ATNEUC", "ERBMON", "SOTIBED", "SOTIDERC", "RODUED", "RODEERCA",
    "OVITCA", "OVISAP", "ADIDREP", "AICNANAG",
})


def _texto_nativo_parece_lateral(lineas: list[str]) -> bool:
    """Detecta el patrón estricto de encabezados nativos invertidos.

    No estima una rotación visual desde el texto. Sólo identifica el caso en
    que la extracción nativa ya demostró ser ilegible porque devolvió los
    encabezados de una tabla tributaria caracter por caracter al revés.
    """
    tokens = set(re.findall(
        r"[A-Z]+",
        _sin_acentos("\n".join(lineas or [])).upper(),
    ))
    return bool(
        {"ATNEUC", "ERBMON"}.issubset(tokens)
        and len(tokens & _NATIVE_SIDEWAYS_REVERSED_HEADERS) >= 5
    )


def _extraer_texto_nativo_layout(path: Path) -> list[str]:
    """Recupera el orden visual de una tabla lateral con Poppler.

    Se invoca sólo después de ``_texto_nativo_parece_lateral``. La salida se
    acepta únicamente si aporta varias filas con ocho importes, de modo que un
    texto libre o una salida parcial nunca reemplace la lectura nativa.
    """
    pdftotext_bin = shutil.which("pdftotext")
    if not pdftotext_bin:
        return []
    try:
        resultado = subprocess.run(
            [pdftotext_bin, "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if resultado.returncode != 0 or not resultado.stdout:
        return []
    lineas = [linea.rstrip() for linea in resultado.stdout.splitlines() if linea.strip()]
    filas_ocho_importes = sum(
        len(PATRON_MONTOS.findall(linea)) >= len(RAW_MONETARY_COLUMNS)
        for linea in lineas
    )
    return lineas if filas_ocho_importes >= 3 else []


# Feature flag: cuando está en False, se usa la heurística fija ULTIMAS_COLS.
# Cuando está en True, LayoutDetector analiza los encabezados del documento
# para determinar el orden real de columnas.
ENABLE_DYNAMIC_LAYOUT = False

# OBSOLETO desde Fase A: ParserPDF ya no ejecuta AccountTypeResolver.
# Se conserva solo para compatibilidad (imports/tests). Sin efecto.
ENABLE_ACCOUNT_TYPE_RESOLVER = False

# Umbral de confianza para aplicar corrección de rotación 180°
# sobre texto nativo. Por debajo de este umbral se usa el flujo normal.
ROTATION_CORRECTION_THRESHOLD = 0.7

# La orientación de una imagen OCR se decide por página. Tesseract OSD por sí
# solo no es suficiente para balances: las grillas y los importes pueden darle
# una respuesta de orientación con baja confianza. Se prueban las cuatro
# rotaciones en una imagen reducida y se conserva evidencia de la selección.
OCR_ORIENTATION_CANDIDATES = (0, 90, 180, 270)
OCR_ORIENTATION_PROBE_MAX_PIXELS = 900_000
OCR_ORIENTATION_PROBE_TIMEOUT_SECONDS = 25
OCR_ORIENTATION_MIN_SCORE = 16.0
OCR_ORIENTATION_MIN_MARGIN = 4.0

# Umbral de confianza para usar LayoutDetector desde ExtractionContext.
# Si la confianza del layout detectado por DocumentAnalyzer supera este
# umbral, ParserPDF usa el orden de columnas del contexto en lugar de la
# heurística estándar (ULTIMAS_COLS).
LAYOUT_CONFIDENCE_THRESHOLD = 0.8

# OBSOLETO desde Fase A: la resolución de tipo_cuenta ya no se activa desde
# ExtractionContext dentro de ParserPDF. Se conserva solo para compatibilidad
# (imports/tests). Sin efecto.
ACCOUNT_TYPE_CONFIDENCE_THRESHOLD = 0.7

# Límites defensivos para OCR en instancias con CPU/memoria acotadas (Render).
# Rasterizar a 250 DPI y entregar imágenes sin límite a Tesseract podía bloquear
# una página durante más de dos minutos y abortar la carga completa.
OCR_RENDER_DPI = 200
# Sólo para un cierre final partido que ya falló la lectura primaria. La
# segunda rasterización de una página no participa en cuentas de detalle y se
# acepta exclusivamente si devuelve ambas mitades observadas y cuadradas.
OCR_FINAL_CONTROL_FALLBACK_DPI = 170
OCR_MAX_PIXELS = 3_500_000
OCR_RETRY_MAX_PIXELS = 1_200_000
OCR_PAGE_TIMEOUT_SECONDS = 120
OCR_RETRY_TIMEOUT_SECONDS = 90
# La segunda lectura focal se aplica solamente a las celdas que ya fallaron
# controles independientes. Sus límites son deliberadamente menores que los
# de una página completa para no convertir una recuperación puntual en una
# nueva fuente de timeouts.
OCR_CELL_TIMEOUT_SECONDS = 8
OCR_CELL_PADDING_PIXELS = 8
# Las cajas TSV de una cifra pueden medir sólo 12-20 píxeles de alto a 200
# DPI. Se amplían antes de la relectura, pero el resultado sigue necesitando
# consenso OCR, identidades de fila y mejora de certificación para aplicarse.
OCR_CELL_MIN_HEIGHT_PIXELS = 72
OCR_CELL_MAX_UPSCALE = 4.0
# Los dos umbrales primarios privilegian el trazo interior de 6/8 en impresos
# tenues. Si divergen, dos umbrales de desempate aportan evidencia adicional;
# sólo se acepta un valor que aparezca en al menos dos lecturas y que además
# supere las identidades y controles independientes del llamador.
OCR_CELL_THRESHOLDS = (100, 120)
# Si ambos umbrales bajos quedan vacíos, el escaneo suele ser tenue, no
# ambiguo. Se salta directamente al par alto para conservar presupuesto OCR.
OCR_CELL_EMPTY_PRIMARY_THRESHOLDS = (200, 220)
# Si 200 y 220 divergen, 210 aporta una tercera lectura independiente. Sólo
# resuelve el empate cuando coincide exactamente con una de las dos; no se
# admite nunca una cifra vista una sola vez.
OCR_CELL_EMPTY_PRIMARY_TIEBREAK_THRESHOLD = 210
# Si los primarios entregan lecturas distintas, estos dos umbrales intermedios
# actúan como desempate. En ambos caminos siguen siendo necesarias dos
# lecturas exactamente iguales.
OCR_CELL_TIEBREAK_THRESHOLDS = (140, 180)
# Una diferencia pequeña en un control puede provenir de una cifra OCR espuria
# que deja la identidad de su propia fila aparentemente válida. No se corrige
# por aritmética: este tope limita una tercera lectura nativa a residuos muy
# acotados, donde una cifra observada puede ser contrastada contra el control.
OCR_CONTROL_RESIDUAL_MAX_ABSOLUTE = 100.0
# Una cifra final reconstruida no equivale a una cifra observada. Sin embargo,
# cuando los controles fuente independientes son exactos y el caso es
# excepcional, el producto puede preparar un paquete explícitamente marcado
# para revisión de extracción. El tope evita que una tabla mayoritariamente
# reconstruida se presente como una revisión corta.
MAX_PROPORCION_FINALES_RECONSTRUIDOS_PARA_REVISION = 0.10


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

class FormatoCodigo(str, Enum):
    GUION = 'guion'           # 1-01-01-02-01
    PUNTO = 'punto'            # 1.01.01.02
    COMPACTO = 'compacto'      # 1112001
    SIN_CODIGO = 'sin_codigo'  # solo nombre


class OrigenColumna(str, Enum):
    """Columna del balance donde se reportó el monto (señal para D3/D4)."""
    ACTIVO = 'activo'
    PASIVO = 'pasivo'
    PERDIDA = 'perdida'
    GANANCIA = 'ganancia'
    DEUDOR = 'deudor'
    ACREEDOR = 'acreedor'
    DESCONOCIDO = 'desconocido'


# Mapeo de strings de LayoutDetector a enum OrigenColumna.
# Solo se incluyen columnas informativas para asignación de monto.
_LAYOUT_COLUMN_MAP: dict[str, OrigenColumna] = {
    "activo": OrigenColumna.ACTIVO,
    "pasivo": OrigenColumna.PASIVO,
    "perdida": OrigenColumna.PERDIDA,
    "ganancia": OrigenColumna.GANANCIA,
    "patrimonio": OrigenColumna.PASIVO,
    "deudor": OrigenColumna.DEUDOR,
    "acreedor": OrigenColumna.ACREEDOR,
    "saldo": OrigenColumna.DESCONOCIDO,
}


@dataclass
class CuentaRaw:
    linea: int
    codigo: Optional[str]
    nombre: str
    monto: Optional[float]
    origen_columna: OrigenColumna = OrigenColumna.DESCONOCIDO
    es_total: bool = False
    confianza_extraccion: float = 1.0  # baja si viene de OCR
    tipo_cuenta: Optional[str] = None  # DEPRECATED (Fase A): NO lo escribe ParserPDF; se puebla post-parseo.
    montos_columnas: dict[str, float] = field(default_factory=dict)
    montos_periodos: dict[str, float] = field(default_factory=dict)
    columnas_derivadas: list[str] = field(default_factory=list)
    # Sección contable observada en el documento, distinta de la columna
    # física. En balances clasificados de dos columnas el lado derecho puede
    # contener primero PASIVO y luego PATRIMONIO; conservar ambos evita
    # convertir la evidencia geométrica en una reclasificación silenciosa.
    seccion_contable: Optional[str] = None
    # Estado financiero explícitamente identificado por sus encabezados.
    # Distingue una hoja de situación de una hoja de resultados cuando ambas
    # conviven en el mismo PDF.
    estado_financiero: Optional[str] = None


@dataclass
class CertificacionExtraccion:
    estado: str = "no_evaluable"  # certificada | parcial | fallida | no_evaluable
    metodo: str = ""
    totales_impresos: dict[str, float] = field(default_factory=dict)
    totales_calculados: dict[str, float] = field(default_factory=dict)
    diferencias: dict[str, float] = field(default_factory=dict)
    razones: list[str] = field(default_factory=list)
    filas_evaluadas: int = 0
    filas_inconsistentes: list[int] = field(default_factory=list)
    totales_finales_validos: Optional[bool] = None
    resultado_ejercicio: Optional[float] = None
    tipo_resultado: Optional[str] = None
    columnas_total_reconstruidas: list[str] = field(default_factory=list)
    # Independiente del estado de certificación de las ocho columnas.
    columnas_finales_validadas: bool = False
    # Filas cuyo importe de Activo/Pasivo/Pérdida/Ganancia se reconstruyó a
    # partir de otras columnas. No se confunde con una celda observada.
    reconstrucciones_finales: list[dict[str, Any]] = field(default_factory=list)
    proporcion_finales_reconstruidos: float = 0.0
    # Autoriza exclusivamente un paquete para que el analista contraste estas
    # filas con el original. Nunca certifica extracción ni integración.
    reconstruccion_final_revisable: bool = False
    observaciones_auxiliares: list[dict] = field(default_factory=list)
    # Diagnóstico de la evidencia observada, no una afirmación sobre la causa
    # del documento. Permite separar, por ejemplo, un subtotal no detectado de
    # inconsistencias masivas de fila sin convertir esa señal en una corrección.
    diagnostico: str = "NO_EVALUADO"
    senales_diagnostico: list[str] = field(default_factory=list)
    # Una extracción OCR sólo puede ser automática cuando la orientación de
    # cada página también quedó respaldada por evidencia independiente.
    orientacion_certificada: Optional[bool] = None
    orientaciones_paginas: list[dict[str, Any]] = field(default_factory=list)
    # Ecuación observada en el balance tributario de ocho columnas:
    # Activo - Pasivo = Ganancia - Pérdida. Es una certificación de la fuente,
    # independiente de la cuadratura del balance ya homologado por código.
    ecuacion_contable_fuente_valida: Optional[bool] = None
    diferencia_ecuacion_contable_fuente: Optional[float] = None


@dataclass
class ResultadoParseo:
    archivo: str
    formato_codigo: FormatoCodigo
    separador_miles: str            # '.' o ','
    requirio_ocr: bool
    rotacion_aplicada: int           # 0/90/180/270; -1 cuando es mixta
    cuentas: list[CuentaRaw] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    # Sprint 31: contexto del análisis documental previo al parseo.
    # None cuando no se ejecutó (Excel) o cuando el análisis falló.
    document_context: Optional[Any] = None
    # Sprint 34: SOLO anotación de qué extractor se seleccionó (id, familia,
    # confidence, fallback, tiempo). NO cambia la extracción: None cuando no
    # hubo análisis documental o cuando el análisis de extractor falló.
    extractor_info: Optional[dict] = None
    certificacion_extraccion: CertificacionExtraccion = field(
        default_factory=CertificacionExtraccion
    )
    orientacion_certificada: Optional[bool] = None
    orientaciones_paginas: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExtractionContext:
    """Contexto de extracción producido por DocumentAnalyzer.

    Contiene pistas estructurales sobre el documento que ParserPDF
    puede usar para adaptar su estrategia de extracción.

    rotation_hint:   rotación detectada por DocumentAnalyzer (0, 90, 180)
    rotation_confidence: confianza de la detección de rotación
    needs_ocr:       si el documento requiere OCR (None = dejar que ParserPDF decida)
    layout_hint:     orden de columnas detectado por LayoutDetector
    format_hint:     formato de código detectado
    confidence:      confianza general del análisis
    """
    rotation_hint: int = 0
    rotation_confidence: float = 0.0
    needs_ocr: Optional[bool] = None
    layout_hint: Optional[list[str]] = None
    layout_confidence: float = 0.0
    format_hint: Optional[FormatoCodigo] = None
    confidence: float = 1.0
    analysis_source: Optional[str] = None
    # Líneas ya separadas por un extractor especializado (doble columna).
    # Si vienen seteadas, ParserPDF las usa en lugar de re-extraer el texto
    # plano del PDF, reutilizando íntegramente el pipeline de parseo.
    lineas_presplit: Optional[list[str]] = None


# ─────────────────────────────────────────────────────────────────────────────
# VALIDACIÓN DE ARCHIVO
# ─────────────────────────────────────────────────────────────────────────────

def validar_archivo(path: Path) -> tuple[bool, str]:
    """Valida que el archivo no esté corrupto antes de procesarlo."""
    if not path.exists():
        return False, f"Archivo no existe: {path}"

    size = path.stat().st_size
    if size == 0:
        return False, "Archivo vacío (0 bytes)"

    suffix = path.suffix.lower()

    if suffix in ('.xlsx', '.xlsm'):
        try:
            with zipfile.ZipFile(path, 'r') as z:
                if 'xl/workbook.xml' not in z.namelist():
                    return False, "El .xlsx no contiene workbook.xml válido"
        except zipfile.BadZipFile:
            with open(path, 'rb') as f:
                head = f.read(min(size, 4096))
            if head == b'\x00' * len(head):
                return False, (
                    f"Archivo corrupto: {size} bytes, todo ceros binarios. "
                    "Probablemente una descarga/exportación fallida."
                )
            return False, "Archivo .xlsx corrupto: no es un ZIP válido"

    elif suffix == '.xls':
        with open(path, 'rb') as f:
            header = f.read(8)
        ole2_sig = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
        if header != ole2_sig:
            return False, f"Archivo .xls no tiene firma OLE2 válida."

    elif suffix == '.pdf':
        with open(path, 'rb') as f:
            header = f.read(5)
        if header != b'%PDF-':
            return False, f"Archivo .pdf no tiene firma PDF válida."

    return True, "OK"


# ─────────────────────────────────────────────────────────────────────────────
# DETECCIÓN DE FORMATO DE CÓDIGO DE CUENTA Y SEPARADOR DE MILES
# ─────────────────────────────────────────────────────────────────────────────

PATRON_GUION = re.compile(r'^\d+(-\d+){2,}$')
PATRON_PUNTO = re.compile(r'^\d+(\.\d+){2,}$')
# COMPACTO acepta códigos de 5 a 10 dígitos (p. ej. 11010 CAJAS / 21010 OBLIG).
# Antes era 6-10: los códigos de 5 dígitos quedaban como SIN_CODIGO.
PATRON_COMPACTO = re.compile(r'^\d{5,10}$')


def detectar_formato_codigo(codigos_muestra: list[str]) -> FormatoCodigo:
    conteo = {FormatoCodigo.GUION: 0, FormatoCodigo.PUNTO: 0,
              FormatoCodigo.COMPACTO: 0, FormatoCodigo.SIN_CODIGO: 0}

    for c in codigos_muestra:
        c = (c or '').strip()
        if not c:
            conteo[FormatoCodigo.SIN_CODIGO] += 1
        elif PATRON_GUION.match(c):
            conteo[FormatoCodigo.GUION] += 1
        elif PATRON_PUNTO.match(c):
            conteo[FormatoCodigo.PUNTO] += 1
        elif PATRON_COMPACTO.match(c):
            conteo[FormatoCodigo.COMPACTO] += 1
        else:
            conteo[FormatoCodigo.SIN_CODIGO] += 1

    return max(conteo, key=conteo.get)


def detectar_separador_miles(montos_muestra: list[str]) -> str:
    puntos_como_miles = 0
    comas_como_miles = 0

    for m in montos_muestra:
        m = m.strip()
        if not m or m in ('0', '-'):
            continue

        if '.' in m and ',' in m:
            if m.rfind('.') > m.rfind(','):
                comas_como_miles += 1
            else:
                puntos_como_miles += 1
            continue

        if '.' in m:
            partes = m.split('.')
            if all(len(p) == 3 for p in partes[1:]) and len(partes) > 1:
                puntos_como_miles += 1
            elif len(partes) == 2 and len(partes[-1]) in (1, 2):
                pass
            else:
                puntos_como_miles += 1

        elif ',' in m:
            partes = m.split(',')
            if all(len(p) == 3 for p in partes[1:]) and len(partes) > 1:
                comas_como_miles += 1
            elif len(partes) == 2 and len(partes[-1]) in (1, 2):
                pass
            else:
                comas_como_miles += 1

    if puntos_como_miles >= comas_como_miles:
        return '.'
    return ','


def parsear_monto(valor: str, separador_miles: str) -> Optional[float]:
    if valor is None:
        return None
    v = valor.strip().replace(' ', '').replace('$', '').replace('CLP', '').replace('USD', '')
    if v in ('', '-', '—', '−', '0', '0.00', '0,00'):
        return 0.0

    negativo = False
    if v.startswith('(') and v.endswith(')'):
        negativo = True
        v = v[1:-1].strip()
    if v.startswith('-'):
        negativo = True
        v = v[1:].strip()
    if v.endswith('-'):
        negativo = True
        v = v[:-1].strip()

    v = v.replace('(', '').replace(')', '')

    # Tesseract puede alternar punto y coma entre grupos de miles dentro de
    # una misma celda de control, por ejemplo ``5.833,800,607``. Si hay al
    # menos dos grupos completos de tres dígitos, son miles inequívocos en el
    # contexto de estos balances y se normalizan antes de aplicar el
    # separador predominante del documento. No se toca una cifra con decimal
    # final de uno o dos dígitos.
    grupos_miles_repetidos = (
        re.fullmatch(r"\d{1,3}(?:,\d{3}){2,}", v)
        or re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}", v)
        or re.fullmatch(r"\d{1,3}(?:[.,]\d{3}){3,}", v)
    )
    if grupos_miles_repetidos:
        v = v.replace('.', '').replace(',', '')

    if separador_miles == '.':
        v = v.replace('.', '').replace(',', '.')
    elif separador_miles == ',':
        v = v.replace(',', '')
    else:
        if '.' in v and ',' in v:
            if v.rfind('.') > v.rfind(','):
                v = v.replace(',', '')
            else:
                v = v.replace('.', '').replace(',', '.')
        elif ',' in v:
            parts = v.split(',')
            if len(parts) == 2 and len(parts[1]) == 3:
                v = v.replace(',', '')
            else:
                v = v.replace(',', '.')
        elif '.' in v:
            parts = v.split('.')
            if len(parts) == 2 and len(parts[1]) == 3:
                v = v.replace('.', '')
            elif len(parts) > 2:
                v = v.replace('.', '')

    try:
        num = float(v)
        return -num if negativo else num
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# OCR CON ROTACIÓN AUTOMÁTICA
# ─────────────────────────────────────────────────────────────────────────────

TESSDATA_DIR = '/usr/local/share/tessdata'


def _tesseract_env() -> dict[str, str]:
    """Entorno estable para instancias con una fracción pequeña de CPU."""
    return {
        'TESSDATA_PREFIX': TESSDATA_DIR,
        'OMP_THREAD_LIMIT': '1',
    }


def obtener_tesseract_bin() -> str:
    return shutil.which('tesseract') or 'tesseract'


def _texto_subproceso(valor: Any) -> str:
    if isinstance(valor, bytes):
        return valor.decode("utf-8", errors="replace")
    return str(valor or "")


def _tesseract_no_pudo_abrir_imagen(resultado: subprocess.CompletedProcess) -> bool:
    """Reconoce el error de Leptonica antes de reintentar por entrada estándar."""
    detalle = _texto_subproceso(resultado.stderr).lower()
    return (
        "failed to open locally" in detalle
        or "image file not found" in detalle
        or "image file cannot be read" in detalle
    )


def _ejecutar_tesseract_imagen(
    imagen: Path,
    salida: str,
    argumentos: list[str],
    *,
    timeout: int,
) -> subprocess.CompletedProcess:
    """Ejecuta Tesseract por ruta y reintenta por stdin sólo si Leptonica falla.

    Algunos entornos locales permiten crear la imagen temporal pero bloquean a
    Leptonica al reabrirla por ruta. El reintento transmite los mismos bytes al
    mismo binario y conserva la salida textual normalizada; no modifica el PDF
    ni sustituye una lectura OCR por otra fuente.
    """
    comando = [obtener_tesseract_bin(), str(imagen), salida, *argumentos]
    resultado = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=_tesseract_env(),
    )
    if not _tesseract_no_pudo_abrir_imagen(resultado):
        return resultado
    try:
        reintento = subprocess.run(
            [obtener_tesseract_bin(), "stdin", salida, *argumentos],
            input=imagen.read_bytes(),
            capture_output=True,
            timeout=timeout,
            env=_tesseract_env(),
        )
    except OSError:
        return resultado
    return subprocess.CompletedProcess(
        reintento.args,
        reintento.returncode,
        stdout=_texto_subproceso(reintento.stdout),
        stderr=_texto_subproceso(reintento.stderr),
    )


def detectar_rotacion_osd(img_path: Path) -> Optional[int]:
    try:
        result = _ejecutar_tesseract_imagen(
            img_path, "-", ["--psm", "0", "-l", "osd"], timeout=60,
        )
        for line in result.stdout.splitlines():
            if 'Orientation in degrees' in line:
                grados = int(line.split(':')[1].strip())
                return grados
    except Exception:
        pass
    return None


def detectar_rotacion_heuristica(img_path: Path) -> int:
    """Compatibilidad: devuelve la mejor rotación probada en las cuatro caras."""
    return int(_seleccionar_orientacion_ocr(img_path)["rotacion"])


_ORIENTATION_KEYWORD_GROUPS: dict[str, tuple[str, ...]] = {
    # El bloque documental permite certificar orientación aunque una grilla
    # deteriorada no reconozca todavía los encabezados de sus ocho columnas.
    "documento": (
        "razon", "social", "rut", "direccion", "ciudad", "balance",
        "tributario",
    ),
    "cuenta": ("cuenta", "cuentas", "codigo", "descripcion", "detalle", "glosa"),
    # Una página intermedia de un balance suele no repetir su cabecera, pero
    # sí contiene varias glosas contables. Estas palabras no bastan aisladas
    # para certificar orientación: deben acumularse y superar el margen frente
    # a las otras rotaciones.
    "partida_contable": (
        "banco", "bancos", "cliente", "clientes", "proveedor", "proveedores",
        "rendicion", "anticipo", "prestamo", "prestamos", "impuesto",
        "impuestos", "iva", "remuneracion", "remuneraciones", "inventario",
        "arriendo", "arriendos", "depreciacion", "amortizacion", "retencion",
        "retenciones", "honorario", "honorarios", "factura", "facturas",
        "credito", "creditos", "deudor", "deudores", "acreedor", "acreedores",
    ),
    "movimiento": ("debe", "debitos", "haber", "creditos"),
    "saldos": ("deudor", "acreedor", "saldo"),
    "balance": ("activo", "pasivo", "patrimonio"),
    "resultado": ("perdida", "ganancia", "resultado", "ingresos", "gastos"),
    "controles": ("total", "totales", "subtotal", "sumas"),
}


def _ocr_pagina_orientacion(img_path: Path, rotacion: int) -> str:
    """OCR reducido para comparar orientación sin cuadruplicar el OCR final."""
    tmp_path: Optional[Path] = None
    imagen_ocr = img_path
    try:
        with Image.open(img_path) as img:
            preparada = img.rotate(rotacion, expand=True) if rotacion else img.copy()
            pixeles = preparada.width * preparada.height
            if pixeles > OCR_ORIENTATION_PROBE_MAX_PIXELS:
                escala = (OCR_ORIENTATION_PROBE_MAX_PIXELS / pixeles) ** 0.5
                preparada = preparada.resize(
                    (
                        max(1, int(preparada.width * escala)),
                        max(1, int(preparada.height * escala)),
                    ),
                    Image.Resampling.LANCZOS,
                )
            if rotacion or pixeles > OCR_ORIENTATION_PROBE_MAX_PIXELS:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    preparada.save(tmp.name)
                    tmp_path = Path(tmp.name)
                    imagen_ocr = tmp_path
        result = _ejecutar_tesseract_imagen(
            imagen_ocr,
            "-",
            ["--psm", "6", "-l", "spa"],
            timeout=OCR_ORIENTATION_PROBE_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _puntuar_orientacion_ocr(texto: str) -> dict[str, Any]:
    """Puntúa legibilidad y vocabulario contable de un candidato OCR."""
    normalizado = _sin_acentos(texto or "").lower()
    palabras = re.findall(r"[a-z]{3,}", normalizado)
    numeros = re.findall(r"\b\d[\d.,]*\b", normalizado)
    grupos: dict[str, int] = {}
    impactos = 0
    for nombre, terminos in _ORIENTATION_KEYWORD_GROUPS.items():
        encontrados = sum(
            len(re.findall(rf"\b{re.escape(termino)}\b", normalizado))
            for termino in terminos
        )
        grupos[nombre] = encontrados
        impactos += encontrados
    grupos_presentes = sum(valor > 0 for valor in grupos.values())
    # Los términos contables pesan mucho más que cantidad de palabras: una
    # imagen lateral puede producir bastante texto, pero no una cabecera ni
    # vocabulario contable coherente.
    puntaje = (
        grupos_presentes * 12.0
        + min(impactos, 20) * 2.0
        + min(len(palabras), 250) * 0.04
        + min(len(numeros), 250) * 0.02
    )
    return {
        "puntaje": round(puntaje, 3),
        "grupos": grupos,
        "grupos_presentes": grupos_presentes,
        "terminos_contables": impactos,
        "palabras": len(palabras),
        "numeros": len(numeros),
    }


def _seleccionar_orientacion_ocr(img_path: Path) -> dict[str, Any]:
    """Elige la rotación por evidencia, sin confiar ciegamente en OSD.

    El resultado incluye el margen frente al segundo candidato. Si el margen
    o la evidencia contable son insuficientes, la extracción puede continuar
    para diagnóstico, pero queda bloqueada para decisiones automáticas.
    """
    candidatos: list[dict[str, Any]] = []
    for rotacion in OCR_ORIENTATION_CANDIDATES:
        metricas = _puntuar_orientacion_ocr(
            _ocr_pagina_orientacion(img_path, rotacion)
        )
        candidatos.append({"rotacion": rotacion, **metricas})
    ordenados = sorted(
        candidatos,
        key=lambda candidato: (-float(candidato["puntaje"]), int(candidato["rotacion"])),
    )
    mejor = ordenados[0]
    segundo = ordenados[1] if len(ordenados) > 1 else {"puntaje": 0.0}
    margen = round(float(mejor["puntaje"]) - float(segundo["puntaje"]), 3)
    suficiente_vocabulario = (
        int(mejor["grupos_presentes"]) >= 2
        or int(mejor["terminos_contables"]) >= 4
    )
    margen_minimo = max(
        OCR_ORIENTATION_MIN_MARGIN,
        float(mejor["puntaje"]) * 0.12,
    )
    # Un escaneo con una grilla muy densa puede conservar sólo dos palabras
    # contables legibles. En ese caso se admite la orientación únicamente si
    # gana de forma amplia a las otras tres, no por la palabra aislada.
    evidencia_minima_con_margen_fuerte = bool(
        int(mejor["terminos_contables"]) >= 2
        and float(mejor["puntaje"]) >= OCR_ORIENTATION_MIN_SCORE
        and margen >= max(8.0, float(mejor["puntaje"]) * 0.40)
    )
    certificada = bool(
        (suficiente_vocabulario or evidencia_minima_con_margen_fuerte)
        and float(mejor["puntaje"]) >= OCR_ORIENTATION_MIN_SCORE
        and margen >= margen_minimo
    )
    return {
        "rotacion": int(mejor["rotacion"]),
        "puntaje": float(mejor["puntaje"]),
        "margen": margen,
        "certificada": certificada,
        "candidatos": [
            {
                "rotacion": int(candidato["rotacion"]),
                "puntaje": float(candidato["puntaje"]),
                "grupos_presentes": int(candidato["grupos_presentes"]),
                "terminos_contables": int(candidato["terminos_contables"]),
            }
            for candidato in ordenados
        ],
    }


def _puntuar_orientacion_tabla_ocr(texto: str) -> dict[str, Any]:
    """Mide si una lectura OCR de tabla es suficiente para elegir orientación.

    La sonda reducida es barata y funciona bien en la mayoría de las páginas,
    pero las grillas densas pueden perder los encabezados al reducirse. Esta
    métrica se usa sólo como segundo intento para una página que quedó
    ambigua. Conserva el vocabulario contable como señal principal y usa el
    número de filas monetarias únicamente para desempatar lecturas de tabla.
    """
    metricas = _puntuar_orientacion_ocr(texto)
    lineas = [linea for linea in (texto or "").splitlines() if linea.strip()]
    filas_monetarias = sum(
        bool(PATRON_MONTOS.search(linea))
        and bool(re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", linea))
        for linea in lineas
    )
    montos = sum(len(PATRON_MONTOS.findall(linea)) for linea in lineas)
    # No se deja que una grilla ilegible gane sólo por contener muchos dígitos.
    # El componente semántico es el mismo que la sonda y domina el puntaje.
    calidad = (
        float(metricas["puntaje"])
        + min(filas_monetarias, 40) * 0.10
        + min(montos, 80) * 0.01
    )
    return {
        **metricas,
        "filas_monetarias": filas_monetarias,
        "montos": montos,
        "calidad_tabla": round(calidad, 3),
    }


def _recuperar_orientacion_por_tabla_ocr(
    img_path: Path,
    evidencia_sondeo: dict[str, Any],
) -> tuple[Optional[str], int, dict[str, Any]]:
    """Reintenta una página OCR ambigua con lectura tabular completa.

    Se prueban las cuatro rotaciones sólo cuando la sonda reducida no pudo
    certificar una página. Una alternativa se acepta únicamente si el texto
    de tabla contiene evidencia contable suficiente y gana por un margen
    explícito. Así no se transforma una orientación incierta en automática por
    sumar números o filas corruptas.
    """
    rotacion_sondeo = int(evidencia_sondeo.get("rotacion", 0))
    if evidencia_sondeo.get("certificada"):
        return None, rotacion_sondeo, evidencia_sondeo

    candidatos: list[dict[str, Any]] = []

    def evaluar(rotaciones: list[int]) -> None:
        for rotacion in rotaciones:
            if any(int(candidato["rotacion"]) == int(rotacion) for candidato in candidatos):
                continue
            texto = ocr_pagina(img_path, int(rotacion), psm=4)
            metricas = _puntuar_orientacion_tabla_ocr(texto)
            candidatos.append({
                "rotacion": int(rotacion),
                "texto": texto,
                **metricas,
            })

    # La sonda ya ordenó las cuatro rotaciones. Probar primero sus dos mejores
    # opciones cubre los casos de página densa sin multiplicar por cuatro el
    # OCR completo. Las otras dos se usan sólo si esa comparación no entrega
    # evidencia suficiente.
    orden_sondeo = [
        int(candidato["rotacion"])
        for candidato in evidencia_sondeo.get("candidatos", [])
        if str(candidato.get("rotacion", "")).lstrip("-").isdigit()
    ]
    if rotacion_sondeo not in orden_sondeo:
        orden_sondeo.insert(0, rotacion_sondeo)
    if not orden_sondeo:
        orden_sondeo = list(OCR_ORIENTATION_CANDIDATES)
    evaluar(orden_sondeo[:2])

    def ordenar() -> list[dict[str, Any]]:
        return sorted(
            candidatos,
            key=lambda candidato: (
                -float(candidato["calidad_tabla"]), int(candidato["rotacion"]),
            ),
        )

    def evidencia_suficiente(ordenados: list[dict[str, Any]]) -> bool:
        if not ordenados:
            return False
        mejor_local = ordenados[0]
        segundo_local = (
            ordenados[1] if len(ordenados) > 1 else {"calidad_tabla": 0.0}
        )
        margen_local = float(mejor_local["calidad_tabla"]) - float(
            segundo_local["calidad_tabla"]
        )
        vocabulario = (
            int(mejor_local["grupos_presentes"]) >= 2
            or int(mejor_local["terminos_contables"]) >= 4
        )
        return bool(
            vocabulario
            and float(mejor_local["puntaje"]) >= OCR_ORIENTATION_MIN_SCORE
            and margen_local >= max(
                OCR_ORIENTATION_MIN_MARGIN,
                float(mejor_local["calidad_tabla"]) * 0.12,
            )
        )

    if not evidencia_suficiente(ordenar()):
        evaluar(orden_sondeo[2:] or list(OCR_ORIENTATION_CANDIDATES))

    ordenados = ordenar()
    mejor = ordenados[0]
    segundo = ordenados[1] if len(ordenados) > 1 else {"calidad_tabla": 0.0}
    margen = round(
        float(mejor["calidad_tabla"]) - float(segundo["calidad_tabla"]), 3,
    )
    vocabulario_suficiente = (
        int(mejor["grupos_presentes"]) >= 2
        or int(mejor["terminos_contables"]) >= 4
    )
    margen_minimo = max(
        OCR_ORIENTATION_MIN_MARGIN,
        float(mejor["calidad_tabla"]) * 0.12,
    )
    certificada = bool(
        vocabulario_suficiente
        and float(mejor["puntaje"]) >= OCR_ORIENTATION_MIN_SCORE
        and margen >= margen_minimo
    )

    evidencia = dict(evidencia_sondeo)
    evidencia["candidatos_tabla"] = [
        {
            "rotacion": int(candidato["rotacion"]),
            "puntaje": float(candidato["puntaje"]),
            "calidad_tabla": float(candidato["calidad_tabla"]),
            "grupos_presentes": int(candidato["grupos_presentes"]),
            "terminos_contables": int(candidato["terminos_contables"]),
            "filas_monetarias": int(candidato["filas_monetarias"]),
        }
        for candidato in ordenados
    ]
    if not certificada:
        return None, rotacion_sondeo, evidencia

    evidencia.update({
        "rotacion_sondeo": rotacion_sondeo,
        "rotacion": int(mejor["rotacion"]),
        "puntaje_sondeo": evidencia_sondeo.get("puntaje"),
        "puntaje": float(mejor["puntaje"]),
        "margen": margen,
        "certificada": True,
        "metodo_certificacion": "lectura_tabular_ocr",
    })
    return str(mejor["texto"]), int(mejor["rotacion"]), evidencia


def _certificar_consenso_documental_orientacion(
    evidencias: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Certifica orientación repetida en varias páginas con señal moderada.

    La regla no sustituye la evidencia fuerte por página. Sólo completa casos
    donde todas las páginas financieras eligen la misma rotación, cada una
    tiene un margen suficiente y el conjunto aporta señal acumulada. Las
    páginas excluidas, por ejemplo un F22 adjunto, no participan.
    """
    salida = [dict(evidencia) for evidencia in evidencias]
    relevantes = [
        evidencia for evidencia in salida
        if evidencia.get("utilizada_en_extraccion", True)
    ]
    if len(relevantes) < 2 or all(
        bool(evidencia.get("certificada")) for evidencia in relevantes
    ):
        return salida

    try:
        rotaciones = {int(evidencia["rotacion"]) for evidencia in relevantes}
    except (KeyError, TypeError, ValueError):
        return salida
    if len(rotaciones) != 1:
        return salida

    puntajes = [float(evidencia.get("puntaje", 0.0)) for evidencia in relevantes]
    margenes = [float(evidencia.get("margen", 0.0)) for evidencia in relevantes]
    # 12 puntos y 8 de margen son deliberadamente más bajos que la evidencia
    # individual, pero se requieren por cada página y una suma de 40 puntos
    # repartida en al menos dos páginas independientes.
    if (
        min(puntajes, default=0.0) < 12.0
        or min(margenes, default=0.0) < 8.0
        or sum(puntajes) < 40.0
    ):
        return salida

    rotacion = next(iter(rotaciones))
    for evidencia in salida:
        if not evidencia.get("utilizada_en_extraccion", True):
            continue
        if evidencia.get("certificada"):
            continue
        evidencia.update({
            "certificada": True,
            "metodo_certificacion": "consenso_documental",
            "rotacion_consenso": rotacion,
            "paginas_consenso": len(relevantes),
        })
    return salida


def _resumir_rotaciones_paginas(rotaciones: list[int]) -> int:
    """Mantiene el contrato histórico y señala explícitamente una mezcla."""
    unicas = set(rotaciones)
    if not unicas:
        return 0
    if len(unicas) == 1:
        return next(iter(unicas))
    return -1


def _anotar_certificacion_orientacion(
    certificacion: CertificacionExtraccion,
    evidencias: list[dict[str, Any]],
) -> CertificacionExtraccion:
    """Evita que una orientación OCR ambigua se presente como automática.

    La evidencia de una página descartada explícitamente, por ejemplo un F22
    adjunto después del balance, se conserva para trazabilidad pero no invalida
    la orientación de las páginas que sí aportaron cuentas a la extracción.
    """
    certificacion.orientaciones_paginas = [dict(evidencia) for evidencia in evidencias]
    relevantes = [
        evidencia for evidencia in evidencias
        if evidencia.get("utilizada_en_extraccion", True)
    ]
    certificacion.orientacion_certificada = bool(relevantes) and all(
        bool(evidencia.get("certificada")) for evidencia in relevantes
    )
    if certificacion.orientacion_certificada:
        return certificacion
    paginas = [
        str(evidencia.get("pagina"))
        for evidencia in relevantes
        if not evidencia.get("certificada")
    ]
    detalle = ", ".join(paginas) if paginas else "sin evidencia OCR"
    razon = (
        "La orientación OCR no quedó certificada en página(s) " + detalle
        + "; se bloquean decisiones automáticas."
    )
    if razon not in certificacion.razones:
        certificacion.razones.append(razon)
    # La cuadratura original se conserva para diagnóstico. El estado sólo se
    # degrada cuando habría habilitado una decisión automática sin la prueba
    # visual de orientación.
    if certificacion.estado == "certificada":
        certificacion.estado = "parcial"
    return certificacion


def ocr_pagina(img_path: Path, rotacion: int, psm: int = 6) -> str:
    tmp_path: Optional[Path] = None
    retry_path: Optional[Path] = None
    imagen_ocr = img_path

    with Image.open(img_path) as img:
        preparada = img.rotate(rotacion, expand=True) if rotacion != 0 else img.copy()
        pixeles = preparada.width * preparada.height
        if pixeles > OCR_MAX_PIXELS:
            escala = (OCR_MAX_PIXELS / pixeles) ** 0.5
            nuevo_tamano = (
                max(1, int(preparada.width * escala)),
                max(1, int(preparada.height * escala)),
            )
            preparada = preparada.resize(nuevo_tamano, Image.Resampling.LANCZOS)

        if rotacion != 0 or pixeles > OCR_MAX_PIXELS:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                preparada.save(tmp.name)
                tmp_path = Path(tmp.name)
                imagen_ocr = tmp_path

    try:
        try:
            result = _ejecutar_tesseract_imagen(
                imagen_ocr,
                "-",
                ["--psm", str(psm), "-l", "spa"],
                timeout=OCR_PAGE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "OCR excedió %ss; reintentando imagen reducida: %s",
                OCR_PAGE_TIMEOUT_SECONDS,
                img_path.name,
            )
            with Image.open(imagen_ocr) as img:
                pixeles = img.width * img.height
                if pixeles <= OCR_RETRY_MAX_PIXELS:
                    return ""
                escala = (OCR_RETRY_MAX_PIXELS / pixeles) ** 0.5
                reducida = img.resize(
                    (
                        max(1, int(img.width * escala)),
                        max(1, int(img.height * escala)),
                    ),
                    Image.Resampling.LANCZOS,
                )
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    reducida.save(tmp.name)
                    retry_path = Path(tmp.name)
            try:
                result = _ejecutar_tesseract_imagen(
                    retry_path,
                    "-",
                    ["--psm", str(psm), "-l", "spa"],
                    timeout=OCR_RETRY_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    "OCR omitido tras segundo timeout de %ss: %s",
                    OCR_RETRY_TIMEOUT_SECONDS,
                    img_path.name,
                )
                return ""
        if result.returncode != 0:
            logger.warning(
                "Tesseract falló para %s (código %s): %s",
                img_path.name,
                result.returncode,
                (result.stderr or "").strip()[:300],
            )
            return ""
        return result.stdout
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        if retry_path is not None:
            retry_path.unlink(missing_ok=True)


def ocr_pagina_tsv(img_path: Path, rotacion: int, psm: int = 6) -> list[dict]:
    """Obtiene palabras y coordenadas OCR para reconstrucción tabular."""
    tmp_path: Optional[Path] = None
    imagen_ocr = img_path
    if rotacion != 0:
        with Image.open(img_path) as img:
            preparada = img.rotate(rotacion, expand=True)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                preparada.save(tmp.name)
                tmp_path = Path(tmp.name)
                imagen_ocr = tmp_path
    try:
        try:
            result = _ejecutar_tesseract_imagen(
                imagen_ocr,
                "stdout",
                ["-l", "spa", "--psm", str(psm), "tsv"],
                timeout=OCR_PAGE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            logger.warning("OCR TSV excedió el timeout: %s", img_path.name)
            return []
        if result.returncode != 0 or not result.stdout.strip():
            return []
        words: list[dict] = []
        line_positions: dict[tuple[str, str, str, str], float] = {}
        # El TSV de Tesseract no escapa necesariamente comillas que OCR lee
        # como glifos aislados. El dialecto CSV por defecto las interpreta
        # como apertura de campo y puede absorber el resto del archivo TSV en
        # una sola "palabra". En este formato los tabuladores son el único
        # delimitador estructural esperado, por eso las comillas se conservan
        # literalmente.
        for row in csv.DictReader(
            io.StringIO(result.stdout), delimiter="\t", quoting=csv.QUOTE_NONE,
        ):
            text = str(row.get("text") or "").strip()
            if row.get("level") != "5" or not text:
                continue
            try:
                left = float(row["left"])
                top = float(row["top"])
                width = float(row["width"])
                height = float(row["height"])
            except (KeyError, TypeError, ValueError):
                continue
            line_key = (
                str(row.get("page_num") or ""), str(row.get("block_num") or ""),
                str(row.get("par_num") or ""), str(row.get("line_num") or ""),
            )
            if line_key not in line_positions:
                line_positions[line_key] = float(len(line_positions) * 5)
            words.append({
                "text": text,
                "x0": left,
                "x1": left + width,
                # ``top`` conserva el orden lógico de las líneas para los
                # extractores actuales. La caja real queda aparte para que
                # una relectura focal recorte exactamente la celda que OCR
                # observó, sin volver a inferir su posición por la glosa.
                "image_top": top,
                "image_bottom": top + height,
                "top": line_positions[line_key],
            })
        return words
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


class _OCRWordsPage:
    def __init__(self, words: list[dict]):
        self._words = words

    def extract_words(self, **_kwargs) -> list[dict]:
        return self._words


# ─────────────────────────────────────────────────────────────────────────────
# VALIDACIÓN Y CUADRE MATEMÁTICO DEL BALANCE
# ─────────────────────────────────────────────────────────────────────────────

def verificar_cuadre_balance(cuentas: list[CuentaRaw]) -> tuple[bool, dict, list[str]]:
    totales_calculados = {'activo': 0.0, 'pasivo': 0.0, 'perdida': 0.0, 'ganancia': 0.0}

    for c in cuentas:
        if not c.es_total and c.monto and c.origen_columna.value in totales_calculados:
            totales_calculados[c.origen_columna.value] += c.monto

    act = totales_calculados['activo']
    pas = totales_calculados['pasivo']
    per = totales_calculados['perdida']
    gan = totales_calculados['ganancia']

    lado_balance = act - pas
    lado_resultado = gan - per

    cuadra = abs(lado_balance - lado_resultado) < 10.0

    alertas = []
    if not cuadra:
        alertas.append(
            f"⚠️ CONTROL DE CUADRE FALLIDO: Suma Activos ({act:,.0f}) - Pasivos ({pas:,.0f}) = {lado_balance:,.0f} | "
            f"Suma Ganancias ({gan:,.0f}) - Pérdidas ({per:,.0f}) = {lado_resultado:,.0f}. "
            f"Diferencia insalvable: {abs(lado_balance - lado_resultado):,.0f}"
        )
    return cuadra, totales_calculados, alertas


def _validar_columnas_finales(
    cuentas, detalle, subtotal, calculados, finales, puentes, tolerancia,
) -> bool:
    """Valida importes homologables sin reescribir movimientos ni saldos.

    No basta la igualdad global: cada fila necesita respaldo en movimiento o
    saldo; no se admiten filas monetarias omitidas, partidas en varios destinos
    ni discrepancias en los controles finales impresos.
    """
    columnas = RAW_MONETARY_COLUMNS[4:]
    if not detalle:
        return False
    incluidos = {id(c) for c in detalle}
    for c in cuentas:
        if not c.es_total and id(c) not in incluidos and (
            c.codigo or (c.monto is not None and c.monto != 0)
            or any(c.montos_columnas.values())
        ):
            return False
    if not all(
        math.isfinite(float(values.get(col, 0)))
        for values in (subtotal, calculados)
        for col in columnas
    ):
        return False
    if any(abs(calculados[col] - subtotal[col]) > tolerancia for col in columnas):
        return False
    resultado = subtotal["activo"] - subtotal["pasivo"]
    if abs(resultado - (subtotal["ganancia"] - subtotal["perdida"])) > tolerancia:
        return False
    for c in detalle:
        v = c.montos_columnas
        if not all(math.isfinite(float(v[col])) for col in RAW_MONETARY_COLUMNS):
            return False
        pobladas = [col for col in columnas if v[col] != 0]
        if len(pobladas) > 1:
            return False
        if pobladas and c.origen_columna.value != pobladas[0]:
            return False
        derivadas = set(c.columnas_derivadas)
        if derivadas.intersection(columnas):
            return False
        importe = v[pobladas[0]] if pobladas else 0
        if c.monto is None or not math.isfinite(c.monto) or abs(c.monto - importe) > tolerancia:
            return False
        neto_final = v["activo"] + v["perdida"] - v["pasivo"] - v["ganancia"]
        respaldo_movimiento = (
            not derivadas.intersection({"debitos", "creditos"})
            and abs(v["debitos"] - v["creditos"] - neto_final) <= tolerancia
        )
        respaldo_saldo = (
            not derivadas.intersection({"saldo_deudor", "saldo_acreedor"})
            and abs(v["saldo_deudor"] - v["saldo_acreedor"] - neto_final) <= tolerancia
        )
        if not (respaldo_movimiento or respaldo_saldo):
            return False
    puente_esperado = dict.fromkeys(columnas, 0.0)
    for col in (("pasivo", "perdida") if resultado >= 0 else ("activo", "ganancia")):
        puente_esperado[col] = abs(resultado)
    if puentes:
        if any(
            not math.isfinite(float(puentes[-1].montos_columnas.get(col, 0)))
            or abs(puentes[-1].montos_columnas.get(col, 0) - puente_esperado[col]) > tolerancia
            for col in columnas
        ):
            return False
    if finales:
        if any(
            not math.isfinite(float(finales[-1].montos_columnas[col]))
            or abs(finales[-1].montos_columnas[col] - subtotal[col] - puente_esperado[col]) > tolerancia
            for col in columnas
        ):
            return False
    return True


def _diagnosticar_controles_extraccion(
    *,
    tiene_subtotal: bool,
    filas_evaluadas: int,
    filas_inconsistentes: list[int],
    diferencias: dict[str, float],
    tolerancia: float,
    totales_finales_validos: Optional[bool],
    fila_final_incompleta: bool,
    puente_invalido: bool,
    ecuacion_subtotal_invalida: bool,
    parcial: bool,
) -> tuple[str, list[str]]:
    """Resume señales de extracción sin atribuir una causa no observada.

    Los códigos describen únicamente el control que falló. Por ejemplo,
    ``SUBTOTAL_NO_DETECTADO`` no afirma que el PDF no tenga subtotal: puede
    faltar en el original o haber fallado su lectura. Esa distinción queda
    disponible para la revisión humana y evita declarar un formato como no
    soportado sólo a partir de una señal OCR.
    """
    senales: list[str] = []
    if filas_evaluadas <= 0:
        senales.append("SIN_FILAS_CONTABLES")
    if not tiene_subtotal:
        senales.append("SUBTOTAL_NO_DETECTADO")

    if filas_inconsistentes:
        proporcion = len(filas_inconsistentes) / max(filas_evaluadas, 1)
        if len(filas_inconsistentes) >= 3 and proporcion >= 0.20:
            senales.append("INCONSISTENCIAS_MASIVAS_DE_FILA")
        else:
            senales.append("FILAS_INCONSISTENTES")

    diferencias_reales = {
        columna: diferencia
        for columna, diferencia in diferencias.items()
        if abs(float(diferencia)) > tolerancia
    }
    if diferencias_reales:
        if (
            not filas_inconsistentes
            and len(diferencias_reales) == 1
            and max(abs(float(valor)) for valor in diferencias_reales.values())
            <= tolerancia * 2
        ):
            senales.append("DIFERENCIA_PUNTUAL_EN_CONTROL")
        else:
            senales.append("CONTROLES_NO_CONCILIAN")
    if totales_finales_validos is False:
        senales.append("FILA_FINAL_NO_CUADRADA")
    if fila_final_incompleta:
        senales.append("FILA_FINAL_INCOMPLETA")
    if ecuacion_subtotal_invalida:
        senales.append("ECUACION_SUBTOTAL_NO_CONCILIA")
    if puente_invalido:
        senales.append("PUENTE_RESULTADO_NO_CONCILIA")

    prioridades = (
        "SIN_FILAS_CONTABLES",
        "INCONSISTENCIAS_MASIVAS_DE_FILA",
        "SUBTOTAL_NO_DETECTADO",
        "FILA_FINAL_NO_CUADRADA",
        "ECUACION_SUBTOTAL_NO_CONCILIA",
        "PUENTE_RESULTADO_NO_CONCILIA",
        "FILA_FINAL_INCOMPLETA",
        "DIFERENCIA_PUNTUAL_EN_CONTROL",
        "CONTROLES_NO_CONCILIAN",
        "FILAS_INCONSISTENTES",
    )
    for diagnostico in prioridades:
        if diagnostico in senales:
            return diagnostico, senales
    if parcial:
        return "CONTROLES_VALIDOS_CON_REVISION", senales
    return "CONTROLES_VALIDADOS", senales


def certificar_extraccion_columnas(
    cuentas: list[CuentaRaw], metodo: str = "",
    tolerancia_absoluta: float = 10.0,
) -> CertificacionExtraccion:
    """Certifica las ocho columnas contra un subtotal impreso independiente."""
    filas_detalle = [
        cuenta for cuenta in cuentas
        if (
            not cuenta.es_total
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
        )
    ]
    # En balances con plan de cuentas explicito, encabezados, firmas y notas
    # OCR sin codigo no son filas contables y no deben afectar la cuadratura.
    filas_codificadas = [cuenta for cuenta in filas_detalle if cuenta.codigo]
    if len(filas_codificadas) >= 3:
        filas_detalle = filas_codificadas
    filas_inconsistentes: list[int] = []
    for cuenta in filas_detalle:
        values = cuenta.montos_columnas
        movement = values["debitos"] - values["creditos"]
        balance = values["saldo_deudor"] - values["saldo_acreedor"]
        classified = (
            values["activo"] + values["pasivo"]
            + values["perdida"] + values["ganancia"]
        )
        if (
            abs(movement - balance) > tolerancia_absoluta
            or abs(values["saldo_deudor"] + values["saldo_acreedor"] - classified)
            > tolerancia_absoluta
        ):
            filas_inconsistentes.append(cuenta.linea)

    def normalized_name(cuenta: CuentaRaw) -> str:
        return re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()

    def control_key(cuenta: CuentaRaw) -> str:
        return re.sub(r"[^a-z0-9]+", "", normalized_name(cuenta))

    puentes_resultado = [
        cuenta for cuenta in cuentas
        if cuenta.es_total and cuenta.montos_columnas
        and re.match(
            r"^(?:perdida o ganancia|ganancia(?: neta|(?: del)? ejercicio)|"
            r"resultado|utilidad|perdida net[ao]|total perdida)\b",
            normalized_name(cuenta),
        )
    ]
    ids_puentes_resultado = {id(cuenta) for cuenta in puentes_resultado}

    # Algunos generadores imprimen ``Sumas``, luego el puente ``Resultado`` y
    # cierran con el rótulo singular ``Total``. Un Total genérico puede ser un
    # subtotal intermedio, por lo que sólo se acepta como cierre cuando el
    # control inmediatamente anterior es precisamente ese puente, existe una
    # suma o subtotal verificable antes del puente y las ocho columnas ya
    # fueron observadas por la comprensión de ``finales``.
    def es_subtotal_referencia(cuenta: CuentaRaw) -> bool:
        clave = control_key(cuenta)
        return bool(
            cuenta.es_total
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
            and (
                "subtotal" in clave
                or clave in {"suma", "sumas"}
                or clave.startswith("totalacumulado")
            )
        )

    ids_totales_tras_puente: set[int] = set()
    for indice, cuenta in enumerate(cuentas):
        if not cuenta.es_total or control_key(cuenta) != "total":
            continue
        control_anterior = next(
            (
                anterior for anterior in reversed(cuentas[:indice])
                if anterior.es_total
            ),
            None,
        )
        tiene_subtotal_previo = any(
            es_subtotal_referencia(anterior)
            for anterior in cuentas[:indice]
        )
        if (
            control_anterior is not None
            and id(control_anterior) in ids_puentes_resultado
            and tiene_subtotal_previo
        ):
            ids_totales_tras_puente.add(id(cuenta))

    finales = [
        cuenta for cuenta in cuentas
        if (
            cuenta.es_total
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
        )
        and (
            "totales iguales" in normalized_name(cuenta)
            or "sumas iguales" in normalized_name(cuenta)
            or control_key(cuenta) in {"totales", "totalgeneral", "sumastotales"}
            or id(cuenta) in ids_totales_tras_puente
        )
    ]
    ids_finales = {id(cuenta) for cuenta in finales}
    totales_finales_validos: Optional[bool] = None
    fila_final_incompleta = False
    if finales:
        values = finales[-1].montos_columnas
        pairs = (
            ("debitos", "creditos"),
            ("saldo_deudor", "saldo_acreedor"),
            ("activo", "pasivo"),
            ("perdida", "ganancia"),
        )
        fila_final_incompleta = any(
            (values[left] == 0) != (values[right] == 0)
            for left, right in pairs
        )
        if not fila_final_incompleta:
            totales_finales_validos = all(
                abs(values[left] - values[right]) <= tolerancia_absoluta
                for left, right in pairs
            )

    candidatos = [
        cuenta for cuenta in cuentas
        if (
            cuenta.es_total
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
        )
        and id(cuenta) not in ids_finales
        and (
            "subtotal" in control_key(cuenta)
            or control_key(cuenta) in {"suma", "sumas"}
            or control_key(cuenta) == "total"
            or control_key(cuenta).startswith("totalacumulado")
        )
    ]
    if not candidatos:
        razones = ["No se detectó un subtotal impreso de ocho columnas."]
        estado = "no_evaluable"
        diferencias_parciales: dict[str, float] = {}
        if finales:
            final_values = finales[-1].montos_columnas
            for column in RAW_MONETARY_COLUMNS[:4]:
                calculated = sum(
                    float(cuenta.montos_columnas.get(column, 0.0) or 0.0)
                    for cuenta in filas_detalle
                )
                diferencias_parciales[column] = round(
                    calculated - float(final_values.get(column, 0.0) or 0.0), 2
                )
            if any(abs(value) > tolerancia_absoluta for value in diferencias_parciales.values()):
                estado = "fallida"
                razones.append(
                    "Las filas no reproducen Débitos, Créditos o Saldos de la "
                    "fila final impresa."
                )
        if filas_inconsistentes:
            estado = "fallida"
            razones.append(
                f"{len(filas_inconsistentes)} filas no cumplen sus identidades "
                "Debe/Haber, saldo o columna de clasificación."
            )
        if totales_finales_validos is False:
            estado = "fallida"
            razones.append("La fila final impresa no está cuadrada.")
        diagnostico, senales_diagnostico = _diagnosticar_controles_extraccion(
            tiene_subtotal=False,
            filas_evaluadas=len(filas_detalle),
            filas_inconsistentes=filas_inconsistentes,
            diferencias=diferencias_parciales,
            tolerancia=tolerancia_absoluta,
            totales_finales_validos=totales_finales_validos,
            fila_final_incompleta=fila_final_incompleta,
            puente_invalido=False,
            ecuacion_subtotal_invalida=False,
            parcial=False,
        )
        return CertificacionExtraccion(
            estado=estado, metodo=metodo,
            diferencias=diferencias_parciales,
            razones=razones,
            filas_evaluadas=len(filas_detalle),
            filas_inconsistentes=filas_inconsistentes,
            totales_finales_validos=totales_finales_validos,
            diagnostico=diagnostico,
            senales_diagnostico=senales_diagnostico,
        )
    acumulados = [
        cuenta for cuenta in candidatos
        if normalized_name(cuenta).startswith("total acumulado")
    ]
    subtotal_referencia = acumulados[-1] if acumulados else candidatos[-1]
    total_impreso = dict(subtotal_referencia.montos_columnas)
    calculados = {column: 0.0 for column in RAW_MONETARY_COLUMNS}
    filas = 0
    for cuenta in filas_detalle:
        filas += 1
        for column in RAW_MONETARY_COLUMNS:
            calculados[column] += float(cuenta.montos_columnas.get(column, 0.0) or 0.0)
    if not filas:
        diagnostico, senales_diagnostico = _diagnosticar_controles_extraccion(
            tiene_subtotal=True,
            filas_evaluadas=0,
            filas_inconsistentes=filas_inconsistentes,
            diferencias={},
            tolerancia=tolerancia_absoluta,
            totales_finales_validos=totales_finales_validos,
            fila_final_incompleta=fila_final_incompleta,
            puente_invalido=False,
            ecuacion_subtotal_invalida=False,
            parcial=False,
        )
        return CertificacionExtraccion(
            estado="fallida", metodo=metodo,
            totales_impresos=dict(total_impreso),
            razones=["No se detectaron filas de cuentas para contrastar el subtotal."],
            filas_evaluadas=0,
            filas_inconsistentes=filas_inconsistentes,
            totales_finales_validos=totales_finales_validos,
            diagnostico=diagnostico,
            senales_diagnostico=senales_diagnostico,
        )
    columnas_total_reconstruidas: list[str] = []
    for column in ("debitos", "creditos"):
        calculated = float(calculados.get(column, 0.0) or 0.0)
        printed = float(total_impreso.get(column, 0.0) or 0.0)
        if calculated <= 0 or printed <= 0:
            continue
        calculated_digits = str(int(round(abs(calculated))))
        printed_digits = str(int(round(abs(printed))))
        missing = len(calculated_digits) - len(printed_digits)
        # Algunos generadores PDF recortan uno o dos dígitos finales del total,
        # aunque las cuentas y los demás seis controles estén completos.
        if missing in {1, 2} and calculated_digits.startswith(printed_digits):
            total_impreso[column] = calculated
            columnas_total_reconstruidas.append(column)

    diferencias = {
        column: round(calculados[column] - float(total_impreso.get(column, 0.0) or 0.0), 2)
        for column in RAW_MONETARY_COLUMNS
    }
    fallidas = {
        column: diff for column, diff in diferencias.items()
        if abs(diff) > tolerancia_absoluta
    }
    razones = []
    if columnas_total_reconstruidas:
        razones.append(
            "Se reconstruyó el final truncado de "
            + ", ".join(columnas_total_reconstruidas)
            + " usando la suma exacta de las cuentas."
        )
    if fallidas:
        detalle = ", ".join(f"{column}={diff:,.0f}" for column, diff in fallidas.items())
        razones.append(f"Las sumas extraídas no reproducen el subtotal impreso: {detalle}.")
    if filas_inconsistentes:
        razones.append(
            f"{len(filas_inconsistentes)} filas no cumplen sus identidades "
            "Debe/Haber, saldo o columna de clasificación."
        )
    if totales_finales_validos is False:
        razones.append("La fila TOTALES IGUALES no está cuadrada en sus pares de columnas.")
    if fila_final_incompleta:
        razones.append(
            "La fila final fue extraída con una o más columnas vacías; el "
            "subtotal y sus identidades se usan como control y el documento "
            "requiere revisión humana."
        )
    resultado_balance_subtotal = (
        float(total_impreso.get("activo", 0.0) or 0.0)
        - float(total_impreso.get("pasivo", 0.0) or 0.0)
    )
    resultado_estado_subtotal = (
        float(total_impreso.get("ganancia", 0.0) or 0.0)
        - float(total_impreso.get("perdida", 0.0) or 0.0)
    )
    diferencia_ecuacion_contable_fuente: Optional[float] = None
    ecuacion_contable_fuente_valida: Optional[bool] = None
    # Una hoja de situación sin estado de resultado puede traer las dos
    # columnas de resultado a cero. En ese caso no se deduce una ecuación
    # inexistente. Sí se controla cuando ambos lados están observados, o
    # cuando una fila final incompleta declara explícitamente esa estructura.
    hay_balance_fuente = any(
        abs(float(total_impreso.get(column, 0.0) or 0.0))
        for column in ("activo", "pasivo")
    )
    hay_resultado_fuente = any(
        abs(float(total_impreso.get(column, 0.0) or 0.0))
        for column in ("perdida", "ganancia")
    )
    hay_evidencia_fuente = hay_balance_fuente and (
        hay_resultado_fuente or fila_final_incompleta
    )
    if hay_evidencia_fuente:
        diferencia_ecuacion_contable_fuente = round(
            resultado_balance_subtotal - resultado_estado_subtotal, 2,
        )
        ecuacion_contable_fuente_valida = (
            abs(diferencia_ecuacion_contable_fuente)
            <= tolerancia_absoluta
        )
    ecuacion_subtotal_invalida = ecuacion_contable_fuente_valida is False
    if ecuacion_subtotal_invalida:
        razones.append(
            "El subtotal impreso no satisface la ecuación entre balance y "
            "resultado del ejercicio."
        )
    resultado_ejercicio: Optional[float] = None
    tipo_resultado: Optional[str] = None
    puente_invalido = False
    if puentes_resultado:
        puente = puentes_resultado[-1]
        resultado_balance = (
            float(total_impreso.get("activo", 0.0) or 0.0)
            - float(total_impreso.get("pasivo", 0.0) or 0.0)
        )
        resultado_estado = (
            float(total_impreso.get("ganancia", 0.0) or 0.0)
            - float(total_impreso.get("perdida", 0.0) or 0.0)
        )
        if abs(resultado_balance - resultado_estado) > tolerancia_absoluta:
            puente_invalido = True
            razones.append(
                "El resultado derivado del balance no coincide con el resultado "
                "derivado de Pérdidas y Ganancias."
            )
        else:
            resultado_ejercicio = round(resultado_balance, 2)
            tipo_resultado = "utilidad" if resultado_balance >= 0 else "perdida"

        if finales:
            final_values = finales[-1].montos_columnas
            bridge_values = puente.montos_columnas
            cierre_reproducido = True
            for column in RAW_MONETARY_COLUMNS:
                expected = (
                    float(total_impreso.get(column, 0.0) or 0.0)
                    + float(bridge_values.get(column, 0.0) or 0.0)
                )
                actual = float(final_values.get(column, 0.0) or 0.0)
                if abs(expected - actual) <= tolerancia_absoluta:
                    continue
                expected_digits = str(int(round(abs(expected))))
                actual_digits = str(int(round(abs(actual))))
                truncated_final = (
                    column in columnas_total_reconstruidas
                    and len(expected_digits) - len(actual_digits) in {1, 2}
                    and expected_digits.startswith(actual_digits)
                )
                if not truncated_final:
                    cierre_reproducido = False
                    break
            if not cierre_reproducido:
                puente_invalido = True
                razones.append(
                    "La fila PÉRDIDA O GANANCIA no conecta el subtotal con "
                    "la fila SUMAS IGUALES."
                )

    failed = bool(
        fallidas or filas_inconsistentes
        or totales_finales_validos is False or puente_invalido
        or ecuacion_subtotal_invalida
    )
    filas_derivadas = [cuenta.linea for cuenta in filas_detalle if cuenta.columnas_derivadas]
    columnas_finales = set(RAW_MONETARY_COLUMNS[4:])
    reconstrucciones_finales = []
    filas_monetarias = 0
    for cuenta in filas_detalle:
        try:
            monto = float(cuenta.monto or 0.0)
        except (TypeError, ValueError):
            monto = 0.0
        if abs(monto) > tolerancia_absoluta:
            filas_monetarias += 1
        columnas_reconstruidas = sorted(
            set(cuenta.columnas_derivadas).intersection(columnas_finales),
        )
        if not columnas_reconstruidas or abs(monto) <= tolerancia_absoluta:
            continue
        reconstrucciones_finales.append({
            "linea": cuenta.linea,
            "cuenta": cuenta.nombre,
            "columnas": columnas_reconstruidas,
            "importe": monto,
        })
    total_derivado = bool(
        subtotal_referencia.columnas_derivadas or fila_final_incompleta
    )
    parcial = bool(filas_derivadas or total_derivado)
    if (filas_derivadas or total_derivado) and not failed:
        razones.append(
            f"{len(filas_derivadas)} filas contienen movimientos reconstruidos "
            "desde saldos y clasificación"
            + (" y el subtotal fue completado" if total_derivado else "")
            + "; requieren revisión humana."
        )
    columnas_finales_validadas = (
        not set(subtotal_referencia.columnas_derivadas).intersection(RAW_MONETARY_COLUMNS[4:])
        and _validar_columnas_finales(
            cuentas, filas_detalle, total_impreso, calculados, finales,
            puentes_resultado, tolerancia_absoluta,
        )
    )
    proporcion_finales_reconstruidos = (
        len(reconstrucciones_finales) / filas_monetarias
        if filas_monetarias else 0.0
    )
    controles_finales_reconstruidos = any(
        set(control.columnas_derivadas).intersection(columnas_finales)
        for control in [subtotal_referencia, *finales, *puentes_resultado]
    )
    reconstruccion_final_revisable = bool(
        reconstrucciones_finales
        and not failed
        and totales_finales_validos is True
        and ecuacion_contable_fuente_valida is True
        and not controles_finales_reconstruidos
        and proporcion_finales_reconstruidos
        <= MAX_PROPORCION_FINALES_RECONSTRUIDOS_PARA_REVISION
    )
    observaciones_auxiliares = []
    if columnas_finales_validadas:
        for cuenta in filas_detalle:
            if cuenta.linea not in filas_inconsistentes:
                continue
            v = cuenta.montos_columnas
            neto = v["activo"] + v["perdida"] - v["pasivo"] - v["ganancia"]
            movimiento_respalda = (
                not set(cuenta.columnas_derivadas).intersection({"debitos", "creditos"})
                and abs(v["debitos"] - v["creditos"] - neto) <= tolerancia_absoluta
            )
            observaciones_auxiliares.append({
                "Fila": cuenta.linea,
                "Cuenta": cuenta.nombre,
                "Revisar": "Saldo deudor / Saldo acreedor" if movimiento_respalda else "Debe / Haber",
                "Detalle": (
                    f"Saldo deudor leído: {v['saldo_deudor']:,.0f}; saldo acreedor leído: "
                    f"{v['saldo_acreedor']:,.0f}. El movimiento respalda el importe final "
                    f"de {cuenta.monto:,.0f}; no cambie la columna de clasificación."
                    if movimiento_respalda else
                    f"Debe leído: {v['debitos']:,.0f}; Haber leído: {v['creditos']:,.0f}. "
                    "El saldo respalda el importe final; no cambie la columna de clasificación."
                ),
            })
    diagnostico, senales_diagnostico = _diagnosticar_controles_extraccion(
        tiene_subtotal=True,
        filas_evaluadas=filas,
        filas_inconsistentes=filas_inconsistentes,
        diferencias=diferencias,
        tolerancia=tolerancia_absoluta,
        totales_finales_validos=totales_finales_validos,
        fila_final_incompleta=fila_final_incompleta,
        puente_invalido=puente_invalido,
        ecuacion_subtotal_invalida=ecuacion_subtotal_invalida,
        parcial=parcial,
    )
    return CertificacionExtraccion(
        estado="fallida" if failed else ("parcial" if parcial else "certificada"),
        metodo=metodo,
        totales_impresos={k: float(total_impreso.get(k, 0.0) or 0.0) for k in RAW_MONETARY_COLUMNS},
        totales_calculados={k: round(v, 2) for k, v in calculados.items()},
        diferencias=diferencias,
        razones=razones,
        filas_evaluadas=filas,
        filas_inconsistentes=filas_inconsistentes,
        totales_finales_validos=totales_finales_validos,
        resultado_ejercicio=resultado_ejercicio,
        tipo_resultado=tipo_resultado,
        columnas_total_reconstruidas=columnas_total_reconstruidas,
        columnas_finales_validadas=columnas_finales_validadas,
        reconstrucciones_finales=reconstrucciones_finales,
        proporcion_finales_reconstruidos=proporcion_finales_reconstruidos,
        reconstruccion_final_revisable=reconstruccion_final_revisable,
        observaciones_auxiliares=observaciones_auxiliares,
        diagnostico=diagnostico,
        senales_diagnostico=senales_diagnostico,
        ecuacion_contable_fuente_valida=ecuacion_contable_fuente_valida,
        diferencia_ecuacion_contable_fuente=(
            diferencia_ecuacion_contable_fuente
        ),
    )


def _es_subtotal_fisico_clasificado(
    nombre: str, origen: OrigenColumna,
) -> bool:
    """Reconoce subtotales de una mitad física de balance clasificado."""
    normalizado = re.sub(r"\s+", " ", _sin_acentos(nombre).lower()).strip()
    if origen is OrigenColumna.ACTIVO:
        return normalizado in {
            "total activo circulante",
            "total activos circulantes",
            "total activo corriente",
            "total activos corrientes",
            "total activo fijo",
            "total activos fijos",
            "total activo no corriente",
            "total activos no corrientes",
            "total otros activos",
        }
    if origen is OrigenColumna.PASIVO:
        return normalizado in {
            "total pasivo circulante",
            "total pasivos circulantes",
            "total pasivo corriente",
            "total pasivos corrientes",
            "total pasivo largo plazo",
            "total pasivos largo plazo",
            "total pasivo no corriente",
            "total pasivos no corrientes",
            "total patrimonio",
            "total patrimonio neto",
        }
    return False


def _diferencias_subtotales_fisicos_clasificados(
    cuentas: list[CuentaRaw],
) -> dict[str, float]:
    """Contrasta subtotales por lado cuando OCR observó ACTIVO y PASIVO.

    El orden de lectura alterna filas de ambas mitades. Por ello se acumula
    cada lado de forma independiente, en lugar de sumar las filas intercaladas
    como si fueran una única columna vertical.
    """
    diferencias: dict[str, float] = {}
    for origen in (OrigenColumna.ACTIVO, OrigenColumna.PASIVO):
        subtotal_calculado = 0.0
        detalles = 0
        filas_lado = [
            cuenta for cuenta in cuentas
            if cuenta.origen_columna is origen
        ]
        for cuenta in filas_lado:
            if cuenta.monto is None:
                continue
            if _es_subtotal_fisico_clasificado(cuenta.nombre, origen):
                if detalles:
                    nombre = re.sub(
                        r"\s+", " ", _sin_acentos(cuenta.nombre).lower(),
                    ).strip()
                    diferencias[f"seccion:{origen.value}:{nombre}"] = round(
                        subtotal_calculado - float(cuenta.monto), 2,
                    )
                subtotal_calculado = 0.0
                detalles = 0
                continue
            if cuenta.es_total:
                continue
            subtotal_calculado += float(cuenta.monto)
            detalles += 1
    return diferencias


def _subtotales_fisicos_posiblemente_no_verificables(
    cuentas: list[CuentaRaw], tolerancia_absoluta: float,
) -> set[str]:
    """Señala controles OCR con muchos menos dígitos que su detalle.

    No afirma que el impreso esté tapado o truncado: identifica el patrón en
    que la ecuación final se conserva y un subtotal físico aislado tiene una
    longitud monetaria incompatible con el detalle que pretende controlar.
    Sirve para explicar por qué el documento queda bloqueado, no para reparar
    ni sustituir el subtotal desde la suma.
    """
    no_verificables: set[str] = set()
    for origen in (OrigenColumna.ACTIVO, OrigenColumna.PASIVO):
        acumulado = 0.0
        detalles = 0
        for cuenta in (
            cuenta for cuenta in cuentas if cuenta.origen_columna is origen
        ):
            if cuenta.monto is None:
                continue
            if _es_subtotal_fisico_clasificado(cuenta.nombre, origen):
                diferencia = acumulado - float(cuenta.monto)
                calculado = abs(int(round(acumulado)))
                impreso = abs(int(round(float(cuenta.monto))))
                digitos_calculado = len(str(calculado))
                digitos_impreso = len(str(impreso))
                nombre = re.sub(
                    r"\s+", " ", _sin_acentos(cuenta.nombre).lower(),
                ).strip()
                if (
                    detalles
                    and abs(diferencia) > tolerancia_absoluta
                    and calculado >= 100_000
                    and digitos_impreso + 2 <= digitos_calculado
                ):
                    no_verificables.add(f"seccion:{origen.value}:{nombre}")
                acumulado = 0.0
                detalles = 0
                continue
            if cuenta.es_total:
                continue
            acumulado += float(cuenta.monto)
            detalles += 1
    return no_verificables


def certificar_totales_clasificados(
    cuentas: list[CuentaRaw], tolerancia_absoluta: float = 10.0,
    *, metodo: str = "classified_totals",
) -> CertificacionExtraccion:
    """Control parcial para balances clasificados/IFRS de una o dos columnas.

    Certifica únicamente la ecuación final impresa. No afirma que todas las
    cuentas intermedias estén completas ni correctamente homologadas.
    """
    totals: dict[str, float] = {}
    generic_liability_totals: list[float] = []
    for cuenta in cuentas:
        if cuenta.monto is None:
            continue
        name = re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()
        if name in {"total activos", "total de activos", "total assets"}:
            totals["activo"] = float(cuenta.monto)
        elif name in {
            "total pasivos y patrimonio",
            "total pasivos y patrimonio neto",
            "total pasivo y patrimonio",
            "total patrimonio y pasivos",
            "total de patrimonio y pasivos",
            "total equity and liabilities",
        }:
            totals["pasivo_patrimonio"] = float(cuenta.monto)
        elif name in {"total pasivos", "total de pasivos"}:
            generic_liability_totals.append(float(cuenta.monto))
    if "activo" in totals and "pasivo_patrimonio" not in totals:
        matching_totals = [
            value for value in generic_liability_totals
            if abs(value - totals["activo"]) <= tolerancia_absoluta
        ]
        if matching_totals:
            totals["pasivo_patrimonio"] = matching_totals[-1]
    if set(totals) != {"activo", "pasivo_patrimonio"}:
        return CertificacionExtraccion(
            estado="no_evaluable", metodo=metodo,
            razones=[
                "No se encontraron ambos totales finales del balance clasificado."
            ],
            diagnostico="TOTALES_FINALES_NO_DETECTADOS",
            senales_diagnostico=["TOTALES_FINALES_NO_DETECTADOS"],
        )
    difference = round(totals["activo"] - totals["pasivo_patrimonio"], 2)
    secciones: dict[str, float] = {}
    diferencias_seccion: dict[str, float] = {}
    diferencias_fisicas: dict[str, float] = {}
    subtotales_posiblemente_no_verificables: set[str] = set()
    subtotales_fisicos_validados = False
    nombres = [
        re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()
        for cuenta in cuentas
    ]
    for index, nombre in enumerate(nombres):
        if cuentas[index].es_total or cuentas[index].monto is not None:
            continue
        total_buscado = f"total {nombre}"
        total_index = next(
            (
                candidate for candidate in range(index + 1, len(cuentas))
                if nombres[candidate] == total_buscado
                and cuentas[candidate].es_total
                and cuentas[candidate].monto is not None
            ),
            None,
        )
        if total_index is None:
            continue
        detalle = [
            float(cuenta.monto)
            for cuenta, nombre_detalle in zip(
                cuentas[index + 1:total_index],
                nombres[index + 1:total_index],
            )
            if cuenta.monto is not None
            and (
                not cuenta.es_total
                or re.match(
                    r"^(?:utilidad|perdida|resultado)\s+(?:\(perdida\)\s+)?del\s+ejercicio$",
                    nombre_detalle, re.I,
                )
            )
        ]
        if not detalle:
            continue
        calculado = round(sum(detalle), 2)
        impreso = float(cuentas[total_index].monto or 0.0)
        secciones[nombre] = impreso
        diferencias_seccion[f"seccion:{nombre}"] = round(calculado - impreso, 2)

    secciones_fallidas = {
        nombre: diferencia
        for nombre, diferencia in diferencias_seccion.items()
        if abs(diferencia) > tolerancia_absoluta
    }
    if metodo in {
        "ocr_classified_two_columns",
        "native_classified_two_columns",
    }:
        diferencias_fisicas = _diferencias_subtotales_fisicos_clasificados(
            cuentas,
        )
        subtotales_posiblemente_no_verificables = (
            _subtotales_fisicos_posiblemente_no_verificables(
                cuentas, tolerancia_absoluta,
            )
        )
        # Para habilitar sólo revisión asistida exigimos al menos un subtotal
        # físico reproducido en cada lado. La ecuación final por sí sola no
        # demuestra que el detalle se extrajo completo.
        subtotales_fisicos_validados = (
            any(nombre.startswith("seccion:activo:") for nombre in diferencias_fisicas)
            and any(nombre.startswith("seccion:pasivo:") for nombre in diferencias_fisicas)
        )
        diferencias_seccion.update(diferencias_fisicas)
        secciones_fallidas.update({
            nombre: diferencia
            for nombre, diferencia in diferencias_fisicas.items()
            if abs(diferencia) > tolerancia_absoluta
        })
    if secciones_fallidas:
        detalle = ", ".join(
            f"{nombre.removeprefix('seccion:')}={diferencia:,.0f}"
            for nombre, diferencia in secciones_fallidas.items()
        )
        subtotal_no_verificable = (
            len(secciones_fallidas) == 1
            and abs(difference) <= tolerancia_absoluta
            and next(iter(secciones_fallidas))
            in subtotales_posiblemente_no_verificables
        )
        diagnostico = (
            "SUBTOTAL_IMPRESO_NO_VERIFICABLE"
            if subtotal_no_verificable else "SUBTOTALES_SECCION_NO_CONCILIAN"
        )
        senales = ["SUBTOTALES_SECCION_NO_CONCILIAN"]
        if subtotal_no_verificable:
            senales.insert(0, "SUBTOTAL_IMPRESO_NO_VERIFICABLE")
        if abs(difference) > tolerancia_absoluta:
            senales.append("ECUACION_FINAL_NO_CONCILIA")
        razones = [
            "El detalle extraído no reproduce uno o más subtotales impresos: "
            f"{detalle}."
        ]
        if subtotal_no_verificable:
            razones.append(
                "El subtotal discrepante tiene muchos menos dígitos que su "
                "detalle OCR; no se pudo verificar desde el documento y "
                "permanece bloqueado para revisión del original."
            )
        return CertificacionExtraccion(
            estado="fallida",
            metodo=("classified_section_totals" if metodo == "classified_totals" else metodo),
            totales_impresos={**totals, **{f"seccion:{k}": v for k, v in secciones.items()}},
            diferencias={
                "activo_menos_pasivo_patrimonio": difference,
                **diferencias_seccion,
            },
            razones=razones,
            filas_evaluadas=sum(
                1 for cuenta in cuentas if cuenta.monto is not None and not cuenta.es_total
            ),
            totales_finales_validos=abs(difference) <= tolerancia_absoluta,
            diagnostico=diagnostico,
            senales_diagnostico=senales,
        )
    if abs(difference) > tolerancia_absoluta:
        return CertificacionExtraccion(
            estado="fallida", metodo=metodo,
            totales_impresos=totals,
            diferencias={"activo_menos_pasivo_patrimonio": difference},
            razones=[
                "El total de activos no coincide con el total de pasivos y patrimonio."
            ],
            totales_finales_validos=False,
            diagnostico="ECUACION_FINAL_NO_CONCILIA",
            senales_diagnostico=["ECUACION_FINAL_NO_CONCILIA"],
        )
    return CertificacionExtraccion(
        estado="parcial", metodo=metodo,
        totales_impresos=totals,
        diferencias={
            "activo_menos_pasivo_patrimonio": difference,
            **diferencias_seccion,
        },
        razones=[
            "La ecuación final impresa cuadra"
            + (
                f" y {len(diferencias_seccion)} subtotales de sección fueron reproducidos"
                if diferencias_seccion else ""
            )
            + ", pero la homologación todavía requiere revisión."
        ],
        filas_evaluadas=sum(
            1 for cuenta in cuentas if cuenta.monto is not None and not cuenta.es_total
        ),
        totales_finales_validos=True,
        columnas_finales_validadas=subtotales_fisicos_validados,
        diagnostico="ECUACION_FINAL_VALIDA_CON_REVISION",
        senales_diagnostico=[],
    )


_SECTION_HEADING_PATTERNS: tuple[tuple[re.Pattern, OrigenColumna], ...] = (
    (re.compile(
        r"^(?:total\s+)?(?:activos?(?:\s+(?:corrientes?|no\s+corrientes?|"
        r"circulantes?|fijos?))?|otros\s+activos?|"
        r"(?:non[- ]?current|current)\s+assets?|assets?)$", re.I,
    ),
     OrigenColumna.ACTIVO),
    (re.compile(
        r"^(?:total\s+)?pasivos?(?:\s+(?:corrientes?|no\s+corrientes?|"
        r"circulantes?|a\s+largo\s+plazo))?|"
        r"(?:non[- ]?current|current)\s+liabilities|liabilities$", re.I,
    ),
     OrigenColumna.PASIVO),
    (re.compile(r"^(?:total\s+)?(?:patrimonio(?:\s+neto)?|equity)$", re.I),
     OrigenColumna.PASIVO),
    (re.compile(
        r"^(?:ingresos?|ventas|ganancias?|otros\s+ingresos|incomes?|revenues?)$",
        re.I,
    ),
     OrigenColumna.GANANCIA),
    (re.compile(
        r"^(?:costos?|gastos|egresos?|perdidas?|otros\s+gastos|"
        r"(?:operating|non[- ]?operational)?\s*expenses?)$",
        re.I,
    ),
     OrigenColumna.PERDIDA),
)

_RESULT_SECTION_HEADING_PATTERNS: tuple[tuple[re.Pattern, OrigenColumna], ...] = (
    (re.compile(
        r"\b(?:ingresos?\s+de\s+la\s+explotacion|"
        r"otros\s+ingresos?\s+fuera\s+de\s+la\s+explotacion)\b", re.I,
    ), OrigenColumna.GANANCIA),
    (re.compile(
        r"\b(?:costos?\s+de\s+la\s+explotacion|"
        r"gastos?\s+de\s+administracion(?:\s+y\s+ventas?)?|"
        r"gastos?\s+f\w{0,4}cieros?|"
        r"otros\s+egresos?\s+fuera\s+de\s+la\s+explotacion)\b", re.I,
    ), OrigenColumna.PERDIDA),
)


def _debe_omitir_pagina_formulario_tributario(
    texto: str, formulario_activo: bool,
) -> tuple[bool, bool]:
    """Descarta un Formulario 22 adjunto sin eliminar un balance posterior.

    Algunos PDF escaneados adjuntan la declaración F22 después de las páginas
    financieras. La detección exige el marcador específico de formulario o la
    pareja SII/Año Tributario; si ya se detectó un formulario, sólo conserva una
    página posterior cuando vuelve a encontrar un encabezado financiero.
    """
    normalizado = re.sub(r"\s+", " ", _sin_acentos(texto)).upper()
    es_formulario = bool(
        re.search(r"\bFORM(?:ULARIO)?\.?\s*22\b", normalizado)
        or (
            "SERVICIO DE IMPUESTOS INTERNOS" in normalizado
            and "ANO TRIBUTARIO" in normalizado
        )
        or (
            "REPUBLICA DE CHILE" in normalizado
            and "ANO TRIBUTARIO" in normalizado
            and "IMPUESTOS ANUALES A LA RENTA" in normalizado
        )
    )
    if es_formulario:
        return True, True

    contiene_encabezado_financiero = bool(re.search(
        r"\b(?:BALANCE(?:\s+(?:GENERAL|TRIBUTARIO|CLASIFICADO))?|"
        r"ESTADO\s+DE\s+RESULTADOS?|ACTIVO\s+CIRCULANTE|"
        r"PASIVO\s+CIRCULANTE)\b",
        normalizado,
    ))
    if formulario_activo and not contiene_encabezado_financiero:
        return True, True
    return False, False


def anotar_secciones_balance_clasificado(cuentas: list[CuentaRaw]) -> int:
    """Propaga el encabezado contable a filas de balances clasificados.

    Sólo completa orígenes desconocidos y nunca cambia una columna observada.
    Los encabezados y totales sirven como límites, pero no se convierten en
    cuentas de detalle. Retorna el número de filas enriquecidas.
    """
    seccion: Optional[OrigenColumna] = None
    secciones_paralelas = False
    posiciones_paralelas: dict[int, int] = {}
    detalles_por_linea = Counter(
        cuenta.linea for cuenta in cuentas
        if cuenta.monto is not None and not cuenta.es_total
    )
    anotadas = 0
    for cuenta in cuentas:
        nombre = re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre)).strip(" :")
        if re.search(
            r"^(?:estado(?:s)?\s+de\s+)?(?:flujo(?:s)?\s+de\s+efectivo|"
            r"cambios?\s+en\s+el\s+patrimonio|resultado(?:s)?(?:\s+integrales?)?|"
            r"profit\s+and\s+loss(?:\s+account)?)$",
            nombre, re.I,
        ):
            # Los estados de resultado impresos por varias páginas repiten el
            # título en cada hoja, pero no vuelven a imprimir "Ingreso" o
            # "Egreso" en las continuaciones. Se conserva únicamente una
            # sección de resultado ya establecida; toda otra sección se
            # reinicia para no propagar Activo/Pasivo entre estados distintos.
            if seccion not in {OrigenColumna.GANANCIA, OrigenColumna.PERDIDA}:
                seccion = None
            secciones_paralelas = False
            continue
        if re.match(
            r"^total(?:es)?\s+(?:de\s+)?(?:"
            r"pasivos?\s+y\s+patrimonio(?:\s+neto)?|"
            r"patrimonio\s+y\s+pasivos?|equity\s+and\s+liabilities)$",
            nombre, re.I,
        ):
            seccion = None
            secciones_paralelas = False
            continue
        normalized_english = nombre.replace("-", " ")
        if (
            re.search(r"\bassets?\b", normalized_english, re.I)
            and re.search(r"\b(?:equity|liabilities)\b", normalized_english, re.I)
            and not cuenta.es_total
        ):
            seccion = None
            secciones_paralelas = True
            continue
        encabezado = nombre
        if cuenta.es_total:
            encabezado = re.sub(r"^total(?:es)?\s+", "", nombre, flags=re.I)
        nueva_seccion = None
        for patron, origen in _SECTION_HEADING_PATTERNS:
            if patron.fullmatch(encabezado):
                nueva_seccion = origen
                break
        if nueva_seccion is None:
            for patron, origen in _RESULT_SECTION_HEADING_PATTERNS:
                if patron.search(encabezado):
                    nueva_seccion = origen
                    break
        if nueva_seccion is not None:
            seccion = nueva_seccion
            secciones_paralelas = False
            # Un rótulo puede venir con importe cuando el OCR mezcla subtotal
            # y detalle. Se actualiza la sección, pero esa fila sigue por el
            # flujo de anotación para no perder una cuenta real.
            if cuenta.monto is None:
                continue
        if (
            secciones_paralelas
            and detalles_por_linea[cuenta.linea] == 2
            and cuenta.monto is not None
            and not cuenta.es_total
            and (
                cuenta.origen_columna == OrigenColumna.DESCONOCIDO
                or not cuenta.montos_columnas
            )
        ):
            posicion = posiciones_paralelas.get(cuenta.linea, 0)
            origen = (
                OrigenColumna.ACTIVO if posicion == 0 else OrigenColumna.PASIVO
            )
            posiciones_paralelas[cuenta.linea] = posicion + 1
            if cuenta.origen_columna != origen:
                cuenta.origen_columna = origen
                anotadas += 1
            continue
        if (
            seccion is not None
            and cuenta.monto is not None
            and not cuenta.es_total
            and (
                cuenta.origen_columna == OrigenColumna.DESCONOCIDO
                or not cuenta.montos_columnas
            )
        ):
            if cuenta.origen_columna != seccion:
                cuenta.origen_columna = seccion
                anotadas += 1
    return anotadas


def anotar_estado_financiero(cuentas: list[CuentaRaw]) -> int:
    """Anota el estado financiero desde encabezados explícitos del PDF.

    El etiquetado no clasifica cuentas. Sólo evita que una hoja de estado de
    resultados, adjunta a un estado de situación ya cuadrado, se incorpore por
    segunda vez a la ecuación patrimonial. Si no aparece un título explícito,
    la función deja la cuenta sin contexto salvo en filas geométricas
    ACTIVO/PASIVO, cuya pertenencia al balance de situación es observable.
    """
    estado_actual: Optional[str] = None
    anotadas = 0
    for cuenta in cuentas:
        nombre = re.sub(
            r"\s+", " ", _sin_acentos(cuenta.nombre).lower(),
        ).strip(" :")
        if re.search(
            r"\b(?:estado(?:s)?\s+de\s+resultados?(?:\s+"
            r"(?:integrales?|intermedios?))?|resultados?\s+integrales?)\b",
            nombre,
        ):
            estado_actual = "resultados"
        elif re.search(
            r"\b(?:balance(?:\s+(?:general|clasificado))?|"
            r"estado\s+de\s+situacion(?:\s+financiera)?)\b",
            nombre,
        ):
            estado_actual = "balance"
        elif (
            estado_actual is None
            and cuenta.origen_columna in {
                OrigenColumna.ACTIVO, OrigenColumna.PASIVO,
            }
            and cuenta.monto is not None
        ):
            estado_actual = "balance"

        if (
            estado_actual is not None
            and cuenta.estado_financiero != estado_actual
        ):
            cuenta.estado_financiero = estado_actual
            anotadas += 1
    return anotadas


def fusionar_cuentas_partidas(cuentas: list[CuentaRaw]) -> tuple[list[CuentaRaw], int]:
    """Une una cuenta partida entre la glosa con código y su fila de importes.

    Algunos extractores PDF entregan dos fragmentos de una misma fila física:
    primero ``código + glosa`` y luego la continuación de la glosa junto a las
    ocho columnas. Ambos conservan el mismo número de línea. Sin esta unión, la
    certificación excluye los importes del fragmento sin código y reporta un
    descuadre aunque el documento haya sido leído completo.

    La regla es deliberadamente estricta: mismo número de línea, primer
    fragmento con código pero sin importes y segundo sin código pero con las
    columnas monetarias observadas. No fusiona totales ni filas adyacentes que
    sólo coincidan por proximidad.
    """
    fusionadas: list[CuentaRaw] = []
    cantidad = 0
    indice = 0
    while indice < len(cuentas):
        actual = cuentas[indice]
        siguiente = cuentas[indice + 1] if indice + 1 < len(cuentas) else None
        if (
            siguiente is not None
            and actual.linea == siguiente.linea
            and bool(actual.codigo)
            and not actual.montos_columnas
            and not actual.es_total
            and not siguiente.codigo
            and bool(siguiente.montos_columnas)
        ):
            siguiente.codigo = actual.codigo
            siguiente.nombre = re.sub(
                r"\s+", " ", f"{actual.nombre} {siguiente.nombre}",
            ).strip()
            # Palabras como "PERDIDA" o "GANANCIA" pueden activar el patrón
            # de total en el fragmento aislado. Al quedar unidas a una cuenta
            # codificada de la misma línea, son parte de la glosa de detalle.
            siguiente.es_total = False
            siguiente.confianza_extraccion = min(
                actual.confianza_extraccion,
                siguiente.confianza_extraccion,
            )
            fusionadas.append(siguiente)
            cantidad += 1
            indice += 2
            continue
        fusionadas.append(actual)
        indice += 1
    return fusionadas, cantidad


def fusionar_control_total_general_partido(
    cuentas: list[CuentaRaw],
) -> tuple[list[CuentaRaw], int]:
    """Une las dos mitades complementarias de un control ``TOTAL GENERAL``.

    Ciertos PDF nativos distribuyen el rótulo y los ocho importes de cierre
    en dos líneas físicas consecutivas: ``TOTAL`` contiene las cuatro
    columnas de la izquierda y ``GENERAL`` las cuatro de la derecha. No son
    dos cuentas ni dos controles independientes. La regla exige ese par
    literal, líneas consecutivas y columnas monetarias complementarias; así
    no fusiona glosas ni totales ordinarios por simple proximidad.
    """
    fusionadas: list[CuentaRaw] = []
    cantidad = 0
    indice = 0
    columnas_izquierda = ("debitos", "saldo_deudor", "activo", "perdida")
    columnas_derecha = ("creditos", "saldo_acreedor", "pasivo", "ganancia")

    def _nombre_control(cuenta: CuentaRaw) -> str:
        return re.sub(r"[^a-z0-9]+", "", _sin_acentos(cuenta.nombre).lower())

    def _monto(cuenta: CuentaRaw, columna: str) -> float:
        try:
            return float(cuenta.montos_columnas.get(columna, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    while indice < len(cuentas):
        actual = cuentas[indice]
        siguiente = cuentas[indice + 1] if indice + 1 < len(cuentas) else None
        es_par_total_general = (
            siguiente is not None
            and actual.linea + 1 == siguiente.linea
            and actual.codigo is None
            and siguiente.codigo is None
            and actual.es_total
            and _nombre_control(actual) == "total"
            and _nombre_control(siguiente) in {"general", "generales"}
            and bool(actual.montos_columnas)
            and bool(siguiente.montos_columnas)
            and any(abs(_monto(actual, columna)) > 0.01 for columna in columnas_izquierda)
            and any(abs(_monto(siguiente, columna)) > 0.01 for columna in columnas_derecha)
            and all(abs(_monto(actual, columna)) <= 0.01 for columna in columnas_derecha)
            and all(abs(_monto(siguiente, columna)) <= 0.01 for columna in columnas_izquierda)
        )
        if es_par_total_general:
            montos = {
                columna: _monto(actual, columna) + _monto(siguiente, columna)
                for columna in RAW_MONETARY_COLUMNS
            }
            fusionadas.append(CuentaRaw(
                linea=actual.linea,
                codigo=None,
                nombre="TOTAL GENERAL",
                monto=max((abs(valor) for valor in montos.values()), default=0.0),
                origen_columna=OrigenColumna.DESCONOCIDO,
                es_total=True,
                confianza_extraccion=min(
                    actual.confianza_extraccion, siguiente.confianza_extraccion,
                ),
                montos_columnas=montos,
                montos_periodos={
                    **actual.montos_periodos,
                    **siguiente.montos_periodos,
                },
                columnas_derivadas=[
                    *actual.columnas_derivadas,
                    *siguiente.columnas_derivadas,
                    "control_total_general_fusionado",
                ],
            ))
            cantidad += 1
            indice += 2
            continue
        fusionadas.append(actual)
        indice += 1
    return fusionadas, cantidad


def descartar_pie_no_contable_despues_cierre(
    cuentas: list[CuentaRaw],
) -> tuple[list[CuentaRaw], int]:
    """Descarta ruido OCR sin código que aparece después del cierre final.

    Sólo se aplica después de un control final explícito de ocho columnas. No
    elimina cuentas codificadas ni controles posteriores: el propósito es
    evitar que números de firmas, timbres o QR se presenten como partidas
    monetarias tras ``SUMAS IGUALES``.
    """
    claves_cierre = {
        "totalgeneral", "sumasiguales", "totalesiguales", "sumastotales",
    }

    def clave(cuenta: CuentaRaw) -> str:
        return re.sub(
            r"[^a-z0-9]+", "", _sin_acentos(cuenta.nombre).lower(),
        )

    ultimo_cierre = max(
        (
            indice for indice, cuenta in enumerate(cuentas)
            if cuenta.es_total and clave(cuenta) in claves_cierre
        ),
        default=None,
    )
    if ultimo_cierre is None:
        return cuentas, 0

    filtradas = [
        cuenta for indice, cuenta in enumerate(cuentas)
        if not (
            indice > ultimo_cierre
            and not cuenta.codigo
            and not cuenta.es_total
        )
    ]
    return filtradas, len(cuentas) - len(filtradas)


# ─────────────────────────────────────────────────────────────────────────────
# PARSER DE LÍNEAS DE TEXTO → CUENTAS
# ─────────────────────────────────────────────────────────────────────────────

PATRONES_CODIGO_LINEA = {
    FormatoCodigo.GUION:    re.compile(r'^(\d+(?:-\d+){2,})\s+(.+)'),
    FormatoCodigo.PUNTO:    re.compile(r'^(\d+(?:\.\d+){2,})\s+(.+)'),
    FormatoCodigo.COMPACTO: re.compile(r'^(\d{5,10})\s+(.+)'),
}

# PQ-2 (FG1/FG2) — recuperación de códigos perdidos en documentos SIN_CODIGO.
# Se prueban SOLO después de los tres patrones estándar y SOLO en la rama de
# auto-detección por línea, por lo que no alteran la extracción de documentos
# con formato GUION/PUNTO/COMPACTO detectado. Reutilizan el resto del flujo
# (montos y columnas) aguas abajo en parsear_linea.
#
# FG1 — código con UN solo separador (guión o punto): 4.021201, 201.1205,
# 1101-51. OCR puede fusionar varios grupos a cualquiera de sus lados. La
# glosa debe comenzar por letra, salvo el caso acotado ``1.V.A.``: Tesseract
# suele confundir la I de IVA con 1. No se admite cualquier glosa numérica,
# para no convertir metadatos de período en códigos de cuenta.
_PATRON_AUX_UNISEP = re.compile(
    r'^(\d{1,6}[-.]\d{2,8})\s+('
    r'(?:[A-Za-zÁÉÍÓÚÑáéíóúñ].+)|'
    r'(?:1[.\s]*V[.\s]*A[.\s]+[A-Za-zÁÉÍÓÚÑáéíóúñ].+)'
    r')',
    re.IGNORECASE,
)
# FG2 — código compacto concatenado al nombre sin espacio: 11090BANCO, 10423CTA.
#    El lookahead `(?=[A-Z...])` parte en la frontera dígito → letra y exige que
#    el código sea de 4 a 6 dígitos seguidos inmediatamente por una letra.
_PATRON_AUX_CONCATENADO = re.compile(r'^(\d{4,6})(?=[A-ZÁÉÍÓÚÑ])(.+)')
PATRONES_CODIGO_AUXILIARES = (_PATRON_AUX_UNISEP, _PATRON_AUX_CONCATENADO)
_PATRON_CODIGO_EMBEBIDO_OCR = re.compile(
    r"^[^\d\n]{1,3}(\d{1,2}(?:[.,/:]\d{1,2}){2,4})\s*[-–—−]?\s*(.+)$"
)

# Exige al menos un dígito: una coma o punto aislado puede ser ruido de la
# grilla OCR, pero no representa un importe ni una celda monetaria observada.
PATRON_MONTOS = re.compile(r'(-?\(?(?=[\d.,]*\d)[\d.,]{1,18}\)?)')
_OCR_CERO = re.compile(r'^[oO]$')
_OCR_CERO_EN_CELDA = re.compile(r'^(?:[oO]|[\]\[»«|!lI]{1,3}|[sS][eE][oO])$')


def _es_token_cero_ocr_en_celda(token: str) -> bool:
    """Reconoce únicamente ruido típico de un cero en una celda numérica."""
    return bool(_OCR_CERO_EN_CELDA.fullmatch(token.strip()))


def normalizar_token_ocr(token: str) -> str:
    token = token.strip()
    if _OCR_CERO.match(token):
        return '0'
    # La línea vertical de la grilla puede quedar adherida a un importe OCR
    # (``3.108.206.983|`` o ``|478.724``). Se elimina únicamente cuando el
    # resto del token ya satisface el formato monetario, sin tocar glosas como
    # ``N*15807`` ni símbolos aislados.
    sin_bordes = re.sub(r"^[|!]+|[|!]+$", "", token)
    if sin_bordes != token and PATRON_MONTOS.fullmatch(sin_bordes):
        token = sin_bordes
    # Los dos puntos aparecen como sustituto del punto de miles en escaneos
    # tenues (p. ej. ``3.732:989.407``). Se limita al contexto entre dígitos.
    return re.sub(r"(?<=\d):(?=\d)", ".", token)

PATRON_TOTAL = re.compile(
    r'^(?:total(?:es)?|sub[-\s]?total(?:es)?|sumas?(?: iguales)?)\b|'
    r'^(?:de la p[aá]gina anterior|saldos? anteriores?)\b|'
    r'^(?:resultado(?: del ejercicio| [\x22\x27]?(?:positivo|negativo))?|'
    r'utilidad\s*(?:/|o)\s*perdida|perdida\s*(?:/|o)\s*utilidad|'
    r'utilidad(?: neta| del ejercicio)?|'
    r'perdida(?: o ganancia| neta| neto| del ejercicio)?|'
    r'ganancia(?: neta|(?: del)? ejercicio)|'
    r'(?:patrimonio(?: neto)?|equity) total)$',
    re.IGNORECASE
)


def _normalizar_etiqueta_control_ocr(
    nombre: str,
    celdas: list[Optional[dict[str, Any]]],
) -> str:
    """Canoniza rótulos de control OCR sólo con ocho celdas observadas.

    No completa valores ni intenta corregir glosas de cuentas. Los casos
    cubiertos son pérdidas de un único carácter al inicio de un control y
    ruido de un carácter alrededor del rótulo. Los subtotales y cierres
    requieren las ocho columnas físicas; el puente de utilidad admite celdas
    vacías porque esos ceros suelen no estar impresos.
    """
    celdas_observadas = sum(celda is not None for celda in celdas)
    if len(celdas) != len(RAW_MONETARY_COLUMNS):
        return nombre
    tokens = re.findall(r"[a-z]+", _sin_acentos(nombre).lower())
    if not tokens:
        return nombre
    primero, resto = tokens[0], tokens[1:]
    if (
        celdas_observadas == len(RAW_MONETARY_COLUMNS)
        and primero == "sub"
        and resto
        and resto[0] in {"total", "totales"}
        and all(len(token) == 1 for token in resto[1:])
    ):
        return "SUBTOTAL"
    if (
        celdas_observadas == len(RAW_MONETARY_COLUMNS)
        and primero == "otales"
        and all(len(token) == 1 for token in resto)
    ):
        return "TOTALES"
    # Los puentes de resultado suelen dejar ceros como celdas realmente
    # vacías. Dos importes físicos complementarios más la pérdida de la ``u``
    # inicial o un único glifo final espurio en "utilidad" bastan para
    # reconocer el rótulo, sin asignar ni completar ninguno de los ceros
    # ausentes.
    if (
        celdas_observadas >= 2
        and primero in {"tilidad", "utilidad"}
        and all(len(token) == 1 for token in resto)
    ):
        return "UTILIDAD DEL EJERCICIO"
    if (
        celdas_observadas >= 2
        and tokens[:3] == ["perdida", "del", "ejercicio"]
        and all(len(token) == 1 for token in tokens[3:])
    ):
        return "PERDIDA DEL EJERCICIO"
    return nombre


def _es_control_final_ocho_columnas(
    nombre: str,
    celdas: list[Optional[dict[str, Any]]],
) -> bool:
    """Distingue un cierre final de un subtotal contable intermedio."""
    if len(celdas) != len(RAW_MONETARY_COLUMNS) or not all(celdas):
        return False
    clave = re.sub(r"[^a-z0-9]+", "", _sin_acentos(nombre).lower())
    return clave in {
        "totales", "totalesiguales", "sumasiguales", "sumastotales",
        "totalgeneral",
    }

# ── Filtro de líneas basura (FASE 24B.2) ─────────────────────────────────
# Cada patrón matchea la línea COMPLETA para no filtrar substrings dentro
# de nombres de cuentas contables.

GARBAGE_PATTERNS: list[re.Pattern] = [
    # URLs
    re.compile(r'^https?://\S+$', re.I),
    re.compile(r'^www\.\S+\.\S+$', re.I),
    # Emails
    re.compile(r'^\S+@\S+\.\S+$'),
    # Teléfonos chilenos (+56 9 XXXX XXXX / (2) XXXX XXXX)
    re.compile(r'^\+56[\s-]?\d[\s\d-]{7,}\d$'),
    re.compile(r'^\(\d{1,4}\)[\s-]?\d[\s\d-]{6,}\d$'),
    # RUTs sueltos
    re.compile(r'^\s*\d{1,2}\.\d{3}\.\d{3}[-][0-9kK]\s*$', re.I),
    # Indicadores de página / folio
    re.compile(r'^\s*(?:P[aá]gina|P[aá]g|Pag|Folio|Hoja|N°|No\.?)\s*\d+(?:\s*(?:de|/)\s*\d+)?\s*$', re.I),
    # Etiquetas administrativas de encabezado (RUT, Domicilio, Teléfono, etc.)
    re.compile(r'^\s*(?:RUT|Domicilio|Comuna|Ciudad|Direcci[oó]n|Tel[eé]fono|Email?|Fax)\s*:.*$', re.I),
    re.compile(r'^\s*Fecha\s*(?:de\s*)?(?:emi[só]i[oó]n|creaci[oó]n)\s*:.*$', re.I),
    # Metadatos frecuentes que terminan en un número y parecen una cuenta.
    re.compile(r'^\s*Nivel\s+\d+(?:[.,]\d+)?\s*$', re.I),
    re.compile(r'^\s*Desde\s+\w+\s+(?:a|hasta)\s+\w+\s+\d{4}\s*$', re.I),
    re.compile(r'^\s*(?:19|20)\d{2}\s+(?:19|20)\d{2}\s*$'),
    # Notas al pie
    re.compile(r'^\s*(?:Notas?\s+\d+(?:\s*(?:a|l|y|al)\s*\d+)?|Ver\s+Notas?\s+\d+(?:\s*(?:a|l|y|al)\s*\d+)?)\s*$', re.I),
    re.compile(r'^\s*Art[ií]culo(?:\s+\d+)?\s+C[oó]digo\s+Tributario\b.*$', re.I),
    re.compile(
        r'^.*\bArt[ií]culo(?:\s+\d+)?\s+del\s+C[oó]digo\s+'
        r'Tributario\b.*$',
        re.I,
    ),
    re.compile(r'^\s*con\s+los\s+antecedentes\s+aportados\s+por\s+el\s+Contribuyente\s*$', re.I),
    # Firmas / cargos
    re.compile(r'^\s*(?:Firma|Representante|Contador|Auditor|Revisor|Preparado)\b.*$', re.I),
    # Firmas de auditoría / consultoría
    re.compile(r'^\s*(?:Deloitte|Ernst\s*Young|PwC|Pricewaterhouse(?:Coopers)?|KPMG|BDO|Grant\s*Thornton|Baker\s*Tilly|Mazars)\b.*$', re.I),
    # Líneas decorativas / separadores
    re.compile(r'^[-=*_]{4,}$'),
    re.compile(r'^\s*-\s*\d+\s*-\s*$'),
    # Fechas sueltas (dd de mes de aaaa o dd/mm/aaaa)
    re.compile(r'^\s*\d{1,2}\s*de\s+\w+\s+de\s+\d{4}\s*$', re.I),
    re.compile(r'^\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$'),
]


def _es_linea_basura(linea: str) -> bool:
    """Retorna True si la línea completa es basura (URL, teléfono, encabezado,
    pie de página, dirección, etc.). No filtra cuentas contables porque los
    patrones matchean la totalidad de la línea, no substrings.
    """
    for patron in GARBAGE_PATTERNS:
        if patron.match(linea):
            return True
    return False

# OCR confunde '.' y ',' dentro de códigos de cuenta tipo X.XX.XX.XX,
# produciendo cosas como "1.1.01,01" o "1,1,08,05". Se detecta un prefijo
# de 3-5 grupos cortos de dígitos separados por '.' o ',' al inicio de la
# línea y se normaliza a '.' antes de cualquier otro procesamiento.
PATRON_CODIGO_OCR = re.compile(r'^(\d{1,2}[.,/:]){2,4}\d{1,2}(?=\s)')


def normalizar_codigo_ocr(linea: str) -> str:
    # Separador tipográfico código/glosa, no un signo del importe.
    linea = re.sub(
        r"^(\d{5,10})\s*[·•]\s*(?=[A-Za-zÁÉÍÓÚÑáéíóúñ])", r"\1 ", linea,
    )
    linea = re.sub(r"(?<=\d)[.,/:]{2,}(?=\d)", ".", linea)
    m = PATRON_CODIGO_OCR.match(linea)
    if not m:
        return linea
    codigo_normalizado = (
        m.group(0).replace(',', '.').replace('/', '.').replace(':', '.')
    )
    return codigo_normalizado + linea[m.end():]


_MONTO_AGRUPADO_OCR = re.compile(r"\d{1,3}(?:[.,]\d{3})+")


def _separar_token_montos_concatenados(token: str) -> str:
    """Separa dos importes agrupados que OCR pegó sin espacio intermedio."""
    for indice in range(1, len(token)):
        izquierda, derecha = token[:indice], token[indice:]
        if (
            _MONTO_AGRUPADO_OCR.fullmatch(izquierda)
            and _MONTO_AGRUPADO_OCR.fullmatch(derecha)
        ):
            return f"{izquierda} {derecha}"
    return token


def normalizar_linea_ocr_tabla(linea: str) -> str:
    """Limpia bordes de tabla y separadores confundidos por OCR.

    No reescribe signos contables ni elimina paréntesis; sólo retira caracteres
    de grilla y normaliza comas intercaladas en montos chilenos.
    """
    limpia = re.sub(r"[\[\]|¡]", " ", linea)
    limpia = _normalizar_ruido_terminal_monetario(limpia)
    limpia = " ".join(
        _separar_token_montos_concatenados(token)
        for token in limpia.split()
    )
    limpia = re.sub(r"(?<=\d),(?=\d)", ".", limpia)
    limpia = re.sub(r"(?<=\d):(?=\d)", ".", limpia)
    # Las filas de arrastre acumulado no son cuentas de detalle. En escaneos
    # tenues, ``Anterior`` suele salir como ``Amerior`` o ``Anterlor``; se
    # corrige sólo al inicio de la etiqueta completa, nunca dentro de una
    # glosa ni de un importe.
    limpia = re.sub(
        r"^(de\s+la\s+p[aá]gina)\s+(?:anterior|amerior|anterlor)\b",
        r"\1 Anterior",
        limpia,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", limpia).strip()


_PATRON_PUENTE_RESULTADO = re.compile(
    r"^\W*(?:utilidad\s*(?:/|o)\s*perdida|"
    r"perdida\s*(?:/|o)\s*utilidad|"
    r"utilidad(?:\s+del\s+ejercicio)?|"
    r"ganancia(?:\s+neta|\s+(?:del\s+)?ejercicio)|"
    r"perdida\s+o\s+ganancia|resultado(?:\s+del\s+ejercicio)?)\b",
    re.I,
)

_PATRON_PUENTE_RESULTADO_REPETIDO = re.compile(
    r"(?:utilidad\s*(?:/|o)\s*perdida|"
    r"perdida\s*(?:/|o)\s*utilidad)"
    r"(?:\s+(?:utilidad\s*(?:/|o)\s*perdida|"
    r"perdida\s*(?:/|o)\s*utilidad))*",
    re.I,
)


def _es_etiqueta_total(linea: str) -> bool:
    """Reconoce controles aunque el extractor repita su rótulo lateral.

    La repetición se limita al puente ``Utilidad/Pérdida`` sin código de
    cuenta. No convierte una glosa codificada en control ni completa cifras.
    """
    normalizada = _sin_acentos(re.sub(r"\s+", " ", linea or "")).strip()
    return bool(
        PATRON_TOTAL.match(normalizada)
        or _PATRON_PUENTE_RESULTADO_REPETIDO.fullmatch(normalizada)
    )


def _es_puente_resultado(linea: str) -> bool:
    """Indica si una fila rotulada conecta subtotal y cierre del ejercicio."""
    return bool(_PATRON_PUENTE_RESULTADO.match(
        normalizar_linea_ocr_tabla(linea),
    ))


def _fila_subtotal_anonima(linea: str) -> Optional[str]:
    """Devuelve ocho importes sólo para el subtotal sin texto anclado.

    Una fila puramente numérica no se trata como cuenta. Sólo queda disponible
    para un control cuando la fila siguiente identifica el resultado del
    ejercicio. La función no rellena posiciones ausentes ni deriva importes.
    """
    normalizada = normalizar_linea_ocr_tabla(linea)
    if not normalizada or re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", normalizada):
        return None
    tokens = normalizada.split()
    if len(tokens) != len(RAW_MONETARY_COLUMNS):
        return None
    montos: list[str] = []
    for token in tokens:
        normalizado = normalizar_token_ocr(token).replace("$", "")
        if normalizado == "-":
            normalizado = "0"
        if not PATRON_MONTOS.fullmatch(normalizado):
            return None
        montos.append(normalizado)
    return " ".join(montos)


def etiquetar_subtotales_anonimos(lineas: list[str]) -> list[str]:
    """Conserva subtotales de ocho importes anclados por el cierre inmediato."""
    etiquetadas: list[str] = []
    for indice, linea in enumerate(lineas):
        montos = _fila_subtotal_anonima(linea)
        siguiente = ""
        for candidata in lineas[indice + 1:]:
            if str(candidata).strip():
                siguiente = str(candidata)
                break
        if montos is not None and _es_puente_resultado(siguiente):
            etiquetadas.append(f"SUBTOTAL SIN ETIQUETA {montos}")
        else:
            etiquetadas.append(linea)
    return etiquetadas


def normalizar_montos_fragmentados(linea: str) -> str:
    """Une el primer dígito separado de un importe con miles agrupados.

    Algunos PDF posicionan visualmente el primer dígito en otro fragmento de
    texto (``2 2.029.324,87``). La regla exige al menos dos grupos de miles para
    no unir códigos, años ni columnas contiguas de montos pequeños.
    """
    return re.sub(
        r"(?<![\d.,])(\d)\s+(\d{1,2}(?:[.,]\d{3}){2,}(?:,\d{2})?)",
        r"\1\2",
        linea,
    )


def _metricas_texto_ocr_balance(texto: str) -> dict[str, int]:
    """Mide estructura contable sin depender de una empresa o plantilla."""
    encabezados = 0
    filas_numericas = 0
    filas_ocho_columnas = 0
    controles = 0
    for linea_cruda in texto.splitlines():
        linea = normalizar_linea_ocr_tabla(linea_cruda)
        if not linea:
            continue
        normalizada = _sin_acentos(linea).upper()
        encabezados += sum(
            1 for token in (
                "DEBIT", "CREDIT", "DEBE", "HABER", "DEUDOR", "ACREEDOR",
                "ACTIVO", "PASIVO", "PATRIMONIO", "PERDIDA", "GANANCIA",
            )
            if token in normalizada
        )
        montos = [
            token for token in linea.split()
            if PATRON_MONTOS.fullmatch(normalizar_token_ocr(token).replace("$", ""))
        ]
        if len(montos) >= 2:
            filas_numericas += 1
        if len(montos) >= 8:
            filas_ocho_columnas += 1
        if re.match(r"^(sumas?|subtotales?|resultado|utilidad|totales?)\b", linea, re.I):
            controles += 1
    return {
        "encabezados": encabezados,
        "filas_numericas": filas_numericas,
        "filas_ocho_columnas": filas_ocho_columnas,
        "controles": controles,
    }


def _puntuar_texto_ocr_balance(texto: str) -> int:
    metricas = _metricas_texto_ocr_balance(texto)
    return (
        metricas["encabezados"]
        + 2 * metricas["filas_numericas"]
        + 5 * metricas["filas_ocho_columnas"]
        + 8 * metricas["controles"]
    )


def _ocr_requiere_alternativa(texto: str, es_ultima_pagina: bool) -> bool:
    """Evita un segundo Tesseract salvo que pueda aportar evidencia nueva."""
    metricas = _metricas_texto_ocr_balance(texto)
    if not texto.strip() or metricas["filas_numericas"] == 0:
        return True
    if es_ultima_pagina and metricas["controles"] == 0:
        return True
    if _tabla_ocr_necesita_recuperacion(texto.splitlines()):
        return True
    return metricas["encabezados"] < 2 and metricas["filas_ocho_columnas"] == 0


def _certificar_candidato_textual_ocr(texto: str) -> CertificacionExtraccion:
    """Evalúa un candidato OCR lineal antes de permitir que reemplace otro.

    La comparación de PSM 6 y PSM 4 no puede decidirse por cantidad de texto
    ni por el número de importes detectados. Ambos pueden crecer cuando OCR
    inventa una cifra. Esta función reproduce sólo el tramo pasivo de parseo
    necesario para contrastar las identidades y el subtotal de ocho columnas;
    no clasifica cuentas ni modifica el candidato recibido.

    Es intencionalmente conservadora: una lectura sin controles suficientes
    queda ``no_evaluable`` y no puede desplazar una lectura previa.
    """
    lineas = [
        normalizar_codigo_ocr(normalizar_linea_ocr_tabla(linea))
        for linea in (texto or "").splitlines()
        if linea.strip()
    ]
    lineas = etiquetar_subtotales_anonimos(lineas)
    primeros_tokens = [
        linea.split()[0] if linea.split() else "" for linea in lineas[:60]
    ]
    formato = detectar_formato_codigo(primeros_tokens)
    montos_muestra = [
        monto for linea in lineas[:80] for monto in PATRON_MONTOS.findall(linea)
    ]
    separador = detectar_separador_miles(montos_muestra)
    cuentas = [
        cuenta
        for indice, linea in enumerate(lineas)
        if (
            cuenta := parsear_linea(
                linea, indice, formato, separador, confianza_base=0.75,
            )
        ) is not None
    ]
    cuentas, _ = fusionar_cuentas_partidas(cuentas)
    cuentas, _ = fusionar_control_total_general_partido(cuentas)
    return certificar_extraccion_columnas(
        cuentas, metodo="ocr_text_candidate",
    )


def _candidato_ocr_mejora_certificacion(
    base: CertificacionExtraccion,
    candidato: CertificacionExtraccion,
) -> bool:
    """Acepta sólo una mejora certificable para la entrega o revisión.

    Una alternativa que sigue ``fallida`` puede ser útil para diagnóstico,
    pero no debe reemplazar datos extraídos. La mejora admitida debe elevar el
    estado y terminar en una extracción certificada, o en una parcial cuyas
    columnas finales sí fueron validadas de forma independiente.
    """
    niveles = {
        "no_evaluable": 0,
        "fallida": 1,
        "parcial": 2,
        "certificada": 3,
    }
    nivel_base = niveles.get(str(base.estado), -1)
    nivel_candidato = niveles.get(str(candidato.estado), -1)
    es_apta = (
        candidato.estado == "certificada"
        or (
            candidato.estado == "parcial"
            and candidato.columnas_finales_validadas is True
        )
    )
    return bool(es_apta and nivel_candidato > nivel_base)


def _candidato_geometrico_ocr_mejora_certificacion(
    lineas_base: list[str], lineas_candidatas: list[str],
) -> bool:
    """Autoriza una segunda geometría OCR sólo a nivel documental.

    PSM 6 y PSM 4 pueden repartir correctamente las mismas ocho columnas,
    pero sólo una lectura completa permite validar los subtotales impresos.
    Por eso no se reemplaza una página aislada ni se mezclan sus celdas: la
    alternativa debe certificar el documento entero y mejorar el estado de la
    lectura geométrica ya usada.
    """
    if not lineas_base or not lineas_candidatas:
        return False
    base = _certificar_candidato_textual_ocr("\n".join(lineas_base))
    candidata = _certificar_candidato_textual_ocr("\n".join(lineas_candidatas))
    return _candidato_ocr_mejora_certificacion(base, candidata)


def _combinar_candidatos_ocr(texto_base: str, texto_alternativo: str) -> tuple[str, str]:
    """Selecciona una lectura OCR sólo cuando mejora su certificación.

    Las métricas estructurales reducen las combinaciones que vale la pena
    evaluar, pero no autorizan por sí solas una sustitución. La decisión final
    requiere que el candidato supere la certificación del texto principal.
    """
    if not texto_alternativo.strip():
        return texto_base, "principal"
    controles_alt = []
    for linea in texto_alternativo.splitlines():
        limpia = normalizar_linea_ocr_tabla(linea)
        if re.match(
            r"^(sumas?|subtotales?|resultado|utilidad|"
            r"ganancia(?:\s+(?:del\s+)?ejercicio|\s+neta)|totales?)\b",
            limpia,
            re.I,
        ):
            controles_alt.append(linea)
    # La alternativa siempre se certifica. Una variante mejor puede tener
    # menos tokens numéricos porque descartó ruido OCR; filtrar por volumen
    # antes de mirar los controles volvería a favorecer el texto más largo.
    candidatos: list[tuple[str, str]] = [(texto_alternativo, "tabla")]
    if controles_alt:
        base_sin_controles = []
        for linea in texto_base.splitlines():
            limpia = normalizar_linea_ocr_tabla(linea)
            if not re.match(
                r"^(sumas?|subtotales?|resultado|utilidad|"
                r"ganancia(?:\s+(?:del\s+)?ejercicio|\s+neta)|totales?)\b",
                limpia,
                re.I,
            ):
                base_sin_controles.append(linea)
        candidatos.append(("\n".join(base_sin_controles + controles_alt), "fusion"))

    if not candidatos:
        return texto_base, "principal"
    certificacion_base = _certificar_candidato_textual_ocr(texto_base)
    for candidato, estrategia in candidatos:
        certificacion_candidata = _certificar_candidato_textual_ocr(candidato)
        if _candidato_ocr_mejora_certificacion(
            certificacion_base, certificacion_candidata,
        ):
            return candidato, estrategia
    return texto_base, "principal"


def parsear_linea(
    linea: str,
    numero_linea: int,
    formato_codigo: FormatoCodigo,
    separador_miles: str,
    confianza_base: float = 1.0,
    column_order: Optional[list[OrigenColumna]] = None,
    periodo_comparativo: bool = False,
    years: Optional[list[str]] = None,
    currencies: Optional[list[str]] = None,
) -> Optional[CuentaRaw]:
    linea = _normalizar_ruido_terminal_monetario(linea).strip()
    if len(linea) < 4:
        return None

    if _es_linea_basura(linea):
        return None

    codigo = None
    resto = linea
    linea_para_total = re.sub(r"^[^\w]+", "", linea).strip()
    if confianza_base < 1.0:
        # En impresos tenues Tesseract confunde con frecuencia la T inicial y
        # lee ``TOTAL`` como ``FORAL``. Sólo se normaliza al evaluar controles
        # OCR; una cuenta nativa conserva siempre su nombre literal.
        linea_para_total = re.sub(
            r"^foral\b", "total", linea_para_total, flags=re.I,
        )

    # Los totales impresos no llevan código. Evita interpretar su primer monto
    # (p. ej. 72.911.536.017) como un código de formato PUNTO.
    if _es_etiqueta_total(linea_para_total):
        resto = linea_para_total
    elif formato_codigo != FormatoCodigo.SIN_CODIGO:
        patron = PATRONES_CODIGO_LINEA[formato_codigo]
        m = patron.match(linea)
        if m:
            codigo = m.group(1)
            resto = m.group(2)
        else:
            # OCR puede perder todos los separadores de una cuenta puntual
            # (1.01.01.01 -> 1010101). Recuperar el formato alternativo evita
            # que el código quede incorporado al nombre y bloquee el matching.
            for fmt, patron_alternativo in PATRONES_CODIGO_LINEA.items():
                if fmt == formato_codigo:
                    continue
                m = patron_alternativo.match(linea)
                if m:
                    codigo = m.group(1)
                    resto = m.group(2)
                    break
            if codigo is None:
                for patron_auxiliar in PATRONES_CODIGO_AUXILIARES:
                    m = patron_auxiliar.match(linea)
                    if m:
                        codigo = m.group(1)
                        resto = m.group(2)
                        break
    else:
        for fmt in (FormatoCodigo.PUNTO, FormatoCodigo.GUION, FormatoCodigo.COMPACTO):
            m = PATRONES_CODIGO_LINEA[fmt].match(linea)
            if m:
                codigo = m.group(1)
                resto = m.group(2)
                break
        # PQ-2 (FG1/FG2): códigos con un solo separador o compactos concatenados
        # al nombre. Solo si ninguno de los patrones estándar coincidió (no
        # altera documentos con formato ya detectado).
        if codigo is None:
            for patron in PATRONES_CODIGO_AUXILIARES:
                m = patron.match(linea)
                if m:
                    codigo = m.group(1)
                    resto = m.group(2)
                    break

    if codigo is None and confianza_base < 1.0:
        embedded = _PATRON_CODIGO_EMBEBIDO_OCR.match(resto)
        if embedded:
            codigo = re.sub(r"[.,/:]", ".", embedded.group(1))
            resto = embedded.group(2)

    tokens = resto.split()
    descartados_finales = 0
    while tokens and descartados_finales < 2 and \
            normalizar_token_ocr(tokens[-1]) != '0' and \
            not re.search(r'\d', tokens[-1]) and len(tokens[-1]) <= 2:
        tokens.pop()
        descartados_finales += 1

    montos_tokens = []
    i = len(tokens) - 1
    while i >= 0 and len(montos_tokens) < 8:
        tok_norm = normalizar_token_ocr(tokens[i])
        if tok_norm == '-':
            montos_tokens.insert(0, '0')
            i -= 1
        elif PATRON_MONTOS.fullmatch(tok_norm.replace('$', '')):
            montos_tokens.insert(0, tok_norm.replace('$', ''))
            i -= 1
        elif montos_tokens and len(tok_norm) <= 2 and not re.search(r'\d', tok_norm):
            # En tablas de ocho columnas Tesseract ocasionalmente convierte
            # un cero intermedio en ruido breve (p. ej. ``ly``). Una vez
            # iniciada la cola numérica se conserva la posición como cero.
            montos_tokens.insert(0, '0')
            i -= 1
        else:
            break

    nombre_tokens = tokens[:i + 1]
    # La raya visual entre codigo y descripcion no forma parte de la cuenta.
    nombre = ' '.join(nombre_tokens).strip(' .-–—−')

    if not nombre or len(nombre) < 3:
        return None

    nombre_para_total = re.sub(r"^[^\w]+", "", nombre).strip()
    es_total = codigo is None and _es_etiqueta_total(nombre_para_total)

    # Determinar orden de columnas: si ENABLE_DYNAMIC_LAYOUT está activo
    # y se proporcionó un column_order con confianza suficiente, usarlo.
    # Fallback: heurística actual (últimas 4 columnas = Activo/Pasivo/Pérdida/Ganancia).
    if column_order and ENABLE_DYNAMIC_LAYOUT:
        columnas = column_order
    else:
        columnas = [OrigenColumna.ACTIVO, OrigenColumna.PASIVO,
                    OrigenColumna.PERDIDA, OrigenColumna.GANANCIA]

    n_col = len(columnas)
    monto_principal = None
    origen = OrigenColumna.DESCONOCIDO
    montos_periodos: dict[str, float] = {}

    # Dynamic year/currency mapping
    if (years or currencies) and montos_tokens:
        n_vals = len(montos_tokens)
        active_years = years if years else []
        active_currencies = currencies if currencies else []

        # Determine if we map primarily by currencies or by years
        if len(active_currencies) >= 2:
            # Map columns to currencies
            for idx, curr in enumerate(active_currencies[:n_vals]):
                val = parsear_monto(montos_tokens[idx], separador_miles)
                if val is not None:
                    val_f = float(val)
                    montos_periodos[curr] = val_f
                    # Also map with year if we have a year
                    if len(active_years) >= 1:
                        montos_periodos[f"{active_years[0]}_{curr}"] = val_f
            main_curr = "CLP" if "CLP" in montos_periodos else active_currencies[0]
            monto_principal = montos_periodos.get(main_curr)
        else:
            # Map columns to years
            for idx, yr in enumerate(active_years[:n_vals]):
                val = parsear_monto(montos_tokens[idx], separador_miles)
                if val is not None:
                    val_f = float(val)
                    montos_periodos[yr] = val_f
                    # If we have a single currency (e.g. USD), also map it
                    if len(active_currencies) == 1:
                        curr = active_currencies[0]
                        montos_periodos[f"{yr}_{curr}"] = val_f
                        montos_periodos[curr] = val_f

            if "actual" not in montos_periodos and len(active_years) >= 1:
                montos_periodos["actual"] = montos_periodos.get(active_years[0], 0.0)
            if "anterior" not in montos_periodos and len(active_years) >= 2:
                montos_periodos["anterior"] = montos_periodos.get(active_years[1], 0.0)
            monto_principal = montos_periodos.get("actual")

            # If single currency and we have actual/anterior, populate them too
            if len(active_currencies) == 1:
                curr = active_currencies[0]
                if "actual" in montos_periodos:
                    montos_periodos[f"actual_{curr}"] = montos_periodos["actual"]
                if "anterior" in montos_periodos:
                    montos_periodos[f"anterior_{curr}"] = montos_periodos["anterior"]
                if monto_principal is not None:
                    montos_periodos[curr] = monto_principal

    if periodo_comparativo and len(montos_tokens) >= 3 and re.fullmatch(
        r"\d{1,2}(?:\.\d{1,2}){2,}", montos_tokens[-1],
    ):
        # Referencia de nota (6.1.2, 12.3.1), no un tercer período monetario.
        montos_tokens.pop()

    if not montos_periodos and periodo_comparativo and len(montos_tokens) >= 2:
        actual_token, anterior_token = montos_tokens[-2:]
        actual = float(parsear_monto(actual_token, separador_miles) or 0.0)
        anterior = float(parsear_monto(anterior_token, separador_miles) or 0.0)
        montos_periodos = {"actual": actual, "anterior": anterior}
        monto_principal = actual

    if montos_tokens and not montos_periodos:
        n = len(montos_tokens)
        k = min(n_col, n)
        cola = montos_tokens[-k:]
        etiquetas = columnas[-k:]

        for tok, et in zip(cola, etiquetas):
            val = parsear_monto(tok, separador_miles)
            if val is not None and val != 0:
                monto_principal = val
                origen = et
                break

        if monto_principal is None:
            monto_principal = parsear_monto(cola[0], separador_miles)
            origen = etiquetas[0]

    montos_columnas: dict[str, float] = {}
    columnas_derivadas: list[str] = []
    if len(montos_tokens) == len(RAW_MONETARY_COLUMNS):
        for column, token in zip(RAW_MONETARY_COLUMNS, montos_tokens):
            montos_columnas[column] = float(parsear_monto(token, separador_miles) or 0.0)
        if confianza_base < 1.0:
            def error_identidades(values: dict[str, float]) -> float:
                return abs(
                    (values["debitos"] - values["creditos"])
                    - (values["saldo_deudor"] - values["saldo_acreedor"])
                ) + abs(
                    values["saldo_deudor"] + values["saldo_acreedor"]
                    - values["activo"] - values["pasivo"]
                    - values["perdida"] - values["ganancia"]
                )

            # En OCR de tablas, un cero aislado se confunde con mucha
            # frecuencia con 2, 3, 5, 6 o 9. Sólo se corrige cuando eliminar
            # ese dígito mejora estrictamente las dos identidades contables;
            # nunca se aplica a extracción nativa ni a importes mayores.
            for column in RAW_MONETARY_COLUMNS:
                if not 0 < abs(montos_columnas[column]) <= 10:
                    continue
                error_antes = error_identidades(montos_columnas)
                candidato = dict(montos_columnas)
                candidato[column] = 0.0
                if error_identidades(candidato) < error_antes:
                    montos_columnas[column] = 0.0
                    columnas_derivadas.append(column)

            # Tesseract también puede depositar una marca marginal o parte del
            # RUT en una segunda columna de clasificación (por ejemplo 7.669
            # en Ganancias cuando el saldo completo ya está en Pérdidas). Se
            # elimina sólo una segunda clasificación pequeña cuando al hacerlo
            # ambas identidades quedan exactas. La cuenta de importe pequeño
            # legítimo se conserva porque quitar su única clasificación
            # empeoraría, en vez de mejorar, la identidad saldo-clasificación.
            debtor_total = abs(montos_columnas["saldo_deudor"]) + abs(
                montos_columnas["saldo_acreedor"]
            )
            classification_noise_limit = max(10_000.0, debtor_total * 0.01)
            nonzero_classifications = [
                column for column in ("activo", "pasivo", "perdida", "ganancia")
                if montos_columnas[column] != 0
            ]
            if len(nonzero_classifications) >= 2:
                for column in nonzero_classifications:
                    value = montos_columnas[column]
                    if abs(value) > classification_noise_limit:
                        continue
                    error_antes = error_identidades(montos_columnas)
                    candidato = dict(montos_columnas)
                    candidato[column] = 0.0
                    error_despues = error_identidades(candidato)
                    if error_despues <= 10 and error_despues < error_antes:
                        montos_columnas[column] = 0.0
                        columnas_derivadas.append(column)
                        break

            # Si movimiento y clasificación repiten exactamente el mismo
            # importe unilateral, ambos son evidencia independiente frente a
            # un saldo OCR discrepante. Se corrige sólo esa tercera copia y
            # únicamente en documentos OCR.
            classification_total = sum(
                montos_columnas[column]
                for column in ("activo", "pasivo", "perdida", "ganancia")
            )
            if (
                montos_columnas["creditos"] == 0
                and montos_columnas["saldo_acreedor"] == 0
                and montos_columnas["debitos"] > 0
                and montos_columnas["debitos"] == classification_total
                and montos_columnas["saldo_deudor"] != montos_columnas["debitos"]
            ):
                montos_columnas["saldo_deudor"] = montos_columnas["debitos"]
                columnas_derivadas.append("saldo_deudor")
            elif (
                montos_columnas["debitos"] == 0
                and montos_columnas["saldo_deudor"] == 0
                and montos_columnas["creditos"] > 0
                and montos_columnas["creditos"] == classification_total
                and montos_columnas["saldo_acreedor"] != montos_columnas["creditos"]
            ):
                montos_columnas["saldo_acreedor"] = montos_columnas["creditos"]
                columnas_derivadas.append("saldo_acreedor")

            # Cuando OCR pierde la repetición del saldo en las columnas de
            # clasificación, se recupera únicamente si hay un saldo unilateral
            # y el primer dígito del código entrega una naturaleza coherente.
            # El signo del saldo conserva las contra-cuentas: un código de
            # activo con saldo acreedor se observa en Pasivo, no en Activo.
            classified_sum = sum(
                montos_columnas[column]
                for column in ("activo", "pasivo", "perdida", "ganancia")
            )
            debtor_value = montos_columnas["saldo_deudor"]
            creditor_value = montos_columnas["saldo_acreedor"]
            code_prefix = re.sub(r"\D", "", codigo or "")[:1]
            if (
                classified_sum == 0
                and bool(code_prefix)
                and (debtor_value == 0) != (creditor_value == 0)
            ):
                if code_prefix in {"1", "2"}:
                    target = "activo" if debtor_value else "pasivo"
                elif code_prefix in {"3", "4"}:
                    target = "perdida" if debtor_value else "ganancia"
                else:
                    target = ""
                if target:
                    montos_columnas[target] = debtor_value or creditor_value
                    columnas_derivadas.append(target)
        debit = montos_columnas["debitos"]
        credit = montos_columnas["creditos"]
        debtor = montos_columnas["saldo_deudor"]
        creditor = montos_columnas["saldo_acreedor"]
        classified = (
            montos_columnas["activo"] + montos_columnas["pasivo"]
            + montos_columnas["perdida"] + montos_columnas["ganancia"]
        )
        balance = debtor - creditor
        classification_consistent = abs(debtor + creditor - classified) <= 10
        movement_consistent = abs(debit - credit - balance) <= 10
        movement_is_implausible = abs(debit - credit) > max(
            abs(balance) * 10, abs(balance) + 1000,
        )
        if classification_consistent and not movement_consistent:
            phantom_limit = max(10_000.0, max(abs(debit), abs(credit)) * 0.01)
            if (
                confianza_base < 1.0 and credit == 0 and creditor == 0
                and debtor > 0 and debit != debtor
            ):
                # Saldo deudor y clasificación repiten el mismo importe; si
                # Crédito es cero, esa evidencia redundante permite corregir
                # con seguridad un dígito omitido en Débito.
                montos_columnas["debitos"] = debtor
                columnas_derivadas.append("debitos")
            elif (
                confianza_base < 1.0 and debit == 0 and debtor == 0
                and creditor > 0 and credit != creditor
            ):
                montos_columnas["creditos"] = creditor
                columnas_derivadas.append("creditos")
            elif (
                confianza_base < 1.0 and balance == 0
                and debit > 0 and credit > 0 and debit != credit
                and (
                    str(int(round(max(debit, credit)))).endswith(
                        str(int(round(min(debit, credit))))
                    )
                    and max(debit, credit) >= min(debit, credit) * 10
                )
            ):
                # Un trazo de la columna o del código puede anteponerse al
                # primer movimiento (1.866.316 -> 121.866.316). Con saldo cero
                # Debe y Haber deben ser iguales; el sufijo completo aporta la
                # corrección sin adivinar dígitos internos.
                if debit > credit:
                    montos_columnas["debitos"] = credit
                    columnas_derivadas.append("debitos")
                else:
                    montos_columnas["creditos"] = debit
                    columnas_derivadas.append("creditos")
            elif debit == 0 and credit == 0 and debtor != 0 and creditor == 0:
                montos_columnas["debitos"] = debtor
                columnas_derivadas.append("debitos")
            elif debit == 0 and credit == 0 and creditor != 0 and debtor == 0:
                montos_columnas["creditos"] = creditor
                columnas_derivadas.append("creditos")
            elif (
                debtor == 0 and abs(credit - creditor) <= 10
                and 0 < abs(debit) <= phantom_limit
            ):
                montos_columnas["debitos"] = 0.0
                columnas_derivadas.append("debitos")
            elif (
                creditor == 0 and abs(debit - debtor) <= 10
                and 0 < abs(credit) <= phantom_limit
            ):
                montos_columnas["creditos"] = 0.0
                columnas_derivadas.append("creditos")
            elif movement_is_implausible and credit == 0 and balance >= 0:
                montos_columnas["debitos"] = balance
                columnas_derivadas.append("debitos")
            elif movement_is_implausible and debit == 0 and balance < 0:
                montos_columnas["creditos"] = -balance
                columnas_derivadas.append("creditos")
            elif (
                debit == 0 and creditor == 0
                and credit > 0 and abs(credit - debtor) <= 10
            ):
                montos_columnas["debitos"] = credit
                montos_columnas["creditos"] = 0.0
                columnas_derivadas.extend(["debitos", "creditos"])
            elif (
                credit == 0 and debtor == 0
                and debit > 0 and abs(debit - creditor) <= 10
            ):
                montos_columnas["creditos"] = debit
                montos_columnas["debitos"] = 0.0
                columnas_derivadas.extend(["debitos", "creditos"])
            elif (
                debit == 0 and creditor == 0 and debtor > 0
                and abs(credit - debtor * 10) <= 10
            ):
                # OCR puede anexar el cero de la celda Crédito al monto de
                # Débito (936.090 + 0 -> 9.360.900) y dejar la primera celda
                # vacía. El saldo deudor independiente permite repararlo.
                montos_columnas["debitos"] = debtor
                montos_columnas["creditos"] = 0.0
                columnas_derivadas.extend(["debitos", "creditos"])
            elif (
                credit == 0 and debtor == 0 and creditor > 0
                and abs(debit - creditor * 10) <= 10
            ):
                montos_columnas["creditos"] = creditor
                montos_columnas["debitos"] = 0.0
                columnas_derivadas.extend(["debitos", "creditos"])
            elif movement_is_implausible:
                expected_debit = credit + balance
                expected_credit = debit - balance
                if (
                    expected_debit >= 0
                    and abs(debit) > max(1_000_000_000, abs(expected_debit) * 100)
                ):
                    montos_columnas["debitos"] = expected_debit
                    columnas_derivadas.append("debitos")
                elif (
                    expected_credit >= 0
                    and abs(credit) > max(1_000_000_000, abs(expected_credit) * 100)
                ):
                    montos_columnas["creditos"] = expected_credit
                    columnas_derivadas.append("creditos")

        # En una fila OCR completa, Debe-Haber y el saldo pueden coincidir
        # entre sí aunque la única copia de la columna final tenga un dígito
        # errado. No se mueve el importe entre naturaleza de cuenta: sólo se
        # corrige el valor de la misma celda final cuando su lado (deudor o
        # acreedor) ya coincide con la evidencia independiente. La marca
        # derivada mantiene el documento fuera de la entrega automática.
        if (
            confianza_base < 1.0
            and movement_consistent
            and not classification_consistent
            and (debtor == 0) != (creditor == 0)
        ):
            final_columns = (
                ("activo", "perdida") if debtor else ("pasivo", "ganancia")
            )
            populated = [
                column for column in final_columns
                if montos_columnas[column] != 0
            ]
            expected = debtor or creditor
            if (
                len(populated) == 1
                and abs(montos_columnas[populated[0]] - expected) > 10
            ):
                target = populated[0]
                montos_columnas[target] = expected
                columnas_derivadas.append(target)
        if es_total and debit == credit and debit != 0:
            if debtor == 0 and creditor != 0:
                montos_columnas["saldo_deudor"] = creditor
                columnas_derivadas.append("saldo_deudor")
            elif creditor == 0 and debtor != 0:
                montos_columnas["saldo_acreedor"] = debtor
                columnas_derivadas.append("saldo_acreedor")
        # Las ocho columnas son evidencia más fuerte que años o monedas
        # detectados en la cabecera. Si exactamente una columna de
        # clasificación contiene saldo, esa columna define tanto el importe
        # homologable como su origen físico. Esto evita que una fecha del
        # documento deje la cuenta como DESCONOCIDO y conserve por error el
        # débito o crédito acumulado como monto principal.
        origin_by_column = {
            "activo": OrigenColumna.ACTIVO,
            "pasivo": OrigenColumna.PASIVO,
            "perdida": OrigenColumna.PERDIDA,
            "ganancia": OrigenColumna.GANANCIA,
        }
        classified_values = [
            (column, montos_columnas[column])
            for column in origin_by_column
            if montos_columnas[column] != 0
        ]
        if len(classified_values) == 1:
            column, value = classified_values[0]
            origen = origin_by_column[column]
            monto_principal = value
        elif not classified_values:
            # Una fila con Debe y Haber iguales puede tener movimiento
            # histórico, pero sin saldo final no representa una cifra vigente
            # que deba entrar a la homologación. Esta evidencia de las ocho
            # columnas prevalece sobre un año detectado en la cabecera.
            monto_principal = 0.0
            origen = OrigenColumna.DESCONOCIDO
    return CuentaRaw(
        linea=numero_linea,
        codigo=codigo,
        nombre=nombre,
        monto=monto_principal,
        origen_columna=origen,
        es_total=es_total,
        confianza_extraccion=confianza_base,
        montos_columnas=montos_columnas,
        montos_periodos=montos_periodos,
        columnas_derivadas=columnas_derivadas,
    )


def _entero_monetario_focal(token: str) -> Optional[float]:
    """Normaliza una lectura focal de una celda monetaria a entero.

    Esta vía recibe sólo Tesseract con whitelist numérica. Se interpreta como
    entero porque las ocho columnas tributarias expresan importes enteros y
    porque la puntuación de miles puede variar entre dos lecturas del mismo
    recorte (``206.182`` versus ``206,182``).
    """
    bruto = str(token or "").strip().replace("O", "0").replace("o", "0")
    if not bruto:
        return None
    # En una celda monetaria aislada el guion es la convención impresa para
    # cero. Se acepta sólo en esta relectura focal, que de todos modos necesita
    # consenso OCR y mejora de identidades antes de modificar una fila.
    if bruto in {"-", "—", "−"}:
        return 0.0
    negativo = bruto.startswith("-") or (
        bruto.startswith("(") and bruto.endswith(")")
    )
    digitos = re.sub(r"\D", "", bruto)
    if not digitos:
        return None
    valor = float(int(digitos))
    return -valor if negativo else valor


def _difiere_hasta_n_digitos_monetarios(
    original: str, releido: float, max_edits: int,
) -> bool:
    """Mide una distancia de edición acotada entre dos lecturas monetarias."""
    base = re.sub(r"\D", "", str(original or ""))
    candidato = str(abs(int(round(float(releido)))))
    if not base or max_edits < 1 or abs(len(base) - len(candidato)) > max_edits:
        return False
    anterior = list(range(len(candidato) + 1))
    for indice_base, digito_base in enumerate(base, start=1):
        actual = [indice_base]
        for indice_candidato, digito_candidato in enumerate(candidato, start=1):
            actual.append(min(
                anterior[indice_candidato] + 1,
                actual[indice_candidato - 1] + 1,
                anterior[indice_candidato - 1]
                + (digito_base != digito_candidato),
            ))
        if min(actual) > max_edits:
            return False
        anterior = actual
    return anterior[-1] <= max_edits


def _difiere_un_digito_monetario(original: str, releido: float) -> bool:
    """Acepta un único error OCR de sustitución, inserción o eliminación."""
    return _difiere_hasta_n_digitos_monetarios(original, releido, max_edits=1)


def _formatear_entero_monetario_focal(valor: float, original: str) -> str:
    """Conserva el estilo de separador de la línea canónica de origen."""
    entero = int(round(abs(float(valor))))
    if "." in original:
        texto = f"{entero:,}".replace(",", ".")
    elif "," in original:
        texto = f"{entero:,}"
    else:
        texto = str(entero)
    return f"-{texto}" if float(valor) < 0 else texto


def _releer_celda_ocr_focal(
    celda: dict[str, Any], cache_imagenes: dict[tuple[str, int], Image.Image],
    *, preservar_escala: bool = False,
) -> Optional[float]:
    """Lee una celda OCR con varias binarizaciones y exige consenso exacto.

    No retorna una cifra cuando no existe caja geométrica, el recorte no se
    puede leer o las dos variantes no coinciden. Es una fuente de evidencia,
    no una reconstrucción aritmética. ``preservar_escala`` se usa sólo como
    segunda lectura: algunos 6/8 de impresión pequeña se degradan al ampliar
    un recorte antes de binarizarlo.
    """
    bbox = celda.get("bbox")
    image_path = celda.get("imagen")
    rotacion = int(celda.get("rotacion", 0) or 0)
    if not bbox or not image_path:
        return None
    key = (str(image_path), rotacion)
    try:
        if key not in cache_imagenes:
            with Image.open(image_path) as original:
                preparada = (
                    original.rotate(rotacion, expand=True)
                    if rotacion else original.copy()
                )
                cache_imagenes[key] = preparada.convert("L")
        imagen = cache_imagenes[key]
        x0, y0, x1, y1 = (float(valor) for valor in bbox)
        izquierda = max(0, int(math.floor(x0)) - OCR_CELL_PADDING_PIXELS)
        arriba = max(0, int(math.floor(y0)) - OCR_CELL_PADDING_PIXELS)
        derecha = min(imagen.width, int(math.ceil(x1)) + OCR_CELL_PADDING_PIXELS)
        abajo = min(imagen.height, int(math.ceil(y1)) + OCR_CELL_PADDING_PIXELS)
        if derecha <= izquierda or abajo <= arriba:
            return None
        recorte = imagen.crop((izquierda, arriba, derecha, abajo))
        if not preservar_escala and recorte.height < OCR_CELL_MIN_HEIGHT_PIXELS:
            escala = min(
                OCR_CELL_MAX_UPSCALE,
                OCR_CELL_MIN_HEIGHT_PIXELS / max(recorte.height, 1),
            )
            recorte = recorte.resize(
                (
                    max(1, int(round(recorte.width * escala))),
                    max(1, int(round(recorte.height * escala))),
                ),
                Image.Resampling.LANCZOS,
            )
    except (OSError, ValueError):
        return None

    lecturas: list[float] = []

    def leer_umbral(umbral: int) -> Optional[float]:
        binaria = recorte.point(lambda pixel, limite=umbral: 255 if pixel > limite else 0)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temporal:
            binaria.save(temporal.name)
            temporal_path = Path(temporal.name)
        try:
            resultado = _ejecutar_tesseract_imagen(
                temporal_path,
                "stdout",
                [
                    "-l", "spa", "--psm", "7", "-c",
                    "tessedit_char_whitelist=0123456789.,()-",
                ],
                timeout=OCR_CELL_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        finally:
            temporal_path.unlink(missing_ok=True)
        if resultado.returncode != 0:
            return None
        return _entero_monetario_focal(resultado.stdout)

    for umbral in OCR_CELL_THRESHOLDS:
        valor = leer_umbral(umbral)
        if valor is not None:
            lecturas.append(valor)
    if len(lecturas) == len(OCR_CELL_THRESHOLDS) and len(set(lecturas)) == 1:
        return lecturas[0]

    # Si los dos umbrales bajos no vieron ningún trazo, 140/180 suele repetir
    # el vacío de una celda tenue. Se prueba directamente un par alto. Cuando
    # sí existe una lectura primaria, se conserva el desempate intermedio.
    sin_lecturas_primarias = not lecturas
    umbrales_rescate = (
        OCR_CELL_EMPTY_PRIMARY_THRESHOLDS
        if sin_lecturas_primarias
        else OCR_CELL_TIEBREAK_THRESHOLDS
    )
    # Un desempate se permite sólo cuando dos umbrales independientes
    # convergen exactamente; nunca se elige el valor de un único umbral ni se
    # reconstruye desde un control.
    for umbral in umbrales_rescate:
        valor = leer_umbral(umbral)
        if valor is not None:
            lecturas.append(valor)
    # Una celda muy tenue puede leerse como 6 con 200 y como 0 con 220. El
    # umbral central no escoge entre ellos por sí solo: sólo añade evidencia
    # cuando reproduce exactamente una de las dos lecturas de rescate.
    if (
        sin_lecturas_primarias
        and lecturas
        and max(Counter(lecturas).values()) < 2
    ):
        valor = leer_umbral(OCR_CELL_EMPTY_PRIMARY_TIEBREAK_THRESHOLD)
        if valor is not None:
            lecturas.append(valor)
    coincidencias = Counter(lecturas)
    if not coincidencias:
        return None
    valor, repeticiones = coincidencias.most_common(1)[0]
    if repeticiones < 2 or sum(
        cantidad == repeticiones for cantidad in coincidencias.values()
    ) > 1:
        return None
    return valor


def _lecturas_importe_clasificado_ocr(
    evidencia: Optional[dict[str, Any]],
    cache_imagenes: dict[tuple[str, int], Image.Image],
) -> set[float]:
    """Devuelve lecturas focales consensuadas para un importe clasificado.

    La salida TSV y el OCR lineal pueden discrepar incluso con el mismo PSM.
    Se prueba primero la escala nativa, luego el recorte ampliado habitual y,
    si la caja OCR cortó un borde de un dígito, un margen horizontal adicional
    de ocho píxeles. Cada valor devuelto ya superó el consenso interno de
    ``_releer_celda_ocr_focal``. Esta función no escoge entre alternativas.
    """
    if not evidencia or not evidencia.get("bbox"):
        return set()

    lecturas: set[float] = set()

    def registrar(celda: dict[str, Any], *, preservar_escala: bool) -> None:
        lectura = _releer_celda_ocr_focal(
            celda, cache_imagenes, preservar_escala=preservar_escala,
        )
        if lectura is not None:
            lecturas.add(float(lectura))

    registrar(evidencia, preservar_escala=True)
    registrar(evidencia, preservar_escala=False)

    try:
        x0, y0, x1, y1 = (
            float(value) for value in evidencia["bbox"]
        )
    except (TypeError, ValueError):
        return lecturas
    ampliada = dict(evidencia)
    ampliada["bbox"] = (
        max(0.0, x0 - OCR_CELL_PADDING_PIXELS), y0,
        x1 + OCR_CELL_PADDING_PIXELS, y1,
    )
    registrar(ampliada, preservar_escala=False)
    return lecturas


def _importe_clasificado_focal_unico(
    evidencia: Optional[dict[str, Any]],
    monto_actual: float,
    cache_imagenes: dict[tuple[str, int], Image.Image],
) -> Optional[float]:
    """Acepta sólo una alternativa focal no ambigua al importe geométrico."""
    alternativas = {
        lectura for lectura in _lecturas_importe_clasificado_ocr(
            evidencia, cache_imagenes,
        )
        if abs(float(lectura) - float(monto_actual)) > 0.01
        and _difiere_un_digito_monetario(
            str(int(round(float(monto_actual)))), lectura,
        )
    }
    if len(alternativas) != 1:
        return None
    return next(iter(alternativas))


def _confirmar_importe_clasificado_ocr(
    evidencia: Optional[dict[str, Any]], candidato: float,
    cache_imagenes: dict[tuple[str, int], Image.Image],
) -> bool:
    """Confirma una alternativa textual con la primera lectura focal sólida.

    La escala nativa tiene prioridad porque evita artefactos de reescalado. Si
    no entrega una lectura consensuada, se prueba el recorte ampliado y luego
    un margen horizontal corto. Una lectura sólida que contradiga al OCR
    textual bloquea la sustitución de inmediato.
    """
    if not evidencia or not evidencia.get("bbox"):
        return False

    def coincide(celda: dict[str, Any], *, preservar_escala: bool) -> Optional[bool]:
        lectura = _releer_celda_ocr_focal(
            celda, cache_imagenes, preservar_escala=preservar_escala,
        )
        if lectura is None:
            return None
        return abs(float(lectura) - float(candidato)) <= 0.01

    nativa = coincide(evidencia, preservar_escala=True)
    if nativa is not None:
        return nativa
    escalada = coincide(evidencia, preservar_escala=False)
    if escalada is not None:
        return escalada
    try:
        x0, y0, x1, y1 = (
            float(value) for value in evidencia["bbox"]
        )
    except (TypeError, ValueError):
        return False
    ampliada = dict(evidencia)
    ampliada["bbox"] = (
        max(0.0, x0 - OCR_CELL_PADDING_PIXELS), y0,
        x1 + OCR_CELL_PADDING_PIXELS, y1,
    )
    ampliada_escalada = coincide(ampliada, preservar_escala=False)
    return bool(ampliada_escalada)


def _parsear_lineas_ocho_columnas_focales(
    lineas: list[str],
) -> tuple[dict[int, CuentaRaw], FormatoCodigo, str]:
    """Replica sólo el contexto mínimo necesario para validar una relectura."""
    primeros = [linea.split()[0] if linea.split() else "" for linea in lineas[:60]]
    formato = detectar_formato_codigo(primeros)
    muestra: list[str] = []
    for linea in lineas[:80]:
        muestra.extend(PATRON_MONTOS.findall(linea))
    separador = detectar_separador_miles(muestra)
    cuentas: dict[int, CuentaRaw] = {}
    for indice, linea in enumerate(lineas):
        cuenta = parsear_linea(
            linea, indice, formato, separador, confianza_base=0.75,
        )
        if cuenta is not None and set(RAW_MONETARY_COLUMNS).issubset(
            cuenta.montos_columnas
        ):
            cuentas[indice] = cuenta
    return cuentas, formato, separador


def _error_identidades_ocho_columnas(cuenta: CuentaRaw) -> float:
    valores = cuenta.montos_columnas
    movimiento = valores["debitos"] - valores["creditos"]
    saldo = valores["saldo_deudor"] - valores["saldo_acreedor"]
    clasificado = sum(
        valores[columna] for columna in ("activo", "pasivo", "perdida", "ganancia")
    )
    return abs(movimiento - saldo) + abs(
        valores["saldo_deudor"] + valores["saldo_acreedor"] - clasificado
    )


def _columnas_posibles_para_correccion_focal(
    cuenta: CuentaRaw, tolerancia: float = 10.0,
) -> set[str]:
    """Acota la relectura a celdas que podrían reparar una sola fila.

    Una corrección focal de detalle admite una sola celda y debe dejar la suma
    de los errores de las dos identidades dentro de ``tolerancia``. Cada
    columna conserva una combinación distinta de esos errores. Si esa
    combinación ya excede la tolerancia, ninguna relectura de esa celda puede
    ser aceptada después. Este filtro no infiere cifras: evita OCR adicional
    sobre celdas que las identidades ya descartan.
    """
    valores = cuenta.montos_columnas
    movimiento = (
        float(valores["debitos"]) - float(valores["creditos"])
        - float(valores["saldo_deudor"]) + float(valores["saldo_acreedor"])
    )
    clasificado = (
        float(valores["saldo_deudor"]) + float(valores["saldo_acreedor"])
        - float(valores["activo"]) - float(valores["pasivo"])
        - float(valores["perdida"]) - float(valores["ganancia"])
    )
    posibles: set[str] = set()
    if abs(clasificado) <= tolerancia:
        posibles.update({"debitos", "creditos"})
    if abs(movimiento) <= tolerancia:
        posibles.update({"activo", "pasivo", "perdida", "ganancia"})
    # Al variar saldo_deudor se conserva movimiento + clasificado; al variar
    # saldo_acreedor se conserva movimiento - clasificado. Cualquier candidato
    # que alcance el umbral final debe respetar estos invariantes.
    if abs(movimiento + clasificado) <= tolerancia:
        posibles.add("saldo_deudor")
    if abs(movimiento - clasificado) <= tolerancia:
        posibles.add("saldo_acreedor")
    return posibles


def _sustituir_celdas_ocho_columnas(
    linea: str, reemplazos: dict[str, float],
) -> str:
    tokens = linea.split()
    if len(tokens) < len(RAW_MONETARY_COLUMNS):
        return linea
    inicio = len(tokens) - len(RAW_MONETARY_COLUMNS)
    for desplazamiento, columna in enumerate(RAW_MONETARY_COLUMNS):
        if columna not in reemplazos:
            continue
        posicion = inicio + desplazamiento
        tokens[posicion] = _formatear_entero_monetario_focal(
            reemplazos[columna], tokens[posicion],
        )
    return " ".join(tokens)


def _candidatos_focales_de_linea(
    linea: str,
    evidencia: Optional[dict[str, Any]],
    releer_celda: Any,
    columnas_permitidas: Optional[set[str]] = None,
    max_edits: int = 1,
) -> dict[str, float]:
    if not evidencia:
        return {}
    celdas = evidencia.get("celdas") or []
    tokens = linea.split()
    if len(celdas) != len(RAW_MONETARY_COLUMNS) or len(tokens) < len(celdas):
        return {}
    inicio = len(tokens) - len(RAW_MONETARY_COLUMNS)
    candidatos: dict[str, float] = {}
    for desplazamiento, columna in enumerate(RAW_MONETARY_COLUMNS):
        if columnas_permitidas is not None and columna not in columnas_permitidas:
            continue
        celda = celdas[desplazamiento]
        original = tokens[inicio + desplazamiento]
        valor_original = _entero_monetario_focal(original)
        if celda is None or valor_original in (None, 0):
            continue
        releido = releer_celda(celda)
        if releido is None or abs(releido - valor_original) < 0.01:
            continue
        difiere_acotado = _difiere_hasta_n_digitos_monetarios(
            original, releido, max_edits=max_edits,
        )
        # Una celda que el OCR leyó como uno o dos dígitos puede ser un cero
        # impreso. Sólo habilita el candidato si la relectura focal leyó cero
        # con consenso; la identidad de la fila y la mejora global siguen
        # siendo condiciones obligatorias más abajo.
        cero_espurio = (
            releido == 0
            and 0 < len(re.sub(r"\D", "", original)) <= 2
        )
        if difiere_acotado or cero_espurio:
            candidatos[columna] = releido
    return candidatos


def _filas_textuales_ocr_con_montos_agrupados(
    texto: str,
) -> list[tuple[str, list[float]]]:
    """Extrae una glosa y sus importes agrupados de una lectura OCR lineal.

    Esta evidencia se usa solamente para contrastar una fila que ya tiene sus
    ocho columnas físicas identificadas por TSV. No pretende reconstruir una
    tabla desde texto lineal: los ceros y las columnas de destino provienen de
    la geometría, y la lectura alternativa aporta sólo dígitos de celdas que
    ya estaban impresas como importes distintos de cero.
    """
    filas: list[tuple[str, list[float]]] = []
    for linea in texto.splitlines():
        normalizada = normalizar_linea_ocr_tabla(linea)
        coincidencias = list(_MONTO_AGRUPADO_OCR.finditer(normalizada))
        if not coincidencias:
            continue
        nombre = normalizada[:coincidencias[0].start()].strip(" .,:;|-–—−")
        if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", nombre):
            continue
        montos: list[float] = []
        for coincidencia in coincidencias:
            monto = _entero_monetario_focal(coincidencia.group(0))
            if monto is None or monto == 0:
                montos = []
                break
            montos.append(monto)
        if montos:
            filas.append((nombre, montos))
    return filas


def _candidato_textual_unico_para_fila_sin_codigo(
    nombre: str,
    texto_alternativo: str,
) -> Optional[list[float]]:
    """Devuelve una única lectura textual compatible con la glosa observada.

    Las glosas parciales no bastan para sustituir importes. Se conserva la
    misma regla de coincidencia fuerte que protege la recuperación de balances
    clasificados y se descartan empates materiales entre dos filas posibles.
    """
    candidatos: list[tuple[float, list[float]]] = []
    for nombre_alternativo, montos in _filas_textuales_ocr_con_montos_agrupados(
        texto_alternativo,
    ):
        if not _nombres_ocr_fuertemente_compatibles(nombre, nombre_alternativo):
            continue
        candidatos.append((
            _puntaje_nombres_ocr_fuerte(nombre, nombre_alternativo), montos,
        ))
    if not candidatos:
        return None
    candidatos.sort(key=lambda item: item[0], reverse=True)
    if len(candidatos) > 1 and candidatos[0][0] - candidatos[1][0] < 0.05:
        return None
    return candidatos[0][1]


def _indices_no_cero_observados_en_fila_geometrica(
    evidencia: Optional[dict[str, Any]],
) -> list[int]:
    """Ubica sólo los importes físicos no nulos de una fila TSV.

    Un guion o un cero impreso no aparece de forma confiable en el OCR lineal.
    Por eso el orden de los importes de contraste sólo puede mapearse contra
    las celdas que TSV observó con una cifra distinta de cero.
    """
    if not evidencia:
        return []
    celdas = evidencia.get("celdas") or []
    if len(celdas) != len(RAW_MONETARY_COLUMNS):
        return []
    indices: list[int] = []
    for indice, celda in enumerate(celdas):
        if celda is None:
            continue
        valor = _entero_monetario_focal(str(celda.get("token", "")))
        if valor not in (None, 0):
            indices.append(indice)
    return indices


def recuperar_celdas_sin_codigo_por_lectura_cruzada(
    lineas: list[str],
    evidencias: list[Optional[dict[str, Any]]],
) -> tuple[list[str], list[bool], list[dict[str, Any]]]:
    """Recupera un dígito OCR en filas sin código con dos lecturas independientes.

    La fila geométrica determina las ocho posiciones. La lectura lineal OCR
    sólo se acepta si identifica de forma única la misma glosa, conserva el
    número de celdas físicas no nulas y cada reemplazo difiere en no más de un
    dígito. La fila resultante debe cumplir ambas identidades contables. No se
    derivan cifras desde subtotales ni desde la cuadratura del documento.
    """
    if len(lineas) != len(evidencias) or not lineas:
        return list(lineas), [False] * len(lineas), []
    cuentas, formato, separador = _parsear_lineas_ocho_columnas_focales(lineas)
    resultado = list(lineas)
    recuperadas = [False] * len(lineas)
    cambios: list[dict[str, Any]] = []
    for indice, cuenta in cuentas.items():
        if (
            cuenta.codigo
            or cuenta.es_total
            or _error_identidades_ocho_columnas(cuenta) <= 10
        ):
            continue
        evidencia = evidencias[indice]
        if not evidencia:
            continue
        texto_alternativo = str(evidencia.get("lectura_cruzada", "") or "")
        if not texto_alternativo:
            continue
        montos_alternativos = _candidato_textual_unico_para_fila_sin_codigo(
            cuenta.nombre, texto_alternativo,
        )
        indices_observados = _indices_no_cero_observados_en_fila_geometrica(
            evidencia,
        )
        if (
            montos_alternativos is None
            or len(montos_alternativos) != len(indices_observados)
        ):
            continue
        tokens = resultado[indice].split()
        if len(tokens) < len(RAW_MONETARY_COLUMNS):
            continue
        inicio = len(tokens) - len(RAW_MONETARY_COLUMNS)
        reemplazos: dict[str, float] = {}
        seguro = True
        for posicion, monto_alternativo in zip(
            indices_observados, montos_alternativos,
        ):
            original = tokens[inicio + posicion]
            valor_original = _entero_monetario_focal(original)
            if valor_original is None:
                seguro = False
                break
            if abs(valor_original - monto_alternativo) <= 0.01:
                continue
            if not _difiere_un_digito_monetario(original, monto_alternativo):
                seguro = False
                break
            reemplazos[RAW_MONETARY_COLUMNS[posicion]] = monto_alternativo
        if not seguro or not reemplazos:
            continue
        candidata_linea = _sustituir_celdas_ocho_columnas(
            resultado[indice], reemplazos,
        )
        candidata = parsear_linea(
            candidata_linea, indice, formato, separador, confianza_base=0.75,
        )
        if (
            candidata is None
            or candidata.codigo
            or _error_identidades_ocho_columnas(candidata) > 10
        ):
            continue
        resultado[indice] = candidata_linea
        recuperadas[indice] = True
        cambios.append({
            "linea": indice,
            "columnas": sorted(reemplazos),
            "origen": "lectura_textual_cruzada",
        })
    return resultado, recuperadas, cambios


def _nombre_control_focal(cuenta: CuentaRaw) -> str:
    return re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()


def _esperados_controles_focales(
    cuentas: dict[int, CuentaRaw],
) -> dict[int, dict[str, float]]:
    """Obtiene expectativas de los controles usados por la certificación.

    El valor esperado nunca se infiere desde el propio control: siempre es la
    suma independiente de filas de detalle, más el puente observado para el
    cierre. Esto permite relecturas focales de etiquetas como SUBTOTAL y
    TOTALES sin ampliar el alcance de una corrección numérica.
    """
    ordenadas = [cuentas[indice] for indice in sorted(cuentas)]
    def clave(cuenta: CuentaRaw) -> str:
        return re.sub(r"[^a-z0-9]+", "", _nombre_control_focal(cuenta))

    subtotales = [
        cuenta for cuenta in ordenadas
        if cuenta.es_total and (
            clave(cuenta) in {"suma", "sumas", "subtotal", "total"}
            or clave(cuenta).startswith("totalacumulado")
        )
    ]
    if not subtotales:
        return {}
    # Coincide con el subtotal de referencia de certificar_extraccion_columnas:
    # el último control acumulado, o el último subtotal disponible.
    acumulados = [
        cuenta for cuenta in subtotales
        if clave(cuenta).startswith("totalacumulado")
    ]
    subtotal = acumulados[-1] if acumulados else subtotales[-1]
    esperado_sumas = {
        columna: round(sum(
            float(cuenta.montos_columnas.get(columna, 0.0) or 0.0)
            for cuenta in ordenadas if not cuenta.es_total
        ), 2)
        for columna in RAW_MONETARY_COLUMNS
    }
    esperados = {subtotal.linea: esperado_sumas}
    indice_sumas = subtotal.linea
    puente = next(
        (
            cuenta for cuenta in ordenadas
            if cuenta.linea > indice_sumas
            and cuenta.es_total
            and re.match(
                r"^(?:perdida o ganancia|ganancia(?: neta|(?: del)? ejercicio)|"
                r"resultado|utilidad)",
                _nombre_control_focal(cuenta),
            )
        ),
        None,
    )
    for cuenta in ordenadas:
        if cuenta.linea <= indice_sumas or not cuenta.es_total:
            continue
        if clave(cuenta) not in {
            "sumasiguales", "totalesiguales", "totales", "sumastotales",
            "totalgeneral",
        } or puente is None:
            continue
        esperados[cuenta.linea] = {
            columna: round(
                esperado_sumas[columna]
                + float(puente.montos_columnas.get(columna, 0.0) or 0.0),
                2,
            )
            for columna in RAW_MONETARY_COLUMNS
        }
    return esperados


def _recuperar_subtotal_ocr_desde_cierre_observado(
    lineas: list[str],
    evidencias: list[Optional[dict[str, Any]]],
    releer_celda: Any,
) -> tuple[list[str], list[dict[str, Any]], bool]:
    """Relee un subtotal sólo cuando el cierre observado lo comprueba.

    Esta pasada trata un caso distinto a la suma de detalle: un subtotal puede
    contener un dígito OCR equivocado aunque la fila final y el puente de
    resultado impresos sean internamente consistentes. No se sustituye una
    cifra por aritmética: el valor esperado desde ``final - puente`` sólo
    habilita una relectura focal, que debe devolver exactamente ese importe y
    diferir en un solo dígito. La corrección puede dejar diferencias con el
    detalle, por lo que nunca certifica por sí misma la extracción.
    """
    if len(lineas) != len(evidencias) or not lineas:
        return list(lineas), [], False
    cuentas, _, _ = _parsear_lineas_ocho_columnas_focales(lineas)
    if not cuentas:
        return list(lineas), [], False
    base = certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )
    if (
        base.totales_finales_validos is not True
        or base.ecuacion_contable_fuente_valida is not False
    ):
        return list(lineas), [], False

    ordenadas = [cuentas[indice] for indice in sorted(cuentas)]

    def clave(cuenta: CuentaRaw) -> str:
        return re.sub(r"[^a-z0-9]+", "", _nombre_control_focal(cuenta))

    def es_puente(cuenta: CuentaRaw) -> bool:
        return bool(
            cuenta.es_total and re.match(
                r"^(?:perdida o ganancia|ganancia(?: neta|(?: del)? ejercicio)|"
                r"resultado|utilidad|perdida net[ao]|total perdida)\b",
                _nombre_control_focal(cuenta),
            )
        )

    finales = [
        cuenta for cuenta in ordenadas
        if cuenta.es_total and (
            "totales iguales" in _nombre_control_focal(cuenta)
            or "sumas iguales" in _nombre_control_focal(cuenta)
            or clave(cuenta) in {"totales", "totalgeneral", "sumastotales"}
        )
    ]
    if not finales:
        return list(lineas), [], False
    final = finales[-1]
    subtotales = [
        cuenta for cuenta in ordenadas
        if (
            cuenta.es_total
            and cuenta.linea < final.linea
            and (
                "subtotal" in clave(cuenta)
                or clave(cuenta) in {"suma", "sumas"}
                or clave(cuenta).startswith("totalacumulado")
            )
        )
    ]
    if not subtotales:
        return list(lineas), [], False
    acumulados = [
        cuenta for cuenta in subtotales
        if clave(cuenta).startswith("totalacumulado")
    ]
    subtotal = acumulados[-1] if acumulados else subtotales[-1]
    puentes = [
        cuenta for cuenta in ordenadas
        if subtotal.linea < cuenta.linea < final.linea and es_puente(cuenta)
    ]
    if not puentes:
        return list(lineas), [], False
    puente = puentes[-1]
    esperados = {
        columna: round(
            float(final.montos_columnas.get(columna, 0.0) or 0.0)
            - float(puente.montos_columnas.get(columna, 0.0) or 0.0),
            2,
        )
        for columna in RAW_MONETARY_COLUMNS
    }
    discrepantes = {
        columna for columna in RAW_MONETARY_COLUMNS
        if abs(
            float(subtotal.montos_columnas.get(columna, 0.0) or 0.0)
            - esperados[columna]
        ) > 0.01
    }
    # Un único desacuerdo evita corregir una fila de control que podría tener
    # más de una celda OCR defectuosa o pertenecer a otra estructura.
    if len(discrepantes) != 1:
        return list(lineas), [], False
    columna = next(iter(discrepantes))
    candidatos = _candidatos_focales_de_linea(
        lineas[subtotal.linea], evidencias[subtotal.linea], releer_celda,
        columnas_permitidas={columna},
    )
    if (
        len(candidatos) != 1
        or abs(float(candidatos.get(columna, 0.0)) - esperados[columna]) > 0.01
    ):
        return list(lineas), [], False
    resultado = list(lineas)
    resultado[subtotal.linea] = _sustituir_celdas_ocho_columnas(
        resultado[subtotal.linea], candidatos,
    )
    cuentas_corregidas, _, _ = _parsear_lineas_ocho_columnas_focales(resultado)
    candidata = certificar_extraccion_columnas(
        list(cuentas_corregidas.values()), metodo="ocr_coordinates_8_amounts",
    )
    if (
        candidata.totales_finales_validos is not True
        or candidata.ecuacion_contable_fuente_valida is not True
    ):
        return list(lineas), [], False
    return resultado, [{
        "linea": subtotal.linea,
        "columnas": [columna],
        "origen": "relectura_focal_de_control_estructural",
    }], True


def _mejora_certificacion_focal(
    base: CertificacionExtraccion,
    candidata: CertificacionExtraccion,
) -> bool:
    """Acepta sólo evidencia focal que mejore la extracción verificable.

    Una fila que ya pasa ambas identidades tras dos lecturas OCR concordantes
    es evidencia local independiente. Si el total final ya estaba impreso de
    forma inconsistente, su diferencia agregada no puede invalidar esa fila:
    la certificación global continúa fallida y bloquea la entrega. Cuando los
    controles finales eran válidos, se conserva la regla estricta de no
    empeorar ninguna diferencia conocida.
    """
    if len(candidata.filas_inconsistentes) > len(base.filas_inconsistentes):
        return False
    if base.totales_finales_validos is True and candidata.totales_finales_validos is False:
        return False
    redujo_filas = len(candidata.filas_inconsistentes) < len(
        base.filas_inconsistentes
    )
    if redujo_filas and base.totales_finales_validos is False:
        return True
    for columna in set(base.diferencias) | set(candidata.diferencias):
        antes = abs(float(base.diferencias.get(columna, 0.0) or 0.0))
        despues = abs(float(candidata.diferencias.get(columna, 0.0) or 0.0))
        if despues > antes + 0.01:
            return False
    return (
        any(
            abs(float(candidata.diferencias.get(columna, 0.0) or 0.0))
            < abs(float(base.diferencias.get(columna, 0.0) or 0.0)) - 0.01
            for columna in set(base.diferencias) | set(candidata.diferencias)
        )
        or redujo_filas
        or (
            base.totales_finales_validos is False
            and candidata.totales_finales_validos is True
        )
    )


def _error_agregado_controles_focales(
    certificacion: CertificacionExtraccion,
) -> float:
    """Resume sólo el error observado entre detalle y controles impresos."""
    return sum(
        abs(float(diferencia or 0.0))
        for diferencia in certificacion.diferencias.values()
    )


def recuperar_celdas_ocr_por_residuo_de_control(
    lineas: list[str],
    evidencias: list[Optional[dict[str, Any]]],
    releer_celda_nativa: Any,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Corrige un residuo mínimo sólo si una lectura nativa lo explica sola.

    Algunas celdas espurias de uno o dos dígitos preservan las dos identidades
    de la fila y, por ello, no entran al reparador de detalle. Esta última
    pasada sólo se habilita cuando no queda ninguna fila inconsistente, la fila
    final sigue cuadrada y los controles difieren por una cantidad muy pequeña.
    Cada propuesta requiere OCR nativo con consenso, identidad local exacta y
    una mejora global estricta sin empeorar ninguna columna. Los empates se
    rechazan: un control nunca decide entre dos lecturas visuales posibles.
    """
    if len(lineas) != len(evidencias) or not lineas:
        return list(lineas), []
    cuentas, formato, separador = _parsear_lineas_ocho_columnas_focales(lineas)
    if not cuentas:
        return list(lineas), []
    base = certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )
    if (
        base.filas_inconsistentes
        or base.totales_finales_validos is not True
        or not base.diferencias
        or not any(abs(float(valor or 0.0)) > 10.0 for valor in base.diferencias.values())
        or max(abs(float(valor or 0.0)) for valor in base.diferencias.values())
        > OCR_CONTROL_RESIDUAL_MAX_ABSOLUTE
    ):
        return list(lineas), []
    error_base = _error_agregado_controles_focales(base)
    propuestas: list[tuple[float, int, list[str], list[str]]] = []
    for indice, cuenta in cuentas.items():
        if cuenta.es_total or _error_identidades_ocho_columnas(cuenta) > 10:
            continue
        candidatos = _candidatos_focales_de_linea(
            lineas[indice], evidencias[indice], releer_celda_nativa,
        )
        if not candidatos:
            continue
        candidata_linea = _sustituir_celdas_ocho_columnas(
            lineas[indice], candidatos,
        )
        candidata_fila = parsear_linea(
            candidata_linea, indice, formato, separador, confianza_base=0.75,
        )
        if (
            candidata_fila is None
            or _error_identidades_ocho_columnas(candidata_fila) > 10
        ):
            continue
        candidata_lineas = list(lineas)
        candidata_lineas[indice] = candidata_linea
        cuentas_candidatas, _, _ = _parsear_lineas_ocho_columnas_focales(
            candidata_lineas,
        )
        certificacion_candidata = certificar_extraccion_columnas(
            list(cuentas_candidatas.values()), metodo="ocr_coordinates_8_amounts",
        )
        if (
            certificacion_candidata.filas_inconsistentes
            or certificacion_candidata.totales_finales_validos is not True
        ):
            continue
        columnas = set(base.diferencias) | set(certificacion_candidata.diferencias)
        if any(
            abs(float(certificacion_candidata.diferencias.get(columna, 0.0) or 0.0))
            > abs(float(base.diferencias.get(columna, 0.0) or 0.0)) + 0.01
            for columna in columnas
        ):
            continue
        error_candidato = _error_agregado_controles_focales(
            certificacion_candidata,
        )
        if error_candidato >= error_base - 0.01:
            continue
        propuestas.append((
            error_candidato,
            indice,
            candidata_lineas,
            sorted(candidatos),
        ))
    if not propuestas:
        return list(lineas), []
    propuestas.sort(key=lambda propuesta: (propuesta[0], propuesta[1]))
    mejor_error, indice, mejor_lineas, columnas = propuestas[0]
    if sum(
        abs(error - mejor_error) <= 0.01
        for error, *_resto in propuestas
    ) != 1:
        return list(lineas), []
    return mejor_lineas, [{
        "linea": indice,
        "columnas": columnas,
        "origen": "relectura_nativa_por_residuo_de_control",
    }]


def recuperar_celdas_ocr_focales(
    lineas: list[str],
    evidencias: list[Optional[dict[str, Any]]],
    *,
    releer_celda: Optional[Any] = None,
    releer_celda_nativa: Optional[Any] = None,
) -> tuple[list[str], list[bool], list[dict[str, Any]]]:
    """Repara dígitos OCR sólo con evidencia visual y controles contables.

    Antes de releer una celda se permite una lectura OCR lineal cruzada para
    filas sin código, siempre que conserve sus columnas físicas y deje la
    identidad local exacta. La relectura focal posterior se limita a una sola
    sustitución por celda. Los controles SUMAS y SUMAS IGUALES sólo cambian
    cuando la lectura focal coincide con su total independiente. Las filas
    resultantes quedan obligatoriamente en revisión.
    """
    if len(evidencias) != len(lineas) or not lineas:
        return list(lineas), [False] * len(lineas), []
    cuentas, formato, separador = _parsear_lineas_ocho_columnas_focales(lineas)
    if not cuentas:
        return list(lineas), [False] * len(lineas), []
    base = certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )
    resultado, filas_cruzadas, cambios_cruzados = (
        recuperar_celdas_sin_codigo_por_lectura_cruzada(lineas, evidencias)
    )
    # La evidencia TSV original ya no representa una fila modificada por la
    # lectura lineal. No se usa para una segunda reparación focal de la misma
    # fila: se prefiere descartar esa posibilidad antes que mezclar fuentes.
    evidencias_focales = [
        None if recuperada else evidencia
        for evidencia, recuperada in zip(evidencias, filas_cruzadas)
    ]
    cuentas, formato, separador = _parsear_lineas_ocho_columnas_focales(
        resultado,
    )
    if not cuentas:
        return list(lineas), [False] * len(lineas), []
    cache_imagenes: dict[tuple[str, int], Image.Image] = {}
    lector_base = releer_celda or (
        lambda celda: _releer_celda_ocr_focal(celda, cache_imagenes)
    )
    lector_nativo_base = releer_celda_nativa or (
        lambda celda: _releer_celda_ocr_focal(
            celda, cache_imagenes, preservar_escala=True,
        )
    )
    lecturas_celdas: dict[int, Optional[float]] = {}
    lecturas_celdas_nativas: dict[int, Optional[float]] = {}

    def lector(celda: dict[str, Any]) -> Optional[float]:
        # Una segunda pasada de candidatos no debe repetir Tesseract sobre el
        # mismo recorte. La lectura permanece como evidencia observada, no se
        # usa para inferir ni completar otra cifra.
        clave = id(celda)
        if clave not in lecturas_celdas:
            lecturas_celdas[clave] = lector_base(celda)
        return lecturas_celdas[clave]

    def lector_nativo(celda: dict[str, Any]) -> Optional[float]:
        # La segunda lectura conserva los píxeles originales del recorte. Se
        # usa sólo si la variante ampliada no consiguió reparar la fila y se
        # mantiene en su propio caché para no mezclar ambas evidencias.
        clave = id(celda)
        if clave not in lecturas_celdas_nativas:
            lecturas_celdas_nativas[clave] = lector_nativo_base(celda)
        return lecturas_celdas_nativas[clave]

    cambios: list[dict[str, Any]] = list(cambios_cruzados)

    # Primero se corrigen filas de detalle que fallan ambas redundancias. La
    # suma de importes por sí sola nunca basta para mover un dígito interno.
    for indice, cuenta in cuentas.items():
        if cuenta.es_total or _error_identidades_ocho_columnas(cuenta) <= 10:
            continue
        columnas_posibles = _columnas_posibles_para_correccion_focal(cuenta)
        # Primero se prueban las celdas que una sola edición podría llevar al
        # umbral de identidad. Si no bastan, se conserva el fallback histórico
        # de varias celdas: hay documentos donde dos errores independientes
        # requieren evidencia focal en más de una columna.
        estrategias = [columnas_posibles]
        todas_las_columnas = set(RAW_MONETARY_COLUMNS)
        if columnas_posibles != todas_las_columnas:
            estrategias.append(None)
        corregida = False
        for lector_actual, origen in (
            (lector, None),
            (lector_nativo, "relectura_nativa_sin_escalar"),
        ):
            for columnas_permitidas in estrategias:
                candidatos = _candidatos_focales_de_linea(
                    resultado[indice], evidencias_focales[indice], lector_actual,
                    columnas_permitidas=columnas_permitidas,
                )
                if not candidatos:
                    continue
                candidata_linea = _sustituir_celdas_ocho_columnas(
                    resultado[indice], candidatos,
                )
                candidata = parsear_linea(
                    candidata_linea, indice, formato, separador,
                    confianza_base=0.75,
                )
                if (
                    candidata is None
                    or _error_identidades_ocho_columnas(candidata) > 10
                    or _error_identidades_ocho_columnas(candidata)
                    >= _error_identidades_ocho_columnas(cuenta)
                ):
                    continue
                resultado[indice] = candidata_linea
                cambio = {"linea": indice, "columnas": sorted(candidatos)}
                if origen:
                    cambio["origen"] = origen
                cambios.append(cambio)
                corregida = True
                break
            if corregida:
                break

    # Después de corregir detalle, una lectura focal de un control sólo se
    # acepta cuando coincide exactamente con su suma independiente.
    cuentas_corregidas, _, _ = _parsear_lineas_ocho_columnas_focales(resultado)
    cambios_estructurales: list[dict[str, Any]] = []
    ecuacion_reparada = False
    # La corrección estructural tiene una regla de aceptación distinta de las
    # correcciones de detalle: restituye un control fuente observado aunque el
    # detalle siga sin conciliar. No se combina con otra mutación en la misma
    # pasada, pues esa combinación podría ocultar un empeoramiento agregado.
    if not cambios:
        resultado_estructural, cambios_estructurales, ecuacion_reparada = (
            _recuperar_subtotal_ocr_desde_cierre_observado(
                resultado, evidencias_focales, lector,
            )
        )
    if cambios_estructurales:
        resultado = resultado_estructural
        cambios.extend(cambios_estructurales)
        cuentas_corregidas, _, _ = _parsear_lineas_ocho_columnas_focales(
            resultado,
        )
    if not ecuacion_reparada:
        for indice, esperado in _esperados_controles_focales(cuentas_corregidas).items():
            control = cuentas_corregidas.get(indice)
            if control is None:
                continue
            discrepantes = {
                columna for columna in RAW_MONETARY_COLUMNS
                if abs(
                    float(control.montos_columnas.get(columna, 0.0) or 0.0)
                    - float(esperado.get(columna, 0.0) or 0.0)
                ) > 0.01
            }
            if not discrepantes:
                continue
            candidatos = _candidatos_focales_de_linea(
                resultado[indice], evidencias_focales[indice], lector, discrepantes,
                # Un control final sólo puede aceptar hasta dos ediciones porque
                # su valor releído debe igualar exactamente la suma independiente
                # de detalles y el puente observado. Las cuentas detalle conservan
                # el límite de una edición anterior.
                max_edits=2,
            )
            aceptados = {
                columna: valor
                for columna, valor in candidatos.items()
                if abs(valor - float(esperado.get(columna, 0.0))) <= 0.01
            }
            if not aceptados:
                continue
            resultado[indice] = _sustituir_celdas_ocho_columnas(
                resultado[indice], aceptados,
            )
            cambios.append({"linea": indice, "columnas": sorted(aceptados)})

        # Al final se revisan sólo residuos mínimos que quedaron invisibles para
        # la identidad local porque una misma cifra OCR espuria afectó dos o tres
        # columnas de la fila. Esta función nunca deduce un importe del subtotal.
        resultado_por_residuo, cambios_por_residuo = (
            recuperar_celdas_ocr_por_residuo_de_control(
                resultado, evidencias_focales, lector_nativo,
            )
        )
        if cambios_por_residuo:
            resultado = resultado_por_residuo
            cambios.extend(cambios_por_residuo)

    if not cambios:
        return list(lineas), [False] * len(lineas), []
    cuentas_finales, _, _ = _parsear_lineas_ocho_columnas_focales(resultado)
    candidata = certificar_extraccion_columnas(
        list(cuentas_finales.values()), metodo="ocr_coordinates_8_amounts",
    )
    mejora_verificable = _mejora_certificacion_focal(base, candidata)
    control_estructural_confirmado = (
        ecuacion_reparada
        and candidata.totales_finales_validos is True
        and candidata.ecuacion_contable_fuente_valida is True
    )
    if not mejora_verificable and not control_estructural_confirmado:
        return list(lineas), [False] * len(lineas), []
    filas_recuperadas = [False] * len(lineas)
    for cambio in cambios:
        filas_recuperadas[int(cambio["linea"])] = True
    return resultado, filas_recuperadas, cambios


def _separar_linea_lateral_con_evidencia(
    linea: str,
    numero_linea: int,
    formato_codigo: FormatoCodigo,
    separador_miles: str,
    confianza_base: float,
) -> tuple[list[str], bool]:
    """Devuelve un corte lateral sólo si ambos fragmentos prueban su código.

    El segundo booleano indica una ambigüedad que debe impedir entrega
    automática: una fila sin códigos puede parecer dos tablas o una sola
    glosa con número. En esa situación se conserva la fila completa para no
    inventar dos cuentas y se exige revisión humana.
    """
    candidatos = split_side_by_side(
        linea, permitir_corte_con_ocho_columnas=True,
    )
    if len(candidatos) != 2:
        return candidatos, False

    # Los cortes que no dependen de ocho celdas terminales conservan la
    # heurística histórica. La ambigüedad tratada aquí sólo existe cuando el
    # nuevo resguardo conservador cambió el resultado por defecto.
    if split_side_by_side(linea) == candidatos:
        return candidatos, False

    cuentas_candidatas = [
        parsear_linea(
            fragmento, numero_linea, formato_codigo, separador_miles,
            confianza_base,
        )
        for fragmento in candidatos
    ]
    if all(cuenta is not None and cuenta.codigo for cuenta in cuentas_candidatas):
        return candidatos, False
    return [linea], True


def parsear_linea_clasificada_observada(
    linea: str,
    numero_linea: int,
    separador_miles: str,
    confianza_base: float = 1.0,
) -> Optional[CuentaRaw]:
    """Parsea una celda geométrica de balance clasificado sin reinterpretarla.

    El extractor especializado ya separó la glosa y observó que el último
    token es su importe. Aplicar la heurística universal a esa celda puede
    confundir un dígito legítimo de la glosa, por ejemplo ``CUENTA BCO.
    ESTADO 1``, con el saldo. Se conserva literalmente el nombre y se usa
    sólo ese importe observado.

    No se infieren códigos en esta ruta: si no se cumple el contrato de
    ``glosa + importe`` el llamador deja que opere el fallback universal.
    """
    partes = linea.strip().rsplit(maxsplit=1)
    if len(partes) != 2:
        return None
    nombre, token_monto = partes
    token_normalizado = normalizar_token_ocr(token_monto).replace("$", "")
    if not PATRON_MONTOS.fullmatch(token_normalizado):
        return None
    monto = parsear_monto(token_normalizado, separador_miles)
    nombre = nombre.strip(" .-–—−")
    if monto is None or len(nombre) < 3:
        return None
    nombre_para_total = re.sub(r"^[^\w]+", "", nombre).strip()
    return CuentaRaw(
        linea=numero_linea,
        codigo=None,
        nombre=nombre,
        monto=monto,
        origen_columna=OrigenColumna.DESCONOCIDO,
        es_total=_es_etiqueta_total(nombre_para_total),
        confianza_extraccion=confianza_base,
    )


def marcar_subtotales_jerarquicos(cuentas: list[CuentaRaw]) -> int:
    """Reconoce padres por prefijo y sumas de descendientes, sin alterar montos."""
    def code(c):
        match = re.match(r"^(\d+)\s*-\s*\D", c.nombre)
        return re.sub(r"[.\-]", "", c.codigo) if c.codigo else (match[1] if match else "")

    codes = [code(c) for c in cuentas]
    marked = 0
    # De abajo hacia arriba: los padres internos no se vuelven a sumar.
    for i in range(len(cuentas) - 1, -1, -1):
        parent = cuentas[i]
        prefix = codes[i]
        if parent.es_total or not prefix or not parent.montos_columnas:
            continue
        children = []
        for j in range(i + 1, len(cuentas)):
            child_code = codes[j]
            if not child_code or not child_code.startswith(prefix) or len(child_code) <= len(prefix):
                break
            if not cuentas[j].es_total:
                children.append(cuentas[j])
        if not children or any(not c.montos_columnas for c in children):
            continue
        sums = {k: sum(c.montos_columnas.get(k, 0) for c in children) for k in RAW_MONETARY_COLUMNS}
        values = parent.montos_columnas
        if not any(values.values()):
            continue
        # Los grupos pueden incluir movimientos de cuentas saldadas omitidas
        # del detalle. Sólo aceptar ese excedente si es igual en Debe/Haber,
        # no negativo y ambos saldos netos reproducen los descendientes.
        extra_debe = values.get("debitos", 0) - sums["debitos"]
        extra_haber = values.get("creditos", 0) - sums["creditos"]
        checks = [
            extra_debe - extra_haber,
            values.get("saldo_deudor", 0) - values.get("saldo_acreedor", 0)
            - sums["saldo_deudor"] + sums["saldo_acreedor"],
            values.get("activo", 0) - values.get("pasivo", 0)
            + values.get("perdida", 0) - values.get("ganancia", 0)
            - sums["activo"] + sums["pasivo"] - sums["perdida"] + sums["ganancia"],
        ]
        if min(extra_debe, extra_haber) >= -0.01 and all(abs(x) <= 0.01 for x in checks):
            parent.es_total = True
            parent.columnas_derivadas = [*parent.columnas_derivadas, "subtotal_jerarquico"]
            marked += 1
    return marked


def _error_identidades_cuenta(cuenta: CuentaRaw) -> float:
    values = cuenta.montos_columnas
    if set(values) != set(RAW_MONETARY_COLUMNS):
        return float("inf")
    return abs(
        (values["debitos"] - values["creditos"])
        - (values["saldo_deudor"] - values["saldo_acreedor"])
    ) + abs(
        values["saldo_deudor"] + values["saldo_acreedor"]
        - values["activo"] - values["pasivo"]
        - values["perdida"] - values["ganancia"]
    )


def _cuenta_desde_candidato_ocr(
    linea: str, numero_linea: int, exigir_consistencia: bool = True,
) -> Optional[CuentaRaw]:
    """Obtiene la variante consistente de una fila OCR con 6 a 8 importes."""
    normalized = normalizar_codigo_ocr(normalizar_linea_ocr_tabla(linea))
    candidates: list[CuentaRaw] = []
    original = parsear_linea(
        normalized,
        numero_linea,
        FormatoCodigo.SIN_CODIGO,
        ".",
        0.75,
    )
    original_has_full_row = bool(
        original is not None
        and set(original.montos_columnas) == set(RAW_MONETARY_COLUMNS)
    )
    if (
        original is not None
        and original.codigo
        and original.montos_columnas
        and (
            not exigir_consistencia
            or _error_identidades_cuenta(original) <= 10
        )
    ):
        candidates.append(original)

    # Sólo se agregan ceros cuando la línea original no entrega las ocho
    # posiciones. Antes se probaban siempre: una fila completa pero
    # inconsistente podía parecer correcta al desplazar sus primeros importes
    # al nombre y completar el final con ceros.
    suffixes = () if original_has_full_row else (" 0", " 0 0")
    for suffix in suffixes:
        candidate = parsear_linea(
            normalized + suffix,
            numero_linea,
            FormatoCodigo.SIN_CODIGO,
            ".",
            0.75,
        )
        if (
            candidate is not None
            and candidate.codigo
            and candidate.montos_columnas
            and (
                not exigir_consistencia
                or _error_identidades_cuenta(candidate) <= 10
            )
        ):
            candidates.append(candidate)
    if not candidates:
        return None
    # Prefiere la variante que conserva más evidencia monetaria. Los sufijos
    # sólo agregan ceros; nunca inventan un importe distinto de cero.
    return min(
        candidates,
        key=lambda account: (
            _error_identidades_cuenta(account),
            -sum(abs(value) for value in account.montos_columnas.values()),
        ),
    )


def _codigo_contable_canonico(codigo: Optional[str]) -> str:
    return re.sub(r"\D", "", codigo or "")


def _nombres_ocr_compatibles(left: str, right: str) -> bool:
    def tokens(value: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9]+", _sin_acentos(value).lower())
            if len(token) >= 3
        }

    left_normalized = re.sub(r"\s+", " ", _sin_acentos(left).lower()).strip()
    right_normalized = re.sub(r"\s+", " ", _sin_acentos(right).lower()).strip()
    if left_normalized == right_normalized:
        return True
    left_tokens, right_tokens = tokens(left), tokens(right)
    if not left_tokens or not right_tokens:
        return False
    # La cobertura se mide sobre la glosa más larga. Medirla sobre la más corta
    # hacía que "Peajes" pareciera equivalente a "Combustibles, Peajes,
    # Estacionamiento" y bloqueaba la recuperación de esta última.
    return len(left_tokens & right_tokens) / max(
        len(left_tokens), len(right_tokens),
    ) >= 0.6


def _nombres_ocr_fuertemente_compatibles(left: str, right: str) -> bool:
    """Exige una coincidencia de glosa apta para sustituir una cifra.

    ``POR PAGAR`` es una coincidencia útil para una sugerencia, pero no para
    reemplazar un importe: por ejemplo, no identifica de forma única si son
    letras, documentos u otra obligación. La recuperación de importes sólo
    acepta identidad normalizada o una cobertura léxica alta.
    """
    left_normalized = re.sub(r"\s+", " ", _sin_acentos(left).lower()).strip()
    right_normalized = re.sub(r"\s+", " ", _sin_acentos(right).lower()).strip()
    if left_normalized == right_normalized:
        return True

    def tokens(value: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9]+", value)
            if len(token) >= 3
        }

    left_tokens, right_tokens = tokens(left_normalized), tokens(right_normalized)
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / max(
        len(left_tokens), len(right_tokens),
    ) >= 0.8


def _puntaje_nombres_ocr_fuerte(left: str, right: str) -> float:
    """Puntaje conservador para asignar una alternativa a una única fila."""
    left_normalized = re.sub(r"[^a-z0-9]+", " ", _sin_acentos(left).lower())
    right_normalized = re.sub(r"[^a-z0-9]+", " ", _sin_acentos(right).lower())
    left_normalized = re.sub(r"\s+", " ", left_normalized).strip()
    right_normalized = re.sub(r"\s+", " ", right_normalized).strip()
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    left_tokens = {
        token for token in left_normalized.split() if len(token) >= 3
    }
    right_tokens = {
        token for token in right_normalized.split() if len(token) >= 3
    }
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(
        len(left_tokens), len(right_tokens),
    )


_PATRON_IMPORTE_CLASIFICADO = re.compile(
    r"(?<![\d.,])-?\d{1,3}(?:[.,]\d{3})+(?![\d.,])"
)


def _importe_clasificado_ocr(token: str) -> Optional[float]:
    """Convierte un importe de una mitad clasificada sin inferir dígitos.

    Las dos lecturas OCR suelen discrepar en el separador, no necesariamente
    en el valor. Se reutiliza la normalización monetaria del parser para que
    ``1.687.786,170`` y ``1,687,786.170`` se interpreten igual. Si el token no
    es un importe agrupado completo, no se usa como evidencia alternativa.
    """
    normalized = normalizar_linea_ocr_tabla(token)
    if not _PATRON_IMPORTE_CLASIFICADO.fullmatch(normalized):
        return None
    value = parsear_monto(normalized, ".")
    return float(value) if value is not None else None


def _candidatos_textuales_balance_clasificado(
    texto_alternativo: str,
) -> list[tuple[str, float, OrigenColumna]]:
    """Extrae pares ``ACTIVO | PASIVO`` de una lectura OCR textual.

    No intenta adivinar columnas a partir de un bloque de texto general. Sólo
    acepta renglones que contengan exactamente dos importes agrupados y los
    asocia con su mitad física por orden visual. Es la evidencia complementaria
    para una tabla ya reconocida geométricamente como balance clasificado.
    """
    candidates: list[tuple[str, float, OrigenColumna]] = []
    for raw_line in texto_alternativo.splitlines():
        line = normalizar_linea_ocr_tabla(raw_line)
        matches = list(_PATRON_IMPORTE_CLASIFICADO.finditer(line))
        if len(matches) != 2:
            continue
        left_match, right_match = matches
        left_name = line[:left_match.start()].strip(" .,:;|-–—")
        right_name = line[left_match.end():right_match.start()].strip(
            " .,:;|-–—"
        )
        left_amount = _importe_clasificado_ocr(left_match.group(0))
        right_amount = _importe_clasificado_ocr(right_match.group(0))
        if left_amount is not None and re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", left_name):
            candidates.append((left_name, left_amount, OrigenColumna.ACTIVO))
        if right_amount is not None and re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", right_name):
            candidates.append((right_name, right_amount, OrigenColumna.PASIVO))
    return candidates


def _cuentas_desde_lineas_clasificadas(
    lineas: list[tuple],
) -> list[CuentaRaw]:
    """Construye una vista mínima para contrastar subtotales por lado."""
    cuentas: list[CuentaRaw] = []
    for index, item in enumerate(lineas):
        line, origin = item[:2]
        cuenta = parsear_linea_clasificada_observada(
            normalizar_linea_ocr_tabla(str(line)), index, ".", 0.75,
        )
        if cuenta is None or cuenta.monto is None:
            continue
        cuenta.origen_columna = origin
        cuentas.append(cuenta)
    return cuentas


def recuperar_importes_balance_clasificado_ocr(
    lineas_coordenadas: list[tuple], texto_alternativo: str,
    *, tolerancia_absoluta: float = 10.0,
    confirmar_importe: Optional[Any] = None,
) -> tuple[list[tuple], list[bool], int]:
    """Recupera importes geométricos sólo con evidencia cruzada y subtotal.

    La geometría preserva la columna física; el OCR textual a veces conserva
    mejor los dígitos de un importe largo. Una sustitución exige: misma mitad,
    glosa compatible, importe textual completo y una reducción estricta de la
    diferencia de subtotales. Para aceptar una mejora pequeña en un documento
    que todavía tenga otro control fallido, ``confirmar_importe`` debe validar
    el mismo importe sobre su recorte OCR. No cambia controles impresos ni
    inventa cifras. Cada fila aceptada queda marcada para revisión humana.
    """
    candidates = _candidatos_textuales_balance_clasificado(texto_alternativo)
    if not candidates or not lineas_coordenadas:
        return list(lineas_coordenadas), [False] * len(lineas_coordenadas), 0

    recovered = list(lineas_coordenadas)
    recovered_flags = [False] * len(recovered)

    def errores_subtotales(items: list[tuple]) -> dict[str, float]:
        differences = _diferencias_subtotales_fisicos_clasificados(
            _cuentas_desde_lineas_clasificadas(items),
        )
        return {
            nombre: abs(float(diferencia))
            for nombre, diferencia in differences.items()
        }

    def mejora_local_de_control(
        antes: dict[str, float], despues: dict[str, float],
    ) -> tuple[bool, float]:
        """Exige que una lectura independiente mejore un subtotal físico.

        Un documento puede contener más de un importe OCR defectuoso. Medir
        una propuesta contra el error agregado hacía que una corrección válida
        pero pequeña quedara bloqueada por otro subtotal ajeno y mucho mayor.
        La aceptación sigue siendo conservadora: ningún subtotal conocido
        puede empeorar y al menos uno debe mejorar más allá de la tolerancia.
        """
        nombres = set(antes) | set(despues)
        if any(
            despues.get(nombre, 0.0)
            > antes.get(nombre, 0.0) + tolerancia_absoluta
            for nombre in nombres
        ):
            return False, 0.0
        mejora = sum(
            antes.get(nombre, 0.0) - despues.get(nombre, 0.0)
            for nombre in nombres
        )
        return mejora > tolerancia_absoluta, mejora

    def error_agregado(errores: dict[str, float]) -> float:
        return sum(
            diferencia for diferencia in errores.values()
            if diferencia > tolerancia_absoluta
        )

    errores_antes = errores_subtotales(recovered)
    error_agregado_antes = error_agregado(errores_antes)
    if not any(
        diferencia > tolerancia_absoluta
        for diferencia in errores_antes.values()
    ):
        return recovered, recovered_flags, 0

    # Una alternativa textual se asigna primero a la única glosa geométrica
    # que más se le parece. Sin esta regla, ``CTA ESPECIAL ...`` podía ocupar
    # la fila vecina ``CTA ESPECIAL ... 2`` por compartir casi todas las
    # palabras, desplazando una cifra correcta. Los empates se dejan intactos.
    target_by_candidate: dict[int, int] = {}
    for candidate_index, (candidate_name, _amount, candidate_origin) in enumerate(candidates):
        scored = []
        for current_index, item in enumerate(recovered):
            line, current_origin = item[:2]
            if current_origin is not candidate_origin:
                continue
            current = parsear_linea_clasificada_observada(
                normalizar_linea_ocr_tabla(str(line)), current_index, ".", 0.75,
            )
            if current is None:
                continue
            if current.es_total:
                continue
            score = _puntaje_nombres_ocr_fuerte(current.nombre, candidate_name)
            if score >= 0.8:
                scored.append((score, current_index))
        if not scored:
            continue
        scored.sort(key=lambda item: (-item[0], item[1]))
        if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.05:
            continue
        target_by_candidate[candidate_index] = scored[0][1]

    replacements = 0
    used_candidates: set[int] = set()
    # El algoritmo es codicioso deliberadamente: cada cambio debe mejorar el
    # control completo por sí mismo, por lo que una lectura alternativa mala
    # no puede compensarse con otra cifra inventada.
    for index, item in enumerate(recovered):
        line, origin = item[:2]
        current = parsear_linea_clasificada_observada(
            normalizar_linea_ocr_tabla(str(line)), index, ".", 0.75,
        )
        if current is None or current.monto is None:
            continue
        current_amount = float(current.monto)
        current_name = current.nombre
        if current.es_total:
            continue

        best: Optional[tuple[float, int, str, dict[str, float]]] = None
        for candidate_index, (candidate_name, candidate_amount, candidate_origin) in enumerate(candidates):
            if (
                candidate_index in used_candidates
                or candidate_origin is not origin
                or target_by_candidate.get(candidate_index) != index
            ):
                continue
            if abs(candidate_amount - current_amount) <= tolerancia_absoluta:
                continue
            if not _nombres_ocr_fuertemente_compatibles(
                current_name, candidate_name,
            ):
                continue
            replacement_amount = f"{int(round(candidate_amount)):,}".replace(
                ",", ".",
            )
            replacement_line = f"{current_name} {replacement_amount}"
            tentative = list(recovered)
            tentative[index] = (replacement_line, *item[1:])
            errores_despues = errores_subtotales(tentative)
            mejora, puntaje = mejora_local_de_control(
                errores_antes, errores_despues,
            )
            if not mejora:
                continue
            if confirmar_importe is None:
                # Sin un recorte focal que confirme la alternativa, se
                # conserva el umbral histórico de mejora material sobre el
                # documento completo. Esto evita que un desacuerdo minúsculo
                # entre dos pasadas de OCR sustituya una cifra ya legible.
                error_agregado_despues = error_agregado(errores_despues)
                mejora_minima = max(100_000.0, error_agregado_antes * 0.01)
                if (
                    error_agregado_despues
                    > error_agregado_antes - mejora_minima
                ):
                    continue
            elif not confirmar_importe(index, candidate_amount):
                continue
            if best is None or puntaje > best[0]:
                best = (
                    puntaje, candidate_index, replacement_line,
                    errores_despues,
                )
        if best is None:
            continue
        _, candidate_index, replacement_line, errores_antes = best
        error_agregado_antes = error_agregado(errores_antes)
        recovered[index] = (replacement_line, *item[1:])
        recovered_flags[index] = True
        used_candidates.add(candidate_index)
        replacements += 1

    return recovered, recovered_flags, replacements


def recuperar_importes_balance_clasificado_por_control_focal(
    lineas_coordenadas: list[tuple],
    evidencias_importes: list[Optional[dict[str, Any]]],
    *, tolerancia_absoluta: float = 10.0,
    releer_importe: Optional[Any] = None,
) -> tuple[list[tuple], list[bool], list[dict[str, Any]]]:
    """Repara un dígito de detalle con OCR focal y su subtotal impreso.

    Esta vía cubre un caso que la lectura OCR lineal no puede proponer: ambas
    pasadas generales pueden repetir el mismo dígito equivocado. El residuo
    de un subtotal sólo selecciona las celdas cuyo cambio de un dígito lo
    resolvería por sí solo; la cifra se acepta únicamente si la lectura focal
    independiente coincide. Conserva la ecuación final cuando ésta ya era
    válida. Los subtotales impresos nunca se cambian.
    """
    if (
        not lineas_coordenadas
        or len(lineas_coordenadas) != len(evidencias_importes)
    ):
        return list(lineas_coordenadas), [False] * len(lineas_coordenadas), []

    def errores_subtotales(items: list[tuple]) -> dict[str, float]:
        return {
            nombre: abs(float(diferencia))
            for nombre, diferencia in _diferencias_subtotales_fisicos_clasificados(
                _cuentas_desde_lineas_clasificadas(items),
            ).items()
        }

    def mejora_local(
        antes: dict[str, float], despues: dict[str, float],
    ) -> tuple[bool, float]:
        nombres = set(antes) | set(despues)
        if any(
            despues.get(nombre, 0.0)
            > antes.get(nombre, 0.0) + tolerancia_absoluta
            for nombre in nombres
        ):
            return False, 0.0
        mejora = sum(
            antes.get(nombre, 0.0) - despues.get(nombre, 0.0)
            for nombre in nombres
        )
        return mejora > tolerancia_absoluta, mejora

    def candidatos_exactos_por_residuo(
        items: list[tuple],
    ) -> dict[int, set[float]]:
        """Ubica qué detalle podría resolver por sí solo un subtotal fallido.

        El cálculo no constituye evidencia de la nueva cifra: sólo evita
        releer todas las celdas de una página. La relectura focal posterior
        debe observar exactamente el valor propuesto y pasar los controles.
        """
        candidatos: dict[int, set[float]] = {}
        cuentas = _cuentas_desde_lineas_clasificadas(items)
        for origen in (OrigenColumna.ACTIVO, OrigenColumna.PASIVO):
            detalles: list[CuentaRaw] = []
            suma_detalles = 0.0
            for cuenta in (
                cuenta for cuenta in cuentas if cuenta.origen_columna is origen
            ):
                if cuenta.monto is None:
                    continue
                if _es_subtotal_fisico_clasificado(cuenta.nombre, origen):
                    diferencia = suma_detalles - float(cuenta.monto)
                    if abs(diferencia) > tolerancia_absoluta:
                        for detalle in detalles:
                            candidato = round(
                                float(detalle.monto) - diferencia, 2,
                            )
                            candidatos.setdefault(detalle.linea, set()).add(
                                candidato,
                            )
                    detalles = []
                    suma_detalles = 0.0
                    continue
                if cuenta.es_total:
                    continue
                detalles.append(cuenta)
                suma_detalles += float(cuenta.monto)
        return candidatos

    recovered = list(lineas_coordenadas)
    recovered_flags = [False] * len(recovered)
    cambios: list[dict[str, Any]] = []
    cache_imagenes: dict[tuple[str, int], Image.Image] = {}
    lector = releer_importe or (
        lambda evidencia, monto_actual: _importe_clasificado_focal_unico(
            evidencia, monto_actual, cache_imagenes,
        )
    )

    # Cada vuelta modifica una sola fila comprobada. Se vuelve a calcular la
    # base antes de proponer la siguiente para impedir que dos candidatos se
    # compensen mutuamente sin mejorar el control que los habilita.
    for _ in range(len(recovered)):
        errores_antes = errores_subtotales(recovered)
        if not any(
            diferencia > tolerancia_absoluta
            for diferencia in errores_antes.values()
        ):
            break
        candidatos_por_residuo = candidatos_exactos_por_residuo(recovered)
        if not candidatos_por_residuo:
            break
        cuentas_antes = _cuentas_desde_lineas_clasificadas(recovered)
        certificacion_antes = certificar_totales_clasificados(
            cuentas_antes, metodo="ocr_classified_two_columns",
        )
        propuestas: list[tuple[float, int, str, dict[str, float]]] = []
        for indice, montos_esperados in candidatos_por_residuo.items():
            item = recovered[indice]
            linea, _origen = item[:2]
            cuenta = parsear_linea_clasificada_observada(
                normalizar_linea_ocr_tabla(str(linea)), indice, ".", 0.75,
            )
            if (
                cuenta is None
                or cuenta.monto is None
                or cuenta.es_total
                or evidencias_importes[indice] is None
            ):
                continue
            monto_actual = float(cuenta.monto)
            monto_focal = lector(evidencias_importes[indice], monto_actual)
            if (
                monto_focal is None
                or abs(float(monto_focal) - monto_actual) <= tolerancia_absoluta
                or not any(
                    abs(float(monto_focal) - monto_esperado)
                    <= tolerancia_absoluta
                    for monto_esperado in montos_esperados
                )
            ):
                continue
            token_original = str(linea).split()[-1] if str(linea).split() else ""
            if not _difiere_un_digito_monetario(token_original, monto_focal):
                continue
            monto_texto = _formatear_entero_monetario_focal(
                monto_focal, token_original,
            )
            candidata_linea = f"{cuenta.nombre} {monto_texto}"
            tentativa = list(recovered)
            tentativa[indice] = (candidata_linea, *item[1:])
            errores_despues = errores_subtotales(tentativa)
            mejora, puntaje = mejora_local(errores_antes, errores_despues)
            if not mejora:
                continue
            certificacion_despues = certificar_totales_clasificados(
                _cuentas_desde_lineas_clasificadas(tentativa),
                metodo="ocr_classified_two_columns",
            )
            if (
                certificacion_antes.totales_finales_validos is True
                and certificacion_despues.totales_finales_validos is not True
            ):
                continue
            propuestas.append((puntaje, indice, candidata_linea, errores_despues))
        if not propuestas:
            break
        propuestas.sort(key=lambda propuesta: (-propuesta[0], propuesta[1]))
        mejor_puntaje, indice, candidata_linea, errores_despues = propuestas[0]
        if sum(
            abs(puntaje - mejor_puntaje) <= 0.01
            for puntaje, _indice, _linea, _errores in propuestas
        ) != 1:
            break
        recovered[indice] = (candidata_linea, *recovered[indice][1:])
        recovered_flags[indice] = True
        cambios.append({
            "linea": indice,
            "origen": "relectura_focal_por_subtotal_clasificado",
            "subtotal_error_despues": errores_despues,
        })
    return recovered, recovered_flags, cambios


def _conservar_evidencia_celdas_no_reemplazada(
    lineas_originales: list[str],
    evidencias_originales: list[Optional[dict[str, Any]]],
    lineas_recuperadas: list[str],
) -> list[Optional[dict[str, Any]]]:
    """Conserva evidencia focal sólo para filas que no cambió la recuperación.

    La reconciliación con una lectura OCR alternativa puede corregir una o
    pocas filas de una tabla por coordenadas. El recorte de esas filas ya no
    representa el texto final y debe descartarse, pero eliminar la evidencia
    de toda la página impedía releer de forma focal las demás celdas, que
    siguen ancladas a la misma imagen. Si se agregaron o quitaron filas no
    existe una correspondencia posicional segura y se descarta el conjunto.
    """
    if (
        len(lineas_originales) != len(evidencias_originales)
        or len(lineas_originales) != len(lineas_recuperadas)
    ):
        return [None] * len(lineas_recuperadas)
    return [
        evidencia if original == recuperada else None
        for original, evidencia, recuperada in zip(
            lineas_originales, evidencias_originales, lineas_recuperadas,
        )
    ]


_CONTROLES_FINALES_PARTIDOS_OCR = {
    "totalgeneral": "TOTAL GENERAL",
    "sumasiguales": "SUMAS IGUALES",
    "totalesiguales": "TOTALES IGUALES",
    "sumastotales": "SUMAS TOTALES",
}


def _etiqueta_control_final_partido_ocr(linea: str) -> Optional[str]:
    """Devuelve la etiqueta canónica de un cierre que puede partirse.

    Algunos balances escaneados imprimen la mitad izquierda de un control
    final junto a su rótulo y la mitad derecha en el renglón siguiente, sin
    repetir el nombre. Esta función sólo admite los cuatro cierres conocidos;
    un subtotal ordinario o una cuenta nunca entra por esta vía.
    """
    normalizada = normalizar_linea_ocr_tabla(linea)
    primer_importe = PATRON_MONTOS.search(normalizada)
    etiqueta = (
        normalizada[:primer_importe.start()]
        if primer_importe is not None else normalizada
    )
    clave = re.sub(
        r"[^a-z0-9]+", "", _sin_acentos(etiqueta).lower(),
    )
    return _CONTROLES_FINALES_PARTIDOS_OCR.get(clave)


def _importes_ocr_partidos(linea: str) -> list[float] | None:
    """Lee exactamente cuatro importes observados de una mitad OCR."""
    normalizada = normalizar_linea_ocr_tabla(linea)
    tokens = PATRON_MONTOS.findall(normalizada)
    if len(tokens) != 4:
        return None
    importes: list[float] = []
    for token in tokens:
        monto = parsear_monto(token, ".")
        if monto is None:
            return None
        importes.append(float(monto))
    return importes


def _es_continuacion_numerica_ocr(linea: str) -> bool:
    """Acepta sólo una continuación sin glosa contable.

    Tesseract puede dejar un residuo de hasta tres letras, por ejemplo
    ``IIA``. Una palabra real se conserva como posible cuenta y no se fusiona.
    """
    normalizada = normalizar_linea_ocr_tabla(linea)
    primer_importe = PATRON_MONTOS.search(normalizada)
    if primer_importe is None:
        return False
    prefijo = normalizada[:primer_importe.start()].strip()
    return not prefijo or bool(re.fullmatch(r"[A-Za-z]{1,3}", prefijo))


def _control_final_ocr_cuadra(cuenta: CuentaRaw) -> bool:
    """Valida las igualdades propias de un cierre de ocho columnas.

    Una fila ``SUMAS IGUALES`` puede incorporar el puente de resultado y por
    eso no siempre cumple la identidad de una cuenta individual entre saldos
    y clasificación. El control final sí debe mostrar pares iguales y la
    ecuación Activo + Pérdida = Pasivo + Ganancia. Activo no tiene por qué
    coincidir aisladamente con Pasivo, ni Pérdida con Ganancia.
    """
    valores = cuenta.montos_columnas
    if set(valores) != set(RAW_MONETARY_COLUMNS):
        return False
    pares = (
        ("debitos", "creditos"),
        ("saldo_deudor", "saldo_acreedor"),
    )
    return bool(
        all(
            abs(
                float(valores[izquierda] or 0.0)
                - float(valores[derecha] or 0.0)
            ) <= 10
            for izquierda, derecha in pares
        )
        and abs(
            float(valores["activo"] or 0.0)
            + float(valores["perdida"] or 0.0)
            - float(valores["pasivo"] or 0.0)
            - float(valores["ganancia"] or 0.0)
        ) <= 10
    )


def _control_final_ocr_incompleto(cuenta: Optional[CuentaRaw]) -> bool:
    """Indica si una mitad de cierre dejó uno de sus pares vacío."""
    if cuenta is None:
        return True
    return any(
        (
            float(cuenta.montos_columnas.get(izquierda, 0.0) or 0.0) == 0
        ) != (
            float(cuenta.montos_columnas.get(derecha, 0.0) or 0.0) == 0
        )
        for izquierda, derecha in (
            ("debitos", "creditos"),
            ("saldo_deudor", "saldo_acreedor"),
            ("activo", "pasivo"),
            ("perdida", "ganancia"),
        )
    )


def _es_continuacion_derecha_control_ocr(linea: str) -> bool:
    """Reconoce el renglón sin etiqueta que acompaña a un cierre partido."""
    normalizada = normalizar_linea_ocr_tabla(linea)
    primer_importe = PATRON_MONTOS.search(normalizada)
    if primer_importe is None:
        return False
    prefijo = normalizada[:primer_importe.start()].strip()
    return bool(
        len(PATRON_MONTOS.findall(normalizada)) >= 4
        and (
            not prefijo
            or bool(re.fullmatch(r"[A-Za-z]{1,3}", prefijo))
        )
    )


def recomponer_controles_finales_ocr_partidos(
    lineas: list[str],
) -> tuple[list[str], int]:
    """Reconstruye cierres OCR partidos sólo con pares complementarios.

    La primera línea debe contener exactamente los cuatro importes izquierdos
    (Debe, saldo deudor, Activo y Pérdida) y la inmediata siguiente los cuatro
    derechos. La candidata se vuelve a parsear y debe satisfacer las dos
    igualdades impresas. Por tanto no infiere una cifra ni fusiona una cuenta
    que esté simplemente cerca de un total.
    """
    recompuestas: list[str] = []
    cantidad = 0
    indice = 0
    while indice < len(lineas):
        actual = normalizar_linea_ocr_tabla(lineas[indice])
        siguiente = (
            normalizar_linea_ocr_tabla(lineas[indice + 1])
            if indice + 1 < len(lineas) else ""
        )
        etiqueta = _etiqueta_control_final_partido_ocr(actual)
        izquierdos = _importes_ocr_partidos(actual) if etiqueta else None
        derechos = _importes_ocr_partidos(siguiente)
        if (
            etiqueta is not None
            and izquierdos is not None
            and derechos is not None
            and _es_continuacion_numerica_ocr(siguiente)
            and any(abs(valor) > 0.01 for valor in izquierdos)
            and any(abs(valor) > 0.01 for valor in derechos)
        ):
            valores = [
                izquierdos[0], derechos[0],
                izquierdos[1], derechos[1],
                izquierdos[2], derechos[2],
                izquierdos[3], derechos[3],
            ]
            candidata = (
                f"{etiqueta} "
                + " ".join(str(int(round(valor))) for valor in valores)
            )
            cuenta = parsear_linea(
                candidata, indice, FormatoCodigo.SIN_CODIGO, ".", 0.75,
            )
            if (
                cuenta is not None
                and cuenta.es_total
                and _control_final_ocr_cuadra(cuenta)
            ):
                recompuestas.append(candidata)
                cantidad += 1
                indice += 2
                continue
        recompuestas.append(actual)
        indice += 1
    return recompuestas, cantidad


def recuperar_filas_tabla_ocr(
    lineas_coordenadas: list[str], texto_alternativo: str,
    *,
    solo_controles_finales: bool = False,
) -> tuple[list[str], int]:
    """Recupera celdas omitidas usando PSM 4 sin duplicar la tabla.

    Exige glosas compatibles y dos identidades contables válidas. La alternativa
    puede completar una fila vacía, movimientos Debe/Haber omitidos o una fila
    completa que el OCR geométrico no vio, siempre que no exista ya el mismo
    código ni una glosa equivalente. ``solo_controles_finales`` restringe la
    recuperación a cierres partidos, para una relectura OCR adicional que no
    debe alterar cuentas de detalle.
    """
    lineas_alternativas, _ = recomponer_controles_finales_ocr_partidos(
        texto_alternativo.splitlines(),
    )
    alternatives: dict[str, tuple[str, CuentaRaw]] = {}
    ordered_alternatives: list[tuple[str, CuentaRaw]] = []
    alternative_controls: dict[str, str] = {}
    alternative_final_controls: dict[str, str] = {}
    for index, line in enumerate(lineas_alternativas):
        account = _cuenta_desde_candidato_ocr(line, index)
        if account is not None:
            alternatives[_codigo_contable_canonico(account.codigo)] = (line, account)
            ordered_alternatives.append((line, account))
        normalized_control = normalizar_linea_ocr_tabla(line)
        control_match = re.match(
            r"^\W*(sumas?|subtotales?)\b", normalized_control, re.I,
        )
        if control_match:
            alternative_controls[control_match.group(1).lower()] = normalized_control
        etiqueta_final = _etiqueta_control_final_partido_ocr(normalized_control)
        if etiqueta_final is not None:
            alternative_final_controls[etiqueta_final] = normalized_control

    current_accounts = [
        account
        for index, line in enumerate(lineas_coordenadas)
        if (
            account := _cuenta_desde_candidato_ocr(
                line, index, exigir_consistencia=False,
            )
        ) is not None
    ]
    recovered: list[str] = []
    replacements = 0
    continuaciones_suprimidas: set[int] = set()
    for index, line in enumerate(lineas_coordenadas):
        if index in continuaciones_suprimidas:
            # Preserva el índice de las evidencias TSV, pero evita que una
            # mitad sin etiqueta se convierta luego en una cuenta espuria.
            recovered.append("")
            continue
        normalized_current = normalizar_linea_ocr_tabla(line)
        etiqueta_final_actual = _etiqueta_control_final_partido_ocr(
            normalized_current,
        )
        alternate_final = (
            alternative_final_controls.get(etiqueta_final_actual)
            if etiqueta_final_actual is not None else None
        )
        if alternate_final is not None:
            control_alternativo = parsear_linea(
                alternate_final, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
            )
            control_actual = parsear_linea(
                normalized_current, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
            )
            if (
                control_alternativo is not None
                and control_alternativo.es_total
                and _control_final_ocr_cuadra(control_alternativo)
                and _control_final_ocr_incompleto(control_actual)
            ):
                recovered.append(alternate_final)
                replacements += 1
                if (
                    index + 1 < len(lineas_coordenadas)
                    and _es_continuacion_derecha_control_ocr(
                        lineas_coordenadas[index + 1],
                    )
                ):
                    continuaciones_suprimidas.add(index + 1)
                continue
        current_control_match = re.match(
            r"^\W*(sumas?|subtotales?)\b", normalized_current, re.I,
        )
        if current_control_match:
            alternate_control = alternative_controls.get(
                current_control_match.group(1).lower(),
            )
            if alternate_control:
                control_alternativo = parsear_linea(
                    alternate_control, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
                )
                control_actual = parsear_linea(
                    normalized_current, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
                )
                if (
                    control_alternativo is not None
                    and control_alternativo.es_total
                    and _control_final_ocr_cuadra(control_alternativo)
                    and (
                        control_actual is None
                        or _error_identidades_cuenta(control_actual) > 10
                        or _control_final_ocr_incompleto(control_actual)
                    )
                ):
                        recovered.append(alternate_control)
                        replacements += 1
                        continue
                current_amounts = [
                    float(parsear_monto(token.replace(",", "."), ".") or 0.0)
                    for token in _MONTO_AGRUPADO_OCR.findall(normalized_current)
                ]
                alternate_amounts = [
                    float(parsear_monto(token.replace(",", "."), ".") or 0.0)
                    for token in _MONTO_AGRUPADO_OCR.findall(alternate_control)
                ]
                current_tail = current_amounts[-6:]
                alternate_head = alternate_amounts[:6]
                if (
                    len(current_tail) == 6
                    and len(alternate_head) == 6
                    and all(
                        abs(left - right) <= 10
                        for left, right in zip(alternate_head[2:], current_tail[:4])
                    )
                ):
                    combined = alternate_head[:2] + current_tail
                    combined_line = (
                        f"{current_control_match.group(1)} "
                        + " ".join(str(int(round(value))) for value in combined)
                    )
                    combined_account = parsear_linea(
                        combined_line, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
                    )
                    if (
                        combined_account is not None
                        and _error_identidades_cuenta(combined_account) <= 10
                    ):
                        recovered.append(combined_line)
                        replacements += 1
                        continue

        if solo_controles_finales:
            recovered.append(line)
            continue

        current = _cuenta_desde_candidato_ocr(
            line, index, exigir_consistencia=False,
        )
        if current is None:
            recovered.append(line)
            continue
        alternative_pair = alternatives.get(_codigo_contable_canonico(current.codigo))
        if alternative_pair is None:
            recovered.append(line)
            continue
        alternative_line, alternative = alternative_pair
        if not _nombres_ocr_compatibles(current.nombre, alternative.nombre):
            recovered.append(line)
            continue

        current_values = current.montos_columnas
        alternative_values = alternative.montos_columnas
        current_balance = tuple(
            current_values[column]
            for column in ("saldo_deudor", "saldo_acreedor")
        )
        alternative_balance = tuple(
            alternative_values[column]
            for column in ("saldo_deudor", "saldo_acreedor")
        )
        current_classification = tuple(
            current_values[column]
            for column in ("activo", "pasivo", "perdida", "ganancia")
        )
        alternative_classification = tuple(
            alternative_values[column]
            for column in ("activo", "pasivo", "perdida", "ganancia")
        )
        current_empty = not any(current_values.values())
        alternative_has_data = any(alternative_values.values())
        current_invalid = _error_identidades_cuenta(current) > 10
        added_debit = alternative_values["debitos"] - current_values["debitos"]
        added_credit = alternative_values["creditos"] - current_values["creditos"]
        completes_movements = (
            current_balance == alternative_balance
            and current_classification == alternative_classification
            and added_debit > 0
            and abs(added_debit - added_credit) <= 10
        )
        if (
            (current_empty and alternative_has_data)
            or current_invalid
            or completes_movements
        ):
            normalized = normalizar_codigo_ocr(normalizar_linea_ocr_tabla(alternative_line))
            # Conserva las ocho posiciones para que el parseo definitivo use
            # exactamente la misma estructura validada arriba.
            parsed_normalized = parsear_linea(
                normalized, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
            )
            if parsed_normalized is None or not parsed_normalized.montos_columnas:
                for suffix in (" 0", " 0 0"):
                    padded = normalized + suffix
                    parsed = parsear_linea(
                        padded, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
                    )
                    if (
                        parsed is not None
                        and parsed.montos_columnas
                        and _error_identidades_cuenta(parsed) <= 10
                        and parsed.montos_columnas == alternative_values
                    ):
                        normalized = padded
                        break
            recovered.append(normalized)
            replacements += 1
        else:
            recovered.append(line)

    if solo_controles_finales:
        return recovered, replacements

    # PSM 6 por coordenadas puede omitir una línea completa aunque PSM 4 la
    # lea con sus ocho columnas. Se incorpora únicamente evidencia contable
    # autoconsistente y se evita duplicar tanto por código como por glosa; así
    # una variante OCR del código (4.02.09.60 vs 4.02.04.60) tampoco duplica la
    # cuenta ya observada.
    current_codes = {
        _codigo_contable_canonico(account.codigo) for account in current_accounts
    }
    for alternative_line, alternative in ordered_alternatives:
        alternative_code = _codigo_contable_canonico(alternative.codigo)
        normalized_alternative = normalizar_linea_ocr_tabla(alternative_line)
        is_control = bool(re.match(
            r"^\W*(?:sumas?|subtotales?|totales?|resultado|utilidad)\b",
            normalized_alternative,
            re.I,
        ))
        already_present = alternative_code in current_codes or any(
            _nombres_ocr_compatibles(current.nombre, alternative.nombre)
            for current in current_accounts
        )
        if already_present or alternative.es_total or is_control:
            continue
        normalized = normalizar_codigo_ocr(normalized_alternative)
        recovered.append(normalized)
        current_accounts.append(alternative)
        current_codes.add(alternative_code)
        replacements += 1
    return recovered, replacements


_PATRON_CONTROL_OCHO_COLUMNAS = re.compile(
    r"^\W*(?:sumas?|sub[-\s]?totales?|total(?:es)?|"
    r"perdida\s+o\s+ganancia|resultado|utilidad|"
    r"ganancia(?:\s+(?:del\s+)?ejercicio|\s+neta))\b",
    re.I,
)


def _cuenta_ocho_columnas_nativa_valida(
    linea: str, numero_linea: int,
) -> Optional[CuentaRaw]:
    """Lee una fila nativa de ocho columnas sin aplicar reparaciones OCR.

    La lectura textual nativa puede conservar mejor las celdas vacías que una
    reconstrucción geométrica. Sólo se admite como evidencia alternativa si
    mantiene las ocho columnas y las dos identidades por fila son exactas.
    """
    normalizada = normalizar_codigo_ocr(normalizar_linea_ocr_tabla(linea))
    cuenta = parsear_linea(
        normalizada,
        numero_linea,
        FormatoCodigo.SIN_CODIGO,
        ".",
        1.0,
    )
    if (
        cuenta is None
        or not cuenta.codigo
        or set(cuenta.montos_columnas) != set(RAW_MONETARY_COLUMNS)
        or _error_identidades_cuenta(cuenta) > 10
    ):
        return None
    return cuenta


def _control_ocho_columnas_nativo_valido(
    linea: str, numero_linea: int,
) -> Optional[CuentaRaw]:
    """Devuelve un control nativo sólo cuando su identidad es verificable."""
    normalizada = normalizar_codigo_ocr(normalizar_linea_ocr_tabla(linea))
    if not _PATRON_CONTROL_OCHO_COLUMNAS.match(normalizada):
        return None
    cuenta = parsear_linea(
        normalizada,
        numero_linea,
        FormatoCodigo.SIN_CODIGO,
        ".",
        1.0,
    )
    if (
        cuenta is None
        or not cuenta.es_total
        or set(cuenta.montos_columnas) != set(RAW_MONETARY_COLUMNS)
        or _error_identidades_cuenta(cuenta) > 10
    ):
        return None
    return cuenta


def _clave_control_ocho_columnas(cuenta: CuentaRaw) -> str:
    return re.sub(
        r"[^a-z0-9]+", "", _sin_acentos(cuenta.nombre).lower(),
    )


def preparar_candidato_texto_nativo_ocho_columnas(
    lineas_coordenadas: list[str], texto_nativo: str,
) -> Optional[dict[str, Any]]:
    """Prepara una lectura nativa alternativa de una tabla geométrica.

    No selecciona todavía la alternativa. Reúne únicamente filas que ya son
    autoconsistentes y métricas de coincidencia de códigos para que el
    llamador pueda preferirla sólo a nivel de documento, nunca por una fila
    aislada.
    """
    cuentas_coordenadas = [
        cuenta
        for indice, linea in enumerate(lineas_coordenadas)
        if (
            cuenta := _cuenta_ocho_columnas_nativa_valida(linea, indice)
        ) is not None
    ]
    lineas_nativas: list[str] = []
    cuentas_nativas: list[CuentaRaw] = []
    controles_nativos: list[CuentaRaw] = []
    for indice, linea in enumerate(texto_nativo.splitlines()):
        cuenta = _cuenta_ocho_columnas_nativa_valida(linea, indice)
        if cuenta is not None:
            lineas_nativas.append(linea)
            cuentas_nativas.append(cuenta)
            continue
        control = _control_ocho_columnas_nativo_valido(linea, indice)
        if control is not None:
            lineas_nativas.append(linea)
            controles_nativos.append(control)

    if not lineas_nativas or not cuentas_coordenadas or not cuentas_nativas:
        return None

    codigos_coordenadas = {
        _codigo_contable_canonico(cuenta.codigo)
        for cuenta in cuentas_coordenadas
    } - {""}
    codigos_nativos = {
        _codigo_contable_canonico(cuenta.codigo)
        for cuenta in cuentas_nativas
    } - {""}
    if not codigos_coordenadas or not codigos_nativos:
        return None
    controles_certificables = sum(
        1
        for cuenta in controles_nativos
        if (
            "subtotal" in _clave_control_ocho_columnas(cuenta)
            or _clave_control_ocho_columnas(cuenta) == "sumas"
            or _clave_control_ocho_columnas(cuenta).startswith("totalacumulado")
        )
    )
    return {
        "lineas": lineas_nativas,
        "cuentas_coordenadas": len(cuentas_coordenadas),
        "cuentas_nativas": len(cuentas_nativas),
        "codigos_coordenadas": codigos_coordenadas,
        "codigos_nativos": codigos_nativos,
        "controles_certificables": controles_certificables,
    }


def debe_preferirse_texto_nativo_ocho_columnas(
    candidatos: list[dict[str, Any]], paginas_coordenadas: int,
) -> bool:
    """Decide si una tabla nativa supera a la reconstrucción geométrica.

    La preferencia exige cobertura casi total de los mismos códigos, al menos
    un subtotal compatible con la certificación existente y más filas válidas
    que la alternativa geométrica. Si cualquier página de la tabla no aporta
    el contraste, se mantiene el extractor anterior.
    """
    if not candidatos or len(candidatos) != paginas_coordenadas:
        return False
    cuentas_coordenadas = sum(
        int(candidato["cuentas_coordenadas"]) for candidato in candidatos
    )
    cuentas_nativas = sum(
        int(candidato["cuentas_nativas"]) for candidato in candidatos
    )
    if (
        cuentas_coordenadas < 8
        or cuentas_nativas < 8
        or cuentas_nativas <= cuentas_coordenadas
        or not any(candidato["controles_certificables"] for candidato in candidatos)
    ):
        return False
    codigos_coordenadas = set().union(
        *(candidato["codigos_coordenadas"] for candidato in candidatos)
    )
    codigos_nativos = set().union(
        *(candidato["codigos_nativos"] for candidato in candidatos)
    )
    comparables = min(len(codigos_coordenadas), len(codigos_nativos))
    if comparables < 8:
        return False
    coincidencia = len(codigos_coordenadas & codigos_nativos) / comparables
    return coincidencia >= 0.95


def _tabla_ocr_tiene_control_final_incompleto(lineas: list[str]) -> bool:
    """Detecta un cierre con sólo una de sus dos mitades observadas."""
    for indice, linea in enumerate(lineas):
        if _etiqueta_control_final_partido_ocr(linea) is None:
            continue
        cuenta = parsear_linea(
            normalizar_linea_ocr_tabla(linea), indice,
            FormatoCodigo.SIN_CODIGO, ".", 0.75,
        )
        if cuenta is None or not cuenta.es_total:
            continue
        for izquierda, derecha in (
            ("debitos", "creditos"),
            ("saldo_deudor", "saldo_acreedor"),
            ("activo", "pasivo"),
            ("perdida", "ganancia"),
        ):
            if (
                float(cuenta.montos_columnas.get(izquierda, 0.0) or 0.0) == 0
            ) != (
                float(cuenta.montos_columnas.get(derecha, 0.0) or 0.0) == 0
            ):
                return True
    return False


def _tabla_ocr_necesita_recuperacion(lineas: list[str]) -> bool:
    for index, line in enumerate(lineas):
        normalized = normalizar_linea_ocr_tabla(line)
        if (
            re.match(r"^\W*(?:sumas?|subtotales?)\b", normalized, re.I)
            and len(_MONTO_AGRUPADO_OCR.findall(normalized)) >= 4
        ):
            parsed_control = parsear_linea(
                normalized, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
            )
            if (
                parsed_control is None
                or not parsed_control.montos_columnas
                or not any(parsed_control.montos_columnas.values())
                or _error_identidades_cuenta(parsed_control) > 10
            ):
                return True
        account = _cuenta_desde_candidato_ocr(
            line, index, exigir_consistencia=False,
        )
        if account is not None and _error_identidades_cuenta(account) > 10:
            return True
        if account is None or any(account.montos_columnas.values()):
            continue
        grouped_amounts = _MONTO_AGRUPADO_OCR.findall(line)
        if any(re.sub(r"\D", "", token).lstrip("0") for token in grouped_amounts):
            return True
    return False


def _texto_palabras_ocr(words: list[dict]) -> str:
    """Une una celda OCR conservando el orden visual de sus palabras."""
    return " ".join(
        str(word.get("text", "")).strip()
        for word in sorted(words, key=lambda word: float(word["x0"]))
        if str(word.get("text", "")).strip()
    ).strip()


def _celda_clasificada_ocr(
    words: list[dict], *, amount_min_x: float,
) -> Optional[tuple[str, str]]:
    """Obtiene ``(glosa, importe)`` de una mitad de balance clasificado.

    Los balances clasificados escaneados suelen tener una glosa y un solo
    importe por mitad de página. El umbral horizontal evita tomar como monto
    un número que forme parte de la glosa (por ejemplo, ``CTA 2``).
    """
    ordered = sorted(words, key=lambda word: float(word["x0"]))
    amount_index: Optional[int] = None
    amount = ""
    for index in range(len(ordered) - 1, -1, -1):
        word = ordered[index]
        token = str(word.get("text", "")).strip()
        xmid = (float(word["x0"]) + float(word["x1"])) / 2
        normalized = normalizar_token_ocr(token).replace("$", "")
        if (
            xmid >= amount_min_x
            and re.search(r"\d", normalized)
            and PATRON_MONTOS.fullmatch(normalized)
        ):
            amount_index = index
            amount = normalized
            break
    if amount_index is None:
        return None

    name_tokens = []
    for word in ordered[:amount_index]:
        token = str(word.get("text", "")).strip()
        # Marcas marginales de Tesseract (|, !, /) no son parte de la glosa.
        if token and re.search(r"[A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ]", token):
            name_tokens.append(token)
    name = " ".join(name_tokens).strip()
    # En filas paralelas puede ocurrir que el importe ``0`` del extremo
    # izquierdo quede apenas a la derecha del corte geométrico y anteceda al
    # total derecho. Es un artefacto de la separación, no parte de la glosa:
    # sólo se elimina ante el patrón inequívoco ``importe + TOTAL ...``.
    name = re.sub(
        r"^(?:[-+]?\d{1,3}(?:[.,]\d{3})*|[-+]?\d+)\s+(?=TOTAL\b)",
        "",
        name,
        flags=re.I,
    ).strip()
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", name):
        return None
    return name, amount


def _evidencia_importe_clasificado_ocr(
    words: list[dict], *, amount_min_x: float,
) -> Optional[dict[str, Any]]:
    """Conserva la caja del importe que originó una celda clasificada.

    La extracción geométrica de dos columnas usa una sola cifra por mitad.
    Guardar su caja permite contrastar más tarde un desacuerdo con una lectura
    OCR focal sobre el mismo píxel, sin deducir importes desde subtotales.
    """
    try:
        ordered = sorted(words, key=lambda word: float(word["x0"]))
        for word in reversed(ordered):
            token = str(word.get("text", "")).strip()
            xmid = (float(word["x0"]) + float(word["x1"])) / 2
            normalized = normalizar_token_ocr(token).replace("$", "")
            if not (
                xmid >= amount_min_x
                and re.search(r"\d", normalized)
                and PATRON_MONTOS.fullmatch(normalized)
            ):
                continue
            top = float(word.get("image_top", word["top"]))
            bottom = float(word.get("image_bottom", word["top"]))
            if bottom <= top:
                bottom = top + 1.0
            return {
                "bbox": (
                    float(word["x0"]), top,
                    float(word["x1"]), bottom,
                ),
                "token": token,
            }
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _es_total_final_activo(nombre: str) -> bool:
    """Reconoce un total final de activos, no un subtotal de sección."""
    normalized = re.sub(r"\s+", " ", _sin_acentos(nombre)).upper().strip()
    if "TOTAL" not in normalized or "ACTIV" not in normalized:
        return False
    return not any(
        marker in normalized
        for marker in (
            "CIRCUL", "CORRIENT", "FIJO", "NO CORRIENT", "OTROS",
        )
    )


def _seccion_contable_doble_columna(
    texto: str, origen: OrigenColumna,
) -> Optional[str]:
    """Reconoce una cabecera sin importe dentro de un balance clasificado.

    ``origen`` describe el lado físico de la hoja. La sección devuelve la
    naturaleza contable explícitamente rotulada dentro de ese lado. En
    particular, un mismo lado derecho puede pasar de PASIVO a PATRIMONIO.
    No se aplica a filas con importe, porque allí una glosa similar a una
    cabecera puede ser una cuenta real.
    """
    normalizado = re.sub(
        r"\s+", " ", _sin_acentos(texto).upper(),
    ).strip(" :$.-")
    if not normalizado:
        return None
    if origen is OrigenColumna.ACTIVO:
        if re.fullmatch(
            r"ACTIVOS?(?: (?:CORRIENTES?|NO CORRIENTES?|CIRCULANTES?|FIJOS?))?"
            r"|(?:CURRENT|NON CURRENT) ASSETS?|ASSETS?",
            normalizado,
        ):
            return "activo"
        return None
    if origen is OrigenColumna.PASIVO:
        if re.match(
            r"^(?:PATRIMONIO(?: NETO)?(?:\b| )|EQUITY(?:\b| )|"
            r"CAPITAL(?: Y RESERVAS?)?$)",
            normalizado,
        ):
            return "patrimonio"
        if re.fullmatch(
            r"PASIVOS?(?: (?:CORRIENTES?|NO CORRIENTES?|CIRCULANTES?|"
            r"A LARGO PLAZO))?|(?:CURRENT|NON CURRENT) LIABILITIES|LIABILITIES",
            normalizado,
        ):
            return "pasivo"
    return None


def _extraer_balance_clasificado_doble_columna_por_coordenadas(
    page, *, permitir_continuacion: bool = False,
    incluir_seccion_contable: bool = False,
    incluir_evidencia_importes: bool = False,
    secciones_iniciales: Optional[dict[OrigenColumna, Optional[str]]] = None,
) -> Any:
    """Extrae un balance OCR ACTIVO | PASIVO preservando su lado físico.

    No es un fallback textual genérico: sólo se activa tras observar una
    cabecera ACTIVO|PASIVO y al menos cinco filas paralelas con glosa e importe
    en ambas mitades. En páginas posteriores del mismo documento se permite
    continuidad si mantienen al menos ocho filas paralelas. Así una tabla de
    ocho columnas o dos bloques de texto normales siguen por el flujo usual.

    Con ``incluir_seccion_contable`` agrega una tercera posición por fila con
    la sección observada. Es metadato audit-able y no sustituye el lado físico.
    Con ``incluir_evidencia_importes`` devuelve también una evidencia por fila
    con la caja OCR del importe observado.
    El parámetro por defecto conserva la interfaz histórica de pares
    ``(texto, origen)`` usada por los tests y por consumidores externos.
    """
    def resultado(
        filas: list[tuple], evidencias: list[Optional[dict[str, Any]]],
    ) -> Any:
        if incluir_evidencia_importes:
            return filas, evidencias
        return filas

    try:
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
        groups = _agrupar_palabras_por_linea(words)
        page_width = max(float(word["x1"]) for word in words)
    except (AttributeError, KeyError, TypeError, ValueError):
        return resultado([], [])
    if page_width < 200 or not groups:
        return resultado([], [])

    split_x = page_width / 2
    left_amount_min_x = split_x * 0.72
    right_amount_min_x = split_x + ((page_width - split_x) * 0.58)
    candidates: list[tuple[
        Optional[tuple[str, str]], Optional[tuple[str, str]],
        Optional[dict[str, Any]], Optional[dict[str, Any]],
    ]] = []
    secciones = {
        OrigenColumna.ACTIVO: None,
        OrigenColumna.PASIVO: None,
    }
    if secciones_iniciales:
        for origen in secciones:
            secciones[origen] = secciones_iniciales.get(origen)
    contextos: list[tuple[Optional[str], Optional[str]]] = []
    header_detected = False

    for group in groups:
        left_words = [
            word for word in group
            if (float(word["x0"]) + float(word["x1"])) / 2 < split_x
        ]
        right_words = [
            word for word in group
            if (float(word["x0"]) + float(word["x1"])) / 2 >= split_x
        ]
        left_text = _sin_acentos(_texto_palabras_ocr(left_words)).upper()
        right_text = _sin_acentos(_texto_palabras_ocr(right_words)).upper()
        left_cell = _celda_clasificada_ocr(
            left_words, amount_min_x=left_amount_min_x,
        )
        right_cell = _celda_clasificada_ocr(
            right_words, amount_min_x=right_amount_min_x,
        )
        left_evidence = (
            _evidencia_importe_clasificado_ocr(
                left_words, amount_min_x=left_amount_min_x,
            )
            if left_cell is not None else None
        )
        right_evidence = (
            _evidencia_importe_clasificado_ocr(
                right_words, amount_min_x=right_amount_min_x,
            )
            if right_cell is not None else None
        )
        # Las cabeceras de sección no tienen importe y por tanto no se emiten
        # como cuentas. Se leen antes de asignar contexto a las filas de la
        # misma página. Esto permite que el lado físico PASIVO siga intacto y
        # que una sección PATRIMONIO dentro de él se haga explícita.
        if left_cell is None:
            seccion_izquierda = _seccion_contable_doble_columna(
                left_text, OrigenColumna.ACTIVO,
            )
            if seccion_izquierda:
                secciones[OrigenColumna.ACTIVO] = seccion_izquierda
        if right_cell is None:
            seccion_derecha = _seccion_contable_doble_columna(
                right_text, OrigenColumna.PASIVO,
            )
            if seccion_derecha:
                secciones[OrigenColumna.PASIVO] = seccion_derecha
        if (
            left_cell is None
            and right_cell is None
            and re.search(r"\bACTIVOS?\b", left_text)
            and re.search(r"\b(?:PASIVOS?|PATRIMONIO)\b", right_text)
        ):
            header_detected = True
        candidates.append((
            left_cell, right_cell, left_evidence, right_evidence,
        ))
        contextos.append((
            secciones[OrigenColumna.ACTIVO],
            secciones[OrigenColumna.PASIVO],
        ))

    paired_rows = sum(
        left is not None and right is not None
        for left, right, _left_evidence, _right_evidence in candidates
    )
    if not header_detected and not (permitir_continuacion and paired_rows >= 8):
        return resultado([], [])
    if paired_rows < 5:
        return resultado([], [])

    extracted: list[tuple] = []
    evidencias_importes: list[Optional[dict[str, Any]]] = []
    for (
        left, right, left_evidence, right_evidence,
    ), (seccion_izquierda, seccion_derecha) in zip(
        candidates, contextos,
    ):
        def agregar(
            nombre: str, monto: str, origen: OrigenColumna,
            seccion: Optional[str], evidencia_importe: Optional[dict[str, Any]],
        ) -> None:
            fila = (f"{nombre} {monto}", origen)
            if incluir_seccion_contable:
                fila = (*fila, seccion)
            extracted.append(fila)
            evidencias_importes.append(evidencia_importe)

        if left is not None and right is not None:
            left_name, left_amount = left
            right_name, right_amount = right
            # La última fila de algunos escaneos pierde "TOTAL" sólo en la
            # derecha (p. ej. OFAL PASIVOS). La pareja física TOTAL ACTIVOS |
            # PASIVOS permite restaurar únicamente ese rótulo final.
            if _es_total_final_activo(left_name):
                left_name = "TOTAL ACTIVOS"
                right_normalized = _sin_acentos(right_name).upper()
                if "PATRIMONIO" in right_normalized:
                    right_name = "TOTAL PASIVOS Y PATRIMONIO"
                elif "PASIV" in right_normalized:
                    right_name = "TOTAL PASIVOS"
            agregar(
                left_name, left_amount, OrigenColumna.ACTIVO,
                seccion_izquierda, left_evidence,
            )
            agregar(
                right_name, right_amount, OrigenColumna.PASIVO,
                seccion_derecha, right_evidence,
            )
        elif left is not None:
            name, amount = left
            agregar(
                name, amount, OrigenColumna.ACTIVO, seccion_izquierda,
                left_evidence,
            )
        elif right is not None:
            name, amount = right
            agregar(
                name, amount, OrigenColumna.PASIVO, seccion_derecha,
                right_evidence,
            )
    if secciones_iniciales is not None:
        secciones_iniciales.update(secciones)
    return resultado(extracted, evidencias_importes)


# ─────────────────────────────────────────────────────────────────────────────
# PARSER PRINCIPAL PDF
# ─────────────────────────────────────────────────────────────────────────────

class ParserPDF:

    def parsear(
        self,
        path: Path,
        context: Optional[ExtractionContext] = None,
    ) -> ResultadoParseo:
        ok, msg = validar_archivo(path)
        if not ok:
            return ResultadoParseo(
                archivo=path.name, formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
                advertencias=[f"VALIDACIÓN FALLIDA: {msg}"]
            )

        # Sprint 31 — Análisis documental ANTES del parseo.
        # Lee solo las primeras páginas, produce un FormatSignature y decide
        # extractor vía ExtractorFactory. NO cambia la extracción: si el
        # análisis falla, se continúa exactamente como antes (backward
        # compatibility).
        advertencias_iniciales: list[str] = []
        try:
            documento_ctx = self._analizar_documento(path)
        except Exception as exc:  # noqa: BLE001 — backward compatibility
            logger.debug(
                "Análisis documental falló (%s); usando flujo clásico.",
                exc, exc_info=True,
            )
            documento_ctx = None
        if documento_ctx is not None:
            logger.info("\n" + documento_ctx.to_log_block())
            for w in documento_ctx.warnings:
                if w not in advertencias_iniciales:
                    advertencias_iniciales.append(w)

        self._ocr_advertencias: list[str] = []
        self._extraction_method = "text"
        # Metadatos paralelos a las líneas OCR. Sólo se rellenan cuando una
        # extracción geométrica de balance clasificado observó el lado físico
        # de cada importe; el flujo textual conserva ``None``.
        self._origenes_lineas_ocr: list[Optional[OrigenColumna]] = []
        # Paralelo a ``_origenes_lineas_ocr``: sección contable explícita
        # observada en un encabezado del documento. No reemplaza la columna
        # física y queda vacía cuando el extractor no la pudo observar.
        self._secciones_lineas_ocr: list[Optional[str]] = []
        # Paralelo a las líneas extraídas: una marca sólo se activa cuando un
        # importe geométrico fue confirmado por el OCR textual y mejoró un
        # subtotal. La salida conserva esa condición para revisión humana.
        self._importes_recuperados_ocr: list[bool] = []
        self._ocr_orientation_evidence: list[dict[str, Any]] = []
        self._ocr_orientation_certified = True
        lineas, requirio_ocr, rotacion = self._extraer_lineas(path, context)

        if not lineas:
            return ResultadoParseo(
                archivo=path.name, formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles='.', requirio_ocr=requirio_ocr,
                rotacion_aplicada=rotacion,
                advertencias=(
                    self._ocr_advertencias
                    + ["No se pudo extraer texto (ni nativo ni OCR)"]
                ),
                document_context=documento_ctx,
                orientacion_certificada=(
                    self._ocr_orientation_certified if requirio_ocr else None
                ),
                orientaciones_paginas=list(self._ocr_orientation_evidence),
            )

        if requirio_ocr:
            lineas = [normalizar_linea_ocr_tabla(l) for l in lineas]
        elif self._extraction_method not in {
            "coordinates_8_amounts",
            "native_table_8_columns",
            "native_text_8_columns_validated",
            "native_layout_8_columns",
            "native_classified_two_columns",
        }:
            lineas = [normalizar_montos_fragmentados(l) for l in lineas]
        lineas = [normalizar_codigo_ocr(l) for l in lineas]
        lineas = etiquetar_subtotales_anonimos(lineas)
        origenes_lineas = list(self._origenes_lineas_ocr)
        secciones_lineas = list(self._secciones_lineas_ocr)
        importes_recuperados = list(self._importes_recuperados_ocr)
        if len(origenes_lineas) != len(lineas):
            # Una implementación de extractor nunca debe desalinear los
            # metadatos de su texto. Si ocurriera, se prefiere no usar la
            # señal adicional antes que atribuir una columna equivocada.
            origenes_lineas = [None] * len(lineas)
        if len(secciones_lineas) != len(lineas):
            # La sección sólo es útil si apunta exactamente a la misma fila
            # que su lado físico. Ante desalineación se descarta, no se
            # propaga por proximidad.
            secciones_lineas = [None] * len(lineas)
        if len(importes_recuperados) != len(lineas):
            # La auditoría nunca se desplaza entre filas: si los metadatos no
            # calzan, se descarta la marca antes que atribuirla a otra cuenta.
            importes_recuperados = [False] * len(lineas)

        primer_tokens = [l.split()[0] if l.split() else '' for l in lineas[:60]]
        formato_codigo = detectar_formato_codigo(primer_tokens)

        muestra_montos = []
        for l in lineas[:80]:
            muestra_montos.extend(PATRON_MONTOS.findall(l))
        separador = detectar_separador_miles(muestra_montos)
        periodo_comparativo = any(
            re.search(r"\bactual\s+anterior\b", _sin_acentos(linea), re.I)
            or re.fullmatch(r"\s*(?:19|20)\d{2}\s+(?:19|20)\d{2}\s*", linea)
            for linea in lineas
        )

        # 3b. Detectar layout de columnas
        # Prioridad:
        #   1) ExtractionContext (de DocumentAnalyzer) si confianza suficiente
        #   2) Perfil de familia aprendido (Sprint 36, solo si ENABLE_DYNAMIC_LAYOUT)
        #   3) LayoutDetector interno (solo si ENABLE_DYNAMIC_LAYOUT)
        #   4) Heurística estándar (ULTIMAS_COLS) por defecto
        advertencias = list(advertencias_iniciales) + self._ocr_advertencias
        column_order: Optional[list[OrigenColumna]] = None
        layout_columns: Optional[list[str]] = None

        # Sprint 36 — detección anticipada de familia/extractor (se reutiliza
        # en _anotar_extractor para no detectar dos veces). Gated por
        # ENABLE_DYNAMIC_LAYOUT: si falla, todo continúa como antes.
        detectado_extractor: Optional[dict] = None
        if ENABLE_DYNAMIC_LAYOUT and documento_ctx is not None:
            try:
                from document_intelligence.extractors.factory import (
                    SpecializedExtractorFactory,
                )
                detectado_extractor = SpecializedExtractorFactory().detect(
                    path, documento_ctx,
                )
            except Exception as exc:  # noqa: BLE001 — fallback deliberado
                logger.debug(
                    "Detección anticipada de extractor falló; "
                    "se sigue con heurística estándar: %s", exc,
                )

        if context and context.layout_hint and context.layout_confidence >= LAYOUT_CONFIDENCE_THRESHOLD:
            layout_columns = list(context.layout_hint)
            cols = []
            for c in layout_columns:
                oc = _LAYOUT_COLUMN_MAP.get(c)
                if oc is not None:
                    cols.append(oc)
            if len(cols) >= 2:
                column_order = cols
                advertencias.append(
                    f"LayoutDetector (context): {len(cols)} columnas "
                    f"({', '.join(c.value for c in cols)}), "
                    f"confianza={context.layout_confidence:.2f}"
                )
            else:
                advertencias.append(
                    "LayoutDetector detectó columnas en contexto pero ninguna "
                    "fue reconocida — usando heurística estándar."
                )
        elif detectado_extractor is not None and detectado_extractor.get(
            "family_id"
        ) not in (None, "", "DESCONOCIDO"):
            # Perfil de familia aprendido (Sprint 36): el orden de columnas
            # proviene del training (Sprint 35) para la familia detectada.
            # Se aplica con cualquier familia match de confianza, tenga o no
            # extractor registrado (los perfiles existen para las 23 familias).
            try:
                from document_intelligence.extractors.profile_driven import (
                    profile_layout_hint,
                )
                hint = profile_layout_hint(
                    path, documento_ctx,
                    family_id=detectado_extractor.get("family_id", ""),
                    lines=lineas,
                )
            except Exception as exc:  # noqa: BLE001 — fallback deliberado
                hint = None
                logger.debug(
                    "Perfil de familia no aplicable (%s); heurística estándar.",
                    exc,
                )
            if hint:
                cols = []
                for c in hint:
                    oc = _LAYOUT_COLUMN_MAP.get(c)
                    if oc is not None:
                        cols.append(oc)
                if len(cols) >= 2:
                    column_order = cols
                    layout_columns = list(hint)
                    advertencias.append(
                        f"Perfil de familia "
                        f"({detectado_extractor.get('family_id', '')}): "
                        f"{len(cols)} columnas "
                        f"({', '.join(c.value for c in cols)})"
                    )
                else:
                    advertencias.append(
                        "Perfil de familia sin columnas aprovechables — "
                        "usando heurística estándar."
                    )
            else:
                advertencias.append(
                    "Perfil de familia no aplicable o sin cobertura — "
                    "usando heurística estándar."
                )
        elif ENABLE_DYNAMIC_LAYOUT:
            from parsers.layout_detector import LayoutDetector
            detector = LayoutDetector()
            layout = detector.detect(lineas)
            if layout.confidence >= 0.5:
                layout_columns = list(layout.columns)
                cols = []
                for c in layout.columns:
                    oc = _LAYOUT_COLUMN_MAP.get(c)
                    if oc is not None:
                        cols.append(oc)
                if len(cols) >= 2:
                    column_order = cols
                    advertencias.append(
                        f"LayoutDetector: {len(cols)} columnas "
                        f"({', '.join(c.value for c in cols)}), "
                        f"confianza={layout.confidence:.2f}"
                    )
                else:
                    advertencias.append(
                        "LayoutDetector detectó columnas pero ninguna "
                        "fue reconocida — usando heurística estándar."
                    )
            else:
                advertencias.append(
                    f"LayoutDetector: confianza insuficiente "
                    f"({layout.confidence:.2f}) — usando heurística estándar."
                )

        # Scan years and currencies dynamically
        years, currencies = detectar_años_y_monedas(lineas)

        # Pre-process lines to associate vertical labels and amounts
        if not any(origen is not None for origen in origenes_lineas):
            lineas = asociar_lineas_verticales(lineas)
        else:
            advertencias.append(
                "OCR geométrico: se preservó la columna física ACTIVO/PASIVO "
                "de un balance clasificado de dos columnas."
            )

        # 4. Parsear todas las líneas
        confianza = 0.75 if requirio_ocr else 1.0
        cuentas = []
        for i, l in enumerate(lineas):
            origen_observado = origenes_lineas[i]
            seccion_observada = secciones_lineas[i]
            importe_recuperado = importes_recuperados[i]
            corte_lateral_ambiguo = False
            if origen_observado is not None:
                sub_lines = [l]
            else:
                sub_lines, corte_lateral_ambiguo = (
                    _separar_linea_lateral_con_evidencia(
                        l, i, formato_codigo, separador, confianza,
                    )
                )
                if corte_lateral_ambiguo:
                    advertencias.append(
                        f"Fila {i + 1}: posible tabla lateral sin dos códigos "
                        "contables; se conservó completa para revisión."
                    )
            for sub_l in sub_lines:
                if origen_observado is not None:
                    c = parsear_linea_clasificada_observada(
                        sub_l, i, separador, confianza,
                    )
                else:
                    c = parsear_linea(
                        sub_l, i, formato_codigo, separador, confianza,
                        column_order=column_order,
                        periodo_comparativo=periodo_comparativo,
                        years=years,
                        currencies=currencies,
                    )
                if c:
                    if corte_lateral_ambiguo:
                        c.columnas_derivadas = [
                            *c.columnas_derivadas,
                            "corte_lateral_ambiguo_sin_dos_codigos",
                        ]
                    if origen_observado is not None and c.monto is not None:
                        c.origen_columna = origen_observado
                        c.seccion_contable = seccion_observada
                        # No son ocho columnas reconstruidas: es la columna
                        # física observada en el OCR. Mantenerla evita que el
                        # anotador de secciones sobrescriba ACTIVO/PASIVO con
                        # un encabezado textual visto en otra página.
                        c.montos_columnas = {
                            origen_observado.value: float(c.monto),
                        }
                    if importe_recuperado:
                        c.columnas_derivadas = [
                            *c.columnas_derivadas,
                            "importe_recuperado_ocr",
                        ]
                    cuentas.append(c)

        cuentas, cuentas_partidas = fusionar_cuentas_partidas(cuentas)
        cuentas, controles_finales_partidos = fusionar_control_total_general_partido(cuentas)
        cuentas, pie_no_contable_descartado = (
            descartar_pie_no_contable_despues_cierre(cuentas)
        )
        jerarquicos = marcar_subtotales_jerarquicos(cuentas)
        if jerarquicos:
            advertencias.append(
                f"Se reconocieron {jerarquicos} subtotales jerárquicos por código y "
                "sumas de sus cuentas. Se conservan como controles, sin duplicar el detalle."
            )
        if cuentas_partidas:
            advertencias.append(
                f"Se reconstruyeron {cuentas_partidas} cuentas partidas entre "
                "su código, glosa e importes."
            )
        if controles_finales_partidos:
            advertencias.append(
                f"Se reconstruyeron {controles_finales_partidos} control(es) "
                "TOTAL GENERAL partidos en dos columnas físicas."
            )
        if pie_no_contable_descartado:
            advertencias.append(
                f"Se descartaron {pie_no_contable_descartado} fila(s) sin "
                "código posteriores al cierre final; corresponden a pie, "
                "firma o metadatos OCR, no a cuentas contables."
            )

        secciones_anotadas = anotar_secciones_balance_clasificado(cuentas)
        if secciones_anotadas:
            advertencias.append(
                f"Se recuperó la sección contable de {secciones_anotadas} cuentas "
                "desde encabezados del balance clasificado."
            )
        estados_anotados = anotar_estado_financiero(cuentas)
        if estados_anotados:
            advertencias.append(
                f"Se identificó el estado financiero de {estados_anotados} filas "
                "desde encabezados explícitos del documento."
            )

        # NOTA (Fase A): la resolución de tipo_cuenta se eliminó de ParserPDF.
        # El parser es un extractor pasivo: NO escribe CuentaRaw.tipo_cuenta.
        # La resolución contable ocurre fuera del parser (HomologationPipeline
        # o reportes vía AccountTypeResolver).
        # Ver reports/cuenta_raw_architecture/fase_a_impact_analysis.md.

        if requirio_ocr:
            advertencias.append(
                f"Documento procesado vía OCR (rotación={rotacion}°). "
                "Confianza de extracción reducida a 0.75 — recomendar revisión humana."
            )

        if not requirio_ocr and rotacion == 180 and context and context.rotation_confidence >= ROTATION_CORRECTION_THRESHOLD:
            advertencias.append(
                f"Documento corregido desde rotación 180° "
                f"(confianza={context.rotation_confidence:.2f})"
            )

        certificacion = certificar_extraccion_columnas(
            cuentas, metodo=self._extraction_method,
        )
        if requirio_ocr:
            certificacion = _anotar_certificacion_orientacion(
                certificacion, self._ocr_orientation_evidence,
            )
        if certificacion.estado == "no_evaluable":
            certificacion_clasificada = certificar_totales_clasificados(
                cuentas, metodo=self._extraction_method,
            )
            if certificacion_clasificada.estado != "no_evaluable":
                certificacion = certificacion_clasificada
                if requirio_ocr:
                    certificacion = _anotar_certificacion_orientacion(
                        certificacion, self._ocr_orientation_evidence,
                    )

        if requirio_ocr:
            # ResultadoParseo mantiene este atributo histórico en paralelo a
            # CertificacionExtraccion. La segunda lectura tabular o el
            # consenso documental pueden haber recuperado una página que la
            # sonda inicial había dejado ambigua.
            self._ocr_orientation_certified = bool(
                certificacion.orientacion_certificada
            )

        resultado = ResultadoParseo(
            archivo=path.name,
            formato_codigo=formato_codigo,
            separador_miles=separador,
            requirio_ocr=requirio_ocr,
            rotacion_aplicada=rotacion,
            cuentas=cuentas,
            advertencias=advertencias,
            document_context=documento_ctx,
            certificacion_extraccion=certificacion,
            orientacion_certificada=(
                self._ocr_orientation_certified if requirio_ocr else None
            ),
            orientaciones_paginas=list(self._ocr_orientation_evidence),
        )
        if resultado.certificacion_extraccion.estado == "fallida":
            resultado.advertencias.extend(resultado.certificacion_extraccion.razones)
        self._anotar_extractor(resultado, detectado_extractor)
        return resultado

    def _anotar_extractor(
        self,
        resultado: ResultadoParseo,
        detectado: Optional[dict] = None,
    ) -> None:
        """Sprint 34 — anota `extractor_info` SIN cambiar la extracción.

        `detectado` es el resultado de la detección anticipada del Sprint 36
        (si ENABLE_DYNAMIC_LAYOUT la computó antes del bucle de parseo);
        si viene None se detecta aquí. Si la factory falla, `extractor_info`
        queda en None y el parseo continúa exactamente igual (backward
        compatibility / fallback obligatorio).
        """
        if resultado.document_context is None:
            return
        try:
            if detectado is None:
                from document_intelligence.extractors.factory import (
                    SpecializedExtractorFactory,
                )
                detectado = SpecializedExtractorFactory().detect(
                    resultado.document_context.pdf_path,
                    resultado.document_context,
                )
            resultado.extractor_info = detectado
        except Exception as exc:  # noqa: BLE001 — fallback deliberado
            logger.debug(
                "Anotación de extractor falló; se omite: %s", exc, exc_info=True,
            )

    def _analizar_documento(self, path: Path) -> Optional[Any]:
        """Sprint 31 — análisis documental previo al parseo.

        Nunca lanza excepción: si el análisis falla retorna None y el flujo
        continúa exactamente como antes (backward compatibility).
        """
        try:
            from document_intelligence.context import analyze_document_preview
            return analyze_document_preview(path)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Document Intelligence no disponible (%s); "
                "usando flujo clásico.", exc, exc_info=True,
            )
            return None

    def _extraer_lineas(
        self,
        path: Path,
        context: Optional[ExtractionContext] = None,
    ) -> tuple[list[str], bool, int]:
        # Sprint F: si un extractor especializado ya separó las líneas
        # (p. ej. doble columna ACTIVO|PASIVO), usarlas directamente. Se
        # reutiliza íntegramente el pipeline de parseo posterior (formato,
        # separador, parsear_linea); no se duplica ninguna lógica.
        if context is not None and context.lineas_presplit:
            lineas = [l for l in context.lineas_presplit if l.strip()]
            if lineas:
                return lineas, False, 0

        lineas: list[str] = []
        # Los metadatos no son exclusivos de OCR: un PDF con texto nativo
        # puede tener el mismo layout ACTIVO | PASIVO. Se conservan en las
        # listas históricas para que el parseo posterior trate ambos orígenes
        # de forma idéntica y nunca vuelva a inferir el lado por posición.
        origenes_lineas: list[Optional[OrigenColumna]] = []
        secciones_lineas: list[Optional[str]] = []
        # Conserva el layout monetario detectado entre paginas nativas. Debe
        # existir incluso cuando la primera pagina no contiene una tabla de
        # ocho columnas; de lo contrario el fallback por coordenadas intentaba
        # leer una variable local aun no inicializada.
        coordinate_centers: Optional[list[float]] = None
        formulario_tributario_activo = False
        balance_tributario_ocho_columnas_detectado = False
        anexo_clasificado_activo = False
        clasificado_doble_detectado = False
        secciones_clasificadas: dict[OrigenColumna, Optional[str]] = {
            OrigenColumna.ACTIVO: None,
            OrigenColumna.PASIVO: None,
        }
        # Las coordenadas son el respaldo habitual para tablas nativas de
        # ocho columnas. En ciertos PDF, sin embargo, los ceros impresos en
        # celdas estrechas se asignan a la columna vecina. Se registra una
        # alternativa textual, pero sólo se preferirá al terminar el documento
        # si todas las páginas de esa tabla pasan sus salvaguardas conjuntas.
        reemplazos_texto_nativo: list[dict[str, Any]] = []
        paginas_tabla_coordenadas = 0

        n_paginas = 0
        try:
            with pdfplumber.open(path) as pdf:
                n_paginas = len(pdf.pages)
                for numero_pagina, page in enumerate(pdf.pages, 1):
                    texto = page.extract_text() or ""
                    if not texto.strip():
                        continue
                    omitir, formulario_tributario_activo = (
                        _debe_omitir_pagina_formulario_tributario(
                            texto, formulario_tributario_activo,
                        )
                    )
                    if omitir:
                        self._ocr_advertencias.append(
                            f"Página {numero_pagina}: se omitió un Formulario 22 "
                            "adjunto al balance."
                        )
                        continue
                    if _es_balance_clasificado_suplementario(
                        texto,
                        balance_tributario_ocho_columnas_detectado,
                    ):
                        anexo_clasificado_activo = True
                        self._ocr_advertencias.append(
                            f"Página {numero_pagina}: se omitió un BALANCE "
                            "CLASIFICADO suplementario porque el BALANCE "
                            "TRIBUTARIO de ocho columnas ya fue extraído."
                        )
                        continue
                    if anexo_clasificado_activo and _es_estado_resultado(texto):
                        self._ocr_advertencias.append(
                            f"Página {numero_pagina}: se omitió un ESTADO DE "
                            "RESULTADO suplementario del BALANCE CLASIFICADO."
                        )
                        continue
                    if (
                        clasificado_doble_detectado
                        and _es_estado_resultado(texto)
                    ):
                        # Un estado de resultados puede tener dos bloques
                        # paralelos, pero no es continuación física de
                        # ACTIVO|PASIVO. Se vuelve a exigir cabecera antes de
                        # usar el extractor clasificado en esta página.
                        clasificado_doble_detectado = False
                        secciones_clasificadas = {
                            OrigenColumna.ACTIVO: None,
                            OrigenColumna.PASIVO: None,
                        }

                    clasificado = (
                        _extraer_balance_clasificado_doble_columna_por_coordenadas(
                            page,
                            permitir_continuacion=clasificado_doble_detectado,
                            incluir_seccion_contable=True,
                            secciones_iniciales=secciones_clasificadas,
                        )
                    )
                    if clasificado:
                        lineas_pagina = [linea for linea, _, _ in clasificado]
                        lineas.extend(lineas_pagina)
                        origenes_lineas.extend(
                            origen for _, origen, _ in clasificado
                        )
                        secciones_lineas.extend(
                            seccion for _, _, seccion in clasificado
                        )
                        self._extraction_method = "native_classified_two_columns"
                        clasificado_doble_detectado = True
                        continue
                    # Sprint F — doble columna: si la página parece tener dos
                    # columnas de cuenta (pre-filtro barato sobre el texto plano),
                    # intentar la separación estructural por coordenadas (x0).
                    # Si el análisis no confirma, se conserva el texto plano tal
                    # cual (comportamiento universal idéntico).
                    page_lineas: Optional[list[str]] = None
                    try:
                        from document_intelligence.extractors.double_column import (
                            _prefiltro_sugiere,
                            separar_page,
                        )
                        if _prefiltro_sugiere(texto):
                            page_lineas = separar_page(page)
                    except Exception as exc:  # noqa: BLE001 — fallback seguro
                        logger.debug(
                            "Detección de doble columna no disponible (%s); "
                            "universal.", exc,
                        )
                    if page_lineas:
                        lineas_pagina = [l for l in page_lineas if l.strip()]
                    else:
                        tabla_8_columnas = _extraer_tabla_balance_8_columnas(page)
                        if tabla_8_columnas:
                            self._extraction_method = "native_table_8_columns"
                            lineas_pagina = tabla_8_columnas
                            if _es_balance_tributario(texto):
                                balance_tributario_ocho_columnas_detectado = True
                        else:
                            tabla_coordenadas, detected_centers = (
                                _extraer_tabla_balance_por_coordenadas(
                                    page, coordinate_centers,
                                )
                            )
                            coordinate_centers = detected_centers
                            if tabla_coordenadas:
                                self._extraction_method = "coordinates_8_amounts"
                                lineas_pagina = tabla_coordenadas
                                paginas_tabla_coordenadas += 1
                                candidato_nativo = (
                                    preparar_candidato_texto_nativo_ocho_columnas(
                                        tabla_coordenadas, texto,
                                    )
                                )
                                if candidato_nativo is not None:
                                    candidato_nativo["inicio"] = len(lineas)
                                    candidato_nativo["fin"] = (
                                        len(lineas) + len(lineas_pagina)
                                    )
                                    reemplazos_texto_nativo.append(
                                        candidato_nativo
                                    )
                                if _es_balance_tributario(texto):
                                    balance_tributario_ocho_columnas_detectado = True
                            else:
                                lineas_pagina = texto.split('\n')
                    lineas.extend(lineas_pagina)
                    origenes_lineas.extend([None] * len(lineas_pagina))
                    secciones_lineas.extend([None] * len(lineas_pagina))
        except Exception as exc:  # noqa: BLE001 — OCR es el respaldo seguro
            logger.warning(
                "No se pudo abrir %s con pdfplumber; se intentará OCR: %s",
                path.name, exc,
            )

        if debe_preferirse_texto_nativo_ocho_columnas(
            reemplazos_texto_nativo, paginas_tabla_coordenadas,
        ):
            lineas_reemplazadas: list[str] = []
            origenes_reemplazados: list[Optional[OrigenColumna]] = []
            secciones_reemplazadas: list[Optional[str]] = []
            cursor = 0
            for candidato in reemplazos_texto_nativo:
                inicio = int(candidato["inicio"])
                fin = int(candidato["fin"])
                lineas_reemplazadas.extend(lineas[cursor:inicio])
                origenes_reemplazados.extend(origenes_lineas[cursor:inicio])
                secciones_reemplazadas.extend(secciones_lineas[cursor:inicio])
                lineas_candidato = list(candidato["lineas"])
                lineas_reemplazadas.extend(lineas_candidato)
                origenes_reemplazados.extend([None] * len(lineas_candidato))
                secciones_reemplazadas.extend([None] * len(lineas_candidato))
                cursor = fin
            lineas_reemplazadas.extend(lineas[cursor:])
            origenes_reemplazados.extend(origenes_lineas[cursor:])
            secciones_reemplazadas.extend(secciones_lineas[cursor:])
            lineas = lineas_reemplazadas
            origenes_lineas = origenes_reemplazados
            secciones_lineas = secciones_reemplazadas
            self._extraction_method = "native_text_8_columns_validated"
            self._ocr_advertencias.append(
                "Se priorizó la lectura textual nativa de la tabla de ocho "
                "columnas: conserva más filas autoconsistentes que la "
                "reconstrucción geométrica y coincide en sus códigos."
            )

        if lineas:
            texto_lateral_recompuesto = False
            if _texto_nativo_parece_lateral(lineas):
                lineas_layout = _extraer_texto_nativo_layout(path)
                if lineas_layout:
                    lineas = lineas_layout
                    # Poppler recompone el orden visual de la tabla. No hay
                    # evidencia geométrica fila a fila para conservar aquí,
                    # por lo que se descartan los metadatos de la lectura
                    # lateral antes que asociarlos a otra cuenta.
                    origenes_lineas = [None] * len(lineas)
                    secciones_lineas = [None] * len(lineas)
                    self._extraction_method = "native_layout_8_columns"
                    texto_lateral_recompuesto = True
                    self._ocr_advertencias.append(
                        "El texto nativo contenía encabezados laterales "
                        "invertidos; se recompuso la tabla con el layout "
                        "nativo y se exigirán sus controles impresos."
                    )
            self._origenes_lineas_ocr = origenes_lineas
            self._secciones_lineas_ocr = secciones_lineas
            if (
                not texto_lateral_recompuesto
                and self._debe_corregir_rotacion(context)
            ):
                lineas = [ParserPDF._reverse_line(l) for l in lineas]
                return lineas, False, 180
            return lineas, False, 0

        if n_paginas <= 0:
            n_paginas = self._contar_paginas_rasterizables(path)
        if n_paginas <= 0:
            self._ocr_advertencias.append(
                "No se pudo determinar la cantidad de páginas para OCR."
            )
            return [], True, 0
        return self._ocr_documento(path, n_paginas)

    @staticmethod
    def _contar_paginas_rasterizables(path: Path) -> int:
        """Cuenta páginas con Poppler cuando pdfplumber no expone el árbol PDF.

        Algunos PDFs escaneados tienen un árbol de páginas que pdfplumber no
        recorre, pero Poppler sí puede rasterizarlos. El conteo se usa sólo
        para activar el OCR de respaldo y no altera la extracción normal.
        """
        pdfinfo_bin = shutil.which("pdfinfo") or "pdfinfo"
        try:
            result = subprocess.run(
                [pdfinfo_bin, str(path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return 0
        if result.returncode != 0:
            return 0
        match = re.search(r"^Pages:\s*(\d+)\s*$", result.stdout, re.MULTILINE)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _debe_corregir_rotacion(context: Optional[ExtractionContext]) -> bool:
        if not context:
            return False
        return (
            context.rotation_hint == 180
            and context.rotation_confidence >= ROTATION_CORRECTION_THRESHOLD
        )

    @staticmethod
    def _reverse_line(linea: str) -> str:
        if not linea.strip():
            return linea
        return " ".join(w[::-1] for w in linea.split())

    def _ocr_documento(self, path: Path, n_paginas: int) -> tuple[list[str], bool, int]:
        lineas: list[str] = []
        # ``text`` significaba históricamente tanto texto nativo como la
        # salida lineal de Tesseract. El método debe conservar el origen real
        # para que un diagnóstico no atribuya erróneamente el fallo al lector
        # nativo cuando ya se usó OCR.
        self._extraction_method = "ocr_text"
        origenes_lineas: list[Optional[OrigenColumna]] = []
        secciones_lineas: list[Optional[str]] = []
        importes_recuperados: list[bool] = []
        evidencias_celdas_ocr: list[Optional[dict[str, Any]]] = []
        rotaciones_paginas: list[int] = []
        # Segmentos de tablas de ocho columnas reconstruidas con PSM 6. Se
        # conservan para poder contrastar, al terminar el documento, una
        # segunda geometría PSM 4 sin sustituir filas de manera aislada.
        paginas_geometricas: list[dict[str, Any]] = []
        coordinate_centers: Optional[list[float]] = None
        clasificado_doble_detectado = False
        # Estado explícito observado en una página anterior de un balance
        # clasificado. Sólo se usa si una página de continuación vuelve a
        # superar las salvaguardas geométricas del extractor especializado.
        secciones_clasificadas: dict[OrigenColumna, Optional[str]] = {
            OrigenColumna.ACTIVO: None,
            OrigenColumna.PASIVO: None,
        }
        formulario_tributario_activo = False

        pdftoppm_bin = shutil.which('pdftoppm') or 'pdftoppm'

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            for pagina in range(1, n_paginas + 1):
                prefix = tmpdir_path / f'pg{pagina}'
                try:
                    raster = subprocess.run(
                        [pdftoppm_bin, '-png', '-gray', '-r', str(OCR_RENDER_DPI),
                         '-f', str(pagina), '-l', str(pagina),
                         str(path), str(prefix)],
                        capture_output=True, timeout=OCR_PAGE_TIMEOUT_SECONDS
                    )
                except subprocess.TimeoutExpired:
                    self._ocr_advertencias.append(
                        f"Página {pagina}: no pudo rasterizarse dentro de "
                        f"{OCR_PAGE_TIMEOUT_SECONDS} segundos y fue omitida."
                    )
                    self._ocr_orientation_evidence.append({
                        "pagina": pagina, "certificada": False,
                        "motivo": "rasterizacion_timeout", "candidatos": [],
                    })
                    self._ocr_orientation_certified = False
                    logger.warning(
                        "Rasterización OCR omitida por timeout en página %d de %s",
                        pagina,
                        path.name,
                    )
                    continue
                if raster.returncode != 0:
                    self._ocr_advertencias.append(
                        f"Página {pagina}: falló su rasterización OCR y fue omitida."
                    )
                    logger.warning(
                        "No se pudo rasterizar página %d de %s (código %s)",
                        pagina,
                        path.name,
                        raster.returncode,
                    )
                    self._ocr_orientation_evidence.append({
                        "pagina": pagina, "certificada": False,
                        "motivo": "rasterizacion_fallida", "candidatos": [],
                    })
                    self._ocr_orientation_certified = False
                    continue
                imgs = list(tmpdir_path.glob(f'pg{pagina}*.png'))
                if not imgs:
                    self._ocr_orientation_evidence.append({
                        "pagina": pagina, "certificada": False,
                        "motivo": "imagen_raster_no_encontrada", "candidatos": [],
                    })
                    self._ocr_orientation_certified = False
                    continue
                img_path = imgs[0]

                evidencia_orientacion = _seleccionar_orientacion_ocr(img_path)
                evidencia_orientacion["pagina"] = pagina
                rotacion = int(evidencia_orientacion["rotacion"])

                texto = ocr_pagina(img_path, rotacion)
                texto_principal = texto
                omitir, formulario_tributario_activo = (
                    _debe_omitir_pagina_formulario_tributario(
                        texto_principal, formulario_tributario_activo,
                    )
                )
                if omitir:
                    evidencia_orientacion["utilizada_en_extraccion"] = False
                    self._ocr_orientation_evidence.append(evidencia_orientacion)
                    self._ocr_advertencias.append(
                        f"Página {pagina}: se omitió un Formulario 22 adjunto "
                        "al balance."
                    )
                    continue
                texto_tabular, rotacion_tabular, evidencia_tabular = (
                    _recuperar_orientacion_por_tabla_ocr(
                        img_path, evidencia_orientacion,
                    )
                )
                if texto_tabular is not None:
                    texto = texto_tabular
                    texto_principal = texto_tabular
                    rotacion = rotacion_tabular
                    evidencia_orientacion = evidencia_tabular
                    # La lectura estructural puede volver legible la marca de
                    # un Formulario 22 que el OCR reducido no reconoció.
                    omitir_tabular, formulario_tributario_activo = (
                        _debe_omitir_pagina_formulario_tributario(
                            texto_principal, formulario_tributario_activo,
                        )
                    )
                    if omitir_tabular:
                        evidencia_orientacion["utilizada_en_extraccion"] = False
                        self._ocr_orientation_evidence.append(
                            evidencia_orientacion
                        )
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se omitió un Formulario 22 "
                            "adjunto al balance."
                        )
                        continue
                elif evidencia_tabular is not evidencia_orientacion:
                    evidencia_orientacion = evidencia_tabular
                evidencia_orientacion["utilizada_en_extraccion"] = True
                self._ocr_orientation_evidence.append(evidencia_orientacion)
                rotaciones_paginas.append(rotacion)
                if not evidencia_orientacion["certificada"]:
                    self._ocr_orientation_certified = False
                    self._ocr_advertencias.append(
                        f"Página {pagina}: la orientación OCR quedó sin certificar "
                        f"(rotación elegida={rotacion}°, margen="
                        f"{evidencia_orientacion['margen']:.1f})."
                    )
                if (
                    clasificado_doble_detectado
                    and re.search(
                        r"\bestado\s+de\s+resultados?\b",
                        _sin_acentos(texto_principal), re.I,
                    )
                ):
                    # Una página de resultados puede alinear detalle y
                    # subtotales en dos mitades. No corresponde tratarla como
                    # continuación física ACTIVO|PASIVO del balance previo.
                    clasificado_doble_detectado = False
                    coordinate_centers = None
                    secciones_clasificadas = {
                        OrigenColumna.ACTIVO: None,
                        OrigenColumna.PASIVO: None,
                    }
                words_tsv = ocr_pagina_tsv(img_path, rotacion)
                tabla_coordenadas_usada = False
                clasificado_doble_usado = False
                origenes_pagina: Optional[list[OrigenColumna]] = None
                secciones_pagina: Optional[list[Optional[str]]] = None
                importes_recuperados_pagina: Optional[list[bool]] = None
                evidencia_celdas_pagina: list[dict[str, Any]] = []
                evidencias_importes_clasificados_pagina: list[
                    Optional[dict[str, Any]]
                ] = []
                # La lectura lineal conserva una segmentación independiente
                # del TSV. Sólo se adjunta como evidencia para una posible
                # corrección posterior de una fila sin código; nunca cambia
                # por sí sola la tabla geométrica.
                lectura_cruzada_pagina = texto_principal
                if words_tsv:
                    (
                        tabla_ocr,
                        detected_centers,
                        evidencia_celdas_pagina,
                    ) = _extraer_tabla_balance_por_coordenadas(
                        _OCRWordsPage(words_tsv), coordinate_centers,
                        incluir_evidencia_celdas=True,
                    )
                    if len(tabla_ocr) >= 3 and detected_centers:
                        coordinate_centers = detected_centers
                        texto = "\n".join(tabla_ocr)
                        self._extraction_method = "ocr_coordinates_8_amounts"
                        tabla_coordenadas_usada = True
                    if not tabla_coordenadas_usada:
                        (
                            clasificado,
                            evidencias_importes_clasificados_pagina,
                        ) = _extraer_balance_clasificado_doble_columna_por_coordenadas(
                            _OCRWordsPage(words_tsv),
                            permitir_continuacion=clasificado_doble_detectado,
                            incluir_seccion_contable=True,
                            incluir_evidencia_importes=True,
                            secciones_iniciales=secciones_clasificadas,
                        )
                        if clasificado:
                            for evidencia_importe in (
                                evidencias_importes_clasificados_pagina
                            ):
                                if evidencia_importe is None:
                                    continue
                                evidencia_importe["imagen"] = str(img_path)
                                evidencia_importe["rotacion"] = rotacion
                            cache_importes_clasificados: dict[
                                tuple[str, int], Image.Image
                            ] = {}

                            def confirmar_importe_clasificado(
                                indice: int, monto: float,
                            ) -> bool:
                                if not (
                                    0 <= indice
                                    < len(evidencias_importes_clasificados_pagina)
                                ):
                                    return False
                                return _confirmar_importe_clasificado_ocr(
                                    evidencias_importes_clasificados_pagina[indice],
                                    monto, cache_importes_clasificados,
                                )

                            (
                                clasificado,
                                importes_recuperados_pagina,
                                replacements,
                            ) = recuperar_importes_balance_clasificado_ocr(
                                clasificado, texto_principal,
                                confirmar_importe=confirmar_importe_clasificado,
                            )
                            if replacements:
                                self._ocr_advertencias.append(
                                    f"Página {pagina}: se recuperaron "
                                    f"{replacements} importe(s) de balance "
                                    "clasificado al contrastar geometría, OCR "
                                    "textual y lectura focal; requieren revisión "
                                    "humana."
                                )
                            (
                                clasificado,
                                importes_releidos_focales,
                                cambios_focales_clasificados,
                            ) = recuperar_importes_balance_clasificado_por_control_focal(
                                clasificado,
                                evidencias_importes_clasificados_pagina,
                            )
                            if cambios_focales_clasificados:
                                importes_recuperados_pagina = [
                                    previo or releido
                                    for previo, releido in zip(
                                        importes_recuperados_pagina,
                                        importes_releidos_focales,
                                    )
                                ]
                                self._ocr_advertencias.append(
                                    f"Página {pagina}: se releyeron "
                                    f"{len(cambios_focales_clasificados)} "
                                    "importe(s) con OCR focal y subtotales "
                                    "impresos; requieren revisión humana."
                                )
                            texto = "\n".join(
                                linea for linea, _, _ in clasificado
                            )
                            origenes_pagina = [
                                origen for _, origen, _ in clasificado
                            ]
                            secciones_pagina = [
                                seccion for _, _, seccion in clasificado
                            ]
                            self._extraction_method = "ocr_classified_two_columns"
                            clasificado_doble_usado = True
                            clasificado_doble_detectado = True
                if tabla_coordenadas_usada and texto_principal.strip():
                    lineas_antes_recuperacion = texto.splitlines()
                    recovered, replacements = recuperar_filas_tabla_ocr(
                        lineas_antes_recuperacion, texto_principal,
                    )
                    if replacements:
                        texto = "\n".join(recovered)
                        evidencia_celdas_pagina = (
                            _conservar_evidencia_celdas_no_reemplazada(
                                lineas_antes_recuperacion,
                                evidencia_celdas_pagina,
                                recovered,
                            )
                        )
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se recuperaron {replacements} filas "
                            "al contrastar la geometría con la lectura textual OCR."
                        )
                if tabla_coordenadas_usada and _tabla_ocr_necesita_recuperacion(
                    texto.splitlines(),
                ):
                    texto_tabla = ocr_pagina(img_path, rotacion, psm=4)
                    if texto_tabla.strip():
                        lectura_cruzada_pagina = texto_tabla
                    lineas_antes_recuperacion = texto.splitlines()
                    recovered, replacements = recuperar_filas_tabla_ocr(
                        lineas_antes_recuperacion, texto_tabla,
                    )
                    if replacements:
                        texto = "\n".join(recovered)
                        evidencia_celdas_pagina = (
                            _conservar_evidencia_celdas_no_reemplazada(
                                lineas_antes_recuperacion,
                                evidencia_celdas_pagina,
                                recovered,
                            )
                        )
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se recuperaron {replacements} filas "
                            "por verificación cruzada de dos lecturas OCR."
                        )
                if (
                    tabla_coordenadas_usada
                    and _tabla_ocr_tiene_control_final_incompleto(
                        texto.splitlines(),
                    )
                ):
                    # Algunos cierres partidos se leen mejor con una
                    # rasterización ligeramente menor: la cifra de la mitad
                    # derecha puede quedar pegada a una regla vertical a 200
                    # DPI. Esta pasada sólo entrega evidencia textual a la
                    # recuperación de controles; nunca sustituye detalle.
                    prefijo_control = tmpdir_path / (
                        f"pg{pagina}-control-final"
                    )
                    try:
                        raster_control = subprocess.run(
                            [
                                pdftoppm_bin, "-png", "-singlefile",
                                "-r", str(OCR_FINAL_CONTROL_FALLBACK_DPI),
                                "-f", str(pagina), "-l", str(pagina),
                                str(path), str(prefijo_control),
                            ],
                            capture_output=True,
                            timeout=min(OCR_PAGE_TIMEOUT_SECONDS, 30),
                        )
                    except (OSError, subprocess.TimeoutExpired):
                        raster_control = None
                    imagenes_control = (
                        [prefijo_control.with_suffix(".png")]
                        if (
                            raster_control is not None
                            and raster_control.returncode == 0
                            and prefijo_control.with_suffix(".png").exists()
                        ) else []
                    )
                    if imagenes_control:
                        texto_control = ocr_pagina(
                            imagenes_control[0], rotacion,
                        )
                        lineas_antes_recuperacion = texto.splitlines()
                        recovered, replacements = recuperar_filas_tabla_ocr(
                            lineas_antes_recuperacion,
                            texto_control,
                            solo_controles_finales=True,
                        )
                        if replacements:
                            texto = "\n".join(recovered)
                            evidencia_celdas_pagina = (
                                _conservar_evidencia_celdas_no_reemplazada(
                                    lineas_antes_recuperacion,
                                    evidencia_celdas_pagina,
                                    recovered,
                                )
                            )
                            self._ocr_advertencias.append(
                                f"Página {pagina}: se recompusieron "
                                f"{replacements} control(es) final(es) "
                                "partido(s) mediante una segunda "
                                "rasterización OCR; requieren revisión humana."
                            )
                # Una tabla reconstruida por coordenadas ya contiene la misma
                # pagina. Fusionarla con PSM 4 duplicaba sus cuentas y montos.
                if (
                    not tabla_coordenadas_usada
                    and not clasificado_doble_usado
                    and _ocr_requiere_alternativa(texto, pagina == n_paginas)
                ):
                    texto_tabla = ocr_pagina(img_path, rotacion, psm=4)
                    recovered, replacements = recuperar_filas_tabla_ocr(
                        texto.splitlines(), texto_tabla,
                    )
                    if replacements:
                        texto = "\n".join(recovered)
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se recuperaron {replacements} filas "
                            "por verificación cruzada de dos lecturas OCR."
                        )
                    else:
                        texto, estrategia = _combinar_candidatos_ocr(
                            texto, texto_tabla,
                        )
                        if estrategia != "principal":
                            self._ocr_advertencias.append(
                                f"Página {pagina}: OCR de tabla seleccionado por "
                                f"mejor certificación contable ({estrategia})."
                            )
                if not texto.strip():
                    self._ocr_advertencias.append(
                        f"Página {pagina}: OCR sin texto utilizable; revise que el "
                        "documento procesado esté completo."
                    )
                inicio_lineas_pagina = len(lineas)
                lineas_pagina = texto.split('\n')
                lineas.extend(lineas_pagina)
                if origenes_pagina is not None and len(origenes_pagina) == len(lineas_pagina):
                    origenes_lineas.extend(origenes_pagina)
                else:
                    origenes_lineas.extend([None] * len(lineas_pagina))
                if secciones_pagina is not None and len(secciones_pagina) == len(lineas_pagina):
                    secciones_lineas.extend(secciones_pagina)
                else:
                    secciones_lineas.extend([None] * len(lineas_pagina))
                if (
                    importes_recuperados_pagina is not None
                    and len(importes_recuperados_pagina) == len(lineas_pagina)
                ):
                    importes_recuperados.extend(importes_recuperados_pagina)
                else:
                    importes_recuperados.extend([False] * len(lineas_pagina))
                if (
                    tabla_coordenadas_usada
                    and len(evidencia_celdas_pagina) == len(lineas_pagina)
                ):
                    for evidencia in evidencia_celdas_pagina:
                        if evidencia is None:
                            # Una fila reconciliada con otra lectura ya no
                            # conserva una caja TSV válida. Se mantiene el
                            # hueco para no desplazar la evidencia de las
                            # demás filas de la página.
                            evidencias_celdas_ocr.append(None)
                            continue
                        enriquecida = dict(evidencia)
                        enriquecida["imagen"] = str(img_path)
                        enriquecida["rotacion"] = rotacion
                        enriquecida["pagina"] = pagina
                        enriquecida["lectura_cruzada"] = lectura_cruzada_pagina
                        enriquecida["celdas"] = [
                            (
                                {
                                    **celda,
                                    "imagen": str(img_path),
                                    "rotacion": rotacion,
                                }
                                if celda is not None else None
                            )
                            for celda in evidencia.get("celdas", [])
                        ]
                        evidencias_celdas_ocr.append(enriquecida)
                else:
                    evidencias_celdas_ocr.extend([None] * len(lineas_pagina))

                if tabla_coordenadas_usada:
                    paginas_geometricas.append({
                        "inicio": inicio_lineas_pagina,
                        "fin": inicio_lineas_pagina + len(lineas_pagina),
                        "imagen": img_path,
                        "rotacion": rotacion,
                    })

            # La geometría primaria puede conservar ocho columnas en cada
            # fila y aun así desplazar una celda. Se prueba PSM 4 sólo contra
            # el documento completo, y sólo cuando no existe una columna
            # física de un balance clasificado que requeriría metadatos por
            # fila. La alternativa debe cubrir cada página geométrica; una
            # mezcla parcial no es evidencia independiente suficiente.
            if (
                paginas_geometricas
                and not any(origen is not None for origen in origenes_lineas)
                and _certificar_candidato_textual_ocr(
                    "\n".join(lineas),
                ).estado != "certificada"
            ):
                centros_alternativos: Optional[list[float]] = None
                reemplazos_geometricos: list[tuple[int, int, list[str]]] = []
                for pagina_geometrica in paginas_geometricas:
                    palabras_alternativas = ocr_pagina_tsv(
                        pagina_geometrica["imagen"],
                        int(pagina_geometrica["rotacion"]),
                        psm=4,
                    )
                    tabla_alternativa, centros_alternativos = (
                        _extraer_tabla_balance_por_coordenadas(
                            _OCRWordsPage(palabras_alternativas),
                            centros_alternativos,
                        )
                    )
                    if len(tabla_alternativa) < 3 or not centros_alternativos:
                        reemplazos_geometricos = []
                        break
                    reemplazos_geometricos.append((
                        int(pagina_geometrica["inicio"]),
                        int(pagina_geometrica["fin"]),
                        tabla_alternativa,
                    ))
                if len(reemplazos_geometricos) == len(paginas_geometricas):
                    candidatas: list[str] = []
                    cursor = 0
                    for inicio, fin, tabla_alternativa in reemplazos_geometricos:
                        candidatas.extend(lineas[cursor:inicio])
                        candidatas.extend(tabla_alternativa)
                        cursor = fin
                    candidatas.extend(lineas[cursor:])
                    if _candidato_geometrico_ocr_mejora_certificacion(
                        lineas, candidatas,
                    ):
                        lineas = candidatas
                        # Las cajas TSV de PSM 6 dejan de representar las
                        # filas seleccionadas. Se descartan antes que aplicar
                        # una relectura focal sobre una evidencia desplazada.
                        origenes_lineas = [None] * len(lineas)
                        secciones_lineas = [None] * len(lineas)
                        importes_recuperados = [False] * len(lineas)
                        evidencias_celdas_ocr = [None] * len(lineas)
                        self._ocr_advertencias.append(
                            "Se seleccionó la geometría OCR alternativa PSM 4 "
                            "porque certificó el documento completo mejor que "
                            "la lectura primaria PSM 6."
                        )

            if any(evidencia is not None for evidencia in evidencias_celdas_ocr):
                # La validación focal debe ver la misma representación que el
                # parseo final: con ceros OCR normalizados y códigos
                # normalizados. Sin esto, una coma de miles podía hacer que
                # el contraste interno interpretara una cifra como decimal y
                # rechazara incluso una relectura visual correcta.
                lineas = [
                    normalizar_codigo_ocr(normalizar_linea_ocr_tabla(linea))
                    for linea in lineas
                ]
                lineas_releidas, filas_releidas, cambios_focales = (
                    recuperar_celdas_ocr_focales(
                        lineas, evidencias_celdas_ocr,
                    )
                )
                if cambios_focales:
                    lineas = lineas_releidas
                    importes_recuperados = [
                        previo or releido
                        for previo, releido in zip(
                            importes_recuperados, filas_releidas,
                        )
                    ]
                    cambios_cruzados = [
                        cambio for cambio in cambios_focales
                        if cambio.get("origen") == "lectura_textual_cruzada"
                    ]
                    cambios_nativos = [
                        cambio for cambio in cambios_focales
                        if cambio.get("origen") == "relectura_nativa_sin_escalar"
                    ]
                    cambios_por_residuo = [
                        cambio for cambio in cambios_focales
                        if cambio.get("origen")
                        == "relectura_nativa_por_residuo_de_control"
                    ]
                    cambios_focales_visuales = [
                        cambio for cambio in cambios_focales
                        if cambio.get("origen") not in {
                            "lectura_textual_cruzada",
                            "relectura_nativa_sin_escalar",
                            "relectura_nativa_por_residuo_de_control",
                        }
                    ]
                    if cambios_cruzados:
                        celdas_cruzadas = sum(
                            len(cambio["columnas"])
                            for cambio in cambios_cruzados
                        )
                        self._ocr_advertencias.append(
                            "Se recuperaron "
                            f"{celdas_cruzadas} celda(s) sin código al "
                            "contrastar dos lecturas OCR y la identidad de "
                            "la fila; requieren revisión humana."
                        )
                    if cambios_nativos:
                        celdas_nativas = sum(
                            len(cambio["columnas"])
                            for cambio in cambios_nativos
                        )
                        self._ocr_advertencias.append(
                            "Se releyeron "
                            f"{celdas_nativas} celda(s) OCR sin reescalar "
                            "el recorte y con controles contables; requieren "
                            "revisión humana."
                        )
                    if cambios_por_residuo:
                        celdas_por_residuo = sum(
                            len(cambio["columnas"])
                            for cambio in cambios_por_residuo
                        )
                        self._ocr_advertencias.append(
                            "Se releyeron "
                            f"{celdas_por_residuo} celda(s) OCR nativas para "
                            "reducir un residuo de control único; requieren "
                            "revisión humana."
                        )
                    if cambios_focales_visuales:
                        celdas_focales = sum(
                            len(cambio["columnas"])
                            for cambio in cambios_focales_visuales
                        )
                        self._ocr_advertencias.append(
                            "Se releyeron "
                            f"{celdas_focales} celda(s) OCR con evidencia "
                            "visual y controles contables; requieren revisión "
                            "humana."
                        )

        self._ocr_orientation_evidence = _certificar_consenso_documental_orientacion(
            self._ocr_orientation_evidence,
        )
        evidencias_relevantes = [
            evidencia for evidencia in self._ocr_orientation_evidence
            if evidencia.get("utilizada_en_extraccion", True)
        ]
        self._ocr_orientation_certified = bool(evidencias_relevantes) and all(
            bool(evidencia.get("certificada"))
            for evidencia in evidencias_relevantes
        )
        self._origenes_lineas_ocr = origenes_lineas
        self._secciones_lineas_ocr = secciones_lineas
        self._importes_recuperados_ocr = importes_recuperados
        return lineas, True, _resumir_rotaciones_paginas(rotaciones_paginas)


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL PARSER (extraído de app_validacion para eliminar import circular)
# ─────────────────────────────────────────────────────────────────────────────

def parsear_excel(file) -> list[CuentaRaw]:
    df = pd.read_excel(file, header=None)

    header_aliases = {
        "debito": "debitos", "debitos": "debitos", "debe": "debitos",
        "credito": "creditos", "creditos": "creditos", "haber": "creditos",
        "deudor": "saldo_deudor", "acreedor": "saldo_acreedor",
        "activo": "activo", "pasivo": "pasivo",
        "perdida": "perdida", "ganancia": "ganancia",
    }
    eight_column_map: dict[int, str] = {}
    eight_column_header = -1
    for row_idx in range(min(30, df.shape[0])):
        candidate: dict[int, str] = {}
        for col_idx, value in enumerate(df.iloc[row_idx].tolist()):
            if pd.isna(value):
                continue
            label = _sin_acentos(str(value)).lower().strip(" .:$")
            label = re.sub(r"\s+", " ", label)
            if label in header_aliases:
                candidate[col_idx] = header_aliases[label]
        if len(set(candidate.values())) >= 6 and {
            "activo", "pasivo", "perdida", "ganancia",
        }.issubset(candidate.values()):
            eight_column_map = candidate
            eight_column_header = row_idx
            break

    if eight_column_map:
        accounts: list[CuentaRaw] = []
        origin_by_column = {
            "activo": OrigenColumna.ACTIVO,
            "pasivo": OrigenColumna.PASIVO,
            "perdida": OrigenColumna.PERDIDA,
            "ganancia": OrigenColumna.GANANCIA,
        }
        for row_idx in range(eight_column_header + 1, df.shape[0]):
            values = df.iloc[row_idx].tolist()
            text_cells = [
                str(value).strip() for value in values
                if isinstance(value, str) and value.strip()
            ]
            if not text_cells:
                continue
            label = max(text_cells, key=len)
            match = re.match(
                r"^\s*(\d+(?:[.\-]\d+)+)\s+(.+?)\s*$", label,
            )
            code = match.group(1) if match else None
            name = match.group(2).strip() if match else label
            amounts = {column: 0.0 for column in RAW_MONETARY_COLUMNS}
            numeric_seen = False
            for col_idx, column in eight_column_map.items():
                value = values[col_idx]
                if pd.isna(value):
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    amounts[column] = float(value)
                    numeric_seen = True
                else:
                    parsed = parsear_monto(str(value), ".")
                    if parsed is not None:
                        amounts[column] = float(parsed)
                        numeric_seen = True
            if not numeric_seen:
                continue
            classified = [
                (column, amounts[column])
                for column in origin_by_column if amounts[column] != 0
            ]
            if len(classified) == 1:
                column, amount = classified[0]
                origin = origin_by_column[column]
            else:
                amount = 0.0 if not classified else classified[0][1]
                origin = OrigenColumna.DESCONOCIDO
            accounts.append(CuentaRaw(
                linea=row_idx, codigo=code, nombre=name, monto=amount,
                origen_columna=origin,
                es_total=code is None and _es_etiqueta_total(name),
                confianza_extraccion=1.0,
                montos_columnas=amounts,
            ))
        return accounts

    # Helper to detect year and currency for a column
    # Scan the top 15 rows of this column and its immediate left neighbor
    col_meta = {}
    for col_idx in range(df.shape[1]):
        year = None
        currency = None
        # Look in current column and adjacent left column (useful for merged cells)
        for c in (col_idx, col_idx - 1):
            if c < 0 or c >= df.shape[1]:
                continue
            for r in range(min(15, df.shape[0])):
                val = df.iloc[r, c]
                if pd.isna(val) or (isinstance(val, (int, float)) and not (1990 <= val <= 2050)):
                    continue
                val_str = str(val).strip().lower()

                # Check year
                year_match = re.search(r'\b(20\d{2})\b', val_str)
                if year_match and not year:
                    year = year_match.group(1)
                elif 'actual' in val_str and not year:
                    year = 'actual'
                elif 'anterior' in val_str and not year:
                    year = 'anterior'
                elif 'acumulado' in val_str and not year:
                    year = 'acumulado'

                # Check currency
                if ('usd' in val_str or 'dolar' in val_str or 'us$' in val_str) and not currency:
                    currency = 'USD'
                elif ('clp' in val_str or 'peso' in val_str or 'clp$' in val_str) and not currency:
                    currency = 'CLP'
        col_meta[col_idx] = (year, currency)

    cuentas = []
    for i, row in df.iterrows():
        vals = row.tolist()
        non_na_vals = [v for v in vals if pd.notna(v)]
        if not non_na_vals:
            continue

        textos = [v for v in non_na_vals if isinstance(v, str)]
        numeros = [v for v in non_na_vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if not textos:
            continue

        nombre = max(textos, key=len)
        if len(nombre) < 3:
            continue

        # Skip header/meta rows (e.g. if the row itself has words like 'balance', 'rut', 'año' and no numeric figures)
        if any(w in nombre.lower() for w in ('rut', 'razon social', 'fecha', 'periodo', 'moneda', 'balance general')) and not numeros:
            continue

        # Detect account code. En históricos exportados suele estar en una
        # columna numérica separada, no necesariamente en la primera.
        codigo = None
        primer = str(vals[0]) if pd.notna(vals[0]) else ""
        if re.match(r'^[\d.\-]+$', primer) and primer != nombre:
            codigo = primer
        if codigo is None:
            name_index = vals.index(nombre) if nombre in vals else len(vals)
            for col_idx, value in enumerate(vals):
                if col_idx >= name_index:
                    break
                if pd.isna(value):
                    continue
                candidate = str(value).strip()
                if re.fullmatch(r"\d{6,}(?:\.0)?", candidate):
                    codigo = candidate.removesuffix(".0")
                    break

        # Map all numeric amounts to their year/currency
        montos_periodos = {}
        montos_columnas = {}
        last_monto = None

        for col_idx, val in enumerate(vals):
            if pd.isna(val) or not isinstance(val, (int, float)) or isinstance(val, bool):
                continue
            if codigo and str(val) == codigo:
                continue
            if col_idx == 0 and isinstance(val, int) and val < 500:
                continue

            val_f = float(val)
            last_monto = val_f

            year, currency = col_meta.get(col_idx, (None, None))

            if year and currency:
                montos_periodos[f"{year}_{currency}"] = val_f
                montos_periodos[year] = val_f
                montos_periodos[currency] = val_f
            elif year:
                montos_periodos[year] = val_f
            elif currency:
                montos_periodos[currency] = val_f

            col_name = f"col_{col_idx}"
            if year:
                col_name += f"_{year}"
            if currency:
                col_name += f"_{currency}"
            montos_columnas[col_name] = val_f

        detected_years = sorted(list({col_meta[c][0] for c in col_meta if col_meta[c][0] is not None}), reverse=True)
        if detected_years:
            if "actual" not in montos_periodos and len(detected_years) >= 1:
                montos_periodos["actual"] = montos_periodos.get(detected_years[0], 0.0)
            if "anterior" not in montos_periodos and len(detected_years) >= 2:
                montos_periodos["anterior"] = montos_periodos.get(detected_years[1], 0.0)

        monto_principal = (
            montos_periodos["actual"]
            if "actual" in montos_periodos else last_monto
        )
        origin = OrigenColumna.DESCONOCIDO
        if codigo:
            origin = {
                "1": OrigenColumna.ACTIVO,
                "2": OrigenColumna.PASIVO,
                "5": OrigenColumna.GANANCIA,
                "6": OrigenColumna.PERDIDA,
            }.get(codigo[0], OrigenColumna.DESCONOCIDO)

        cuentas.append(CuentaRaw(
            linea=i, codigo=codigo, nombre=nombre, monto=monto_principal,
            origen_columna=origin, confianza_extraccion=0.9,
            montos_periodos=montos_periodos, montos_columnas=montos_columnas
        ))

    return cuentas



# ─────────────────────────────────────────────────────────────────────────────
# CLI DE PRUEBA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) < 2:
        print("Uso: python parser_universal.py <ruta_al_pdf>")
        sys.exit(1)

    parser = ParserPDF()
    archivo = Path(sys.argv[1])

    resultado = parser.parsear(archivo)

    print(f"Archivo: {resultado.archivo}")
    print(f"Formato código: {resultado.formato_codigo}")
    print(f"Separador miles: '{resultado.separador_miles}'")
    print(f"Requirió OCR: {resultado.requirio_ocr} (rotación {resultado.rotacion_aplicada}°)")
    print(f"Advertencias: {resultado.advertencias}")
    print(f"Total cuentas extraídas: {len(resultado.cuentas)}")
    print()
    for c in resultado.cuentas[:25]:
        print(f"  [{c.codigo or '-':18s}] {c.nombre[:45]:45s} "
              f"monto={c.monto!s:>15} ({c.origen_columna.value}) "
              f"{'[TOTAL]' if c.es_total else ''}")
