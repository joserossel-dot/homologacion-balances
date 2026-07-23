from __future__ import annotations

from typing import Any


def generate_tests_for_rules(
    generated_rules: list[dict],
    *,
    max_examples: int = 3,
) -> str:
    lines: list[str] = []
    lines.append("# Auto-generado por Knowledge Generator — NO incorporar directamente")
    lines.append("# Revisar antes de agregar al proyecto de tests")
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# Tests para nuevas reglas semánticas")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")

    for rule in generated_rules:
        if "error" in rule:
            continue
        _append_rule_tests(lines, rule, max_examples)

    return "\n".join(lines)


def _append_rule_tests(lines: list[str], rule: dict, max_examples: int) -> None:
    rule_name = rule.get("rule_name", "unknown_rule")
    semantic_type = rule.get("suggested_semantic_type", "unknown")
    keywords = rule.get("keywords", [])

    lines.append("")
    lines.append(f"def test_{_safe_name(rule_name)}_match():")
    kw_comment = ", ".join(keywords)
    lines.append(f'    """Debería activarse para cuentas con: {kw_comment}"""')
    lines.append("    from semantic.semantic_rules import build_rules")
    lines.append("    from models.account_balance import AccountBalance")
    lines.append("    from semantic.semantic_context import SemanticContext")
    lines.append("    from models.monetary_amounts import MonetaryAmounts")
    lines.append("")
    lines.append("    rules = build_rules()")
    lines.append(f"    rule = next((r for r in rules if r.name == '{rule_name}'), None)")
    lines.append("    assert rule is not None, f'Regla {rule_name!r} no encontrada'")
    lines.append("")
    lines.append("    # Test con nombre de cuenta que debería coincidir")

    for i, kw in enumerate(keywords[:max_examples]):
        test_name = f"Cuenta de {kw} Test {i}"
        lines.append(f"    account_{i} = AccountBalance(")
        lines.append(f'        account_name="{test_name}",')
        lines.append(f"        nature=\"{_nature_for_type(semantic_type)}\",")
        lines.append(f"        amounts=MonetaryAmounts({_amount_field(semantic_type)}=1000.0),")
        lines.append(f"    )")
        lines.append(f"    ctx_{i} = SemanticContext.from_account(account_{i})")
        lines.append(f"    result_{i} = rule.evaluate(ctx_{i})")
        lines.append(f"    assert result_{i} is not None, f'Regla {rule_name!r} debería activarse para {test_name!r}'")
        lines.append(f"    assert result_{i}.semantic_type == \"{semantic_type}\"")
        lines.append(f"    assert result_{i}.confidence > 0.0")
        lines.append("")

    _append_no_match_test(lines, rule, rule_name, keywords)


def _append_no_match_test(lines: list[str], rule: dict, rule_name: str, keywords: list[str]) -> None:
    lines.append("")
    lines.append(f"def test_{_safe_name(rule_name)}_no_match():")
    lines.append('    """No debería activarse para cuentas no relacionadas"""')
    lines.append("    from semantic.semantic_rules import build_rules")
    lines.append("    from models.account_balance import AccountBalance")
    lines.append("    from semantic.semantic_context import SemanticContext")
    lines.append("    from models.monetary_amounts import MonetaryAmounts")
    lines.append("")
    lines.append("    rules = build_rules()")
    lines.append(f"    rule = next((r for r in rules if r.name == '{rule_name}'), None)")
    lines.append("    assert rule is not None")
    lines.append("")
    lines.append("    account = AccountBalance(")
    lines.append('        account_name="Cuenta No Relacionada",')
    lines.append(f"        nature=\"{_nature_for_type(rule.get('suggested_semantic_type', 'asset'))}\",")
    lines.append(f"        amounts=MonetaryAmounts({_amount_field(rule.get('suggested_semantic_type', 'asset'))}=1000.0),")
    lines.append("    )")
    lines.append("    ctx = SemanticContext.from_account(account)")
    lines.append("    result = rule.evaluate(ctx)")
    lines.append("    assert result is None")
    lines.append("")


def generate_tests_for_dictionary(
    entries: list[dict],
    *,
    max_examples: int = 5,
) -> str:
    lines: list[str] = []
    lines.append("# Auto-generado por Knowledge Generator — NO incorporar directamente")
    lines.append("# Tests para nuevas entradas de diccionario")
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# Tests para nuevas entradas de diccionario")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")

    for i, entry in enumerate(entries[:max_examples]):
        name = entry.get("cuenta_original", "")
        code = entry.get("codigo_estandar", "")
        safe = _safe_name(name)
        lines.append("")
        lines.append(f"def test_dictionary_entry_{safe}():")
        lines.append(f'    """Diccionario debería clasificar {name!r} como {code}"""')
        lines.append("    from src.dictionary import DictionaryClassifier")
        lines.append("    from models.account_balance import AccountBalance")
        lines.append("    from models.monetary_amounts import MonetaryAmounts")
        lines.append("")
        lines.append("    classifier = DictionaryClassifier()")
        lines.append("    account = AccountBalance(")
        lines.append(f'        account_name="{name}",')
        lines.append("        nature=\"asset\",")
        lines.append("        amounts=MonetaryAmounts(assets=1000.0),")
        lines.append("    )")
        lines.append("    result = classifier.classify(account)")
        lines.append(f"    assert result is not None")
        lines.append(f"    assert result.standard_code == \"{code}\"")
        lines.append("")

    return "\n".join(lines)


def _safe_name(name: str) -> str:
    safe = ""
    for ch in name.lower():
        if ch.isalnum() or ch == "_":
            safe += ch
        else:
            safe += "_"
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or "unnamed"


def _nature_for_type(semantic_type: str) -> str:
    return {"asset": "deudora", "liability": "acreedora", "revenue": "profit", "expense": "loss", "equity": "acreedora", "contra_asset": "acreedora"}.get(semantic_type, "deudora")


def _amount_field(semantic_type: str) -> str:
    return {"asset": "assets", "liability": "liabilities", "revenue": "profits", "expense": "losses", "equity": "liabilities", "contra_asset": "liabilities"}.get(semantic_type, "assets")
