# Janus SaaS architecture & Railway deployment

This document explains how Janus is exposed as a SaaS — what runs where,
how authentication works, and how to deploy on Railway end-to-end.

> Quick links: [`Dockerfile`](./Dockerfile) · [`railway.toml`](./railway.toml) ·
> [`deploy/railway/`](./deploy/railway) · [`scripts/admin_keys.py`](./scripts/admin_keys.py)

---

## Service topology

```
                ┌────────────────────────────────────────────────────┐
                │ Railway Project: janus                              │
                │                                                     │
   client  →   ┌──────────┐         ┌──────────┐         ┌──────────┐│
  (curl,       │ janus-   │         │ janus-   │         │ janus-   ││
   browser,    │ api      │  ───→   │ migrate  │   ───→  │ ingest   ││
   bot)        │ (HTTP)   │         │ (one-off)│         │ (worker) ││
                └────┬─────┘         └────┬─────┘         └────┬─────┘│
                     │                     │                    │      │
                     ▼                     ▼                    ▼      │
                ┌─────────────────┐    ┌──────────┐    ┌──────────────┐│
                │ TimescaleDB     │ ←─ │ Postgres │    │ janus-paper  ││
                │ (custom image)  │    │ on disk  │    │ (worker)     ││
                └─────────────────┘    └──────────┘    └──────────────┘│
                ┌──────────┐                                           │
                │ Redis    │                                           │
                │ (cache + │                                           │
                │ outbox)  │                                           │
                └──────────┘                                           │
                └────────────────────────────────────────────────────┘
```

| Service        | Image                              | Role |
|----------------|------------------------------------|------|
| `janus-api`    | Janus `Dockerfile`, default CMD    | Public HTTP API. Auth, control plane, read-only views. |
| `janus-migrate`| Janus `Dockerfile`, `alembic upgrade head` | One-shot DB migration on every redeploy. |
| `janus-ingest` | Janus `Dockerfile`, `python scripts/run_ingest.py` | Long-running websocket consumer. |
| `janus-paper`  | Janus `Dockerfile`, `python scripts/run_paper.py` | One per (strategy, symbol-set). |
| `timescaledb`  | `deploy/railway/timescaledb.Dockerfile` | TimescaleDB-enabled Postgres. |
| `redis`        | Railway Redis template             | Cache + transactional outbox sink. |

All workers share the same image — only the start command differs.

---

## Authentication & multi-tenancy

- Every request to `/v1/*` requires `Authorization: Bearer jns_<short>_<secret>`.
- Plaintext keys are shown **once** at issuance. Only an HMAC-SHA256(pepper, short.secret) is stored.
- `JANUS_API_API_KEY_PEPPER` is a single application-wide secret. Rotating it invalidates every key — by design.
- Keys carry scopes: `read`, `write`, `admin`. `admin` implies all.
- Tenants are first-class but the database schema is single-tenant by default; row-level multi-tenancy lands when the SaaS goes multi-customer.

### Bootstrap a tenant + admin key

```bash
# After migrate has run:
poetry run python scripts/admin_keys.py create-tenant --name acme --plan pro
# tenant_id=01F... name=acme plan=pro

poetry run python scripts/admin_keys.py issue-key --tenant 01F... --label primary --scopes admin
# Save this key — it will not be shown again:
# jns_aBcD1234_<long-secret>
```

---

## Endpoints (v1)

| Method | Path                                  | Scope    | Description |
|--------|---------------------------------------|----------|-------------|
| GET    | `/healthz`                            | public   | Liveness probe |
| GET    | `/readyz`                             | public   | Readiness probe (DB reachable) |
| GET    | `/v1/portfolio/summary`               | read     | Realised P&L, open positions, last update |
| GET    | `/v1/portfolio/attribution`           | read     | Per-strategy P&L attribution today |
| GET    | `/v1/strategies`                      | read     | Strategies + paused state |
| POST   | `/v1/strategies/{id}/pause`           | write    | Trip the strategy kill switch |
| POST   | `/v1/strategies/{id}/resume`          | write    | Reset the kill switch |
| GET    | `/v1/journal/{strategy_id}/{date}`    | read     | Trade fills for a day |
| GET    | `/v1/regime`                          | read     | Current regime + gating weights |
| POST   | `/v1/admin/tenants`                   | admin    | Create a tenant |
| GET    | `/v1/admin/tenants`                   | admin    | List tenants |
| POST   | `/v1/admin/api-keys`                  | admin    | Issue a new key (returns plaintext once) |
| DELETE | `/v1/admin/api-keys/{short_id}`       | admin    | Revoke a key |

