"""Narrative index construction + momentum / acceleration / beta decomposition.

Pipeline:
  1. For each narrative, take its constituents (loaded from snapshots — never
     "today's tagging" applied to historical data; UPGRADES §2.4).
  2. Build a daily equal-weighted index of returns: NarrativeIndex_X(t).
  3. Momentum_X(t) = product of daily returns over `momentum_window_days`.
  4. Acceleration_X(t) = d²/dt² of NarrativeMomentum (smoothed EMA-5).
  5. Beta_to_BTC: OLS regression of narrative returns vs BTC returns;
     "narrative excess return" = narrative_return - beta * btc_return.

The output is a polars DataFrame indexed by (narrative, date) with all
features computed point-in-time.

Why this matters (UPGRADES §2.3):
- Without beta decomposition you capture beta-to-BTC, not narrative rotation.
- A "high momentum" narrative during a bull market often just means "tracks
  BTC" — which has no rotation alpha.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import polars as pl


@dataclass(frozen=True, slots=True)
class IndexConfig:
    momentum_window_days: int = 30
    acceleration_smoothing_span: int = 5
    rebalance_freq_days: int = 7
    top_n_by_mcap: int = 10


def _ema(values: np.ndarray, span: int) -> np.ndarray:
    if len(values) == 0:
        return values
    alpha = 2.0 / (span + 1.0)
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def build_narrative_returns(
    bars: pl.DataFrame,
    tag_snapshots: pl.DataFrame,
    *,
    cfg: IndexConfig = IndexConfig(),
) -> pl.DataFrame:
    """Return a DataFrame with one row per (narrative, date), columns = mean log-return.

    `bars` must have columns (symbol, ts, close). The function:
      1. Computes daily log returns per symbol.
      2. Joins each (symbol, date) to its narrative tags valid on that date.
      3. Aggregates equal-weighted per narrative per date.
    """
    if bars.is_empty():
        return pl.DataFrame(schema={"narrative": pl.Utf8, "date": pl.Date, "ret": pl.Float64})

    # Daily close per symbol — last bar of each UTC day.
    daily = (
        bars.with_columns(pl.col("ts").dt.date().alias("date"))
        .sort(["symbol", "ts"])
        .group_by(["symbol", "date"])
        .agg(pl.col("close").last())
    )
    # Log return per (symbol, date).
    daily = daily.sort(["symbol", "date"]).with_columns(
        (pl.col("close").log() - pl.col("close").shift().over("symbol").log()).alias("ret")
    ).drop_nulls("ret")

    # Join tag snapshots: for each (snapshot_date, ticker, narrative), all dates >= snapshot_date
    # use that tag *until* a later snapshot supersedes it.
    if tag_snapshots.is_empty():
        return pl.DataFrame(schema={"narrative": pl.Utf8, "date": pl.Date, "ret": pl.Float64})

    snaps = tag_snapshots.with_columns(
        pl.col("snapshot_date").dt.date().alias("date_from")
    ).select(["ticker", "narrative", "date_from"])

    # asof join: for each (symbol, date), pick the latest tag snapshot <= date.
    joined = daily.rename({"symbol": "ticker"}).join_asof(
        snaps.sort("date_from"),
        left_on="date", right_on="date_from",
        by="ticker",
        strategy="backward",
    )
    joined = joined.drop_nulls("narrative")

    # Equal-weight aggregate per (narrative, date).
    agg = joined.group_by(["narrative", "date"]).agg(pl.col("ret").mean().alias("ret"))
    return agg.sort(["narrative", "date"])


def momentum(returns_df: pl.DataFrame, *, window_days: int = 30) -> pl.DataFrame:
    """Add a `momentum` column = rolling sum of log returns over `window_days`.

    Uses a sum of log returns (= log of compounded simple return) — additive
    rolling math is numerically nicer than multiplicative.
    """
    out_frames: list[pl.DataFrame] = []
    for narr in returns_df.get_column("narrative").unique().to_list():
        slice_ = returns_df.filter(pl.col("narrative") == narr).sort("date")
        if slice_.is_empty():
            continue
        rets = slice_.get_column("ret").to_numpy()
        mom = np.zeros_like(rets)
        for i in range(len(rets)):
            lo = max(0, i - window_days + 1)
            mom[i] = rets[lo:i + 1].sum()
        slice_ = slice_.with_columns(pl.Series("momentum", mom))
        out_frames.append(slice_)
    if not out_frames:
        return returns_df.with_columns(pl.lit(0.0).alias("momentum"))
    return pl.concat(out_frames)


def acceleration(returns_df: pl.DataFrame, *, smoothing_span: int = 5) -> pl.DataFrame:
    """Second discrete derivative of momentum, smoothed via EMA."""
    out: list[pl.DataFrame] = []
    for narr in returns_df.get_column("narrative").unique().to_list():
        slice_ = returns_df.filter(pl.col("narrative") == narr).sort("date")
        m = slice_.get_column("momentum").to_numpy() if "momentum" in slice_.columns else np.zeros(len(slice_))
        # First derivative (delta).
        d1 = np.diff(m, prepend=m[0] if len(m) > 0 else 0.0)
        d2 = np.diff(d1, prepend=d1[0] if len(d1) > 0 else 0.0)
        smooth = _ema(d2, smoothing_span)
        slice_ = slice_.with_columns(pl.Series("acceleration", smooth))
        out.append(slice_)
    if not out:
        return returns_df.with_columns(pl.lit(0.0).alias("acceleration"))
    return pl.concat(out)


def beta_to_btc(returns_df: pl.DataFrame, btc_returns: pl.DataFrame,
                 *, window_days: int = 60) -> pl.DataFrame:
    """Rolling OLS beta of each narrative vs BTC, computed over `window_days`."""
    if btc_returns.is_empty():
        return returns_df.with_columns(pl.lit(0.0).alias("beta_btc"))

    btc = btc_returns.rename({"ret": "btc_ret"}).select(["date", "btc_ret"])
    out: list[pl.DataFrame] = []
    for narr in returns_df.get_column("narrative").unique().to_list():
        slice_ = (
            returns_df.filter(pl.col("narrative") == narr)
            .sort("date")
            .join(btc, on="date", how="inner")
        )
        if slice_.is_empty():
            continue
        r = slice_.get_column("ret").to_numpy()
        b = slice_.get_column("btc_ret").to_numpy()
        beta = np.zeros_like(r)
        for i in range(len(r)):
            lo = max(0, i - window_days + 1)
            r_w = r[lo:i + 1]
            b_w = b[lo:i + 1]
            if len(r_w) < 5 or b_w.var(ddof=1) == 0:
                beta[i] = 0.0
            else:
                beta[i] = float(np.cov(r_w, b_w, ddof=1)[0, 1] / b_w.var(ddof=1))
        slice_ = slice_.with_columns(pl.Series("beta_btc", beta))
        out.append(slice_.drop("btc_ret"))
    if not out:
        return returns_df.with_columns(pl.lit(0.0).alias("beta_btc"))
    return pl.concat(out)


def excess_return(returns_df: pl.DataFrame, btc_returns: pl.DataFrame) -> pl.DataFrame:
    """Add `excess_ret = ret - beta * btc_ret` (UPGRADES §2.3).

    Strips beta-to-BTC. Rotation alpha lives in the residual.
    """
    if btc_returns.is_empty() or "beta_btc" not in returns_df.columns:
        return returns_df.with_columns(pl.lit(0.0).alias("excess_ret"))
    btc = btc_returns.rename({"ret": "btc_ret"}).select(["date", "btc_ret"])
    joined = returns_df.join(btc, on="date", how="left").with_columns(
        (pl.col("ret") - pl.col("beta_btc") * pl.col("btc_ret").fill_null(0.0)).alias("excess_ret")
    )
    return joined.drop("btc_ret")


def capacity_aware_size_pct(
    *, ticker: str, target_quote: float, daily_volume_quote: float,
    max_pct_of_daily_volume: float = 5.0,
) -> float:
    """UPGRADES §2.5: limit position to a % of the token's daily volume.

    Returns the actual position size (in quote ccy) to use, capped at the
    `max_pct_of_daily_volume` ceiling.
    """
    if daily_volume_quote <= 0:
        return 0.0
    cap_quote = daily_volume_quote * max_pct_of_daily_volume / 100.0
    return min(target_quote, cap_quote)
