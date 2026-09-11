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
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from datetime import date, datetime
from io import BytesIO
from html import escape
from typing import Any
from uuid import uuid4
from document_scope import page_count, parse_pages, select_pdf, render_page
from report_presentation import (
    complete_catalog, add_report_sheets, apply_depreciation_reclassification,
)

import pandas as pd
import streamlit as st
from rapidfuzz import fuzz, process
from dotenv import load_dotenv

from clasificador_codigo_cuenta import ClasificadorCodigo
from catalog_selection import es_clasificable, opciones_clasificacion
from catalog_aliases import (
    canonical_catalog_code, canonicalize_catalog, canonicalize_dictionary,
)
from gold_standard.builder import GoldBuilder
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
    FormatoCodigo, ResultadoParseo, CertificacionExtraccion, certificar_clasificado_final,
    certificar_extraccion_columnas, detectar_años_y_monedas, ocr_pagina,
    parsear_excel,
)
from parsers.column_interpretation import es_ingreso as es_ingreso_col, es_gasto as es_gasto_col
from parsers.account_type_resolver import (
    is_accumulated_result_name,
    is_contra_asset_name,
    is_equity_account_name,
    is_patrimonial_reserve_name,
)
from extractor_metadata import extraer_metadata, MetadataEmpresa
from account_qualification import qualify_cuentas as _safe_qualify_cuentas, \
    safe_mode_enabled as _safe_mode_enabled
from persistence.neon_store import NeonKnowledgeStore
from persistence import PersistenceSettings, build_persistence
from persistence.contracts.knowledge import ValidationDecision
from persistence.contracts.identity import (
    AuthenticatedActor,
    AuthenticationRequired,
    AuthorizationDenied,
    IdentityRole,
    require_role,
)
from persistence.contracts.promotions import (
    PromotionOutcomeRecord, PromotionPolicyRecord, PromotionPolicyRepository,
)
from persistence.contracts.processes import (
    LocalProcessPersistence, PersistedProcess, ProcessPersistenceError,
    ProcessScope,
)
from persistence.promotion_metadata import build_promotion_policy_record
from reporting_integrity import (
    resultado_compatible, importe_resultado_homologado, conciliar_resultados,
    validar_reclasificacion_depreciacion,
)
from validation.classification_metrics import account_metrics, document_family, method_provenance
from validation.prepost_balance import compare_pre_post
from validation.promotion_policy import (
    DEFAULT_EXPIRATION_DAYS,
)


MESES_SELECCION = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

CERTIFIABLE_CONTENT_VERSION = "certifiable_rows.v1"
AUTH_STAGING_VALUES = frozenset({"", "0", "false", "off", "disabled", "staging"})


def _auth_enforced() -> bool:
    """Indica si el despliegue exige una identidad entregada por un adaptador confiable."""
    return os.getenv("AUTH_ENFORCEMENT", "staging").strip().lower() not in AUTH_STAGING_VALUES


def _authenticated_actor() -> AuthenticatedActor | None:
    """Lee sólo el contrato autenticado; no deriva identidades desde cabeceras o texto UI."""
    actor = st.session_state.get("authenticated_actor")
    return actor if isinstance(actor, AuthenticatedActor) else None


def _normalize_required_role(role: str) -> IdentityRole:
    """Compatibilidad transitoria: ``administrator`` pasa al rol canónico ``admin``."""
    normalized = "admin" if str(role).strip().lower() == "administrator" else str(role).strip().lower()
    if normalized not in {"analyst", "supervisor", "admin"}:
        raise ValueError(f"Rol no soportado: {role}")
    return normalized  # type: ignore[return-value]


def _require_app_role(minimum: str) -> AuthenticatedActor | None:
    """Default deny en modo autenticado; staging permanece explícitamente anónimo."""
    actor = _authenticated_actor()
    if _auth_enforced():
        require_role(actor, _normalize_required_role(minimum))
    return actor


def _actor_audit_fields() -> dict[str, object]:
    actor = _authenticated_actor()
    if _auth_enforced() and actor is None:
        raise AuthenticationRequired("Identidad autenticada obligatoria para registrar auditoría")
    if actor is None:
        return {"Actor": "", "Organización": "", "Roles": []}
    return {
        "Actor": actor.actor_id,
        "Organización": actor.organization_id,
        "Roles": sorted(actor.roles),
    }


def _promotion_source_reference(source_path: str | Path) -> str:
    path = Path(source_path)
    if not path.is_file():
        raise FileNotFoundError(f"Fuente de promoción no encontrada: {path}")
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _promotion_subject_id(preview, source_reference: str) -> str:
    """Identifica de forma estable el conjunto evaluado, sin usar texto libre."""
    payload = preview.to_dict() if hasattr(preview, "to_dict") else dict(preview)
    digest = hashlib.sha256(json.dumps(
        {"preview": payload, "source_reference": source_reference},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=str,
    ).encode("utf-8")).hexdigest()
    return f"gold-runtime-batch:{digest}"


def _persistir_evaluacion_promocion(
    *, preview, actor: AuthenticatedActor | None, evidence_confirmed: bool,
    approved: bool, expiration_days: int,
    repository: PromotionPolicyRepository, source_path: str | Path,
) -> PromotionPolicyRecord:
    """Evalúa y verifica la escritura durable antes de permitir una promoción."""
    evaluation_id = str(uuid4())
    source_reference = _promotion_source_reference(source_path)
    evidence = ({
        "source_document": source_reference,
        "human_decision": f"actor:{actor.actor_id}",
        "classification_reason": "policy:manual_supervisor",
    } if evidence_confirmed and actor is not None else {})
    record = build_promotion_policy_record(
        subject_id=_promotion_subject_id(preview, source_reference),
        actor=actor,
        evidence=evidence,
        conflicts=int(getattr(preview, "conflicts", 0)),
        approved=bool(approved),
        reversal_reference=f"promotion-policy:{evaluation_id}",
        expires_in_days=int(expiration_days),
        evaluation_id=evaluation_id,
    )
    saved = repository.save_promotion_policy_metadata(record)
    durable = repository.get_promotion_policy_metadata(
        record.evaluation_id, organization_id=record.organization_id,
    )
    if saved != record or durable != record:
        raise RuntimeError(
            "La evaluación de promoción no pudo verificarse en persistencia durable"
        )
    return record


class PromotionStateInconsistent(RuntimeError):
    """La aplicación Gold y su resultado durable no pueden reconciliarse."""


def _promotion_error_text(error: BaseException | str) -> str:
    """Normaliza el diagnóstico sin incluir trazas ni texto ilimitado."""
    if isinstance(error, BaseException):
        value = f"{type(error).__name__}: {str(error)}"
    else:
        value = str(error)
    return " ".join(value.split())[:500] or "error de promoción no especificado"


def _promotion_ids_from_result(result) -> tuple[str, ...]:
    """Obtiene identificadores explícitos sin inferirlos desde montos o contadores."""
    raw_ids = getattr(result, "promotion_ids", ())
    if not raw_ids:
        raw_id = getattr(result, "promotion_id", "")
        raw_ids = (raw_id,) if raw_id else ()
    return tuple(dict.fromkeys(
        str(value).strip() for value in raw_ids if str(value).strip()
    ))


def _runtime_promotion_ids(
    manager: RuntimeManager, policy: PromotionPolicyRecord,
) -> tuple[str, ...]:
    """Vincula el batch con los eventos PROMOTE escritos por RuntimeManager."""
    return tuple(dict.fromkeys(
        str(event.get("promotion_id") or "").strip()
        for event in manager.get_history(limit=10000)
        if event.get("accion") == "PROMOTE"
        and event.get("origen") == policy.reversal_reference
        and str(event.get("promotion_id") or "").strip()
    ))


def _persistir_outcome_promocion(
    *, repository: PromotionPolicyRepository, policy: PromotionPolicyRecord,
    status: str, promotion_ids: tuple[str, ...] = (), error: str | None = None,
) -> PromotionOutcomeRecord:
    """Anexa y relee el outcome terminal; nunca modifica la evaluación original."""
    outcome = PromotionOutcomeRecord(
        evaluation_id=policy.evaluation_id,
        subject_id=policy.subject_id,
        organization_id=policy.organization_id,
        actor_id=policy.supervisor_actor_id,
        status=status,  # type: ignore[arg-type]
        occurred_at=datetime.now().astimezone(),
        promotion_ids=tuple(promotion_ids),
        error=error,
    )
    saved = repository.save_promotion_outcome(outcome)
    durable = repository.get_promotion_outcome(
        policy.evaluation_id, organization_id=policy.organization_id,
    )
    if saved != outcome or durable != outcome:
        raise PromotionStateInconsistent(
            "El resultado de la promoción no pudo verificarse en persistencia "
            "durable. El subject queda bloqueado hasta reconciliación."
        )
    return outcome


def _assert_promotion_subject_reconciled(
    *, repository: PromotionPolicyRepository, subject_id: str,
    organization_id: str,
) -> None:
    unresolved = repository.list_unresolved_promotion_evaluations(
        subject_id, organization_id=organization_id,
    )
    if unresolved:
        identifiers = ", ".join(record.evaluation_id for record in unresolved[:3])
        raise PromotionStateInconsistent(
            "Existe una promoción anterior sin outcome terminal durable para este "
            f"subject ({identifiers}). Debe reconciliarse antes de reintentar."
        )


def _aplicar_promocion_durable(
    *, preview, actor: AuthenticatedActor | None, evidence_confirmed: bool,
    approved: bool, expiration_days: int,
    repository: PromotionPolicyRepository | None, apply_callback,
    promotion_ids_resolver=None,
    source_path: str | Path | None = None,
):
    """Ejecuta la saga evaluación/aplicación/outcome con bloqueo fail-closed."""
    if repository is None:
        raise RuntimeError(
            "La persistencia durable de promociones no está configurada"
        )
    if actor is None:
        raise AuthenticationRequired(
            "Se requiere un supervisor autenticado para aplicar una promoción"
        )
    resolved_source = source_path or _gold_benchmark_path()
    source_reference = _promotion_source_reference(resolved_source)
    subject_id = _promotion_subject_id(preview, source_reference)
    _assert_promotion_subject_reconciled(
        repository=repository, subject_id=subject_id,
        organization_id=actor.organization_id,
    )
    record = _persistir_evaluacion_promocion(
        preview=preview, actor=actor,
        evidence_confirmed=evidence_confirmed, approved=approved,
        expiration_days=expiration_days, repository=repository,
        source_path=resolved_source,
    )
    if not record.allowed:
        return record, None
    try:
        result = apply_callback(record)
    except Exception as apply_error:
        try:
            _persistir_outcome_promocion(
                repository=repository, policy=record, status="FAILED",
                error=_promotion_error_text(apply_error),
            )
        except Exception as outcome_error:
            raise PromotionStateInconsistent(
                "La aplicación falló y tampoco fue posible persistir/releer su "
                "outcome FAILED. El subject queda bloqueado hasta reconciliación."
            ) from outcome_error
        raise

    resolver = promotion_ids_resolver or (
        lambda applied_result, _policy: _promotion_ids_from_result(applied_result)
    )
    try:
        promotion_ids = tuple(resolver(result, record))
        if not promotion_ids:
            raise ValueError("la aplicación no expuso promotion_id durable")
    except Exception as resolution_error:
        try:
            _persistir_outcome_promocion(
                repository=repository, policy=record, status="INCONSISTENT",
                error=_promotion_error_text(
                    "No fue posible vincular la aplicación con promotion_id: "
                    f"{type(resolution_error).__name__}: {str(resolution_error)}"
                ),
            )
        finally:
            raise PromotionStateInconsistent(
                "La promoción pudo aplicarse, pero no se pudo vincular con un "
                "promotion_id. El subject queda bloqueado hasta reconciliación."
            ) from resolution_error

    try:
        _persistir_outcome_promocion(
            repository=repository, policy=record, status="APPLIED",
            promotion_ids=promotion_ids,
        )
    except Exception as outcome_error:
        raise PromotionStateInconsistent(
            "La promoción pudo aplicarse, pero su outcome APPLIED no quedó "
            "verificado. El subject queda bloqueado hasta reconciliación."
        ) from outcome_error
    return record, result


def _valor_digest_certificable(valor):
    if isinstance(valor, (list, tuple)):
        return [_valor_digest_certificable(item) for item in valor]
    if isinstance(valor, dict):
        return {str(key): _valor_digest_certificable(item)
                for key, item in sorted(valor.items(), key=lambda pair: str(pair[0]))}
    if valor is None:
        return None
    if hasattr(valor, "item"):
        valor = valor.item()
    try:
        return None if bool(pd.isna(valor)) else valor
    except (TypeError, ValueError):
        return str(valor)


def _digest_filas_certificables(df: pd.DataFrame, *, clasificacion: bool = False) -> str:
    campos = ["linea", "codigo_original", "nombre_original", "monto",
              "origen_columna", "es_total", "columnas_derivadas", "jerarquia_contable"]
    for p_col in ("pagina", "page", "ubicacion"):
        if p_col in df.columns and p_col not in campos:
            campos.append(p_col)
    for r_col in ("respaldo_documental", "decision_exclusion", "excluida", "origen"):
        if r_col in df.columns and r_col not in campos:
            campos.append(r_col)
    campos += sorted(c for c in df.columns if str(c).startswith("monto_periodo_"))
    campos += [c for c in RAW_MONETARY_COLUMNS if c in df.columns]
    if clasificacion:
        if "codigo_clasificado" in df.columns and "codigo_clasificado" not in campos:
            campos.append("codigo_clasificado")
        if "requiere_revision" in df.columns and "requiere_revision" not in campos:
            campos.append("requiere_revision")
    filas = []
    for _, row in df.iterrows():
        item = {}
        for campo in campos:
            item[campo] = _valor_digest_certificable(row.get(campo))
        filas.append(item)
    filas.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, default=str))
    payload = {"version": CERTIFIABLE_CONTENT_VERSION, "rows": filas}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str).encode("utf-8")).hexdigest()



def _safe_session_get(key: str, default=None):
    """Obtiene un valor de st.session_state de forma segura, incluso si está mockeado como SimpleNamespace."""
    state = getattr(st, "session_state", None)
    if state is None:
        return default
    if hasattr(state, "get"):
        val = state.get(key, default)
        return val if val is not None else default
    return getattr(state, key, default)


def _detectar_bloquear_colision_homonimo(
    filename: str,
    file_digest: str,
    organization_id: str | None = None,
) -> None:
    """Detecta y bloquea colisiones de archivos homónimos con distinto contenido
    dentro de la misma organización antes de sobrescribir registros consumidores
    (resultados, snapshots, certificaciones y file_metadata)."""
    if not filename or not file_digest:
        return
    existing_meta = (_safe_session_get("file_metadata") or {}).get(filename)
    if existing_meta:
        prev_digest = existing_meta.get("file_digest")
        prev_org = existing_meta.get("organization_id")
        if prev_digest and prev_digest != file_digest:
            if not organization_id or not prev_org or prev_org == organization_id:
                msg = (
                    f"Colisión de archivo homónimo detectada para '{filename}': "
                    f"existe un documento previo con distinta huella ({prev_digest[:8]}... vs {file_digest[:8]}...) "
                    f"en la organización '{prev_org or organization_id}'. "
                    f"Operación bloqueada para evitar sobrescritura de registros y evidencia."
                )
                if hasattr(st, "error"):
                    st.error(msg)
                raise ValueError(msg)

    existing_snap = (_safe_session_get("classified_source_snapshots") or {}).get(filename)
    if existing_snap and existing_snap.get("file_digest"):
        prev_digest = existing_snap.get("file_digest")
        if prev_digest != file_digest:
            msg = (
                f"Colisión de snapshot homónimo detectada para '{filename}': "
                f"la huella del documento actual ({file_digest[:8]}...) difiere del snapshot registrado ({prev_digest[:8]}...). "
                f"Operación bloqueada para evitar sobrescritura de evidencia."
            )
            if hasattr(st, "error"):
                st.error(msg)
            raise ValueError(msg)


def _obtener_huella_archivo_real(
    filename: str,
    *,
    expected_digest: str | None = None,
    organization_id: str | None = None,
    source_path: str | Path | None = None,
    actor: AuthenticatedActor | None = None,
) -> tuple[str | None, str]:
    """Lee exclusivamente una fuente registrada, autorizada y de versión exacta.

    El nombre selecciona un registro de la sesión, nunca una ruta implícita.
    Toda salida disponible acredita bytes leídos, organización y SHA-256.
    """
    if not filename or not str(filename).strip():
        return None, "no_disponible"
    fn = str(filename).strip()
    effective_actor = actor or _authenticated_actor()
    if not isinstance(effective_actor, AuthenticatedActor):
        return None, "no_autorizada"
    require_role(effective_actor, "analyst")
    org = effective_actor.organization_id
    if organization_id is not None and organization_id != org:
        return None, "no_autorizada"

    # Recuperar la ejecución mediante el servicio que comprueba organización.
    cached = (_safe_session_get("persisted_processes") or {}).get(fn)
    service = None
    document = None
    if cached is not None:
        service = _streamlit_process_service(effective_actor)
        if service is None:
            return None, "no_disponible"
        recovered = service.get(cached.execution.execution_id, actor=effective_actor)
        if recovered is None:
            return None, "no_disponible"
        document = recovered.document
        if document.document_id != cached.document.document_id:
            return None, "rechazada"

    meta = (_safe_session_get("file_metadata") or {}).get(fn) or {}
    doc_org = document.metadata.get("organization_id") if document else meta.get("organization_id")
    version = document.sha256 if document else meta.get("file_digest")
    if not doc_org or doc_org != org:
        return None, "no_autorizada"
    if not isinstance(version, str) or not re.fullmatch(r"[0-9a-f]{64}", version):
        return None, "no_disponible"
    if expected_digest is not None and expected_digest != version:
        return None, "rechazada"
    if document and meta:
        if meta.get("organization_id", org) != org or meta.get("file_digest", version) != version:
            return None, "rechazada"

    def verify(content):
        if not isinstance(content, (bytes, bytearray)):
            return None, "rechazada"
        actual = hashlib.sha256(content).hexdigest()
        return (actual, "disponible") if actual == version else (None, "rechazada")

    # La carga activa prevalece: una sustitución no cae al documento histórico.
    uploads = []
    for key in ("archivos", "uploaded_files", "document_scope_preview_file"):
        value = _safe_session_get(key)
        values = value if isinstance(value, (list, tuple)) else [value]
        uploads.extend(obj for obj in values if getattr(obj, "name", None) == fn
                       and hasattr(obj, "getvalue"))
    if uploads:
        try:
            contents = [obj.getvalue() for obj in uploads]
            hashes = {hashlib.sha256(content).hexdigest() for content in contents}
        except (OSError, ValueError, TypeError):
            return None, "no_disponible"
        if len(hashes) != 1:
            if expected_digest is not None:
                matched = [content for content in contents
                           if hashlib.sha256(content).hexdigest() == version]
                if matched:
                    return verify(matched[0])
            return None, "ambiguo"
        return verify(contents[0])

    if document is not None:
        try:
            return verify(service.documents.read(document.document_id))
        except (FileNotFoundError, KeyError, OSError):
            return None, "no_disponible"
        except ValueError:
            return None, "rechazada"

    raw = (_safe_session_get("raw_file_bytes") or {}).get((fn, org, version))
    if raw is not None:
        return verify(raw)

    registered_path = meta.get("source_path")
    if source_path is not None:
        if not registered_path or Path(source_path).resolve() != Path(registered_path).resolve():
            return None, "rechazada"
    if not registered_path:
        return None, "no_disponible"
    try:
        return verify(Path(registered_path).read_bytes())
    except (OSError, ValueError):
        return None, "no_disponible"


def _vincular_certificacion_contenido(
    certificacion,
    df: pd.DataFrame,
    *,
    filename: str = "",
    file_digest: str | None = None,
    alcance: dict[str, Any] | None = None,
    filas_evaluadas: int | None = None,
    incorporaciones: list[dict[str, Any]] | None = None,
    exclusiones: list[dict[str, Any]] | None = None,
):
    if certificacion is not None:
        certificacion.contenido_certificado_version = CERTIFIABLE_CONTENT_VERSION
        certificacion.contenido_certificado_digest = _digest_filas_certificables(
            df, clasificacion=getattr(certificacion, "metodo", "") == "classified_final_detail",
        )
        certificacion.contenido_certificado_fecha = datetime.now().astimezone().isoformat()
        resolved_filename = filename or str(df.attrs.get("filename", ""))
        resolved_digest = file_digest or str(df.attrs.get("file_digest", ""))
        source_path = getattr(df, "attrs", {}).get("source_path") or (
            st.session_state.get("file_metadata", {}).get(resolved_filename, {}).get("source_path")
        ) or (
            st.session_state.get("file_sources", {}).get(resolved_filename)
        )
        actor = _authenticated_actor()
        org_id = (
            getattr(df, "attrs", {}).get("organization_id")
            or st.session_state.get("file_metadata", {}).get(resolved_filename, {}).get("organization_id")
            or (actor.organization_id if actor else None)
        )

        if not resolved_digest and resolved_filename:
            try:
                real_dig, _ = _obtener_huella_archivo_real(
                    resolved_filename,
                    expected_digest=None,
                    organization_id=org_id,
                    source_path=source_path,
                    actor=actor,
                )
                if real_dig:
                    resolved_digest = real_dig
            except AuthorizationDenied:
                pass

        doc_identity = {
            "filename": resolved_filename,
            "file_digest": resolved_digest,
        }
        if source_path:
            doc_identity["source_path"] = str(source_path)
            st.session_state.setdefault("file_sources", {})[resolved_filename] = str(source_path)

        if org_id:
            doc_identity["organization_id"] = org_id

        binding = {
            "version": certificacion.contenido_certificado_version,
            "digest": certificacion.contenido_certificado_digest,
            "certified_at": certificacion.contenido_certificado_fecha,
            "document_identity": doc_identity,
            "scope": alcance or {},
            "evaluated_rows_count": filas_evaluadas if filas_evaluadas is not None else len(df),
            "incorporaciones": list(incorporaciones) if incorporaciones is not None else [],
            "exclusiones": list(exclusiones) if exclusiones is not None else [],
        }
        df.attrs["certification_binding"] = binding
        certificacion.certification_binding = binding
    return certificacion


def _restaurar_vinculo_certificacion(certificacion, df: pd.DataFrame, *, al_restaurar: bool = False):
    """Restaura el vínculo primitivo conservado por la serialización de DataFrame."""
    binding = dict(df.attrs.get("certification_binding") or {})
    if not binding:
        return certificacion

    doc_id = binding.get("document_identity", {})
    filename = doc_id.get("filename") or str(df.attrs.get("filename", ""))
    expected_file_digest = doc_id.get("file_digest")
    organization_id = (
        doc_id.get("organization_id")
        or st.session_state.get("file_metadata", {}).get(filename, {}).get("organization_id")
    )
    source_path = (
        doc_id.get("source_path")
        or getattr(df, "attrs", {}).get("source_path")
        or st.session_state.get("file_metadata", {}).get(filename, {}).get("source_path")
        or st.session_state.get("file_sources", {}).get(filename)
    )

    # 1. Comprobar que el contenido actual del DataFrame coincida con el digest sellado
    current_content_digest = _digest_filas_certificables(
        df, clasificacion=getattr(certificacion, "metodo", "") == "classified_final_detail" if certificacion else False,
    )
    if binding.get("digest") != current_content_digest:
        # Alteración de contenido -> invalidar vínculo
        if hasattr(df, "attrs"):
            df.attrs.pop("certification_binding", None)
        if certificacion is not None:
            certificacion.certification_binding = None
            certificacion.contenido_certificado_digest = None
        return certificacion

    # 2. Comprobar huella del archivo real exclusivamente desde fuente vinculada
    msg_ausente = "El archivo original no está disponible para verificar su huella documental; certificación pendiente."
    if filename:
        try:
            real_digest, estado_archivo = _obtener_huella_archivo_real(
                filename,
                expected_digest=expected_file_digest,
                organization_id=organization_id,
                source_path=source_path,
                actor=_authenticated_actor(),
            )
        except AuthorizationDenied:
            real_digest, estado_archivo = None, "denegado"

        if estado_archivo == "disponible":
            if expected_file_digest and real_digest != expected_file_digest:
                # El archivo real en disco/sesión tiene una huella distinta (documento sustituido) -> invalidar
                if hasattr(df, "attrs"):
                    df.attrs.pop("certification_binding", None)
                if certificacion is not None:
                    certificacion.certification_binding = None
                    certificacion.contenido_certificado_digest = None
                    certificacion.estado = "fallida"
                    certificacion.columnas_finales_validadas = False
                    certificacion.razones = [f"El archivo real '{filename}' tiene una huella distinta a la certificada; evidencia rechazada."]
                return certificacion

            # Huella coincide: limpiar marca de pendiente de archivo fuente
            binding.pop("estado_verificacion", None)
            df.attrs["certification_binding"] = binding

            if certificacion is not None:
                if hasattr(certificacion, "razones") and certificacion.razones:
                    certificacion.razones = [r for r in certificacion.razones if r != msg_ausente]

                # Preservar estado acreditado y razones previas:
                # - Una certificación fallida conserva su estado 'fallida' y sus razones.
                # - Una certificación parcial conserva su estado 'parcial'.
                # - Aportar nuevamente el archivo NO rehabilita por sí solo la emisión:
                #   columnas_finales_validadas permanece False si no está certificada,
                #   y al restaurar exige validación explícita para rehabilitar la emisión.
                if certificacion.estado == "fallida":
                    certificacion.columnas_finales_validadas = False
                elif certificacion.estado == "parcial":
                    certificacion.columnas_finales_validadas = False
                elif al_restaurar:
                    certificacion.columnas_finales_validadas = False

        elif estado_archivo in ("rechazada", "rechazado", "alterado", "denegado", "no_autorizada", "ambiguo"):
            # Evidencia rechazada, alterada o acceso no autorizado: invalidar vínculo y marcar fallida
            if hasattr(df, "attrs"):
                df.attrs.pop("certification_binding", None)
            if certificacion is not None:
                certificacion.certification_binding = None
                certificacion.contenido_certificado_digest = None
                certificacion.estado = "fallida"
                certificacion.columnas_finales_validadas = False
                motivo = "evidencia rechazada"
                if estado_archivo == "denegado":
                    motivo = "acceso denegado por organización no autorizada"
                elif estado_archivo in ("rechazada", "rechazado"):
                    motivo = "fuente no registrada o huella rechazada"
                elif estado_archivo == "alterado":
                    motivo = "el archivo fue alterado físicamente"
                razon = f"Validación documental fallida para '{filename}': {motivo}."
                certificacion.razones = list(certificacion.razones or [])
                if razon not in certificacion.razones:
                    certificacion.razones.append(razon)
            return certificacion

        else:
            # Archivo no disponible: conservar evidencia como pendiente de verificación, sin habilitar certificación
            binding["estado_verificacion"] = "pendiente_archivo_fuente"
            df.attrs["certification_binding"] = binding
            if certificacion is not None:
                certificacion.contenido_certificado_version = binding.get("version")
                certificacion.contenido_certificado_digest = binding.get("digest")
                certificacion.contenido_certificado_fecha = binding.get("certified_at")
                certificacion.certification_binding = binding

                # Una certificación fallida conserva su estado 'fallida' y sus razones.
                # La ausencia de fuente se registra como condición adicional.
                # Si no era fallida, pasa a 'parcial'.
                if certificacion.estado != "fallida":
                    certificacion.estado = "parcial"
                certificacion.columnas_finales_validadas = False
                if hasattr(certificacion, "razones"):
                    if msg_ausente not in certificacion.razones:
                        certificacion.razones.append(msg_ausente)
            return certificacion

    # Restaurar atributos sellados en la certificación
    if certificacion is not None:
        certificacion.contenido_certificado_version = binding.get("version")
        certificacion.contenido_certificado_digest = binding.get("digest")
        certificacion.contenido_certificado_fecha = binding.get("certified_at")
        certificacion.certification_binding = binding

    return certificacion


