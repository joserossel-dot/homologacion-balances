from __future__ import annotations

from typing import Any

from knowledge_base.account import FinancialAccount


class TaxonomyNode:
    def __init__(self, key: str, label: str, level: int = 0) -> None:
        self.key = key
        self.label = label
        self.level = level
        self.children: list[TaxonomyNode] = []
        self.parent: TaxonomyNode | None = None
        self.accounts: list[FinancialAccount] = []

    def add_child(self, child: TaxonomyNode) -> None:
        child.parent = self
        self.children.append(child)

    def add_account(self, account: FinancialAccount) -> None:
        self.accounts.append(account)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "level": self.level,
            "children": [c.to_dict() for c in self.children],
            "accounts": [a.standard_code for a in self.accounts],
        }


class Taxonomy:
    def __init__(self, accounts: list[FinancialAccount] | None = None) -> None:
        self._root = TaxonomyNode("root", "Raíz")
        self._nodes: dict[str, TaxonomyNode] = {"root": self._root}
        if accounts is not None:
            self.build(accounts)

    def build(self, accounts: list[FinancialAccount]) -> None:
        classes: dict[str, TaxonomyNode] = {}
        subclasses: dict[str, TaxonomyNode] = {}
        groups: dict[str, TaxonomyNode] = {}

        for account in accounts:
            class_key = account.class_
            subclass_key = f"{account.class_}/{account.subclass}" if account.subclass else ""
            group_key = f"{account.class_}/{account.subclass}/{account.group}" if account.group else ""

            if class_key and class_key not in classes:
                node = TaxonomyNode(class_key, class_key, level=1)
                classes[class_key] = node
                self._nodes[class_key] = node
                self._root.add_child(node)

            if subclass_key:
                if subclass_key not in subclasses:
                    node = TaxonomyNode(subclass_key, account.subclass, level=2)
                    subclasses[subclass_key] = node
                    self._nodes[subclass_key] = node
                    if class_key in classes:
                        classes[class_key].add_child(node)

                if group_key:
                    if group_key not in groups:
                        node = TaxonomyNode(group_key, account.group, level=3)
                        groups[group_key] = node
                        self._nodes[group_key] = node
                        subclasses[subclass_key].add_child(node)
                    groups[group_key].add_account(account)
                else:
                    subclasses[subclass_key].add_account(account)
            else:
                if class_key in classes:
                    classes[class_key].add_account(account)

    @property
    def root(self) -> TaxonomyNode:
        return self._root

    def get_node(self, key: str) -> TaxonomyNode | None:
        return self._nodes.get(key)

    def find_accounts_by_class(self, class_: str) -> list[FinancialAccount]:
        node = self._nodes.get(class_)
        if node is None:
            return []
        return self._collect_accounts(node)

    def find_accounts_by_subclass(self, subclass: str) -> list[FinancialAccount]:
        for key, node in self._nodes.items():
            if node.level == 2 and node.label == subclass:
                return self._collect_accounts(node)
        return []

    def _collect_accounts(self, node: TaxonomyNode) -> list[FinancialAccount]:
        result = list(node.accounts)
        for child in node.children:
            result.extend(self._collect_accounts(child))
        return result

    def path_to(self, account: FinancialAccount) -> list[str]:
        parts: list[str] = []
        if account.class_:
            parts.append(account.class_)
        if account.subclass:
            parts.append(account.subclass)
        if account.group:
            parts.append(account.group)
        parts.append(account.standard_name)
        return parts

    def to_dict(self) -> dict[str, Any]:
        return self._root.to_dict()
