"""Contrato explícito de confianza, gobernanza y pisos de regresión en Gold Schema 2.

Este módulo centraliza las constantes y validaciones del contrato de confianza
sin dependencias de la aplicación para permitir su uso desacoplado y pruebas
unitarias directas.
"""

from __future__ import annotations

import math
import re
from typing import Any, Optional

GOLD_CONFIDENCE_CONTRACT_VERSION = 1
SUPPORTED_CONFIDENCE_CONTRACT_VERSIONS = frozenset({1})


def is_valid_sha256(val: Any) -> bool:
    """Valida que el valor sea un SHA-256 hexadecimal válido de exactamente 64 caracteres."""
    if val is None or not isinstance(val, (str, bytes)):
        return False
    clean = str(val).strip().lower()
    return len(clean) == 64 and bool(re.fullmatch(r"^[0-9a-f]{64}$", clean))


def validate_sha256_binding(
    *,
    gold_sha256: Any,
    manifest_sha256: Any,
    document_sha256: Any,
    context_label: str = "documento",
) -> str:
    """Valida fail-closed la triple coincidencia del SHA-256 cuando se utiliza un piso < 1.0.

    Reglas:
    1. gold_sha256 debe estar presente y ser un SHA-256 hexadecimal válido de 64 caracteres.
    2. manifest_sha256 debe estar presente y ser un SHA-256 hexadecimal válido de 64 caracteres.
    3. document_sha256 debe estar presente y ser un SHA-256 hexadecimal válido de 64 caracteres.
    4. Los tres hashes deben ser idénticos (comparación en minúsculas).
    """
    if not gold_sha256 or str(gold_sha256).strip() == "":
        raise ValueError(
            f"El libro Gold para {context_label} contiene filas con Confianza_minima < 1.0 "
            "pero no declara un SHA256 documental autorizado en Resumen."
        )
    clean_gold = str(gold_sha256).strip().lower()
    if not is_valid_sha256(clean_gold):
        raise ValueError(
            f"El SHA-256 declarado en el libro Gold para {context_label} es malformado o inválido: {gold_sha256!r}."
        )

    if not manifest_sha256 or str(manifest_sha256).strip() == "":
        raise ValueError(
            f"El libro Gold para {context_label} exige piso de confianza < 1.0 pero el manifiesto "
            "no declara la expectativa sha256."
        )
    clean_manifest = str(manifest_sha256).strip().lower()
    if not is_valid_sha256(clean_manifest):
        raise ValueError(
            f"La expectativa sha256 del manifiesto para {context_label} es malformada o inválida: {manifest_sha256!r}."
        )

    if not document_sha256 or str(document_sha256).strip() == "":
        raise ValueError(
            f"El libro Gold para {context_label} exige piso de confianza < 1.0 pero no se proporcionó "
            "el SHA-256 real del documento procesado."
        )
    clean_doc = str(document_sha256).strip().lower()
    if not is_valid_sha256(clean_doc):
        raise ValueError(
            f"El SHA-256 del documento real procesado ({context_label}) es malformado o inválido: {document_sha256!r}."
        )

    if clean_gold != clean_manifest:
        raise ValueError(
            f"Discrepancia de hash en {context_label}: el libro Gold autoriza SHA256 '{clean_gold}' "
            f"pero el manifiesto declara '{clean_manifest}'."
        )

    if clean_doc != clean_gold:
        raise ValueError(
            f"Discrepancia de hash en {context_label}: el documento procesado tiene SHA-256 '{clean_doc}' "
            f"pero el libro Gold autoriza exclusivamente '{clean_gold}'."
        )

    if clean_doc != clean_manifest:
        raise ValueError(
            f"Discrepancia de hash en {context_label}: el documento procesado tiene SHA-256 '{clean_doc}' "
            f"pero el manifiesto exige '{clean_manifest}'."
        )

    return clean_gold


