# Janus — multi-strategy crypto trading system

Janus runs three structurally decorrelated alpha strategies behind a regime-aware
meta-layer, with institutional risk controls and end-to-end reproducibility.

This repository ships **Phases 0 → 4 dev-complete** — every module to backtest
and paper-trade the full system. Live deployment requires the backfill, paper
period (60d/strategy), and gate metrics in the plan.

> Read [`JANUS_TRADING_SYSTEM_PLAN.md`](./JANUS_TRADING_SYSTEM_PLAN.md) for the
> end-to-end project plan, and [`UPGRADES.md`](./UPGRADES.md) for the phase-by-phase
> upgrades that take it from "institutional" to "top-tier quant pod" quality.
> Each strategy folder has a `RATIONALE.md` answering the five mandatory
> design-justification questions.

---

## Status by phase

| Phase | Scope | Module path(s) | Status |
|-------|-------|----------------|--------|
| 0 — Data infrastructure | TimescaleDB schema (10 tables, 8 hypertables, 5 CAGGs, compression + retention), loaders (Binance + 3 stubs), live ingestion (websocket supervisor + liq parser), data quality (sanity / gap / cross-source), point-in-time repository, NTP gate, structured logging, error taxonomy, idempotent ingestion | `janus/data/`, `janus/config/`, `janus/monitoring/logging_config.py`, `janus/time_sync.py`, `alembic/` | ✅ |
| 1 — Refractory Period | Strategy primitives, P² adaptive thresholds, BOCPD, OFI/CVD features, cascade + exhaustion signals, multi-asset contagion, fractional-Kelly + vol-overlay sizing, conformal-prediction TP, RATIONALE | `janus/strategies/refractory/`, `janus/features/{adaptive_thresholds,bocpd,refractory_features,conformal_tp}.py`, `janus/risk/position_sizing.py` | ✅ |
| Backtest infra | Event-driven engine, point-in-time data provider, metrics (Sharpe / Sortino / Calmar / DD / VaR / CVaR / etc.), L2 + sqrt-impact slippage models, walk-forward (Optuna multivariate-TPE), stress tests (bootstrap / sensitivity / removed-extremes / GBM), paper simulator | `janus/backtest/`, `janus/paper/` | ✅ |
| 2 — Narrative Rotation | Narrative index (point-in-time tag snapshots, equal-weight returns), momentum / acceleration / β-decomposition, TF-IDF / embedding clustering, capacity-aware sizing, rotation strategy state machine, RATIONALE | `janus/features/{narrative_index,narrative_clustering}.py`, `janus/strategies/narrative_rotation/` | ✅ |
| 3 — Stablecoin Stress Flow | StablecoinSnapshot + 7 features (peg deviation, pool depth, issuer treasury, volume + inflow ratios, pair-volume, funding term structure), stress + flow signals, spot-only state machine with 45-min stress window + 6h time stop, RATIONALE | `janus/features/stablecoin_features.py`, `janus/strategies/stablecoin_stress/` | ✅ |
| 4 — Regime Detector | 5-state Gaussian HMM, BOCPD-on-vol-of-vol transition detector, confidence-weighted regime router (gate × correlation × drawdown), macro feature panel, counterfactual evaluation hook | `janus/regime/` | ✅ |
| Engine + execution | Strategy multiplexer, OrderManager (idempotent state machine), smart router (TWAP + Almgren-Chriss), reconciliation, slippage tracker, kill-switch registry, correlation monitor, drawdown manager | `janus/engine/`, `janus/execution/`, `janus/risk/` | ✅ |
| Monitoring | Prometheus metric registry, Telegram alerter (httpx-driven), append-only JSONL trade journal, daily report script, paper runner | `janus/monitoring/`, `scripts/{run_paper,daily_report}.py` | ✅ |
| Backfill 3y | Resumable Binance backfill (klines / funding / OI / trades) | `scripts/backfill_historical.py` | ⏳ run-required |
| 60-day paper × 3 strategies | Live websocket → engine wiring | `scripts/run_paper.py` | 🚧 wiring needed |
| Live deployment | VPS provisioning, kill-switch monitoring, capital ramp 5% → 100% over 90d | — | ⏳ post-paper |

---

## Quickstart

