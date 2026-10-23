"""
app_validacion.py — Plataforma de homologación de balances tributarios chilenos

Ejecutar con:
    streamlit run app_validacion.py

Requiere en el mismo directorio:
    - catalogo_maestro.json
    - diccionario.json
    - parser_universal.py
    - clasificador_codigo_cuenta.py
    - reglas_especiales.py

Funcionalidad:
    1. Carga de archivo (PDF o Excel)
    2. Clasificación híbrida: código de cuenta → diccionario (exacto/fuzzy) → reglas regex
    3. Aplicación de reglas especiales (D1-D5 del análisis del vaciador)
    4. Cola de revisión para cuentas con confianza < umbral
    5. Balance normalizado agrupado por catálogo maestro
    6. Feedback loop: las correcciones se agregan al diccionario y son descargables
"""

import hashlib
import calendar
import json
import math
import os
import re
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from datetime import date, datetime
from io import BytesIO
from html import escape
from document_scope import (
    page_count, parse_pages, select_pdf, render_page, sugerir_periodos_balance,
)
from report_presentation import complete_catalog, add_report_sheets
from access_control import Permission, ResourceScope, authorize

import pandas as pd
import streamlit as st
from rapidfuzz import fuzz, process
from dotenv import load_dotenv

from clasificador_codigo_cuenta import ClasificadorCodigo
from catalog_selection import opciones_clasificacion
from gold_standard.builder import GoldBuilder
from gold_standard.promotion import promote as promover_revisiones
from gold_standard.runtime import RuntimeGoldStorage
from gold_standard.runtime_manager import RuntimeManager
from gold_standard.runtime_stats import RuntimeStatistics
from reglas_especiales import (
    ProcesadorReglasEspeciales,
    calcular_patrimonio_efectivo,
    es_cuenta_socios,
)
from config.regex_rules import REGLAS_REGEX, REGLAS_COMPILADAS
from parser_universal import (
    ParserPDF, CuentaRaw, OrigenColumna, RAW_MONETARY_COLUMNS,
    FormatoCodigo, ResultadoParseo,
    certificar_extraccion_columnas, parsear_excel,
)
from parsers.column_interpretation import es_ingreso as es_ingreso_col, es_gasto as es_gasto_col
from parsers.account_type_resolver import (
    account_type_from_explicit_section,
    is_accumulated_result_name,
    is_accumulated_result_2402_code,
    is_capital_pending_name,
    is_contra_asset_name,
    is_credit_balance_depreciation_name,
    is_debit_balance_financial_liability,
    is_historical_accumulated_result_name,
    is_current_result_name,
    is_patrimonial_reserve_name,
    result_year_from_name,
)
from extractor_metadata import extraer_metadata, MetadataEmpresa
from account_qualification import qualify_cuentas as _safe_qualify_cuentas, \
    safe_mode_enabled as _safe_mode_enabled
from pilot_mode import configure_pilot_tempdir, pilot_mode_active
from pilot_manifest import match_pilot_manifest_uploads_json
from local_access_ui import (
    local_access_enabled,
    render_local_access_gate,
    render_local_access_sidebar,
)
from team_dictionary import (
    TeamDictionaryError,
    TeamDictionaryStore,
    overlay_team_dictionary,
)
from team_dictionary_ui import (
    can_view_team_dictionary,
    render_team_dictionary_view,
)
from persistence.neon_store import NeonKnowledgeStore
from reporting_integrity import (
    certificar_cuadratura_homologada, debe_incorporar_resultado_derivado,
    resultado_final_fuente_certificado,
    resultado_compatible,
    importe_resultado_homologado, importe_presentacion_balance,
    conciliar_resultados,
)
from delivery_readiness import evaluar_entregabilidad
from format_support import evaluar_formato


MESES_SELECCION = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _valores_periodo_metadata(meta: MetadataEmpresa) -> tuple[str, int, int]:
    """Deriva mes, año y duración desde el período detectado."""
    cierre = None
    inicio = None
    for raw, target in ((meta.periodo_hasta, "cierre"), (meta.periodo_desde, "inicio")):
        if not raw:
            continue
        try:
            parsed = datetime.strptime(str(raw), "%d/%m/%Y").date()
        except ValueError:
            continue
        if target == "cierre":
            cierre = parsed
        else:
            inicio = parsed
    cierre = cierre or date.today()
    meses = 12
    if inicio:
        meses = (cierre.year - inicio.year) * 12 + cierre.month - inicio.month + 1
        meses = min(12, max(1, meses))
    return MESES_SELECCION[cierre.month - 1], cierre.year, meses


def _fechas_periodo_seleccionado(
    mes: str, anio: int, numero_meses: int,
) -> tuple[str, str]:
    """Convierte mes de cierre y duración a fechas inclusivas del período."""
    mes_numero = MESES_SELECCION.index(mes) + 1
    total_inicio = anio * 12 + mes_numero - int(numero_meses)
    anio_inicio, mes_inicio_cero = divmod(total_inicio, 12)
    mes_inicio = mes_inicio_cero + 1
    ultimo_dia = calendar.monthrange(int(anio), mes_numero)[1]
    return (
        f"01/{mes_inicio:02d}/{anio_inicio}",
        f"{ultimo_dia:02d}/{mes_numero:02d}/{int(anio)}",
    )


def _normalizar_anio_cierre(valor) -> int | None:
    """Acepta sólo años de cierre plausibles, sin completar valores ausentes."""
    if isinstance(valor, bool):
        return None
    try:
        anio = int(valor)
    except (TypeError, ValueError):
        return None
    return anio if 1900 <= anio <= 2100 else None


def _anio_cierre_detectado(meta: MetadataEmpresa) -> int | None:
    """Obtiene el año sólo desde metadata extraída, nunca desde el nombre."""
    directo = _normalizar_anio_cierre(getattr(meta, "anio_cierre", None))
    if directo is not None:
        return directo
    periodo_hasta = getattr(meta, "periodo_hasta", None)
    if not periodo_hasta:
        return None
    try:
        return datetime.strptime(str(periodo_hasta), "%d/%m/%Y").year
    except ValueError:
        coincidencia = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", str(periodo_hasta))
        return int(coincidencia.group(1)) if coincidencia else None


def _contexto_confirmacion_anio(archivo) -> dict:
    """Identifica el contenido y alcance a los que aplica una confirmación."""
    contenido = archivo.getvalue()
    paginas = st.session_state.get("document_pages", {}).get(archivo.name)
    return {
        "sha256": hashlib.sha256(contenido).hexdigest(),
        "paginas": list(paginas) if paginas is not None else [],
    }


def _contexto_metadata_general(archivo) -> dict:
    """Vincula el testigo de vigencia del lote al primer documento."""
    return {
        "archivo": archivo.name,
        **_contexto_confirmacion_anio(archivo),
    }


def _registro_anio_confirmado_vigente(archivo) -> dict | None:
    """Devuelve la confirmación sólo si aún corresponde al mismo documento."""
    registro = st.session_state.get("document_closing_years", {}).get(archivo.name)
    if not isinstance(registro, dict) or not registro.get("confirmado", False):
        return None
    contexto = _contexto_confirmacion_anio(archivo)
    if (registro.get("sha256") != contexto["sha256"]
            or list(registro.get("paginas", [])) != contexto["paginas"]):
        return None
    return registro


def _anio_cierre_confirmado_documento(archivo) -> int | None:
    """Devuelve el año confirmado por archivo, o None si quedó sin confirmar."""
    registro = _registro_anio_confirmado_vigente(archivo)
    return _normalizar_anio_cierre(registro.get("anio_cierre")) if registro else None


def _confirmacion_anio_vigente(archivo) -> bool:
    """Distingue una confirmación explícita sin año de una no confirmación."""
    return _registro_anio_confirmado_vigente(archivo) is not None


_CAMPOS_METADATA_DOCUMENTAL = (
    "rut", "razon_social", "giro", "moneda", "mes_cierre", "numero_meses",
)


def _normalizar_numero_meses(valor) -> int | None:
    """Acepta sólo duraciones contables explícitas de uno a doce meses."""
    if isinstance(valor, bool):
        return None
    try:
        numero_meses = int(valor)
    except (TypeError, ValueError):
        return None
    return numero_meses if 1 <= numero_meses <= 12 else None


def _registro_metadata_documental_vigente(archivo) -> dict | None:
    """Devuelve metadata confirmada sólo para el contenido y alcance vigentes."""
    registro = st.session_state.get(
        "document_metadata_confirmations", {},
    ).get(archivo.name)
    if not isinstance(registro, dict) or not registro.get("confirmado", False):
        return None
    if any(campo not in registro for campo in _CAMPOS_METADATA_DOCUMENTAL):
        return None
    if (registro.get("mes_cierre") not in MESES_SELECCION
            or _normalizar_numero_meses(registro.get("numero_meses")) is None):
        return None
    contexto = _contexto_confirmacion_anio(archivo)
    if (registro.get("sha256") != contexto["sha256"]
            or list(registro.get("paginas", [])) != contexto["paginas"]):
        return None
    return registro


def _metadata_documental_confirmada_vigente(archivo) -> bool:
    """Indica si todos los campos del documento fueron confirmados en contexto."""
    return _registro_metadata_documental_vigente(archivo) is not None


def _campos_metadata_detectada(archivo) -> dict:
    """Obtiene valores iniciales de un único documento, sin reutilizar otro PDF."""
    try:
        meta = extraer_metadata(_extraer_lineas_encabezado(archivo))
    except Exception:
        meta = MetadataEmpresa()

    mes_cierre = getattr(meta, "mes_cierre", None)
    numero_meses = _normalizar_numero_meses(
        getattr(meta, "numero_meses", None),
    )
    periodo_hasta = getattr(meta, "periodo_hasta", None)
    periodo_desde = getattr(meta, "periodo_desde", None)
    try:
        cierre = datetime.strptime(str(periodo_hasta), "%d/%m/%Y").date()
    except (TypeError, ValueError):
        cierre = None
    try:
        inicio = datetime.strptime(str(periodo_desde), "%d/%m/%Y").date()
    except (TypeError, ValueError):
        inicio = None
    if mes_cierre not in MESES_SELECCION and cierre is not None:
        mes_cierre = MESES_SELECCION[cierre.month - 1]
    if numero_meses is None and cierre is not None and inicio is not None:
        numero_meses = _normalizar_numero_meses(
            (cierre.year - inicio.year) * 12 + cierre.month - inicio.month + 1,
        )

    # Las propuestas seguras no proceden de otro archivo. Su confirmación sigue
    # siendo obligatoria aun cuando el extractor no haya podido detectar un dato.
    return {
        "rut": str(getattr(meta, "rut", "") or "").strip(),
        "razon_social": str(getattr(meta, "razon_social", "") or "").strip(),
        "giro": str(getattr(meta, "giro", "") or "").strip(),
        "moneda": str(getattr(meta, "moneda", "$") or "$").strip(),
        "mes_cierre": (
            mes_cierre if mes_cierre in MESES_SELECCION else "Diciembre"
        ),
        "numero_meses": numero_meses or 12,
    }


def _normalizar_campos_metadata_documental(valores: dict) -> dict:
    """Normaliza los campos editables antes de ligarlos al documento concreto."""
    mes_cierre = valores.get("mes_cierre")
    if mes_cierre not in MESES_SELECCION:
        mes_cierre = "Diciembre"
    return {
        "rut": str(valores.get("rut") or "").strip(),
        "razon_social": str(valores.get("razon_social") or "").strip(),
        "giro": str(valores.get("giro") or "").strip(),
        "moneda": str(valores.get("moneda") or "").strip(),
        "mes_cierre": mes_cierre,
        "numero_meses": _normalizar_numero_meses(
            valores.get("numero_meses"),
        ) or 12,
    }


def _serie_texto(df: pd.DataFrame, columna: str) -> pd.Series:
    """Obtiene una columna de texto sin exigirla a resultados de versiones previas."""
    if columna not in df.columns:
        return pd.Series("", index=df.index, dtype=object)
    return df[columna].fillna("").astype(str)


def _invalidar_propagaciones_desde(nombre_archivo: str) -> set[str]:
    """Reabre destinos que heredaron una decisión de un documento modificado.

    Las propagaciones antiguas no tenían trazabilidad de origen. Si una fila
    propagada carece de esa traza, se invalida también de forma conservadora:
    no puede conservar una clasificación cruzada cuyo origen no sea auditable.
    """
    resultados = st.session_state.get("resultados", {})
    if not isinstance(resultados, dict):
        return set()

    destinos_invalidados: set[str] = set()
    for destino, resultado in list(resultados.items()):
        if not isinstance(resultado, pd.DataFrame) or resultado.empty:
            continue
        metodo = _serie_texto(resultado, "metodo").str.lower()
        evidencia = _serie_texto(resultado, "evidencia").str.lower()
        es_propagada = (
            metodo.str.contains("propag", regex=False)
            | evidencia.str.contains("propag", regex=False)
        ) & ~metodo.eq("propagacion_invalidada")
        if not es_propagada.any():
            continue
        origen = _serie_texto(resultado, "propagacion_origen_archivo")
        sin_traza = origen.eq("")
        afectadas = es_propagada & (
            origen.eq(nombre_archivo) | sin_traza
        )
        if not afectadas.any():
            continue

        actualizado = resultado.copy()
        actualizado.loc[afectadas, "codigo_clasificado"] = ""
        actualizado.loc[afectadas, "metodo"] = "propagacion_invalidada"
        actualizado.loc[afectadas, "confianza"] = 0.0
        actualizado.loc[afectadas, "requiere_revision"] = True
        actualizado.loc[afectadas, "regla"] = "propagacion_invalidada"
        actualizado.loc[afectadas, "evidencia"] = (
            "El documento de origen cambió; requiere revisión."
        )
        actualizado.loc[afectadas, "propagacion_origen_archivo"] = ""
        if "origen" in actualizado.columns:
            actualizado.loc[afectadas, "origen"] = "Sin clasificar"
        resultados[destino] = actualizado
        destinos_invalidados.add(destino)

    revisiones = st.session_state.setdefault("extraction_revisions", {})
    for destino in destinos_invalidados:
        revisiones[destino] = revisiones.get(destino, 0) + 1
        for state_key in ("quality_controls", "delivery_readiness"):
            st.session_state.setdefault(state_key, {}).pop(destino, None)
    return destinos_invalidados


def _invalidar_estado_documento(
        nombre_archivo: str, *, invalidar_metadata_documental: bool = False,
) -> None:
    """Descarta resultados derivados de contenido, páginas o año modificados."""
    _invalidar_propagaciones_desde(nombre_archivo)
    if invalidar_metadata_documental:
        st.session_state.setdefault(
            "document_metadata_confirmations", {},
        ).pop(nombre_archivo, None)
    historial = st.session_state.get("historial_decisiones")
    if isinstance(historial, list):
        # Un nombre puede reutilizarse para contenido distinto. No permita que
        # decisiones del PDF anterior se exporten junto con el nuevo documento.
        st.session_state["historial_decisiones"] = [
            decision for decision in historial
            if not isinstance(decision, dict)
            or decision.get("Archivo") != nombre_archivo
        ]
    revisiones = st.session_state.setdefault("extraction_revisions", {})
    revisiones[nombre_archivo] = revisiones.get(nombre_archivo, 0) + 1
    for state_key in (
            "resultados", "metadata_files", "document_intel", "extraction_pending",
            "extraction_resolved", "extraction_certifications", "processed_at",
            "quality_controls", "delivery_readiness",
    ):
        st.session_state.setdefault(state_key, {}).pop(nombre_archivo, None)
    st.session_state.pop("propagation_done", None)


_CAMPOS_METADATA_GENERAL = (
    "company_rut", "company_razon", "company_giro", "company_moneda",
    "company_mes", "company_anio", "company_numero_meses",
)


def _invalidar_metadata_general() -> None:
    """Invalida el testigo de vigencia del lote y campos heredados antiguos."""
    st.session_state["metadata_confirmada"] = False
    st.session_state.pop("metadata_confirmada_contexto", None)
    for campo in _CAMPOS_METADATA_GENERAL:
        st.session_state.pop(campo, None)


def _metadata_general_vigente(archivos) -> bool:
    """Comprueba que el testigo del lote pertenezca al primer documento actual."""
    if not st.session_state.get("metadata_confirmada", False):
        return True
    if not archivos:
        return False
    esperado = st.session_state.get("metadata_confirmada_contexto")
    return esperado == _contexto_metadata_general(archivos[0])


def _asegurar_metadata_general_vigente(archivos) -> bool:
    """Limpia el testigo global heredado si deja de coincidir con el lote.

    La metadata que alimenta el procesamiento ya se confirma por documento.
    Por ello, que cambie el primer PDF sólo vuelve inválido este residuo global:
    la sincronización de contextos se encarga, por separado, de invalidar el
    documento cuyo contenido o alcance cambió. No se deben descartar los
    resultados o revisiones de los demás archivos del lote.
    """
    if _metadata_general_vigente(archivos):
        return True
    _invalidar_metadata_general()
    return False


def _sincronizar_contextos_documentos(archivos) -> set[str]:
    """Detecta cambios externos de contenido o páginas antes de procesar.

    El formulario de alcance no es la única vía que puede cambiar
    ``document_pages`` en una sesión. Este control se ejecuta antes del retorno
    rápido del alcance para que ningún resultado, certificación o propagación
    sobreviva a un contexto distinto.
    """
    contextos_previos = st.session_state.setdefault("document_contexts", {})
    alcance_previo = st.session_state.get("document_scope_confirmed")
    nombres_actuales = {archivo.name for archivo in archivos}
    cambios: set[str] = set()

    contextos_actuales = {}
    for archivo in archivos:
        anterior = contextos_previos.get(archivo.name)
        actual = _contexto_confirmacion_anio(archivo)
        contextos_actuales[archivo.name] = actual
        # Una sesión creada antes de este registro no puede acreditar que sus
        # páginas actuales sean las mismas que originaron resultados previos.
        if anterior is None:
            hay_estado_derivado = any(
                archivo.name in st.session_state.get(clave, {})
                for clave in (
                    "resultados", "metadata_files", "document_intel",
                    "extraction_certifications", "document_closing_years",
                )
            )
            if alcance_previo or hay_estado_derivado:
                cambios.add(archivo.name)
        elif anterior != actual:
            cambios.add(archivo.name)

    for nombre in set(contextos_previos) - nombres_actuales:
        cambios.add(nombre)

    if not cambios:
        return cambios

    for nombre in cambios:
        # El resultado se invalida antes de descartar su confirmación de año.
        _invalidar_estado_documento(
            nombre, invalidar_metadata_documental=True,
        )
        st.session_state.setdefault("document_closing_years", {}).pop(nombre, None)
        if nombre in contextos_actuales:
            # Evita repetir la invalidación en cada rerun mientras el usuario
            # aún confirma el alcance, sin declarar el alcance como confirmado.
            contextos_previos[nombre] = contextos_actuales[nombre]
        else:
            contextos_previos.pop(nombre, None)
    # Conserva la firma anterior para comparar cada documento al enviar el
    # formulario. La bandera obliga a mostrarlo incluso si sólo cambiaron
    # páginas y el hash del archivo sigue siendo igual.
    st.session_state["document_scope_reconfirmation_required"] = True
    return cambios


def _documentos_con_alcance_modificado(
        signature, alcance_previo, paginas_previas, selecciones,
) -> set[str]:
    """Identifica sólo los documentos que requieren invalidación al confirmar."""
    firma_previa = dict(alcance_previo or ())
    return {
        nombre
        for nombre, digest in signature
        if (firma_previa.get(nombre) != digest
            or paginas_previas.get(nombre) != selecciones.get(nombre))
    }


def _opciones_anio_cierre(anio_detectado: int | None) -> list[int | None]:
    """Incluye una decisión explícita de no confirmar el período del documento."""
    opciones: list[int | None] = [None]
    opciones.extend(range(date.today().year + 2, 1978, -1))
    if anio_detectado is not None and anio_detectado not in opciones:
        opciones.append(anio_detectado)
        opciones[1:] = sorted(opciones[1:], reverse=True)
    return opciones


def _confirmar_anios_cierre_documentos(archivos) -> bool:
    """Pide y guarda una confirmación de año independiente para cada archivo.

    La opción sin año también exige una acción explícita del analista. Así los
    clasificadores dependientes del período reciben ``None`` en vez de un año
    supuesto por el nombre del archivo o por otro balance del lote.
    """
    if _modo_piloto_activo():
        return _confirmar_anios_autorizados_piloto(archivos)

    confirmaciones = st.session_state.setdefault("document_closing_years", {})
    nombres_actuales = {archivo.name for archivo in archivos}
    for nombre in list(confirmaciones):
        if nombre not in nombres_actuales:
            confirmaciones.pop(nombre, None)
    for archivo in archivos:
        if (archivo.name in confirmaciones
                and _registro_anio_confirmado_vigente(archivo) is None):
            confirmaciones.pop(archivo.name, None)

    editando = st.session_state.get("document_year_editing", False)
    if not editando and all(_confirmacion_anio_vigente(archivo) for archivo in archivos):
        return True

    st.subheader("Confirme el año de cierre por documento")
    st.info(
        "El año de cierre se confirma por cada archivo y se aplica sólo a sus "
        "cuentas. Si no puede confirmarlo desde las páginas seleccionadas, elija "
        "Sin año confirmado: las reglas dependientes del período serán conservadoras."
    )
    selecciones: dict[str, int | None] = {}
    with st.form("form_document_closing_years"):
        for archivo in archivos:
            try:
                meta_detectada = extraer_metadata(_extraer_lineas_encabezado(archivo))
                anio_detectado = _anio_cierre_detectado(meta_detectada)
            except Exception:  # La confirmación humana no depende de la detección.
                anio_detectado = None
            paginas = st.session_state.get("document_pages", {}).get(archivo.name)
            paginas_label = ", ".join(map(str, paginas or [])) or "todas"
            st.markdown(f"**{archivo.name}** · páginas: {paginas_label}")
            if anio_detectado is None:
                st.caption("No se detectó un año de cierre en las páginas seleccionadas.")
            else:
                st.caption(f"Año detectado en las páginas seleccionadas: {anio_detectado}.")
            opciones = _opciones_anio_cierre(anio_detectado)
            registro = _registro_anio_confirmado_vigente(archivo)
            valor_inicial = (
                _normalizar_anio_cierre(registro.get("anio_cierre"))
                if registro is not None else anio_detectado
            )
            if valor_inicial not in opciones:
                valor_inicial = None
            contexto = _contexto_confirmacion_anio(archivo)
            clave = hashlib.sha256(
                (contexto["sha256"] + repr(contexto["paginas"])).encode("utf-8")
            ).hexdigest()[:16]
            selecciones[archivo.name] = st.selectbox(
                "Año de cierre confirmado",
                opciones,
                index=opciones.index(valor_inicial),
                format_func=lambda anio: "Sin año confirmado" if anio is None else str(anio),
                key=f"document_year_{clave}",
            )
        submitted = st.form_submit_button("Confirmar años y procesar balances")

    if not submitted:
        return False

    confirmaciones_previas = dict(confirmaciones)
    confirmaciones_nuevas = {}
    documentos_a_reprocesar = []
    for archivo in archivos:
        anio_confirmado = _normalizar_anio_cierre(selecciones[archivo.name])
        contexto = _contexto_confirmacion_anio(archivo)
        nuevo = {
            **contexto,
            "anio_cierre": anio_confirmado,
            "confirmado": True,
        }
        anterior = confirmaciones_previas.get(archivo.name)
        if anterior is not None and anterior != nuevo:
            documentos_a_reprocesar.append(archivo.name)
        confirmaciones_nuevas[archivo.name] = nuevo
    st.session_state.document_closing_years = confirmaciones_nuevas
    for nombre_archivo in documentos_a_reprocesar:
        _invalidar_estado_documento(nombre_archivo)
    st.session_state.document_year_editing = False
    return True


def _confirmar_metadata_documentos(archivos) -> bool:
    """Confirma los datos contables por archivo antes de cualquier proceso.

    Cada confirmación conserva el hash y las páginas de su propio documento.
    No existe un valor general que se copie a los demás archivos del lote.
    """
    confirmaciones = st.session_state.setdefault(
        "document_metadata_confirmations", {},
    )
    nombres_actuales = {archivo.name for archivo in archivos}
    for nombre in list(confirmaciones):
        if nombre not in nombres_actuales:
            confirmaciones.pop(nombre, None)
    for archivo in archivos:
        if (archivo.name in confirmaciones
                and _registro_metadata_documental_vigente(archivo) is None):
            confirmaciones.pop(archivo.name, None)

    editando = st.session_state.get("document_metadata_editing", False)
    if (not editando
            and all(_metadata_documental_confirmada_vigente(archivo)
                    for archivo in archivos)):
        resumen = []
        for archivo in archivos:
            registro = _registro_metadata_documental_vigente(archivo)
            resumen.append({
                "Archivo": archivo.name,
                "RUT": registro.get("rut", ""),
                "Razón social": registro.get("razon_social", ""),
                "Giro": registro.get("giro", ""),
                "Moneda": registro.get("moneda", ""),
                "Cierre": registro.get("mes_cierre", ""),
                "Meses": registro.get("numero_meses", ""),
                "Año": _anio_cierre_confirmado_documento(archivo),
            })
        st.subheader("Datos confirmados por documento")
        st.caption(
            "Cada fila está vinculada al contenido y a las páginas seleccionadas "
            "de ese PDF."
        )
        st.dataframe(pd.DataFrame(resumen), hide_index=True, use_container_width=True)
        if st.button("Cambiar datos por documento"):
            st.session_state.document_metadata_editing = True
            st.rerun()
        return True

    st.subheader("Confirme los datos por documento")
    st.info(
        "Los valores iniciales provienen de cada archivo. Revise RUT, razón "
        "social, giro, moneda y período antes de procesar los balances."
    )
    selecciones: dict[str, dict] = {}
    with st.form("form_document_metadata"):
        for archivo in archivos:
            detectada = _campos_metadata_detectada(archivo)
            registro = _registro_metadata_documental_vigente(archivo)
            valores = _normalizar_campos_metadata_documental(
                registro if registro is not None else detectada,
            )
            contexto = _contexto_confirmacion_anio(archivo)
            clave = hashlib.sha256(
                (contexto["sha256"] + repr(contexto["paginas"])).encode("utf-8"),
            ).hexdigest()[:16]
            paginas = ", ".join(map(str, contexto["paginas"])) or "todas"
            anio = _anio_cierre_confirmado_documento(archivo)
            st.markdown(f"**{archivo.name}** · páginas: {paginas}")
            st.caption(
                "Año de cierre confirmado: "
                + (str(anio) if anio is not None else "Sin año confirmado")
            )
            col1, col2 = st.columns(2)
            with col1:
                rut = st.text_input(
                    "RUT", value=valores["rut"], key=f"document_rut_{clave}",
                )
                razon_social = st.text_input(
                    "Razón social", value=valores["razon_social"],
                    key=f"document_razon_{clave}",
                )
                giro = st.text_input(
                    "Giro", value=valores["giro"], key=f"document_giro_{clave}",
                    help=(
                        "Se usa sólo para las reglas que declaran compatibilidad "
                        "con ese giro."
                    ),
                )
            with col2:
                moneda = st.text_input(
                    "Moneda o unidad", value=valores["moneda"],
                    key=f"document_moneda_{clave}",
                    help="Ejemplos: $, M, MM, USD, EUR, UF o UTM.",
                )
                mes_cierre = st.selectbox(
                    "Mes de cierre", MESES_SELECCION,
                    index=MESES_SELECCION.index(valores["mes_cierre"]),
                    key=f"document_mes_{clave}",
                )
                numero_meses = st.selectbox(
                    "Número de meses del período", list(range(1, 13)),
                    index=list(range(1, 13)).index(valores["numero_meses"]),
                    key=f"document_meses_{clave}",
                )
            selecciones[archivo.name] = {
                "rut": rut,
                "razon_social": razon_social,
                "giro": giro,
                "moneda": moneda,
                "mes_cierre": mes_cierre,
                "numero_meses": numero_meses,
            }
            st.divider()
        submitted = st.form_submit_button("Confirmar datos por documento")

    if not submitted:
        return False

    confirmaciones_previas = dict(confirmaciones)
    confirmaciones_nuevas = {}
    documentos_a_reprocesar = []
    for archivo in archivos:
        contexto = _contexto_confirmacion_anio(archivo)
        nuevo = {
            **contexto,
            **_normalizar_campos_metadata_documental(selecciones[archivo.name]),
            "confirmado": True,
        }
        anterior = confirmaciones_previas.get(archivo.name)
        if anterior is not None and anterior != nuevo:
            documentos_a_reprocesar.append(archivo.name)
        confirmaciones_nuevas[archivo.name] = nuevo
    st.session_state.document_metadata_confirmations = confirmaciones_nuevas
    for nombre_archivo in documentos_a_reprocesar:
        _invalidar_estado_documento(nombre_archivo)
    st.session_state.document_metadata_editing = False
    # Se conserva únicamente como testigo de que el primer documento del lote
    # no cambió. Los datos de la empresa ya no alimentan el procesamiento.
    st.session_state.metadata_confirmada = True
    st.session_state.metadata_confirmada_contexto = _contexto_metadata_general(
        archivos[0],
    )
    return True


def _aplicar_metadata_confirmada(
        meta: MetadataEmpresa, *, archivo=None,
) -> MetadataEmpresa:
    """Aplica sólo la metadata confirmada para el documento recibido.

    Sin un archivo o sin confirmación vigente, los campos se limpian para que un
    llamador no vuelva a usar metadata de otro documento por accidente.
    """
    registro = (
        _registro_metadata_documental_vigente(archivo)
        if archivo is not None else None
    )
    if registro is None:
        for campo in _CAMPOS_METADATA_DOCUMENTAL:
            setattr(meta, campo, None if campo in {"mes_cierre", "numero_meses"} else "")
        anio_cierre = None
    else:
        valores = _normalizar_campos_metadata_documental(registro)
        for campo, valor in valores.items():
            setattr(meta, campo, valor)
        anio_cierre = _anio_cierre_confirmado_documento(archivo)
    meta.anio_cierre = anio_cierre
    if anio_cierre is None or not meta.mes_cierre or not meta.numero_meses:
        meta.periodo_desde = None
        meta.periodo_hasta = None
    else:
        meta.periodo_desde, meta.periodo_hasta = _fechas_periodo_seleccionado(
            meta.mes_cierre, anio_cierre, meta.numero_meses,
        )
    return meta

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')
UMBRAL_REVISION = 0.85  # bajo este valor, la cuenta va a la cola de revisión
USE_LEGACY_ENGINE = False  # True → MotorHibridoLocal (antiguo); False → HomologationPipeline (nuevo, default)
SHADOW_MODE = True  # True → ejecuta nuevo pipeline en paralelo sin afectar UI, guarda logs en logs/shadow/


def _modo_piloto_activo() -> bool:
    """Indica si la sesión debe impedir persistencia de revisiones.

    Las lecturas del catálogo y diccionario de Neon permanecen permitidas: son
    necesarias para que el piloto use el mismo conocimiento operativo y no
    modifican datos remotos.
    """
    return pilot_mode_active()


def _tiene_permiso_cuenta_local(permission: Permission) -> bool:
    """Aplica el rol local a las acciones de la interfaz cuando está activado.

    Cada balance del piloto es propio de la sesión actual. Por eso el recurso
    se marca con el actor y equipo actuales; no se concede acceso cruzado por
    sesión hasta que exista un almacén de trabajo compartido.
    """

    if not local_access_enabled():
        return True
    actor = st.session_state.get("local_access_actor")
    if actor is None:
        return False
    scope = ResourceScope(
        team_id=getattr(actor, "team_id", None),
        owner_id=getattr(actor, "actor_id", None),
    )
    return authorize(actor, permission, scope).allowed


def _diccionario_efectivo_para_actor_local(
    diccionario_base: list[dict], actor,
) -> tuple[list[dict], str]:
    """Compone el diccionario base con la superposición privada del equipo.

    La superposición se carga sólo para la identidad local autenticada. El
    administrador sin equipo conserva el diccionario base y revisa propuestas
    desde su vista de control; no hereda diccionarios de otros equipos.
    """

    team_id = getattr(actor, "team_id", None)
    if not team_id:
        return list(diccionario_base), "base"
    store = TeamDictionaryStore()
    team_entries = store.active_entries_for_team(str(team_id))
    version = store.revision_token_for_team(str(team_id))
    return (
        overlay_team_dictionary(diccionario_base, team_entries),
        f"team:{team_id}:{version}",
    )


def _usar_diccionario_equipo_local() -> bool:
    """Indica si una propuesta debe ir al diccionario privado del equipo."""

    if not local_access_enabled():
        return False
    actor = st.session_state.get("local_access_actor")
    return bool(getattr(actor, "team_id", None))


def _etiqueta_alcance_diccionario() -> str:
    """Evita presentar una propuesta de equipo como edición del original."""

    if _usar_diccionario_equipo_local():
        return "Proponer para el diccionario del equipo"
    return "Agregar al diccionario"


def _agregar_entrada_diccionario_sesion(entrada: dict) -> bool:
    """Agrega una decisión local sólo si no está ya representada.

    Una confirmación puede alcanzar a registrar la decisión antes de que un
    rerun posterior falle. El reintento debe ser seguro: no corresponde dejar
    dos entradas equivalentes sólo porque se repitió el botón.
    """

    diccionario = st.session_state.setdefault("diccionario", [])
    correcciones = st.session_state.setdefault("correcciones", [])
    if entrada in diccionario:
        return False
    diccionario.append(entrada)
    correcciones.append(entrada)
    return True


def _proponer_para_diccionario_equipo(
    *, nombre: str, codigo: str, nota: str,
) -> bool:
    """Guarda una propuesta local de equipo sin invocar persistencia global."""

    actor = st.session_state.get("local_access_actor")
    team_id = getattr(actor, "team_id", None)
    if actor is None or not team_id:
        st.error("No hay una identidad de equipo válida para registrar la propuesta.")
        return False
    try:
        TeamDictionaryStore().propose(
            actor,
            team_id=str(team_id),
            account_name=nombre,
            standard_code=codigo,
            note=nota,
        )
    except TeamDictionaryError as exc:
        st.warning(f"La clasificación se aplicó al caso, pero no se creó propuesta de equipo: {exc}")
        return False
    st.info(
        "La clasificación se aplicó al caso y quedó como propuesta para el "
        "diccionario del equipo. Jefatura debe activarla antes de usarla en casos futuros."
    )
    return True


def _token_local_carga_piloto(posicion: int) -> str:
    """Genera un token efímero de interfaz, no una identidad documental."""
    return f"upload-{posicion:02d}"