def extract_and_validate_sha256(
    source: Any,
    *,
    required: bool = False,
    context_label: str = "documento",
) -> Optional[str]:
    """Extrae y valida el SHA-256 declarado en un objeto, dict o DataFrame (hoja Resumen).

    Retorna el hash en minúsculas si es válido, o None si no está presente y no es requerido.
    Lanza ValueError si es requerido y falta, o si está presente pero es malformado.
    """
    raw_val = None
    if source is not None:
        if hasattr(source, "columns"):
            if not source.empty:
                for col in ("SHA256", "sha256", "Documento_SHA256", "documento_sha256"):
                    if col in source.columns:
                        v = source.iloc[0][col]
                        if v is not None and str(v).strip() != "" and str(v).lower() != "nan":
                            raw_val = v
                            break
        elif isinstance(source, dict):
            for k in ("SHA256", "sha256", "Documento_SHA256", "documento_sha256"):
                if k in source:
                    v = source[k]
                    if v is not None and str(v).strip() != "" and str(v).lower() != "nan":
                        raw_val = v
                        break
        elif isinstance(source, (str, bytes)):
            raw_val = source

    if raw_val is None or str(raw_val).strip() == "" or str(raw_val).lower() == "nan":
        if required:
            raise ValueError(
                f"El {context_label} exige validación de hash pero no declara un SHA-256 en Resumen."
            )
        return None

    clean = str(raw_val).strip().lower()
    if not is_valid_sha256(clean):
        raise ValueError(
            f"El SHA-256 declarado en {context_label} es malformado o inválido: {raw_val!r}."
        )
    return clean


def has_approved_sub_one_floor(rows_or_df: Any) -> bool:
    """Detecta si cualquier fila con Estado_revision=APROBADO tiene piso de confianza < 1.0."""
    if rows_or_df is None:
        return False

    if hasattr(rows_or_df, "iterrows"):
        for _, row in rows_or_df.iterrows():
            state = str(row.get("Estado_revision") or "").strip().upper()
            if state != "APROBADO":
                continue
            for col in ("Confianza_minima", "confidence_min", "Confianza_minima_exigida"):
                val = row.get(col)
                if val is not None and str(val).strip() != "" and str(val).lower() != "nan":
                    if is_valid_confidence(val) and float(val) < 1.0:
                        return True
        return False

    if isinstance(rows_or_df, list):
        for item in rows_or_df:
            if not isinstance(item, dict):
                continue
            state = str(item.get("Estado_revision") or item.get("review_state") or "APROBADO").strip().upper()
            if state != "APROBADO":
                continue
            for k in ("Confianza_minima", "confidence_min", "Confianza_minima_exigida"):
                val = item.get(k)
                if val is not None and str(val).strip() != "" and str(val).lower() != "nan":
                    if is_valid_confidence(val) and float(val) < 1.0:
                        return True
        return False

    return False


def extract_unique_authorized_sha256(rows: list[dict], *, context_label: str = "documento") -> Optional[str]:
    """Comprueba que todas las filas con piso inferior a 1.0 declaren un único _authorized_sha256 válido.

    Lanza ValueError si alguna fila con piso < 1.0 carece de _authorized_sha256,
    si el hash es malformado, o si se declaran hashes distintos entre filas.
    """
    if not rows:
        return None

    sub_one_hashes: list[str] = []
    for idx, r in enumerate(rows, start=1):
        if not isinstance(r, dict):
            continue
        c_min = r.get("confidence_min")
        if c_min is None:
            c_min = r.get("Confianza_minima")
        if c_min is None:
            c_min = r.get("Confianza_minima_exigida")
        if c_min is not None and is_valid_confidence(c_min) and float(c_min) < 1.0:
            auth_sha = r.get("_authorized_sha256")
            if not auth_sha or str(auth_sha).strip() == "":
                line_info = r.get("line") or r.get("Fila") or idx
                raise ValueError(
                    f"Fila {line_info} con Confianza_minima < 1.0 en {context_label} "
                    "no declara un hash documental autorizado (_authorized_sha256)."
                )
            clean_sha = str(auth_sha).strip().lower()
            if not is_valid_sha256(clean_sha):
                line_info = r.get("line") or r.get("Fila") or idx
                raise ValueError(
                    f"El hash autorizado declarado en fila {line_info} ({context_label}) "
                    f"es malformado o inválido: {auth_sha!r}."
                )
            sub_one_hashes.append(clean_sha)

    if not sub_one_hashes:
        return None

    unique_hashes = set(sub_one_hashes)
    if len(unique_hashes) > 1:
        raise ValueError(
            f"Discrepancia en {context_label}: existen múltiples hashes autorizados distintos "
            f"para filas con piso < 1.0: {sorted(unique_hashes)}."
        )

    return sub_one_hashes[0]


