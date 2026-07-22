"""AST-aware matching: keywords inside string literals must not fool the rules.

Rules match on ``Statement.normalized``. If the normalized form still contains
the *contents* of string literals, a keyword sitting inside a quoted string can
trigger a rule that should stay silent (false positive) or suppress a rule that
should fire (false negative). The parser masks string literals so every rule --
present and future -- sees only real SQL syntax.
"""

from migration_guard.analyzer import Analyzer
from migration_guard.parser import _mask_literals, parse_sql


def _ids(sql: str) -> set[str]:
    return {f.rule_id for f in Analyzer().analyze_sql(sql).findings}


def test_string_literal_contents_are_masked_in_normalized():
    stmts = parse_sql("UPDATE accounts SET note = 'reset WHERE stale' WHERE id = 1;")
    normalized = stmts[0].normalized
    # A keyword that exists only inside the quoted string must be gone...
    assert "STALE" not in normalized
    # ...while the real trailing WHERE clause survives.
    assert "WHERE ID = 1" in normalized


def test_false_negative_update_flagged_when_where_is_only_inside_a_string():
    # The only "WHERE" is inside the string literal, so this UPDATE really does
    # touch every row -- MG008 must still fire.
    assert "MG008" in _ids("UPDATE accounts SET note = 'clear WHERE done';")


def test_false_positive_insert_not_flagged_for_ddl_inside_a_string():
    # An INSERT that merely stores DDL text as data is not an ALTER at all;
    # MG001 (add NOT NULL column) must not fire on it.
    sql = "INSERT INTO audit (msg) VALUES ('ALTER TABLE users ADD COLUMN age int NOT NULL');"
    assert "MG001" not in _ids(sql)


def test_double_quoted_identifiers_are_preserved():
    # Quoted identifiers are String.Symbol, not String.Single -- masking them
    # would erase the table/column names the rules need. MG005 must still fire.
    assert "MG005" in _ids('ALTER TABLE "public"."users" ALTER COLUMN c TYPE bigint;')


def test_mask_literals_handles_empty_input():
    assert _mask_literals("") == ""
