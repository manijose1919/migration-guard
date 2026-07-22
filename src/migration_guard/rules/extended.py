"""Extended rule set — data-loss guards and additional locking operations.

Kept separate from ``builtin.py`` to demonstrate the registry pattern: adding
a whole new category of rules touches only this file plus the registry list.
"""

from __future__ import annotations

import re

from ..config import Config
from ..models import Finding, Severity
from ..parser import Statement
from .base import Rule


class UpdateOrDeleteWithoutWhere(Rule):
    id = "MG008"
    name = "update-or-delete-without-where"
    default_severity = Severity.CRITICAL

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        if stmt.action not in ("UPDATE", "DELETE"):
            return []
        if "WHERE" in stmt.normalized:
            return []
        verb = stmt.action.title()
        return [
            self._finding(
                stmt,
                config,
                f"{verb} without a WHERE clause affects every row in the table.",
                "Add a WHERE clause, or if a full-table change is intended, do it "
                "in explicit batches to avoid a long-running lock and huge WAL.",
            )
        ]


class Truncate(Rule):
    id = "MG009"
    name = "truncate"
    default_severity = Severity.HIGH

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        if stmt.action != "TRUNCATE":
            return []
        return [
            self._finding(
                stmt,
                config,
                "TRUNCATE irreversibly removes all rows and takes an exclusive lock.",
                "Confirm the data loss is intended; for large tables consider "
                "batched DELETEs or a table swap instead.",
            )
        ]


