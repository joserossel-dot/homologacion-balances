from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from knowledge.rule_generator import generate_rule_for_candidate
from knowledge.code_generator import generate_dictionary_entries, generate_gold_standard_entries
from knowledge.test_generator import generate_tests_for_rules, generate_tests_for_dictionary

log = logging.getLogger(__name__)


DEFAULT_CONFIG: dict[str, Any] = {
    "min_priority": 1,
    "max_rule_candidates": 20,
    "max_synonym_entries": 5,
    "max_rule_examples": 3,
    "max_test_examples": 3,
    "max_dictionary_test_examples": 5,
}


def build_proposals(
    ranked: list[dict],
    synonyms: list[dict],
    clusters: dict[str, dict],
    candidates: list[dict] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    # Build lookups by representative
    cluster_by_rep: dict[str, dict] = {}
    for cluster_id, info in clusters.items():
        rep = info.get("representative", "")
        if rep:
            cluster_by_rep[rep] = info

    candidate_by_rep: dict[str, dict] = {}
    if candidates:
        for c in candidates:
            rep = c.get("representative", "")
            if rep:
                candidate_by_rep[rep] = c

    # Filter: new_semantic_rule items only, apply min_priority
    rule_improvements = [
        r for r in ranked
        if r.get("type") == "new_semantic_rule"
        and r.get("priority", 999) <= cfg["min_priority"]
    ]

    # Generate semantic rules
    generated_rules: list[dict] = []
    seen_rules: set[str] = set()
    for imp in rule_improvements:
        rep = imp.get("representative", "")
        if not rep or rep in seen_rules:
            continue
        seen_rules.add(rep)

        orig_candidate = candidate_by_rep.get(rep, {})

        cluster_info = cluster_by_rep.get(rep, {})
        sample_accounts = cluster_info.get("members", [])
        raw_names = [
            m.get("account_name", "") for m in sample_accounts[:10] if m.get("account_name")
        ] if sample_accounts else []

        candidate = {
            "suggested_semantic_type": orig_candidate.get("suggested_semantic_type", ""),
            "suggested_keywords": orig_candidate.get("suggested_keywords", []),
            "suggested_financial_statement": orig_candidate.get("suggested_financial_statement", "balance_sheet"),
            "suggested_economic_nature": orig_candidate.get("suggested_economic_nature", "debit"),
            "dominant_nature": orig_candidate.get("dominant_nature", ""),
            "size": imp.get("cluster_size", orig_candidate.get("size", 0)),
            "confidence_score": imp.get("confidence", orig_candidate.get("confidence_score", 0.0)),
            "source_files": cluster_info.get("source_files", orig_candidate.get("source_files", [])),
            "cluster_id": cluster_info.get("cluster_id", orig_candidate.get("cluster_id", "")),
        }

        if not candidate["suggested_keywords"] and raw_names:
            candidate["suggested_keywords"] = _extract_keywords_from_names(raw_names)
        if not candidate["suggested_semantic_type"]:
            candidate["suggested_semantic_type"] = imp.get("suggested_semantic_type", "asset")

        generated = generate_rule_for_candidate(candidate)
        generated_rules.append(generated)

    # Generate dictionary entries from rule candidates
    dict_candidates = []
    for c in generated_rules:
        if "error" not in c:
            dict_candidates.append({
                "suggested_semantic_type": c["suggested_semantic_type"],
                "suggested_keywords": c["keywords"],
                "confidence_score": c["confidence_score"],
                "cluster_id": c.get("rule_name", ""),
                "source_files": c.get("examples", []),
                "size": c.get("size", 0),
            })

    # Also create dictionary entries from synonyms
    dict_entries = generate_dictionary_entries(
        dict_candidates,
        synonyms,
        max_per_synonym=cfg["max_synonym_entries"],
    )

    # Generate gold standard entries from rule candidates
    gs_entries = generate_gold_standard_entries(
        dict_candidates,
        max_per_candidate=cfg["max_rule_examples"],
    )

    # Generate test code
    tests_code = generate_tests_for_rules(generated_rules, max_examples=cfg["max_test_examples"])
    dict_tests_code = generate_tests_for_dictionary(dict_entries, max_examples=cfg["max_dictionary_test_examples"])
    full_tests_code = tests_code + "\n" + dict_tests_code

    # Build suggested code for generated_rules.py
    rules_code_lines: list[str] = []
    rules_code_lines.append("# Auto-generado por Knowledge Generator — NO incorporar directamente")
    rules_code_lines.append("# Revisar antes de agregar a semantic/semantic_rules.py")
    rules_code_lines.append("")
    rules_code_lines.append("from __future__ import annotations")
    rules_code_lines.append("")
    rules_code_lines.append("# Agregar al final de la lista RULES en semantic/semantic_rules.py")
    rules_code_lines.append("")
    for gr in generated_rules:
        if "code" in gr and gr["code"]:
            rules_code_lines.append(gr["code"])
            rules_code_lines.append("")

    return {
        "config": cfg,
        "generated_rules": generated_rules,
        "dictionary_entries": dict_entries,
        "gold_standard_entries": gs_entries,
        "generated_rules_code": "\n".join(rules_code_lines),
        "generated_tests_code": full_tests_code,
        "summary": {
            "num_rule_proposals": len(generated_rules),
            "num_dictionary_entries": len(dict_entries),
            "num_gold_standard_entries": len(gs_entries),
            "tests_lines": len(full_tests_code.splitlines()),
            "rules_lines": len(rules_code_lines),
        },
    }


def export_proposals(
    proposals: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    # generated_rules.py
    path = out / "generated_rules.py"
    path.write_text(proposals["generated_rules_code"], encoding="utf-8")
    paths["generated_rules"] = path

    # generated_tests.py
    path = out / "generated_tests.py"
    path.write_text(proposals["generated_tests_code"], encoding="utf-8")
    paths["generated_tests"] = path

    # generated_dictionary_entries.json
    path = out / "generated_dictionary_entries.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(proposals["dictionary_entries"], f, indent=2, ensure_ascii=False)
    paths["dictionary_entries"] = path

    # generated_gold_standard.json
    path = out / "generated_gold_standard.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(proposals["gold_standard_entries"], f, indent=2, ensure_ascii=False)
    paths["gold_standard_entries"] = path

    # proposal_report.md
    path = out / "proposal_report.md"
    path.write_text(
        _render_proposal_report(proposals), encoding="utf-8"
    )
    paths["proposal_report"] = path

    return paths


def _render_proposal_report(proposals: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Propuestas de Mejora — Knowledge Generator\n")
    lines.append(f"Generado: {_now()}\n")

    summary = proposals["summary"]
    lines.append("## Resumen\n")
    lines.append(f"| Métrica | Valor |")
    lines.append(f"|---|---|")
    lines.append(f"| Propuestas de reglas | {summary['num_rule_proposals']} |")
    lines.append(f"| Entradas de diccionario | {summary['num_dictionary_entries']} |")
    lines.append(f"| Entradas Gold Standard | {summary['num_gold_standard_entries']} |")
    lines.append(f"| Líneas de tests generados | {summary['tests_lines']} |")
    lines.append(f"| Líneas de código de reglas | {summary['rules_lines']} |")
    lines.append("")

    lines.append("## Reglas Semánticas Propuestas\n")
    for i, rule in enumerate(proposals["generated_rules"], 1):
        if "error" in rule:
            continue
        lines.append(f"### {i}. `{rule['rule_name']}`")
        lines.append(f"- **Tipo**: {rule['suggested_semantic_type']}")
        lines.append(f"- **Keywords**: {', '.join(rule['keywords'])}")
        lines.append(f"- **Prioridad sugerida**: {rule['priority']}")
        lines.append(f"- **Confianza**: {rule['confidence_score']}")
        lines.append(f"- **Cuentas afectadas**: ~{rule['size']}")
        lines.append(f"- **Columna aceptable**: {rule.get('acceptable_column', 'activo')}")
        lines.append("")
        lines.append("```python")
        lines.append(rule["code"])
        lines.append("```")
        lines.append("")

    lines.append("## Entradas de Diccionario Propuestas\n")
    lines.append(f"Total: {len(proposals['dictionary_entries'])} entradas\n")
    lines.append("| # | Cuenta Original | Código Estándar | Fuente | Confianza |")
    lines.append("|---|---|---|---|---|")
    for i, entry in enumerate(proposals["dictionary_entries"][:30], 1):
        lines.append(
            f"| {i} | {entry['cuenta_original']} | {entry['codigo_estandar']} | "
            f"{entry['fuente']} | {entry['confidence']} |"
        )
    if len(proposals["dictionary_entries"]) > 30:
        lines.append(f"| ... | ({len(proposals['dictionary_entries']) - 30} más) | ... | ... | ... |")
    lines.append("")

    lines.append("## Entradas Gold Standard Propuestas\n")
    lines.append(f"Total: {len(proposals['gold_standard_entries'])} entradas\n")
    lines.append("| # | Account Name | Suggested Code | Confidence | Comments |")
    lines.append("|---|---|---|---|---|")
    for i, entry in enumerate(proposals["gold_standard_entries"][:20], 1):
        lines.append(
            f"| {i} | {entry['account_name']} | {entry['suggested_code']} | "
            f"{entry['suggested_confidence']} | {entry['comments']} |"
        )
    if len(proposals["gold_standard_entries"]) > 20:
        lines.append(f"| ... | ({len(proposals['gold_standard_entries']) - 20} más) | ... | ... | ... |")
    lines.append("")

    lines.append("## Archivos Generados\n")
    lines.append("| Archivo | Contenido |")
    lines.append("|---|---|")
    lines.append("| `generated_rules.py` | Código Python sugerido para nuevas reglas semánticas |")
    lines.append("| `generated_tests.py` | Tests unitarios sugeridos para nuevas reglas y entradas |")
    lines.append("| `generated_dictionary_entries.json` | Entradas de diccionario sugeridas |")
    lines.append("| `generated_gold_standard.json` | Entradas Gold Standard sugeridas |")
    lines.append("")

    lines.append("---\n")
    lines.append("*Reporte generado automáticamente por Knowledge Generator. Ninguna propuesta ha sido incorporada al proyecto.*\n")
    return "\n".join(lines)


def _extract_keywords_from_names(names: list[str]) -> list[str]:
    import re
    from collections import Counter

    stop_words = {
        "de", "la", "el", "en", "por", "del", "las", "los", "al", "con",
        "su", "para", "una", "un", "y", "e", "o", "a", "que", "es", "se",
        "no", "lo", "le", "cuenta", "0000", "000",
    }
    counter: Counter = Counter()
    for name in names:
        name_lower = name.lower()
        name_lower = re.sub(r"[á]", "a", name_lower)
        name_lower = re.sub(r"[é]", "e", name_lower)
        name_lower = re.sub(r"[í]", "i", name_lower)
        name_lower = re.sub(r"[ó]", "o", name_lower)
        name_lower = re.sub(r"[ú]", "u", name_lower)
        name_lower = re.sub(r"[^a-z0-9\s]", " ", name_lower)
        words = [w for w in name_lower.split() if w not in stop_words and len(w) > 2]
        counter.update(words)

    top = [w for w, _ in counter.most_common(5)]
    return top


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
