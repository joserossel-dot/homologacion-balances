from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from adapters.account_adapter import AccountAdapter
from app_validacion import REGLAS_REGEX, parsear_excel
from clasificador_codigo_cuenta import ClasificadorCodigo
from interpreters.balance_interpreter import BalanceInterpreter
from learning.engine import LearningEngine
from models.account_balance import AccountBalance
from parser_universal import FormatoCodigo, ParserPDF, ResultadoParseo
from pipeline.cmcc_classifier import CMCCClassifier
from pipeline.features import CMCCFeatureFlags
from reglas_especiales import ProcesadorReglasEspeciales
from decision.engine import DecisionEngine
from semantic.semantic_engine import SemanticEngine
from semantic.matcher import SemanticMatcher

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
    # Indices into REGLAS_REGEX: PC.05(16), PC.08(19), PAT.02(26),
    #                             ER.04(31), ER.09(34), ER.10(35), ER.11(36)
    # ------------------------------------------------------------------

    _REGEX_FALLBACK: list[tuple[re.Pattern, str, float]] = [
        (re.compile(REGLAS_REGEX[i][0], re.IGNORECASE | re.UNICODE), REGLAS_REGEX[i][1], REGLAS_REGEX[i][2])
        for i in (16, 19, 26, 31, 34, 35, 36)
    ]

    # ------------------------------------------------------------------
    # Dictionary loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_dictionary() -> list[dict[str, str]]:
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
                return {
                    "standard_code": entry["codigo_estandar"],
                    "confidence": 0.98,
                    "method": "dictionary_exact",
                    "reason": f"Coincidencia exacta con diccionario → {entry['codigo_estandar']}",
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
            return {
                "standard_code": best_entry["codigo_estandar"],
                "confidence": round(confidence, 4),
                "method": "dictionary_fuzzy",
                "reason": (
                    f"Coincidencia fuzzy ({best_score}%) con "
                    f"'{best_entry['cuenta_original']}' → {best_entry['codigo_estandar']}"
                ),
            }
        return None

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
        if learning_result["source"] != "none":
            return {
                "standard_code": learning_result["code"],
                "confidence": learning_result["confidence"],
                "method": f"learning_{learning_result['source']}",
                "reason": (
                    f"Gold Standard ({learning_result['source']}) → "
                    f"{learning_result['code']} "
                    f"(matched: {learning_result['matched_name']})"
                ),
            }

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
            result["_cmcc_score"] = cmcc_score
            if cmcc_raw is not None:
                result["cmcc_detail"] = cmcc_raw
            if store_cmcc_shadow and cmcc_raw is not None:
                result["cmcc_shadow"] = cmcc_raw
            return result

        # --- Original first-match-wins path (DE disabled) ---
        result = (
            result
            or self._classify_by_code(account_code)
            or self._classify_by_dictionary_exact(account_name)
            or self._classify_by_dictionary_fuzzy(account_name)
        )

        if result is None and self._features.ENABLE_SEMANTIC_MATCHER and self._semantic_matcher is not None:
            sm_result = self._semantic_matcher.match(account_name, account_tipo)
            if not sm_result.is_unknown:
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
            result = {
                "standard_code": None,
                "confidence": 0.0,
                "method": "unclassified",
                "reason": "Sin coincidencia en código ni diccionario",
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
            ab: AccountBalance = AccountAdapter.from_cuenta_raw(cr)
            interp = BalanceInterpreter(ab)

            classification_amount = interp.classification_amount

            tipo_result = type_resolver.resolve(
                origen_columna=cr.origen_columna,
                codigo=cr.codigo,
            )
            account_tipo = tipo_result.account_type.value

            if classification_amount is None or classification_amount == 0:
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
            )

            if enable_type_filter and account_tipo and classification.get("standard_code"):
                if not self._is_code_allowed_for_tipo(classification["standard_code"], account_tipo):
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
            )

            final_code = (
                adjustment.codigo_final
                if adjustment.aplica
                else classification.get("standard_code")
            )

            if classification.get("standard_code") is None:
                unclassified_count += 1

            classified.append({
                "account_code": ab.account_code,
                "account_name": ab.account_name,
                "nature": interp.nature.value,
                "classification_amount": classification_amount,
                "standard_code": classification.get("standard_code"),
                "final_code": final_code,
                "confidence": classification.get("confidence", 0.0),
                "method": classification.get("method", "unknown"),
                "reason": classification.get("reason", ""),
                "special_rule": adjustment.nota if adjustment.aplica else None,
                "source_file": path.name,
                "source_page": ab.source_page,
                "semantic_result": semantic_result,
                "cmcc_shadow": cmcc_shadow,
                "cmcc_decision": classification.get("cmcc_detail"),
            })

        accounts_classified = len(classified)
        accounts_ignored = len(ignored)
        accounts_without_dictionary_match = unclassified_count

        elapsed = time.perf_counter() - start

        summary = {
            "source_file": path.name,
            "accounts_total": accounts_total,
            "accounts_classified": accounts_classified,
            "accounts_ignored": accounts_ignored,
            "accounts_without_dictionary_match": accounts_without_dictionary_match,
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
        if tipo == "DESCONOCIDO" or not standard_code:
            return True
        _PREFIX_TIPO: dict[str, set[str]] = {
            "ANC": {"ACTIVO"},
            "AC": {"ACTIVO"},
            "PNC": {"PASIVO"},
            "PC": {"PASIVO"},
            "PAT": {"PATRIMONIO"},
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
