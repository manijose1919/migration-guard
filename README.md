# 🛡️ MigrationGuard

**Static safety analyzer for SQL database migrations.** Catch locking and breaking
schema changes *before* they hit production — no database connection required.

[![CI](https://github.com/manijose1919/migration-guard/actions/workflows/main.yml/badge.svg)](https://github.com/manijose1919/migration-guard/actions/workflows/main.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## The niche problem

Schema migrations are one of the most common causes of self-inflicted production
outages. Statements that look harmless routinely take an `ACCESS EXCLUSIVE` lock and
freeze a busy table:

| Migration you wrote | What actually happens in prod |
|---|---|
| `ALTER TABLE users ADD COLUMN age INT NOT NULL;` | Full table rewrite + exclusive lock |
| `CREATE INDEX idx ON orders (email);` | Writes blocked for the whole build |
| `ALTER TABLE users ALTER COLUMN id TYPE bigint;` | Table rewrite, long lock |
| `ALTER TABLE t ADD CONSTRAINT fk ... REFERENCES ...;` | Full validation scan under lock |

You usually discover this **at 2 a.m., in production.** MigrationGuard reads your
migration SQL statically, applies a registry of well-documented safety rules, and
tells you *before* you ship.

## What it does

- **Parses** raw SQL migration files (via `sqlparse`).
- **Analyzes** them against a registry of lock / breaking-change **rules**, each with
  an ID, severity, rationale, and a safer-alternative suggestion.
- **Reports** in `text`, `json`, or `sarif` (for GitHub code scanning).
- **Gates** CI: exits non-zero when a finding meets/exceeds your severity threshold.

Runs three ways from the same modular core: **CLI**, **REST API**, and **GitHub Action**.

---

## Quickstart (1 step)

### Windows

```bat
run.bat analyze examples\dangerous_migration.sql
```

That script creates a virtualenv, installs the package, and runs the analyzer.
`run.bat` alone starts the REST API; `run.bat test` runs the suite.

### Any OS (Docker)

```bash
docker compose up --build         # REST API at http://localhost:8000/docs
```

### Any OS (Python)

```bash
pip install -e .
migration-guard analyze examples/dangerous_migration.sql
```

Example output:

```
examples/dangerous_migration.sql
  HIGH    MG002  line 3  CREATE INDEX without CONCURRENTLY locks the table against writes.
                         -> Use CREATE INDEX CONCURRENTLY (outside a transaction).
  HIGH    MG001  line 1  Adding a NOT NULL column without a default rewrites the table.
                         -> Add the column nullable, backfill, then SET NOT NULL.

2 findings (2 HIGH). Gate = HIGH -> FAILED
```

---

## Integration guide (plug into enterprise systems)

MigrationGuard is intentionally modular — the analysis core has **no I/O and no
framework dependencies**, so it drops into any pipeline.

**1. As a library**

```python
from migration_guard.analyzer import Analyzer
from migration_guard.config import Config

result = Analyzer(Config(large_tables={"users", "orders"})).analyze_sql(sql_text)
if result.gate_failed("HIGH"):        # safe on clean input (never raises)
    raise RuntimeError(result.to_text())
```

**2. As a REST microservice** — `POST /analyze` with `{"sql": "...", "filename": "..."}`
returns structured JSON findings. Deploy the provided `Dockerfile` behind any gateway;
call it from a deploy pipeline, a bot, or a code-review service.

**3. As a GitHub Action** — drop this into any workflow; findings appear as inline
annotations on the PR diff and the build fails past your threshold:

```yaml
- uses: actions/checkout@v4
- uses: manijose1919/migration-guard@main
  with:
    paths: db/migrations
    fail-on: HIGH
    large-tables: users,orders   # optional: escalate locks on hot tables
```

The `--format github` output emits `::error`/`::warning` workflow commands, and a
**SARIF** format is available for the GitHub "Security" tab / code scanning.

**4. As a pre-commit / pre-deploy hook** — the CLI exit code is the contract: `0` = pass,
non-zero = a finding met the `--fail-on` threshold.

The rule registry is the extension point: implement one `Rule` class, register it, and
every surface (CLI/API/CI) picks it up automatically — no core changes.

---

## Target audience & client-acquisition strategy

**Who needs this**
- Platform / DevOps / SRE teams owning migration safety across many services.
- Backend teams on Postgres/MySQL without a heavyweight migration framework.
- Consultancies and agencies who inherit legacy databases and need a fast audit.

**Go-to-market / acquisition**
- **Open-core, free CLI** → land developers bottom-up; the CI gate is the daily habit.
- **SARIF + GitHub Action** → distribute via the GitHub Marketplace (huge discovery channel).
- **"Migration audit" lead magnet** → a free hosted `/analyze` endpoint that scores a
  pasted migration, capturing teams at the exact moment of pain.
- **Upsell surface** → hosted dashboards, org-wide policy config, DB-connected sizing,
  Slack/PR bots, and multi-dialect support become the commercial tier.

---

## Architecture

```
src/migration_guard/
  models.py      # Severity, Finding, AnalysisResult (pydantic)
  config.py      # env-driven policy (fail-on, large tables, disabled rules)
  parser.py      # SQL text -> normalized statements
  rules/         # one file per rule, auto-registered
  analyzer.py    # orchestrates parse + rules -> AnalysisResult
  reporting.py   # text / json / sarif renderers
  cli.py         # argparse entrypoint  (exit code = CI contract)
  api.py         # FastAPI app  (POST /analyze)
tests/           # pytest suite (rules, parser, analyzer, CLI, API)
```

## Development

```bash
pip install -r requirements-dev.txt
pytest            # run tests + coverage
ruff check .      # lint
```

## License

MIT — see [LICENSE](LICENSE).
