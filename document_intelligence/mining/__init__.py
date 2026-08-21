"""Data Mining del Document Knowledge Base (Sprint 33).

Módulo exclusivamente analítico: NO modifica el Parser Universal, ni el
pipeline de homologación, ni los clasificadores, ni las reglas.

Descubre familias documentales usando SOLO fingerprints, construye una
matriz de similitud NxN (Top-K vecinos), selecciona representantes,
mide cobertura y genera reportes + CSV + recomendación de extractores.

Módulos:

  - similarity_matrix.py     DocumentRecord + SimilarityMatrix (NxN, Top-K)
  - family_detector.py       DocumentFamily + detect_families (solo fingerprint)
  - representative_selector.py Representative + select_representatives
  - coverage.py              Cobertura esperada Top 5/10/20/30
  - reports.py               Quality analyzer + dashboard MD + CSVs + JSON

Uso rápido:

    from document_intelligence.mining import (
        build_similarity_matrix, detect_families, select_representatives,
        coverage_by_top_families, run_mining_analysis,
    )

    result = run_mining_analysis(records)   # registros con fingerprint
"""

from __future__ import annotations

from .similarity_matrix import (
    FINGERPRINT_WEIGHTS,
    DocumentRecord,
    SimilarityMatrix,
    build_similarity_matrix,
    fingerprint_similarity,
)
from .family_detector import DocumentFamily, detect_families
from .representative_selector import Representative, select_representatives
from .coverage import CoverageResult, coverage_by_top_families
from .reports import (
    detect_quality_issues,
    load_analysis_result,
    recommend_extractors,
    run_mining_analysis,
    save_analysis_result,
    write_csvs,
    write_dashboard_report,
)

__all__ = [
    "FINGERPRINT_WEIGHTS",
    "DocumentRecord",
    "SimilarityMatrix",
    "build_similarity_matrix",
    "fingerprint_similarity",
    "DocumentFamily",
    "detect_families",
    "Representative",
    "select_representatives",
    "CoverageResult",
    "coverage_by_top_families",
    "detect_quality_issues",
    "recommend_extractors",
    "run_mining_analysis",
    "save_analysis_result",
    "load_analysis_result",
    "write_csvs",
    "write_dashboard_report",
]