def _certificacion_coincide_contenido(certificacion, df: pd.DataFrame) -> bool:
    _restaurar_vinculo_certificacion(certificacion, df)
    if certificacion is None:
        return False
    if getattr(certificacion, "contenido_certificado_version", None) != CERTIFIABLE_CONTENT_VERSION:
        return False
    current_digest = _digest_filas_certificables(
        df, clasificacion=getattr(certificacion, "metodo", "") == "classified_final_detail",
    )
    if getattr(certificacion, "contenido_certificado_digest", None) != current_digest:
        return False
    binding = df.attrs.get("certification_binding") or {}
    if not binding or binding.get("digest") != current_digest:
        return False
    # Si la verificación de archivo está pendiente, no habilitar certificación (Condición 2)
    if binding.get("estado_verificacion") == "pendiente_archivo_fuente":
        return False
    if getattr(certificacion, "estado", "") != "certificada" and not getattr(certificacion, "columnas_finales_validadas", False):
        return False
    # Validar coincidencia de identidad si está registrada en attrs
    if df.attrs.get("filename") and binding.get("document_identity", {}).get("filename"):
        if df.attrs.get("filename") != binding.get("document_identity", {}).get("filename"):
            return False
    if df.attrs.get("file_digest") and binding.get("document_identity", {}).get("file_digest"):
        if df.attrs.get("file_digest") != binding.get("document_identity", {}).get("file_digest"):
            return False
    return True


def _alcance_snapshot_clasificado(filename):
    scope_confirmed = getattr(st.session_state, "document_scope_confirmed", None)
    if scope_confirmed is None and hasattr(st.session_state, "get"):
        scope_confirmed = st.session_state.get("document_scope_confirmed")
    doc_pages = getattr(st.session_state, "document_pages", None)
    if doc_pages is None and hasattr(st.session_state, "get"):
        doc_pages = st.session_state.get("document_pages")
    return (
        dict(scope_confirmed or ()).get(filename),
        tuple(dict(doc_pages or ()).get(filename) or ()),
        tuple(_periodos_seleccionados()),
    )


def _es_certificacion_ocho_columnas(cert: Any) -> bool:
    """Identifica si una certificación corresponde a un método de ocho columnas (PDF o Excel)."""
    if not cert:
        return False
    metodo = str(getattr(cert, "metodo", "") or "").lower()
    if any(k in metodo for k in ("8_columns", "8_amounts", "10_columns", "columnas", "ocr_coordinates", "coordinates")):
        return True
    totales_impresos = getattr(cert, "totales_impresos", {}) or {}
    if any(k in totales_impresos for k in ("activo", "pasivo", "perdida", "ganancia")):
        return True
    totales_calculados = getattr(cert, "totales_calculados", {}) or {}
    if any(k in totales_calculados for k in ("activo", "pasivo", "perdida", "ganancia")):
        return True
    return False


def _guardar_snapshot_clasificado(filename, resultado):
    certification = getattr(resultado, "certificacion_extraccion", None)
    if certification is None:
        return
    metodo = getattr(certification, "metodo", "") or ""
    f_digest = getattr(resultado, "file_digest", None) or (
        (_safe_session_get("file_metadata") or {}).get(filename, {}).get("file_digest")
    )
    if f_digest:
        _detectar_bloquear_colision_homonimo(filename, f_digest)
    if metodo == "classified_totals":
        source_method = next((
            str(item.get("metodo") or "")
            for item in (getattr(certification, "observaciones_auxiliares", None) or [])
            if item.get("tipo") == "metodo_extraccion_fuente"
        ), None)
        st.session_state.setdefault("classified_source_snapshots", {})[filename] = {
            "file_digest": f_digest,
            "scope": _alcance_snapshot_clasificado(filename),
            "accounts": deepcopy(resultado.cuentas),
            "periods": list(getattr(resultado, "periodos_detectados", []) or []),
            "currencies": list(getattr(resultado, "monedas_detectadas", []) or []),
            "metodo": "classified_totals",
            "metodo_extraccion_fuente": source_method,
        }
    elif _es_certificacion_ocho_columnas(certification):
        st.session_state.setdefault("classified_source_snapshots", {})[filename] = {
            "file_digest": f_digest,
            "scope": _alcance_snapshot_clasificado(filename),
            "accounts": deepcopy(resultado.cuentas),
            "periods": list(getattr(resultado, "periodos_detectados", []) or []),
            "currencies": list(getattr(resultado, "monedas_detectadas", []) or []),
            "metodo": metodo or "excel_8_columns",
        }


def _recertificar_balance_clasificado(filename, df, certification, *, force=False, catalogo=None):
    """Usa fuente completa; una tabla filtrada no puede acreditar cobertura."""
    if certification is None or getattr(certification, "metodo", "") not in {
        "classified_totals", "classified_final_detail",
    }:
        return certification
    if certification.metodo == "classified_final_detail" and not force:
        return certification
    snapshot = st.session_state.get("classified_source_snapshots", {}).get(filename)

    def blocked(reason):
        return CertificacionExtraccion(
            estado="parcial", metodo="classified_final_detail", razones=[reason],
        )

    if not snapshot or not snapshot["scope"][0] or snapshot["scope"] != _alcance_snapshot_clasificado(filename):
        return blocked("Falta el documento completo del alcance actual; vuelva a procesar las páginas seleccionadas.")
    if "linea" not in df or df["linea"].duplicated().any():
        return blocked("Las filas editadas no tienen una identidad única.")
    rows = {row["linea"]: row for row in df.to_dict("records")}
    accounts = deepcopy(snapshot["accounts"])
    if set(rows) - {c.linea for c in accounts}:
        return blocked("Hay cuentas sin vínculo con el documento completo; revise su origen antes de certificar.")
    classifications = []
    for account in accounts:
        if _periodos_seleccionados()[0] in account.montos_periodos:
            account.monto = account.montos_periodos[_periodos_seleccionados()[0]]
        row = rows.get(account.linea)
        if row is None:
            if not account.es_total and account.monto is not None:
                return blocked(f"Falta la cuenta fuente de la fila {account.linea}; no puede certificarse una tabla filtrada.")
            continue
        if bool(row.get("es_total")) != account.es_total:
            return blocked(f"La fila {account.linea} cambió de detalle a control o viceversa; requiere revisar la extracción.")
        try:
            account.monto = float(row["monto"])
            account.nombre = str(row["nombre_original"])
            account.origen_columna = OrigenColumna(row["origen_columna"])
            for year in snapshot["periods"]:
                column = f"monto_periodo_{year}"
                if column in row:
                    account.montos_periodos[str(year)] = float(row[column])
            if account.monto != account.montos_periodos.get(_periodos_seleccionados()[0]):
                return blocked(f"La fila {account.linea} tiene importe principal distinto del período seleccionado.")
        except (KeyError, ValueError, TypeError):
            return blocked(f"La fila {account.linea} no tiene importes u origen válidos.")
        if not account.es_total:
            classifications.append({
                "line": account.linea, "name": account.nombre, "amount": account.monto,
                "code": row.get("codigo_clasificado"),
                "review": row.get("requiere_revision", True),
            })
    result = certificar_clasificado_final(
        accounts, classifications, snapshot["periods"], snapshot["currencies"],
        codigos_validos=set(catalogo or ()), periodo_actual=_periodos_seleccionados()[0],
        metodo_extraccion_fuente=snapshot.get("metodo_extraccion_fuente"),
    )
    if result.estado == "certificada":
        f_digest = df.attrs.get("file_digest") or st.session_state.get("file_metadata", {}).get(filename, {}).get("file_digest")
        if not f_digest:
            actor = _authenticated_actor()
            org_id = (
                getattr(df, "attrs", {}).get("organization_id")
                or st.session_state.get("file_metadata", {}).get(filename, {}).get("organization_id")
                or (actor.organization_id if actor else None)
            )
            source_path = (
                getattr(df, "attrs", {}).get("source_path")
                or st.session_state.get("file_metadata", {}).get(filename, {}).get("source_path")
                or st.session_state.get("file_sources", {}).get(filename)
            )
            try:
                f_digest, _ = _obtener_huella_archivo_real(
                    filename,
                    expected_digest=None,
                    organization_id=org_id,
                    source_path=source_path,
                    actor=actor,
                )
            except AuthorizationDenied:
                f_digest = None
        _vincular_certificacion_contenido(
            result, df,
            filename=filename,
            file_digest=f_digest,
            alcance={
                "pages": list(snapshot["scope"][1]) if snapshot and len(snapshot.get("scope", ())) > 1 else [],
                "periods": list(snapshot.get("periods", []) or []),
            },
            filas_evaluadas=len(accounts),
            incorporaciones=[],
            exclusiones=[],
        )
    else:
        if hasattr(df, "attrs"):
            df.attrs.pop("certification_binding", None)
        setattr(result, "certification_binding", None)
        result.contenido_certificado_digest = None
        result.contenido_certificado_version = None
    return result


def _clave_compuesta_cuenta(item: Any) -> tuple[Any, Any]:
    """Genera la tupla (pagina, linea) para identificar unívocamente una cuenta."""
    if isinstance(item, dict):
        p = item.get("pagina")
        if p is None:
            p = item.get("page")
        l = item.get("linea")
    else:
        p = getattr(item, "pagina", None)
        if p is None:
            p = getattr(item, "page", None)
        l = getattr(item, "linea", None)
    if p is not None and pd.notna(p):
        try:
            p_val = int(p)
        except (ValueError, TypeError):
            p_val = str(p).strip()
    else:
        p_val = None
    return (p_val, l)


def _es_cuenta_relevante(cuenta: CuentaRaw) -> bool:
    """Una cuenta es relevante si no es total y tiene movimientos, saldos o clasificación."""
    if getattr(cuenta, "es_total", False):
        return False
    if cuenta.monto is not None and abs(float(cuenta.monto)) > 1e-6:
        return True
    if cuenta.montos_columnas:
        if any(abs(float(v or 0)) > 1e-6 for v in cuenta.montos_columnas.values()):
            return True
    if cuenta.codigo and str(cuenta.codigo).strip():
        return True
    return False


def _es_cuenta_relevante_row(row: dict[str, Any]) -> bool:
    """Evalúa si una fila del DataFrame representa una cuenta contable relevante."""
    if bool(row.get("es_total")):
        return False
    m = row.get("monto")
    if pd.notna(m) and abs(float(m or 0)) > 1e-6:
        return True
    for col in RAW_MONETARY_COLUMNS:
        v = row.get(col)
        if pd.notna(v) and abs(float(v or 0)) > 1e-6:
            return True
    if row.get("codigo_original") and str(row.get("codigo_original")).strip():
        return True
    return False