class DropIndexNonConcurrent(Rule):
    id = "MG010"
    name = "drop-index-non-concurrent"
    default_severity = Severity.MEDIUM
    dialects = frozenset({"postgres"})  # DROP INDEX CONCURRENTLY is Postgres-only

    _drop_index = re.compile(r"\bDROP\s+INDEX\b")
    _fix_sub = re.compile(r"(?i)\b(DROP\s+INDEX)\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        n = stmt.normalized
        if not self._drop_index.search(n) or "CONCURRENTLY" in n:
            return []
        return [
            self._finding(
                stmt,
                config,
                "DROP INDEX takes an exclusive lock on the table.",
                "Use DROP INDEX CONCURRENTLY (outside a transaction) to avoid "
                "blocking reads and writes.",
            )
        ]

    def fix(self, stmt: Statement) -> str | None:
        return self._fix_sub.sub(r"\1 CONCURRENTLY", stmt.source, count=1)


class AddPrimaryKey(Rule):
    id = "MG011"
    name = "add-primary-key"
    default_severity = Severity.HIGH
    dialects = frozenset({"postgres"})  # advice uses CREATE UNIQUE INDEX CONCURRENTLY

    _add_pk = re.compile(r"\bADD\s+(?:CONSTRAINT\b.*)?PRIMARY\s+KEY\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        n = stmt.normalized
        if "ALTER TABLE" not in n or not self._add_pk.search(n):
            return []
        return [
            self._finding(
                stmt,
                config,
                "ADD PRIMARY KEY builds a unique index and sets NOT NULL under an "
                "exclusive lock (a full-table scan).",
                "CREATE UNIQUE INDEX CONCURRENTLY, then ADD PRIMARY KEY USING "
                "INDEX to attach it with a brief lock.",
            )
        ]


class VacuumFull(Rule):
    id = "MG012"
    name = "vacuum-full"
    default_severity = Severity.HIGH
    dialects = frozenset({"postgres"})  # VACUUM FULL is not MySQL syntax

    _vacuum_full = re.compile(r"\bVACUUM\s+FULL\b")
    _fix_sub = re.compile(r"(?i)\bVACUUM\s+FULL\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        if not self._vacuum_full.search(stmt.normalized):
            return []
        return [
            self._finding(
                stmt,
                config,
                "VACUUM FULL rewrites the entire table while holding an exclusive "
                "lock for the whole operation.",
                "Use plain VACUUM, or a tool like pg_repack to reclaim space "
                "without a long exclusive lock.",
            )
        ]

    def fix(self, stmt: Statement) -> str | None:
        return self._fix_sub.sub("VACUUM", stmt.source, count=1)


class DropTable(Rule):
    id = "MG013"
    name = "drop-table"
    default_severity = Severity.HIGH

    _drop_table = re.compile(r"\bDROP\s+TABLE\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        if not self._drop_table.search(stmt.normalized):
            return []
        return [
            self._finding(
                stmt,
                config,
                "Dropping a table permanently deletes its data and breaks any "
                "deployed code still using it.",
                "Follow expand/contract: stop all readers/writers first and take "
                "a backup, then drop the table in a later migration.",
            )
        ]


class Cluster(Rule):
    id = "MG014"
    name = "cluster"
    default_severity = Severity.HIGH
    dialects = frozenset({"postgres"})  # CLUSTER is Postgres syntax

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        # Action-based so an identifier containing "cluster" cannot trip it.
        if stmt.action != "CLUSTER":
            return []
        return [
            self._finding(
                stmt,
                config,
                "CLUSTER rewrites the whole table while holding an ACCESS "
                "EXCLUSIVE lock for the entire operation.",
                "Avoid CLUSTER on a live table; use pg_repack to reorder rows "
                "without a long exclusive lock.",
            )
        ]


class MysqlModifyColumn(Rule):
    id = "MG015"
    name = "mysql-modify-column"
    default_severity = Severity.HIGH
    dialects = frozenset({"mysql"})  # MODIFY/CHANGE COLUMN is MySQL syntax

    _modify = re.compile(r"\bALTER\s+TABLE\b.*\b(?:MODIFY|CHANGE)\s+(?:COLUMN\s+)?")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        if not self._modify.search(stmt.normalized):
            return []
        return [
            self._finding(
                stmt,
                config,
                "MODIFY/CHANGE COLUMN can rewrite the table and lock it, "
                "depending on the change and storage engine.",
                "Use an online-DDL path (ALGORITHM=INPLACE, LOCK=NONE) or a tool "
                "like gh-ost / pt-online-schema-change.",
            )
        ]


class Reindex(Rule):
    id = "MG016"
    name = "reindex"
    default_severity = Severity.HIGH
    dialects = frozenset({"postgres"})  # REINDEX is Postgres syntax

    # The safe rewrite (add CONCURRENTLY, PG12+) only covers the INDEX/TABLE
    # forms; DATABASE/SCHEMA/SYSTEM are flagged but not auto-rewritten.
    _fix_sub = re.compile(r"(?i)\b(REINDEX\s+(?:INDEX|TABLE))\b")

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        if stmt.action != "REINDEX" or "CONCURRENTLY" in stmt.normalized:
            return []
        return [
            self._finding(
                stmt,
                config,
                "REINDEX rebuilds indexes under an exclusive lock, blocking "
                "reads and writes for the whole rebuild.",
                "Use REINDEX ... CONCURRENTLY (PostgreSQL 12+) so the rebuild "
                "does not block traffic.",
            )
        ]

    def fix(self, stmt: Statement) -> str | None:
        fixed = self._fix_sub.sub(r"\1 CONCURRENTLY", stmt.source, count=1)
        return fixed if fixed != stmt.source else None


class LockTable(Rule):
    id = "MG017"
    name = "lock-table"
    default_severity = Severity.MEDIUM

    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        # Action-based: covers both LOCK TABLE (Postgres) and LOCK TABLES (MySQL).
        if stmt.action != "LOCK":
            return []
        return [
            self._finding(
                stmt,
                config,
                "Explicitly locking a table in a migration blocks other sessions "
                "for as long as the transaction runs.",
                "Avoid manual LOCK statements; rely on the minimal locks the DDL "
                "itself takes, and keep migration transactions short.",
            )
        ]
