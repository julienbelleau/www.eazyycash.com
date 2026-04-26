# Janus — multi-strategy crypto trading system

Janus runs three structurally decorrelated alpha strategies behind a regime-aware
meta-layer, with institutional risk controls and end-to-end reproducibility.
This repository ships **Phase 0 (data infrastructure)** — the foundation that
every later phase depends on.

> Read [`JANUS_TRADING_SYSTEM_PLAN.md`](./JANUS_TRADING_SYSTEM_PLAN.md) for the
> end-to-end project plan, and [`UPGRADES.md`](./UPGRADES.md) for the phase-by-phase
> upgrades that take us from "institutional" to "top-tier quant pod" quality.

---

## What's in Phase 0

| Component | Module | Status |
|-----------|--------|--------|
| Typed runtime config (Pydantic v2) | `janus/config/settings.py` | ✅ |
| Structured logging (loguru, JSON in prod) | `janus/monitoring/logging_config.py` | ✅ |
| Error taxonomy (transient vs permanent) | `janus/errors.py` | ✅ |
| NTP/clock-drift gate (refuses to start on drift) | `janus/time_sync.py` | ✅ |
| TimescaleDB schema (10 tables, 8 hypertables) | `janus/data/schema/models.py` | ✅ |
| Continuous aggregates 5m/15m/1h/4h/1d | `alembic/versions/0001_initial_schema.py` | ✅ |
| Compression + retention policies | (same migration) | ✅ |
| Loader scaffolding (rate limit, retry, dedup, audit) | `janus/data/loaders/base.py` | ✅ |
| Binance loaders (klines, funding, OI, agg-trades) | `janus/data/loaders/binance.py` | ✅ |
| Stub loaders (Coinglass, Glassnode, DefiLlama) | `janus/data/loaders/{coinglass,glassnode,defillama}.py` | 🚧 stub |
| Data quality (sanity, gap detector, cross-source) | `janus/data/quality/` | ✅ |
| OHLCV repository (point-in-time enforced) | `janus/data/repositories/ohlcv_repo.py` | ✅ |
| WebSocket supervisor (CCXT pro) | `janus/data/live/websocket_manager.py` | ✅ |
| Liquidation stream parser | `janus/data/live/liquidation_stream.py` | 🚧 parser only |
| Resumable backfill driver | `scripts/backfill_historical.py` | ✅ |
| DB bootstrap | `scripts/init_db.py` | ✅ |

## What's in Phase 1 (Refractory Period — partial)

| Component | Module | Status |
|-----------|--------|--------|
| Strategy primitives (Signal, Order, Position, MarketState, ABC) | `janus/strategies/base.py` | ✅ |
| P² online quantile estimator (UPGRADES §1.1) | `janus/features/adaptive_thresholds.py` | ✅ |
| BOCPD with Normal-Gamma prior (UPGRADES §1.4) | `janus/features/bocpd.py` | ✅ |
| Refractory features (liq velocity, OFI, CVD, OI, funding z) | `janus/features/refractory_features.py` | ✅ |
| Cascade detector (adaptive thresholds + multi-asset contagion §1.3) | `janus/strategies/refractory/signals.py` | ✅ |
| Exhaustion detector (BOCPD + OFI reversion + price stability §1.2) | `janus/strategies/refractory/signals.py` | ✅ |
| Refractory state machine (IDLE → IN_CASCADE → IN_TRADE → COOLDOWN) | `janus/strategies/refractory/strategy.py` | ✅ |
| Per-strategy YAML config (cascade thresholds, exits, gating) | `config/strategies/refractory.yaml` | ✅ |
| Strategy rationale (5 questions) | `janus/strategies/refractory/RATIONALE.md` | ✅ |
| Risk: fractional-Kelly position sizing + vol overlay (UPGRADES §R.1) | `janus/risk/position_sizing.py` | ✅ |
| Backtest engine (event-driven, walk-forward) | — | ⏳ next |
| Slippage model from L2 snapshots (UPGRADES §1.6) | — | ⏳ next |
| Conformal-prediction TP intervals (UPGRADES §1.5) | — | ⏳ next |
| 60-day paper trading harness | — | ⏳ Phase 1 gate |

