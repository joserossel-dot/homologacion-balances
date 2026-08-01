"""classification_engine — Motor de clasificación por cuenta (Sprint 38).

Paquete 100% aditivo e independiente. Produce, por cada cuenta, un ranking
Top-N de candidatos con score, confianza, explicación completa y trazabilidad
de todas las evidencias.

Documentación de referencia: reports/sprint38_architecture_review.md
"""

from __future__ import annotations

from classification_engine.candidate import CandidateGenerator, KnowledgeLoader
from classification_engine.decision import (
    Candidate,
    ClassificationExplanation,
    DocumentProcessingContextAdapter,
    EvidenceSource,
    RankedCandidate,
    TopNResult,
)
from classification_engine.engine import DecisionEngine
from classification_engine.explainer import Explainer
from classification_engine.metrics import MetricsResult, compute_metrics
from classification_engine.score import (
    CANDIDATE_LAYERS,
    DEFAULT_CONFIDENCE_THRESHOLDS,
    DEFAULT_LAYER_WEIGHTS,
    Scorer,
    WeightConfig,
)

__all__ = [
    # motor
    "DecisionEngine",
    "CandidateGenerator",
    "KnowledgeLoader",
    "Scorer",
    "Explainer",
    "WeightConfig",
    # modelos
    "Candidate",
    "RankedCandidate",
    "EvidenceSource",
    "ClassificationExplanation",
    "TopNResult",
    "DocumentProcessingContextAdapter",
    # métricas
    "MetricsResult",
    "compute_metrics",
    # constantes
    "CANDIDATE_LAYERS",
    "DEFAULT_LAYER_WEIGHTS",
    "DEFAULT_CONFIDENCE_THRESHOLDS",
]

__version__ = "0.1.0"