def validate_migration_hashes(
    legacy_summary: Any,
    candidate_summary: Any,
    has_sub_one_floor: bool,
    *,
    context_label: str = "migración",
) -> Optional[str]:
    """Valida los hashes entre libros durante la migración.

    Si has_sub_one_floor es True:
    - Exige SHA-256 válido en Resumen del legado.
    - Exige SHA-256 válido en Resumen del candidato.
    - Ambos hashes deben coincidir exactamente.
    - Retorna el hash validado.
    Si has_sub_one_floor es False:
    - Si ambos declaran SHA-256, valida que coincidan.
    - Retorna el SHA-256 si está presente.
    """
    if has_sub_one_floor:
        leg_sha = extract_and_validate_sha256(
            legacy_summary, required=True, context_label=f"libro legado ({context_label})"
        )
        cand_sha = extract_and_validate_sha256(
            candidate_summary, required=True, context_label=f"candidato ({context_label})"
        )
        if leg_sha != cand_sha:
            raise ValueError(
                f"Discrepancia de SHA-256 en {context_label}: el libro legado declara '{leg_sha}' "
                f"pero el candidato declara '{cand_sha}'."
            )
        return leg_sha
    else:
        leg_sha = extract_and_validate_sha256(
            legacy_summary, required=False, context_label=f"libro legado ({context_label})"
        )
        cand_sha = extract_and_validate_sha256(
            candidate_summary, required=False, context_label=f"candidato ({context_label})"
        )
        if leg_sha is not None and cand_sha is not None and leg_sha != cand_sha:
            raise ValueError(
                f"Discrepancia de SHA-256 en {context_label}: el libro legado declara '{leg_sha}' "
                f"pero el candidato declara '{cand_sha}'."
            )
        return leg_sha or cand_sha


def is_valid_confidence(value: Any) -> bool:
    """Valida que la confianza o umbral sea un número finito dentro de [0.0, 1.0]."""
    if value is None or isinstance(value, bool):
        return False
    try:
        f = float(value)
        return math.isfinite(f) and 0.0 <= f <= 1.0
    except (ValueError, TypeError):
        return False


# Alias privado para compatibilidad hacia atrás
_is_valid_confidence = is_valid_confidence


def parse_contract_version(val: Any, *, allow_none: bool = True) -> Optional[int]:
    """Parsea y valida la versión del contrato de confianza.

    Parámetros:
        val: Valor a evaluar.
        allow_none: Si es True y val es None, retorna None (marcador ausente).
                   Si es False y val es None, lanza ValueError.

    Retorna:
        int: Versión soportada si está presente y es válida.
        None: Si allow_none es True y val es None.

    Lanza:
        ValueError: Si el valor es no numérico, no entero, no finito (incluyendo NaN, inf, -inf),
                    cadena vacía, marcador corrupto o versión no soportada.
    """
    if val is None:
        if allow_none:
            return None
        raise ValueError("Marcador Gold_confidence_contract_version ausente o nulo.")

    try:
        import pandas as pd
        if pd.isna(val):
            raise ValueError(f"Versión de contrato de confianza no válida: '{val}'.")
    except ImportError:
        pass

    s = str(val).strip()
    if not s:
        raise ValueError("Versión de contrato de confianza no válida: ''.")

    try:
        f_val = float(s)
        if not math.isfinite(f_val) or not f_val.is_integer():
            raise ValueError(
                f"Versión de contrato de confianza no válida: '{val}'."
            )
        ver = int(f_val)
    except (ValueError, TypeError):
        raise ValueError(
            f"Versión de contrato de confianza no válida: '{val}'."
        )

    if ver not in SUPPORTED_CONFIDENCE_CONTRACT_VERSIONS:
        raise ValueError(
            f"Versión de contrato de confianza no soportada: {ver}. "
            f"Versiones soportadas: {sorted(SUPPORTED_CONFIDENCE_CONTRACT_VERSIONS)}."
        )
    return ver


