"""Turn raw SQL text into a list of normalized :class:`Statement` objects.

We lean on ``sqlparse`` for splitting and comment stripping, then compute a
best-effort source line number for each statement so findings can point the
developer at the offending line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlparse


@dataclass
class Statement:
    """One normalized SQL statement.

    Attributes:
        raw: The statement with comments stripped, original casing preserved.
        normalized: Uppercased, whitespace-collapsed form used by rule regexes.
        line: 1-based line in the source document where the action starts.
        index: 0-based position of the statement in the document.
        action: Leading keyword (ALTER, CREATE, ...), uppercased.
    """

    raw: str
    normalized: str
    line: int
    index: int
    action: str = field(default="")

    @property
    def table(self) -> str | None:
        """Best-effort table name the statement operates on."""
        return extract_table(self.normalized)


def _normalize(text: str) -> str:
    return " ".join(text.upper().split())


def _first_word(text: str) -> str:
    match = re.match(r"\s*([A-Za-z_]+)", text)
    return match.group(1).upper() if match else ""


def parse_sql(sql: str) -> list[Statement]:
    """Split ``sql`` into normalized statements with source line numbers.

    The cursor always advances past the *entire* previous statement, so a
    statement that repeats its action keyword (e.g. ``ALTER TABLE t ALTER
    COLUMN ...``) never confuses the line lookup for the next statement.
    """
    statements: list[Statement] = []
    cursor = 0
    index = 0
    for raw_chunk in sqlparse.split(sql):
        chunk = raw_chunk.strip()
        if not chunk:
            continue

        start = sql.find(chunk, cursor)
        if start == -1:
            start = cursor
        cursor = start + len(chunk)

        formatted = sqlparse.format(chunk, strip_comments=True).strip()
        # Drop the statement terminator so raw/normalized stay clean.
        formatted = formatted.rstrip(";").strip()
        if not formatted:
            continue

        action = _first_word(formatted)
        # Line of the action keyword within this chunk (skips leading comments).
        kw_offset = chunk.upper().find(action) if action else -1
        anchor = start + kw_offset if kw_offset >= 0 else start
        line = sql.count("\n", 0, anchor) + 1

        statements.append(
            Statement(
                raw=formatted,
                normalized=_normalize(formatted),
                line=line,
                index=index,
                action=action,
            )
        )
        index += 1
    return statements


# --- table-name extraction ---------------------------------------------------

_TABLE_PATTERNS = (
    re.compile(r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?([A-Z0-9_.\"]+)"),
    re.compile(r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([A-Z0-9_.\"]+)"),
    re.compile(r"\bTRUNCATE\s+(?:TABLE\s+)?([A-Z0-9_.\"]+)"),
    re.compile(r"\bON\s+([A-Z0-9_.\"]+)"),
    re.compile(r"\bINSERT\s+INTO\s+([A-Z0-9_.\"]+)"),
    re.compile(r"\bUPDATE\s+(?:ONLY\s+)?([A-Z0-9_.\"]+)"),
    re.compile(r"\bDELETE\s+FROM\s+([A-Z0-9_.\"]+)"),
)


def extract_table(normalized: str) -> str | None:
    """Return the primary table name a statement targets, if identifiable."""
    for pat in _TABLE_PATTERNS:
        m = pat.search(normalized)
        if m:
            return m.group(1).strip('"').lower()
    return None
