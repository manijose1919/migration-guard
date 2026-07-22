"""Automatic fixes (Feature 8).

A rule may offer a *safe, single-statement* rewrite. Only three qualify
(MG002/MG010/MG012 -> add CONCURRENTLY / drop FULL); the rest return None
because a correct fix is multi-statement or needs a human decision.
"""

from migration_guard.analyzer import Analyzer


def _fix(sql: str) -> tuple[str, int]:
    return Analyzer().apply_fixes(sql)


def test_create_index_gets_concurrently():
    fixed, count = _fix("CREATE INDEX idx ON users (email);")
    assert count == 1
    assert "CONCURRENTLY" in fixed
    assert fixed == "CREATE INDEX CONCURRENTLY idx ON users (email);"


def test_drop_index_gets_concurrently():
    fixed, count = _fix("DROP INDEX idx_users_email;")
    assert count == 1
    assert fixed == "DROP INDEX CONCURRENTLY idx_users_email;"


def test_vacuum_full_loses_full():
    fixed, count = _fix("VACUUM FULL users;")
    assert count == 1
    assert fixed == "VACUUM users;"


def test_non_fixable_statement_is_left_untouched():
    # Dropping a column has no safe single-statement rewrite.
    sql = "ALTER TABLE users DROP COLUMN old;"
    fixed, count = _fix(sql)
    assert count == 0
    assert fixed == sql


def test_only_the_flagged_statement_is_rewritten_formatting_preserved():
    sql = (
        "-- keep me\n"
        "CREATE INDEX idx ON users (email);\n"
        "SELECT 1;\n"
    )
    fixed, count = _fix(sql)
    assert count == 1
    assert "-- keep me" in fixed            # comment preserved
    assert "SELECT 1;" in fixed             # untouched statement preserved
    assert "CREATE INDEX CONCURRENTLY idx" in fixed


def test_suppressed_finding_is_not_fixed():
    sql = "CREATE INDEX idx ON users (email);  -- migrationguard:disable-line MG002"
    fixed, count = _fix(sql)
    assert count == 0
    assert "CONCURRENTLY" not in fixed


def test_finding_carries_its_fix():
    result = Analyzer().analyze_sql("CREATE INDEX idx ON users (email);")
    mg002 = next(f for f in result.findings if f.rule_id == "MG002")
    assert mg002.fix == "CREATE INDEX CONCURRENTLY idx ON users (email);"


def test_non_fixable_finding_has_no_fix():
    result = Analyzer().analyze_sql("ALTER TABLE users DROP COLUMN old;")
    mg003 = next(f for f in result.findings if f.rule_id == "MG003")
    assert mg003.fix is None


def test_cli_fix_rewrites_file_in_place_and_clears_the_gate(tmp_path, capsys):
    from migration_guard.cli import main

    sql = tmp_path / "m.sql"
    sql.write_text("CREATE INDEX idx ON users (email);\n", encoding="utf-8")
    # Without --fix the gate fails; with --fix the file is rewritten and passes.
    assert main(["analyze", str(sql)]) == 1
    code = main(["analyze", str(sql), "--fix"])
    assert code == 0
    assert "CONCURRENTLY" in sql.read_text(encoding="utf-8")
    assert "Applied 1 automatic fix" in capsys.readouterr().err


def test_cli_fix_on_missing_file_returns_2(capsys):
    from migration_guard.cli import main

    assert main(["analyze", "does_not_exist.sql", "--fix"]) == 2
