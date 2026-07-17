"""Inline suppression directives.

Teams grandfather known-safe statements with SQL comments:

    ALTER TABLE users ADD COLUMN a int NOT NULL;  -- migrationguard:disable-line MG001

    -- migrationguard:disable-next-line MG002
    CREATE INDEX idx ON users (email);

    -- migrationguard:disable-file MG003   (suppress MG003 for the whole file)

A directive with no rule IDs suppresses *all* rules at its scope.

Because the parser strips comments, we scan the raw SQL here and apply the
result as a post-filter in the analyzer — keeping this concern decoupled from
both parsing and rule logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DIRECTIVE = re.compile(
    r"migrationguard:(disable-next-line|disable-line|disable-file)\b(.*)$",
    re.IGNORECASE,
)
_RULE_ID = re.compile(r"MG\d+")

# Sentinel meaning "all rules".
ALL = None


@dataclass
class Suppressions:
    """Line-keyed suppression lookup for one SQL document."""

    file_all: bool = False
    file_ids: set[str] = field(default_factory=set)
    # line -> set of rule ids, or None for "all rules on this line".
    line_ids: dict[int, set[str] | None] = field(default_factory=dict)

    def _matches(self, entry: set[str] | None, rule_id: str) -> bool:
        return entry is ALL or rule_id in entry

    def is_suppressed(self, rule_id: str, line: int) -> bool:
        if self.file_all or rule_id in self.file_ids:
            return True
        if line in self.line_ids and self._matches(self.line_ids[line], rule_id):
            return True
        return False


def _parse_ids(trailing: str) -> set[str] | None:
    ids = set(_RULE_ID.findall(trailing.upper()))
    return ids or ALL


def parse_directives(sql: str) -> Suppressions:
    result = Suppressions()
    for lineno, text in enumerate(sql.splitlines(), start=1):
        m = _DIRECTIVE.search(text)
        if not m:
            continue
        kind = m.group(1).lower()
        ids = _parse_ids(m.group(2))

        if kind == "disable-file":
            if ids is ALL:
                result.file_all = True
            else:
                result.file_ids |= ids
        elif kind == "disable-line":
            result.line_ids[lineno] = _merge(result.line_ids.get(lineno, set()), ids)
        elif kind == "disable-next-line":
            target = lineno + 1
            result.line_ids[target] = _merge(result.line_ids.get(target, set()), ids)
    return result


def _merge(existing: set[str] | None, incoming: set[str] | None) -> set[str] | None:
    if existing is ALL or incoming is ALL:
        return ALL
    return (existing or set()) | (incoming or set())
