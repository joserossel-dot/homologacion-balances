from __future__ import annotations
import difflib
from .structure_models import StructuralTree, StructureTemplate, TemplateMatch


class TemplateMatcher:

    def __init__(self, templates: list[StructureTemplate]):
        self.templates = templates

    def match(self, tree: StructuralTree, threshold: float = 0.5) -> list[TemplateMatch]:
        if not self.templates:
            return []

        sig = tree.signature
        results = []

        for template in self.templates:
            if not template.signatures:
                continue

            max_sim = max(
                sig.similarity_to(ts) for ts in template.signatures
            )

            if max_sim >= threshold:
                confidence = max_sim

                section_overlap = _section_overlap(
                    [n.section for n in tree.nodes],
                    template.section_sequence,
                )

                results.append(TemplateMatch(
                    template_id=template.template_id,
                    template_name=template.name,
                    family=template.family,
                    similarity=round(max_sim * 100, 1),
                    confidence=round(confidence * 100, 1),
                    matched_sections=section_overlap[0],
                    total_sections=section_overlap[1],
                ))

        results.sort(key=lambda m: (-m.similarity, -m.confidence))
        return results

    def best_match(self, tree: StructuralTree, min_similarity: float = 0.5) -> TemplateMatch | None:
        matches = self.match(tree, threshold=min_similarity)
        return matches[0] if matches else None


def _section_overlap(tree_sections: list[str], template_sections: list[str]) -> tuple[int, int]:
    if not tree_sections or not template_sections:
        return (0, 0)
    tree_unique = set(s for s in tree_sections if s)
    template_unique = set(s for s in template_sections if s)
    overlap = len(tree_unique & template_unique)
    total_unique = len(tree_unique | template_unique)
    return (overlap, max(len(tree_unique), len(template_unique)))