---

## Quickstart

Prereqs: Docker, Python 3.11+, [Poetry](https://python-poetry.org).

```bash
# 1. install deps + pre-commit hooks
make install

# 2. configure
cp .env.example .env && $EDITOR .env

# 3. start TimescaleDB + Redis
make up

# 4. create the schema
make db-init

# 5. run the unit suite
make test

# 6. backfill 3 years of BTC + ETH klines (this can take ~30 min)
poetry run python scripts/backfill_historical.py \
    --symbols BTCUSDT ETHUSDT \
    --start 2023-01-01 \
    --datasets klines funding open_interest
```

A psql shell is one make target away (`make db-shell`).

---

## Repository layout

```
janus/
├── alembic/                       # versioned schema migrations
├── config/                        # YAML configs (strategies, narratives)
├── janus/                         # python package
│   ├── config/                    # Pydantic settings
│   ├── data/
│   │   ├── loaders/               # source-specific data ingestion
│   │   ├── live/                  # websocket consumers
│   │   ├── quality/               # OHLC sanity, gaps, cross-source check
│   │   ├── repositories/          # the *only* read API for time-series
│   │   └── schema/                # SQLAlchemy table objects
│   ├── monitoring/                # logging (Phase 0); metrics+alerts later
│   ├── errors.py                  # transient/permanent error taxonomy
│   └── time_sync.py               # clock drift guard
├── scripts/                       # operational entry points
└── tests/
    ├── unit/                      # 100% deterministic, no DB
    └── integration/               # require docker compose up
```

---

## Engineering invariants

These are non-negotiable. Pull requests that break any of them fail CI.

1. **Point-in-time correctness.** No code path may return a row with `ts > as_of`.
   Enforced by `OhlcvRepository.fetch()`; covered by `tests/unit/test_point_in_time.py`.
2. **Idempotent ingestion.** Re-running a backfill must never produce duplicates.
   Enforced by content-hash dedup in `BaseLoader` + `ON CONFLICT DO NOTHING`.
3. **Type-strict.** `mypy --strict` must pass on `janus/` with zero ignores.
4. **No look-ahead in features.** Every feature is computed via the repository's
   `as_of` argument; never by reading the DB directly.
5. **Determinism in tests.** `pytest-randomly` seed is logged on every run; the
   `_fix_seeds` fixture resets `random` and `numpy.random` before each test.
6. **Secret hygiene.** `detect-secrets` runs in pre-commit. `.env` is git-ignored.

---

## Phase gates (recap)

| Phase | Gate to advance | Kill criterion |
|-------|-----------------|----------------|
| 0 — Data infra (this) | 3-yr backtest <5 min, live stable 7 days, all unit tests green | n/a — foundation |
| 1 — Refractory | Sharpe OOS > 1.5, paper Sharpe > 0.75 over 60 days | Sharpe OOS < 1.0 |
| 2 — Narrative | Sharpe OOS > 1.2, paper Sharpe > 0.6 | Sharpe OOS < 0.8 |
| 3 — Stablecoin | Edge net > 0.3% / trade | Edge net < 0.2% |
| 4 — Regime | Sharpe improvement > 0.2 vs always-on | Improvement < 0.1 |
| Live small | P&L within ±30% of paper for 30 days | Drawdown > 20% |
| Live full | Sharpe stable over 90 days at full size | Drawdown > 25% |

---

## Contributing (solo dev rules)

- Branch off `main`, develop on `feature/<phase>-<slug>`. Squash-merge.
- Every PR: passes `make ci`, has tests, updates `RATIONALE.md` of the strategy if behavior changes.
- Use `make migrate MSG="…"` to generate Alembic migrations; never edit existing migrations after merge.
- Production deployment uses a separate compose file; this repo's `docker-compose.yml` is dev-only.
