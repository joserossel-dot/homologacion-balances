from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from knowledge.variant_discovery.clusterer import VariantClusterer, VariantCluster


class VariantDiscoveryEngine:
    def __init__(self, cmcc_path: str | Path = "knowledge/cmcc.json",
                 threshold: float = 0.60):
        self.cmcc_path = Path(cmcc_path)
        self.threshold = threshold
        self.accounts: list[dict] = []
        self.clusterer = VariantClusterer(threshold=threshold)
        self.cmcc_concepts: list[dict] = []
        self._load_cmcc()

    def _load_cmcc(self) -> None:
        if self.cmcc_path.exists():
            with open(self.cmcc_path, "r", encoding="utf-8") as f:
                self.cmcc_concepts = json.load(f)

    def load_unclassified(self, path: str | Path) -> None:
        df = pd.read_excel(path)
        for _, row in df.iterrows():
            name = str(row.get("account_name", row.get("cuenta", "")))
            if not name or name == "nan":
                continue
            src = str(row.get("source_path", row.get("source_file", row.get("Documento", ""))))
            self.accounts.append({
                "account_name": name,
                "frecuencia": int(row.get("frecuencia", row.get("frequency", 1))),
                "source_file": src,
                "source_path": src,
                "classification_amount": float(row.get("classification_amount",
                                              row.get("monto", 0.0))),
            })

    def load_cmcc_shadow(self, path: str | Path) -> None:
        df = pd.read_excel(path)
        for _, row in df.iterrows():
            name = str(row.get("Cuenta", ""))
            if not name or name == "nan":
                continue
            self.accounts.append({
                "account_name": name,
                "frecuencia": 1,
                "source_file": str(row.get("Documento", "")),
                "source_path": str(row.get("Documento", "")),
                "classification_amount": 0.0,
            })

    def run(self) -> dict[str, Any]:
        print(f"Clustering {len(self.accounts)} accounts...")
        names = [a.get("account_name", a.get("cuenta", ""))
                 for a in self.accounts]
        all_names = list(set(n for n in names if n and n != "nan"))
        self.clusterer.scorer = self.clusterer.scorer.from_names(all_names)
        clusters = self.clusterer.cluster(self.accounts)
        print(f"  {len(clusters)} clusters formed")
        print(f"  Multi-member: {self.clusterer.get_multi_member_count()}")

        self.clusterer.compute_confidences()
        print(f"  Confidences computed")

        self.clusterer.suggest_concepts(self.cmcc_concepts)
        print(f"  Concepts suggested")

        multi = self.clusterer.get_multi_member()
        singletons = self.clusterer.get_singletons()

        high_conf = [c for c in multi if c.confidence >= 0.70]
        needs_review = [c for c in multi if c.confidence < 0.70]

        result = {
            "clusters": clusters,
            "multi_member": multi,
            "singletons": singletons,
            "high_confidence": high_conf,
            "needs_review": needs_review,
            "total_accounts": len(self.accounts),
            "total_clusters": len(clusters),
            "multi_clusters": len(multi),
            "singleton_count": len(singletons),
            "high_confidence_count": len(high_conf),
            "needs_review_count": len(needs_review),
        }
        return result
