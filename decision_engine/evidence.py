from __future__ import annotations

from typing import Any

from document_context import DocumentContext
from document_context.models import DocumentMetadata, ParserData, KnowledgeData, ValidationData, StructureData

from .models import DecisionEvidence


class EvidenceCollector:
    @staticmethod
    def collect_all(ctx: DocumentContext) -> list[DecisionEvidence]:
        evidence: list[DecisionEvidence] = []
        evidence.extend(EvidenceCollector._from_parser(ctx))
        evidence.extend(EvidenceCollector._from_knowledge(ctx))
        evidence.extend(EvidenceCollector._from_structure(ctx))
        evidence.extend(EvidenceCollector._from_validation(ctx))
        evidence.extend(EvidenceCollector._from_die(ctx))
        return evidence

    @staticmethod
    def _from_parser(ctx: DocumentContext) -> list[DecisionEvidence]:
        result: list[DecisionEvidence] = []
        parser: ParserData | None = ctx.parser
        if parser is None:
            return result
        if parser.selected_parser:
            result.append(DecisionEvidence(
                source="parser", field="selected_parser",
                value=parser.selected_parser, confidence=0.9,
                detail=f"Parser: {parser.selected_parser}",
            ))
        result.append(DecisionEvidence(
            source="parser", field="total_raw",
            value=parser.total_raw, confidence=0.8,
            detail=f"Cuentas raw: {parser.total_raw}",
        ))
        if parser.accounts:
            result.append(DecisionEvidence(
                source="parser", field="accounts",
                value=len(parser.accounts), confidence=0.85,
                detail=f"Cuentas parseadas: {len(parser.accounts)}",
            ))
        return result

    @staticmethod
    def _from_knowledge(ctx: DocumentContext) -> list[DecisionEvidence]:
        result: list[DecisionEvidence] = []
        knowledge: KnowledgeData | None = ctx.knowledge
        if knowledge is None:
            return result
        result.append(DecisionEvidence(
            source="knowledge", field="total_matches",
            value=knowledge.total_matches, confidence=0.9,
            detail=f"Matches totales: {knowledge.total_matches}",
        ))
        if knowledge.learning_hits:
            result.append(DecisionEvidence(
                source="knowledge", field="learning_hits",
                value=len(knowledge.learning_hits), confidence=0.95,
                detail=f"Learning hits: {len(knowledge.learning_hits)}",
            ))
        if knowledge.dictionary_matches:
            result.append(DecisionEvidence(
                source="knowledge", field="dictionary_matches",
                value=len(knowledge.dictionary_matches), confidence=0.85,
                detail=f"Matches diccionario: {len(knowledge.dictionary_matches)}",
            ))
        return result

    @staticmethod
    def _from_structure(ctx: DocumentContext) -> list[DecisionEvidence]:
        result: list[DecisionEvidence] = []
        structure: StructureData | None = ctx.structure
        if structure is None:
            return result
        if structure.family:
            result.append(DecisionEvidence(
                source="structure", field="family",
                value=structure.family, confidence=0.7,
                detail=f"Familia: {structure.family}",
            ))
        if structure.template:
            result.append(DecisionEvidence(
                source="structure", field="template",
                value=structure.template, confidence=0.75,
                detail=f"Template: {structure.template}",
            ))
        if structure.column_layout:
            result.append(DecisionEvidence(
                source="structure", field="layout",
                value=structure.column_layout, confidence=0.6,
                detail=f"Layout: {structure.column_layout}",
            ))
        return result

    @staticmethod
    def _from_validation(ctx: DocumentContext) -> list[DecisionEvidence]:
        result: list[DecisionEvidence] = []
        validation: ValidationData | None = ctx.validation
        if validation is None:
            return result
        has_integrity = validation.integrity is not None
        result.append(DecisionEvidence(
            source="validation", field="has_integrity",
            value=has_integrity, confidence=0.8 if has_integrity else 0.0,
            detail=f"Integrity: {'ok' if has_integrity else 'not run'}",
        ))
        if validation.errors:
            result.append(DecisionEvidence(
                source="validation", field="errors",
                value=len(validation.errors), confidence=0.0,
                detail=f"Errores: {len(validation.errors)}",
            ))
        if validation.warnings:
            result.append(DecisionEvidence(
                source="validation", field="warnings",
                value=len(validation.warnings), confidence=0.3,
                detail=f"Advertencias: {len(validation.warnings)}",
            ))
        return result

    @staticmethod
    def _from_die(ctx: DocumentContext) -> list[DecisionEvidence]:
        result: list[DecisionEvidence] = []
        report = ctx.get_custom("die_report")
        if report is not None:
            result.append(DecisionEvidence(
                source="die", field="die_report",
                value=True, confidence=0.5,
                detail="Reporte DIE disponible",
            ))
        prediction = ctx.prediction
        if prediction is not None:
            result.append(DecisionEvidence(
                source="die", field="confidence_expected",
                value=prediction.confidence_expected, confidence=prediction.confidence_expected,
                detail=f"Confianza esperada: {prediction.confidence_expected}",
            ))
            result.append(DecisionEvidence(
                source="die", field="coverage_expected",
                value=prediction.coverage_expected, confidence=prediction.coverage_expected,
                detail=f"Cobertura esperada: {prediction.coverage_expected}",
            ))
        return result
