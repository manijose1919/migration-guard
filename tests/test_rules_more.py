"""Additional rules MG013-MG015 (Feature 9).

Each exercises a different dialect scope:
  - MG013 drop-table          : universal
  - MG014 cluster             : postgres-only
  - MG015 mysql-modify-column : mysql-only
"""

from migration_guard.analyzer import Analyzer
from migration_guard.config import Config
from migration_guard.models import Severity


def _ids(sql: str, **cfg) -> set[str]:
    return {f.rule_id for f in Analyzer(Config(**cfg)).analyze_sql(sql).findings}


# --- MG013 DROP TABLE (universal) -------------------------------------------

def test_drop_table_flagged_in_both_dialects():
    assert "MG013" in _ids("DROP TABLE users;")
    assert "MG013" in _ids("DROP TABLE users;", dialect="mysql")


def test_drop_table_if_exists_still_flagged():
    assert "MG013" in _ids("DROP TABLE IF EXISTS users;")


def test_drop_table_is_high_severity():
    finding = next(
        f for f in Analyzer().analyze_sql("DROP TABLE users;").findings
        if f.rule_id == "MG013"
    )
    assert finding.severity is Severity.HIGH


# --- MG014 CLUSTER (postgres-only) ------------------------------------------

def test_cluster_flagged_for_postgres_only():
    assert "MG014" in _ids("CLUSTER users USING idx_users_email;")
    assert "MG014" not in _ids("CLUSTER users USING idx_users_email;", dialect="mysql")


def test_cluster_not_triggered_by_a_column_named_cluster():
    # Action-based, so an identifier that merely contains the word is safe.
    assert "MG014" not in _ids("ALTER TABLE t ADD COLUMN cluster int;")


# --- MG015 MySQL MODIFY/CHANGE COLUMN (mysql-only) --------------------------

def test_mysql_modify_and_change_flagged_in_mysql():
    assert "MG015" in _ids("ALTER TABLE users MODIFY COLUMN age BIGINT;", dialect="mysql")
    assert "MG015" in _ids("ALTER TABLE users CHANGE old_col new_col BIGINT;", dialect="mysql")


def test_mysql_modify_not_flagged_in_postgres():
    # MODIFY is not Postgres syntax; the rule is mysql-only.
    assert "MG015" not in _ids("ALTER TABLE users MODIFY COLUMN age BIGINT;")


# --- registry ---------------------------------------------------------------

def test_registry_now_has_fifteen_rules():
    from migration_guard.rules import default_rules

    ids = {r.id for r in default_rules()}
    assert ids == {f"MG{n:03d}" for n in range(1, 16)}