def _autorizacion_piloto_por_archivo(nombre_archivo: str) -> dict | None:
    """Busca la autorización ya resuelta, sin usar el nombre como evidencia."""
    registro = st.session_state.get(
        "pilot_manifest_authorizations", {},
    ).get(nombre_archivo)
    if not isinstance(registro, dict):
        return None
    document_id = registro.get("document_id")
    source_sha256 = registro.get("source_sha256")
    if (not isinstance(document_id, str) or not document_id
            or not isinstance(source_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None):
        return None
    return registro


def _hay_estado_derivado_documento(nombre_archivo: str) -> bool:
    """Identifica estado que no puede sobrevivir a otra autorización piloto."""
    return any(
        nombre_archivo in st.session_state.get(clave, {})
        for clave in (
            "resultados", "metadata_files", "document_intel",
            "extraction_pending", "extraction_resolved",
            "extraction_certifications", "document_closing_years",
            "document_metadata_confirmations", "delivery_readiness",
        )
    )


def _invalidar_autorizaciones_piloto(nombres_archivo) -> None:
    """Descarta todo resultado ligado a una autorización piloto reemplazada."""
    for nombre_archivo in set(nombres_archivo):
        _invalidar_estado_documento(
            nombre_archivo, invalidar_metadata_documental=True,
        )
        st.session_state.setdefault("document_closing_years", {}).pop(
            nombre_archivo, None,
        )
    st.session_state["document_year_editing"] = False
    st.session_state["document_metadata_editing"] = False


def _limpiar_autorizacion_piloto_actual(archivos) -> None:
    """Elimina una autorización previa cuando falta o falla el manifiesto."""
    contexto_anterior = st.session_state.get("pilot_manifest_context")
    anteriores = (
        contexto_anterior.get("authorizations", {})
        if isinstance(contexto_anterior, dict) else {}
    )
    nombres = set(anteriores) if isinstance(anteriores, dict) else set()
    nombres.update(archivo.name for archivo in archivos)
    afectados = {
        nombre for nombre in nombres
        if (isinstance(contexto_anterior, dict)
            or _hay_estado_derivado_documento(nombre))
    }
    if afectados:
        _invalidar_autorizaciones_piloto(afectados)
    st.session_state["pilot_manifest_authorizations"] = {}
    st.session_state.pop("pilot_manifest_context", None)
    st.session_state.pop("pilot_manifest_client_id", None)


def _contexto_autorizacion_piloto(archivos, manifest_sha256: str, match) -> dict:
    """Construye un contexto de sesión desde bytes y autorización ya validada."""
    authorizations = {}
    for posicion, archivo in enumerate(archivos, start=1):
        token = _token_local_carga_piloto(posicion)
        documento = match.token_to_document[token]
        contenido = archivo.getvalue()
        # ``archivo.name`` sólo conserva la asociación con la UI existente. La
        # evidencia de autorización viene exclusivamente del token y los bytes.
        authorizations[archivo.name] = {
            "document_id": documento.document_id,
            "confirmed_closing_year": documento.confirmed_closing_year,
            "source_sha256": hashlib.sha256(contenido).hexdigest(),
        }
    return {
        "manifest_sha256": manifest_sha256,
        "authorizations": authorizations,
    }


def _nombres_afectados_por_autorizacion_piloto(
        anterior, actual: dict,
) -> set[str]:
    """Delimita el alcance de una sustitución de manifiesto o asociación."""
    actuales = set(actual["authorizations"])
    if not isinstance(anterior, dict):
        return {
            nombre for nombre in actuales
            if _hay_estado_derivado_documento(nombre)
        }
    autorizaciones_anteriores = anterior.get("authorizations", {})
    if not isinstance(autorizaciones_anteriores, dict):
        return actuales
    anteriores = set(autorizaciones_anteriores)
    return {
        nombre
        for nombre in anteriores | actuales
        if autorizaciones_anteriores.get(nombre)
        != actual["authorizations"].get(nombre)
    }


def _mensaje_error_autorizacion_piloto(match, archivos) -> str:
    """Resume un rechazo del manifiesto sin filtrar datos del lote.

    La interfaz puede informar cuántos documentos autorizó el manifiesto y
    cuántos fueron cargados. No expone nombres, rutas, hashes ni ids opacos;
    esa información no es necesaria para corregir una carga incompleta.
    """
    codigos = sorted({error.code for error in match.errors})
    mensaje = "No se procesó el lote. Códigos: " + ", ".join(
        codigos or ["invalid_pilot_manifest"],
    )
    if "missing_uploaded_document" not in codigos:
        return mensaje

    esperados = len(getattr(match, "documents", ()) or ())
    cargados = len(archivos)
    if esperados > cargados:
        return (
            f"{mensaje}. El manifiesto autoriza {esperados} documento(s) y "
            f"se cargaron {cargados}. Cargue todos los documentos "
            "autorizados juntos."
        )
    return (
        f"{mensaje}. La cantidad cargada coincide con el manifiesto, pero "
        "al menos un archivo no coincide con su contenido autorizado."
    )


def _autorizar_lote_piloto(archivos, manifiesto) -> bool:
    """Autoriza el lote del piloto antes de cualquier lectura o procesamiento.

    La API de manifiesto concentra reglas de cliente, estado, límite y hash.
    Esta capa se limita a generar tokens locales por posición y a mantener la
    asociación autorizada para el ciclo de vida de la interfaz.
    """
    if manifiesto is None:
        _limpiar_autorizacion_piloto_actual(archivos)
        st.error("No se procesó el lote. Código: missing_pilot_manifest")
        return False
    if len({archivo.name for archivo in archivos}) != len(archivos):
        _limpiar_autorizacion_piloto_actual(archivos)
        st.error("No se procesó el lote. Código: duplicate_upload_name")
        return False
    try:
        manifest_bytes = manifiesto.getvalue()
        contenidos = {
            _token_local_carga_piloto(posicion): archivo.getvalue()
            for posicion, archivo in enumerate(archivos, start=1)
        }
        match = match_pilot_manifest_uploads_json(manifest_bytes, contenidos)
    except Exception:
        # No exponga detalles de contenido, rutas o el error del parser en UI.
        _limpiar_autorizacion_piloto_actual(archivos)
        st.error("No se procesó el lote. Código: invalid_pilot_manifest_input")
        return False

    if not match.valid:
        _limpiar_autorizacion_piloto_actual(archivos)
        st.error(_mensaje_error_autorizacion_piloto(match, archivos))
        return False

    contexto_actual = _contexto_autorizacion_piloto(
        archivos, hashlib.sha256(manifest_bytes).hexdigest(), match,
    )
    contexto_anterior = st.session_state.get("pilot_manifest_context")
    afectados = _nombres_afectados_por_autorizacion_piloto(
        contexto_anterior, contexto_actual,
    )
    if afectados:
        _invalidar_autorizaciones_piloto(afectados)
    st.session_state["pilot_manifest_authorizations"] = dict(
        contexto_actual["authorizations"],
    )
    st.session_state["pilot_manifest_context"] = contexto_actual
    st.session_state["pilot_manifest_client_id"] = match.client_id
    return True


def _confirmar_anios_autorizados_piloto(archivos) -> bool:
    """Vincula el año autorizado al documento sin ofrecer edición local."""
    confirmaciones_nuevas = {}
    documentos_a_reprocesar = []
    confirmaciones_anteriores = dict(
        st.session_state.setdefault("document_closing_years", {}),
    )
    for archivo in archivos:
        autorizacion = _autorizacion_piloto_por_archivo(archivo.name)
        if autorizacion is None:
            return False
        contexto = _contexto_confirmacion_anio(archivo)
        nuevo = {
            **contexto,
            "anio_cierre": autorizacion["confirmed_closing_year"],
            "confirmado": True,
            "origen": "pilot_manifest",
            "document_id": autorizacion["document_id"],
            "source_sha256": autorizacion["source_sha256"],
        }
        anterior = confirmaciones_anteriores.get(archivo.name)
        if anterior is not None and anterior != nuevo:
            documentos_a_reprocesar.append(archivo.name)
        confirmaciones_nuevas[archivo.name] = nuevo
    st.session_state["document_closing_years"] = confirmaciones_nuevas
    for nombre_archivo in documentos_a_reprocesar:
        _invalidar_estado_documento(nombre_archivo)
    st.session_state["document_year_editing"] = False
    st.caption(
        "Año de cierre vinculado al manifiesto autorizado. No se puede "
        "modificar desde esta sesión de piloto."
    )
    return True


def _referencia_exportacion_piloto(nombre_archivo: str) -> dict | None:
    """Obtiene la referencia opaca permitida para una exportación piloto."""
    autorizacion = _autorizacion_piloto_por_archivo(nombre_archivo)
    if autorizacion is None:
        return None
    return {
        "document_id": autorizacion["document_id"],
        "source_sha256": autorizacion["source_sha256"],
    }


def _nombre_descarga_piloto(nombre_archivo: str, tipo: str) -> str:
    """Genera un nombre opaco de descarga, sin RUT, razón ni nombre cargado."""
    referencia = _referencia_exportacion_piloto(nombre_archivo)
    if referencia is None:
        return f"PILOTO-{tipo}-NO_AUTORIZADO"
    document_id = re.sub(
        r"[^A-Za-z0-9._-]+", "_", referencia["document_id"],
    ).strip("._-") or "DOCUMENTO"
    return f"PILOTO-{tipo}-{document_id}-{referencia['source_sha256']}"


def _shadow_mode_activo() -> bool:
    """El shadow logger queda desactivado cuando el piloto no admite escrituras."""
    return SHADOW_MODE and not _modo_piloto_activo()


def _build_date() -> str:
    configured = os.environ.get("APP_BUILD_DATE")
    if configured:
        return configured
    try:
        return (BASE_DIR / ".build_date").read_text(encoding="utf-8").strip()
    except OSError:
        return "desarrollo-local"


def _trazabilidad_release_local() -> tuple[str, str]:
    """Obtiene rama y commit reales cuando no existen metadatos de despliegue."""
    branch = os.environ.get("APP_RELEASE_BRANCH")
    commit = os.environ.get("RENDER_GIT_COMMIT")
    if branch or commit:
        return branch or "desconocida", (commit or "desconocido")[:8]
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        commit_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "local", "local"
    resolved_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "local"
    resolved_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "local"
    return resolved_branch or "local", resolved_commit or "local"

st.set_page_config(
    page_title="Homologación de Balances Tributarios",
    page_icon="📊",
    layout="wide",
)


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE CATÁLOGO Y DICCIONARIO
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data
def cargar_catalogo() -> dict:
    with open(BASE_DIR / 'catalogo_maestro.json', encoding='utf-8') as f:
        catalogo_local = json.load(f)
    store = NeonKnowledgeStore()
    if store.enabled:
        try:
            catalogo_neon = store.load_catalog()
            if catalogo_neon:
                return {
                    codigo: {**entrada, **catalogo_neon.get(codigo, {})}
                    for codigo, entrada in catalogo_local.items()
                } | {
                    codigo: entrada for codigo, entrada in catalogo_neon.items()
                    if codigo not in catalogo_local
                }
        except Exception:
            pass
    return catalogo_local


@st.cache_data
def cargar_diccionario_base() -> list[dict]:
    store = NeonKnowledgeStore()
    if store.enabled:
        try:
            diccionario = store.load_dictionary()
            if diccionario:
                return diccionario
        except Exception:
            pass
    with open(BASE_DIR / 'diccionario.json', encoding='utf-8') as f:
        return json.load(f)


def _persistir_validacion(
    *, nombre: str, codigo: str, fuente: str, agregar_diccionario: bool,
    sugerido: str | None = None, metodo: str | None = None,
    confianza: float | None = None, archivo: str = '',
) -> bool:
    """Persiste en Neon salvo en el piloto no mutativo.

    Retornar ``True`` en piloto evita que los callers escriban el respaldo
    JSON. Las decisiones se mantienen sólo en ``session_state``.
    """
    if _modo_piloto_activo():
        return True
    store = NeonKnowledgeStore()
    if not store.enabled:
        return False
    try:
        store.save_validation(
            account_name=nombre,
            validated_code=codigo,
            source=fuente,
            suggested_code=sugerido,
            suggested_method=metodo,
            suggested_confidence=confianza,
            source_file=archivo,
            add_to_dictionary=agregar_diccionario,
        )
        cargar_diccionario_base.clear()
        return True
    except Exception:
        st.error("Neon no pudo guardar la validación; se usará respaldo local.")
        return False


def _persistir_validaciones_lote(validaciones: list[dict]) -> bool:
    """Persiste un lote completo en una única transacción Neon."""
    if _modo_piloto_activo():
        return True
    store = NeonKnowledgeStore()
    if not store.enabled:
        return False
    try:
        store.save_validations(validaciones)
        cargar_diccionario_base.clear()
        return True
    except Exception:
        st.error(
            "Neon no pudo guardar el lote; las clasificaciones permanecen "
            "en esta sesión y se usará el respaldo local del diccionario."
        )
        return False


def _persistir_catalogo(entry: dict) -> bool:
    if _modo_piloto_activo():
        return True
    store = NeonKnowledgeStore()
    if not store.enabled:
        return False
    try:
        store.save_catalog_entry(entry)
        cargar_catalogo.clear()
        return True
    except Exception:
        st.error("Neon no pudo guardar la categoría; se usará respaldo local.")
        return False


@st.cache_data(ttl=60)
def _neon_disponible() -> bool:
    return NeonKnowledgeStore().healthcheck()


# ─────────────────────────────────────────────────────────────────────────────
# REGLAS REGEX (patrones de mayor cobertura)
# ─────────────────────────────────────────────────────────────────────────────

PATRON_NO_CUENTA = re.compile(
    r'^(comprendido|periodo|per[ií]odo|desde|hasta|rut|r\.u\.t|balance|'
    r'fecha|p[aá]gina|hora|moneda|firma|declaro|art[ií]culo|situaci[oó]n|'
    r'cifras\s+expresadas|direcci[oó]n|comuna|^giro|raz[oó]n\s+soc|'
    r'^a\s+nivel|contabilidad\s+en)',
    re.IGNORECASE
)


def normalizar_nombre(nombre: str) -> str:
    n = nombre.lower().strip()
    n = re.sub(r"[^\w\sñáéíóú]", " ", n)
    n = re.sub(r"\s+", " ", n)
    return n.strip()


def _seleccion_lote_actualizada(
    seleccion_actual: set, indices: list, accion: str,
) -> set:
    """Calcula la selección en lote sin depender del ciclo de Streamlit."""
    seleccion = set(seleccion_actual)
    objetivos = set(indices)
    if accion == 'reemplazar':
        return objetivos
    if accion == 'agregar':
        return seleccion | objetivos
    if accion == 'quitar':
        return seleccion - objetivos
    raise ValueError(f"Acción de selección desconocida: {accion}")


def _reemplazar_seleccion_lote(indices: list, checkbox_prefix: str) -> None:
    """Sincroniza selección y widgets antes del único rerun normal."""
    anterior = set(st.session_state.get('lote_seleccion', set()))
    nueva = _seleccion_lote_actualizada(anterior, indices, 'reemplazar')
    st.session_state.lote_seleccion = nueva
    for idx in anterior | nueva:
        st.session_state[f"{checkbox_prefix}_{idx}"] = idx in nueva


def _alternar_seleccion_lote(idx, checkbox_key: str) -> None:
    """Actualiza una casilla sin encadenar un segundo st.rerun()."""
    accion = 'agregar' if st.session_state.get(checkbox_key, False) else 'quitar'
    st.session_state.lote_seleccion = _seleccion_lote_actualizada(
        set(st.session_state.get('lote_seleccion', set())), [idx], accion,
    )


def _asignar_estado_widget(key: str, value) -> None:
    """Permite que un botón actualice otro widget antes del rerun."""
    st.session_state[key] = value


def propagar_clasificacion_resultados(
        nombre_original: str, codigo_final: str, metodo: str,
        *, archivo_origen: str | None = None,
):
    """Propaga una decisión y deja trazado el documento que la originó."""
    nombre_norm = normalizar_nombre(nombre_original)
    resultados = st.session_state.get('resultados')
    if isinstance(resultados, dict):
        propagaciones = 0
        for fn in list(resultados.keys()):
            resultado = resultados[fn]
            columnas_requeridas = {
                'nombre_original', 'requiere_revision',
                'codigo_clasificado', 'confianza',
            }
            # Un documento bloqueado puede conservar un DataFrame vacío sin
            # columnas mientras otro documento del mismo lote se revisa. No
            # hay evidencia suficiente para propagar hacia esa tabla y, sobre
            # todo, no debe impedir confirmar la fila que el analista eligió.
            if (
                not isinstance(resultado, pd.DataFrame)
                or not columnas_requeridas.issubset(resultado.columns)
            ):
                continue
            df_res = resultado.copy()
            names = df_res['nombre_original'].fillna('').apply(normalizar_nombre)
            mask = names == nombre_norm
            mask_target = mask & (
                df_res['requiere_revision'] | 
                (df_res['codigo_clasificado'] == '') | 
                (df_res['confianza'] < 1.0)
            )
            if codigo_final != '__EXCLUIR__':
                compatibles = df_res.apply(
                    lambda row: _codigo_compatible_con_origen(
                        codigo_final,
                        row.get('origen_columna'),
                        row.get('monto'),
                        row.get('nombre_original'),
                        seccion_contable=row.get('seccion_contable'),
                        codigo_original=row.get('codigo_original'),
                        anio_cierre=row.get('anio_cierre'),
                    ),
                    axis=1,
                )
                mask_target &= compatibles
            if mask_target.any():
                df_res.loc[mask_target, 'codigo_clasificado'] = codigo_final
                df_res.loc[mask_target, 'metodo'] = metodo
                df_res.loc[mask_target, 'confianza'] = 1.0
                df_res.loc[mask_target, 'requiere_revision'] = False
                df_res.loc[mask_target, 'propagacion_origen_archivo'] = (
                    archivo_origen or ''
                )
                if 'origen' in df_res.columns:
                    df_res.loc[mask_target, 'origen'] = (
                        'Manual' if any(k in metodo for k in ('humana', 'manual')) else 'Código'
                    )
                    df_res.loc[mask_target, 'regla'] = metodo
                    df_res.loc[mask_target, 'evidencia'] = 'Propagación automática entre balances'
                resultados[fn] = df_res
                propagaciones += 1
        
        if propagaciones > 1:
            st.toast(f"Homologación propagada a {propagaciones - 1} otro(s) balance(s) 🔄", icon="🔄")


def _nombre_mostrar(row: pd.Series) -> str:
    return row.get('nombre_revision_usuario', '') or row['nombre_original']


# ─────────────────────────────────────────────────────────────────────────────
# EXPLICABILIDAD (P6) — trazabilidad auditable de cada decisión.
# Solo expone información existente: nunca modifica la decisión del motor.
# ─────────────────────────────────────────────────────────────────────────────

ORIGENES_EXPLICABILIDAD = [
    'Runtime', 'Gold', 'Código', 'Regex', 'CMCC', 'Semantic', 'Manual', 'Regla', 'Sin clasificar',
]

_BADGE_ORIGEN_COLORS = {
    'Runtime': '#7B1FA2', 'Gold': '#C2185B', 'Código': '#1565C0', 'Regex': '#00695C',
    'CMCC': '#EF6C00', 'Semantic': '#2E7D32', 'Manual': '#37474F',
    'Regla': '#F9A825', 'Sin clasificar': '#757575',
}


def _badge_origen(origen: str) -> str:
    color = _BADGE_ORIGEN_COLORS.get(origen or '', '#757575')
    label = origen or '—'
    return (
        f"<span style='background:{color}; color:white; padding:2px 8px; border-radius:4px; "
        f"font-size:0.72em; font-weight:600;'>{label}</span>"
    )


def _origen_desde_metodo_display(metodo: str) -> str:
    """Mapea el método de clasificación a la categoría de origen (solo lectura)."""
    m = (metodo or '').lower()
    if not m:
        return 'Sin clasificar'
    if m in ('sin_clasificar', 'unclassified', 'movement_only'):
        return 'Sin clasificar'
    if 'learning' in m or m.startswith('gold_') or m.startswith('runtime_'):
        return 'Gold'
    if 'cmcc' in m:
        return 'CMCC'
    if 'semantic' in m:
        return 'Semantic'
    if 'regex' in m:
        return 'Regex'
    if m.startswith('code') or m == 'codigo' or 'diccionario' in m or 'dictionary' in m:
        return 'Código'
    if 'decision' in m:
        return 'Regla'
    if 'propagad' in m:
        return 'Código'
    if any(k in m for k in ('validacion_humana', 'manual', 'excluido', 'lote')):
        return 'Manual'
    if 'regla_especial' in m or m == 'regla' or 'regla' in m:
        return 'Regla'
    if 'columna_ambiguo' in m:
        return 'Código'
    return 'Regla'


def _fmt_confianza(val) -> str:
    if val is None:
        return '—'
    if isinstance(val, float) and pd.isna(val):
        return '—'
    try:
        return f"{float(val):.0%}"
    except (TypeError, ValueError):
        return str(val)


def _learning_runtime_hit(account_name: str, hp) -> bool:
    """True si el learning_* vino del runtime (consulta read-only)."""
    try:
        rt = hp._learning_engine._runtime_lookup(account_name)
    except Exception:
        rt = None
    return rt is not None


def _origen_desde_clasif(clasif: dict, account_name: str, hp=None) -> str:
    """Origen (Runtime/Gold/Código/Regex/CMCC/Semantic) a partir del dict del motor."""
    metodo = (clasif.get('method') or '').lower()
    if metodo.startswith('learning_'):
        if hp is not None and _learning_runtime_hit(account_name, hp):
            return 'Runtime'
        return 'Gold'
    if metodo.startswith('cmcc'):
        return 'CMCC'
    if metodo.startswith('semantic'):
        return 'Semantic'
    if metodo.startswith('regex'):
        return 'Regex'
    if metodo.startswith('code') or metodo.startswith('diccionario') or metodo.startswith('dictionary'):
        return 'Código'
    if metodo.startswith('decision'):
        de = clasif.get('decision_engine') or {}
        src = (de.get('decision_source') or '').upper()
        if 'SM' in src:
            return 'Semantic'
        if 'REGEX' in src:
            return 'Regex'
        if 'DICT' in src:
            return 'Código'
        return 'Regla'
    if metodo in ('', 'unclassified', 'movement_only'):
        return 'Sin clasificar'
    return 'Regla'


def _resolver_tipo_cuenta(origen_columna, codigo) -> str | None:
    """Account type (read-only) para etapas sensibles al tipo. Never modifica nada."""
    if str(getattr(origen_columna, 'value', origen_columna) or '').lower() == 'patrimonio':
        return 'PATRIMONIO'
    try:
        from parser_universal import OrigenColumna as _OC
        from parsers.account_type_resolver import AccountTypeResolver
        origen = _OC(origen_columna) if origen_columna else _OC.DESCONOCIDO
        return AccountTypeResolver().resolve(origen_columna=origen, codigo=codigo).account_type.value
    except Exception:
        return None


def _resolver_tipos_permitidos(origen_columna) -> set[str]:
    """Tipos compatibles con la columna, conservando sus ambiguedades reales."""
    if str(getattr(origen_columna, 'value', origen_columna) or '').lower() == 'patrimonio':
        return {'PATRIMONIO'}
    try:
        from parser_universal import OrigenColumna as _OC
        from parsers.account_type_resolver import AccountTypeResolver
        origen = _OC(origen_columna) if origen_columna else _OC.DESCONOCIDO
        resultado = AccountTypeResolver().resolve(origen_columna=origen)
        return {tipo.value for tipo in resultado.allowed_types}
    except Exception:
        return set()


_CONTRA_ORIGEN = {
    'activo': 'pasivo',
    'pasivo': 'activo',
    'perdida': 'ganancia',
    'ganancia': 'perdida',
}


def _origen_efectivo(
        origen_columna, monto, nombre: str | None = None,
        seccion_contable: str | None = None,
        *, codigo_original: str | None = None, anio_cierre: int | None = None,
) -> str:
    """Naturaleza contable efectiva, preservando aparte la columna física.

    En balances de 8 columnas un importe negativo representa una contra cuenta:
    ACTIVO <-> PASIVO y PERDIDA <-> GANANCIA.
    """
    origen = getattr(origen_columna, 'value', origen_columna)
    origen = str(origen or 'desconocido').strip().lower()
    if (_es_resultado_historico_acumulado(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
    ) or _es_resultado_anual_del_cierre(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
    )):
        return 'patrimonio'
    seccion = account_type_from_explicit_section(seccion_contable)
    if seccion is not None:
        return seccion.value.lower()
    if _es_partida_patrimonial(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
    ):
        return 'patrimonio'
    try:
        es_negativo = monto is not None and pd.notna(monto) and float(monto) < 0
    except (TypeError, ValueError):
        es_negativo = False
    return _CONTRA_ORIGEN.get(origen, origen) if es_negativo else origen


def _etiqueta_origen(
        origen_columna, monto, nombre: str | None = None,
        seccion_contable: str | None = None,
        *, codigo_original: str | None = None, anio_cierre: int | None = None,
) -> str:
    """Etiqueta auditable para la cola: extracción y naturaleza efectiva."""
    extraido = getattr(origen_columna, 'value', origen_columna)
    extraido = str(extraido or 'desconocido').strip().upper()
    efectivo = _origen_efectivo(
        origen_columna, monto, nombre, seccion_contable,
        codigo_original=codigo_original,
        anio_cierre=anio_cierre,
    ).upper()
    if (_es_resultado_historico_acumulado(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
    ) or _es_resultado_anual_del_cierre(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
    )):
        return f"{extraido} → PATRIMONIO (naturaleza de la cuenta)"
    if account_type_from_explicit_section(seccion_contable) is not None:
        if efectivo != extraido:
            return f"{extraido} → {efectivo} (sección observada)"
        return extraido
    if _es_partida_patrimonial(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
    ):
        return f"{extraido} → PATRIMONIO (naturaleza de la cuenta)"
    if efectivo != extraido:
        return f"{extraido} → {efectivo} (monto negativo)"
    return extraido


def _es_contra_activo(
        nombre: str | None, origen_columna=None, monto=None,
) -> bool:
    """Reconoce cuentas acreedoras que corrigen el valor de un activo."""
    return (
        is_contra_asset_name(nombre)
        or is_credit_balance_depreciation_name(
            nombre, origen_columna, monto,
        )
    )


def _es_resultado_historico_acumulado(
        nombre: str | None,
        *, codigo_original: str | None = None,
        anio_cierre: int | None = None,
) -> bool:
    """Delega la excepción histórica al predicado semántico compartido.

    No basta una glosa ``RESULTADO AÑO``: el resolver exige código fuente y
    año de cierre para distinguir el resultado del ejercicio del acumulado.
    """
    return is_historical_accumulated_result_name(
        nombre,
        account_code=codigo_original,
        closing_year=anio_cierre,
    )


def _es_resultado_anual_del_cierre(
        nombre: str | None,
        *, codigo_original: str | None = None,
        anio_cierre: int | None = None,
) -> bool:
    """Reconoce sólo el resultado explícito del año de cierre confirmado."""
    try:
        cierre_confirmado = int(anio_cierre) if anio_cierre is not None else None
    except (TypeError, ValueError):
        return False
    return (
        cierre_confirmado is not None
        and result_year_from_name(nombre) == cierre_confirmado
        and is_accumulated_result_2402_code(codigo_original)
    )


def _es_partida_patrimonial(
        nombre: str | None,
        *, codigo_original: str | None = None,
        anio_cierre: int | None = None,
) -> bool:
    return (
        is_patrimonial_reserve_name(nombre)
        or is_accumulated_result_name(
            nombre,
            account_code=codigo_original,
            closing_year=anio_cierre,
        )
        or _es_resultado_anual_del_cierre(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
        )
        or is_current_result_name(nombre)
        or is_capital_pending_name(nombre)
    )


def _monto_presentacion(codigo: str | None, monto, nombre: str | None = None,
                        origen=None, catalogo=None) -> float:
    """Aplica el signo contable sin alterar el importe extraído auditable."""
    valor = 0.0 if pd.isna(monto) else float(monto)
    if str(codigo or '').startswith('ER.') and origen is not None:
        resultado = importe_resultado_homologado(codigo, valor, origen, catalogo)
        if resultado is not None:
            return resultado
    return importe_presentacion_balance(
        str(codigo or ''), valor, nombre or '', origen,
    )


def _resultado_periodo(clasificadas: pd.DataFrame) -> float | None:
    """Calcula ganancia menos pérdida desde las columnas efectivas extraídas."""
    ganancias = 0.0
    perdidas = 0.0
    encontro_resultado = False
    for _, row in clasificadas.iterrows():
        origen = row.get('origen_columna_efectiva') or _origen_efectivo(
            row.get('origen_columna'), row.get('monto'), row.get('nombre_original'),
            codigo_original=row.get('codigo_original'),
            anio_cierre=row.get('anio_cierre'),
        )
        monto = abs(float(row.get('monto') or 0.0))
        if origen == 'ganancia':
            ganancias += monto
            encontro_resultado = True
        elif origen == 'perdida':
            perdidas += monto
            encontro_resultado = True
    return ganancias - perdidas if encontro_resultado else None


def _codigo_compatible_con_origen(
        codigo: str | None, origen_columna, monto, nombre: str | None = None,
        catalogo=None, *, seccion_contable: str | None = None,
        codigo_original: str | None = None, anio_cierre: int | None = None,
) -> bool:
    """Impide sugerencias que contradigan la columna efectiva del balance."""
    origen_efectivo = _origen_efectivo(
        origen_columna, monto, nombre, seccion_contable,
        codigo_original=codigo_original,
        anio_cierre=anio_cierre,
    )
    if not resultado_compatible(codigo, origen_efectivo, catalogo):
        return False
    # En una glosa anual explícita no basta una sección que parezca
    # patrimonial: PAT.03 y PAT.04 requieren respectivamente la evidencia
    # histórica o de año de cierre de la familia fuente 2402-. Esto conserva
    # las demás alternativas manuales, pero impide que el selector convierta
    # un "RESULTADO AÑO" no respaldado en resultado acumulado o del ejercicio.
    if result_year_from_name(nombre) is not None:
        if str(codigo or '') == 'PAT.03':
            return _es_resultado_historico_acumulado(
                nombre,
                codigo_original=codigo_original,
                anio_cierre=anio_cierre,
            )
        if str(codigo or '') == 'PAT.04':
            return _es_resultado_anual_del_cierre(
                nombre,
                codigo_original=codigo_original,
                anio_cierre=anio_cierre,
            )
    if _es_resultado_historico_acumulado(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
    ):
        return str(codigo or '') == 'PAT.03'
    if _es_resultado_anual_del_cierre(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
    ):
        return str(codigo or '') == 'PAT.04'
    seccion = account_type_from_explicit_section(seccion_contable)
    if seccion is not None:
        # Una cabecera explícita es más precisa que la ambigüedad general de
        # la columna física PASIVO, que puede incluir patrimonio en balances
        # clasificados de dos columnas.
        from pipeline.homologation_pipeline import HomologationPipeline
        return HomologationPipeline._is_code_allowed_for_tipo(codigo, seccion.value)
    if str(codigo or '').startswith('ER.') and origen_efectivo in {'ganancia', 'perdida'}:
        return True
    # Una depreciación/amortización acumulada puede venir físicamente en la
    # columna Pasivo por su saldo acreedor, pero contablemente es contra-activo
    # y debe poder homologarse dentro del activo fijo (ANC).
    if (origen_efectivo == 'pasivo' and _es_contra_activo(
            nombre, origen_columna, monto,
    )
            and str(codigo or '').startswith('ANC')):
        return True
    if (_es_partida_patrimonial(
            nombre,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
    ) and str(codigo or '').startswith('PAT')):
        return True
    if (origen_efectivo == 'activo' and str(codigo or '') == 'PAT.10'
            and es_cuenta_socios(nombre)):
        return True
    # Una obligación bancaria puede exhibir saldo deudor y por ello aparecer
    # físicamente bajo ACTIVO/DEUDOR. Se permite como contra-pasivo sólo para
    # la glosa bancaria acotada; el flujo de clasificación la deja siempre en
    # revisión humana y no sustituye la columna de origen.
    if (
            str(codigo or '').startswith(('PC.', 'PNC.'))
            and is_debit_balance_financial_liability(
                nombre, origen_columna, monto,
            )):
        return True
    tipos = _resolver_tipos_permitidos(origen_efectivo)
    if not tipos:
        return True
    from pipeline.homologation_pipeline import HomologationPipeline
    return any(
        HomologationPipeline._is_code_allowed_for_tipo(codigo, tipo)
        for tipo in tipos
    )


def _pendientes_revision(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve solo cuentas revisables: no totales y con saldo distinto de cero."""
    pendientes = df[df['requiere_revision'] | (df['codigo_clasificado'] == '')]
    pendientes = pendientes[~pendientes['es_total']]
    montos = pd.to_numeric(pendientes['monto'], errors='coerce')
    return pendientes[montos.isna() | montos.ne(0)]


def _resumen_revision_operativa(df: pd.DataFrame) -> dict[str, int]:
    """Separa revisión contable de cotejo acotado de extracción.

    Los controles de extracción y las filas de monto cero no son cuentas
    operables. La separación evita que una excepción OCR delimitada parezca
    una revisión masiva de clasificación.
    """
    vacio = {
        'operables': 0,
        'automaticas': 0,
        'revision_contable': 0,
        'cotejo_ocr': 0,
        'propuestas_bloqueadas_extraccion': 0,
        'sin_clasificar': 0,
        'cola_total': 0,
    }
    if df.empty:
        return vacio
    es_total = (
        df['es_total'].fillna(False).astype(bool)
        if 'es_total' in df else pd.Series(False, index=df.index)
    )
    montos = (
        pd.to_numeric(df['monto'], errors='coerce')
        if 'monto' in df
        else pd.Series(float('nan'), index=df.index)
    )
    operables = df.loc[~es_total & (montos.isna() | montos.ne(0))]
    if operables.empty:
        return vacio
    requiere_revision = (
        operables['requiere_revision'].fillna(False).astype(bool)
        if 'requiere_revision' in operables
        else pd.Series(False, index=operables.index)
    )
    codigo = (
        operables['codigo_clasificado'].fillna('').astype(str).str.strip()
        if 'codigo_clasificado' in operables
        else pd.Series('', index=operables.index)
    )
    revision_extraccion = (
        operables['revision_extraccion'].fillna(False).astype(bool)
        if 'revision_extraccion' in operables
        else pd.Series(False, index=operables.index)
    )
    en_revision = requiere_revision | codigo.eq('')
    cotejo_ocr = en_revision & revision_extraccion
    revision_contable = en_revision & ~cotejo_ocr
    propuestas_bloqueadas_extraccion = cotejo_ocr & codigo.ne('')
    return {
        'operables': int(len(operables)),
        'automaticas': int((~en_revision & codigo.ne('')).sum()),
        'revision_contable': int(revision_contable.sum()),
        'cotejo_ocr': int(cotejo_ocr.sum()),
        'propuestas_bloqueadas_extraccion': int(
            propuestas_bloqueadas_extraccion.sum(),
        ),
        'sin_clasificar': int(codigo.eq('').sum()),
        'cola_total': int(en_revision.sum()),
    }


def _archivo_activo_preferido(
        nombres_archivo: list[str], resultados: dict[str, pd.DataFrame],
) -> str | None:
    """Prioriza un documento con cuentas cuando otro quedó bloqueado.

    La preferencia se usa sólo al iniciar o cuando la selección anterior ya no
    pertenece al lote. Una selección explícita del analista siempre prevalece.
    Así, en un lote mixto, una extracción fallida no oculta un documento que sí
    puede continuar a revisión asistida.
    """
    for nombre in nombres_archivo:
        resultado = resultados.get(nombre)
        if resultado is not None and not resultado.empty:
            return nombre
    return nombres_archivo[0] if nombres_archivo else None


def _seleccion_activa_para_lote(
        nombres_archivo: list[str], resultados: dict[str, pd.DataFrame],
        lote_anterior: tuple[str, ...] | None, seleccion_previa: str | None,
) -> str | None:
    """Devuelve la selección inicial segura sin pisar una elección vigente."""
    lote_actual = tuple(nombres_archivo)
    if lote_anterior == lote_actual and seleccion_previa in nombres_archivo:
        return seleccion_previa
    return _archivo_activo_preferido(nombres_archivo, resultados)


def _etiqueta_estado_archivo_cargado(resultado, certificacion) -> str:
    """Resume el estado individual de un documento en la barra lateral."""
    estado = str(getattr(certificacion, "estado", "") or "")
    if resultado is not None and not resultado.empty:
        if estado == "parcial":
            return "revisión asistida"
        if estado == "certificada":
            return "extracción certificada"
        if estado == "no_evaluable":
            return "revisión requerida"
        return "procesado"
    if estado == "fallida":
        return "bloqueado: extracción no validada"
    return "pendiente de procesamiento"


def _lineas_revision_por_extraccion(certificacion) -> set[int] | None:
    """Delimita filas reconstruidas sólo cuando el parser las identificó.

    ``None`` mantiene la regla histórica segura: toda extracción no
    certificada requiere revisión. Un conjunto no vacío es la excepción
    documentada de reconstrucciones acotadas con controles fuente exactos;
    permite enfocar el cotejo sin presentar el documento como listo para
    integrar.
    """
    if getattr(certificacion, 'estado', '') == 'certificada':
        return set()
    if getattr(certificacion, 'orientacion_certificada', None) is False:
        return None
    if bool(getattr(certificacion, 'reconstruccion_final_revisable', False)):
        reconstrucciones = getattr(
            certificacion, 'reconstrucciones_finales', [],
        ) or []
    elif bool(getattr(
            certificacion, 'reconstruccion_movimientos_revisable', False,
    )):
        reconstrucciones = getattr(
            certificacion, 'reconstrucciones_movimientos', [],
        ) or []
    else:
        return None
    lineas: set[int] = set()
    for reconstruccion in reconstrucciones:
        try:
            lineas.add(int(reconstruccion['linea']))
        except (KeyError, TypeError, ValueError):
            return None
    return lineas or None


def _requiere_revision_por_extraccion(certificacion, linea: int | None = None) -> bool:
    """Evita automatismos fuera de las filas que el parser pudo delimitar."""
    lineas = _lineas_revision_por_extraccion(certificacion)
    if lineas is None:
        return getattr(certificacion, 'estado', '') != 'certificada'
    if linea is None:
        return bool(lineas)
    return int(linea) in lineas


def _nota_revision_por_extraccion(certificacion) -> str:
    if bool(getattr(certificacion, 'reconstruccion_final_revisable', False)):
        return (
            'Cifra final reconstruida con controles fuente concordantes: '
            'coteje esta fila contra el original antes de confirmar.'
        )
    if bool(getattr(
            certificacion, 'reconstruccion_movimientos_revisable', False,
    )):
        return (
            'Movimiento auxiliar reconstruido con controles fuente '
            'concordantes: coteje esta fila contra el original antes de '
            'confirmar.'
        )
    estado = getattr(certificacion, 'estado', '') or 'sin certificación'
    return (
        'Extracción no certificada (' + str(estado)
        + '): requiere revisión humana antes de confirmar la clasificación.'
    )


def _fila_control_extraccion(cuenta) -> dict:
    """Conserva un control de cuadratura sin enviarlo al clasificador."""
    monto = cuenta.monto
    seccion_contable = getattr(cuenta, 'seccion_contable', None)
    origen_efectivo = _origen_efectivo(
        cuenta.origen_columna, monto, cuenta.nombre, seccion_contable,
    )
    periodos = getattr(cuenta, 'montos_periodos', {}) or {}
    return {
        'linea': cuenta.linea,
        'codigo_original': cuenta.codigo or '',
        'nombre_original': cuenta.nombre,
        'nombre_normalizado': normalizar_nombre(cuenta.nombre),
        'monto': monto,
        'monto_periodo_actual': periodos.get('actual'),
        'monto_periodo_anterior': periodos.get('anterior'),
        'columnas_derivadas': ', '.join(cuenta.columnas_derivadas),
        'origen_columna': cuenta.origen_columna.value,
        'seccion_contable': seccion_contable or '',
        'estado_financiero': getattr(cuenta, 'estado_financiero', None) or '',
        'origen_columna_efectiva': origen_efectivo,
        'es_total': True,
        'codigo_clasificado': '',
        'metodo': 'extraction_control',
        'confianza': 1.0,
        'requiere_revision': False,
        'revision_extraccion': False,
        'nota': 'Control de cuadratura: no se clasifica como cuenta.',
        'confianza_extraccion': cuenta.confianza_extraccion,
        'origen_columna_display': _etiqueta_origen(
            cuenta.origen_columna, monto, cuenta.nombre, seccion_contable,
        ),
        'nombre_revision_usuario': '',
        'tipo_revision': '',
        'origen': 'Control',
        'regla': 'extraction_control',
        'evidencia': 'Control de cuadratura conservado fuera de la clasificación.',
        'tiempo_clasificacion': 0.0,
    }


def _con_saldo_relevante(df: pd.DataFrame) -> pd.DataFrame:
    """Excluye filas con saldo cero de clasificación, resumen y exportación."""
    montos = pd.to_numeric(df['monto'], errors='coerce')
    return df[montos.isna() | montos.ne(0)]


def _alternativas_revision(
    *, nombre: str, sugerido: str, confianza: float,
    origen_columna, monto, catalogo: dict, motor,
    seccion_contable: str | None = None,
    codigo_original: str | None = None,
    anio_cierre: int | None = None,
    limite: int = 3,
) -> list[dict]:
    """Rankea candidatos compatibles sin alterar la decisión del motor."""
    candidatos: dict[str, dict] = {}

    def agregar(codigo: str | None, score: float, fuente: str, evidencia: str):
        if not codigo or codigo not in catalogo:
            return
        if not _codigo_compatible_con_origen(
            codigo, origen_columna, monto, nombre, catalogo,
            seccion_contable=seccion_contable,
            codigo_original=codigo_original,
            anio_cierre=anio_cierre,
        ):
            return
        item = {
            "codigo": codigo,
            "nombre": catalogo[codigo].get("nombre_estandar", codigo),
            "score": max(0.0, min(float(score), 1.0)),
            "fuente": fuente,
            "evidencia": evidencia,
        }
        previous = candidatos.get(codigo)
        if previous is None or item["score"] > previous["score"]:
            candidatos[codigo] = item

    agregar(
        sugerido or None,
        float(confianza or 0.0),
        "Sugerencia actual",
        "Clasificación producida por el pipeline operativo.",
    )

    normalized = normalizar_nombre(nombre)
    dictionary_names = getattr(motor, "dic_lista", []) or []
    dictionary = getattr(motor, "dic_exacto", {}) or {}
    if normalized and dictionary_names:
        for matched_name, similarity, _ in process.extract(
            normalized, dictionary_names,
            scorer=fuzz.token_set_ratio, limit=max(limite * 3, 8),
        ):
            if similarity < 55:
                continue
            entry = dictionary.get(matched_name) or {}
            source = str(entry.get("fuente") or "Diccionario")
            human = any(token in source.lower() for token in (
                "human", "manual", "validacion", "analista",
            ))
            agregar(
                entry.get("codigo_estandar"),
                similarity / 100.0 + (0.03 if human else 0.0),
                "Neon · validación humana" if human else "Diccionario",
                f"Cuenta similar: {entry.get('cuenta_original', matched_name)} "
                f"({similarity:.0f}% de similitud).",
            )

    catalog_names = {
        codigo: normalizar_nombre(str(entry.get("nombre_estandar") or codigo))
        for codigo, entry in catalogo.items()
    }
    for codigo, catalog_name in catalog_names.items():
        similarity = fuzz.token_set_ratio(normalized, catalog_name)
        if similarity >= 58:
            agregar(
                codigo, similarity / 100.0, "Catálogo maestro",
                f"Nombre estándar similar: {catalogo[codigo].get('nombre_estandar', codigo)} "
                f"({similarity:.0f}%).",
            )

    return sorted(
        candidatos.values(),
        key=lambda item: (-item["score"], item["codigo"]),
    )[:max(1, int(limite))]


def _explicar_clasificacion(hp, account_code: str, account_name: str, *,
                            account_tipo: str | None = None,
                            origen_columna=None,
                            metodo_actual: str = '') -> list[dict]:
    """Reconstrucción read-only de las reglas evaluadas para la UI.

    No ejecuta ni modifica la decisión del motor: re-evalúa cada etapa para
    auditar la cadena de decisión. Cada lectura va envuelta en try/except para
    que un fallo en una etapa nunca rompa la UI.
    """
    etapas: list[dict] = []

    def _agregar(nombre, result, metodo):
        if result is None:
            etapas.append({
                'regla': nombre, 'coincidio': False, 'resultado': '—',
                'confianza': '—', 'detalle': 'Sin coincidencia', 'ganadora': False,
                '_metodo': metodo,
            })
            return
        detalle = result.get('reason') if isinstance(result, dict) else None
        etapas.append({
            'regla': nombre, 'coincidio': True,
            'resultado': result.get('standard_code') or '—',
            'confianza': _fmt_confianza(result.get('confidence')),
            'detalle': detalle or 'Coincidencia',
            'ganadora': False,
            '_metodo': metodo,
        })

    try:
        _agregar('1 · Código de cuenta',
                 hp._classify_by_code(account_code) if account_code else None, 'code')
    except Exception:
        pass
    try:
        _agregar('2 · Diccionario (exacto)',
                 hp._classify_by_dictionary_exact(account_name), 'dictionary_exact')
    except Exception:
        pass
    try:
        _agregar('3 · Diccionario (fuzzy)',
                 hp._classify_by_dictionary_fuzzy(account_name), 'dictionary_fuzzy')
    except Exception:
        pass
    try:
        _regex = None
        if hp._features.ENABLE_REGEX_FALLBACK:
            _regex = hp._classify_by_regex(account_name, account_tipo)
        _agregar('4 · Regex fallback', _regex, 'regex_fallback')
    except Exception:
        pass
    try:
        _rt = None
        if hp._learning_engine._runtime_path.exists():
            _rt = hp._learning_engine._runtime_lookup(account_name)
        if _rt is not None:
            _agregar('5 · Runtime (gold runtime)', _rt, f"learning_{_rt.get('source')}")
    except Exception:
        pass
    try:
        _gold = hp._learning_engine.best_match(account_name, use_runtime=False)
        if _gold.get('source') != 'none':
            _agregar('6 · Gold Standard', _gold, f"learning_{_gold.get('source')}")
    except Exception:
        pass
    try:
        if hp._features.ENABLE_CMCC:
            _cmcc = hp._cmcc_classifier.classify(account_name)
            _agregar('7 · CMCC', _cmcc, (_cmcc or {}).get('method', 'cmcc'))
    except Exception:
        pass
    try:
        if hp._features.ENABLE_SEMANTIC_MATCHER and hp._semantic_matcher is not None:
            _sm = hp._semantic_matcher.match(account_name, account_tipo)
            if _sm is not None and not _sm.is_unknown:
                _agregar(
                    '8 · Semantic',
                    {'standard_code': _sm.expected_cmcc,
                     'confidence': min(_sm.score, 0.99),
                     'reason': f"tier={_sm.match_tier} concept={_sm.concept_name}"},
                    f"semantic_{_sm.match_tier}",
                )
    except Exception:
        pass

    ma = (metodo_actual or '').lower()
    if ma.startswith('learning_'):
        for e in etapas:
            if str(e.get('_metodo', '')).startswith('learning_'):
                e['ganadora'] = True
                break
    else:
        for e in etapas:
            if e.get('_metodo') == ma:
                e['ganadora'] = True
                break
    return etapas


def _mostrar_detalle_cuenta(row: pd.Series, catalogo: dict, hp=None, close_key: str | None = None):
    if close_key:
        if st.button('✖ Cerrar detalle', key=f"close_{close_key}"):
            st.session_state.pop(close_key, None)
            st.rerun()

    st.markdown('#### 🔍 Detalle de clasificación')
    nombre = _nombre_mostrar(row)
    origen = row.get('origen') if 'origen' in row.index else ''
    origen = origen or _origen_desde_metodo_display(row.get('metodo', ''))
    regla = row.get('regla') if 'regla' in row.index else ''
    regla = regla or row.get('metodo', '')
    evidencia = row.get('evidencia') if 'evidencia' in row.index else ''
    evidencia = evidencia or row.get('nota', '') or 'Sin evidencia adicional.'
    tiempo = row.get('tiempo_clasificacion') if 'tiempo_clasificacion' in row.index else None

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Nombre original:** {nombre}")
        nombre_norm = row.get('nombre_normalizado') if 'nombre_normalizado' in row.index else ''
        st.markdown(f"**Nombre normalizado:** `{nombre_norm or normalizar_nombre(nombre)}`")
        st.markdown(f"**Código final:** `{row.get('codigo_clasificado', '') or '(sin clasificar)'}`")
    with c2:
        st.markdown(f"**Regla ganadora:** `{regla}`")
        st.markdown(f"**Score:** **{_fmt_confianza(row.get('confianza'))}**")
        st.markdown(f"**Confianza:** {_fmt_confianza(row.get('confianza'))}")
        st.markdown(f"**Origen:** {_badge_origen(origen)}", unsafe_allow_html=True)
        tiempo_txt = f"{tiempo:.2f} ms" if tiempo is not None and pd.notna(tiempo) else '—'
        st.markdown(f"**Tiempo de clasificación:** {tiempo_txt}")
        st.markdown(f"**Runtime usado:** {'Sí' if origen == 'Runtime' else 'No'}")
        st.markdown(f"**Gold usado:** {'Sí' if origen == 'Gold' else 'No'}")

    st.markdown('**Evidencia:**')
    st.info(evidencia)

    if hp is not None:
        etapas = _explicar_clasificacion(
            hp,
            row.get('codigo_original', '') or '',
            nombre,
            origen_columna=row.get('origen_columna'),
            metodo_actual=regla,
        )
        if etapas:
            st.markdown('**Reglas evaluadas (auditoría read-only):**')
            df_etapas = pd.DataFrame([
                {k: v for k, v in e.items() if not k.startswith('_')} for e in etapas
            ])
            st.dataframe(df_etapas, use_container_width=True, hide_index=True)


def _tab_explicabilidad(df: pd.DataFrame, catalogo: dict, hp=None, archivo_nombre: str = ''):
    st.subheader('🔍 Explicabilidad de clasificación')
    st.caption(
        'Trazabilidad auditable por cuenta: código final, origen, score, regla, evidencia y '
        'confianza. La auditoría es de solo lectura y no modifica decisiones del motor.'
    )

    clasificadas = df[
        (df['codigo_clasificado'] != '') &
        (df['codigo_clasificado'] != '__EXCLUIR__') &
        (~df['es_total'])
    ].copy()
    if clasificadas.empty:
        st.info('No hay cuentas clasificadas para auditar.')
        return

    if 'origen' not in clasificadas.columns:
        clasificadas['origen'] = clasificadas['metodo'].map(_origen_desde_metodo_display)
    if 'regla' not in clasificadas.columns:
        clasificadas['regla'] = clasificadas['metodo']
    if 'evidencia' not in clasificadas.columns:
        clasificadas['evidencia'] = ''

    cf1, cf2 = st.columns(2)
    with cf1:
        filtro = st.text_input('Buscar cuenta (nombre o código)', key='exp_buscar')
    with cf2:
        origenes = ['Todos'] + sorted(o for o in clasificadas['origen'].dropna().unique() if o)
        sel_origen = st.selectbox('Origen', origenes, key='exp_origen')

    v = clasificadas
    if filtro:
        f = filtro.lower()
        v = v[
            v['nombre_original'].astype(str).str.lower().str.contains(f, na=False) |
            v['codigo_clasificado'].astype(str).str.lower().str.contains(f, na=False)
        ]
    if sel_origen != 'Todos':
        v = v[v['origen'] == sel_origen]
    v = v.sort_values(
        ['codigo_clasificado', 'monto'],
        key=lambda x: x.abs() if x.dtype.kind == 'f' else x,
        ascending=[True, False],
    )

    st.caption(f"`{archivo_nombre}` · {len(v)} cuenta(s) · filtro origen = {sel_origen}")

    for idx, row in v.iterrows():
        with st.container(border=True):
            cc1, cc2, cc3, cc4, cc5 = st.columns([1.2, 2.5, 1, 1, 1.5])
            with cc1:
                st.markdown(f"`{row['codigo_clasificado']}`")
            with cc2:
                st.markdown(f"**{_nombre_mostrar(row)}**")
            with cc3:
                st.markdown(_badge_origen(row.get('origen', '')), unsafe_allow_html=True)
            with cc4:
                st.markdown(f"**{_fmt_confianza(row.get('confianza'))}**")
            with cc5:
                st.markdown(f"`{row.get('regla', '')}`")
            if st.button('🔍 Ver detalle', key=f"det_exp_{idx}", use_container_width=True):
                st.session_state['detalle_explicabilidad_idx'] = idx
                st.rerun()

    det_idx = st.session_state.get('detalle_explicabilidad_idx')
    if det_idx is not None and det_idx in v.index:
        st.divider()
        _mostrar_detalle_cuenta(v.loc[det_idx], catalogo, hp=hp, close_key='detalle_explicabilidad_idx')


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR DE CLASIFICACIÓN HÍBRIDA
# ─────────────────────────────────────────────────────────────────────────────

class MotorHibridoLocal:
    UMBRAL_CODIGO = 0.85
    NOMBRES_AMBIGUOS = {'arriendos', 'arriendo', 'intereses', 'interes', 'honorarios', 'comisiones', 'servicios'}
    UMBRAL_DICCIONARIO_EXACTO = 0.98
    UMBRAL_DICCIONARIO_FUZZY = 0.85
    UMBRAL_REGLA = 0.80

    def __init__(self, diccionario: list[dict]):
        self.clasificador_codigo = ClasificadorCodigo()
        self.reglas_especiales = ProcesadorReglasEspeciales()
        self.dic_exacto = {normalizar_nombre(d['cuenta_original']): d for d in diccionario}
        self.dic_lista = list(self.dic_exacto.keys())

    def clasificar(self, cuenta: CuentaRaw, giro_empresa: str | None = None) -> dict:
        nombre_norm = normalizar_nombre(cuenta.nombre)

        if (cuenta.origen_columna != OrigenColumna.DESCONOCIDO and nombre_norm in self.NOMBRES_AMBIGUOS):
            col = cuenta.origen_columna
            es_ing = es_ingreso_col(col)
            es_gas = es_gasto_col(col)
            MAPA_AMBIGUO = {
                'arriendos': ('ER.01', 'ER.04'), 'arriendo':  ('ER.01', 'ER.04'),
                'intereses': ('ER.12', 'ER.09'), 'interes':   ('ER.12', 'ER.09'),
                'honorarios':('ER.01', 'ER.04'), 'honorario': ('ER.01', 'ER.04'),
                'comisiones':('ER.01', 'ER.05'), 'servicios': ('ER.01', 'ER.04'),
            }
            if nombre_norm in MAPA_AMBIGUO:
                cod_ing, cod_gas = MAPA_AMBIGUO[nombre_norm]
                if es_ing:
                    return {'codigo_estandar': cod_ing, 'metodo': 'columna_ambiguo', 'confianza': 0.88, 'requiere_revision': False}
                if es_gas:
                    return {'codigo_estandar': cod_gas, 'metodo': 'columna_ambiguo', 'confianza': 0.88, 'requiere_revision': False}

        r_codigo = self.clasificador_codigo.clasificar(cuenta.codigo)
        if r_codigo and r_codigo.confianza >= self.UMBRAL_CODIGO:
            resultado = {'codigo_estandar': r_codigo.codigo_estandar, 'metodo': 'codigo', 'confianza': r_codigo.confianza}
        else:
            if nombre_norm in self.dic_exacto:
                d = self.dic_exacto[nombre_norm]
                resultado = {'codigo_estandar': d['codigo_estandar'], 'metodo': 'diccionario_exacto', 'confianza': self.UMBRAL_DICCIONARIO_EXACTO}
            else:
                match = process.extractOne(nombre_norm, self.dic_lista, scorer=fuzz.token_sort_ratio)
                if match and match[1] >= 90:
                    d = self.dic_exacto[match[0]]
                    resultado = {'codigo_estandar': d['codigo_estandar'], 'metodo': 'diccionario_fuzzy', 'confianza': round(0.80 + (match[1] - 90) * 0.01, 3)}
                else:
                    mejor = None
                    for patron, cod, conf in REGLAS_COMPILADAS:
                        if patron.search(nombre_norm):
                            if mejor is None or conf > mejor[1]:
                                mejor = (cod, conf)
                    if mejor:
                        resultado = {'codigo_estandar': mejor[0], 'metodo': 'regla_regex', 'confianza': mejor[1]}
                    else:
                        resultado = {'codigo_estandar': None, 'metodo': 'sin_clasificar', 'confianza': 0.0}

        codigo_actual = resultado.get('codigo_estandar')
        origen = cuenta.origen_columna
        if origen != OrigenColumna.DESCONOCIDO and codigo_actual:
            codigo_corregido = self._corregir_por_columna(nombre_norm, codigo_actual, origen, cuenta.monto)
            if codigo_corregido and codigo_corregido != codigo_actual:
                resultado['codigo_estandar'] = codigo_corregido
                resultado['metodo'] += '+columna'
                resultado['confianza'] = min(resultado['confianza'] + 0.05, 0.99)

        codigo_pre = resultado['codigo_estandar'] or 'AC.08'
        ajuste = self.reglas_especiales.aplicar(
            cuenta.nombre, codigo_pre, cuenta.monto, giro_empresa,
            origen_columna=cuenta.origen_columna,
        )
        if ajuste.aplica:
            resultado['codigo_estandar'] = ajuste.codigo_final
            resultado['metodo'] += f'+regla_especial({ajuste.flag})'
            resultado['nota_regla_especial'] = ajuste.nota

        resultado['requiere_revision'] = (
            resultado['confianza'] < UMBRAL_REVISION
            or (ajuste.aplica and ajuste.requiere_revision)
        )
        return resultado

    def _corregir_por_columna(self, nombre_norm, codigo_actual, origen, monto):
        from parser_universal import OrigenColumna as OC
        es_ingreso = es_ingreso_col(origen)
        es_gasto   = es_gasto_col(origen)

        AMBIGUOS = [
            ('arriendo', 'ER.01', 'ER.04'), ('interes', 'ER.12', 'ER.09'),
            ('comision', 'ER.01', 'ER.05'), ('servicio', 'ER.01', 'ER.04'),
            ('honorario', 'ER.01', 'ER.04'), ('diferencia de cambio', 'ER.15', 'ER.15'),
            ('correccion monetaria', 'ER.14', 'ER.14'), ('otras ganancias', 'ER.13', 'ER.13'),
            ('reajuste', 'ER.14', 'ER.14'),
        ]

        if (monto is not None and monto < 0 and origen == OC.ACTIVO and codigo_actual in ('AC.01',)
                and any(k in nombre_norm for k in ('banco','cta cte','cuenta corriente'))):
            return 'PC.02'

        for keyword, cod_ing, cod_gas in AMBIGUOS:
            if keyword in nombre_norm:
                if es_ingreso and codigo_actual not in (cod_ing, cod_gas): return cod_ing
                if es_gasto and codigo_actual not in (cod_ing, cod_gas): return cod_gas

        if origen in (OC.ACTIVO, OC.PASIVO) and codigo_actual and codigo_actual.startswith('ER'):
            return None

        return None


# ─────────────────────────────────────────────────────────────────────────────
# INTERFAZ DE USUARIO PRINCIPAL (MAIN)
# ─────────────────────────────────────────────────────────────────────────────

def _contenido_para_extraer(archivo) -> bytes:
    content = archivo.getvalue()
    if Path(archivo.name).suffix.lower() == ".pdf":
        pages = st.session_state.setdefault("document_pages", {}).get(archivo.name)
        if pages is not None:
            return select_pdf(content, pages)
    return content


def _confirmar_alcance_documentos(archivos) -> bool:
    if len({a.name for a in archivos}) != len(archivos):
        st.error("Hay archivos con el mismo nombre. Renómbrelos para mantener separadas sus páginas y correcciones.")
        return False
    signature = tuple((a.name, hashlib.sha256(a.getvalue()).hexdigest()) for a in archivos)
    _sincronizar_contextos_documentos(archivos)
    _asegurar_metadata_general_vigente(archivos)
    if (st.session_state.get("document_scope_confirmed") == signature
            and not st.session_state.get("document_scope_editing", False)
            and not st.session_state.get(
                "document_scope_reconfirmation_required", False,
            )):
        return True
    st.subheader("Seleccione las páginas que se analizarán")
    st.info(
        "Revise el documento completo en el visor inferior. Si contiene el mismo balance "
        "en varios formatos, elija sólo uno. En informes auditados seleccione las páginas "
        "del estado y sus continuaciones, sin volver a incluir sus anexos o duplicados."
    )
    if st.session_state.get("document_scope_editing"):
        st.warning("Cambiar las páginas vuelve a procesar ese documento y reemplaza sus correcciones en esta sesión. Los documentos sin cambios conservan sus resultados.")
    elif st.session_state.get("document_scope_reconfirmation_required"):
        st.warning(
            "Cambió el contenido o alcance de un documento. Confirme las páginas "
            "para continuar; los documentos sin cambios conservarán sus resultados."
        )
    preview_name = st.selectbox("Documento a visualizar", [a.name for a in archivos])
    selections = {}
    errors = []
    with st.form("document_scope"):
        for archivo in archivos:
            if Path(archivo.name).suffix.lower() != ".pdf":
                continue
            try:
                contenido_archivo = archivo.getvalue()
                count = page_count(contenido_archivo)
            except Exception:
                errors.append(f"No se pudo abrir {archivo.name} como PDF.")
                continue
            st.write(f"{archivo.name}: {count} páginas")
            key = hashlib.sha256(archivo.name.encode() + archivo.getvalue()).hexdigest()[:16]
            saved_pages = st.session_state.get("document_pages", {}).get(archivo.name, [])
            saved_subset = bool(saved_pages) and saved_pages != list(range(1, count + 1))
            mode = st.radio("Páginas a analizar", ["Todas", "Sólo las seleccionadas"],
                            index=1 if saved_subset else 0,
                            key=f"scope_mode_{key}", horizontal=True)
            text = st.text_input("Páginas o rangos", placeholder="1, 3-5",
                                 value=", ".join(map(str, saved_pages)) if saved_subset else "",
                                 key=f"scope_pages_{key}")
            sugerencias_periodo = sugerir_periodos_balance(contenido_archivo)
            eleccion_periodo = ""
            if sugerencias_periodo:
                opciones_periodo = [
                    "Elegir páginas manualmente",
                    *[
                        f"{sugerencia['periodo']} (págs. "
                        + ", ".join(map(str, sugerencia['paginas'])) + ")"
                        for sugerencia in sugerencias_periodo
                    ],
                ]
                eleccion_periodo = st.selectbox(
                    "Período detectado",
                    opciones_periodo,
                    help=(
                        "Sugerencia basada en encabezados nativos. No se "
                        "aplica hasta confirmar el formulario."
                    ),
                    key=f"scope_period_{key}",
                )
            try:
                if eleccion_periodo and eleccion_periodo != opciones_periodo[0]:
                    indice_periodo = opciones_periodo.index(eleccion_periodo) - 1
                    selections[archivo.name] = list(
                        sugerencias_periodo[indice_periodo]['paginas']
                    )
                else:
                    selections[archivo.name] = list(range(1, count + 1)) if mode == "Todas" else parse_pages(text, count)
            except ValueError as exc:
                errors.append(f"{archivo.name}: {exc}")
        submitted = st.form_submit_button("Confirmar páginas y continuar")
    if submitted:
        if errors:
            for error in errors:
                st.error(error)
        else:
            previous = st.session_state.get("document_scope_confirmed")
            previous_pages = st.session_state.get("document_pages", {})
            hubo_cambio = False
            documentos_cambiados = _documentos_con_alcance_modificado(
                signature, previous, previous_pages, selections,
            )
            for name in documentos_cambiados:
                _invalidar_estado_documento(
                    name, invalidar_metadata_documental=True,
                )
                st.session_state.setdefault("document_closing_years", {}).pop(name, None)
                hubo_cambio = True
            nombres_actuales = {name for name, _digest in signature}
            confirmaciones = st.session_state.setdefault("document_closing_years", {})
            for name in list(confirmaciones):
                if name not in nombres_actuales:
                    _invalidar_estado_documento(
                        name, invalidar_metadata_documental=True,
                    )
                    confirmaciones.pop(name, None)
                    hubo_cambio = True
            if hubo_cambio:
                st.session_state.document_year_editing = False
            st.session_state.document_pages = selections
            st.session_state.document_scope_confirmed = signature
            st.session_state.document_scope_reconfirmation_required = False
            st.session_state.document_contexts = {
                archivo.name: _contexto_confirmacion_anio(archivo)
                for archivo in archivos
            }
            _asegurar_metadata_general_vigente(archivos)
            st.session_state.document_scope_editing = False
            # Retorna en esta misma ejecución: el formulario ya fue emitido y
            # sus widgets conservan el estado necesario si el usuario vuelve a
            # editar el alcance. Un rerun inmediato retiraba esos widgets y
            # podía perder la selección de páginas antes de la siguiente vista.
            return True
    st.divider()
    _visor_documento(next(a for a in archivos if a.name == preview_name),
                     altura="58vh", mostrar_titulo=True)
    return False


def main():
    actor_local = None
    if local_access_enabled():
        actor_local = render_local_access_gate()
        if actor_local is None:
            return
        st.session_state["local_access_actor"] = actor_local
    if _modo_piloto_activo():
        temporales_piloto = configure_pilot_tempdir()
        if not temporales_piloto.ready:
            st.error(
                "El piloto no puede iniciar porque el directorio temporal "
                "controlado no está disponible o no cumple los controles "
                "requeridos. Contacte al custodio de datos."
            )
            return
    st.title("📊 Homologación de Balances Tributarios Chilenos")
    st.caption(
        "Carga uno o más balances (PDF o Excel) → clasificación híbrida automática "
        "(código → diccionario → reglas) → cola de revisión → balance normalizado."
    )
    if _modo_piloto_activo():
        st.info(
            "Piloto no mutativo: se usa el catálogo y diccionario operativo "
            "en modo lectura. Las decisiones del balance no se guardarán en "
            "Neon, JSON, Gold Standard ni runtime. Las propuestas explícitas "
            "del diccionario de equipo quedan sólo en el control local y no "
            "modifican el diccionario original."
        )

    catalogo = cargar_catalogo()
    dic_base = cargar_diccionario_base()

    try:
        diccionario_efectivo, contexto_diccionario = (
            _diccionario_efectivo_para_actor_local(dic_base, actor_local)
            if actor_local is not None else (list(dic_base), "base")
        )
    except TeamDictionaryError as exc:
        st.error(
            "No se pudo cargar el diccionario privado del equipo. "
            f"El procesamiento se detuvo para no ignorar sus asignaciones: {exc}"
        )
        return
    if (
        'diccionario' not in st.session_state
        or st.session_state.get("team_dictionary_context") != contexto_diccionario
    ):
        st.session_state.diccionario = diccionario_efectivo
        st.session_state["team_dictionary_context"] = contexto_diccionario
    if 'resultados' not in st.session_state or not isinstance(st.session_state.resultados, dict):
        st.session_state.resultados = {}
    if 'metadata_files' not in st.session_state:
        st.session_state.metadata_files = {}
    if 'document_closing_years' not in st.session_state:
        st.session_state.document_closing_years = {}
    if 'document_metadata_confirmations' not in st.session_state:
        st.session_state.document_metadata_confirmations = {}
    if 'document_metadata_editing' not in st.session_state:
        st.session_state.document_metadata_editing = False
    if 'pilot_manifest_authorizations' not in st.session_state:
        st.session_state.pilot_manifest_authorizations = {}
    if 'document_contexts' not in st.session_state:
        st.session_state.document_contexts = {}
    if 'document_scope_reconfirmation_required' not in st.session_state:
        st.session_state.document_scope_reconfirmation_required = False
    if 'document_intel' not in st.session_state:
        st.session_state.document_intel = {}
    if 'extraction_pending' not in st.session_state:
        st.session_state.extraction_pending = {}
    if 'extraction_resolved' not in st.session_state:
        st.session_state.extraction_resolved = {}
    if 'extraction_certifications' not in st.session_state:
        st.session_state.extraction_certifications = {}
    if 'delivery_readiness' not in st.session_state:
        st.session_state.delivery_readiness = {}
    if 'correcciones' not in st.session_state:
        st.session_state.correcciones = []

    manifiesto_piloto = None
    with st.sidebar:
        st.header("⚙️ Configuración")
        if actor_local is not None:
            render_local_access_sidebar(actor_local)
        release_branch, commit = _trazabilidad_release_local()
        build_date = _build_date()
        persistence_label = "Neon conectado" if _neon_disponible() else "JSON local"
        if _modo_piloto_activo() and _neon_disponible():
            persistence_label = "Neon, solo lectura"
        st.caption(
            f"Rama `{release_branch}` · Commit `{commit}` · Build `{build_date}` · "
            f"Persistencia: **{persistence_label}**"
        )
        if _tiene_permiso_cuenta_local(Permission.ENTRY_UPLOAD):
            archivos = st.file_uploader(
                "Balances tributarios", type=['pdf', 'xlsx', 'xls'],
                accept_multiple_files=True, key="balance_uploads",
            )
            if _modo_piloto_activo():
                st.caption(
                    "Antes de procesar, cargue el manifiesto JSON que autoriza "
                    "este lote por contenido."
                )
                manifiesto_piloto = st.file_uploader(
                    "Manifiesto de autorización del piloto (JSON)",
                    type=["json"], key="pilot_manifest_file",
                )
        else:
            archivos = []
            st.info(
                "Este rol no carga balances. En el piloto actual las cargas "
                "aún no se comparten entre sesiones."
            )
        if archivos and st.session_state.get("document_scope_confirmed"):
            if st.button("Cambiar páginas a analizar"):
                st.session_state.document_scope_editing = True
                st.rerun()

        st.divider()
        st.metric("Cuentas en diccionario", len(st.session_state.diccionario))
        st.metric("Códigos en catálogo", len(catalogo))

        if st.session_state.correcciones:
            st.divider()
            st.success(f"{len(st.session_state.correcciones)} correcciones pendientes")
            buf = json.dumps(st.session_state.diccionario, ensure_ascii=False, indent=2)
            st.download_button(
                ("⬇️ Descargar diccionario provisional del piloto"
                 if _modo_piloto_activo() else "⬇️ Descargar diccionario actualizado"),
                data=buf,
                file_name=(
                    "PILOTO-diccionario_provisional.json"
                    if _modo_piloto_activo() else "diccionario_actualizado.json"
                ),
                mime="application/json"
            )

    if not archivos:
        st.info("⬆️ Carga uno o más archivos en la barra lateral para comenzar.")
        st.session_state.resultados = {}
        st.session_state.metadata_files = {}
        st.session_state.extraction_pending = {}
        st.session_state.extraction_resolved = {}
        st.session_state.extraction_certifications = {}
        st.session_state.delivery_readiness = {}
        _invalidar_metadata_general()
        st.session_state.document_scope_confirmed = None
        st.session_state.document_scope_editing = False
        st.session_state.document_scope_reconfirmation_required = False
        st.session_state.document_closing_years = {}
        st.session_state.document_metadata_confirmations = {}
        st.session_state.document_contexts = {}
        st.session_state.document_year_editing = False
        st.session_state.document_metadata_editing = False
        st.session_state.document_pages = {}
        st.session_state.pilot_manifest_authorizations = {}
        st.session_state.pop("pilot_manifest_context", None)
        st.session_state.pop("pilot_manifest_client_id", None)
        if actor_local is not None and can_view_team_dictionary(actor_local):
            render_team_dictionary_view(actor_local, catalogo)
        _mostrar_resumen_catalogo(catalogo)
        return

    if (_modo_piloto_activo()
            and not _autorizar_lote_piloto(archivos, manifiesto_piloto)):
        return

    if not _confirmar_alcance_documentos(archivos):
        return

    if (not _modo_piloto_activo()
            and not st.session_state.get("document_year_editing", False)
            and all(_confirmacion_anio_vigente(archivo) for archivo in archivos)):
        if st.button("Cambiar años de cierre por documento"):
            st.session_state.document_year_editing = True
            st.rerun()
    if not _confirmar_anios_cierre_documentos(archivos):
        return
    if not _confirmar_metadata_documentos(archivos):
        return

    nombres_subidos = [a.name for a in archivos]
    for k in list(st.session_state.resultados.keys()):
        if k not in nombres_subidos:
            st.session_state.resultados.pop(k, None)
            st.session_state.metadata_files.pop(k, None)
            st.session_state.document_closing_years.pop(k, None)
            st.session_state.document_metadata_confirmations.pop(k, None)
    for k in list(st.session_state.document_metadata_confirmations):
        if k not in nombres_subidos:
            st.session_state.document_metadata_confirmations.pop(k, None)
    for state_key in (
            'extraction_pending', 'extraction_resolved', 'extraction_certifications',
            'delivery_readiness',
    ):
        state = st.session_state.get(state_key, {})
        for k in list(state.keys()):
            if k not in nombres_subidos:
                state.pop(k, None)

    # ── Procesar archivos nuevos ──────────────────────────────────────────────
    if USE_LEGACY_ENGINE:
        # LEGACY PIPELINE (MotorHibridoLocal)
        for archivo in archivos:
            if archivo.name not in st.session_state.resultados:
                with st.spinner(f"Clasificando cuentas de {archivo.name}..."):
                    lineas_encabezado = _extraer_lineas_encabezado(archivo)
                    meta_indiv = _aplicar_metadata_confirmada(
                        extraer_metadata(lineas_encabezado), archivo=archivo,
                    )
                    st.session_state.metadata_files[archivo.name] = meta_indiv
                    anio_cierre_documento = getattr(meta_indiv, 'anio_cierre', None)
                    giro_documento = getattr(meta_indiv, "giro", None) or None

                    if archivo.name in st.session_state.extraction_resolved:
                        cuentas = st.session_state.extraction_resolved.pop(archivo.name)
                        doc_ctx = st.session_state.document_intel.get(archivo.name)
                    else:
                        cuentas, doc_ctx = _extraer_cuentas(archivo)
                    st.session_state.document_intel[archivo.name] = doc_ctx
                    certificacion = st.session_state.get(
                        'extraction_certifications', {},
                    ).get(archivo.name)
                    revision_forzada_extraccion = _requiere_revision_por_extraccion(
                        certificacion,
                    )
                    nota_revision_extraccion = _nota_revision_por_extraccion(
                        certificacion,
                    ) if revision_forzada_extraccion else ''
                    from pipeline.homologation_pipeline import HomologationPipeline
                    motor = MotorHibridoLocal(st.session_state.diccionario)
                    filas = []
                    for c in cuentas:
                        if c.es_total:
                            filas.append(_fila_control_extraccion(c))
                            continue
                        if c.monto is None and not c.codigo:
                            continue
                        if c.monto is not None and float(c.monto) == 0:
                            continue
                        if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()):
                            continue
                        revision_extraccion_cuenta = _requiere_revision_por_extraccion(
                            certificacion, c.linea,
                        )
                        _t0_legacy = time.perf_counter()
                        r = motor.clasificar(c, giro_documento)
                        resultado_anual_explicito = (
                            HomologationPipeline._classification_for_explicit_result_year(
                                c.nombre,
                                c.codigo or '',
                                anio_cierre_documento,
                            )
                        )
                        if resultado_anual_explicito is not None:
                            r = {
                                **r,
                                'codigo_estandar': resultado_anual_explicito.get(
                                    'standard_code',
                                ),
                                'metodo': resultado_anual_explicito.get(
                                    'method', r.get('metodo', ''),
                                ),
                                'confianza': resultado_anual_explicito.get(
                                    'confidence', r.get('confianza', 0.0),
                                ),
                                'requiere_revision': resultado_anual_explicito.get(
                                    'requires_review',
                                    r.get('requiere_revision', False),
                                ),
                                'nota_regla_especial': resultado_anual_explicito.get(
                                    'reason', r.get('nota_regla_especial', ''),
                                ),
                            }
                        _t1_legacy = (time.perf_counter() - _t0_legacy) * 1000
                        seccion_contable = getattr(c, 'seccion_contable', None)
                        origen_efectivo = _origen_efectivo(
                            c.origen_columna, c.monto, c.nombre,
                            seccion_contable,
                            codigo_original=c.codigo,
                            anio_cierre=anio_cierre_documento,
                        )
                        if (r.get('codigo_estandar') and
                                not _codigo_compatible_con_origen(
                                    r['codigo_estandar'], c.origen_columna, c.monto,
                                    c.nombre,
                                    seccion_contable=seccion_contable,
                                    codigo_original=c.codigo,
                                    anio_cierre=anio_cierre_documento)):
                            r = {
                                **r,
                                'codigo_estandar': None,
                                'metodo': 'sin_clasificar+filtro_columna',
                                'confianza': 0.0,
                                'requiere_revision': True,
                            }
                        filas.append({
                            'linea': c.linea,
                            'codigo_original': c.codigo or '',
                            'anio_cierre': anio_cierre_documento,
                            'nombre_original': c.nombre,
                            'nombre_normalizado': normalizar_nombre(c.nombre),
                            'monto': c.monto,
                            'monto_periodo_actual': c.montos_periodos.get('actual'),
                            'monto_periodo_anterior': c.montos_periodos.get('anterior'),
                            'columnas_derivadas': ', '.join(c.columnas_derivadas),
                            'origen_columna': c.origen_columna.value,
                            'seccion_contable': seccion_contable or '',
                            'estado_financiero': getattr(c, 'estado_financiero', None) or '',
                            'origen_columna_efectiva': origen_efectivo,
                            'es_total': c.es_total,
                            'codigo_clasificado': r['codigo_estandar'] or '',
                            'metodo': r['metodo'],
                            'confianza': r['confianza'],
                            'requiere_revision': (
                                r['requiere_revision']
                                or bool(c.columnas_derivadas)
                                or revision_extraccion_cuenta
                            ),
                            'revision_extraccion': revision_extraccion_cuenta,
                            'nota': ' '.join(filter(None, [
                                r.get('nota_regla_especial', ''),
                                (
                                    nota_revision_extraccion
                                    if revision_extraccion_cuenta else ''
                                ),
                            ])),
                            'confianza_extraccion': c.confianza_extraccion,
                            'origen_columna_display': _etiqueta_origen(
                                c.origen_columna, c.monto, c.nombre,
                                seccion_contable,
                                codigo_original=c.codigo,
                                anio_cierre=anio_cierre_documento,
                            ),
                            'nombre_revision_usuario': '',
                            'tipo_revision': '',
                            'origen': _origen_desde_metodo_display(r['metodo']),
                            'regla': r['metodo'],
                            'evidencia': r.get('nota_regla_especial', '') or r['metodo'],
                            'tiempo_clasificacion': round(_t1_legacy, 3),
                        })
                    df_file = pd.DataFrame(filas)
                    st.session_state.resultados[archivo.name] = df_file

                    # SHADOW MODE — homologación comparativa contra motor legacy
                    if _shadow_mode_activo() and Path(archivo.name).suffix.lower() == '.pdf':
                        import tempfile
                        from pipeline.homologation_pipeline import HomologationPipeline
                        from shadow.shadow_logger import ShadowLogger
                        tmp_shadow = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                        try:
                            tmp_shadow.write(archivo.read())
                            tmp_shadow.close()
                            sh_path = Path(tmp_shadow.name)
                            hp_shadow = HomologationPipeline(
                                dictionary_entries=st.session_state.diccionario,
                            )
                            sh_summary = hp_shadow.process(sh_path)
                            logger_sh = ShadowLogger()
                            comparisons = []
                            matches = 0
                            for sh_entry in sh_summary.get("classified", []):
                                aname = sh_entry["account_name"]
                                amatch = df_file[df_file["nombre_original"] == aname]
                                if amatch.empty:
                                    continue
                                comparisons.append(logger_sh.build_comparison(
                                    account_name=aname,
                                    account_code=sh_entry.get("account_code", ""),
                                    legacy_code=amatch.iloc[0]["codigo_clasificado"] or None,
                                    legacy_confidence=amatch.iloc[0]["confianza"],
                                    new_code=sh_entry.get("final_code") or sh_entry.get("standard_code"),
                                    new_confidence=sh_entry.get("confidence", 0.0),
                                    new_method=sh_entry.get("method", ""),
                                    learning_hit="learning" in sh_entry.get("method", ""),
                                ))
                                if comparisons[-1]["match"]:
                                    matches += 1
                            total_comp = len(comparisons)
                            match_rate = matches / total_comp if total_comp else 1.0
                            logger_sh.log(archivo.name, comparisons, match_rate)
                        finally:
                            sh_path.unlink(missing_ok=True)
                            archivo.seek(0)
    else:
        # NEW PIPELINE (HomologationPipeline)
        import logging as _logging
        _shadow_logger = _logging.getLogger("homologation_pipeline")
        from pipeline.homologation_pipeline import HomologationPipeline
        from adapters.account_adapter import AccountAdapter
        from interpreters.balance_interpreter import BalanceInterpreter

        archivos_nuevos = [
            archivo for archivo in archivos
            if archivo.name not in st.session_state.resultados
        ]
        hp = (
            HomologationPipeline(
                dictionary_entries=st.session_state.diccionario,
            )
            if archivos_nuevos else None
        )
        for archivo in archivos_nuevos:
            if archivo.name not in st.session_state.resultados:
                with st.spinner(f"Clasificando cuentas de {archivo.name}..."):
                    _t0 = time.perf_counter()
                    lineas_encabezado = _extraer_lineas_encabezado(archivo)
                    meta_indiv = _aplicar_metadata_confirmada(
                        extraer_metadata(lineas_encabezado), archivo=archivo,
                    )
                    st.session_state.metadata_files[archivo.name] = meta_indiv
                    anio_cierre_documento = getattr(meta_indiv, 'anio_cierre', None)
                    giro_documento = getattr(meta_indiv, "giro", None) or None

                    if archivo.name in st.session_state.extraction_resolved:
                        cuentas = st.session_state.extraction_resolved.pop(archivo.name)
                        doc_ctx = st.session_state.document_intel.get(archivo.name)
                    else:
                        cuentas, doc_ctx = _extraer_cuentas(archivo)
                    st.session_state.document_intel[archivo.name] = doc_ctx
                    certificacion = st.session_state.get(
                        'extraction_certifications', {},
                    ).get(archivo.name)
                    revision_forzada_extraccion = _requiere_revision_por_extraccion(
                        certificacion,
                    )
                    nota_revision_extraccion = _nota_revision_por_extraccion(
                        certificacion,
                    ) if revision_forzada_extraccion else ''
                    total_cuentas = len(cuentas)
                    filas = []
                    clasificadas = 0
                    learning_hits = 0
                    fallback_count = 0

                    for c in cuentas:
                        if c.es_total:
                            filas.append(_fila_control_extraccion(c))
                            continue
                        if c.monto is None and not c.codigo:
                            continue
                        if c.monto is not None and float(c.monto) == 0:
                            continue
                        if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()):
                            continue
                        revision_extraccion_cuenta = _requiere_revision_por_extraccion(
                            certificacion, c.linea,
                        )
                        ab = AccountAdapter.from_cuenta_raw(c)
                        interp = BalanceInterpreter(ab)
                        classification_amount = interp.classification_amount
                        seccion_contable = getattr(c, 'seccion_contable', None)
                        origen_efectivo = _origen_efectivo(
                            c.origen_columna, classification_amount, c.nombre,
                            seccion_contable,
                            codigo_original=c.codigo,
                            anio_cierre=anio_cierre_documento,
                        )
                        tipo_seccion = account_type_from_explicit_section(
                            seccion_contable,
                        )
                        account_tipo = (
                            tipo_seccion.value if tipo_seccion is not None
                            else _resolver_tipo_cuenta(origen_efectivo, c.codigo)
                        )
                        if (tipo_seccion is None and origen_efectivo == 'pasivo'
                                and _es_contra_activo(
                                    c.nombre, c.origen_columna,
                                    classification_amount,
                                )):
                            account_tipo = 'ACTIVO'
                        if tipo_seccion is None and _es_partida_patrimonial(
                                c.nombre,
                                codigo_original=c.codigo,
                                anio_cierre=anio_cierre_documento,
                        ):
                            account_tipo = 'PATRIMONIO'
                        contra_activo_depreciacion = (
                            is_credit_balance_depreciation_name(
                                c.nombre, c.origen_columna,
                                classification_amount,
                            )
                        )
                        contra_activo_depreciacion_contextual = (
                            contra_activo_depreciacion
                            and not is_contra_asset_name(c.nombre)
                        )
                        contra_pasivo_deudor = is_debit_balance_financial_liability(
                            c.nombre, c.origen_columna, classification_amount,
                        )
                        if classification_amount is None:
                            codigo_clasificado = ""
                            metodo = "movement_only"
                            confianza = 0.0
                            requiere_revision = True
                            nota = ""
                            clasif_origen = 'Sin clasificar'
                            clasif_evidencia = ''
                            tiempo_clasif_ms = 0.0
                        else:
                            clasificadas += 1
                            _t0_clasif = time.perf_counter()
                            # La evidencia semántica acotada de un resultado
                            # anual 2402- prevalece sobre la sección física:
                            # una cuenta histórica puede aparecer bajo ACTIVO
                            # aunque su naturaleza efectiva sea patrimonio.
                            classification = hp._classification_for_explicit_result_year(
                                ab.account_name,
                                ab.account_code,
                                anio_cierre_documento,
                            ) or (
                                hp._classify_debit_balance_financial_liability(
                                    ab.account_name,
                                )
                                if contra_pasivo_deudor else None
                            ) or hp._classify_account(
                                ab.account_code,
                                ab.account_name,
                                account_tipo=account_tipo,
                            )
                            # Esta inferencia cambia la presentación contable;
                            # aun con una coincidencia ANC previa se muestra
                            # como propuesta que exige confirmación humana.
                            if contra_activo_depreciacion_contextual:
                                special = hp._classify_credit_balance_depreciation(
                                    ab.account_name,
                                    c.origen_columna,
                                    classification_amount,
                                )
                                if special is not None:
                                    classification = special
                            tiempo_clasif_ms = round((time.perf_counter() - _t0_clasif) * 1000, 3)
                            adjustment = hp._rule_processor.aplicar(
                                nombre_cuenta=ab.account_name,
                                codigo_clasificado=classification.get("standard_code") or "",
                                monto=classification_amount,
                                giro_empresa=giro_documento,
                                origen_columna=c.origen_columna,
                            )
                            final_code = (
                                adjustment.codigo_final if adjustment.aplica
                                else classification.get("standard_code")
                            )
                            if (final_code and
                                    not _codigo_compatible_con_origen(
                                        final_code, c.origen_columna,
                                        classification_amount, c.nombre,
                                        seccion_contable=seccion_contable,
                                        codigo_original=c.codigo,
                                        anio_cierre=anio_cierre_documento)):
                                final_code = None
                                classification = {
                                    **classification,
                                    "standard_code": None,
                                    "confidence": 0.0,
                                    "method": "unclassified_type_filter",
                                    "reason": (
                                        "Sugerencia descartada por ser incompatible con "
                                        f"la columna efectiva {account_tipo}"
                                    ),
                                }
                            codigo_clasificado = final_code or ""
                            metodo = classification.get("method", "")
                            confianza = classification.get("confidence", 0.0)
                            requiere_revision = (
                                confianza < UMBRAL_REVISION
                                or (adjustment.aplica and adjustment.requiere_revision)
                                or classification.get('requires_review', False)
                                or bool(c.columnas_derivadas)
                                or revision_extraccion_cuenta
                            )
                            nota = adjustment.nota if adjustment.aplica else ""
                            clasif_evidencia = classification.get("reason", "")
                            clasif_origen = _origen_desde_clasif(classification, ab.account_name, hp)
                            if metodo.startswith("learning_"):
                                learning_hits += 1
                            else:
                                fallback_count += 1

                        if revision_extraccion_cuenta:
                            nota = ' '.join(filter(None, [
                                nota, nota_revision_extraccion,
                            ]))
                            clasif_evidencia = ' '.join(filter(None, [
                                clasif_evidencia, nota_revision_extraccion,
                            ]))

                        filas.append({
                            'linea': c.linea,
                            'codigo_original': c.codigo or '',
                            'anio_cierre': anio_cierre_documento,
                            'nombre_original': c.nombre,
                            'nombre_normalizado': normalizar_nombre(c.nombre),
                            'monto': c.monto,
                            'monto_periodo_actual': c.montos_periodos.get('actual'),
                            'monto_periodo_anterior': c.montos_periodos.get('anterior'),
                            'columnas_derivadas': ', '.join(c.columnas_derivadas),
                            'origen_columna': c.origen_columna.value,
                            'seccion_contable': seccion_contable or '',
                            'estado_financiero': getattr(c, 'estado_financiero', None) or '',
                            'origen_columna_efectiva': origen_efectivo,
                            'es_total': c.es_total,
                            'codigo_clasificado': codigo_clasificado,
                            'metodo': metodo,
                            'confianza': confianza,
                            'requiere_revision': requiere_revision,
                            'revision_extraccion': revision_extraccion_cuenta,
                            'nota': nota,
                            'confianza_extraccion': c.confianza_extraccion,
                            'origen_columna_display': _etiqueta_origen(
                                c.origen_columna, classification_amount, c.nombre,
                                seccion_contable,
                                codigo_original=c.codigo,
                                anio_cierre=anio_cierre_documento,
                            ),
                            'nombre_revision_usuario': '',
                            'tipo_revision': '',
                            'origen': clasif_origen,
                            'regla': metodo,
                            'evidencia': clasif_evidencia,
                            'tiempo_clasificacion': tiempo_clasif_ms,
                        })

                    df_file = pd.DataFrame(filas)
                    st.session_state.resultados[archivo.name] = df_file

                    _t1 = time.perf_counter()
                    _shadow_logger.info(
                        "archivo=%s cuentas=%d clasificadas=%d learning_hits=%d fallback=%d time=%.3fs",
                        archivo.name, total_cuentas, clasificadas,
                        learning_hits, fallback_count, _t1 - _t0,
                    )
        # P5.5 Runtime Observability: persistir métricas de uso para Runtime Analytics.
        try:
            st.session_state["runtime_metrics_last"] = hp._learning_engine.get_metrics()
        except Exception:  # noqa: BLE001 — observabilidad no debe interrumpir el flujo
            pass
    # After processing all uploaded files, propagate classifications across all balances
    if 'propagation_done' not in st.session_state:
        # Define helper to propagate classifications across balances
        def propagar_entre_balances():
            """Propaga códigos clasificados entre balances cargados."""
            # Build mapping from normalized account name to list of (file, index).
            # Keep the ultimate source so a later page/content change can reopen
            # only the decisions that crossed from that document.
            name_map = {}
            for fname, df in st.session_state.resultados.items():
                for idx, row in df.iterrows():
                    nombre = row['nombre_original']
                    if not nombre:
                        continue
                    norm = normalizar_nombre(nombre)
                    name_map.setdefault(norm, []).append((
                        fname, idx, row['codigo_clasificado'],
                        row.get('propagacion_origen_archivo', ''),
                    ))
            # Propagar si existe alguna clasificación
            for norm, entries in name_map.items():
                classified_code = None
                archivo_origen = ''
                for fname, idx, cod, origen_previo in entries:
                    if cod and cod not in ('', '__EXCLUIR__'):
                        classified_code = cod
                        archivo_origen = origen_previo or fname
                        break
                if classified_code:
                    for fname, idx, cod, _origen_previo in entries:
                        row = st.session_state.resultados[fname].loc[idx]
                        if ((not cod or cod == '')
                                and _codigo_compatible_con_origen(
                                    classified_code,
                                    row.get('origen_columna'),
                                    row.get('monto'),
                                    row.get('nombre_original'),
                                    seccion_contable=row.get('seccion_contable'),
                                    codigo_original=row.get('codigo_original'),
                                    anio_cierre=row.get('anio_cierre'),
                                )):
                            st.session_state.resultados[fname].at[idx, 'codigo_clasificado'] = classified_code
                            st.session_state.resultados[fname].at[idx, 'metodo'] = 'propagado_automático'
                            st.session_state.resultados[fname].at[idx, 'confianza'] = 1.0
                            st.session_state.resultados[fname].at[idx, 'requiere_revision'] = False
                            st.session_state.resultados[fname].at[
                                idx, 'propagacion_origen_archivo'
                            ] = archivo_origen
                            if 'origen' in st.session_state.resultados[fname].columns:
                                st.session_state.resultados[fname].at[idx, 'origen'] = 'Código'
                                st.session_state.resultados[fname].at[idx, 'regla'] = 'propagado_automático'
                                st.session_state.resultados[fname].at[idx, 'evidencia'] = 'Propagación automática entre balances'
        propagar_entre_balances()
        st.session_state['propagation_done'] = True

    with st.sidebar:
        st.divider()
        st.subheader("📁 Balances Cargados")
        for name in nombres_subidos:
            df_f = st.session_state.resultados.get(name)
            certificacion_f = st.session_state.get(
                "extraction_certifications", {},
            ).get(name)
            if df_f is not None and not df_f.empty:
                pendientes_f = _pendientes_revision(df_f)
                n_pendientes = len(pendientes_f)
                etiqueta = _etiqueta_estado_archivo_cargado(
                    df_f, certificacion_f,
                )
                if n_pendientes > 0:
                    st.caption(
                        f"`{name}` ({etiqueta}; {n_pendientes} pendientes)",
                    )
                else:
                    st.caption(f"`{name}` ({etiqueta})")
            else:
                etiqueta = _etiqueta_estado_archivo_cargado(
                    df_f, certificacion_f,
                )
                st.caption(f"`{name}` ({etiqueta})")

        st.write("")
        seleccion_previa = st.session_state.get("archivo_activo_select")
        lote_actual = tuple(nombres_subidos)
        archivo_preferido = _seleccion_activa_para_lote(
            nombres_subidos,
            st.session_state.resultados,
            st.session_state.get("archivo_activo_lote"),
            seleccion_previa,
        )
        if archivo_preferido is not None:
            st.session_state["archivo_activo_select"] = archivo_preferido
        st.session_state["archivo_activo_lote"] = lote_actual
        archivo_activo_name = st.selectbox(
            "Ver y validar balance:", options=nombres_subidos,
            key="archivo_activo_select",
        )

    try:
        archivo_activo = next(a for a in archivos if a.name == archivo_activo_name)
        df = st.session_state.resultados[archivo_activo_name]
        meta_activo = st.session_state.metadata_files.get(archivo_activo_name)
    except (NameError, Exception):
        class DummyDF: empty = False
        df = DummyDF()
        archivo_activo_name = ""
        archivo_activo = None
        meta_activo = None

    if df.empty:
        certificacion_extraccion = st.session_state.get(
            "extraction_certifications", {},
        ).get(archivo_activo_name)
        estado_entrega = _evaluar_estado_entrega_documento(
            pd.DataFrame(),
            certificacion_extraccion,
            catalogo,
            contexto_documental=st.session_state.get(
                "document_intel", {},
            ).get(archivo_activo_name),
        )
        st.session_state.setdefault("delivery_readiness", {})[
            archivo_activo_name
        ] = estado_entrega
        _mostrar_estado_entrega(estado_entrega)
        emision_diagnostico = {
            "definitivo": False,
            "motivos": list(estado_entrega["razones"]),
        }
        payload_diagnostico = _payload_entrega_json(
            archivo_nombre=archivo_activo_name,
            meta=meta_activo,
            estado_entrega=estado_entrega,
            emision=emision_diagnostico,
            presentacion=pd.DataFrame(),
            detalle=pd.DataFrame(),
            identificacion_caso=_identificacion_caso_exportacion(
                archivo_activo_name, meta_activo,
            ),
        )
        st.download_button(
            ("Descargar diagnóstico piloto provisional (JSON)"
             if _modo_piloto_activo() else "Descargar diagnóstico (JSON)"),
            data=json.dumps(
                payload_diagnostico, ensure_ascii=False, indent=2, default=str,
            ).encode("utf-8"),
            file_name=(
                f"{_nombre_descarga_piloto(archivo_activo_name, 'DIAGNOSTICO')}.json"
                if _modo_piloto_activo()
                else f"DIAGNOSTICO-{Path(archivo_activo_name).stem}.json"
            ),
            mime="application/json",
        )
        if archivo_activo_name in st.session_state.extraction_pending:
            _mostrar_etapa_correccion_extraccion(archivo_activo, archivo_activo_name)
        else:
            st.warning(f"No se extrajeron cuentas del archivo {archivo_activo_name}.")
        st.stop()

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        razon_social = getattr(meta_activo, "razon_social", "—")
        rut_empresa = getattr(meta_activo, "rut", "—")
        c1.markdown(f"**{razon_social or '—'}** \n`{rut_empresa or '—'}`")
        periodo_str = "—"
        if meta_activo:
            periodo_str = (
                f"{meta_activo.periodo_desde or '—'} → "
                f"{meta_activo.periodo_hasta or '—'} · "
                f"{meta_activo.numero_meses or '—'} meses · "
                f"{meta_activo.moneda or '—'}"
            )
        c2.markdown(f"**Período y moneda** \n{periodo_str}")
        giro_empresa = getattr(meta_activo, "giro", "—")
        c3.markdown(f"**Giro** \n{giro_empresa or '—'}")
        c4.markdown(f"**Archivo Activo** \n`{archivo_activo_name}`")

    _mostrar_advertencias_auxiliares(
        st.session_state.extraction_certifications.get(archivo_activo_name)
    )
    _doc_ctx = st.session_state.document_intel.get(archivo_activo_name)
    estado_entrega = _evaluar_estado_entrega_documento(
        df,
        st.session_state.extraction_certifications.get(archivo_activo_name),
        catalogo,
        contexto_documental=_doc_ctx,
    )
    st.session_state.setdefault("delivery_readiness", {})[archivo_activo_name] = estado_entrega
    _mostrar_estado_entrega(estado_entrega)

    # El contexto previo y la estructura observada son evidencias distintas.
    _mostrar_informacion_documento(
        _doc_ctx, estado_entrega.get("formato"),
    )

    col_visor, col_trabajo = st.columns([1, 1], gap="medium")

    with col_visor:
        try:
            _visor_documento(archivo_activo)
        except (NameError, Exception):
            pass

    with col_trabajo:
        tab_km = "🧠 Knowledge Manager"
        vistas = ["📈 Resumen"]
        if _tiene_permiso_cuenta_local(Permission.ACCOUNT_REVIEW):
            vistas.append("🔍 Cola de Revisión")
        if _tiene_permiso_cuenta_local(Permission.EXPORT_REVIEW_PACKAGE):
            vistas.append("📋 Balance Normalizado")
        if (
            _tiene_permiso_cuenta_local(Permission.ENTRY_VIEW_OWN)
            or _tiene_permiso_cuenta_local(Permission.ENTRY_VIEW_TEAM)
        ):
            vistas.append("📖 Conocimiento Documental")
        if actor_local is not None and can_view_team_dictionary(actor_local):
            vistas.append("🗂️ Diccionario del equipo")
        if _tiene_permiso_cuenta_local(Permission.GLOBAL_DICTIONARY_EDIT):
            vistas.extend([
                "📚 Diccionario", "🧠 Aprendizaje", "📊 Analytics",
                "📈 Inteligencia del Dataset", tab_km,
            ])
        vista_solicitada = st.session_state.pop("vista_trabajo_solicitada", None)
        if vista_solicitada in vistas:
            st.session_state["vista_trabajo"] = vista_solicitada
        vista = st.selectbox(
            "Vista de trabajo", vistas, key="vista_trabajo",
            help="Solo se ejecuta la vista seleccionada para evitar recargas innecesarias.",
        )

        if vista == "📈 Resumen":
            _tab_resumen(df)
        elif vista == "🔍 Cola de Revisión":
            _tab_revision(
                df, catalogo,
                motor=MotorHibridoLocal(st.session_state.diccionario),
                archivo_nombre=archivo_activo_name,
            )
        elif vista == "📋 Balance Normalizado":
            _tab_balance(df, catalogo, archivo_activo_name)
        elif vista == "📚 Diccionario":
            _tab_diccionario()
        elif vista == "🧠 Aprendizaje":
            _tab_aprendizaje()
        elif vista == "📊 Analytics":
            st.markdown("Analytics Dashboard (Work in Progress)")
        elif vista == "📖 Conocimiento Documental":
            _tab_conocimiento(archivo_activo, _doc_ctx, meta_activo)
        elif vista == "🗂️ Diccionario del equipo":
            render_team_dictionary_view(actor_local, catalogo)
        elif vista == "📈 Inteligencia del Dataset":
            _tab_inteligencia()
        elif vista == tab_km:
            _tab_knowledge_manager()


@st.cache_data(max_entries=12, show_spinner=False)
def _render_pdf_cached(content: bytes, page: int) -> bytes:
    return render_page(content, page)


@st.fragment
def _visor_documento(
    archivo, *, altura: str = "72vh", mostrar_titulo: bool = True,
):
    import tempfile, base64, io, platform, shutil, subprocess, glob
    from PIL import Image
    from pathlib import Path

    suffix = Path(archivo.name).suffix.lower()
    archivo.seek(0)
    if mostrar_titulo:
        st.markdown("#### 📄 Documento original")

    if suffix == '.pdf':
        content = archivo.getvalue()
        contenido_id = hashlib.sha256(content).hexdigest()[:16]
        try:
            n_paginas = page_count(content)
        except Exception:
            st.error("No se pudo abrir el PDF para visualizarlo.")
            return
        ctrl1, ctrl2, ctrl3 = st.columns(3)
        with ctrl1:
            pagina = st.number_input(f"Página (1-{n_paginas})", min_value=1,
                                     max_value=n_paginas, value=1, step=1,
                                     key=f"visor_pagina_{contenido_id}")
        with ctrl2:
            zoom = st.slider("Zoom", 50, 200, 100, 10, format="%d%%",
                             key=f"visor_zoom_{contenido_id}")
        with ctrl3:
            rotacion = st.select_slider("Rotación", options=[0, 90, 180, 270],
                                        key=f"visor_rot_{contenido_id}")
        try:
            img = Image.open(BytesIO(_render_pdf_cached(content, int(pagina))))
            if rotacion:
                img = img.rotate(-rotacion, expand=True)
            if zoom != 100:
                img = img.resize((int(img.width * zoom / 100), int(img.height * zoom / 100)))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception:
            st.error("No se pudo mostrar esta página. El documento original no se modificó.")
            return
        st.html(f"""
        <div style="height:{altura};min-height:50vh;overflow:auto;border:1px solid #d0d0d0;background:#f5f5f5;text-align:center">
          <img src="data:image/png;base64,{b64}" style="max-width:none" />
        </div>
        <p>Página {pagina} de {n_paginas} · {escape(archivo.name)}</p>
        """)

    elif suffix in ('.xlsx', '.xls'):
        archivo.seek(0)
        try:
            df_raw = pd.read_excel(archivo, header=None, dtype=str).fillna('')
            html_tabla = df_raw.to_html(index=False, header=False, border=0, classes='excel-visor')
            html_visor = f"""
            <style>
                .excel-visor td {{ padding: 3px 8px; border-bottom: 1px solid #eee; font-size: 12px; white-space: nowrap; font-family: monospace; }}
                .excel-visor tr:nth-child(even) {{ background: #f9f9f9; }}
            </style>
            <div style="height: {altura}; min-height: 50vh; overflow-y: auto; overflow-x: auto; border: 1px solid #d0d0d0; border-radius: 8px; background: white; padding: 8px;">{html_tabla}</div>
            <div style="font-size:12px; color:#888; text-align:center; margin-top:4px;">{archivo.name}</div>
            """
            st.html(html_visor)
        except Exception as e:
            st.error(f"No se pudo mostrar el Excel: {e}")
        finally:
            archivo.seek(0)


def _extraer_lineas_encabezado(archivo) -> list[str]:
    import tempfile
    suffix = Path(archivo.name).suffix.lower()
    archivo.seek(0)
    if suffix == '.pdf':
        try:
            import pdfplumber
            with pdfplumber.open(BytesIO(_contenido_para_extraer(archivo))) as pdf:
                texto = pdf.pages[0].extract_text() or ""
                return texto.split('\n')[:40]
        except Exception:
            return []
        finally:
            archivo.seek(0)
    else:
        archivo.seek(0)
        df = pd.read_excel(archivo, header=None, nrows=15).fillna('')
        archivo.seek(0)
        lineas = []
        for _, row in df.iterrows():
            vals = [str(v) for v in row if str(v) not in ('nan', 'None', '')]
            if vals: lineas.append(' '.join(vals))
        return lineas


def _documento_no_es_balance(signature) -> bool:
    """Gate conservador para anexos/otros con señal documental suficiente."""
    document_type = getattr(getattr(signature, 'document_type', None), 'value', '')
    return bool(
        document_type == 'OTRO'
        and not bool(getattr(signature, 'has_headers', False))
        and float(getattr(signature, 'confidence', 0.0) or 0.0) >= 0.30
    )


def _aplicar_correcciones_extraccion(
    cuentas: list[CuentaRaw], edited: pd.DataFrame,
) -> tuple[list[CuentaRaw], object]:
    """Aplica importes editados y vuelve a certificar las ocho columnas."""
    rows = {int(row["linea"]): row for _, row in edited.iterrows()}
    corrected: list[CuentaRaw] = []
    origin_by_column = {
        "activo": OrigenColumna.ACTIVO,
        "pasivo": OrigenColumna.PASIVO,
        "perdida": OrigenColumna.PERDIDA,
        "ganancia": OrigenColumna.GANANCIA,
    }

    def numeric(value) -> float:
        parsed = pd.to_numeric(value, errors="coerce")
        return 0.0 if pd.isna(parsed) else float(parsed)

    for cuenta in cuentas:
        row = rows.get(int(cuenta.linea))
        if row is None or not cuenta.montos_columnas:
            corrected.append(cuenta)
            continue
        if bool(row.get("excluir", False)) and not bool(row.get("total", cuenta.es_total)):
            continue
        amounts = {
            column: numeric(row.get(column, cuenta.montos_columnas.get(column, 0)))
            for column in RAW_MONETARY_COLUMNS
        }
        amount = None
        origin = OrigenColumna.DESCONOCIDO
        for column in ("activo", "pasivo", "perdida", "ganancia"):
            if amounts[column] != 0:
                amount = amounts[column]
                origin = origin_by_column[column]
                break
        derived = list(cuenta.columnas_derivadas)
        if amounts != cuenta.montos_columnas and "correccion_humana" not in derived:
            derived.append("correccion_humana")
        corrected.append(replace(
            cuenta,
            montos_columnas=amounts,
            monto=amount,
            origen_columna=origin,
            es_total=bool(row.get("total", cuenta.es_total)),
            columnas_derivadas=derived,
        ))
    certification = certificar_extraccion_columnas(
        corrected, metodo="revision_humana_8_columnas",
    )
    return corrected, certification


def _crear_cuenta_manual_extraccion(
    cuentas: list[CuentaRaw], *, codigo: str, nombre: str,
    montos: dict[str, float], es_total: bool = False,
) -> CuentaRaw:
    """Construye una fila auditable ingresada por el analista."""
    if not str(nombre or '').strip():
        raise ValueError("El nombre de la cuenta es obligatorio")
    amounts = {
        column: float(montos.get(column, 0.0) or 0.0)
        for column in RAW_MONETARY_COLUMNS
    }
    origin_by_column = {
        "activo": OrigenColumna.ACTIVO,
        "pasivo": OrigenColumna.PASIVO,
        "perdida": OrigenColumna.PERDIDA,
        "ganancia": OrigenColumna.GANANCIA,
    }
    amount = None
    origin = OrigenColumna.DESCONOCIDO
    for column in ("activo", "pasivo", "perdida", "ganancia"):
        if amounts[column] != 0:
            amount = amounts[column]
            origin = origin_by_column[column]
            break
    return CuentaRaw(
        linea=max((int(c.linea) for c in cuentas), default=-1) + 1,
        codigo=str(codigo or '').strip() or None,
        nombre=str(nombre).strip(),
        monto=amount,
        origen_columna=origin,
        es_total=bool(es_total),
        confianza_extraccion=1.0,
        montos_columnas=amounts,
        columnas_derivadas=["ingreso_manual_analista"],
    )


def _diagnosticar_filas_extraccion(
        cuentas: list[CuentaRaw], certification=None,
        tolerancia: float = 10.0) -> dict[int, dict]:
    """Explica por fila por qué falló la certificación y qué revisar.

    La función es deliberadamente informativa: no modifica importes, no excluye
    filas y no marca subtotales automáticamente. La decisión permanece en manos
    del analista.
    """
    inconsistent = set(
        getattr(certification, "filas_inconsistentes", []) or []
    )
    diagnostics: dict[int, dict] = {}
    footer_terms = (
        "firma", "representante legal", "contador", "auditor", "rut",
        "dirección", "direccion", "página", "pagina",
    )
    total_terms = (
        "subtotal", "total", "totales", "sumas", "utilidad del ejercicio",
        "pérdida del ejercicio", "perdida del ejercicio",
    )

    for cuenta in cuentas:
        if not cuenta.montos_columnas:
            continue
        if cuenta.es_total:
            diagnostics[int(cuenta.linea)] = {
                "prioridad": 3,
                "diagnostico": "Control reconocido, no se suma como cuenta",
                "accion_sugerida": (
                    "No necesita excluirlo. Se conserva para comprobar la cuadratura; "
                    "corrija sus importes sólo si difieren del documento."
                ),
                "valores_sugeridos": "",
            }
            continue
        values = {
            column: float(cuenta.montos_columnas.get(column, 0.0) or 0.0)
            for column in RAW_MONETARY_COLUMNS
        }
        movement_error = (
            values["debitos"] - values["creditos"]
            - values["saldo_deudor"] + values["saldo_acreedor"]
        )
        classification_error = (
            values["saldo_deudor"] + values["saldo_acreedor"]
            - values["activo"] - values["pasivo"]
            - values["perdida"] - values["ganancia"]
        )
        name = normalizar_nombre(cuenta.nombre)
        is_inconsistent = int(cuenta.linea) in inconsistent
        suggested: list[str] = []
        movement_candidates = {
            "Debe": values["creditos"] + values["saldo_deudor"] - values["saldo_acreedor"],
            "Haber": values["debitos"] - values["saldo_deudor"] + values["saldo_acreedor"],
            "Saldo deudor": values["debitos"] - values["creditos"] + values["saldo_acreedor"],
            "Saldo acreedor": values["creditos"] - values["debitos"] + values["saldo_deudor"],
        }
        current_movement = {
            "Debe": values["debitos"], "Haber": values["creditos"],
            "Saldo deudor": values["saldo_deudor"],
            "Saldo acreedor": values["saldo_acreedor"],
        }
        if abs(movement_error) > tolerancia:
            zero_first = [
                label for label, current in current_movement.items()
                if current == 0 and movement_candidates[label] > 0
            ]
            labels = zero_first or list(movement_candidates)
            suggested.extend(
                f"{label}: {current_movement[label]:,.0f} → "
                f"{movement_candidates[label]:,.0f}"
                for label in labels
                if movement_candidates[label] >= 0
                and abs(current_movement[label] - movement_candidates[label]) > tolerancia
            )
        classification_values = {
            "Activo": values["activo"], "Pasivo": values["pasivo"],
            "Pérdidas": values["perdida"], "Ganancias": values["ganancia"],
        }
        populated = [label for label, value in classification_values.items() if value != 0]
        saldo_total = values["saldo_deudor"] + values["saldo_acreedor"]
        neto_final = values["activo"] + values["perdida"] - values["pasivo"] - values["ganancia"]
        movimiento_respalda_final = (
            len(populated) == 1
            and abs(values["debitos"] - values["creditos"] - neto_final) <= tolerancia
        )
        if abs(classification_error) > tolerancia and len(populated) == 1 and not movimiento_respalda_final:
            label = populated[0]
            suggested.append(
                f"{label}: {classification_values[label]:,.0f} → {saldo_total:,.0f}"
            )

        if is_inconsistent and movimiento_respalda_final and abs(movement_error) > tolerancia:
            reason = "El movimiento respalda el importe final, pero el saldo intermedio difiere"
            action = "Revise Saldo deudor y Saldo acreedor; no cambie el importe final respaldado por Debe menos Haber."
            priority = 1
        elif is_inconsistent and abs(movement_error) > tolerancia:
            if abs(classification_error) > tolerancia:
                reason = "No coinciden movimiento, saldo y columna de clasificación"
                action = (
                    "Compare Debe/Haber y ambos saldos con el documento; después "
                    "deje el saldo en una sola columna contable."
                )
            else:
                reason = "Debe menos Haber no coincide con el saldo"
                action = (
                    "Revise Débitos, Créditos, Saldo deudor y Saldo acreedor."
                )
            priority = 1
        elif is_inconsistent and abs(classification_error) > tolerancia:
            reason = "El saldo no coincide con Activo/Pasivo/Pérdidas/Ganancias"
            action = (
                "Compare las cuatro columnas finales y deje el importe en la "
                "columna impresa correspondiente."
            )
            priority = 1
        elif any(term in name for term in footer_terms):
            reason = "Posible firma, identificación o pie de página"
            action = "Si no es una cuenta contable, marque Excluir."
            priority = 2
        elif any(name.startswith(term) for term in total_terms):
            reason = "Posible fila de control o resultado del ejercicio"
            action = (
                "Si corresponde a un subtotal, utilidad/pérdida o total impreso, "
                "marque Subtotal/total."
            )
            priority = 2
        else:
            reason = "Sin inconsistencia individual detectada"
            action = (
                "No cambie esta fila salvo que el importe difiera del documento."
            )
            priority = 3

        diagnostics[int(cuenta.linea)] = {
            "prioridad": priority,
            "diagnostico": reason,
            "accion_sugerida": action,
            "valores_sugeridos": "; ".join(suggested),
            "error_movimiento": round(movement_error, 2),
            "error_clasificacion": round(classification_error, 2),
        }
    return diagnostics


def _mensaje_bloqueo_extraccion(certification) -> str:
    """Entrega una instrucción segura para una extracción bloqueada.

    La etiqueta ``SUBTOTAL_IMPRESO_NO_VERIFICABLE`` no identifica una cuenta
    equivocada ni autoriza completar un importe por suma. El mensaje debe
    separar ese caso de un descuadre ordinario para no inducir al analista a
    alterar cuentas que ya podrían estar correctamente leídas.
    """
    diagnostico = str(getattr(certification, "diagnostico", "") or "")
    if diagnostico == "SUBTOTAL_IMPRESO_NO_VERIFICABLE":
        return (
            "El formato fue reconocido, pero un subtotal impreso no se pudo "
            "verificar íntegramente desde el documento. La clasificación y la "
            "entrega quedan bloqueadas: no complete el subtotal por suma ni "
            "cambie las clasificaciones. Solicite una copia legible antes de "
            "reintentar la extracción."
        )
    return (
        "La extracción no reproduce los totales impresos del balance. "
        "El documento no será homologado hasta corregir filas o columnas."
    )


def _permite_clasificar_extraccion(certification) -> bool:
    return bool(certification) and (
        certification.estado in {"certificada", "parcial"}
        or bool(getattr(certification, "columnas_finales_validadas", False))
    )


def _tabla_control_auxiliar(certification) -> pd.DataFrame:
    labels = ("Debe", "Haber", "Saldo deudor", "Saldo acreedor")
    return pd.DataFrame([
        {
            "Columna": label,
            "Suma de cuentas": certification.totales_calculados.get(col, 0),
            "Subtotal impreso": certification.totales_impresos.get(col, 0),
            "Diferencia": certification.diferencias.get(col, 0),
        }
        for col, label in zip(RAW_MONETARY_COLUMNS[:4], labels)
        if abs(certification.diferencias.get(col, 0)) > 10
    ])


def _mostrar_advertencias_auxiliares(certification) -> None:
    if not (
        getattr(certification, "columnas_finales_validadas", False)
        and certification.estado == "fallida"
    ):
        return
    st.warning(
        "Clasificación habilitada: Activo, Pasivo, Pérdidas y Ganancias coinciden "
        "con los controles impresos y cuadran. Quedan diferencias en movimientos "
        "o saldos intermedios; no se certifican las ocho columnas. No cambie los "
        "importes finales ni excluya los totales para resolver esas diferencias."
    )
    with st.expander("Detalle de advertencias de movimientos y saldos"):
        tabla = _tabla_control_auxiliar(certification)
        if not tabla.empty:
            st.dataframe(tabla, hide_index=True, use_container_width=True)
        if certification.observaciones_auxiliares:
            st.dataframe(pd.DataFrame(certification.observaciones_auxiliares), hide_index=True, use_container_width=True)
        st.caption("Las cifras originales se conservan. Estas observaciones también se incluyen en el Excel exportado.")


def _exportar_advertencias_auxiliares(writer, certification) -> None:
    if not (
        getattr(certification, "columnas_finales_validadas", False)
        and certification.estado == "fallida"
    ):
        return
    sheet = "Control de extracción"
    resumen = pd.DataFrame([
        {"Control": "Importes para homologación", "Estado": "Cuatro columnas finales validadas contra controles impresos"},
        {"Control": "Certificación de ocho columnas", "Estado": "No certificada: diferencias en movimientos o saldos"},
        {"Control": "Tratamiento", "Estado": "Cifras originales conservadas; no se aplicaron ajustes automáticos"},
    ])
    resumen.to_excel(writer, sheet_name=sheet, index=False)
    tabla = _tabla_control_auxiliar(certification)
    startrow = len(resumen) + 3
    if not tabla.empty:
        tabla.to_excel(writer, sheet_name=sheet, index=False, startrow=startrow)
        startrow += len(tabla) + 3
    if certification.observaciones_auxiliares:
        pd.DataFrame(certification.observaciones_auxiliares).to_excel(
            writer, sheet_name=sheet, index=False, startrow=startrow,
        )


def _mostrar_etapa_correccion_extraccion(archivo, filename: str) -> None:
    """Corrección a ancho completo y documento en la parte inferior."""
    _mostrar_correccion_extraccion(filename)
    st.divider()
    st.subheader("Documento original")
    _visor_documento(archivo, altura="58vh", mostrar_titulo=False)


def _explicar_diferencia_controles(certification) -> str:
    """Distingue diferencias de movimientos de errores en saldos/clasificación."""
    diferencias = getattr(certification, "diferencias", {}) or {}
    if not set(RAW_MONETARY_COLUMNS).issubset(diferencias):
        return ""
    debe = diferencias["debitos"]
    haber = diferencias["creditos"]
    if (
        abs(debe) > 10 and abs(debe - haber) <= 10
        and all(abs(diferencias[column]) <= 10 for column in RAW_MONETARY_COLUMNS[2:])
        and not getattr(certification, "filas_inconsistentes", [])
    ):
        return (
            f"La diferencia de {abs(debe):,.0f} se repite en Debe y Haber; "
            "los saldos y las cuatro columnas de clasificación coinciden con "
            "el subtotal, y las cuentas cumplen sus identidades individuales. "
            "Revise los movimientos y el subtotal impreso con el emisor: esto "
            "no se corrige reclasificando cuentas ni excluyendo los controles. "
            "Si el subtotal del original es incorrecto, solicite un balance corregido."
        )
    return ""


def _config_importes_extraccion():
    labels = ["Debe", "Haber", "Saldo deudor", "Saldo acreedor",
              "Activo", "Pasivo", "Pérdidas", "Ganancias"]
    return {key: st.column_config.NumberColumn(label, format="localized")
            for key, label in zip(RAW_MONETARY_COLUMNS, labels)}


def _mostrar_correccion_extraccion(filename: str) -> None:
    """Editor seguro previo a homologación para extracciones OCR fallidas."""
    resultado = st.session_state.extraction_pending.get(filename)
    if resultado is None:
        return
    revisions = st.session_state.setdefault("extraction_revisions", {})
    revision = revisions.get(filename, 0)
    if revision:
        st.caption("Sus correcciones están guardadas; el diagnóstico muestra la validación actualizada.")
    st.error(
        "La extracción aún no puede certificarse. La clasificación está pausada "
        "para evitar que una lectura incorrecta llegue al balance homologado."
    )
    rows = []
    certification = getattr(resultado, "certificacion_extraccion", None)
    if getattr(certification, "estado", "") == "no_evaluable":
        st.warning(
            "Falta un subtotal impreso utilizable para validar. Eliminar los controles "
            "no resuelve el descuadre. Conserve o ingrese el subtotal del documento."
        )
    explicacion_control = _explicar_diferencia_controles(certification)
    if explicacion_control:
        st.warning(explicacion_control)
    inconsistent = set(getattr(certification, "filas_inconsistentes", []) or [])
    diagnostics = _diagnosticar_filas_extraccion(
        resultado.cuentas, certification,
    )
    for cuenta in resultado.cuentas:
        if not cuenta.montos_columnas:
            continue
        diagnosis = diagnostics.get(int(cuenta.linea), {})
        rows.append({
            "linea": cuenta.linea,
            "codigo": cuenta.codigo or "",
            "cuenta": cuenta.nombre,
            "inconsistente": int(cuenta.linea) in inconsistent,
            "prioridad": int(diagnosis.get("prioridad", 3)),
            "diagnostico": diagnosis.get("diagnostico", ""),
            "accion_sugerida": diagnosis.get("accion_sugerida", ""),
            "valores_sugeridos": diagnosis.get("valores_sugeridos", ""),
            "excluir": False,
            **{
                column: float(cuenta.montos_columnas.get(column, 0.0) or 0.0)
                for column in RAW_MONETARY_COLUMNS
            },
            "total": bool(cuenta.es_total),
        })
    if not rows:
        if getattr(certification, "diagnostico", "") == (
            "SUBTOTAL_IMPRESO_NO_VERIFICABLE"
        ):
            st.warning(
                "Este formato no expone una grilla de ocho columnas para "
                "editar. El subtotal de control no se puede reconstruir de "
                "forma segura desde las cuentas extraídas; cargue una copia "
                "legible del documento."
            )
        st.warning("OCR no produjo filas tabulares que puedan corregirse.")
        return
    source = pd.DataFrame(rows).sort_values(
        ["prioridad", "linea"], kind="stable",
    ).reset_index(drop=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Filas extraídas", len(source))
    c2.metric("Filas inconsistentes", len(inconsistent))
    c3.metric("Estado", "Bloqueada")
    if certification is not None and certification.razones:
        st.caption(" ".join(certification.razones))
        diferencias = getattr(certification, "diferencias", {}) or {}
        impresos = getattr(certification, "totales_impresos", {}) or {}
        calculados = getattr(certification, "totales_calculados", {}) or {}
        columnas_con_diferencia = [
            column for column, value in diferencias.items() if abs(value) > 10
        ]
        if columnas_con_diferencia:
            st.markdown("#### Qué no coincide")
            labels = {
                "debitos": "Débitos", "creditos": "Créditos",
                "saldo_deudor": "Saldo deudor", "saldo_acreedor": "Saldo acreedor",
                "activo": "Activo", "pasivo": "Pasivo",
                "perdida": "Pérdidas", "ganancia": "Ganancias",
            }
            st.dataframe(pd.DataFrame([
                {
                    "Columna": labels.get(column, column),
                    "Suma de cuentas": float(calculados.get(column, 0) or 0),
                    "Control extraído": float(impresos.get(column, 0) or 0),
                    "Diferencia": float(diferencias[column]),
                }
                for column in columnas_con_diferencia
            ]), use_container_width=True, hide_index=True, column_config={
                key: st.column_config.NumberColumn(key, format="localized")
                for key in ("Suma de cuentas", "Control extraído", "Diferencia")
            })
            final_errors = [c for c in columnas_con_diferencia if c in RAW_MONETARY_COLUMNS[4:]]
            if not final_errors:
                st.info(
                    "Las sumas de Activo, Pasivo, Pérdidas y Ganancias coinciden con el "
                    "control leído. Las diferencias mostradas están en movimientos o saldos. "
                    "No cambie importes finales que coincidan con el PDF: revise los controles "
                    "y las filas señaladas. La validación individual sigue siendo necesaria."
                )

    st.markdown("#### Qué debe hacer el analista")
    st.info(
        "Los subtotales, resultados de cierre y totales reconocidos ya están "
        "fuera de la suma de cuentas. No debe excluirlos: se conservan como "
        "controles para contrastar las cifras extraídas con el documento."
    )
    st.markdown(
        "1. Revise primero las filas señaladas en **Revisar** contra el PDF.  \n"
        "2. Si una fila es un pie de página, firma o texto legal, marque **Excluir**.  \n"
        "3. Sólo si un control aún no está reconocido, active **Subtotal/total**. "
        "Los controles ya reconocidos aparecen separados debajo de las cuentas.  \n"
        "4. Corrija una cifra únicamente cuando sea distinta de la impresa. "
        "Después pulse **Verificar y continuar**."
    )
    st.caption(
        "Los valores sugeridos se calculan desde las identidades Debe/Haber y "
        "saldo/clasificación. No se aplican automáticamente: compárelos con el PDF."
    )
    if inconsistent:
        nombres_inconsistentes = source[source["inconsistente"]][
            ["linea", "cuenta"]
        ].copy()
        st.warning(
            "Estas son las filas concretas que rompen una identidad contable:"
        )
        st.dataframe(
            nombres_inconsistentes.rename(columns={"linea": "Fila", "cuenta": "Cuenta"}),
            use_container_width=True, hide_index=True,
        )
        with st.expander("Detalle de las diferencias y posibles valores", expanded=True):
            st.dataframe(source[source["inconsistente"]][
                ["linea", "cuenta", "diagnostico", "accion_sugerida", "valores_sugeridos"]
            ].rename(columns={"linea": "Fila", "cuenta": "Cuenta",
                              "diagnostico": "Motivo", "accion_sugerida": "Qué revisar",
                              "valores_sugeridos": "Posible corrección, verificar contra PDF"}),
                         hide_index=True, use_container_width=True)
    else:
        st.info(
            "No hay filas con errores individuales detectados. El problema está en la "
            "comparación de las sumas con los controles. Revise primero el subtotal leído "
            "y si falta alguna cuenta o se repite un grupo; no hay una cifra individual "
            "identificada para corregir automáticamente."
        )
    with st.expander("Ingresar una cuenta omitida por la extracción"):
        st.caption(
            "Use esta opción sólo cuando la cuenta exista en el documento y no "
            "aparezca en la tabla. Copie sus ocho columnas tal como están impresas."
        )
        with st.form(f"manual_extraction_row_{filename}", clear_on_submit=True):
            codigo_manual = st.text_input("Código original, si existe")
            nombre_manual = st.text_input("Nombre de la cuenta")
            m1, m2, m3, m4 = st.columns(4)
            debitos_manual = m1.number_input("Debe", value=0.0, format="%.0f")
            creditos_manual = m2.number_input("Haber", value=0.0, format="%.0f")
            saldo_deudor_manual = m3.number_input("Saldo deudor", value=0.0, format="%.0f")
            saldo_acreedor_manual = m4.number_input("Saldo acreedor", value=0.0, format="%.0f")
            c1m, c2m, c3m, c4m = st.columns(4)
            activo_manual = c1m.number_input("Activo", value=0.0, format="%.0f")
            pasivo_manual = c2m.number_input("Pasivo", value=0.0, format="%.0f")
            perdida_manual = c3m.number_input("Pérdidas", value=0.0, format="%.0f")
            ganancia_manual = c4m.number_input("Ganancias", value=0.0, format="%.0f")
            total_manual = st.checkbox("Es subtotal, resultado o total impreso")
            agregar_manual = st.form_submit_button("Agregar cuenta a la extracción")
        if agregar_manual:
            try:
                nueva = _crear_cuenta_manual_extraccion(
                    resultado.cuentas,
                    codigo=codigo_manual,
                    nombre=nombre_manual,
                    montos={
                        "debitos": debitos_manual, "creditos": creditos_manual,
                        "saldo_deudor": saldo_deudor_manual,
                        "saldo_acreedor": saldo_acreedor_manual,
                        "activo": activo_manual, "pasivo": pasivo_manual,
                        "perdida": perdida_manual, "ganancia": ganancia_manual,
                    },
                    es_total=total_manual,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                resultado.cuentas.append(nueva)
                resultado.certificacion_extraccion = certificar_extraccion_columnas(
                    resultado.cuentas, metodo="revision_humana_8_columnas",
                )
                revisions[filename] = revision + 1
                st.success("Cuenta incorporada. Revise la certificación actualizada.")
                st.rerun()
    st.caption("Puede corregir varias celdas antes de guardar. Los números conservan su precisión; los separadores se adaptan al idioma del navegador.")
    with st.form(f"extraction_batch_{filename}_{revision}"):
        controles = source[source["total"]].copy()
        detalle = source[~source["total"]].copy()
        st.markdown("#### Cuentas y filas por revisar")
        edited = st.data_editor(
            detalle,
            hide_index=True,
            use_container_width=True,
            column_order=["linea", "cuenta", "inconsistente", "activo", "pasivo", "perdida", "ganancia",
                          "debitos", "creditos", "saldo_deudor", "saldo_acreedor", "total", "excluir"],
            disabled=[
                "linea", "codigo", "cuenta", "inconsistente", "prioridad",
                "diagnostico", "accion_sugerida",
                "valores_sugeridos",
            ],
            key=f"extraction_editor_{filename}_{revision}",
            column_config={
                "linea": st.column_config.NumberColumn("Fila", format="%d"),
                "codigo": "Código",
                "cuenta": "Cuenta",
                "inconsistente": st.column_config.CheckboxColumn("Revisar"),
                "prioridad": st.column_config.NumberColumn(
                    "Prioridad", help="1: revisar primero; 2: validar tipo de fila; 3: sin señal directa.",
                ),
                "diagnostico": st.column_config.TextColumn(
                    "Qué detectó el sistema", width="large",
                ),
                "accion_sugerida": st.column_config.TextColumn(
                    "Qué debe hacer", width="large",
                ),
                "valores_sugeridos": st.column_config.TextColumn(
                    "Leído → valor contablemente posible", width="large",
                ),
                "excluir": st.column_config.CheckboxColumn(
                    "Excluir", help="Úselo sólo para pies, firmas, notas o texto que no sea una cuenta."
                ),
                "debitos": st.column_config.NumberColumn("Debe", format="localized"),
                "creditos": st.column_config.NumberColumn("Haber", format="localized"),
                "saldo_deudor": st.column_config.NumberColumn("Saldo deudor", format="localized"),
                "saldo_acreedor": st.column_config.NumberColumn("Saldo acreedor", format="localized"),
                "activo": st.column_config.NumberColumn("Activo", format="localized"),
                "pasivo": st.column_config.NumberColumn("Pasivo", format="localized"),
                "perdida": st.column_config.NumberColumn("Pérdidas", format="localized"),
                "ganancia": st.column_config.NumberColumn("Ganancias", format="localized"),
                "total": st.column_config.CheckboxColumn(
                    "Subtotal/total",
                    help="Marque filas de control; no se sumarán como cuentas.",
                ),
            },
        )
        if not controles.empty:
            with st.expander(f"Controles reconocidos: {len(controles)} (no se suman como cuentas)"):
                st.caption(
                    "No requieren exclusión. Edite un importe sólo si está mal leído. "
                    "Desmarque Subtotal/total únicamente si la fila es realmente una cuenta."
                )
                controles_editados = st.data_editor(
                    controles.drop(columns=["excluir"]),
                    hide_index=True,
                    use_container_width=True,
                    column_order=["linea", "cuenta", *RAW_MONETARY_COLUMNS, "total"],
                    key=f"extraction_controls_{filename}_{revision}",
                    disabled=[column for column in controles.columns
                              if column not in (*RAW_MONETARY_COLUMNS, "total", "excluir")],
                    column_config={
                        "linea": "Fila", "cuenta": "Control impreso",
                        **_config_importes_extraccion(),
                        "total": st.column_config.CheckboxColumn("Subtotal/total"),
                    },
                )
                controles_editados["excluir"] = False
                edited = pd.concat([edited, controles_editados], ignore_index=True)
        submitted = st.form_submit_button("🔎 Verificar correcciones y continuar", type="primary")
    if submitted:
        corrected, certification = _aplicar_correcciones_extraccion(
            resultado.cuentas, edited,
        )
        resultado.cuentas = corrected
        resultado.certificacion_extraccion = certification
        st.session_state.setdefault("extraction_certifications", {})[filename] = certification
        revisions[filename] = revision + 1
        if not _permite_clasificar_extraccion(certification):
            st.rerun()
        else:
            st.session_state.extraction_resolved[filename] = corrected
            st.session_state.extraction_pending.pop(filename, None)
            st.session_state.resultados.pop(filename, None)
            st.success("Importes para homologación validados. Iniciando clasificación.")
            st.rerun()


def _extraer_cuentas(archivo) -> tuple[list[CuentaRaw], object]:
    """Extrae cuentas y devuelve (cuentas, document_context).

    `document_context` es el DocumentProcessingContext (Sprint 31) cuando el
    archivo es PDF y el análisis documental corrió; None en caso contrario.
    """
    suffix = Path(archivo.name).suffix.lower()
    st.session_state.setdefault("processed_at", {})[archivo.name] = datetime.now().astimezone().isoformat()
    if suffix == '.pdf':
        import tempfile
        with tempfile.TemporaryDirectory(prefix="balance-seleccion-") as directory:
            tmp_path = Path(directory) / "seleccion.pdf"
            tmp_path.write_bytes(_contenido_para_extraer(archivo))
            parser = ParserPDF()
            resultado = parser.parsear(tmp_path)
        for adv in resultado.advertencias: st.warning(adv)
        document_context = getattr(resultado, 'document_context', None)
        signature = getattr(document_context, 'signature', None)
        if _documento_no_es_balance(signature):
            st.error(
                "El archivo fue identificado como anexo u otro documento, no "
                "como balance. Se detuvo la homologación para evitar interpretar "
                "sus filas con una estructura contable incorrecta."
            )
            return [], document_context
        certificacion = getattr(resultado, 'certificacion_extraccion', None)
        st.session_state.setdefault("extraction_certifications", {})[archivo.name] = certificacion
        if certificacion is not None and certificacion.estado == 'fallida' and not _permite_clasificar_extraccion(certificacion):
            st.error(_mensaje_bloqueo_extraccion(certificacion))
            if getattr(certificacion, 'ecuacion_contable_fuente_valida', None) is True:
                st.info(
                    "La ecuación del subtotal observado sí cuadra, pero el "
                    "detalle extraído no reproduce ese subtotal. Esto no "
                    "habilita clasificación ni entrega."
                )
            if certificacion.razones:
                st.caption(" ".join(certificacion.razones))
            if certificacion.filas_inconsistentes:
                muestra = ", ".join(
                    str(linea) for linea in certificacion.filas_inconsistentes[:12]
                )
                st.caption(
                    f"Filas con inconsistencias internas: {muestra}"
                    + ("…" if len(certificacion.filas_inconsistentes) > 12 else "")
                )
            st.session_state.extraction_pending[archivo.name] = resultado
            return [], document_context
        if certificacion is not None and certificacion.estado == 'certificada':
            resultado_ejercicio = getattr(
                certificacion, 'resultado_ejercicio', None,
            )
            tipo_resultado = getattr(certificacion, 'tipo_resultado', None)
            if resultado_ejercicio is not None and tipo_resultado:
                st.success(
                    "Extracción certificada: las cuentas reproducen el subtotal "
                    f"y el cierre impreso. {tipo_resultado.capitalize()} del "
                    f"ejercicio: ${abs(resultado_ejercicio):,.0f}."
                )
            else:
                st.success(
                    "Extracción certificada: las ocho columnas reproducen los "
                    "subtotales impresos."
                )
            if getattr(certificacion, 'ecuacion_contable_fuente_valida', None) is True:
                st.caption(
                    "Cuadratura de origen validada: Activo − Pasivo = "
                    "Ganancia − Pérdida."
                )
            reconstruidas = getattr(
                certificacion, 'columnas_total_reconstruidas', [],
            )
            if reconstruidas:
                st.info(
                    "El PDF truncaba el último dígito del control de "
                    + " y ".join(reconstruidas)
                    + ". El sistema lo reconstruyó con la suma exacta de las "
                    "cuentas y verificó las otras seis columnas."
                )
        elif certificacion is not None and certificacion.estado == 'parcial':
            st.warning(
                "La ecuación final del balance está cuadrada, pero la extracción "
                "de las cuentas intermedias no está certificada. Todas las cuentas "
                "deben pasar por revisión humana antes de usar el resultado."
            )
            if certificacion.razones:
                st.caption(" ".join(certificacion.razones))
        elif certificacion is not None and certificacion.estado == 'no_evaluable':
            st.info(
                "Este formato todavía no dispone de totales independientes para "
                "certificar automáticamente la extracción. Revise sus cuentas "
                "antes de confirmar la homologación."
            )
        # GATE 4E: SAFE-R02+R03+R08 (ruido de encabezado/pie, URLs/emails,
        # duplicados) aplicado ANTES de la clasificación, ÚNICAMENTE con
        # activación explícita (env SAFE_MODE ON). Con SAFE OFF el
        # comportamiento es exactamente el previo: se devuelven todas las
        # cuentas extraídas, sin filtrado.
        if _safe_mode_enabled():
            return _safe_qualify_cuentas(resultado.cuentas), \
                document_context
        return resultado.cuentas, document_context
    else:
        cuentas = parsear_excel(archivo)
        certificacion = certificar_extraccion_columnas(
            cuentas, metodo="excel_8_columns",
        )
        st.session_state.setdefault("extraction_certifications", {})[archivo.name] = certificacion
        if certificacion.estado == "fallida" and not _permite_clasificar_extraccion(certificacion):
            st.error(
                "Las ocho columnas del Excel no reproducen sus controles "
                "impresos. La homologación queda pausada hasta revisar las filas."
            )
            if certificacion.razones:
                st.caption(" ".join(certificacion.razones))
            st.session_state.extraction_pending[archivo.name] = ResultadoParseo(
                archivo=archivo.name,
                formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles=".",
                requirio_ocr=False,
                rotacion_aplicada=0,
                cuentas=cuentas,
                certificacion_extraccion=certificacion,
            )
            return [], None
        if certificacion.estado == "certificada":
            st.success(
                "Excel certificado: las cuentas reproducen el subtotal y el "
                "control final de sus ocho columnas."
            )
        elif certificacion.estado == "parcial":
            st.warning(
                "El Excel cuadra en su ecuación final, pero requiere revisión "
                "humana de sus filas antes de exportar."
            )
        elif certificacion.estado == "no_evaluable":
            st.info(
                "El Excel no contiene un subtotal independiente de ocho columnas; "
                "su extracción no puede certificarse automáticamente."
            )
        return cuentas, None


def _resumen_estructura_extraida(
        formato: dict | None,
) -> tuple[str, str, str]:
    """Etiqueta la evidencia posterior a la extracción sin sobreprometerla.

    El análisis documental previo puede no reconocer un PDF escaneado porque
    sólo dispone de texto nativo. Esta vista usa el resultado del extractor
    que sí leyó las filas, pero mantiene explícito si sus controles quedaron
    pendientes o fallidos.
    """
    formato = formato or {}
    estado = str(formato.get("estado") or "")
    familia = str(formato.get("familia") or "").strip()
    metodo = str(formato.get("metodo") or "").strip()

    if estado == "SOPORTADO":
        return (
            familia or "Estructura registrada",
            "Extracción certificada",
            metodo or "No informado",
        )
    if estado == "RECONOCIDO_PENDIENTE_VALIDACION":
        return (
            familia or "Estructura registrada",
            "Estructura reconocida, extracción no certificada",
            metodo or "No informado",
        )
    if estado == "NO_ES_BALANCE":
        return (
            "No corresponde a un balance completo",
            "No aplicable",
            metodo or "No informado",
        )
    if estado == "NO_RECONOCIDO":
        return (
            "Estructura no reconocida",
            "No certificada",
            metodo or "No informado",
        )
    return (
        "Sin evidencia de estructura",
        "Sin validar",
        metodo or "No informado",
    )


def _mostrar_informacion_documento(ctx, formato: dict | None = None) -> None:
    """Muestra evidencia previa y evidencia observada durante extracción.

    No modifica ningún resultado. La estructura posterior a OCR se presenta
    antes que el análisis previo para no confundir un PDF escaneado sin texto
    nativo con un formato que el extractor efectivamente reconoció.
    """
    info = {}
    if ctx is not None:
        try:
            info = ctx.ui_summary()
        except Exception:
            info = {}

    estructura, validacion, metodo = _resumen_estructura_extraida(formato)
    if not info and not formato:
        return

    with st.container(border=True):
        st.markdown("#### INFORMACIÓN DEL DOCUMENTO")
        cols = st.columns(4)
        items = [
            ("Estructura extraída", estructura),
            ("Validación de extracción", validacion),
            ("Método de extracción", metodo),
            ("Documento", info.get("Documento", "—")),
        ]
        for i, (label, value) in enumerate(items):
            with cols[i % 4]:
                st.markdown(f"**{label}**  \n`{value}`")

        if info:
            with st.expander("Detalle del análisis previo del PDF"):
                previos = [
                    ("Formato previo", info.get("Formato", "—")),
                    ("Columnas previas", info.get("Columnas", "—")),
                    ("Layout previo", info.get("Layout", "—")),
                    ("OCR requerido", info.get("OCR", "—")),
                    ("Extractor previo", info.get("Extractor", "—")),
                    ("Confianza previa", info.get("Confianza", "—")),
                    ("Familia previa", info.get("Familia", "—")),
                ]
                for label, value in previos:
                    st.caption(f"{label}: {value}")


# ─────────────────────────────────────────────────────────────────────────────
# CONOCIMIENTO DOCUMENTAL (Sprint 32 — Document Knowledge Base)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def _cargar_document_kb():
    """Carga la DKB desde knowledge_base/document_kb.json (None si no existe)."""
    try:
        from document_intelligence.knowledge import DocumentKnowledgeBase
        path = BASE_DIR / "knowledge_base" / "document_kb.json"
        if not path.exists():
            return None
        kb = DocumentKnowledgeBase()
        kb.load(path)
        return kb
    except Exception:
        return None


def _build_fingerprint_archivo(archivo, doc_ctx):
    """Construye el fingerprint del archivo activo (con caché por nombre)."""
    if "document_fingerprints" not in st.session_state:
        st.session_state.document_fingerprints = {}
    name = archivo.name
    if name in st.session_state.document_fingerprints:
        return st.session_state.document_fingerprints[name]

    import tempfile
    from document_intelligence.knowledge.fingerprint import fingerprint_from_file
    suffix = Path(archivo.name).suffix.lower()
    archivo.seek(0)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(archivo.read())
        tmp_path = Path(tmp.name)
    try:
        fp = fingerprint_from_file(tmp_path, signature=doc_ctx.signature)
    finally:
        archivo.seek(0)
        tmp_path.unlink(missing_ok=True)
    st.session_state.document_fingerprints[name] = fp
    return fp


def _tab_conocimiento(archivo, doc_ctx, meta_activo) -> None:
    """Sección CONOCIMIENTO DOCUMENTAL: DKB + matching del documento activo.

    Solo lectura. Si la DKB no está disponible o el matcher falla, muestra
    un aviso y NO afecta ningún resultado.
    """
    if archivo is None or doc_ctx is None:
        st.info("El análisis documental no está disponible para este archivo.")
        return

    kb = _cargar_document_kb()
    if kb is None or not getattr(kb, "profiles", None):
        st.info(
            "📖 La Document Knowledge Base aún no existe. "
            "Ejecuta `python tools/build_document_kb.py` para construirla."
        )
        return

    try:
        fp = _build_fingerprint_archivo(archivo, doc_ctx)
        company = ""
        if meta_activo is not None and getattr(meta_activo, "razon_social", ""):
            company = meta_activo.razon_social
        from document_intelligence.knowledge import Matcher
        result = Matcher().match(fp, kb.profiles, company=company)
    except Exception as exc:  # noqa: BLE001 — el matcher nunca rompe el pipeline
        st.warning(f"El matcher de la DKB no pudo ejecutarse ({exc}).")
        return

    profile = result.matched_profile
    if profile is None:
        st.info("No se encontraron perfiles similares en la DKB.")
        return

    st.markdown("#### 📖 Conocimiento Documental")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Perfil detectado", profile.name, help=profile.description)
    c2.metric("Empresa", profile.company)
    c3.metric("Familia", profile.family)
    c4.metric("Extractor recomendado", profile.recommended_extractor)
    c5.metric("Similitud", f"{result.similarity:.0f}%")

    st.markdown("**Top 5 perfiles similares**")
    ranking_rows = []
    for p, sim in result.ranking[:5]:
        ranking_rows.append({
            "Perfil": p.name,
            "Empresa": p.company,
            "Familia": p.family,
            "Similitud": f"{sim:.0f}%",
            "Frecuencia": p.times_seen,
        })
    st.dataframe(ranking_rows, use_container_width=True, hide_index=True)

    st.markdown("**Variantes conocidas**")
    if profile.known_variants:
        st.write(", ".join(profile.known_variants))
    else:
        st.caption("Sin variantes registradas.")

    st.markdown("**Historial**")
    h1, h2, h3 = st.columns(3)
    h1.metric("Primera aparición", profile.first_seen or "—")
    h2.metric("Última aparición", profile.last_seen or "—")
    h3.metric("Frecuencia (documentos)", profile.times_seen)


@st.cache_resource
def _cargar_mining_result():
    """Carga el resultado de minería desde document_mining.json (None si no existe)."""
    try:
        path = BASE_DIR / "knowledge_base" / "document_mining.json"
        if not path.exists():
            return None
        from document_intelligence.mining import load_analysis_result
        return load_analysis_result(path)
    except Exception:
        return None


def _tab_inteligencia() -> None:
    """Inteligencia del Dataset: minería del DKB (solo lectura).

    Muestra familias descubiertas, cobertura esperada, representantes,
    variantes y confianza. NO edita datos.
    """
    result = _cargar_mining_result()
    if result is None:
        st.info(
            "📈 La minería del dataset aún no existe. "
            "Ejecuta `python tools/run_document_mining.py` para generarla."
        )
        return

    st.markdown("#### 📈 Inteligencia del Dataset")
    st.caption("Familias descubiertas por fingerprint (sin empresa ni nombre de archivo).")

    matrix = result.get("matrix", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Familias detectadas", result.get("n_families", 0))
    c2.metric("Documentos analizados", result.get("n_documents", 0))
    c3.metric("Similitud media global", f"{matrix.get('mean_similarity', 0):.0f}%")
    c4.metric("Pares comparados", f"{matrix.get('pairs_computed', 0):,}")

    coverage = result.get("coverage", {}).get("tiers", [])
    if coverage:
        st.markdown("**Cobertura esperada**")
        st.dataframe([{
            "Top N familias": t["top_n"],
            "Familias": t["families"],
            "Documentos": t["documents"],
            "% acumulado": f"{t['cumulative_pct']}%",
            "% restante": f"{t['remaining_pct']}%",
        } for t in coverage], use_container_width=True, hide_index=True)

    familias = result.get("families", [])
    st.markdown("**Top familias**")
    if familias:
        st.dataframe([{
            "Familia": f["id"],
            "Empresa principal": f.get("top_company", "") or "—",
            "Documentos": f["count"],
            "Similitud interna": f"{f['avg_similarity']:.0f}%",
            "Layout": f["dominant_layout"],
            "Código": f["dominant_code_pattern"],
            "Tipo doc": f["dominant_document_type"],
        } for f in familias[:10]], use_container_width=True, hide_index=True)

    representantes = result.get("representatives", [])
    st.markdown("**Representantes**")
    if representantes:
        st.dataframe([{
            "Familia": r["family_id"],
            "Documento representante": r["file"],
            "Similitud promedio": f"{r['avg_similarity']:.0f}%",
            "Documentos": r["n_documents"],
            "Empresa": r["company"],
        } for r in representantes[:10]], use_container_width=True, hide_index=True)

    recomendaciones = result.get("recommendations", [])
    st.markdown("**Recomendación de extractores**")
    if recomendaciones:
        top = recomendaciones[0]
        st.write(
            f"Desarrollar primero un **`{top['extractor_type']}`** para la familia "
            f"`{top['family_name']}` ({top['count']} documentos, "
            f"{top['pct_dataset']}% del dataset)."
        )
        if len(recomendaciones) > 1:
            st.caption("Siguientes candidatas: " + ", ".join(
                r["family_name"] for r in recomendaciones[1:5]
            ))
    else:
        st.caption("Aún no hay familias con volumen suficiente.")

    variantes = result.get("statistics", {}).get("top_variants", [])
    if variantes:
        st.markdown("**Top variantes (empresa · layout)**")
        st.dataframe([{
            "Empresa": v["company"],
            "Layout": v["layout"],
            "Familias": v["count"],
        } for v in variantes[:10]], use_container_width=True, hide_index=True)

    problemas = result.get("quality_issues", [])
    if problemas:
        st.markdown(f"**Problemas detectados ({len(problemas)})**")
        st.dataframe([{
            "Severidad": p["severity"],
            "Tipo": p["kind"],
            "Detalle": p["message"],
        } for p in problemas[:10]], use_container_width=True, hide_index=True)


def _tab_resumen(df: pd.DataFrame):
    col1, col2, col3, col4, col5 = st.columns(5)
    resumen = _resumen_revision_operativa(df)
    confianza_prom = df.loc[df['confianza'] > 0, 'confianza'].mean()

    col1.metric("Cuentas operables", resumen['operables'])
    col2.metric("Automáticas", resumen['automaticas'])
    col3.metric("Revisión contable", resumen['revision_contable'])
    col4.metric("Cotejo OCR", resumen['cotejo_ocr'])
    col5.metric("Sin clasificar", resumen['sin_clasificar'])
    texto_resumen = (
        f"Cola total: {resumen['cola_total']} cuenta(s). "
        "La revisión contable y el cotejo OCR se informan por separado."
    )
    bloqueadas = resumen['propuestas_bloqueadas_extraccion']
    if bloqueadas:
        texto_resumen += (
            f" {bloqueadas} propuesta(s) de clasificación tienen código, "
            "pero siguen bloqueadas hasta validar la extracción."
        )
    if pd.notna(confianza_prom):
        texto_resumen += f" Confianza promedio: {confianza_prom:.0%}."
    st.caption(texto_resumen)

    st.subheader("Cobertura por método de clasificación")
    dist = df['metodo'].apply(lambda m: m.split('+')[0]).value_counts()
    dist_df = dist.reset_index()
    dist_df.columns = ['Método', 'Cuentas']
    
    METODO_LABELS = {
        'code': '0 · Código de cuenta',
        'codigo': '0 · Código de cuenta',
        'dictionary_exact': '1 · Diccionario exacto',
        'diccionario_exacto': '1 · Diccionario exacto',
        'dictionary_fuzzy': '1b · Diccionario aproximado',
        'diccionario_fuzzy': '1b · Diccionario aproximado',
        'regex_fallback': '2 · Regla auditada',
        'regla_regex': '2 · Regla auditada',
        'accounting_exact_rule': '2a · Regla contable exacta',
        'regex_contextual': '2b · Regla contextual, revisión',
        'contextual_accounting_suggestion': '2b · Regla contextual, revisión',
        'contextual_credit_balance_depreciation': (
            '2b · Contra-activo, revisión'
        ),
        'origin_fallback': '3 · Categoría residual, revisión',
        'unclassified': '4 · Sin clasificar',
        'sin_clasificar': '4 · Sin clasificar',
    }
    dist_df['Método'] = dist_df['Método'].map(lambda m: METODO_LABELS.get(m, m))
    st.dataframe(dist_df, use_container_width=True, hide_index=True)


_TOLERANCIA_CUADRATURA_CANONICA = 1.0
_CATEGORIAS_PENDIENTES_COMERCIALES = (
    "sugeridas_automatizadas",
    "origin_fallback_en_revision",
    "sugerencias_metodo_no_admitido",
    "sugerencias_sin_evidencia_trazable",
    "sugerencias_confianza_insuficiente",
    "sin_clasificar",
    "incompatibles",
    "excluidas",
    "otras_en_revision",
    "propagacion_sin_traza_confirmada",
)


def _incorporar_componentes_cuadratura_canonica(
        estado: dict, cuadratura: dict, *, tolerancia: float,
) -> dict:
    """Expone la misma cuadratura canónica usada para decidir la entrega.

    ``evaluar_entregabilidad`` conserva una vista breve de la cuadratura para
    decidir sus gates. El contrato de salida necesita, además, los componentes
    estáticos de esa misma certificación. No usa el diagnóstico visual, que
    tiene una tolerancia deliberadamente distinta para orientar al analista.
    """
    enriquecido = dict(estado)
    bloque = dict(enriquecido.get("cuadratura_homologada") or {})
    for campo in (
        "certificada",
        "cuadra",
        "activo",
        "pasivo",
        "patrimonio_sin_resultado",
        "resultado_periodo",
        "resultado_derivado_incorporado",
        "resultado_final_fuente_incorporado",
        "resultado_final_fuente",
        "pasivo_mas_patrimonio",
        "diferencia",
        "filas_relevantes",
        "filas_clasificadas",
        "sin_clasificar",
        "codigos_invalidos",
        "incompatibles",
        "pendientes",
        "motivos",
    ):
        if campo in cuadratura:
            bloque[campo] = cuadratura[campo]
    bloque["resultado"] = dict(cuadratura.get("resultado") or {})
    bloque["tolerancia"] = float(tolerancia)
    enriquecido["cuadratura_homologada"] = bloque
    return enriquecido


def _evaluar_estado_entrega_documento(
        df: pd.DataFrame, certificacion, catalogo: dict,
        *, contexto_documental=None, bloqueos_finales=()) -> dict:
    """Compone el contrato de entrega sin alterar las filas del balance."""
    filas = df.to_dict("records")
    incluir_resultado_derivado = debe_incorporar_resultado_derivado(
        filas, certificacion,
    )
    cuadratura = certificar_cuadratura_homologada(
        filas,
        catalogo,
        tolerancia=_TOLERANCIA_CUADRATURA_CANONICA,
        incluir_resultado_derivado=incluir_resultado_derivado,
        resultado_final_fuente=resultado_final_fuente_certificado(
            certificacion,
        ),
        compatibilidad=lambda fila: _codigo_compatible_con_origen(
            fila.get("codigo_clasificado"),
            fila.get("origen_columna"),
            fila.get("monto"),
            fila.get("nombre_original"),
            catalogo,
            seccion_contable=fila.get("seccion_contable"),
            codigo_original=fila.get("codigo_original"),
            anio_cierre=fila.get("anio_cierre"),
        ),
    )
    estado = evaluar_entregabilidad(
        filas,
        certificacion,
        cuadratura,
        compatibilidad=lambda fila: _codigo_compatible_con_origen(
            fila.get("codigo_clasificado"),
            fila.get("origen_columna"),
            fila.get("monto"),
            fila.get("nombre_original"),
            catalogo,
            seccion_contable=fila.get("seccion_contable"),
            codigo_original=fila.get("codigo_original"),
            anio_cierre=fila.get("anio_cierre"),
        ),
        bloqueos_finales=bloqueos_finales,
        formato=evaluar_formato(certificacion, contexto_documental),
    )
    estado = _incorporar_componentes_cuadratura_canonica(
        estado,
        cuadratura,
        tolerancia=_TOLERANCIA_CUADRATURA_CANONICA,
    )
    return _aplicar_guardia_piloto_entrega(estado)


def _proteger_aceptacion_comercial_piloto(aceptacion: dict) -> dict:
    """Evita que un piloto presente una aceptación comercial como final.

    La cobertura calculada sigue siendo evidencia útil para el analista. La
    autorización de entrega revisada, en cambio, queda explícitamente falsa
    mientras el modo piloto esté activo. La copia conserva el diagnóstico
    técnico para auditoría y hace la transformación idempotente, ya que el
    payload puede aplicar la guardia una segunda vez.
    """
    protegido = dict(aceptacion)
    estado_tecnico = protegido.get(
        "estado_tecnico_comercial", protegido.get("estado"),
    )
    apto_tecnico = protegido.get(
        "apto_para_entrega_revisada_tecnica",
        protegido.get("apto_para_entrega_revisada", False),
    )
    mensaje = (
        "Piloto interno: la aceptación comercial es informativa y no "
        "autoriza una entrega revisada ni integración."
    )
    protegido["piloto"] = True
    protegido["estado_tecnico_comercial"] = estado_tecnico
    protegido["apto_para_entrega_revisada_tecnica"] = bool(apto_tecnico)
    protegido["estado"] = "PILOTO_PROVISIONAL_NO_INTEGRAR"
    protegido["apto_para_entrega_revisada"] = False
    protegido["integracion_autorizada"] = False
    protegido["mensaje_piloto"] = mensaje
    motivos = list(protegido.get("motivos") or [])
    if mensaje not in motivos:
        motivos.insert(0, mensaje)
    protegido["motivos"] = motivos
    siguiente_accion = list(protegido.get("siguiente_accion") or [])
    accion = "Completar la revisión humana antes de cualquier integración."
    if accion not in siguiente_accion:
        siguiente_accion.insert(0, accion)
    protegido["siguiente_accion"] = siguiente_accion
    return protegido


def _aplicar_guardia_piloto_entrega(estado: dict) -> dict:
    """Bloquea la promesa de integración cuando la sesión es un piloto.

    La condición técnica se conserva en ``estado``. El piloto agrega una
    restricción de entrega, pero no reemplaza diagnósticos como ``NO_LEGIBLE``
    o ``REVISION_EXTRACCION_REQUERIDA`` por una etiqueta operacional.
    """
    if not _modo_piloto_activo():
        return estado

    protegido = dict(estado)
    estado_tecnico = protegido.get("estado_tecnico", protegido.get("estado"))
    etiqueta_tecnica = protegido.get(
        "etiqueta_tecnica", protegido.get("etiqueta", estado_tecnico),
    )
    permite_revision = bool(
        protegido.get("exportacion_revision_permitida")
        or protegido.get("exportacion_final_permitida"),
    )
    protegido["piloto"] = True
    protegido["estado_tecnico"] = estado_tecnico
    protegido["etiqueta_tecnica"] = etiqueta_tecnica
    protegido["exportacion_final_permitida"] = False
    protegido["exportacion_revision_permitida"] = permite_revision
    if permite_revision:
        protegido["estado_piloto"] = "REVISION_PROVISIONAL"
        protegido["etiqueta_piloto"] = "Piloto: paquete provisional"
        mensaje = (
            "Piloto interno: la salida es provisional y exige revisión humana; "
            "no está autorizada para integración."
        )
    else:
        protegido["estado_piloto"] = "SOLO_DIAGNOSTICO"
        protegido["etiqueta_piloto"] = "Piloto: sólo diagnóstico"
        mensaje = (
            "Piloto interno: sólo se permite diagnóstico; no está autorizado "
            "para revisión operativa ni integración."
        )
    protegido["mensaje_piloto"] = mensaje
    aceptacion_comercial = protegido.get("aceptacion_comercial")
    if isinstance(aceptacion_comercial, dict):
        protegido["aceptacion_comercial"] = (
            _proteger_aceptacion_comercial_piloto(aceptacion_comercial)
        )
    # La etiqueta visible debe ser segura para el cliente. La etiqueta técnica
    # queda explícita en ``etiqueta_tecnica`` para auditoría y diagnóstico.
    protegido["etiqueta"] = protegido["etiqueta_piloto"]
    razones = list(protegido.get("razones") or [])
    if mensaje not in razones:
        razones.insert(0, mensaje)
    protegido["razones"] = razones
    return protegido


def _mostrar_estado_entrega(estado: dict) -> None:
    """Muestra una sola decisión utilizable por cliente y analista."""
    cobertura = estado["cobertura"]
    cuentas = cobertura["cuentas"]
    montos = cobertura["monto_absoluto"]
    estado_codigo = estado["estado"]

    with st.container(border=True):
        st.subheader("Estado del documento")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Estado", estado["etiqueta"])
        col2.metric(
            "Cobertura para revisión",
            f"{cuentas['porcentaje']:.0%}",
            help=(f"{cuentas['cubiertas_para_revision']} de "
                  f"{cuentas['elegibles']} cuentas con saldo"),
        )
        col3.metric(
            "Cobertura monetaria",
            f"{montos['porcentaje']:.0%}",
            help="Cobertura sobre el valor absoluto de las cuentas con saldo.",
        )
        col4.metric("Pendientes del analista", cuentas["pendientes"])
        formato = estado["formato"]
        st.caption(
            f"Legibilidad: {estado['legibilidad'].replace('_', ' ').lower()}. "
            f"Formato: {formato['estado'].replace('_', ' ').lower()}. "
            + formato["mensaje"]
        )

        aceptacion_comercial = estado.get("aceptacion_comercial")
        if isinstance(aceptacion_comercial, dict):
            cobertura_comercial = dict(
                aceptacion_comercial.get("cobertura", {}).get("cuentas", {})
            )
            automaticas_sugeridas = int(
                cobertura_comercial.get("automaticas_o_sugeridas", 0) or 0
            )
            elegibles_comerciales = int(
                cobertura_comercial.get("elegibles", 0) or 0
            )
            decisiones_humanas = sum(
                int(cobertura_comercial.get(categoria, 0) or 0)
                for categoria in (
                    "decisiones_humanas_individuales",
                    "decisiones_humanas_lote",
                    "asistencia_derivada_humano_lote",
                    "asistencia_derivada_humano_historial_confirmado",
                )
            )
            pendientes_comerciales = sum(
                int(cobertura_comercial.get(categoria, 0) or 0)
                for categoria in _CATEGORIAS_PENDIENTES_COMERCIALES
            )
            estado_comercial = str(
                aceptacion_comercial.get("estado", "NO_EVALUADO"),
            ).replace("_", " ").lower()
            st.markdown("#### Cobertura comercial de asistencia")
            comercial_1, comercial_2, comercial_3, comercial_4 = st.columns(4)
            comercial_1.metric("Estado comercial", estado_comercial)
            comercial_2.metric(
                "Automáticas o sugeridas",
                f"{automaticas_sugeridas}/{elegibles_comerciales}",
                help=(
                    "Sólo las automáticas estrictas y sugerencias con "
                    "evidencia forman el numerador comercial."
                ),
            )
            comercial_3.metric(
                "Umbral comercial",
                f"{float(aceptacion_comercial.get('umbral_cobertura', 0)):.0%}",
            )
            comercial_4.metric(
                "Pendientes comerciales", pendientes_comerciales,
            )
            st.caption(
                "Decisiones humanas fuera del indicador comercial: "
                f"{decisiones_humanas}. Cobertura automática o sugerida: "
                f"{float(cobertura_comercial.get('porcentaje', 0)):.0%}."
            )

        if estado.get("piloto"):
            st.warning(estado.get(
                "mensaje_piloto",
                "Piloto interno: la salida no está autorizada para integración.",
            ))
            etiqueta_tecnica = estado.get("etiqueta_tecnica", estado_codigo)
            st.caption(f"Diagnóstico técnico: {etiqueta_tecnica}.")
        elif estado_codigo == "LISTO_PARA_INTEGRAR":
            st.success(
                "El balance tiene extracción, clasificación y cuadratura "
                "certificadas para integración."
            )
        elif estado_codigo == "LISTO_PARA_REVISION_ANALISTA":
            st.warning(
                "La extracción está certificada y el paquete reduce la revisión "
                "a las cuentas pendientes."
            )
        elif estado_codigo == "REVISION_EXTRACCION_REQUERIDA":
            st.warning(
                "Los controles fuente concilian, pero existen cifras finales "
                "reconstruidas. El paquete exige cotejarlas con el original "
                "antes de usar el vaciado."
            )
        elif estado_codigo == "COBERTURA_INSUFICIENTE":
            st.warning(
                "La extracción es válida, pero no hay cobertura suficiente para "
                "una revisión asistida eficiente."
            )
        elif estado_codigo == "LECTURA_NO_RESPALDADA":
            st.warning(
                "Se detectaron cuentas, pero la orientación OCR no tiene evidencia "
                "suficiente. Revise el documento antes de usar sus cifras."
            )
        elif estado_codigo == "FORMATO_NO_SOPORTADO":
            st.warning(
                "El formato no pertenece a una familia que el producto pueda "
                "declarar soportada. Sólo se entrega diagnóstico."
            )
        else:
            st.error(
                "No use estas cifras para integración: falta evidencia suficiente "
                "de legibilidad o extracción."
            )

        if estado["razones"]:
            st.caption(" ".join(estado["razones"][:3]))


def _tabla_para_json(df: pd.DataFrame) -> list[dict]:
    """Serializa tablas del reporte sin filtrar evidencia ni convertir montos a texto."""
    return json.loads(df.to_json(orient="records", force_ascii=False))


_METADATA_NO_INFORMADA = "No informado"


def _valor_documental_exportable(valor):
    """Normaliza ausencia documental sin sustituirla por un dato supuesto."""
    if valor is None:
        return None
    if isinstance(valor, str):
        valor = valor.strip()
        return valor or None
    return valor


def _campo_identificacion_exportacion(valor) -> dict:
    """Expresa tanto el valor documental como su disponibilidad."""
    valor_normalizado = _valor_documental_exportable(valor)
    return {
        "valor": valor_normalizado,
        "estado": "informado" if valor_normalizado is not None else "no_informado",
    }


def _analista_exportacion():
    """Identidad autenticada, si existe; nunca inventa un responsable."""
    actor = st.session_state.get("local_access_actor")
    return _valor_documental_exportable(getattr(actor, "actor_id", None))


def _identificacion_caso_exportacion(
        archivo_nombre: str, meta, *, processed_at: str | None = None,
) -> dict:
    """Entrega metadatos inequívocos y seguros para Excel y JSON.

    ``metadata`` se conserva como contrato histórico del JSON. Esta estructura
    añade el estado de cada campo para distinguir un valor ausente de un valor
    vacío y para no presentar una inferencia como dato documental.
    """
    referencia_piloto = (
        _referencia_exportacion_piloto(archivo_nombre)
        if _modo_piloto_activo() else None
    )
    documento = (
        referencia_piloto["document_id"]
        if referencia_piloto is not None else archivo_nombre
    )
    return {
        "documento": _campo_identificacion_exportacion(documento),
        "empresa": _campo_identificacion_exportacion(
            getattr(meta, "razon_social", None) if meta else None,
        ),
        "rut": _campo_identificacion_exportacion(
            getattr(meta, "rut", None) if meta else None,
        ),
        "periodo_desde": _campo_identificacion_exportacion(
            getattr(meta, "periodo_desde", None) if meta else None,
        ),
        "periodo_hasta": _campo_identificacion_exportacion(
            getattr(meta, "periodo_hasta", None) if meta else None,
        ),
        "moneda_declarada": _campo_identificacion_exportacion(
            getattr(meta, "moneda", None) if meta else None,
        ),
        "giro": _campo_identificacion_exportacion(
            getattr(meta, "giro", None) if meta else None,
        ),
        "analista_id": _campo_identificacion_exportacion(
            _analista_exportacion(),
        ),
        "fecha_proceso": _campo_identificacion_exportacion(processed_at),
    }


def _texto_identificacion_exportacion(campo: dict) -> str:
    """Representación visible de un campo documental sin semántica ambigua."""
    valor = campo.get("valor")
    return str(valor) if valor is not None else _METADATA_NO_INFORMADA


def _controles_materializados_exportacion(
        estado_entrega: dict,
) -> dict:
    """Construye controles estáticos, independientes del recálculo del libro.

    Las fórmulas de ``Resumen`` se conservan como una vista auditable. Este
    bloque es la fuente de entrega para un lector que no ejecuta Excel ni
    LibreOffice. Procede exclusivamente de la cuadratura homologada canónica
    que ya decide la entregabilidad, no del diagnóstico visual de cuadratura.
    """
    cuadratura = dict(estado_entrega.get("cuadratura_homologada") or {})
    resultado = dict(cuadratura.get("resultado") or {})

    def importe(campo: str):
        valor = cuadratura.get(campo)
        try:
            return float(valor) if valor is not None else None
        except (TypeError, ValueError):
            return None

    activo = importe("activo")
    pasivo = importe("pasivo")
    patrimonio_sin_resultado = importe("patrimonio_sin_resultado")
    resultado_periodo = importe("resultado_periodo")
    patrimonio = (
        patrimonio_sin_resultado + resultado_periodo
        if patrimonio_sin_resultado is not None and resultado_periodo is not None
        else None
    )
    pasivo_patrimonio = importe("pasivo_mas_patrimonio")
    diferencia = importe("diferencia")
    tolerancia = importe("tolerancia")
    cuadra = bool(cuadratura.get("cuadra", False))
    return {
        "materializados": True,
        "requiere_recalculo_del_libro": False,
        "fuente_cuadratura": "certificacion_homologada_canonica",
        "total_activos": activo,
        "total_pasivos": pasivo,
        "total_patrimonio": patrimonio,
        "patrimonio_sin_resultado": patrimonio_sin_resultado,
        "resultado_periodo_incorporado": resultado_periodo,
        "pasivo_mas_patrimonio": pasivo_patrimonio,
        "diferencia_activo_menos_pasivo_patrimonio": diferencia,
        "tolerancia_cuadratura": tolerancia,
        "estado_cuadratura": (
            "CUADRA_DENTRO_DE_TOLERANCIA" if cuadra else "NO_CUADRA"
        ),
        "resultado_derivado_incorporado": bool(
            cuadratura.get("resultado_derivado_incorporado", False),
        ),
        "resultado_final_fuente_incorporado": bool(
            cuadratura.get("resultado_final_fuente_incorporado", False),
        ),
        "resultado_final_fuente": importe("resultado_final_fuente"),
        "resultado_segun_columnas_originales": resultado.get(
            "resultado_origen",
        ),
        "resultado_segun_categorias_homologadas": resultado.get(
            "resultado_homologado",
        ),
        "diferencia_resultado": resultado.get("diferencia"),
    }


def _resumen_comercial_para_control(estado_entrega: dict) -> dict:
    """Resume la métrica comercial sin convertirla en una autorización."""
    aceptacion = dict(estado_entrega.get("aceptacion_comercial") or {})
    cobertura = dict(aceptacion.get("cobertura", {}).get("cuentas", {}))
    pendientes = sum(
        int(cobertura.get(categoria, 0) or 0)
        for categoria in _CATEGORIAS_PENDIENTES_COMERCIALES
    )
    decisiones_humanas = sum(
        int(cobertura.get(categoria, 0) or 0)
        for categoria in (
            "decisiones_humanas_individuales",
            "decisiones_humanas_lote",
            "asistencia_derivada_humano_lote",
            "asistencia_derivada_humano_historial_confirmado",
        )
    )
    return {
        "estado": aceptacion.get("estado", "NO_EVALUADO"),
        "estado_tecnico": aceptacion.get(
            "estado_tecnico_comercial", aceptacion.get("estado"),
        ),
        "umbral": aceptacion.get("umbral_cobertura"),
        "automaticas_o_sugeridas": cobertura.get(
            "automaticas_o_sugeridas", 0,
        ),
        "elegibles": cobertura.get("elegibles", 0),
        "porcentaje": cobertura.get("porcentaje", 0.0),
        "decisiones_humanas": decisiones_humanas,
        "pendientes": pendientes,
        "apto_para_revision_comercial": bool(
            aceptacion.get("apto_para_revision_comercial", False),
        ),
        "apto_para_entrega_revisada": bool(
            aceptacion.get("apto_para_entrega_revisada", False),
        ),
        "integracion_autorizada": bool(
            aceptacion.get(
                "integracion_autorizada",
                aceptacion.get("apto_para_entrega_revisada", False),
            ),
        ),
    }


def _payload_entrega_json(
        *, archivo_nombre: str, meta, estado_entrega: dict,
        emision: dict, presentacion: pd.DataFrame,
        detalle: pd.DataFrame, controles_materializados: dict | None = None,
        identificacion_caso: dict | None = None) -> dict:
    """Contrato compartido por el archivo Excel y el JSON descargable."""
    estado_exportacion = _aplicar_guardia_piloto_entrega(estado_entrega)
    permite_paquete_revision = bool(
        estado_exportacion.get("exportacion_final_permitida")
        or estado_exportacion.get("exportacion_revision_permitida")
    )
    emision_exportacion = {
        "definitivo": bool(emision["definitivo"]),
        "motivos": list(emision["motivos"]),
    }
    if _modo_piloto_activo():
        emision_exportacion["definitivo"] = False
        motivo = "Piloto interno: la exportación es provisional y no autoriza integración."
        if motivo not in emision_exportacion["motivos"]:
            emision_exportacion["motivos"].insert(0, motivo)
    rama, commit = _trazabilidad_release_local()
    referencia_piloto = (
        _referencia_exportacion_piloto(archivo_nombre)
        if _modo_piloto_activo() else None
    )
    payload = {
        "schema_version": "1.0",
        "archivo_origen": (
            referencia_piloto["document_id"]
            if referencia_piloto is not None else archivo_nombre
        ),
        "ejecucion": {
            "modo_piloto": _modo_piloto_activo(),
            "rama": rama,
            "commit": commit,
        },
        "estado_entrega": estado_exportacion,
        "emision": {
            "definitiva": emision_exportacion["definitivo"],
            "motivos": emision_exportacion["motivos"],
        },
        "metadata": {
            "razon_social": getattr(meta, "razon_social", "") if meta else "",
            "rut": getattr(meta, "rut", "") if meta else "",
            "periodo_desde": getattr(meta, "periodo_desde", "") if meta else "",
            "periodo_hasta": getattr(meta, "periodo_hasta", "") if meta else "",
            "moneda": getattr(meta, "moneda", "") if meta else "",
        },
        # Un diagnóstico bloqueado puede explicar por qué no se entrega, pero
        # no debe convertirse en un vaciado reutilizable por contener las
        # filas extraídas. Sólo los paquetes expresamente habilitados para
        # revisión o integración incluyen cifras homologadas y de origen.
        "balance_homologado": (
            _tabla_para_json(presentacion) if permite_paquete_revision else []
        ),
        "cuentas_origen": (
            _tabla_para_json(detalle) if permite_paquete_revision else []
        ),
    }
    if identificacion_caso is not None:
        payload["identificacion_caso"] = identificacion_caso
    if controles_materializados is not None:
        payload["controles_materializados"] = controles_materializados
    if referencia_piloto is not None:
        payload["documento_piloto"] = referencia_piloto
    return payload


def _registrar_decision(archivo_nombre, idx, row, codigo, motivo):
    """Historial de esta sesión; Neon conserva además la validación y sugerencia previa."""
    st.session_state.setdefault('historial_decisiones', []).append({
        'Archivo': archivo_nombre, 'Fila': str(idx),
        'Cuenta': row.get('nombre_original', ''),
        'Clasificación anterior': row.get('codigo_clasificado', ''),
        'Clasificación nueva': codigo, 'Método anterior': row.get('metodo', ''),
        'Motivo': motivo, 'Fecha': datetime.now().isoformat(timespec='seconds'),
    })


def _clave_revision_documento(archivo_nombre):
    doc_key = hashlib.sha1(archivo_nombre.encode('utf-8')).hexdigest()[:10]
    revision = st.session_state.get("extraction_revisions", {}).get(archivo_nombre, 0)
    return f"{doc_key}_{revision}" if revision else doc_key


def _solicitar_revision_completa(archivo_nombre):
    doc_key = _clave_revision_documento(archivo_nombre)
    st.session_state[f'revision_vista_{doc_key}'] = 'Todas (incluye confirmadas y excluidas)'
    st.session_state[f'revision_busqueda_{doc_key}'] = ''
    st.session_state['vista_trabajo_solicitada'] = '🔍 Cola de Revisión'


@st.fragment
def _tab_revision(df: pd.DataFrame, catalogo: dict, motor: MotorHibridoLocal, archivo_nombre: str):
    doc_key = _clave_revision_documento(archivo_nombre)
    vista = st.radio(
        'Cuentas a revisar', ['Pendientes', 'Todas (incluye confirmadas y excluidas)'],
        horizontal=True, key=f'revision_vista_{doc_key}',
    )
    busqueda = st.text_input('Buscar cuenta o código', key=f'revision_busqueda_{doc_key}')
    pendientes = (_pendientes_revision(df) if vista == 'Pendientes'
                  else _con_saldo_relevante(df[~df['es_total']]))
    if busqueda.strip() and not pendientes.empty:
        texto = pendientes[['nombre_original', 'codigo_original', 'codigo_clasificado']].fillna('').astype(str).agg(' '.join, axis=1)
        pendientes = pendientes[texto.str.contains(busqueda.strip(), case=False, regex=False)]
    st.caption('Puede cambiar una decisión confirmada o recuperar una cuenta excluida. Elija la nueva clasificación y pulse Confirmar; no necesita volver a cargar el documento.')

    if pendientes.empty:
        st.info("No hay cuentas en esta vista. Seleccione Todas para revisar decisiones anteriores o cambie la búsqueda.")
        return

    # Catálogo ordenado por grupos de presentación y sin cuentas no
    # seleccionables (cálculo / TOTAL). Ver catalog_selection.py.
    opciones_codigo = [''] + opciones_clasificacion(catalogo)
    if _tiene_permiso_cuenta_local(Permission.GLOBAL_DICTIONARY_EDIT):
        opciones_codigo.append('➕ NUEVA CATEGORÍA')
    opciones_codigo.append('🚫 NO INCLUIR')

    checkbox_prefix = f"chk_{doc_key}"
    if st.session_state.get('lote_archivo') != archivo_nombre:
        st.session_state.lote_archivo = archivo_nombre
        st.session_state.lote_seleccion = set()
    elif 'lote_seleccion' not in st.session_state:
        st.session_state.lote_seleccion = set()
    st.session_state.lote_seleccion.intersection_update(pendientes.index)

    n_sel = len(st.session_state.lote_seleccion)
    with st.container(border=True):
        st.markdown(f"#### 📦 Asignación en lote — {n_sel} cuenta(s) seleccionada(s)")
        bc1, bc2, bc3 = st.columns([3, 2, 1])
        with bc1:
            cat_lote = st.selectbox(
                "Clasificar todas las seleccionadas como:", opciones_codigo,
                format_func=lambda c: f"{c} — {catalogo[c]['nombre_estandar']}" if c in catalogo else c if c else "(elegir categoría)",
                key=f"lote_categoria_{doc_key}"
            )
        with bc2:
            alcance_lote = st.radio(
                "Alcance", ["Solo este caso", _etiqueta_alcance_diccionario()],
                index=1, horizontal=True, key=f"lote_alcance_{doc_key}",
            )
        with bc3:
            st.write(""); st.write("")
            confirmar_lote = st.button(f"✅ Confirmar lote ({n_sel})", disabled=(n_sel == 0 or not cat_lote), use_container_width=True)

        if confirmar_lote and n_sel > 0 and cat_lote:
            codigo_lote = '__EXCLUIR__' if cat_lote == '🚫 NO INCLUIR' else (cat_lote if cat_lote != '➕ NUEVA CATEGORÍA' else None)
            if codigo_lote:
                agregar_diccionario_lote = (
                    "diccionario" in alcance_lote.lower()
                    and codigo_lote != '__EXCLUIR__'
                )
                propuesta_equipo_lote = (
                    agregar_diccionario_lote and _usar_diccionario_equipo_local()
                )
                incompatibles = [
                    idx_lote for idx_lote in st.session_state.lote_seleccion
                    if codigo_lote != '__EXCLUIR__'
                    and not _codigo_compatible_con_origen(
                        codigo_lote,
                        df.at[idx_lote, 'origen_columna'],
                        df.at[idx_lote, 'monto'],
                        df.at[idx_lote, 'nombre_original'],
                        catalogo,
                        seccion_contable=df.loc[idx_lote].get('seccion_contable'),
                        codigo_original=df.loc[idx_lote].get('codigo_original'),
                        anio_cierre=df.loc[idx_lote].get('anio_cierre'),
                    )
                ]
                if incompatibles:
                    st.error(
                        "La categoría elegida contradice la columna contable de "
                        f"{len(incompatibles)} cuenta(s). No se aplicó el lote."
                    )
                    st.stop()
                procesados = 0
                fallback_json_lote = False
                validaciones_lote = []
                for idx_lote in list(st.session_state.lote_seleccion):
                    _registrar_decision(archivo_nombre, idx_lote, df.loc[idx_lote].copy(), codigo_lote, 'Confirmación en lote')
                    nombre_orig = df.at[idx_lote, 'nombre_original']
                    codigo_sugerido = df.at[idx_lote, 'codigo_clasificado'] or None
                    metodo_sugerido = df.at[idx_lote, 'metodo']
                    confianza_sugerida = float(df.at[idx_lote, 'confianza'])
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'codigo_clasificado'] = codigo_lote
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'metodo'] = 'validacion_humana_lote'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'confianza'] = 1.0
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'requiere_revision'] = False
                    st.session_state.resultados[archivo_nombre].at[
                        idx_lote, 'propagacion_origen_archivo'
                    ] = ''
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'origen'] = 'Manual'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'regla'] = 'validacion_humana_lote'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'evidencia'] = 'Asignación en lote por analista'
                    validaciones_lote.append({
                        'account_name': nombre_orig,
                        'validated_code': codigo_lote,
                        'source': 'validacion_humana_lote',
                        'add_to_dictionary': (
                            agregar_diccionario_lote and not propuesta_equipo_lote
                        ),
                        'suggested_code': codigo_sugerido,
                        'suggested_method': metodo_sugerido,
                        'suggested_confidence': confianza_sugerida,
                        'source_file': archivo_nombre,
                    })
                    if agregar_diccionario_lote:
                        if propuesta_equipo_lote:
                            _proponer_para_diccionario_equipo(
                                nombre=nombre_orig,
                                codigo=codigo_lote,
                                nota="Confirmación en lote por analista.",
                            )
                        else:
                            entrada = {
                                'cuenta_original': nombre_orig,
                                'codigo_estandar': codigo_lote,
                                'fuente': 'validacion_humana_lote',
                            }
                            _agregar_entrada_diccionario_sesion(entrada)
                    if agregar_diccionario_lote:
                        propagar_clasificacion_resultados(
                            nombre_orig, codigo_lote,
                            'validacion_humana_lote_propagada',
                            archivo_origen=archivo_nombre,
                        )
                    procesados += 1
                persistido = _persistir_validaciones_lote(validaciones_lote)
                fallback_json_lote = not persistido
                if (
                    agregar_diccionario_lote
                    and not propuesta_equipo_lote
                    and fallback_json_lote
                ):
                    with open(BASE_DIR / 'diccionario.json', 'w', encoding='utf-8') as f:
                        json.dump(st.session_state.diccionario, f, ensure_ascii=False, indent=2)
                st.session_state.lote_seleccion = set()
                st.rerun()

        qa, qb, qc = st.columns(3)
        qa.button(
            "☑️ Seleccionar todas", use_container_width=True,
            on_click=_reemplazar_seleccion_lote,
            args=(pendientes.index.tolist(), checkbox_prefix),
        )
        qb.button(
            "🟦 Seleccionar sin clasificar", use_container_width=True,
            on_click=_reemplazar_seleccion_lote,
            args=(pendientes[pendientes['codigo_clasificado'] == ''].index.tolist(), checkbox_prefix),
        )
        qc.button(
            "⬜ Limpiar selección", use_container_width=True,
            on_click=_reemplazar_seleccion_lote,
            args=([], checkbox_prefix),
        )

    pc1, pc2 = st.columns([1, 2])
    with pc1:
        page_size = st.selectbox(
            "Cuentas por página", [10, 25, 50], index=0,
            key=f"revision_page_size_{doc_key}",
        )
    total_pages = max(1, (len(pendientes) + page_size - 1) // page_size)
    current_page = min(
        max(int(st.session_state.get(f"revision_page_{doc_key}", 1)), 1),
        total_pages,
    )
    if st.session_state.get(f"revision_page_{doc_key}") != current_page:
        st.session_state[f"revision_page_{doc_key}"] = current_page
    with pc2:
        page = int(st.number_input(
            "Página", min_value=1, max_value=total_pages,
            step=1, key=f"revision_page_{doc_key}",
        ))
    start = (page - 1) * page_size
    visible = pendientes.iloc[start:start + page_size]
    st.caption(
        f"Mostrando {start + 1}–{min(start + page_size, len(pendientes))} "
        f"de {len(pendientes)} cuentas · página {page} de {total_pages}."
    )

    for idx, row in visible.iterrows():
        seleccionada = idx in st.session_state.lote_seleccion
        with st.container(border=seleccionada):
            c0, c1, c2 = st.columns([0.3, 4, 4])
            with c0:
                checkbox_key = f"{checkbox_prefix}_{idx}"
                st.checkbox(
                    "", value=seleccionada, key=checkbox_key,
                    label_visibility="collapsed",
                    on_change=_alternar_seleccion_lote,
                    args=(idx, checkbox_key),
                )

            with c1:
                col_extraida = row.get('origen_columna', 'desconocido')
                col_actual = row.get(
                    'origen_columna_efectiva',
                    _origen_efectivo(
                        col_extraida, row.get('monto'), row.get('nombre_original'),
                        row.get('seccion_contable'),
                        codigo_original=row.get('codigo_original'),
                        anio_cierre=row.get('anio_cierre'),
                    ),
                ).upper()
                etiqueta_columna = _etiqueta_origen(
                    col_extraida, row.get('monto'), row.get('nombre_original'),
                    row.get('seccion_contable'),
                    codigo_original=row.get('codigo_original'),
                    anio_cierre=row.get('anio_cierre'),
                )
                badge_bg = {
                    'ACTIVO': '#1E90FF', 'PASIVO': '#FF8C00',
                    'PATRIMONIO': '#7E57C2', 'PERDIDA': '#DC143C',
                    'GANANCIA': '#2E8B57',
                }.get(col_actual, '#6B7280')
                st.markdown(
                    f"<span style='background:{badge_bg}; color:white; "
                    f"padding:2px 10px; border-radius:4px; font-size:0.75em; "
                    f"font-weight:600; letter-spacing:0.5px;'>{etiqueta_columna}</span>",
                    unsafe_allow_html=True,
                )
                st.caption("Columna física y naturaleza contable efectiva")
                st.markdown(f"**{_nombre_mostrar(row)}**")
                st.caption(f"Decisión actual: {row.get('codigo_clasificado') or 'Sin clasificar'} · {row.get('metodo', '')}")
                monto_val = row['monto']
                if pd.notna(monto_val):
                    color = 'blue' if monto_val > 0 else ('red' if monto_val < 0 else 'gray')
                    st.markdown(
                        f"<span style='color:{color}; font-weight:bold;'>{monto_val:,.0f}</span>",
                        unsafe_allow_html=True,
                    )
                monto_anterior = row.get('monto_periodo_anterior')
                if pd.notna(monto_anterior):
                    st.caption(
                        f"Período seleccionado: actual · "
                        f"Anterior: {float(monto_anterior):,.0f}"
                    )
                columnas_derivadas = str(row.get('columnas_derivadas') or '').strip()
                if columnas_derivadas:
                    st.warning(
                        "Dato reconstruido contablemente: "
                        f"{columnas_derivadas}. Requiere confirmación humana."
                    )

                edit_mode = st.checkbox("Editar cuenta", key=f"edit_{doc_key}_{idx}")

                if edit_mode:
                    st.divider()
                    nuevo_nombre = st.text_input("Nombre", value=_nombre_mostrar(row), key=f"ed_nombre_{doc_key}_{idx}")
                    opciones_nat = ['ACTIVO', 'PASIVO', 'PERDIDA', 'GANANCIA']
                    columna_fisica = str(col_extraida).upper()
                    idx_nat = opciones_nat.index(columna_fisica) if columna_fisica in opciones_nat else 0
                    nueva_nat = st.selectbox("Columna contable", opciones_nat, index=idx_nat, key=f"ed_nat_{doc_key}_{idx}")
                    monto_inicial = row['monto'] if pd.notna(row['monto']) else 0.0
                    nuevo_monto = st.number_input("Monto", value=float(monto_inicial), format="%.0f", key=f"ed_monto_{doc_key}_{idx}")

                    if st.button("💾 Guardar corrección", key=f"ed_guardar_{doc_key}_{idx}", use_container_width=True):
                        df_mod = st.session_state.resultados[archivo_nombre]
                        original_col = row.get('origen_columna', '')
                        original_monto = row['monto']
                        col_changed = nueva_nat.lower() != original_col
                        monto_changed = (nuevo_monto != original_monto) if pd.notna(original_monto) else (nuevo_monto != 0)

                        if col_changed or monto_changed:
                            sel_clave = st.session_state.get(f"sel_{doc_key}_{idx}", '')
                            codigo_final = sel_clave if sel_clave not in ('', '➕ NUEVA CATEGORÍA', '🚫 NO INCLUIR') else ''
                            codigo_final = codigo_final or str(row.get('codigo_clasificado') or '')
                            if codigo_final and not _codigo_compatible_con_origen(
                                codigo_final, nueva_nat, nuevo_monto, nuevo_nombre, catalogo,
                                codigo_original=row.get('codigo_original'),
                                anio_cierre=row.get('anio_cierre'),
                            ):
                                st.error('La corrección contradice la clasificación actual. Seleccione una categoría compatible antes de guardarla.')
                                st.stop()
                            _registrar_decision(archivo_nombre, idx, row.copy(), codigo_final, 'Corrección de datos de la cuenta')
                            df_mod.at[idx, 'nombre_original'] = nuevo_nombre
                            df_mod.at[idx, 'nombre_revision_usuario'] = ''
                            df_mod.at[idx, 'origen_columna'] = nueva_nat.lower()
                            df_mod.at[idx, 'seccion_contable'] = ''
                            df_mod.at[idx, 'monto'] = nuevo_monto
                            df_mod.at[idx, 'origen_columna_efectiva'] = _origen_efectivo(
                                nueva_nat, nuevo_monto, nuevo_nombre,
                                codigo_original=row.get('codigo_original'),
                                anio_cierre=row.get('anio_cierre'),
                            )
                            df_mod.at[idx, 'origen_columna_display'] = _etiqueta_origen(
                                nueva_nat, nuevo_monto, nuevo_nombre,
                                codigo_original=row.get('codigo_original'),
                                anio_cierre=row.get('anio_cierre'),
                            )
                            if codigo_final:
                                df_mod.at[idx, 'codigo_clasificado'] = codigo_final
                            df_mod.at[idx, 'metodo'] = 'manual_revision'
                            df_mod.at[idx, 'confianza'] = 1.0
                            df_mod.at[idx, 'requiere_revision'] = True
                            df_mod.at[idx, 'propagacion_origen_archivo'] = ''
                            df_mod.at[idx, 'tipo_revision'] = 'correccion_extraccion'
                            df_mod.at[idx, 'origen'] = 'Manual'
                            df_mod.at[idx, 'regla'] = 'manual_revision'
                            df_mod.at[idx, 'evidencia'] = 'Corrección manual de extracción'
                            # Una corrección de extracción es local y debe confirmarse.
                            st.toast(f"'{nuevo_nombre[:35]}' corregida ✅", icon="✅")
                        else:
                            df_mod.at[idx, 'nombre_revision_usuario'] = nuevo_nombre
                            df_mod.at[idx, 'tipo_revision'] = 'visual'
                            st.toast(f"'{nuevo_nombre[:35]}' nombre visual actualizado ✏️", icon="✏️")
                        st.rerun()

            with c2:
                mostrar_todas = st.checkbox(
                    "🔎 Buscar más clasificaciones",
                    key=f"mostrar_todas_{doc_key}_{idx}",
                    help=(
                        "Muestra el catálogo completo para casos contables "
                        "excepcionales que no coinciden con la columna física."
                    ),
                )
                sugerido = row['codigo_clasificado']
                if (not mostrar_todas and sugerido
                        and not _codigo_compatible_con_origen(
                            sugerido, row.get('origen_columna'), row.get('monto'),
                            _nombre_mostrar(row), catalogo,
                            seccion_contable=row.get('seccion_contable'),
                            codigo_original=row.get('codigo_original'),
                            anio_cierre=row.get('anio_cierre'))):
                    sugerido = ''
                st.write(f"Sugerido: **{sugerido or '(ninguno)'}**")

                alternativas = _alternativas_revision(
                    nombre=_nombre_mostrar(row),
                    sugerido=sugerido,
                    confianza=float(row.get('confianza') or 0.0),
                    origen_columna=row.get('origen_columna'),
                    monto=row.get('monto'),
                    catalogo=catalogo,
                    motor=motor,
                    seccion_contable=row.get('seccion_contable'),
                    codigo_original=row.get('codigo_original'),
                    anio_cierre=row.get('anio_cierre'),
                )
                if alternativas:
                    st.caption("Alternativas compatibles · selección asistida, no automática")
                    if (
                        len(alternativas) > 1
                        and alternativas[0]["codigo"] != alternativas[1]["codigo"]
                        and alternativas[0]["score"] - alternativas[1]["score"] <= 0.05
                    ):
                        st.warning(
                            "Señales contradictorias: los dos primeros candidatos "
                            "tienen relevancia similar. Requiere criterio del analista."
                        )
                    alt_cols = st.columns(len(alternativas))
                    for alt_col, alternativa in zip(alt_cols, alternativas):
                        with alt_col:
                            st.markdown(
                                f"**`{alternativa['codigo']}`**  \n"
                                f"{alternativa['nombre']}"
                            )
                            st.caption(
                                f"{alternativa['score']:.0%} · {alternativa['fuente']}  \n"
                                f"{alternativa['evidencia']}"
                            )
                            selection_key = f"sel_{doc_key}_{idx}"
                            st.button(
                                "Usar",
                                key=f"usar_alt_{doc_key}_{idx}_{alternativa['codigo']}",
                                use_container_width=True,
                                on_click=_asignar_estado_widget,
                                args=(selection_key, alternativa['codigo']),
                            )

                if mostrar_todas:
                    opciones_fila = opciones_codigo
                    st.caption("Catálogo completo habilitado para esta cuenta.")
                else:
                    opciones_fila = [opciones_codigo[0]] + [
                        codigo for codigo in opciones_codigo[1:]
                        if codigo in ('➕ NUEVA CATEGORÍA', '🚫 NO INCLUIR')
                        or _codigo_compatible_con_origen(
                            codigo, row.get('origen_columna'), row.get('monto'),
                            _nombre_mostrar(row), catalogo,
                            seccion_contable=row.get('seccion_contable'),
                            codigo_original=row.get('codigo_original'),
                            anio_cierre=row.get('anio_cierre'))
                    ]
                default_idx = (opciones_fila.index(sugerido)
                               if sugerido in opciones_fila else 0)
                seleccion = st.selectbox(
                    "Clasificación correcta",
                    opciones_fila,
                    index=default_idx,
                    format_func=lambda c: (
                        f"{c} — {catalogo[c]['nombre_estandar']}" if c in catalogo
                        else c if c else "(sin clasificar)"
                    ),
                    key=f"sel_{doc_key}_{idx}"
                )

                es_nueva_cat = seleccion == '➕ NUEVA CATEGORÍA'
                if es_nueva_cat:
                    st.info("Define la nueva categoría:")
                    nuevo_codigo = st.text_input("Código (ej: AC.10, ER.17)",
                                                  key=f"new_cod_{doc_key}_{idx}", max_chars=10)
                    nuevo_nombre_cat = st.text_input("Nombre de la categoría",
                                                  key=f"new_nom_{doc_key}_{idx}")
                    nuevo_tipo = st.selectbox("Tipo de estado",
                                              ['balance', 'resultados'],
                                              key=f"new_tipo_{doc_key}_{idx}")
                    nuevo_cat = st.selectbox(
                        "Categoría",
                        ['activo_corriente', 'activo_no_corriente',
                         'pasivo_corriente', 'pasivo_no_corriente',
                         'patrimonio', 'resultado'],
                        key=f"new_cat_{doc_key}_{idx}"
                    )
                    naturaleza_resultado = st.selectbox(
                        'Naturaleza de la nueva categoría', ['ganancia', 'perdida'],
                        key=f'new_naturaleza_{doc_key}_{idx}',
                    ) if nuevo_cat == 'resultado' else None

                if not es_nueva_cat and seleccion not in ('', '🚫 NO INCLUIR'):
                    alcance = st.radio(
                        "¿Aplicar esta clasificación?",
                        ["Solo para este caso",
                         f"{_etiqueta_alcance_diccionario()} (aplica a casos futuros iguales)"],
                        index=1 if row.get('requiere_revision', False) else 0,
                        key=f"alc_{doc_key}_{idx}", horizontal=True
                    )
                else:
                    alcance = "Solo para este caso"

                if st.button("✅ Confirmar", key=f"btn_{doc_key}_{idx}"):
                    codigo_final = None
                    agregar_diccionario = "diccionario" in alcance.lower()
                    propuesta_equipo = (
                        agregar_diccionario and _usar_diccionario_equipo_local()
                    )

                    if es_nueva_cat:
                        if not _tiene_permiso_cuenta_local(
                                Permission.GLOBAL_DICTIONARY_EDIT):
                            st.error(
                                "Solo el administrador puede crear una categoría "
                                "del catálogo original."
                            )
                            st.stop()
                        if nuevo_codigo and nuevo_nombre_cat:
                            nueva_entrada = {
                                'codigo_estandar': nuevo_codigo.strip().upper(),
                                'nombre_estandar': nuevo_nombre_cat.strip(),
                                'categoria': nuevo_cat,
                                'tipo_estado': nuevo_tipo,
                                'naturaleza': 'deudora' if nuevo_cat.startswith('activo') else 'acreedora',
                                'signo_normal': 1,
                                'es_deuda_financiera': False,
                                'es_activo_liquido': False,
                                'afecta_ebitda': False,
                            }
                            if naturaleza_resultado:
                                nueva_entrada['naturaleza'] = 'deudora' if naturaleza_resultado == 'perdida' else 'acreedora'
                                nueva_entrada['signo_normal'] = -1 if naturaleza_resultado == 'perdida' else 1
                            candidato = nuevo_codigo.strip().upper()
                            prefijos = {'activo_corriente': 'AC.', 'activo_no_corriente': 'ANC.',
                                        'pasivo_corriente': 'PC.', 'pasivo_no_corriente': 'PNC.',
                                        'patrimonio': 'PAT.', 'resultado': 'ER.'}
                            if candidato in catalogo or not candidato.startswith(prefijos[nuevo_cat]):
                                st.error('Use un código nuevo con el prefijo de la categoría seleccionada. No se puede redefinir una categoría existente desde esta cuenta.')
                                st.stop()
                            if not _codigo_compatible_con_origen(
                                    candidato, row.get('origen_columna'),
                                    row.get('monto'), _nombre_mostrar(row),
                                    {**catalogo, candidato: nueva_entrada},
                                    seccion_contable=row.get('seccion_contable'),
                                    codigo_original=row.get('codigo_original'),
                                    anio_cierre=row.get('anio_cierre')):
                                st.error('La nueva categoría contradice la naturaleza de esta cuenta. No fue creada.')
                                st.stop()
                            catalogo[nuevo_codigo.strip().upper()] = nueva_entrada
                            if not _persistir_catalogo(nueva_entrada):
                                with open(BASE_DIR / 'catalogo_maestro.json', 'w', encoding='utf-8') as f:
                                    json.dump(catalogo, f, ensure_ascii=False, indent=2)
                            codigo_final = nuevo_codigo.strip().upper()
                            st.toast(f"Nueva categoría '{nuevo_nombre_cat}' ({codigo_final}) creada ✨", icon="🆕")
                        else:
                            st.error("Debes ingresar código y nombre.")

                    elif seleccion == '🚫 NO INCLUIR':
                        _registrar_decision(archivo_nombre, idx, row.copy(), '__EXCLUIR__', 'Exclusión por analista')
                        st.session_state.resultados[archivo_nombre].at[idx, 'codigo_clasificado'] = '__EXCLUIR__'
                        st.session_state.resultados[archivo_nombre].at[idx, 'metodo'] = 'excluido_analista'
                        st.session_state.resultados[archivo_nombre].at[idx, 'confianza'] = 1.0
                        st.session_state.resultados[archivo_nombre].at[idx, 'requiere_revision'] = False
                        st.session_state.resultados[archivo_nombre].at[
                            idx, 'propagacion_origen_archivo'
                        ] = ''
                        if agregar_diccionario and not propuesta_equipo:
                            entrada_exclusion = {
                                'cuenta_original': _nombre_mostrar(row),
                                'codigo_estandar': '__EXCLUIR__',
                                'fuente': 'excluido_analista'
                            }
                            _agregar_entrada_diccionario_sesion(entrada_exclusion)
                        persistido = _persistir_validacion(
                            nombre=_nombre_mostrar(row), codigo='__EXCLUIR__',
                            fuente='excluido_analista',
                            agregar_diccionario=(
                                agregar_diccionario and not propuesta_equipo
                            ),
                            sugerido=row['codigo_clasificado'] or None,
                            metodo=row['metodo'], confianza=float(row['confianza']),
                            archivo=archivo_nombre,
                        )
                        if (
                            agregar_diccionario
                            and not propuesta_equipo
                            and not persistido
                        ):
                            with open(BASE_DIR / 'diccionario.json', 'w', encoding='utf-8') as f:
                                json.dump(st.session_state.diccionario, f, ensure_ascii=False, indent=2)
                        if agregar_diccionario:
                            propagar_clasificacion_resultados(
                                row['nombre_original'],
                                '__EXCLUIR__',
                                'excluido_analista_propagado',
                                archivo_origen=archivo_nombre,
                            )
                        st.session_state.lote_seleccion.discard(idx)
                        st.toast(f"'{_nombre_mostrar(row)[:35]}' excluida", icon="🚫")
                        st.rerun()

                    elif seleccion:
                        codigo_final = seleccion

                    if codigo_final:
                        if not _codigo_compatible_con_origen(
                                codigo_final, row.get('origen_columna'),
                                row.get('monto'), _nombre_mostrar(row), catalogo,
                                seccion_contable=row.get('seccion_contable'),
                                codigo_original=row.get('codigo_original'),
                                anio_cierre=row.get('anio_cierre')):
                            st.error('La categoría contradice la naturaleza contable. No se cambió la cuenta ni se guardó en el diccionario.')
                            st.stop()
                        _registrar_decision(archivo_nombre, idx, row.copy(), codigo_final, 'Confirmación individual')
                        st.session_state.resultados[archivo_nombre].at[idx, 'codigo_clasificado'] = codigo_final
                        st.session_state.resultados[archivo_nombre].at[idx, 'metodo'] = 'validacion_humana'
                        st.session_state.resultados[archivo_nombre].at[idx, 'confianza'] = 1.0
                        st.session_state.resultados[archivo_nombre].at[idx, 'requiere_revision'] = False
                        st.session_state.resultados[archivo_nombre].at[
                            idx, 'propagacion_origen_archivo'
                        ] = ''
                        st.session_state.lote_seleccion.discard(idx)
                        persistido = _persistir_validacion(
                            nombre=row['nombre_original'], codigo=codigo_final,
                            fuente='validacion_humana',
                            agregar_diccionario=(
                                agregar_diccionario and not propuesta_equipo
                            ),
                            sugerido=row['codigo_clasificado'] or None,
                            metodo=row['metodo'], confianza=float(row['confianza']),
                            archivo=archivo_nombre,
                        )
                        if agregar_diccionario:
                            if propuesta_equipo:
                                _proponer_para_diccionario_equipo(
                                    nombre=row['nombre_original'],
                                    codigo=codigo_final,
                                    nota="Confirmación individual por analista.",
                                )
                                st.toast(
                                    f"'{_nombre_mostrar(row)[:35]}' → {codigo_final} "
                                    "propuesto para el equipo",
                                    icon="✅",
                                )
                            else:
                                nuevo_dic = {
                                    'cuenta_original': row['nombre_original'],
                                    'codigo_estandar': codigo_final,
                                    'fuente': 'validacion_humana'
                                }
                                _agregar_entrada_diccionario_sesion(nuevo_dic)
                                if not persistido:
                                    with open(BASE_DIR / 'diccionario.json', 'w', encoding='utf-8') as f:
                                        json.dump(st.session_state.diccionario, f, ensure_ascii=False, indent=2)
                                st.toast(f"'{_nombre_mostrar(row)[:35]}' → {codigo_final} guardado 📚", icon="✅")
                        else:
                            st.toast(f"'{_nombre_mostrar(row)[:35]}' → {codigo_final} (solo este caso)", icon="✅")
                        if agregar_diccionario:
                            propagar_clasificacion_resultados(
                                row['nombre_original'], codigo_final,
                                'validacion_humana_propagada',
                                archivo_origen=archivo_nombre,
                            )
                        st.rerun()


def _diagnosticar_cuadratura(
        df: pd.DataFrame, agrupado: pd.DataFrame,
        clasificadas: pd.DataFrame, tolerancia: float = 1_000,
        certificacion_extraccion=None) -> dict:
    """Concilia el balance homologado y localiza causas probables del descuadre."""
    codigos = agrupado['codigo_clasificado'].fillna('').astype(str)
    activo = agrupado[codigos.str.startswith(('AC.', 'ANC.'))]['monto_total'].sum()
    pasivo_patrimonio = agrupado[
        codigos.str.startswith(('PC.', 'PNC.', 'PAT.'))
    ]['monto_total'].sum()
    diferencia = float(activo - pasivo_patrimonio)

    incompatibles = clasificadas[
        ~clasificadas.apply(
            lambda row: _codigo_compatible_con_origen(
                row.get('codigo_clasificado'), row.get('origen_columna'),
                row.get('monto'), row.get('nombre_original'),
                seccion_contable=row.get('seccion_contable'),
                codigo_original=row.get('codigo_original'),
                anio_cierre=row.get('anio_cierre'),
            ),
            axis=1,
        )
    ].copy()
    if not incompatibles.empty:
        incompatibles['impacto_potencial'] = incompatibles['monto'].abs() * 2
        incompatibles['explica_diferencia'] = (
            incompatibles['impacto_potencial'] - abs(diferencia)
        ).abs() <= tolerancia

    relevantes = _con_saldo_relevante(df[~df['es_total']].copy())
    sin_clasificar = relevantes[relevantes['codigo_clasificado'] == ''].copy()
    excluidas = relevantes[relevantes['codigo_clasificado'] == '__EXCLUIR__'].copy()
    total_cuentas = len(relevantes)
    cuentas_clasificadas = total_cuentas - len(sin_clasificar) - len(excluidas)
    cobertura = cuentas_clasificadas / total_cuentas if total_cuentas else 1.0
    filas_cuadratura = df.to_dict("records")
    cuadratura_homologada = certificar_cuadratura_homologada(
        filas_cuadratura,
        tolerancia=tolerancia,
        incluir_resultado_derivado=debe_incorporar_resultado_derivado(
            filas_cuadratura, certificacion_extraccion,
        ),
        resultado_final_fuente=resultado_final_fuente_certificado(
            certificacion_extraccion,
        ),
        compatibilidad=lambda fila: _codigo_compatible_con_origen(
            fila.get("codigo_clasificado"),
            fila.get("origen_columna"),
            fila.get("monto"),
            fila.get("nombre_original"),
            seccion_contable=fila.get("seccion_contable"),
            codigo_original=fila.get("codigo_original"),
            anio_cierre=fila.get("anio_cierre"),
        ),
    )

    return {
        'activo': float(activo),
        'pasivo_patrimonio': float(pasivo_patrimonio),
        'diferencia': diferencia,
        'cuadra': abs(diferencia) <= tolerancia,
        'tolerancia': tolerancia,
        'incompatibles': incompatibles,
        'sin_clasificar': sin_clasificar,
        'excluidas': excluidas,
        'total_cuentas': total_cuentas,
        'cuentas_clasificadas': cuentas_clasificadas,
        'cobertura': cobertura,
        'cuadratura_homologada': cuadratura_homologada,
    }


def _reabrir_incompatibles(df: pd.DataFrame, indices) -> pd.DataFrame:
    """Devuelve las clasificaciones incompatibles a la cola de revisión humana."""
    resultado = df.copy()
    indices_validos = resultado.index.intersection(indices)
    if len(indices_validos):
        resultado.loc[indices_validos, 'codigo_clasificado'] = ''
        resultado.loc[indices_validos, 'metodo'] = 'reapertura_cuadratura'
        resultado.loc[indices_validos, 'confianza'] = 0.0
        resultado.loc[indices_validos, 'requiere_revision'] = True
        if 'propagacion_origen_archivo' in resultado.columns:
            resultado.loc[indices_validos, 'propagacion_origen_archivo'] = ''
        if 'regla' in resultado.columns:
            resultado.loc[indices_validos, 'regla'] = 'reapertura_cuadratura'
        if 'evidencia' in resultado.columns:
            resultado.loc[indices_validos, 'evidencia'] = (
                'Clasificación incompatible detectada por conciliación contable'
            )
    return resultado


def _mostrar_resumen_cuadratura(
        diagnostico: dict, df: pd.DataFrame, archivo_nombre: str) -> None:
    """Resumen ejecutivo, causas probables y navegación a revisión humana."""
    st.subheader("✅ Control de cuadratura del balance homologado")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Activo normalizado", f"${diagnostico['activo']:,.0f}")
    c2.metric("Pasivo + Patrimonio", f"${diagnostico['pasivo_patrimonio']:,.0f}")
    c3.metric(
        "Diferencia", f"${abs(diagnostico['diferencia']):,.0f}",
        delta="Cuadra" if diagnostico['cuadra'] else "Requiere corrección",
        delta_color="normal" if diagnostico['cuadra'] else "inverse",
    )
    c4.metric(
        "Cobertura", f"{diagnostico['cobertura']:.1%}",
        help=(f"{diagnostico['cuentas_clasificadas']} de "
              f"{diagnostico['total_cuentas']} cuentas con saldo"),
    )

    if diagnostico['cuadra']:
        st.success(
            "El activo homologado coincide con pasivo más patrimonio dentro de "
            f"la tolerancia de ${diagnostico['tolerancia']:,.0f}."
        )
        certificacion = diagnostico.get('cuadratura_homologada', {})
        if certificacion.get('resultado_final_fuente_incorporado', False):
            st.info(
                "La ecuación incorpora el cierre final certificado de la "
                "fuente y lo contrasta con el detalle de resultados."
            )
        if (
            not certificacion.get('resultado_derivado_incorporado', True)
            and not certificacion.get('resultado_final_fuente_incorporado', False)
        ):
            st.info(
                "El resultado proviene de un estado separado y no se añadió "
                "por segunda vez al patrimonio. Su conciliación se mantiene "
                "como un control independiente."
            )
        if not certificacion.get('certificada', False):
            motivos = certificacion.get('motivos', [])
            st.warning(
                "La ecuación aritmética cuadra, pero la homologación completa "
                "todavía no está certificada. " + "; ".join(motivos[:3])
            )
        return

    st.error(
        "El balance homologado no cuadra. La descarga permanece disponible para "
        "auditoría, pero el resultado requiere revisión humana."
    )
    incompatibles = diagnostico['incompatibles']
    sin_clasificar = diagnostico['sin_clasificar']
    excluidas = diagnostico['excluidas']

    with st.container(border=True):
        st.markdown("#### Causas probables")
        if not incompatibles.empty:
            exactas = incompatibles[incompatibles['explica_diferencia']]
            if not exactas.empty:
                st.warning(
                    f"Se encontraron {len(exactas)} clasificación(es) incompatible(s) "
                    "cuyo cambio de lado explica exactamente el descuadre."
                )
            else:
                st.warning(
                    f"Se encontraron {len(incompatibles)} clasificación(es) que "
                    "contradicen la columna contable extraída."
                )
            tabla = incompatibles.copy()
            tabla['Cuenta'] = tabla['nombre_original']
            tabla['Columna extraída'] = tabla['origen_columna'].str.upper()
            tabla['Clasificación actual'] = tabla['codigo_clasificado']
            tabla['Monto'] = tabla['monto'].map(lambda x: f"${x:,.0f}")
            tabla['Impacto si cambia de lado'] = tabla['impacto_potencial'].map(
                lambda x: f"${x:,.0f}"
            )
            st.dataframe(
                tabla[['Cuenta', 'Columna extraída', 'Clasificación actual',
                       'Monto', 'Impacto si cambia de lado']],
                use_container_width=True, hide_index=True,
            )
        if not sin_clasificar.empty:
            st.warning(
                f"Hay {len(sin_clasificar)} cuenta(s) con saldo sin clasificar por "
                f"${sin_clasificar['monto'].abs().sum():,.0f}."
            )
        if not excluidas.empty:
            st.info(
                f"Hay {len(excluidas)} cuenta(s) excluida(s) por "
                f"${excluidas['monto'].abs().sum():,.0f}."
            )
        if incompatibles.empty and sin_clasificar.empty and excluidas.empty:
            st.info(
                "No se detectó una causa única. Revise signos, cuentas contra-activo "
                "y asignaciones de patrimonio cercanas al monto de la diferencia."
            )

        if not incompatibles.empty:
            if st.button(
                f"↩️ Reabrir {len(incompatibles)} cuenta(s) incompatible(s) en revisión",
                type="primary", use_container_width=True,
            ):
                st.session_state.resultados[archivo_nombre] = _reabrir_incompatibles(
                    df, incompatibles.index
                )
                st.session_state['vista_trabajo_solicitada'] = "🔍 Cola de Revisión"
                st.rerun()
        elif st.button("↩️ Volver a la clasificación humana", use_container_width=True):
            st.session_state['vista_trabajo_solicitada'] = "🔍 Cola de Revisión"
            st.rerun()


def _mostrar_control_calidad_operativo(control) -> None:
    """Presenta Structure, Coverage y Self-QA sin mezclarlo con clasificación."""
    st.subheader("🛡️ Control posterior de calidad")
    mode_label = "Aplicado a exportación" if control.mode == "enforced" else "Shadow mode"
    coverage = control.coverage
    monetary = coverage.get("monetary", {})
    semantic = coverage.get("semantic", {})
    qa_state = control.self_qa.get("approval_state", "SIN_DATOS")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Estructura", control.structure.get("column_layout", "—"))
    c2.metric("Cobertura monetaria", f"{float(monetary.get('coverage_pct', 0)):.1%}")
    c3.metric("Cobertura de cuentas", f"{float(semantic.get('overall', 0)):.1%}")
    c4.metric("Self-QA", str(qa_state).replace("_", " "))
    st.caption(
        f"{mode_label}. Los motores auxiliares sólo leen una copia del resultado; "
        "no pueden modificar clasificaciones ni montos."
    )
    if control.requires_review:
        st.warning("Revisión requerida: " + "; ".join(control.reasons) + ".")
    else:
        st.success("Los controles posteriores no detectaron motivos para reabrir la revisión.")
    if not control.export_allowed:
        st.error(
            "Exportación bloqueada por el control posterior. Corrige los motivos "
            "indicados en la cola de revisión y vuelve a este balance."
        )


def _control_emision(df, catalogo, diagnostico, quality_control=None):
    """Control independiente, sin mutar decisiones ni importes del analista."""
    incidencias = []
    for idx, row in df[~df['es_total']].iterrows():
        codigo = str(row.get('codigo_clasificado') or '')
        monto = pd.to_numeric(row.get('monto'), errors='coerce')
        motivos = []
        if pd.isna(monto) or not math.isfinite(float(monto)):
            motivos.append('Importe ausente o no válido')
        elif monto == 0:
            continue
        if codigo == '__EXCLUIR__':
            motivos.append('Cuenta con saldo excluida; revise si debe reincorporarse')
        elif codigo not in catalogo:
            motivos.append('Sin clasificación válida')
        elif not _codigo_compatible_con_origen(
            codigo, row.get('origen_columna'), monto, row.get('nombre_original'), catalogo,
            seccion_contable=row.get('seccion_contable'),
            codigo_original=row.get('codigo_original'),
            anio_cierre=row.get('anio_cierre'),
        ):
            motivos.append('La categoría contradice la naturaleza efectiva de la cuenta')
        if row.get('requiere_revision', False):
            motivos.append('Decisión pendiente de confirmación')
        if motivos:
            incidencias.append({
                'Fila': str(idx), 'Cuenta': row.get('nombre_original', ''),
                'Clasificación': codigo, 'Columna original': row.get('origen_columna', ''),
                'Monto': monto, 'Qué corregir': '; '.join(motivos),
            })
    cuadratura = diagnostico.get('cuadratura_homologada', {})
    resultado = conciliar_resultados(
        df.to_dict('records'),
        catalogo,
        considerar_pat04_declarado=not bool(
            cuadratura.get('resultado_final_fuente_incorporado', False),
        ),
    )
    motivos = list(resultado['problemas'])
    if incidencias:
        motivos.append(f'{len(incidencias)} cuenta(s) requieren corregir o confirmar su clasificación')
    if not diagnostico['cuadra']:
        motivos.append('Activo no coincide con Pasivo más Patrimonio')
    if quality_control is not None and not quality_control.export_allowed:
        motivos.extend(quality_control.reasons or ['El control posterior no autoriza la emisión definitiva'])
    return {'definitivo': not motivos, 'motivos': motivos,
            'incidencias': pd.DataFrame(incidencias), 'resultado': resultado}


def _tab_balance(df: pd.DataFrame, catalogo: dict, archivo_nombre: str):
    st.button('Revisar o cambiar clasificaciones', on_click=_solicitar_revision_completa,
              args=(archivo_nombre,), use_container_width=True)
    clasificadas = df[(df['codigo_clasificado'] != '') & (df['codigo_clasificado'] != '__EXCLUIR__') & (~df['es_total'])].copy()
    clasificadas = _con_saldo_relevante(clasificadas)
    if clasificadas.empty:
        st.info("No hay cuentas clasificadas todavía.")
        return

    clasificadas['monto'] = clasificadas['monto'].fillna(0)
    clasificadas['monto_presentacion'] = clasificadas.apply(
        lambda row: _monto_presentacion(
            row['codigo_clasificado'], row['monto'], row['nombre_original'],
            row.get('origen_columna'), catalogo,
        ), axis=1,
    )
    agrupado = clasificadas.groupby('codigo_clasificado').agg(
        monto_total=('monto_presentacion', 'sum'),
        num_cuentas=('nombre_original', 'count'),
    ).reset_index()
    agrupado['nombre_estandar'] = agrupado['codigo_clasificado'].map(lambda c: catalogo.get(c, {}).get('nombre_estandar', c))
    agrupado['categoria'] = agrupado['codigo_clasificado'].map(lambda c: catalogo.get(c, {}).get('categoria', ''))

    certificacion_extraccion = st.session_state.get(
        "extraction_certifications", {},
    ).get(archivo_nombre)
    incluir_resultado_derivado = debe_incorporar_resultado_derivado(
        df.to_dict('records'), certificacion_extraccion,
    )
    resultado_final_fuente = resultado_final_fuente_certificado(
        certificacion_extraccion,
    )
    conciliacion = conciliar_resultados(
        df.to_dict('records'),
        catalogo,
        considerar_pat04_declarado=resultado_final_fuente is None,
    )
    resultado_periodo = (
        resultado_final_fuente
        if resultado_final_fuente is not None
        else conciliacion['resultado_origen']
    )
    if resultado_periodo is not None and incluir_resultado_derivado:
        derivados = []
        for codigo_resultado in ('ER.11', 'PAT.04'):
            if codigo_resultado not in set(agrupado['codigo_clasificado']):
                info = catalogo.get(codigo_resultado, {})
                derivados.append({
                    'codigo_clasificado': codigo_resultado,
                    'monto_total': (conciliacion['resultado_homologado'] or 0.0)
                        if codigo_resultado == 'ER.11' else resultado_periodo,
                    'num_cuentas': 0,
                    'nombre_estandar': info.get('nombre_estandar', codigo_resultado),
                    'categoria': info.get('categoria', ''),
                })
        if derivados:
            agrupado = pd.concat([agrupado, pd.DataFrame(derivados)], ignore_index=True)

    orden_cat = ['activo_corriente', 'activo_no_corriente', 'pasivo_corriente', 'pasivo_no_corriente', 'patrimonio', 'resultado']
    agrupado['orden'] = agrupado['categoria'].map(lambda c: orden_cat.index(c) if c in orden_cat else 99)
    agrupado = agrupado.sort_values(['orden', 'codigo_clasificado'])

    diagnostico = _diagnosticar_cuadratura(
        df, agrupado, clasificadas,
        certificacion_extraccion=certificacion_extraccion,
    )
    _mostrar_resumen_cuadratura(diagnostico, df, archivo_nombre)
    from pipeline.operational_quality import analyze_operational_quality
    enforce_export = os.environ.get(
        "QUALITY_CONTROL_ENFORCE_EXPORT", "false",
    ).strip().lower() in {"1", "true", "yes", "on"}
    quality_control = analyze_operational_quality(
        df, balance_squared=diagnostico['cuadra'],
        enforce_export=enforce_export,
    )
    st.session_state.setdefault("quality_controls", {})[archivo_nombre] = quality_control
    _mostrar_control_calidad_operativo(quality_control)

    emision = _control_emision(df, catalogo, diagnostico, quality_control)
    estado_entrega = _evaluar_estado_entrega_documento(
        df,
        certificacion_extraccion,
        catalogo,
        contexto_documental=st.session_state.get("document_intel", {}).get(archivo_nombre),
        bloqueos_finales=emision["motivos"],
    )
    if _modo_piloto_activo():
        emision["definitivo"] = False
        motivo_piloto = (
            "Piloto interno: la emisión es provisional y no autoriza integración."
        )
        if motivo_piloto not in emision["motivos"]:
            emision["motivos"].insert(0, motivo_piloto)
    if not estado_entrega["exportacion_final_permitida"]:
        emision["definitivo"] = False
        motivo_estado = "Estado de entrega: " + estado_entrega["etiqueta"]
        if motivo_estado not in emision["motivos"]:
            emision["motivos"].insert(0, motivo_estado)
    st.session_state.setdefault("delivery_readiness", {})[archivo_nombre] = estado_entrega
    presentacion, formulas_reporte = complete_catalog(
        agrupado, catalogo, conciliacion["resultado_homologado"] is not None,
    )
    _validar_cuadre_utilidad(emision['resultado'])
    total_cols = st.columns(3)
    for target, label, categories in (
        (total_cols[0], "Total activos", ("activo_corriente", "activo_no_corriente")),
        (total_cols[1], "Total pasivos", ("pasivo_corriente", "pasivo_no_corriente")),
        (total_cols[2], "Total patrimonio", ("patrimonio",)),
    ):
        total = presentacion[presentacion["categoria"].isin(categories)]["monto_total"].sum()
        target.metric(label, f"{total:,.2f}")
    st.caption("Se muestran todas las clasificaciones del catálogo. Cero indica que no hay importes asignados; no acredita por sí solo la integridad de la extracción.")
    if _modo_piloto_activo():
        st.warning(
            "Piloto interno: cualquier descarga es provisional, debe ser revisada "
            "por un analista y no puede integrarse."
        )
        for motivo in emision['motivos']:
            st.write(motivo)
        if not emision['incidencias'].empty:
            st.dataframe(emision['incidencias'], hide_index=True, use_container_width=True)
    elif emision['definitivo']:
        st.success('Controles de emisión aprobados para este reporte.')
    elif estado_entrega["exportacion_revision_permitida"]:
        st.warning(
            "Se puede descargar un paquete de revisión para el analista. "
            "No debe integrarse hasta resolver las incidencias y volver a cuadrar."
        )
        for motivo in emision['motivos']:
            st.write(motivo)
        if not emision['incidencias'].empty:
            st.dataframe(emision['incidencias'], hide_index=True, use_container_width=True)
    else:
        st.error('Sólo se permite descargar un diagnóstico. Corrija los motivos antes de emitir el reporte definitivo.')
        for motivo in emision['motivos']:
            st.write(motivo)
        if not emision['incidencias'].empty:
            st.dataframe(emision['incidencias'], hide_index=True, use_container_width=True)
        st.caption('Pulse Revisar o cambiar clasificaciones, seleccione Todas y busque la cuenta. Puede modificar decisiones manuales y recuperar cuentas excluidas.')

    resultado_periodo_display = resultado_periodo or 0.0
    r1, r2, r3 = st.columns(3)
    ganancias = clasificadas[
        clasificadas['origen_columna_efectiva'] == 'ganancia'
    ]['monto'].abs().sum()
    perdidas = clasificadas[
        clasificadas['origen_columna_efectiva'] == 'perdida'
    ]['monto'].abs().sum()
    r1.metric("Ganancias", f"${ganancias:,.0f}")
    r2.metric("Pérdidas", f"${perdidas:,.0f}")
    r3.metric(
        "Resultado del período", f"${resultado_periodo_display:,.0f}",
        delta="Utilidad" if resultado_periodo_display >= 0 else "Pérdida",
    )
    st.divider()

    LABELS_CAT = {
        'activo_corriente': '🟦 Activo Corriente', 'activo_no_corriente': '🟦 Activo No Corriente',
        'pasivo_corriente': '🟥 Pasivo Corriente', 'pasivo_no_corriente': '🟥 Pasivo No Corriente',
        'patrimonio': '🟩 Patrimonio', 'resultado': '🟨 Estado de Resultados'
    }

    for cat in orden_cat:
        sub = presentacion[presentacion['categoria'] == cat]
        if sub.empty: continue
        st.subheader(LABELS_CAT.get(cat, cat))
        tabla = sub[['codigo_clasificado', 'nombre_estandar', 'monto_total', 'num_cuentas']].copy()
        tabla.columns = ['Código', 'Cuenta Estándar', 'Monto Total', '# Cuentas Agrupadas']
        tabla['Monto Total'] = tabla['Monto Total'].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "No disponible")
        st.dataframe(tabla, use_container_width=True, hide_index=True)
        if cat == 'resultado':
            st.caption('Ingresos positivos y gastos negativos. El resultado neto es un cálculo y no se suma nuevamente al detalle.')
        else:
            st.metric(f"Subtotal", f"{sub['monto_total'].sum():,.0f}")
        st.divider()

    meta = st.session_state.get('metadata_files', {}).get(archivo_nombre)
    if not estado_entrega["exportacion_revision_permitida"]:
        # No se arma un Excel ni se serializan sus filas cuando la extracción
        # está bloqueada. El diagnóstico conserva el motivo y la trazabilidad,
        # pero no entrega un vaciado que pueda reutilizarse aguas abajo.
        nombre_diagnostico = (
            _nombre_descarga_piloto(archivo_nombre, "DIAGNOSTICO")
            if _modo_piloto_activo()
            else f"DIAGNOSTICO-{Path(archivo_nombre).stem}"
        )
        payload_diagnostico = _payload_entrega_json(
            archivo_nombre=archivo_nombre,
            meta=meta,
            estado_entrega=estado_entrega,
            emision=emision,
            presentacion=pd.DataFrame(),
            detalle=pd.DataFrame(),
            identificacion_caso=_identificacion_caso_exportacion(
                archivo_nombre, meta,
            ),
        )
        st.download_button(
            "Descargar diagnóstico (JSON)",
            data=json.dumps(
                payload_diagnostico, ensure_ascii=False, indent=2,
                default=str,
            ).encode("utf-8"),
            file_name=f"{nombre_diagnostico}.json",
            mime="application/json",
        )
        return

    # Ajuste Patrimonio Efectivo
    pat = agrupado[agrupado['categoria'] == 'patrimonio']
    ac06s = agrupado[agrupado['codigo_clasificado'] == 'AC.06S']
    if not pat.empty:
        monto_ac06s = ac06s['monto_total'].sum() if not ac06s.empty else 0.0
        ajuste = calcular_patrimonio_efectivo(dict(zip(pat['codigo_clasificado'], pat['monto_total'])), monto_ac06s)
        st.subheader("🎯 Patrimonio Efectivo")
        colp1, colp2, colp3 = st.columns(3)
        colp1.metric("Patrimonio contable", f"{ajuste['patrimonio_contable']:,.0f}")
        colp2.metric("Ajuste cta. socios", f"-{ajuste['ajuste_cta_socios']:,.0f}")
        colp3.metric("Patrimonio efectivo", f"{ajuste['patrimonio_efectivo']:,.0f}")

    # Detalle Excel Exporter
    import io
    from openpyxl.styles import Font, PatternFill
    
    export_df = presentacion[["codigo_clasificado", "nombre_estandar", "monto_total", "num_cuentas"]].copy()
    referencia_piloto = (
        _referencia_exportacion_piloto(archivo_nombre)
        if _modo_piloto_activo() else None
    )
    unidad = (getattr(meta, 'moneda', None) or 'unidad original')
    columna_monto = f'Monto Total ({unidad})'
    export_df.columns = ["Código", "Cuenta Estándar", columna_monto, "# Cuentas Agrupadas"]
    export_df['Tipo de fila'] = presentacion['codigo_clasificado'].map(
        lambda c: 'Calculado, no sumar al detalle' if catalogo.get(c, {}).get('clasificable') is False else 'Cuenta'
    )
    processed_at = st.session_state.setdefault("processed_at", {}).setdefault(
        archivo_nombre, datetime.now().astimezone().isoformat(),
    )
    identificacion_caso = _identificacion_caso_exportacion(
        archivo_nombre, meta, processed_at=processed_at,
    )
    controles_materializados = _controles_materializados_exportacion(
        estado_entrega,
    )
    resumen_comercial = _resumen_comercial_para_control(estado_entrega)
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        FILA_INICIO_BALANCE = 7
        export_df.to_excel(writer, index=False, sheet_name="Balance Normalizado", startrow=FILA_INICIO_BALANCE - 1)
        _exportar_advertencias_auxiliares(
            writer, st.session_state.get("extraction_certifications", {}).get(archivo_nombre),
        )
        ws = writer.sheets["Balance Normalizado"]
        if _modo_piloto_activo():
            estado_emision = "PILOTO: PAQUETE PROVISIONAL, NO INTEGRAR"
        elif estado_entrega["estado"] == "LISTO_PARA_INTEGRAR":
            estado_emision = "DEFINITIVO: LISTO PARA INTEGRAR"
        elif estado_entrega["exportacion_revision_permitida"]:
            estado_emision = "PAQUETE DE REVISIÓN ANALISTA"
        else:
            estado_emision = "DIAGNÓSTICO: NO INTEGRAR"
        ws['E1'] = 'Estado de emisión'
        ws['F1'] = estado_emision
        ws['F1'].font = Font(
            bold=True,
            color='008000' if emision['definitivo'] else 'C00000',
        )
        rama_exportacion, commit_exportacion = _trazabilidad_release_local()
        control_filas = [
            {
                'Control': 'Contrato de controles',
                'Valor': (
                    'Valores materializados por el proceso; no requieren '
                    'recálculo del libro.'
                ),
            },
            {
                'Control': 'Requiere recálculo del libro para estos controles',
                'Valor': controles_materializados[
                    'requiere_recalculo_del_libro'
                ],
            },
            {
                'Control': 'Documento de origen',
                'Valor': _texto_identificacion_exportacion(
                    identificacion_caso['documento'],
                ),
            },
            {
                'Control': 'Empresa (metadata documental)',
                'Valor': _texto_identificacion_exportacion(
                    identificacion_caso['empresa'],
                ),
            },
            {
                'Control': 'RUT (metadata documental)',
                'Valor': _texto_identificacion_exportacion(
                    identificacion_caso['rut'],
                ),
            },
            {
                'Control': 'Período desde (metadata documental)',
                'Valor': _texto_identificacion_exportacion(
                    identificacion_caso['periodo_desde'],
                ),
            },
            {
                'Control': 'Período hasta (metadata documental)',
                'Valor': _texto_identificacion_exportacion(
                    identificacion_caso['periodo_hasta'],
                ),
            },
            {
                'Control': 'Moneda declarada (metadata documental)',
                'Valor': _texto_identificacion_exportacion(
                    identificacion_caso['moneda_declarada'],
                ),
            },
            {'Control': 'Unidad de presentación', 'Valor': unidad},
            {
                'Control': 'Analista (ID autenticado)',
                'Valor': _texto_identificacion_exportacion(
                    identificacion_caso['analista_id'],
                ),
            },
            {
                'Control': 'Fecha de proceso',
                'Valor': _texto_identificacion_exportacion(
                    identificacion_caso['fecha_proceso'],
                ),
            },
            {'Control': 'Estado de emisión', 'Valor': estado_emision},
            {'Control': 'Modo piloto', 'Valor': _modo_piloto_activo()},
            {'Control': 'Rama de ejecución', 'Valor': rama_exportacion},
            {'Control': 'Commit de ejecución', 'Valor': commit_exportacion},
            {'Control': 'Estado de entrega', 'Valor': estado_entrega['etiqueta']},
            {
                'Control': 'Estado técnico de entrega',
                'Valor': estado_entrega.get(
                    'etiqueta_tecnica', estado_entrega['etiqueta'],
                ),
            },
            {'Control': 'Cobertura para revisión', 'Valor': estado_entrega['cobertura']['cuentas']['porcentaje']},
            {'Control': 'Cobertura monetaria', 'Valor': estado_entrega['cobertura']['monto_absoluto']['porcentaje']},
            {
                'Control': 'Estado comercial de asistencia',
                'Valor': resumen_comercial['estado'],
            },
            {
                'Control': 'Estado técnico comercial',
                'Valor': resumen_comercial['estado_tecnico'] or 'No informado',
            },
            {
                'Control': 'Umbral de cobertura comercial',
                'Valor': resumen_comercial['umbral'],
            },
            {
                'Control': (
                    'Numerador comercial: automáticas estrictas más '
                    'sugeridas automatizadas'
                ),
                'Valor': resumen_comercial['automaticas_o_sugeridas'],
            },
            {
                'Control': 'Universo elegible comercial',
                'Valor': resumen_comercial['elegibles'],
            },
            {
                'Control': 'Cobertura comercial automática o sugerida',
                'Valor': resumen_comercial['porcentaje'],
            },
            {
                'Control': 'Decisiones humanas fuera del indicador comercial',
                'Valor': resumen_comercial['decisiones_humanas'],
            },
            {
                'Control': 'Pendientes comerciales',
                'Valor': resumen_comercial['pendientes'],
            },
            {
                'Control': 'Apto para revisión comercial',
                'Valor': resumen_comercial['apto_para_revision_comercial'],
            },
            {
                'Control': 'Apto para entrega revisada comercial',
                'Valor': resumen_comercial['apto_para_entrega_revisada'],
            },
            {
                'Control': 'Integración autorizada comercial',
                'Valor': resumen_comercial['integracion_autorizada'],
            },
            {
                'Control': 'Fuente de cuadratura materializada',
                'Valor': controles_materializados['fuente_cuadratura'],
            },
            {
                'Control': 'Total activos (materializado)',
                'Valor': controles_materializados['total_activos'],
            },
            {
                'Control': 'Total pasivos (materializado)',
                'Valor': controles_materializados['total_pasivos'],
            },
            {
                'Control': 'Total patrimonio (materializado)',
                'Valor': controles_materializados['total_patrimonio'],
            },
            {
                'Control': 'Patrimonio sin resultado del período (materializado)',
                'Valor': controles_materializados['patrimonio_sin_resultado'],
            },
            {
                'Control': 'Resultado del período incorporado (materializado)',
                'Valor': controles_materializados[
                    'resultado_periodo_incorporado'
                ],
            },
            {
                'Control': 'Pasivo más patrimonio (materializado)',
                'Valor': controles_materializados['pasivo_mas_patrimonio'],
            },
            {
                'Control': (
                    'Diferencia Activo menos Pasivo y Patrimonio '
                    '(materializada)'
                ),
                'Valor': controles_materializados[
                    'diferencia_activo_menos_pasivo_patrimonio'
                ],
            },
            {
                'Control': 'Tolerancia de cuadratura (materializada)',
                'Valor': controles_materializados['tolerancia_cuadratura'],
            },
            {
                'Control': 'Estado de cuadratura (materializado)',
                'Valor': controles_materializados['estado_cuadratura'],
            },
            {
                'Control': 'Resultado derivado incorporado en cuadratura',
                'Valor': controles_materializados[
                    'resultado_derivado_incorporado'
                ],
            },
            {
                'Control': 'Cierre final fuente incorporado en cuadratura',
                'Valor': controles_materializados[
                    'resultado_final_fuente_incorporado'
                ],
            },
            {
                'Control': 'Cierre final certificado de fuente',
                'Valor': (
                    controles_materializados['resultado_final_fuente']
                    if controles_materializados['resultado_final_fuente'] is not None
                    else 'No informado'
                ),
            },
            {
                'Control': 'Resultado según columnas originales',
                'Valor': controles_materializados[
                    'resultado_segun_columnas_originales'
                ],
            },
            {
                'Control': 'Resultado según categorías homologadas',
                'Valor': controles_materializados[
                    'resultado_segun_categorias_homologadas'
                ],
            },
            {
                'Control': 'Diferencia de resultado',
                'Valor': controles_materializados['diferencia_resultado'],
            },
        ]
        if referencia_piloto is not None:
            control_filas.extend([
                {
                    'Control': 'ID opaco de documento',
                    'Valor': referencia_piloto['document_id'],
                },
                {
                    'Control': 'SHA-256 de origen',
                    'Valor': referencia_piloto['source_sha256'],
                },
            ])
        control_filas += [
            {'Control': 'Pendiente de resolver', 'Valor': motivo}
            for motivo in emision['motivos']
        ]
        pd.DataFrame(control_filas).to_excel(writer, sheet_name='Control de emisión', index=False)
        if not emision['incidencias'].empty:
            emision['incidencias'].to_excel(writer, sheet_name='Cuentas a corregir', index=False)
        historial = [
            h for h in st.session_state.get('historial_decisiones', [])
            if h.get('Archivo') == archivo_nombre
        ]
        if historial:
            if referencia_piloto is not None:
                # El nombre local sólo es una clave de sesión. Una exportación
                # del piloto conserva la traza mediante el identificador opaco.
                historial = [
                    {**decision, 'Archivo': referencia_piloto['document_id']}
                    for decision in historial
                ]
            pd.DataFrame(historial).to_excel(
                writer, sheet_name='Decisiones de esta sesión', index=False,
            )

        ws["A1"] = "Empresa (documental):"
        ws["B1"] = _texto_identificacion_exportacion(
            identificacion_caso['empresa'],
        )
        ws["A2"] = "RUT (documental):"
        ws["B2"] = _texto_identificacion_exportacion(identificacion_caso['rut'])
        ws["A3"] = "Período desde (documental):"
        ws["B3"] = _texto_identificacion_exportacion(
            identificacion_caso['periodo_desde'],
        )
        ws["A4"] = "Período hasta (documental):"
        ws["B4"] = _texto_identificacion_exportacion(
            identificacion_caso['periodo_hasta'],
        )
        ws["A5"] = "Giro (documental):"
        ws["B5"] = _texto_identificacion_exportacion(identificacion_caso['giro'])
        ws["A6"] = "Moneda declarada:"
        ws["B6"] = _texto_identificacion_exportacion(
            identificacion_caso['moneda_declarada'],
        )

        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 36
        ws.column_dimensions["C"].width = 22
        ws.column_dimensions["D"].width = 20

        AZUL = "1F4E79"; BLANCO = "FFFFFF"; GRIS = "F2F2F2"
        header_fill = PatternFill("solid", fgColor=AZUL)
        header_font = Font(bold=True, color=BLANCO, size=11)
        for cell in ws[FILA_INICIO_BALANCE]:
            cell.fill = header_fill
            cell.font = header_font

        for i, row in enumerate(ws.iter_rows(min_row=FILA_INICIO_BALANCE + 1, max_row=FILA_INICIO_BALANCE + len(export_df), max_col=4), start=0):
            if i % 2 == 0:
                for cell in row: cell.fill = PatternFill("solid", fgColor=GRIS)

        fila_sep = FILA_INICIO_BALANCE + len(export_df) + 3

        catalogo_local = catalogo
        det = clasificadas[
            (clasificadas['codigo_clasificado'] != '') &
            (clasificadas['codigo_clasificado'] != '__EXCLUIR__') &
            (~clasificadas['es_total'])
        ][['codigo_clasificado', 'codigo_original', 'nombre_original',
           'nombre_revision_usuario', 'monto', 'origen_columna',
           'origen_columna_efectiva', 'metodo', 'confianza']].copy()

        det['nombre_visual'] = det['nombre_revision_usuario'].where(det['nombre_revision_usuario'] != '', det['nombre_original'])
        det['nombre_estandar'] = det['codigo_clasificado'].map(lambda c: catalogo_local.get(c, {}).get('nombre_estandar', c))
        det['monto_normalizado'] = det.apply(
            lambda row: _monto_presentacion(
                row['codigo_clasificado'], row['monto'], row['nombre_visual'],
                row.get('origen_columna'), catalogo,
            ), axis=1,
        )
        detalle_completo = det[[
            'codigo_clasificado', 'nombre_estandar', 'codigo_original',
            'nombre_visual', 'origen_columna', 'origen_columna_efectiva',
            'monto', 'monto_normalizado', 'metodo', 'confianza',
        ]].copy()

        # Reconstrucción de la lógica de ordenamiento nativo
        detalle_completo = detalle_completo.sort_values(
            ['codigo_clasificado', 'monto'],
            key=lambda x: x.abs() if x.dtype.kind == 'f' else x,
            ascending=[True, False]
        )
        detalle_completo.columns = [
            'Código Estándar', 'Nombre Estándar',
            'Cód. Original', 'Nombre', 'Columna Extraída', 'Naturaleza Efectiva',
            'Monto Extraído', 'Monto Normalizado',
            'Método Clasificación', 'Confianza'
        ]
        detalle_completo['Confianza'] = detalle_completo['Confianza'].apply(
            lambda x: f"{x:.0%}" if pd.notna(x) else ""
        )

        ws.cell(row=fila_sep, column=1, value="APERTURA DE CUENTAS — DETALLE COMPLETO")
        title_cell = ws.cell(row=fila_sep, column=1)
        title_cell.font = Font(bold=True, size=12, color=AZUL)

        detalle_completo.to_excel(
            writer, index=False,
            sheet_name="Balance Normalizado",
            startrow=fila_sep
        )

        header_row_ap = fila_sep + 1
        naranja = "E26B0A"
        for cell in ws[header_row_ap]:
            cell.fill = PatternFill("solid", fgColor=naranja)
            cell.font = Font(bold=True, color=BLANCO, size=10)

        ws.column_dimensions["E"].width = 18
        ws.column_dimensions["F"].width = 20
        ws.column_dimensions["G"].width = 18
        ws.column_dimensions["H"].width = 20
        ws.column_dimensions["I"].width = 22
        ws.column_dimensions["J"].width = 12
        add_report_sheets(
            writer.book, presentacion, formulas_reporte,
            start_row=FILA_INICIO_BALANCE, unit=unidad, meta=meta,
            processed_at=processed_at,
            source_name=(
                referencia_piloto['document_id']
                if referencia_piloto is not None else archivo_nombre
            ),
            pages=st.session_state.get("document_pages", {}).get(archivo_nombre),
            definitive=emision["definitivo"], reasons=emision["motivos"],
            tolerance=diagnostico["tolerancia"],
        )
        # ``Resumen`` conserva fórmulas auditables de presentación. Sus campos
        # identificatorios y la referencia a los controles, en cambio, deben
        # ser visibles aun para un lector que no recalcula el libro.
        resumen = writer.book["Resumen"]
        resumen["B2"] = _texto_identificacion_exportacion(
            identificacion_caso['empresa'],
        )
        resumen["B3"] = _texto_identificacion_exportacion(
            identificacion_caso['rut'],
        )
        resumen["B4"] = (
            "Desde "
            + _texto_identificacion_exportacion(
                identificacion_caso['periodo_desde'],
            )
            + " hasta "
            + _texto_identificacion_exportacion(
                identificacion_caso['periodo_hasta'],
            )
        )
        resumen["B7"] = _texto_identificacion_exportacion(
            identificacion_caso['analista_id'],
        )
        resumen.append([
            "Fuente de controles",
            (
                "La hoja Control de emisión contiene valores materializados "
                "y no requiere recálculo del libro."
            ),
        ])
        ws["E3"] = "Analista (ID autenticado)"
        ws["F3"] = _texto_identificacion_exportacion(
            identificacion_caso['analista_id'],
        )

    buf.seek(0)
    
    # ``archivo_nombre`` es la clave de sesión para recuperar autorización,
    # metadata e historial. Nunca se reemplaza por el nombre de descarga.
    clave_documento = archivo_nombre
    if _modo_piloto_activo():
        nombre_descarga = _nombre_descarga_piloto(clave_documento, "BALANCE")
    else:
        meta_state = meta
        razon_fn = (
            (meta_state.razon_social or "empresa").replace(" ", "_")[:30]
            if meta_state else "empresa"
        )
        rut_fn = (
            (meta_state.rut or "").replace(".", "").replace("-", "")
            if meta_state else ""
        )
        nombre_descarga = f"Balance_Unificado-{razon_fn}-{rut_fn}"
    if not _modo_piloto_activo() and estado_entrega["estado"] in {
        "LISTO_PARA_REVISION_ANALISTA",
        "REVISION_EXTRACCION_REQUERIDA",
    }:
        nombre_descarga = 'REVISION-' + nombre_descarga
    elif not _modo_piloto_activo() and not emision['definitivo']:
        nombre_descarga = 'DIAGNOSTICO-' + nombre_descarga

    payload_json = _payload_entrega_json(
        archivo_nombre=clave_documento,
        meta=meta,
        estado_entrega=estado_entrega,
        emision=emision,
        presentacion=presentacion,
        detalle=detalle_completo,
        controles_materializados=controles_materializados,
        identificacion_caso=identificacion_caso,
    )
    payload_json_bytes = json.dumps(
        payload_json, ensure_ascii=False, indent=2, default=str,
    ).encode("utf-8")

    descarga_excel, descarga_json = st.columns(2)
    # Se invoca el API global dentro de cada columna para conservar los
    # adaptadores de interfaz que ya capturan la descarga de Excel.
    with descarga_json:
        st.download_button(
            ('Descargar paquete piloto provisional (JSON)'
             if _modo_piloto_activo()
             else ('Descargar contrato de integración (JSON)' if emision['definitivo']
                   else 'Descargar contrato de revisión (JSON)')),
            data=payload_json_bytes,
            file_name=f"{nombre_descarga}.json",
            mime="application/json",
        )
    with descarga_excel:
        st.download_button(
            ('Descargar balance piloto provisional (Excel)'
             if _modo_piloto_activo()
             else ('Descargar balance definitivo (Excel)' if emision['definitivo']
                   else 'Descargar paquete con diagnóstico (Excel)')),
            data=buf.getvalue(),
            file_name=f"{nombre_descarga}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

def _validar_cuadre_utilidad(resultado):
    st.subheader('Conciliación independiente del estado de resultados')
    if resultado['resultado_origen'] is None and resultado['resultado_homologado'] is None:
        st.info('El documento no contiene detalle de ingresos y gastos para conciliar el resultado.')
        return
    c1, c2, c3 = st.columns(3)
    def mostrar(valor):
        return 'Sin detalle' if valor is None else f'{valor:,.2f}'
    c1.metric('Resultado según columnas originales', mostrar(resultado['resultado_origen']))
    c2.metric('Resultado según categorías homologadas', mostrar(resultado['resultado_homologado']))
    c3.metric('Diferencia del resultado', mostrar(resultado['diferencia']))
    if resultado['cuadra']:
        st.success('Las categorías de ingresos y gastos reproducen el resultado de las columnas originales.')
    else:
        st.error('Las categorías asignadas no reproducen el resultado de origen o falta detalle para comprobarlo. Revise las cuentas indicadas antes de emitir.')


def _tab_diccionario():
    busqueda = st.text_input("Buscar en el diccionario", "")
    catalogo_local = cargar_catalogo()
    dic = st.session_state.diccionario
    df_dic = pd.DataFrame(dic)
    
    df_dic['nombre_estandar'] = df_dic['codigo_estandar'].map(
        lambda c: catalogo_local.get(c, {}).get('nombre_estandar', '') if c else ''
    )
    df_dic['codigo_y_nombre'] = df_dic.apply(
        lambda r: f"{r['codigo_estandar']} — {r['nombre_estandar']}" if r['nombre_estandar']
        else r['codigo_estandar'], axis=1
    )
    if busqueda:
        mask = (
            df_dic['cuenta_original'].str.contains(busqueda, case=False, na=False) |
            df_dic['nombre_estandar'].str.contains(busqueda, case=False, na=False) |
            df_dic['codigo_estandar'].str.contains(busqueda, case=False, na=False)
        )
        df_dic = df_dic[mask]
    st.caption(f"{len(df_dic)} entradas encontradas")
    st.dataframe(
        df_dic[['cuenta_original', 'codigo_y_nombre', 'fuente']].rename(columns={
            'cuenta_original': 'Cuenta Original',
            'codigo_y_nombre': 'Código — Nombre Estándar',
            'fuente': 'Fuente'
        }),
        use_container_width=True, hide_index=True, height=500
    )


def _tab_aprendizaje():
    st.subheader("🧠 Autoaprendizaje — Gold Standard")
    if _modo_piloto_activo():
        st.info(
            "La gestión de aprendizaje y runtime está deshabilitada durante "
            "el piloto no mutativo."
        )
        return
    store = NeonKnowledgeStore()
    if _neon_disponible():
        try:
            stats = store.learning_statistics()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Diccionario activo", stats["dictionary_entries"])
            c2.metric("Aprendidas por humanos", stats["human_learned"])
            c3.metric("Validaciones registradas", stats["validations"])
            c4.metric("Correcciones", stats["corrections"])
            st.caption(
                "Fuente: Neon. Cada validación queda auditada y las entradas agregadas "
                "al diccionario son consumidas por el pipeline en futuras sesiones."
            )
            recientes = store.recent_validations(20)
            if recientes:
                st.markdown("#### Actividad reciente")
                st.dataframe(pd.DataFrame(recientes), use_container_width=True, hide_index=True)
            else:
                st.info("Neon está conectado; aún no hay validaciones registradas.")
            return
        except Exception:
            st.warning("No fue posible leer las métricas de Neon; se muestran datos locales.")
    try:
        builder = GoldBuilder()
        stats = builder.statistics()
        top = builder.top_learned()
        conflicts = builder.find_conflicts()
        builder.close()
    except Exception as e:
        st.error(f"No se pudieron cargar estadísticas: {e}")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Registros aprendidos", stats["total_records"])
    c2.metric("Coincidencias exactas", stats["exact_hits"])
    c3.metric("Cuentas con conflicto", stats["conflicts"])

    if stats["total_records"] > 0:
        st.subheader("🏆 Top 20 cuentas más aprendidas")
        top_df = pd.DataFrame(top)
        top_df.columns = ["Cuenta", "Código Final", "Veces Usada", "Último Uso"]
        top_df["Último Uso"] = top_df["Último Uso"].str[:19]
        st.dataframe(top_df, use_container_width=True, hide_index=True)

    if conflicts:
        st.subheader("⚔️ Cuentas con conflicto (múltiples códigos asignados)")
        cf_df = pd.DataFrame(conflicts)
        cf_df.columns = ["Cuenta", "Códigos Distintos", "Códigos", "Versiones"]
        st.dataframe(cf_df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay cuentas con conflictos de clasificación.")

    st.divider()
    st.subheader("🔄 Promoción al Gold Standard (Learning Loop)")
    st.caption(
        "Promueve las revisiones humanas (gold_records) a una base RUNTIME separada "
        "(`gold_standard_runtime.db`). La base del benchmark (2660/2662) NO se modifica. "
        "Ver `reports/product/P1_learning_loop_design.md`."
    )
    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        if st.button("🔍 Previsualizar promoción", use_container_width=True):
            try:
                res = promover_revisiones(dry_run=True)
                st.success(
                    f"Candidatos: {res.candidates} · Promovibles: {res.promotable} · "
                    f"Conflictos: {res.conflicts} · Duplicados: {res.duplicates} · "
                    f"Reservados (total): {res.reserved}"
                )
                if res.conflict_details:
                    st.warning("Conflictos (se omiten de la promoción):")
                    for c in res.conflict_details:
                        st.write(f"- {c['name']}: candidato={c['candidate_code']} gold={c['existing_codes']}")
            except Exception as e:
                st.error(f"No se pudo previsualizar: {e}")
    with pc2:
        if st.button("✅ Aplicar a runtime", use_container_width=True):
            try:
                res = promover_revisiones(dry_run=False)
                st.success(
                    f"Promovidos: {res.promoted} · Conflictos omitidos: {res.conflicts} · "
                    f"Duplicados: {res.duplicates} · Reservados: {res.reserved}"
                )
            except Exception as e:
                st.error(f"No se pudo aplicar: {e}")
    with pc3:
        if st.button("🧹 Borrar runtime", use_container_width=True):
            try:
                rt = RuntimeGoldStorage()
                rt.close()
                rt.path.unlink(missing_ok=True)
                st.success("Runtime eliminado. El benchmark sigue intacto.")
            except Exception as e:
                st.error(f"No se pudo borrar: {e}")


def _km_usuario() -> str:
    actor = st.session_state.get("local_access_actor")
    actor_id = getattr(actor, "actor_id", None)
    if actor_id:
        return str(actor_id)
    return str(st.session_state.get("km_usuario", "analista"))


def _tab_knowledge_manager() -> None:
    """🧠 Knowledge Manager (P5).

    Administra EXCLUSIVAMENTE ``gold_standard_runtime.db`` a través de
    ``RuntimeManager`` (única capa de persistencia). La UI no ejecuta SQL ni
    abre conexiones SQLite. El benchmark (``gold_standard.db``) nunca se escribe.
    Toda acción (promover, rechazar, rollback) requiere aprobación explícita.
    """
    st.subheader("🧠 Knowledge Manager")
    if _modo_piloto_activo():
        st.info(
            "Las promociones, rechazos y rollbacks están deshabilitados "
            "durante el piloto no mutativo."
        )
        return
    if _neon_disponible():
        _tab_neon_knowledge_manager()
        return
    st.caption(
        "Administra exclusivamente `gold_standard_runtime.db` vía `RuntimeManager`. "
        "El benchmark (`gold_standard.db`) permanece intacto. Eventos auditables: "
        "PROMOTE / ROLLBACK / REJECT. Estado del candidato: PENDING / APPROVED / "
        "REJECTED / ROLLED_BACK."
    )

    runtime_path = BASE_DIR / "gold_standard_runtime.db"
    gold_path = BASE_DIR / "gold_standard.db"
    rm = RuntimeManager(runtime_path)

    tab_pend, tab_conf, tab_run, tab_hist, tab_stat, tab_an = st.tabs(
        ["📥 Promociones pendientes", "⚔️ Conflictos", "🗃️ Runtime",
         "📜 Historial", "📊 Estadísticas", "📊 Runtime Analytics"]
    )

    with tab_pend:
        _km_pendientes(rm, gold_path)
    with tab_conf:
        _km_conflictos(rm, gold_path)
    with tab_run:
        _km_runtime(rm)
    with tab_hist:
        _km_historial(rm)
    with tab_stat:
        _km_estadisticas(rm, gold_path)
    with tab_an:
        _km_runtime_analytics(rm, gold_path)


def _tab_neon_knowledge_manager() -> None:
    """Gobernanza durable del diccionario cuando Neon es la fuente activa."""
    if _modo_piloto_activo():
        st.info(
            "Los cambios de diccionario están deshabilitados durante el "
            "piloto no mutativo."
        )
        return
    store = NeonKnowledgeStore()
    st.caption(
        "Fuente durable: Neon. El rollback solo se permite si el cambio elegido "
        "continúa siendo el estado vigente de la cuenta."
    )
    tab_hist, tab_conf, tab_stats = st.tabs(
        ["📜 Historial", "⚔️ Conflictos", "📊 Estadísticas"]
    )
    with tab_hist:
        history = store.dictionary_history(100)
        if not history:
            st.info("Aún no hay cambios humanos en el diccionario Neon.")
        else:
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
            options = {
                f"#{row['id']} · {row['cuenta_original']} · "
                f"{row['codigo_anterior'] or 'sin entrada'} → {row['codigo_nuevo'] or 'inactivo'}": row
                for row in history if row["accion"] != "ROLLBACK"
            }
            if options:
                selected = st.selectbox("Cambio a revertir", list(options))
                confirm = st.checkbox(
                    "Confirmo que deseo revertir este cambio vigente",
                    key="neon_rollback_confirm",
                )
                if st.button("↩️ Ejecutar rollback", disabled=not confirm):
                    row = options[selected]
                    if store.rollback_dictionary_change(row["id"], reviewer=_km_usuario()):
                        cargar_diccionario_base.clear()
                        st.success("Rollback aplicado y registrado en el historial.")
                        st.rerun()
                    else:
                        st.error(
                            "No se aplicó: el cambio ya no es el estado vigente o no existe."
                        )
    with tab_conf:
        conflicts = store.conflicts()
        if conflicts:
            st.warning(f"Se detectaron {len(conflicts)} cuentas con códigos históricos distintos.")
            st.dataframe(pd.DataFrame(conflicts), use_container_width=True, hide_index=True)
        else:
            st.success("No hay conflictos históricos registrados en Neon.")
    with tab_stats:
        stats = store.learning_statistics()
        cols = st.columns(5)
        labels = [
            ("Catálogo", "catalog_entries"), ("Diccionario", "dictionary_entries"),
            ("Aprendidas", "human_learned"), ("Validaciones", "validations"),
            ("Correcciones", "corrections"),
        ]
        for col, (label, key) in zip(cols, labels):
            col.metric(label, stats[key])


def _km_pendientes(rm: RuntimeManager, gold_path: Path) -> None:
    """TAB 1 — Promociones pendientes: aprobar/rechazar selección múltiple."""
    st.markdown("#### 📥 Promociones pendientes")
    try:
        pend = rm.get_pending_promotions(gold_path)
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudieron cargar los candidatos: {e}")
        return

    if not pend:
        st.info("No hay candidatos pendientes de promoción en `gold_records`.")
        return

    df = pd.DataFrame([{
        "Cuenta": p["account_name"],
        "Código sugerido": p["candidate_code"],
        "Origen": p["origen"] or "—",
        "Confianza": p["confidence"],
        "Fecha": (p["fecha"] or "")[:19],
        "Estado": p["state"],
        "Clasificación": p["status"],
        "source_record_id": p["source_record_id"],
    } for p in pend])
    df.insert(0, "Seleccionar", False)

    st.caption(
        "Estado actual derivado de `promotion_history`. Solo los candidatos "
        "PENDING se promueven; duplicados y conflictos se omiten automáticamente."
    )

    edited = st.data_editor(
        df,
        hide_index=True,
        disabled=[c for c in df.columns if c not in ("Seleccionar",)],
        use_container_width=True,
        key="km_pend_editor",
        column_config={
            "Seleccionar": st.column_config.CheckboxColumn("Seleccionar", default=False),
            "Confianza": st.column_config.NumberColumn("Confianza", format="%.2f"),
            "source_record_id": None,
        },
    )

    if not isinstance(edited, pd.DataFrame):
        edited = df
    seleccionadas = edited[edited["Seleccionar"] == True] if "Seleccionar" in edited.columns else edited.iloc[0:0]  # noqa: E712
    ids = [int(r["source_record_id"]) for _, r in seleccionadas.iterrows()]

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        aprobar = st.button("✅ Aprobar selección", use_container_width=True)
    with c2:
        rechazar = st.button("❌ Rechazar selección", use_container_width=True)
    with c3:
        st.caption(f"{len(ids)} seleccionadas · usuario: `{_km_usuario()}`")

    if aprobar:
        if not ids:
            st.warning("Selecciona al menos una fila para aprobar.")
        else:
            try:
                res = rm.promote(gold_path, dry_run=False, source_ids=ids, usuario=_km_usuario())
                st.success(
                    f"Promovidos: {res.promoted} · Conflictos omitidos: {res.conflicts} · "
                    f"Duplicados: {res.duplicates} · Reservados: {res.reserved}"
                )
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudo aprobar la selección: {e}")
    if rechazar:
        if not ids:
            st.warning("Selecciona al menos una fila para rechazar.")
        else:
            try:
                n = 0
                for _, r in seleccionadas.iterrows():
                    rm.reject_promotion(
                        source_record_id=int(r["source_record_id"]),
                        account_name=str(r["Cuenta"]),
                        candidate_code=str(r["Código sugerido"]),
                        usuario=_km_usuario(),
                    )
                    n += 1
                st.success(f"Rechazos registrados (REJECT): {n}")
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudieron registrar los rechazos: {e}")


def _km_conflictos(rm: RuntimeManager, gold_path: Path) -> None:
    """TAB 2 — Conflictos runtime vs gold."""
    st.markdown("#### ⚔️ Conflictos (runtime vs gold)")
    try:
        conf = rm.get_conflicts(gold_path)
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudieron cargar los conflictos: {e}")
        return

    if not conf:
        st.info("No hay conflictos entre runtime y gold oficial.")
        return

    st.caption(
        "Misma cuenta normalizada con código distinto en runtime y gold. "
        "Resolver: mantener runtime (no hacer nada) o rollback (prevalece gold). "
        "`gold_standard.db` nunca se modifica."
    )
    df = pd.DataFrame([{
        "Cuenta": c["account_name"],
        "Código runtime": c["codigo_runtime"],
        "Código gold": c["codigo_gold"],
    } for c in conf])
    st.dataframe(df, use_container_width=True, hide_index=True)

    for c in conf:
        with st.expander(
            f"⚔️ {c['account_name']} — runtime {c['codigo_runtime']} vs gold {c['codigo_gold']}"
        ):
            hist = rm.get_history(account_name=c["account_name"], limit=20)
            if hist:
                st.dataframe(pd.DataFrame([{
                    "Fecha": (h["fecha"] or "")[:19],
                    "Usuario": h["usuario"],
                    "Acción": h["accion"],
                    "Estado": h["state"],
                    "Código": h["codigo_nuevo"] or h["codigo_anterior"] or "",
                    "Comentario": h["comentario"],
                } for h in hist]), use_container_width=True, hide_index=True)
            else:
                st.caption("Sin historial para esta cuenta.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔁 Rollback (prevalece gold)", key=f"km_rb_{c['runtime_id']}"):
                    try:
                        ok = rm.rollback(
                            int(c["runtime_id"]), usuario=_km_usuario(),
                            comentario="Conflicto resuelto: prevalece gold",
                        )
                        st.success("Rollback aplicado y registrado (ROLLBACK)." if ok else "No se pudo aplicar el rollback.")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Error en rollback: {e}")
            with c2:
                if st.button("✓ Mantener runtime", key=f"km_keep_{c['runtime_id']}"):
                    st.info("Runtime mantenido (no se modifica nada).")


def _km_runtime(rm: RuntimeManager) -> None:
    """TAB 3 — Cuentas activas del runtime: filtro, buscador y rollback."""
    st.markdown("#### 🗃️ Runtime (`gold_standard_runtime.db`)")
    if not rm.path.exists():
        st.info("El runtime aún no existe. Promueve candidatos desde la pestaña 'Promociones pendientes'.")
        return
    try:
        rows = rm.load_runtime()
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudieron cargar las cuentas del runtime: {e}")
        return
    if not rows:
        st.info("El runtime existe pero no tiene cuentas activas.")
        return

    df = pd.DataFrame([{
        "id": r["id"],
        "Cuenta": r["nombre_cuenta"],
        "Código": r["codigo_estandar"],
        "Normalizado": r["normalized"],
        "Reviewer": r["reviewer"] or "—",
        "Fecha": (r["promoted_at"] or "")[:19],
    } for r in rows])

    q = st.text_input("🔍 Buscar cuenta o código", key="km_runtime_q")
    if q:
        ql = q.lower().strip()
        df = df[df["Cuenta"].str.lower().str.contains(ql)
                | df["Código"].str.lower().str.contains(ql)
                | df["Normalizado"].str.lower().str.contains(ql)]

    prefijos = sorted({str(c).split(".")[0] for c in df["Código"]})
    filtro = st.selectbox("Filtrar por prefijo de código", ["todos"] + prefijos, key="km_runtime_filtro")
    if filtro != "todos":
        df = df[df["Código"].astype(str).str.startswith(filtro)]

    st.caption(f"{len(df)} cuentas activas en runtime.")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("**Rollback / Eliminar**")
    st.caption("Rollback elimina la entrada de runtime y registra el evento ROLLBACK (prevalece gold).")
    options = {f"{r['Cuenta']} ({r['Código']})": int(r["id"]) for _, r in df.iterrows()}
    if options:
        sel_label = st.selectbox("Cuenta", list(options), key="km_runtime_sel")
        confirm = st.checkbox("Confirmo el rollback de esta cuenta", key="km_runtime_confirm")
        if st.button("🗑️ Rollback", use_container_width=True, disabled=not confirm):
            try:
                ok = rm.rollback(options[sel_label], usuario=_km_usuario(), comentario="Rollback desde Knowledge Manager")
                st.success("Rollback aplicado y registrado." if ok else "No se pudo aplicar.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Error en rollback: {e}")


def _km_historial(rm: RuntimeManager) -> None:
    """TAB 4 — Historial de promotion_history (solo lectura)."""
    st.markdown("#### 📜 Historial (`promotion_history`)")
    try:
        hist = rm.get_history(limit=500)
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudo leer el historial: {e}")
        return
    if not hist:
        st.info("Sin eventos registrados en `promotion_history`.")
        return

    df = pd.DataFrame([{
        "Promotion ID": h["promotion_id"][:8],
        "Fecha": (h["fecha"] or "")[:19],
        "Usuario": h["usuario"],
        "Acción": h["accion"],
        "Estado": h["state"],
        "Cuenta": h["account_name"],
        "Código": h["codigo_nuevo"] or h["codigo_anterior"] or "",
        "Comentario": h["comentario"],
    } for h in hist])

    q = st.text_input("🔍 Buscar en historial", key="km_hist_q")
    if q:
        ql = q.lower()
        df = df[df.apply(lambda r: ql in " ".join(str(v) for v in r), axis=1)]

    st.caption("Solo lectura. El historial nunca se borra.")
    st.dataframe(df, use_container_width=True, hide_index=True)


def _km_estadisticas(rm: RuntimeManager, gold_path: Path) -> None:
    """TAB 5 — Estadísticas del runtime y del historial."""
    st.markdown("#### 📊 Estadísticas")
    try:
        s = rm.get_runtime_statistics(gold_path)
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudieron calcular las estadísticas: {e}")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Runtime size", s["runtime_size"])
    c2.metric("Promociones (PROMOTE)", s["promotions"])
    c3.metric("Rechazos (REJECT)", s["rejects"])
    c4.metric("Rollback (ROLLBACK)", s["rollbacks"])
    c5.metric("Cobertura", f"{s['coverage']}%")

    st.caption(
        f"Gold oficial: {s['gold_size']} cuentas · Eventos en historial: "
        f"{s['history_events']} · Runtime: {s['runtime_size']} cuentas activas."
    )


def _km_runtime_analytics(rm: RuntimeManager, gold_path: Path) -> None:
    """TAB 6 — 📊 Runtime Analytics: observabilidad completa (P5.5).

    Toda la información sale de ``RuntimeStatistics`` (fuente única); la UI no
    ejecuta SQL ni abre SQLite. Las métricas de uso provienen del último
    procesamiento (``session_state``) y los eventos/cobertura de RuntimeManager.
    No promueve, no revierte, no puebla: solo observa.
    """
    st.markdown("#### 📊 Runtime Analytics")
    st.caption(
        "Observabilidad del runtime (solo lectura). Métricas de uso del último "
        "procesamiento + eventos/cobertura de `gold_standard_runtime.db`. "
        "El benchmark (`gold_standard.db`) no se modifica."
    )

    snapshot = st.session_state.get("runtime_metrics_last")
    try:
        stats = RuntimeStatistics.capture(
            metrics=snapshot,
            runtime=rm,
            gold_db=str(gold_path),
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudieron calcular las métricas runtime: {e}")
        return

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("💠 Entradas runtime", stats.runtime_size)
    c2.metric("🚀 Promociones", stats.promotion_count)
    c3.metric("🔁 Rollbacks", stats.rollback_count)
    c4.metric("❌ Rejects", stats.reject_count)
    c5.metric("🎯 Runtime exact", stats.runtime_exact_hits)
    c6.metric("🌀 Runtime fuzzy", stats.runtime_fuzzy_hits)

    c7, c8, c9, c10, c11, c12 = st.columns(6)
    c7.metric("🟢 Gold exact", stats.gold_exact_hits)
    c8.metric("🌫️ Gold fuzzy", stats.gold_fuzzy_hits)
    c9.metric("⬇️ Fallbacks", stats.fallback_to_gold)
    c10.metric("Runtime miss", stats.runtime_miss)
    c11.metric("Requests", stats.total_requests)
    c12.metric("Historial", stats.history_events)

    st.markdown("#### Cobertura")
    c13, c14, c15, c16, c17 = st.columns(5)
    c13.metric("📚 Cobertura runtime (uso)", f"{stats.runtime_usage_pct}%")
    c14.metric("🏛️ Cobertura gold (uso)", f"{stats.gold_usage_pct}%")
    c15.metric("🧠 Aprendizaje usado", f"{stats.learning_used_pct}%")
    c16.metric("📐 Catálogo runtime", f"{stats.runtime_catalog_coverage_pct}%")
    c17.metric("⬇️ Fallback", f"{stats.fallback_pct}%")

    st.markdown("#### Impacto por promoción")
    st.caption(
        "¿Qué promociones realmente generan impacto? Promoción cuyo código "
        "estándar fue usado por el runtime (hit exacto/fuzzy) durante el "
        "último procesamiento."
    )
    if not stats.promotion_impact:
        st.info("Sin promociones registradas o sin actividad de uso todavía.")
    else:
        df = pd.DataFrame(stats.promotion_impact)
        df["impacto"] = df["impactful"].map({True: "✅ Impacto", False: "—"})
        st.dataframe(
            df[["account_name", "code", "hits", "impacto", "promotion_id"]],
            use_container_width=True, hide_index=True,
        )

    if stats.promotion_count:
        st.caption(
            f"Promociones con impacto real: **{stats.impactful_promotions}** "
            f"de {len(stats.promotion_impact)} promociones registradas. "
            "Promociones sin hits pendientes de adopción."
        )


def _mostrar_resumen_catalogo(catalogo: dict):
    st.subheader("Catálogo Maestro de Homologación")
    df = pd.DataFrame.from_dict(catalogo, orient='index')
    df = df[['codigo_estandar', 'nombre_estandar', 'categoria', 'tipo_estado']]
    df.columns = ['Código', 'Nombre Estándar', 'Categoría', 'Tipo Estado']
    st.dataframe(df, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# INVOCACIÓN RESTRINGIDA (ESCUDO DE EJECUCIÓN GLOBAL)
# ─────────────────────────────────────────────────────────────────────────────

class TaxFolder:
    """Clase de marcador de posición para evitar que el orquestador falle al importar"""
    pass
    
if __name__ == '__main__':
    main()
