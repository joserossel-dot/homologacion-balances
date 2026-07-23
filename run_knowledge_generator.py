#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
from pathlib import Path

from knowledge.unknown_cluster import load_unclassified, cluster_accounts
from knowledge.rule_suggester import suggest_rules
from knowledge.synonym_detector import detect_synonyms
from knowledge.improvement_ranker import rank_improvements
from knowledge.proposal_builder import build_proposals, export_proposals

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SHADOW_DATA = Path("reports/semantic_shadow/shadow_data.json")
OUTPUT_DIR = Path("reports/knowledge")


def main() -> None:
    log.info("=== Knowledge Generator ===\n")

    log.info("1. Cargando datos...")
    with open(SHADOW_DATA) as f:
        all_data = json.load(f)
    all_accounts = all_data.get("accounts", [])
    log.info(f"   Total cuentas: {len(all_accounts)}")

    unclassified = load_unclassified(str(SHADOW_DATA))
    log.info(f"   No clasificadas: {len(unclassified)}")

    log.info("\n2. Clusterizando...")
    clusters = cluster_accounts(unclassified)
    log.info(f"   Clusters: {len(clusters)}")

    log.info("\n3. Candidatos a reglas...")
    candidates = suggest_rules(clusters)
    log.info(f"   Candidatos: {len(candidates)}")

    log.info("\n4. Sinónimos...")
    synonyms = detect_synonyms(unclassified)
    log.info(f"   Grupos sinónimos: {len(synonyms)}")

    log.info("\n5. Priorizando...")
    ranked = rank_improvements(candidates, synonyms, len(unclassified))
    log.info(f"   Recomendaciones: {len(ranked)}")

    log.info("\n6. Generando propuestas...")
    proposals = build_proposals(ranked, synonyms, clusters, candidates, {
        "min_priority": 999,  # Accept all rule candidates
        "max_rule_candidates": 30,
        "max_synonym_entries": 5,
        "max_rule_examples": 3,
        "max_test_examples": 2,
        "max_dictionary_test_examples": 5,
    })

    summ = proposals["summary"]
    log.info(f"   Reglas propuestas: {summ['num_rule_proposals']}")
    log.info(f"   Entradas diccionario: {summ['num_dictionary_entries']}")
    log.info(f"   Entradas Gold Standard: {summ['num_gold_standard_entries']}")
    log.info(f"   Líneas tests: {summ['tests_lines']}")
    log.info(f"   Líneas reglas: {summ['rules_lines']}")

    log.info("\n7. Exportando...")
    paths = export_proposals(proposals, OUTPUT_DIR)
    for name, p in paths.items():
        log.info(f"   {name}: {p}")

    log.info("\n=== Knowledge Generator Complete ===")


if __name__ == "__main__":
    main()
