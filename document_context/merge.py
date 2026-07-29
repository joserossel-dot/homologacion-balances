from __future__ import annotations

from typing import Any

from .context import DocumentContext
from .models import (
    DocumentMetadata, StructureData, ParserData, KnowledgeData,
    ValidationData, PredictionData, ExecutionData,
)


class ContextMerger:

    @staticmethod
    def merge(target: DocumentContext, source: DocumentContext) -> DocumentContext:
        """Fusiona source en target. No sobreescribe campos existentes."""

        if target.metadata is None and source.metadata is not None:
            target._metadata = source.metadata

        if target.structure is None and source.structure is not None:
            target._structure = source.structure

        if target.parser is None and source.parser is not None:
            target._parser = source.parser

        if target.knowledge is None and source.knowledge is not None:
            target._knowledge = source.knowledge

        if target.validation is None and source.validation is not None:
            target._validation = source.validation

        if target.prediction is None and source.prediction is not None:
            target._prediction = source.prediction

        if target.execution is None and source.execution is not None:
            target._execution = source.execution

        for key, value in source.custom_data.items():
            if key not in target._custom:
                target._custom[key] = value

        return target

    @staticmethod
    def merge_partial(
        ctx: DocumentContext,
        metadata: DocumentMetadata | None = None,
        structure: StructureData | None = None,
        parser: ParserData | None = None,
        knowledge: KnowledgeData | None = None,
        validation: ValidationData | None = None,
        prediction: PredictionData | None = None,
        execution: ExecutionData | None = None,
    ) -> DocumentContext:
        """Fusiona datos parciales en el contexto. No sobreescribe."""

        if metadata is not None and ctx._metadata is None:
            ctx._metadata = metadata

        if structure is not None and ctx._structure is None:
            ctx._structure = structure

        if parser is not None and ctx._parser is None:
            ctx._parser = parser

        if knowledge is not None and ctx._knowledge is None:
            ctx._knowledge = knowledge

        if validation is not None and ctx._validation is None:
            ctx._validation = validation

        if prediction is not None and ctx._prediction is None:
            ctx._prediction = prediction

        if execution is not None and ctx._execution is None:
            ctx._execution = execution

        return ctx

    @staticmethod
    def merge_dict(ctx: DocumentContext, data: dict[str, Any]) -> DocumentContext:
        """Fusiona datos de un diccionario. Útil para integración con
        módulos externos sin acoplamiento."""

        if "metadata" in data and ctx._metadata is None:
            ctx._metadata = DocumentMetadata.from_dict(data["metadata"])

        if "structure" in data and ctx._structure is None:
            ctx._structure = StructureData.from_dict(data["structure"])

        if "parser" in data and ctx._parser is None:
            ctx._parser = ParserData.from_dict(data["parser"])

        if "knowledge" in data and ctx._knowledge is None:
            ctx._knowledge = KnowledgeData.from_dict(data["knowledge"])

        if "validation" in data and ctx._validation is None:
            ctx._validation = ValidationData.from_dict(data["validation"])

        if "prediction" in data and ctx._prediction is None:
            ctx._prediction = PredictionData.from_dict(data["prediction"])

        if "execution" in data and ctx._execution is None:
            ctx._execution = ExecutionData.from_dict(data["execution"])

        custom = data.get("custom", {})
        for key, value in custom.items():
            if key not in ctx._custom:
                ctx._custom[key] = value

        return ctx
