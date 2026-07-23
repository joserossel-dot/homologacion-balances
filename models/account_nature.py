from __future__ import annotations

from enum import Enum


class AccountNature(str, Enum):
    UNKNOWN = "unknown"
    ASSET = "asset"
    LIABILITY = "liability"
    LOSS = "loss"
    PROFIT = "profit"
