"""Data providers for the backtest engine.

The engine sees data exclusively through `MarketWindowProvider.get_window(...)`.
Backtests use `InMemoryWindowProvider` (preloaded polars DataFrames); live/paper
use `RepositoryWindowProvider` (queries OhlcvRepository at as_of=now).

This abstraction is what lets the *same* strategy code run in backtest and live —
the strategy never knows where the bars came from.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

import polars as pl

from janus.features.refractory_features import MarketWindow


class MarketWindowProvider(abc.ABC):
    @abc.abstractmethod
    def get_window(self, symbol: str, as_of: datetime, lookback: timedelta) -> MarketWindow: ...

    @abc.abstractmethod
    def get_baseline_bars(self, symbol: str, as_of: datetime, days: int = 30) -> Sequence[dict[str, Any]]: ...


class InMemoryWindowProvider(MarketWindowProvider):
    """Backtest-friendly provider — sliced from preloaded polars DataFrames.

    Schemas (column names match the DB tables):
        bars:           symbol, ts, open, high, low, close, volume,
                        quote_volume, trade_count, taker_buy_volume,
                        taker_buy_quote_volume
        liquidations:   symbol, ts, side, price, quantity, notional_usd
        open_interest:  symbol, ts, oi_contracts, oi_quote
        funding:        symbol, ts, rate, mark_price
    """

    def __init__(
        self,
        bars: pl.DataFrame,
        liquidations: pl.DataFrame | None = None,
        open_interest: pl.DataFrame | None = None,
        funding: pl.DataFrame | None = None,
    ):
        self.bars = bars.sort("ts")
        self.liq = (liquidations or pl.DataFrame()).sort("ts") if liquidations is not None else pl.DataFrame()
        self.oi = (open_interest or pl.DataFrame()).sort("ts") if open_interest is not None else pl.DataFrame()
        self.funding = (funding or pl.DataFrame()).sort("ts") if funding is not None else pl.DataFrame()

    @staticmethod
    def _slice(df: pl.DataFrame, symbol: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        if df.is_empty():
            return []
        sliced = df.filter(
            (pl.col("symbol") == symbol)
            & (pl.col("ts") >= start)
            & (pl.col("ts") <= end)
        )
        return sliced.to_dicts()

    def get_window(self, symbol: str, as_of: datetime, lookback: timedelta) -> MarketWindow:
        start = as_of - lookback
        bars = self._slice(self.bars, symbol, start, as_of)
        liq = self._slice(self.liq, symbol, start, as_of)
        oi = self._slice(self.oi, symbol, start, as_of)
        # Funding history needs more lookback (30d) for z-score.
        funding_start = as_of - timedelta(days=30)
        funding = self._slice(self.funding, symbol, funding_start, as_of)
        return MarketWindow(
            as_of=as_of,
            bars=bars,
            liquidations=liq,
            open_interest=oi,
            funding_history=funding,
        )

    def get_baseline_bars(self, symbol: str, as_of: datetime, days: int = 30) -> Sequence[dict[str, Any]]:
        start = as_of - timedelta(days=days)
        # Baseline is "the period BEFORE the cascade window" — use everything up to as_of - 1h.
        end = as_of - timedelta(hours=1)
        return self._slice(self.bars, symbol, start, end)
