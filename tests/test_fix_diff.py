"""`--diff` preview for autofix (Feature 11).

A dry run of ``--fix``: print a unified diff of what would change, write nothing,
and exit 1 when any fix is pending (so CI can require issues be fixed first).
"""

import pytest

from migration_guard.cli import main


def _write(tmp_path, text):
    p = tmp_path / "m.sql"
    p.write_text(text, encoding="utf-8")
    return p


def test_diff_previews_fix_without_writing(tmp_path, capsys):
    sql = _write(tmp_path, "CREATE INDEX idx ON users (email);\n")
    code = main(["analyze", str(sql), "--diff"])
    out = capsys.readouterr().out
    # A change is pending -> exit 1.
    assert code == 1
    # Unified-diff markers and the actual rewrite are shown.
    assert "-CREATE INDEX idx ON users (email);" in out
    assert "+CREATE INDEX CONCURRENTLY idx ON users (email);" in out
    # ...but the file itself is untouched.
    assert sql.read_text(encoding="utf-8") == "CREATE INDEX idx ON users (email);\n"


def test_diff_clean_when_nothing_to_fix(tmp_path, capsys):
    sql = _write(tmp_path, "CREATE INDEX CONCURRENTLY idx ON users (email);\n")
    code = main(["analyze", str(sql), "--diff"])
    assert code == 0
    assert capsys.readouterr().out == ""


def test_diff_on_directory(tmp_path, capsys):
    (tmp_path / "a.sql").write_text("VACUUM FULL orders;\n", encoding="utf-8")
    (tmp_path / "b.sql").write_text("SELECT 1;\n", encoding="utf-8")
    code = main(["analyze", str(tmp_path), "--diff"])
    out = capsys.readouterr().out
    assert code == 1
    assert "-VACUUM FULL orders;" in out
    assert "+VACUUM orders;" in out


def test_diff_on_missing_file_returns_2(capsys):
    assert main(["analyze", "does_not_exist.sql", "--diff"]) == 2


def test_fix_and_diff_are_mutually_exclusive(tmp_path):
    sql = _write(tmp_path, "CREATE INDEX idx ON users (email);\n")
    with pytest.raises(SystemExit) as exc:
        main(["analyze", str(sql), "--fix", "--diff"])
    assert exc.value.code == 2
