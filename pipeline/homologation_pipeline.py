from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from adapters.account_adapter import AccountAdapter
from catalog_aliases import canonical_catalog_code, canonicalize_dictionary
from clasificador_codigo_cuenta import ClasificadorCodigo
from config.regex_rules import REGLAS_REGEX
from parser_universal import parsear_excel
from interpreters.balance_interpreter import BalanceInterpreter
from learning.engine import LearningEngine
from models.account_balance import AccountBalance
from parser_universal import FormatoCodigo, ParserPDF, ResultadoParseo
from pipeline.cmcc_classifier import CMCCClassifier
from pipeline.features import CMCCFeatureFlags
from persistence.neon_store import NeonKnowledgeStore
from parsers.account_type_resolver import (
    is_contra_asset_name,
    is_equity_account_name,
    is_ppe_depreciation_name,
)
from reglas_especiales import ProcesadorReglasEspeciales
from decision.engine import DecisionEngine
from semantic.semantic_engine import SemanticEngine
from semantic.matcher import SemanticMatcher
from reporting_integrity import resultado_compatible
from validation.classification_metrics import (
    RESIDUAL_CLASSIFICATION_METHODS, account_metrics, document_family,
)
from validation.prepost_balance import compare_pre_post

logger = logging.getLogger(__name__)


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
    # Regex fallback — only audited rules with 100% precision (Sprint 28.5A)
    # Target codes: PC.05, PC.08, PAT.02, ER.04, ER.09, ER.10, ER.11, ER.20, ER.21
    # ------------------------------------------------------------------

    _REGEX_FALLBACK: list[tuple[re.Pattern, str, float]] = [
        (re.compile(pattern, re.IGNORECASE | re.UNICODE), code, confidence)
        for pattern, code, confidence in REGLAS_REGEX
        if code in ("PC.05", "PC.08", "PAT.02", "ER.04", "ER.09", "ER.10", "ER.11", "ER.20", "ER.21")
    ]
    _REGEX_CONTEXTUAL: list[tuple[re.Pattern, str, float]] = [
        (re.compile(pattern, re.IGNORECASE | re.UNICODE), code, confidence)
        for pattern, code, confidence in REGLAS_REGEX
    ]

    # Etiquetas canónicas de estados financieros auditados. Son nombres
    # completos, no coincidencias parciales, y por eso pueden resolverse sin
    # un código de cuenta. Las partidas de balance además exigen que la
    # columna/tipo observado sea compatible; las de resultados no dependen
    # del signo ni de que el PDF haya impreso una columna explícita.
    _AUDITED_STATEMENT_LABELS: list[tuple[re.Pattern, str, set[str | None] | None]] = [
        (re.compile(r"efectivo y (?:efectivo )?equivalente(?:s)?(?: al efectivo)?", re.I), "AC.01", {"ACTIVO"}),
        (re.compile(r"otros activos financieros(?: corrientes?)?", re.I), "AC.08", {"ACTIVO"}),
        (re.compile(r"deudores comerciales y otras cuentas por cobrar(?: corrientes)?", re.I), "AC.03", {"ACTIVO"}),
        (re.compile(r"cuentas por cobrar a entidades relacionadas corrientes", re.I), "AC.06", {"ACTIVO"}),
        (re.compile(r"inventarios(?: corrientes)?", re.I), "AC.05", {"ACTIVO"}),
        (re.compile(r"activos por impuestos(?: corrientes)?", re.I), "AC.08", {"ACTIVO"}),
        (re.compile(r"otros activos no financieros corrientes", re.I), "AC.08", {"ACTIVO"}),
        (re.compile(r"propiedades planta y equipo", re.I), "ANC.01", {"ACTIVO"}),
        (re.compile(r"activos intangibles distintos de la plusval[ií]a", re.I), "ANC.03", {"ACTIVO"}),
        (re.compile(r"inversiones contabilizadas utilizando el m[eé]todo de la participaci[oó]n", re.I), "ANC.04", {"ACTIVO"}),
        (re.compile(r"cuentas por cobrar a entidades relacionadas no corrientes", re.I), "ANC.05", {"ACTIVO"}),
        (re.compile(r"activos por impuestos diferidos(?: no corrientes)?", re.I), "ANC.09", {"ACTIVO"}),
        (re.compile(r"otros activos no financieros(?: no corrientes)?", re.I), "ANC.06", {"ACTIVO"}),
        (re.compile(r"cuentas comerciales y otras cuentas por pagar(?: corrientes)?", re.I), "PC.01", {"PASIVO"}),
        (re.compile(r"acreedores comerciales(?: y otras cuentas por pagar)?", re.I), "PC.01", {"PASIVO"}),
        (re.compile(r"otros acreedores", re.I), "PC.01", {"PASIVO"}),
        (re.compile(r"(?:otros )?pasivos financieros(?: corrientes)?", re.I), "PC.02", {"PASIVO"}),
        (re.compile(r"obligaciones con instituciones de cr[eé]dito(?: corrientes?)?", re.I), "PC.02", {"PASIVO"}),
        (re.compile(r"pasivos por impuestos(?: corrientes)?", re.I), "PC.05", {"PASIVO"}),
        (re.compile(r"(?:provisi[oó]n |provisiones por )?beneficios a los empleados(?: corrientes)?", re.I), "PC.06", {"PASIVO"}),
        (re.compile(r"cuentas por pagar a entidades relacionadas corrientes", re.I), "PC.07", {"PASIVO"}),
        (re.compile(r"otras provisiones", re.I), "PC.09", {"PASIVO"}),
        (re.compile(r"otros pasivos no financieros", re.I), "PC.08", {"PASIVO"}),
        (re.compile(r"otros pasivos financieros no corrientes?", re.I), "PNC.05", {"PASIVO"}),
        (re.compile(r"pasivos financieros no corrientes?", re.I), "PNC.01", {"PASIVO"}),
        (re.compile(r"obligaciones con instituciones de cr[eé]dito no corrientes?", re.I), "PNC.01", {"PASIVO"}),
        (re.compile(r"cuentas por pagar a entidades relacionadas no corrientes", re.I), "PNC.04", {"PASIVO"}),
        (re.compile(r"pasivos? por impuestos diferidos", re.I), "PNC.06", {"PASIVO"}),
        (re.compile(r"deferred taxes", re.I), "PNC.06", {"PASIVO"}),
        (re.compile(r"deferred taxes", re.I), "ANC.09", {"ACTIVO"}),
        (re.compile(r"inversiones en otras (?:empresas|sociedades)", re.I), "ANC.04", {"ACTIVO"}),
        (re.compile(r"activos biol[oó]gicos(?: corrientes?)?", re.I), "AC.05", {"ACTIVO"}),
        (re.compile(r"activos biol[oó]gicos no corrientes?", re.I), "ANC.01", {"ACTIVO"}),
        (re.compile(r"gastos futuras cosechas", re.I), "AC.05", {"ACTIVO"}),
        (re.compile(r"parronales", re.I), "ANC.01", {"ACTIVO"}),
        (re.compile(r"pozos profundos", re.I), "ANC.01", {"ACTIVO"}),
        (re.compile(r"salas de bombas", re.I), "ANC.01", {"ACTIVO"}),
        (re.compile(r"bocatomas?(?:,\s*piscinas?\s*y\s*canales?)?", re.I), "ANC.01", {"ACTIVO"}),
        (re.compile(r"galpones", re.I), "ANC.01", {"ACTIVO"}),
        (re.compile(r"bodegas", re.I), "ANC.01", {"ACTIVO"}),
        (re.compile(r"derechos? de agua(?:s)?", re.I), "ANC.03", {"ACTIVO"}),
        (re.compile(r"derechos? de aprovechamiento de aguas?", re.I), "ANC.03", {"ACTIVO"}),
        (re.compile(r"documentos por pagar", re.I), "PC.01", {"PASIVO"}),
        (re.compile(r"sence", re.I), "AC.07", {"ACTIVO"}),
        (re.compile(r"credito sence", re.I), "AC.07", {"ACTIVO"}),
        (re.compile(r"combustibles y lubricantes", re.I), "ER.04", {"PERDIDA", None}),
        (re.compile(r"energ[ií]a el[eé]ctrica y suministros", re.I), "ER.04", {"PERDIDA", None}),
        (re.compile(r"sueldos y remuneraciones", re.I), "ER.04", {"PERDIDA", None}),
        (re.compile(r"leyes sociales e imposiciones", re.I), "ER.04", {"PERDIDA", None}),
        (re.compile(r"seguros agr[ií]colas y generales", re.I), "ER.04", {"PERDIDA", None}),
        (re.compile(r"asesor[ií]as t[eé]cnicas y agron[oó]micas", re.I), "ER.04", {"PERDIDA", None}),
        (re.compile(r"fletes y transportes", re.I), "ER.04", {"PERDIDA", None}),
        (re.compile(r"mantenci[oó]n y reparaci[oó]n(?: maquinaria)?", re.I), "ER.04", {"PERDIDA", None}),
        (re.compile(r"capital emitido", re.I), "PAT.01", {"PATRIMONIO"}),
        (re.compile(r"capital pagado", re.I), "PAT.01", {"PATRIMONIO"}),
        (re.compile(r"(?:otras )?reservas", re.I), "PAT.02", {"PATRIMONIO"}),
        (re.compile(r"retasaci[oó]n t[eé]cnica", re.I), "PAT.02", {"PATRIMONIO"}),
        (re.compile(r"ganancias? p[eé]rdidas? acumuladas", re.I), "PAT.03", {"PATRIMONIO"}),
        (re.compile(r"resultados acumulados", re.I), "PAT.03", {"PATRIMONIO"}),
        (re.compile(r"utilidad(?:\s*p[eé]rdida)?\s*del ejercicio", re.I), "PAT.04", {"PATRIMONIO", "PERDIDA", "GANANCIA"}),
        (re.compile(r"ingresos de (?:actividades ordinarias|explotaci[oó]n)", re.I), "ER.01", None),
        (re.compile(r"costo de (?:ventas|explotaci[oó]n)", re.I), "ER.02", None),
        (re.compile(r"gastos? de administraci[oó]n", re.I), "ER.04", None),
        (re.compile(r"costos? de distribuci[oó]n", re.I), "ER.04", {"PERDIDA", "GANANCIA", "DESCONOCIDO", None}),
        (re.compile(r"costos? financieros", re.I), "ER.09", None),
        (re.compile(r"gasto o utilidad por impuestos a las ganancias", re.I), "ER.10", None),
        (re.compile(r"gasto por impuestos a las ganancias", re.I), "ER.10", None),
        (re.compile(r"ingresos financieros", re.I), "ER.12", None),
        (re.compile(r"otras ganancias p[eé]rdidas(?: por funci[oó]n)?", re.I), "ER.13", None),
        (re.compile(r"resultados por unidades de reajuste", re.I), "ER.14", None),
        (re.compile(r"diferencias de cambio", re.I), "ER.15", None),
        (re.compile(r"participaci[oó]n en las ganancias p[eé]rdidas de asociadas y negocios", re.I), "ER.16", None),
        (re.compile(r"otros ingresos por funci[oó]n", re.I), "ER.17", None),
        (re.compile(r"otros gastos por funci[oó]n", re.I), "ER.18", None),
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
                    return canonicalize_dictionary(
                        e for e in data if e.get("codigo_estandar") != "__EXCLUIR__"
                    )
            except Exception as exc:
                logger.warning("Neon no disponible; usando diccionario JSON: %s", exc)
        path = Path(__file__).resolve().parent.parent / "diccionario.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return canonicalize_dictionary(
            e for e in data if e.get("codigo_estandar") != "__EXCLUIR__"
        )

    _ACCOUNT_ABBREVIATIONS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"\b(?:c/p|c\.p\.|cp)\b", re.I), "corto plazo"),
        (re.compile(r"\b(?:l/p|l\.p\.|lp)\b", re.I), "largo plazo"),
        (re.compile(r"\bdep(?:r)?\.?\s*acum(?:ulada)?(?:\.|\b)", re.I), "depreciacion acumulada"),
        (re.compile(r"\bamort\.?\s*acum(?:ulada)?(?:\.|\b)", re.I), "amortizacion acumulada"),
        (re.compile(r"\bcta\.?\s*cte\.?\s*", re.I), "cuenta corriente "),
        (re.compile(r"\bctas\.?\s*ctes\.?\s*", re.I), "cuentas corrientes "),
        (re.compile(r"\bcta(?:\.|\b)\s*", re.I), "cuenta "),
        (re.compile(r"\bctas(?:\.|\b)\s*", re.I), "cuentas "),
        (re.compile(r"\bdoctos(?:\.|\b)\s*", re.I), "documentos "),
        (re.compile(r"\bdocto(?:\.|\b)\s*", re.I), "documento "),
        (re.compile(r"\bdctos(?:\.|\b)\s*", re.I), "documentos "),
        (re.compile(r"\bdcto(?:\.|\b)\s*", re.I), "documento "),
        (re.compile(r"\boblig(?:\.|\b)\s*", re.I), "obligaciones "),
        (re.compile(r"\binst(?:\.|\b)\s*", re.I), "instituciones "),
        (re.compile(r"\bfinanc(?:\.|\b)\s*", re.I), "financieras "),
        (re.compile(r"\bbcos(?:\.|\b)\s*", re.I), "bancos "),
        (re.compile(r"\bbco(?:\.|\b)\s*", re.I), "banco "),
        (re.compile(r"\brelac(?:\.|\b)\s*", re.I), "relacionadas "),
        (re.compile(r"\bgtos(?:\.|\b)\s*", re.I), "gastos "),
        (re.compile(r"\bgto(?:\.|\b)\s*", re.I), "gasto "),
        (re.compile(r"\beqs(?:\.|\b)\s*|\bequip\.\s*", re.I), "equipos "),
        (re.compile(r"\beq(?:\.|\b)\s*", re.I), "equipo "),
        (re.compile(r"\bmaqs?(?:\.|\b)\s*", re.I), "maquinaria "),
        (re.compile(r"\bo\.?o\.?c\.?c\.?\s*|\boocc\s*", re.I), "obras civiles "),
        (re.compile(r"\bprov(?:\.|\b)\s*", re.I), "provision "),
        (re.compile(r"\bimpt?os(?:\.|\b)\s*", re.I), "impuestos "),
        (re.compile(r"\bvta(?:\.|\b)\s*", re.I), "venta "),
        (re.compile(r"\badmin(?:\.|\b)\s*", re.I), "administracion "),
        (re.compile(r"\bmat(?:\.|\b)\s*", re.I), "materiales "),
    ]

    _PATRONES_RUIDO_ERP: list[re.Pattern] = [
        re.compile(r"^\s*Usuario\s*:\s*\w+", re.I),
        re.compile(r"^\s*HASTA\s+\d{1,2}/\d{1,2}/\d{4}", re.I),
        re.compile(r"^\s*[\$\s=_\-*#]+\s*$"),
        re.compile(r"^\s*(?:BALANCE|GASTOS|INGRESOS|FINANCIEROS|PLAZO|BALANCE\s+GENERAL|BALANCE\s+TRIBUTARIO|ESTADO\s+DE\s+SITUACION|P[AÁ]GINA\s+\d+)\s*$", re.I),
    ]

    @classmethod
    def _expand_abbreviations(cls, text: str) -> str:
        for pattern, replacement in cls._ACCOUNT_ABBREVIATIONS:
            text = pattern.sub(replacement, text)
        return text

    @classmethod
    def _is_erp_metadata_noise(
        cls, account_name: str, monto: float | None = None, account_code: str | None = None,
    ) -> bool:
        if not account_name:
            return True
        raw = account_name.strip()
        if account_code:
            return False
        if monto is not None and abs(float(monto)) > 0.01:
            if re.fullmatch(r"[=\-*_.#/\s]{3,}", raw):
                return True
            return False
        for pat in cls._PATRONES_RUIDO_ERP:
            if pat.search(raw):
                return True
        return False

    @classmethod
    def _normalize_name(cls, name: str) -> str:
        name = name.lower().strip()
        name = cls._expand_abbreviations(name)
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

    @staticmethod
    def _is_plausible_account_name(name: str | None) -> bool:
        """Valida si una glosa de cuenta tiene una estructura léxica plausible.

        Filtra artefactos de OCR degradado, ruido numérico o secuencias espurias
        que no corresponden a nombres de cuenta reales.
        """
        if not name or not isinstance(name, str):
            return False
        clean = name.strip()
        if len(clean) < 2:
            return False

        letras = [c for c in clean if c.isalpha()]
        if len(letras) < 2:
            return False

        if "%" in clean or "[]" in clean or "{}" in clean:
            return False

        if len(re.findall(r"\b\d{6,}\b", clean)) >= 2:
            return False

        if re.search(r"([a-zA-Z])\1{2,}", clean):
            return False

        chars_no_space = [c for c in clean if not c.isspace()]
        ratio_letras = len(letras) / max(len(chars_no_space), 1)
        if ratio_letras < 0.30:
            return False

        if " " not in clean and len(clean) >= 6:
            vocales = [c for c in clean.lower() if c in "aeiouáéíóúü"]
            if not vocales or (len(vocales) / len(clean)) < 0.15:
                return False

        return True

    def _classify_by_code(
        self, account_code: str, account_name: str = "",
    ) -> dict[str, Any] | None:
        result = self._code_classifier.clasificar(account_code)
        if result is not None:
            is_plausible = self._is_plausible_account_name(account_name) if account_name else True
            conf = result.confianza if is_plausible else min(result.confianza, 0.50)
            reason = result.razon
            if not is_plausible and account_name:
                reason += " (advertencia: nombre de cuenta no plausible / sospechoso de ruido OCR)"
            return {
                "standard_code": result.codigo_estandar,
                "confidence": conf,
                "method": "code",
                "reason": reason,
                "plausible_name": is_plausible,
            }
        return None

    def _classify_by_dictionary_exact(self, account_name: str) -> dict[str, Any] | None:
        normalized = self._normalize_name(account_name)
        for entry in self._dictionary:
            if self._normalize_name(entry["cuenta_original"]) == normalized:
                code = (
                    "ANC.01.01" if is_ppe_depreciation_name(account_name)
                    else entry["codigo_estandar"]
                )
                return {
                    "standard_code": code,
                    "confidence": 0.98,
                    "method": "dictionary_exact",
                    "reason": f"Coincidencia exacta con diccionario → {code}",
                }
        return None

    def _classify_by_hierarchy(
        self, account_hierarchy: str | None, account_tipo: str | None,
        account_section: str | None = None,
    ) -> dict[str, Any] | None:
        """Hereda sólo categorías inequívocas desde un subtotal reconocido."""
        hierarchy = self._normalize_name(account_hierarchy or "")
        rules = (
            (r"(?:caja y )?bancos?", "AC.01", {"ACTIVO"}),
            (r"efectivo y equivalentes(?: al efectivo)?", "AC.01", {"ACTIVO"}),
            (r"depreciaci(?:o|ó)n acumulada", "ANC.01.01", {"ACTIVO", "PASIVO"}),
            (r"proveedores", "PC.01", {"PASIVO"}),
            (r"capital social", "PAT.01", {"PASIVO", "PATRIMONIO"}),
        )
        for pattern, code, allowed_types in rules:
            if re.fullmatch(pattern, hierarchy) and account_tipo in allowed_types:
                if not self._is_code_allowed_for_section(code, account_section):
                    continue
                return {
                    "standard_code": code,
                    "confidence": 0.99,
                    "method": "hierarchy_inheritance",
                    "reason": (
                        f"Detalle contenido en subtotal inequívoco "
                        f"'{account_hierarchy}' → {code}"
                    ),
                }
        return None

    def _classify_audited_statement_label(
        self, account_name: str, account_tipo: str | None,
        account_section: str | None = None,
    ) -> dict[str, Any] | None:
        """Resuelve nombres completos estandarizados de estados auditados."""
        normalized = self._normalize_name(account_name)
        normalized_section = self._normalize_name(account_section or "")
        sec_code = self._normalize_section_code(account_section)
        is_no_corriente = "no corrient" in normalized_section or sec_code in {"ANC", "PNC"}
        # Política global aprobada el 2026-09-07: no trasladar una etiqueta
        # de activo corriente a AC.08 cuando la sección acredita largo plazo.
        if (
            re.fullmatch(r"otros activos financieros(?: corrientes?)?", normalized)
            and (is_no_corriente or sec_code == "ANC")
        ):
            return None
        if (
            re.fullmatch(r"(?:otros )?pasivos financieros", normalized)
            and (is_no_corriente or sec_code == "PNC")
            and account_tipo == "PASIVO"
        ):
            return {
                "standard_code": "PNC.05" if normalized.startswith("otros ") else "PNC.01",
                "confidence": 0.96,
                "method": "audited_statement_label",
                "reason": "Etiqueta exacta en sección de pasivos no corrientes",
            }
        for pattern, code, allowed_types in self._AUDITED_STATEMENT_LABELS:
            if not pattern.fullmatch(normalized):
                continue
            if allowed_types is not None and account_tipo not in allowed_types:
                continue
            if not self._is_code_allowed_for_section(code, account_section):
                continue
            return {
                "standard_code": code,
                "confidence": 0.96,
                "method": "audited_statement_label",
                "reason": f"Etiqueta exacta de estado financiero auditado → {code}",
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
                "ANC.01.01" if is_ppe_depreciation_name(account_name)
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

    @staticmethod
    def _canonicalize_special_code(
        result: dict[str, Any], account_name: str,
    ) -> dict[str, Any]:
        """Migra decisiones antiguas al código específico vigente."""
        previous_code = result.get("standard_code")
        canonical_code = canonical_catalog_code(previous_code)
        if canonical_code and canonical_code != previous_code:
            result = {**result, "standard_code": canonical_code}
            result["reason"] = (
                f"{result.get('reason', 'Clasificación previa')}; "
                f"código histórico {previous_code} normalizado a {canonical_code}"
            )
        if (is_ppe_depreciation_name(account_name)
                and result.get("standard_code") == "ANC.01"):
            result = {**result, "standard_code": "ANC.01.01"}
            result["reason"] = (
                f"{result.get('reason', 'Clasificación previa')}; "
                "contra-activo normalizado a ANC.01.01"
            )
        elif (result.get("standard_code") == "ANC.01.01"
              and not is_ppe_depreciation_name(account_name)):
            result = {**result, "standard_code": None, "confidence": 0.0,
                      "method": "unclassified"}
            result["reason"] = (
                f"{result.get('reason', 'Clasificación previa')}; "
                "ANC.01.01 incompatible con la etiqueta; requiere revisión sin sustitución automática"
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
                if not self._is_valid_ppe_depreciation(cod, account_name):
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
    ) -> dict[str, Any] | None:
        """Aplica reglas amplias solo cuando la columna contable las valida."""
        if not account_name or not account_tipo:
            return None
        normalized = self._normalize_name(account_name)
        if account_tipo == "ACTIVO" and is_ppe_depreciation_name(account_name):
            return {
                "standard_code": "ANC.01.01",
                "confidence": 0.84,
                "method": "regex_contextual",
                "reason": (
                    "Contra-activo identificado por nombre y columna acreedora → "
                    "ANC.01.01; requiere revisión humana"
                ),
            }
        for pattern, code, confidence in self._REGEX_CONTEXTUAL:
            if (pattern.search(normalized)
                    and self._is_code_allowed_for_tipo(code, account_tipo)
                    and self._is_valid_ppe_depreciation(code, account_name)):
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
        account_code: str, account_tipo: str | None,
    ) -> dict[str, Any] | None:
        """Evita dejar sin categoría balances sin códigos y con columna fiable."""
        if account_code or not account_tipo:
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
                f"Categoría residual inferida desde columna {account_tipo}; "
                "requiere revisión humana"
            ),
        }

    @staticmethod
    def _normalize_section_code(section: str | None) -> str | None:
        if not section:
            return None
        raw = re.sub(r"\s+", " ", str(section).strip()).lower()
        raw = re.sub(r"^(?:total(?:es)?\s+(?:de\s+)?)", "", raw).strip()
        raw = re.sub(r"\s+(?:total|totales)$", "", raw).strip()
        if raw in {"ac", "activo corriente", "activos corrientes", "activo circulante", "activos circulantes"}:
            return "AC"
        if raw in {"anc", "activo no corriente", "activos no corrientes", "activo fijo", "activos fijos"}:
            return "ANC"
        if raw in {"pc", "pasivo corriente", "pasivos corrientes", "pasivo circulante", "pasivos circulantes"}:
            return "PC"
        if raw in {"pnc", "pasivo no corriente", "pasivos no corrientes", "pasivo a largo plazo", "pasivos a largo plazo"}:
            return "PNC"
        if raw in {"pat", "patrimonio", "patrimonio neto"}:
            return "PAT"
        if raw in {"er", "estado de resultados", "resultado", "resultados", "perdidas y ganancias"}:
            return "ER"
        return None

    @classmethod
    def _is_code_allowed_for_section(cls, code: str | None, section: str | None) -> bool:
        if not code or not section:
            return True
        sec = cls._normalize_section_code(section)
        if not sec:
            return True
        if sec == "AC":
            return not (code.startswith("ANC.") or code.startswith("PNC.") or code.startswith("PC.") or code.startswith("PAT.") or code.startswith("ER."))
        if sec == "ANC":
            return not (code.startswith("AC.") or code.startswith("PNC.") or code.startswith("PC.") or code.startswith("PAT.") or code.startswith("ER."))
        if sec == "PC":
            return not (code.startswith("PNC.") or code.startswith("ANC.") or code.startswith("AC.") or code.startswith("PAT.") or code.startswith("ER."))
        if sec == "PNC":
            return not (code.startswith("PC.") or code.startswith("ANC.") or code.startswith("AC.") or code.startswith("PAT.") or code.startswith("ER."))
        if sec == "PAT":
            return code.startswith("PAT.")
        if sec == "ER":
            return code.startswith("ER.")
        return True

    @staticmethod
    def _is_valid_ppe_depreciation(code: str | None, account_name: str) -> bool:
        if code == "ANC.01.01":
            return is_ppe_depreciation_name(account_name)
        return True

    def _is_code_allowed(
        self,
        code: str | None,
        tipo: str | None,
        section: str | None = None,
    ) -> bool:
        if not code:
            return True
        if self._features.ENABLE_ACCOUNT_TYPE_FILTER and tipo:
            if not self._is_code_allowed_for_tipo(code, tipo):
                return False
        if section and not self._is_code_allowed_for_section(code, section):
            return False
        return True

    def _classify_account(
        self, account_code: str, account_name: str,
        account_tipo: str | None = None,
        store_cmcc_shadow: bool = True,
        account_section: str | None = None,
        account_hierarchy: str | None = None,
    ) -> dict[str, Any]:
        # Las etiquetas canónicas completas de estados auditados son evidencia
        # más fuerte que similitudes históricas. Se resuelven antes del motor
        # aprendido para impedir que una asociación antigua las desvíe.
        audited_result = self._classify_audited_statement_label(
            account_name, account_tipo, account_section,
        )
        if audited_result is not None:
            return self._canonicalize_special_code(audited_result, account_name)

        hierarchy_result = self._classify_by_hierarchy(
            account_hierarchy, account_tipo, account_section,
        )
        if hierarchy_result is not None:
            return self._canonicalize_special_code(hierarchy_result, account_name)

        learning_result = self._learning_engine.best_match(account_name)
        if learning_result["source"] != "none":
            l_code = learning_result["code"]
            if (self._is_code_allowed(l_code, account_tipo, account_section)
                    and self._is_valid_ppe_depreciation(l_code, account_name)):
                return self._canonicalize_special_code({
                    "standard_code": l_code,
                    "confidence": learning_result["confidence"],
                    "method": f"learning_{learning_result['source']}",
                    "reason": (
                        f"Gold Standard ({learning_result['source']}) → "
                        f"{l_code} "
                        f"(matched: {learning_result['matched_name']})"
                    ),
                }, account_name)

        cmcc_raw: dict[str, Any] | None = None
        cmcc_score = -1.0

        if self._features.ENABLE_CMCC:
            cmcc_raw = self._cmcc_classifier.classify(account_name)
            cmcc_score = cmcc_raw.get("score", 0.0) if cmcc_raw else -1.0

        result: dict[str, Any] | None = None

        if (
            self._features.ENABLE_CMCC_PRODUCTION
            and cmcc_score >= self._features.CMCC_THRESHOLD
            and cmcc_raw is not None
            and self._is_code_allowed(cmcc_raw.get("code"), account_tipo, account_section)
            and self._is_valid_ppe_depreciation(cmcc_raw.get("code"), account_name)
        ):
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
                account_section=account_section,
            )
            result = self._canonicalize_special_code(result, account_name)
            if (not self._is_code_allowed(result.get("standard_code"), account_tipo, account_section)
                    or not self._is_valid_ppe_depreciation(result.get("standard_code"), account_name)):
                result["standard_code"] = None
                result["confidence"] = 0.0
                result["method"] = "unclassified"
                result["reason"] = f"Filtrado: código incompatible con sección {account_section} o tipo {account_tipo}"
            result["_cmcc_score"] = cmcc_score
            if cmcc_raw is not None:
                result["cmcc_detail"] = cmcc_raw
            if store_cmcc_shadow and cmcc_raw is not None:
                result["cmcc_shadow"] = cmcc_raw
            return result

        # --- Original first-match-wins path (DE disabled) ---
        candidates = [
            result,
            self._classify_by_code(account_code, account_name),
            self._classify_audited_statement_label(account_name, account_tipo, account_section),
            self._classify_by_dictionary_exact(account_name),
            self._classify_by_dictionary_fuzzy(account_name),
        ]
        result = None
        for cand in candidates:
            if (cand
                    and self._is_code_allowed(cand.get("standard_code"), account_tipo, account_section)
                    and self._is_valid_ppe_depreciation(cand.get("standard_code"), account_name)):
                result = cand
                break

        if result is None and self._features.ENABLE_SEMANTIC_MATCHER and self._semantic_matcher is not None:
            sm_result = self._semantic_matcher.match(account_name, account_tipo)
            if (not sm_result.is_unknown
                    and self._is_code_allowed(sm_result.expected_cmcc, account_tipo, account_section)
                    and self._is_valid_ppe_depreciation(sm_result.expected_cmcc, account_name)):
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
            reg_cand = self._classify_by_regex(account_name, account_tipo)
            if (reg_cand
                    and self._is_code_allowed(reg_cand.get("standard_code"), account_tipo, account_section)
                    and self._is_valid_ppe_depreciation(reg_cand.get("standard_code"), account_name)):
                result = reg_cand

        if result is None:
            reg_cand = self._classify_by_regex_contextual(account_name, account_tipo)
            if (reg_cand
                    and self._is_code_allowed(reg_cand.get("standard_code"), account_tipo, account_section)
                    and self._is_valid_ppe_depreciation(reg_cand.get("standard_code"), account_name)):
                result = reg_cand

        if result is None:
            orig_cand = self._classify_by_origin_fallback(account_code, account_tipo)
            if (orig_cand
                    and self._is_code_allowed(orig_cand.get("standard_code"), account_tipo, account_section)
                    and self._is_valid_ppe_depreciation(orig_cand.get("standard_code"), account_name)):
                result = orig_cand

        if result is None:
            result = {
                "standard_code": None,
                "confidence": 0.0,
                "method": "unclassified",
                "reason": "Sin coincidencia en código ni diccionario",
            }

        result = self._canonicalize_special_code(result, account_name)

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
        account_section: str | None = None,
    ) -> dict[str, Any]:
        from decision.models import DecisionResult as DEResult

        code_r = self._classify_by_code(account_code, account_name)
        if code_r and (not self._is_code_allowed(code_r.get("standard_code"), account_tipo, account_section)
                       or not self._is_valid_ppe_depreciation(code_r.get("standard_code"), account_name)):
            code_r = None

        dict_r = (
            self._classify_audited_statement_label(account_name, account_tipo, account_section)
            or self._classify_by_dictionary_exact(account_name)
            or self._classify_by_dictionary_fuzzy(account_name)
        )
        if dict_r and (not self._is_code_allowed(dict_r.get("standard_code"), account_tipo, account_section)
                       or not self._is_valid_ppe_depreciation(dict_r.get("standard_code"), account_name)):
            dict_r = None

        sm_match = None
        sm_code = None
        sm_score = None
        sm_tier = None
        sm_confidence = None
        if self._features.ENABLE_SEMANTIC_MATCHER and self._semantic_matcher is not None:
            sm_match = self._semantic_matcher.match(account_name, account_tipo)
            if (not sm_match.is_unknown
                    and self._is_code_allowed(sm_match.expected_cmcc, account_tipo, account_section)
                    and self._is_valid_ppe_depreciation(sm_match.expected_cmcc, account_name)):
                sm_code = sm_match.expected_cmcc
                sm_score = sm_match.score
                sm_tier = sm_match.match_tier
                sm_confidence = sm_match.confidence

        regex_r = None
        if self._features.ENABLE_REGEX_FALLBACK:
            regex_r = self._classify_by_regex(account_name, account_tipo)
            if regex_r and (not self._is_code_allowed(regex_r.get("standard_code"), account_tipo, account_section)
                            or not self._is_valid_ppe_depreciation(regex_r.get("standard_code"), account_name)):
                regex_r = None

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

    def process(self, pdf_path: str | Path) -> dict[str, Any]:
        start = time.perf_counter()
        path = Path(pdf_path)
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
            )
        else:
            resultado = self._parser.parsear(path)
        accounts_total = len(resultado.cuentas)
        logger.info("accounts_total: %d", accounts_total)

        classified: list[dict[str, Any]] = []
        ignored: list[dict[str, Any]] = []
        controls_count = 0
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
            ab: AccountBalance = AccountAdapter.from_cuenta_raw(cr)
            interp = BalanceInterpreter(ab)

            if cr.es_total:
                controls_count += 1
                ignored.append({
                    "account_code": ab.account_code,
                    "account_name": ab.account_name,
                    "monto": cr.monto,
                    "ignored_reason": "control_total",
                    "is_total": True,
                })
                continue

            if self._is_erp_metadata_noise(ab.account_name, cr.monto, ab.account_code):
                ignored.append({
                    "account_code": ab.account_code,
                    "account_name": ab.account_name,
                    "monto": cr.monto,
                    "ignored_reason": "metadato_erp",
                })
                continue

            classification_amount = interp.classification_amount
            # Los estados financieros auditados suelen traer sólo importes
            # comparativos y no las ocho columnas del balance tributario. En
            # ese formato ``BalanceInterpreter`` no puede inferir una columna
            # física, pero el monto del período actual sigue siendo una cuenta
            # clasificable. Los controles impresos permanecen fuera del flujo.
            if (
                classification_amount is None
                and cr.monto is not None
                and cr.montos_periodos
                and not cr.es_total
            ):
                classification_amount = float(cr.monto)

            tipo_result = type_resolver.resolve(
                origen_columna=cr.origen_columna,
                codigo=cr.codigo,
            )
            account_tipo = tipo_result.account_type.value
            contextual_name = " ".join(filter(None, (
                cr.jerarquia_contable, ab.account_name,
            )))
            if account_tipo == "PASIVO" and is_contra_asset_name(contextual_name):
                account_tipo = "ACTIVO"
            if is_equity_account_name(ab.account_name):
                account_tipo = "PATRIMONIO"

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
            classification = self._classify_account(
                ab.account_code, ab.account_name,
                account_tipo=account_tipo,
                store_cmcc_shadow=store_shadow,
                account_section=cr.seccion_contable,
                account_hierarchy=cr.jerarquia_contable,
            )

            if classification.get("standard_code"):
                code_cand = classification["standard_code"]
                tipo_invalido = bool(enable_type_filter and account_tipo and not self._is_code_allowed_for_tipo(code_cand, account_tipo))
                seccion_invalida = bool(cr.seccion_contable and not self._is_code_allowed_for_section(code_cand, cr.seccion_contable))
                ppe_invalido = bool(not self._is_valid_ppe_depreciation(code_cand, ab.account_name))
                if tipo_invalido or seccion_invalida or ppe_invalido:
                    motivo = ("tipo " + str(account_tipo)) if tipo_invalido else (
                        ("sección " + str(cr.seccion_contable)) if seccion_invalida else "restricción ANC.01.01 de PPE"
                    )
                    classification["standard_code"] = None
                    classification["confidence"] = 0.0
                    classification["method"] = "unclassified"
                    classification["reason"] = f"Filtrado: código incompatible con {motivo}"
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

            if classification.get("standard_code") is None:
                unclassified_count += 1

            is_column_bleed = (
                getattr(cr, "requiere_revision_extraccion", False)
                or bool(re.search(
                    r"[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]\d+[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]|\d+[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]+\d+|\b\w*(?:[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]\d{1,2}\.\d{3}|\d{1,2}\.[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ])\w*",
                    ab.account_name,
                ))
            )

            requires_review_by_code = False
            if classification.get("method") in {"code", "codigo"}:
                is_plausible = self._is_plausible_account_name(ab.account_name)
                if not is_plausible or not classification.get("plausible_name", True):
                    requires_review_by_code = True

            review_required = (
                adjustment.requiere_revision
                or classification.get("method") in RESIDUAL_CLASSIFICATION_METHODS
                or requires_review_by_code
                or is_column_bleed
            )

            account_confidence = classification.get("confidence", 0.0)
            account_reason = classification.get("reason", "")
            if is_column_bleed:
                account_confidence = min(account_confidence, 0.50)
                if "fusión de columnas" not in account_reason:
                    account_reason = (account_reason + " (advertencia: posible contaminación por fusión/solapamiento de columnas)").strip()

            classified.append({
                "account_code": ab.account_code,
                "account_name": ab.account_name,
                "nature": interp.nature.value,
                "classification_amount": classification_amount,
                "standard_code": classification.get("standard_code"),
                "final_code": final_code,
                "confidence": account_confidence,
                "method": classification.get("method", "unknown"),
                "reason": account_reason,
                "special_rule": adjustment.nota if adjustment.aplica else None,
                "review_required": review_required,
                "source_file": path.name,
                "source_page": ab.source_page,
                "semantic_result": semantic_result,
                "cmcc_shadow": cmcc_shadow,
                "cmcc_decision": classification.get("cmcc_detail"),
            })

        metric_contract = account_metrics(classified, controls_count)
        accounts_classified = metric_contract["accounts_classified"]
        accounts_ignored = len(ignored)
        accounts_without_dictionary_match = unclassified_count

        elapsed = time.perf_counter() - start

        summary = {
            "source_file": path.name,
            "ocr": bool(getattr(resultado, "requirio_ocr", False)),
            "requirio_ocr": bool(getattr(resultado, "requirio_ocr", False)),
            "accounts_total": accounts_total,
            "accounts_classified": accounts_classified,
            "accounts_ignored": accounts_ignored,
            "accounts_without_dictionary_match": accounts_without_dictionary_match,
            **metric_contract,
            "learning_hits": learning_hits,
            "learning_exact": learning_exact,
            "learning_fuzzy": learning_fuzzy,
            "fallback_classifier": fallback_classifier,
            "fallback_classifier_legacy": fallback_classifier,
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
        summary["document_family"] = document_family(
            {"requirio_ocr": getattr(resultado, "requirio_ocr", False)}, classified,
        )
        summary["balance_reconciliation"] = compare_pre_post(
            getattr(resultado, "certificacion_extraccion", None), classified,
        )
        summary["extraction_status"] = "success" if accounts_total > 0 else "failed"
        summary["export_blocked_by_classification_degradation"] = bool(
            summary["balance_reconciliation"]["classification_degradation"]
        )
        summary["export_blocked_by_empty_document"] = bool(accounts_total == 0)

        logger.info(
            "total=%d specific=%d residual=%d unclassified=%d controls=%d ignored=%d (%.3fs)",
            accounts_total, metric_contract["accounts_classified_specific"],
            metric_contract["accounts_classified_residual"], metric_contract["accounts_unclassified"],
            metric_contract["accounts_controls"], accounts_ignored, elapsed,
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
