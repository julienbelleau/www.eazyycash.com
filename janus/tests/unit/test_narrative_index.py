"""Narrative index features — sanity tests.

We construct a tiny synthetic universe so the math is easily checkable.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import polars as pl

from janus.features.narrative_index import (
    acceleration,
    beta_to_btc,
    build_narrative_returns,
    capacity_aware_size_pct,
    excess_return,
    momentum,
)


def _bars(symbol: str, start: datetime, n_days: int, daily_drift: float = 0.005) -> pl.DataFrame:
    rows = []
    price = 1.0
    for i in range(n_days):
        ts = start + timedelta(days=i)
        price *= 1.0 + daily_drift
        rows.append({"symbol": symbol, "ts": ts, "close": price})
    return pl.DataFrame(rows)


def _tag_snapshots(ticker: str, narrative: str, start: datetime) -> pl.DataFrame:
    return pl.DataFrame([{
        "snapshot_date": start, "ticker": ticker, "narrative": narrative,
    }])


def test_build_returns_assigns_to_narrative() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = pl.concat([_bars("AAA", start, 30, 0.01), _bars("BBB", start, 30, -0.005)])
    tags = pl.concat([_tag_snapshots("AAA", "ai", start), _tag_snapshots("BBB", "ai", start)])
    df = build_narrative_returns(bars, tags)
    assert "narrative" in df.columns
    assert "ret" in df.columns
    assert df.get_column("narrative").unique().to_list() == ["ai"]


def test_momentum_is_rolling_sum() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = _bars("AAA", start, 60, 0.01)
    tags = _tag_snapshots("AAA", "ai", start)
    df = build_narrative_returns(bars, tags)
    df = momentum(df, window_days=10)
    assert "momentum" in df.columns
    # With a constant +0.01 daily return, after 10 days momentum ≈ 10 * log(1.01) ≈ 0.0995.
    last = df.sort("date").tail(1).get_column("momentum")[0]
    assert 0.05 < last < 0.15


def test_acceleration_present() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = _bars("AAA", start, 60, 0.01)
    tags = _tag_snapshots("AAA", "ai", start)
    df = build_narrative_returns(bars, tags)
    df = momentum(df, window_days=10)
    df = acceleration(df, smoothing_span=5)
    assert "acceleration" in df.columns


def test_beta_one_to_self() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = _bars("AAA", start, 90, 0.005)
    tags = _tag_snapshots("AAA", "ai", start)
    df = build_narrative_returns(bars, tags)
    df = momentum(df, window_days=10)
    btc = df.rename({"ret": "ret"}).select(["date", "ret"])
    df_b = beta_to_btc(df, btc, window_days=30)
    # When narrative *is* BTC, beta should be ~1.
    last_betas = df_b.sort("date").tail(20).get_column("beta_btc").to_list()
    assert all(0.5 < b < 1.5 for b in last_betas if b != 0)


def test_excess_return_zero_when_pure_beta() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = _bars("AAA", start, 90, 0.005)
    tags = _tag_snapshots("AAA", "ai", start)
    df = build_narrative_returns(bars, tags)
    df = momentum(df, window_days=10)
    btc = df.select(["date", "ret"])
    df = beta_to_btc(df, btc, window_days=30)
    df = excess_return(df, btc)
    assert "excess_ret" in df.columns


def test_capacity_aware_size() -> None:
    # 5% of $10M daily volume = $500k cap, asked $1M → should clip to $500k.
    assert capacity_aware_size_pct(
        ticker="AAA", target_quote=1_000_000.0, daily_volume_quote=10_000_000.0,
        max_pct_of_daily_volume=5.0,
    ) == 500_000.0
    # Under the cap → unchanged.
    assert capacity_aware_size_pct(
        ticker="AAA", target_quote=100_000.0, daily_volume_quote=10_000_000.0,
        max_pct_of_daily_volume=5.0,
    ) == 100_000.0
    # Zero volume → zero size.
    assert capacity_aware_size_pct(
        ticker="AAA", target_quote=100_000.0, daily_volume_quote=0.0,
    ) == 0.0
