"""Rule registry.

``default_rules()`` returns a fresh list of every built-in rule instance. The
analyzer consumes this; tests and integrators can pass their own list to run a
custom rule set.
"""

from __future__ import annotations

from .base import Rule
from .builtin import (
    AddNotNullColumnWithoutDefault,
    AddValidatedForeignKey,
    AlterColumnType,
    CreateIndexNonConcurrent,
    DropColumn,
    RenameColumnOrTable,
    SetNotNullOnExisting,
)
from .extended import (
    AddPrimaryKey,
    Cluster,
    DropIndexNonConcurrent,
    DropTable,
    LockTable,
    MysqlModifyColumn,
    Reindex,
    Truncate,
    UpdateOrDeleteWithoutWhere,
    VacuumFull,
)

_REGISTRY: list[type[Rule]] = [
    AddNotNullColumnWithoutDefault,
    CreateIndexNonConcurrent,
    DropColumn,
    RenameColumnOrTable,
    AlterColumnType,
    SetNotNullOnExisting,
    AddValidatedForeignKey,
    UpdateOrDeleteWithoutWhere,
    Truncate,
    DropIndexNonConcurrent,
    AddPrimaryKey,
    VacuumFull,
    DropTable,
    Cluster,
    MysqlModifyColumn,
    Reindex,
    LockTable,
]


def default_rules() -> list[Rule]:
    """Instantiate every registered rule."""
    return [cls() for cls in _REGISTRY]


def rule_catalog() -> list[dict]:
    """Metadata for every rule (for docs / an API ``/rules`` endpoint)."""
    return [
        {
            "id": cls.id,
            "name": cls.name,
            "default_severity": cls.default_severity.value,
            "summary": cls.summary,
            "dialects": sorted(cls.dialects),
            # A rule is fixable when it overrides the base no-op ``fix``.
            "fixable": cls.fix is not Rule.fix,
        }
        for cls in _REGISTRY
    ]


__all__ = ["Rule", "default_rules", "rule_catalog"]
