from __future__ import annotations

from knowledge.financial_node import FinancialNode


class FinancialGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, FinancialNode] = {}
        self._edges: list[tuple[str, str, str]] = []

    def add_node(self, node: FinancialNode) -> None:
        self._nodes[node.code] = node

    def get_node(self, code: str) -> FinancialNode | None:
        return self._nodes.get(code)

    def remove_node(self, code: str) -> None:
        self._nodes.pop(code, None)
        self._edges = [
            (s, t, r) for s, t, r in self._edges if s != code and t != code
        ]

    def add_edge(self, source: str, target: str, relation: str) -> None:
        if source not in self._nodes or target not in self._nodes:
            return
        edge = (source, target, relation)
        if edge not in self._edges:
            self._edges.append(edge)

    def remove_edge(self, source: str, target: str, relation: str) -> None:
        self._edges = [
            (s, t, r) for s, t, r in self._edges
            if not (s == source and t == target and r == relation)
        ]

    def has_edge(self, source: str, target: str, relation: str) -> bool:
        return (source, target, relation) in self._edges

    @property
    def nodes(self) -> dict[str, FinancialNode]:
        return dict(self._nodes)

    @property
    def edges(self) -> list[tuple[str, str, str]]:
        return list(self._edges)

    def neighbors(self, code: str, relation: str | None = None) -> list[FinancialNode]:
        result: list[FinancialNode] = []
        for s, t, r in self._edges:
            if s == code and (relation is None or r == relation):
                node = self._nodes.get(t)
                if node is not None:
                    result.append(node)
            if t == code and (relation is None or r == relation):
                node = self._nodes.get(s)
                if node is not None:
                    result.append(node)
        return result

    def neighbors_by_relation(self, code: str, relation: str) -> list[FinancialNode]:
        return self.neighbors(code, relation)

    def find_by_class(self, class_: str) -> list[FinancialNode]:
        return [n for n in self._nodes.values() if n.class_ == class_]

    def find_by_tag(self, tag: str) -> list[FinancialNode]:
        return [n for n in self._nodes.values() if tag in n.tags]

    def subgraph(self, codes: list[str]) -> FinancialGraph:
        g = FinancialGraph()
        code_set = set(codes)
        for code in codes:
            node = self._nodes.get(code)
            if node is not None:
                g.add_node(node)
        for s, t, r in self._edges:
            if s in code_set and t in code_set:
                g.add_edge(s, t, r)
        return g
