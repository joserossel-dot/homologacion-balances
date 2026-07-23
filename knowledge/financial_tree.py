from __future__ import annotations

from knowledge.financial_node import FinancialNode


class FinancialTree:
    def __init__(self, nodes: list[FinancialNode] | None = None) -> None:
        self._nodes: dict[str, FinancialNode] = {}
        self._roots: list[FinancialNode] = []
        if nodes is not None:
            for node in nodes:
                self.add_node(node)

    def add_node(self, node: FinancialNode) -> None:
        self._nodes[node.code] = node

    def get_node(self, code: str) -> FinancialNode | None:
        return self._nodes.get(code)

    def remove_node(self, code: str) -> None:
        self._nodes.pop(code, None)

    @property
    def nodes(self) -> dict[str, FinancialNode]:
        return dict(self._nodes)

    @property
    def roots(self) -> list[FinancialNode]:
        return [n for n in self._nodes.values() if n.parent_code is None]

    def children(self, code: str) -> list[FinancialNode]:
        node = self._nodes.get(code)
        if node is None:
            return []
        return [self._nodes[c] for c in node.children_codes if c in self._nodes]

    def parent(self, code: str) -> FinancialNode | None:
        node = self._nodes.get(code)
        if node is None or node.parent_code is None:
            return None
        return self._nodes.get(node.parent_code)

    def ancestors(self, code: str) -> list[FinancialNode]:
        result: list[FinancialNode] = []
        current = self.parent(code)
        while current is not None:
            result.append(current)
            current = self.parent(current.code)
        return result

    def descendants(self, code: str) -> list[FinancialNode]:
        result: list[FinancialNode] = []
        stack = list(self.children(code))
        while stack:
            node = stack.pop()
            result.append(node)
            stack.extend(self.children(node.code))
        return result

    def siblings(self, code: str) -> list[FinancialNode]:
        p = self.parent(code)
        if p is None:
            return []
        return [self._nodes[c] for c in p.children_codes if c in self._nodes and c != code]

    def depth(self, code: str) -> int:
        return len(self.ancestors(code))

    def path_to_root(self, code: str) -> list[str]:
        return [n.code for n in self.ancestors(code)] + [code]

    def find_by_class(self, class_: str) -> list[FinancialNode]:
        return [n for n in self._nodes.values() if n.class_ == class_]

    def find_by_subclass(self, subclass: str) -> list[FinancialNode]:
        return [n for n in self._nodes.values() if n.subclass == subclass]

    def find_by_tag(self, tag: str) -> list[FinancialNode]:
        return [n for n in self._nodes.values() if tag in n.tags]

    def find_by_semantic_type(self, semantic_type: str) -> list[FinancialNode]:
        return [n for n in self._nodes.values() if semantic_type in n.semantic_types]

    def find_by_kpi(self, kpi: str) -> list[FinancialNode]:
        return [n for n in self._nodes.values() if kpi in n.kpi_groups]