def _validar_respaldo_incorporacion(
    row: dict[str, Any],
    filename: str,
    file_digest: str | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Valida el registro estructurado de respaldo documental para incorporar una cuenta omitida."""
    respaldo = row.get("respaldo_documental")
    if not isinstance(respaldo, dict):
        return False, "carece de registro estructurado de respaldo documental ('respaldo_documental')", None

    doc_id = str(respaldo.get("archivo") or respaldo.get("file_name") or respaldo.get("file_digest") or "").strip()
    if not doc_id:
        return False, "el respaldo documental no especifica el identificador o huella del archivo", None
    if doc_id != filename and (not file_digest or doc_id != file_digest):
        return False, f"el respaldo documental vincula al archivo '{doc_id}', distinto de '{filename}'", None

    # Comprobar huella del archivo real (Condición 2: documento sustituido por otro con igual nombre)
    actor = _authenticated_actor()
    file_meta = (st.session_state.get("file_metadata") or {}).get(filename, {})
    org_id = file_meta.get("organization_id") or (actor.organization_id if actor else None)
    source_path = file_meta.get("source_path") or (st.session_state.get("file_sources") or {}).get(filename)
    resp_digest = respaldo.get("file_digest") or (doc_id if doc_id != filename else None)
    if not isinstance(resp_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", resp_digest):
        return False, "el respaldo no registra una huella SHA-256 válida de su versión documental", None
    try:
        real_digest, estado_fuente = _obtener_huella_archivo_real(
            filename,
            expected_digest=resp_digest or file_digest,
            organization_id=org_id,
            source_path=source_path,
            actor=actor,
        )
    except AuthorizationDenied:
        return False, f"acceso denegado: actor no autorizado para verificar el archivo '{filename}'", None

    if estado_fuente == "rechazada":
        return False, f"la fuente documental de '{filename}' fue rechazada o alterada", None
    if estado_fuente == "ambiguo":
        return False, f"referencia ambigua: existen múltiples archivos con el nombre '{filename}'", None
    if estado_fuente != "disponible" or not real_digest:
        return False, "no se pudo verificar la fuente documental autorizada y su huella", None
    if file_digest is not None and file_digest != real_digest:
        return False, "la huella proporcionada no coincide con la fuente documental", None

    current_digest = file_digest or real_digest
    if current_digest and resp_digest and resp_digest != current_digest:
        return False, f"el respaldo documental corresponde a una versión anterior o distinta del archivo (huella '{resp_digest}' != '{current_digest}')", None

    pagina = respaldo.get("pagina")
    ubicacion = respaldo.get("ubicacion")
    if (pagina is None or pd.isna(pagina) or str(pagina).strip() == "") and not str(ubicacion or "").strip():
        return False, "el respaldo documental no especifica página ni ubicación documental", None
    if pagina is not None and pd.notna(pagina) and str(pagina).strip() != "":
        try:
            p_int = int(pagina)
            if p_int < 1:
                return False, f"página inválida en respaldo documental: {pagina}", None
        except (ValueError, TypeError):
            return False, f"página inválida en respaldo documental: {pagina}", None

    actor = str(respaldo.get("actor") or respaldo.get("actor_id") or respaldo.get("usuario_confirmacion") or "").strip()
    if not actor:
        return False, "el respaldo documental no registra la trazabilidad del actor que confirmó la incorporación", None

    # Verificación de actor y contexto de auditoría (Condición 1)
    actor_obj = respaldo.get("actor_object") or _authenticated_actor()
    if actor_obj is not None:
        if not isinstance(actor_obj, AuthenticatedActor):
            return False, "el actor que respaldó la incorporación no es una identidad autenticada válida", None
        if actor not in (actor_obj.actor_id, actor_obj.display_name):
            return False, f"el actor registrado '{actor}' no coincide con el actor autenticado '{actor_obj.actor_id}'", None
        file_meta = st.session_state.get("file_metadata", {}).get(filename, {})
        file_org = file_meta.get("organization_id")
        if file_org and actor_obj.organization_id != file_org:
            return False, f"el actor pertenece a la organización '{actor_obj.organization_id}', incompatible con la del archivo '{file_org}'", None
    elif _auth_enforced():
        return False, "se requiere una identidad autenticada acreditada para respaldar la incorporación", None

    # Confirmación explícita obligatoria (Condición 6)
    if not (respaldo.get("confirmacion_explicita") or "importes_confirmados" in respaldo):
        return False, "el respaldo documental no registra la confirmación explícita de los importes", None

    importes = respaldo.get("importes_confirmados") if "importes_confirmados" in respaldo else respaldo.get("importes")
    if not isinstance(importes, dict):
        return False, "el respaldo documental no contiene el registro estructurado de importes confirmados", None

    for col in RAW_MONETARY_COLUMNS:
        if col not in row or row[col] is None or pd.isna(row[col]):
            return False, f"la fila agregada no especifica la columna requerida '{col}'; no se permite inventar importes faltantes para obtener cuadratura", None
        if col not in importes or importes[col] is None or pd.isna(importes[col]):
            return False, f"la fila agregada no especifica la columna requerida '{col}'; no se permite inventar importes faltantes para obtener cuadratura", None
        try:
            val_row = float(row[col])
            val_resp = float(importes[col])
        except (ValueError, TypeError):
            return False, f"valor numérico no convertible en columna '{col}'", None
        if not math.isfinite(val_row) or not math.isfinite(val_resp):
            return False, f"el importe en la columna '{col}' no es un número finito", None
        if abs(val_row - val_resp) > 1e-4:
            return False, f"discrepancia entre importe de fila y respaldo para '{col}': {val_row} vs {val_resp}", None

    return True, "", dict(respaldo)


def _validar_respaldo_exclusion(
    row: dict[str, Any],
    filename: str,
    file_digest: str | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Valida el registro estructurado de autorización para excluir una cuenta relevante."""
    exclusion = row.get("decision_exclusion") or row.get("respaldo_exclusion")
    if not isinstance(exclusion, dict):
        return False, "carece de registro estructurado de exclusión autorizada ('decision_exclusion')", None

    doc_id = str(exclusion.get("archivo") or exclusion.get("file_name") or exclusion.get("file_digest") or "").strip()
    if not doc_id:
        return False, "el registro de exclusión no especifica el identificador o huella del archivo", None
    if doc_id != filename and (not file_digest or doc_id != file_digest):
        return False, f"el registro de exclusión vincula al archivo '{doc_id}', distinto de '{filename}'", None

    actor = str(exclusion.get("actor") or exclusion.get("actor_id") or exclusion.get("usuario_confirmacion") or "").strip()
    if not actor:
        return False, "el registro de exclusión no registra la trazabilidad del actor que autorizó la exclusión", None

    motivo = str(exclusion.get("motivo") or exclusion.get("tipo_exclusion") or "").strip()
    if not motivo:
        return False, "el registro de exclusión no especifica el motivo estructurado de exclusión", None

    return True, "", dict(exclusion)


def _es_control_o_subtotal(nombre: str) -> bool:
    """Identifica si una descripción corresponde a un subtotal o control contable."""
    if not nombre:
        return False
    import unicodedata
    s = unicodedata.normalize("NFKD", str(nombre))
    s = "".join(c for c in s if not unicodedata.combining(c))
    norm = re.sub(r"[^a-z0-9]+", "", s.lower())
    if not norm:
        return False
    patrones = (
        "subtotal", "sumas", "totalgeneral", "sumastotales",
        "totalesiguales", "sumasiguales", "totalacumulado", "total",
    )
    return any(p in norm for p in patrones)


def _recertificar_balance_columnas(
    filename: str,
    df: pd.DataFrame,
    certification: Any,
    *,
    snapshot_cuentas: list[CuentaRaw] | None = None,
    file_digest: str | None = None,
) -> CertificacionExtraccion:
    """Recertifica las ocho columnas con correspondencia documental estricta contra el snapshot original."""
    metodo_cert = getattr(certification, "metodo", "excel_8_columns") or "excel_8_columns"
    if certification is None:
        if hasattr(df, "attrs"):
            df.attrs.pop("certification_binding", None)
        return CertificacionExtraccion(
            estado="fallida", metodo=metodo_cert,
            razones=["Falta certificación previa de ocho columnas."],
            columnas_finales_validadas=False,
        )
    snapshot = snapshot_cuentas
    if snapshot is None:
        snap_info = st.session_state.get("classified_source_snapshots", {}).get(filename)
        if snap_info and "accounts" in snap_info:
            snapshot = snap_info["accounts"]
    if not snapshot:
        if hasattr(df, "attrs"):
            df.attrs.pop("certification_binding", None)
        return CertificacionExtraccion(
            estado="fallida", metodo=metodo_cert,
            razones=["Falta el documento completo original de ocho columnas; no puede recertificarse desde una tabla editada sin controles fuente."],
            columnas_finales_validadas=False,
        )
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        if hasattr(df, "attrs"):
            df.attrs.pop("certification_binding", None)
        return CertificacionExtraccion(
            estado="fallida", metodo=metodo_cert,
            razones=["El contenido editado está vacío o no es un DataFrame válido."],
            columnas_finales_validadas=False,
        )
    if "linea" not in df.columns:
        if hasattr(df, "attrs"):
            df.attrs.pop("certification_binding", None)
        return CertificacionExtraccion(
            estado="fallida", metodo=metodo_cert,
            razones=["Las filas editadas no tienen una columna de identidad de línea ('linea')."],
            columnas_finales_validadas=False,
        )

    # 1. Comprobar identificador presente y no nulo en todas las filas de df
    for idx, row in df.iterrows():
        val = row.get("linea")
        if val is None or pd.isna(val) or str(val).strip() == "":
            if hasattr(df, "attrs"):
                df.attrs.pop("certification_binding", None)
            return CertificacionExtraccion(
                estado="fallida", metodo=metodo_cert,
                razones=[f"Identificador de línea ausente o nulo detectado en la fila de índice {idx}."],
                columnas_finales_validadas=False,
            )

    # 2. Identificadores compuestos y detección de duplicados en df
    page_col = "pagina" if "pagina" in df.columns else ("page" if "page" in df.columns else None)
    df_records = df.to_dict("records")
    df_by_composite: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    lines_in_df: dict[Any, set[Any]] = {}

    for r in df_records:
        k = _clave_compuesta_cuenta(r)
        df_by_composite.setdefault(k, []).append(r)
        l_val = r["linea"]
        lines_in_df.setdefault(l_val, set()).add(k[0])

    for k, rows_k in df_by_composite.items():
        if len(rows_k) > 1:
            if hasattr(df, "attrs"):
                df.attrs.pop("certification_binding", None)
            montos = [r.get("monto") for r in rows_k]
            p_desc = f"en página {k[0]}" if k[0] is not None else "sin página"
            if len(set(montos)) > 1:
                return CertificacionExtraccion(
                    estado="fallida", metodo=metodo_cert,
                    razones=[f"Líneas duplicadas con importes distintos detectadas en la edición (línea {k[1]} {p_desc}: importes {montos})."],
                    columnas_finales_validadas=False,
                )
            return CertificacionExtraccion(
                estado="fallida", metodo=metodo_cert,
                razones=[f"Líneas duplicadas detectadas en la edición (línea {k[1]} {p_desc})."],
                columnas_finales_validadas=False,
            )

    # 3. Identificadores compuestos en snapshot y detección de ambigüedad
    snap_by_composite: dict[tuple[Any, Any], list[CuentaRaw]] = {}
    snap_lines_pages: dict[Any, set[Any]] = {}
    for c in snapshot:
        sk = _clave_compuesta_cuenta(c)
        snap_by_composite.setdefault(sk, []).append(c)
        snap_lines_pages.setdefault(c.linea, set()).add(sk[0])

    for sk, clist in snap_by_composite.items():
        if len(clist) > 1:
            if hasattr(df, "attrs"):
                df.attrs.pop("certification_binding", None)
            p_desc = f"en página {sk[0]}" if sk[0] is not None else "sin página"
            return CertificacionExtraccion(
                estado="fallida", metodo=metodo_cert,
                razones=[f"Identificadores duplicados o ambiguos detectados en el snapshot original (línea {sk[1]} {p_desc})."],
                columnas_finales_validadas=False,
            )

    # Validar ambigüedad entre páginas si misma línea aparece en múltiples páginas
    for l_val, pages in lines_in_df.items():
        if len(pages) > 1:
            for p in pages:
                if (p, l_val) not in snap_by_composite:
                    r_candidate = df_by_composite[(p, l_val)][0]
                    if not r_candidate.get("respaldo_documental"):
                        if hasattr(df, "attrs"):
                            df.attrs.pop("certification_binding", None)
                        return CertificacionExtraccion(
                            estado="fallida", metodo=metodo_cert,
                            razones=[f"Identificadores ambiguos entre páginas detectados sin correspondencia unívoca en el documento original (línea {l_val}, página {p})."],
                            columnas_finales_validadas=False,
                        )

    # 4. Tratamiento de cuentas agregadas (filas en df que no están en snapshot)
    decisiones_incorporacion: list[dict[str, Any]] = []
    cuentas_nuevas: list[CuentaRaw] = []
    snapshot_lines_only = {c.linea: c for c in snapshot if _clave_compuesta_cuenta(c)[0] is None}

    for k, rows_k in df_by_composite.items():
        row = rows_k[0]
        match_snap = snap_by_composite.get(k)
        if not match_snap and k[0] is None:
            match_snap = [snapshot_lines_only[k[1]]] if k[1] in snapshot_lines_only else None

        if not match_snap:
            # Fila agregada nueva: exige respaldo documental estructurado estricto
            valido, motivo_respaldo, respaldo_dict = _validar_respaldo_incorporacion(row, filename, file_digest)
            if not valido:
                if hasattr(df, "attrs"):
                    df.attrs.pop("certification_binding", None)
                return CertificacionExtraccion(
                    estado="fallida", metodo=metodo_cert,
                    razones=[f"Fila agregada sin respaldo documental válido (línea {k[1]}): {motivo_respaldo}."],
                    columnas_finales_validadas=False,
                )
            col_montos = {col: float(row[col]) for col in RAW_MONETARY_COLUMNS}
            monto_val = float(row["monto"]) if pd.notna(row.get("monto")) else None
            nom_cuenta = str(row.get("nombre_original") or row.get("nombre") or "").strip()
            es_sub = bool(
                row.get("es_total") is True
                or row.get("total") is True
                or _es_control_o_subtotal(nom_cuenta)
                or (respaldo_dict and respaldo_dict.get("es_subtotal") is True)
            )
            nueva_c = CuentaRaw(
                linea=int(k[1]) if str(k[1]).isdigit() else k[1],
                codigo=str(row.get("codigo_original") or row.get("codigo") or "").strip() or None,
                nombre=nom_cuenta,
                monto=monto_val,
                es_total=es_sub,
                montos_columnas=col_montos,
                confianza_extraccion=1.0,
            )
            if es_sub:
                setattr(nueva_c, "es_subtotal_manual", True)
            if k[0] is not None:
                setattr(nueva_c, "pagina", k[0])
            setattr(nueva_c, "respaldo_documental", respaldo_dict)
            cuentas_nuevas.append(nueva_c)
            decisiones_incorporacion.append(respaldo_dict)

    # 5. Tratamiento de cuentas eliminadas o excluidas
    df_keys = set(df_by_composite.keys())
    df_lines_only = {k[1] for k in df_keys if k[0] is None}
    decisiones_exclusion: list[dict[str, Any]] = []
    claves_excluidas: set[tuple[Any, Any]] = set()

    for c in snapshot:
        if c.es_total:
            continue
        ck = _clave_compuesta_cuenta(c)
        presente_en_df = ck in df_keys or (ck[0] is None and c.linea in df_lines_only)
        if not presente_en_df:
            # Cuenta del snapshot ausente en df
            if _es_cuenta_relevante(c):
                if hasattr(df, "attrs"):
                    df.attrs.pop("certification_binding", None)
                return CertificacionExtraccion(
                    estado="fallida", metodo=metodo_cert,
                    razones=[f"Eliminación no documentada de cuenta relevante detectada (cuenta '{c.nombre}', línea {c.linea})."],
                    columnas_finales_validadas=False,
                )

    # Verificar filas en df marcadas para exclusión
    for k, rows_k in df_by_composite.items():
        row = rows_k[0]
        esta_marcada_excluida = bool(row.get("excluida") is True or str(row.get("codigo_clasificado") or "").strip() == "__EXCLUIR__")
        if esta_marcada_excluida:
            if _es_cuenta_relevante_row(row):
                valida_exc, motivo_exc, exc_dict = _validar_respaldo_exclusion(row, filename, file_digest)
                if not valida_exc:
                    if hasattr(df, "attrs"):
                        df.attrs.pop("certification_binding", None)
                    return CertificacionExtraccion(
                        estado="fallida", metodo=metodo_cert,
                        razones=[f"Exclusión no autorizada de cuenta relevante (línea {k[1]}, cuenta '{row.get('nombre_original')}'): {motivo_exc}. Una justificación libre no autoriza a excluir una cuenta."],
                        columnas_finales_validadas=False,
                    )
                decisiones_exclusion.append(exc_dict)
                claves_excluidas.add(k)

    # 6. Construir cuentas_actualizadas:
    # Snapshot original deepcopy, omitir excluidas justificadas, actualizar editadas, añadir incorporaciones
    cuentas_actualizadas: list[CuentaRaw] = []
    for cuenta in deepcopy(snapshot):
        ck = _clave_compuesta_cuenta(cuenta)
        if ck in claves_excluidas:
            continue
        if ck[0] is None and (None, cuenta.linea) in claves_excluidas:
            continue
        if cuenta.es_total:
            cuentas_actualizadas.append(cuenta)
            continue

        matching_row = None
        if ck in df_by_composite:
            matching_row = df_by_composite[ck][0]
        elif ck[0] is None and (None, cuenta.linea) in df_by_composite:
            matching_row = df_by_composite[(None, cuenta.linea)][0]

        if matching_row is not None:
            for col in RAW_MONETARY_COLUMNS:
                if col in matching_row and pd.notna(matching_row[col]):
                    cuenta.montos_columnas[col] = float(matching_row[col])
            if "monto" in matching_row and pd.notna(matching_row["monto"]):
                cuenta.monto = float(matching_row["monto"])
            if "nombre_original" in matching_row and matching_row["nombre_original"]:
                cuenta.nombre = str(matching_row["nombre_original"])
            if "codigo_original" in matching_row:
                cuenta.codigo = str(matching_row["codigo_original"]) if matching_row["codigo_original"] else None
            if "origen_columna" in matching_row and matching_row["origen_columna"]:
                try:
                    cuenta.origen_columna = OrigenColumna(matching_row["origen_columna"])
                except (ValueError, KeyError):
                    pass
        cuentas_actualizadas.append(cuenta)

    cuentas_actualizadas.extend(cuentas_nuevas)

    # 7. Ejecutar validación de ocho columnas contrastando controles originales
    resultado = certificar_extraccion_columnas(cuentas_actualizadas, metodo=metodo_cert)
    filas_eval = len([c for c in cuentas_actualizadas if not c.es_total])
    resultado.filas_evaluadas = filas_eval
    setattr(resultado, "decisiones_incorporacion", decisiones_incorporacion)
    setattr(resultado, "decisiones_exclusion", decisiones_exclusion)

    if resultado.estado == "certificada" or getattr(resultado, "columnas_finales_validadas", False):
        _vincular_certificacion_contenido(
            resultado, df,
            filename=filename,
            file_digest=file_digest,
            alcance={
                "pages": list(df[page_col].dropna().unique()) if page_col else [],
                "filas": [r["linea"] for r in df_records],
            },
            filas_evaluadas=filas_eval,
            incorporaciones=decisiones_incorporacion,
            exclusiones=decisiones_exclusion,
        )
    else:
        if hasattr(df, "attrs"):
            df.attrs.pop("certification_binding", None)

    return resultado


def _ejecutar_recertificar_contenido_corregido(
    archivo_nombre: str,
    df: pd.DataFrame,
    extraction_certification: Any,
    catalogo: Any = None,
) -> Any:
    """Acción del botón 'Recertificar contenido corregido'.

    Identifica el método de certificación (8 columnas o clasificado) y ejecuta
    la recertificación completa contra controles documentales independientes.
    """
    if extraction_certification is None:
        nueva_cert = CertificacionExtraccion(
            estado="fallida", metodo="desconocido",
            razones=["No existe certificación previa para recertificar."],
            columnas_finales_validadas=False,
        )
        st.session_state.setdefault("extraction_certifications", {})[archivo_nombre] = nueva_cert
        return nueva_cert

    metodo = getattr(extraction_certification, "metodo", "") or ""
    if metodo in {"classified_totals", "classified_final_detail"}:
        nueva_cert = _recertificar_balance_clasificado(
            archivo_nombre, df, extraction_certification, force=True, catalogo=catalogo,
        )
    elif _es_certificacion_ocho_columnas(extraction_certification):
        nueva_cert = _recertificar_balance_columnas(
            archivo_nombre, df, extraction_certification,
        )
    else:
        nueva_cert = CertificacionExtraccion(
            estado="fallida", metodo=metodo,
            razones=["Método no reconocido o sin controles documentales independientes; no se certifica."],
            columnas_finales_validadas=False,
        )

    st.session_state.setdefault("extraction_certifications", {})[archivo_nombre] = nueva_cert
    if nueva_cert.estado == "certificada" or getattr(nueva_cert, "columnas_finales_validadas", False):
        if not (hasattr(df, "attrs") and "certification_binding" in df.attrs):
            _vincular_certificacion_contenido(nueva_cert, df, filename=archivo_nombre)
        _registrar_evento_auditoria(
            "Recertificación", archivo_nombre,
            "Contenido corregido comparado nuevamente con el documento original",
            df.attrs.get("certification_binding", {}).get("digest", ""), df,
        )
    else:
        if hasattr(df, "attrs"):
            df.attrs.pop("certification_binding", None)
    return nueva_cert


def _aplicar_edicion_monto_periodos(
    df: pd.DataFrame, idx: Any, nuevo_monto: float, periodo_activo: str | None = None,
    *, periodos: tuple[str, ...] | None = None,
) -> None:
    """Sincroniza atómicamente monto y el período activo sin alterar otros períodos."""
    value = float(nuevo_monto)
    if not math.isfinite(value) or idx not in df.index:
        raise ValueError("El monto debe ser finito y la fila debe existir")
    years = tuple(str(p) for p in periodos) if periodos is not None else tuple(
        str(col).removeprefix("monto_periodo_") for col in df.columns
        if re.fullmatch(r"monto_periodo_\d{4}", str(col))
    )
    selected = str(periodo_activo) if periodo_activo is not None else None
    if years and (selected not in years or f"monto_periodo_{selected}" not in df.columns):
        raise ValueError("Debe indicar un período presente en el documento")
    position = years.index(selected) if years else 0
    if position > 1:
        raise ValueError("La edición admite los dos períodos del comparativo")
    updates = {}
    if selected is not None:
        if f"monto_periodo_{selected}" not in df.columns:
            raise ValueError("El período no tiene una columna documental")
        updates[f"monto_periodo_{selected}"] = value
    if position == 0:
        updates["monto"] = value
    alias = "monto_periodo_actual" if position == 0 else "monto_periodo_anterior"
    if alias in df.columns:
        updates[alias] = value
    for column, amount in updates.items():
        df.at[idx, column] = amount
    df.attrs.pop("certification_binding", None)


def _extraer_confianza_segura(valor: Any) -> float | None:
    """Extrae confianza numérica entre 0.0 y 1.0, preservando 0.0 exacto.

    Devuelve None si el valor no existe o no es numérico finito.
    """
    if valor is None or valor is False:
        return 0.0 if valor is False else None
    try:
        f = float(valor)
        if not math.isfinite(f):
            return None
        return max(0.0, min(1.0, f))
    except (ValueError, TypeError):
        return None


def normalizar_rut(rut_str: str) -> str:
    """Normaliza un RUT chileno eliminando puntos, guiones y espacios, en mayúsculas."""
    if not rut_str:
        return ""
    return re.sub(r"[^0-9kK]", "", str(rut_str)).upper()


def propagar_entre_balances_seguro(
    resultados: dict[str, pd.DataFrame],
    metadatos_archivos: dict[str, dict[str, Any]] | None = None,
) -> int:
    """Propaga clasificaciones respetando identidad de empresa, organización y revisión."""
    if not resultados or len(resultados) < 2:
        return 0
    metadatos = metadatos_archivos
    if metadatos is None:
        metadatos = st.session_state.get("file_metadata") or {}

    act = _authenticated_actor()
    actor_org = str(getattr(act, "organization_id", "") or "").strip()
    if not actor_org and _auth_enforced():
        return 0

    def _obtener_info(fname: str) -> tuple[str, str, bool]:
        meta = metadatos.get(fname, {})
        # Exige identidad documental propia vinculada al archivo; NUNCA tomar de sesión
        raw_rut = meta.get("rut") or meta.get("company_rut")
        rut_norm = normalizar_rut(str(raw_rut or ""))

        # Exige organización explícita vinculada al archivo; NUNCA inventar default_org
        org = str(meta.get("organization_id") or "").strip()
        if not org:
            return rut_norm, "", False

        # Si el actor autenticado tiene organización, la org del archivo DEBE coincidir
        if actor_org and org != actor_org:
            return rut_norm, org, False

        # Verificación explícita: debe ser booleano True estricto (no "false", "true", 1, etc.)
        verified_val = meta.get("verified")
        if verified_val is not True:
            return rut_norm, org, False

        if not rut_norm:
            return "", org, False

        return rut_norm, org, True

    ruts_por_archivo: dict[str, str] = {}
    orgs_por_archivo: dict[str, str] = {}
    verified_por_archivo: dict[str, bool] = {}
    for fname in resultados:
        r, o, v = _obtener_info(fname)
        ruts_por_archivo[fname] = r
        orgs_por_archivo[fname] = o
        verified_por_archivo[fname] = v

    candidates: dict[tuple[str, str, str], list[tuple[str, Any, str, str, float | None]]] = {}
    for fname, df in resultados.items():
        rut = ruts_por_archivo[fname]
        org = orgs_por_archivo[fname]
        verified = verified_por_archivo[fname]
        if not rut or not org or not verified:
            continue
        for idx, row in df.iterrows():
            nombre = row.get("nombre_original")
            if not nombre:
                continue
            norm = normalizar_nombre(str(nombre))
            cod = str(row.get("codigo_clasificado") or "").strip()
            sec = str(row.get("seccion_contable") or row.get("origen_columna") or "").strip().upper()
            conf = _extraer_confianza_segura(row.get("confianza"))
            candidates.setdefault((org, rut, norm), []).append((fname, idx, cod, sec, conf))

    propagados = 0
    for (org, rut, norm), entries in candidates.items():
        classified_entries = [e for e in entries if e[2] and e[2] not in ("", "__EXCLUIR__")]
        if not classified_entries:
            continue
        unique_codes = {e[2] for e in classified_entries}
        if len(unique_codes) > 1:
            continue
        source_fname, source_idx, classified_code, source_sec, source_conf = classified_entries[0]

        for fname, idx, cod, sec, conf in entries:
            if cod and cod != "":
                continue
            if orgs_por_archivo.get(fname) != org or ruts_por_archivo.get(fname) != rut:
                continue
            row = resultados[fname].loc[idx]
            es_source_no_corriente = "NO CORRIENT" in source_sec or source_sec.startswith("ANC") or source_sec.startswith("PNC")
            target_sec = str(row.get("seccion_contable") or row.get("origen_columna") or "").strip().upper()
            es_target_no_corriente = "NO CORRIENT" in target_sec or target_sec.startswith("ANC") or target_sec.startswith("PNC")
            if es_source_no_corriente != es_target_no_corriente and bool(source_sec) and bool(target_sec):
                continue
            if _codigo_compatible_con_origen(
                classified_code,
                row.get("origen_columna"),
                row.get("monto"),
                _nombre_contable_fila(row),
            ):
                resultados[fname].at[idx, "codigo_clasificado"] = classified_code
                resultados[fname].at[idx, "metodo"] = "propagado_sugerido"
                target_conf = source_conf if source_conf is not None else 0.0
                resultados[fname].at[idx, "confianza"] = target_conf
                resultados[fname].at[idx, "requiere_revision"] = True
                if "origen" in resultados[fname].columns:
                    resultados[fname].at[idx, "origen"] = "Propagado"
                    resultados[fname].at[idx, "regla"] = "propagado_sugerido"
                    evid = f"Sugerencia propagada desde {source_fname} (revisión pendiente"
                    if source_conf is not None:
                        evid += f"; confianza origen: {source_conf})"
                    else:
                        evid += "; sin confianza previa)"
                    resultados[fname].at[idx, "evidencia"] = evid
                propagados += 1
    return propagados


def _registrar_evento_auditoria(
        tipo: str, archivo: str, razon: str, detalle: str = "",
        df: pd.DataFrame | None = None) -> dict:
    evento = {
        "Tipo": tipo, "Archivo": archivo, "Razón": razon, "Detalle": detalle,
        "Fecha/hora": datetime.now().astimezone().isoformat(),
        **_actor_audit_fields(),
    }
    st.session_state.setdefault("audit_events", []).append(evento)
    if df is not None:
        df.attrs.setdefault("audit_events", []).append(dict(evento))
    return evento


def _resumen_bloqueadores_emision(motivos: list[str]) -> pd.DataFrame:
    filas = []
    for motivo in dict.fromkeys(str(m) for m in motivos if str(m).strip()):
        recertificar = any(token in motivo.lower() for token in (
            "certific", "extracción documental", "contenido actual",
        ))
        filas.append({
            "Tipo": "Recertificar extracción" if recertificar else "Corregir clasificación o control",
            "Bloqueador": motivo,
            "Acción requerida": (
                "Volver a verificar la extracción contra el documento"
                if recertificar else "Revisar la cuenta o control indicado"
            ),
        })
    return pd.DataFrame(filas)


def _valores_periodo_metadata(meta: MetadataEmpresa) -> tuple[str, int | None, int]:
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
    if not cierre:
        if meta.anio_cierre:
            return meta.mes_cierre or "Diciembre", int(meta.anio_cierre), meta.numero_meses or 12
        return meta.mes_cierre or "Diciembre", None, meta.numero_meses or 12
    meses = 12
    if inicio:
        meses = (cierre.year - inicio.year) * 12 + cierre.month - inicio.month + 1
        meses = min(12, max(1, meses))
    return MESES_SELECCION[cierre.month - 1], cierre.year, meses


def _fechas_periodo_seleccionado(
    mes: str, anio: int | None, numero_meses: int,
) -> tuple[str, str]:
    """Convierte mes de cierre y duración a fechas inclusivas del período."""
    if anio is None:
        return ("", "")
    mes_numero = MESES_SELECCION.index(mes) + 1 if mes in MESES_SELECCION else 12
    total_inicio = int(anio) * 12 + mes_numero - int(numero_meses)
    anio_inicio, mes_inicio_cero = divmod(total_inicio, 12)
    mes_inicio = mes_inicio_cero + 1
    ultimo_dia = calendar.monthrange(int(anio), mes_numero)[1]
    return (
        f"01/{mes_inicio:02d}/{anio_inicio}",
        f"{ultimo_dia:02d}/{mes_numero:02d}/{int(anio)}",
    )


def _aplicar_metadata_confirmada(meta: MetadataEmpresa) -> MetadataEmpresa:
    """Aplica a cada archivo los datos generales confirmados por el usuario."""
    meta.rut = st.session_state.company_rut
    meta.razon_social = st.session_state.company_razon
    meta.giro = st.session_state.company_giro
    meta.moneda = st.session_state.company_moneda
    meta.mes_cierre = st.session_state.company_mes
    meta.anio_cierre = int(st.session_state.company_anio) if st.session_state.company_anio is not None else None
    meta.numero_meses = int(st.session_state.company_numero_meses) if st.session_state.company_numero_meses is not None else 12
    meta.periodos_detectados = tuple(
        st.session_state.get("company_periodos_detectados", ())
    )
    meta.periodos_seleccionados = tuple(
        st.session_state.get(
            "company_periodos_seleccionados", (str(meta.anio_cierre),) if meta.anio_cierre else (),
        )
    )
    if meta.anio_cierre:
        meta.periodo_desde, meta.periodo_hasta = _fechas_periodo_seleccionado(
            meta.mes_cierre, meta.anio_cierre, meta.numero_meses,
        )
    return meta


def _detectar_periodos_comparativos(
    lineas: list[str], anio_fallback: int | None = None,
) -> tuple[str, ...]:
    """Devuelve hasta dos años explícitos respetando el orden del documento."""
    years, _ = detectar_años_y_monedas(lineas)
    numeric = []
    for year in years:
        if re.fullmatch(r"(?:19|20)\d{2}", str(year)) and year not in numeric:
            numeric.append(str(year))
    if not numeric and anio_fallback is not None:
        numeric.append(str(int(anio_fallback)))
    return tuple(numeric[:2])


def _periodos_seleccionados() -> tuple[str, ...]:
    sel = getattr(st.session_state, "company_periodos_seleccionados", None)
    if sel is None and hasattr(st.session_state, "get"):
        sel = st.session_state.get("company_periodos_seleccionados", ())
    selected = tuple(sel or ())
    if selected:
        return selected
    anio = getattr(st.session_state, "company_anio", None)
    if anio is None and hasattr(st.session_state, "get"):
        anio = st.session_state.get("company_anio")
    if anio is not None and str(anio).strip():
        return (str(int(anio)),)
    return ()


def _valor_periodo(
    montos_periodos: dict, periodo: str, posicion: int,
    monto_fallback: float | None = None,
) -> float | None:
    """Obtiene el valor anual sin confundir alias actual/anterior o moneda."""
    if periodo in montos_periodos:
        return montos_periodos[periodo]
    alias = "actual" if posicion == 0 else "anterior"
    if alias in montos_periodos:
        return montos_periodos[alias]
    return monto_fallback if posicion == 0 else None


def _montos_periodos_cuenta(cuenta: CuentaRaw) -> dict[str, float | None]:
    return {
        periodo: _valor_periodo(
            cuenta.montos_periodos, periodo, posicion, cuenta.monto,
        )
        for posicion, periodo in enumerate(_periodos_seleccionados())
    }


def _campos_periodos_cuenta(cuenta: CuentaRaw) -> tuple[float | None, dict]:
    valores = _montos_periodos_cuenta(cuenta)
    periodos = _periodos_seleccionados()
    principal = valores.get(periodos[0], cuenta.monto)
    campos = {
        f"monto_periodo_{periodo}": valores.get(periodo)
        for periodo in periodos
    }
    campos["monto_periodo_actual"] = valores.get(periodos[0])
    campos["monto_periodo_anterior"] = (
        valores.get(periodos[1]) if len(periodos) > 1 else None
    )
    return principal, campos


def _cuenta_tiene_saldo_seleccionado(cuenta: CuentaRaw) -> bool:
    valores = _montos_periodos_cuenta(cuenta).values()
    presentes = [float(valor) for valor in valores if valor is not None]
    if presentes:
        return any(valor != 0 for valor in presentes)
    return cuenta.monto is None or float(cuenta.monto) != 0

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')
UMBRAL_REVISION = 0.85  # bajo este valor, la cuenta va a la cola de revisión
USE_LEGACY_ENGINE = False  # True → MotorHibridoLocal (antiguo); False → HomologationPipeline (nuevo, default)
SHADOW_MODE = True  # True → ejecuta nuevo pipeline en paralelo sin afectar UI, guarda logs en logs/shadow/


def _build_date() -> str:
    configured = os.environ.get("APP_BUILD_DATE")
    if configured:
        return configured
    try:
        return (BASE_DIR / ".build_date").read_text(encoding="utf-8").strip()
    except OSError:
        return "desarrollo-local"

st.set_page_config(
    page_title="Homologación de Balances Tributarios",
    page_icon="📊",
    layout="wide",
)


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE CATÁLOGO Y DICCIONARIO
# ─────────────────────────────────────────────────────────────────────────────

def _persistence_settings() -> PersistenceSettings:
    return PersistenceSettings.from_environment()


def _legacy_neon_store() -> NeonKnowledgeStore:
    if _local_persistence_enabled():
        raise RuntimeError("Neon está deshabilitado en modo de persistencia local")
    return NeonKnowledgeStore()


def _knowledge_repository():
    """Resuelve el puerto activo conservando explícitamente el modo heredado."""
    settings = _persistence_settings()
    legacy_store = _legacy_neon_store() if settings.mode == "legacy_neon" else None
    return build_persistence(
        settings, legacy_neon_store=legacy_store,
    ).knowledge


def _local_persistence_enabled() -> bool:
    return _persistence_settings().mode == "local"


def _gold_benchmark_path() -> Path:
    """Benchmark empaquetado de solo lectura."""
    return BASE_DIR / "gold_standard.db"


def _gold_runtime_path() -> Path:
    """Runtime mutable bajo el volumen local; legacy conserva su ruta histórica."""
    settings = _persistence_settings()
    if settings.mode != "local":
        return BASE_DIR / "gold_standard_runtime.db"
    if settings.local_root is None:
        raise RuntimeError("LOCAL_PERSISTENCE_ROOT es obligatorio para el runtime Gold")
    path = settings.local_root.resolve() / "gold" / "gold_standard_runtime.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _legacy_json_fallback_allowed() -> bool:
    """El JSON empaquetado sólo es fallback del despliegue heredado."""
    return not _local_persistence_enabled()


def _write_legacy_packaged_dictionary(dictionary: list[dict]) -> None:
    """Fallback heredado deliberado; queda inaccesible en modo on-prem local."""
    if not _legacy_json_fallback_allowed():
        raise RuntimeError("No se permite escribir el JSON empaquetado en modo local")
    with open(BASE_DIR / "diccionario.json", "w", encoding="utf-8") as handle:
        json.dump(dictionary, handle, ensure_ascii=False, indent=2)


def _write_legacy_packaged_catalog(catalog: dict) -> None:
    """Fallback heredado deliberado; queda inaccesible en modo on-prem local."""
    if not _legacy_json_fallback_allowed():
        raise RuntimeError("No se permite escribir el JSON empaquetado en modo local")
    with open(BASE_DIR / "catalogo_maestro.json", "w", encoding="utf-8") as handle:
        json.dump(catalog, handle, ensure_ascii=False, indent=2)


def _validation_reviewer() -> str:
    actor = _authenticated_actor()
    if _auth_enforced():
        require_role(actor, "analyst")
    return actor.actor_id if actor is not None else "anonymous_staging"

@st.cache_data
def cargar_catalogo() -> dict:
    try:
        catalogo_repo = _knowledge_repository().load_catalog()
    except Exception:
        if _local_persistence_enabled():
            raise RuntimeError(
                "No se pudo cargar el catálogo desde la persistencia local durable"
            )
        catalogo_repo = {}
    if _local_persistence_enabled():
        return canonicalize_catalog(catalogo_repo)
    with open(BASE_DIR / 'catalogo_maestro.json', encoding='utf-8') as f:
        catalogo_empaquetado = json.load(f)
    return canonicalize_catalog({
        codigo: {**entrada, **catalogo_repo.get(codigo, {})}
        for codigo, entrada in catalogo_empaquetado.items()
    } | {
        codigo: entrada for codigo, entrada in catalogo_repo.items()
        if codigo not in catalogo_empaquetado
    })


@st.cache_data
def cargar_diccionario_base() -> list[dict]:
    try:
        diccionario = _knowledge_repository().load_dictionary()
        if diccionario or _local_persistence_enabled():
            return canonicalize_dictionary(diccionario)
    except Exception:
        if _local_persistence_enabled():
            raise RuntimeError(
                "No se pudo cargar el diccionario desde la persistencia local durable"
            )
    with open(BASE_DIR / 'diccionario.json', encoding='utf-8') as f:
        return canonicalize_dictionary(json.load(f))


def _persistir_validacion(
    *, nombre: str, codigo: str, fuente: str, agregar_diccionario: bool,
    sugerido: str | None = None, metodo: str | None = None,
    confianza: float | None = None, archivo: str = '',
) -> bool:
    """Persiste mediante el puerto activo; el fallback JSON es sólo heredado."""
    codigo = canonical_catalog_code(codigo)
    sugerido = canonical_catalog_code(sugerido) if sugerido else sugerido
    try:
        _knowledge_repository().save_validation(ValidationDecision(
            account_name=nombre,
            validated_code=codigo,
            source=fuente,
            suggested_code=sugerido,
            suggested_method=metodo,
            suggested_confidence=confianza,
            reviewer=_validation_reviewer(),
            source_file=archivo,
            add_to_dictionary=agregar_diccionario,
        ))
        cargar_diccionario_base.clear()
        return True
    except (AuthenticationRequired, AuthorizationDenied):
        raise
    except Exception as exc:
        if _local_persistence_enabled():
            st.error(f"No se guardó la validación en persistencia local durable: {exc}")
        else:
            st.error("Neon no pudo guardar la validación; se usará respaldo JSON heredado.")
        return False


def _persistir_validaciones_lote(validaciones: list[dict]) -> bool:
    """Persiste un lote completo mediante el repositorio configurado."""
    try:
        reviewer = _validation_reviewer()
        decisions = [ValidationDecision(
            account_name=item["account_name"],
            validated_code=canonical_catalog_code(item["validated_code"]),
            source=item["source"],
            suggested_code=(canonical_catalog_code(item["suggested_code"])
                            if item.get("suggested_code") else None),
            suggested_method=item.get("suggested_method"),
            suggested_confidence=item.get("suggested_confidence"),
            reviewer=reviewer,
            source_file=item.get("source_file", ""),
            add_to_dictionary=bool(item.get("add_to_dictionary", True)),
        ) for item in validaciones]
        _knowledge_repository().save_validations(decisions)
        cargar_diccionario_base.clear()
        return True
    except (AuthenticationRequired, AuthorizationDenied):
        raise
    except Exception as exc:
        if _local_persistence_enabled():
            st.error(f"No se guardó el lote en persistencia local durable: {exc}")
        else:
            st.error(
                "Neon no pudo guardar el lote; las clasificaciones permanecen "
                "en esta sesión y se usará el respaldo JSON heredado."
            )
        return False


def _persistir_catalogo(entry: dict) -> bool:
    try:
        _knowledge_repository().save_catalog_entry(entry)
        cargar_catalogo.clear()
        return True
    except Exception as exc:
        if _local_persistence_enabled():
            st.error(f"No se guardó la categoría en persistencia local durable: {exc}")
        else:
            st.error("Neon no pudo guardar la categoría; se usará respaldo JSON heredado.")
        return False


@st.cache_data(ttl=60)
def _neon_disponible() -> bool:
    if _local_persistence_enabled():
        return False
    return _knowledge_repository().healthcheck()


# ─────────────────────────────────────────────────────────────────────────────
# REGLAS REGEX (patrones de mayor cobertura)
# ─────────────────────────────────────────────────────────────────────────────

PATRON_NO_CUENTA = re.compile(
    r'^(comprendido|periodo|per[ií]odo|desde|hasta|rut|r\.u\.t|balance|'
    r'fecha|p[aá]gina|hora|moneda|firma|declaro|art[ií]culo|situaci[oó]n|'
    r'estados?\s+de\s+(?:situaci[oó]n|resultados?)|'
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


def propagar_clasificacion_resultados(nombre_original: str, codigo_final: str, metodo: str):
    nombre_norm = normalizar_nombre(nombre_original)
    if 'resultados' in st.session_state and isinstance(st.session_state.resultados, dict):
        propagaciones = 0
        for fn in list(st.session_state.resultados.keys()):
            df_res = st.session_state.resultados[fn].copy()
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
                        _nombre_contable_fila(row),
                    ),
                    axis=1,
                )
                mask_target &= compatibles
            if mask_target.any():
                df_res.loc[mask_target, 'codigo_clasificado'] = codigo_final
                df_res.loc[mask_target, 'metodo'] = metodo
                df_res.loc[mask_target, 'confianza'] = 1.0
                df_res.loc[mask_target, 'requiere_revision'] = False
                if 'origen' in df_res.columns:
                    df_res.loc[mask_target, 'origen'] = (
                        'Manual' if any(k in metodo for k in ('humana', 'manual')) else 'Código'
                    )
                    df_res.loc[mask_target, 'regla'] = metodo
                    df_res.loc[mask_target, 'evidencia'] = 'Propagación automática entre balances'
                st.session_state.resultados[fn] = df_res
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


