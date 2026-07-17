from migration_guard.analyzer import Analyzer
from migration_guard.reporting import render, render_github


def _results(sql: str, filename="m.sql"):
    return [Analyzer().analyze_sql(sql, filename=filename)]


def test_github_format_emits_error_for_high():
    out = render(_results("CREATE INDEX i ON users (email);"), "github")
    assert out.startswith("::error ")
    assert "file=m.sql" in out
    assert "line=1" in out
    assert "title=MG002" in out


def test_github_format_uses_warning_for_medium():
    out = render(_results("ALTER TABLE users DROP COLUMN old;"), "github")  # MG003 MEDIUM
    assert "::warning " in out
    assert "::error " not in out


def test_github_format_uses_error_for_critical():
    out = render(_results("DELETE FROM users;"), "github")  # MG008 CRITICAL
    assert "::error " in out


def test_github_escapes_newlines_and_specials():
    # Craft a filename with a comma/colon to ensure property escaping.
    out = render_github(_results("CREATE INDEX i ON users (email);", filename="a,b:c.sql"))
    assert "\n" not in out.split("::", 1)[1] or out.count("\n") == 0
    assert "%2C" in out or "%3A" in out  # comma or colon encoded in the file prop


def test_github_clean_input_is_empty():
    assert render(_results("SELECT 1;"), "github") == ""
