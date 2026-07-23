from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from evidence.account_evidence import AccountEvidence, MonetaryAmounts


def build_from_shadow_entry(
    entry: dict[str, Any],
    *,
    context_before: list[dict] | None = None,
    context_after: list[dict] | None = None,
) -> AccountEvidence:
    semantic = entry.get("semantic_result", {}) or {}

    # Attempt to extract company info from source_path
    company_info = _extract_company_from_path(
        entry.get("source_path", "") or entry.get("source_file", "")
    )
    year = _extract_year_from_name(entry.get("account_name", ""))

    amounts = _build_monetary(entry)
    classification_amount = entry.get("classification_amount", 0.0) or 0.0

    ev = AccountEvidence(
        source_file=entry.get("source_file", ""),
        source_group=entry.get("source_group", ""),
        source_page=entry.get("source_page", 0) or 0,
        row_number=0,
        company_name=company_info.get("company", ""),
        company_rut=company_info.get("rut", ""),
        company_business="",
        year=year,
        original_account_code=entry.get("account_code", ""),
        clean_account_code=entry.get("account_code", ""),
        original_account_name=entry.get("account_name", ""),
        clean_account_name=_clean_name(entry.get("account_name", "")),
        classification_method=entry.get("method", "unknown"),
        classification_confidence=entry.get("confidence", 0.0) or 0.0,
        learning_hit=entry.get("method", "").startswith("learning"),
        semantic_hit=semantic.get("semantic_type", "unknown") != "unknown",
        semantic_rule=semantic.get("matched_rule", ""),
        semantic_type=semantic.get("semantic_type", ""),
        dictionary_match=entry.get("method", "") if "dictionary" in entry.get("method", "") else "",
        gold_standard_match="",
        final_code=entry.get("final_code", "") or entry.get("standard_code", "") or "",
        final_confidence=entry.get("confidence", 0.0) or 0.0,
        monetary=amounts,
        classification_amount=classification_amount,
        sign="",
        expected_side=semantic.get("expected_side", ""),
        context_before=context_before or [],
        context_after=context_after or [],
        raw_text=entry.get("account_name", ""),
        metadata={
            "reason": entry.get("reason", ""),
            "nature": entry.get("nature", ""),
        },
        source_path=entry.get("source_path", ""),
        source_raw=entry,
    )

    if not ev.source_file and ev.source_path:
        ev.source_file = Path(ev.source_path).name

    return ev


def build_from_account_balance(
    account: Any,
    source_file: str = "",
    source_group: str = "",
    context_before: list | None = None,
    context_after: list | None = None,
) -> AccountEvidence:
    amounts = _build_amounts_from_model(account)
    classification_amount = _pick_classification_amount(amounts)
    name = getattr(account, "account_name", "")
    year = _extract_year_from_name(name)
    company_info = _extract_company_from_path(source_file)

    ev = AccountEvidence(
        source_file=source_file,
        source_group=source_group,
        source_page=getattr(account, "source_page", 0) or 0,
        original_account_code=getattr(account, "account_code", ""),
        original_account_name=name,
        clean_account_name=_clean_name(name),
        parser_used=getattr(account, "extractor", ""),
        monetary=amounts,
        classification_amount=classification_amount,
        company_name=company_info.get("company", ""),
        company_rut=company_info.get("rut", ""),
        year=year,
        context_before=context_before or [],
        context_after=context_after or [],
        raw_text=name,
    )
    return ev


def _build_monetary(entry: dict) -> MonetaryAmounts:
    amt = entry.get("classification_amount", 0.0) or 0.0
    nature = entry.get("nature", "")
    if nature == "asset" or nature == "deudora":
        return MonetaryAmounts(assets=abs(amt), debit=abs(amt))
    elif nature == "liability" or nature == "acreedora":
        return MonetaryAmounts(liabilities=abs(amt), credit=abs(amt))
    elif nature == "loss":
        return MonetaryAmounts(losses=abs(amt), debit=abs(amt))
    elif nature == "profit":
        return MonetaryAmounts(profits=abs(amt), credit=abs(amt))
    return MonetaryAmounts()


def _build_amounts_from_model(account: Any) -> MonetaryAmounts:
    try:
        a = account.amounts
        return MonetaryAmounts(
            assets=a.assets,
            liabilities=a.liabilities,
            losses=a.losses,
            profits=a.profits,
            debit=a.debit,
            credit=a.credit,
            balance_debit=a.balance_debit,
            balance_credit=a.balance_credit,
        )
    except AttributeError:
        return MonetaryAmounts()


def _pick_classification_amount(amounts: MonetaryAmounts) -> float:
    for val in [amounts.assets, amounts.liabilities, amounts.losses, amounts.profits,
                amounts.debit, amounts.credit, amounts.balance_debit, amounts.balance_credit]:
        if val is not None:
            return val
    return 0.0


def _clean_name(name: str) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"^[\d\s\.\-,;:/\\|]+", "", name)
    cleaned = re.sub(r"[•·●♦♣♥♠√∞≈≠≤≥±×÷←↑→↓↔→⇒⇔∀∃∅∈∉⊂⊃∪∩∖∅¬∧∨∑∏∫∂∞∝∡∥∦≅≜≝≞≠≡≤≥≪≫≲≳≶≷≺≻≼≽⊀⊁⋞⋟⊏⊐⊑⊒⊓⊔⊕⊖⊗⊘⊙⊚⊛⊜⊝⊥⊧⊨⊩⊪⊫⊬⊭⊮⊯]", "", cleaned)
    cleaned = cleaned.strip()
    return cleaned


def _extract_company_from_path(path: str) -> dict[str, str]:
    if not path:
        return {"company": "", "rut": ""}
    p = Path(path)
    parts = p.parts
    for part in parts:
        lower = part.lower()
        rut_match = re.search(r"(\d{1,2}\.\d{3}\.\d{3}[-][\dkK])", part)
        if rut_match:
            return {"company": part, "rut": rut_match.group(1)}
    stem = p.stem
    for token in re.split(r"[/\\_\-]", stem):
        if re.search(r"\d{1,2}\.\d{3}\.\d{3}[-][\dkK]", token):
            return {"company": stem, "rut": re.search(r"\d{1,2}\.\d{3}\.\d{3}[-][\dkK]", token).group()}
    return {"company": stem, "rut": ""}


def _extract_year_from_name(name: str) -> str:
    if not name:
        return ""
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", name)
    if years:
        return max(years)
    return ""
