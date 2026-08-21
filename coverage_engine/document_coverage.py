from __future__ import annotations

from typing import Any

from .models import (
    DocumentCoverage, CoverageIssue, CoverageSeverity,
    EXPECTED_SECTIONS, FAMILY_ORDER,
)


class DocumentCoverageCalculator:
    """Calcula cobertura documental del documento.

    Mide:
    - Secciones esperadas vs presentes vs correctamente interpretadas
    - Para cada sección (Activo, Pasivo, Patrimonio, Resultado, Notas)
    """

    def compute(
        self,
        structure_data: Any = None,
        metadata: Any = None,
        expected_sections: list[str] | None = None,
    ) -> tuple[DocumentCoverage, list[CoverageIssue]]:
        issues: list[CoverageIssue] = []

        if expected_sections is None:
            expected_sections = list(EXPECTED_SECTIONS)

        present_sections = self._detect_present_sections(structure_data)
        correct_sections = self._detect_correct_sections(
            structure_data, present_sections,
        )
        not_applicable: list[str] = []

        na_keywords = ["nota", "anexo", "no aplica"]
        for section in list(present_sections):
            if any(kw in section.lower() for kw in na_keywords):
                not_applicable.append(section)
                present_sections.remove(section)
                if section in correct_sections:
                    correct_sections.remove(section)

        active_expected = [s for s in expected_sections if s not in not_applicable]
        total_expected = len(active_expected)
        total_present = len(present_sections)
        total_correct = len(correct_sections)

        coverage_pct = (
            total_correct / total_expected if total_expected > 0 else 1.0
        )

        section_details: dict[str, str] = {}
        for sec in expected_sections:
            if sec in not_applicable:
                section_details[sec] = "N/A"
            elif sec in correct_sections:
                section_details[sec] = "OK"
            elif sec in present_sections:
                section_details[sec] = "PRESENT"
            else:
                section_details[sec] = "MISSING"

        missing = set(active_expected) - present_sections
        if missing:
            issues.append(CoverageIssue(
                issue_type="section_missing",
                severity=CoverageSeverity.HIGH,
                monetary_impact=0.0,
                document_impact=round(len(missing) / total_expected, 4),
                detail=f"Secciones faltantes: {', '.join(sorted(missing))}",
                family="",
            ))

        incorrect = present_sections - correct_sections
        if incorrect:
            issues.append(CoverageIssue(
                issue_type="section_incorrect",
                severity=CoverageSeverity.MEDIUM,
                monetary_impact=0.0,
                document_impact=round(len(incorrect) / total_expected, 4),
                detail=f"Secciones incorrectamente interpretadas: {', '.join(sorted(incorrect))}",
                family="",
            ))

        document = DocumentCoverage(
            expected_sections=expected_sections,
            present_sections=list(present_sections),
            correct_sections=list(correct_sections),
            not_applicable_sections=not_applicable,
            coverage_pct=coverage_pct,
            section_details=section_details,
        )

        return document, issues

    def _detect_present_sections(self, structure_data: Any) -> set[str]:
        present: set[str] = set()

        if structure_data is None:
            return present

        sections = getattr(structure_data, "sections", None) or []
        if sections:
            for s in sections:
                if isinstance(s, dict):
                    name = s.get("name", "")
                else:
                    name = getattr(s, "name", "")
                if name:
                    present.add(name)
            return present

        family = getattr(structure_data, "family", "") or ""
        if family:
            present.add(family)

        tree = getattr(structure_data, "tree", None)
        if tree is not None:
            tree_sections = getattr(tree, "sections", []) or []
            for s in tree_sections:
                name = getattr(s, "name", "") if not isinstance(s, dict) else s.get("name", "")
                if name:
                    present.add(name)

        doc_type = getattr(structure_data, "document_type", "") or ""
        if doc_type:
            present.add(doc_type)

        return present or set(EXPECTED_SECTIONS[:2])

    def _detect_correct_sections(
        self,
        structure_data: Any,
        present_sections: set[str],
    ) -> set[str]:
        correct: set[str] = set()

        if structure_data is None:
            return correct

        family = getattr(structure_data, "family", "") or ""
        template = getattr(structure_data, "template", "") or ""

        for sec in present_sections:
            section_lower = sec.lower()
            family_lower = family.lower()
            if family_lower and section_lower == family_lower:
                correct.add(sec)
            elif family_lower and section_lower in family_lower:
                correct.add(sec)
            elif section_lower in [e.lower() for e in EXPECTED_SECTIONS]:
                correct.add(sec)

        if template:
            for sec in present_sections:
                correct.add(sec)

        if not correct and present_sections:
            correct = set(present_sections)

        return correct
