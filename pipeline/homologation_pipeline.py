from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from adapters.account_adapter import AccountAdapter
from clasificador_codigo_cuenta import ClasificadorCodigo
from config.regex_rules import REGLAS_REGEX, REGLAS_REGEX_FALLBACK_AUDITADAS
from parser_universal import parsear_excel
from interpreters.balance_interpreter import BalanceInterpreter
from learning.engine import LearningEngine
from models.account_balance import AccountBalance
from parser_universal import (
    FormatoCodigo, ParserPDF, ResultadoParseo,
    certificar_extraccion_columnas,
)
from pipeline.cmcc_classifier import CMCCClassifier
from pipeline.features import CMCCFeatureFlags
from persistence.neon_store import NeonKnowledgeStore
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
from reglas_especiales import ProcesadorReglasEspeciales
from decision.engine import DecisionEngine
from semantic.semantic_engine import SemanticEngine
from semantic.matcher import SemanticMatcher
from reporting_integrity import (
    certificar_cuadratura_homologada,
    debe_incorporar_resultado_derivado,
    resultado_final_fuente_certificado,
    resultado_compatible,
)
from delivery_readiness import evaluar_entregabilidad
from format_support import evaluar_formato

logger = logging.getLogger(__name__)

# Debe mantenerse alineado con ``UMBRAL_REVISION`` de la interfaz. Se define
# localmente para que el pipeline reutilizable no dependa de Streamlit.
REVIEW_CONFIDENCE_THRESHOLD = 0.85


def _lineas_revision_extraccion(certificacion: Any) -> set[int] | None:
    """Devuelve las filas que requieren cotejo de extracción.

    ``None`` representa una extracción no certificada sin delimitación segura,
    por lo que todas las cuentas deben quedar en revisión. Un conjunto vacío
    representa una extracción certificada. El conjunto no vacío sólo se acepta
    cuando el parser ya calificó una reconstrucción final acotada para cotejo.
    """
    if getattr(certificacion, "estado", "") == "certificada":
        return set()
    if not bool(getattr(certificacion, "reconstruccion_final_revisable", False)):
        return None
    lineas: set[int] = set()
    for reconstruccion in (
        getattr(certificacion, "reconstrucciones_finales", []) or []
    ):
        try:
            lineas.add(int(reconstruccion["linea"]))
        except (KeyError, TypeError, ValueError):
            # Una certificación que declara ser acotada pero no puede señalar
            # sus filas se trata como no delimitada, nunca como automática.
            return None
    return lineas or None


# Estas equivalencias no son decisiones finales: dependen de que la columna
# física ya haya delimitado la naturaleza de la cuenta y siempre llegan al
# analista como sugerencia. Se mantienen fuera del diccionario porque una
# misma glosa puede cambiar de naturaleza entre ACTIVO y PASIVO.
_SUGERENCIAS_CONTEXTUALES_EXACTAS: dict[tuple[str, str], tuple[str, str]] = {
    ("ACTIVO", "cuenta corriente personal"): (
        "AC.07", "cuenta corriente personal deudora",
    ),
    ("ACTIVO", "anticipo acreedores"): (
        "AC.07", "anticipo a acreedores",
    ),
    ("ACTIVO", "plantaciones en produccion"): (
        "ANC.07", "plantaciones en producción",
    ),
    ("ACTIVO", "utilaje y herramientas"): (
        "ANC.01", "utilaje y herramientas",
    ),
    ("ACTIVO", "cuenta particular bgc"): (
        "AC.06S", "cuenta particular con saldo deudor",
    ),
    ("ACTIVO", "cuenta particular lfb"): (
        "AC.06S", "cuenta particular con saldo deudor",
    ),
    ("PASIVO", "provisiones generales"): (
        "PC.08", "provisiones generales",
    ),
    ("PASIVO", "instituciones previsionales"): (
        "PC.06", "instituciones previsionales por pagar",
    ),
    ("PASIVO", "retenciones personal"): (
        "PC.06", "retenciones de personal",
    ),
    ("PASIVO", "retenciones varias"): (
        "PC.05", "retenciones tributarias varias",
    ),
    ("PERDIDA", "comisiones y gastos bancarios"): (
        "ER.09", "comisiones y gastos bancarios",
    ),
    ("PERDIDA", "diferencia tipo de cambio"): (
        "ER.15", "diferencia de tipo de cambio",
    ),
    ("PERDIDA", "gastos varios"): (
        "ER.18", "gastos varios",
    ),
}


