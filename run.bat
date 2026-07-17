@echo off
REM ============================================================
REM  MigrationGuard - one-step launcher for Windows
REM ============================================================
REM  Usage:
REM    run.bat            -> set up venv + start the REST API
REM    run.bat analyze <path>  -> run the CLI analyzer on a file/dir
REM    run.bat test       -> install dev deps + run the test suite
REM ============================================================
setlocal

if not exist ".venv" (
    echo [MigrationGuard] Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

if "%1"=="test" (
    echo [MigrationGuard] Installing dev dependencies...
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements-dev.txt
    python -m pip install --quiet -e .
    echo [MigrationGuard] Running test suite...
    python -m pytest
    goto :eof
)

echo [MigrationGuard] Installing dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e .

if "%1"=="analyze" (
    echo [MigrationGuard] Running analyzer on: %2
    migration-guard analyze %2 %3 %4 %5
    goto :eof
)

echo [MigrationGuard] Starting REST API on http://localhost:8000  (docs at /docs)
uvicorn migration_guard.api:app --host 0.0.0.0 --port 8000

endlocal
