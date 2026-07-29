from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from document_context import DocumentContext
from document_context.models import KnowledgeData


class KBAdapter:
    def __init__(self, db_path: str | Path = "gold_standard.db"):
        from pipeline.homologation_pipeline import HomologationPipeline
        self._pipeline = HomologationPipeline(db_path=db_path)

    def run(self, ctx: DocumentContext) -> DocumentContext:
        path = Path(ctx.source_file)
        if not path.exists():
            ctx.set_custom("kb_error", f"File not found: {path}")
            return ctx

        raw_accounts = ctx.parser.raw_accounts if ctx.parser else []
        if not raw_accounts:
            ctx.set_custom("classified", [])
            ctx.set_custom("ignored", [])
            knowledge = KnowledgeData()
            ctx.set_knowledge(knowledge, module="kb_adapter")
            return ctx

        start = time.perf_counter()
        classified = self._classify_accounts(ctx, raw_accounts)
        elapsed = time.perf_counter() - start

        ignored = [c for c in classified if c.get("standard_code") is None and c.get("method") == "ignored"]
        classified_filtered = [c for c in classified if c not in ignored]

        cmcc_matches = [c for c in classified_filtered if c.get("cmcc_shadow") is not None or c.get("cmcc_decision") is not None]
        learning_hits_list = [c for c in classified_filtered if c.get("method", "").startswith("learning_")]
        dictionary_matches = [c for c in classified_filtered if "dictionary" in c.get("method", "")]

        knowledge = KnowledgeData(
            cmcc_matches=cmcc_matches,
            learning_hits=learning_hits_list,
            dictionary_matches=dictionary_matches,
        )
        ctx.set_knowledge(knowledge, module="kb_adapter")
        ctx.set_custom("classified", classified_filtered)
        ctx.set_custom("ignored", ignored)
        ctx.set_custom("kb_elapsed", round(elapsed, 3))

        return ctx

    def _classify_accounts(self, ctx: DocumentContext, raw_accounts: list[Any]) -> list[dict[str, Any]]:
        from adapters.account_adapter import AccountAdapter
        from interpreters.balance_interpreter import BalanceInterpreter
        from parsers.account_type_resolver import AccountTypeResolver

        type_resolver = AccountTypeResolver()
        classified = []
        total_classified = 0
        for cr in raw_accounts:
            ab = AccountAdapter.from_cuenta_raw(cr)
            interp = BalanceInterpreter(ab)
            classification_amount = interp.classification_amount
            tipo_result = type_resolver.resolve(
                origen_columna=getattr(cr, "origen_columna", None),
                codigo=getattr(cr, "codigo", ""),
            )
            account_tipo = getattr(tipo_result, "account_type", tipo_result)
            if hasattr(account_tipo, "value"):
                account_tipo = account_tipo.value

            if classification_amount is None or classification_amount == 0:
                classified.append({
                    "account_code": ab.account_code,
                    "account_name": ab.account_name,
                    "ignored_reason": "movement_only",
                    "standard_code": None,
                    "method": "ignored",
                })
                continue

            classification = self._pipeline._classify_account(
                ab.account_code, ab.account_name,
                account_tipo=account_tipo,
                store_cmcc_shadow=True,
            )

            if self._pipeline._features.ENABLE_ACCOUNT_TYPE_FILTER and account_tipo and classification.get("standard_code"):
                if not self._pipeline._is_code_allowed(classification["standard_code"], account_tipo):
                    classification["standard_code"] = None
                    classification["confidence"] = 0.0
                    classification["method"] = "unclassified"
                    classification["reason"] = f"Filtrado: código incompatible con tipo {account_tipo}"

            semantic_result = self._pipeline._semantic_engine.interpret(ab).to_dict()
            adjustment = self._pipeline._rule_processor.aplicar(
                nombre_cuenta=ab.account_name,
                codigo_clasificado=classification.get("standard_code") or "",
                monto=classification_amount,
            )

            final_code = (
                adjustment.codigo_final
                if adjustment.aplica
                else classification.get("standard_code")
            )

            total_classified += 1

            classified.append({
                "account_code": ab.account_code,
                "account_name": ab.account_name,
                "nature": getattr(interp, "nature", ab.account_code).value if hasattr(getattr(interp, "nature", ab.account_code), "value") else "",
                "classification_amount": classification_amount,
                "standard_code": classification.get("standard_code"),
                "final_code": final_code,
                "confidence": classification.get("confidence", 0.0),
                "method": classification.get("method", "unknown"),
                "reason": classification.get("reason", ""),
                "special_rule": adjustment.nota if adjustment.aplica else None,
                "source_file": Path(ctx.source_file).name,
                "source_page": getattr(ab, "source_page", 0),
                "semantic_result": semantic_result,
                "cmcc_shadow": classification.get("cmcc_shadow"),
                "cmcc_decision": classification.get("cmcc_detail"),
            })

        return classified

    @staticmethod
    def extract_v1_summary(ctx: DocumentContext) -> dict[str, Any]:
        result = ctx.get_custom("pipeline_v1_result")
        if result is not None:
            return dict(result)
        classified = ctx.get_custom("classified", [])
        ignored = ctx.get_custom("ignored", [])
        return {
            "source_file": Path(ctx.source_file).name,
            "accounts_total": len(classified) + len(ignored),
            "accounts_classified": len(classified),
            "accounts_ignored": len(ignored),
            "classified": classified,
            "ignored": ignored,
        }
