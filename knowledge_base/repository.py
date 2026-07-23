from __future__ import annotations

from knowledge_base.account import FinancialAccount
from knowledge_base.relation import Relation, RelationManager
from knowledge_base.rule import Rule, RuleManager
from knowledge_base.synonym import SynonymEntry, SynonymManager
from knowledge_base.taxonomy import Taxonomy


class Repository:
    def __init__(self) -> None:
        self._accounts: dict[str, FinancialAccount] = {}
        self._synonyms = SynonymManager()
        self._relations = RelationManager()
        self._rules = RuleManager()
        self._taxonomy = Taxonomy()

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def add_account(self, account: FinancialAccount) -> None:
        self._accounts[account.account_id] = account

    def get_account(self, account_id: str) -> FinancialAccount | None:
        return self._accounts.get(account_id)

    def get_account_by_code(self, code: str) -> FinancialAccount | None:
        for a in self._accounts.values():
            if a.standard_code == code:
                return a
        return None

    def update_account(self, account: FinancialAccount) -> bool:
        if account.account_id in self._accounts:
            self._accounts[account.account_id] = account
            return True
        return False

    def delete_account(self, account_id: str) -> bool:
        return self._accounts.pop(account_id, None) is not None

    def list_accounts(self) -> list[FinancialAccount]:
        return list(self._accounts.values())

    def count_accounts(self) -> int:
        return len(self._accounts)

    def find_by_class(self, class_: str) -> list[FinancialAccount]:
        return [a for a in self._accounts.values() if a.class_ == class_]

    def find_by_subclass(self, subclass: str) -> list[FinancialAccount]:
        return [a for a in self._accounts.values() if a.subclass == subclass]

    def find_by_semantic_type(self, semantic_type: str) -> list[FinancialAccount]:
        return [a for a in self._accounts.values() if a.semantic_type == semantic_type]

    def find_by_kpi(self, kpi: str) -> list[FinancialAccount]:
        return [a for a in self._accounts.values() if kpi in a.kpi_tags]

    def find_by_industry_tag(self, tag: str) -> list[FinancialAccount]:
        return [a for a in self._accounts.values() if tag in a.industry_tags]

    def find_by_status(self, status: str) -> list[FinancialAccount]:
        return [a for a in self._accounts.values() if a.status == status]

    def find_by_keyword(self, keyword: str) -> list[FinancialAccount]:
        kw = keyword.lower()
        return [
            a for a in self._accounts.values()
            if any(kw in s.lower() for s in a.synonyms)
            or any(kw in k.lower() for k in a.keywords)
        ]

    # ------------------------------------------------------------------
    # Synonyms
    # ------------------------------------------------------------------

    @property
    def synonyms(self) -> SynonymManager:
        return self._synonyms

    def add_synonym(self, entry: SynonymEntry) -> None:
        self._synonyms.add(entry)

    def remove_synonym(self, term: str, account_id: str) -> bool:
        return self._synonyms.remove(term, account_id)

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    @property
    def relations(self) -> RelationManager:
        return self._relations

    def add_relation(self, relation: Relation) -> None:
        self._relations.add(relation)

    def remove_relation(self, source_id: str, target_id: str, relation_type: str) -> bool:
        return self._relations.remove(source_id, target_id, relation_type)

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    @property
    def rules(self) -> RuleManager:
        return self._rules

    def add_rule(self, rule: Rule) -> None:
        self._rules.add(rule)

    def remove_rule(self, rule_id: str) -> bool:
        return self._rules.remove(rule_id)

    # ------------------------------------------------------------------
    # Taxonomy
    # ------------------------------------------------------------------

    def build_taxonomy(self) -> Taxonomy:
        self._taxonomy = Taxonomy(self.list_accounts())
        return self._taxonomy

    @property
    def taxonomy(self) -> Taxonomy:
        return self._taxonomy

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def account_codes(self) -> set[str]:
        return {a.standard_code for a in self._accounts.values()}

    def find_contra_accounts(self, account_id: str) -> list[FinancialAccount]:
        account = self.get_account(account_id)
        if account is None:
            return []
        result: list[FinancialAccount] = []
        for contra_id in account.contra_accounts:
            contra = self.get_account(contra_id)
            if contra is not None:
                result.append(contra)
        return result

    def find_related_accounts(self, account_id: str) -> list[FinancialAccount]:
        account = self.get_account(account_id)
        if account is None:
            return []
        result: list[FinancialAccount] = []
        for rel_id in account.related_accounts:
            rel = self.get_account(rel_id)
            if rel is not None:
                result.append(rel)
        return result
