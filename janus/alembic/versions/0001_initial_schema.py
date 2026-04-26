"""initial schema — operational tables, hypertables, continuous aggregates,
compression and retention policies.

Revision ID: 0001
Revises:
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ───────── extension ─────────
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")

    # ───────── operational tables ─────────
    op.execute(
        """
        CREATE TABLE ingest_jobs (
            id              VARCHAR(32) PRIMARY KEY,
            source          VARCHAR(32) NOT NULL,
            dataset         VARCHAR(64) NOT NULL,
            symbol          VARCHAR(32),
            range_start     TIMESTAMPTZ,
            range_end       TIMESTAMPTZ,
            status          VARCHAR(16) NOT NULL,
            attempt         INTEGER NOT NULL DEFAULT 1,
            rows_written    BIGINT NOT NULL DEFAULT 0,
            content_hash    VARCHAR(64),
            error           TEXT,
            started_at      TIMESTAMPTZ NOT NULL,
            finished_at     TIMESTAMPTZ
        );
        CREATE INDEX ix_ingest_jobs_source_dataset ON ingest_jobs (source, dataset);
        CREATE INDEX ix_ingest_jobs_status ON ingest_jobs (status);
        """
    )

    op.execute(
        """
        CREATE TABLE outbox (
            id              BIGSERIAL PRIMARY KEY,
            topic           VARCHAR(64) NOT NULL,
            payload         JSONB NOT NULL,
            event_ts        TIMESTAMPTZ NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL,
            dispatched_at   TIMESTAMPTZ
        );
        CREATE INDEX ix_outbox_topic_event_ts ON outbox (topic, event_ts);
        CREATE INDEX ix_outbox_undispatched ON outbox (id) WHERE dispatched_at IS NULL;
        """
    )

    op.execute(
        """
        CREATE TABLE dead_letter (
            id              BIGSERIAL PRIMARY KEY,
            source          VARCHAR(32) NOT NULL,
            dataset         VARCHAR(64) NOT NULL,
            payload         JSONB NOT NULL,
            reason          TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX ix_dead_letter_source_dataset ON dead_letter (source, dataset);
        """
    )

    # ───────── time-series tables ─────────
    op.execute(
        """
        CREATE TABLE ohlcv_1m (
            symbol                  VARCHAR(32) NOT NULL,
            ts                      TIMESTAMPTZ NOT NULL,
            open                    NUMERIC(28,12) NOT NULL,
            high                    NUMERIC(28,12) NOT NULL,
            low                     NUMERIC(28,12) NOT NULL,
            close                   NUMERIC(28,12) NOT NULL,
            volume                  NUMERIC(28,12) NOT NULL,
            quote_volume            NUMERIC(28,12) NOT NULL,
            trade_count             INTEGER NOT NULL,
            taker_buy_volume        NUMERIC(28,12) NOT NULL,
            taker_buy_quote_volume  NUMERIC(28,12) NOT NULL,
            source                  VARCHAR(16) NOT NULL,
            ingest_job_id           VARCHAR(32) NOT NULL,
            CONSTRAINT pk_ohlcv_1m PRIMARY KEY (symbol, ts, source),
            CONSTRAINT ck_ohlcv_1m_hi_ge_lo  CHECK (high >= low),
            CONSTRAINT ck_ohlcv_1m_hi_ge_oc  CHECK (high >= open AND high >= close),
            CONSTRAINT ck_ohlcv_1m_lo_le_oc  CHECK (low <= open AND low <= close),
            CONSTRAINT ck_ohlcv_1m_vol_nn    CHECK (volume >= 0),
            CONSTRAINT ck_ohlcv_1m_trades_nn CHECK (trade_count >= 0)
        );
        SELECT create_hypertable('ohlcv_1m', 'ts', chunk_time_interval => INTERVAL '7 days');
        CREATE INDEX ix_ohlcv_1m_symbol_ts_desc ON ohlcv_1m (symbol, ts DESC);
        """
    )

    op.execute(
        """
        CREATE TABLE funding_rates (
            symbol          VARCHAR(32) NOT NULL,
            ts              TIMESTAMPTZ NOT NULL,
            rate            NUMERIC(18,12) NOT NULL,
            mark_price      NUMERIC(28,12),
            source          VARCHAR(16) NOT NULL,
            ingest_job_id   VARCHAR(32) NOT NULL,
            CONSTRAINT pk_funding_rates PRIMARY KEY (symbol, ts, source)
        );
        SELECT create_hypertable('funding_rates', 'ts', chunk_time_interval => INTERVAL '90 days');
        """
    )

    op.execute(
        """
        CREATE TABLE open_interest (
            symbol          VARCHAR(32) NOT NULL,
            ts              TIMESTAMPTZ NOT NULL,
            oi_contracts    NUMERIC(28,12) NOT NULL,
            oi_quote        NUMERIC(28,12),
            source          VARCHAR(16) NOT NULL,
            ingest_job_id   VARCHAR(32) NOT NULL,
            CONSTRAINT pk_open_interest PRIMARY KEY (symbol, ts, source),
            CONSTRAINT ck_open_interest_oi_nn CHECK (oi_contracts >= 0)
        );
        SELECT create_hypertable('open_interest', 'ts', chunk_time_interval => INTERVAL '30 days');
        """
    )

    op.execute(
        """
        CREATE TABLE liquidations (
            id              BIGSERIAL,
            symbol          VARCHAR(32) NOT NULL,
            ts              TIMESTAMPTZ NOT NULL,
            side            VARCHAR(4) NOT NULL,
            price           NUMERIC(28,12) NOT NULL,
            quantity        NUMERIC(28,12) NOT NULL,
            notional_usd    NUMERIC(28,12) NOT NULL,
            source          VARCHAR(16) NOT NULL,
            source_order_id VARCHAR(64),
            ingest_job_id   VARCHAR(32) NOT NULL,
            PRIMARY KEY (id, ts),
            CONSTRAINT ck_liquidations_side_chk CHECK (side IN ('long','short')),
            CONSTRAINT ck_liquidations_pq_pos   CHECK (price > 0 AND quantity > 0)
        );
        SELECT create_hypertable('liquidations', 'ts', chunk_time_interval => INTERVAL '7 days');
        CREATE INDEX ix_liquidations_symbol_ts ON liquidations (symbol, ts DESC);
        """
    )

    op.execute(
        """
        CREATE TABLE trades (
            symbol          VARCHAR(32) NOT NULL,
            ts              TIMESTAMPTZ NOT NULL,
            trade_id        BIGINT NOT NULL,
            price           NUMERIC(28,12) NOT NULL,
            quantity        NUMERIC(28,12) NOT NULL,
            is_buyer_maker  BOOLEAN NOT NULL,
            source          VARCHAR(16) NOT NULL,
            ingest_job_id   VARCHAR(32) NOT NULL,
            CONSTRAINT pk_trades PRIMARY KEY (symbol, source, trade_id, ts)
        );
        SELECT create_hypertable('trades', 'ts', chunk_time_interval => INTERVAL '1 day');
        CREATE INDEX ix_trades_symbol_ts ON trades (symbol, ts DESC);
        """
    )

    op.execute(
        """
        CREATE TABLE orderbook_snapshots (
            symbol          VARCHAR(32) NOT NULL,
            ts              TIMESTAMPTZ NOT NULL,
            levels          SMALLINT NOT NULL,
            bids            JSONB NOT NULL,
            asks            JSONB NOT NULL,
            source          VARCHAR(16) NOT NULL,
            ingest_job_id   VARCHAR(32) NOT NULL,
            CONSTRAINT pk_orderbook_snapshots PRIMARY KEY (symbol, source, ts)
        );
        SELECT create_hypertable('orderbook_snapshots', 'ts', chunk_time_interval => INTERVAL '1 day');
        """
    )

    op.execute(
        """
        CREATE TABLE onchain_metrics (
            asset            VARCHAR(16) NOT NULL,
            metric           VARCHAR(64) NOT NULL,
            ts               TIMESTAMPTZ NOT NULL,
            value            NUMERIC(28,12) NOT NULL,
            source           VARCHAR(32) NOT NULL,
            feature_version  SMALLINT NOT NULL DEFAULT 1,
            ingest_job_id    VARCHAR(32) NOT NULL,
            CONSTRAINT pk_onchain_metrics PRIMARY KEY (asset, metric, ts, source, feature_version)
        );
        SELECT create_hypertable('onchain_metrics', 'ts', chunk_time_interval => INTERVAL '90 days');
        """
    )

    op.execute(
        """
        CREATE TABLE stablecoin_supply (
            asset           VARCHAR(16) NOT NULL,
            chain           VARCHAR(16) NOT NULL,
            ts              TIMESTAMPTZ NOT NULL,
            supply          NUMERIC(28,6) NOT NULL,
            issued_24h      NUMERIC(28,6),
            burned_24h      NUMERIC(28,6),
            source          VARCHAR(16) NOT NULL,
            ingest_job_id   VARCHAR(32) NOT NULL,
            CONSTRAINT pk_stablecoin_supply PRIMARY KEY (asset, chain, ts, source)
        );
        SELECT create_hypertable('stablecoin_supply', 'ts', chunk_time_interval => INTERVAL '90 days');
        """
    )

    op.execute(
        """
        CREATE TABLE narrative_tag_snapshots (
            snapshot_date   TIMESTAMPTZ NOT NULL,
            ticker          VARCHAR(32) NOT NULL,
            narrative       VARCHAR(64) NOT NULL,
            source          VARCHAR(32) NOT NULL,
            payload_hash    VARCHAR(64) NOT NULL,
            CONSTRAINT pk_narrative_tag_snapshots
                PRIMARY KEY (snapshot_date, ticker, narrative, source)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE raw_payloads (
            id              BIGSERIAL,
            ingest_job_id   VARCHAR(32) NOT NULL,
            source          VARCHAR(32) NOT NULL,
            dataset         VARCHAR(64) NOT NULL,
            retrieved_at    TIMESTAMPTZ NOT NULL,
            content_hash    VARCHAR(64) NOT NULL,
            payload_gzip    BYTEA NOT NULL,
            PRIMARY KEY (id, retrieved_at)
        );
        SELECT create_hypertable('raw_payloads', 'retrieved_at', chunk_time_interval => INTERVAL '7 days');
        CREATE INDEX ix_raw_payloads_hash ON raw_payloads (content_hash);
        CREATE INDEX ix_raw_payloads_source_dataset_ret
            ON raw_payloads (source, dataset, retrieved_at DESC);
        """
    )

    # ───────── continuous aggregates (UPGRADES §0.3) ─────────
    # One MV per resolution. Refresh policies are scheduled below.
    for window in ("5 minutes", "15 minutes", "1 hour", "4 hours", "1 day"):
        slug = window.replace(" ", "").replace("minutes", "m").replace("minute", "m") \
                     .replace("hours", "h").replace("hour", "h").replace("days", "d").replace("day", "d")
        op.execute(
            f"""
            CREATE MATERIALIZED VIEW ohlcv_{slug}
            WITH (timescaledb.continuous) AS
            SELECT
                symbol,
                source,
                time_bucket(INTERVAL '{window}', ts) AS bucket,
                FIRST(open, ts)                       AS open,
                MAX(high)                             AS high,
                MIN(low)                              AS low,
                LAST(close, ts)                       AS close,
                SUM(volume)                           AS volume,
                SUM(quote_volume)                     AS quote_volume,
                SUM(trade_count)                      AS trade_count,
                SUM(taker_buy_volume)                 AS taker_buy_volume,
                SUM(taker_buy_quote_volume)           AS taker_buy_quote_volume
            FROM ohlcv_1m
            GROUP BY symbol, source, bucket
            WITH NO DATA;
            """
        )
        # Refresh: fill the recent past on a cadence sized to the window.
        op.execute(
            f"""
            SELECT add_continuous_aggregate_policy('ohlcv_{slug}',
                start_offset => INTERVAL '14 days',
                end_offset   => INTERVAL '1 minute',
                schedule_interval => INTERVAL '{window}');
            """
        )

    # ───────── compression policies (UPGRADES §0.4) ─────────
    # Compress chunks older than the cutoffs below — typically gives 8-15× reduction.
    op.execute(
        """
        ALTER TABLE ohlcv_1m SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'symbol, source',
            timescaledb.compress_orderby = 'ts DESC'
        );
        SELECT add_compression_policy('ohlcv_1m', INTERVAL '14 days');
        """
    )
    op.execute(
        """
        ALTER TABLE trades SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'symbol, source',
            timescaledb.compress_orderby = 'ts DESC, trade_id DESC'
        );
        SELECT add_compression_policy('trades', INTERVAL '7 days');
        """
    )
    op.execute(
        """
        ALTER TABLE orderbook_snapshots SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'symbol, source',
            timescaledb.compress_orderby = 'ts DESC'
        );
        SELECT add_compression_policy('orderbook_snapshots', INTERVAL '3 days');
        """
    )
    op.execute(
        """
        ALTER TABLE liquidations SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'symbol, source',
            timescaledb.compress_orderby = 'ts DESC'
        );
        SELECT add_compression_policy('liquidations', INTERVAL '14 days');
        """
    )
    op.execute(
        """
        ALTER TABLE raw_payloads SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'source, dataset',
            timescaledb.compress_orderby = 'retrieved_at DESC'
        );
        SELECT add_compression_policy('raw_payloads', INTERVAL '3 days');
        """
    )

    # ───────── retention policies ─────────
    # raw_payloads: 90 days (forensic, not analytical) — analytical tables retain forever for now.
    op.execute("SELECT add_retention_policy('raw_payloads', INTERVAL '90 days');")
    # orderbook L2 at 1-second cadence is voluminous; 180 days is plenty for slippage modeling.
    op.execute("SELECT add_retention_policy('orderbook_snapshots', INTERVAL '180 days');")


def downgrade() -> None:
    # Drop in reverse order. Continuous aggregates and policies are dropped
    # implicitly when tables are dropped.
    for slug in ("5m", "15m", "1h", "4h", "1d"):
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS ohlcv_{slug} CASCADE;")
    for table in (
        "raw_payloads",
        "narrative_tag_snapshots",
        "stablecoin_supply",
        "onchain_metrics",
        "orderbook_snapshots",
        "trades",
        "liquidations",
        "open_interest",
        "funding_rates",
        "ohlcv_1m",
        "dead_letter",
        "outbox",
        "ingest_jobs",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
