from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge_base.account import FinancialAccount
from knowledge_base.repository import Repository


@dataclass
class ValidationError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class Validator:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def validate_all(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        errors.extend(self._check_duplicate_codes())
        errors.extend(self._check_cycles())
        errors.extend(self._check_invalid_relations())
        errors.extend(self._check_nonexistent_contra_accounts())
        errors.extend(self._check_duplicate_synonyms())
        errors.extend(self._check_nonexistent_related_accounts())
        errors.extend(self._check_invalid_status())
        errors.extend(self._check_missing_required_fields())
        return errors

    def _check_duplicate_codes(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        seen: dict[str, list[str]] = {}
        for account in self._repository.list_accounts():
            code = account.standard_code
            if code in seen:
                seen[code].append(account.account_id)
            else:
                seen[code] = [account.account_id]
        for code, ids in seen.items():
            if len(ids) > 1:
                errors.append(ValidationError(
                    code="DUPLICATE_CODE",
                    message=f"Standard code '{code}' is used by multiple accounts: {ids}",
                    details={"code": code, "account_ids": ids},
                ))
        return errors

    def _check_cycles(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        accounts = self._repository.list_accounts()
        adj: dict[str, list[str]] = {}
        for a in accounts:
            adj.setdefault(a.account_id, [])
            for contra_id in a.contra_accounts:
                adj[a.account_id].append(contra_id)
            for rel_id in a.related_accounts:
                adj[a.account_id].append(rel_id)

        visited: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()

        def dfs(node: str) -> bool:
            if node in path_set:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                errors.append(ValidationError(
                    code="CYCLE_DETECTED",
                    message=f"Circular reference detected: {' → '.join(cycle)}",
                    details={"cycle": cycle},
                ))
                return True
            if node in visited:
                return False
            visited.add(node)
            path.append(node)
            path_set.add(node)
            for neighbor in adj.get(node, []):
                dfs(neighbor)
            path.pop()
            path_set.discard(node)
            return False

        for a in accounts:
            if a.account_id not in visited:
                dfs(a.account_id)

        return errors

    def _check_invalid_relations(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        codes = self._repository.account_codes()
        for relation in self._repository.relations.all_relations():
            if relation.source_id not in codes:
                errors.append(ValidationError(
                    code="INVALID_RELATION_SOURCE",
                    message=f"Relation source '{relation.source_id}' does not exist",
                    details={"source": relation.source_id, "type": relation.relation_type, "target": relation.target_id},
                ))
            if relation.target_id not in codes:
                errors.append(ValidationError(
                    code="INVALID_RELATION_TARGET",
                    message=f"Relation target '{relation.target_id}' does not exist",
                    details={"source": relation.source_id, "type": relation.relation_type, "target": relation.target_id},
                ))
        return errors

    def _check_nonexistent_contra_accounts(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        codes = self._repository.account_codes()
        for account in self._repository.list_accounts():
            for contra_id in account.contra_accounts:
                if contra_id not in codes:
                    errors.append(ValidationError(
                        code="NONEXISTENT_CONTRA_ACCOUNT",
                        message=f"Account '{account.standard_code}' references non-existent contra account '{contra_id}'",
                        details={"account": account.standard_code, "contra_account": contra_id},
                    ))
        return errors

    def _check_nonexistent_related_accounts(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        codes = self._repository.account_codes()
        for account in self._repository.list_accounts():
            for rel_id in account.related_accounts:
                if rel_id not in codes:
                    errors.append(ValidationError(
                        code="NONEXISTENT_RELATED_ACCOUNT",
                        message=f"Account '{account.standard_code}' references non-existent related account '{rel_id}'",
                        details={"account": account.standard_code, "related_account": rel_id},
                    ))
        return errors

    def _check_duplicate_synonyms(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        duplicates = self._repository.synonyms.has_duplicates()
        for term, account_id in duplicates:
            errors.append(ValidationError(
                code="DUPLICATE_SYNONYM",
                message=f"Duplicate synonym term '{term}' for account '{account_id}'",
                details={"term": term, "account_id": account_id},
            ))
        return errors

    def _check_invalid_status(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        valid_statuses = {"active", "inactive", "deprecated"}
        for account in self._repository.list_accounts():
            if account.status not in valid_statuses:
                errors.append(ValidationError(
                    code="INVALID_STATUS",
                    message=f"Account '{account.standard_code}' has invalid status '{account.status}'",
                    details={"account": account.standard_code, "status": account.status},
                ))
        return errors

    def _check_missing_required_fields(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        for account in self._repository.list_accounts():
            if not account.standard_code:
                errors.append(ValidationError(
                    code="MISSING_CODE",
                    message=f"Account '{account.account_id}' is missing standard_code",
                    details={"account_id": account.account_id},
                ))
            if not account.standard_name:
                errors.append(ValidationError(
                    code="MISSING_NAME",
                    message=f"Account '{account.account_id}' is missing standard_name",
                    details={"account_id": account.account_id},
                ))
        return errors
