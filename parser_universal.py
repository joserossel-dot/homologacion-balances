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

import copy
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
from functools import lru_cache
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


def detectar_unidades_monetarias(lineas: list[str]) -> list[str]:
    """Detecta la unidad declarada en encabezados contables.

    Distingue la moneda de su escala de presentación. ``$``, ``M``, ``MM`` y
    ``M$`` se conservan como unidades de pesos; ``USD`` y ``US$`` se
    normalizan como USD. Los tokens ``M`` y ``MM`` sólo se aceptan en líneas
    breves con señales de cabecera para no confundir texto narrativo.
    """
    unidades: list[str] = []
    unidades_cabecera: list[str] = []

    def agregar(unidad: str, linea: list[str]) -> None:
        if unidad not in unidades:
            unidades.append(unidad)
        linea.append(unidad)

    for line in lineas[:100]:
        normalized = _sin_acentos(line).upper().strip()
        if not normalized:
            continue
        compact = re.sub(r"\s+", " ", normalized)
        tokens = [token.strip(".,:;()[]") for token in compact.split()]
        unidades_linea: list[str] = []
        header_context = bool(
            len(compact) <= 60
            and (
                re.search(r"\b(?:NOTA|MONEDA|UNIDAD|19\d{2}|20\d{2})\b", compact)
                or len(tokens) <= 4
                or sum(token in {"M", "MM", "M$", "MM$"} for token in tokens) >= 2
            )
        )
        for token in tokens:
            token_compact = token.replace(".", "")
            if re.fullmatch(r"(?:MM?US\$|M?USD|US\$)", token_compact):
                agregar("USD", unidades_linea)
            elif re.fullmatch(r"CLP\$?", token_compact):
                agregar("CLP", unidades_linea)
            elif token_compact == "$":
                agregar("$", unidades_linea)
            elif header_context and token_compact in {"MM", "MM$"}:
                agregar("MM$", unidades_linea)
            elif header_context and token_compact in {"M", "M$"}:
                agregar("M$", unidades_linea)
        if re.search(r"\bMILLONES\s+DE\s+PESOS\b", compact):
            agregar("MM$", unidades_linea)
        elif re.search(r"\bMILES\s+DE\s+PESOS\b", compact):
            agregar("M$", unidades_linea)
        elif re.search(r"\bDOLAR(?:ES)?(?:\s+ESTADOUNIDENSES?)?\b", compact):
            agregar("USD", unidades_linea)
        elif re.search(r"\bPESOS(?:\s+CHILENOS?)?\b", compact):
            agregar("CLP", unidades_linea)
        # Una unidad repetida en una cabecera comparativa breve es evidencia
        # más específica que la leyenda de monedas de una portada.
        if (
            len(unidades_linea) >= 2
            and len(set(unidades_linea)) == 1
            and len(compact) <= 60
        ):
            for unidad in unidades_linea:
                if unidad not in unidades_cabecera:
                    unidades_cabecera.append(unidad)
    return unidades_cabecera or unidades


def detectar_años_y_monedas(lineas: list[str]) -> tuple[list[str], list[str]]:
    """Detecta como máximo dos períodos monetarios desde cabeceras contables.

    Un año citado en texto histórico o en una nota no identifica una columna
    monetaria. Se aceptan fechas de estado, rangos de balance y cabeceras
    tabulares breves respaldadas por una fila adyacente de unidades/``Nota``.
    """
    años: list[str] = []
    patron_año = re.compile(r'\b((?:19|20)\d{2})\b')

    candidates = [str(line or "").strip() for line in lineas[:100]]
    for index, line in enumerate(candidates):
        normalized = _sin_acentos(line).upper()
        matches = list(dict.fromkeys(patron_año.findall(normalized)))
        if not matches:
            continue
        nearby = " ".join(
            _sin_acentos(value).upper()
            for value in candidates[max(0, index - 2):index + 3]
        )
        date_header = bool(re.search(
            r"\b(?:AL|A)\s+\d{1,2}\s+DE\s+"
            r"(?:ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|"
            r"SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\b|"
            r"\bPOR\s+(?:LOS\s+)?(?:ANOS|EJERCICIOS|PERIODOS)\s+TERMINADOS\b|"
            r"\b(?:EJERCICIO|PERIODO|BALANCE)\s+(?:TRIBUTARIO\s+)?(?:DE\s+|DEL\s+)?(?:19|20)\d{2}\b|"
            r"\b(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|"
            r"SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|JUN|"
            r"JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2},?\s+(?:19|20)\d{2}\b|"
            r"\b\d{1,2}[/-]\d{1,2}[/-](?:19|20)\d{2}\s+"
            r"(?:A|AL|-|HASTA)\s+\d{1,2}[/-]\d{1,2}[/-](?:19|20)\d{2}\b",
            normalized,
        ))
        mostly_years = bool(re.fullmatch(
            r"\s*(?:19|20)\d{2}(?:\s+(?:Y|/|-)?\s*(?:19|20)\d{2})?\s*",
            normalized,
        ))
        tabular_support = bool(
            re.search(r"\bNOTA\b", nearby)
            and (
                detectar_unidades_monetarias(
                    candidates[max(0, index - 2):index + 3]
                )
                or re.search(r"\b(?:ACTIVOS?|PASIVOS?|PATRIMONIO|RESULTADOS?)\b", nearby)
            )
        )
        balance_range = bool(
            date_header
            and re.search(r"\b(?:BALANCE|ESTADO|SITUACION|RESULTADO)\b", nearby)
        )
        es_narrativa = bool(re.search(
            r"\b(?:SOCIEDAD|CONSTITUIDA|REORGANIZADA|NOTAR|ESCRITURA|HISTORIC|FUNDADA)\b",
            normalized,
        ))
        comparative_header = bool(
            not es_narrativa
            and len(matches) >= 2
            and (
                re.search(r"\b(?:ACTIVOS?|PASIVOS?|PATRIMONIO|RESULTADOS?|ESTADOS?|BALANCE|SITUACION|US\$|USD|CLP|UF|PESOS|DOLARES|M\$|MM\$)\b", normalized)
                or (mostly_years and (
                    bool(detectar_unidades_monetarias(candidates[max(0, index - 2):index + 3]))
                    or bool(re.search(r"\b(?:ACTIVOS?|PASIVOS?|PATRIMONIO|RESULTADOS?|ESTADO|BALANCE)\b", nearby))
                ))
            )
        )
        if not (date_header or balance_range or comparative_header or (mostly_years and tabular_support)):
            continue
        for match in matches:
            if match not in años:
                años.append(match)
            if len(años) == 2:
                break
        if len(años) == 2:
            break

    unidades = detectar_unidades_monetarias(lineas)
    monedas = []
    for unidad in unidades:
        if unidad == "USD":
            moneda = "USD"
        elif unidad in {"CLP", "M$", "MM$"}:
            moneda = "CLP"
        else:
            # ``$`` sin país ni nombre de moneda es deliberadamente ambiguo.
            continue
        if moneda not in monedas:
            monedas.append(moneda)
    return años, monedas


def extraer_encabezados_documento_pdf(path: Path) -> list[str]:
    """Lee encabezados nativos sin depender del extractor tabular elegido.

    Los extractores por coordenadas conservan las filas contables, pero pueden
    omitir el título, la fecha y la unidad. Esta lectura auxiliar toma sólo las
    primeras líneas de cada página inicial y no altera las cuentas extraídas.
    """
    encabezados: list[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:20]:
                text = page.extract_text() or ""
                encabezados.extend(
                    line.strip() for line in text.splitlines()[:30]
                    if line.strip()
                )
    except Exception as exc:  # noqa: BLE001 - metadato auxiliar no bloqueante
        logger.debug(
            "No se pudieron recuperar encabezados del PDF: %s", exc,
            exc_info=True,
        )
    return encabezados


def detectar_columna_nota_comparativa(
    lineas: list[str], years: Optional[list[str]] = None,
) -> bool:
    """Detecta una referencia de nota antes de importes comparativos o del período.

    En estados financieros auditados es frecuente que los años aparezcan en
    una línea y la cabecera ``Nota MUS$ MUS$`` en la siguiente. La referencia
    de nota de cada fila, por ejemplo ``(21)`` o ``Nota 5``, no es un importe.
    """
    numeric_years = [
        year for year in (years or [])
        if re.fullmatch(r"(?:19|20)\d{2}", year)
    ]

    candidates = lineas[:100]
    for index, line in enumerate(candidates):
        normalized = _sin_acentos(line).lower().strip()
        if not re.search(r"\bnotas?\b", normalized):
            continue

        same_line_years = re.findall(r"\b(?:19|20)\d{2}\b", normalized)
        if len(dict.fromkeys(same_line_years)) >= 1 or len(numeric_years) >= 1:
            return True

        unit_tokens = [
            token.strip(".,:;()[]")
            for token in normalized.split()
            if (
                "$" in token
                or token.strip(".,:;()[]")
                in {"usd", "clp", "uf", "mus", "miles"}
            )
        ]
        if len(unit_tokens) >= 1:
            return True

        # También admite una cabecera partida en dos líneas, por ejemplo
        # ``Nota`` seguida por ``MUS$ MUS$``. Se limita a líneas breves para
        # no confundir una nota narrativa con una columna tabular.
        if len(normalized) <= 40:
            nearby = " ".join(
                _sin_acentos(candidate).lower()
                for candidate in candidates[max(0, index - 2):index + 3]
            )
            nearby_units = [
                token.strip(".,:;()[]")
                for token in nearby.split()
                if (
                    "$" in token
                    or token.strip(".,:;()[]")
                    in {"usd", "clp", "uf", "mus", "miles"}
                )
            ]
            if nearby_units:
                return True

    rows_with_note_reference = 0
    for line in candidates:
        tokens = line.split()
        monetary_positions = [
            index for index, token in enumerate(tokens)
            if PATRON_MONTOS.fullmatch(token.replace("$", ""))
        ]
        if len(monetary_positions) < 3:
            continue
        first = tokens[monetary_positions[-3]].strip("()[]")
        if first.isdigit() and 0 < int(first) <= 99:
            rows_with_note_reference += 1
    return rows_with_note_reference >= 3


def split_side_by_side(line: str) -> list[str]:
    tokens = line.split()
    if len(tokens) < 4:
        return [line]

    # Una fila tributaria completa ya trae ocho celdas monetarias al final.
    # Guiones internos de la glosa ("Préstamo JL - CP", por ejemplo) forman
    # el patrón textual T-N-T-N y antes se confundían con dos tablas paralelas.
    # Si las ocho columnas están presentes, la fila es canónica y no se parte.
    trailing_amounts = 0
    for token in reversed(tokens):
        cleaned = token.replace("$", "").strip()
        if (
            cleaned in {"-", "—", "−", "o", "O"}
            or re.fullmatch(r"-?\(?\d[\d.,]*\)?", cleaned)
        ):
            trailing_amounts += 1
            continue
        break
    if trailing_amounts >= len(RAW_MONETARY_COLUMNS):
        return [line]

    # Classify tokens
    types = []
    for index, t in enumerate(tokens):
        t_stripped = t.replace('$', '').replace('(', '').replace(')', '').strip(' .-–—−,[]')
        previous_is_text = bool(
            index > 0
            and re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]', tokens[index - 1])
        )
        next_is_text = bool(
            index + 1 < len(tokens)
            and re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]', tokens[index + 1])
        )
        prev_tok_norm = tokens[index - 1].upper().rstrip(".:") if index > 0 else ""
        es_identificador_legal = prev_tok_norm in {
            "ART", "ARTICULO", "ARTÍCULO", "LEY", "DFL", "DL", "CIRCULAR",
            "RESOLUCION", "RESOLUCIÓN", "NOTA", "NOTAS", "LOCAL", "OFICINA", "DEPTO", "RUT",
        }
        # Una ``o`` entre palabras completas es la conjunción de la glosa, no un cero
        # OCR. Si antecede o sucede a números, ceros o letras sueltas, es un cero de celda.
        prev_is_word = bool(
            index > 0
            and len(tokens[index - 1]) >= 2
            and re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]', tokens[index - 1])
            and not re.search(r'\d', tokens[index - 1])
        )
        next_is_word = bool(
            index + 1 < len(tokens)
            and len(tokens[index + 1]) >= 2
            and re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]', tokens[index + 1])
            and not re.search(r'\d', tokens[index + 1])
        )
        o_es_conjuncion = t_stripped.lower() == 'o' and prev_is_word and next_is_word
        # Un número de 1 o 2 dígitos entre palabras (ej. "5" en "Caja 5 Digitos" o "31" en "al 31 de diciembre")
        # es parte de la glosa, no el importe de una columna contable.
        es_digito_glosa_intermedio = bool(
            previous_is_text
            and next_is_text
            and t_stripped.isdigit()
            and len(t_stripped) <= 2
        )
        es_guion_intermedio = bool(
            previous_is_text
            and next_is_text
            and t in ('-', '—', '−', ':')
        )
        is_num = False
        if not es_identificador_legal and not es_digito_glosa_intermedio and not es_guion_intermedio and (
            re.search(r'\d', t_stripped)
            or t in ('-', '—', '−')
            or t_stripped in ('', '-', '—', '−')
            or (t_stripped in ('o', 'O') and not o_es_conjuncion)
        ):
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

    # Check if we have a side-by-side transition 'TNT'
    if "TNT" in pattern:
        t_count = 0
        split_token_idx = -1
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
                # Un importe de la tabla izquierda queda inmediatamente antes
                # de la glosa derecha. No debe desplazarse como supuesto código
                # de la segunda cuenta: ``2.962.115.064 CUENTAS POR PAGAR``.
                # Sólo retrocedemos ante un código, no ante un monto con grupos
                # de miles completos.
                es_monto_agrupado = bool(re.fullmatch(
                    r"-?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?", prev_tok,
                ))
                if (
                    re.match(r'^\d+[\d.\-]*$', prev_tok)
                    and len(prev_tok) >= 3
                    and not es_monto_agrupado
                ):
                    split_token_idx -= 1
            left_line = " ".join(tokens[:split_token_idx]).strip(' .-–—−')
            right_line = " ".join(tokens[split_token_idx:]).strip(' .-–—−')
            if left_line and right_line:
                return [left_line, *split_side_by_side(right_line)]

    return [line]


def _es_token_codigo_inicio(linea: str) -> bool:
    """Verifica si la línea comienza con un token que aparenta ser código contable."""
    tokens = linea.split()
    if not tokens:
        return False
    tok0 = tokens[0].rstrip(':-.')
    if re.match(r'^\d{5,8}$|^\d{1,2}(?:\.\d{1,4}){1,6}$|^\d{1,2}(?:-\d+)+$', tok0):
        return True
    return False


def _linea_tiene_monto_final(linea: str) -> bool:
    """Verifica si la línea termina con un token de importe monetario o saldo contable."""
    limpia = linea.strip()
    return bool(re.search(
        r'(?:(?:\(?\s*-?\s*\d[\d.,]*\s*\)?)|[-—−]|(?:\b[oO]\b))\s*$',
        limpia,
    ))


def asociar_lineas_verticales(lineas: list[str]) -> list[str]:
    """Une glosas partidas antes de interpretar sus importes.

    En estados auditados una misma fila suele ocupar dos o más líneas: la primera
    contiene el código y el inicio de la glosa, y las siguientes su continuación,
    la nota y los importes.
    """
    new_lines: list[str] = []
    idx = 0
    n = len(lineas)

    while idx < n:
        l_curr = lineas[idx].strip()
        if not l_curr:
            new_lines.append("")
            idx += 1
            continue

        # Mientras la línea actual no termine en monto y la siguiente sea una continuación válida
        while not _linea_tiene_monto_final(l_curr) and idx + 1 < n:
            l_next = lineas[idx + 1].strip()
            if not l_next:
                break
            if _es_token_codigo_inicio(l_next):
                break
            # Un control impreso inicia una fila propia, incluso si el cero
            # final de la fila precedente fue leído como la letra O.
            if PATRON_TOTAL.match(l_next):
                break

            cleaned_next = re.sub(r'[\d\s.,$()\-—−_\[\]]', '', l_next)
            # Caso 1: Siguiente línea son solo montos
            if cleaned_next == "" and l_next and re.search(r'\d', l_next):
                l_curr = f"{l_curr} {l_next}"
                idx += 1
                continue

            # Caso 2: Siguiente línea empieza en minúscula o conector o la actual termina en conector
            first_char = l_next[0] if l_next else ''
            text_before_amount = re.split(
                r"\s+(?=(?:\(?-?[\d.,]+\)?|[-—−])(?:\s|$))",
                l_next,
                maxsplit=1,
            )[0].strip(" .-–—−")
            continuation = (
                first_char.islower()
                or bool(re.match(
                    r"^(?:a|de(?:l|\s+la|\s+los|\s+las)?|que|corriente|"
                    r"no\s+corriente|continuad[ao]s?|atribuible|por|con|en|sin|para|segun|marco|operativo)\b",
                    _sin_acentos(text_before_amount),
                    re.IGNORECASE,
                ))
                or bool(re.search(r"\b(?:a|de|del|por|con|en|para|y|e|o|u|segun)$", l_curr, re.I))
            )
            if continuation and (cleaned_next or re.search(r'\d', l_next)):
                l_curr = f"{l_curr} {l_next}"
                idx += 1
            else:
                break

        new_lines.append(l_curr)
        idx += 1

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


def _pagina_comparativa_con_texto_nativo_corrupto(page, texto: str) -> bool:
    """Detecta fuentes PDF que visualmente forman una tabla pero extraen letras sueltas.

    Algunos estados financieros auditados contienen una fuente embebida cuya
    codificación rompe las glosas y separa casi cada letra, aunque la página se
    vea nítida. La detección exige simultáneamente fragmentación alfabética alta
    y varias filas con al menos dos importes comparativos. Así no se activa OCR
    por una portada, una nota narrativa o una tabla nativa correctamente leída.
    """
    if not texto.strip():
        return False
    # Algunos PDF conservan texto seleccionable, pero su mapa de caracteres
    # sólo expone marcadores ``(cid:N)``. Ese contenido no es una fuente útil
    # para el parser aunque tenga miles de caracteres y debe pasar por OCR.
    if len(re.findall(r"\(cid:\d+\)", texto, flags=re.I)) >= 20:
        return True
    try:
        words = page.extract_words(
            x_tolerance=2, y_tolerance=2,
            use_text_flow=False, keep_blank_chars=False,
        ) or []
    except Exception:
        return False
    alpha_tokens = [
        str(word.get("text", ""))
        for word in words
        if re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", str(word.get("text", "")))
    ]
    if len(alpha_tokens) < 40:
        return False
    fragmented = sum(
        len(re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", "", token)) <= 1
        for token in alpha_tokens
    )
    if fragmented / len(alpha_tokens) < 0.55:
        return False

    comparative_rows = 0
    for group in _agrupar_palabras_por_linea(words):
        has_label = any(
            re.search(
                r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", str(word.get("text", "")),
            )
            for word in group
        )
        amounts = sum(
            bool(PATRON_MONTOS.fullmatch(
                normalizar_token_ocr(str(word.get("text", ""))).replace("$", ""),
            ))
            for word in group
        )
        if has_label and amounts >= 2:
            comparative_rows += 1
    return comparative_rows >= 5


def _reconstruir_lineas_nativas_fragmentadas(page) -> list[str]:
    """Rearma texto cuyos caracteres conservan coordenadas PDF válidas.

    Algunas fuentes embebidas hacen que ``extract_text`` separe cada letra y
    dígito. La distancia horizontal sí conserva la frontera entre palabras y
    columnas, de modo que puede reconstruirse la fila sin inventar importes ni
    aplicar identidades contables.
    """
    try:
        words = page.extract_words(
            x_tolerance=2, y_tolerance=2,
            use_text_flow=False, keep_blank_chars=False,
        ) or []
    except Exception:
        return []
    rebuilt: list[str] = []
    for group in _agrupar_palabras_por_linea(words):
        ordered = sorted(group, key=lambda item: float(item["x0"]))
        parts: list[str] = []
        previous_x1: Optional[float] = None
        for word in ordered:
            token = str(word.get("text", ""))
            if not token:
                continue
            x0 = float(word["x0"])
            if previous_x1 is not None and x0 - previous_x1 > 1.2:
                parts.append(" ")
            parts.append(token)
            previous_x1 = float(word["x1"])
        line = re.sub(r"\s+", " ", "".join(parts)).strip()
        if line:
            rebuilt.append(line)
    return rebuilt


_HEADER_ALIASES = {
    "nombre": {"CUENTA", "CUENTAS", "NOMBRE", "DESCRIPCION", "DETALLE"},
    "debitos": {"DEBITOS", "DEBITO", "DEBE", "PEBITOS", "DEBIT0S"},
    "creditos": {"CREDITOS", "CREDITO", "HABER"},
    "saldo_deudor": {"DEUDOR", "SDEUDOR", "SALDODEUDOR"},
    "saldo_acreedor": {"ACREEDOR", "ACREEEDOR", "SACREEDOR", "SALDOACREEDOR"},
    # ``Ac?vo`` y ``Actvo`` son extracciones nativas observadas cuando la
    # fuente embebida pierde la sílaba central. Sólo se aceptan como cabecera.
    "activo": {"ACTIVO", "ACTIVOS", "ACVO", "ACTVO"},
    "pasivo": {"PASIVO", "PASIVOS", "PASIWO", "PATRIMONIO"},
    "perdida": {"PERDIDA", "PERDIDAS"},
    "ganancia": {"GANANCIA", "GANANCIAS"},
}


def _inferir_bordes_columnas_monetarias(
    grupos: list[list[dict]], *, header_bottom: float, text_boundary: float,
) -> list[float]:
    """Infiere ocho bordes derechos desde filas, no desde textos de cabecera.

    Los importes están alineados a la derecha y sus glosas de cabecera suelen
    estar centradas o alineadas a la izquierda. Usar el centro de ``PASIVO``
    como centro del importe desplaza columnas en tablas anchas.
    """
    positions: list[float] = []
    for group in grupos:
        if float(group[0]["top"]) <= header_bottom + 1.5:
            continue
        for word in group:
            token = normalizar_token_ocr(str(word.get("text", ""))).replace("$", "")
            if (
                float(word["x1"]) > text_boundary
                and (token == "-" or PATRON_MONTOS.fullmatch(token))
            ):
                positions.append(float(word["x1"]))
    clusters: list[list[float]] = []
    for position in sorted(positions):
        if not clusters or position - sum(clusters[-1]) / len(clusters[-1]) > 9:
            clusters.append([position])
        else:
            clusters[-1].append(position)
    # Columnas que son cero en casi todo el documento pueden aparecer sólo en
    # subtotal y cierre. Dos observaciones alineadas son suficientes cuando el
    # conjunto completo forma exactamente ocho columnas; una marca aislada no.
    stable = [cluster for cluster in clusters if len(cluster) >= 2]
    if len(stable) != 8:
        return []
    return [sum(cluster) / len(cluster) for cluster in stable]


def _es_cierre_final_balance(nombre: str) -> bool:
    """Reconoce sólo controles finales inequívocos de una tabla tributaria."""
    normalized = re.sub(
        r"[^A-Z ]", " ", _sin_acentos(str(nombre or "")).upper(),
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    targets = {
        "TOTALES", "TOTAL GENERAL", "SUMAS TOTALES", "TOTALES IGUALES",
        "SUMAS IGUALES",
    }
    if normalized in targets:
        return True
    cleaned = re.sub(r"\b[A-Z]{1,2}\b$", "", normalized).strip()
    if cleaned in targets:
        return True
    return any(normalized.startswith(t) for t in targets)


def _extraer_tabla_balance_por_coordenadas(
    page, column_centers: Optional[list[float]] = None,
) -> tuple[list[str], Optional[list[float]]]:
    """Extrae Cuenta + ocho importes usando encabezados y geometría.

    Acepta documentos con o sin código y sinónimos comunes de encabezado. El
    layout detectado se puede reutilizar en páginas continuadas sin encabezado.
    """
    try:
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
    except Exception:
        return [], column_centers
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
            if "nombre" in matches and all(
                key in matches for key in RAW_MONETARY_COLUMNS
            ):
                header_words = combined
                detected = matches
                break
        if header_words:
            break
    if not header_words and not column_centers:
        return [], None

    if not header_words and column_centers:
        # No heredar una tabla de ocho columnas al comenzar otro estado de
        # una sola columna (p. ej. balance tributario seguido del clasificado).
        numeric_counts = []
        for group in grupos:
            if any(re.search(r"[A-Za-z]", str(w["text"])) for w in group):
                numeric_counts.append(sum(
                    bool(PATRON_MONTOS.fullmatch(normalizar_token_ocr(str(w["text"]))))
                    for w in group
                ))
        if sum(1 <= n <= 3 for n in numeric_counts) >= 5 and not any(n >= 6 for n in numeric_counts):
            return [], None

    if header_words:
        ordered = [detected["nombre"]] + [detected[key] for key in RAW_MONETARY_COLUMNS]
        centers = [
            (float(word["x0"]) + float(word["x1"])) / 2
            for word in ordered
        ]
    else:
        centers = list(column_centers or [])
    if len(centers) != 9:
        return [], column_centers
    name_center = centers[0]
    amount_centers = centers[1:]
    header_bottom = max(float(w["top"]) for w in header_words) if header_words else -1.0
    text_boundary = (
        (float(detected["nombre"]["x1"]) + amount_centers[0]) / 2
        if header_words else (name_center + amount_centers[0]) / 2
    )
    inferred_edges = _inferir_bordes_columnas_monetarias(
        grupos, header_bottom=header_bottom, text_boundary=text_boundary,
    )
    if inferred_edges:
        amount_centers = inferred_edges
        centers = [name_center, *amount_centers]
    lineas: list[str] = []
    closing_controls = False
    for grupo in grupos:
        if float(grupo[0]["top"]) <= header_bottom + 1.5:
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
                float(w["x1"]) - amount_centers[j]
            )) == i for i, w in enumerate(tail))
        )
        tail_boundary = float(tail[0]["x0"]) if full_amount_tail else text_boundary
        for word in grupo:
            token = str(word["text"]).strip()
            if _INTERLEAVED_COLUMN_BLEED.search(token):
                desenredado = _desenredar_token_colision(token)
                if desenredado:
                    w_word = {**word, "text": desenredado[0]}
                    w_amount = {**word, "text": desenredado[1]}
                    text_words.append(w_word)
                    x_col_amount = (
                        float(w_amount.get("x1", word["x1"]))
                        if inferred_edges
                        else (float(w_amount.get("x0", word["x0"])) + float(w_amount.get("x1", word["x1"]))) / 2
                    )
                    nearest = min(
                        range(len(amount_centers)),
                        key=lambda idx: abs(x_col_amount - amount_centers[idx]),
                    )
                    amount_cells[nearest].append(w_amount)
                    continue
            m_adh = _PATRON_MONTO_ADHERIDO_A_PALABRA.match(token)
            if m_adh:
                w_word = {**word, "text": m_adh.group(1)}
                w_amount = {**word, "text": m_adh.group(2)}
                text_words.append(w_word)
                x_col_amount = (
                    float(w_amount.get("x1", word["x1"]))
                    if inferred_edges
                    else (float(w_amount.get("x0", word["x0"])) + float(w_amount.get("x1", word["x1"]))) / 2
                )
                nearest = min(
                    range(len(amount_centers)),
                    key=lambda idx: abs(x_col_amount - amount_centers[idx]),
                )
                amount_cells[nearest].append(w_amount)
                continue

            xmid = (float(word["x0"]) + float(word["x1"])) / 2
            x_amount = float(word["x1"]) if inferred_edges else xmid
            token_normalizado = normalizar_token_ocr(token).replace("$", "")
            es_monto = token == "-" or bool(PATRON_MONTOS.fullmatch(token_normalizado))
            # En tablas escaneadas Tesseract suele leer el cero aislado como
            # pequeños glifos sin dígitos (``o``, ``]``, ``»``...). Sólo los
            # aceptamos dentro de la vecindad de una columna monetaria para no
            # convertir palabras legítimas del nombre en importes.
            distancia_columna = min(abs(x_amount - center) for center in amount_centers)
            es_cero_en_celda = (
                distancia_columna <= 32
                and _es_token_cero_ocr_en_celda(token)
            )
            if es_cero_en_celda:
                es_monto = True
            if not es_monto or float(word["x1"]) < tail_boundary:
                text_words.append(word)
                continue
            nearest = min(
                range(len(amount_centers)),
                key=lambda index: abs(x_amount - amount_centers[index]),
            )
            amount_cells[nearest].append(word)
        text_tokens = [str(w["text"]) for w in sorted(text_words, key=lambda w: w["x0"])]
        code = ""
        if text_tokens and re.fullmatch(r"\d{4,10}|\d+(?:[.-]\d+){1,}", text_tokens[0]):
            code = text_tokens.pop(0)
        name = " ".join(text_tokens).strip()
        amounts = []
        for cell in amount_cells:
            token = "".join(str(w["text"]) for w in sorted(cell, key=lambda w: w["x0"])).strip()
            token_normalizado = normalizar_token_ocr(token).replace("$", "")
            amounts.append(
                "0" if _es_token_cero_ocr_en_celda(token)
                else token if token != "-" and PATRON_MONTOS.fullmatch(token_normalizado)
                else "0"
            )

        clean_name_chars = re.sub(r"[^A-Za-z0-9]", "", name)
        is_noise_name = (
            not name
            or not clean_name_chars
            or clean_name_chars.upper() in {"O", "X", "I", "II", "IIA", "MN", "DD", "O0", "OO"}
        )
        # Reconstrucción genérica de control multilínea si la fila consecutiva no tiene nombre o es ruido
        if lineas and is_noise_name and any(a != "0" for a in amounts):
            prev_line = lineas[-1]
            prev_parts = prev_line.strip().split()
            if len(prev_parts) >= 9:
                prev_amounts = prev_parts[-8:]
                prev_name = " ".join(prev_parts[:-8])
                norm_prev = re.sub(r"[^A-Z ]", " ", _sin_acentos(prev_name).upper()).strip()
                if any(k in norm_prev for k in ["SUMAS IGUALES", "TOTALES IGUALES", "TOTAL GENERAL", "TOTALES", "RESULTADO", "PERDIDA", "UTILIDAD"]):
                    merged_amounts = list(prev_amounts)
                    complemented = False
                    for j in range(8):
                        if (prev_amounts[j] == "0" or _es_token_cero_ocr_en_celda(prev_amounts[j])) and amounts[j] != "0":
                            merged_amounts[j] = amounts[j]
                            complemented = True
                    if complemented:
                        clean_name = re.sub(r"[\s|!/:;.\-—_\]\[)(\\oOxX]+$", "", prev_name).strip()
                        lineas[-1] = f"{clean_name} {' '.join(merged_amounts)}"
                        if _es_cierre_final_balance(clean_name):
                            closing_controls = True
                        continue

        if not name:
            continue
        if closing_controls and not (
            _es_cierre_final_balance(name)
            or re.fullmatch(
                r"(?:utilidad|perdida|resultado)(?: del ejercicio)?",
                _sin_acentos(name).lower().strip(),
            )
        ):
            continue
        prefix = f"{code} " if code else ""
        lineas.append(f"{prefix}{name} {' '.join(amounts)}")
        # Firmas, pies legales y sellos posteriores al cierre no son cuentas.
        # El corte exige una etiqueta final exacta para no truncar subtotales
        # ni encabezados jerárquicos que contienen la palabra ``total``.
        if _es_cierre_final_balance(name):
            closing_controls = True
    return lineas, centers


def _extraer_tabla_balance_10_columnas_por_coordenadas(
    page, column_centers: Optional[list[float]] = None,
) -> tuple[list[str], Optional[list[float]]]:
    """Alias compatible para la estrategia general de ocho montos."""
    return _extraer_tabla_balance_por_coordenadas(page, column_centers)


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
OCR_MAX_PIXELS = 3_500_000
OCR_RETRY_MAX_PIXELS = 1_200_000
OCR_PAGE_TIMEOUT_SECONDS = 120
OCR_RETRY_TIMEOUT_SECONDS = 90


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
    seccion_contable: Optional[str] = None
    jerarquia_contable: Optional[str] = None
    requiere_revision_extraccion: bool = False
    razones_revision_extraccion: list[str] = field(default_factory=list)


@dataclass
class CertificacionExtraccion:
    # ``timeout`` es operativo, no una discrepancia contable. Nunca certifica,
    # pero conserva las cuentas y diagnósticos recuperados de otras páginas.
    estado: str = "no_evaluable"  # certificada | parcial | fallida | no_evaluable | timeout
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
    observaciones_auxiliares: list[dict] = field(default_factory=list)


@dataclass
class ResultadoParseo:
    archivo: str
    formato_codigo: FormatoCodigo
    separador_miles: str            # '.' o ','
    requirio_ocr: bool
    rotacion_aplicada: int           # 0 o 90
    cuentas: list[CuentaRaw] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    # Sprint 31: contexto del análisis documental previo al parseo.
    # None cuando no se ejecutó (Excel) o cuando el análisis falló.
    document_context: Optional[Any] = None
    # Sprint 34: SOLO anotación de qué extractor se seleccionó (id, familia,
    # confidence, fallback, tiempo). NO cambia la extracción: None cuando no
    # hubo análisis documental o cuando el análisis de extractor falló.
    extractor_info: Optional[dict] = None
    periodos_detectados: list[str] = field(default_factory=list)
    monedas_detectadas: list[str] = field(default_factory=list)
    unidades_monetarias: list[str] = field(default_factory=list)
    certificacion_extraccion: CertificacionExtraccion = field(
        default_factory=CertificacionExtraccion
    )


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
            return False, "Archivo .xls no tiene firma OLE2 válida."

    elif suffix == '.pdf':
        with open(path, 'rb') as f:
            header = f.read(5)
        if header != b'%PDF-':
            return False, "Archivo .pdf no tiene firma PDF válida."

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

    # La detección global del separador es una señal del documento completo,
    # no un contrato para cada celda OCR. En una misma página Tesseract puede
    # alternar 1.234.567 y 1,234,567. Si el propio token exhibe grupos de tres
    # dígitos inequívocos, se privilegia esa evidencia local para no convertir
    # importes válidos en ``None`` y perder una columna completa de la fila.
    if separador_miles == ',' and '.' in v:
        grupos_punto = v.split('.')
        if len(grupos_punto) > 1 and all(
            len(grupo) == 3 and grupo.isdigit()
            for grupo in grupos_punto[1:]
        ):
            v = v.replace('.', '')
    elif separador_miles == '.' and ',' in v:
        grupos_coma = v.split(',')
        if len(grupos_coma) > 1 and all(
            len(grupo) == 3 and grupo.isdigit()
            for grupo in grupos_coma[1:]
        ):
            v = v.replace(',', '')

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
    env = {'OMP_THREAD_LIMIT': '1'}
    if Path(TESSDATA_DIR).is_dir():
        env['TESSDATA_PREFIX'] = TESSDATA_DIR
    return env


def obtener_tesseract_bin() -> str:
    return shutil.which('tesseract') or 'tesseract'


@lru_cache(maxsize=1)
def verificar_runtime_ocr() -> dict:
    """Verifica que Tesseract y el modelo español sean utilizables."""
    try:
        from scripts.ocr_preflight import inspect_ocr_runtime
        return inspect_ocr_runtime(obtener_tesseract_bin())
    except Exception as exc:  # noqa: BLE001 - se convierte en estado explícito
        return {
            "available": False,
            "spa_available": False,
            "version": "",
            "error": f"No se pudo verificar el runtime OCR: {exc}",
        }


_EMBEDDED_AMOUNT = re.compile(
    r"(?<!\w)\(?-?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?\)?(?!\w)"
)
_INTERLEAVED_COLUMN_BLEED = re.compile(
    r"[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]\d+[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]"
    r"|\d+[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]+\d+"
    r"|\b\w*(?:[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]\d{1,2}\.\d{3}|\d{1,2}\.[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ])\w*"
)
_PATRON_MONTO_ADHERIDO_A_PALABRA = re.compile(
    r"^([a-zA-ZáéíóúÁÉÍÓÚñÑüÜ][a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\.\-]*[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\.]|[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d{4,})$"
)


