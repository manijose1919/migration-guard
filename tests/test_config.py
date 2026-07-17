from migration_guard.config import Config
from migration_guard.models import Severity


def test_defaults():
    cfg = Config()
    assert cfg.fail_on is Severity.HIGH
    assert cfg.large_tables == set()
    assert cfg.disabled_rules == set()


def test_is_large_is_case_insensitive():
    cfg = Config(large_tables={"Users", "ORDERS"})
    assert cfg.is_large("users")
    assert cfg.is_large("Orders")
    assert not cfg.is_large("widgets")
    assert not cfg.is_large(None)


def test_from_env_parses_csv_and_severity():
    env = {
        "MG_FAIL_ON": "medium",
        "MG_LARGE_TABLES": "users, orders ,,",
        "MG_DISABLED_RULES": "MG001,MG002",
    }
    cfg = Config.from_env(env)
    assert cfg.fail_on is Severity.MEDIUM
    assert cfg.large_tables == {"users", "orders"}
    assert cfg.disabled_rules == {"MG001", "MG002"}


def test_from_env_defaults_when_missing():
    cfg = Config.from_env({})
    assert cfg.fail_on is Severity.HIGH
    assert cfg.large_tables == set()
