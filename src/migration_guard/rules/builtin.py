"""Built-in migration-safety rules.

Each rule matches a specific dangerous pattern in a normalized statement and
explains the safer expand/contract alternative. Rules are intentionally small
and independent so they are trivial to unit-test in isolation.

Dialect focus: PostgreSQL (the locking semantics described are Postgres's).
"""

from __future__ import annotations

import re

from ..config import Config
from ..models import Finding, Severity
from ..parser import Statement
from .base import Rule


class AddNotNullColumnWithoutDefault(Rule):
    id = "MG001"
    summary = "Adding a NOT NULL column without a default rewrites the whole table under a lock."
    name = "add-not-null-column-without-default"
    default_severity = Severity.HIGH

    _add_col = re.compile(r"\bALTER\s+TABLE\b.*\bADD\s+(?:COLUMN\s+)?")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        n = stmt.normalized
        if not self._add_col.search(n):
            return []
        if "NOT NULL" in n and "DEFAULT" not in n:
            return [
                self._finding(
                    stmt,
                    config,
                    "Adding a NOT NULL column without a default rewrites the "
                    "whole table under an exclusive lock.",
                    "Add the column nullable, backfill in batches, then "
                    "ALTER COLUMN ... SET NOT NULL (validated separately).",
                )
            ]
        return []


class CreateIndexNonConcurrent(Rule):
    id = "MG002"
    summary = "CREATE INDEX without CONCURRENTLY blocks writes to the table for the entire build."
    name = "create-index-non-concurrent"
    default_severity = Severity.HIGH
    dialects = frozenset({"postgres"})  # CONCURRENTLY is Postgres-only syntax

    _create_index = re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b")
    _fix_sub = re.compile(r"(?i)\b(CREATE\s+(?:UNIQUE\s+)?INDEX)\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        n = stmt.normalized
        if not self._create_index.search(n):
            return []
        if "CONCURRENTLY" in n:
            return []
        return [
            self._finding(
                stmt,
                config,
                "CREATE INDEX without CONCURRENTLY blocks writes to the table "
                "for the entire build.",
                "Use CREATE INDEX CONCURRENTLY (note: cannot run inside a "
                "transaction block).",
            )
        ]

    def fix(self, stmt: Statement) -> str | None:
        return self._fix_sub.sub(r"\1 CONCURRENTLY", stmt.source, count=1)


class DropColumn(Rule):
    id = "MG003"
    summary = "Dropping a column is a breaking change for deployed code still reading it."
    name = "drop-column"
    default_severity = Severity.MEDIUM

    _drop_col = re.compile(r"\bALTER\s+TABLE\b.*\bDROP\s+(?:COLUMN\b)")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        if not self._drop_col.search(stmt.normalized):
            return []
        return [
            self._finding(
                stmt,
                config,
                "Dropping a column is a breaking change for any deployed code "
                "still reading it.",
                "Follow expand/contract: stop referencing the column in all "
                "running versions first, then drop it in a later migration.",
            )
        ]


class RenameColumnOrTable(Rule):
    id = "MG004"
    summary = "Renaming a column or table breaks running code that uses the old name mid-deploy."
    name = "rename-column-or-table"
    default_severity = Severity.MEDIUM

    _rename = re.compile(r"\bALTER\s+TABLE\b.*\bRENAME\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        if not self._rename.search(stmt.normalized):
            return []
        return [
            self._finding(
                stmt,
                config,
                "Renaming a column/table breaks running code that uses the old "
                "name during a rolling deploy.",
                "Add the new name, dual-write/read, migrate readers, then drop "
                "the old name in a later migration.",
            )
        ]


class AlterColumnType(Rule):
    id = "MG005"
    summary = "Changing a column type generally rewrites the table under an exclusive lock."
    name = "alter-column-type"
    default_severity = Severity.HIGH

    _alter_type = re.compile(r"\bALTER\s+(?:COLUMN\s+)?[A-Z0-9_\"]+\s+(?:SET\s+DATA\s+)?TYPE\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        n = stmt.normalized
        if "ALTER TABLE" not in n or not self._alter_type.search(n):
            return []
        return [
            self._finding(
                stmt,
                config,
                "Changing a column type generally rewrites the table under an "
                "exclusive lock.",
                "Add a new column of the target type, backfill, swap reads/"
                "writes, then drop the old column.",
            )
        ]


class SetNotNullOnExisting(Rule):
    id = "MG006"
    summary = "SET NOT NULL scans the whole table under an exclusive lock to validate rows."
    name = "set-not-null-on-existing"
    default_severity = Severity.HIGH
    dialects = frozenset({"postgres"})  # CHECK ... NOT VALID trick is Postgres-only

    _set_not_null = re.compile(r"\bALTER\s+(?:COLUMN\s+)?[A-Z0-9_\"]+\s+SET\s+NOT\s+NULL\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        n = stmt.normalized
        if "ALTER TABLE" not in n or not self._set_not_null.search(n):
            return []
        return [
            self._finding(
                stmt,
                config,
                "SET NOT NULL scans the entire table under an exclusive lock to "
                "validate existing rows.",
                "Add a CHECK (col IS NOT NULL) NOT VALID constraint, VALIDATE it "
                "(no exclusive lock), then SET NOT NULL on modern Postgres.",
            )
        ]


class AddValidatedForeignKey(Rule):
    id = "MG007"
    summary = "Adding a validated foreign key scans every existing row while locking both tables."
    name = "add-validated-foreign-key"
    default_severity = Severity.HIGH
    dialects = frozenset({"postgres"})  # ADD CONSTRAINT ... NOT VALID is Postgres-only

    _add_fk = re.compile(r"\bADD\s+(?:CONSTRAINT\b.*)?FOREIGN\s+KEY\b")
    _references = re.compile(r"\bREFERENCES\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        n = stmt.normalized
        if "ALTER TABLE" not in n:
            return []
        is_fk = bool(self._add_fk.search(n)) or (
            "ADD CONSTRAINT" in n and bool(self._references.search(n))
        )
        if not is_fk or "NOT VALID" in n:
            return []
        return [
            self._finding(
                stmt,
                config,
                "Adding a foreign key validates every existing row while holding "
                "locks on both tables.",
                "Add the constraint with NOT VALID, then run VALIDATE CONSTRAINT "
                "in a separate step (takes only a lightweight lock).",
            )
        ]
