from fastapi.testclient import TestClient

from migration_guard.api import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_rules_endpoint_lists_rules():
    resp = client.get("/rules")
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()}
    assert "MG001" in ids


def test_analyze_flags_dangerous_sql():
    resp = client.post(
        "/analyze",
        json={"sql": "ALTER TABLE users ADD COLUMN a int NOT NULL;", "filename": "m.sql"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["gate_failed"] is True
    assert body["max_severity"] == "HIGH"
    assert body["findings"][0]["rule_id"] == "MG001"
    assert body["findings"][0]["filename"] == "m.sql"


def test_analyze_clean_sql_passes():
    resp = client.post("/analyze", json={"sql": "SELECT 1;"})
    body = resp.json()
    assert body["gate_failed"] is False
    assert body["max_severity"] is None
    assert body["findings"] == []


def test_analyze_respects_disabled_rules():
    resp = client.post(
        "/analyze",
        json={
            "sql": "CREATE INDEX i ON users (email);",
            "disabled_rules": ["MG002"],
        },
    )
    body = resp.json()
    assert body["findings"] == []


def test_analyze_large_table_escalation():
    payload = {"sql": "ALTER TABLE users DROP COLUMN old;", "large_tables": ["users"]}
    body = client.post("/analyze", json=payload).json()
    assert body["max_severity"] == "HIGH"  # MG003 escalated from MEDIUM


def test_analyze_rejects_invalid_severity():
    resp = client.post("/analyze", json={"sql": "SELECT 1;", "fail_on": "BOGUS"})
    assert resp.status_code == 422  # pydantic validation error


def test_analyze_defaults_to_postgres_and_flags_concurrently():
    resp = client.post("/analyze", json={"sql": "CREATE INDEX i ON users (email);"})
    body = resp.json()
    assert body["findings"][0]["rule_id"] == "MG002"


def test_analyze_respects_mysql_dialect():
    # MG002 is postgres-only; under mysql the same SQL is clean.
    resp = client.post(
        "/analyze",
        json={"sql": "CREATE INDEX i ON users (email);", "dialect": "mysql"},
    )
    body = resp.json()
    assert body["gate_failed"] is False
    assert body["findings"] == []


def test_analyze_rejects_invalid_dialect():
    resp = client.post("/analyze", json={"sql": "SELECT 1;", "dialect": "oracle"})
    assert resp.status_code == 422