class HomologationPipeline:
    def __init__(
        self,
        db_path: str | Path = "gold_standard.db",
        features: CMCCFeatureFlags | None = None,
    ) -> None:
        self._parser = ParserPDF()
        self._code_classifier = ClasificadorCodigo()
        self._rule_processor = ProcesadorReglasEspeciales()
        self._learning_engine = LearningEngine(db_path)
        self._dictionary: list[dict[str, str]] = self._load_dictionary()
        self._semantic_engine = SemanticEngine()
        self._cmcc_classifier = CMCCClassifier()
        self._decision_engine = DecisionEngine()
        self._features = features or CMCCFeatureFlags.default()
        self._semantic_matcher: SemanticMatcher | None = None
        if self._features.ENABLE_SEMANTIC_MATCHER:
            catalog_path = Path(__file__).resolve().parent.parent / "knowledge" / "concept_catalog.json"
            if catalog_path.exists():
                self._semantic_matcher = SemanticMatcher(str(catalog_path))
            else:
                logger.warning("Concept Catalog not found at %s — SemanticMatcher disabled", catalog_path)

    # ------------------------------------------------------------------
    # Regex fallback — only audited rules with 100% precision (Sprint 28.5A).
    # La lista se define explícitamente en config por código, no por índice:
    # reordenar REGLAS_REGEX no altera silenciosamente este comportamiento.
    # ------------------------------------------------------------------

    _REGEX_FALLBACK: list[tuple[re.Pattern, str, float]] = [
        (re.compile(pattern, re.IGNORECASE | re.UNICODE), code, confidence)
        for pattern, code, confidence in REGLAS_REGEX_FALLBACK_AUDITADAS
    ]
    _REGEX_CONTEXTUAL: list[tuple[re.Pattern, str, float]] = [
        (re.compile(pattern, re.IGNORECASE | re.UNICODE), code, confidence)
        for pattern, code, confidence in REGLAS_REGEX
    ]

    # ------------------------------------------------------------------
    # Dictionary loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_dictionary() -> list[dict[str, str]]:
        store = NeonKnowledgeStore()
        if store.enabled:
            try:
                data = store.load_dictionary()
                if data:
                    logger.info("Diccionario cargado desde Neon: %d entradas", len(data))
                    return [e for e in data if e.get("codigo_estandar") != "__EXCLUIR__"]
            except Exception as exc:
                logger.warning("Neon no disponible; usando diccionario JSON: %s", exc)
        path = Path(__file__).resolve().parent.parent / "diccionario.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [e for e in data if e.get("codigo_estandar") != "__EXCLUIR__"]

    @staticmethod
    def _normalize_name(name: str) -> str:
        name = name.lower().strip()
        name = re.sub(r"[^a-z0-9áéíóúñü ]+", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name

    @staticmethod
    def _infer_company(source_file: str) -> str:
        name = Path(source_file).stem
        name = re.sub(r"^\d+\s*", "", name)
        name = re.sub(r"\s*\d{4}.*$", "", name)
        return name.strip()[:60] or "unknown"

    @staticmethod
    def _infer_layout(source_file: str) -> str:
        lower = source_file.lower()
        if "balance" in lower and "8 columnas" in lower:
            return "8_columnas"
        if "tributario" in lower:
            return "tributario"
        if "pre-balance" in lower or "pre balance" in lower:
            return "pre_balance"
        if "consolidado" in lower:
            return "consolidado"
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            return "excel"
        return "pdf_estandar"

    # ------------------------------------------------------------------
    # Classification stages
    # ------------------------------------------------------------------

    def _classify_by_code(self, account_code: str) -> dict[str, Any] | None:
        result = self._code_classifier.clasificar(account_code)
        if result is not None:
            return {
                "standard_code": result.codigo_estandar,
                "confidence": result.confianza,
                "method": "code",
                "reason": result.razon,
            }
        return None

    def _classify_by_dictionary_exact(self, account_name: str) -> dict[str, Any] | None:
        normalized = self._normalize_name(account_name)
        for entry in self._dictionary:
            if self._normalize_name(entry["cuenta_original"]) == normalized:
                code = (
                    "ANC.01.01" if is_contra_asset_name(account_name)
                    else entry["codigo_estandar"]
                )
                return {
                    "standard_code": code,
                    "confidence": 0.98,
                    "method": "dictionary_exact",
                    "reason": f"Coincidencia exacta con diccionario → {code}",
                }
        return None

    def _classify_by_dictionary_fuzzy(self, account_name: str) -> dict[str, Any] | None:
        normalized = self._normalize_name(account_name)
        best_score = 0
        best_entry: dict[str, str] | None = None
        for entry in self._dictionary:
            dict_name = self._normalize_name(entry["cuenta_original"])
            score = fuzz.token_sort_ratio(normalized, dict_name)
            if score > best_score:
                best_score = score
                best_entry = entry
        if best_score >= 90 and best_entry is not None:
            confidence = min(0.80 + (best_score - 90) * 0.01, 0.97)
            code = (
                "ANC.01.01" if is_contra_asset_name(account_name)
                else best_entry["codigo_estandar"]
            )
            return {
                "standard_code": code,
                "confidence": round(confidence, 4),
                "method": "dictionary_fuzzy",
                "reason": (
                    f"Coincidencia fuzzy ({best_score}%) con "
                    f"'{best_entry['cuenta_original']}' → {code}"
                ),
            }
        return None

    def _classify_debit_balance_financial_liability(
        self, account_name: str,
    ) -> dict[str, Any] | None:
        """Propone sólo una coincidencia exacta para saldo deudor de pasivo.

        Esta excepción no habilita una inferencia general desde la columna
        ACTIVO. Requiere una glosa bancaria específica y una entrada exacta
        del diccionario, y siempre conserva revisión humana.
        """
        result = self._classify_by_dictionary_exact(account_name)
        if result is None or not str(result.get("standard_code") or "").startswith(
            ("PC.", "PNC."),
        ):
            return None
        return {
            **result,
            "method": "dictionary_exact_contra_pasivo",
            "reason": (
                f"{result.get('reason', 'Coincidencia exacta con diccionario')}; "
                "obligación financiera con saldo deudor físico: propuesta "
                "como contra-pasivo, requiere confirmación humana"
            ),
            "requires_review": True,
        }

    @staticmethod
    def _classify_credit_balance_depreciation(
        account_name: str,
        origen_columna: Any,
        monto: Any,
    ) -> dict[str, Any] | None:
        """Sugiere depreciación acumulada desde un saldo acreedor observado.

        La sugerencia no se usa para cerrar una entrega sin analista. Su
        evidencia es la combinación de glosa de depreciación y columna física
        acreedora, no una inferencia por texto aislado.
        """
        if not is_credit_balance_depreciation_name(
            account_name, origen_columna, monto,
        ):
            return None
        return {
            "standard_code": "ANC.01.01",
            "confidence": 0.84,
            "method": "contextual_credit_balance_depreciation",
            "reason": (
                "Depreciación observada con saldo acreedor: propuesta como "
                "contra-activo ANC.01.01; requiere confirmación humana"
            ),
            "requires_review": True,
        }

    @staticmethod
    def _classification_for_explicit_result_year(
        account_name: str,
        account_code: str,
        closing_year: int | None,
    ) -> dict[str, Any] | None:
        """Clasifica resultados anuales sólo con período de cierre confirmado.

        ``2402-`` es una familia conocida de resultados acumulados. Para que
        una glosa ``RESULTADO AÑO YYYY`` llegue automáticamente a PAT.03 se
        exige además que YYYY sea anterior al cierre. El año de cierre sólo
        se propone como resultado del ejercicio si también pertenece a 2402-
        y conserva revisión; un año futuro no se reclasifica silenciosamente
        como patrimonio acumulado.
        """
        if closing_year is None:
            return None
        result_year = result_year_from_name(account_name)
        if result_year is None:
            return None
        if is_historical_accumulated_result_name(
            account_name,
            account_code=account_code,
            closing_year=closing_year,
        ):
            return {
                "standard_code": "PAT.03",
                "confidence": 0.90,
                "method": "historical_result_year",
                "reason": (
                    "Resultado anual histórico: etiqueta explícita "
                    f"{result_year}, cierre confirmado {closing_year} y "
                    "familia de cuenta 2402- → PAT.03"
                ),
            }
        if (
            result_year == closing_year
            and is_accumulated_result_2402_code(account_code)
        ):
            return {
                "standard_code": "PAT.04",
                "confidence": 0.84,
                "method": "current_result_year",
                "reason": (
                    "Resultado del año de cierre: etiqueta explícita "
                    f"{result_year} coincide con el cierre confirmado "
                    f"{closing_year} → PAT.04; requiere revisión humana"
                ),
                "requires_review": True,
            }
        if result_year == closing_year:
            return {
                "standard_code": None,
                "confidence": 0.0,
                "method": "unclassified_current_result_year",
                "reason": (
                    "Resultado del año de cierre sin familia de cuenta 2402- "
                    f"({result_year}); no se clasifica automáticamente como "
                    "PAT.03 ni PAT.04"
                ),
                "requires_review": True,
            }
        if result_year > closing_year:
            return {
                "standard_code": None,
                "confidence": 0.0,
                "method": "unclassified_future_result_year",
                "reason": (
                    "Resultado anual con año posterior al cierre confirmado "
                    f"({result_year} > {closing_year}); no se clasifica "
                    "automáticamente como PAT.03"
                ),
                "requires_review": True,
            }
        return None

    @staticmethod
    def _canonicalize_special_code(
        result: dict[str, Any], account_name: str,
    ) -> dict[str, Any]:
        """Migra decisiones antiguas al código específico vigente."""
        if (is_contra_asset_name(account_name)
                and result.get("standard_code") == "ANC.01"):
            result = {**result, "standard_code": "ANC.01.01"}
            result["reason"] = (
                f"{result.get('reason', 'Clasificación previa')}; "
                "contra-activo normalizado a ANC.01.01"
            )
        return result

    def _classify_by_regex(self, account_name: str, account_tipo: str | None = None) -> dict[str, Any] | None:
        if not account_name:
            return None
        normalized = self._normalize_name(account_name)
        for pat, cod, conf in self._REGEX_FALLBACK:
            if pat.search(normalized):
                if account_tipo and not self._is_code_allowed_for_tipo(cod, account_tipo):
                    continue
                return {
                    "standard_code": cod,
                    "confidence": conf,
                    "method": "regex_fallback",
                    "reason": f"Patrón regex (precisión auditada 100%) → {cod}",
                }
        return None

    def _classify_by_regex_contextual(
        self, account_name: str, account_tipo: str | None,
        account_code: str = "",
    ) -> dict[str, Any] | None:
        """Aplica reglas acotadas por columna física y, cuando existe, plan."""
        if not account_name or not account_tipo:
            return None
        normalized = self._normalize_name(account_name)

        def key_without_accents(value: str) -> str:
            return "".join(
                char for char in unicodedata.normalize("NFKD", value)
                if not unicodedata.combining(char)
            )

        def suggestion(code: str, evidence: str) -> dict[str, Any]:
            return {
                "standard_code": code,
                "confidence": 0.84,
                "method": "contextual_accounting_suggestion",
                "reason": (
                    f"Regla contable contextual ({evidence}) compatible con "
                    f"{account_tipo} → {code}; requiere revisión humana"
                ),
                "requires_review": True,
            }

        canonical = key_without_accents(normalized)
        codigo_plan = re.sub(r"\s+", "", str(account_code or ""))
        exact_suggestion = _SUGERENCIAS_CONTEXTUALES_EXACTAS.get(
            (account_tipo, canonical),
        )
        if exact_suggestion is not None:
            return suggestion(*exact_suggestion)

        # ``BCO`` es la abreviatura frecuente de banco en planes de cuentas
        # locales. La misma glosa sólo cambia de propuesta cuando la columna
        # física confirma un saldo deudor (efectivo) o acreedor (obligación).
        if re.search(r"\b(?:bco|banco)\b", canonical):
            code = {"ACTIVO": "AC.01", "PASIVO": "PC.02"}.get(account_tipo)
            if code:
                return suggestion(code, "banco observado en columna física")

        # Se exige simultáneamente documento/cuenta, la relación y el verbo
        # cobrar o pagar. Así no se propone una relacionada CP desde una glosa
        # genérica que sólo mencione a una empresa del grupo.
        relacionada = bool(re.search(
            r"\b(?:emp(?:resa)?s?\s+rel(?:acionad)?s?|relacionad[ao]s?)\b",
            canonical,
        ))
        documento_o_cuenta = bool(re.search(
            r"\b(?:doctos?|documentos?|ctas?|cuentas?)\b", canonical,
        ))
        if relacionada and documento_o_cuenta:
            if account_tipo == "ACTIVO" and "por cobrar" in canonical:
                return suggestion("AC.06", "cuenta por cobrar a relacionada")
            if account_tipo == "PASIVO" and "por pagar" in canonical:
                return suggestion("PC.07", "cuenta por pagar a relacionada")

        # Algunos planes mantienen las relacionadas corrientes bajo 2.1.07
        # aunque una cuenta individual tenga saldo deudor y se presente en
        # ACTIVO. La combinación de esa familia, la glosa y la columna física
        # permite proponer una cuenta por cobrar, sin convertirla en decisión
        # automática ni inferir plazos fuera de lo observado.
        if (
            account_tipo == "ACTIVO"
            and relacionada
            and codigo_plan.startswith("2.1.07.")
        ):
            return suggestion(
                "AC.06",
                "saldo deudor de relacionada en familia corriente 2.1.07",
            )

        # La familia 1.3 del plan observado corresponde a partidas no
        # corrientes. Un préstamo dentro de ella se presenta de manera
        # conservadora como otro activo no corriente: la sugerencia conserva
        # revisión humana porque la glosa por sí sola no acredita contraparte
        # relacionada ni condiciones financieras.
        if (
            account_tipo == "ACTIVO"
            and codigo_plan.startswith("1.3.")
            and re.search(r"\bprestamo\b", canonical)
        ):
            return suggestion(
                "ANC.06",
                "préstamo en familia no corriente 1.3",
            )

        if (
            account_tipo == "PASIVO"
            and re.search(r"\bobligacion(?:es)?\b", canonical)
            and re.search(
                r"\b(?:bco|banco|institucion(?:es)?\s+financieras?)\b",
                canonical,
            )
        ):
            return suggestion("PC.02", "obligación financiera de corto plazo")

        if account_tipo == "ACTIVO" and is_contra_asset_name(account_name):
            return {
                "standard_code": "ANC.01.01",
                "confidence": 0.84,
                "method": "regex_contextual",
                "reason": (
                    "Contra-activo identificado por nombre y columna acreedora → "
                    "ANC.01.01; requiere revisión humana"
                ),
            }
        # El mismo término "intereses" puede ser gasto financiero o ingreso
        # financiero. La columna GANANCIA lo resuelve sin asumir que una
        # glosa de intereses en PÉRDIDA sea ingreso. Se mantiene bajo el
        # umbral automático porque no distingue origen del rendimiento.
        if (
            account_tipo == "GANANCIA"
            and re.search(r"\binter[eé](?:s|ses)\b", normalized, re.I)
        ):
            return {
                "standard_code": "ER.12",
                "confidence": 0.84,
                "method": "regex_contextual",
                "reason": (
                    "Intereses observados en columna GANANCIA → ER.12; "
                    "requiere revisión humana"
                ),
            }
        for pattern, code, confidence in self._REGEX_CONTEXTUAL:
            if (pattern.search(normalized)
                    and self._is_code_allowed_for_tipo(code, account_tipo)):
                return {
                    "standard_code": code,
                    "confidence": min(confidence, 0.84),
                    "method": "regex_contextual",
                    "reason": (
                        f"Patrón contextual compatible con {account_tipo} → {code}; "
                        "requiere revisión humana"
                    ),
                }
        return None

    @staticmethod
    def _classify_by_origin_fallback(
        account_code: str, account_tipo: str | None, *,
        permitir_codigo_sin_homologacion: bool = False,
    ) -> dict[str, Any] | None:
        """Sugiere una categoría residual desde una columna física fiable.

        El fallback no sustituye una clasificación producida por un código de
        origen. Sólo puede usarse al final del flujo, después de que ese código
        no tuvo equivalencia compatible en código, diccionario ni reglas. En
        ese caso el código se conserva como trazabilidad, pero la columna
        física permite ofrecer una propuesta revisable en vez de dejar una
        cuenta sin categoría.
        """
        if (account_code and not permitir_codigo_sin_homologacion) or not account_tipo:
            return None
        fallback = {
            "ACTIVO": "AC.08",
            "PASIVO": "PC.08",
            "PATRIMONIO": "PAT.10",
            "GANANCIA": "ER.17",
            "PERDIDA": "ER.18",
        }.get(account_tipo)
        if not fallback:
            return None
        return {
            "standard_code": fallback,
            "confidence": 0.55,
            "method": "origin_fallback",
            "reason": (
                f"Categoría residual inferida desde columna {account_tipo}"
                + (
                    "; el código de origen no tuvo homologación compatible"
                    if account_code else ""
                )
                + "; "
                "requiere revisión humana"
            ),
        }

    def _is_code_allowed(self, code: str | None, tipo: str | None) -> bool:
        if not self._features.ENABLE_ACCOUNT_TYPE_FILTER or not code or not tipo:
            return True
        return self._is_code_allowed_for_tipo(code, tipo)

    def _classify_account(
        self, account_code: str, account_name: str,
        account_tipo: str | None = None,
        store_cmcc_shadow: bool = True,
    ) -> dict[str, Any]:
        learning_result = self._learning_engine.best_match(account_name)
        learning_rejected: dict[str, Any] | None = None
        if learning_result["source"] != "none":
            learning_candidate = {
                "standard_code": learning_result["code"],
                "confidence": learning_result["confidence"],
                "method": f"learning_{learning_result['source']}",
                "reason": (
                    f"Gold Standard ({learning_result['source']}) → "
                    f"{learning_result['code']} "
                    f"(matched: {learning_result['matched_name']})"
                ),
            }
            # Una corrección humana es una evidencia fuerte, pero puede venir
            # de otra plantilla donde la misma glosa ocupa una naturaleza
            # distinta. Nunca debe atravesar la columna contable observada ni
            # bloquear el diccionario/reglas compatibles que siguen.
            if (
                not account_tipo
                or self._is_code_allowed_for_tipo(
                    learning_candidate["standard_code"], account_tipo,
                )
            ):
                return learning_candidate
            learning_rejected = learning_candidate

        cmcc_raw: dict[str, Any] | None = None
        cmcc_score = -1.0

        if self._features.ENABLE_CMCC:
            cmcc_raw = self._cmcc_classifier.classify(account_name)
            cmcc_score = cmcc_raw.get("score", 0.0) if cmcc_raw else -1.0

        result: dict[str, Any] | None = None

        if self._features.ENABLE_CMCC_PRODUCTION and cmcc_score >= self._features.CMCC_THRESHOLD:
            result = {
                "standard_code": cmcc_raw["code"],
                "confidence": cmcc_score,
                "method": cmcc_raw.get("method", "cmcc"),
                "reason": (
                    f"CMCC ({cmcc_raw.get('method', '?')}) → "
                    f"{cmcc_raw['code']} ({cmcc_raw.get('concept', '')}) "
                    f"score={cmcc_score}"
                ),
                "cmcc_detail": cmcc_raw,
            }

        if self._features.ENABLE_DECISION_ENGINE:
            result = self._classify_with_decision_engine(
                account_code, account_name, account_tipo,
            )
            result = self._canonicalize_special_code(result, account_name)
            result["_cmcc_score"] = cmcc_score
            if cmcc_raw is not None:
                result["cmcc_detail"] = cmcc_raw
            if store_cmcc_shadow and cmcc_raw is not None:
                result["cmcc_shadow"] = cmcc_raw
            return result

        # Un código de origen puede coincidir con una plantilla distinta y
        # proponer una categoría incompatible con la columna observada. Antes
        # se descartaba esa propuesta, pero el ``or`` ya había impedido probar
        # el diccionario. Se recorren las fuentes en prioridad y se conserva
        # la primera compatible; así un nombre exacto validado puede reparar
        # un código de plan ajeno sin ocultar la contradicción original.
        candidatos_iniciales = (
            result,
            self._classify_by_code(account_code),
            self._classify_by_dictionary_exact(account_name),
            self._classify_by_dictionary_fuzzy(account_name),
        )
        result = next(
            (
                candidato
                for candidato in candidatos_iniciales
                if candidato is not None
                and (
                    not account_tipo
                    or self._is_code_allowed_for_tipo(
                        candidato.get("standard_code"), account_tipo,
                    )
                )
            ),
            None,
        )

        if result is None and self._features.ENABLE_SEMANTIC_MATCHER and self._semantic_matcher is not None:
            sm_result = self._semantic_matcher.match(account_name, account_tipo)
            if (
                not sm_result.is_unknown
                and (
                    not account_tipo
                    or self._is_code_allowed_for_tipo(
                        sm_result.expected_cmcc, account_tipo,
                    )
                )
            ):
                result = {
                    "standard_code": sm_result.expected_cmcc,
                    "confidence": min(sm_result.score, 0.99),
                    "method": f"semantic_{sm_result.match_tier}",
                    "reason": (
                        f"SemanticMatcher ({sm_result.concept_name}) → "
                        f"{sm_result.expected_cmcc} "
                        f"tier={sm_result.match_tier} score={sm_result.score:.4f}"
                    ),
                    "semantic_match": sm_result.to_dict(),
                }

        if result is None and self._features.ENABLE_REGEX_FALLBACK:
            result = self._classify_by_regex(account_name, account_tipo)

        if result is None:
            result = self._classify_by_regex_contextual(
                account_name, account_tipo, account_code,
            )

        if result is None:
            result = self._classify_by_origin_fallback(
                account_code,
                account_tipo,
                permitir_codigo_sin_homologacion=True,
            )

        if result is None:
            result = {
                "standard_code": None,
                "confidence": 0.0,
                "method": "unclassified",
                "reason": "Sin coincidencia en código ni diccionario",
            }

        result = self._canonicalize_special_code(result, account_name)

        if learning_rejected is not None:
            result["learning_rejected"] = {
                "standard_code": learning_rejected["standard_code"],
                "method": learning_rejected["method"],
                "reason": (
                    "Coincidencia histórica descartada por incompatibilidad "
                    f"con tipo {account_tipo}."
                ),
            }

        if store_cmcc_shadow and cmcc_raw is not None:
            result["cmcc_shadow"] = cmcc_raw
        if cmcc_raw is not None:
            result.setdefault("cmcc_detail", cmcc_raw)

        result["_cmcc_score"] = cmcc_score
        return result

    def _classify_with_decision_engine(
        self,
        account_code: str,
        account_name: str,
        account_tipo: str | None = None,
    ) -> dict[str, Any]:
        from decision.models import DecisionResult as DEResult

        code_r = self._classify_by_code(account_code)
        dict_r = self._classify_by_dictionary_exact(account_name) or self._classify_by_dictionary_fuzzy(account_name)

        sm_match = None
        sm_code = None
        sm_score = None
        sm_tier = None
        sm_confidence = None
        if self._features.ENABLE_SEMANTIC_MATCHER and self._semantic_matcher is not None:
            sm_match = self._semantic_matcher.match(account_name, account_tipo)
            if not sm_match.is_unknown and self._is_code_allowed(sm_match.expected_cmcc, account_tipo):
                sm_code = sm_match.expected_cmcc
                sm_score = sm_match.score
                sm_tier = sm_match.match_tier
                sm_confidence = sm_match.confidence

        regex_r = None
        if self._features.ENABLE_REGEX_FALLBACK:
            regex_r = self._classify_by_regex(account_name, account_tipo)

        # Collect inputs
        de_sm_code = sm_code
        de_sm_score = sm_score
        de_sm_tier = sm_tier
        de_sm_confidence = sm_confidence

        de_regex_code = regex_r["standard_code"] if regex_r else None
        de_regex_method = regex_r["method"] if regex_r else None

        de_dict_code = None
        de_dict_method = None
        if dict_r is not None:
            de_dict_code = dict_r["standard_code"]
            de_dict_method = dict_r["method"]

        de_ac_type = account_tipo
        de_ac_code = account_code

        decision: DEResult = self._decision_engine.decide(
            sm_code=de_sm_code,
            sm_score=de_sm_score,
            sm_tier=de_sm_tier,
            sm_confidence=de_sm_confidence,
            regex_code=de_regex_code,
            regex_method=de_regex_method,
            dict_code=de_dict_code,
            dict_method=de_dict_method,
            account_type=de_ac_type,
            account_code=de_ac_code,
        )

        # El motor de decisión sólo compara sus fuentes históricas. Cuando
        # ninguna llega a código, todavía pueden existir reglas contextuales
        # acotadas por la columna física. Conservamos el resultado del motor
        # como trazabilidad, pero la propuesta nunca se convierte en decisión
        # automática: lleva ``requires_review`` y una confianza inferior al
        # umbral automático.
        if decision.codigo_final is None:
            contextual = self._classify_by_regex_contextual(
                account_name, account_tipo, account_code,
            )
            if contextual is not None:
                contextual["decision_engine"] = decision.to_dict()
                return contextual
            fallback = self._classify_by_origin_fallback(
                account_code,
                account_tipo,
                permitir_codigo_sin_homologacion=True,
            )
            if fallback is not None:
                fallback["decision_engine"] = decision.to_dict()
                return fallback

        method_map = {
            "SM_AND_REGEX_AGREE": "decision_agree",
            "SM_HIGH_CONFIDENCE": "decision_sm_high",
            "REGEX_EXACT": "decision_regex_exact",
            "SM_ONLY": "decision_sm_only",
            "REGEX_ONLY": "decision_regex_only",
            "CONFLICT_UNRESOLVED": "decision_conflict",
            "BOTH_UNKNOWN": "decision_unknown",
        }

        result: dict[str, Any] = {
            "standard_code": decision.codigo_final,
            "confidence": self._confidence_from_label(decision.confidence, sm_score if sm_score else 0.0),
            "method": method_map.get(decision.decision_source, f"decision_{decision.decision_source.lower()}"),
            "reason": decision.reason,
            "decision_engine": decision.to_dict(),
        }
        if sm_match is not None and not sm_match.is_unknown:
            result["semantic_match"] = sm_match.to_dict()

        return result

    @staticmethod
    def _confidence_from_label(label: str, fallback_score: float) -> float:
        mapping = {
            "VERY_HIGH": 0.99,
            "HIGH": 0.90,
            "MEDIUM": 0.75,
            "LOW": 0.50,
            "UNKNOWN": 0.0,
        }
        return mapping.get(label, fallback_score)

    # ------------------------------------------------------------------
    # Main processing
    # ------------------------------------------------------------------

    def process(
        self,
        pdf_path: str | Path,
        *,
        closing_year: int | str | None = None,
    ) -> dict[str, Any]:
        """Procesa un balance con un año de cierre opcional confirmado.

        El año se usa sólo para distinguir ``RESULTADO AÑO YYYY`` de la
        familia 2402-. No se infiere desde el nombre del archivo ni habilita
        clasificaciones por año si falta o no es válido.
        """
        start = time.perf_counter()
        path = Path(pdf_path)
        try:
            confirmed_closing_year = (
                int(closing_year) if closing_year is not None else None
            )
        except (TypeError, ValueError):
            confirmed_closing_year = None
        if confirmed_closing_year is not None and not (
            1900 <= confirmed_closing_year <= 2200
        ):
            confirmed_closing_year = None
        ext = path.suffix.lower()

        if ext in (".xlsx", ".xls"):
            cuentas = parsear_excel(path)
            resultado = ResultadoParseo(
                archivo=path.name,
                formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles="",
                requirio_ocr=False,
                rotacion_aplicada=0,
                cuentas=cuentas,
                certificacion_extraccion=certificar_extraccion_columnas(
                    cuentas, metodo="excel_8_columns",
                ),
            )
        else:
            resultado = self._parser.parsear(path)
        certification = getattr(resultado, "certificacion_extraccion", None)
        certification_state = (
            getattr(certification, "estado", "") or "no_evaluable"
        )
        extraction_review_required = certification_state != "certificada"
        extraction_review_lines = _lineas_revision_extraccion(certification)
        accounts_total = len(resultado.cuentas)
        logger.info("accounts_total: %d", accounts_total)

        classified: list[dict[str, Any]] = []
        ignored: list[dict[str, Any]] = []
        unclassified_count = 0
        learning_hits = 0
        learning_exact = 0
        learning_fuzzy = 0
        fallback_classifier = 0
        semantic_total = 0
        semantic_matches = 0
        semantic_unknown = 0
        semantic_confidences: list[float] = []
        cmcc_shadow_hits = 0
        cmcc_production_hits = 0
        cmcc_review_queue: list[dict[str, Any]] = []

        enable_cmcc = self._features.ENABLE_CMCC
        enable_shadow = self._features.ENABLE_CMCC_SHADOW
        enable_production = self._features.ENABLE_CMCC_PRODUCTION
        cmcc_threshold = self._features.CMCC_THRESHOLD
        cmcc_review = self._features.CMCC_REVIEW_THRESHOLD
        enable_review_pipeline = self._features.ENABLE_CMCC_REVIEW_PIPELINE
        enable_type_filter = self._features.ENABLE_ACCOUNT_TYPE_FILTER
        enable_regex = self._features.ENABLE_REGEX_FALLBACK

        from parsers.account_type_resolver import AccountTypeResolver
        type_resolver = AccountTypeResolver()

        tipo_filtered = 0
        regex_hits = 0
        semantic_matcher_hits = 0
        decision_engine_agreements = 0
        decision_engine_sm_high = 0
        decision_engine_regex_exact = 0
        decision_engine_conflicts = 0
        decision_engine_human_review = 0
        decision_engine_total = 0

        for cr in resultado.cuentas:
            # Los subtotales y totales se conservan como evidencia de
            # extracción, pero no son cuentas que puedan homologarse.
            if cr.es_total:
                ignored.append({
                    "account_code": cr.codigo or "",
                    "account_name": cr.nombre,
                    "ignored_reason": "extraction_control",
                })
                continue
            ab: AccountBalance = AccountAdapter.from_cuenta_raw(cr)
            interp = BalanceInterpreter(ab)

            classification_amount = interp.classification_amount

            tipo_result = type_resolver.resolve(
                origen_columna=cr.origen_columna,
                codigo=cr.codigo,
            )
            tipo_seccion = account_type_from_explicit_section(
                getattr(cr, "seccion_contable", None),
            )
            account_tipo = (
                tipo_seccion.value if tipo_seccion is not None
                else tipo_result.account_type.value
            )
            classification_by_result_year = (
                self._classification_for_explicit_result_year(
                    ab.account_name,
                    ab.account_code,
                    confirmed_closing_year,
                )
            )
            historical_accumulated_result = bool(
                classification_by_result_year
                and classification_by_result_year.get("method")
                == "historical_result_year"
            )
            current_result_year = bool(
                classification_by_result_year
                and classification_by_result_year.get("method")
                == "current_result_year"
            )
            contra_activo_depreciacion = is_credit_balance_depreciation_name(
                ab.account_name, cr.origen_columna, classification_amount,
            )
            # Las depreciaciones acumuladas explícitas ya pertenecen a la
            # regla histórica de contra-activos. Esta rama sólo cubre las
            # abreviaturas o glosas incompletas que requieren propuesta.
            contra_activo_depreciacion_contextual = (
                contra_activo_depreciacion
                and not is_contra_asset_name(ab.account_name)
            )
            if (tipo_seccion is None
                    and account_tipo == "PASIVO"
                    and (
                        is_contra_asset_name(ab.account_name)
                        or contra_activo_depreciacion
                    )):
                account_tipo = "ACTIVO"
            if (tipo_seccion is None
                    and (is_patrimonial_reserve_name(ab.account_name)
                    or is_accumulated_result_name(
                        ab.account_name,
                        account_code=ab.account_code,
                        closing_year=confirmed_closing_year,
                    )
                    or is_current_result_name(ab.account_name)
                    or is_capital_pending_name(ab.account_name))):
                account_tipo = "PATRIMONIO"
            if historical_accumulated_result or current_result_year:
                account_tipo = "PATRIMONIO"

            contra_pasivo_deudor = is_debit_balance_financial_liability(
                ab.account_name, cr.origen_columna, classification_amount,
            )

            # None significa ausencia de información.
            # Un saldo 0.0 puede tener cuenta válida y debe clasificarse.
            if classification_amount is None:
                ignored.append({
                    "account_code": ab.account_code,
                    "account_name": ab.account_name,
                    "ignored_reason": "movement_only",
                })
                continue

            store_shadow = enable_cmcc and enable_shadow
            classification = classification_by_result_year or (
                self._classify_debit_balance_financial_liability(ab.account_name)
                if contra_pasivo_deudor else None
            ) or self._classify_account(
                ab.account_code, ab.account_name,
                account_tipo=account_tipo,
                store_cmcc_shadow=store_shadow,
            )
            # Una depreciación con saldo acreedor puede coincidir antes con una
            # regla genérica ANC. Aun así, su presentación como contra-activo
            # modifica el signo de la cuadratura y siempre debe llegar al
            # analista como propuesta contextual, no como decisión automática.
            if contra_activo_depreciacion_contextual:
                special = self._classify_credit_balance_depreciation(
                    ab.account_name, cr.origen_columna, classification_amount,
                )
                if special is not None:
                    classification = special

            if enable_type_filter and account_tipo and classification.get("standard_code"):
                allowed_contra_pasivo = (
                    contra_pasivo_deudor
                    and str(classification["standard_code"]).startswith(("PC.", "PNC."))
                )
                if not (
                    allowed_contra_pasivo
                    or self._is_code_allowed_for_tipo(
                        classification["standard_code"], account_tipo,
                    )
                ):
                    classification["standard_code"] = None
                    classification["confidence"] = 0.0
                    classification["method"] = "unclassified"
                    classification["reason"] = (
                        f"Filtrado: código incompatible con tipo {account_tipo}"
                    )
                    tipo_filtered += 1

            if classification.get("method") == "regex_fallback":
                regex_hits += 1
            if classification.get("method", "").startswith("semantic_"):
                semantic_matcher_hits += 1

            de_method = classification.get("method", "")
            if de_method.startswith("decision_"):
                decision_engine_total += 1
                de_source = classification.get("decision_engine", {}).get("decision_source", "")
                if de_source == "SM_AND_REGEX_AGREE":
                    decision_engine_agreements += 1
                elif de_source == "SM_HIGH_CONFIDENCE":
                    decision_engine_sm_high += 1
                elif de_source == "REGEX_EXACT":
                    decision_engine_regex_exact += 1
                elif de_source == "CONFLICT_UNRESOLVED":
                    decision_engine_conflicts += 1

                if classification.get("decision_engine", {}).get("review_required"):
                    decision_engine_human_review += 1

            cmcc_shadow = classification.pop("cmcc_shadow", None)
            cmcc_detail = classification.get("cmcc_detail")
            cmcc_score = classification.pop("_cmcc_score", -1.0)

            if enable_cmcc and enable_production and cmcc_score >= cmcc_threshold:
                cmcc_production_hits += 1
            elif enable_cmcc and enable_shadow and cmcc_score >= 0.90:
                cmcc_shadow_hits += 1

            if enable_cmcc and enable_production and cmcc_review <= cmcc_score < cmcc_threshold:
                cmcc_review_queue.append({
                    "account_name": ab.account_name,
                    "cmcc_result": cmcc_detail,
                })

            # ── REVIEW_CMCC queue (feature-flagged, shadow only) ──
            if (
                enable_review_pipeline
                and enable_cmcc
                and classification.get("standard_code") is None
                and cmcc_detail is not None
                and cmcc_score == 1.0
            ):
                from review.cmcc_review_models import ReviewCMCC
                source_file = path.name
                company = self._infer_company(source_file)
                layout = self._infer_layout(source_file)
                review_entry = ReviewCMCC.from_pipeline_account(
                    account_name=ab.account_name,
                    source_file=source_file,
                    cmcc_detail=cmcc_detail,
                    company=company,
                    layout=layout,
                )
                cmcc_review_queue.append(review_entry.to_dict())

            semantic_result = self._semantic_engine.interpret(ab).to_dict()
            semantic_total += 1
            if semantic_result["semantic_type"] != "unknown":
                semantic_matches += 1
            else:
                semantic_unknown += 1
            semantic_confidences.append(semantic_result["confidence"])

            method = classification.get("method", "")
            if method.startswith("learning_"):
                learning_hits += 1
                if method == "learning_exact":
                    learning_exact += 1
                elif method == "learning_fuzzy":
                    learning_fuzzy += 1
            else:
                fallback_classifier += 1

            adjustment = self._rule_processor.aplicar(
                nombre_cuenta=ab.account_name,
                codigo_clasificado=classification.get("standard_code") or "",
                monto=classification_amount,
                origen_columna=cr.origen_columna,
            )

            final_code = (
                adjustment.codigo_final
                if adjustment.aplica
                else classification.get("standard_code")
            )
            final_code_compatible = bool(final_code) and (
                not account_tipo
                or (
                    contra_pasivo_deudor
                    and str(final_code).startswith(("PC.", "PNC."))
                )
                or self._is_code_allowed_for_tipo(final_code, account_tipo)
            )
            if enable_type_filter and final_code and not final_code_compatible:
                final_code = None

            if final_code is None:
                unclassified_count += 1

            confidence = float(classification.get("confidence") or 0.0)
            account_extraction_review_required = bool(
                extraction_review_required
                and (
                    extraction_review_lines is None
                    or cr.linea in extraction_review_lines
                )
            )
            review_required = bool(
                final_code is None
                or not final_code_compatible
                or confidence < REVIEW_CONFIDENCE_THRESHOLD
                or adjustment.requiere_revision
                or classification.get("requires_review", False)
                or classification.get("decision_engine", {}).get(
                    "review_required", False,
                )
                or account_extraction_review_required
            )
            classified.append({
                "account_code": ab.account_code,
                "account_name": ab.account_name,
                "nature": interp.nature.value,
                "classification_amount": classification_amount,
                "origen_columna": cr.origen_columna.value,
                "seccion_contable": getattr(cr, "seccion_contable", None) or "",
                "origen_columna_efectiva": (
                    "patrimonio"
                    if historical_accumulated_result or current_result_year
                    else (
                        tipo_seccion.value.lower()
                        if tipo_seccion is not None else cr.origen_columna.value
                    )
                ),
                "estado_financiero": getattr(cr, "estado_financiero", None) or "",
                "standard_code": classification.get("standard_code"),
                "final_code": final_code,
                "compatible": final_code_compatible,
                "confidence": confidence,
                "method": classification.get("method", "unknown"),
                "reason": classification.get("reason", ""),
                "special_rule": adjustment.nota if adjustment.aplica else None,
                "review_required": review_required,
                "extraction_certification": certification_state,
                "extraction_review_required": account_extraction_review_required,
                "source_file": path.name,
                "source_page": ab.source_page,
                "semantic_result": semantic_result,
                "cmcc_shadow": cmcc_shadow,
                "cmcc_decision": classification.get("cmcc_detail"),
            })

        accounts_classified = len(classified)
        accounts_ignored = len(ignored)
        accounts_without_dictionary_match = unclassified_count
        incluir_resultado_derivado = debe_incorporar_resultado_derivado(
            classified, certification,
        )
        accounting_quadrature = certificar_cuadratura_homologada(
            classified,
            incluir_resultado_derivado=incluir_resultado_derivado,
            resultado_final_fuente=resultado_final_fuente_certificado(
                certification,
            ),
        )
        format_support = evaluar_formato(
            certification,
            getattr(resultado, "document_context", None),
        )
        delivery_readiness = evaluar_entregabilidad(
            classified,
            certification,
            accounting_quadrature,
            formato=format_support,
        )

        elapsed = time.perf_counter() - start

        summary = {
            "source_file": path.name,
            "accounts_total": accounts_total,
            "accounts_classified": accounts_classified,
            "accounts_ignored": accounts_ignored,
            "accounts_without_dictionary_match": accounts_without_dictionary_match,
            "extraction_certification_state": certification_state,
            "automatic_decisions_allowed": not extraction_review_required,
            "homologated_balance_certified": accounting_quadrature["certificada"],
            "accounting_quadrature": accounting_quadrature,
            "delivery_readiness": delivery_readiness,
            "learning_hits": learning_hits,
            "learning_exact": learning_exact,
            "learning_fuzzy": learning_fuzzy,
            "fallback_classifier": fallback_classifier,
            "semantic_total": semantic_total,
            "semantic_matches": semantic_matches,
            "semantic_unknown": semantic_unknown,
            "semantic_confidence_avg": round(
                sum(semantic_confidences) / len(semantic_confidences), 4
            ) if semantic_confidences else 0.0,
            "regex_hits": regex_hits,
            "semantic_matcher_hits": semantic_matcher_hits,
            "decision_engine_total": decision_engine_total,
            "decision_engine_agreements": decision_engine_agreements,
            "decision_engine_sm_high": decision_engine_sm_high,
            "decision_engine_regex_exact": decision_engine_regex_exact,
            "decision_engine_conflicts": decision_engine_conflicts,
            "decision_engine_human_review": decision_engine_human_review,
            "cmcc_shadow_hits": cmcc_shadow_hits,
            "cmcc_production_hits": cmcc_production_hits,
            "cmcc_review_queue": cmcc_review_queue,
            "tipo_filtered": tipo_filtered,
            "cmcc_feature_flags": self._features.to_dict(),
            "elapsed_seconds": round(elapsed, 3),
            "classified": classified,
            "ignored": ignored,
        }

        logger.info(
            "total=%d classified=%d ignored=%d unmatched=%d (%.3fs)",
            accounts_total, accounts_classified, accounts_ignored,
            accounts_without_dictionary_match, elapsed,
        )

        return summary

    @staticmethod
    def _is_code_allowed_for_tipo(standard_code: str | None, tipo: str) -> bool:
        if not resultado_compatible(standard_code, tipo):
            return False
        if tipo == "DESCONOCIDO" or not standard_code:
            return True
        _PREFIX_TIPO: dict[str, set[str]] = {
            "ANC": {"ACTIVO"},
            "AC": {"ACTIVO"},
            "PNC": {"PASIVO"},
            "PC": {"PASIVO"},
            "PAT": {"PATRIMONIO", "PASIVO"},
            "ER": {"PERDIDA", "GANANCIA"},
        }
        for prefix, allowed in _PREFIX_TIPO.items():
            if standard_code.startswith(prefix):
                return tipo in allowed
        return True

    def to_json(self, pdf_path: str | Path, output_file: str | Path) -> None:
        data = self.process(pdf_path)
        path = Path(output_file)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("JSON escrito en: %s", path.resolve())
