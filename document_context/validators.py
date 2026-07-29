from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import ProcessingState
from .lifecycle import STATE_REQUIRED_DATA


@dataclass
class ValidationIssue:
    field: str
    severity: str  # "error", "warning", "info"
    message: str
    category: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "severity": self.severity,
            "message": self.message,
            "category": self.category,
        }


SESSION_ISSUES = {
    "no_parser": "Documento sin parser asignado",
    "parser_no_accounts": "Parser no extrajo cuentas",
    "no_structure": "Documento sin estructura",
    "no_metadata": "Documento sin metadatos",
    "validation_no_parser": "Validación ejecutada sin datos de parser",
    "confidence_no_validation": "Confianza calculada sin validación",
    "coverage_no_knowledge": "Cobertura calculada sin knowledge base",
    "review_no_validation": "Revisión sin validación completada",
    "completed_with_errors": "Completado con errores de validación",
    "completed_without_review": "Completado sin pasar por revisión",
    "snapshot_gap": "Saltos de estado sin snapshots intermedios",
}


class ContextValidator:

    @staticmethod
    def validate(ctx: Any) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        state = ctx.state if hasattr(ctx, "state") else ProcessingState.NEW

        issues += ContextValidator._check_required_fields(ctx, state)
        issues += ContextValidator._check_parser_consistency(ctx)
        issues += ContextValidator._check_validation_consistency(ctx)
        issues += ContextValidator._check_knowledge_consistency(ctx)
        issues += ContextValidator._check_lifecycle_consistency(ctx)
        issues += ContextValidator._check_snapshot_gaps(ctx)
        issues += ContextValidator._check_completion_issues(ctx)

        return issues

    @staticmethod
    def _check_required_fields(ctx: Any, state: ProcessingState) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        required = STATE_REQUIRED_DATA.get(state, [])

        field_map = {
            "identity": lambda: hasattr(ctx, "identity") and bool(ctx.identity.document_id),
            "metadata": lambda: hasattr(ctx, "metadata") and ctx.metadata is not None,
            "structure": lambda: hasattr(ctx, "structure") and ctx.structure is not None,
            "parser": lambda: hasattr(ctx, "parser") and ctx.parser is not None,
            "knowledge": lambda: hasattr(ctx, "knowledge") and ctx.knowledge is not None,
            "validation": lambda: hasattr(ctx, "validation") and ctx.validation is not None,
        }

        for field_name in required:
            check = field_map.get(field_name)
            if check and not check():
                issues.append(ValidationIssue(
                    field=field_name,
                    severity="error",
                    message=f"Campo requerido '{field_name}' no presente para estado {state.value}",
                    category="required_field",
                ))

        return issues

    @staticmethod
    def _check_parser_consistency(ctx: Any) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        parser = getattr(ctx, "parser", None)
        if parser is None:
            return issues

        if not parser.selected_parser:
            issues.append(ValidationIssue(
                field="parser.selected_parser",
                severity="warning",
                message="Parser no especificado",
                category="parser",
            ))

        if hasattr(parser, "accounts") and isinstance(parser.accounts, list):
            if len(parser.accounts) == 0:
                issues.append(ValidationIssue(
                    field="parser.accounts",
                    severity="warning",
                    message="Parser no extrajo cuentas (lista vacía)",
                    category="parser",
                ))

        return issues

    @staticmethod
    def _check_validation_consistency(ctx: Any) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        validation = getattr(ctx, "validation", None)
        if validation is None:
            return issues

        parser = getattr(ctx, "parser", None)
        if parser is None or not parser.accounts:
            issues.append(ValidationIssue(
                field="validation",
                severity="error",
                message="Validación ejecutada sin datos de parser",
                category="validation",
            ))

        if hasattr(validation, "errors") and validation.errors:
            for err in validation.errors:
                issues.append(ValidationIssue(
                    field="validation.errors",
                    severity="error",
                    message=f"Error de validación: {err}",
                    category="validation",
                ))

        return issues

    @staticmethod
    def _check_knowledge_consistency(ctx: Any) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        knowledge = getattr(ctx, "knowledge", None)
        if knowledge is None:
            return issues

        return issues

    @staticmethod
    def _check_lifecycle_consistency(ctx: Any) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        events = getattr(ctx, "events", [])
        if not events:
            return issues

        for i in range(1, len(events)):
            prev = events[i - 1]
            curr = events[i]
            if prev.to_state != curr.from_state and prev.to_state is not None:
                issues.append(ValidationIssue(
                    field=f"events[{i}]",
                    severity="warning",
                    message=f"Salto en cadena de eventos: {prev.to_state.value} → {curr.from_state.value}",
                    category="lifecycle",
                ))

        return issues

    @staticmethod
    def _check_snapshot_gaps(ctx: Any) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        events = getattr(ctx, "events", [])
        snapshots = getattr(ctx, "snapshots", [])

        if len(events) > len(snapshots) + 1:
            issues.append(ValidationIssue(
                field="snapshots",
                severity="info",
                message=f"Hay {len(events)} eventos pero solo {len(snapshots)} snapshots",
                category="snapshot",
            ))

        return issues

    @staticmethod
    def _check_completion_issues(ctx: Any) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        state = getattr(ctx, "state", None)
        if state != ProcessingState.COMPLETED:
            return issues

        validation = getattr(ctx, "validation", None)
        if validation and hasattr(validation, "errors") and validation.errors:
            issues.append(ValidationIssue(
                field="state",
                severity="warning",
                message="Completado con errores de validación",
                category="completion",
            ))

        has_review = any(
            getattr(e, "to_state", None) == ProcessingState.REVIEWED
            for e in getattr(ctx, "events", [])
        )
        if not has_review:
            issues.append(ValidationIssue(
                field="lifecycle",
                severity="info",
                message="Completado sin pasar por revisión humana",
                category="completion",
            ))

        return issues
