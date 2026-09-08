"""Contrato mínimo de identidad y roles locales."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable


UserRole = Literal["analyst", "supervisor", "admin"]


@dataclass(frozen=True, slots=True)
class UserRecord:
    user_id: str
    display_name: str
    role: UserRole
    active: bool
    created_at: datetime


@runtime_checkable
class LocalUserRepository(Protocol):
    def upsert(self, user: UserRecord) -> UserRecord: ...

    def get_user(self, user_id: str) -> UserRecord | None: ...

    def list_active(self) -> list[UserRecord]: ...
