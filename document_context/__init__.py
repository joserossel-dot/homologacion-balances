"""Document Context Engine (DCE).

Único objeto de contexto que acompaña al documento desde INBOX hasta
la exportación final. Cada módulo lee lo que necesita y agrega su resultado.
Nunca se elimina ni modifica información de módulos anteriores.

Uso básico:

    from document_context import DocumentContext
    from document_context.models import DocumentMetadata, StructureData

    ctx = DocumentContext(source_file="balance.pdf")

    ctx.set_metadata(DocumentMetadata(
        company="Empresa SA", rut="76.693.319-K", year=2024,
    ))
    ctx.set_structure(StructureData(family="TRIBUTARIO", template="T14"))

    print(ctx.state)             # ProcessingState.STRUCTURED
    print(ctx.metadata.company)  # "Empresa SA"

    ctx.snapshot("after_structure")
    ctx.complete()
"""

from __future__ import annotations

from .context import DocumentContext, WriteOnceError
from .lifecycle import LifecycleManager, LifecycleError
from .snapshot import SnapshotManager, SnapshotNotFoundError
from .serializers import DocumentContextSerializer
from .merge import ContextMerger
from .validators import ContextValidator, ValidationIssue
from .statistics import ContextStatistics

from .models import (
    DocumentIdentity, DocumentMetadata, StructureData, ParserData,
    KnowledgeData, ValidationData, PredictionData, ExecutionData,
    ProcessingState, ContextSnapshot, LifecycleEvent,
)

__all__ = [
    "DocumentContext",
    "DocumentContextSerializer",
    "ContextMerger",
    "ContextValidator",
    "ContextStatistics",
    "LifecycleManager",
    "SnapshotManager",
    "WriteOnceError",
    "LifecycleError",
    "SnapshotNotFoundError",
    "ValidationIssue",
    # Models
    "DocumentIdentity",
    "DocumentMetadata",
    "StructureData",
    "ParserData",
    "KnowledgeData",
    "ValidationData",
    "PredictionData",
    "ExecutionData",
    "ProcessingState",
    "ContextSnapshot",
    "LifecycleEvent",
]
