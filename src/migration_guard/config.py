"""Analysis policy configuration.

Config is deliberately a plain, immutable-ish value object so it can be
constructed in code (library use) or hydrated from environment variables
(container / CI use) without any framework coupling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 CI only
    import tomli as tomllib

from .models import Severity

CONFIG_FILENAME = ".migrationguard.toml"

#: SQL dialects the analyzer understands. The dialect selects which rules run:
#: Postgres-mechanism rules (CONCURRENTLY, NOT VALID, VACUUM FULL) are skipped
#: for MySQL, where that advice would be wrong.
SUPPORTED_DIALECTS = ("postgres", "mysql")
DEFAULT_DIALECT = "postgres"


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
        dialect: Target SQL dialect; selects which rules apply.
    """

    fail_on: Severity = Severity.HIGH
    large_tables: set[str] = field(default_factory=set)
    disabled_rules: set[str] = field(default_factory=set)
    dialect: str = DEFAULT_DIALECT

    def __post_init__(self) -> None:
        # Normalize for case-insensitive table matching.
        self.large_tables = {t.lower() for t in self.large_tables}
        self.fail_on = Severity.coerce(self.fail_on)
        self.dialect = self.dialect.lower()
        if self.dialect not in SUPPORTED_DIALECTS:
            raise ValueError(
                f"unknown dialect {self.dialect!r}; "
                f"choose one of {', '.join(SUPPORTED_DIALECTS)}"
            )

    def is_large(self, table: str | None) -> bool:
        return bool(table) and table.lower() in self.large_tables

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        src = env if env is not None else dict(os.environ)
        return cls(
            fail_on=Severity.coerce(src.get("MG_FAIL_ON", "HIGH")),
            large_tables=_split_csv(src.get("MG_LARGE_TABLES")),
            disabled_rules=_split_csv(src.get("MG_DISABLED_RULES")),
            dialect=src.get("MG_DIALECT", DEFAULT_DIALECT),
        )


# --- layered configuration resolution ---------------------------------------
#
# Precedence (lowest to highest): defaults -> config file -> env vars -> CLI flags.
# Each source contributes only the keys it actually sets, so higher layers
# override lower ones field-by-field rather than wholesale.


def discover_config(start: str | Path = ".") -> Path | None:
    """Walk up from ``start`` looking for a ``.migrationguard.toml`` file."""
    here = Path(start).resolve()
    for directory in (here, *here.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def _dict_from_toml(path: Path) -> dict[str, Any]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    # Support a standalone file (top-level keys) or a [tool.migration_guard] table.
    section = data.get("tool", {}).get("migration_guard", data)
    out: dict[str, Any] = {}
    if "fail_on" in section:
        out["fail_on"] = section["fail_on"]
    if "large_tables" in section:
        out["large_tables"] = set(section["large_tables"])
    if "disabled_rules" in section:
        out["disabled_rules"] = set(section["disabled_rules"])
    if "dialect" in section:
        out["dialect"] = section["dialect"]
    return out


def _dict_from_env(env: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "MG_FAIL_ON" in env:
        out["fail_on"] = env["MG_FAIL_ON"]
    if env.get("MG_LARGE_TABLES"):
        out["large_tables"] = _split_csv(env["MG_LARGE_TABLES"])
    if env.get("MG_DISABLED_RULES"):
        out["disabled_rules"] = _split_csv(env["MG_DISABLED_RULES"])
    if env.get("MG_DIALECT"):
        out["dialect"] = env["MG_DIALECT"]
    return out


def resolve_config(
    *,
    config_path: str | Path | None = None,
    start: str | Path = ".",
    env: dict[str, str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> Config:
    """Build a Config by layering file, environment, then explicit overrides."""
    env = dict(os.environ) if env is None else env
    layers: dict[str, Any] = {}

    path = Path(config_path) if config_path else discover_config(start)
    if path and path.is_file():
        layers.update(_dict_from_toml(path))

    layers.update(_dict_from_env(env))

    if overrides:
        layers.update({k: v for k, v in overrides.items() if v is not None})

    return Config(**layers)
