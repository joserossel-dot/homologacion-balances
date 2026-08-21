from __future__ import annotations

import json
import pickle
from datetime import datetime, timezone
from typing import Any, TextIO

from .context import DocumentContext
from .models import (
    DocumentIdentity, DocumentMetadata, StructureData, ParserData,
    KnowledgeData, ValidationData, PredictionData, ExecutionData,
    ProcessingState,
)


class DocumentContextSerializer:

    @staticmethod
    def to_dict(ctx: DocumentContext) -> dict[str, Any]:
        return {
            "identity": ctx.identity.to_dict(),
            "metadata": ctx.metadata.to_dict() if ctx.metadata else None,
            "structure": ctx.structure.to_dict() if ctx.structure else None,
            "parser": ctx.parser.to_dict() if ctx.parser else None,
            "knowledge": ctx.knowledge.to_dict() if ctx.knowledge else None,
            "validation": ctx.validation.to_dict() if ctx.validation else None,
            "prediction": ctx.prediction.to_dict() if ctx.prediction else None,
            "execution": ctx.execution.to_dict() if ctx.execution else None,
            "state": ctx.state.value,
            "events": [e.to_dict() for e in ctx.events],
            "snapshots": [s.to_dict() for s in ctx.snapshots],
            "custom": dict(ctx.custom_data),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> DocumentContext:
        identity_data = data.get("identity", {})
        ctx = DocumentContext(
            source_file=identity_data.get("source_file", ""),
            document_id=identity_data.get("document_id"),
        )

        if metadata := data.get("metadata"):
            ctx._metadata = DocumentMetadata.from_dict(metadata)
            ctx._write_once.add("metadata")

        if structure := data.get("structure"):
            ctx._structure = StructureData.from_dict(structure)
            ctx._write_once.add("structure")

        if parser := data.get("parser"):
            ctx._parser = ParserData.from_dict(parser)
            ctx._write_once.add("parser")

        if knowledge := data.get("knowledge"):
            ctx._knowledge = KnowledgeData.from_dict(knowledge)
            ctx._write_once.add("knowledge")

        if validation := data.get("validation"):
            ctx._validation = ValidationData.from_dict(validation)
            ctx._write_once.add("validation")

        if prediction := data.get("prediction"):
            ctx._prediction = PredictionData.from_dict(prediction)
            ctx._write_once.add("prediction")

        if execution := data.get("execution"):
            ctx._execution = ExecutionData.from_dict(execution)
            ctx._write_once.add("execution")

        ctx._custom = dict(data.get("custom", {}))

        state_str = data.get("state", "NEW")
        try:
            state = ProcessingState(state_str)
            if state != ProcessingState.NEW:
                ctx._lifecycle._state = state
        except ValueError:
            pass

        return ctx

    @staticmethod
    def to_json(ctx: DocumentContext, indent: int = 2) -> str:
        return json.dumps(
            DocumentContextSerializer.to_dict(ctx),
            indent=indent,
            ensure_ascii=False,
            default=str,
        )

    @staticmethod
    def from_json(json_str: str) -> DocumentContext:
        data = json.loads(json_str)
        return DocumentContextSerializer.from_dict(data)

    @staticmethod
    def to_json_file(ctx: DocumentContext, file_path: str, indent: int = 2) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(DocumentContextSerializer.to_json(ctx, indent=indent))

    @staticmethod
    def from_json_file(file_path: str) -> DocumentContext:
        with open(file_path, "r", encoding="utf-8") as f:
            return DocumentContextSerializer.from_json(f.read())

    @staticmethod
    def to_pickle(ctx: DocumentContext) -> bytes:
        return pickle.dumps(DocumentContextSerializer.to_dict(ctx))

    @staticmethod
    def from_pickle(data: bytes) -> DocumentContext:
        return DocumentContextSerializer.from_dict(pickle.loads(data))

    @staticmethod
    def to_markdown(ctx: DocumentContext) -> str:
        lines: list[str] = []
        lines.append(f"# Document Context: {ctx.document_id}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Identity")
        lines.append("")
        lines.append(f"| Campo | Valor |")
        lines.append(f"|-------|-------|")
        lines.append(f"| document_id | {ctx.identity.document_id} |")
        lines.append(f"| source_file | {ctx.identity.source_file} |")
        lines.append(f"| sha256 | {ctx.identity.sha256[:16]}{'...' if len(ctx.identity.sha256) > 16 else ''} |")
        lines.append(f"| created_at | {ctx.identity.created_at.isoformat()} |")
        lines.append(f"| updated_at | {ctx.identity.updated_at.isoformat()} |")
        lines.append(f"| version | {ctx.identity.version} |")
        lines.append("")

        if ctx.metadata:
            lines.append("## Metadata")
            lines.append("")
            lines.append("| Campo | Valor |")
            lines.append("|-------|-------|")
            md = ctx.metadata
            lines.append(f"| company | {md.company} |")
            lines.append(f"| rut | {md.rut} |")
            lines.append(f"| year | {md.year} |")
            lines.append(f"| pages | {md.pages} |")
            lines.append(f"| language | {md.language} |")
            lines.append(f"| orientation | {md.orientation} |")
            lines.append(f"| layout | {md.layout} |")
            lines.append(f"| ocr_probability | {md.ocr_probability:.2%} |")
            lines.append("")

        if ctx.structure:
            lines.append("## Structure")
            lines.append("")
            lines.append("| Campo | Valor |")
            lines.append("|-------|-------|")
            s = ctx.structure
            lines.append(f"| family | {s.family} |")
            lines.append(f"| template | {s.template} |")
            lines.append(f"| document_type | {s.document_type} |")
            lines.append(f"| column_layout | {s.column_layout} |")
            lines.append(f"| sections | {len(s.sections)} |")
            lines.append("")

        if ctx.parser:
            lines.append("## Parser")
            lines.append("")
            lines.append("| Campo | Valor |")
            lines.append("|-------|-------|")
            p = ctx.parser
            lines.append(f"| selected_parser | {p.selected_parser} |")
            lines.append(f"| parser_version | {p.parser_version} |")
            lines.append(f"| parser_time | {p.parser_time:.2f}s |")
            lines.append(f"| accounts | {p.total_accounts} |")
            lines.append(f"| raw_accounts | {p.total_raw} |")
            lines.append(f"| ignored | {p.total_ignored} |")
            lines.append("")

        if ctx.prediction:
            lines.append("## Prediction")
            lines.append("")
            lines.append("| Campo | Valor |")
            lines.append("|-------|-------|")
            pr = ctx.prediction
            lines.append(f"| confidence_expected | {pr.confidence_expected:.1%} |")
            lines.append(f"| coverage_expected | {pr.coverage_expected:.1%} |")
            lines.append(f"| estimated_time | {pr.estimated_time:.1f}s |")
            lines.append(f"| complexity | {pr.complexity} |")
            lines.append("")

        if ctx.execution:
            lines.append("## Execution")
            lines.append("")
            lines.append("| Campo | Valor |")
            lines.append("|-------|-------|")
            ex = ctx.execution
            lines.append(f"| confidence_real | {ex.confidence_real:.1%} |")
            lines.append(f"| coverage_real | {ex.coverage_real:.1%} |")
            lines.append(f"| processing_time | {ex.processing_time:.1f}s |")
            lines.append(f"| review_required | {ex.review_required} |")
            lines.append(f"| status | {ex.status} |")
            lines.append("")

        lines.append("## Lifecycle")
        lines.append("")
        lines.append(f"**State:** {ctx.state.value}")
        lines.append("")
        lines.append("### Events")
        lines.append("")
        lines.append("| # | Timestamp | From | To | Module | Description |")
        lines.append("|---|-----------|------|-----|--------|-------------|")
        for i, evt in enumerate(ctx.events, 1):
            f = evt.from_state.value if evt.from_state else "-"
            lines.append(f"| {i} | {evt.timestamp.strftime('%H:%M:%S')} | {f} | {evt.to_state.value} | {evt.module} | {evt.description} |")
        lines.append("")

        if ctx.snapshots:
            lines.append("### Snapshots")
            lines.append("")
            lines.append("| # | Label | State | Timestamp |")
            lines.append("|---|-------|-------|-----------|")
            for i, snap in enumerate(ctx.snapshots, 1):
                lines.append(f"| {i} | {snap.label} | {snap.state.value} | {snap.timestamp.strftime('%H:%M:%S')} |")
            lines.append("")

        lines.append("---")
        lines.append(f"*Serializado: {datetime.now(timezone.utc).isoformat()}*")
        return "\n".join(lines)