def validate_workbook_resumen_and_cuentas(
    workbook_path: Any,
    label: str = "libro",
    enforce_confidence_coherence: bool = False,
) -> tuple[Optional[int], Any, Any]:
    """Valida estrictamente la estructura, hojas y contrato de un libro Gold (legado o candidato).

    Reglas de validación:
    1. El archivo debe existir y contener las hojas 'Resumen' y 'Cuentas'.
    2. Si 'Gold_confidence_contract_version' está presente en Resumen:
       - No puede estar vacío, NaN, no numérico, no entero, no finito ni ser versión no soportada.
       - Debe validarse con parse_contract_version(val, allow_none=False).
    3. Si enforce_confidence_coherence=True, valida coherencia entre marcador y columnas de confianza:
       - Si Cuentas tiene 'Confianza_minima' pero falta el marcador en Resumen: ValueError.
       - Si Resumen declara contrato v1 pero Cuentas carece de 'Confianza_minima': ValueError.
    4. Si el marcador está ausente:
       - Se retorna contract_version=None (modo compatible legado).
    """
    import pandas as pd
    from pathlib import Path

    path = Path(workbook_path)
    if not path.exists():
        raise ValueError(f"El {label} '{path}' no existe.")

    excel = pd.ExcelFile(path)
    if "Resumen" not in excel.sheet_names or "Cuentas" not in excel.sheet_names:
        raise ValueError(
            f"El {label} '{path.name}' debe contener las hojas obligatorias 'Resumen' y 'Cuentas'."
        )

    summary = pd.read_excel(excel, sheet_name="Resumen")
    cuentas = pd.read_excel(excel, sheet_name="Cuentas")

    marker_col = None
    for col in ("Gold_confidence_contract_version", "gold_confidence_contract_version"):
        if col in summary.columns:
            marker_col = col
            break

    contract_version = None
    if marker_col is not None:
        if summary.empty:
            raise ValueError(
                f"El {label} '{path.name}' tiene la hoja 'Resumen' vacía pero declara '{marker_col}'."
            )
        raw_val = summary.iloc[0][marker_col]
        # Si la columna está presente, el valor no puede ser None, NaN ni corrupto
        contract_version = parse_contract_version(raw_val, allow_none=False)

    if enforce_confidence_coherence:
        has_conf_min = (
            "Confianza_minima" in cuentas.columns
            or "Confianza_minima_exigida" in cuentas.columns
        )

        if has_conf_min and contract_version is None:
            raise ValueError(
                f"El {label} '{path.name}' contiene la columna Confianza_minima pero "
                "falta el marcador Gold_confidence_contract_version en Resumen."
            )
        if contract_version is not None and not has_conf_min and not cuentas.empty:
            raise ValueError(
                f"El {label} '{path.name}' declara Gold_confidence_contract_version={contract_version} "
                "pero falta la columna Confianza_minima en Cuentas."
            )

    return contract_version, summary, cuentas


def validate_confidence_floor(value: Any, row_context: str = "") -> float:
    """Valida y retorna un piso de confianza garantizando que sea float en [0.0, 1.0]."""
    if not is_valid_confidence(value):
        ctx = f" en {row_context}" if row_context else ""
        raise ValueError(
            f"Piso de confianza inválido{ctx}: {value!r}. Debe ser un número finito en [0.0, 1.0]."
        )
    return float(value)


def validate_candidate_confidence(value: Any, row_context: str = "") -> float:
    """Valida y retorna la confianza candidata garantizando que sea float en [0.0, 1.0]."""
    if not is_valid_confidence(value):
        ctx = f" en {row_context}" if row_context else ""
        raise ValueError(
            f"Confianza de extracción candidata inválida{ctx}: {value!r}. Debe ser un número finito en [0.0, 1.0]."
        )
    return float(value)
