from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AccountNode:
    account_code: str = ""
    account_name: str = ""
    amount: float = 0.0
    level: int = 0
    line_number: int = 0
    source_column: str = ""
    es_total: bool = False
    es_header: bool = False
    es_subtotal: bool = False
    naturaleza: str = ""
    parent: Optional[AccountNode] = None
    children: list[AccountNode] = field(default_factory=list)

    def add_child(self, child: AccountNode):
        child.parent = self
        self.children.append(child)

    @property
    def all_descendants(self) -> list[AccountNode]:
        result = []
        for c in self.children:
            result.append(c)
            result.extend(c.all_descendants)
        return result

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def depth(self) -> int:
        d = 0
        p = self.parent
        while p:
            d += 1
            p = p.parent
        return d


@dataclass
class HierarchyTree:
    roots: list[AccountNode] = field(default_factory=list)
    all_nodes: list[AccountNode] = field(default_factory=list)
    total_nodes: list[AccountNode] = field(default_factory=list)
    subtotal_nodes: list[AccountNode] = field(default_factory=list)
    header_nodes: list[AccountNode] = field(default_factory=list)
    detail_nodes: list[AccountNode] = field(default_factory=list)

    def find_by_name(self, name: str) -> list[AccountNode]:
        return [n for n in self.all_nodes if name.lower() in n.account_name.lower()]

    def find_by_code(self, code: str) -> Optional[AccountNode]:
        for n in self.all_nodes:
            if n.account_code == code:
                return n
        return None

    @property
    def total_accounts(self) -> int:
        return len(self.all_nodes)


@dataclass
class SubtotalResult:
    account_name: str = ""
    account_code: str = ""
    expected: float = 0.0
    actual: float = 0.0
    difference: float = 0.0
    pct_diff: float = 0.0
    children_count: int = 0
    children: list[str] = field(default_factory=list)
    passed: bool = False
    line_number: int = 0


@dataclass
class EquationResult:
    equation: str = ""
    left_side: float = 0.0
    right_side: float = 0.0
    difference: float = 0.0
    left_components: dict[str, float] = field(default_factory=dict)
    right_components: dict[str, float] = field(default_factory=dict)
    passed: bool = False


@dataclass
class MissingAccountCandidate:
    target_amount: float = 0.0
    matched_amount: float = 0.0
    line_number: int = 0
    account_name: str = ""
    reason: str = ""
    similarity_pct: float = 0.0


@dataclass
class IntegrityScore:
    extraction_score: float = 0.0
    classification_score: float = 0.0
    hierarchy_score: float = 0.0
    subtotal_score: float = 0.0
    equation_score: float = 0.0
    overall: float = 0.0

    def compute_overall(self):
        weights = {
            "extraction": 0.10,
            "classification": 0.20,
            "hierarchy": 0.15,
            "subtotal": 0.30,
            "equation": 0.25,
        }
        self.overall = (
            self.extraction_score * weights["extraction"]
            + self.classification_score * weights["classification"]
            + self.hierarchy_score * weights["hierarchy"]
            + self.subtotal_score * weights["subtotal"]
            + self.equation_score * weights["equation"]
        )
        return self.overall


@dataclass
class ValidationResult:
    source_file: str = ""
    company: str = ""
    year: int = 0
    pages: int = 0
    accounts_total: int = 0
    accounts_classified: int = 0
    accounts_ignored: int = 0
    format_family: str = ""
    layout_type: str = ""

    hierarchy_tree: Optional[HierarchyTree] = None
    section_map: dict = field(default_factory=dict)
    subtotal_results: list[SubtotalResult] = field(default_factory=list)
    equation_results: list[EquationResult] = field(default_factory=list)
    missing_candidates: list[MissingAccountCandidate] = field(default_factory=list)
    integrity_score: Optional[IntegrityScore] = None

    warnings: list[str] = field(default_factory=list)
