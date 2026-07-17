from migration_guard.analyzer import Analyzer
from migration_guard.suppressions import parse_directives


def _ids(sql: str) -> set[str]:
    return {f.rule_id for f in Analyzer().analyze_sql(sql).findings}


def test_disable_line_suppresses_same_line():
    sql = "CREATE INDEX i ON users (email);  -- migrationguard:disable-line MG002"
    assert "MG002" not in _ids(sql)


def test_disable_next_line_suppresses_following_statement():
    sql = (
        "-- migrationguard:disable-next-line MG002\n"
        "CREATE INDEX i ON users (email);"
    )
    assert "MG002" not in _ids(sql)


def test_disable_file_suppresses_everywhere():
    sql = (
        "-- migrationguard:disable-file MG002\n"
        "CREATE INDEX a ON users (email);\n"
        "CREATE INDEX b ON orders (email);"
    )
    assert "MG002" not in _ids(sql)


def test_specific_id_does_not_suppress_other_rules():
    # disable MG002 only; the DROP COLUMN (MG003) on another line must survive.
    sql = (
        "CREATE INDEX i ON users (email);  -- migrationguard:disable-line MG002\n"
        "ALTER TABLE users DROP COLUMN old;"
    )
    ids = _ids(sql)
    assert "MG002" not in ids
    assert "MG003" in ids


def test_bare_directive_suppresses_all_on_line():
    sql = "CREATE INDEX i ON users (email);  -- migrationguard:disable-line"
    assert _ids(sql) == set()


def test_next_line_with_specific_id_does_not_over_suppress():
    # Regression: a specific-id disable-next-line must not suppress other rules.
    sql = (
        "-- migrationguard:disable-next-line MG001\n"
        "CREATE INDEX i ON users (email);"  # this is MG002, must still fire
    )
    assert "MG002" in _ids(sql)


def test_parse_directives_units():
    sup = parse_directives(
        "-- migrationguard:disable-file MG009\n"
        "x -- migrationguard:disable-line MG001, MG002\n"
    )
    assert sup.is_suppressed("MG009", 999)         # file-level, any line
    assert sup.is_suppressed("MG001", 2)           # line-level
    assert sup.is_suppressed("MG002", 2)
    assert not sup.is_suppressed("MG003", 2)
