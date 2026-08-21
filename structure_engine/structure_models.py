from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SectionInfo:
    name: str = ""
    type: str = ""
    start_line: int = 0
    end_line: int = 0
    depth: int = 0
    node_count: int = 0


@dataclass
class StructuralNode:
    original_name: str = ""
    structural_type: str = ""  # H=header, D=detail, S=subtotal, I=intermediate
    depth: int = 0
    level: int = 0
    position: int = 0
    line_number: int = 0
    section: str = ""
    parent: Optional[StructuralNode] = None
    children: list[StructuralNode] = field(default_factory=list)
    has_amount: bool = False
    amount: float = 0.0
    original_code: str = ""
    code_format: str = ""


@dataclass
class StructuralTree:
    source_file: str = ""
    nodes: list[StructuralNode] = field(default_factory=list)
    max_depth: int = 0
    total_nodes: int = 0
    header_count: int = 0
    detail_count: int = 0
    subtotal_count: int = 0
    section_count: int = 0
    sections: list[SectionInfo] = field(default_factory=list)
    level_distribution: dict[int, int] = field(default_factory=dict)
    type_sequence: str = ""
    code_format: str = ""
    column_layout: str = ""

    @property
    def signature(self) -> StructuralSignature:
        return StructuralSignature(
            type_sequence=self.type_sequence,
            max_depth=self.max_depth,
            total_nodes=self.total_nodes,
            subtotal_ratio=round(self.subtotal_count / max(self.total_nodes, 1), 4),
            section_count=self.section_count,
            level_distribution=tuple(sorted(self.level_distribution.items())),
            code_format=self.code_format,
            column_layout=self.column_layout,
        )


@dataclass
class StructuralSignature:
    type_sequence: str = ""
    max_depth: int = 0
    total_nodes: int = 0
    subtotal_ratio: float = 0.0
    section_count: int = 0
    level_distribution: tuple = field(default_factory=tuple)
    code_format: str = ""
    column_layout: str = ""

    def similarity_to(self, other: StructuralSignature) -> float:
        if not other.type_sequence or not self.type_sequence:
            return 0.0

        seq_score = _sequence_similarity(self.type_sequence, other.type_sequence)
        depth_score = 1.0 - abs(self.max_depth - other.max_depth) / max(max(self.max_depth, other.max_depth), 1)
        node_score = 1.0 - abs(self.total_nodes - other.total_nodes) / max(max(self.total_nodes, other.total_nodes), 1)
        section_score = 1.0 - abs(self.section_count - other.section_count) / max(max(self.section_count, other.section_count), 1)
        subtotal_score = 1.0 - abs(self.subtotal_ratio - other.subtotal_ratio)
        format_score = 1.0 if self.code_format == other.code_format else 0.0
        column_score = 1.0 if self.column_layout == other.column_layout else 0.0

        return round(
            seq_score * 0.30
            + depth_score * 0.15
            + node_score * 0.10
            + section_score * 0.10
            + subtotal_score * 0.15
            + format_score * 0.10
            + column_score * 0.10,
            4,
        )


def _sequence_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0

    from difflib import SequenceMatcher
    return SequenceMatcher(None, s1, s2).ratio()


@dataclass
class StructureTemplate:
    template_id: str = ""
    family: str = ""
    name: str = ""
    type_sequence: str = ""
    level_sequence: list[int] = field(default_factory=list)
    section_sequence: list[str] = field(default_factory=list)
    max_depth: int = 0
    total_nodes: int = 0
    subtotal_count: int = 0
    section_count: int = 0
    node_type_counts: dict[str, int] = field(default_factory=dict)
    code_format: str = ""
    column_layout: str = ""
    signatures: list[StructuralSignature] = field(default_factory=list)
    example_files: list[str] = field(default_factory=list)
    frequency: int = 1
    avg_confidence: float = 0.0


@dataclass
class TemplateMatch:
    template_id: str = ""
    template_name: str = ""
    family: str = ""
    similarity: float = 0.0
    confidence: float = 0.0
    matched_sections: int = 0
    total_sections: int = 0


@dataclass
class StructuralFamily:
    name: str = ""
    templates: list[str] = field(default_factory=list)
    total_members: int = 0
    avg_depth: float = 0.0
    common_pattern: str = ""
    description: str = ""
