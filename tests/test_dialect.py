"""Dialect awareness (Feature 7).

Some rules describe Postgres-only mechanisms (CONCURRENTLY, NOT VALID, VACUUM
FULL). Under ``--dialect mysql`` those must not fire — their advice would be
wrong — while the universal data-loss / breaking-change rules still run.
"""

import pytest

from migration_guard.analyzer import Analyzer
from migration_guard.config import Config, resolve_config


def _ids(sql: str, **cfg) -> set[str]:
    return {f.rule_id for f in Analyzer(Config(**cfg)).analyze_sql(sql).findings}


def test_postgres_is_the_default_dialect():
    assert Config().dialect == "postgres"


def test_invalid_dialect_is_rejected():
    with pytest.raises(ValueError):
        Config(dialect="oracle")


def test_dialect_is_normalized_to_lowercase():
    assert Config(dialect="MySQL").dialect == "mysql"


def test_postgres_only_rule_runs_for_postgres_but_not_mysql():
    # MG002 recommends CREATE INDEX CONCURRENTLY, which does not exist in MySQL.
    assert "MG002" in _ids("CREATE INDEX idx ON users (email);")
    assert "MG002" not in _ids("CREATE INDEX idx ON users (email);", dialect="mysql")


def test_vacuum_full_is_postgres_only():
    # VACUUM FULL is not valid MySQL syntax at all.
    assert "MG012" in _ids("VACUUM FULL users;")
    assert "MG012" not in _ids("VACUUM FULL users;", dialect="mysql")


def test_universal_rules_still_run_for_mysql():
    # Data-loss and breaking-change dangers apply to every dialect.
    assert "MG008" in _ids("DELETE FROM users;", dialect="mysql")
    assert "MG003" in _ids("ALTER TABLE users DROP COLUMN old;", dialect="mysql")


def test_dialect_from_env():
    cfg = Config.from_env({"MG_DIALECT": "mysql"})
    assert cfg.dialect == "mysql"


def test_dialect_resolves_from_config_file(tmp_path):
    path = tmp_path / ".migrationguard.toml"
    path.write_text('dialect = "mysql"\n', encoding="utf-8")
    assert resolve_config(config_path=path, env={}).dialect == "mysql"


def test_dialect_env_overrides_file(tmp_path):
    path = tmp_path / ".migrationguard.toml"
    path.write_text('dialect = "postgres"\n', encoding="utf-8")
    cfg = resolve_config(config_path=path, env={"MG_DIALECT": "mysql"})
    assert cfg.dialect == "mysql"  # env layer beats the committed file


def test_cli_dialect_flag_skips_postgres_only_rule(tmp_path):
    from migration_guard.cli import main

    sql = tmp_path / "m.sql"
    sql.write_text("CREATE INDEX i ON users (email);", encoding="utf-8")
    # Postgres (default) flags MG002 and fails the gate; MySQL has no such rule.
    assert main(["analyze", str(sql)]) == 1
    assert main(["analyze", str(sql), "--dialect", "mysql"]) == 0