```bash
make install              # poetry install + pre-commit hooks
cp .env.example .env      # configure (see comments)
make up                   # docker-compose: TimescaleDB + Redis
make db-init              # create extension + alembic upgrade head
make test                 # run the unit suite (>80% coverage required)

# Backfill 3 years of BTC/ETH (one-time, ~30 min)
poetry run python scripts/backfill_historical.py \
    --symbols BTCUSDT ETHUSDT \
    --start 2023-01-01 \
    --datasets klines funding open_interest

# Paper-trade a strategy
poetry run python scripts/run_paper.py --strategies refractory --symbols BTCUSDT

# Daily report (run via cron at 00:05 UTC)
poetry run python scripts/daily_report.py --telegram
```

---

## Engineering invariants (enforced by CI)

1. **Point-in-time correctness.** No code path returns a row with `ts > as_of`.
   Enforced by `OhlcvRepository.fetch()`; pinned by `tests/unit/test_point_in_time.py`.
2. **Idempotent ingestion.** Re-running a backfill never produces duplicates
   (content-hash dedup + `ON CONFLICT DO NOTHING`).
3. **Type-strict.** `mypy --strict` passes on `janus/` with zero new ignores.
4. **No look-ahead in features.** Every feature is computed via the repository's
   `as_of` argument — strategies never query the DB directly.
5. **Determinism.** `pytest-randomly` seeds are logged; `_fix_seeds` resets
   `random` and `numpy.random` per test.
6. **Strategy auditability.** Every order carries a `Signal` with the
   decision-time feature snapshot. Trade journal stores it forever.
7. **Secret hygiene.** `detect-secrets` runs in pre-commit. `.env` is git-ignored.

---

## Repository layout

```
janus/
├── alembic/                       # versioned schema migrations
├── config/                        # YAML configs (strategies, narratives)
├── janus/
│   ├── backtest/                  # engine, metrics, slippage, walk-forward, stress tests
│   ├── config/                    # Pydantic settings
│   ├── data/                      # loaders, live, quality, repositories, schema
│   ├── engine/                    # multiplexer (strategy + regime + risk)
│   ├── execution/                 # order_manager, smart_router, reconciliation, slippage_tracker
│   ├── features/                  # technical / on-chain / narrative / stablecoin features
│   ├── monitoring/                # logging, prometheus, telegram, trade journal
│   ├── paper/                     # paper-trading simulator + runner
│   ├── regime/                    # HMM + BOCPD + router + macro
│   ├── risk/                      # position sizing, kill switches, correlation, drawdown
│   ├── strategies/                # base ABC + refractory + narrative_rotation + stablecoin_stress
│   ├── errors.py                  # transient/permanent error taxonomy
│   └── time_sync.py               # clock drift guard
├── scripts/                       # backfill, init_db, run_paper, daily_report
└── tests/
    ├── unit/                      # 100% deterministic, no DB
    └── integration/               # require docker compose up
```

---

## Phase gates (recap)

| Phase | Gate to advance | Kill criterion |
|-------|-----------------|----------------|
| 0 — Data infra | 3-yr backtest <5 min, live stable 7 days, all unit tests green | n/a — foundation |
| 1 — Refractory | Sharpe OOS > 1.5, paper Sharpe > 0.75 over 60 days | Sharpe OOS < 1.0 |
| 2 — Narrative | Sharpe OOS > 1.2, paper Sharpe > 0.6 | Sharpe OOS < 0.8 |
| 3 — Stablecoin | Edge net > 0.3% / trade | Edge net < 0.2% |
| 4 — Regime | Sharpe improvement > 0.2 vs always-on | Improvement < 0.1 |
| Live small | P&L within ±30% of paper for 30 days | Drawdown > 20% |
| Live full | Sharpe stable over 90 days at full size | Drawdown > 25% |

---

## Contributing (solo dev rules)

- Branch off `main`, develop on `feature/<phase>-<slug>`. Squash-merge.
- Every PR: passes `make ci`, has tests, updates the strategy `RATIONALE.md`
  if behavior changes.
- Use `make migrate MSG="…"` for new Alembic migrations; never edit existing
  migrations after merge.
- Production deployment uses a separate compose file; this repo's
  `docker-compose.yml` is dev-only.
