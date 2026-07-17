# --- MigrationGuard API image ---
# Uses 3.12-slim for broad wheel availability; the code targets >=3.10.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy source and install the package itself.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-deps -e .

# Run as a non-root user (defense in depth).
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Default: serve the REST API. Override the command to use the CLI instead.
CMD ["uvicorn", "migration_guard.api:app", "--host", "0.0.0.0", "--port", "8000"]
