"""Analysis policy configuration.

Config is deliberately a plain, immutable-ish value object so it can be
constructed in code (library use) or hydrated from environment variables
(container / CI use) without any framework coupling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .models import Severity


def _split_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


@dataclass
class Config:
    """Policy that shapes how the analyzer scores and gates findings.

    Attributes:
        fail_on: Severity threshold that makes the CLI/CI gate fail.
        large_tables: Tables treated as high-traffic; locking ops on them
            are escalated one severity level.
        disabled_rules: Rule IDs to skip entirely.
    """

    fail_on: Severity = Severity.HIGH
    large_tables: set[str] = field(default_factory=set)
    disabled_rules: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        # Normalize for case-insensitive table matching.
        self.large_tables = {t.lower() for t in self.large_tables}
        self.fail_on = Severity.coerce(self.fail_on)

    def is_large(self, table: str | None) -> bool:
        return bool(table) and table.lower() in self.large_tables

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        src = env if env is not None else dict(os.environ)
        return cls(
            fail_on=Severity.coerce(src.get("MG_FAIL_ON", "HIGH")),
            large_tables=_split_csv(src.get("MG_LARGE_TABLES")),
            disabled_rules=_split_csv(src.get("MG_DISABLED_RULES")),
        )