Auto-generated OpenAPI: `/openapi.json` · Swagger UI: `/docs` · Redoc: `/redoc`.

---

## Deploying to Railway

### Step 1 — Database

Create a service from `deploy/railway/timescaledb.Dockerfile`. Add a persistent
volume mounted at `/var/lib/postgresql/data`. Note the auto-injected
`DATABASE_URL`.

### Step 2 — Redis

Add the Railway Redis template — `REDIS_URL` is auto-injected.

### Step 3 — App services

For each role create a Railway service connected to the same repo, with:

| Service        | Start command (`Settings → Deploy`)                                              |
|----------------|----------------------------------------------------------------------------------|
| `janus-migrate`| `alembic upgrade head`                                                           |
| `janus-api`    | `uvicorn janus.api.main:app --host 0.0.0.0 --port $PORT` (Health = `/readyz`)    |
| `janus-ingest` | `python scripts/run_ingest.py`                                                   |
| `janus-paper`  | `python scripts/run_paper.py --strategies refractory --symbols BTCUSDT`          |

Link each service to the Postgres + Redis services so `DATABASE_URL` / `REDIS_URL`
are injected. Set per-service env vars from the table below.

### Step 4 — Environment variables (Project shared)

| Variable                            | Required | Notes |
|-------------------------------------|----------|-------|
| `JANUS_ENV`                         | yes      | `paper` for staging, `live` for prod |
| `JANUS_LOG_JSON`                    | yes      | `true` in prod |
| `JANUS_RANDOM_SEED`                 | yes      | reproducibility |
| `JANUS_API_API_KEY_PEPPER`          | api      | 32+ random chars; rotating invalidates all keys |
| `JANUS_API_CORS_ALLOW_ORIGINS`      | api      | comma-separated; tighten for prod |
| `JANUS_API_RATE_LIMIT_PER_MINUTE`   | api      | default 120 |
| `BINANCE_API_KEY` / `..._SECRET`    | live     | only in `JANUS_ENV=live` |
| `SENTRY_DSN`                        | optional | error tracking |
| `TELEGRAM_BOT_TOKEN` / `..._CHAT_ID`| optional | daily report + alerts |

`DATABASE_URL` and `REDIS_URL` come from Railway service links — do not set them manually.

### Step 5 — Bootstrap

After the first successful deploy of `janus-migrate`, run the admin CLI from a Railway
"Shell" against the API service (or any service with the same image):

```bash
python scripts/admin_keys.py create-tenant --name yourname --plan pro
python scripts/admin_keys.py issue-key --tenant <id> --label primary --scopes admin
```

Save the resulting `jns_...` key in your password manager.

---

## Local dev

Bring everything up with the existing dev compose:

```bash
make up
make db-init
poetry run python scripts/admin_keys.py create-tenant --name dev --plan free
poetry run python scripts/admin_keys.py issue-key --tenant <id> --label local --scopes admin

# Boot the API
poetry run uvicorn janus.api.main:app --reload

# Test
curl -H "Authorization: Bearer $JANUS_KEY" http://localhost:8000/v1/strategies
```

---

## Security model

- Keys are HMAC-hashed; database compromise doesn't leak active credentials.
- Pepper rotation is a one-line change (`JANUS_API_API_KEY_PEPPER`) that nukes all sessions.
- All requests carry a `x-request-id` header (logged server-side) — every action is auditable.
- `detect-secrets` runs in pre-commit. `.env*` is git-ignored (the example template is the only exception).
- The API container runs as non-root (`uid=10001`).
- `tini` is PID 1 — zombies get reaped, signals propagate cleanly.

## What's deferred (post-Phase-1 of SaaS-ification)

- **Engine state snapshot to Redis** so the API serves live P&L + positions
  rather than the trade journal (5-minute staleness today).
- **Per-tenant data isolation** at the row level (RLS or explicit
  `WHERE tenant_id = $current`) — currently single-tenant.
- **Stripe billing** for plan tier enforcement.
- **A web UI** (Next.js) consuming this API. The OpenAPI schema is the contract.
- **Per-tenant Binance keys** (currently global per `JANUS_ENV=live`).
