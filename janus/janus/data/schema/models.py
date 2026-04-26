"""SQLAlchemy schema for Janus.

Design notes:

* Every time-series table has `(symbol, ts)` (or analogue) as primary key.
  TimescaleDB requires the time column in the PK for hypertable creation.
* All ts columns are `TIMESTAMPTZ` — never naive timestamps. Naive timestamps
  in a multi-source system are a bug factory.
* `feature_version` columns let us store multiple definitions of derived
  features without breaking historical backtests (UPGRADES §0.11).
* `ingest_job_id` foreign-key-ish on every row makes ingestion idempotent
  and audit-friendly (UPGRADES §0.5).
* Numeric columns use `Numeric(28, 12)` (28 digits, 12 fractional) — enough
  for any crypto price including microcaps with 8+ decimals.

This module defines tables only; the Alembic migration creates the hypertables,
continuous aggregates, compression policies, and retention policies (those are
TimescaleDB-specific DDL not expressible in SQLAlchemy core).
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

# Naming convention so Alembic can reliably autogenerate names that match
# what Postgres produces — fewer surprises in migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ─────────────────────────── operational tables ───────────────────────────

ingest_jobs = Table(
    "ingest_jobs",
    metadata,
    # UUID-like string (we use ULIDs in code — sortable + unique + opaque).
    Column("id", String(32), primary_key=True),
    Column("source", String(32), nullable=False),  # e.g. binance, coinglass
    Column("dataset", String(64), nullable=False),  # e.g. klines_1m, funding_rates
    Column("symbol", String(32), nullable=True),
    Column("range_start", DateTime(timezone=True), nullable=True),
    Column("range_end", DateTime(timezone=True), nullable=True),
    Column("status", String(16), nullable=False),  # pending|running|succeeded|failed
    Column("attempt", Integer, nullable=False, server_default=text("1")),
    Column("rows_written", BigInteger, nullable=False, server_default=text("0")),
    Column("content_hash", String(64), nullable=True),  # sha256 of payload
    Column("error", Text, nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Index("ix_ingest_jobs_source_dataset", "source", "dataset"),
    Index("ix_ingest_jobs_status", "status"),
)


outbox = Table(
    "outbox",
    metadata,
    # Sequence-backed monotonic id; consumers track a last-seen offset in Redis.
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("topic", String(64), nullable=False),  # e.g. ohlcv.btcusdt.1m, liq.btcusdt
    Column("payload", JSONB, nullable=False),
    Column("event_ts", DateTime(timezone=True), nullable=False),  # event time, not ingest time
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("dispatched_at", DateTime(timezone=True), nullable=True),
    Index("ix_outbox_topic_event_ts", "topic", "event_ts"),
    Index("ix_outbox_undispatched", "id", postgresql_where=text("dispatched_at IS NULL")),
)


dead_letter = Table(
    "dead_letter",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("source", String(32), nullable=False),
    Column("dataset", String(64), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("reason", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_dead_letter_source_dataset", "source", "dataset"),
)


# ─────────────────────────── time-series tables ───────────────────────────

ohlcv_1m = Table(
    "ohlcv_1m",
    metadata,
    Column("symbol", String(32), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("open", Numeric(28, 12), nullable=False),
    Column("high", Numeric(28, 12), nullable=False),
    Column("low", Numeric(28, 12), nullable=False),
    Column("close", Numeric(28, 12), nullable=False),
    Column("volume", Numeric(28, 12), nullable=False),
    Column("quote_volume", Numeric(28, 12), nullable=False),
    Column("trade_count", Integer, nullable=False),
    Column("taker_buy_volume", Numeric(28, 12), nullable=False),
    Column("taker_buy_quote_volume", Numeric(28, 12), nullable=False),
    Column("source", String(16), nullable=False),  # binance|bybit|...
    Column("ingest_job_id", String(32), nullable=False),
    PrimaryKeyConstraint("symbol", "ts", "source", name="pk_ohlcv_1m"),
    CheckConstraint("high >= low", name="hi_ge_lo"),
    CheckConstraint("high >= open AND high >= close", name="hi_ge_oc"),
    CheckConstraint("low <= open AND low <= close", name="lo_le_oc"),
    CheckConstraint("volume >= 0", name="vol_nn"),
    CheckConstraint("trade_count >= 0", name="trades_nn"),
)


funding_rates = Table(
    "funding_rates",
    metadata,
    Column("symbol", String(32), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),  # funding interval end
    Column("rate", Numeric(18, 12), nullable=False),
    Column("mark_price", Numeric(28, 12), nullable=True),
    Column("source", String(16), nullable=False),
    Column("ingest_job_id", String(32), nullable=False),
    PrimaryKeyConstraint("symbol", "ts", "source", name="pk_funding_rates"),
)


open_interest = Table(
    "open_interest",
    metadata,
    Column("symbol", String(32), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("oi_contracts", Numeric(28, 12), nullable=False),  # in contracts
    Column("oi_quote", Numeric(28, 12), nullable=True),       # in quote currency (usd)
    Column("source", String(16), nullable=False),
    Column("ingest_job_id", String(32), nullable=False),
    PrimaryKeyConstraint("symbol", "ts", "source", name="pk_open_interest"),
    CheckConstraint("oi_contracts >= 0", name="oi_nn"),
)


liquidations = Table(
    "liquidations",
    metadata,
    # Liquidations are events, not periodic — id = exchange's order id when available.
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("symbol", String(32), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("side", String(4), nullable=False),  # 'long' (long got liquidated) | 'short'
    Column("price", Numeric(28, 12), nullable=False),
    Column("quantity", Numeric(28, 12), nullable=False),
    Column("notional_usd", Numeric(28, 12), nullable=False),
    Column("source", String(16), nullable=False),
    Column("source_order_id", String(64), nullable=True),
    Column("ingest_job_id", String(32), nullable=False),
    Index("ix_liquidations_symbol_ts", "symbol", "ts"),
    CheckConstraint("side IN ('long','short')", name="side_chk"),
    CheckConstraint("price > 0 AND quantity > 0", name="pq_pos"),
)


# UPGRADES §0.1: tick-level trades for honest slippage modeling.
trades = Table(
    "trades",
    metadata,
    Column("symbol", String(32), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("trade_id", BigInteger, nullable=False),
    Column("price", Numeric(28, 12), nullable=False),
    Column("quantity", Numeric(28, 12), nullable=False),
    Column("is_buyer_maker", Boolean, nullable=False),
    Column("source", String(16), nullable=False),
    Column("ingest_job_id", String(32), nullable=False),
    PrimaryKeyConstraint("symbol", "source", "trade_id", name="pk_trades"),
    Index("ix_trades_symbol_ts", "symbol", "ts"),
)


# UPGRADES §0.2: L2 orderbook snapshots (top-N levels) for execution simulation.
# Bids/asks are stored as JSONB arrays of [price, qty] tuples — Postgres jsonb_path_ops
# index isn't needed, we always read by (symbol, ts).
orderbook_snapshots = Table(
    "orderbook_snapshots",
    metadata,
    Column("symbol", String(32), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("levels", SmallInteger, nullable=False),  # how many levels actually captured
    Column("bids", JSONB, nullable=False),
    Column("asks", JSONB, nullable=False),
    Column("source", String(16), nullable=False),
    Column("ingest_job_id", String(32), nullable=False),
    PrimaryKeyConstraint("symbol", "source", "ts", name="pk_orderbook_snapshots"),
)


onchain_metrics = Table(
    "onchain_metrics",
    metadata,
    Column("asset", String(16), nullable=False),     # btc, eth, ...
    Column("metric", String(64), nullable=False),    # exchange_inflow, mvrv, sopr, ...
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("value", Numeric(28, 12), nullable=False),
    Column("source", String(32), nullable=False),    # glassnode|cryptoquant
    Column("feature_version", SmallInteger, nullable=False, server_default=text("1")),
    Column("ingest_job_id", String(32), nullable=False),
    PrimaryKeyConstraint(
        "asset", "metric", "ts", "source", "feature_version", name="pk_onchain_metrics"
    ),
)


stablecoin_supply = Table(
    "stablecoin_supply",
    metadata,
    Column("asset", String(16), nullable=False),     # USDT, USDC, DAI
    Column("chain", String(16), nullable=False),     # ethereum, tron, solana
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("supply", Numeric(28, 6), nullable=False),
    Column("issued_24h", Numeric(28, 6), nullable=True),
    Column("burned_24h", Numeric(28, 6), nullable=True),
    Column("source", String(16), nullable=False),
    Column("ingest_job_id", String(32), nullable=False),
    PrimaryKeyConstraint("asset", "chain", "ts", "source", name="pk_stablecoin_supply"),
)


# Holds the daily snapshots used to avoid look-ahead on category tags
# (UPGRADES §2.4).
narrative_tag_snapshots = Table(
    "narrative_tag_snapshots",
    metadata,
    Column("snapshot_date", DateTime(timezone=True), nullable=False),
    Column("ticker", String(32), nullable=False),
    Column("narrative", String(64), nullable=False),
    Column("source", String(32), nullable=False),    # coingecko|messari|manual
    Column("payload_hash", String(64), nullable=False),
    PrimaryKeyConstraint(
        "snapshot_date", "ticker", "narrative", "source", name="pk_narrative_tag_snapshots"
    ),
)


# Bronze layer: raw payloads kept compressed for replay/audit. We store the
# raw bytes (not parsed) so a future schema bug can be re-derived correctly.
raw_payloads = Table(
    "raw_payloads",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("ingest_job_id", String(32), nullable=False),
    Column("source", String(32), nullable=False),
    Column("dataset", String(64), nullable=False),
    Column("retrieved_at", DateTime(timezone=True), nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("payload_gzip", LargeBinary, nullable=False),
    Index("ix_raw_payloads_hash", "content_hash"),
    Index("ix_raw_payloads_source_dataset_ret", "source", "dataset", "retrieved_at"),
)


# All hypertable / continuous aggregate / compression / retention DDL is
# created in the Alembic migration `0001_initial_schema.py`. Keeping it there
# lets us evolve those policies (e.g. tighten retention) via versioned
# migrations rather than scattered scripts.

HYPERTABLES: tuple[str, ...] = (
    "ohlcv_1m",
    "funding_rates",
    "open_interest",
    "liquidations",
    "trades",
    "orderbook_snapshots",
    "onchain_metrics",
    "stablecoin_supply",
    "raw_payloads",
)