def _nombre_con_contexto(
    nombre: str | None, jerarquia_contable: str | None = None,
) -> str:
    """Combina glosa y subtotal padre sólo para interpretar la cuenta."""
    return " ".join(
        str(value).strip() for value in (jerarquia_contable, nombre)
        if value and str(value).strip()
    )


def _nombre_contable_fila(row) -> str:
    return _nombre_con_contexto(
        _nombre_mostrar(row), row.get('jerarquia_contable'),
    )


def _origen_efectivo(origen_columna, monto, nombre: str | None = None) -> str:
    """Naturaleza contable efectiva, preservando aparte la columna física.

    En balances de 8 columnas un importe negativo representa una contra cuenta:
    ACTIVO <-> PASIVO y PERDIDA <-> GANANCIA.
    """
    origen = getattr(origen_columna, 'value', origen_columna)
    origen = str(origen or 'desconocido').strip().lower()
    if is_patrimonial_reserve_name(nombre) or is_accumulated_result_name(nombre):
        return 'patrimonio'
    if _es_contra_activo(nombre):
        return 'activo'
    try:
        es_negativo = monto is not None and pd.notna(monto) and float(monto) < 0
    except (TypeError, ValueError):
        es_negativo = False
    return _CONTRA_ORIGEN.get(origen, origen) if es_negativo else origen


def _etiqueta_origen(origen_columna, monto, nombre: str | None = None) -> str:
    """Etiqueta auditable para la cola: extracción y naturaleza efectiva."""
    extraido = getattr(origen_columna, 'value', origen_columna)
    extraido = str(extraido or 'desconocido').strip().upper()
    efectivo = _origen_efectivo(origen_columna, monto, nombre).upper()
    if is_patrimonial_reserve_name(nombre) or is_accumulated_result_name(nombre):
        return f"{extraido} → PATRIMONIO (naturaleza de la cuenta)"
    if _es_contra_activo(nombre) and efectivo == 'ACTIVO' and extraido != efectivo:
        return f"{extraido} → ACTIVO (contra-activo)"
    if efectivo != extraido:
        return f"{extraido} → {efectivo} (monto negativo)"
    return extraido


def _es_contra_activo(nombre: str | None) -> bool:
    """Reconoce cuentas acreedoras que corrigen el valor de un activo."""
    return is_contra_asset_name(nombre)


def _es_partida_patrimonial(nombre: str | None) -> bool:
    return is_equity_account_name(nombre)


def _monto_presentacion(codigo: str | None, monto, nombre: str | None = None,
                        origen=None, catalogo=None) -> float:
    """Aplica el signo contable sin alterar el importe extraído auditable."""
    valor = 0.0 if pd.isna(monto) else float(monto)
    codigo_normalizado = str(codigo or '')
    origen_normalizado = getattr(origen, 'value', origen)
    origen_normalizado = str(origen_normalizado or '').strip().lower()
    if str(codigo or '').startswith('ER.') and origen is not None:
        resultado = importe_resultado_homologado(codigo, valor, origen, catalogo)
        if resultado is not None:
            return resultado
    # En un balance de ocho columnas, una partida patrimonial ubicada
    # físicamente en Activo tiene saldo deudor y reduce el patrimonio. La
    # extracción conserva el importe positivo de la columna; el signo se
    # normaliza únicamente para homologación y presentación.
    if codigo_normalizado.startswith('PAT.') and origen_normalizado == 'activo':
        return -abs(valor)
    if codigo_normalizado == 'PAT.10':
        return -abs(valor)
    if codigo_normalizado == 'ANC.01.01' or (
        codigo_normalizado.startswith('ANC') and _es_contra_activo(nombre)
    ):
        return -abs(valor)
    return valor


def _resultado_periodo(clasificadas: pd.DataFrame) -> float | None:
    """Calcula ganancia menos pérdida desde las columnas efectivas extraídas."""
    ganancias = 0.0
    perdidas = 0.0
    encontro_resultado = False
    for _, row in clasificadas.iterrows():
        origen = row.get('origen_columna_efectiva') or _origen_efectivo(
            row.get('origen_columna'), row.get('monto'), row.get('nombre_original')
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
        catalogo=None) -> bool:
    """Impide sugerencias que contradigan la columna efectiva del balance."""
    origen_efectivo = _origen_efectivo(origen_columna, monto, nombre)
    if not resultado_compatible(codigo, origen_efectivo, catalogo):
        return False
    if str(codigo or '').startswith('ER.') and origen_efectivo in {'ganancia', 'perdida'}:
        return True
    # Una depreciación/amortización acumulada puede venir físicamente en la
    # columna Pasivo por su saldo acreedor, pero contablemente es contra-activo
    # y debe poder homologarse dentro del activo fijo (ANC).
    if (origen_efectivo == 'pasivo' and _es_contra_activo(nombre)
            and str(codigo or '').startswith('ANC')):
        return True
    if _es_partida_patrimonial(nombre) and str(codigo or '').startswith('PAT'):
        return True
    if (origen_efectivo == 'activo' and str(codigo or '') == 'PAT.10'
            and es_cuenta_socios(nombre)):
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


def _con_saldo_relevante(df: pd.DataFrame) -> pd.DataFrame:
    """Excluye filas con saldo cero de clasificación, resumen y exportación."""
    montos = pd.to_numeric(df['monto'], errors='coerce')
    return df[montos.isna() | montos.ne(0)]


