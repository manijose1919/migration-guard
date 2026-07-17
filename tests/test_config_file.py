from migration_guard.analyzer import Analyzer
from migration_guard.cli import main
from migration_guard.config import Config, discover_config, resolve_config
from migration_guard.models import Severity

TOML = """
fail_on = "CRITICAL"
large_tables = ["users", "orders"]
disabled_rules = ["MG010"]
"""


def _write(tmp_path, text=TOML):
    p = tmp_path / ".migrationguard.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_resolve_from_file(tmp_path):
    path = _write(tmp_path)
    cfg = resolve_config(config_path=path, env={})
    assert cfg.fail_on is Severity.CRITICAL
    assert cfg.large_tables == {"users", "orders"}
    assert cfg.disabled_rules == {"MG010"}


def test_env_overrides_file(tmp_path):
    path = _write(tmp_path)
    cfg = resolve_config(config_path=path, env={"MG_FAIL_ON": "LOW"})
    assert cfg.fail_on is Severity.LOW           # env beats file
    assert cfg.large_tables == {"users", "orders"}  # untouched key stays from file


def test_overrides_beat_everything(tmp_path):
    path = _write(tmp_path)
    cfg = resolve_config(
        config_path=path,
        env={"MG_FAIL_ON": "LOW"},
        overrides={"fail_on": Severity.MEDIUM},
    )
    assert cfg.fail_on is Severity.MEDIUM


def test_none_overrides_are_ignored(tmp_path):
    path = _write(tmp_path)
    cfg = resolve_config(config_path=path, env={}, overrides={"fail_on": None})
    assert cfg.fail_on is Severity.CRITICAL


def test_discover_walks_up(tmp_path):
    _write(tmp_path)
    nested = tmp_path / "db" / "migrations"
    nested.mkdir(parents=True)
    found = discover_config(nested)
    assert found is not None and found.name == ".migrationguard.toml"


def test_pyproject_style_table(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text(
        "[tool.migration_guard]\nfail_on = 'MEDIUM'\n", encoding="utf-8"
    )
    cfg = resolve_config(config_path=path, env={})
    assert cfg.fail_on is Severity.MEDIUM


def test_no_sources_gives_defaults():
    cfg = resolve_config(config_path=None, start=".", env={})
    assert isinstance(cfg, Config)
    assert cfg.fail_on is Severity.HIGH


def test_cli_uses_config_file(tmp_path):
    (tmp_path / ".migrationguard.toml").write_text(
        'disabled_rules = ["MG002"]\n', encoding="utf-8"
    )
    sql = tmp_path / "m.sql"
    sql.write_text("CREATE INDEX i ON users (email);", encoding="utf-8")
    # Point --config at the file; MG002 should be disabled -> gate passes.
    code = main(["analyze", str(sql), "--config", str(tmp_path / ".migrationguard.toml")])
    assert code == 0


def test_sanity_default_flags_index():
    # Without the config, the same SQL fails the gate.
    assert Analyzer().analyze_sql("CREATE INDEX i ON users (email);").gate_failed("HIGH")