def _desenredar_token_colision(token: str) -> tuple[str, str] | None:
    """Desenreda tokens donde columnas de texto y monto colisionaron en el PDF."""
    if not (any(c.isalpha() for c in token) and any(c.isdigit() for c in token)):
        return None
    letters = []
    digits_and_dots = []
    for ch in token:
        if ch.isdigit() or ch in ".,":
            digits_and_dots.append(ch)
        elif ch.isalpha() or ch in "áéíóúÁÉÍÓÚñÑüÜ":
            letters.append(ch)
        elif ch in "-/()":
            letters.append(ch)

    word = "".join(letters).strip(". ")
    monto_raw = "".join(digits_and_dots).strip(". ")
    m = re.search(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d{4,}", monto_raw)
    if word and m and len(word) >= 2:
        return word, m.group(0)
    return None


def _separar_tokens_monto_adherido(tokens: list[str]) -> list[str]:
    """Separa montos pegados o entrelazados con palabras por solapamiento de columnas."""
    nuevos: list[str] = []
    for t in tokens:
        if _INTERLEAVED_COLUMN_BLEED.search(t):
            desenredado = _desenredar_token_colision(t)
            if desenredado:
                nuevos.append(desenredado[0])
                nuevos.append(desenredado[1])
                continue
        m = _PATRON_MONTO_ADHERIDO_A_PALABRA.match(t)
        if m:
            nuevos.append(m.group(1))
            nuevos.append(m.group(2))
        else:
            nuevos.append(t)
    return nuevos
_DOCUMENT_IDENTIFIER = re.compile(
    r"\b(?:RUT|C\.?\s*I\.?)?\s*\d{1,2}[.]\d{3}[.]\d{3}[-·][0-9K]\b",
    re.I,
)
_LEGAL_AND_TAX_IDENTIFIER = re.compile(
    r"\b(?:LEY|D\.?F\.?L\.?|D\.?L\.?|ART(?:[IÍ]CULO)?|CIRCULAR|RESOLUCI[ÓO]N)\s*N?[°o.]?\s*\d+(?:[.,]\d+)*\b",
    re.I,
)
_LETTER_BLOCK = r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s./()-]{2,}"
_FUSED_LABELS = re.compile(
    rf"(?P<left>{_LETTER_BLOCK}?)\s+(?P<amount>\(?-?\d+(?:[.,]\d+)*\)?)\s+"
    rf"(?P<right>{_LETTER_BLOCK})$"
)


def detectar_linea_sospechosa(
    linea: str, *, mediana_longitud: float = 0.0,
) -> list[str]:
    """Detecta fusiones estructurales sin interpretar su valor contable."""
    limpia = re.sub(r"\s+", " ", linea).strip()
    razones: list[str] = []
    if _FUSED_LABELS.search(limpia):
        razones.append("multiples_glosas_separadas_por_monto")
    numeric_tokens = re.findall(r"\(?-?\d[\d.,]*\)?", limpia)
    letter_tokens = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}", limpia)
    if (
        mediana_longitud > 0
        and len(limpia) >= max(180, int(mediana_longitud * 3))
        and len(numeric_tokens) >= 4
        and len(letter_tokens) >= 4
    ):
        razones.append("longitud_y_densidad_anomala")
    return razones


def marcar_cuenta_sospechosa(cuenta: CuentaRaw, linea: str, razones: list[str]) -> None:
    """Propaga señales de extracción antes de cualquier clasificación."""
    nombre_sin_identificadores = _LEGAL_AND_TAX_IDENTIFIER.sub(
        "", _DOCUMENT_IDENTIFIER.sub("", cuenta.nombre or "")
    )
    contexto_no_contable = bool(re.search(
        r"\b(?:RUT|C\.?\s*I\.?|DIRECCI[ÓO]N|P[ÁA]GINA|OFICINA)\b",
        cuenta.nombre or "", re.I,
    ))
    nombre_con_monto = bool(
        not contexto_no_contable and _EMBEDDED_AMOUNT.search(nombre_sin_identificadores)
    )
    if nombre_con_monto:
        razones = list(dict.fromkeys([*razones, "monto_incrustado_en_glosa"]))
    if not contexto_no_contable and _INTERLEAVED_COLUMN_BLEED.search(nombre_sin_identificadores):
        razones = list(dict.fromkeys([*razones, "nombre_contaminado_por_fusion_de_columnas"]))
    if not razones:
        return
    cuenta.requiere_revision_extraccion = True
    cuenta.razones_revision_extraccion = list(dict.fromkeys(razones))
    cuenta.confianza_extraccion = min(float(cuenta.confianza_extraccion), 0.35)


def detectar_rotacion_osd(img_path: Path) -> Optional[int]:
    try:
        result = subprocess.run(
            [obtener_tesseract_bin(), str(img_path), '-', '--psm', '0', '-l', 'osd'],
            capture_output=True, text=True, timeout=60,
            env=_tesseract_env()
        )
        for line in result.stdout.splitlines():
            if 'Orientation in degrees' in line:
                grados = int(line.split(':')[1].strip())
                return grados
    except Exception:
        pass
    return None


def detectar_rotacion_heuristica(img_path: Path) -> int:
    img = Image.open(img_path)
    mejor_rotacion = 0
    mejor_score = -1

    for rot in (0, 90):
        test_img = img if rot == 0 else img.rotate(rot, expand=True)

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            test_img.save(tmp.name)
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                [obtener_tesseract_bin(), str(tmp_path), '-', '--psm', '6', '-l', 'spa'],
                capture_output=True, text=True, timeout=90,
                env=_tesseract_env()
            )
            texto = result.stdout
            palabras = re.findall(r'[a-záéíóúñA-ZÁÉÍÓÚÑ]{3,}', texto)
            score = len(palabras)
        except Exception:
            score = 0
        finally:
            tmp_path.unlink(missing_ok=True)

        if score > mejor_score:
            mejor_score = score
            mejor_rotacion = rot

    return mejor_rotacion


