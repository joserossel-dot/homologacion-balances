from __future__ import annotations
import hashlib
from collections import Counter
from .structure_models import StructuralTree, StructureTemplate, StructuralSignature


class TemplateBuilder:

    @staticmethod
    def build_template(
        tree: StructuralTree,
        file_name: str = "",
    ) -> StructureTemplate:
        type_seq = tree.type_sequence
        level_seq = [n.level for n in tree.nodes]
        section_seq = [n.section for n in tree.nodes]
        node_types = Counter(n.structural_type for n in tree.nodes)

        sig = tree.signature

        tid = hashlib.md5(
            f"{type_seq}|{tree.max_depth}|{tree.subtotal_count}|{tree.section_count}|{tree.code_format}"
            .encode()
        ).hexdigest()[:12]

        template = StructureTemplate(
            template_id=tid,
            name=f"template_{tid[:8]}",
            type_sequence=type_seq,
            level_sequence=level_seq,
            section_sequence=section_seq,
            max_depth=tree.max_depth,
            total_nodes=tree.total_nodes,
            subtotal_count=tree.subtotal_count,
            section_count=tree.section_count,
            node_type_counts=dict(node_types),
            code_format=tree.code_format,
            column_layout=tree.column_layout,
            signatures=[sig],
            example_files=[file_name] if file_name else [],
            frequency=1,
        )

        return template

    @staticmethod
    def templates_similar(
        t1: StructureTemplate,
        t2: StructureTemplate,
        threshold: float = 0.85,
    ) -> float:
        if not t1.signatures or not t2.signatures:
            return 0.0
        max_sim = max(
            s1.similarity_to(s2)
            for s1 in t1.signatures
            for s2 in t2.signatures
        )
        return max_sim

    @staticmethod
    def merge_templates(
        t1: StructureTemplate,
        t2: StructureTemplate,
    ) -> StructureTemplate:
        merged = StructureTemplate(
            template_id=t1.template_id,
            family=t1.family or t2.family,
            name=t1.name,
            type_sequence=t1.type_sequence,
            level_sequence=_longer_seq(t1.level_sequence, t2.level_sequence),
            section_sequence=_longer_seq(t1.section_sequence, t2.section_sequence)
            if len(t1.section_sequence) >= len(t2.section_sequence)
            else t2.section_sequence,
            max_depth=max(t1.max_depth, t2.max_depth),
            total_nodes=max(t1.total_nodes, t2.total_nodes),
            subtotal_count=max(t1.subtotal_count, t2.subtotal_count),
            section_count=max(t1.section_count, t2.section_count),
            node_type_counts={
                k: t1.node_type_counts.get(k, 0) + t2.node_type_counts.get(k, 0)
                for k in set(list(t1.node_type_counts.keys()) + list(t2.node_type_counts.keys()))
            },
            code_format=t1.code_format or t2.code_format,
            column_layout=t1.column_layout or t2.column_layout,
            signatures=t1.signatures + t2.signatures,
            example_files=list(set(t1.example_files + t2.example_files)),
            frequency=t1.frequency + t2.frequency,
        )
        return merged


def _longer_seq(s1: list, s2: list) -> list:
    return s1 if len(s1) >= len(s2) else s2
