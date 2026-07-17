"""Each rule must flag its dangerous form and stay silent on the safe form."""

import pytest

from migration_guard.analyzer import Analyzer
from migration_guard.config import Config
from migration_guard.models import Severity

# (rule_id, dangerous_sql, safe_sql)
CASES = [
    (
        "MG001",
        "ALTER TABLE users ADD COLUMN age int NOT NULL;",
        "ALTER TABLE users ADD COLUMN age int DEFAULT 0;",
    ),
    (
        "MG002",
        "CREATE INDEX idx ON users (email);",
        "CREATE INDEX CONCURRENTLY idx ON users (email);",
    ),
    (
        "MG003",
        "ALTER TABLE users DROP COLUMN old;",
        "ALTER TABLE users ADD COLUMN new int;",
    ),
    (
        "MG004",
        "ALTER TABLE users RENAME COLUMN a TO b;",
        "ALTER TABLE users ADD COLUMN b int;",
    ),
    (
        "MG005",
        "ALTER TABLE users ALTER COLUMN id TYPE bigint;",
        "ALTER TABLE users ADD COLUMN id2 bigint;",
    ),
    (
        "MG006",
        "ALTER TABLE users ALTER COLUMN email SET NOT NULL;",
        "ALTER TABLE users ADD COLUMN email text;",
    ),
    (
        "MG007",
        "ALTER TABLE users ADD CONSTRAINT fk FOREIGN KEY (o) REFERENCES orgs (id);",
        "ALTER TABLE users ADD CONSTRAINT fk FOREIGN KEY (o) REFERENCES orgs (id) NOT VALID;",
    ),
]


def _rule_ids(sql: str) -> set[str]:
    result = Analyzer().analyze_sql(sql)
    return {f.rule_id for f in result.findings}


@pytest.mark.parametrize("rule_id, dangerous, safe", CASES)
def test_rule_flags_dangerous(rule_id, dangerous, safe):
    assert rule_id in _rule_ids(dangerous)


@pytest.mark.parametrize("rule_id, dangerous, safe", CASES)
def test_rule_silent_on_safe(rule_id, dangerous, safe):
    assert rule_id not in _rule_ids(safe)


def test_large_table_escalates_severity():
    sql = "ALTER TABLE users DROP COLUMN old;"  # MG003 is MEDIUM by default
    normal = Analyzer(Config()).analyze_sql(sql).findings[0]
    escalated = Analyzer(Config(large_tables={"users"})).analyze_sql(sql).findings[0]
    assert normal.severity is Severity.MEDIUM
    assert escalated.severity is Severity.HIGH


def test_disabled_rule_is_skipped():
    sql = "CREATE INDEX idx ON users (email);"
    # Enabled by default...
    assert "MG002" in _rule_ids(sql)
    # ...and skipped when disabled via config.
    disabled = Analyzer(Config(disabled_rules={"MG002"})).analyze_sql(sql)
    assert "MG002" not in {f.rule_id for f in disabled.findings}
