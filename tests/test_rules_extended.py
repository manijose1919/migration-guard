"""Tests for the extended rule set (MG008-MG012)."""

import pytest

from migration_guard.analyzer import Analyzer
from migration_guard.models import Severity


def _findings(sql: str):
    return Analyzer().analyze_sql(sql).findings


def _ids(sql: str) -> set[str]:
    return {f.rule_id for f in _findings(sql)}


# (rule_id, dangerous, safe)
CASES = [
    ("MG008", "UPDATE users SET active = true;", "UPDATE users SET active = true WHERE id = 1;"),
    ("MG008", "DELETE FROM users;", "DELETE FROM users WHERE id = 1;"),
    ("MG009", "TRUNCATE users;", "DELETE FROM users WHERE id = 1;"),
    ("MG010", "DROP INDEX idx_users_email;", "DROP INDEX CONCURRENTLY idx_users_email;"),
    (
        "MG011",
        "ALTER TABLE users ADD PRIMARY KEY (id);",
        "ALTER TABLE users ADD COLUMN id int;",
    ),
    ("MG012", "VACUUM FULL users;", "VACUUM users;"),
]


@pytest.mark.parametrize("rule_id, dangerous, safe", CASES)
def test_flags_dangerous(rule_id, dangerous, safe):
    assert rule_id in _ids(dangerous)


@pytest.mark.parametrize("rule_id, dangerous, safe", CASES)
def test_silent_on_safe(rule_id, dangerous, safe):
    assert rule_id not in _ids(safe)


def test_delete_without_where_is_critical():
    finding = next(f for f in _findings("DELETE FROM users;") if f.rule_id == "MG008")
    assert finding.severity is Severity.CRITICAL


def test_full_registry_ids_are_contiguous():
    from migration_guard.rules import default_rules

    ids = {r.id for r in default_rules()}
    # IDs are contiguous MG001..MGNNN with no gaps or duplicates.
    assert ids == {f"MG{n:03d}" for n in range(1, len(ids) + 1)}
