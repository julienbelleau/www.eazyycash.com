# CLAUDE.md — Janus codebase conventions

This file briefs future Claude Code sessions on the codebase. Read it before
making changes.

## Project at a glance
- **Janus** is a multi-strategy crypto trading system. Solo dev. Python 3.11+.
- Stack: TimescaleDB, Redis, ccxt[pro], SQLAlchemy 2 async, Pydantic v2, loguru.
- We are currently in **Phase 0 (data infrastructure)**. No strategy code yet.
- Reference docs: `JANUS_TRADING_SYSTEM_PLAN.md` (canonical plan) and
  `UPGRADES.md` (phase-by-phase upgrades to "top-tier" quality).

## Non-negotiable invariants

These hold in **every** PR. CI enforces them:

1. **Point-in-time correctness.** No code path returns a bar with `ts > as_of`.
   The only way to fetch OHLCV is via `OhlcvRepository.fetch()`; never raw SQL
   from a strategy. `tests/unit/test_point_in_time.py` pins this.
2. **Idempotent ingestion.** Every loader uses `BaseLoader.write_batch()` which
   does content-hash dedup + `ON CONFLICT DO NOTHING`. Don't bypass it.
3. **Type-strict.** `mypy --strict` must pass on `janus/` with zero new ignores.
4. **Tests deterministic.** `tests/conftest.py::_fix_seeds` is autouse; if you
   need randomness, draw from a seeded generator.
5. **Errors typed.** Raise `TransientError` (retried) or `PermanentError` (escalated),
   not bare `Exception`.

## Layout cheatsheet

- `janus/data/loaders/` — one module per upstream source. Subclass `BaseLoader`.
- `janus/data/quality/` — pure functions over row dicts; no I/O.
- `janus/data/repositories/` — the only public read interface to the DB.
- `janus/data/live/` — websocket consumers + outbox publishers (Phase 0 = parsers only).
- `alembic/versions/` — never edit a migration after merge; add a new one.

## Workflow rules

- **Branches.** `feature/<phase>-<slug>`; squash-merge into `main`.
- **Migrations.** `make migrate MSG="…"`. Always include a `downgrade()`.
- **Adding a loader.** New file in `janus/data/loaders/`, subclass `BaseLoader`,
  set `source` and `dataset`, implement `fetch()` and `parse()`. Tests in
  `tests/unit/test_<source>_parsers.py`.
- **Adding a strategy** (Phase 1+). New folder under `janus/strategies/<name>/`
  with `strategy.py`, `signals.py`, `tests/`, and `RATIONALE.md` (the doc that
  states the inefficiency, why it exists, and when it'll disappear).

## Skills you'll likely use

- `/security-review` before any commit that touches `loaders`, `execution`, or
  anything reading credentials.
- `/review` to self-review before opening a PR.
- `/simplify` after writing a feature, to verify there's no duplicated logic
  and abstractions are warranted.

## Anti-patterns to refuse

- Bypassing `OhlcvRepository` to read OHLCV from a strategy.
- Hard-coding thresholds without quoting the data that motivates them.
- Adding a feature flag for a behavior that should just be the default.
- Running `pytest -x` and skipping the full suite "because it's slow".
- Committing `.env`, real API keys, or production DSNs.

## Build & run

```bash
make install     # poetry install + pre-commit
make up          # docker-compose up -d
make db-init     # extension + alembic upgrade head
make test        # pytest tests/unit
make ci          # lint + typecheck + test (matches CI)
```

## Where to look when…

- "Why did the backfill stall?" → `ingest_jobs` table; status='running' rows older than X.
- "Why is a feature value off?" → check `feature_version` on the source row;
  cross-reference `narrative_tag_snapshots` if narrative-related.
- "Why did the websocket reconnect?" → log lines bound `exchange` + `symbol`
  with reason `WebSocketDisconnected` or `idle`.