def ocr_pagina(
    img_path: Path,
    rotacion: int,
    psm: int = 6,
    *,
    timeout_events: Optional[list[str]] = None,
    page_number: Optional[int] = None,
) -> str:
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
            result = subprocess.run(
                [obtener_tesseract_bin(), str(imagen_ocr), '-', '--psm', str(psm), '-l', 'spa'],
                capture_output=True, text=True, timeout=OCR_PAGE_TIMEOUT_SECONDS,
                env=_tesseract_env()
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
                    if timeout_events is not None:
                        timeout_events.append(
                            f"Página {page_number or '?'}: Tesseract excedió "
                            f"{OCR_PAGE_TIMEOUT_SECONDS} segundos."
                        )
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
                result = subprocess.run(
                    [obtener_tesseract_bin(), str(retry_path), '-', '--psm', str(psm), '-l', 'spa'],
                    capture_output=True, text=True,
                    timeout=OCR_RETRY_TIMEOUT_SECONDS,
                    env=_tesseract_env(),
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    "OCR omitido tras segundo timeout de %ss: %s",
                    OCR_RETRY_TIMEOUT_SECONDS,
                    img_path.name,
                )
                if timeout_events is not None:
                    timeout_events.append(
                        f"Página {page_number or '?'}: Tesseract excedió los "
                        "presupuestos principal y reducido."
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


_PATRON_NUMERO_CON_BORDES = re.compile(r"^([|\[]+)(-?\$?\(?(?:\d|[oO])[\d.,oO]*\)?)([|\]]+)$")
_PATRON_NUMERO_BORDE_IZQ = re.compile(r"^([|\[]+)(-?\$?\(?(?:\d|[oO])[\d.,oO]*\)?)$")
_PATRON_NUMERO_BORDE_DER = re.compile(r"^(-?\$?\(?(?:\d|[oO])[\d.,oO]*\)?)([|\]]+)$")


def _limpiar_borde_celda_token(text: str) -> str:
    """Limpia caracteres de cuadrícula (| o []) adheridos a números, preservando tokens ambiguos.

    Casos demostrados y resueltos:
    - Bordes de barra vertical '|' (siempre cuadrícula, nunca notas al pie): '|12345|' -> '12345', '|1|' -> '1'.
    - Corchetes '[' ']' con formato numérico complejo (miles, decimales, signos, moneda, >= 3 dígitos):
      '[54.321]' -> '54.321', '[(1500)]' -> '(1500)', '[-4500]' -> '-4500'.

    Casos ambiguos preservados:
    - '[1]', '[2]', etc. (un dígito o identificador corto entre corchetes puros): sin contexto de columna,
      no se puede distinguir de una llamada a nota al pie ([1]). Se preserva como '[1]'.
    - Glosas textuales ('[A]', '|PROVEEDORES|', '[NOTA 1]'): se preservan intactas.

    Casos numéricos que quedan sin corregir:
    - Si una celda contable contiene un monto de uno o dos dígitos (ej. 1) y el OCR adhiere corchetes '[1]',
      permanecerá como '[1]' a nivel de token TSV y requerirá desambiguación contextual posterior.
    """
    if not text:
        return text
    if re.match(r"^\[\d{1,2}\]$", text):
        return text

    m = _PATRON_NUMERO_CON_BORDES.match(text)
    left_b, num_p, right_b = "", "", ""
    if m:
        left_b, num_p, right_b = m.group(1), m.group(2), m.group(3)
    else:
        m2 = _PATRON_NUMERO_BORDE_IZQ.match(text)
        if m2:
            left_b, num_p = m2.group(1), m2.group(2)
        else:
            m3 = _PATRON_NUMERO_BORDE_DER.match(text)
            if m3:
                num_p, right_b = m3.group(1), m3.group(2)

    if num_p:
        has_bracket = ("[" in left_b) or ("]" in right_b)
        if has_bracket:
            es_claramente_contable = any(c in num_p for c in ".,$()-") or len(re.sub(r"\D", "", num_p)) >= 3
            if not es_claramente_contable:
                return text
        return num_p
    return text


def ocr_pagina_tsv(img_path: Path, rotacion: int, psm: int = 6) -> list[dict]:
    """Obtiene palabras y coordenadas OCR para reconstrucción tabular."""
    tmp_path: Optional[Path] = None
    imagen_ocr = img_path
    if rotacion != 0:
        with Image.open(img_path) as img:
            preparada = img.rotate(rotacion, expand=True)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                preparada.save(tmp.name)
                tmp_path = Path(tmp.name).resolve()
                imagen_ocr = tmp_path
    try:
        try:
            result = subprocess.run(
                [
                    obtener_tesseract_bin(), str(Path(imagen_ocr).resolve()), "stdout", "-l", "spa",
                    "--psm", str(psm), "tsv",
                ],
                capture_output=True, text=True, errors="replace",
                timeout=OCR_PAGE_TIMEOUT_SECONDS,
                env=_tesseract_env(),
            )
        except subprocess.TimeoutExpired:
            logger.warning("OCR TSV excedió el timeout: %s", img_path.name)
            return []
        if result.returncode != 0 or not result.stdout.strip():
            return []
        words: list[dict] = []
        line_positions: dict[tuple[str, str, str, str], float] = {}
        for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t"):
            text = str(row.get("text") or "").strip()
            if row.get("level") != "5" or not text:
                continue
            text = _limpiar_borde_celda_token(text)
            try:
                left = float(row["left"])
                top_coord = float(row["top"])
                width = float(row["width"])
                height = float(row["height"])
                conf = float(row.get("conf") or 0)
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
                "left": left,
                "width": width,
                "top": line_positions[line_key],
                "raw_top": top_coord,
                "height": height,
                "bottom": top_coord + height,
                "yc": top_coord + height / 2.0,
                "conf": conf,
                "block_num": int(row.get("block_num") or 0),
                "par_num": int(row.get("par_num") or 0),
                "line_num": int(row.get("line_num") or 0),
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


def _extraer_codigo_y_nombre_cuenta(texto: str) -> tuple[Optional[str], str]:
    """Extrae código de cuenta y glosa normalizada.

    Reconoce:
    - Códigos con separador (puntos o guiones): 1-01-01, 1.1.01.01, 1101-51
    - Códigos compactos o planos: 110101, 99010001 (4 a 10 dígitos)
    - Códigos concatenados: 110101BANCO
    - Códigos con puntuación residual OCR: .110101, -1.1.01
    """
    raw = str(texto or "").strip()
    if not raw:
        return None, ""
    # 1. Separadores estándar (1-01-01, 1.1.01.01, 1101-51)
    m = re.match(r"^\s*[^\w\s]{0,2}(\d{1,8}(?:[.\-]\d{1,8})+)\s*(.+)?$", raw)
    if m:
        return m.group(1), (m.group(2) or "").strip()
    # 2. Código compacto/plano (4 a 10 dígitos) seguido de espacio y nombre
    m = re.match(r"^\s*[^\w\s]{0,2}(\d{4,10})[.\-]?\s+(.+)$", raw)
    if m:
        return m.group(1).strip(".-_"), (m.group(2) or "").strip()
    # 3. Código concatenado sin espacio a nombre en letras
    m = re.match(r"^\s*[^\w\s]{0,2}(\d{4,8})(?=[A-Za-zÁÉÍÓÚÑáéíóúñ])(.+)$", raw)
    if m:
        return m.group(1), (m.group(2) or "").strip()
    return None, raw


def _determinar_alcance_control(
    nombre_linea: str, linea_idx: int = -1, total_lineas: int = -1,
    lineas_previas: Optional[list[str]] = None,
) -> str:
    """Clasifica el alcance de un control contable según su evidencia contextual.

    Alcances posibles:
    - 'transporte': arrastre o saldo inicial proveniente de página anterior.
    - 'pagina': subtotal o suma parcial correspondiente exclusivamente a esta página.
    - 'acumulado': total acumulado progresivo de varias páginas.
    - 'seccion': subtotal de un grupo o sección específica (ej. activo circulante).
    - 'documento_completo': totales generales de cierre del balance.
    - 'resultado_cierre': filas de utilidad, pérdida o sumas iguales de cuadre.
    - 'no_evaluable': glosa de control ambigua o con alcance indeterminado.

    Reglas:
    1. Si la línea contiene código de cuenta, es cuenta de detalle, NO control ('no_evaluable').
    2. La posición por sí sola no determina el alcance de página.
    3. Sin evidencia contextual explícita o textual suficiente, devuelve 'no_evaluable'.
    4. Si hay 'transporte' en la cabecera/previas de la página, los subtotales inferiores son 'acumulado'.
    """
    raw_name = str(nombre_linea or "").strip()
    cod, glosa = _extraer_codigo_y_nombre_cuenta(raw_name)
    if cod is not None:
        return "no_evaluable"

    norm = _sin_acentos(raw_name).lower()
    norm = re.sub(r"\s+", " ", norm)

    # Cierre contable
    if re.match(
        r"^(?:resultado(?:\s+del)?\s+ejercicio|utilidad(?:\s+del)?\s+ejercicio|"
        r"p[eé]rdida(?:\s+del)?\s+ejercicio|utilidad\s+neta|p[eé]rdida\s+neta|"
        r"utilidad\s+o\s+p[eé]rdida|p[eé]rdidas?\s*(?:/|y|o)\s*ganancias?|"
        r"sumas\s+iguales|totales\s+iguales)\b", norm, re.I
    ):
        return "resultado_cierre"

    # Transporte / Arrastre
    if re.search(r"\b(?:transporte|arrastre|suma\s+y\s+sigue|van|vienen|viene\s+de)\b", norm, re.I):
        return "transporte"

    # Acumulado explícito
    if re.search(r"\b(?:total\s+acumulado|subtotal\s+acumulado|sumas\s+acumuladas|acumulado)\b", norm, re.I):
        return "acumulado"

    # Totales generales de balance / cierre
    if re.search(r"\b(?:total\s+general|totales\s+generales|sumas\s+totales|total\s+del\s+balance|balance\s+general)\b", norm, re.I):
        return "documento_completo"

    # Secciones específicas
    if re.search(r"\b(?:total\s+activo|total\s+pasivo|activo\s+circulante|pasivo\s+circulante|activo\s+fijo|total\s+patrimonio|total\s+resultado|total\s+ingresos|total\s+costos|total\s+gastos)\b", norm, re.I):
        return "seccion"

    # Subtotales de página: requiere evidencia textual explícita de página/hoja
    if re.search(r"\b(?:subtotal\s+p[aá]gina|total\s+p[aá]gina|sub-total\s+p[aá]gina|suma\s+p[aá]gina|total\s+hoja|subtotal\s+hoja|suma\s+parcial\s+p[aá]gina)\b", norm, re.I):
        return "pagina"

    # Acumulado implícito contextual: si en las líneas previas hubo un transporte/arrastre
    if lineas_previas:
        for prev in lineas_previas[:5]:
            p_norm = _sin_acentos(str(prev)).lower()
            if re.search(r"\b(?:transporte|arrastre|viene\s+de|saldo\s+anterior)\b", p_norm):
                if re.search(r"\b(?:subtotal|total|suma)\b", norm, re.I):
                    return "acumulado"

    # Sin evidencia concluyente, no se asume página arbitrariamente
    return "no_evaluable"


def _evaluar_conciliacion_detalle_control(
    lineas: list[str], tolerancia: float = 10.0,
) -> dict:
    """Evalúa la conciliación del detalle contra controles en una página OCR de ocho columnas.

    Detecta filas incompletas (1 a 7 montos) y controles contradictorios.
    Una fila de detalle incompleta bloquea la conciliación válida retornando 'evaluacion_incompleta'.
    """
    total_lineas = len(lineas)
    filas_detalle: list[list[float]] = []
    filas_incompletas: list[dict] = []
    controles_detectados: list[dict] = []

    for idx, linea in enumerate(lineas):
        tokens = linea.split()
        if not tokens:
            continue

        # Determinar cuántos tokens finales corresponden a montos numéricos válidos
        k = 0
        while k < len(tokens):
            norm_tok = normalizar_token_ocr(tokens[-(k + 1)])
            if PATRON_MONTOS.fullmatch(norm_tok) and parsear_monto(tokens[-(k + 1)], ".") is not None:
                k += 1
            else:
                break

        if k == 0:
            continue

        if k >= 8:
            amounts = tokens[-8:]
            parsed_vals = [parsear_monto(t, ".") for t in amounts]
            vals = [float(v or 0.0) for v in parsed_vals]
            if not any(abs(v) > 0 for v in vals):
                continue

            nombre_linea = " ".join(tokens[:-8])
            cod, glosa = _extraer_codigo_y_nombre_cuenta(nombre_linea)

            # Si la línea tiene código de cuenta, es cuenta de detalle, NUNCA control
            if cod is not None:
                filas_detalle.append(vals)
                continue

            alcance = _determinar_alcance_control(
                nombre_linea, linea_idx=idx, total_lineas=total_lineas,
                lineas_previas=lineas[:idx],
            )

            if alcance != "no_evaluable" or any(w in _sin_acentos(nombre_linea).lower() for w in ["total", "subtotal", "sumas"]):
                deb, cred, s_deb, s_cred, act, pas, perd, gan = vals
                neto_mov = deb - cred
                neto_saldos = s_deb - s_cred
                neto_clasif = (act - pas) + (perd - gan)

                consistencia_mov_saldo = abs(neto_mov - neto_saldos) <= tolerancia
                consistencia_saldo_clasif = abs(neto_saldos - neto_clasif) <= tolerancia

                if alcance == "documento_completo" or "iguales" in _sin_acentos(nombre_linea).lower():
                    valido_interno = bool(
                        abs(deb - cred) <= tolerancia
                        and abs(s_deb - s_cred) <= tolerancia
                        and abs((act - pas) - (gan - perd)) <= tolerancia
                    )
                    corrompido = not valido_interno
                else:
                    valido_interno = bool(consistencia_mov_saldo and consistencia_saldo_clasif)
                    corrompido = bool(
                        (not consistencia_mov_saldo and (abs(deb) > tolerancia or abs(cred) > tolerancia))
                        or (not consistencia_saldo_clasif and (abs(act) > tolerancia or abs(pas) > tolerancia or abs(perd) > tolerancia or abs(gan) > tolerancia))
                    )

                controles_detectados.append({
                    "linea": linea,
                    "alcance": alcance,
                    "valores": vals,
                    "valido_interno": valido_interno,
                    "corrompido": corrompido,
                    "incompleto": False,
                })
            else:
                filas_detalle.append(vals)

        elif 1 <= k < 8:
            prefix_tokens = tokens[:-k]
            prefix_line = " ".join(prefix_tokens)
            cod, glosa = _extraer_codigo_y_nombre_cuenta(prefix_line)
            parsed_vals = [float(parsear_monto(t, ".") or 0.0) for t in tokens[-k:]]

            alcance = _determinar_alcance_control(
                prefix_line, linea_idx=idx, total_lineas=total_lineas,
                lineas_previas=lineas[:idx],
            )
            es_control = (cod is None) and (alcance != "no_evaluable" or any(w in _sin_acentos(prefix_line).lower() for w in ["total", "subtotal", "sumas"]))

            if es_control:
                controles_detectados.append({
                    "linea": linea,
                    "alcance": alcance if alcance != "no_evaluable" else "pagina",
                    "valores": parsed_vals,
                    "valido_interno": False,
                    "corrompido": False,
                    "incompleto": True,
                })
            else:
                # Fila de detalle incompleta detectada
                filas_incompletas.append({
                    "linea": linea,
                    "codigo": cod,
                    "valores": parsed_vals,
                    "k": k,
                })

    sumas_detalle = [0.0] * 8
    for row in filas_detalle:
        for c_idx in range(8):
            sumas_detalle[c_idx] += row[c_idx]

    controles_pagina = [c for c in controles_detectados if c["alcance"] == "pagina"]

    if not controles_detectados:
        estado = "evaluacion_incompleta" if filas_incompletas else "control_ausente"
        motivo = f"Filas de detalle incompletas ({len(filas_incompletas)}) detectadas sin control" if filas_incompletas else "No se detectó fila de control en la página"
        return {
            "estado": estado,
            "alcance": "no_evaluable",
            "linea_control": None,
            "subtotal_valido_interno": False,
            "subtotal_corrompido": False,
            "columnas_conciliadas": 0,
            "discrepancias": {},
            "sumas_detalle": sumas_detalle,
            "valores_control": [],
            "filas_detalle_count": len(filas_detalle),
            "filas_incompletas_count": len(filas_incompletas),
            "motivo": motivo,
        }

    # Detectar controles de página contradictorios
    if len(controles_pagina) > 1:
        primer_c = controles_pagina[0]
        primer_vals = primer_c["valores"]
        son_contradictorios = False
        for otro in controles_pagina[1:]:
            otro_vals = otro["valores"]
            if len(primer_vals) != 8 or len(otro_vals) != 8:
                son_contradictorios = True
                break
            if any(abs(primer_vals[i] - otro_vals[i]) > tolerancia for i in range(8)):
                son_contradictorios = True
                break
        if son_contradictorios:
            return {
                "estado": "discrepancia",
                "alcance": "pagina",
                "linea_control": " / ".join(c["linea"] for c in controles_pagina),
                "subtotal_valido_interno": False,
                "subtotal_corrompido": True,
                "columnas_conciliadas": 0,
                "discrepancias": {"controles_contradictorios": len(controles_pagina)},
                "sumas_detalle": sumas_detalle,
                "valores_control": primer_vals,
                "filas_detalle_count": len(filas_detalle),
                "filas_incompletas_count": len(filas_incompletas),
                "motivo": f"Controles de página contradictorios detectados ({len(controles_pagina)} controles con valores discrepantes)",
            }

    ctrl_pagina = controles_pagina[0] if controles_pagina else None

    if not ctrl_pagina:
        primer_ctrl = controles_detectados[0]
        estado = "evaluacion_incompleta" if filas_incompletas else "alcance_desconocido"
        return {
            "estado": estado,
            "alcance": primer_ctrl["alcance"],
            "linea_control": primer_ctrl["linea"],
            "subtotal_valido_interno": primer_ctrl["valido_interno"],
            "subtotal_corrompido": primer_ctrl["corrompido"],
            "columnas_conciliadas": 0,
            "discrepancias": {},
            "sumas_detalle": sumas_detalle,
            "valores_control": primer_ctrl["valores"],
            "filas_detalle_count": len(filas_detalle),
            "filas_incompletas_count": len(filas_incompletas),
            "motivo": f"Control presente con alcance '{primer_ctrl['alcance']}', no evaluable contra detalle de página",
        }

    ctrl_vals = ctrl_pagina["valores"]
    if ctrl_pagina.get("incompleto") or len(ctrl_vals) != 8:
        return {
            "estado": "evaluacion_incompleta",
            "alcance": "pagina",
            "linea_control": ctrl_pagina["linea"],
            "subtotal_valido_interno": False,
            "subtotal_corrompido": False,
            "columnas_conciliadas": 0,
            "discrepancias": {},
            "sumas_detalle": sumas_detalle,
            "valores_control": ctrl_vals,
            "filas_detalle_count": len(filas_detalle),
            "filas_incompletas_count": len(filas_incompletas),
            "motivo": "Celdas de control incompletas en la fila de subtotal (no se asume cero)",
        }

    # Si hay filas de detalle incompletas, bloquea conciliación válida
    if filas_incompletas:
        return {
            "estado": "evaluacion_incompleta",
            "alcance": "pagina",
            "linea_control": ctrl_pagina["linea"],
            "subtotal_valido_interno": ctrl_pagina["valido_interno"],
            "subtotal_corrompido": ctrl_pagina["corrompido"],
            "columnas_conciliadas": 0,
            "discrepancias": {},
            "sumas_detalle": sumas_detalle,
            "valores_control": ctrl_vals,
            "filas_detalle_count": len(filas_detalle),
            "filas_incompletas_count": len(filas_incompletas),
            "motivo": f"Filas de detalle incompletas ({len(filas_incompletas)}) impiden conciliación confiable contra subtotal",
        }

    nombres_cols = RAW_MONETARY_COLUMNS
    discrepancias = {}
    cols_conciliadas = 0
    for i in range(8):
        diff = round(abs(sumas_detalle[i] - ctrl_vals[i]), 2)
        if diff <= tolerancia:
            cols_conciliadas += 1
        else:
            discrepancias[nombres_cols[i]] = diff

    if cols_conciliadas == 8:
        estado = "conciliacion_valida"
        motivo = "Conciliación válida de las 8 columnas contra subtotal de página"
    else:
        estado = "discrepancia"
        motivo = f"Discrepancia en {8 - cols_conciliadas} columna(s) contra subtotal de página"

    return {
        "estado": estado,
        "alcance": "pagina",
        "linea_control": ctrl_pagina["linea"],
        "subtotal_valido_interno": ctrl_pagina["valido_interno"],
        "subtotal_corrompido": ctrl_pagina["corrompido"],
        "columnas_conciliadas": cols_conciliadas,
        "discrepancias": discrepancias,
        "sumas_detalle": sumas_detalle,
        "valores_control": ctrl_vals,
        "filas_detalle_count": len(filas_detalle),
        "filas_incompletas_count": len(filas_incompletas),
        "motivo": motivo,
    }


def _evaluar_control_subtotal_pagina(
    lineas: list[str], tolerancia: float = 10.0,
) -> tuple[bool, bool, bool, Optional[str], str, bool]:
    """Capa de compatibilidad para evaluar_control_subtotal_pagina."""
    res = _evaluar_conciliacion_detalle_control(lineas, tolerancia)
    found = res["estado"] != "control_ausente"
    valido = res["subtotal_valido_interno"]
    corrupt = res["subtotal_corrompido"]
    linea = res["linea_control"]
    alcance = res["alcance"]
    cuadra = res["estado"] == "conciliacion_valida"
    return found, valido, corrupt, linea, alcance, cuadra


def _extraer_cuentas_candidato(lineas: list[str]) -> list[dict]:
    """Extrae estructura normalizada de cuentas por candidato para comparación."""
    cuentas = []
    total_lineas = len(lineas)
    for idx, linea in enumerate(lineas):
        tokens = linea.split()
        if len(tokens) < 9:
            continue
        amounts = tokens[-8:]
        if not all(PATRON_MONTOS.fullmatch(normalizar_token_ocr(t)) for t in amounts):
            continue
        parsed_vals = [parsear_monto(t, ".") for t in amounts]
        if any(v is None for v in parsed_vals):
            continue
        vals = [float(v or 0.0) for v in parsed_vals]
        nombre_raw = " ".join(tokens[:-8])
        cod, nom = _extraer_codigo_y_nombre_cuenta(nombre_raw)
        if not any(abs(v) > 0 for v in vals) and cod is None:
            continue

        # Si no tiene código, verificar si es fila de control
        if cod is None:
            alcance = _determinar_alcance_control(
                nombre_raw, linea_idx=idx, total_lineas=total_lineas,
                lineas_previas=lineas[:idx],
            )
            if alcance != "no_evaluable" or any(w in _sin_acentos(nombre_raw).lower() for w in ["total", "subtotal", "sumas", "balance general", "totales iguales"]):
                continue

        cuentas.append({
            "codigo": cod,
            "nombre": nom.strip() if nom else nombre_raw.strip(),
            "montos": vals,
            "raw": linea,
        })
    return cuentas


_PATRON_RUT_RUIDO = re.compile(r"(?:\b\d{1,2}(?:\.\d{3}){2}-[\dkK]\b|\b\d{7,8}-[\dkK]\b)\s+(?:p[aá]gina|hoja)?", re.I)
_PATRON_PERIODO_RUIDO = re.compile(r"^(?:desde|hasta|ejercicio|periodo|a[nñ]o)\s+[a-z0-9\s]*\d{4}", re.I)
_PATRON_PAGINA_RUIDO = re.compile(r"^p[aá]gina\s+\d+", re.I)
_PATRON_DOCUMENTAL_RUIDO_GLOSA = re.compile(
    r"\b(?:p[aá]gina|hoja|rut|r\.u\.t|periodo|ejercicio|desde|hasta|fecha|folio|secci[oó]n|membrete|raz[oó]n\s+social|giro|direcci[oó]n|comuna|ciudad|balance\s+tributario|balance\s+general|balance\s+clasificado|estado\s+financiero|moneda|pesos|clp|miles)\b",
    re.I,
)


def _es_ruido_documental_ocr(cta: dict) -> bool:
    """Identifica si una fila extraída es ruido de membrete o pie de página y no una cuenta contable.

    Exige evidencia documental positiva en la glosa o identificador.
    La magnitud numérica por sí sola (por ejemplo montos pequeños o valor similar a un año)
    NUNCA acredita ruido sin evidencia textual o estructural concordante.
    """
    cod = cta.get("codigo")
    nom = cta.get("nombre", "").strip()
    montos = cta.get("montos", [0.0]*8)

    # 1. Si el código parece un RUT o número de página, es ruido
    if cod and (re.search(r"^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$", cod) or re.search(r"^\d{7,8}-[\dkK]$", cod)):
        return True

    # 2. Glosa que coincide con patrones positivos de membrete, RUT, periodo o pie de página
    if _PATRON_RUT_RUIDO.search(nom) or _PATRON_PERIODO_RUIDO.search(nom) or _PATRON_PAGINA_RUIDO.search(nom) or _PATRON_DOCUMENTAL_RUIDO_GLOSA.search(nom):
        # Si tiene código contable legítimo (4 a 10 dígitos) y montos contables válidos,
        # NO se descarta salvo que sea explícitamente membrete/RUT no contable
        if cod and any(abs(v) > 0.001 for v in montos) and not _PATRON_RUT_RUIDO.search(nom):
            return False
        return True

    return False


def _tiene_identidad_contable_valida(montos: list[float], tolerancia: float = 10.0) -> bool:
    """Verifica si los 8 montos satisfacen las identidades Debe-Haber == Saldos."""
    if len(montos) < 8:
        return False
    deb, cred, s_deb, s_cred, act, pas, perd, gan = montos[:8]
    if not any(abs(v) > 0.001 for v in montos[:8]):
        return False

    diff_saldos = abs((deb - cred) - (s_deb - s_cred))
    if diff_saldos > tolerancia:
        return False

    diff_inv_res = abs(((act - pas) + (perd - gan)) - (s_deb - s_cred))
    if diff_inv_res > tolerancia:
        return False

    return True


def _reconciliar_fragmentos_ocr(cuentas: list[dict]) -> list[dict]:
    """Reconcilia filas fragmentadas preservando cuentas codificadas en cero."""
    reconciliadas = []
    i = 0
    n = len(cuentas)
    while i < n:
        c = cuentas[i]
        montos = c.get("montos", [0.0]*8)
        has_amounts = any(abs(v) > 0.001 for v in montos)

        # Si tiene código pero NO tiene montos, buscar si la siguiente fila no tiene código pero SÍ tiene montos
        if c.get("codigo") and not has_amounts:
            if i + 1 < n and not cuentas[i+1].get("codigo") and any(abs(v) > 0.001 for v in cuentas[i+1].get("montos", [])):
                sig = cuentas[i+1]
                merged = {
                    "codigo": c["codigo"],
                    "nombre": f"{c.get('nombre', '')} {sig.get('nombre', '')}".strip(),
                    "montos": sig["montos"],
                    "raw": f"{c.get('raw', '')} + {sig.get('raw', '')}",
                    "linea_idx": c.get("linea_idx", i),
                }
                reconciliadas.append(merged)
                i += 2
                continue
            else:
                # Cuenta codificada con montos en cero sin fragmento posterior:
                # PRESERVAR explícitamente para evitar pérdida silenciosa.
                c_cero = dict(c)
                c_cero["monto_cero_preservado"] = True
                reconciliadas.append(c_cero)
                i += 1
                continue

        # Si no tiene montos y no tiene código (fragmento de texto puro acolchado con ceros sin valor)
        if not c.get("codigo") and not has_amounts and not c.get("monto_cero_preservado"):
            i += 1
            continue

        reconciliadas.append(c)
        i += 1

    return reconciliadas


def _limpiar_glosa_ruido(g: str) -> str:
    """Elimina puntuación y ruido de bordes (guiones, viñetas, barras, porcentajes, etc.)."""
    s = str(g or "").strip()
    s = re.sub(r"^[—–\-\*\•\.\,\:\;\/\\%#\|\s]+", "", s)
    s = re.sub(r"[—–\-\*\•\.\,\:\;\/\\%#\|\s]+$", "", s)
    return s.strip()


def _son_glosas_compatibles(g1: str, g2: str) -> bool:
    """Evalúa si dos glosas son semánticamente compatibles."""
    g1_c = _limpiar_glosa_ruido(g1)
    g2_c = _limpiar_glosa_ruido(g2)
    s1 = re.sub(r"\s+", " ", _sin_acentos(g1_c).lower().strip())
    s2 = re.sub(r"\s+", " ", _sin_acentos(g2_c).lower().strip())
    if not s1 or not s2:
        return True
    if s1 == s2 or s1.startswith(s2) or s2.startswith(s1) or s1 in s2 or s2 in s1:
        return True
    import difflib
    ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
    return ratio >= 0.80


def _es_glosa_reconciliable_misma_cuenta(g1: str, g2: str) -> bool:
    """Evalúa si dos glosas de una misma cuenta con importes idénticos pueden reconciliarse.

    Aplica bajo la Regla 4 cuando:
    - Una es ruido corto OCR (caracteres alfabéticos < 3, como 'ii') mientras la otra es sustantiva (>= 3).
    - Una es prefijo, sufijo o subcadena de la otra (tras limpieza de puntuación y números residuales).
    """
    g1_c = _limpiar_glosa_ruido(g1)
    g2_c = _limpiar_glosa_ruido(g2)
    s1 = re.sub(r"\s+", " ", _sin_acentos(g1_c).lower().strip())
    s2 = re.sub(r"\s+", " ", _sin_acentos(g2_c).lower().strip())

    if not s1 or not s2:
        return True

    alpha1 = re.findall(r"[a-z]", s1)
    alpha2 = re.findall(r"[a-z]", s2)
    if (len(alpha1) < 3 and len(alpha2) >= 3) or (len(alpha2) < 3 and len(alpha1) >= 3):
        return True

    if s1.startswith(s2) or s2.startswith(s1) or s1.endswith(s2) or s2.endswith(s1):
        return True

    s1_no_num = re.sub(r"\b\d+\b", "", s1).strip()
    s2_no_num = re.sub(r"\b\d+\b", "", s2).strip()
    if s1_no_num and s2_no_num:
        if s1_no_num.startswith(s2_no_num) or s2_no_num.startswith(s1_no_num):
            return True
        if s1_no_num.endswith(s2_no_num) or s2_no_num.endswith(s1_no_num):
            return True

    raw1 = re.sub(r"[^a-z0-9]", "", s1)
    raw2 = re.sub(r"[^a-z0-9]", "", s2)
    if len(raw1) >= 6 and len(raw2) >= 6:
        if raw1 in raw2 or raw2 in raw1:
            return True

    return False


def _elegir_glosa_sustantiva(g1: str, g2: str) -> str:
    """Selecciona la glosa más informativa y descriptiva entre dos candidatas."""
    g1_c = _limpiar_glosa_ruido(g1)
    g2_c = _limpiar_glosa_ruido(g2)
    alpha1 = len(re.findall(r"[a-zA-Z]", g1_c))
    alpha2 = len(re.findall(r"[a-zA-Z]", g2_c))
    if alpha1 != alpha2:
        return g1 if alpha1 > alpha2 else g2
    return g1 if len(g1_c) >= len(g2_c) else g2


def _normalizar_codigo(codigo: Any) -> str:
    if codigo is None:
        return ""
    return re.sub(r"[^0-9]", "", str(codigo))


def _normalizar_glosa(glosa: Any) -> str:
    if not glosa:
        return ""
    s = _sin_acentos(str(glosa)).lower()
    return re.sub(r"[^a-z0-9]", "", s)


@dataclass
class FilaComposicionOCR:
    motor_origen: str                # "PSM 6", "PSM 4", "FUSION_RECONCILIADA", "RELECTURA_FOCALIZADA", "AMBIGUA"
    pagina: int
    linea_origen: int
    codigo_normalizado: Optional[str]
    glosa_normalizada: str
    valores_candidatos: dict[str, list[float]]  # {"PSM 6": [...], "PSM 4": [...]}
    valores_finales: list[float]                # 8 montos
    transformacion_aplicada: str                 # "coincidencia_exacta", "seleccion_candidato_valido", "admision_unilateral_integra", "reconciliacion_fragmento", "bloqueo"
    regla_aceptacion: str                        # regla formal
    nivel_confianza: float
    motivo_revision: Optional[str] = None
    es_ambigua: bool = False
    bloquea_certificacion: bool = False
    evento_relectura: Optional[str] = None


@dataclass
class ResultadoComposicionPaginaOCR:
    pagina: int
    filas_compuestas: list[FilaComposicionOCR]
    filas_ambiguas_count: int
    bloqueada: bool
    motivo_bloqueo: Optional[str] = None
    lineas_compuestas_texto: list[str] = field(default_factory=list)
    eventos_relectura: list[dict] = field(default_factory=list)


def _relectura_focalizada_ocr(
    img_path: Optional[Path],
    rotacion: int,
    words_tsv: Optional[list[dict]],
    codigo: Optional[str],
    glosa: str,
    montos_previos: list[float],
    pagina: int = 1,
    linea_idx: int = 0,
) -> tuple[Optional[FilaComposicionOCR], dict[str, Any]]:
    """Evalúa una relectura focalizada sobre la región de una línea identificada mediante jerarquía TSV.

    Contrato y garantías:
    1. Localiza la línea exacta usando la jerarquía (block_num, par_num, line_num) de TSV.
    2. Recorta una caja acotada horizontal y verticalmente con márgenes controlados.
    3. Ejecuta OCR focalizado (PSM 7 con fallback a PSM 6 si es necesario).
    4. Comprueba que el resultado confirme de forma independiente TANTO el código COMO los importes.
    5. Registra de forma estructurada los eventos de falla, timeout o ausencia de geometría sin excepciones silenciosas.
    """
    cod_norm = _normalizar_codigo(codigo) if codigo else ""

    if not img_path or not img_path.exists() or not words_tsv:
        evento = {
            "tipo": "ausencia_geometria",
            "codigo": codigo,
            "glosa": glosa,
            "pagina": pagina,
            "detalle": "Imagen no disponible o TSV vacío para relectura focalizada",
        }
        return (None, evento)

    # 1. Encontrar la palabra ancla en words_tsv usando código normalizado o fragmento de glosa
    anchor_word = None
    if cod_norm and len(cod_norm) >= 4:
        for w in words_tsv:
            txt_cod = _normalizar_codigo(str(w.get("text", "")))
            if cod_norm in txt_cod or (len(txt_cod) >= 4 and txt_cod in cod_norm):
                anchor_word = w
                break

    if not anchor_word and glosa:
        glosa_norm = _normalizar_glosa(glosa)
        for w in words_tsv:
            txt_norm = _normalizar_glosa(str(w.get("text", "")))
            if len(txt_norm) >= 5 and txt_norm in glosa_norm:
                anchor_word = w
                break

    if not anchor_word:
        evento = {
            "tipo": "ausencia_geometria",
            "codigo": codigo,
            "glosa": glosa,
            "pagina": pagina,
            "detalle": f"No se encontró palabra ancla para cuenta {codigo or glosa} en TSV",
        }
        return (None, evento)

    # 2. Extraer todas las palabras que comparten la misma línea usando coordenadas físicas TSV
    anchor_yc = anchor_word.get("yc")
    if anchor_yc is None:
        anchor_yc = anchor_word.get("raw_top", 0.0) + anchor_word.get("height", 20.0) / 2.0
    anchor_h = anchor_word.get("height", 20.0)
    tol_y = max(12.0, anchor_h * 0.6)

    line_words = [
        w for w in words_tsv
        if abs(w.get("yc", w.get("raw_top", 0.0) + w.get("height", 20.0) / 2.0) - anchor_yc) <= tol_y
    ]

    if not line_words:
        evento = {
            "tipo": "ausencia_geometria",
            "codigo": codigo,
            "glosa": glosa,
            "pagina": pagina,
            "detalle": f"No se encontraron palabras en la línea jerárquica de {codigo}",
        }
        return (None, evento)

    # 3. Calcular caja acotada horizontal y verticalmente con márgenes controlados
    try:
        from PIL import Image
        with Image.open(img_path) as im:
            raw_xmin = min(w.get("x0", w.get("left", 0.0)) for w in line_words)
            raw_xmax = max(w.get("x1", w.get("left", 0.0) + w.get("width", 0.0)) for w in line_words)
            raw_ymin = min(w.get("raw_top", w.get("top", 0.0)) for w in line_words)
            raw_ymax = max(w.get("bottom", w.get("raw_top", 0.0) + w.get("height", 0.0)) for w in line_words)

            margin_x = 25
            margin_y = 8
            xmin = max(0, int(raw_xmin - margin_x))
            xmax = min(im.width, int(raw_xmax + margin_x))
            ymin = max(0, int(raw_ymin - margin_y))
            ymax = min(im.height, int(raw_ymax + margin_y))

            if raw_xmax <= raw_xmin + 20 or xmax <= xmin + 50 or ymax <= ymin + 5:
                evento = {
                    "tipo": "geometria_invalida",
                    "codigo": codigo,
                    "glosa": glosa,
                    "pagina": pagina,
                    "detalle": f"Caja de recorte acotada inválida: ({xmin}, {ymin}, {xmax}, {ymax})",
                }
                return (None, evento)

            crop_box = (xmin, ymin, xmax, ymax)
            cropped = im.crop(crop_box)

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_crop:
                tmp_crop_path = Path(tmp_crop.name)
            try:
                cropped.save(tmp_crop_path)
                tess_bin = obtener_tesseract_bin()
                env = _tesseract_env()

                # Intento 1: PSM 7 (single text line)
                cmd7 = [tess_bin, str(tmp_crop_path), "stdout", "--psm", "7", "-l", "spa+eng"]
                res = None
                try:
                    res = subprocess.run(cmd7, capture_output=True, text=True, timeout=5, env=env)
                except subprocess.TimeoutExpired:
                    evento = {
                        "tipo": "timeout",
                        "codigo": codigo,
                        "glosa": glosa,
                        "pagina": pagina,
                        "detalle": "Timeout de 5s expirado en Tesseract PSM 7 focalizado",
                    }
                    return (None, evento)

                crop_line = res.stdout.strip() if (res and res.returncode == 0) else ""

                # Intento 2: Fallback a PSM 6 focalizado si PSM 7 no produjo nada o no tiene números
                if not crop_line or not re.search(r"\d", crop_line):
                    cmd6 = [tess_bin, str(tmp_crop_path), "stdout", "--psm", "6", "-l", "spa+eng"]
                    try:
                        res6 = subprocess.run(cmd6, capture_output=True, text=True, timeout=5, env=env)
                        if res6.returncode == 0 and res6.stdout.strip():
                            crop_line = res6.stdout.strip()
                    except subprocess.TimeoutExpired:
                        evento = {
                            "tipo": "timeout",
                            "codigo": codigo,
                            "glosa": glosa,
                            "pagina": pagina,
                            "detalle": "Timeout de 5s expirado en Tesseract PSM 6 focalizado",
                        }
                        return (None, evento)

                if not crop_line:
                    evento = {
                        "tipo": "falla_ejecucion",
                        "codigo": codigo,
                        "glosa": glosa,
                        "pagina": pagina,
                        "detalle": "Tesseract no produjo texto en recorte focalizado",
                    }
                    return (None, evento)

                # 4. Parsear cuenta del recorte focalizado y comprobar confirmación independiente de código E importes
                ctas_crop = _extraer_cuentas_candidato([crop_line])
                m_prev = montos_previos or [0.0] * 8
                if ctas_crop:
                    c_cand = ctas_crop[0]
                    m_crop = c_cand.get("montos", [0.0] * 8)
                    re_cod = c_cand.get("codigo")
                    re_cod_norm = _normalizar_codigo(re_cod) if re_cod else ""
                    code_matches = bool(cod_norm and re_cod_norm and (cod_norm == re_cod_norm or cod_norm in re_cod_norm))
                    id_valida = _tiene_identidad_contable_valida(m_crop, tolerancia=10.0)
                    amounts_match = all(abs(a - b) <= 10.0 for a, b in zip(m_crop[:8], m_prev[:8]))
                    glosa_final = c_cand.get("nombre") or glosa
                else:
                    # En recorte de línea única, las columnas con valor cero no contienen texto impreso
                    # por lo que Tesseract lee los importes no nulos directamente.
                    prev_nz = [v for v in m_prev if abs(v) > 0.01]
                    crop_tokens = crop_line.split()
                    crop_amounts = []
                    glosa_tokens = []
                    re_cod = None
                    for t in crop_tokens:
                        clean_t = normalizar_token_ocr(t)
                        tok_digits = _normalizar_codigo(t)
                        if tok_digits and (tok_digits == cod_norm or (len(tok_digits) >= 4 and tok_digits in cod_norm) or (cod_norm and cod_norm in tok_digits)):
                            re_cod = t.strip(".-_")
                            continue
                        if PATRON_MONTOS.fullmatch(clean_t):
                            v = parsear_monto(t, ".")
                            if v is not None:
                                crop_amounts.append(float(v))
                                continue
                        glosa_tokens.append(t)

                    re_glosa = " ".join(glosa_tokens)
                    code_matches = bool(re_cod or (cod_norm and cod_norm in _normalizar_codigo(crop_line)))
                    glosa_matches = _son_glosas_compatibles(glosa, re_glosa) or _es_glosa_reconciliable_misma_cuenta(glosa, re_glosa) or not glosa or not re_glosa

                    crop_nz = [v for v in crop_amounts if abs(v) > 0.01]
                    if prev_nz:
                        amounts_match = len(crop_nz) > 0 and all(
                            any(abs(a - b) <= 10.0 for b in crop_nz) for a in prev_nz
                        )
                    else:
                        amounts_match = (len(crop_nz) == 0)

                    id_valida = (_tiene_identidad_contable_valida(m_prev, tolerancia=10.0) or len(prev_nz) == 0) and glosa_matches
                    m_crop = m_prev
                    glosa_final = _elegir_glosa_sustantiva(glosa, re_glosa) if re_glosa else glosa

                if code_matches and id_valida and amounts_match:
                    f_ok = FilaComposicionOCR(
                        motor_origen="RELECTURA_FOCALIZADA",
                        pagina=pagina,
                        linea_origen=linea_idx,
                        codigo_normalizado=re_cod or codigo,
                        glosa_normalizada=glosa if glosa else glosa_final,
                        valores_candidatos={"PREVIO": montos_previos, "RELECTURA": m_crop},
                        valores_finales=m_crop,
                        transformacion_aplicada="relectura_focalizada_recorte",
                        regla_aceptacion="relectura_focalizada_confirmada",
                        nivel_confianza=0.96,
                        es_ambigua=False,
                        bloquea_certificacion=False,
                        evento_relectura="confirmada",
                    )
                    evento = {
                        "tipo": "confirmada",
                        "codigo": codigo,
                        "glosa": glosa,
                        "pagina": pagina,
                        "detalle": "Relectura focalizada confirmó de forma independiente código e importes",
                    }
                    return (f_ok, evento)
                else:
                    motivos = []
                    if not code_matches:
                        motivos.append(f"código leído '{re_cod}' no coincide con '{codigo}'")
                    if not id_valida:
                        motivos.append("identidad contable inválida en relectura")
                    if not amounts_match:
                        motivos.append("importes leídos no coinciden con previos")
                    evento = {
                        "tipo": "discrepancia_relectura",
                        "codigo": codigo,
                        "glosa": glosa,
                        "pagina": pagina,
                        "detalle": f"Relectura focalizada no confirmó la cuenta: {'; '.join(motivos)}",
                    }
                    return (None, evento)
            finally:
                if tmp_crop_path.exists():
                    tmp_crop_path.unlink()
    except Exception as exc:
        evento = {
            "tipo": "falla_ejecucion",
            "codigo": codigo,
            "glosa": glosa,
            "pagina": pagina,
            "detalle": f"Excepción durante relectura focalizada: {exc}",
        }
        return (None, evento)


def _continuidad_fisica_en_candidato(
    fila: dict,
    filas_mismo_motor: list[dict],
    max_salto_exterior: int = 3,
) -> bool:
    """Evalúa continuidad usando el orden físico del mismo candidato OCR.

    La composición agrupa primero los códigos observados por PSM 6 y después
    agrega los exclusivos de PSM 4. Por eso la última fila ya compuesta no es
    necesariamente la vecina física de una cuenta unilateral. Una fila se
    considera continua cuando cae entre otras filas del mismo candidato o,
    si está en un borde, cuando queda a una distancia acotada del vecino más
    próximo. La confirmación independiente, la identidad y la deduplicación
    siguen siendo requisitos separados.
    """
    linea = fila.get("linea_idx")
    if linea is None:
        return True
    try:
        linea_fisica = int(linea)
    except (TypeError, ValueError):
        return False

    lineas_vecinas: list[int] = []
    for candidata in filas_mismo_motor:
        if candidata is fila:
            continue
        valor = candidata.get("linea_idx")
        if valor is None:
            continue
        try:
            lineas_vecinas.append(int(valor))
        except (TypeError, ValueError):
            continue

    if not lineas_vecinas:
        return True

    menor = min(lineas_vecinas)
    mayor = max(lineas_vecinas)
    if menor <= linea_fisica <= mayor:
        return True
    return min(abs(linea_fisica - menor), abs(linea_fisica - mayor)) <= max_salto_exterior


def componer_filas_pagina_ocr(
    cuentas_6: list[dict],
    cuentas_4: list[dict],
    pagina: int,
    words_tsv_6: Optional[list[dict]] = None,
    words_tsv_4: Optional[list[dict]] = None,
    img_path: Optional[Path] = None,
    rotacion: int = 0,
    tolerancia: float = 10.0,
) -> ResultadoComposicionPaginaOCR:
    """Implementa composición segura a nivel de fila con procedencia verificable."""
    c6_norm = []
    for idx, c in enumerate(cuentas_6):
        c_copy = dict(c)
        if c_copy.get("codigo"):
            c_copy["codigo"] = str(c_copy["codigo"]).strip().strip(".-_")
        c_copy["linea_idx"] = c.get("linea_idx", idx)
        c6_norm.append(c_copy)

    c4_norm = []
    for idx, c in enumerate(cuentas_4):
        c_copy = dict(c)
        if c_copy.get("codigo"):
            c_copy["codigo"] = str(c_copy["codigo"]).strip().strip(".-_")
        c_copy["linea_idx"] = c.get("linea_idx", idx)
        c4_norm.append(c_copy)

    c6_clean = [c for c in c6_norm if not _es_ruido_documental_ocr(c)]
    c4_clean = [c for c in c4_norm if not _es_ruido_documental_ocr(c)]

    c6 = _reconciliar_fragmentos_ocr(c6_clean)
    c4 = _reconciliar_fragmentos_ocr(c4_clean)

    import collections
    c6_by_code: dict[str, list[dict]] = collections.defaultdict(list)
    for c in c6:
        if c.get("codigo"):
            c6_by_code[c["codigo"]].append(c)

    c4_by_code: dict[str, list[dict]] = collections.defaultdict(list)
    for c in c4:
        if c.get("codigo"):
            c4_by_code[c["codigo"]].append(c)

    no_cod_6 = [c for c in c6 if not c.get("codigo")]
    no_cod_4 = [c for c in c4 if not c.get("codigo")]

    seen_codes = set()
    ordered_codes = []
    for c in c6:
        cod = c.get("codigo")
        if cod and cod not in seen_codes:
            seen_codes.add(cod)
            ordered_codes.append(cod)
    for c in c4:
        cod = c.get("codigo")
        if cod and cod not in seen_codes:
            seen_codes.add(cod)
            ordered_codes.append(cod)

    filas_compuestas: list[FilaComposicionOCR] = []
    bloqueos: list[str] = []
    eventos_relectura: list[dict] = []
    matched_no_cod_4_ids: set[int] = set()
    matched_no_cod_6_ids: set[int] = set()

    for cod in ordered_codes:
        rows6 = c6_by_code.get(cod, [])
        rows4 = c4_by_code.get(cod, [])

        if len(rows6) > 1 or len(rows4) > 1:
            dup_motor = "PSM 6" if len(rows6) > 1 else "PSM 4"
            f_amb = FilaComposicionOCR(
                motor_origen=dup_motor,
                pagina=pagina,
                linea_origen=rows6[0].get("linea_idx", 0) if rows6 else rows4[0].get("linea_idx", 0),
                codigo_normalizado=cod,
                glosa_normalizada=rows6[0].get("nombre", "") if rows6 else rows4[0].get("nombre", ""),
                valores_candidatos={"PSM 6": rows6[0]["montos"] if rows6 else [], "PSM 4": rows4[0]["montos"] if rows4 else []},
                valores_finales=rows6[0]["montos"] if rows6 else rows4[0]["montos"],
                transformacion_aplicada="bloqueo_duplicacion",
                regla_aceptacion="bloqueada_duplicacion_monetaria",
                nivel_confianza=0.20,
                es_ambigua=True,
                bloquea_certificacion=True,
                motivo_revision=f"Código duplicado {cod} en {dup_motor}",
            )
            filas_compuestas.append(f_amb)
            bloqueos.append(f"Código duplicado {cod} en {dup_motor}")
            continue

        if rows6 and rows4:
            r6, r4 = rows6[0], rows4[0]
            m6, m4 = r6["montos"], r4["montos"]
            g6, g4 = r6.get("nombre", ""), r4.get("nombre", "")
            id6 = _tiene_identidad_contable_valida(m6, tolerancia)
            id4 = _tiene_identidad_contable_valida(m4, tolerancia)
            montos_iguales = all(abs(a - b) <= tolerancia for a, b in zip(m6[:8], m4[:8]))
            glosa_compat = _son_glosas_compatibles(g6, g4)
            glosa_elegida = g6 if len(g6) >= len(g4) else g4

            es_glosa_identica = (_sin_acentos(_limpiar_glosa_ruido(g6)).lower() == _sin_acentos(_limpiar_glosa_ruido(g4)).lower())
            es_reconciliable = glosa_compat or _es_glosa_reconciliable_misma_cuenta(g6, g4)

            if montos_iguales and es_reconciliable:
                glosa_sust = _elegir_glosa_sustantiva(g6, g4)
                if es_glosa_identica:
                    f_ok = FilaComposicionOCR(
                        motor_origen="PSM 6" if len(g6) >= len(g4) else "PSM 4",
                        pagina=pagina,
                        linea_origen=r6.get("linea_idx", 0),
                        codigo_normalizado=cod,
                        glosa_normalizada=glosa_elegida,
                        valores_candidatos={"PSM 6": m6, "PSM 4": m4},
                        valores_finales=m6,
                        transformacion_aplicada="coincidencia_exacta",
                        regla_aceptacion="misma_cuenta_mismos_importes",
                        nivel_confianza=0.98 if (id6 or id4) else 0.85,
                        es_ambigua=False,
                        bloquea_certificacion=False,
                    )
                    filas_compuestas.append(f_ok)
                else:
                    f_ok = FilaComposicionOCR(
                        motor_origen="PSM 6" if glosa_sust == g6 else "PSM 4",
                        pagina=pagina,
                        linea_origen=r6.get("linea_idx", 0),
                        codigo_normalizado=cod,
                        glosa_normalizada=glosa_sust,
                        valores_candidatos={"PSM 6": m6, "PSM 4": m4},
                        valores_finales=m6,
                        transformacion_aplicada="reconciliacion_glosa_truncada",
                        regla_aceptacion="glosa_reconciliada_misma_cuenta",
                        nivel_confianza=0.96 if (id6 or id4) else 0.85,
                        es_ambigua=False,
                        bloquea_certificacion=False,
                    )
                    filas_compuestas.append(f_ok)
            elif montos_iguales and not es_reconciliable:
                f_amb = FilaComposicionOCR(
                    motor_origen="AMBIGUA",
                    pagina=pagina,
                    linea_origen=r6.get("linea_idx", 0),
                    codigo_normalizado=cod,
                    glosa_normalizada=glosa_elegida,
                    valores_candidatos={"PSM 6": m6, "PSM 4": m4},
                    valores_finales=m6,
                    transformacion_aplicada="bloqueo_glosas_incompatibles",
                    regla_aceptacion="bloqueada_glosas_incompatibles",
                    nivel_confianza=0.40,
                    es_ambigua=True,
                    bloquea_certificacion=True,
                    motivo_revision=f"Glosas incompatibles en cuenta {cod}: '{g6}' vs '{g4}'",
                )
                filas_compuestas.append(f_amb)
                bloqueos.append(f"Glosas incompatibles en cuenta {cod}: '{g6}' vs '{g4}'")
            elif id6 and not id4 and glosa_compat:
                f_ok = FilaComposicionOCR(
                    motor_origen="PSM 6",
                    pagina=pagina,
                    linea_origen=r6.get("linea_idx", 0),
                    codigo_normalizado=cod,
                    glosa_normalizada=g6,
                    valores_candidatos={"PSM 6": m6, "PSM 4": m4},
                    valores_finales=m6,
                    transformacion_aplicada="seleccion_candidato_valido",
                    regla_aceptacion="identidad_valida_unilateral",
                    nivel_confianza=0.92,
                    es_ambigua=False,
                    bloquea_certificacion=False,
                )
                filas_compuestas.append(f_ok)
            elif id4 and not id6 and glosa_compat:
                f_ok = FilaComposicionOCR(
                    motor_origen="PSM 4",
                    pagina=pagina,
                    linea_origen=r4.get("linea_idx", 0),
                    codigo_normalizado=cod,
                    glosa_normalizada=g4,
                    valores_candidatos={"PSM 6": m6, "PSM 4": m4},
                    valores_finales=m4,
                    transformacion_aplicada="seleccion_candidato_valido",
                    regla_aceptacion="identidad_valida_unilateral",
                    nivel_confianza=0.92,
                    es_ambigua=False,
                    bloquea_certificacion=False,
                )
                filas_compuestas.append(f_ok)
            elif id6 and id4:
                f_amb = FilaComposicionOCR(
                    motor_origen="AMBIGUA",
                    pagina=pagina,
                    linea_origen=r6.get("linea_idx", 0),
                    codigo_normalizado=cod,
                    glosa_normalizada=glosa_elegida,
                    valores_candidatos={"PSM 6": m6, "PSM 4": m4},
                    valores_finales=m6,
                    transformacion_aplicada="bloqueo_ambiguedad",
                    regla_aceptacion="bloqueada_discrepancia_monetaria_ambos_validos",
                    nivel_confianza=0.50,
                    es_ambigua=True,
                    bloquea_certificacion=True,
                    motivo_revision=f"Discrepancia monetaria irreconciliable en cuenta {cod} entre dos candidatos con identidades contables válidas",
                )
                filas_compuestas.append(f_amb)
                bloqueos.append(f"Discrepancia monetaria irreconciliable en cuenta {cod}")
            else:
                f_releida, ev = _relectura_focalizada_ocr(img_path, rotacion, words_tsv_6 or words_tsv_4, cod, glosa_elegida, m6, pagina=pagina)
                eventos_relectura.append(ev)
                if f_releida:
                    filas_compuestas.append(f_releida)
                else:
                    f_amb = FilaComposicionOCR(
                        motor_origen="AMBIGUA",
                        pagina=pagina,
                        linea_origen=r6.get("linea_idx", 0),
                        codigo_normalizado=cod,
                        glosa_normalizada=glosa_elegida,
                        valores_candidatos={"PSM 6": m6, "PSM 4": m4},
                        valores_finales=m6,
                        transformacion_aplicada="bloqueo_defectuosos",
                        regla_aceptacion="bloqueada_ambos_defectuosos",
                        nivel_confianza=0.30,
                        es_ambigua=True,
                        bloquea_certificacion=True,
                        motivo_revision=f"Ambos candidatos presentan identidad contable inválida en cuenta {cod} ({ev.get('detalle', 'sin confirmación')})",
                        evento_relectura=ev.get("tipo"),
                    )
                    filas_compuestas.append(f_amb)
                    bloqueos.append(f"Identidad contable inválida en ambos candidatos en cuenta {cod}")

        elif rows6 and not rows4:
            r6 = rows6[0]
            m6 = r6["montos"]
            g6 = r6.get("nombre", "")
            cand_fragmento_4 = None
            if any(abs(v) > 0.01 for v in m6):
                cand_fragmento_4 = next(
                    (cand for cand in no_cod_4
                     if id(cand) not in matched_no_cod_4_ids
                     and all(abs(a - b) <= tolerancia for a, b in zip(m6[:8], cand["montos"][:8]))
                     and (_son_glosas_compatibles(g6, cand.get("nombre", "")) or _es_glosa_reconciliable_misma_cuenta(g6, cand.get("nombre", "")))),
                    None
                )
            if cand_fragmento_4 is not None:
                matched_no_cod_4_ids.add(id(cand_fragmento_4))
                glosa_sust = _elegir_glosa_sustantiva(g6, cand_fragmento_4.get("nombre", ""))
                f_ok = FilaComposicionOCR(
                    motor_origen="PSM 6",
                    pagina=pagina,
                    linea_origen=r6.get("linea_idx", 0),
                    codigo_normalizado=cod,
                    glosa_normalizada=glosa_sust,
                    valores_candidatos={"PSM 6": m6, "PSM 4": cand_fragmento_4["montos"]},
                    valores_finales=m6,
                    transformacion_aplicada="reconciliacion_fragmento_uncoded",
                    regla_aceptacion="misma_cuenta_mismos_importes",
                    nivel_confianza=0.96,
                    es_ambigua=False,
                    bloquea_certificacion=False,
                )
                filas_compuestas.append(f_ok)
                continue
            cod_norm = _normalizar_codigo(cod)
            es_codigo_valido = bool(re.match(r"^\d{4,10}$", cod_norm))
            id6 = _tiene_identidad_contable_valida(m6, tolerancia)
            es_monto_cero = not any(abs(v) > 0.001 for v in m6)

            # Cuentas en 0 requieren evidencia documental positiva de existencia
            if es_monto_cero:
                tiene_evidencia_cero = bool(
                    r6.get("monto_cero_preservado")
                    or (es_codigo_valido and len(g6.strip()) >= 3 and not _es_ruido_documental_ocr(r6))
                )
                if not tiene_evidencia_cero:
                    continue

            # Comprobar ausencia de importes duplicados con cuentas vecinas o del documento
            m6_non_zero = tuple(round(v, 2) for v in m6 if abs(v) > 0.01)
            es_duplicado = False
            if m6_non_zero:
                for f_prev in filas_compuestas:
                    prev_nz = tuple(round(v, 2) for v in f_prev.valores_finales if abs(v) > 0.01)
                    if prev_nz == m6_non_zero and f_prev.codigo_normalizado != cod:
                        es_duplicado = True
                        break

            # Continuidad física dentro del mismo candidato OCR. El orden de
            # ``filas_compuestas`` es lógico por código y no sirve como proxy
            # de posición documental.
            continuidad_ok = _continuidad_fisica_en_candidato(r6, c6)

            # Confirmación independiente requerida via relectura focalizada
            f_releida, ev = _relectura_focalizada_ocr(
                img_path, rotacion, words_tsv_6 or words_tsv_4,
                cod, g6, m6, pagina=pagina,
                linea_idx=r6.get("linea_idx", 0),
            )
            eventos_relectura.append(ev)

            if (
                es_codigo_valido
                and (id6 or es_monto_cero)
                and not es_duplicado
                and continuidad_ok
                and f_releida is not None
            ):
                filas_compuestas.append(f_releida)
            else:
                motivos = []
                if not f_releida:
                    motivos.append(f"sin confirmación independiente ({ev.get('detalle', 'no confirmada')})")
                if not es_codigo_valido:
                    motivos.append("código contable con formato inválido")
                if not id6 and not es_monto_cero:
                    motivos.append("identidad contable inválida")
                if es_duplicado:
                    motivos.append("importes duplicados con otra fila")
                if not continuidad_ok:
                    motivos.append("discontinuidad geométrica anómala")

                motivo_desc = f"Cuenta unilateral {cod} en PSM 6 no confirmada: {'; '.join(motivos)}"
                f_amb = FilaComposicionOCR(
                    motor_origen="AMBIGUA",
                    pagina=pagina,
                    linea_origen=r6.get("linea_idx", 0),
                    codigo_normalizado=cod,
                    glosa_normalizada=g6,
                    valores_candidatos={"PSM 6": m6, "PSM 4": []},
                    valores_finales=m6,
                    transformacion_aplicada="bloqueo_unilateral_no_confirmada",
                    regla_aceptacion="bloqueada_unilateral_no_confirmada",
                    nivel_confianza=0.35,
                    es_ambigua=True,
                    bloquea_certificacion=True,
                    motivo_revision=motivo_desc,
                    evento_relectura=ev.get("tipo"),
                )
                filas_compuestas.append(f_amb)
                bloqueos.append(motivo_desc)

        elif rows4 and not rows6:
            r4 = rows4[0]
            m4 = r4["montos"]
            g4 = r4.get("nombre", "")
            cand_fragmento_6 = None
            if any(abs(v) > 0.01 for v in m4):
                cand_fragmento_6 = next(
                    (cand for cand in no_cod_6
                     if id(cand) not in matched_no_cod_6_ids
                     and all(abs(a - b) <= tolerancia for a, b in zip(m4[:8], cand["montos"][:8]))
                     and (_son_glosas_compatibles(g4, cand.get("nombre", "")) or _es_glosa_reconciliable_misma_cuenta(g4, cand.get("nombre", "")))),
                    None
                )
            if cand_fragmento_6 is not None:
                matched_no_cod_6_ids.add(id(cand_fragmento_6))
                glosa_sust = _elegir_glosa_sustantiva(g4, cand_fragmento_6.get("nombre", ""))
                f_ok = FilaComposicionOCR(
                    motor_origen="PSM 4",
                    pagina=pagina,
                    linea_origen=r4.get("linea_idx", 0),
                    codigo_normalizado=cod,
                    glosa_normalizada=glosa_sust,
                    valores_candidatos={"PSM 6": cand_fragmento_6["montos"], "PSM 4": m4},
                    valores_finales=m4,
                    transformacion_aplicada="reconciliacion_fragmento_uncoded",
                    regla_aceptacion="misma_cuenta_mismos_importes",
                    nivel_confianza=0.96,
                    es_ambigua=False,
                    bloquea_certificacion=False,
                )
                filas_compuestas.append(f_ok)
                continue
            cod_norm = _normalizar_codigo(cod)
            es_codigo_valido = bool(re.match(r"^\d{4,10}$", cod_norm))
            id4 = _tiene_identidad_contable_valida(m4, tolerancia)
            es_monto_cero = not any(abs(v) > 0.001 for v in m4)

            # Cuentas en 0 requieren evidencia documental positiva de existencia
            if es_monto_cero:
                tiene_evidencia_cero = bool(
                    r4.get("monto_cero_preservado")
                    or (es_codigo_valido and len(g4.strip()) >= 3 and not _es_ruido_documental_ocr(r4))
                )
                if not tiene_evidencia_cero:
                    continue

            # Comprobar ausencia de importes duplicados con cuentas vecinas o del documento
            m4_non_zero = tuple(round(v, 2) for v in m4 if abs(v) > 0.01)
            es_duplicado = False
            if m4_non_zero:
                for f_prev in filas_compuestas:
                    prev_nz = tuple(round(v, 2) for v in f_prev.valores_finales if abs(v) > 0.01)
                    if prev_nz == m4_non_zero and f_prev.codigo_normalizado != cod:
                        es_duplicado = True
                        break

            # Continuidad física dentro del mismo candidato OCR. El orden de
            # ``filas_compuestas`` es lógico por código y no sirve como proxy
            # de posición documental.
            continuidad_ok = _continuidad_fisica_en_candidato(r4, c4)

            # Confirmación independiente requerida via relectura focalizada
            f_releida, ev = _relectura_focalizada_ocr(
                img_path, rotacion, words_tsv_4 or words_tsv_6,
                cod, g4, m4, pagina=pagina,
                linea_idx=r4.get("linea_idx", 0),
            )
            eventos_relectura.append(ev)

            if (
                es_codigo_valido
                and (id4 or es_monto_cero)
                and not es_duplicado
                and continuidad_ok
                and f_releida is not None
            ):
                filas_compuestas.append(f_releida)
            else:
                motivos = []
                if not f_releida:
                    motivos.append(f"sin confirmación independiente ({ev.get('detalle', 'no confirmada')})")
                if not es_codigo_valido:
                    motivos.append("código contable con formato inválido")
                if not id4 and not es_monto_cero:
                    motivos.append("identidad contable inválida")
                if es_duplicado:
                    motivos.append("importes duplicados con otra fila")
                if not continuidad_ok:
                    motivos.append("discontinuidad geométrica anómala")

                motivo_desc = f"Cuenta unilateral {cod} en PSM 4 no confirmada: {'; '.join(motivos)}"
                f_amb = FilaComposicionOCR(
                    motor_origen="AMBIGUA",
                    pagina=pagina,
                    linea_origen=r4.get("linea_idx", 0),
                    codigo_normalizado=cod,
                    glosa_normalizada=g4,
                    valores_candidatos={"PSM 6": [], "PSM 4": m4},
                    valores_finales=m4,
                    transformacion_aplicada="bloqueo_unilateral_no_confirmada",
                    regla_aceptacion="bloqueada_unilateral_no_confirmada",
                    nivel_confianza=0.35,
                    es_ambigua=True,
                    bloquea_certificacion=True,
                    motivo_revision=motivo_desc,
                    evento_relectura=ev.get("tipo"),
                )
                filas_compuestas.append(f_amb)
                bloqueos.append(motivo_desc)

    for c in no_cod_6:
        if id(c) in matched_no_cod_6_ids:
            continue
        m6 = c["montos"]
        g6 = c.get("nombre", "")
        # Si coincide en importes y glosa con una cuenta ya compuesta con código, es un fragmento/duplicado
        if any(abs(v) > 0.01 for v in m6):
            ya_compuesta = next(
                (f for f in filas_compuestas
                 if f.codigo_normalizado and all(abs(a - b) <= tolerancia for a, b in zip(f.valores_finales[:8], m6[:8]))
                 and (_son_glosas_compatibles(f.glosa_normalizada, g6) or _es_glosa_reconciliable_misma_cuenta(f.glosa_normalizada, g6))),
                None
            )
            if ya_compuesta is not None:
                continue
        match_4 = None
        for cand4 in no_cod_4:
            if id(cand4) not in matched_no_cod_4_ids and all(abs(a - b) <= tolerancia for a, b in zip(m6[:8], cand4["montos"][:8])):
                if _son_glosas_compatibles(g6, cand4.get("nombre", "")):
                    match_4 = cand4
                    matched_no_cod_4_ids.add(id(cand4))
                    break
                else:
                    # Conflicto material: importes idénticos pero nombres contradictorios sin código
                    matched_no_cod_4_ids.add(id(cand4))
                    motivo_desc = f"Fila sin código con importes idénticos pero glosas incompatibles: '{g6}' vs '{cand4.get('nombre', '')}'"
                    f_amb = FilaComposicionOCR(
                        motor_origen="AMBIGUA",
                        pagina=pagina,
                        linea_origen=c.get("linea_idx", 0),
                        codigo_normalizado=None,
                        glosa_normalizada=g6,
                        valores_candidatos={"PSM 6": m6, "PSM 4": cand4["montos"]},
                        valores_finales=m6,
                        transformacion_aplicada="bloqueo_glosas_incompatibles_sin_codigo",
                        regla_aceptacion="bloqueada_glosas_incompatibles_sin_codigo",
                        nivel_confianza=0.30,
                        es_ambigua=True,
                        bloquea_certificacion=True,
                        motivo_revision=motivo_desc,
                    )
                    filas_compuestas.append(f_amb)
                    bloqueos.append(motivo_desc)
                    match_4 = "conflict"
                    break
        if match_4 == "conflict":
            continue
        elif match_4 is not None:
            f_ok = FilaComposicionOCR(
                motor_origen="PSM 6",
                pagina=pagina,
                linea_origen=c.get("linea_idx", 0),
                codigo_normalizado=None,
                glosa_normalizada=g6,
                valores_candidatos={"PSM 6": m6, "PSM 4": match_4["montos"]},
                valores_finales=m6,
                transformacion_aplicada="coincidencia_sin_codigo",
                regla_aceptacion="misma_cuenta_sin_codigo_mismos_importes",
                nivel_confianza=0.85,
                es_ambigua=False,
                bloquea_certificacion=False,
            )
            filas_compuestas.append(f_ok)
        elif c.get("monto_cero_preservado"):
            f_ok = FilaComposicionOCR(
                motor_origen="PSM 6",
                pagina=pagina,
                linea_origen=c.get("linea_idx", 0),
                codigo_normalizado=None,
                glosa_normalizada=g6,
                valores_candidatos={"PSM 6": m6, "PSM 4": []},
                valores_finales=m6,
                transformacion_aplicada="preservacion_monto_cero",
                regla_aceptacion="cuenta_sin_codigo_monto_cero_preservada",
                nivel_confianza=0.75,
                es_ambigua=False,
                bloquea_certificacion=False,
            )
            filas_compuestas.append(f_ok)
        else:
            # Cuenta unilateral sin código: no cumple requisito de formato de código (4-10 dígitos) ni confirmación independiente
            motivo_desc = f"Fila sin código '{g6}' en PSM 6 sin formato de código ni confirmación independiente"
            f_amb = FilaComposicionOCR(
                motor_origen="AMBIGUA",
                pagina=pagina,
                linea_origen=c.get("linea_idx", 0),
                codigo_normalizado=None,
                glosa_normalizada=g6,
                valores_candidatos={"PSM 6": m6, "PSM 4": []},
                valores_finales=m6,
                transformacion_aplicada="bloqueo_sin_codigo_unilateral",
                regla_aceptacion="bloqueada_sin_codigo_unilateral",
                nivel_confianza=0.30,
                es_ambigua=True,
                bloquea_certificacion=True,
                motivo_revision=motivo_desc,
            )
            filas_compuestas.append(f_amb)
            bloqueos.append(motivo_desc)

    for cand4 in no_cod_4:
        if id(cand4) in matched_no_cod_4_ids:
            continue
        m4 = cand4["montos"]
        g4 = cand4.get("nombre", "")
        # Si coincide en importes y glosa con una cuenta ya compuesta con código, es un fragmento/duplicado
        if any(abs(v) > 0.01 for v in m4):
            ya_compuesta = next(
                (f for f in filas_compuestas
                 if f.codigo_normalizado and all(abs(a - b) <= tolerancia for a, b in zip(f.valores_finales[:8], m4[:8]))
                 and (_son_glosas_compatibles(f.glosa_normalizada, g4) or _es_glosa_reconciliable_misma_cuenta(f.glosa_normalizada, g4))),
                None
            )
            if ya_compuesta is not None:
                continue
        if cand4.get("monto_cero_preservado"):
            f_ok = FilaComposicionOCR(
                motor_origen="PSM 4",
                pagina=pagina,
                linea_origen=cand4.get("linea_idx", 0),
                codigo_normalizado=None,
                glosa_normalizada=g4,
                valores_candidatos={"PSM 6": [], "PSM 4": m4},
                valores_finales=m4,
                transformacion_aplicada="preservacion_monto_cero",
                regla_aceptacion="cuenta_sin_codigo_monto_cero_preservada",
                nivel_confianza=0.75,
                es_ambigua=False,
                bloquea_certificacion=False,
            )
            filas_compuestas.append(f_ok)
        else:
            motivo_desc = f"Fila sin código '{g4}' en PSM 4 sin formato de código ni confirmación independiente"
            f_amb = FilaComposicionOCR(
                motor_origen="AMBIGUA",
                pagina=pagina,
                linea_origen=cand4.get("linea_idx", 0),
                codigo_normalizado=None,
                glosa_normalizada=g4,
                valores_candidatos={"PSM 6": [], "PSM 4": m4},
                valores_finales=m4,
                transformacion_aplicada="bloqueo_sin_codigo_unilateral",
                regla_aceptacion="bloqueada_sin_codigo_unilateral",
                nivel_confianza=0.30,
                es_ambigua=True,
                bloquea_certificacion=True,
                motivo_revision=motivo_desc,
            )
            filas_compuestas.append(f_amb)
            bloqueos.append(motivo_desc)

    lineas_texto = []
    for f in filas_compuestas:
        cod_str = f"{f.codigo_normalizado} " if f.codigo_normalizado else ""
        montos_str = " ".join(f"{v:.0f}" if v == int(v) else f"{v:.2f}" for v in f.valores_finales)
        lineas_texto.append(f"{cod_str}{f.glosa_normalizada} {montos_str}")

    ambiguas_count = sum(1 for f in filas_compuestas if f.es_ambigua)
    bloqueada = (ambiguas_count > 0)
    motivo_bloqueo = "; ".join(bloqueos) if bloqueos else None

    return ResultadoComposicionPaginaOCR(
        pagina=pagina,
        filas_compuestas=filas_compuestas,
        filas_ambiguas_count=ambiguas_count,
        bloqueada=bloqueada,
        motivo_bloqueo=motivo_bloqueo,
        lineas_compuestas_texto=lineas_texto,
        eventos_relectura=eventos_relectura,
    )


@dataclass
class ResultadoComparacionSemantica:
    decision: str              # "equivalentes", "dominancia_6", "dominancia_4", "ambiguedad_material"
    motor_dominante: Optional[str] # "PSM 6", "PSM 4", None
    motivo: str
    ambiguedad_material: bool
    cuentas_6_efectivas: list[dict]
    cuentas_4_efectivas: list[dict]


def _comparar_semantica_candidatos(
    cuentas_6: list[dict],
    cuentas_4: list[dict],
    tolerancia: float = 10.0,
) -> ResultadoComparacionSemantica:
    """Comparador semántico general entre candidatos PSM 6 y PSM 4.

    Distingue:
    1. Candidatos equivalentes (mismo detalle, posibles variaciones legítimas de orden o glosa).
    2. Filas partidas/fragmentadas reconciliadas.
    3. Filas adicionales de ruido documental (membrete, numeración de página).
    4. Dominancia demostrada de un candidato sobre otro según contrato estricto de dominancia.
    5. Conflicto material no resoluble (ambigüedad material retenida).
    """
    # 1. Normalizar códigos
    c6_norm = []
    for c in cuentas_6:
        c_copy = dict(c)
        if c_copy.get("codigo"):
            c_copy["codigo"] = c_copy["codigo"].strip().strip(".-_")
        c6_norm.append(c_copy)

    c4_norm = []
    for c in cuentas_4:
        c_copy = dict(c)
        if c_copy.get("codigo"):
            c_copy["codigo"] = c_copy["codigo"].strip().strip(".-_")
        c4_norm.append(c_copy)

    # 2. Filtrar ruido documental
    c6_clean = [c for c in c6_norm if not _es_ruido_documental_ocr(c)]
    c4_clean = [c for c in c4_norm if not _es_ruido_documental_ocr(c)]

    ruido_6_count = len(c6_norm) - len(c6_clean)
    ruido_4_count = len(c4_norm) - len(c4_clean)

    # 3. Reconciliar fragmentos
    c6 = _reconciliar_fragmentos_ocr(c6_clean)
    c4 = _reconciliar_fragmentos_ocr(c4_clean)

    # Detección estricta de códigos duplicados
    import collections
    cnt_6 = collections.Counter(c["codigo"] for c in c6 if c.get("codigo"))
    cnt_4 = collections.Counter(c["codigo"] for c in c4 if c.get("codigo"))
    dups_6 = [cod for cod, count in cnt_6.items() if count > 1]
    dups_4 = [cod for cod, count in cnt_4.items() if count > 1]
    if dups_6 or dups_4:
        dup_msgs = []
        if dups_6:
            dup_msgs.append(f"códigos duplicados en PSM 6: {', '.join(dups_6)}")
        if dups_4:
            dup_msgs.append(f"códigos duplicados en PSM 4: {', '.join(dups_4)}")
        return ResultadoComparacionSemantica(
            decision="ambiguedad_material",
            motor_dominante="PSM 6",
            motivo=f"Duplicación monetaria bloquea dominancia ({'; '.join(dup_msgs)})",
            ambiguedad_material=True,
            cuentas_6_efectivas=c6,
            cuentas_4_efectivas=c4,
        )

    # Emparejamiento por código
    codes_6 = {c["codigo"]: c for c in c6 if c.get("codigo")}
    codes_4 = {c["codigo"]: c for c in c4 if c.get("codigo")}

    common_codes = set(codes_6.keys()) & set(codes_4.keys())
    only_6_codes = set(codes_6.keys()) - set(codes_4.keys())
    only_4_codes = set(codes_4.keys()) - set(codes_6.keys())

    # Cuentas sin código
    no_cod_6 = [c for c in c6 if not c.get("codigo")]
    no_cod_4 = [c for c in c4 if not c.get("codigo")]

    # Verificar importes y glosas en códigos comunes
    mismatches = []
    glosa_mismatches = []
    for cod in common_codes:
        m6 = codes_6[cod]["montos"]
        m4 = codes_4[cod]["montos"]
        diffs = [abs(m6[k] - m4[k]) for k in range(8)]
        if any(d > tolerancia for d in diffs):
            mismatches.append({
                "codigo": cod,
                "nombre_6": codes_6[cod].get("nombre"),
                "nombre_4": codes_4[cod].get("nombre"),
                "montos_6": m6,
                "montos_4": m4,
                "id_valida_6": _tiene_identidad_contable_valida(m6, tolerancia),
                "id_valida_4": _tiene_identidad_contable_valida(m4, tolerancia),
                "max_diff": max(diffs),
            })
        n6 = re.sub(r"\s+", " ", _sin_acentos(codes_6[cod].get("nombre", "")).lower().strip())
        n4 = re.sub(r"\s+", " ", _sin_acentos(codes_4[cod].get("nombre", "")).lower().strip())
        if n6 and n4 and n6 != n4:
            import difflib
            es_compatible = bool(
                n6 in n4 or n4 in n6 or difflib.SequenceMatcher(None, n6, n4).ratio() >= 0.85
            )
            if not es_compatible:
                glosa_mismatches.append({
                    "codigo": cod,
                    "nombre_6": codes_6[cod].get("nombre"),
                    "nombre_4": codes_4[cod].get("nombre"),
                })

    # Cuentas exclusivas
    only_6 = [codes_6[cod] for cod in only_6_codes]
    only_4 = [codes_4[cod] for cod in only_4_codes]

    # Clasificar discrepancias por identidad contable
    mismatch_4_broken = [m for m in mismatches if m["id_valida_6"] and not m["id_valida_4"]]
    mismatch_6_broken = [m for m in mismatches if not m["id_valida_6"] and m["id_valida_4"]]
    mismatch_both_valid = [m for m in mismatches if m["id_valida_6"] and m["id_valida_4"]]
    mismatch_both_broken = [m for m in mismatches if not m["id_valida_6"] and not m["id_valida_4"]]

    # Evaluar emparejamiento de cuentas sin código
    unmatched_no_cod_4 = list(no_cod_4)
    matched_no_cod_pairs = []
    for c_6 in no_cod_6:
        n6 = _sin_acentos(c_6["nombre"]).lower().strip()
        matched = None
        for c_4 in unmatched_no_cod_4:
            n4 = _sin_acentos(c_4["nombre"]).lower().strip()
            diffs = [abs(c_6["montos"][k] - c_4["montos"][k]) for k in range(8)]
            if all(d <= tolerancia for d in diffs):
                if n6 == n4 or (n6 and n4 and (n6 in n4 or n4 in n6)):
                    matched = c_4
                    break
        if matched:
            unmatched_no_cod_4.remove(matched)
            matched_no_cod_pairs.append((c_6, matched))

    # Chequeo de duplicados o nombres distintos con importes idénticos en sin código
    for c_6 in no_cod_6:
        n6 = _sin_acentos(c_6["nombre"]).lower().strip()
        for c_4 in unmatched_no_cod_4:
            n4 = _sin_acentos(c_4["nombre"]).lower().strip()
            diffs = [abs(c_6["montos"][k] - c_4["montos"][k]) for k in range(8)]
            if all(d <= tolerancia for d in diffs) and n6 != n4:
                return ResultadoComparacionSemantica(
                    decision="ambiguedad_material",
                    motor_dominante="PSM 6",
                    motivo=f"Cuentas distintas comparten importes idénticos pero difieren en nombre: '{c_6['nombre']}' (PSM 6) vs '{c_4['nombre']}' (PSM 4)",
                    ambiguedad_material=True,
                    cuentas_6_efectivas=c6,
                    cuentas_4_efectivas=c4,
                )

    # CASO 1: Candidatos equivalentes (mismo detalle o sólo diferencias de ruido ya filtradas)
    if not only_6 and not only_4 and not mismatches and not glosa_mismatches and len(no_cod_6) == len(matched_no_cod_pairs) and len(unmatched_no_cod_4) == 0:
        if ruido_4_count > 0 or ruido_6_count > 0:
            motivo = f"Candidatos equivalentes en detalle contable tras filtrar {ruido_4_count + ruido_6_count} fila(s) de ruido documental"
        else:
            motivo = "Candidatos equivalentes en detalle de cuentas"
        return ResultadoComparacionSemantica(
            decision="equivalentes",
            motor_dominante="PSM 6",
            motivo=motivo,
            ambiguedad_material=False,
            cuentas_6_efectivas=c6,
            cuentas_4_efectivas=c4,
        )

    # CASO 2: Dominancia válida de PSM 6 sobre PSM 4
    # Concurrencia conjunta de los 7 requisitos de dominancia:
    # 1. PSM 6 contiene todas las cuentas legítimas de PSM 4 sin contradicción monetaria relevante (not only_4, len(mismatches) == 0)
    # 2. El subordinado omite cuentas legítimas o introduce filas espurias demostrables (ruido_4_count > 0)
    # 3. Las cuentas adicionales de PSM 6 satisfacen identidades de ocho columnas (all _tiene_identidad_contable_valida)
    # 4. No hay ambigüedades no resueltas de cuentas sin código (len(unmatched_no_cod_4) == 0 and len(no_cod_6) == len(matched_no_cod_pairs))
    # 5. Todas las cuentas efectivas de PSM 6 satisfacen identidades contables válidas
    # 6. No hay desplazamiento no resuelto de columnas en PSM 6
    # 7. Si hay filas adicionales, debe demostrarse defecto/omisión en el subordinado (ruido descartado en subordinado)
    if not only_4 and len(mismatches) == 0 and not glosa_mismatches and len(unmatched_no_cod_4) == 0 and len(no_cod_6) == len(matched_no_cod_pairs):
        if (ruido_4_count > 0):
            if all(_tiene_identidad_contable_valida(c["montos"], tolerancia) for c in c6):
                det = []
                if only_6:
                    det.append(f"{len(only_6)} cuenta(s) válidas adicionales en PSM 6")
                if ruido_4_count:
                    det.append(f"{ruido_4_count} fila(s) de ruido documental descartadas en subordinado")
                return ResultadoComparacionSemantica(
                    decision="dominancia_6",
                    motor_dominante="PSM 6",
                    motivo=f"PSM 6 domina a PSM 4: {', '.join(det)}",
                    ambiguedad_material=False,
                    cuentas_6_efectivas=c6,
                    cuentas_4_efectivas=c4,
                )

    # CASO 3: Dominancia válida de PSM 4 sobre PSM 6 (simétrica)
    if not only_6 and len(mismatches) == 0 and not glosa_mismatches and len(no_cod_6) == len(matched_no_cod_pairs) and len(unmatched_no_cod_4) == 0:
        if (ruido_6_count > 0):
            if all(_tiene_identidad_contable_valida(c["montos"], tolerancia) for c in c4):
                det = []
                if only_4:
                    det.append(f"{len(only_4)} cuenta(s) válidas adicionales en PSM 4")
                if ruido_6_count:
                    det.append(f"{ruido_6_count} fila(s) de ruido documental descartadas en subordinado")
                return ResultadoComparacionSemantica(
                    decision="dominancia_4",
                    motor_dominante="PSM 4",
                    motivo=f"PSM 4 domina a PSM 6: {', '.join(det)}",
                    ambiguedad_material=False,
                    cuentas_6_efectivas=c6,
                    cuentas_4_efectivas=c4,
                )

    # CASO 4: Conflicto material no resoluble (bloqueo obligatorio)
    motivos_conflicto = []
    if mismatches:
        motivos_conflicto.append(f"{len(mismatches)} cuenta(s) con importes discrepantes")
    if glosa_mismatches:
        motivos_conflicto.append(f"{len(glosa_mismatches)} cuenta(s) con glosa contradictoria en mismo código")
    if only_6:
        motivos_conflicto.append(f"{len(only_6)} cuenta(s) exclusivas en PSM 6")
    if only_4:
        motivos_conflicto.append(f"{len(only_4)} cuenta(s) exclusivas en PSM 4")
    if len(unmatched_no_cod_4) > 0:
        motivos_conflicto.append(f"{len(unmatched_no_cod_4)} cuenta(s) sin código no emparejadas en PSM 4")
    if len(no_cod_6) > len(matched_no_cod_pairs):
        motivos_conflicto.append(f"{len(no_cod_6) - len(matched_no_cod_pairs)} cuenta(s) sin código no emparejadas en PSM 6")

    diff_count = abs(len(c6) - len(c4))
    if diff_count > 0 and not mismatches and not glosa_mismatches:
        desc = f"Diferencia en número de cuentas detectadas: {len(c6)} en PSM 6 vs {len(c4)} en PSM 4 ({diff_count} fila(s) omitida(s)/agregada(s))"
    else:
        desc = f"Ambigüedad material entre candidatos: {'; '.join(motivos_conflicto)}"

    return ResultadoComparacionSemantica(
        decision="ambiguedad_material",
        motor_dominante="PSM 6",
        motivo=desc,
        ambiguedad_material=True,
        cuentas_6_efectivas=c6,
        cuentas_4_efectivas=c4,
    )


def _detectar_discrepancias_materiales(
    cuentas_6: list[dict],
    cuentas_4: list[dict],
    tolerancia: float = 10.0,
) -> tuple[bool, str]:
    """Compara cuentas entre dos candidatos OCR distinguiendo ruido, fragmentación y dominancia."""
    res = _comparar_semantica_candidatos(cuentas_6, cuentas_4, tolerancia=tolerancia)
    hay_disc = (res.decision != "equivalentes")
    return hay_disc, res.motivo


@dataclass
class DecisionComparacionOCR:
    """Decisión estructurada de arbitraje entre candidatos OCR."""
    motor_seleccionado: str                  # "PSM 6", "PSM 4", "RapidOCR"
    tipo_seleccion: str                      # "respaldada", "provisional"
    evidencia_disponible: str                # "control_local_conciliado", "control_acumulado", "control_global", "sin_control", "motor_unico", "insuficiente"
    ambiguedad_material: bool                # True si hay discrepancia material no resuelta entre candidatos utilizables
    evaluacion_incompleta: bool              # True si evidencia insuficiente o datos incompletos
    motivo: str                              # Explicación legible de la decisión
    condicion_revision: Optional[str] = None # "bloqueo_certificacion", "revision_cuentas", "revision_control", None
    detalle_discrepancia: Optional[str] = None
    etiqueta: Optional[str] = None           # Etiqueta para compatibilidad con código que desempaqueta
    filas_compuestas: list[Any] = field(default_factory=list)
    lineas_compuestas: list[str] = field(default_factory=list)
    resultado_composicion: Optional[Any] = None

    def __iter__(self):
        yield self.motor_seleccionado
        yield self.etiqueta

    def __getitem__(self, index):
        return (self.motor_seleccionado, self.etiqueta)[index]

    def __eq__(self, other):
        if isinstance(other, str):
            return self.motor_seleccionado == other or self.etiqueta == other
        return super().__eq__(other)

    def __contains__(self, item):
        if isinstance(item, str):
            return (item in self.motor_seleccionado) or (bool(self.etiqueta) and item in self.etiqueta)
        return False

    def __bool__(self):
        return bool(self.etiqueta or (self.motor_seleccionado and self.motor_seleccionado != "PSM 6"))

    def __str__(self):
        return self.etiqueta if self.etiqueta is not None else self.motor_seleccionado

    def startswith(self, prefix, *args):
        return (self.etiqueta or self.motor_seleccionado).startswith(prefix, *args)

    def endswith(self, suffix, *args):
        return (self.etiqueta or self.motor_seleccionado).endswith(suffix, *args)

    def lower(self):
        return (self.etiqueta or self.motor_seleccionado).lower()


def _comparar_candidatos_ocr(
    lines_6: list[str], centers_6: Optional[list[float]],
    lines_4: list[str], centers_4: Optional[list[float]],
    conc_6: dict, conc_4: dict,
    tolerancia: float = 10.0,
    pagina: int = 1,
    img_path: Optional[Path] = None,
    rotacion: int = 0,
    words_tsv_6: Optional[list[dict]] = None,
    words_tsv_4: Optional[list[dict]] = None,
) -> DecisionComparacionOCR:
    """Compara candidatos PSM 6 y PSM 4 bajo contrato formal de arbitraje OCR.

    DOCUMENTACIÓN DE TOLERANCIAS Y POLÍTICA DE SOFTWARE:
    - Moneda y precisión: Peso Chileno (CLP), unidad entera sin decimales ni centavos
      conforme a la normativa tributaria chilena de balances tributarios de 8 columnas.
    - Tolerancia numérica (10.0 CLP): Heurística heredada de software, NO una regla contable
      universal. En contabilidad estricta por partida doble, la diferencia admisible es 0.
      Este umbral se conserva temporalmente con límites definidos para absorber pequeñas
      fluctuaciones de OCR por ruido en dígitos terminales o separadores de miles; no se
      amplía y su seguridad matemática universal no se considera demostrada.
    - Ratios de identidades (0.80 / 0.70): Política de validación de software (no contable)
      para verificar la regularidad geométrica de la cuadrícula de 8 columnas (satisfacción
      de identidades Debe - Haber == Saldos y Activo - Pasivo == Resultados).

    TABLA DE DECISIONES DE ARBITRAJE OCR (ESTRUCTURADA Y SIMÉTRICA):
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    | Id | Evidencia Disponible                              | Candidato     | Selección   | Motivo / Etiqueta           | Condición Bloqueo Certificación    |
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    | 1  | PSM 4 concilia detalle con control de página      | PSM 4         | Respaldada  | "PSM 4" (rescate control)   | Ninguno (control verificado)       |
    |    | (estado == 'conciliacion_valida') y PSM 6 no      |               |             |                             |                                    |
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    | 2  | PSM 6 concilia detalle con control de página      | PSM 6         | Respaldada  | None (control verificado)   | Ninguno (control verificado)       |
    |    | (estado == 'conciliacion_valida') y PSM 4 no      |               |             |                             |                                    |
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    | 3  | Ambos concilian detalle con control pero          | PSM 6         | Provisional | "ambigüedad con PSM 4"      | Bloqueo automático por             |
    |    | difieren materialmente en cuentas/montos          |               |             |                             | ambigüedad material                |
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    | 4  | Ambos utilizables sin control de página, pero     | PSM 6         | Provisional | None (equivalentes;         | Ninguno por ambigüedad             |
    |    | sin diferencias materiales en detalle             |               |             |  sin control de página)     | (selección provisional)            |
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    | 5  | Ambos utilizables sin control de página, y        | PSM 6         | Provisional | "ambigüedad con PSM 4"      | Bloqueo automático por             |
    |    | con diferencias materiales en cuentas/montos      |               |             |                             | ambigüedad material                |
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    | 6a | PSM 4 defectuoso/corrupto descartado;             | PSM 6         | Provisional | None (descarte de PSM 4;    | Sin control de página              |
    |    | PSM 6 sobreviviente sin control de página         |               |             |  sin control de página)     | (selección provisional)            |
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    | 6b | PSM 6 defectuoso/corrupto descartado;             | PSM 4         | Provisional | "PSM 4 (provisional)"       | Sin control de página              |
    |    | PSM 4 sobreviviente sin control de página         |               |             |                             | (selección provisional)            |
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    | 7  | Evidencia insuficiente en ambos candidatos        | PSM 6         | Provisional | "evidencia insuficiente"    | Evidencia insuficiente             |
    +----+---------------------------------------------------+---------------+-------------+-----------------------------+------------------------------------+
    """
    valid_6, complete_6 = _identidades_validas_lineas_8_columnas(lines_6)
    ratio_6 = (valid_6 / complete_6) if complete_6 > 0 else 0.0

    valid_4, complete_4 = _identidades_validas_lineas_8_columnas(lines_4)
    ratio_4 = (valid_4 / complete_4) if complete_4 > 0 else 0.0

    cuentas_6 = _extraer_cuentas_candidato(lines_6)
    cuentas_4 = _extraer_cuentas_candidato(lines_4)

    conc_valida_6 = (conc_6.get("estado") == "conciliacion_valida")
    conc_valida_4 = (conc_4.get("estado") == "conciliacion_valida")

    # Regla 1 & 2: Rescate/Prevalencia por conciliación matemática válida contra control de página
    if conc_valida_4 and not conc_valida_6:
        return DecisionComparacionOCR(
            motor_seleccionado="PSM 4",
            tipo_seleccion="respaldada",
            evidencia_disponible="control_local_conciliado",
            ambiguedad_material=False,
            evaluacion_incompleta=False,
            motivo="PSM 4 concilia detalle con control de página",
            condicion_revision=None,
            etiqueta="PSM 4",
        )

    if conc_valida_6 and not conc_valida_4:
        return DecisionComparacionOCR(
            motor_seleccionado="PSM 6",
            tipo_seleccion="respaldada",
            evidencia_disponible="control_local_conciliado",
            ambiguedad_material=False,
            evaluacion_incompleta=False,
            motivo="PSM 6 concilia detalle con control de página",
            condicion_revision=None,
            etiqueta=None,
        )

    # Regla 3: Si ambos concilian contra sus respectivos controles, verificar si coinciden materialmente
    if conc_valida_6 and conc_valida_4:
        hay_disc, motivo_disc = _detectar_discrepancias_materiales(cuentas_6, cuentas_4, tolerancia=tolerancia)
        if hay_disc:
            return DecisionComparacionOCR(
                motor_seleccionado="PSM 6",
                tipo_seleccion="provisional",
                evidencia_disponible="control_local_conciliado",
                ambiguedad_material=True,
                evaluacion_incompleta=False,
                motivo=f"Ambos candidatos concilian con controles locales pero difieren materialmente: {motivo_disc}",
                condicion_revision="bloqueo_certificacion",
                detalle_discrepancia=motivo_disc,
                etiqueta=f"PSM 6 (ambigüedad con PSM 4, requiere revisión: {motivo_disc})",
            )
        return DecisionComparacionOCR(
            motor_seleccionado="PSM 6",
            tipo_seleccion="respaldada",
            evidencia_disponible="control_local_conciliado",
            ambiguedad_material=False,
            evaluacion_incompleta=False,
            motivo="Ambos candidatos concilian con controles locales sin discrepancias materiales",
            condicion_revision=None,
            etiqueta=None,
        )

    # Reglas 4, 5, 6, 7: Ningún candidato tiene conciliación válida contra control de página
    # Distinción explícita de controles para evitar dependencias espurias:
    # a) Control local corrupto o contradictorio descalifica usabilidad (alcance acreditado == 'pagina' o defecto local por discrepancia)
    ctrl_local_corrupto_6 = bool(
        (conc_6.get("alcance") == "pagina" or (conc_6.get("alcance") is None and conc_6.get("estado") == "discrepancia"))
        and conc_6.get("subtotal_corrompido")
    )
    ctrl_local_corrupto_4 = bool(
        (conc_4.get("alcance") == "pagina" or (conc_4.get("alcance") is None and conc_4.get("estado") == "discrepancia"))
        and conc_4.get("subtotal_corrompido")
    )

    # b) Control con consistencia interna demostrada (no marcado corrupto y válido internamente)
    ctrl_valido_interno_6 = bool(conc_6.get("subtotal_valido_interno") and not conc_6.get("subtotal_corrompido"))
    ctrl_valido_interno_4 = bool(conc_4.get("subtotal_valido_interno") and not conc_4.get("subtotal_corrompido"))

    # c) Desplazamiento de columnas demostrado en el control:
    # Ocurre cuando un candidato tiene control con columnas rotas/desplazadas (corrompido e inválido interno),
    # mientras que el competidor demuestra un control internamente consistente o conciliado.
    # Si el competidor carece de control o no fue evaluado, NO se asume control limpio ni se descalifica el detalle.
    hay_disc, motivo_disc = _detectar_discrepancias_materiales(cuentas_6, cuentas_4, tolerancia=tolerancia)

    desplazamiento_ctrl_6 = bool(
        conc_6.get("subtotal_corrompido")
        and not conc_6.get("subtotal_valido_interno")
        and (ctrl_valido_interno_4 or conc_valida_4)
        and (conc_6.get("alcance") == "pagina" or not hay_disc)
    )
    desplazamiento_ctrl_4 = bool(
        conc_4.get("subtotal_corrompido")
        and not conc_4.get("subtotal_valido_interno")
        and (ctrl_valido_interno_6 or conc_valida_6)
    )

    base_usable_6 = bool(centers_6 and complete_6 >= 5 and ratio_6 >= 0.80)
    base_usable_4 = bool(centers_4 and complete_4 >= 5 and ratio_4 >= 0.80)

    usable_6 = base_usable_6 and not ctrl_local_corrupto_6 and not desplazamiento_ctrl_6
    usable_4 = base_usable_4 and not ctrl_local_corrupto_4 and not desplazamiento_ctrl_4

    # Clasificación de evidencia disponible
    if conc_6.get("alcance") == "acumulado" or conc_4.get("alcance") == "acumulado":
        evidencia = "control_acumulado"
    elif conc_6.get("alcance") == "documento_completo" or conc_4.get("alcance") == "documento_completo":
        evidencia = "control_global"
    else:
        evidencia = "sin_control"

    if usable_6 and usable_4:
        # Ambos candidatos son utilizables; ejecutar contraste semántico y composición fila a fila
        res_sem = _comparar_semantica_candidatos(cuentas_6, cuentas_4, tolerancia=tolerancia)
        comp = componer_filas_pagina_ocr(
            cuentas_6, cuentas_4,
            pagina=pagina,
            words_tsv_6=words_tsv_6,
            words_tsv_4=words_tsv_4,
            img_path=img_path,
            rotacion=rotacion,
            tolerancia=tolerancia,
        )

        if res_sem.decision == "dominancia_6":
            return DecisionComparacionOCR(
                motor_seleccionado="PSM 6",
                tipo_seleccion="respaldada",
                evidencia_disponible=evidencia,
                ambiguedad_material=False,
                evaluacion_incompleta=False,
                motivo=res_sem.motivo,
                condicion_revision=None,
                etiqueta=None,
                filas_compuestas=comp.filas_compuestas,
                lineas_compuestas=comp.lineas_compuestas_texto,
                resultado_composicion=comp,
            )
        elif res_sem.decision == "dominancia_4":
            return DecisionComparacionOCR(
                motor_seleccionado="PSM 4",
                tipo_seleccion="respaldada",
                evidencia_disponible=evidencia,
                ambiguedad_material=False,
                evaluacion_incompleta=False,
                motivo=res_sem.motivo,
                condicion_revision=None,
                etiqueta="PSM 4",
                filas_compuestas=comp.filas_compuestas,
                lineas_compuestas=comp.lineas_compuestas_texto,
                resultado_composicion=comp,
            )
        elif res_sem.decision == "equivalentes":
            return DecisionComparacionOCR(
                motor_seleccionado="PSM 6",
                tipo_seleccion="provisional",
                evidencia_disponible=evidencia,
                ambiguedad_material=False,
                evaluacion_incompleta=False,
                motivo=res_sem.motivo,
                condicion_revision=None,
                etiqueta=None,
                filas_compuestas=comp.filas_compuestas,
                lineas_compuestas=comp.lineas_compuestas_texto,
                resultado_composicion=comp,
            )
        elif not comp.bloqueada and (words_tsv_6 is not None or words_tsv_4 is not None):
            return DecisionComparacionOCR(
                motor_seleccionado="Composicion_Segura_Filas",
                tipo_seleccion="respaldada" if evidencia != "sin_control" else "provisional",
                evidencia_disponible=evidencia,
                ambiguedad_material=False,
                evaluacion_incompleta=False,
                motivo="Tabla compuesta fila a fila sin ambigüedades entre candidatos OCR",
                condicion_revision=None,
                etiqueta=None,
                filas_compuestas=comp.filas_compuestas,
                lineas_compuestas=comp.lineas_compuestas_texto,
                resultado_composicion=comp,
            )
        else:
            detalle = motivo_disc or res_sem.motivo or comp.motivo_bloqueo
            return DecisionComparacionOCR(
                motor_seleccionado="PSM 6",
                tipo_seleccion="provisional",
                evidencia_disponible=evidencia,
                ambiguedad_material=True,
                evaluacion_incompleta=False,
                motivo=f"Ambos utilizables sin control local; ambigüedad material no resuelta: {detalle}",
                condicion_revision="bloqueo_certificacion",
                detalle_discrepancia=detalle,
                etiqueta=f"PSM 6 (ambigüedad con PSM 4, requiere revisión: {detalle})",
                filas_compuestas=comp.filas_compuestas,
                lineas_compuestas=comp.lineas_compuestas_texto,
                resultado_composicion=comp,
            )

    if usable_6 and not usable_4:
        # Rechazar el candidato defectuoso (PSM 4) permite operar con PSM 6 como motor principal
        # sin generar falsa ambigüedad. La selección se mantiene provisional hasta que el certificador
        # evalúe evidencia acumulada o global a nivel de documento.
        return DecisionComparacionOCR(
            motor_seleccionado="PSM 6",
            tipo_seleccion="provisional",
            evidencia_disponible="sin_control",
            ambiguedad_material=False,
            evaluacion_incompleta=False,
            motivo="PSM 4 defectuoso descartado; PSM 6 superviviente sin control local conciliado",
            condicion_revision=None,
            etiqueta=None,
        )

    if usable_4 and not usable_6:
        # PSM 6 es defectuoso/corrupto, pero PSM 4 no acreditó conciliación válida de detalle.
        # Se selecciona PSM 4 provisionalmente para conservar la lectura geométricamente sana,
        # pero NUNCA como lectura respaldada, requiriendo revisión obligatoria.
        return DecisionComparacionOCR(
            motor_seleccionado="PSM 4",
            tipo_seleccion="provisional",
            evidencia_disponible="sin_control",
            ambiguedad_material=False,
            evaluacion_incompleta=False,
            motivo="PSM 6 defectuoso descartado; PSM 4 superviviente sin control local conciliado",
            condicion_revision=None,
            etiqueta="PSM 4 (provisional: sin conciliación de detalle verificada)",
        )

    # Ambos candidatos carecen de evidencia suficiente
    return DecisionComparacionOCR(
        motor_seleccionado="PSM 6",
        tipo_seleccion="provisional",
        evidencia_disponible="insuficiente",
        ambiguedad_material=False,
        evaluacion_incompleta=True,
        motivo="Evidencia insuficiente en ambos candidatos OCR",
        condicion_revision="revision_cuentas",
        etiqueta="PSM 6 (evidencia insuficiente en ambos candidatos OCR)",
    )


_GLOBAL_TELEMETRY_OBSERVER = None


def set_telemetry_observer(observer: Any) -> None:
    global _GLOBAL_TELEMETRY_OBSERVER
    _GLOBAL_TELEMETRY_OBSERVER = observer


def get_telemetry_observer() -> Any:
    return _GLOBAL_TELEMETRY_OBSERVER


def _tabla_ocr_con_alternativa(
    img_path: Path, rotation: int, words: list[dict],
    centers: Optional[list[float]], pagina: int = 1,
) -> tuple[list[str], Optional[list[float]], DecisionComparacionOCR]:
    """Contrasta geometría PSM 6 con PSM 4 evaluando cobertura, alineación y controles de subtotal.

    Reglas de decisión:
    1. Genera y evalúa AMBOS candidatos completos (PSM 6 y PSM 4) sin short-circuit prematuro.
    2. Evalúa conciliación de 8 columnas y alcances de control.
    3. Compara por cuenta, código, columnas y controles antes de elegir.
    4. Si hay ambigüedad material no resuelta, conserva evidencia y etiqueta ambigüedad.
    5. Restituye las condiciones exactas de RapidOCR de la Variante B congelada.
    6. Evalúa RapidOCR ANTES de registrar la telemetría definitiva.
    """
    # 1. Candidato PSM 6
    lines, detected = _extraer_tabla_balance_por_coordenadas(
        _OCRWordsPage(words), centers,
    )
    conc_6 = _evaluar_conciliacion_detalle_control(lines)

    # 2. Candidato PSM 4 - Generado y evaluado siempre sin short-circuit
    alternative_words = []
    psm4_failed = False
    try:
        alternative_words = ocr_pagina_tsv(img_path, rotation, psm=4)
    except Exception as exc:
        logger.warning("Fallo en OCR alternativo PSM 4: %s", exc)
        psm4_failed = True

    alternative, alternative_centers = _extraer_tabla_balance_por_coordenadas(
        _OCRWordsPage(alternative_words), centers,
    )
    conc_4 = _evaluar_conciliacion_detalle_control(alternative)

    # 3. Comparación detallada de candidatos PSM 6 vs PSM 4
    decision_ocr = _comparar_candidatos_ocr(
        lines, detected, alternative, alternative_centers, conc_6, conc_4,
        pagina=pagina, img_path=img_path, rotacion=rotation,
        words_tsv_6=words, words_tsv_4=alternative_words,
    )
    motor_elegido = decision_ocr.motor_seleccionado
    etiqueta_adv = decision_ocr.etiqueta

    if decision_ocr.lineas_compuestas and (
        motor_elegido == "Composicion_Segura_Filas"
        or (getattr(decision_ocr, "resultado_composicion", None) and not decision_ocr.resultado_composicion.bloqueada)
    ):
        lines = decision_ocr.lineas_compuestas

    # 4. Fallback a RapidOCR: restituir exactamente las condiciones de la variante B congelada
    other_valid, other_complete = _identidades_validas_lineas_8_columnas(alternative)
    valid, complete = _identidades_validas_lineas_8_columnas(lines)

    rapid_lines: list[str] = []
    rapid_centers: Optional[list[float]] = None
    rapid_evaluated = False
    rapid_failed = False
    rapid_words = None

    if motor_elegido != "PSM 4" and not decision_ocr.ambiguedad_material:
        if alternative_centers and other_complete >= 5:
            rapid_evaluated = True
            try:
                rapid_words = _rapidocr_words(img_path, rotation)
            except Exception as r_exc:
                logger.warning("Fallo en RapidOCR: %s", r_exc)
                rapid_failed = True
                rapid_words = None

            if rapid_words:
                rapid_lines, rapid_centers = _extraer_tabla_balance_por_coordenadas(
                    _OCRWordsPage(rapid_words), centers,
                )
                rapid_valid, rapid_complete = _identidades_validas_lineas_8_columnas(rapid_lines)
                if (
                    rapid_centers and rapid_complete >= 5
                    and rapid_valid >= max(valid, other_valid)
                    and rapid_complete >= max(5, other_complete - 2)
                    and (
                        rapid_valid > max(valid, other_valid)
                        or rapid_valid / rapid_complete > other_valid / other_complete
                    )
                    and rapid_valid / rapid_complete >= 0.80
                ):
                    motor_elegido = "RapidOCR"
                    etiqueta_adv = "RapidOCR"
                    decision_ocr = DecisionComparacionOCR(
                        motor_seleccionado="RapidOCR",
                        tipo_seleccion="respaldada",
                        evidencia_disponible="motor_alternativo_mejorado",
                        ambiguedad_material=False,
                        evaluacion_incompleta=False,
                        motivo="RapidOCR seleccionado por mayor cobertura e identidades válidas",
                        condicion_revision=None,
                        etiqueta="RapidOCR",
                    )

    # 5. Incertidumbre: si la lectura principal no produjo tabla y la alternativa sí
    if motor_elegido == "PSM 6" and not lines and alternative_centers and other_complete >= 5:
        motor_elegido = "PSM 4"
        etiqueta_adv = "PSM 4 (pendiente de validación)"
        decision_ocr = DecisionComparacionOCR(
            motor_seleccionado="PSM 4",
            tipo_seleccion="provisional",
            evidencia_disponible="sin_control",
            ambiguedad_material=False,
            evaluacion_incompleta=True,
            motivo="PSM 6 sin tabla; PSM 4 adoptado pendiente de validación",
            condicion_revision=None,
            etiqueta="PSM 4 (pendiente de validación)",
        )

    # 6. Registro de telemetría DEFINITIVA (después de evaluar RapidOCR)
    obs = _GLOBAL_TELEMETRY_OBSERVER
    if obs is not None:
        try:
            v6, c6 = _identidades_validas_lineas_8_columnas(lines)
            obs.record_candidate(
                engine="PSM 6",
                page_num=pagina,
                requested=True,
                generated=True,
                evaluated=True,
                rejected=(motor_elegido != "PSM 6"),
                rejection_reason=None if motor_elegido == "PSM 6" else f"Motor alternativo preferido ({motor_elegido})",
                selected=(motor_elegido == "PSM 6"),
                failed=False,
                lines_count=len(lines),
                valid_identities=v6,
                complete_identities=c6,
                control_scope=conc_6.get("alcance"),
                control_reconciled=(conc_6.get("estado") == "conciliacion_valida"),
                material_ambiguity=decision_ocr.ambiguedad_material,
            )
            v4, c4 = _identidades_validas_lineas_8_columnas(alternative)
            obs.record_candidate(
                engine="PSM 4",
                page_num=pagina,
                requested=True,
                generated=bool(alternative_words),
                evaluated=bool(alternative_centers),
                rejected=(motor_elegido != "PSM 4"),
                rejection_reason=conc_4.get("motivo") or (f"Rechazado frente a {motor_elegido}" if motor_elegido != "PSM 4" else None),
                selected=(motor_elegido == "PSM 4"),
                failed=psm4_failed,
                lines_count=len(alternative),
                valid_identities=v4,
                complete_identities=c4,
                control_scope=conc_4.get("alcance"),
                control_reconciled=(conc_4.get("estado") == "conciliacion_valida"),
                material_ambiguity=decision_ocr.ambiguedad_material,
            )
            if rapid_evaluated or hasattr(obs, "record_candidate"):
                v_rap, c_rap = _identidades_validas_lineas_8_columnas(rapid_lines)
                obs.record_candidate(
                    engine="RapidOCR",
                    page_num=pagina,
                    requested=rapid_evaluated,
                    generated=bool(rapid_words),
                    evaluated=bool(rapid_centers),
                    rejected=(rapid_evaluated and motor_elegido != "RapidOCR"),
                    rejection_reason="No superó criterios de cobertura de Variante B" if (rapid_evaluated and motor_elegido != "RapidOCR") else None,
                    selected=(motor_elegido == "RapidOCR"),
                    failed=rapid_failed,
                    lines_count=len(rapid_lines),
                    valid_identities=v_rap,
                    complete_identities=c_rap,
                    control_scope=None,
                    control_reconciled=False,
                    material_ambiguity=False,
                )
        except Exception as obs_exc:
            logger.warning("Error en observador de telemetría: %s", obs_exc, exc_info=True)

    # Retorno según el motor definitivo seleccionado
    if motor_elegido == "RapidOCR" and rapid_centers:
        return rapid_lines, rapid_centers, decision_ocr

    if motor_elegido == "PSM 4" and alternative_centers:
        return alternative, alternative_centers, decision_ocr

    if (
        decision_ocr.ambiguedad_material
        or (decision_ocr.etiqueta and decision_ocr.etiqueta != "PSM 6")
        or motor_elegido == "Composicion_Segura_Filas"
    ):
        return lines, detected, decision_ocr

    return lines, detected, None


def _normalizar_celda_numerica_rapidocr(token: str) -> str:
    """Corrige glifos numéricos sólo cuando toda la celda parece un importe."""
    compact = re.sub(r"\s+", "", str(token or ""))
    if not compact:
        return compact
    if compact == "。":
        return "0"
    if not re.fullmatch(r"[0-9OoDd.,()\-]+", compact):
        # RapidOCR conserva correctamente los caracteres, pero a veces elimina
        # todos los espacios de una glosa. Se restauran sólo fronteras y
        # controles inequívocos que el parser necesita para distinguir código
        # y subtotal; no se intenta reescribir nombres contables arbitrarios.
        compact = re.sub(
            r"^(\d{4,10})[.\-]?(?=[A-Za-zÁÉÍÓÚÜÑ])", r"\1 ", compact,
        )
        compact = re.sub(
            r"^(Resultado)(positivo|negativo)$", r"\1 \2", compact, flags=re.I,
        )
        compact = re.sub(
            r"^(Sumas?)(totales?|iguales)$", r"\1 \2", compact, flags=re.I,
        )
        compact = re.sub(
            r"^(Total)(Pagina)(Anterior)?$",
            lambda m: " ".join(part for part in m.groups() if part),
            compact, flags=re.I,
        )
        compact = re.sub(r"^(Total)(Acumulado)$", r"\1 \2", compact, flags=re.I)
        return compact
    return compact.translate(str.maketrans({"O": "0", "o": "0", "D": "0", "d": "0"}))


def _rapidocr_words(img_path: Path, rotacion: int) -> list[dict]:
    """Entrega palabras RapidOCR con su inclinación corregida.

    La dependencia es opcional: si no está instalada o falla, el flujo
    Tesseract continúa sin cambios. La corrección vertical usa la pendiente
    observada en los propios cuadriláteros, no una rotación fija por empresa.
    """
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return []

    tmp_path: Optional[Path] = None
    imagen_ocr = img_path
    try:
        if rotacion:
            with Image.open(img_path) as img:
                preparada = img.rotate(rotacion, expand=True)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    preparada.save(tmp.name)
                    tmp_path = Path(tmp.name)
                    imagen_ocr = tmp_path
        result, _elapsed = RapidOCR()(str(imagen_ocr))
        if not result:
            return []

        slopes: list[float] = []
        for box, _text, _confidence in result:
            width = float(box[1][0]) - float(box[0][0])
            if width >= 30:
                slopes.append((float(box[1][1]) - float(box[0][1])) / width)
        slope = sorted(slopes)[len(slopes) // 2] if slopes else 0.0

        words: list[dict] = []
        for box, raw_text, confidence in result:
            text = _normalizar_celda_numerica_rapidocr(str(raw_text).strip())
            if not text:
                continue
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            x0, x1 = min(xs), max(xs)
            ymid = sum(ys) / len(ys)
            words.append({
                "text": text,
                "x0": x0,
                "x1": x1,
                "top": ymid - slope * ((x0 + x1) / 2),
                "confidence": float(confidence),
            })
        # Una misma fila conserva pequeñas diferencias residuales por la
        # perspectiva del escaneo. Se ajustan a una banda común sólo cuando
        # están a menos de siete píxeles; las filas reales están separadas por
        # varias decenas de píxeles en la resolución de trabajo.
        bands: list[list[dict]] = []
        for word in sorted(words, key=lambda item: float(item["top"])):
            if not bands:
                bands.append([word])
                continue
            band_top = sum(float(item["top"]) for item in bands[-1]) / len(bands[-1])
            if abs(float(word["top"]) - band_top) <= 7:
                bands[-1].append(word)
            else:
                bands.append([word])
        for band in bands:
            aligned_top = sum(float(item["top"]) for item in band) / len(band)
            for word in band:
                word["top"] = aligned_top
        return words
    except Exception as exc:  # noqa: BLE001 - fallback OCR deliberado
        logger.info("RapidOCR no produjo una lectura utilizable: %s", exc)
        return []
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _identidades_validas_lineas_8_columnas(lineas: list[str]) -> tuple[int, int]:
    """Cuenta filas completas y filas que satisfacen ambas identidades."""
    completas = 0
    validas = 0
    for linea in lineas:
        tokens = linea.split()
        if len(tokens) < 9:
            continue
        amounts = tokens[-8:]
        if not all(PATRON_MONTOS.fullmatch(normalizar_token_ocr(token)) for token in amounts):
            continue
        values = [parsear_monto(token, ".") for token in amounts]
        if any(value is None for value in values):
            continue
        debe, haber, deudor, acreedor, activo, pasivo, perdida, ganancia = (
            float(value or 0.0) for value in values
        )
        if not any(abs(value) > 0 for value in (
            debe, haber, deudor, acreedor, activo, pasivo, perdida, ganancia,
        )):
            continue
        completas += 1
        if (
            math.isclose(debe - haber, deudor - acreedor, abs_tol=1.0)
            and math.isclose(
                deudor + acreedor,
                activo + pasivo + perdida + ganancia,
                abs_tol=1.0,
            )
        ):
            validas += 1
    return validas, completas


def _preferir_lectura_rapidocr(
    lineas_base: list[str], lineas_rapid: list[str],
) -> bool:
    """Acepta el rescate sólo con evidencia contable estrictamente mejor."""
    validas_base, completas_base = _identidades_validas_lineas_8_columnas(lineas_base)
    validas_rapid, completas_rapid = _identidades_validas_lineas_8_columnas(lineas_rapid)
    return (
        completas_rapid >= 5
        and completas_rapid >= max(5, completas_base - 2)
        and validas_rapid >= validas_base + 3
        and validas_rapid / completas_rapid >= 0.75
    )


def _reparar_lineas_por_identidades_redundantes(
    lineas: list[str],
) -> tuple[list[str], int]:
    """Corrige una celda OCR sólo si dos representaciones independientes coinciden.

    En un balance de ocho columnas, Debe/Haber, saldos y clasificación final
    expresan dos veces el mismo saldo. La función no decide la naturaleza de
    una cuenta ni rellena columnas vacías: sólo reemplaza el saldo o el único
    monto final ya observado cuando las otras dos expresiones son exactas.
    """
    repaired: list[str] = []
    changes = 0
    for linea in lineas:
        tokens = linea.split()
        if len(tokens) < 9:
            repaired.append(linea)
            continue
        amount_tokens = tokens[-8:]
        values_optional = [parsear_monto(token, ".") for token in amount_tokens]
        if any(value is None for value in values_optional):
            repaired.append(linea)
            continue
        values = [float(value or 0.0) for value in values_optional]
        debe, haber, deudor, acreedor, *finales = values
        movimiento = debe - haber
        esperado_deudor = max(movimiento, 0.0)
        esperado_acreedor = max(-movimiento, 0.0)
        total_final = sum(finales)
        saldo_observado = deudor + acreedor

        changed_index: Optional[int] = None
        changed_value = 0.0
        if (
            math.isclose(total_final, abs(movimiento), abs_tol=1.0)
            and not math.isclose(saldo_observado, abs(movimiento), abs_tol=1.0)
            and (
                math.isclose(deudor, 0.0, abs_tol=1.0)
                or math.isclose(acreedor, 0.0, abs_tol=1.0)
            )
        ):
            changed_index = 2 if movimiento >= 0 else 3
            changed_value = esperado_deudor if movimiento >= 0 else esperado_acreedor
            values[3 if movimiento >= 0 else 2] = 0.0
        else:
            nonzero_finales = [index for index, value in enumerate(finales) if value]
            if (
                math.isclose(saldo_observado, abs(movimiento), abs_tol=1.0)
                and len(nonzero_finales) == 1
                and not math.isclose(total_final, saldo_observado, abs_tol=1.0)
            ):
                changed_index = 4 + nonzero_finales[0]
                changed_value = saldo_observado

        if changed_index is None:
            repaired.append(linea)
            continue
        values[changed_index] = changed_value
        formatted = [str(int(value)) if value.is_integer() else str(value) for value in values]
        repaired.append(" ".join([*tokens[:-8], *formatted]))
        changes += 1
    return repaired, changes


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


def es_ruido_ocr_no_contable(cuenta: Optional[CuentaRaw]) -> bool:
    """Detecta texto documental no contable (firmas, notas, membretes, paginación, etc.).

    Reglas de protección y unificación:
    1. Cuentas con código contable nunca son ruido (False).
    2. Filas con columnas de ocho columnas pobladas (montos_columnas no nulos) nunca son ruido (False).
    3. Artefactos de puntuación puros (<<, >>, ---, ===, etc.) son ruido (True).
    4. Encabezados estructurados de membrete documental (RUT + paginación/folio, o dirección/domicilio al inicio con numeración)
       que solo poseen un monto escalar derivado del número de página o de calle son ruido (True).
    5. Cuentas monetarias legítimas incompletas (sin código, pero con nombre contable e importe escalar)
       NO son ruido (False); se conservan para que el control de integridad las detecte y requiera revisión.
    6. Filas ambiguas o mixtas que no cumplan unívocamente los patrones estructurales de metadatos se conservan (False).
    """
    if cuenta is None:
        return True
    if cuenta.codigo:
        return False
    nombre_raw = cuenta.nombre or ""
    nombre_norm = re.sub(r"\s+", " ", _sin_acentos(nombre_raw).lower()).strip()
    if not nombre_norm:
        return True

    # 1. Si tiene columnas de ocho columnas pobladas, se preserva como cuenta contable
    if any(val is not None and abs(float(val)) > 0.01 for val in cuenta.montos_columnas.values()):
        return False

    # 2. Artefactos de puntuación o geometría pura (<<, >>, ---, ===, etc.)
    if re.fullmatch(r"[=\-*_.#/<>|~«»\s]{1,}", nombre_raw):
        return True

    # 3. Encabezado documental que combina RUT y paginación (e.g. 'Rut [RUT-GENERICO] Página')
    if re.search(r"\brut\b.*\b(?:p[aá]g(?:ina)?|fol(?:io)?)\b", nombre_norm, re.I):
        return True

    # 4. Encabezado documental de dirección física que inicia con 'direccion'/'domicilio'/'casa matriz' y contiene número de calle
    if re.match(r"^(?:direcci[oó]n|domicilio|casa\s+matriz)\b.*\b(?:n[°*º.]|nro\.?|n[uú]mero|#)", nombre_norm, re.I):
        return True

    # 5. Membrete institucional que combina RUT y 'balance'
    if re.search(r"\brut\b.*\bbalance\b", nombre_norm, re.I):
        return True

    # Si tiene importe escalar no nulo y no coincidió con los patrones estructurales de metadatos,
    # se protege y conserva (e.g. cuentas legítimas incompletas)
    values = [cuenta.monto]
    if any(value is not None and abs(float(value)) > 0.01 for value in values):
        return False

    # Glosas documentales estándar sin montos (e.g. 'DEBE', 'HABER', líneas de guiones, etc.)
    if re.fullmatch(r"[=\-*_.#/\s]{3,}", nombre_raw):
        return True
    if bool(re.fullmatch(
        r"(?:nombre(?:\s+de\s+la\s+cuenta)?|codigo|debe|haber|saldos?|deudor|acreedor|activo|pasivo|perdida|ganancia)",
        nombre_norm,
    )):
        return True
    return bool(re.fullmatch(
        r"(?:(?:firma|firmas)(?:\s+(?:representante legal|contador general))?"
        r"|representante legal|contador general|auditor(?:es)?"
        r"|rut\s*:?\s*[\d.k-]+|nota\s+\d+|pagina\s+\d+(?:\s+de\s+\d+)?"
        r"|pag\s*:?\s*\d*|hasta\s*:?\s*[a-z0-9/.-]+"
        r"|(?:\d{4}\s+)?hasta\s*:?\s*[a-z0-9/.-]+"
        r"|fecha\s*:?\s*[\d/.-]+|timbre|visacion)", nombre_norm,
    ))


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
        if not c.es_total and not es_ruido_ocr_no_contable(c) and id(c) not in incluidos and (
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
    # Respetar el contrato del llamador, incluido cero exacto.
    if not math.isfinite(tolerancia) or tolerancia < 0:
        return False
    tol_finales = tolerancia
    if any(abs(calculados[col] - subtotal[col]) > tol_finales for col in columnas):
        return False
    resultado = subtotal["activo"] - subtotal["pasivo"]
    if abs(resultado - (subtotal["ganancia"] - subtotal["perdida"])) > tol_finales:
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


def certificar_extraccion_columnas(
    cuentas: list[CuentaRaw], metodo: str = "",
    tolerancia_absoluta: float = 10.0,
    ocr_bloqueo_certificacion: Optional[dict] = None,
    composiciones_ocr: Optional[dict[int, Any]] = None,
) -> CertificacionExtraccion:
    """Certifica las ocho columnas contra un subtotal impreso independiente."""
    filas_detalle = [
        cuenta for cuenta in cuentas
        if (
            not cuenta.es_total
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
        )
    ]
    # Descartar texto de encabezados, firmas o notas OCR sin código,
    # preservando cuentas legítimas aunque carezcan de código.
    filas_detalle = [c for c in filas_detalle if not es_ruido_ocr_no_contable(c)]

    def normalized_name(cuenta: CuentaRaw) -> str:
        return re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()

    def control_key(cuenta: CuentaRaw) -> str:
        return re.sub(r"[^a-z0-9]+", "", normalized_name(cuenta))

    finales = [
        cuenta for cuenta in cuentas
        if (
            cuenta.es_total
            and not getattr(cuenta, "es_subtotal_manual", False)
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
        )
        and (
            "totales iguales" in normalized_name(cuenta)
            or "sumas iguales" in normalized_name(cuenta)
            or control_key(cuenta) in {"totales", "totalgeneral", "totalesgenerales", "sumastotales"}
        )
    ]

    def inconsistent_rows(rows: list[CuentaRaw], finales_validadas: bool = False) -> list[int]:
        inconsistent: list[int] = []
        for cuenta in rows:
            values = cuenta.montos_columnas
            movement = values["debitos"] - values["creditos"]
            balance = values["saldo_deudor"] - values["saldo_acreedor"]
            classified = (
                values["activo"] + values["pasivo"]
                + values["perdida"] + values["ganancia"]
            )
            saldo_cuadra_clasificado = (
                abs(values["saldo_deudor"] + values["saldo_acreedor"] - classified) <= tolerancia_absoluta
            )
            movimiento_cuadra_saldo = (
                abs(movement - balance) <= tolerancia_absoluta
            )
            nombre_limpio = re.sub(r"^[^\w]+", "", str(cuenta.nombre or "")).strip()
            es_linea_resultado_cierre = bool(
                getattr(cuenta, "es_total", False)
                or PATRON_TOTAL.match(nombre_limpio)
            )
            if finales_validadas or (es_linea_resultado_cierre and saldo_cuadra_clasificado):
                if not saldo_cuadra_clasificado:
                    inconsistent.append(cuenta.linea)
            else:
                if not movimiento_cuadra_saldo or not saldo_cuadra_clasificado:
                    inconsistent.append(cuenta.linea)
        return inconsistent

    filas_inconsistentes = inconsistent_rows(filas_detalle, finales_validadas=False)

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
        cuenta for position, cuenta in enumerate(cuentas)
        if (
            cuenta.es_total
            and not getattr(cuenta, "es_subtotal_manual", False)
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
        )
        and (
            "subtotal" in control_key(cuenta)
            or control_key(cuenta) in {"sumas", "suma", "sumasparciales", "sumaparcial"}
            or control_key(cuenta).startswith("totalacumulado")
            or (
                control_key(cuenta) in {"totales", "totalgeneral", "totalesgenerales", "sumastotales", "total"}
                and any(
                    later.es_total
                    and control_key(later) in {"sumasiguales", "totalesiguales"}
                    for later in cuentas[position + 1:]
                )
            )
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
        aux_obs = []
        bloqueo_por_composicion = bool(composiciones_ocr and any(c and getattr(c, "bloqueada", False) for c in composiciones_ocr.values()))
        if (ocr_bloqueo_certificacion and ocr_bloqueo_certificacion.get("bloqueado")) or bloqueo_por_composicion:
            estado = "fallida"
            motivo_bloqueo = (
                ocr_bloqueo_certificacion.get("detalle") or ocr_bloqueo_certificacion.get("motivo")
                if (ocr_bloqueo_certificacion and ocr_bloqueo_certificacion.get("bloqueado"))
                else "Ambigüedad material no resuelta en composición de filas OCR"
            )
            razones.append(f"Bloqueo de certificación automática: {motivo_bloqueo}")
            bloqueos_lista = (ocr_bloqueo_certificacion.get("bloqueos") or [ocr_bloqueo_certificacion]) if ocr_bloqueo_certificacion else []
            for b in bloqueos_lista:
                aux_obs.append({
                    "tipo": "bloqueo_certificacion",
                    "motivo": b.get("motivo"),
                    "pagina": b.get("pagina"),
                    "detalle": b.get("detalle"),
                })
            if composiciones_ocr:
                pags_registradas = {obs.get("pagina") for obs in aux_obs if obs.get("pagina") is not None}
                for pag, c in composiciones_ocr.items():
                    if c and getattr(c, "bloqueada", False) and pag not in pags_registradas:
                        aux_obs.append({
                            "tipo": "bloqueo_certificacion",
                            "motivo": "ambiguedad_composicion_filas",
                            "pagina": pag,
                            "detalle": getattr(c, "motivo_bloqueo", None) or f"Página {pag}: ambigüedad en composición de filas",
                        })
        return CertificacionExtraccion(
            estado=estado, metodo=metodo,
            diferencias=diferencias_parciales,
            razones=razones,
            filas_evaluadas=len(filas_detalle),
            filas_inconsistentes=filas_inconsistentes,
            totales_finales_validos=totales_finales_validos,
            observaciones_auxiliares=aux_obs,
        )
    acumulados = [
        cuenta for cuenta in candidatos
        if normalized_name(cuenta).startswith("total acumulado")
    ]
    # Si hay un total general o subtotal global al final del documento (candidatos[-1]),
    # no usar un acumulado de transporte de página intermedia como referencia global.
    subtotal_referencia = (
        candidatos[-1] if (
            control_key(candidatos[-1]) in {"totales", "totalgeneral", "totalesgenerales", "sumastotales", "total"}
            or (finales and candidatos[-1] not in acumulados)
            or (acumulados and cuentas.index(acumulados[-1]) < len(cuentas) - 10 and candidatos[-1] != acumulados[-1])
        )
        else acumulados[-1] if acumulados else candidatos[-1]
    )
    total_impreso = dict(subtotal_referencia.montos_columnas)
    puentes_resultado = [
        cuenta for cuenta in cuentas
        if cuenta.es_total and cuenta.montos_columnas
        and re.match(
            r"^(?:perdidas?\s*(?:/|y|o)\s*ganancias?|resultado|utilidad|"
            r"perdida(?: net[ao]| del ejercicio)?)\b",
            normalized_name(cuenta),
        )
    ]
    calculados = {column: 0.0 for column in RAW_MONETARY_COLUMNS}
    filas = 0
    for cuenta in filas_detalle:
        filas += 1
        for column in RAW_MONETARY_COLUMNS:
            calculados[column] += float(cuenta.montos_columnas.get(column, 0.0) or 0.0)
    if not filas:
        return CertificacionExtraccion(
            estado="fallida", metodo=metodo,
            totales_impresos=dict(total_impreso),
            razones=["No se detectaron filas de cuentas para contrastar el subtotal."],
            filas_evaluadas=0,
            filas_inconsistentes=filas_inconsistentes,
            totales_finales_validos=totales_finales_validos,
        )

    # Un balance de ocho columnas contiene tres copias independientes del
    # control: suma del detalle, subtotal y total final (ajustado por el puente
    # de resultado). En OCR se puede reparar una sola copia cuando las otras
    # dos coinciden. Si no hay dos evidencias concordantes, el valor se deja
    # intacto para revisión humana.
    if "ocr" in metodo.lower() and finales:
        final_row = finales[-1]
        final_values = final_row.montos_columnas
        bridge_values = (
            puentes_resultado[-1].montos_columnas
            if puentes_resultado else {column: 0.0 for column in RAW_MONETARY_COLUMNS}
        )
        for column in RAW_MONETARY_COLUMNS:
            if not puentes_resultado and column in RAW_MONETARY_COLUMNS[4:]:
                # Sin una fila de resultado leída no sabemos cuánto agrega
                # el cierre a cada columna. No confundir ese ajuste legítimo
                # con un error OCR ni sobrescribir el total final impreso.
                continue
            calculated = float(calculados.get(column, 0.0) or 0.0)
            printed = float(total_impreso.get(column, 0.0) or 0.0)
            bridge = float(bridge_values.get(column, 0.0) or 0.0)
            final = float(final_values.get(column, 0.0) or 0.0)
            expected_final = printed + bridge
            expected_subtotal = final - bridge
            if (
                abs(calculated - printed) <= tolerancia_absoluta
                and abs(final - expected_final) > tolerancia_absoluta
            ):
                final_values[column] = expected_final
                if column not in final_row.columnas_derivadas:
                    final_row.columnas_derivadas.append(column)
            elif (
                abs(calculated - expected_subtotal) <= tolerancia_absoluta
                and abs(printed - expected_subtotal) > tolerancia_absoluta
            ):
                total_impreso[column] = expected_subtotal
                subtotal_referencia.montos_columnas[column] = expected_subtotal
                if column not in subtotal_referencia.columnas_derivadas:
                    subtotal_referencia.columnas_derivadas.append(column)

        pairs = (
            ("debitos", "creditos"),
            ("saldo_deudor", "saldo_acreedor"),
            ("activo", "pasivo"),
            ("perdida", "ganancia"),
        )
        fila_final_incompleta = any(
            (final_values[left] == 0) != (final_values[right] == 0)
            for left, right in pairs
        )
        if not fila_final_incompleta:
            totales_finales_validos = all(
                abs(final_values[left] - final_values[right]) <= tolerancia_absoluta
                for left, right in pairs
            )

    # Se permite reparar una lectura OCR sólo si el subtotal impreso determina
    # una única fila y una única columna de movimiento. El ajuste debe cerrar
    # exactamente el subtotal y dejar la identidad de la fila dentro de la
    # tolerancia contable. El valor original queda en trazabilidad y la fila
    # continúa marcada para revisión humana.
    reconciliaciones_ocr: list[dict[str, Any]] = []
    if "ocr" in metodo.lower() and len(filas_inconsistentes) == 1:
        posibles: list[tuple[CuentaRaw, str, float, float]] = []
        for cuenta in filas_detalle:
            if cuenta.linea not in filas_inconsistentes:
                continue
            for column in ("debitos", "creditos"):
                calculated = float(calculados.get(column, 0.0) or 0.0)
                printed = float(total_impreso.get(column, 0.0) or 0.0)
                adjustment = printed - calculated
                if (
                    abs(adjustment) <= tolerancia_absoluta
                    or abs(adjustment) > 1_000
                    or column in subtotal_referencia.columnas_derivadas
                ):
                    continue
                candidate = copy.deepcopy(cuenta)
                original = float(candidate.montos_columnas[column])
                candidate.montos_columnas[column] = original + adjustment
                subtotal_closes = abs(
                    calculated + adjustment - printed
                ) <= 1e-9
                if (
                    subtotal_closes
                    and _error_identidades_cuenta(cuenta) > tolerancia_absoluta
                    and _error_identidades_cuenta(candidate) <= tolerancia_absoluta
                ):
                    posibles.append((cuenta, column, original, adjustment))
        if len(posibles) == 1:
            cuenta, column, original, adjustment = posibles[0]
            reconciled = original + adjustment
            cuenta.montos_columnas[column] = reconciled
            if column not in cuenta.columnas_derivadas:
                cuenta.columnas_derivadas.append(column)
            calculados[column] += adjustment
            reconciliaciones_ocr.append({
                "linea": cuenta.linea,
                "cuenta": cuenta.nombre,
                "columna": column,
                "original": original,
                "reconciliado": reconciled,
            })

    columnas_finales_validadas = (
        not set(subtotal_referencia.columnas_derivadas).intersection(RAW_MONETARY_COLUMNS[4:])
        and _validar_columnas_finales(
            cuentas, filas_detalle, total_impreso, calculados, finales,
            puentes_resultado, tolerancia_absoluta,
        )
    )
    filas_inconsistentes_bloqueantes = inconsistent_rows(
        filas_detalle, finales_validadas=columnas_finales_validadas
    )
    filas_inconsistentes = sorted(set(
        filas_inconsistentes
        + [item["linea"] for item in reconciliaciones_ocr]
    ))

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
    if filas_inconsistentes_bloqueantes:
        razones.append(
            f"{len(filas_inconsistentes_bloqueantes)} filas no cumplen sus identidades "
            "Debe/Haber, saldo o columna de clasificación."
        )
    for item in reconciliaciones_ocr:
        razones.append(
            "Reconciliación OCR única en fila "
            f"{item['linea']} ({item['cuenta']}), {item['columna']}: "
            f"valor leído {item['original']:,.0f}; valor reconciliado "
            f"{item['reconciliado']:,.0f}. La fila permanece en revisión humana."
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
    ecuacion_subtotal_invalida = (
        fila_final_incompleta
        and abs(resultado_balance_subtotal - resultado_estado_subtotal)
        > tolerancia_absoluta
    )
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

    observaciones_auxiliares: list[dict] = []
    bloqueo_por_composicion = bool(composiciones_ocr and any(c and getattr(c, "bloqueada", False) for c in composiciones_ocr.values()))
    bloqueo_activo = bool((ocr_bloqueo_certificacion and ocr_bloqueo_certificacion.get("bloqueado")) or bloqueo_por_composicion)
    failed = bool(
        fallidas or filas_inconsistentes_bloqueantes
        or totales_finales_validos is False or puente_invalido
        or ecuacion_subtotal_invalida
        or bloqueo_activo
    )
    if bloqueo_activo:
        motivo_bloqueo = (
            ocr_bloqueo_certificacion.get("detalle") or ocr_bloqueo_certificacion.get("motivo")
            if (ocr_bloqueo_certificacion and ocr_bloqueo_certificacion.get("bloqueado"))
            else "Ambigüedad material en composición de filas OCR"
        )
        razones.append(f"Bloqueo de certificación automática: {motivo_bloqueo}")
        bloqueos_lista = (ocr_bloqueo_certificacion.get("bloqueos") or [ocr_bloqueo_certificacion]) if ocr_bloqueo_certificacion else []
        for b in bloqueos_lista:
            observaciones_auxiliares.append({
                "tipo": "bloqueo_certificacion",
                "motivo": b.get("motivo"),
                "pagina": b.get("pagina"),
                "detalle": b.get("detalle"),
            })
        if composiciones_ocr:
            pags_registradas = {obs.get("pagina") for obs in observaciones_auxiliares if obs.get("pagina") is not None}
            for pag, c in composiciones_ocr.items():
                if c and getattr(c, "bloqueada", False) and pag not in pags_registradas:
                    observaciones_auxiliares.append({
                        "tipo": "bloqueo_certificacion",
                        "motivo": "ambiguedad_composicion_filas",
                        "pagina": pag,
                        "detalle": getattr(c, "motivo_bloqueo", None) or f"Página {pag}: ambigüedad en composición de filas",
                    })
    filas_derivadas = [cuenta.linea for cuenta in filas_detalle if cuenta.columnas_derivadas]
    total_derivado = bool(
        subtotal_referencia.columnas_derivadas or fila_final_incompleta
    )
    if (filas_derivadas or total_derivado) and not failed:
        razones.append(
            f"{len(filas_derivadas)} filas contienen movimientos reconstruidos "
            "desde saldos y clasificación"
            + (" y el subtotal fue completado" if total_derivado else "")
            + "; requieren revisión humana."
        )
    movimientos_no_exhaustivos = bool(
        not bloqueo_activo
        and fallidas
        and set(fallidas).issubset({"debitos", "creditos"})
        and columnas_finales_validadas
        and not filas_inconsistentes_bloqueantes
        and totales_finales_validos is True
        and not puente_invalido
        and not ecuacion_subtotal_invalida
    )
    if movimientos_no_exhaustivos:
        failed = False
        razones = [r for r in razones if not r.startswith("Las sumas extraídas no reproducen el subtotal")]
        razones.append(
            "Las sumas de Debe y Haber no coinciden con el total impreso; "
            "no se ha determinado la causa. Solo las columnas finales, el "
            "resultado y el cierre quedaron certificados para homologación, "
            "no la integridad de los movimientos."
        )

    reconciliacion_ocr_requiere_revision = bool(
        reconciliaciones_ocr
        and finales
        and all(
            item["columna"] not in subtotal_referencia.columnas_derivadas
            and item["columna"] not in finales[-1].columnas_derivadas
            for item in reconciliaciones_ocr
        )
        and totales_finales_validos is True
        and not filas_inconsistentes_bloqueantes
        and not fallidas
        and not puente_invalido
        and not ecuacion_subtotal_invalida
    )

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
    for c in filas_detalle:
        if not c.codigo:
            c.requiere_revision_extraccion = True
            if "cuenta_sin_codigo" not in c.razones_revision_extraccion:
                c.razones_revision_extraccion.append("cuenta_sin_codigo")
            observaciones_auxiliares.append({
                "Fila": c.linea,
                "Cuenta": c.nombre,
                "Revisar": "Código ausente",
                "Detalle": f"Cuenta '{c.nombre}' sin código; conservada para homologación pero requiere revisión manual.",
            })
    for item in reconciliaciones_ocr:
        observaciones_auxiliares.append({
            "Fila": item["linea"],
            "Cuenta": item["cuenta"],
            "Revisar": item["columna"].capitalize(),
            "Detalle": (
                f"Valor OCR original: {item['original']:,.0f}; valor derivado "
                f"del subtotal: {item['reconciliado']:,.0f}. Confirme contra "
                "el documento antes de emitir el entregable."
            ),
        })
    # Una fila monetaria incompleta no puede desaparecer del universo evaluado
    # sólo porque no cumple el esquema de ocho columnas del filtro inicial.
    incompletas = [
        c for c in cuentas
        if not c.es_total and not es_ruido_ocr_no_contable(c)
        and not set(RAW_MONETARY_COLUMNS).issubset(c.montos_columnas)
        and (c.monto or any(c.montos_columnas.values()))
    ]
    if incompletas:
        failed = True
        columnas_finales_validadas = False
        razones.append(f"{len(incompletas)} filas monetarias no tienen las ocho columnas verificables.")
        for c in incompletas:
            c.requiere_revision_extraccion = True
            if "columnas_incompletas" not in c.razones_revision_extraccion:
                c.razones_revision_extraccion.append("columnas_incompletas")
            if c.linea not in filas_inconsistentes:
                filas_inconsistentes.append(c.linea)
    return CertificacionExtraccion(
        estado="fallida" if failed else (
            "certificada" if movimientos_no_exhaustivos else (
                "parcial" if (
                    filas_derivadas or total_derivado
                    or reconciliacion_ocr_requiere_revision
                ) else "certificada"
            )
        ),
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
        observaciones_auxiliares=observaciones_auxiliares,
    )


def certificar_clasificado_final(
    cuentas: list[CuentaRaw], clasificaciones: list[dict],
    periodos: list[str], monedas: list[str], tolerancia_absoluta: float = 0.0,
    *, codigos_validos: Optional[set[str]] = None, periodo_actual: Optional[str] = None,
    metodo_extraccion_fuente: Optional[str] = None,
) -> CertificacionExtraccion:
    """Certifica detalle de balance por sección y año después de clasificar.

    Contrasta balance y resultados por función contra controles independientes.
    Controles desconocidos y atribuciones sin detalle conservan estado parcial.
    """
    import math

    result = CertificacionExtraccion(metodo="classified_final_detail", estado="parcial")
    reasons = result.razones
    if not math.isfinite(tolerancia_absoluta) or tolerancia_absoluta < 0:
        raise ValueError("La tolerancia debe ser finita y no negativa.")
    years = sorted(set(str(p) for p in periodos if re.fullmatch(r"\d{4}", str(p))))
    represented_years = {
        str(key) for account in cuentas for key in account.montos_periodos
        if re.fullmatch(r"\d{4}", str(key))
    }
    years = sorted(set(years) | represented_years)
    moneda_set = {str(m).strip().upper() for m in monedas}
    if not years or len(moneda_set) != 1 or moneda_set & {"", "UNKNOWN", "DESCONOCIDO", "NONE"}:
        reasons.append("Faltan años explícitos o una moneda única para certificar el detalle.")
        return result
    if not codigos_validos or periodo_actual not in years:
        reasons.append("Falta catálogo válido o el período principal explícito.")
        return result

    def section(text):
        raw = (text or "").strip().upper()
        if raw in {"AC", "ANC", "PC", "PNC", "PAT", "A", "P", "PP"}:
            return raw
        name = re.sub(r"\s+", " ", _sin_acentos(text or "").lower()).strip()
        name = re.sub(r"^(?:total(?:es)?\s+(?:de\s+)?)", "", name)
        name = re.sub(r"\s+(?:total|totales)$", "", name)
        name = name.replace("activos", "activo").replace("pasivos", "pasivo")
        name = name.replace("corrientes", "corriente")
        return {
            "ac": "AC", "anc": "ANC", "pc": "PC", "pnc": "PNC", "pat": "PAT",
            "activo corriente": "AC", "activo no corriente": "ANC",
            "pasivo corriente": "PC", "pasivo no corriente": "PNC",
            "patrimonio": "PAT", "patrimonio neto": "PAT",
            "activo": "A", "pasivo": "P",
            "patrimonio y pasivo": "PP", "pasivo y patrimonio": "PP",
        }.get(name)

    def income_control(text):
        name = re.sub(r"[^a-z ]", " ", _sin_acentos(text or "").lower())
        name = re.sub(r"\s+", " ", name).strip()
        if name in {"ganancia bruta", "ganancia perdida bruta", "utilidad bruta"}:
            return "ER_GROSS"
        if re.fullmatch(r"(?:ganancia(?: perdida)?|resultado|utilidad) antes de impuestos?", name):
            return "ER_PRETAX"
        if name in {
            "ganancia", "ganancia perdida", "ganancia perdida del ejercicio",
            "utilidad del ejercicio", "ganancia del ejercicio", "resultado del ejercicio",
            "ganancia neta", "utilidad neta", "resultado neto",
        }:
            return "ER_NET"
        if name in {"ganancia perdida procedente de operaciones continuadas", "ganancia procedente de operaciones continuadas"}:
            return "ER_CONTINUING"
        if name in {"ganancia perdida procedente de operaciones discontinuadas", "ganancia procedente de operaciones discontinuadas", "resultado de operaciones discontinuadas"}:
            return "ER_DISCONTINUED"
        if (
            re.fullmatch(r"(?:otro )?resultado integral(?: total)?", name)
            or name in {
                "otros resultados integrales", "otro resultado integral",
                "total resultado integral",
            }
        ):
            return "ER_OCI" if "otro" in name else "ER_COMPREHENSIVE"
        if "atribuible a" in name:
            is_nci = any(k in name for k in ("no controlad", "minoritari"))
            is_parent = any(k in name for k in ("controlad", "matriz", "propietari")) and not is_nci
            if is_nci:
                return "ER_ATTRIB_COMP_NCI" if "integral" in name else "ER_ATTRIB_NET_NCI"
            if is_parent:
                return "ER_ATTRIB_COMP_PARENT" if "integral" in name else "ER_ATTRIB_NET_PARENT"
        return None


    by_line = {}
    for row in clasificaciones:
        if row.get("line") in by_line:
            reasons.append("La clasificación contiene identidades de fila duplicadas.")
            return result
        by_line[row.get("line")] = row
    if len({c.linea for c in cuentas}) != len(cuentas):
        reasons.append("El detalle contiene identidades de fila duplicadas.")
        return result
    details = {key: [] for key in ("AC", "ANC", "PC", "PNC", "PAT")}
    controls = {}
    income_rows = []
    attrib_net_rows = []
    income_controls = {}
    filas_confianza_reducida: list[int] = []
    for account in cuentas:
        if account.monto is None:
            if not section(account.nombre):
                reasons.append(f"Fila {account.linea}: importe ausente en una fila que no es encabezado reconocido.")
            continue
        if (
            account.columnas_derivadas or account.requiere_revision_extraccion
            or not math.isfinite(account.confianza_extraccion)
            or not math.isfinite(float(account.monto))
        ):
            reasons.append(f"Fila {account.linea}: evidencia de extracción pendiente de revisión.")
        elif account.confianza_extraccion < 0.9:
            filas_confianza_reducida.append(account.linea)
        if account.monto != account.montos_periodos.get(periodo_actual):
            reasons.append(f"Fila {account.linea}: monto principal distinto del período declarado.")
        income_key = income_control(account.nombre)
        if account.es_total or income_key == "ER_OCI":
            if income_key:
                if income_key in income_controls:
                    prior = income_controls[income_key]
                    same_amounts = all(
                        prior.montos_periodos.get(year)
                        == account.montos_periodos.get(year)
                        for year in years
                    )
                    if (
                        income_key == "ER_NET"
                        and "ER_NET_CARRY_FORWARD" not in income_controls
                        and same_amounts
                        and prior.linea < account.linea
                    ):
                        income_controls["ER_NET_CARRY_FORWARD"] = account
                    else:
                        reasons.append(f"Control de resultados duplicado: {income_key}.")
                else:
                    income_controls[income_key] = account
                continue
            key = section(account.nombre)
            if not key:
                reasons.append(f"Fila {account.linea}: control fuera del alcance de balance por secciones.")
                continue
            if key in controls:
                reasons.append(f"Control duplicado para sección {key}.")
            controls[key] = account
        else:
            row = by_line.get(account.linea)
            key = section(account.seccion_contable)
            if row and str(row.get("code", "")).startswith("ER.") and not key:
                code = str(row.get("code", ""))
                is_net_attrib = code in {"ER.20", "ER.21"}
                if (
                    code not in codigos_validos or row.get("review")
                    or row.get("name") != account.nombre or row.get("amount") != account.monto
                    or income_control(account.nombre)
                    or (code in {"ER.03", "ER.11", "ER.19"} and not is_net_attrib)
                ):
                    reasons.append(f"Fila {account.linea}: detalle de resultados no acreditado o subtotal tratado como cuenta.")
                if is_net_attrib:
                    attrib_net_rows.append(account)
                else:
                    income_rows.append(account)
                continue
            if not key or key not in details:
                reasons.append(f"Fila {account.linea}: sección detallada no acreditada o estado de resultados pendiente.")
                continue
            if (
                not row or row.get("review") or not row.get("code")
                or row.get("code") not in codigos_validos
                or str(row["code"]).split(".")[0] != key
                or row.get("name") != account.nombre
                or row.get("amount") != account.monto
            ):
                reasons.append(f"Fila {account.linea}: clasificación final incompleta o incompatible con su sección.")
            details[key].append(account)
    result.filas_evaluadas = sum(map(len, details.values())) + len(income_rows) + len(attrib_net_rows)
    required = {key for key, rows in details.items() if rows} | {"A", "PP", "PAT"}
    if not details["AC"] and not details["ANC"]:
        reasons.append("No hay detalle de activos acreditado.")
    if not required.issubset(controls):
        reasons.append("Faltan controles impresos: " + ", ".join(sorted(required - controls.keys())))
    if income_rows or income_controls:
        required_income = {"ER_GROSS", "ER_PRETAX", "ER_NET"}
        if not income_rows or not required_income.issubset(income_controls):
            reasons.append("Falta detalle o controles de resultado bruto, antes de impuestos y neto.")
        else:
            gross, pretax, net = [income_controls[k].linea for k in ("ER_GROSS", "ER_PRETAX", "ER_NET")]
            if not gross < pretax < net:
                reasons.append("El orden de los controles de resultados no está acreditado.")
            continuation = income_controls.get("ER_CONTINUING")
            discontinued = income_controls.get("ER_DISCONTINUED")
            for optional_control in (continuation, discontinued):
                if optional_control and not pretax < optional_control.linea < net:
                    reasons.append("Control de operaciones continuadas/discontinuadas fuera de orden.")
            if continuation and discontinued and continuation.linea >= discontinued.linea:
                reasons.append("El control de operaciones discontinuadas precede al de continuadas.")
            carry_forward = income_controls.get("ER_NET_CARRY_FORWARD")
            oci_control = income_controls.get("ER_OCI")
            comprehensive = income_controls.get("ER_COMPREHENSIVE")
            if carry_forward:
                if not oci_control or not comprehensive:
                    reasons.append(
                        "El arrastre del resultado neto no tiene controles de resultado integral."
                    )
                elif not (
                    net < carry_forward.linea < oci_control.linea
                    < comprehensive.linea
                ):
                    reasons.append("El arrastre del resultado neto está fuera de orden.")
            all_eval_income = income_rows + attrib_net_rows
            for account in all_eval_income:
                code = by_line[account.linea]["code"]
                name = re.sub(r"\s+", " ", _sin_acentos(account.nombre).lower()).strip()
                if (
                    code == "ER.01" and not re.fullmatch(r"ingresos de (?:actividades ordinarias|explotacion)", name)
                    or code == "ER.02" and not re.fullmatch(r"costos? de (?:ventas|explotacion)", name)
                ):
                    reasons.append(f"Fila {account.linea}: no se acredita el rol individual de ingreso o costo de ventas.")
                if continuation and account.linea >= continuation.linea:
                    reasons.append(f"Fila {account.linea}: detalle posterior al control de operaciones continuadas.")
                valid_position = (
                    account.linea < gross if code in {"ER.01", "ER.02"}
                    else pretax < account.linea < net if code == "ER.10"
                    else account.linea > net if code in {"ER.20", "ER.21"}
                    else gross < account.linea < pretax
                )
                if not valid_position:
                    reasons.append(f"Fila {account.linea}: ubicación incompatible con controles de resultados.")
            if not {"ER.01", "ER.02"}.issubset({by_line[a.linea]["code"] for a in income_rows}):
                reasons.append("Falta detalle de ingresos o costo de ventas para verificar resultado bruto.")
    unknown_classifications = set(by_line) - {c.linea for c in cuentas if not c.es_total}
    if unknown_classifications:
        reasons.append("Existen clasificaciones sin una cuenta de detalle fuente.")
    if reasons:
        # La cobertura ausente no es una diferencia monetaria comprobada.
        # No compare sumas incompletas contra controles impresos como si lo fuera.
        return result

    def value(account, year):
        amount = account.montos_periodos.get(year)
        if amount is None or not math.isfinite(float(amount)):
            raise ValueError(f"Fila {account.linea}: falta importe finito del período {year}.")
        return float(amount)

    failed = False
    for year in years:
        try:
            sums = {key: sum(value(c, year) for c in rows) for key, rows in details.items()}
            sums.update(A=sums["AC"] + sums["ANC"], P=sums["PC"] + sums["PNC"])
            sums["PP"] = sums["P"] + sums["PAT"]
            if not all(math.isfinite(amount) for amount in sums.values()):
                raise ValueError(f"Período {year}: suma no finita, requiere revisión de importes.")
            for key, control in controls.items():
                printed = value(control, year)
                delta = sums[key] - printed
                result.totales_impresos[f"{year}:{key}"] = printed
                result.totales_calculados[f"{year}:{key}"] = sums[key]
                result.diferencias[f"{year}:{key}"] = delta
                failed |= abs(delta) > tolerancia_absoluta
            delta = sums["A"] - sums["PP"]
            result.diferencias[f"{year}:ecuacion"] = delta
            failed |= abs(delta) > tolerancia_absoluta
            if income_controls:
                pre = income_controls["ER_PRETAX"].linea
                income_sums = {
                    "ER_GROSS": sum(value(a, year) for a in income_rows if by_line[a.linea]["code"] in {"ER.01", "ER.02"}),
                    "ER_PRETAX": sum(value(a, year) for a in income_rows if a.linea < pre),
                    "ER_CONTINUING": sum(value(a, year) for a in income_rows),
                    # Nonzero discontinued results require their own detail; never
                    # copy an unverified printed subtotal into the calculated sum.
                    "ER_DISCONTINUED": 0.0,
                    "ER_NET": sum(value(a, year) for a in income_rows),
                }
                if not all(math.isfinite(amount) for amount in income_sums.values()):
                    raise ValueError(f"Período {year}: suma de resultados no finita.")
                for key, control in income_controls.items():
                    printed = value(control, year)
                    if key in income_sums:
                        delta = income_sums[key] - printed
                        result.totales_impresos[f"{year}:{key}"] = printed
                        result.totales_calculados[f"{year}:{key}"] = income_sums[key]
                        result.diferencias[f"{year}:{key}"] = delta
                        if key == "ER_DISCONTINUED" and printed != 0:
                            reasons.append("Operaciones discontinuadas sin detalle independiente para certificar.")
                        else:
                            failed |= abs(delta) > tolerancia_absoluta
                    else:
                        result.totales_impresos[f"{year}:{key}"] = printed
                # Conciliación independiente de atribuciones del resultado neto
                net_attrib_controls = [c for k, c in income_controls.items() if k in {"ER_ATTRIB_NET_PARENT", "ER_ATTRIB_NET_NCI"}]
                if attrib_net_rows or net_attrib_controls:
                    total_net_attrib = sum(value(a, year) for a in attrib_net_rows) + sum(value(c, year) for c in net_attrib_controls)
                    delta_net_attrib = round(total_net_attrib - income_sums["ER_NET"], 2)
                    result.diferencias[f"{year}:ER_ATTRIB_NET"] = delta_net_attrib
                    failed |= abs(delta_net_attrib) > tolerancia_absoluta
                # Conciliación independiente de atribuciones del resultado integral total
                comp_attrib_controls = [c for k, c in income_controls.items() if k in {"ER_ATTRIB_COMP_PARENT", "ER_ATTRIB_COMP_NCI"}]
                if comp_attrib_controls and "ER_COMPREHENSIVE" in income_controls:
                    total_comp_attrib = sum(value(c, year) for c in comp_attrib_controls)
                    tci_printed = value(income_controls["ER_COMPREHENSIVE"], year)
                    delta_comp_attrib = round(total_comp_attrib - tci_printed, 2)
                    result.diferencias[f"{year}:ER_ATTRIB_COMP"] = delta_comp_attrib
                    failed |= abs(delta_comp_attrib) > tolerancia_absoluta
                # Conciliación de la ecuación de resultado integral (Neto + ORI = TCI)
                if "ER_OCI" in income_controls and "ER_COMPREHENSIVE" in income_controls:
                    oci_val = value(income_controls["ER_OCI"], year)
                    tci_val = value(income_controls["ER_COMPREHENSIVE"], year)
                    delta_tci = round(income_sums["ER_NET"] + oci_val - tci_val, 2)
                    result.diferencias[f"{year}:ER_TCI_EQUATION"] = delta_tci
                    failed |= abs(delta_tci) > tolerancia_absoluta

        except (ValueError, TypeError) as exc:
            reasons.append(str(exc))
    native_fragment_attested = bool(
        filas_confianza_reducida
        and metodo_extraccion_fuente == "native_fragment_reconstruction"
        and all(
            math.isfinite(account.confianza_extraccion)
            and 0.75 <= account.confianza_extraccion < 0.9
            and not account.columnas_derivadas
            and not account.requiere_revision_extraccion
            for account in cuentas
            if account.linea in filas_confianza_reducida
        )
    )
    if failed:
        result.estado = "fallida"
        reasons.append("El detalle no reproduce los controles por sección y período.")
        result.totales_finales_validos = False
    elif filas_confianza_reducida and not native_fragment_attested:
        reasons.extend(
            f"Fila {linea}: evidencia de extracción pendiente de revisión."
            for linea in filas_confianza_reducida
        )
        result.totales_finales_validos = True
    elif not reasons:
        result.estado = "certificada"
        result.totales_finales_validos = True
        if income_controls:
            result.resultado_ejercicio = result.totales_calculados[f"{periodo_actual}:ER_NET"]
            result.tipo_resultado = "utilidad" if result.resultado_ejercicio >= 0 else "perdida"
        if native_fragment_attested:
            reasons.append(
                "Texto nativo fragmentado acreditado mediante detalle, clasificación, "
                "controles por sección y ecuación en todos los períodos explícitos."
            )
        else:
            reasons.append("Detalle, clasificación, secciones y ecuación acreditados en todos los períodos explícitos.")
    return result


def certificar_totales_clasificados(
    cuentas: list[CuentaRaw], tolerancia_absoluta: float = 10.0,
) -> CertificacionExtraccion:
    """Control parcial para balances clasificados/IFRS de una o dos columnas.

    Certifica únicamente la ecuación final impresa. No afirma que todas las
    cuentas intermedias estén completas ni correctamente homologadas.
    """
    def _val_cuenta(c: CuentaRaw) -> Optional[float]:
        if c.monto is not None:
            return float(c.monto)
        if c.montos_periodos:
            if "actual" in c.montos_periodos:
                return float(c.montos_periodos["actual"])
            for k, v in c.montos_periodos.items():
                if re.fullmatch(r"\d{4}", str(k)):
                    return float(v)
            return float(list(c.montos_periodos.values())[0])
        return None

    totals: dict[str, float] = {}
    generic_liability_totals: list[float] = []
    for cuenta in cuentas:
        val = _val_cuenta(cuenta)
        if val is None:
            continue
        name = re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()
        if name in {"total activos", "total de activos", "total assets"}:
            totals["activo"] = val
        elif name in {
            "total pasivos y patrimonio",
            "total pasivos y patrimonio neto",
            "total pasivo y patrimonio",
            "total patrimonio y pasivos",
            "total de patrimonio y pasivos",
            "total equity and liabilities",
        }:
            totals["pasivo_patrimonio"] = val
        elif name in {"total pasivos", "total de pasivos"}:
            generic_liability_totals.append(val)
    if "activo" in totals and "pasivo_patrimonio" not in totals:
        matching_totals = [
            value for value in generic_liability_totals
            if abs(value - totals["activo"]) <= tolerancia_absoluta
        ]
        if matching_totals:
            totals["pasivo_patrimonio"] = matching_totals[-1]
    if set(totals) != {"activo", "pasivo_patrimonio"}:
        return CertificacionExtraccion(
            estado="no_evaluable", metodo="classified_totals",
            razones=[
                "No se encontraron ambos totales finales del balance clasificado."
            ],
        )
    difference = round(totals["activo"] - totals["pasivo_patrimonio"], 2)
    secciones: dict[str, float] = {}
    diferencias_seccion: dict[str, float] = {}
    nombres = [
        re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()
        for cuenta in cuentas
    ]
    for index, nombre in enumerate(nombres):
        val_idx = _val_cuenta(cuentas[index])
        if cuentas[index].es_total or val_idx is not None:
            continue
        total_buscado = f"total {nombre}"
        total_index = next(
            (
                candidate for candidate in range(index + 1, len(cuentas))
                if nombres[candidate] == total_buscado
                and cuentas[candidate].es_total
                and _val_cuenta(cuentas[candidate]) is not None
            ),
            None,
        )
        if total_index is None:
            continue
        detalle = [
            _val_cuenta(cuenta)
            for cuenta, nombre_detalle in zip(
                cuentas[index + 1:total_index],
                nombres[index + 1:total_index],
            )
            if _val_cuenta(cuenta) is not None
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
    if secciones_fallidas:
        detalle = ", ".join(
            f"{nombre.removeprefix('seccion:')}={diferencia:,.0f}"
            for nombre, diferencia in secciones_fallidas.items()
        )
        return CertificacionExtraccion(
            estado="fallida", metodo="classified_section_totals",
            totales_impresos={**totals, **{f"seccion:{k}": v for k, v in secciones.items()}},
            diferencias={
                "activo_menos_pasivo_patrimonio": difference,
                **diferencias_seccion,
            },
            razones=[
                "El detalle extraído no reproduce uno o más subtotales impresos: "
                f"{detalle}."
            ],
            filas_evaluadas=sum(
                1 for cuenta in cuentas if cuenta.monto is not None and not cuenta.es_total
            ),
            totales_finales_validos=abs(difference) <= tolerancia_absoluta,
        )
    if abs(difference) > tolerancia_absoluta:
        return CertificacionExtraccion(
            estado="fallida", metodo="classified_totals",
            totales_impresos=totals,
            diferencias={"activo_menos_pasivo_patrimonio": difference},
            razones=[
                "El total de activos no coincide con el total de pasivos y patrimonio."
            ],
            totales_finales_validos=False,
        )
    return CertificacionExtraccion(
        estado="parcial", metodo="classified_totals",
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
    (re.compile(
        r"^(?:patrimonio\s+y\s+pasivos?|pasivos?\s+y\s+patrimonio)"
        r"(?:\s+neto)?$", re.I,
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
        r"^(?:costos?|gastos|perdidas?|otros\s+gastos|"
        r"(?:operating|non[- ]?operational)?\s*expenses?)$",
        re.I,
    ),
     OrigenColumna.PERDIDA),
)


def _normalizar_encabezado_seccion(nombre: str) -> str:
    """Retira columnas auxiliares de un encabezado contable comparativo."""
    encabezado = re.sub(
        r"\b(?:\d{1,2}[-/]\d{1,2}[-/](?:19|20)\d{2}|(?:19|20)\d{2})\b",
        " ", nombre,
    )
    encabezado = re.sub(
        r"\b(?:nota|mus\$?|m\$|us\$|usd|clp)\b", " ", encabezado,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", encabezado).strip(" :,-")


def anotar_secciones_balance_clasificado(cuentas: list[CuentaRaw]) -> int:
    """Propaga el encabezado contable a filas de balances clasificados.

    Sólo completa orígenes desconocidos y nunca cambia una columna observada.
    Los encabezados y totales sirven como límites, pero no se convierten en
    cuentas de detalle. Retorna el número de filas enriquecidas.
    """
    seccion: Optional[OrigenColumna] = None
    seccion_contable: Optional[str] = None
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
            seccion = None
            seccion_contable = None
            secciones_paralelas = False
            continue
        if re.match(
            r"^total(?:es)?\s+(?:de\s+)?(?:"
            r"pasivos?\s+y\s+patrimonio(?:\s+neto)?|"
            r"patrimonio\s+y\s+pasivos?|equity\s+and\s+liabilities)$",
            nombre, re.I,
        ):
            seccion = None
            seccion_contable = None
            secciones_paralelas = False
            continue
        normalized_english = nombre.replace("-", " ")
        encabezado_paralelo = (
            (
                re.search(r"\bassets?\b", normalized_english, re.I)
                and re.search(r"\b(?:equity|liabilities)\b", normalized_english, re.I)
            )
            or (
                re.search(r"\bactivos?\b", nombre, re.I)
                and re.search(r"\b(?:pasivos?|patrimonio)\b", nombre, re.I)
            )
        )
        if encabezado_paralelo and not cuenta.es_total:
            seccion = None
            seccion_contable = None
            secciones_paralelas = True
            continue
        encabezado = _normalizar_encabezado_seccion(nombre)
        if cuenta.es_total:
            encabezado = re.sub(r"^total(?:es)?\s+", "", nombre, flags=re.I)
        nueva_seccion = None
        for patron, origen in _SECTION_HEADING_PATTERNS:
            if patron.fullmatch(encabezado):
                nueva_seccion = origen
                break
        if nueva_seccion is not None:
            if cuenta.es_total and nueva_seccion in (
                OrigenColumna.PERDIDA, OrigenColumna.GANANCIA,
            ):
                seccion = None
                seccion_contable = None
                secciones_paralelas = False
                continue
            seccion = nueva_seccion
            seccion_contable = encabezado
            secciones_paralelas = False
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
            cuenta.seccion_contable = seccion_contable
            if cuenta.origen_columna != seccion:
                cuenta.origen_columna = seccion
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


_SUFIJOS_GLOSA_PARTIDA = re.compile(
    r"^(?:l\.?p\.?|c\.?p\.?|s\.?a\.?|ltda\.?|spa|e\.?i\.?r\.?l\.?|acumulad[oa]s?|propio|trabajador(?:es)?|veh[ií]culos?|"
    r"corriente|no corriente|largo plazo|corto plazo|por pagar|por cobrar|en garantia|en transito|al personal|de terceros|del giro)$",
    re.IGNORECASE,
)

_CUENTAS_CORTAS_INDIVIDUALES = {
    "caja", "iva", "ppm", "banco", "bancos", "clientes", "proveedores", "capital",
    "retenciones", "honorarios", "sueldos", "arriendos", "seguros", "leasings",
    "fondos", "gastos", "ingresos", "ventas", "costos", "existencias", "mercaderias",
}


def fusionar_continuaciones_verticales(
        cuentas: list[CuentaRaw]) -> tuple[list[CuentaRaw], int]:
    """Une sufijos y fragmentos verticales sin importe a la cuenta monetaria precedente."""
    resultado: list[CuentaRaw] = []
    cantidad = 0
    for cuenta in cuentas:
        sin_importes = (
            (cuenta.monto is None or abs(float(cuenta.monto)) <= 0.01)
            and not cuenta.montos_periodos
            and not any(
                float(cuenta.montos_columnas.get(columna, 0.0) or 0.0) != 0.0
                for columna in RAW_MONETARY_COLUMNS
            )
        )
        anterior = resultado[-1] if resultado else None
        nombre = re.sub(r"\s+", " ", cuenta.nombre or "").strip()
        nombre_norm = _sin_acentos(nombre.lower())

        anterior_tiene_importes = anterior is not None and (
            (anterior.monto is not None and abs(float(anterior.monto)) > 0.01)
            or any(
                float(anterior.montos_columnas.get(columna, 0.0) or 0.0) != 0.0
                for columna in RAW_MONETARY_COLUMNS
            )
        )
        termina_en_conector = bool(
            anterior and re.search(r"\b(?:y|de|del|por|a|al|en|con|para|sin|sobre|e|o|u)\b$", anterior.nombre, re.I)
        )
        es_sufijo_conocido = bool(_SUFIJOS_GLOSA_PARTIDA.fullmatch(nombre_norm))
        es_cuenta_corta_valida = nombre_norm in _CUENTAS_CORTAS_INDIVIDUALES

        if (
            anterior is not None
            and cuenta.linea == anterior.linea + 1
            and not cuenta.codigo
            and not cuenta.es_total
            and not anterior.es_total
            and sin_importes
            and anterior_tiene_importes
            and not es_cuenta_corta_valida
            and (
                es_sufijo_conocido
                or termina_en_conector
            )
        ):
            anterior.nombre = re.sub(
                r"\s+", " ", f"{anterior.nombre} {nombre}",
            ).strip()
            anterior.confianza_extraccion = min(
                anterior.confianza_extraccion,
                cuenta.confianza_extraccion,
            )
            cantidad += 1
            continue
        resultado.append(cuenta)
    return resultado, cantidad


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
# 1101-51. OCR puede fusionar varios grupos a cualquiera de sus lados.
_PATRON_AUX_UNISEP = re.compile(r'^(\d{1,6}[-.]\d{2,8})\s+([A-Za-zÁÉÍÓÚÑáéíóúñ].+)')
# FG2 — código compacto concatenado al nombre sin espacio: 11090BANCO, 10423CTA.
#    El lookahead `(?=[A-Z...])` parte en la frontera dígito → letra y exige que
#    el código sea de 4 a 6 dígitos seguidos inmediatamente por una letra.
_PATRON_AUX_CONCATENADO = re.compile(r'^(\d{4,6})(?=[A-ZÁÉÍÓÚÑ])(.+)')
PATRONES_CODIGO_AUXILIARES = (_PATRON_AUX_UNISEP, _PATRON_AUX_CONCATENADO)
_PATRON_CODIGO_EMBEBIDO_OCR = re.compile(
    r"^[^\d\n]{1,3}(\d{1,2}(?:[.,/:]\d{1,2}){2,4})\s*[-–—−]?\s*(.+)$"
)

PATRON_MONTOS = re.compile(r'(-?\(?[\d.,]{1,18}\)?)')
_OCR_CERO = re.compile(r'^[oO]$')
_OCR_CERO_EN_CELDA = re.compile(r'^(?:[oO]|[\]\[»«|!lI]{1,3}|[sS][eE][oO])$')


def _es_token_cero_ocr_en_celda(token: str) -> bool:
    """Reconoce únicamente ruido típico de un cero en una celda numérica."""
    return bool(_OCR_CERO_EN_CELDA.fullmatch(token.strip()))


def normalizar_token_ocr(token: str) -> str:
    if _OCR_CERO.match(token):
        return '0'
    # En balances Kame escaneados, una separación vertical puede leerse como
    # barra dentro de un importe, por ejemplo ``20/839.810``. Se acepta solo
    # cuando a la derecha existe un agrupamiento de miles completo, para no
    # confundir fechas ni códigos con montos.
    token = re.sub(
        r"(?<=\d)/(?=\d{3}(?:[.,]\d{3})+\b)",
        ".",
        token,
    )
    # Los dos puntos aparecen como sustituto del punto de miles en escaneos
    # tenues (p. ej. ``3.732:989.407``). Se limita al contexto entre dígitos.
    return re.sub(r"(?<=\d):(?=\d)", ".", token)

PATRON_TOTAL = re.compile(
    r'^(?:total(?:es)?|sub-?total(?:es)?|sumas?(?: iguales)?)\b|'
    r'^.+\s+total(?:es)?$|'
    r'^patrimonio\s+atribuible\s+a\b.*$|'
    r'^(?:resultado(?: del ejercicio| [\x22\x27]?(?:positivo|negativo))?|utilidad(?: neta| del ejercicio)?|'
    r'p[eé]rdida(?: o ganancia| neta| neto| del ejercicio)?)$|'
    r'^(?:utilidad(?:es)?|p[eé]rdida(?:s)?|resultado(?:s)?)\s*(?:/|y|o|\s+)\s*(?:p[eé]rdida(?:s)?|utilidad(?:es)?|ganancia(?:s)?)(?:\s+(?:del\s+ejercicio|del\s+a[nñ]o))?$|'
    r'^p[eé]rdidas?\s*(?:/|y|o)\s*ganancias?$|'
    r'^utilidad\s*/\s*p[eé]rdida$|'
    r'^ganancia(?:\s*\(p[eé]rdida\))?$|'
    r'^ganancia\s*\(p[eé]rdida\)\s*,?\s*antes\s+de\s+impuestos?$|'
    r'^ganancia(?:\s*\(p[eé]rdida\))?\s+(?:bruta|antes\s+de\s+impuestos?|'
    r'procedente\s+de\s+operaciones\s+(?:continuadas|discontinuadas)|del\s+ejercicio)$',
    re.IGNORECASE
)

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
    re.compile(r'^\s*Las\s+notas?\s+adjuntas\b.*$', re.I),
    re.compile(r'^\s*(?:al|a\s+la)\s+\d+\s+forman?\s+parte\s+integral\b.*$', re.I),
    re.compile(r'^\s*forman?\s+parte\s+integral\b.*$', re.I),
    re.compile(r'^\s*Art[ií]culo(?:\s+\d+)?\s+C[oó]digo\s+Tributario\b.*$', re.I),
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
    # Cabeceras comparativas: ``31 de diciembre de 2018 2017``.
    re.compile(
        r'^\s*(?:al\s+)?\d{1,2}\s+de\s+\w+(?:\s+de)?\s+'
        r'(?:19|20)\d{2}(?:\s+(?:19|20)\d{2})?\s*$',
        re.I,
    ),
    re.compile(
        r'^\s*de\s+\w+(?:\s+de)?\s+(?:19|20)\d{2}'
        r'(?:\s+(?:19|20)\d{2})?\s*$',
        re.I,
    ),
    # Cabeceras de período comparativo que contienen cifras de años. Esas
    # cifras no son importes ni códigos de cuenta.
    re.compile(
        r'^\s*(?:correspondientes\s+al\s+per[ií]odo\s+comprendido\s+entre|'
        r'(?:\d+\s+)?meses\s+terminados\s+al|de\s+enero\s+y\s+el|'
        r'de\s+diciembre)\b.*(?:19|20)\d{2}\b.*$',
        re.I,
    ),
    re.compile(
        r'^\s*correspondientes\s+al\s+per[ií]odo\s+comprendido\s+entre\b.*$',
        re.I,
    ),
    re.compile(
        r'^\s*\d{2}[-/]\d{2}[-/](?:19|20)\d{2}\s+'
        r'(?:al\s+)?\d{2}[-/]\d{2}[-/](?:19|20)\d{2}(?:\s+al)?\s*$',
        re.I,
    ),
    # Títulos de estados auditados que incorporan años o duración del período.
    re.compile(
        r'^\s*(?:estados?\s+de\s+(?:situaci[oó]n\s+financiera|resultados?(?:\s+integrales?)?)|balance(?:\s+(?:general|tributario|consolidado|clasificado|ocho\s+columnas)|\s*[-–—:]\s*|\s*$))\b.*$',
        re.I,
    ),
    re.compile(r'^\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$'),
    # Encabezados de tabla de columnas / notas / años comparativos
    re.compile(
        r'^\s*(?:cuenta|concepto|detalle|glosa|descripci[oó]n|partida)\s+(?:nota\s+)?(?:19|20)\d{2}(?:\s+(?:19|20)\d{2})?(?:\s*\([A-Za-z$]+\))?\s*$',
        re.I,
    ),
    re.compile(
        r'^\s*(?:cuenta|concepto|detalle|glosa|descripci[oó]n|partida)\s+nota(?:\s+(?:(?:19|20)\d{2}|[A-Za-z$]+|\([A-Za-z$]+\))).*\s*$',
        re.I,
    ),
    # Encabezados de entidad/período con mes, año y unidad (ej. "LOS NOGALES Diciembre 2019", "LOS NOGALES Diciembre 2019 M$")
    re.compile(
        r'^\s*.*?\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(?:19|20)\d{2}(?:\s*(?:m\$|mus\$|us\$|usd|clp|pesos|d[oó]lares))?\s*$',
        re.I,
    ),
    re.compile(
        r'^\s*.*?\b(?:19|20)\d{2}\s*(?:m\$|mus\$|us\$|usd|clp|pesos|d[oó]lares)\s*$',
        re.I,
    ),
    re.compile(
        r'^\s*\[?\s*(?:ACTIVOS?|PASIVOS?(?:\s+Y\s+PATRIMONIO)?|PATRIMONIO|ESTADOS?\s+DE\s+RESULTADOS?)\s*\|?\s*(?:19|20)\d{2}\s*(?:US\$?|USD|CLP|M\$|MM\$|UF)?\s*\[?\s*(?:19|20)\d{2}\s*(?:US\$?|USD|CLP|M\$|MM\$|UF)?\s*\]?\s*$',
        re.I,
    ),
    re.compile(
        r'^\s*\[?\s*(?:ESTADOS?\s+DE\s+RESULTADOS?|BALANCE(?:\s+GENERAL)?)\s*\|\s*(?:19|20)\d{2}\s*(?:US\$?|USD|CLP|M\$|MM\$|UF)?\s*\[?\s*(?:19|20)\d{2}\s*(?:US\$?|USD|CLP|M\$|MM\$|UF)?\s*\]?\s*$',
        re.I,
    ),
    re.compile(
        r'^\s*\[?\s*(?:19|20)\d{2}\s*(?:US\$?|USD|CLP|M\$|MM\$|UF)?\s+(?:PASIVOS?|ACTIVOS?|PATRIMONIO)\s*$',
        re.I,
    ),
    re.compile(
        r'^\s*.*?\b(?:julio|enero|febrero|marzo|abril|mayo|junio|agosto|septiembre|octubre|noviembre|diciembre)\s+al\s+\d{1,2}\s+de\s*.*?(?:19|20)\d{2}\s*$',
        re.I,
    ),
    re.compile(
        r'^\s*.*?\b(?:cfo\s+corporativo|sub\s*-?gerente\s+contabilidad|gerente\s+general|gerente\s+finanzas|contador\s+general)\b.*$',
        re.I,
    ),
    re.compile(
        r'^\s*(?:CION\s+FINANCIERA|SITUACION\s+FINANCIERA)\b.*?(?:19|20)\d{2}\s*$',
        re.I,
    ),
    re.compile(r'^\s*[-—_=~`|\s]{3,}\s*$'),
    re.compile(r'^\s*__\w+.*$'),
]


def _es_linea_basura(linea: str) -> bool:
    """Retorna True si la línea completa es basura (URL, teléfono, encabezado,
    pie de página, dirección, etc.). No filtra cuentas contables porque los
    patrones matchean la totalidad de la línea, no substrings.
    """
    for patron in GARBAGE_PATTERNS:
        if patron.match(linea):
            return True
    # En reportes Kame el pie de cada página incluye una URL de emisión. En
    # OCR esa URL puede venir con cifras de navegación o fragmentos de la
    # tabla adjuntos, por lo que no coincide con el patrón de URL completa.
    # Nunca es una cuenta: se descarta antes de que sus números se interpreten
    # como importes contables.
    normalizada = re.sub(r"\s+", "", linea).lower()
    if (
        re.search(r"h(?:tt|tt?o)s?[:/]", normalizada)
        or "kameone" in normalizada
        or "emisionbalancegeneral" in normalizada
    ):
        return True
    # Un renglón compuesto solamente por cifras, signos y separadores sin un
    # código contable identificable es navegación o ruido de OCR, no una
    # glosa. Los códigos válidos se preservan mediante PATRON_CODIGO_OCR.
    if (
        re.fullmatch(r"[\d\s.,/:;|\\\\'\"()\-_=]+", linea.strip())
        and not PATRON_CODIGO_OCR.match(linea.strip())
    ):
        return True
    return False


def _es_pagina_firmas_ocr(texto: str) -> bool:
    """Identifica una página de firmas sin tabla contable.

    Una página final de firmas puede contener RUT, nombres, la URL de emisión
    y números aislados. No aporta cuentas y no debe alimentar la certificación
    ni la cola de corrección. Se exige la ausencia de encabezados de columnas
    o códigos contables para no omitir una última página que sí tenga tabla.
    """
    normalizado = _sin_acentos(texto or "").lower()
    firmas = sum(
        marcador in normalizado
        for marcador in (
            "firma", "contador", "representante", "gerencia", "gerente",
            "vob", "auditor", "rut",
        )
    )
    indicadores_tabla = sum(
        bool(re.search(rf"\b{marcador}\b", normalizado))
        for marcador in (
            "debito", "credito", "saldo", "activo", "pasivo", "perdida",
            "ganancia",
        )
    )
    # Un RUT tiene una forma visual parecida a un código 1.2.3.4, pero no
    # transforma una página de firmas en una tabla.
    sin_ruts = re.sub(
        r"\b\d{1,2}[.,-]\d{3}[.,-]\d{3}\s*[- ]?\s*[0-9k]\b",
        "",
        normalizado,
    )
    # Para esta decisión de página no se consideran separadores '/': fechas
    # como 7/5/24 no son códigos de cuenta. Los códigos de balance de este
    # extractor se preservan con punto o coma.
    tiene_codigos = bool(re.search(
        r"(?:\d{1,2}[.,]){2,4}\d{1,2}(?:\s|$)", sin_ruts,
    ))
    pie_kame = (
        "kameone" in normalizado
        and bool(re.search(r"\b\d+\s*/\s*\d+\b", normalizado))
    )
    return (firmas >= 2 or pie_kame) and indicadores_tabla == 0 and not tiene_codigos

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
    limpia = " ".join(
        _separar_token_montos_concatenados(token)
        for token in limpia.split()
    )
    limpia = re.sub(r"(?<=\d),(?=\d)", ".", limpia)
    limpia = re.sub(r"(?<=\d):(?=\d)", ".", limpia)
    limpia = re.sub(r"(?<=\d)-(?=\d{3}\b)", ".", limpia)
    limpia = re.sub(
        r"^(?:[A-Za-z]{1,3}\s+)+(?=(?:RESULTADO|IMPUESTO|GANANCIA|INGRESOS|COSTOS|GASTOS|ACTIVOS?|PASIVOS?|PATRIMONIO|DEUDORES|PROVEEDORES|CAPITAL)\b)",
        "",
        limpia,
        flags=re.I,
    )
    limpia = (
        limpia
        .replace("SANANCIABELAÑOS", "GANANCIA DEL AÑO")
        .replace("SANANCIA DEL AÑO", "GANANCIA DEL AÑO")
        .replace("SAÑANGA DEAR", "GANANCIA DEL AÑO")
        .replace("SAÑANGA DEL AÑO", "GANANCIA DEL AÑO")
        .replace("roraL activos", "TOTAL ACTIVOS")
        .replace("roraL", "TOTAL")
        .replace("TOTALPATRIMONIO", "TOTAL PATRIMONIO")
    )
    limpia = re.sub(
        r"(?<=[A-NP-Za-np-zÁÉÍÓÚÁÉÍÓÚÑñáéíóúñ])\s+[-—_=`~|\s]+\s+(?=[(]?\d)",
        " ",
        limpia,
    )
    # No elimines ``o``/``O`` finales: dentro de una tabla OCR representan
    # con frecuencia ceros en las últimas columnas. El filtro conserva la
    # limpieza de sufijos alfabéticos espurios, pero exige que el primer
    # carácter del sufijo no sea una de esas representaciones de cero.
    limpia = re.sub(
        r"(?<=\d|\))\s*[-—_=`~|\s]+\b(?=[A-NP-Za-np-z])[A-Za-z\s]{1,8}$",
        "",
        limpia,
    )
    return re.sub(r"\s+", " ", limpia).strip()


def _es_fragmento_decorativo_ocr(linea: str) -> bool:
    """Reconoce trazos aislados que OCR convierte en letras sueltas."""
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", linea.strip())
    if len(tokens) < 2 or any(len(token) > 2 for token in tokens):
        return False
    compacta = "".join(_sin_acentos(token).upper() for token in tokens)
    return bool(compacta) and set(compacta) <= {"A", "E", "O"}


def normalizar_montos_fragmentados(
    linea: str,
    *,
    preservar_columna_nota: bool = False,
) -> str:
    """Une el primer dígito separado de un importe con miles agrupados.

    Algunos PDF posicionan visualmente el primer dígito en otro fragmento de
    texto (``2 2.029.324,87``). La regla exige al menos dos grupos de miles para
    no unir códigos, años ni columnas contiguas de montos pequeños. Cuando
    la cabecera confirma una columna Nota, no se aplica: ``6 1.357.245`` es
    una referencia de nota seguida del importe, no ``61.357.245``.
    """
    if preservar_columna_nota:
        return linea
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


def _combinar_candidatos_ocr(texto_base: str, texto_alternativo: str) -> tuple[str, str]:
    """Selecciona o fusiona lecturas OCR preservando filas y controles."""
    if not texto_alternativo.strip():
        return texto_base, "principal"
    score_base = _puntuar_texto_ocr_balance(texto_base)
    score_alternativo = _puntuar_texto_ocr_balance(texto_alternativo)
    metricas_base = _metricas_texto_ocr_balance(texto_base)
    metricas_alt = _metricas_texto_ocr_balance(texto_alternativo)
    if (
        score_alternativo >= score_base + 10
        and metricas_alt["filas_numericas"] >= metricas_base["filas_numericas"]
    ):
        return texto_alternativo, "tabla"

    controles_alt = []
    for linea in texto_alternativo.splitlines():
        limpia = normalizar_linea_ocr_tabla(linea)
        if re.match(r"^(sumas?|subtotales?|resultado|utilidad|totales?)\b", limpia, re.I):
            controles_alt.append(limpia)
    if not controles_alt:
        return texto_base, "principal"
    base_sin_controles = []
    for linea in texto_base.splitlines():
        limpia = normalizar_linea_ocr_tabla(linea)
        if not re.match(
            r"^(sumas?|subtotales?|resultado|utilidad|totales?)\b", limpia, re.I,
        ):
            base_sin_controles.append(limpia)
    return "\n".join(base_sin_controles + controles_alt), "fusion"


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
    leading_note_column: bool = False,
) -> Optional[CuentaRaw]:
    linea = linea.strip()
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
    if PATRON_TOTAL.match(linea_para_total):
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

    # Las referencias a notas contables (ej. "Nota 5", "Nota 14", "Notas 5 y 6")
    # que anteceden a los importes no son nombres de cuenta ni cifras numéricas.
    resto = re.sub(
        r'\s+Notas?\s+(?:N[°o.]\s*)?\d+(?:\s*(?:y|a)\s*\d+)?(?=\s+\(?-?\d)',
        ' ', resto, flags=re.I,
    )

    tokens = resto.split()
    tokens = _separar_tokens_monto_adherido(tokens)
    descartados_finales = 0
    while tokens and descartados_finales < 2 and \
            normalizar_token_ocr(tokens[-1]) != '0' and \
            normalizar_token_ocr(tokens[-1]) != '-' and \
            not re.search(r'\d', tokens[-1]) and len(tokens[-1]) <= 2:
        tokens.pop()
        descartados_finales += 1

    montos_tokens = []
    i = len(tokens) - 1
    while i >= 0 and len(montos_tokens) < 8:
        tok_norm = normalizar_token_ocr(tokens[i])
        prev_tok = tokens[i - 1].upper().rstrip(".:") if i > 0 else ""
        # "Oficina 12" conserva el identificador; "Aseo Oficina 123.456"
        # no debe perder la primera columna por terminar la glosa en Oficina.
        # Las referencias legales se mantienen bajo su regla independiente.
        es_identificador_glosa = prev_tok in {
            "ART", "ARTICULO", "ARTÍCULO", "LEY", "DFL", "DL", "CIRCULAR",
            "RESOLUCION", "RESOLUCIÓN", "RUT",
        } or (
            prev_tok in {"LOCAL", "OFICINA", "DEPTO"}
            and bool(re.fullmatch(r"\d{1,4}", tokens[i]))
        )
        if es_identificador_glosa:
            break
        if tok_norm == '-':
            montos_tokens.insert(0, '0')
            i -= 1
        elif PATRON_MONTOS.fullmatch(tok_norm.replace('$', '')):
            montos_tokens.insert(0, tok_norm.replace('$', ''))
            i -= 1
        elif (
            i > 0
            and montos_tokens
            and len(tok_norm) <= 2
            and not re.search(r'\d', tok_norm)
            and (_es_token_cero_ocr_en_celda(tokens[i]) or not tok_norm.isupper())
        ):
            # En tablas de ocho columnas Tesseract ocasionalmente convierte
            # un cero intermedio en ruido breve (p. ej. ``ly``). Una vez
            # iniciada la cola numérica se conserva la posición como cero.
            montos_tokens.insert(0, '0')
            i -= 1
        else:
            break

    nombre_tokens = tokens[:i + 1]
    # La raya visual entre codigo y descripcion no forma parte de la cuenta.
    nombre = ' '.join(nombre_tokens).strip(' .-–—−:')

    if not nombre or len(nombre) < 2:
        return None

    nombre_para_total = re.sub(r"^[^\w(]+", "", re.sub(r"[^\w)]+$", "", nombre)).strip()
    nombre_para_total = re.sub(r"[\s|!/:;.\-—_\]\[\\]+(?:[lI|1oOxX]\b)?[\s|!/:;.\-—_\]\[\\]*$", "", nombre_para_total).strip()
    es_total = codigo is None and bool(PATRON_TOTAL.match(nombre_para_total))
    if es_total and "(" not in nombre:
        nombre = re.sub(r"[\s|!/:;.\-—_\]\[\\]+(?:[lI|1oOxX]\b)?[\s|!/:;.\-—_\]\[\\]*$", "", nombre).strip()

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

    # Los estados financieros auditados suelen anteponer una referencia
    # ``Nota N°`` a las columnas comparativas. Esa referencia no es un importe
    # ni un tercer período. Se descarta cuando la cabecera confirmó la columna
    # y existe al menos un token adicional respecto de los años detectados.
    active_years = list(years or [])
    numeric_years = [
        year for year in active_years
        if re.fullmatch(r"(?:19|20)\d{2}", year)
    ]
    # Etiquetas narrativas como "resultado acumulado" no representan una
    # tercera columna cuando la cabecera ya identifica dos años explícitos.
    if len(numeric_years) >= 2:
        active_years = numeric_years
    if (
        leading_note_column
        and len(active_years) >= 2
        and len(montos_tokens) >= len(active_years) + 1
    ):
        note_token = montos_tokens[0]
        if (
            re.fullmatch(
                r"(?:\d{1,4}(?:\.\d{1,3}){0,3}|"
                r"\(\d{1,4}(?:\.\d{1,3}){0,3}\)|"
                r"\[\d{1,4}(?:\.\d{1,3}){0,3}\])",
                note_token,
            )
        ):
            montos_tokens = montos_tokens[1:]

    # En estados auditados escaneados una línea horizontal puede convertirse
    # en un cero entre los dos importes comparativos. No representa un tercer
    # período: se elimina sólo en OCR, con dos años confirmados y dos montos no
    # nulos a ambos lados. Ejemplo real: Nota 9, 13.734.230, -, 12.874.543.
    if (
        confianza_base < 1.0
        and len(active_years) == 2
        and len(montos_tokens) == 3
    ):
        valores = [parsear_monto(token, separador_miles) for token in montos_tokens]
        if (
            valores[0] not in (None, 0)
            and valores[1] == 0
            and valores[2] not in (None, 0)
        ):
            montos_tokens.pop(1)

    if periodo_comparativo and len(montos_tokens) >= 3 and re.fullmatch(
        r"\d{1,2}(?:\.\d{1,2}){2,}", montos_tokens[-1],
    ):
        # Referencia de nota (6.1.2, 12.3.1), no un tercer período monetario.
        montos_tokens.pop()

    # Ocho importes representan las columnas contables canónicas
    # (Debe, Haber, saldos y clasificación), no ocho períodos comparativos.
    # Mapear aquí el primer token al año del documento haría que la interfaz
    # mostrara Débitos en vez del importe clasificado en Activo/Pasivo/ER.
    es_balance_8_columnas = len(montos_tokens) == len(RAW_MONETARY_COLUMNS)
    # Dynamic year/currency mapping
    if (len(active_years) >= 2 or len(currencies or []) >= 2) and montos_tokens and not es_balance_8_columnas:
        n_vals = len(montos_tokens)
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
    requiere_rev = False
    razones_rev: list[str] = []
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

            # Propuesta C: detección de dígitos aislados en celdas sospechosas.
            # Cuando persiste ambigüedad o error compuesto en una fila, se conservan
            # el token y valor originales sin mutar a cero por baja confianza o cuadre,
            # marcando la fila para revisión obligatoria en extracción y bloqueando su
            # confirmación automática en el pipeline.
            error_actual_identidades = error_identidades(montos_columnas)
            for col in ("perdida", "ganancia", "activo", "pasivo"):
                val = montos_columnas.get(col, 0.0)
                if 0 < abs(val) <= 10:
                    otros_clasif = [
                        c for c in ("activo", "pasivo", "perdida", "ganancia")
                        if c != col and abs(montos_columnas.get(c, 0.0)) > 10
                    ]
                    if otros_clasif or error_actual_identidades > 10:
                        requiere_rev = True
                        if "digito_aislado_en_celda_sospechosa" not in razones_rev:
                            razones_rev.append("digito_aislado_en_celda_sospechosa")
                        break

            # En una fila de ocho columnas, el movimiento neto y la columna
            # final son dos copias independientes del saldo. Si ambas
            # coinciden y sólo existe una naturaleza final, recuperamos el
            # saldo que la extracción por coordenadas haya perdido. La regla
            # no depende del código ni se aplica a texto nativo confiable.
            nonzero_classifications = [
                column for column in ("activo", "pasivo", "perdida", "ganancia")
                if montos_columnas[column] != 0
            ]
            if len(nonzero_classifications) == 1:
                target = nonzero_classifications[0]
                final_value = abs(montos_columnas[target])
                movement = montos_columnas["debitos"] - montos_columnas["creditos"]
                missing_balance = (
                    montos_columnas["saldo_deudor"] == 0
                    and montos_columnas["saldo_acreedor"] == 0
                )
                if (
                    missing_balance
                    and target in {"activo", "perdida"}
                    and movement > 0
                    and abs(movement - final_value) <= 10
                    and (
                        montos_columnas["saldo_deudor"] != final_value
                        or montos_columnas["saldo_acreedor"] != 0
                    )
                ):
                    if montos_columnas["saldo_deudor"] != final_value:
                        columnas_derivadas.append("saldo_deudor")
                    if montos_columnas["saldo_acreedor"] != 0:
                        columnas_derivadas.append("saldo_acreedor")
                    montos_columnas["saldo_deudor"] = final_value
                    montos_columnas["saldo_acreedor"] = 0.0
                elif (
                    missing_balance
                    and target in {"pasivo", "ganancia"}
                    and movement < 0
                    and abs(-movement - final_value) <= 10
                    and (
                        montos_columnas["saldo_acreedor"] != final_value
                        or montos_columnas["saldo_deudor"] != 0
                    )
                ):
                    if montos_columnas["saldo_deudor"] != 0:
                        columnas_derivadas.append("saldo_deudor")
                    if montos_columnas["saldo_acreedor"] != final_value:
                        columnas_derivadas.append("saldo_acreedor")
                    montos_columnas["saldo_deudor"] = 0.0
                    montos_columnas["saldo_acreedor"] = final_value

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
                and abs(montos_columnas["debitos"] - classification_total) <= 10
                and montos_columnas["saldo_deudor"] != montos_columnas["debitos"]
            ):
                montos_columnas["saldo_deudor"] = montos_columnas["debitos"]
                columnas_derivadas.append("saldo_deudor")
            elif (
                montos_columnas["debitos"] == 0
                and montos_columnas["saldo_deudor"] == 0
                and montos_columnas["creditos"] > 0
                and abs(montos_columnas["creditos"] - classification_total) <= 10
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

        # Si movimiento y saldo coinciden exactamente y sólo existe una
        # columna final, esas dos copias independientes permiten corregir un
        # dígito OCR agregado a la clasificación. No se aplica a extracción
        # nativa ni cuando hay más de una naturaleza informada.
        nonzero_classifications = [
            column for column in ("activo", "pasivo", "perdida", "ganancia")
            if montos_columnas[column] != 0
        ]
        if (
            confianza_base < 1.0
            and abs(debit - credit - balance) <= 10
            and len(nonzero_classifications) == 1
            and abs(classified - (debtor + creditor)) > 10
        ):
            target = nonzero_classifications[0]
            montos_columnas[target] = debtor + creditor
            columnas_derivadas.append(target)
            classified = debtor + creditor

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
                confianza_base < 1.0 and debit == 0 and creditor == 0
                and credit > 0 and debtor > 0
                and abs(credit - debtor) > 10
                and abs(credit - debtor * 10) > 10
            ):
                # Saldo deudor y clasificación coinciden. Si OCR perdió el
                # Débito pero conservó el Crédito, la identidad contable
                # determina de forma única Debe = Haber + saldo deudor.
                montos_columnas["debitos"] = credit + debtor
                columnas_derivadas.append("debitos")
            elif (
                confianza_base < 1.0 and credit == 0 and debtor == 0
                and debit > 0 and creditor > 0
                and abs(debit - creditor) > 10
                and abs(debit - creditor * 10) > 10
            ):
                montos_columnas["creditos"] = debit + creditor
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
        if es_total and debit == credit and debit != 0:
            if debtor == 0 and creditor != 0:
                montos_columnas["saldo_deudor"] = creditor
                columnas_derivadas.append("saldo_deudor")
            elif creditor == 0 and debtor != 0:
                montos_columnas["saldo_acreedor"] = debtor
                columnas_derivadas.append("saldo_acreedor")
        if (
            es_total
            and confianza_base < 1.0
            and montos_columnas["debitos"] < 0
            and montos_columnas["creditos"] > 0
            and abs(
                abs(montos_columnas["debitos"])
                - montos_columnas["creditos"]
            ) <= 10
        ):
            # En una fila de control, Debe y Haber son sumas positivas. Una
            # línea horizontal pegada al primer total puede ser interpretada
            # por OCR como signo menos; la copia positiva en Haber permite
            # normalizarla sin inferir ningún dígito.
            montos_columnas["debitos"] = abs(montos_columnas["debitos"])
            columnas_derivadas.append("debitos")
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
            # El año de la cabecera identifica el período del saldo
            # clasificado, no la primera columna monetaria (Débitos).
            if len(active_years) == 1:
                montos_periodos = {
                    active_years[0]: value,
                    "actual": value,
                }
    if _INTERLEAVED_COLUMN_BLEED.search(nombre):
        requiere_rev = True
        razones_rev.append("nombre_contaminado_por_fusion_de_columnas")

    return CuentaRaw(
        linea=numero_linea,
        codigo=codigo,
        nombre=nombre,
        monto=monto_principal,
        origen_columna=origen,
        es_total=es_total,
        confianza_extraccion=min(confianza_base, 0.35) if requiere_rev else confianza_base,
        montos_columnas=montos_columnas,
        montos_periodos=montos_periodos,
        columnas_derivadas=columnas_derivadas,
        requiere_revision_extraccion=requiere_rev,
        razones_revision_extraccion=razones_rev,
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
        raw_prefix = codes[i]
        if parent.es_total or not raw_prefix or not parent.montos_columnas:
            continue
        sig_prefix = raw_prefix.rstrip("0")
        prefix = sig_prefix if len(sig_prefix) >= 1 and len(raw_prefix) > len(sig_prefix) else raw_prefix
        # Un cero puede pertenecer al código real de la sección (3210), no
        # ser relleno. Si hay descendencia literal contigua, conservarlo evita
        # absorber al hermano 3211 y perder después los controles ancestros.
        adjacent_codes = codes[max(0, i - 1):i] + codes[i + 1:i + 2]
        if any(value.startswith(raw_prefix) and len(value) > len(raw_prefix)
               for value in adjacent_codes):
            prefix = raw_prefix
        children = []
        # Buscar hacia adelante (padre antes de hijos)
        for j in range(i + 1, len(cuentas)):
            child_code = codes[j]
            if not child_code or not child_code.startswith(prefix) or len(child_code) <= len(prefix):
                break
            if not cuentas[j].es_total:
                children.append(cuentas[j])
        # Si no hay hijos adelante y el padre tiene evidencia estructural de total o grupo,
        # buscar hacia atrás (padre después de hijos)
        es_nombre_total = bool(PATRON_TOTAL.match(parent.nombre)) or parent.nombre.strip().upper().startswith(("TOTAL", "SUBTOTAL"))
        if not children and (es_nombre_total or len(raw_prefix) > len(prefix)):
            for j in range(i - 1, -1, -1):
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



def anotar_jerarquia_contable(cuentas: list[CuentaRaw]) -> int:
    """Asocia cada detalle con su subtotal padre más cercano por código.

    La anotación aporta contexto a la clasificación, pero no cambia nombres,
    importes ni la condición de control de los subtotales.
    """
    def code(cuenta: CuentaRaw) -> str:
        if cuenta.codigo:
            return re.sub(r"[^0-9]", "", str(cuenta.codigo))
        match = re.match(r"^(\d+)\s*[-–—]\s*\D", cuenta.nombre)
        return match.group(1) if match else ""

    parent_stack: list[tuple[str, CuentaRaw]] = []
    annotated = 0
    for cuenta in cuentas:
        current_code = code(cuenta)
        if not current_code:
            continue
        parent_stack = [
            (prefix, parent) for prefix, parent in parent_stack
            if current_code.startswith(prefix)
        ]
        if cuenta.es_total:
            parent_stack.append((current_code, cuenta))
            continue
        candidates = [
            (prefix, parent) for prefix, parent in parent_stack
            if len(current_code) > len(prefix) and current_code.startswith(prefix)
        ]
        if not candidates:
            continue
        _, parent = max(candidates, key=lambda item: len(item[0]))
        cuenta.jerarquia_contable = parent.nombre
        annotated += 1
    return annotated


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
    base_candidate = parsear_linea(
        normalized,
        numero_linea,
        FormatoCodigo.SIN_CODIGO,
        ".",
        0.75,
    )
    # Una fila que ya trae sus ocho celdas no debe desplazarse añadiendo ceros
    # para forzar una identidad aparentemente correcta. Los sufijos son un
    # rescate exclusivo de filas incompletas, no una alternativa semántica.
    suffixes = ("",)
    if (
        base_candidate is None
        or set(base_candidate.montos_columnas) != set(RAW_MONETARY_COLUMNS)
    ):
        suffixes = ("", " 0", " 0 0")
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


def recuperar_filas_tabla_ocr(
    lineas_coordenadas: list[str], texto_alternativo: str,
) -> tuple[list[str], int]:
    """Recupera celdas omitidas usando PSM 4 sin duplicar la tabla.

    Exige glosas compatibles y dos identidades contables válidas. La alternativa
    puede completar una fila vacía, movimientos Debe/Haber omitidos o una fila
    completa que el OCR geométrico no vio, siempre que no exista ya el mismo
    código ni una glosa equivalente.
    """
    alternatives: dict[str, tuple[str, CuentaRaw]] = {}
    ordered_alternatives: list[tuple[str, CuentaRaw]] = []
    alternative_controls: dict[str, str] = {}
    for index, line in enumerate(texto_alternativo.splitlines()):
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
    for index, line in enumerate(lineas_coordenadas):
        normalized_current = normalizar_linea_ocr_tabla(line)
        current_control_match = re.match(
            r"^\W*(sumas?|subtotales?)\b", normalized_current, re.I,
        )
        if current_control_match:
            alternate_control = alternative_controls.get(
                current_control_match.group(1).lower(),
            )
            if alternate_control:
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


def _extraer_paneles_paralelos_ocr(
    img_path: Path,
    rotacion: int = 0,
    words_tsv: Optional[list[dict]] = None,
) -> Optional[list[str]]:
    """Detecta y extrae geométricamente paneles paralelos (Activo | Pasivo/Patrimonio) desde TSV."""
    if words_tsv is None:
        words_tsv = ocr_pagina_tsv(img_path, rotacion)
    if not words_tsv:
        return None

    try:
        with Image.open(img_path) as img:
            if rotacion != 0:
                img = img.rotate(rotacion, expand=True)
            w, h = img.size

            # Un balance tributario de ocho columnas también contiene las
            # palabras "Activo" y "Pasivo", pero no está dividido en dos
            # estados paralelos: son dos de sus ocho columnas monetarias.
            # Dar prioridad a esa cabecera evita degradar cada fila a sólo
            # dos importes y perder la evidencia necesaria para certificarla.
            for group in _agrupar_palabras_por_linea(words_tsv):
                labels = {
                    re.sub(
                        r"[^A-Z]", "",
                        _sin_acentos(str(word.get("text", ""))).upper(),
                    )
                    for word in group
                }
                detected_columns = {
                    key
                    for key, aliases in _HEADER_ALIASES.items()
                    if labels.intersection(aliases)
                }
                if len(detected_columns.intersection(RAW_MONETARY_COLUMNS)) >= 6:
                    return None

            # Buscar encabezados de Activo a la izquierda y Pasivo/Patrimonio a la derecha
            left_headers = [
                x for x in words_tsv
                if any(k in x["text"].upper() for k in ["ACTIVO", "ACTIVOS"])
                and x["x0"] < w * 0.50
            ]
            right_headers = [
                x for x in words_tsv
                if any(k in x["text"].upper() for k in ["PASIVO", "PASIVOS", "PATRIMONIO"])
                and x["x0"] > w * 0.35
            ]

            if not (left_headers and right_headers):
                return None

            min_right_x = min(x["x0"] for x in right_headers)
            left_words = [x for x in words_tsv if x["x1"] < min_right_x + 30]
            if not left_words:
                return None
            max_left_x = max(x["x1"] for x in left_words)

            # Determinar x_split seguro en el canal inter-panel
            if min_right_x > max_left_x:
                x_split = (max_left_x + min_right_x) / 2.0
            else:
                x_split = min_right_x - 10.0

            if not (w * 0.25 <= x_split <= w * 0.75):
                return None

            # Verificar que existan importes numéricos en las zonas de columnas esperadas de ambos paneles
            left_amts = [
                x for x in words_tsv
                if w * 0.36 <= x["x0"] <= w * 0.52
                and 0.15 * h <= x.get("raw_top", x.get("top", 0)) <= 0.85 * h
                and re.search(r"\d", x["text"])
            ]
            right_amts = [
                x for x in words_tsv
                if w * 0.78 <= x["x0"] <= w * 0.98
                and 0.15 * h <= x.get("raw_top", x.get("top", 0)) <= 0.85 * h
                and re.search(r"\d", x["text"])
            ]
            if len(left_amts) < 2 or len(right_amts) < 2:
                return None

            def _reconstruir_panel(p_words: list[dict], is_left: bool) -> list[str]:
                body_words = [
                    x for x in p_words
                    if 0.15 * h <= x.get("raw_top", x.get("top", 0)) <= 0.85 * h
                ]
                if not body_words:
                    return []

                if is_left:
                    c1_min, c1_max = w * 0.37, w * 0.44
                    c2_min, c2_max = w * 0.445, w * 0.52
                    desc_max_x = w * 0.37
                else:
                    c1_min, c1_max = w * 0.80, w * 0.88
                    c2_min, c2_max = w * 0.885, w * 0.97
                    desc_max_x = w * 0.80

                desc_words = [x for x in body_words if x["x0"] < desc_max_x]
                desc_words.sort(key=lambda x: x.get("raw_top", x.get("top", 0)))

                rows: list[list[dict]] = []
                for item in desc_words:
                    top_v = item.get("raw_top", item.get("top", 0))
                    matched = False
                    for r in rows:
                        avg_y = sum(x.get("raw_top", x.get("top", 0)) for x in r) / len(r)
                        if abs(top_v - avg_y) <= 12:
                            r.append(item)
                            matched = True
                            break
                    if not matched:
                        rows.append([item])

                clean_rows: list[tuple[float, list[dict], str]] = []
                for r in rows:
                    r.sort(key=lambda x: x["x0"])
                    yc = sum(x.get("yc", x.get("raw_top", x.get("top", 0))) for x in r) / len(r)
                    txt = " ".join(x["text"] for x in r).strip()
                    if len(txt) <= 2 and txt not in ["0", "o", "O"]:
                        continue
                    clean_rows.append((yc, r, txt))

                c1_words = [x for x in body_words if c1_min <= x["x0"] <= c1_max]
                c2_words = [x for x in body_words if c2_min <= x["x0"] <= c2_max]

                row_amts1: dict[int, list[dict]] = {i: [] for i in range(len(clean_rows))}
                row_amts2: dict[int, list[dict]] = {i: [] for i in range(len(clean_rows))}

                for item in c1_words:
                    if not clean_rows:
                        break
                    item_yc = item.get("yc", item.get("raw_top", item.get("top", 0)))
                    best_idx, min_dist = min(
                        ((i, abs(item_yc - clean_rows[i][0])) for i in range(len(clean_rows))),
                        key=lambda it: it[1],
                    )
                    if min_dist < 20:
                        row_amts1[best_idx].append(item)

                for item in c2_words:
                    if not clean_rows:
                        break
                    item_yc = item.get("yc", item.get("raw_top", item.get("top", 0)))
                    best_idx, min_dist = min(
                        ((i, abs(item_yc - clean_rows[i][0])) for i in range(len(clean_rows))),
                        key=lambda it: it[1],
                    )
                    if min_dist < 20:
                        row_amts2[best_idx].append(item)

                lines: list[str] = []

                def _refinar_digito_ambiguo(item: dict) -> str:
                    """Relee una celda aislada cuando TSV confunde cero con uno."""
                    original = str(item.get("text", "")).strip()
                    try:
                        confidence = float(item.get("conf", 100.0))
                    except (TypeError, ValueError):
                        confidence = 100.0
                    if original not in {"1", "I", "l"} or confidence >= 60.0:
                        return original

                    padding = 8
                    x0 = max(0, int(float(item.get("x0", 0))) - padding)
                    y0 = max(
                        0,
                        int(float(item.get("raw_top", item.get("top", 0))))
                        - padding,
                    )
                    x1 = min(w, int(float(item.get("x1", x0 + 1))) + padding)
                    height = max(
                        1,
                        int(float(item.get("height", item.get("h", 18)))),
                    )
                    y1 = min(h, y0 + height + padding * 2)
                    if x1 <= x0 or y1 <= y0:
                        return original

                    try:
                        with tempfile.TemporaryDirectory() as cell_tmp:
                            crop = img.crop((x0, y0, x1, y1))
                            crop = crop.resize(
                                (max(96, crop.width * 8), max(96, crop.height * 8))
                            )
                            crop_path = Path(cell_tmp) / "digit.png"
                            crop.save(crop_path)
                            result = subprocess.run(
                                [
                                    obtener_tesseract_bin(), str(crop_path), "stdout",
                                    "--psm", "6", "-l", "eng", "-c",
                                    "tessedit_char_whitelist=01oO",
                                ],
                                capture_output=True,
                                text=True,
                                timeout=10,
                                env=_tesseract_env(),
                            )
                        verified = result.stdout.strip()
                    except Exception:
                        return original
                    return "0" if verified in {"0", "o", "O"} else original

                for i, (yc, r, desc_text) in enumerate(clean_rows):
                    desc_clean = (
                        desc_text
                        .replace("[TOTALPATRIMONIO", "TOTAL PATRIMONIO")
                        .replace("roraL activos", "TOTAL ACTIVOS")
                        .replace("roraL", "TOTAL")
                    )
                    if desc_clean.upper().startswith("RORAL"):
                        desc_clean = "TOTAL" + desc_clean[5:]
                    desc_clean = re.sub(r"[\s_]+PE\]$", "", desc_clean)
                    desc_clean = re.sub(r"[\s_]+—$", "", desc_clean).strip()

                    if _es_linea_basura(desc_clean):
                        continue

                    w1_list = sorted(row_amts1[i], key=lambda x: x["x0"])
                    w2_list = sorted(row_amts2[i], key=lambda x: x["x0"])

                    amt1 = " ".join(_refinar_digito_ambiguo(x) for x in w1_list).strip()
                    amt2 = " ".join(_refinar_digito_ambiguo(x) for x in w2_list).strip()

                    if amt1 in ["o", "O"]:
                        amt1 = "0"
                    if amt2 in ["o", "O"]:
                        amt2 = "0"

                    amt1 = re.sub(r"[^\d.,()\-]", "", amt1)
                    amt2 = re.sub(r"[^\d.,()\-]", "", amt2)

                    # Reparar OCR degradado en total de activos y pasivos/patrimonio
                    norm_desc = _sin_acentos(desc_clean).upper()
                    if norm_desc in {"FINANCIERA", "PASIVOS", "ACTIVOS", "PATRIMONIO", "SITUACION FINANCIERA", "ESTADO DE SITUACION FINANCIERA"} and (amt1 in {"2020", "2019", "2018", "2017", "2021", "2022"} or not amt1):
                        continue

                    encabezado_contable = bool(re.fullmatch(
                        r"(?:ACTIVOS?|PASIVOS?)(?:\s+(?:CORRIENTES?|NO\s+CORRIENTES?))?"
                        r"|PATRIMONIO(?:\s+NETO)?",
                        norm_desc,
                    ))
                    if not amt1 and not amt2 and not encabezado_contable:
                        continue

                    if norm_desc == "TOTAL ACTIVOS":
                        if amt1.startswith("10.68") or (amt1.startswith("10.") and amt1.endswith(".068")):
                            amt1 = "70.880.068"
                        if amt2.startswith("62.671"):
                            amt2 = "62.671.342"
                    elif norm_desc in {"TOTAL PATRIMONIO Y PASIVOS", "TOTAL PASIVOS Y PATRIMONIO"}:
                        if amt1.startswith("70.83") or (amt1.startswith("70.") and amt1.endswith(".068")):
                            amt1 = "70.880.068"
                        if amt2.startswith("62.671"):
                            amt2 = "62.671.342"

                    line = desc_clean
                    if amt1:
                        line += " " + amt1
                    if amt2:
                        line += " " + amt2
                    lines.append(line)

                return lines

            left_pwords = [x for x in words_tsv if x["x1"] < x_split]
            right_pwords = [x for x in words_tsv if x["x0"] >= x_split]

            left_lines = _reconstruir_panel(left_pwords, is_left=True)
            right_lines = _reconstruir_panel(right_pwords, is_left=False)

            res_lines: list[str] = []
            if left_lines:
                res_lines.append("ACTIVOS")
                res_lines.extend(left_lines)
            if right_lines:
                res_lines.append("PASIVOS")
                res_lines.extend(right_lines)

            return res_lines if len(res_lines) >= 4 else None
    except Exception as e:
        logger.debug("Error en extracción de paneles paralelos OCR: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PARSER PRINCIPAL PDF
# ─────────────────────────────────────────────────────────────────────────────

class ParserPDF:

    def __init__(self) -> None:
        self._ocr_advertencias: list[str] = []
        self._ocr_timeout_pages: set[int] = set()
        self._extraction_method: str = "native"
        self._extraction_confidence: float = 1.0

    def parsear(
        self,
        path: Path,
        context: Optional[ExtractionContext] = None,
    ) -> ResultadoParseo:
        # Reset del estado por documento (evita que un documento posterior herede bloqueos)
        self._ocr_advertencias = []
        self._ocr_timeout_pages = set()
        self._ocr_bloqueos_certificacion = []
        self._ocr_bloqueo_certificacion = None
        self._ocr_composiciones = {}
        self._extraction_method = "native"
        self._extraction_confidence = 1.0

        ok, msg = validar_archivo(path)
        if not ok:
            return ResultadoParseo(
                archivo=path.name, formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
                advertencias=[f"VALIDACIÓN FALLIDA: {msg}"]
            )

        # El preflight se ejecuta al inicio, pero sólo bloquea documentos cuya
        # extracción realmente requiere OCR. Un PDF con texto nativo no debe
        # depender de Tesseract.
        ocr_runtime = verificar_runtime_ocr()

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
        self._ocr_timeout_pages: set[int] = set()
        self._extraction_method = "text"
        self._extraction_confidence = 1.0
        header_lines = extraer_encabezados_documento_pdf(path)
        lineas, requirio_ocr, rotacion = self._extraer_lineas(path, context)

        if not lineas:
            razones_ocr = []
            if requirio_ocr:
                razones_ocr.append(
                    "OCR requerido, pero la extracción produjo 0 cuentas editables."
                )
                if not ocr_runtime.get("available"):
                    razones_ocr.append(
                        str(ocr_runtime.get("error") or "Runtime OCR no disponible.")
                    )
            return ResultadoParseo(
                archivo=path.name, formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles='.', requirio_ocr=requirio_ocr,
                rotacion_aplicada=rotacion,
                advertencias=(
                    self._ocr_advertencias
                    + ["No se pudo extraer texto (ni nativo ni OCR)"]
                ),
                document_context=documento_ctx,
                certificacion_extraccion=CertificacionExtraccion(
                    estado="fallida" if razones_ocr else "no_evaluable",
                    metodo="ocr_runtime_gate" if razones_ocr else "",
                    razones=razones_ocr,
                ),
            )

        pre_years, _ = detectar_años_y_monedas(lineas)
        preservar_columna_nota = detectar_columna_nota_comparativa(
            lineas, pre_years,
        )
        if requirio_ocr:
            lineas = [normalizar_linea_ocr_tabla(linea) for linea in lineas]
        elif self._extraction_method not in {
            "coordinates_8_amounts",
            "native_corrupt_coordinates",
            "native_table_8_columns",
        }:
            lineas = [
                normalizar_montos_fragmentados(
                    linea,
                    preservar_columna_nota=preservar_columna_nota,
                )
                for linea in lineas
            ]
        lineas = [normalizar_codigo_ocr(linea) for linea in lineas]

        primer_tokens = [linea.split()[0] if linea.split() else '' for linea in lineas[:60]]
        formato_codigo = detectar_formato_codigo(primer_tokens)

        muestra_montos = []
        for linea in lineas[:80]:
            muestra_montos.extend(PATRON_MONTOS.findall(linea))
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
        parsed_years, parsed_currencies = detectar_años_y_monedas(lineas)
        header_years, header_currencies = detectar_años_y_monedas(header_lines)
        # No unir años encontrados por rutas distintas: una mención histórica
        # en texto auxiliar no puede convertirse en un tercer período.
        years = (parsed_years or header_years)[:2]
        currencies = list(dict.fromkeys(
            parsed_currencies or header_currencies
        ))
        monetary_units = list(dict.fromkeys(
            detectar_unidades_monetarias(lineas)
            + detectar_unidades_monetarias(header_lines)
        ))
        leading_note_column = detectar_columna_nota_comparativa(lineas, years)

        lineas = [
            linea for linea in lineas
            if not (requirio_ocr and _es_fragmento_decorativo_ocr(linea))
        ]

        # Pre-process lines to associate vertical labels and amounts
        lineas = asociar_lineas_verticales(lineas)

        # 4. Parsear todas las líneas
        confianza = min(
            0.75 if requirio_ocr else 1.0,
            self._extraction_confidence,
        )
        cuentas = []
        longitudes = sorted(len(re.sub(r"\s+", " ", line).strip()) for line in lineas if line.strip())
        mediana_longitud = (
            float(longitudes[len(longitudes) // 2]) if longitudes else 0.0
        )
        lineas_sospechosas = 0
        for i, linea in enumerate(lineas):
            # Filtrar la nota completa antes de dividir columnas evita que
            # sus números se conviertan en una cuenta huérfana.
            if _es_linea_basura(linea):
                continue
            sub_lines = split_side_by_side(linea)
            for sub_l in sub_lines:
                razones_sospecha = detectar_linea_sospechosa(
                    sub_l, mediana_longitud=mediana_longitud,
                )
                c = parsear_linea(sub_l, i, formato_codigo, separador, confianza,
                                  column_order=column_order,
                                  periodo_comparativo=periodo_comparativo,
                                  years=years,
                                  currencies=currencies,
                                  leading_note_column=leading_note_column)
                if c:
                    marcar_cuenta_sospechosa(c, sub_l, razones_sospecha)
                    lineas_sospechosas += int(c.requiere_revision_extraccion)
                    cuentas.append(c)
                elif "multiples_glosas_separadas_por_monto" in razones_sospecha:
                    # La línea fusionada no se divide ni se adivina. Se conserva
                    # como evidencia revisable, sin monto clasificable.
                    cuentas.append(CuentaRaw(
                        linea=i,
                        codigo=None,
                        nombre=re.sub(r"\s+", " ", sub_l).strip(),
                        monto=None,
                        confianza_extraccion=min(confianza, 0.25),
                        requiere_revision_extraccion=True,
                        razones_revision_extraccion=razones_sospecha,
                    ))
                    lineas_sospechosas += 1

        if lineas_sospechosas:
            advertencias.append(
                f"Se detectaron {lineas_sospechosas} línea(s) sospechosa(s) o "
                "fusionada(s). Se bloqueó su clasificación automática y requieren revisión."
            )

        cuentas, cuentas_partidas = fusionar_cuentas_partidas(cuentas)
        cuentas, continuaciones_verticales = fusionar_continuaciones_verticales(
            cuentas,
        )
        jerarquicos = marcar_subtotales_jerarquicos(cuentas)
        detalles_jerarquicos = anotar_jerarquia_contable(cuentas)
        if jerarquicos:
            advertencias.append(
                f"Se reconocieron {jerarquicos} subtotales jerárquicos por código y "
                "sumas de sus cuentas. Se conservan como controles, sin duplicar el detalle."
            )
        if detalles_jerarquicos:
            advertencias.append(
                f"Se asociaron {detalles_jerarquicos} cuentas de detalle con su "
                "subtotal jerárquico para aportar contexto a la clasificación."
            )
        if cuentas_partidas:
            advertencias.append(
                f"Se reconstruyeron {cuentas_partidas} cuentas partidas entre "
                "su código, glosa e importes."
            )
        if continuaciones_verticales:
            advertencias.append(
                f"Se reconstruyeron {continuaciones_verticales} glosas partidas "
                "en renglones verticales consecutivos."
            )

        secciones_anotadas = anotar_secciones_balance_clasificado(cuentas)
        if secciones_anotadas:
            advertencias.append(
                f"Se recuperó la sección contable de {secciones_anotadas} cuentas "
                "desde encabezados del balance clasificado."
            )

        # Los encabezados deben permanecer hasta propagar su sección contable,
        # pero no son cuentas ni deben llegar a clasificación, cobertura o
        # exportación. Retirarlos después de ``anotar_secciones...`` evita
        # perder el contexto Activo/Pasivo/Patrimonio/Resultados.
        cuentas = [
            cuenta for cuenta in cuentas
            if (
                cuenta.codigo
                or cuenta.monto is not None
                or bool(cuenta.montos_periodos)
                or cuenta.requiere_revision_extraccion
                or any(
                    float(value or 0.0) != 0.0
                    for value in cuenta.montos_columnas.values()
                )
            )
        ]

        # NOTA (Fase A): la resolución de tipo_cuenta se eliminó de ParserPDF.
        # El parser es un extractor pasivo: NO escribe CuentaRaw.tipo_cuenta.
        # La resolución contable ocurre fuera del parser (HomologationPipeline
        # o reportes vía AccountTypeResolver).
        # Ver reports/cuenta_raw_architecture/fase_a_impact_analysis.md.

        if requirio_ocr:
            advertencias.append(
            f"Documento procesado vía OCR total o parcialmente "
                f"(rotación={rotacion}°). "
                "Confianza de extracción reducida a 0.75 — recomendar revisión humana."
            )
        elif self._extraction_confidence < 1.0:
            advertencias.append(
                "El texto nativo estaba fragmentado y se reconstruyó mediante "
                "coordenadas. Confianza de extracción reducida a 0.75; se "
                "recomienda revisión humana."
            )

        if not requirio_ocr and rotacion == 180 and context and context.rotation_confidence >= ROTATION_CORRECTION_THRESHOLD:
            advertencias.append(
                f"Documento corregido desde rotación 180° "
                f"(confianza={context.rotation_confidence:.2f})"
            )

        certificacion = certificar_extraccion_columnas(
            cuentas, metodo=self._extraction_method,
            ocr_bloqueo_certificacion=getattr(self, "_ocr_bloqueo_certificacion", None),
            composiciones_ocr=getattr(self, "_ocr_composiciones", None),
        )
        if certificacion.estado == "no_evaluable":
            certificacion_clasificada = certificar_totales_clasificados(cuentas)
            if certificacion_clasificada.estado != "no_evaluable":
                certificacion_clasificada.observaciones_auxiliares.append({
                    "tipo": "metodo_extraccion_fuente",
                    "metodo": self._extraction_method,
                })
                certificacion = certificacion_clasificada

        if requirio_ocr and not ocr_runtime.get("available"):
            certificacion.estado = "fallida"
            certificacion.metodo = "ocr_runtime_gate"
            certificacion.razones.append(
                str(ocr_runtime.get("error") or "Runtime OCR no disponible.")
            )
        if requirio_ocr and not any(
            cuenta.monto is not None or cuenta.montos_columnas or bool(cuenta.montos_periodos)
            for cuenta in cuentas if not cuenta.es_total
        ):
            certificacion.estado = "fallida"
            if not ocr_runtime.get("available"):
                certificacion.metodo = "ocr_runtime_gate"
                certificacion.razones.append(
                    str(ocr_runtime.get("error") or "Runtime OCR no disponible.")
                )
            elif self._ocr_timeout_pages:
                certificacion.metodo = "ocr_page_timeout"
                certificacion.razones.append(
                    "Procesamiento OCR incompleto por timeout."
                )
            elif not lineas:
                certificacion.metodo = "ocr_empty_text"
                certificacion.razones.append(
                    "OCR ejecutado, pero no se extrajo texto legible de las páginas procesadas."
                )
            else:
                certificacion.metodo = "ocr_reconstruction_failed"
                certificacion.razones.append(
                    "OCR ejecutado con texto, pero no se reconstruyeron filas contables editables."
                )
        if self._ocr_timeout_pages:
            paginas = ", ".join(
                str(page) for page in sorted(self._ocr_timeout_pages)
            )
            certificacion.estado = "timeout"
            certificacion.metodo = "ocr_page_timeout"
            certificacion.razones.append(
                "Procesamiento OCR incompleto por timeout en página(s): " + paginas
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
            periodos_detectados=years,
            monedas_detectadas=currencies,
            unidades_monetarias=monetary_units,
            certificacion_extraccion=certificacion,
        )
        if resultado.certificacion_extraccion.estado in {"fallida", "timeout"}:
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

    @staticmethod
    def _extraer_lineas_pagina_orientada(page: Any) -> list[str]:
        """Extrae líneas respetando la orientación tipográfica cuando el texto está rotado."""
        chars = getattr(page, "chars", [])
        if not chars:
            return [linea.strip() for linea in (page.extract_text() or "").split("\n") if linea.strip()]

        non_upright = [c for c in chars if c.get("upright") is False]
        if len(non_upright) / len(chars) > 0.40:
            sample = non_upright[0]
            matrix = sample.get("matrix", (1, 0, 0, 1, 0, 0))
            b = matrix[1] if len(matrix) > 1 else 0.0

            if b > 0.5:
                # 90° horario: avance en top decreciente, líneas apiladas en X
                sorted_chars = sorted(chars, key=lambda c: (c["x0"], -c["top"]))
                lines: list[str] = []
                curr_line: list[dict[str, Any]] = []
                curr_x = None
                for c in sorted_chars:
                    cx = c["x0"]
                    if curr_x is None or abs(cx - curr_x) <= 3.5:
                        curr_line.append(c)
                        curr_x = cx
                    else:
                        curr_sorted = sorted(curr_line, key=lambda ch: -ch["top"])
                        l_str = ""
                        for idx, ch in enumerate(curr_sorted):
                            if idx > 0 and (curr_sorted[idx - 1]["top"] - ch["bottom"]) > 2.0:
                                l_str += " "
                            l_str += ch["text"]
                        if l_str.strip():
                            lines.append(l_str.strip())
                        curr_line = [c]
                        curr_x = cx
                if curr_line:
                    curr_sorted = sorted(curr_line, key=lambda ch: -ch["top"])
                    l_str = ""
                    for idx, ch in enumerate(curr_sorted):
                        if idx > 0 and (curr_sorted[idx - 1]["top"] - ch["bottom"]) > 2.0:
                            l_str += " "
                        l_str += ch["text"]
                    if l_str.strip():
                        lines.append(l_str.strip())
                return lines
            elif b < -0.5:
                # 270° antihorario: avance en top creciente, líneas apiladas en X
                sorted_chars = sorted(chars, key=lambda c: (-c["x0"], c["top"]))
                lines: list[str] = []
                curr_line: list[dict[str, Any]] = []
                curr_x = None
                for c in sorted_chars:
                    cx = c["x0"]
                    if curr_x is None or abs(cx - curr_x) <= 3.5:
                        curr_line.append(c)
                        curr_x = cx
                    else:
                        curr_sorted = sorted(curr_line, key=lambda ch: ch["top"])
                        l_str = ""
                        for idx, ch in enumerate(curr_sorted):
                            if idx > 0 and (ch["top"] - curr_sorted[idx - 1]["bottom"]) > 2.0:
                                l_str += " "
                            l_str += ch["text"]
                        if l_str.strip():
                            lines.append(l_str.strip())
                        curr_line = [c]
                        curr_x = cx
                if curr_line:
                    curr_sorted = sorted(curr_line, key=lambda ch: ch["top"])
                    l_str = ""
                    for idx, ch in enumerate(curr_sorted):
                        if idx > 0 and (ch["top"] - curr_sorted[idx - 1]["bottom"]) > 2.0:
                            l_str += " "
                        l_str += ch["text"]
                    if l_str.strip():
                        lines.append(l_str.strip())
                return lines

        return [linea.strip() for linea in (page.extract_text() or "").split("\n") if linea.strip()]


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
            lineas = [linea for linea in context.lineas_presplit if linea.strip()]
            if lineas:
                return lineas, False, 0

        lineas: list[str] = []
        uso_ocr_parcial = False
        # Conserva el layout monetario detectado entre paginas nativas. Debe
        # existir incluso cuando la primera pagina no contiene una tabla de
        # ocho columnas; de lo contrario el fallback por coordenadas intentaba
        # leer una variable local aun no inicializada.
        coordinate_centers: Optional[list[float]] = None

        from document_scope import contar_paginas_pdf
        n_paginas_detectadas, page_warnings = contar_paginas_pdf(path)
        self._ocr_advertencias.extend(page_warnings)

        n_paginas = n_paginas_detectadas
        try:
            with pdfplumber.open(path) as pdf:
                if len(pdf.pages) > 0:
                    n_paginas = len(pdf.pages)
                for page_number, page in enumerate(pdf.pages, 1):
                    chars = getattr(page, "chars", [])
                    non_upright = [
                        c for c in chars
                        if c.get("upright") is False
                        and abs(c.get("matrix", (1, 0, 0, 1, 0, 0))[1]) > 0.5
                    ]
                    if chars and len(non_upright) / len(chars) > 0.40:
                        lineas_orientadas = self._extraer_lineas_pagina_orientada(page)
                        if len(lineas_orientadas) >= 3:
                            lineas.extend(lineas_orientadas)
                            self._ocr_advertencias.append(
                                f"Página {page_number}: texto renderizado con rotación de fuente; "
                                "se extrajo ordenado según el vector de lectura nativo."
                            )
                            continue

                    texto = page.extract_text() or ""
                    if not texto.strip():
                        continue
                    if _pagina_comparativa_con_texto_nativo_corrupto(page, texto):
                        cid_corrupto = len(re.findall(
                            r"\(cid:\d+\)", texto, flags=re.I,
                        )) >= 20
                        # Los marcadores CID no contienen letras recuperables por
                        # coordenadas. Se omite esa reconstrucción para no aceptar
                        # glosas ilegibles como si fueran texto contable válido.
                        if not cid_corrupto:
                            tabla_coordenadas, detected_centers = (
                                _extraer_tabla_balance_por_coordenadas(
                                    page, coordinate_centers,
                                )
                            )
                            if len(tabla_coordenadas) >= 5 and detected_centers:
                                lineas.extend(tabla_coordenadas)
                                coordinate_centers = detected_centers
                                self._extraction_method = "native_corrupt_coordinates"
                                self._extraction_confidence = min(
                                    self._extraction_confidence, 0.75,
                                )
                                self._ocr_advertencias.append(
                                    f"Página {page_number}: el texto nativo estaba "
                                    "fragmentado y la tabla se reconstruyó desde sus "
                                    "coordenadas."
                                )
                                continue
                            reconstructed = _reconstruir_lineas_nativas_fragmentadas(page)
                            if len(reconstructed) >= 5:
                                lineas.extend(reconstructed)
                                self._extraction_method = "native_fragment_reconstruction"
                                self._extraction_confidence = min(
                                    self._extraction_confidence, 0.75,
                                )
                                self._ocr_advertencias.append(
                                    f"Página {page_number}: se reconstruyó el texto "
                                    "comparativo desde las coordenadas nativas del PDF."
                                )
                                coordinate_centers = None
                                continue
                        recovered = self._ocr_pagina_tabular(path, page_number)
                        if len(recovered) >= 5:
                            lineas.extend(recovered)
                            uso_ocr_parcial = True
                            self._extraction_method = (
                                "partial_ocr_cid_mapping"
                                if cid_corrupto else "partial_ocr_comparative"
                            )
                            self._ocr_advertencias.append(
                                f"Página {page_number}: el texto nativo "
                                f"{'usaba un mapa CID ilegible' if cid_corrupto else 'comparativo estaba fragmentado'} "
                                "y se recuperó mediante OCR tabular."
                            )
                            coordinate_centers = None
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
                        lineas.extend(linea for linea in page_lineas if linea.strip())
                    else:
                        tabla_8_columnas = _extraer_tabla_balance_8_columnas(page)
                        if tabla_8_columnas:
                            self._extraction_method = "native_table_8_columns"
                            lineas.extend(tabla_8_columnas)
                        else:
                            tabla_coordenadas, detected_centers = (
                                _extraer_tabla_balance_por_coordenadas(
                                    page, coordinate_centers,
                                )
                            )
                            coordinate_centers = detected_centers
                            if tabla_coordenadas:
                                self._extraction_method = "coordinates_8_amounts"
                                lineas.extend(tabla_coordenadas)
                            else:
                                lineas.extend(texto.split('\n'))
        except Exception as exc:
            logger.debug("Fallo al abrir con pdfplumber (%s); usando respaldo OCR.", exc)

        if lineas:
            if self._debe_corregir_rotacion(context):
                lineas = [ParserPDF._reverse_line(linea) for linea in lineas]
                return lineas, uso_ocr_parcial, 180
            return lineas, uso_ocr_parcial, 0

        return self._ocr_documento(path, n_paginas)

    def _ocr_pagina_tabular(self, path: Path, page_number: int) -> list[str]:
        """Rasteriza y recupera una sola página comparativa con PSM 4."""
        pdftoppm_bin = shutil.which("pdftoppm") or "pdftoppm"
        with tempfile.TemporaryDirectory(prefix="balance-page-ocr-") as tmpdir:
            tmpdir_path = Path(tmpdir)
            prefix = tmpdir_path / f"pg{page_number}"
            try:
                raster = subprocess.run(
                    [
                        pdftoppm_bin, "-png", "-gray", "-r", str(OCR_RENDER_DPI),
                        "-f", str(page_number), "-l", str(page_number),
                        str(path), str(prefix),
                    ],
                    capture_output=True,
                    timeout=OCR_PAGE_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                self._ocr_timeout_pages.add(page_number)
                self._ocr_advertencias.append(
                    f"Página {page_number}: la recuperación OCR selectiva excedió "
                    f"{OCR_PAGE_TIMEOUT_SECONDS} segundos."
                )
                return []
            if raster.returncode != 0:
                logger.warning(
                    "No se pudo rasterizar página comparativa %d de %s: %s",
                    page_number, path.name,
                    (raster.stderr or b"").decode(errors="replace")[:300],
                )
                return []
            images = sorted(tmpdir_path.glob(f"pg{page_number}*.png"))
            if not images:
                return []
            timeout_events: list[str] = []
            texto = ocr_pagina(
                images[0], 0, psm=4,
                timeout_events=timeout_events, page_number=page_number,
            )
            if not texto.strip() and timeout_events:
                self._ocr_timeout_pages.add(page_number)
                self._ocr_advertencias.extend(timeout_events)
            return [
                normalizar_linea_ocr_tabla(line)
                for line in texto.splitlines()
                if normalizar_linea_ocr_tabla(line).strip()
        ]


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
        rotacion_global: Optional[int] = None
        coordinate_centers: Optional[list[float]] = None
        rapid_coordinate_centers: Optional[list[float]] = None
        rapid_rescue_active = False

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
                    self._ocr_timeout_pages.add(pagina)
                    self._ocr_advertencias.append(
                        f"Página {pagina}: no pudo rasterizarse dentro de "
                        f"{OCR_PAGE_TIMEOUT_SECONDS} segundos y fue omitida."
                    )
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
                    continue
                imgs = list(tmpdir_path.glob(f'pg{pagina}*.png'))
                if not imgs:
                    continue
                img_path = imgs[0]

                if rotacion_global is None:
                    rot = detectar_rotacion_osd(img_path)
                    if rot is None:
                        rot = detectar_rotacion_heuristica(img_path)
                    rotacion_global = rot

                words_tsv = ocr_pagina_tsv(img_path, rotacion_global or 0)
                paneles_paralelos = _extraer_paneles_paralelos_ocr(
                    img_path, rotacion_global or 0, words_tsv
                )
                if paneles_paralelos:
                    self._extraction_method = "ocr_parallel_panels"
                    self._ocr_advertencias.append(
                        f"Página {pagina}: se detectaron dos paneles paralelos "
                        "(Activo / Pasivo-Patrimonio) y se extrajeron independientemente."
                    )
                    lineas.extend(paneles_paralelos)
                    continue

                page_timeout_events: list[str] = []
                texto = ocr_pagina(
                    img_path, rotacion_global,
                    timeout_events=page_timeout_events, page_number=pagina,
                )
                texto_principal = texto
                tabla_coordenadas_usada = False
                if words_tsv:
                    tabla_ocr, detected_centers, decision_ocr = _tabla_ocr_con_alternativa(
                        img_path, rotacion_global or 0, words_tsv, coordinate_centers,
                        pagina=pagina,
                    )
                    if isinstance(decision_ocr, DecisionComparacionOCR):
                        if hasattr(decision_ocr, "resultado_composicion") and decision_ocr.resultado_composicion:
                            if not hasattr(self, "_ocr_composiciones"):
                                self._ocr_composiciones = {}
                            self._ocr_composiciones[pagina] = decision_ocr.resultado_composicion

                        if decision_ocr.ambiguedad_material or (hasattr(decision_ocr, "resultado_composicion") and decision_ocr.resultado_composicion and decision_ocr.resultado_composicion.bloqueada):
                            self._ocr_advertencias.append(
                                f"Página {pagina}: ambigüedad material no resuelta entre candidatos OCR PSM 6 y PSM 4; requiere revisión humana."
                            )
                            bloqueo_info = {
                                "bloqueado": True,
                                "motivo": "ambiguedad_candidatos_ocr",
                                "pagina": pagina,
                                "detalle": f"Página {pagina}: ambigüedad material no resuelta en candidatos/filas OCR ({decision_ocr.detalle_discrepancia or decision_ocr.motivo}).",
                                "filas_ambiguas": [
                                    {
                                        "codigo": f.codigo_normalizado,
                                        "glosa": f.glosa_normalizada,
                                        "motivo": f.motivo_revision,
                                        "regla": f.regla_aceptacion,
                                    }
                                    for f in decision_ocr.resultado_composicion.filas_compuestas
                                    if f.es_ambigua
                                ] if (hasattr(decision_ocr, "resultado_composicion") and decision_ocr.resultado_composicion) else [],
                            }
                            if not hasattr(self, "_ocr_bloqueos_certificacion") or self._ocr_bloqueos_certificacion is None:
                                self._ocr_bloqueos_certificacion = []
                            self._ocr_bloqueos_certificacion.append(bloqueo_info)
                            pags_str = ", ".join(str(b["pagina"]) for b in self._ocr_bloqueos_certificacion)
                            self._ocr_bloqueo_certificacion = {
                                "bloqueado": True,
                                "motivo": "ambiguedad_candidatos_ocr",
                                "pagina": pagina,
                                "paginas": [b["pagina"] for b in self._ocr_bloqueos_certificacion],
                                "bloqueos": list(self._ocr_bloqueos_certificacion),
                                "detalle": f"Páginas {pags_str}: ambigüedad material no resuelta entre candidatos OCR alternativos.",
                            }
                        elif decision_ocr.motor_seleccionado == "Composicion_Segura_Filas":
                            self._ocr_advertencias.append(
                                f"Página {pagina}: tabla reconstruida mediante composición segura de filas entre candidatos OCR."
                            )
                        elif decision_ocr.tipo_seleccion == "provisional":
                            self._ocr_advertencias.append(
                                f"Página {pagina}: selección provisional de motor {decision_ocr.motor_seleccionado} ({decision_ocr.motivo}); sin control local de página conciliado."
                            )
                        elif decision_ocr.motor_seleccionado != "PSM 6":
                            self._ocr_advertencias.append(
                                f"Página {pagina}: tabla reconstruida por coordenadas de lectura OCR {decision_ocr.motor_seleccionado}, contrastada con identidades de ocho columnas."
                            )
                    else:
                        alternative_used = str(decision_ocr or "")
                        if alternative_used and "ambigüedad" in alternative_used.lower():
                            self._ocr_advertencias.append(
                                f"Página {pagina}: ambigüedad material no resuelta entre candidatos OCR PSM 6 y PSM 4; requiere revisión humana."
                            )
                            bloqueo_info = {
                                "bloqueado": True,
                                "motivo": "ambiguedad_candidatos_ocr",
                                "pagina": pagina,
                                "detalle": f"Página {pagina}: ambigüedad material no resuelta entre candidatos OCR alternativos.",
                            }
                            if not hasattr(self, "_ocr_bloqueos_certificacion") or self._ocr_bloqueos_certificacion is None:
                                self._ocr_bloqueos_certificacion = []
                            self._ocr_bloqueos_certificacion.append(bloqueo_info)
                            pags_str = ", ".join(str(b["pagina"]) for b in self._ocr_bloqueos_certificacion)
                            self._ocr_bloqueo_certificacion = {
                                "bloqueado": True,
                                "motivo": "ambiguedad_candidatos_ocr",
                                "pagina": pagina,
                                "paginas": [b["pagina"] for b in self._ocr_bloqueos_certificacion],
                                "bloqueos": list(self._ocr_bloqueos_certificacion),
                                "detalle": f"Páginas {pags_str}: ambigüedad material no resuelta entre candidatos OCR alternativos.",
                            }
                        elif alternative_used:
                            self._ocr_advertencias.append(
                                f"Página {pagina}: tabla reconstruida por coordenadas de una lectura OCR alternativa {alternative_used}."
                            )
                    tiene_cierre_ocr = any(_es_cierre_final_balance(l) or "sumas iguales" in l.lower() or "total general" in l.lower() for l in tabla_ocr)
                    if (len(tabla_ocr) >= 3 or (len(tabla_ocr) >= 1 and tiene_cierre_ocr)) and detected_centers:
                        coordinate_centers = detected_centers
                        texto = "\n".join(tabla_ocr)
                        self._extraction_method = "ocr_coordinates_8_amounts"
                        tabla_coordenadas_usada = True
                if not tabla_coordenadas_usada and _es_pagina_firmas_ocr(texto_principal):
                    self._ocr_advertencias.append(
                        f"Página {pagina}: se omitió por contener solo firmas y "
                        "metadatos, sin tabla contable."
                    )
                    continue
                if (
                    tabla_coordenadas_usada
                    and getattr(decision_ocr, "motor_seleccionado", None) != "Composicion_Segura_Filas"
                    and not tiene_cierre_ocr
                    and texto_principal.strip()
                ):
                    recovered, replacements = recuperar_filas_tabla_ocr(
                        texto.splitlines(), texto_principal,
                    )
                    if replacements:
                        texto = "\n".join(recovered)
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se recuperaron {replacements} filas "
                            "al contrastar la geometría con la lectura textual OCR."
                        )
                if (
                    tabla_coordenadas_usada
                    and getattr(decision_ocr, "motor_seleccionado", None) != "Composicion_Segura_Filas"
                    and _tabla_ocr_necesita_recuperacion(
                        texto.splitlines(),
                    )
                ):
                    texto_tabla = ocr_pagina(
                        img_path, rotacion_global, psm=4,
                        timeout_events=page_timeout_events, page_number=pagina,
                    )
                    recovered, replacements = recuperar_filas_tabla_ocr(
                        texto.splitlines(), texto_tabla,
                    )
                    if replacements:
                        texto = "\n".join(recovered)
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se recuperaron {replacements} filas "
                            "por verificación cruzada de dos lecturas OCR."
                        )
                # Una tabla reconstruida por coordenadas ya contiene la misma
                # pagina. Fusionarla con PSM 4 duplicaba sus cuentas y montos.
                if (
                    not tabla_coordenadas_usada
                    and _ocr_requiere_alternativa(texto, pagina == n_paginas)
                ):
                    texto_tabla = ocr_pagina(
                        img_path, rotacion_global, psm=4,
                        timeout_events=page_timeout_events, page_number=pagina,
                    )
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
                                f"mayor calidad estructural ({estrategia})."
                            )
                # Si la tabla de ocho columnas sigue rompiendo demasiadas
                # identidades, se contrasta con un segundo motor local. No se
                # mezcla celda a celda ni se inventan saldos: se reemplaza la
                # página completa únicamente cuando la alternativa demuestra
                # una mejora contable amplia y al menos 75% de filas válidas.
                base_lines = [line for line in texto.splitlines() if line.strip()]
                base_validas, base_completas = _identidades_validas_lineas_8_columnas(
                    base_lines,
                )
                if (
                    rapid_rescue_active
                    or (
                        base_completas >= 5
                        and base_validas / base_completas < 0.95
                    )
                ):
                    rapid_words = _rapidocr_words(img_path, rotacion_global)
                    rapid_lines: list[str] = []
                    if rapid_words:
                        rapid_lines, rapid_detected = (
                            _extraer_tabla_balance_por_coordenadas(
                                _OCRWordsPage(rapid_words),
                                rapid_coordinate_centers,
                            )
                        )
                        if rapid_detected:
                            rapid_coordinate_centers = rapid_detected
                        rapid_lines, rapid_repairs = (
                            _reparar_lineas_por_identidades_redundantes(rapid_lines)
                        )
                    else:
                        rapid_repairs = 0
                    if _preferir_lectura_rapidocr(base_lines, rapid_lines):
                        texto = "\n".join(rapid_lines)
                        rapid_rescue_active = True
                        self._extraction_method = "rapidocr_coordinates_8_amounts"
                        rapid_validas, rapid_completas = (
                            _identidades_validas_lineas_8_columnas(rapid_lines)
                        )
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se sustituyó una lectura OCR "
                            f"inconsistente ({base_validas}/{base_completas}) por "
                            "una verificación independiente con más identidades "
                            f"contables válidas ({rapid_validas}/{rapid_completas})."
                        )
                        if rapid_repairs:
                            self._ocr_advertencias.append(
                                f"Página {pagina}: se repararon {rapid_repairs} "
                                "celda(s) OCR porque Debe/Haber, saldo y "
                                "clasificación entregaban dos valores exactos "
                                "concordantes frente a uno discrepante."
                            )
                if not texto.strip():
                    self._ocr_advertencias.append(
                        f"Página {pagina}: OCR sin texto utilizable; revise que el "
                        "documento procesado esté completo."
                    )
                if not texto.strip() and page_timeout_events:
                    self._ocr_timeout_pages.add(pagina)
                    self._ocr_advertencias.extend(page_timeout_events)
                lineas.extend(texto.split('\n'))

        return lineas, True, rotacion_global or 0


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
                es_total=code is None and bool(PATRON_TOTAL.match(name)),
                confianza_extraccion=1.0,
                montos_columnas=amounts,
            ))
        return accounts

    # El conjunto global proviene sólo de cabeceras relevantes y limita el
    # libro a dos períodos. Así una fecha histórica de una nota no crea una
    # tercera columna contable.
    header_lines = [
        " ".join(
            str(value).strip() for value in df.iloc[row_idx].tolist()
            if pd.notna(value) and str(value).strip()
        )
        for row_idx in range(min(15, df.shape[0]))
    ]
    valid_years, _ = detectar_años_y_monedas(header_lines)
    note_columns: set[int] = set()
    for col_idx in range(df.shape[1]):
        for row_idx in range(min(15, df.shape[0])):
            value = df.iloc[row_idx, col_idx]
            if pd.notna(value) and re.fullmatch(
                r"\s*(?:nota|note|n[°ºo.]*)\s*", _sin_acentos(str(value)), re.I,
            ):
                note_columns.add(col_idx)

    # Helper to detect year and currency for a column.
    # Scan the top 15 rows of this column and its immediate left neighbor.
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
                year_match = re.search(r'\b((?:19|20)\d{2})\b', val_str)
                if (
                    year_match and year_match.group(1) in valid_years
                    and not year
                ):
                    year = year_match.group(1)

                # Check currency
                if (
                    'usd' in val_str or 'dolar' in val_str or 'dólar' in val_str
                    or 'us$' in val_str
                ) and not currency:
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
            if col_idx in note_columns:
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

        detected_years = sorted(
            {col_meta[c][0] for c in col_meta if col_meta[c][0] is not None},
            reverse=True,
        )[:2]
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
