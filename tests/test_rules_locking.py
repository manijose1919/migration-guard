"""Locking rules MG016-MG017 (Feature 10).

  - MG016 reindex    : postgres-only, fixable for INDEX/TABLE forms
  - MG017 lock-table : universal, no autofix
"""

from migration_guard.analyzer import Analyzer
from migration_guard.config import Config
from migration_guard.models import Severity
from migration_guard.rules import default_rules


def _ids(sql: str, **cfg) -> set[str]:
    return {f.rule_id for f in Analyzer(Config(**cfg)).analyze_sql(sql).findings}


# --- MG016 REINDEX (postgres-only, fixable) ---------------------------------

def test_reindex_flagged_for_postgres_only():
    assert "MG016" in _ids("REINDEX TABLE users;")
    assert "MG016" not in _ids("REINDEX TABLE users;", dialect="mysql")


def test_reindex_concurrently_is_clean():
    assert "MG016" not in _ids("REINDEX TABLE CONCURRENTLY users;")


def test_reindex_table_autofix_adds_concurrently():
    fixed, count = Analyzer().apply_fixes("REINDEX TABLE users;")
    assert count == 1
    assert fixed == "REINDEX TABLE CONCURRENTLY users;"


def test_reindex_index_autofix_adds_concurrently():
    fixed, count = Analyzer().apply_fixes("REINDEX INDEX idx_users_email;")
    assert count == 1
    assert fixed == "REINDEX INDEX CONCURRENTLY idx_users_email;"


def test_reindex_database_is_flagged_but_not_autofixed():
    # The DATABASE form is still risky, but our safe rewrite only covers the
    # INDEX/TABLE forms, so it flags without offering a fix.
    assert "MG016" in _ids("REINDEX DATABASE mydb;")
    _, count = Analyzer().apply_fixes("REINDEX DATABASE mydb;")
    assert count == 0


# --- MG017 LOCK TABLE (universal) -------------------------------------------

def test_lock_table_flagged_in_both_dialects():
    assert "MG017" in _ids("LOCK TABLE users IN ACCESS EXCLUSIVE MODE;")
    assert "MG017" in _ids("LOCK TABLES users WRITE;", dialect="mysql")


def test_lock_table_is_medium_severity():
    finding = next(
        f for f in Analyzer().analyze_sql("LOCK TABLE users;").findings
        if f.rule_id == "MG017"
    )
    assert finding.severity is Severity.MEDIUM


# --- registry ---------------------------------------------------------------

def test_registry_now_has_seventeen_rules():
    ids = {r.id for r in default_rules()}
    assert ids == {f"MG{n:03d}" for n in range(1, 18)}