def _alternativas_revision(
    *, nombre: str, sugerido: str, confianza: float,
    origen_columna, monto, catalogo: dict, motor,
    limite: int = 3,
) -> list[dict]:
    """Rankea candidatos compatibles sin alterar la decisión del motor."""
    candidatos: dict[str, dict] = {}

    def agregar(codigo: str | None, score: float, fuente: str, evidencia: str):
        if not codigo or codigo not in catalogo:
            return
        # Las cuentas calculadas pueden explicar una coincidencia, pero no
        # deben ofrecer un botón que el selector no puede aceptar.
        if not es_clasificable(catalogo[codigo]):
            return
        if not _codigo_compatible_con_origen(
            codigo, origen_columna, monto, nombre, catalogo,
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
        diccionario = canonicalize_dictionary(diccionario)
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

        resultado['codigo_estandar'] = canonical_catalog_code(
            resultado.get('codigo_estandar')
        ) or None
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

PROCESS_REGISTRY_QUERY_KEY = "processes"


def _process_media_type(file_name: str) -> str:
    return (
        "application/pdf" if Path(file_name).suffix.lower() == ".pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def _process_scope(archivo) -> ProcessScope:
    periods = tuple(str(value) for value in
                    st.session_state.get("company_periodos_seleccionados", ())[:2])
    if not periods:
        year = st.session_state.get("company_anio")
        periods = (str(year),) if year else ()
    pages = tuple(sorted(set(int(page) for page in
                             st.session_state.get("document_pages", {}).get(
                                 archivo.name, ()))))
    if Path(archivo.name).suffix.lower() != ".pdf" or not pages:
        return ProcessScope("all", (), periods)
    total = page_count(archivo.getvalue())
    if pages == tuple(range(1, total + 1)):
        return ProcessScope("all", (), periods)
    return ProcessScope("selected", pages, periods)


def _application_version() -> str:
    raw = (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("APP_BUILD_ID")
        or "local"
    )
    normalized = re.sub(r"[^A-Za-z0-9._:/-]", "-", str(raw).strip())[:80]
    return normalized or "local"


def _recover_or_start_process(
    service: LocalProcessPersistence, *, actor: AuthenticatedActor,
    content: bytes, original_name: str, media_type: str, scope: ProcessScope,
    execution_id: str | None = None, application_version: str | None = None,
) -> PersistedProcess:
    """Recupera por ID explícito o inicia una ejecución; nunca busca por nombre."""
    if execution_id:
        recovered = service.get(execution_id, actor=actor)
        if recovered is None:
            raise ProcessPersistenceError(
                "El puntero de proceso no referencia una ejecución durable",
                stage="execution_recovery", execution_id=execution_id,
            )
        digest = hashlib.sha256(content).hexdigest()
        metadata = recovered.execution.metadata
        expected_scope = {
            "page_mode": scope.page_mode,
            "selected_pages": list(scope.selected_pages),
            "periods": list(scope.periods),
        }
        actual_scope = {key: metadata.get(key) for key in expected_scope}
        if recovered.document.sha256 != digest:
            raise ProcessPersistenceError(
                "La ejecución durable pertenece a otro contenido",
                stage="document_digest_mismatch",
                document_id=recovered.document.document_id,
                execution_id=execution_id,
            )
        if actual_scope != expected_scope:
            raise ProcessPersistenceError(
                "El alcance durable no coincide con la selección actual",
                stage="scope_mismatch",
                document_id=recovered.document.document_id,
                execution_id=execution_id,
            )
        return recovered
    return service.start(
        content, original_name=original_name, media_type=media_type,
        scope=scope, actor=actor,
        application_version=application_version or _application_version(),
    )


def _persist_process_correction(
    service: LocalProcessPersistence, *, process: PersistedProcess,
    actor: AuthenticatedActor, correction_id: str, classification_code: str,
):
    """Audita sólo referencias y clasificación; no recibe ni envía montos."""
    return service.record_correction(
        process.execution.execution_id, actor=actor,
        correction_id=correction_id,
        classification_code=classification_code,
    )


def _persist_definitive_process_report(
    service: LocalProcessPersistence, *, process: PersistedProcess,
    actor: AuthenticatedActor, content: bytes, file_name: str,
    media_type: str, certified: bool,
) -> tuple[PersistedProcess, bytes]:
    """Completa una vez y relee el binario sólo desde el servicio autorizado."""
    if not certified:
        raise AuthorizationDenied(
            "Un reporte no certificado no puede persistirse como definitivo"
        )
    current = service.get(process.execution.execution_id, actor=actor)
    if current is None:
        raise ProcessPersistenceError(
            "La ejecución desapareció antes de persistir el reporte",
            stage="report_execution_recovery",
            execution_id=process.execution.execution_id,
        )
    if current.execution.status == "completed":
        definitive = [report for report in current.reports if report.definitive]
        if len(definitive) != 1:
            raise ProcessPersistenceError(
                "La ejecución completada no tiene un único reporte definitivo",
                stage="report_reconciliation",
                execution_id=current.execution.execution_id,
            )
        return current, service.read_definitive_report(
            current.execution.execution_id, definitive[0].report_id, actor=actor,
        )
    if current.execution.status not in {"running", "review"}:
        raise ProcessPersistenceError(
            "La ejecución no está habilitada para emitir un reporte definitivo",
            stage="report_state", execution_id=current.execution.execution_id,
        )
    completed = service.complete_with_report(
        current.execution.execution_id, content, actor=actor,
        file_name=file_name, media_type=media_type,
    )
    definitive = [report for report in completed.reports if report.definitive]
    if completed.execution.status != "completed" or len(definitive) != 1:
        raise ProcessPersistenceError(
            "La finalización no produjo un único reporte definitivo recuperable",
            stage="report_reconciliation",
            execution_id=completed.execution.execution_id,
        )
    durable_content = service.read_definitive_report(
        completed.execution.execution_id, definitive[0].report_id, actor=actor,
    )
    if durable_content != content:
        raise ProcessPersistenceError(
            "El reporte durable no coincide con el contenido certificado",
            stage="report_content_mismatch",
            execution_id=completed.execution.execution_id,
            report_id=definitive[0].report_id,
        )
    return completed, durable_content


def _process_registry() -> dict[str, str]:
    registry = st.session_state.setdefault("process_execution_ids", {})
    if registry:
        return registry
    try:
        raw = st.query_params.get(PROCESS_REGISTRY_QUERY_KEY, "")
        decoded = json.loads(raw) if raw else {}
        if isinstance(decoded, dict):
            registry.update({
                str(key): str(value) for key, value in decoded.items()
                if re.fullmatch(r"[a-f0-9]{64}", str(key))
                and re.fullmatch(r"[A-Za-z0-9-]{20,80}", str(value))
            })
    except Exception:
        pass
    return registry


def _save_process_registry(registry: dict[str, str]) -> None:
    st.session_state["process_execution_ids"] = dict(registry)
    st.query_params[PROCESS_REGISTRY_QUERY_KEY] = json.dumps(
        registry, sort_keys=True, separators=(",", ":"),
    )


def _streamlit_process_service(
    actor: AuthenticatedActor | None,
) -> LocalProcessPersistence | None:
    if actor is None:
        return None
    return build_persistence().processes


def _streamlit_process_for_file(
    file_name: str, actor: AuthenticatedActor | None,
) -> tuple[LocalProcessPersistence, PersistedProcess] | None:
    """Obtiene el proceso durable de un archivo sin inferirlo por su nombre."""
    service = _streamlit_process_service(actor)
    if service is None or actor is None:
        return None
    process = st.session_state.get("persisted_processes", {}).get(file_name)
    if not isinstance(process, PersistedProcess):
        raise ProcessPersistenceError(
            "No existe un proceso durable para la acción solicitada",
            stage="streamlit_process_lookup",
        )
    recovered = service.get(process.execution.execution_id, actor=actor)
    if recovered is None:
        raise ProcessPersistenceError(
            "El proceso durable dejó de estar disponible",
            stage="streamlit_process_recovery",
            document_id=process.document.document_id,
            execution_id=process.execution.execution_id,
        )
    st.session_state.setdefault("persisted_processes", {})[file_name] = recovered
    return service, recovered


def _correction_reference(file_name: str, row_reference, action: str) -> str:
    payload = f"{file_name}\0{row_reference}\0{action}".encode("utf-8")
    return f"ui:{action}:{hashlib.sha256(payload).hexdigest()[:24]}"


def _persist_streamlit_correction(
    file_name: str, *, row_reference, classification_code: str,
    action: str,
):
    """Registra una decisión manual antes de alterar el estado de Streamlit.

    El registro deliberadamente sólo contiene referencias y el código de
    clasificación. Los importes permanecen en la sesión y en el reporte, no en
    el evento de auditoría operacional.
    """
    actor = _authenticated_actor()
    resolved = _streamlit_process_for_file(file_name, actor)
    if resolved is None:
        return None
    service, process = resolved
    if process.execution.status == "running":
        process = service.mark_review(
            process.execution.execution_id, actor=actor,
        )
        st.session_state["persisted_processes"][file_name] = process
    if process.execution.status != "review":
        raise ProcessPersistenceError(
            "La ejecución durable no admite nuevas correcciones",
            stage="correction_state",
            document_id=process.document.document_id,
            execution_id=process.execution.execution_id,
        )
    event = _persist_process_correction(
        service, process=process, actor=actor,
        correction_id=_correction_reference(
            file_name, row_reference, action,
        ),
        classification_code=(
            "EXCLUDE" if classification_code == "__EXCLUIR__"
            else classification_code or "UNCLASSIFIED"
        ),
    )
    recovered = service.get(process.execution.execution_id, actor=actor)
    if recovered is None:
        raise ProcessPersistenceError(
            "La corrección fue auditada, pero la ejecución no pudo releerse",
            stage="correction_recovery",
            document_id=process.document.document_id,
            execution_id=process.execution.execution_id,
        )
    st.session_state["persisted_processes"][file_name] = recovered
    return event


def _persist_streamlit_definitive_report(
    file_name: str, *, content: bytes, report_name: str, certified: bool,
) -> bytes:
    """Persiste y relee el reporte definitivo, o conserva staging explícito."""
    if not certified:
        return content
    actor = _authenticated_actor()
    resolved = _streamlit_process_for_file(file_name, actor)
    if resolved is None:
        return content
    service, process = resolved
    completed, durable_content = _persist_definitive_process_report(
        service, process=process, actor=actor, content=content,
        file_name=report_name,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        certified=True,
    )
    st.session_state["persisted_processes"][file_name] = completed
    return durable_content


def _ensure_streamlit_processes(archivos, actor: AuthenticatedActor | None) -> None:
    service = _streamlit_process_service(actor)
    if service is None or actor is None:
        st.session_state["process_persistence_mode"] = "staging_or_legacy_disabled"
        return
    registry = _process_registry()
    processes = st.session_state.setdefault("persisted_processes", {})
    revised_scopes = st.session_state.setdefault(
        "process_scope_revisions_pending", set(),
    )
    for archivo in archivos:
        content = archivo.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        execution_id = registry.get(digest)
        if digest in revised_scopes and execution_id:
            previous = service.get(execution_id, actor=actor)
            if previous is None:
                raise ProcessPersistenceError(
                    "No se encontró la ejecución cuyo alcance fue modificado",
                    stage="scope_revision_recovery", execution_id=execution_id,
                )
            if previous.execution.status in {"pending", "running", "review"}:
                service.fail(
                    execution_id, actor=actor, error_code="SCOPE_CHANGED",
                )
            execution_id = None
        process = _recover_or_start_process(
            service, actor=actor, content=content, original_name=archivo.name,
            media_type=_process_media_type(archivo.name),
            scope=_process_scope(archivo), execution_id=execution_id,
        )
        if process.execution.status == "failed":
            raise ProcessPersistenceError(
                "La ejecución durable está fallida y requiere conciliación antes "
                "de iniciar otro procesamiento",
                stage="failed_execution_recovery",
                document_id=process.document.document_id,
                execution_id=process.execution.execution_id,
            )
        processes[archivo.name] = process
        revised_scopes.discard(digest)
        if registry.get(digest) == process.execution.execution_id:
            continue
        registry[digest] = process.execution.execution_id
        try:
            _save_process_registry(registry)
        except Exception as pointer_error:
            try:
                service.fail(
                    process.execution.execution_id, actor=actor,
                    error_code="PROCESS_POINTER_PERSISTENCE_FAILED",
                )
            except Exception:
                pass
            raise ProcessPersistenceError(
                "La ejecución inició, pero no pudo guardarse su puntero de recuperación",
                stage="process_pointer", document_id=process.document.document_id,
                execution_id=process.execution.execution_id,
            ) from pointer_error


def _restore_streamlit_process_scope(
    archivos, actor: AuthenticatedActor | None,
) -> None:
    """Restaura alcance y estado desde IDs URL; no infiere ejecuciones por nombre."""
    if st.session_state.get("document_scope_editing"):
        return
    if st.session_state.get("process_scope_revisions_pending"):
        return
    service = _streamlit_process_service(actor)
    if service is None or actor is None:
        return
    registry = _process_registry()
    recovered_by_name = {}
    recovered_pages = {}
    recovered_periods = None
    for archivo in archivos:
        content = archivo.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        execution_id = registry.get(digest)
        if not execution_id:
            return
        recovered = service.get(execution_id, actor=actor)
        if recovered is None or recovered.document.sha256 != digest:
            raise ProcessPersistenceError(
                "No fue posible reconciliar el documento con su ejecución durable",
                stage="scope_recovery", execution_id=execution_id,
            )
        metadata = recovered.execution.metadata
        periods = tuple(str(value) for value in metadata.get("periods", ()))
        if recovered_periods is not None and periods != recovered_periods:
            raise ProcessPersistenceError(
                "Los procesos recuperados tienen períodos incompatibles",
                stage="period_recovery", execution_id=execution_id,
            )
        recovered_periods = periods
        if Path(archivo.name).suffix.lower() == ".pdf":
            if metadata.get("page_mode") == "selected":
                pages = list(metadata.get("selected_pages", ()))
            else:
                pages = list(range(1, page_count(content) + 1))
            recovered_pages[archivo.name] = pages
        recovered_by_name[archivo.name] = recovered
    if len(recovered_by_name) != len(archivos):
        return
    signature = tuple(
        (archivo.name, hashlib.sha256(archivo.getvalue()).hexdigest())
        for archivo in archivos
    )
    st.session_state["persisted_processes"] = recovered_by_name
    st.session_state["document_pages"] = recovered_pages
    st.session_state["document_scope_confirmed"] = signature
    if recovered_periods:
        st.session_state["company_periodos_seleccionados"] = recovered_periods

    raw_map = st.session_state.setdefault("raw_file_bytes", {})
    for archivo in archivos:
        content = archivo.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        if actor and getattr(actor, "organization_id", None):
            raw_map[(archivo.name, actor.organization_id, digest)] = content

    # Revalidar vínculos de certificación existentes en memoria al restaurar alcance
    for archivo in archivos:
        df_existente = st.session_state.get("resultados", {}).get(archivo.name)
        cert_existente = st.session_state.get("extraction_certifications", {}).get(archivo.name)
        if df_existente is not None and cert_existente is not None:
            _restaurar_vinculo_certificacion(cert_existente, df_existente, al_restaurar=True)


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
    for a in archivos:
        try:
            a_digest = hashlib.sha256(a.getvalue()).hexdigest()
            existing_meta = st.session_state.get("file_metadata", {}).get(a.name)
            if existing_meta:
                prev_digest = existing_meta.get("file_digest")
                if prev_digest and prev_digest != a_digest:
                    st.error(
                        f"El archivo '{a.name}' tiene un nombre idéntico a un documento ya procesado pero con distinto contenido. "
                        f"Renómbrelo para mantener separadas sus páginas, correcciones y evidencia."
                    )
                    return False
        except Exception:
            pass
    signature = tuple((a.name, hashlib.sha256(a.getvalue()).hexdigest()) for a in archivos)
    if (st.session_state.get("document_scope_confirmed") == signature
            and not st.session_state.get("document_scope_editing", False)):
        # Conserva el valor del selector aunque esta vista se omita durante el
        # procesamiento; al volver a editar el alcance, Streamlit puede
        # reconstruir el mismo widget sin perder su estado.
        st.session_state.setdefault("document_scope_preview", archivos[0].name)
        return True
    preview_doc = next((a for a in archivos if a.name == preview_name), archivos[0])
    col_visor, col_form = st.columns([1, 1], gap="medium")

    with col_visor:
        _visor_documento(preview_doc, altura="72vh", mostrar_titulo=True)

    with col_form:
        st.subheader("📄 Selección de páginas a analizar")
        st.info(
            "Revise el documento en el visor sticky a la izquierda. Si contiene el mismo balance "
            "en varios formatos, elija sólo uno. En informes auditados seleccione las páginas "
            "del estado y sus continuaciones."
        )
        if st.session_state.get("document_scope_editing"):
            st.warning("Cambiar las páginas vuelve a procesar ese documento y reemplaza sus correcciones en esta sesión.")
        
        if len(archivos) > 1:
            preview_name = st.selectbox(
                "Documento a visualizar", [a.name for a in archivos],
                key="document_scope_preview",
            )
        
        selections = {}
        errors = []
        with st.form("document_scope"):
            for archivo in archivos:
                if Path(archivo.name).suffix.lower() != ".pdf":
                    continue
                try:
                    count = page_count(archivo.getvalue())
                except Exception:
                    errors.append(f"No se pudo abrir {archivo.name} como PDF.")
                    continue
                st.markdown(f"**{archivo.name}** (`{count} páginas`)")
                key = hashlib.sha256(archivo.name.encode() + archivo.getvalue()).hexdigest()[:16]
                saved_pages = st.session_state.get("document_pages", {}).get(archivo.name, [])
                saved_subset = bool(saved_pages) and saved_pages != list(range(1, count + 1))
                mode = st.radio("Páginas a analizar", ["Todas", "Sólo las seleccionadas"],
                                index=1 if saved_subset else 0,
                                key=f"scope_mode_{key}", horizontal=True)
                text = st.text_input("Páginas o rangos", placeholder="1, 3-5",
                                     value=", ".join(map(str, saved_pages)) if saved_subset else "",
                                     key=f"scope_pages_{key}")
                try:
                    selections[archivo.name] = list(range(1, count + 1)) if mode == "Todas" else parse_pages(text, count)
                except ValueError as exc:
                    errors.append(f"{archivo.name}: {exc}")
            submitted = st.form_submit_button("Confirmar páginas y continuar", use_container_width=True)

        if submitted:
            if errors:
                for error in errors:
                    st.error(error)
            else:
                previous = dict(st.session_state.get("document_scope_confirmed") or ())
                previous_pages = st.session_state.get("document_pages", {})
                for name, digest in signature:
                    if previous.get(name) != digest or previous_pages.get(name) != selections.get(name):
                        st.session_state.setdefault(
                            "process_scope_revisions_pending", set(),
                        ).add(digest)
                        revisions = st.session_state.setdefault("extraction_revisions", {})
                        revisions[name] = revisions.get(name, 0) + 1
                        st.session_state.metadata_confirmada = False
                        st.session_state.company_periodos_detectados = ()
                        st.session_state.company_periodos_seleccionados = ()
                        for state_key in ("resultados", "metadata_files", "document_intel", "document_families", "extraction_pending",
                                          "extraction_resolved", "extraction_certifications", "classified_source_snapshots", "processed_at",
                                          "quality_controls", "depreciation_reclassifications"):
                            st.session_state.setdefault(state_key, {}).pop(name, None)
                st.session_state.document_pages = selections
                st.session_state.document_scope_confirmed = signature
                st.session_state.document_scope_editing = False
                return True
    return False


def main():
    st.title("📊 Homologación de Balances Tributarios Chilenos")
    st.caption(
        "Carga uno o más balances (PDF o Excel) → clasificación híbrida automática "
        "(código → diccionario → reglas) → cola de revisión → balance normalizado."
    )

    try:
        actor = _require_app_role("analyst")
    except (AuthenticationRequired, AuthorizationDenied) as exc:
        st.error(f"Acceso bloqueado: {exc}")
        st.stop()
    if actor is None:
        st.caption("Modo staging sin autenticación: las acciones quedan con actor vacío.")
    else:
        st.caption(
            f"Sesión autenticada: {actor.display_name} · Organización: {actor.organization_id}"
        )

    catalogo = cargar_catalogo()
    dic_base = cargar_diccionario_base()

    if 'diccionario' not in st.session_state:
        st.session_state.diccionario = list(dic_base)
    if 'resultados' not in st.session_state or not isinstance(st.session_state.resultados, dict):
        st.session_state.resultados = {}
    if 'metadata_files' not in st.session_state:
        st.session_state.metadata_files = {}
    if 'document_intel' not in st.session_state:
        st.session_state.document_intel = {}
    if 'document_families' not in st.session_state:
        st.session_state.document_families = {}
    if 'extraction_pending' not in st.session_state:
        st.session_state.extraction_pending = {}
    if 'extraction_resolved' not in st.session_state:
        st.session_state.extraction_resolved = {}
    if 'extraction_certifications' not in st.session_state:
        st.session_state.extraction_certifications = {}
        st.session_state.classified_source_snapshots = {}
    if 'depreciation_reclassifications' not in st.session_state:
        st.session_state.depreciation_reclassifications = {}
    if 'correcciones' not in st.session_state:
        st.session_state.correcciones = []

    with st.sidebar:
        st.header("⚙️ Configuración")
        commit = os.environ.get("RENDER_GIT_COMMIT", "local")[:8]
        release_branch = os.environ.get("APP_RELEASE_BRANCH", "desarrollo-local")
        build_date = _build_date()
        persistence_label = "Neon conectado" if _neon_disponible() else "JSON local"
        st.caption(
            f"Rama `{release_branch}` · Commit `{commit}` · Build `{build_date}` · "
            f"Persistencia: **{persistence_label}**"
        )
        archivos = st.file_uploader(
            "Balances tributarios", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True
        )
        if archivos and st.session_state.get("document_scope_confirmed"):
            if st.button("Cambiar páginas a analizar"):
                st.session_state.document_scope_editing = True
                st.rerun()
        giro = st.selectbox(
            "Giro de la empresa (afecta regla D2-Terrenos)",
            ['Otro', 'Inmobiliaria', 'Construcción', 'Promotora'],
            help="Si el giro es inmobiliario/construcción, los terrenos en activo corriente se reclasifican como inventario."
        )
        giro_norm = None if giro == 'Otro' else giro.lower()

        st.divider()
        st.metric("Cuentas en diccionario", len(st.session_state.diccionario))
        st.metric("Códigos en catálogo", len(catalogo))

        if st.session_state.correcciones:
            st.divider()
            st.success(f"{len(st.session_state.correcciones)} correcciones pendientes")
            buf = json.dumps(st.session_state.diccionario, ensure_ascii=False, indent=2)
            st.download_button(
                "⬇️ Descargar diccionario actualizado",
                data=buf, file_name="diccionario_actualizado.json",
                mime="application/json"
            )

    if not archivos:
        st.info("⬆️ Carga uno o más archivos en la barra lateral para comenzar.")
        st.session_state.resultados = {}
        st.session_state.metadata_files = {}
        st.session_state.extraction_pending = {}
        st.session_state.extraction_resolved = {}
        st.session_state.extraction_certifications = {}
        st.session_state.depreciation_reclassifications = {}
        st.session_state.metadata_confirmada = False
        st.session_state.document_scope_confirmed = None
        st.session_state.document_scope_editing = False
        st.session_state.document_pages = {}
        st.session_state.company_periodos_detectados = ()
        st.session_state.company_periodos_seleccionados = ()
        _mostrar_resumen_catalogo(catalogo)
        return

    try:
        # La URL contiene exclusivamente punteros opacos por hash. Si existen,
        # el alcance durable se recupera antes de mostrar o confirmar páginas.
        _restore_streamlit_process_scope(archivos, actor)
    except (ProcessPersistenceError, AuthorizationDenied, ValueError) as exc:
        st.error(f"No se pudo recuperar el procesamiento durable: {exc}")
        st.stop()

    if not _confirmar_alcance_documentos(archivos):
        return

    if not st.session_state.get('metadata_confirmada', False):
        first_file = archivos[0]
        with st.spinner(f"Detectando metadata de la empresa en {first_file.name}..."):
            lineas_encabezado = _extraer_lineas_encabezado(first_file)
            meta = extraer_metadata(lineas_encabezado)
            st.session_state.company_rut = meta.rut or ""
            st.session_state.company_razon = meta.razon_social or ""
            st.session_state.company_giro = meta.giro or "Otro"
            mes_detectado, anio_detectado, meses_detectados = _valores_periodo_metadata(meta)
            st.session_state.company_moneda = meta.moneda or "$"
            st.session_state.company_mes = mes_detectado
            st.session_state.company_anio = anio_detectado
            st.session_state.company_numero_meses = meses_detectados
            periodos_detectados = _detectar_periodos_comparativos(
                lineas_encabezado, anio_detectado,
            )
            st.session_state.company_periodos_detectados = periodos_detectados
            seleccion_guardada = tuple(
                st.session_state.get("company_periodos_seleccionados", ())
            )
            if not seleccion_guardada or not set(seleccion_guardada).issubset(
                periodos_detectados
            ):
                st.session_state.company_periodos_seleccionados = periodos_detectados

        col_visor, col_form = st.columns([1, 1], gap="medium")
        with col_visor:
            _visor_documento(first_file, altura="72vh", mostrar_titulo=True)

        with col_form:
            st.subheader("📋 Confirma los datos de la empresa")
            st.caption("El sistema detectó los siguientes datos generales. Corrígelos si es necesario antes de continuar.")

            with st.form("form_empresa"):
                col1, col2 = st.columns(2)
                with col1:
                    rut = st.text_input("RUT", value=st.session_state.company_rut)
                    razon = st.text_input("Razón Social", value=st.session_state.company_razon)
                with col2:
                    giro_list = ['Otro', 'Inmobiliaria', 'Construcción', 'Promotora']
                    default_giro_idx = 0
                    if st.session_state.company_giro in giro_list:
                        default_giro_idx = giro_list.index(st.session_state.company_giro)
                    giro_sel = st.selectbox(
                        "Giro de la empresa (afecta regla D2-Terrenos)",
                        giro_list, index=default_giro_idx,
                        help="Escriba dentro del desplegable para filtrar opciones.",
                    )

                st.markdown("##### Moneda y período informado")
                moneda_col, otra_col = st.columns(2)
                moneda_opciones = ["$", "M", "MM", "USD", "Otra"]
                moneda_actual = st.session_state.company_moneda
                moneda_indice = (
                    moneda_opciones.index(moneda_actual)
                    if moneda_actual in moneda_opciones else moneda_opciones.index("Otra")
                )
                with moneda_col:
                    moneda_sel = st.selectbox(
                        "Moneda o unidad",
                        moneda_opciones,
                        index=moneda_indice,
                        help=(
                            "$: pesos; M: miles; MM: millones; USD: dólares. "
                            "Escriba para buscar una opción."
                        ),
                        filter_mode="fuzzy",
                    )
                with otra_col:
                    otra_moneda = st.text_input(
                        "Otra moneda o unidad",
                        value=(moneda_actual if moneda_actual not in moneda_opciones else ""),
                        placeholder="Ejemplo: EUR, UF, UTM",
                        help="Complete este campo únicamente si seleccionó Otra.",
                    )

                periodo1, periodo2, periodo3 = st.columns(3)
                with periodo1:
                    mes_sel = st.selectbox(
                        "Mes de cierre",
                        MESES_SELECCION,
                        index=MESES_SELECCION.index(st.session_state.company_mes),
                        help="Escriba el nombre del mes para encontrarlo.",
                        filter_mode="fuzzy",
                    )
                anio_actual = date.today().year
                anios = list(range(anio_actual + 1, 1979, -1))
                val_anio = st.session_state.company_anio
                if val_anio is not None and int(val_anio) not in anios:
                    anios.append(int(val_anio))
                    anios.sort(reverse=True)
                default_anio_idx = anios.index(int(val_anio)) if val_anio is not None else 1
                with periodo2:
                    anio_sel = st.selectbox(
                        "Año de cierre" + ("" if val_anio is not None else " (No detectado en documento)"),
                        anios,
                        index=default_anio_idx,
                        help="Año fiscal o de término del balance.",
                        filter_mode="fuzzy",
                    )
                opciones_meses = list(range(1, 13))
                with periodo3:
                    numero_meses_sel = st.selectbox(
                        "Número de meses del período",
                        opciones_meses,
                        index=opciones_meses.index(
                            int(st.session_state.company_numero_meses) if st.session_state.company_numero_meses is not None else 12
                        ),
                        help="Escriba un número entre 1 y 12 para encontrarlo.",
                        filter_mode="fuzzy",
                    )

                periodos_detectados = tuple(
                    st.session_state.get("company_periodos_detectados", ())
                )
                if len(periodos_detectados) >= 2:
                    actual, anterior = periodos_detectados[:2]
                    opciones_periodo = {
                        f"Ambos períodos detectados: {actual} y {anterior}": (actual, anterior),
                        f"Sólo {actual}": (actual,),
                        f"Sólo {anterior}": (anterior,),
                    }
                elif len(periodos_detectados) == 1:
                    unico = periodos_detectados[0]
                    opciones_periodo = {f"Sólo {unico} (Período detectado)": (unico,)}
                else:
                    opciones_periodo = {f"Período manual: {anio_sel}": (str(anio_sel),)}

                seleccion_actual = tuple(
                    st.session_state.get(
                        "company_periodos_seleccionados",
                        periodos_detectados or (str(anio_sel),),
                    )
                )
                etiquetas_periodo = list(opciones_periodo)
                indice_periodo = next(
                    (
                        indice for indice, etiqueta in enumerate(etiquetas_periodo)
                        if opciones_periodo[etiqueta] == seleccion_actual
                    ),
                    0,
                )
                alcance_periodos = st.selectbox(
                    "Períodos a extraer",
                    etiquetas_periodo,
                    index=indice_periodo,
                    help=(
                        "Ambos conserva una sola clasificación por cuenta y un "
                        "importe independiente para cada período."
                    ),
                )

                submitted = st.form_submit_button("Confirmar y procesar todos los balances", use_container_width=True)
                if submitted:
                    moneda_final = otra_moneda.strip() if moneda_sel == "Otra" else moneda_sel
                    if not moneda_final:
                        st.error("Especifique la moneda o unidad cuando seleccione Otra.")
                    else:
                        st.session_state.company_rut = rut
                        st.session_state.company_razon = razon
                        st.session_state.company_giro = giro_sel
                        st.session_state.company_moneda = moneda_final
                        st.session_state.company_mes = mes_sel
                        st.session_state.company_anio = int(anio_sel)
                        st.session_state.company_numero_meses = int(numero_meses_sel)
                        st.session_state.company_periodos_seleccionados = (
                            opciones_periodo[alcance_periodos]
                        )
                        st.session_state.company_anio = int(
                            st.session_state.company_periodos_seleccionados[0]
                        )
                        st.session_state.metadata_confirmada = True
                        st.session_state.resultados = {}
                        st.session_state.metadata_files = {}
                        st.rerun()
        return

    try:
        # Sólo se crea una ejecución después de que páginas, períodos y metadata
        # fueron confirmados. Cualquier fallo detiene el procesamiento.
        _ensure_streamlit_processes(archivos, actor)
    except (ProcessPersistenceError, AuthorizationDenied, ValueError, OSError) as exc:
        st.error(f"No se pudo iniciar o reconciliar el procesamiento durable: {exc}")
        st.stop()

    company_giro_norm = None if st.session_state.company_giro == 'Otro' else st.session_state.company_giro.lower()

    nombres_subidos = [a.name for a in archivos]
    for k in list(st.session_state.resultados.keys()):
        if k not in nombres_subidos:
            st.session_state.resultados.pop(k, None)
            st.session_state.metadata_files.pop(k, None)
            st.session_state.document_families.pop(k, None)
    for state_key in (
        'document_families', 'extraction_pending', 'extraction_resolved',
        'extraction_certifications', 'classified_source_snapshots', 'file_metadata',
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
                    doc_meta_raw = extraer_metadata(lineas_encabezado)
                    meta_indiv = _aplicar_metadata_confirmada(
                        deepcopy(doc_meta_raw)
                    )
                    st.session_state.metadata_files[archivo.name] = meta_indiv

                    if archivo.name in st.session_state.extraction_resolved:
                        cuentas = st.session_state.extraction_resolved.pop(archivo.name)
                        doc_ctx = st.session_state.document_intel.get(archivo.name)
                    else:
                        cuentas, doc_ctx = _extraer_cuentas(archivo)
                    st.session_state.document_intel[archivo.name] = doc_ctx
                    motor = MotorHibridoLocal(st.session_state.diccionario)
                    filas = []
                    for c in cuentas:
                        if c.monto is None and not c.codigo:
                            continue
                        if not _cuenta_tiene_saldo_seleccionado(c):
                            continue
                        if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()):
                            continue
                        monto_seleccionado, campos_periodos = (
                            _campos_periodos_cuenta(c)
                        )
                        cuenta_clasificacion = replace(
                            c, monto=monto_seleccionado,
                        )
                        _t0_legacy = time.perf_counter()
                        r = motor.clasificar(
                            cuenta_clasificacion, company_giro_norm,
                        )
                        _t1_legacy = (time.perf_counter() - _t0_legacy) * 1000
                        nombre_contable = _nombre_con_contexto(
                            c.nombre, c.jerarquia_contable,
                        )
                        origen_efectivo = _origen_efectivo(
                            c.origen_columna, monto_seleccionado, nombre_contable,
                        )
                        if (r.get('codigo_estandar') and
                                not _codigo_compatible_con_origen(
                                    r['codigo_estandar'], c.origen_columna,
                                    monto_seleccionado,
                                    nombre_contable)):
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
                            'nombre_original': c.nombre,
                            'nombre_normalizado': normalizar_nombre(c.nombre),
                            'monto': monto_seleccionado,
                            'pagina': getattr(c, 'pagina', None),
                            'respaldo_documental': getattr(c, 'respaldo_documental', None),
                            **{col: float(c.montos_columnas.get(col, 0.0) or 0.0) for col in RAW_MONETARY_COLUMNS},
                            **campos_periodos,
                            'columnas_derivadas': ', '.join(c.columnas_derivadas),
                            'jerarquia_contable': c.jerarquia_contable or '',
                            'origen_columna': c.origen_columna.value,
                            'origen_columna_efectiva': origen_efectivo,
                            'es_total': c.es_total,
                            'codigo_clasificado': r['codigo_estandar'] or '',
                            'metodo': r['metodo'],
                            'confianza': r['confianza'],
                            'requiere_revision': (
                                r['requiere_revision'] or bool(c.columnas_derivadas)
                            ),
                            'nota': r.get('nota_regla_especial', ''),
                            'confianza_extraccion': c.confianza_extraccion,
                            'origen_columna_display': _etiqueta_origen(
                                c.origen_columna, monto_seleccionado, nombre_contable,
                            ),
                            'nombre_revision_usuario': '',
                            'tipo_revision': '',
                            'origen': _origen_desde_metodo_display(r['metodo']),
                            'regla': r['metodo'],
                            'evidencia': r.get('nota_regla_especial', '') or r['metodo'],
                            'tiempo_clasificacion': round(_t1_legacy, 3),
                        })
                    df_file = pd.DataFrame(filas)
                    df_file.attrs["document_family"] = st.session_state.document_families.get(
                        archivo.name, "",
                    )
                    st.session_state.resultados[archivo.name] = df_file
                    actor_leg = _authenticated_actor()
                    actor_leg_org = str(getattr(actor_leg, "organization_id", "") or "").strip() or None
                    doc_rut_raw = (getattr(doc_meta_raw, "rut", "") or "").strip()
                    doc_rut_norm = normalizar_rut(doc_rut_raw)
                    file_leg_company = getattr(meta_indiv, "razon_social", "") or ""
                    file_leg_period = getattr(meta_indiv, "periodo", "") or str(st.session_state.get("company_anio", ""))

                    file_digest = dict(st.session_state.get("document_scope_confirmed") or ()).get(archivo.name)
                    if not file_digest and hasattr(archivo, "getvalue"):
                        file_digest = hashlib.sha256(archivo.getvalue()).hexdigest()
                    confirmed_scope = dict(st.session_state.get("document_scope_confirmed") or ())
                    scope_confirmed = bool(archivo.name in confirmed_scope and confirmed_scope[archivo.name] == file_digest)
                    confirmed_rut_norm = normalizar_rut(st.session_state.get("company_rut", ""))
                    rut_matches = bool(doc_rut_norm and confirmed_rut_norm and doc_rut_norm == confirmed_rut_norm)
                    is_session_confirmed = (st.session_state.get("metadata_confirmada") is True)

                    is_verified = bool(
                        is_session_confirmed
                        and doc_rut_norm
                        and rut_matches
                        and scope_confirmed
                        and actor_leg_org
                    )

                    _detectar_bloquear_colision_homonimo(archivo.name, file_digest, actor_leg_org)
                    st.session_state.setdefault("file_metadata", {})[archivo.name] = {
                        "rut": doc_rut_norm,
                        "company_name": file_leg_company.strip(),
                        "period": file_leg_period,
                        "organization_id": actor_leg_org,
                        "file_digest": file_digest,
                        "verified": True if is_verified else False,
                    }
                    _vincular_certificacion_contenido(
                        st.session_state.get("extraction_certifications", {}).get(archivo.name), df_file)
                    _registrar_evento_auditoria(
                        "Recertificación", archivo.name,
                        "Certificación vinculada a la versión exacta de las filas extraídas",
                        df_file.attrs.get("certification_binding", {}).get("digest", ""), df_file,
                    )

                    # SHADOW MODE — homologación comparativa contra motor legacy
                    if SHADOW_MODE and Path(archivo.name).suffix.lower() == '.pdf':
                        import tempfile
                        from pipeline.homologation_pipeline import HomologationPipeline
                        from shadow.shadow_logger import ShadowLogger
                        tmp_shadow = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                        try:
                            tmp_shadow.write(archivo.read())
                            tmp_shadow.close()
                            sh_path = Path(tmp_shadow.name)
                            hp_shadow = HomologationPipeline()
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
        hp = HomologationPipeline() if archivos_nuevos else None
        for archivo in archivos_nuevos:
            if archivo.name not in st.session_state.resultados:
                with st.spinner(f"Clasificando cuentas de {archivo.name}..."):
                    _t0 = time.perf_counter()
                    lineas_encabezado = _extraer_lineas_encabezado(archivo)
                    doc_meta_raw = extraer_metadata(lineas_encabezado)
                    meta_indiv = _aplicar_metadata_confirmada(
                        deepcopy(doc_meta_raw)
                    )
                    st.session_state.metadata_files[archivo.name] = meta_indiv

                    if archivo.name in st.session_state.extraction_resolved:
                        cuentas = st.session_state.extraction_resolved.pop(archivo.name)
                        doc_ctx = st.session_state.document_intel.get(archivo.name)
                    else:
                        cuentas, doc_ctx = _extraer_cuentas(archivo)
                    st.session_state.document_intel[archivo.name] = doc_ctx
                    total_cuentas = len(cuentas)
                    filas = []
                    clasificadas = 0
                    learning_hits = 0
                    fallback_count = 0

                    for c in cuentas:
                        if c.monto is None and not c.codigo:
                            continue
                        if not _cuenta_tiene_saldo_seleccionado(c):
                            continue
                        if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()):
                            continue
                        monto_seleccionado, campos_periodos = _campos_periodos_cuenta(c)
                        cuenta_clasificacion = replace(c, monto=monto_seleccionado)
                        ab = AccountAdapter.from_cuenta_raw(cuenta_clasificacion)
                        interp = BalanceInterpreter(ab)
                        classification_amount = interp.classification_amount
                        if (
                            classification_amount is None
                            and monto_seleccionado is not None
                            and c.montos_periodos
                            and not c.es_total
                        ):
                            classification_amount = float(monto_seleccionado)
                        nombre_contable = _nombre_con_contexto(
                            c.nombre, c.jerarquia_contable,
                        )
                        origen_efectivo = _origen_efectivo(
                            c.origen_columna, classification_amount, nombre_contable,
                        )
                        account_tipo = _resolver_tipo_cuenta(origen_efectivo, c.codigo)
                        if (origen_efectivo == 'pasivo'
                                and _es_contra_activo(nombre_contable)):
                            account_tipo = 'ACTIVO'
                        if _es_partida_patrimonial(nombre_contable):
                            account_tipo = 'PATRIMONIO'
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
                            classification = hp._classify_account(
                                ab.account_code,
                                ab.account_name,
                                account_tipo=account_tipo,
                                account_section=c.seccion_contable,
                                account_hierarchy=c.jerarquia_contable,
                            )
                            tiempo_clasif_ms = round((time.perf_counter() - _t0_clasif) * 1000, 3)
                            adjustment = hp._rule_processor.aplicar(
                                nombre_cuenta=ab.account_name,
                                codigo_clasificado=classification.get("standard_code") or "",
                                monto=classification_amount,
                                origen_columna=c.origen_columna,
                            )
                            final_code = (
                                adjustment.codigo_final if adjustment.aplica
                                else classification.get("standard_code")
                            )
                            if (final_code and
                                    not _codigo_compatible_con_origen(
                                        final_code, c.origen_columna,
                                        classification_amount, nombre_contable)):
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
                                or bool(c.columnas_derivadas)
                            )
                            nota = adjustment.nota if adjustment.aplica else ""
                            clasif_evidencia = classification.get("reason", "")
                            clasif_origen = _origen_desde_clasif(classification, ab.account_name, hp)
                            if metodo.startswith("learning_"):
                                learning_hits += 1
                            else:
                                fallback_count += 1

                        filas.append({
                            'linea': c.linea,
                            'codigo_original': c.codigo or '',
                            'nombre_original': c.nombre,
                            'nombre_normalizado': normalizar_nombre(c.nombre),
                            'monto': monto_seleccionado,
                            'pagina': getattr(c, 'pagina', None),
                            'respaldo_documental': getattr(c, 'respaldo_documental', None),
                            **{col: float(c.montos_columnas.get(col, 0.0) or 0.0) for col in RAW_MONETARY_COLUMNS},
                            **campos_periodos,
                            'columnas_derivadas': ', '.join(c.columnas_derivadas),
                            'jerarquia_contable': c.jerarquia_contable or '',
                            'origen_columna': c.origen_columna.value,
                            'origen_columna_efectiva': origen_efectivo,
                            'es_total': c.es_total,
                            'codigo_clasificado': codigo_clasificado,
                            'metodo': metodo,
                            'confianza': confianza,
                            'requiere_revision': requiere_revision,
                            'nota': nota,
                            'confianza_extraccion': c.confianza_extraccion,
                            'origen_columna_display': _etiqueta_origen(
                                c.origen_columna, classification_amount, nombre_contable),
                            'nombre_revision_usuario': '',
                            'tipo_revision': '',
                            'origen': clasif_origen,
                            'regla': metodo,
                            'evidencia': clasif_evidencia,
                            'tiempo_clasificacion': tiempo_clasif_ms,
                        })

                    df_file = pd.DataFrame(filas)
                    df_file.attrs["document_family"] = st.session_state.document_families.get(
                        archivo.name, "",
                    )
                    st.session_state.resultados[archivo.name] = df_file
                    actor_new = _authenticated_actor()
                    actor_new_org = str(getattr(actor_new, "organization_id", "") or "").strip() or None
                    doc_rut_raw = (getattr(doc_meta_raw, "rut", "") or "").strip()
                    doc_rut_norm = normalizar_rut(doc_rut_raw)
                    file_new_company = getattr(meta_indiv, "razon_social", "") or ""
                    file_new_period = getattr(meta_indiv, "periodo", "") or str(st.session_state.get("company_anio", ""))

                    file_digest = dict(st.session_state.get("document_scope_confirmed") or ()).get(archivo.name)
                    if not file_digest and hasattr(archivo, "getvalue"):
                        file_digest = hashlib.sha256(archivo.getvalue()).hexdigest()
                    confirmed_scope = dict(st.session_state.get("document_scope_confirmed") or ())
                    scope_confirmed = bool(archivo.name in confirmed_scope and confirmed_scope[archivo.name] == file_digest)
                    confirmed_rut_norm = normalizar_rut(st.session_state.get("company_rut", ""))
                    rut_matches = bool(doc_rut_norm and confirmed_rut_norm and doc_rut_norm == confirmed_rut_norm)
                    is_session_confirmed = (st.session_state.get("metadata_confirmada") is True)

                    is_verified = bool(
                        is_session_confirmed
                        and doc_rut_norm
                        and rut_matches
                        and scope_confirmed
                        and actor_new_org
                    )

                    _detectar_bloquear_colision_homonimo(archivo.name, file_digest, actor_new_org)
                    st.session_state.setdefault("file_metadata", {})[archivo.name] = {
                        "rut": doc_rut_norm,
                        "company_name": file_new_company.strip(),
                        "period": file_new_period,
                        "organization_id": actor_new_org,
                        "file_digest": file_digest,
                        "verified": True if is_verified else False,
                    }
                    _vincular_certificacion_contenido(
                        st.session_state.get("extraction_certifications", {}).get(archivo.name), df_file)
                    _registrar_evento_auditoria(
                        "Recertificación", archivo.name,
                        "Certificación vinculada a la versión exacta de las filas extraídas",
                        df_file.attrs.get("certification_binding", {}).get("digest", ""), df_file,
                    )

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
        propagar_entre_balances_seguro(
            st.session_state.resultados,
            metadatos_archivos=st.session_state.get("file_metadata"),
        )
        st.session_state['propagation_done'] = True


    with st.sidebar:
        st.divider()
        st.subheader("📁 Balances Cargados")
        for name in nombres_subidos:
            df_f = st.session_state.resultados.get(name)
            if df_f is not None and not df_f.empty:
                pendientes_f = _pendientes_revision(df_f)
                n_pendientes = len(pendientes_f)
                if n_pendientes > 0:
                    st.caption(f"🔸 `{name}` ({n_pendientes} pendientes)")
                else:
                    st.caption(f"✅ `{name}` (completo)")
            else:
                st.caption(f"⏳ `{name}` (procesando)")

        st.write("")
        archivo_activo_name = st.selectbox(
            "Ver y validar balance:", options=nombres_subidos,
            index=0 if nombres_subidos else None, key="archivo_activo_select"
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
        if archivo_activo_name in st.session_state.extraction_pending:
            _mostrar_etapa_correccion_extraccion(archivo_activo, archivo_activo_name)
        else:
            st.warning(f"No se extrajeron cuentas del archivo {archivo_activo_name}.")
        st.stop()

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        razon_social = getattr(st.session_state, "company_razon", "—")
        rut_empresa = getattr(st.session_state, "company_rut", "—")
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
        giro_empresa = getattr(st.session_state, "company_giro", "—")
        c3.markdown(f"**Giro** \n{giro_empresa or '—'}")
        c4.markdown(f"**Archivo Activo** \n`{archivo_activo_name}`")

    _mostrar_advertencias_auxiliares(
        st.session_state.extraction_certifications.get(archivo_activo_name)
    )

    # Sprint 31 — Información del documento (análisis documental, solo lectura)
    _doc_ctx = st.session_state.document_intel.get(archivo_activo_name)
    if _doc_ctx is not None:
        _mostrar_informacion_documento(_doc_ctx)

    st.markdown("""
    <style>
        /* Split-view sticky visor */
        [data-testid="column"]:first-child:has(.document-visor-anchor) {
            position: -webkit-sticky !important;
            position: sticky !important;
            top: 2rem !important;
            max-height: calc(100vh - 3rem) !important;
            overflow-y: auto !important;
            z-index: 10;
        }
        .document-visor-anchor {
            position: sticky;
            top: 0;
        }
    </style>
    <div class="document-visor-anchor"></div>
    """, unsafe_allow_html=True)

    col_visor, col_trabajo = st.columns([1, 1], gap="medium")

    with col_visor:
        try:
            _visor_documento(archivo_activo)
        except (NameError, Exception):
            pass

    with col_trabajo:
        tab_km = "🧠 Knowledge Manager"
        vistas = [
            "📈 Resumen", "🔍 Cola de Revisión", "📋 Balance Normalizado",
            "📚 Diccionario", "🧠 Aprendizaje", "📊 Analytics",
            "📖 Conocimiento Documental", "📈 Inteligencia del Dataset",
            tab_km,
        ]
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
            contenido = _contenido_para_extraer(archivo)
            with pdfplumber.open(BytesIO(contenido)) as pdf:
                texto = pdf.pages[0].extract_text() or ""
            lineas = texto.split('\n')[:40]
            if any(re.search(r"(?:19|20)\d{2}", linea) for linea in lineas):
                return lineas

            # Los estados auditados suelen ser PDFs escaneados. La selección
            # de períodos ocurre antes del parseo principal, por lo que el
            # encabezado necesita un OCR breve de la primera página elegida.
            png = render_page(contenido, 1)
            with tempfile.TemporaryDirectory() as tmpdir:
                imagen = Path(tmpdir) / "encabezado.png"
                imagen.write_bytes(png)
                texto_ocr = ocr_pagina(imagen, 0, psm=6)
            return texto_ocr.split('\n')[:60]
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
        nueva_c = replace(
            cuenta,
            montos_columnas=amounts,
            monto=amount,
            origen_columna=origin,
            es_total=bool(row.get("total", cuenta.es_total)),
            columnas_derivadas=derived,
        )
        if hasattr(cuenta, "respaldo_documental"):
            setattr(nueva_c, "respaldo_documental", getattr(cuenta, "respaldo_documental"))
        if hasattr(cuenta, "pagina"):
            setattr(nueva_c, "pagina", getattr(cuenta, "pagina"))
        if getattr(cuenta, "es_subtotal_manual", False):
            setattr(nueva_c, "es_subtotal_manual", True)
        corrected.append(nueva_c)
    certification = certificar_extraccion_columnas(
        corrected, metodo="revision_humana_8_columnas",
    )
    return corrected, certification


def _crear_cuenta_manual_extraccion(
    cuentas: list[CuentaRaw], *, codigo: str, nombre: str,
    montos: dict[str, float], es_total: bool = False,
    pagina: int | None = None,
    respaldo_documental: dict[str, Any] | None = None,
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
    c = CuentaRaw(
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
    if pagina is not None:
        setattr(c, "pagina", pagina)
    if respaldo_documental is not None:
        setattr(c, "respaldo_documental", respaldo_documental)
    return c


def _ejecutar_incorporar_cuenta_omitida(
    filename: str,
    *,
    codigo: str,
    nombre: str,
    pagina: int | None,
    ubicacion: str,
    montos: dict[str, Any],
    confirmacion_explicita: bool,
    es_total: bool = False,
) -> tuple[bool, str, CuentaRaw | None]:
    """Valida documentalmente e incorpora una cuenta omitida por la extracción.

    Exige:
    1. Actor acreditado con rol 'analyst' y pertenencia a la organización del documento.
    2. Identidad y huella del archivo real, rechazando sustituciones.
    3. Ubicación física comprobable en el documento (página, celda o coordenada).
    4. Confirmación explícita de importes para las ocho columnas.
    5. Cifras numéricas finitas distinguiendo ausencia de cero confirmado.
    6. No permite que subtotales manuales actúen como controles de certificación.
    7. No contamina el snapshot prístino de extracción.
    """
    if not str(nombre or "").strip():
        return False, "El nombre de la cuenta es obligatorio.", None

    # 1. Actor acreditado y organización (Condición 1)
    act = _authenticated_actor()
    if act is None or not getattr(act, "actor_id", None):
        return False, "Operación rechazada: no existe un actor autenticado en la sesión.", None
    try:
        require_role(act, "analyst")
    except Exception as exc:
        return False, f"Operación rechazada: el actor no cuenta con el rol 'analyst' autorizado ({exc}).", None

    file_meta = (st.session_state.get("file_metadata") or {}).get(filename, {})
    doc_org = file_meta.get("organization_id")
    actor_org = getattr(act, "organization_id", None)
    if doc_org and actor_org != doc_org:
        return False, f"Operación rechazada: la organización del actor ('{actor_org}') no coincide con la del archivo ('{doc_org}').", None

    # 2. Huella del archivo real (Condición 2)
    expected_digest = file_meta.get("file_digest")
    source_path = file_meta.get("source_path") or (st.session_state.get("file_sources") or {}).get(filename)
    try:
        real_hash, status_archivo = _obtener_huella_archivo_real(
            filename,
            expected_digest=expected_digest,
            organization_id=doc_org or actor_org,
            source_path=source_path,
            actor=act,
        )
    except AuthorizationDenied:
        return False, f"Operación rechazada: actor no autorizado para acceder al archivo '{filename}'.", None

    if not real_hash or status_archivo != "disponible":
        return False, f"Operación rechazada: no se pudo verificar la huella del archivo real '{filename}'.", None

    # 3. Ubicación física comprobable
    ubicacion_str = str(ubicacion or "").strip()
    if (pagina is None or (isinstance(pagina, (int, float)) and pagina <= 0)) and not ubicacion_str:
        return False, "Debe indicar la ubicación comprobable en el documento (página o celda/coordenada).", None

    # 4. Confirmación explícita (Condición 6)
    if not confirmacion_explicita:
        return False, "Debe confirmar explícitamente los importes según el documento original.", None

    # 5. Distinguir ausencia de valor de cero confirmado y validar finitud (Condición 6)
    montos_confirmados: dict[str, float] = {}
    for col in RAW_MONETARY_COLUMNS:
        if col not in montos or montos[col] is None:
            return False, f"Falta el importe para la columna requerida '{col}'. No se permite inventar ceros para forzar cuadratura.", None
        try:
            val = float(montos[col])
        except (ValueError, TypeError):
            return False, f"El importe en la columna '{col}' no es un número válido.", None
        if not math.isfinite(val):
            return False, f"El importe en la columna '{col}' no es un número finito.", None
        montos_confirmados[col] = val

    # 6. Prevención de subtotales manuales que actúen como controles independientes (Condición 7)
    es_subtotal = bool(es_total or _es_control_o_subtotal(nombre))

    respaldo_documental = {
        "archivo": filename,
        "file_name": filename,
        "file_digest": real_hash,
        "pagina": pagina,
        "ubicacion": ubicacion_str or (f"Página {pagina}" if pagina is not None else ""),
        "actor": act.actor_id,
        "actor_id": act.actor_id,
        "actor_org": actor_org or "",
        "confirmacion_explicita": True,
        "importes": montos_confirmados,
        "importes_confirmados": montos_confirmados,
        "es_subtotal": es_subtotal,
        "timestamp": datetime.now().astimezone().isoformat(),
    }

    # Asegurar snapshot prístino e inmutable en classified_source_snapshots (Condición 3)
    resultado = st.session_state.get("extraction_pending", {}).get(filename)
    if "classified_source_snapshots" not in st.session_state or filename not in st.session_state["classified_source_snapshots"]:
        if resultado and hasattr(resultado, "cuentas"):
            st.session_state.setdefault("classified_source_snapshots", {})[filename] = {
                "scope": _alcance_snapshot_clasificado(filename),
                "accounts": deepcopy(resultado.cuentas),
                "periods": list(getattr(resultado, "periodos_detectados", []) or []),
                "currencies": list(getattr(resultado, "monedas_detectadas", []) or []),
                "metodo": getattr(getattr(resultado, "certificacion_extraccion", None), "metodo", "revision_humana_8_columnas"),
            }

    cuentas_actuales = resultado.cuentas if (resultado and hasattr(resultado, "cuentas")) else []

    nueva_cuenta = _crear_cuenta_manual_extraccion(
        cuentas_actuales,
        codigo=codigo,
        nombre=nombre,
        montos=montos_confirmados,
        es_total=es_subtotal,
        pagina=pagina,
        respaldo_documental=respaldo_documental,
    )
    if es_subtotal:
        setattr(nueva_cuenta, "es_subtotal_manual", True)

    return True, "", nueva_cuenta


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
    """Corrección en split-view sticky con documento original a la izquierda."""
    col_visor, col_diag = st.columns([1, 1], gap="medium")
    with col_visor:
        _visor_documento(archivo, altura="72vh", mostrar_titulo=True)
    with col_diag:
        _mostrar_correccion_extraccion(filename)


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
    """Editor seguro previo a homologación para extracciones no certificadas."""
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
        st.warning(
            "La extracción no produjo filas tabulares editables. Revise que las "
            "páginas seleccionadas contengan el detalle de cuentas. El problema "
            "puede deberse al formato de la tabla y no necesariamente al OCR."
        )
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
            codigo_manual = st.text_input("Código original, si existe", key=f"manual_code_{filename}")
            nombre_manual = st.text_input("Nombre de la cuenta", key=f"manual_name_{filename}")
            loc_c1, loc_c2 = st.columns(2)
            pagina_manual = loc_c1.number_input(
                "Página en el documento", min_value=1, step=1, value=1, key=f"manual_page_{filename}",
            )
            ubicacion_manual = loc_c2.text_input(
                "Ubicación / Coordenada / Celda", value="", key=f"manual_loc_{filename}",
                help="Ej: Celda B14, fila 28 o coordenada física",
            )
            m1, m2, m3, m4 = st.columns(4)
            debitos_manual = m1.number_input("Debe", value=0.0, format="%.2f", key=f"man_deb_{filename}")
            creditos_manual = m2.number_input("Haber", value=0.0, format="%.2f", key=f"man_cred_{filename}")
            saldo_deudor_manual = m3.number_input("Saldo deudor", value=0.0, format="%.2f", key=f"man_sdeud_{filename}")
            saldo_acreedor_manual = m4.number_input("Saldo acreedor", value=0.0, format="%.2f", key=f"man_sacred_{filename}")
            c1m, c2m, c3m, c4m = st.columns(4)
            activo_manual = c1m.number_input("Activo", value=0.0, format="%.2f", key=f"man_act_{filename}")
            pasivo_manual = c2m.number_input("Pasivo", value=0.0, format="%.2f", key=f"man_pas_{filename}")
            perdida_manual = c3m.number_input("Pérdidas", value=0.0, format="%.2f", key=f"man_per_{filename}")
            ganancia_manual = c4m.number_input("Ganancias", value=0.0, format="%.2f", key=f"man_gan_{filename}")
            total_manual = st.checkbox(
                "Es subtotal, resultado o total impreso (no se sumará al detalle ni autocertifica)",
                key=f"man_tot_{filename}",
            )
            confirm_manual = st.checkbox(
                "Confirmo explícitamente los importes según el documento original",
                value=False,
                key=f"man_conf_{filename}",
            )
            agregar_manual = st.form_submit_button("Agregar cuenta a la extracción")
        if agregar_manual:
            ok, msg, nueva = _ejecutar_incorporar_cuenta_omitida(
                filename,
                codigo=codigo_manual,
                nombre=nombre_manual,
                pagina=int(pagina_manual) if pagina_manual else None,
                ubicacion=ubicacion_manual,
                montos={
                    "debitos": debitos_manual, "creditos": creditos_manual,
                    "saldo_deudor": saldo_deudor_manual, "saldo_acreedor": saldo_acreedor_manual,
                    "activo": activo_manual, "pasivo": pasivo_manual,
                    "perdida": perdida_manual, "ganancia": ganancia_manual,
                },
                confirmacion_explicita=confirm_manual,
                es_total=total_manual,
            )
            if not ok:
                st.error(msg)
            else:
                _persist_streamlit_correction(
                    filename,
                    row_reference=f"manual-row:{nueva.linea}",
                    classification_code=(
                        "TOTAL_CONTROL" if total_manual else "UNCLASSIFIED"
                    ),
                    action="manual-row",
                )
                resultado.cuentas.append(nueva)
                filas_recert = []
                for c in resultado.cuentas:
                    r_c = {
                        "linea": c.linea,
                        "codigo_original": c.codigo or "",
                        "nombre_original": c.nombre,
                        "cuenta": c.nombre,
                        "pagina": getattr(c, "pagina", None),
                        "es_total": c.es_total,
                        "total": c.es_total,
                        **{col: float(c.montos_columnas.get(col, 0.0) or 0.0) for col in RAW_MONETARY_COLUMNS},
                    }
                    if hasattr(c, "respaldo_documental"):
                        r_c["respaldo_documental"] = getattr(c, "respaldo_documental")
                    filas_recert.append(r_c)
                df_recert = pd.DataFrame(filas_recert)
                nueva_cert = _recertificar_balance_columnas(
                    filename, df_recert, resultado.certificacion_extraccion,
                )
                resultado.certificacion_extraccion = nueva_cert
                st.session_state.setdefault("extraction_certifications", {})[filename] = nueva_cert
                revisions[filename] = revision + 1
                if nueva_cert.estado == "certificada":
                    st.success("Cuenta incorporada y respaldada. Extracción certificada exitosamente.")
                else:
                    st.info("Cuenta incorporada con respaldo documental. Revise la certificación actualizada.")
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
        _persist_streamlit_correction(
            filename,
            row_reference=f"extraction-batch:{revision}",
            classification_code="PENDING_REVIEW",
            action="extraction-batch",
        )
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
        st.session_state.setdefault("document_families", {})[archivo.name] = document_family(
            {"requirio_ocr": bool(getattr(resultado, "requirio_ocr", False))},
            [{"codigo_original": cuenta.codigo or "", "is_total": cuenta.es_total}
             for cuenta in resultado.cuentas],
        )
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
        _guardar_snapshot_clasificado(archivo.name, resultado)
        st.session_state.setdefault("extraction_certifications", {})[archivo.name] = certificacion
        if certificacion is not None and certificacion.estado == 'fallida' and not _permite_clasificar_extraccion(certificacion):
            st.error(
                "La extracción no reproduce los totales impresos del balance. "
                "El documento no será homologado hasta corregir filas o columnas."
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
        st.session_state.setdefault("document_families", {})[archivo.name] = document_family(
            {"requirio_ocr": False},
            [{"codigo_original": cuenta.codigo or "", "is_total": cuenta.es_total}
             for cuenta in cuentas],
        )
        certificacion = certificar_extraccion_columnas(
            cuentas, metodo="excel_8_columns",
        )
        st.session_state.setdefault("extraction_certifications", {})[archivo.name] = certificacion
        st.session_state.setdefault("classified_source_snapshots", {})[archivo.name] = {
            "scope": ("excel", (archivo.name,), ()),
            "accounts": deepcopy(cuentas),
            "periods": [],
            "currencies": [],
            "metodo": "excel_8_columns",
        }

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


def _mostrar_informacion_documento(ctx) -> None:
    """Sección solo-lectura INFORMACIÓN DEL DOCUMENTO (Sprint 31, FASE 5).

    Muestra la metadata del análisis documental ANTES de los resultados.
    No modifica ningún resultado: si `ctx` no está disponible, no dibuja nada.
    """
    if ctx is None:
        return
    try:
        info = ctx.ui_summary()
    except Exception:
        return

    with st.container(border=True):
        st.markdown("#### 🧾 INFORMACIÓN DEL DOCUMENTO")
        cols = st.columns(4)
        items = [
            ("Documento", info.get("Documento", "—")),
            ("Formato", info.get("Formato", "—")),
            ("Columnas", info.get("Columnas", "—")),
            ("Layout", info.get("Layout", "—")),
            ("OCR", info.get("OCR", "—")),
            ("Extractor", info.get("Extractor", "—")),
            ("Confianza", info.get("Confianza", "—")),
            ("Familia", info.get("Familia", "—")),
        ]
        for i, (label, value) in enumerate(items):
            with cols[i % 4]:
                st.markdown(f"**{label}**  \n`{value}`")


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
    metricas = account_metrics(df.to_dict('records'))
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    total = metricas['accounts_total_detail']
    requiere_rev = metricas['accounts_pending_review']
    confianza_prom = df.loc[df['confianza'] > 0, 'confianza'].mean()

    col1.metric("Detalle", total)
    col2.metric("Específicas", metricas['accounts_classified_specific'])
    col3.metric("Residuales", metricas['accounts_classified_residual'])
    col4.metric("Sin clasificar", metricas['accounts_unclassified'])
    col5.metric("Pendientes", requiere_rev)
    col6.metric("Controles", metricas['accounts_controls'])
    st.caption(
        f"Confianza promedio: {confianza_prom:.0%}. Las categorías residuales, "
        "incluido origin_fallback, no se contabilizan como clasificación específica."
        if pd.notna(confianza_prom) else
        "Las categorías residuales no se contabilizan como clasificación específica."
    )
    familia = df.attrs.get("document_family") or document_family(
        {"ocr": False}, df.to_dict('records'),
    )
    cobertura_especifica = (
        metricas['accounts_classified_specific'] / total if total else 1.0
    )
    st.caption(
        f"Familia documental: {familia}. Cobertura específica: {cobertura_especifica:.1%}."
    )

    st.subheader("Cobertura por método de clasificación")
    dist = df['metodo'].apply(lambda m: m.split('+')[0]).value_counts()
    dist_df = dist.reset_index()
    dist_df.columns = ['Método', 'Cuentas']
    dist_df['Procedencia'] = dist_df['Método'].map(method_provenance)
    
    METODO_LABELS = {
        'codigo': '0 · Código de cuenta', 'diccionario_exacto': '1 · Diccionario (exacto)',
        'diccionario_fuzzy': '1b · Diccionario (fuzzy)', 'regla_regex': '2 · Reglas regex',
        'sin_clasificar': '3-4 · Pendiente (embeddings/LLM)',
    }
    dist_df['Método'] = dist_df['Método'].map(lambda m: METODO_LABELS.get(m, m))
    st.dataframe(dist_df, use_container_width=True, hide_index=True)


def _registrar_decision(archivo_nombre, idx, row, codigo, motivo):
    """Historial de esta sesión; Neon conserva además la validación y sugerencia previa."""
    st.session_state.setdefault('historial_decisiones', []).append({
        'Archivo': archivo_nombre, 'Fila': str(idx),
        'Cuenta': row.get('nombre_original', ''),
        'Clasificación anterior': row.get('codigo_clasificado', ''),
        'Clasificación nueva': codigo, 'Método anterior': row.get('metodo', ''),
        'Motivo': motivo, 'Fecha': datetime.now().isoformat(timespec='seconds'),
        **_actor_audit_fields(),
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
    opciones_codigo = [''] + opciones_clasificacion(catalogo) + ['➕ NUEVA CATEGORÍA', '🚫 NO INCLUIR']

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
            alcance_lote = st.radio("Alcance", ["Solo este caso", "Agregar al diccionario"], index=1, horizontal=True, key=f"lote_alcance_{doc_key}")
        with bc3:
            st.write(""); st.write("")
            confirmar_lote = st.button(f"✅ Confirmar lote ({n_sel})", disabled=(n_sel == 0 or not cat_lote), use_container_width=True)

        if confirmar_lote and n_sel > 0 and cat_lote:
            codigo_lote = '__EXCLUIR__' if cat_lote == '🚫 NO INCLUIR' else (cat_lote if cat_lote != '➕ NUEVA CATEGORÍA' else None)
            if codigo_lote:
                incompatibles = [
                    idx_lote for idx_lote in st.session_state.lote_seleccion
                    if codigo_lote != '__EXCLUIR__'
                    and not _codigo_compatible_con_origen(
                        codigo_lote,
                        df.at[idx_lote, 'origen_columna'],
                        df.at[idx_lote, 'monto'],
                        _nombre_contable_fila(df.loc[idx_lote]),
                        catalogo,
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
                    _persist_streamlit_correction(
                        archivo_nombre, row_reference=idx_lote,
                        classification_code=codigo_lote,
                        action="classification-batch",
                    )
                    _registrar_decision(archivo_nombre, idx_lote, df.loc[idx_lote].copy(), codigo_lote, 'Confirmación en lote')
                    nombre_orig = df.at[idx_lote, 'nombre_original']
                    codigo_sugerido = df.at[idx_lote, 'codigo_clasificado'] or None
                    metodo_sugerido = df.at[idx_lote, 'metodo']
                    confianza_sugerida = float(df.at[idx_lote, 'confianza'])
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'codigo_clasificado'] = codigo_lote
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'metodo'] = 'validacion_humana_lote'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'confianza'] = 1.0
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'requiere_revision'] = False
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'origen'] = 'Manual'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'regla'] = 'validacion_humana_lote'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'evidencia'] = 'Asignación en lote por analista'
                    validaciones_lote.append({
                        'account_name': nombre_orig,
                        'validated_code': codigo_lote,
                        'source': 'validacion_humana_lote',
                        'add_to_dictionary': "diccionario" in alcance_lote,
                        'suggested_code': codigo_sugerido,
                        'suggested_method': metodo_sugerido,
                        'suggested_confidence': confianza_sugerida,
                        'source_file': archivo_nombre,
                    })
                    if "diccionario" in alcance_lote:
                        entrada = {'cuenta_original': nombre_orig, 'codigo_estandar': codigo_lote, 'fuente': 'validacion_humana_lote'}
                        st.session_state.diccionario.append(entrada)
                        st.session_state.correcciones.append(entrada)
                    if "diccionario" in alcance_lote:
                        propagar_clasificacion_resultados(nombre_orig, codigo_lote, 'validacion_humana_lote_propagada')
                    procesados += 1
                persistido = _persistir_validaciones_lote(validaciones_lote)
                fallback_json_lote = not persistido
                if ("diccionario" in alcance_lote and fallback_json_lote
                        and _legacy_json_fallback_allowed()):
                    _write_legacy_packaged_dictionary(st.session_state.diccionario)
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
    st.caption(
        f"Mostrando {start + 1}–{min(start + page_size, len(pendientes))} "
        f"de {len(pendientes)} cuentas · página {page} de {total_pages}."
    )
    st.markdown("""
    <style>
        /* Compact review rows */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 6px 10px !important;
            margin-bottom: 4px !important;
            background-color: #ffffff;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }
        /* Ticket chip buttons */
        div[data-testid="column"] button[kind="secondary"] {
            padding: 2px 6px !important;
            min-height: 28px !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    visible = pendientes.iloc[start:start + page_size]
    for idx, row in visible.iterrows():
        seleccionada = idx in st.session_state.lote_seleccion
        with st.container(border=seleccionada):
            c0, c1, c2 = st.columns([0.3, 4.2, 4.5])
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
                        col_extraida, row.get('monto'), _nombre_contable_fila(row),
                    ),
                ).upper()
                etiqueta_columna = _etiqueta_origen(
                    col_extraida, row.get('monto'), _nombre_contable_fila(row),
                )
                badge_bg = {
                    'ACTIVO': '#1E90FF', 'PASIVO': '#FF8C00',
                    'PERDIDA': '#DC143C', 'GANANCIA': '#2E8B57',
                }.get(col_actual, '#6B7280')

                monto_val = row['monto']
                monto_str = f"${monto_val:,.0f}" if pd.notna(monto_val) else "—"
                monto_color = '#1d4ed8' if pd.notna(monto_val) and monto_val > 0 else ('#b91c1c' if pd.notna(monto_val) and monto_val < 0 else '#64748b')

                st.markdown(
                    f"<div style='display:flex; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:2px;'>"
                    f"<span style='background:{badge_bg}; color:white; padding:1px 7px; border-radius:4px; font-size:0.75em; font-weight:700;'>{etiqueta_columna}</span>"
                    f"<span style='font-weight:700; font-size:0.95em; color:#0f172a;'>{_nombre_mostrar(row)}</span>"
                    f"<span style='font-weight:700; font-family:monospace; font-size:0.95em; color:{monto_color}; margin-left:auto;'>{monto_str}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                detalles = []
                actual_cod = row.get('codigo_clasificado')
                detalles.append(f"Actual: <b>{actual_cod}</b>" if actual_cod else "<i>Sin clasificar</i>")
                if row.get('metodo'):
                    detalles.append(f"{row.get('metodo')}")
                if pd.notna(row.get('confianza')) and float(row.get('confianza') or 0) > 0:
                    detalles.append(f"{float(row.get('confianza')):.0%}")
                if pd.notna(row.get('monto_periodo_anterior')):
                    detalles.append(f"Ant: ${float(row['monto_periodo_anterior']):,.0f}")
                st.markdown(f"<div style='font-size:0.75em; color:#64748b; margin-bottom:4px;'>{' · '.join(detalles)}</div>", unsafe_allow_html=True)

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
                    periodos_edicion = _periodos_seleccionados()
                    etiqueta_monto = f"Monto ({periodos_edicion[0]})" if periodos_edicion else "Monto"
                    nuevo_monto = st.number_input(etiqueta_monto, value=float(monto_inicial), format="%.0f", key=f"ed_monto_{doc_key}_{idx}")

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
                                codigo_final, nueva_nat, nuevo_monto,
                                _nombre_con_contexto(
                                    nuevo_nombre, row.get('jerarquia_contable'),
                                ), catalogo,
                            ):
                                st.error('La corrección contradice la clasificación actual. Seleccione una categoría compatible antes de guardarla.')
                                st.stop()
                            _persist_streamlit_correction(
                                archivo_nombre, row_reference=idx,
                                classification_code=(
                                    codigo_final or "PENDING_REVIEW"
                                ),
                                action="account-edit",
                            )
                            _registrar_decision(archivo_nombre, idx, row.copy(), codigo_final, 'Corrección de datos de la cuenta')
                            df_mod.at[idx, 'nombre_original'] = nuevo_nombre
                            df_mod.at[idx, 'nombre_revision_usuario'] = ''
                            df_mod.at[idx, 'origen_columna'] = nueva_nat.lower()
                            _aplicar_edicion_monto_periodos(
                                df_mod, idx, nuevo_monto,
                                periodo_activo=_periodos_seleccionados()[0] if _periodos_seleccionados() else None,
                                periodos=_periodos_seleccionados(),
                            )
                            if nueva_nat.lower() in df_mod.columns:
                                df_mod.at[idx, nueva_nat.lower()] = nuevo_monto
                                old_nat_col = str(row.get('origen_columna') or '').lower()
                                if old_nat_col and old_nat_col != nueva_nat.lower() and old_nat_col in df_mod.columns:
                                    df_mod.at[idx, old_nat_col] = 0.0
                            df_mod.attrs.pop("certification_binding", None)

                            df_mod.at[idx, 'origen_columna_efectiva'] = _origen_efectivo(
                                nueva_nat, nuevo_monto, _nombre_con_contexto(
                                    nuevo_nombre, row.get('jerarquia_contable'),
                                ))
                            df_mod.at[idx, 'origen_columna_display'] = _etiqueta_origen(
                                nueva_nat, nuevo_monto, _nombre_con_contexto(
                                    nuevo_nombre, row.get('jerarquia_contable'),
                                ))
                            if codigo_final:
                                df_mod.at[idx, 'codigo_clasificado'] = codigo_final
                            df_mod.at[idx, 'metodo'] = 'manual_revision'
                            df_mod.at[idx, 'confianza'] = 1.0
                            df_mod.at[idx, 'requiere_revision'] = True
                            df_mod.at[idx, 'tipo_revision'] = 'correccion_extraccion'
                            df_mod.at[idx, 'origen'] = 'Manual'
                            df_mod.at[idx, 'regla'] = 'manual_revision'
                            df_mod.at[idx, 'evidencia'] = 'Corrección manual de extracción'
                            _registrar_evento_auditoria(
                                "Invalidación de certificación", archivo_nombre,
                                "Edición manual de monto u origen",
                                f"Fila {idx}; cuenta {nuevo_nombre}", df_mod,
                            )
                            # Una corrección de extracción es local y debe confirmarse.
                            st.toast(f"'{nuevo_nombre[:35]}' corregida ✅", icon="✅")
                        else:
                            _persist_streamlit_correction(
                                archivo_nombre, row_reference=idx,
                                classification_code=(
                                    str(row.get('codigo_clasificado') or '')
                                    or "UNCLASSIFIED"
                                ),
                                action="display-name-edit",
                            )
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
                            _nombre_contable_fila(row), catalogo)):
                    sugerido = ''
                st.write(f"Sugerido: **{sugerido or '(ninguno)'}**")

                requiere_decision = (
                    bool(row.get('requiere_revision', False)) or not sugerido
                )
                if sugerido and not requiere_decision and not mostrar_todas:
                    st.caption(
                        "Clasificación automática confirmada · "
                        f"{float(row.get('confianza') or 0.0):.0%}"
                    )
                alternativas = (
                    _alternativas_revision(
                        nombre=_nombre_contable_fila(row),
                        sugerido=sugerido,
                        confianza=float(row.get('confianza') or 0.0),
                        origen_columna=row.get('origen_columna'),
                        monto=row.get('monto'),
                        catalogo=catalogo,
                        motor=motor,
                    )
                    if requiere_decision or mostrar_todas else []
                )
                if alternativas:
                    st.caption("Alternativas compatibles · selección asistida")
                    if (
                        len(alternativas) > 1
                        and alternativas[0]["codigo"] != alternativas[1]["codigo"]
                        and alternativas[0]["score"] - alternativas[1]["score"] <= 0.05
                    ):
                        st.warning(
                            "Señales contradictorias: los dos primeros candidatos "
                            "tienen relevancia similar. Requiere criterio del analista."
                        )
                    # Render chips horizontally side-by-side
                    alt_cols = st.columns(min(len(alternativas), 3))
                    for i_alt, alt in enumerate(alternativas[:3]):
                        with alt_cols[i_alt]:
                            score_pct = f"{alt['score']:.0%}"
                            chip_label = f"✓ {alt['codigo']} ({score_pct})"
                            selection_key = f"sel_{doc_key}_{idx}"
                            st.button(
                                chip_label,
                                key=f"usar_alt_{doc_key}_{idx}_{alt['codigo']}",
                                use_container_width=True,
                                help=f"{alt['codigo']} — {alt['nombre']} · Relevancia: {score_pct}",
                                on_click=_asignar_estado_widget,
                                args=(selection_key, alt['codigo']),
                            )
                    with st.expander("Ver fundamento de las sugerencias"):
                        for alternativa in alternativas:
                            st.caption(
                                f"{alternativa['codigo']} · {alternativa['fuente']} · "
                                f"{alternativa['evidencia']}"
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
                            _nombre_contable_fila(row), catalogo)
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
                         "Agregar al diccionario (aplica a casos futuros iguales)"],
                        index=1 if row.get('requiere_revision', False) else 0,
                        key=f"alc_{doc_key}_{idx}", horizontal=True
                    )
                else:
                    alcance = "Solo para este caso"

                if st.button("✅ Confirmar", key=f"btn_{doc_key}_{idx}"):
                    codigo_final = None

                    if es_nueva_cat:
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
                            if candidato in catalogo:
                                nombre_existente = catalogo[candidato].get(
                                    'nombre_estandar', candidato,
                                )
                                st.error(
                                    f'El código {candidato} ya existe como '
                                    f'“{nombre_existente}”. Use un código libre. '
                                    'No se puede redefinir una categoría '
                                    'existente desde esta cuenta.'
                                )
                                st.stop()
                            if not candidato.startswith(prefijos[nuevo_cat]):
                                st.error(
                                    'El código debe comenzar con el prefijo '
                                    f'{prefijos[nuevo_cat]} correspondiente a '
                                    f'{nuevo_cat}. La categoría no fue creada.'
                                )
                                st.stop()
                            if not _codigo_compatible_con_origen(candidato, row.get('origen_columna'), row.get('monto'), _nombre_contable_fila(row), {**catalogo, candidato: nueva_entrada}):
                                st.error('La nueva categoría contradice la naturaleza de esta cuenta. No fue creada.')
                                st.stop()
                            catalogo[nuevo_codigo.strip().upper()] = nueva_entrada
                            if (not _persistir_catalogo(nueva_entrada)
                                    and _legacy_json_fallback_allowed()):
                                _write_legacy_packaged_catalog(catalogo)
                            codigo_final = nuevo_codigo.strip().upper()
                            st.toast(f"Nueva categoría '{nuevo_nombre_cat}' ({codigo_final}) creada ✨", icon="🆕")
                        else:
                            st.error("Debes ingresar código y nombre.")

                    elif seleccion == '🚫 NO INCLUIR':
                        _persist_streamlit_correction(
                            archivo_nombre, row_reference=idx,
                            classification_code="__EXCLUIR__",
                            action="classification-exclude",
                        )
                        _registrar_decision(archivo_nombre, idx, row.copy(), '__EXCLUIR__', 'Exclusión por analista')
                        st.session_state.resultados[archivo_nombre].at[idx, 'codigo_clasificado'] = '__EXCLUIR__'
                        st.session_state.resultados[archivo_nombre].at[idx, 'metodo'] = 'excluido_analista'
                        st.session_state.resultados[archivo_nombre].at[idx, 'confianza'] = 1.0
                        st.session_state.resultados[archivo_nombre].at[idx, 'requiere_revision'] = False
                        if "diccionario" in alcance:
                            entrada_exclusion = {
                                'cuenta_original': _nombre_mostrar(row),
                                'codigo_estandar': '__EXCLUIR__',
                                'fuente': 'excluido_analista'
                            }
                            st.session_state.diccionario.append(entrada_exclusion)
                        persistido = _persistir_validacion(
                            nombre=_nombre_mostrar(row), codigo='__EXCLUIR__',
                            fuente='excluido_analista',
                            agregar_diccionario="diccionario" in alcance,
                            sugerido=row['codigo_clasificado'] or None,
                            metodo=row['metodo'], confianza=float(row['confianza']),
                            archivo=archivo_nombre,
                        )
                        if ("diccionario" in alcance and not persistido
                                and _legacy_json_fallback_allowed()):
                            _write_legacy_packaged_dictionary(st.session_state.diccionario)
                        if "diccionario" in alcance:
                            propagar_clasificacion_resultados(row['nombre_original'], '__EXCLUIR__', 'excluido_analista_propagado')
                        st.session_state.lote_seleccion.discard(idx)
                        st.toast(f"'{_nombre_mostrar(row)[:35]}' excluida", icon="🚫")
                        st.rerun()

                    elif seleccion:
                        codigo_final = seleccion

                    if codigo_final:
                        if not _codigo_compatible_con_origen(codigo_final, row.get('origen_columna'), row.get('monto'), _nombre_contable_fila(row), catalogo):
                            st.error('La categoría contradice la naturaleza contable. No se cambió la cuenta ni se guardó en el diccionario.')
                            st.stop()
                        _persist_streamlit_correction(
                            archivo_nombre, row_reference=idx,
                            classification_code=codigo_final,
                            action="classification-individual",
                        )
                        _registrar_decision(archivo_nombre, idx, row.copy(), codigo_final, 'Confirmación individual')
                        st.session_state.resultados[archivo_nombre].at[idx, 'codigo_clasificado'] = codigo_final
                        st.session_state.resultados[archivo_nombre].at[idx, 'metodo'] = 'validacion_humana'
                        st.session_state.resultados[archivo_nombre].at[idx, 'confianza'] = 1.0
                        st.session_state.resultados[archivo_nombre].at[idx, 'requiere_revision'] = False
                        st.session_state.lote_seleccion.discard(idx)
                        persistido = _persistir_validacion(
                            nombre=row['nombre_original'], codigo=codigo_final,
                            fuente='validacion_humana',
                            agregar_diccionario="diccionario" in alcance,
                            sugerido=row['codigo_clasificado'] or None,
                            metodo=row['metodo'], confianza=float(row['confianza']),
                            archivo=archivo_nombre,
                        )
                        if "diccionario" in alcance:
                            nuevo_dic = {
                                'cuenta_original': row['nombre_original'],
                                'codigo_estandar': codigo_final,
                                'fuente': 'validacion_humana'
                            }
                            st.session_state.diccionario.append(nuevo_dic)
                            st.session_state.correcciones.append(nuevo_dic)
                            if not persistido and _legacy_json_fallback_allowed():
                                _write_legacy_packaged_dictionary(st.session_state.diccionario)
                            st.toast(f"'{_nombre_mostrar(row)[:35]}' → {codigo_final} guardado 📚", icon="✅")
                        else:
                            st.toast(f"'{_nombre_mostrar(row)[:35]}' → {codigo_final} (solo este caso)", icon="✅")
                        if "diccionario" in alcance:
                            propagar_clasificacion_resultados(row['nombre_original'], codigo_final, 'validacion_humana_propagada')
                        st.rerun()


def _diagnosticar_cuadratura(
        df: pd.DataFrame, agrupado: pd.DataFrame,
        clasificadas: pd.DataFrame, tolerancia: float = 1_000) -> dict:
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
                row.get('monto'), _nombre_contable_fila(row),
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


def _control_emision(
        df, catalogo, diagnostico, quality_control=None,
        extraction_certification=None):
    """Control independiente, sin mutar decisiones ni importes del analista."""
    incidencias = []
    for idx, row in df[~df['es_total']].iterrows():
        codigo = str(row.get('codigo_clasificado') or '')
        monto = pd.to_numeric(row.get('monto'), errors='coerce')
        motivos = []
        if row.get('requiere_revision', False):
            motivos.append('Decisión pendiente de confirmación')
        if pd.isna(monto) or not math.isfinite(float(monto)):
            motivos.append('Importe ausente o no válido')
        elif monto == 0:
            if motivos:
                incidencias.append({
                    'Fila': str(idx), 'Cuenta': row.get('nombre_original', ''),
                    'Clasificación': codigo,
                    'Columna original': row.get('origen_columna', ''),
                    'Monto': monto, 'Qué corregir': '; '.join(motivos),
                })
            continue
        if codigo == '__EXCLUIR__':
            motivos.append('Cuenta con saldo excluida; revise si debe reincorporarse')
        elif codigo not in catalogo:
            motivos.append('Sin clasificación válida')
        elif not _codigo_compatible_con_origen(
            codigo, row.get('origen_columna'), monto, _nombre_contable_fila(row), catalogo,
        ):
            motivos.append('La categoría contradice la naturaleza efectiva de la cuenta')
        if motivos:
            incidencias.append({
                'Fila': str(idx), 'Cuenta': row.get('nombre_original', ''),
                'Clasificación': codigo, 'Columna original': row.get('origen_columna', ''),
                'Monto': monto, 'Qué corregir': '; '.join(motivos),
            })
    resultado = conciliar_resultados(df.to_dict('records'), catalogo)
    motivos = list(resultado['problemas'])
    if incidencias:
        motivos.append(f'{len(incidencias)} cuenta(s) requieren corregir o confirmar su clasificación')
    if not diagnostico['cuadra']:
        motivos.append('Activo no coincide con Pasivo más Patrimonio')
    estado_certificacion = getattr(
        extraction_certification, 'estado', None,
    )
    if estado_certificacion != 'certificada':
        if estado_certificacion:
            motivos.append(
                'La extracción documental no está certificada '
                f'(estado: {estado_certificacion})'
            )
        else:
            motivos.append('No existe una certificación documental válida para emitir')
        motivos.extend(
            str(reason) for reason in (
                getattr(extraction_certification, 'razones', None) or []
            ) if str(reason) not in motivos
        )
    elif not _certificacion_coincide_contenido(extraction_certification, df):
        motivos.append('La certificación documental no corresponde al contenido actual; recertifique después de editar montos u origen de columnas')
    if quality_control is not None:
        razones_calidad = list(getattr(quality_control, 'reasons', None) or [])
        marcadores_duros = ('sin clasificación', 'no cuadra', 'crítico', 'critico', 'rechaz', 'fallid', 'incompatib')
        bloqueadores_duros = [r for r in razones_calidad if any(m in str(r).lower() for m in marcadores_duros)]
        if not getattr(quality_control, 'export_allowed', False):
            motivos.extend(razones_calidad or ['El control posterior no autoriza la emisión definitiva'])
        elif bloqueadores_duros:
            motivos.extend(bloqueadores_duros)
    return {'definitivo': not motivos, 'motivos': motivos,
            'incidencias': pd.DataFrame(incidencias), 'resultado': resultado}


def _valor_fila_periodo(row: pd.Series, periodo: str, posicion: int):
    """Recupera el importe elegido para un período sin alterar la fila fuente."""
    columna = f"monto_periodo_{periodo}"
    if columna in row.index and pd.notna(row.get(columna)):
        return float(row[columna])
    alias = "monto_periodo_actual" if posicion == 0 else "monto_periodo_anterior"
    if alias in row.index and pd.notna(row.get(alias)):
        return float(row[alias])
    if posicion == 0 and pd.notna(row.get("monto")):
        return float(row["monto"])
    return None


def _saldo_codigo_agrupado(agrupado: pd.DataFrame, codigo: str) -> float:
    valores = pd.to_numeric(
        agrupado.loc[agrupado["codigo_clasificado"] == codigo, "monto_total"],
        errors="coerce",
    ).fillna(0)
    return float(valores.sum())


def _gestionar_reclasificacion_depreciacion(
        reportes_periodo: list[dict], archivo_nombre: str) -> tuple[dict, list[str]]:
    """Solicita la apertura desde notas cuando ER.07 no fue extraída."""
    ajustes_documento = st.session_state.setdefault(
        "depreciation_reclassifications", {},
    ).setdefault(archivo_nombre, {})
    ajustes_aplicables = {}
    pendientes = []
    periodos_sin_depreciacion = []
    for reporte in reportes_periodo:
        agrupado = reporte["agrupado"]
        tiene_resultados = any(
            str(codigo).startswith("ER.")
            for codigo in agrupado.get("codigo_clasificado", pd.Series(dtype=str))
        )
        depreciacion = abs(_saldo_codigo_agrupado(agrupado, "ER.07"))
        if tiene_resultados and depreciacion <= 0.01:
            periodos_sin_depreciacion.append(reporte)
    if not periodos_sin_depreciacion:
        return ajustes_aplicables, pendientes

    st.subheader("Depreciación del ejercicio informada en notas")
    st.info(
        "No se detectó una cuenta separada de Depreciación y Amortización en uno o "
        "más períodos. Confirme que no corresponde o informe su distribución. El "
        "ajuste sólo abre el gasto: no cambia la utilidad del período."
    )
    st.caption(
        "Depreciación Acumulada (ANC.01.01) es una contra-cuenta del activo y no "
        "sustituye la Depreciación del Ejercicio (ER.07) del estado de resultados."
    )
    opciones = {
        "pending": "Pendiente de revisar en las notas",
        "none": "No existe depreciación por separar en este período",
        "notes": "Ingresar depreciación incluida en otras cuentas",
    }
    for reporte in periodos_sin_depreciacion:
        periodo = str(reporte["periodo"])
        guardado = ajustes_documento.get(periodo, {})
        identificador = hashlib.sha256(
            f"{archivo_nombre}:{periodo}:depreciacion".encode()
        ).hexdigest()[:14]
        with st.container(border=True):
            st.markdown(f"#### Período {periodo}")
            modo_guardado = guardado.get("mode", "pending")
            modo = st.selectbox(
                "Tratamiento",
                list(opciones),
                index=list(opciones).index(modo_guardado)
                if modo_guardado in opciones else 0,
                format_func=opciones.get,
                key=f"depreciation_mode_{identificador}",
            )
            total = costo = administracion = 0.0
            if modo == "notes":
                c1, c2, c3 = st.columns(3)
                total = c1.number_input(
                    "Depreciación total del período",
                    min_value=0.0, value=float(guardado.get("total", 0)),
                    step=1.0, format="%.2f",
                    key=f"depreciation_total_{identificador}",
                )
                costo = c2.number_input(
                    "Incluida en Costo de Ventas",
                    min_value=0.0, value=float(guardado.get("cost_of_sales", 0)),
                    step=1.0, format="%.2f",
                    key=f"depreciation_cost_{identificador}",
                )
                administracion = c3.number_input(
                    "Incluida en Gastos de Administración",
                    min_value=0.0, value=float(guardado.get("administration", 0)),
                    step=1.0, format="%.2f",
                    key=f"depreciation_admin_{identificador}",
                )
                st.caption(
                    "La suma de las dos porciones debe coincidir con la depreciación "
                    "total y no puede superar el saldo de la cuenta de origen."
                )
            guardar = st.button(
                "Guardar tratamiento", key=f"save_depreciation_{identificador}",
            )
            if guardar:
                errores = []
                if modo == "pending":
                    ajustes_documento.pop(periodo, None)
                elif modo == "none":
                    ajustes_documento[periodo] = {"mode": "none", "decision": "No existe o no aplica depreciación por separar", "evidence": "Confirmación manual tras revisar el estado y sus notas", "source": "manual_confirmation", "decided_at": datetime.now().astimezone().isoformat(), "analyst": _actor_audit_fields()["Actor"]}
                    _registrar_evento_auditoria(
                        "Decisión de depreciación", archivo_nombre,
                        "No existe o no aplica depreciación por separar", f"Período {periodo}")
                else:
                    errores = validar_reclasificacion_depreciacion(
                        total, costo, administracion,
                        costo_ventas_disponible=_saldo_codigo_agrupado(
                            reporte["agrupado"], "ER.02",
                        ),
                        gastos_administracion_disponible=_saldo_codigo_agrupado(
                            reporte["agrupado"], "ER.04",
                        ),
                    )
                    if not errores:
                        ajustes_documento[periodo] = {
                            "mode": "notes", "total": float(total),
                            "cost_of_sales": float(costo),
                            "administration": float(administracion),
                            "source": "manual_notes",
                            "decision": "Depreciación informada desde notas",
                            "evidence": "Monto y distribución ingresados manualmente desde notas",
                            "decided_at": datetime.now().astimezone().isoformat(),
                            "analyst": _actor_audit_fields()["Actor"],
                        }
                        _registrar_evento_auditoria(
                            "Decisión de depreciación", archivo_nombre,
                            "Depreciación informada desde notas",
                            f"Período {periodo}; total {float(total):.2f}; costo {float(costo):.2f}; administración {float(administracion):.2f}",
                        )
                if errores:
                    for error in errores:
                        st.error(error)
                else:
                    st.rerun()

        guardado = ajustes_documento.get(periodo)
        if guardado and guardado.get("mode") == "none" and not guardado.get("decided_at"):
            guardado.update({"decision": "No existe o no aplica depreciación por separar", "evidence": "Confirmación manual tras revisar el estado y sus notas", "source": "manual_confirmation", "decided_at": datetime.now().astimezone().isoformat(), "analyst": _actor_audit_fields()["Actor"]})
            _registrar_evento_auditoria(
                "Decisión de depreciación", archivo_nombre,
                guardado["decision"], f"Período {periodo}",
            )
        if not guardado:
            pendientes.append(
                f"Período {periodo}: falta confirmar la depreciación del ejercicio"
            )
        elif guardado.get("mode") == "notes":
            errores = validar_reclasificacion_depreciacion(
                guardado.get("total"), guardado.get("cost_of_sales"),
                guardado.get("administration"),
                costo_ventas_disponible=_saldo_codigo_agrupado(
                    reporte["agrupado"], "ER.02",
                ),
                gastos_administracion_disponible=_saldo_codigo_agrupado(
                    reporte["agrupado"], "ER.04",
                ),
            )
            if errores:
                pendientes.extend(f"Período {periodo}: {error}" for error in errores)
            else:
                ajustes_aplicables[periodo] = guardado
                st.success(
                    f"Período {periodo}: se separarán {guardado['total']:,.2f}; "
                    f"{guardado['cost_of_sales']:,.2f} desde Costo de Ventas y "
                    f"{guardado['administration']:,.2f} desde Gastos de Administración."
                )
        else:
            ajustes_aplicables[periodo] = guardado
            st.caption(f"Período {periodo}: confirmado sin depreciación por separar.")
    return ajustes_aplicables, pendientes


def _preparar_periodo_reporte(
        df: pd.DataFrame, catalogo: dict, periodo: str, posicion: int) -> dict:
    """Genera clasificación, conciliación y cuadratura independientes por período."""
    periodo_df = df.copy()
    periodo_df["monto"] = periodo_df.apply(
        lambda row: _valor_fila_periodo(row, periodo, posicion), axis=1,
    )
    clasificadas = periodo_df[
        (periodo_df["codigo_clasificado"] != "")
        & (periodo_df["codigo_clasificado"] != "__EXCLUIR__")
        & (~periodo_df["es_total"])
    ].copy()
    clasificadas = _con_saldo_relevante(clasificadas)
    clasificadas["monto"] = pd.to_numeric(
        clasificadas["monto"], errors="coerce",
    ).fillna(0)
    clasificadas["monto_presentacion"] = clasificadas.apply(
        lambda row: _monto_presentacion(
            row["codigo_clasificado"], row["monto"], row["nombre_original"],
            row.get("origen_columna"), catalogo,
        ), axis=1,
    )
    agrupado = clasificadas.groupby("codigo_clasificado").agg(
        monto_total=("monto_presentacion", "sum"),
        num_cuentas=("nombre_original", "count"),
    ).reset_index()
    agrupado["nombre_estandar"] = agrupado["codigo_clasificado"].map(
        lambda code: catalogo.get(code, {}).get("nombre_estandar", code)
    )
    agrupado["categoria"] = agrupado["codigo_clasificado"].map(
        lambda code: catalogo.get(code, {}).get("categoria", "")
    )
    conciliacion = conciliar_resultados(periodo_df.to_dict("records"), catalogo)
    resultado_periodo = conciliacion["resultado_origen"]
    if resultado_periodo is not None:
        existentes = set(agrupado["codigo_clasificado"])
        derivados = []
        for codigo_resultado in ("ER.11", "PAT.04"):
            if codigo_resultado in existentes:
                continue
            info = catalogo.get(codigo_resultado, {})
            derivados.append({
                "codigo_clasificado": codigo_resultado,
                "monto_total": (
                    conciliacion["resultado_homologado"] or 0.0
                    if codigo_resultado == "ER.11" else resultado_periodo
                ),
                "num_cuentas": 0,
                "nombre_estandar": info.get("nombre_estandar", codigo_resultado),
                "categoria": info.get("categoria", ""),
            })
        if derivados:
            agrupado = pd.concat([agrupado, pd.DataFrame(derivados)], ignore_index=True)
    diagnostico = _diagnosticar_cuadratura(periodo_df, agrupado, clasificadas)
    return {
        "periodo": periodo, "df": periodo_df, "clasificadas": clasificadas,
        "agrupado": agrupado, "conciliacion": conciliacion,
        "diagnostico": diagnostico,
    }


def _tab_balance(df: pd.DataFrame, catalogo: dict, archivo_nombre: str):
    st.button('Revisar o cambiar clasificaciones', on_click=_solicitar_revision_completa,
              args=(archivo_nombre,), use_container_width=True)
    periodos = _periodos_seleccionados()
    reportes_periodo = [
        _preparar_periodo_reporte(df, catalogo, periodo, posicion)
        for posicion, periodo in enumerate(periodos)
    ]
    ajustes_depreciacion, pendientes_depreciacion = (
        _gestionar_reclasificacion_depreciacion(reportes_periodo, archivo_nombre)
    )
    for reporte in reportes_periodo:
        ajuste = ajustes_depreciacion.get(str(reporte["periodo"]))
        reporte["agrupado"] = apply_depreciation_reclassification(
            reporte["agrupado"], ajuste,
        )
        reporte["agrupado"]["nombre_estandar"] = reporte["agrupado"][
            "codigo_clasificado"
        ].map(lambda code: catalogo.get(code, {}).get("nombre_estandar", code))
        reporte["agrupado"]["categoria"] = reporte["agrupado"][
            "codigo_clasificado"
        ].map(lambda code: catalogo.get(code, {}).get("categoria", ""))
        reporte["agrupado"]["num_cuentas"] = pd.to_numeric(
            reporte["agrupado"].get("num_cuentas", 0), errors="coerce",
        ).fillna(0)
    principal = reportes_periodo[0]
    clasificadas = principal["clasificadas"]
    if clasificadas.empty:
        st.info("No hay cuentas clasificadas todavía.")
        return
    agrupado = principal["agrupado"].copy()
    conciliacion = principal["conciliacion"]
    resultado_periodo = conciliacion['resultado_origen']
    period_columns = [(
        periodos[0] if len(periodos) > 1 else "Importe", "monto_total",
    )]
    for reporte in reportes_periodo[1:]:
        amount_column = f"monto_total_{reporte['periodo']}"
        period_columns.append((reporte["periodo"], amount_column))
        valores = reporte["agrupado"][["codigo_clasificado", "monto_total"]].rename(
            columns={"monto_total": amount_column}
        )
        agrupado = agrupado.merge(valores, on="codigo_clasificado", how="outer")
        agrupado["nombre_estandar"] = agrupado.apply(
            lambda row: row.get("nombre_estandar")
            if pd.notna(row.get("nombre_estandar")) else catalogo.get(
                row["codigo_clasificado"], {}
            ).get("nombre_estandar", row["codigo_clasificado"]), axis=1,
        )
        agrupado["categoria"] = agrupado.apply(
            lambda row: row.get("categoria")
            if pd.notna(row.get("categoria")) else catalogo.get(
                row["codigo_clasificado"], {}
            ).get("categoria", ""), axis=1,
        )
        agrupado["num_cuentas"] = agrupado["num_cuentas"].fillna(0)
        agrupado["monto_total"] = agrupado["monto_total"].fillna(0)
        agrupado[amount_column] = agrupado[amount_column].fillna(0)

    orden_cat = ['activo_corriente', 'activo_no_corriente', 'pasivo_corriente', 'pasivo_no_corriente', 'patrimonio', 'resultado']
    agrupado['orden'] = agrupado['categoria'].map(lambda c: orden_cat.index(c) if c in orden_cat else 99)
    agrupado = agrupado.sort_values(['orden', 'codigo_clasificado'])

    diagnostico = principal["diagnostico"]
    _mostrar_resumen_cuadratura(diagnostico, df, archivo_nombre)
    if len(reportes_periodo) > 1:
        st.subheader("Control comparativo por período")
        st.dataframe(pd.DataFrame([{
            "Período": reporte["periodo"],
            "Activo": reporte["diagnostico"]["activo"],
            "Pasivo + Patrimonio": reporte["diagnostico"]["pasivo_patrimonio"],
            "Diferencia": reporte["diagnostico"]["diferencia"],
            "Cuadratura": "Cuadra" if reporte["diagnostico"]["cuadra"] else "Requiere revisión",
            "Resultado original": reporte["conciliacion"]["resultado_origen"],
            "Resultado homologado": reporte["conciliacion"]["resultado_homologado"],
            "Diferencia resultado": reporte["conciliacion"]["diferencia"],
        } for reporte in reportes_periodo]), hide_index=True, use_container_width=True)
    from pipeline.operational_quality import analyze_operational_quality
    enforce_export = os.environ.get(
        "QUALITY_CONTROL_ENFORCE_EXPORT", "true",
    ).strip().lower() in {"1", "true", "yes", "on"}
    quality_control = analyze_operational_quality(
        df, balance_squared=diagnostico['cuadra'],
        enforce_export=enforce_export,
    )
    st.session_state.setdefault("quality_controls", {})[archivo_nombre] = quality_control
    _mostrar_control_calidad_operativo(quality_control)

    extraction_certification = st.session_state.get(
        "extraction_certifications", {},
    ).get(archivo_nombre)
    extraction_certification = _recertificar_balance_clasificado(
        archivo_nombre, df, extraction_certification, catalogo=catalogo,
    )
    st.session_state.setdefault("extraction_certifications", {})[archivo_nombre] = extraction_certification
    if (
        extraction_certification is not None
        and getattr(extraction_certification, "metodo", "") == "classified_final_detail"
        and extraction_certification.estado != "certificada"
        and st.button("Verificar detalle clasificado corregido", key=f"verify_classified_{archivo_nombre}")
    ):
        extraction_certification = _recertificar_balance_clasificado(
            archivo_nombre, df, extraction_certification, force=True, catalogo=catalogo,
        )
        st.session_state.extraction_certifications[archivo_nombre] = extraction_certification
    emision = _control_emision(
        df, catalogo, diagnostico, quality_control,
        extraction_certification=extraction_certification,
    )
    comparacion_cuadre = compare_pre_post(
        extraction_certification, df.to_dict('records'),
        late_difference=diagnostico['diferencia'],
        tolerance=diagnostico['tolerancia'],
    )
    if comparacion_cuadre['classification_degradation']:
        emision['definitivo'] = False
        emision['motivos'].append(
            'La extracción cuadraba antes de clasificar, pero el balance homologado no cuadra; '
            'la degradación fue introducida durante la clasificación'
        )
        responsables = comparacion_cuadre['responsible_changes']
        if responsables:
            st.error('La clasificación degradó una cuadratura documental válida.')
            st.dataframe(pd.DataFrame(responsables), hide_index=True, use_container_width=True)
    if pendientes_depreciacion:
        emision["definitivo"] = False
        emision["motivos"].extend(pendientes_depreciacion)
    for reporte in reportes_periodo[1:]:
        if not reporte["diagnostico"]["cuadra"]:
            emision["definitivo"] = False
            emision["motivos"].append(
                f"El período {reporte['periodo']} no cuadra: diferencia "
                f"{reporte['diagnostico']['diferencia']:,.2f}"
            )
        problemas_resultado = reporte["conciliacion"].get("problemas", [])
        if problemas_resultado:
            emision["definitivo"] = False
            emision["motivos"].extend(
                f"Período {reporte['periodo']}: {problema}"
                for problema in problemas_resultado
            )
    motivo_vinculo = next((motivo for motivo in emision["motivos"]
        if "no corresponde al contenido actual" in motivo), None)
    otros_bloqueadores = [motivo for motivo in emision["motivos"] if motivo != motivo_vinculo]
    if motivo_vinculo and not otros_bloqueadores:
        st.warning(
            "El contenido fue editado después de certificarse. Antes de emitir, "
            "confirme que ya comparó las filas corregidas con el documento original."
        )
        if st.button("Recertificar contenido corregido", type="primary"):
            extraction_certification = _ejecutar_recertificar_contenido_corregido(
                archivo_nombre, df, extraction_certification, catalogo=catalogo,
            )
            st.rerun()
    amount_columns = [column for _, column in period_columns]
    income_available = {
        column: reporte["conciliacion"]["resultado_homologado"] is not None
        for reporte, (_, column) in zip(reportes_periodo, period_columns)
    }
    presentacion, formulas_reporte = complete_catalog(
        agrupado, catalogo, income_available, amount_columns=amount_columns,
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
    if emision['definitivo']:
        st.success('Controles de emisión aprobados para este reporte.')
    else:
        st.error('Sólo se permite descargar un BORRADOR. Corrija los motivos antes de emitir el reporte definitivo.')
        st.subheader('Resumen previo a exportación')
        st.dataframe(
            _resumen_bloqueadores_emision(emision['motivos']),
            hide_index=True, use_container_width=True,
        )
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
        columnas_tabla = ['codigo_clasificado', 'nombre_estandar', *amount_columns, 'num_cuentas']
        tabla = sub[columnas_tabla].copy()
        nombres_montos = {column: f"Monto {label}" for label, column in period_columns}
        tabla = tabla.rename(columns={
            'codigo_clasificado': 'Código', 'nombre_estandar': 'Cuenta Estándar',
            'num_cuentas': '# Cuentas Agrupadas', **nombres_montos,
        })
        for nombre_monto in nombres_montos.values():
            tabla[nombre_monto] = tabla[nombre_monto].map(
                lambda value: f"{value:,.2f}" if pd.notna(value) else "No disponible"
            )
        st.dataframe(tabla, use_container_width=True, hide_index=True)
        if cat == 'resultado':
            st.caption('Ingresos positivos y gastos negativos. El resultado neto es un cálculo y no se suma nuevamente al detalle.')
        else:
            st.metric(f"Subtotal", f"{sub['monto_total'].sum():,.0f}")
        st.divider()

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
    
    export_df = presentacion[[
        "codigo_clasificado", "nombre_estandar", *amount_columns, "num_cuentas",
    ]].copy()
    meta = st.session_state.get('metadata_files', {}).get(archivo_nombre)
    unidad = (getattr(meta, 'moneda', None) or 'unidad original')
    report_actor = _authenticated_actor()
    report_identity = _actor_audit_fields()
    report_analyst_name = (
        report_actor.display_name if report_actor is not None else ""
    )
    columnas_exportacion = ["Código", "Cuenta Estándar"] + [
        f"Monto Total ({unidad})" if len(period_columns) == 1
        else f"Monto Total {label} ({unidad})"
        for label, _ in period_columns
    ] + ["# Cuentas Agrupadas"]
    export_df.columns = columnas_exportacion
    export_df['Tipo de fila'] = presentacion['codigo_clasificado'].map(
        lambda c: 'Calculado, no sumar al detalle' if catalogo.get(c, {}).get('clasificable') is False else 'Cuenta'
    )
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        FILA_INICIO_BALANCE = 7
        export_df.to_excel(writer, index=False, sheet_name="Balance Normalizado", startrow=FILA_INICIO_BALANCE - 1)
        _exportar_advertencias_auxiliares(
            writer, st.session_state.get("extraction_certifications", {}).get(archivo_nombre),
        )
        ws = writer.sheets["Balance Normalizado"]
        estado_emision = 'DEFINITIVO' if emision['definitivo'] else 'BORRADOR: REQUIERE REVISIÓN'
        ws['E1'] = 'Estado de emisión'
        ws['F1'] = estado_emision
        ws['F1'].font = Font(bold=True, color='008000' if emision['definitivo'] else 'C00000')
        control_filas = [
            {'Control': 'Estado de emisión', 'Valor': estado_emision},
            {'Control': 'Versión de contenido certificado', 'Valor': getattr(
                extraction_certification, 'contenido_certificado_version', '')},
            {'Control': 'Digest de contenido certificado', 'Valor': getattr(
                extraction_certification, 'contenido_certificado_digest', '')},
            {'Control': 'Resultado según columnas originales', 'Valor': conciliacion['resultado_origen']},
            {'Control': 'Resultado según categorías homologadas', 'Valor': conciliacion['resultado_homologado']},
            {'Control': 'Diferencia de resultado', 'Valor': conciliacion['diferencia']},
            {'Control': 'Diferencia Activo menos Pasivo y Patrimonio', 'Valor': diagnostico['diferencia']},
            {'Control': 'Cuadre temprano disponible', 'Valor': comparacion_cuadre['early']['available']},
            {'Control': 'Cuadre temprano aprobado', 'Valor': comparacion_cuadre['early']['squared']},
            {'Control': 'Degradación introducida por clasificación',
             'Valor': comparacion_cuadre['classification_degradation']},
        ]
        for periodo, ajuste in ajustes_depreciacion.items():
            if ajuste.get('mode') == 'notes':
                control_filas.extend([
                {'Control': f'Depreciación informada desde notas ({periodo})',
                 'Valor': ajuste['total']},
                {'Control': f'Rebaja de Costo de Ventas ({periodo})',
                 'Valor': ajuste['cost_of_sales']},
                {'Control': f'Rebaja de Gastos de Administración ({periodo})',
                 'Valor': ajuste['administration']},
                ])
            else:
                control_filas.append({'Control': f'Decisión sobre depreciación ({periodo})', 'Valor': ajuste.get('decision', 'No existe o no aplica')})
        control_filas += [
            {'Control': 'Pendiente de resolver', 'Valor': m} for m in emision['motivos']
        ]
        pd.DataFrame(control_filas).to_excel(writer, sheet_name='Control de emisión', index=False)
        eventos_auditoria = [
            evento for evento in st.session_state.get('audit_events', [])
            if evento.get('Archivo') == archivo_nombre
        ]
        for evento in df.attrs.get('audit_events', []):
            if evento not in eventos_auditoria:
                eventos_auditoria.append(evento)
        if eventos_auditoria:
            pd.DataFrame(eventos_auditoria).to_excel(
                writer, sheet_name='Auditoría de emisión', index=False,
            )
        if ajustes_depreciacion:
            pd.DataFrame([{'Período': periodo, 'Decisión': ajuste.get('decision', ''),
                'Evidencia': ajuste.get('evidence', ''), 'Fecha/hora': ajuste.get('decided_at', ''),
                'Analista': ajuste.get('analyst', ''), 'Fuente': ajuste.get('source', ''),
                'Depreciación total': ajuste.get('total'), 'Costo de ventas': ajuste.get('cost_of_sales'),
                'Gastos de administración': ajuste.get('administration')}
                for periodo, ajuste in ajustes_depreciacion.items()]).to_excel(
                    writer, sheet_name='Decisiones depreciación', index=False)
        if not emision['incidencias'].empty:
            emision['incidencias'].to_excel(writer, sheet_name='Cuentas a corregir', index=False)
        if comparacion_cuadre['responsible_changes']:
            pd.DataFrame(comparacion_cuadre['responsible_changes']).to_excel(
                writer, sheet_name='Cambios de cuadratura', index=False,
            )
        historial = [h for h in st.session_state.get('historial_decisiones', []) if h['Archivo'] == archivo_nombre]
        if historial:
            pd.DataFrame(historial).to_excel(writer, sheet_name='Decisiones de esta sesión', index=False)

        meta = st.session_state.get("metadata_files", {}).get(archivo_nombre)
        if meta:
            ws["A1"] = "Empresa:";    ws["B1"] = meta.razon_social or ""
            ws["A2"] = "RUT:";       ws["B2"] = meta.rut or ""
            ws["A3"] = "Período:";   ws["B3"] = f'{meta.periodo_desde or ""} al {meta.periodo_hasta or ""}'
            ws["A4"] = "Giro:";      ws["B4"] = meta.giro or ""
            ws["A5"] = "Moneda/unidad:"; ws["B5"] = meta.moneda or ""
            ws["A6"] = "Duración:";  ws["B6"] = (
                f"{meta.numero_meses} meses" if meta.numero_meses else ""
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

        for i, row in enumerate(ws.iter_rows(
                min_row=FILA_INICIO_BALANCE + 1,
                max_row=FILA_INICIO_BALANCE + len(export_df),
                max_col=len(export_df.columns)), start=0):
            if i % 2 == 0:
                for cell in row: cell.fill = PatternFill("solid", fgColor=GRIS)

        fila_sep = FILA_INICIO_BALANCE + len(export_df) + 3

        catalogo_local = catalogo
        detail_indices = pd.Index([])
        for reporte in reportes_periodo:
            detail_indices = detail_indices.union(reporte["clasificadas"].index)
        columnas_base = [
            'codigo_clasificado', 'codigo_original', 'nombre_original',
            'nombre_revision_usuario', 'origen_columna',
            'origen_columna_efectiva', 'metodo', 'confianza',
        ]
        det = df.loc[detail_indices, columnas_base].copy()

        det['nombre_visual'] = det['nombre_revision_usuario'].where(det['nombre_revision_usuario'] != '', det['nombre_original'])
        det['nombre_estandar'] = det['codigo_clasificado'].map(lambda c: catalogo_local.get(c, {}).get('nombre_estandar', c))
        columnas_detalle_periodo = []
        for posicion, periodo in enumerate(periodos):
            extraido = f"monto_extraido_{periodo}"
            normalizado = f"monto_normalizado_{periodo}"
            det[extraido] = df.loc[det.index].apply(
                lambda row, p=periodo, pos=posicion: _valor_fila_periodo(row, p, pos),
                axis=1,
            )
            det[normalizado] = det.apply(
                lambda row, col=extraido: _monto_presentacion(
                    row['codigo_clasificado'], row[col], row['nombre_visual'],
                    row.get('origen_columna'), catalogo,
                ) if pd.notna(row[col]) else None,
                axis=1,
            )
            columnas_detalle_periodo.extend([extraido, normalizado])
        detalle_completo = det[[
            'codigo_clasificado', 'nombre_estandar', 'codigo_original',
            'nombre_visual', 'origen_columna', 'origen_columna_efectiva',
            *columnas_detalle_periodo, 'metodo', 'confianza',
        ]].copy()

        # Reconstrucción de la lógica de ordenamiento nativo
        detalle_completo = detalle_completo.sort_values(
            ['codigo_clasificado', columnas_detalle_periodo[0]],
            key=lambda x: x.abs() if x.dtype.kind in 'fi' else x,
            ascending=[True, False]
        )
        nombres_detalle_periodo = []
        for periodo in periodos:
            if len(periodos) == 1:
                nombres_detalle_periodo.extend(['Monto Extraído', 'Monto Normalizado'])
            else:
                nombres_detalle_periodo.extend([
                    f'Monto Extraído {periodo}', f'Monto Normalizado {periodo}',
                ])
        detalle_completo.columns = [
            'Código Estándar', 'Nombre Estándar',
            'Cód. Original', 'Nombre', 'Columna Extraída', 'Naturaleza Efectiva',
            *nombres_detalle_periodo,
            'Método Clasificación', 'Confianza'
        ]
        if ajustes_depreciacion:
            filas_ajuste = []
            conceptos = (
                ("ER.02", "Ajuste: depreciación separada desde Costo de Ventas",
                 "cost_of_sales", 1.0),
                ("ER.04", "Ajuste: depreciación separada desde Gastos de Administración",
                 "administration", 1.0),
                ("ER.07", "Depreciación del ejercicio informada desde notas",
                 "total", -1.0),
            )
            for codigo, nombre, campo, signo in conceptos:
                fila = {
                    'Código Estándar': codigo,
                    'Nombre Estándar': catalogo.get(codigo, {}).get(
                        'nombre_estandar', codigo,
                    ),
                    'Cód. Original': '', 'Nombre': nombre,
                    'Columna Extraída': 'NOTAS',
                    'Naturaleza Efectiva': 'PÉRDIDA',
                    'Método Clasificación': 'reclasificación manual desde notas',
                    'Confianza': 1.0,
                }
                tiene_importe = False
                for periodo in periodos:
                    ajuste = ajustes_depreciacion.get(str(periodo))
                    valor = float(ajuste.get(campo, 0)) if ajuste else 0.0
                    tiene_importe = tiene_importe or abs(valor) > 0.01
                    if len(periodos) == 1:
                        fila['Monto Extraído'] = None
                        fila['Monto Normalizado'] = signo * valor
                    else:
                        fila[f'Monto Extraído {periodo}'] = None
                        fila[f'Monto Normalizado {periodo}'] = signo * valor
                if tiene_importe:
                    filas_ajuste.append(fila)
            if filas_ajuste:
                detalle_completo = pd.concat(
                    [detalle_completo, pd.DataFrame(filas_ajuste)],
                    ignore_index=True,
                )
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
        processed_at = st.session_state.setdefault("processed_at", {}).setdefault(
            archivo_nombre, datetime.now().astimezone().isoformat(),
        )
        add_report_sheets(
            writer.book, presentacion, formulas_reporte,
            account_detail=detalle_completo,
            start_row=FILA_INICIO_BALANCE, unit=unidad, meta=meta,
            processed_at=processed_at, source_name=archivo_nombre,
            pages=st.session_state.get("document_pages", {}).get(archivo_nombre),
            definitive=emision["definitivo"], reasons=emision["motivos"],
            tolerance=diagnostico["tolerancia"],
            period_columns=period_columns,
            analyst_name=report_analyst_name,
            actor_id=str(report_identity["Actor"] or ""),
            organization_id=str(report_identity["Organización"] or ""),
            roles=tuple(str(role) for role in report_identity["Roles"]),
        )

    buf.seek(0)
    
    meta_state = meta
    razon_fn = (meta_state.razon_social or "empresa").replace(" ", "_")[:30] if meta_state else "empresa"
    rut_fn   = (meta_state.rut or "").replace(".", "").replace("-", "") if meta_state else ""
    nombre_archivo = f"Balance_Unificado-{razon_fn}-{rut_fn}"
    if not emision['definitivo']:
        nombre_archivo = 'BORRADOR-' + nombre_archivo

    report_content = buf.getvalue()
    if emision['definitivo']:
        certified = bool(
            getattr(extraction_certification, "estado", None) == "certificada"
            and _certificacion_coincide_contenido(extraction_certification, df)
        )
        if not certified:
            st.error(
                "El estado visual indicó emisión definitiva, pero no existe una "
                "certificación vinculada al contenido actual. Descarga bloqueada."
            )
            return
        try:
            report_content = _persist_streamlit_definitive_report(
                archivo_nombre, content=report_content,
                report_name=f"{nombre_archivo}.xlsx", certified=certified,
            )
        except (ProcessPersistenceError, AuthorizationDenied, ValueError, OSError) as exc:
            st.error(
                "El reporte certificado no pudo conciliarse con la persistencia "
                f"durable y no se habilitará su descarga: {exc}"
            )
            return

    st.download_button(
        'Descargar reporte definitivo (Excel)' if emision['definitivo'] else 'Descargar BORRADOR con diagnóstico (Excel)', data=report_content,
        file_name=f"{nombre_archivo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
    if _neon_disponible():
        store = _legacy_neon_store()
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
        "(`gold_standard_runtime.db`). La base empaquetada del benchmark no se modifica. "
        "La política predeterminada exige aprobación manual de supervisor, evidencia "
        "mínima, ausencia de conflictos, vigencia definida y capacidad de reversión."
    )
    promotion_actor = _authenticated_actor()
    if promotion_actor is None:
        st.info(
            "No hay un supervisor autenticado. Puede previsualizar, pero no aplicar "
            "una promoción en este modo."
        )
    else:
        st.caption(
            f"Supervisor autenticado: {promotion_actor.actor_id} · "
            f"Organización: {promotion_actor.organization_id}"
        )
    evidence_confirmed = st.checkbox(
        "Confirmo documento fuente, decisión humana y razón de clasificación",
        value=False, key="promotion_evidence",
    )
    approved = st.checkbox(
        "Aprobar manualmente esta promoción", value=False, key="promotion_approved",
    )
    expiration_days = st.number_input(
        "Vigencia antes de revisión", min_value=1, max_value=3650,
        value=DEFAULT_EXPIRATION_DAYS, step=30,
    )
    st.caption(
        "Toda promoción es reversible. Al vencer su vigencia debe revisarse; "
        "los conflictos nunca se promueven automáticamente."
    )
    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        if st.button("🔍 Previsualizar promoción", use_container_width=True):
            try:
                rm = RuntimeManager(_gold_runtime_path())
                res = rm.promote(_gold_benchmark_path(), dry_run=True)
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
                actor = _require_app_role("supervisor")
                if actor is None:
                    raise AuthenticationRequired(
                        "Se requiere un supervisor autenticado incluso en staging; "
                        "no se acepta atribución por texto libre"
                    )
                rm = RuntimeManager(_gold_runtime_path())
                benchmark_path = _gold_benchmark_path()
                preview = rm.promote(benchmark_path, dry_run=True)
                repository = build_persistence().promotions
                record, res = _aplicar_promocion_durable(
                    preview=preview, actor=actor,
                    evidence_confirmed=evidence_confirmed, approved=approved,
                    expiration_days=int(expiration_days), repository=repository,
                    apply_callback=lambda durable_record: rm.promote(
                        benchmark_path, dry_run=False,
                        usuario=actor.actor_id,
                        origen=durable_record.reversal_reference,
                    ),
                    promotion_ids_resolver=lambda _result, durable_record: _runtime_promotion_ids(
                        rm, durable_record,
                    ),
                    source_path=benchmark_path,
                )
                if not record.allowed:
                    st.error(
                        "Promoción bloqueada por política. Evaluación durable "
                        f"{record.evaluation_id}: " + "; ".join(record.decision_reasons)
                    )
                else:
                    assert res is not None
                    _registrar_evento_auditoria(
                        "Promoción de diccionario", "gold_standard_runtime.db",
                        f"Evaluación durable permitida: {record.evaluation_id}",
                        f"Promovidos {res.promoted}; subject {record.subject_id}; "
                        f"expira {record.expires_at.isoformat()}; reversión "
                        f"{record.reversal_reference}",
                    )
                    st.success(
                        f"Promovidos: {res.promoted} · Conflictos omitidos: {res.conflicts} · "
                        f"Duplicados: {res.duplicates} · Evaluación: {record.evaluation_id} · "
                        f"Vigencia hasta: {record.expires_at.isoformat()} · Reversión: "
                        f"{record.reversal_reference}."
                    )
            except (AuthenticationRequired, AuthorizationDenied) as e:
                st.error(f"Promoción bloqueada por autorización: {e}")
            except Exception as e:
                st.error(f"No se pudo aplicar: {e}")
    with pc3:
        st.info(
            "La reversión se ejecuta por cuenta desde Knowledge Manager y conserva "
            "el promotion_id original. No se elimina el runtime completo."
        )


def _km_usuario() -> str:
    actor = _authenticated_actor()
    return actor.actor_id if actor is not None else ""


def _tab_knowledge_manager() -> None:
    """🧠 Knowledge Manager (P5).

    Administra EXCLUSIVAMENTE ``gold_standard_runtime.db`` a través de
    ``RuntimeManager`` (única capa de persistencia). La UI no ejecuta SQL ni
    abre conexiones SQLite. El benchmark (``gold_standard.db``) nunca se escribe.
    Toda acción (promover, rechazar, rollback) requiere aprobación explícita.
    """
    st.subheader("🧠 Knowledge Manager")
    try:
        _require_app_role("supervisor")
    except (AuthenticationRequired, AuthorizationDenied) as exc:
        st.error(f"Knowledge Manager bloqueado por autorización: {exc}")
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

    runtime_path = _gold_runtime_path()
    gold_path = _gold_benchmark_path()
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
    store = _legacy_neon_store()
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
