# Janus production image.
# Multi-stage: build deps in a heavyweight stage, copy site-packages into a slim runtime.
# Same image runs every Janus role — the entrypoint is overridden per Railway service.

# ────────── stage 1: builder ──────────
FROM python:3.11-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="/opt/poetry/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc curl libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /build
COPY pyproject.toml poetry.lock* ./
# Install runtime deps only (skip dev) into the system site-packages.
RUN poetry install --no-root --only main --no-interaction --no-ansi


# ────────── stage 2: runtime ──────────
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    JANUS_LOG_JSON=true

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system janus --gid 10001 \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin janus

# Bring in the installed deps.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /usr/local/bin/alembic /usr/local/bin/alembic

WORKDIR /app

# App code last — maximises Docker layer caching during deps-stable iterations.
COPY --chown=janus:janus alembic.ini ./
COPY --chown=janus:janus alembic ./alembic
COPY --chown=janus:janus janus ./janus
COPY --chown=janus:janus scripts ./scripts
COPY --chown=janus:janus config ./config

USER janus

# Default port — overridden by Railway via $PORT.
ENV PORT=8000
EXPOSE 8000

# Tini reaps zombies for any subprocess (e.g. uvicorn worker children).
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default = API service. Override via Railway service `Start command`:
#   API:        uvicorn janus.api.main:app --host 0.0.0.0 --port $PORT
#   migrate:    alembic upgrade head
#   ingest:     python scripts/run_ingest.py
#   paper:      python scripts/run_paper.py --strategies refractory --symbols BTCUSDT
#   report:     python scripts/daily_report.py --telegram
CMD ["sh", "-c", "uvicorn janus.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# Healthcheck — Railway has its own probes via railway.toml, but this
# helps `docker run` users.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:${PORT:-8000}/healthz || exit 1
