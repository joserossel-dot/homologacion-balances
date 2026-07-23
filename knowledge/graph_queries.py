from __future__ import annotations

from knowledge.financial_graph import FinancialGraph
from knowledge.financial_node import FinancialNode
from knowledge.financial_tree import FinancialTree


class GraphQueries:
    def __init__(self, graph: FinancialGraph, tree: FinancialTree) -> None:
        self._graph = graph
        self._tree = tree

    @property
    def graph(self) -> FinancialGraph:
        return self._graph

    @property
    def tree(self) -> FinancialTree:
        return self._tree

    def activos_corrientes(self) -> list[FinancialNode]:
        return self._tree.find_by_subclass("corriente")

    def activos_no_corrientes(self) -> list[FinancialNode]:
        return self._tree.find_by_subclass("no_corriente")

    def pasivos_corrientes(self) -> list[FinancialNode]:
        nodes: list[FinancialNode] = []
        for node in self._tree.find_by_subclass("corriente"):
            if node.class_ == "pasivo":
                nodes.append(node)
        return nodes

    def pasivos_no_corrientes(self) -> list[FinancialNode]:
        nodes: list[FinancialNode] = []
        for node in self._tree.find_by_subclass("no_corriente"):
            if node.class_ == "pasivo":
                nodes.append(node)
        return nodes

    def patrimonio(self) -> list[FinancialNode]:
        return self._tree.find_by_class("patrimonio")

    def gastos(self) -> list[FinancialNode]:
        return [
            n for n in self._tree.nodes.values()
            if "expense" in n.semantic_types
        ]

    def ingresos(self) -> list[FinancialNode]:
        return [
            n for n in self._tree.nodes.values()
            if "revenue" in n.semantic_types
        ]

    def contra_activos(self) -> list[FinancialNode]:
        return [
            n for n in self._tree.nodes.values()
            if n.contra_accounts
        ]

    def cuentas_por_tag(self, tag: str) -> list[FinancialNode]:
        return self._tree.find_by_tag(tag)

    def cuentas_ifrs(self, ifrs_ref: str) -> list[FinancialNode]:
        return [
            n for n in self._tree.nodes.values()
            if any(ifrs_ref.upper() in r.upper() for r in n.ifrs)
        ]

    def cuentas_kpi(self, kpi: str) -> list[FinancialNode]:
        return self._tree.find_by_kpi(kpi)

    def activos_totales(self) -> list[FinancialNode]:
        return self._tree.find_by_class("activo")

    def pasivos_totales(self) -> list[FinancialNode]:
        return self._tree.find_by_class("pasivo")
