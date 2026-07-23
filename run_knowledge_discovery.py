#!/usr/bin/env python3
from __future__ import annotations

import logging
from pathlib import Path

from knowledge.unknown_cluster import load_unclassified, cluster_accounts, summarize_clusters
from knowledge.rule_suggester import suggest_rules
from knowledge.synonym_detector import detect_synonyms
from knowledge.improvement_ranker import rank_improvements
from knowledge.knowledge_report import generate_all_reports

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SHADOW_DATA = Path("reports/semantic_shadow/shadow_data.json")
OUTPUT_DIR = Path("reports/knowledge")


def main() -> None:
    log.info("=== Knowledge Discovery Engine ===\n")

    log.info("1. Cargando cuentas no clasificadas...")
    accounts = load_unclassified(str(SHADOW_DATA))
    log.info(f"   Total cuentas no clasificadas: {len(accounts)}")

    all_accounts_count = 0
    import json
    with open(SHADOW_DATA) as f:
        all_accounts_count = len(json.load(f).get("accounts", []))

    log.info("\n2. Clusterizando...")
    clusters = cluster_accounts(accounts)
    log.info(f"   Clusters formados: {len(clusters)}")
    if clusters:
        sizes = [c["size"] for c in clusters.values()]
        log.info(f"   Cluster más grande: {max(sizes)} cuentas")
        log.info(f"   Cluster más pequeño: {min(sizes)} cuentas")

    log.info("\n3. Resumiendo clusters...")
    summary = summarize_clusters(clusters)
    log.info(f"   Clusters con resumen: {len(summary)}")

    log.info("\n4. Sugiriendo reglas...")
    candidates = suggest_rules(clusters)
    log.info(f"   Candidatos a reglas: {len(candidates)}")
    for c in candidates[:5]:
        log.info(f"   - {c['representative']}: {c['suggested_semantic_type']} (confianza={c['confidence_score']}, size={c['size']})")

    log.info("\n5. Detectando sinónimos...")
    synonyms = detect_synonyms(accounts)
    log.info(f"   Grupos de sinónimos: {len(synonyms)}")
    for s in synonyms[:5]:
        log.info(f"   - {s['group_label']}: {s['num_variants']} variantes")

    log.info("\n6. Priorizando mejoras...")
    ranked = rank_improvements(candidates, synonyms, len(accounts))
    log.info(f"   Recomendaciones priorizadas: {len(ranked)}")
    for r in ranked[:5]:
        log.info(f"   #{r['priority']}: {r['description']} (impacto={r['weighted_impact']})")

    log.info("\n7. Generando reportes...")
    paths = generate_all_reports(
        OUTPUT_DIR, clusters, summary, candidates, synonyms, ranked,
        all_accounts_count, len(accounts),
    )
    for name, p in paths.items():
        log.info(f"   {name}: {p}")

    log.info("\n=== Knowledge Discovery Complete ===")


if __name__ == "__main__":
    main()
