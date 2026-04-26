"""Binance loaders for klines, funding rates, open interest, trades.

Why httpx + REST instead of CCXT for backfill:
- CCXT pro is for websockets (live). For historical pulls we want explicit
  control over pagination and rate limit headers, which CCXT abstracts away.
- Binance public endpoints don't require auth; auth only lifts the rate limit.

Each loader subclass corresponds to one Binance endpoint. Pagination is
explicit per endpoint because Binance uses different parameter names
(`startTime/endTime/limit` vs others).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
from loguru import logger

from janus.data.loaders.base import BaseLoader
from janus.errors import (
    AuthError,
    ExchangeUnavailableError,
    PermanentError,
    RateLimitedError,
)

_BASE_SPOT = "https://api.binance.com"
_BASE_FUTURES = "https://fapi.binance.com"

# Binance: spot weight budget = 6000/min IP. Futures = 2400/min IP.
# We pace conservatively to 20/sec — leaves headroom for live websockets.
_DEFAULT_RATE = (20, 1.0)


def _classify_http_error(exc: httpx.HTTPStatusError) -> Exception:
    """Map an HTTP error to the Janus error taxonomy."""
    code = exc.response.status_code
    if code in (418, 429):
        return RateLimitedError(f"Binance rate-limited ({code}): {exc.response.text[:300]}")
    if code in (401, 403):
        return AuthError(f"Binance auth error ({code})")
    if code >= 500:
        return ExchangeUnavailableError(f"Binance {code}: {exc.response.text[:300]}")
    # 4xx client errors that aren't 401/403/429 are programming errors.
    return PermanentError(f"Binance {code}: {exc.response.text[:300]}")


async def _get_json(client: httpx.AsyncClient, base: str, path: str, params: dict[str, Any]) -> Any:
    try:
        response = await client.get(f"{base}{path}", params=params, timeout=15.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _classify_http_error(exc) from exc
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise ExchangeUnavailableError(str(exc)) from exc
    return response.json()


# ─────────────────────────── klines ───────────────────────────

class BinanceKlineLoader(BaseLoader):
    """Fetch 1-minute klines from Binance spot.

    Binance returns at most 1000 bars per call. The loader paginates using
    the `endTime` of the last returned bar.
    """

    source = "binance"
    dataset = "klines_1m"
    rate_limit = _DEFAULT_RATE

    INTERVAL_MS = 60_000  # 1 minute

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch(  # type: ignore[override]
        self,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
        limit: int = 1000,
    ) -> list[list[Any]]:
        params = {
            "symbol": symbol,
            "interval": "1m",
            "startTime": int(start_ts.timestamp() * 1000),
            "endTime": int(end_ts.timestamp() * 1000),
            "limit": limit,
        }
        return await _get_json(self._client, _BASE_SPOT, "/api/v3/klines", params)

    def parse(self, raw: list[list[Any]], **kwargs: Any) -> Sequence[dict[str, Any]]:
        symbol = kwargs.get("symbol")
        if symbol is None:
            raise PermanentError("BinanceKlineLoader.parse: symbol required")
        out: list[dict[str, Any]] = []
        for k in raw:
            # Binance kline tuple shape:
            # [openTime, open, high, low, close, volume, closeTime, quoteVolume,
            #  numTrades, takerBuyBase, takerBuyQuote, ignored]
            if k[6] - k[0] != self.INTERVAL_MS - 1:
                # Ignore the in-progress (incomplete) bar — closeTime - openTime
                # for a complete 1m bar is exactly 59999 ms.
                continue
            out.append({
                "symbol": symbol,
                "ts": datetime.fromtimestamp(k[0] / 1000.0, tz=timezone.utc),
                "open": Decimal(str(k[1])),
                "high": Decimal(str(k[2])),
                "low": Decimal(str(k[3])),
                "close": Decimal(str(k[4])),
                "volume": Decimal(str(k[5])),
                "quote_volume": Decimal(str(k[7])),
                "trade_count": int(k[8]),
                "taker_buy_volume": Decimal(str(k[9])),
                "taker_buy_quote_volume": Decimal(str(k[10])),
            })
        return out

    async def paginate(
        self,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Yield page-sized lists of parsed rows until end_ts is reached."""
        cursor = start_ts
        while cursor < end_ts:
            page = await self.fetch_with_retry(symbol=symbol, start_ts=cursor, end_ts=end_ts)
            rows = self.parse(page, symbol=symbol)
            if not rows:
                logger.bind(symbol=symbol, cursor=cursor.isoformat()).warning(
                    "empty page from binance klines — advancing cursor"
                )
                cursor += timedelta(minutes=1000)
                continue
            yield list(rows)
            # Advance past the last bar's open time + 1 minute.
            last_ts = rows[-1]["ts"]
            cursor = last_ts + timedelta(minutes=1)


# ─────────────────────────── funding rate ───────────────────────────

class BinanceFundingLoader(BaseLoader):
    """Fetch perpetual funding rate history. Binance futures (USD-M)."""

    source = "binance"
    dataset = "funding_rates"
    rate_limit = _DEFAULT_RATE

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch(  # type: ignore[override]
        self,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        params = {
            "symbol": symbol,
            "startTime": int(start_ts.timestamp() * 1000),
            "endTime": int(end_ts.timestamp() * 1000),
            "limit": limit,
        }
        return await _get_json(self._client, _BASE_FUTURES, "/fapi/v1/fundingRate", params)

    def parse(self, raw: list[dict[str, Any]], **kwargs: Any) -> Sequence[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in raw:
            out.append({
                "symbol": r["symbol"],
                "ts": datetime.fromtimestamp(r["fundingTime"] / 1000.0, tz=timezone.utc),
                "rate": Decimal(str(r["fundingRate"])),
                "mark_price": Decimal(str(r["markPrice"])) if r.get("markPrice") else None,
            })
        return out


# ─────────────────────────── open interest ───────────────────────────

class BinanceOpenInterestLoader(BaseLoader):
    """Fetch open-interest history from Binance futures (5m granularity is the densest available)."""

    source = "binance"
    dataset = "open_interest"
    rate_limit = _DEFAULT_RATE

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch(  # type: ignore[override]
        self,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
        period: str = "5m",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        params = {
            "symbol": symbol,
            "period": period,
            "startTime": int(start_ts.timestamp() * 1000),
            "endTime": int(end_ts.timestamp() * 1000),
            "limit": limit,
        }
        return await _get_json(self._client, _BASE_FUTURES, "/futures/data/openInterestHist", params)

    def parse(self, raw: list[dict[str, Any]], **kwargs: Any) -> Sequence[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in raw:
            out.append({
                "symbol": r["symbol"],
                "ts": datetime.fromtimestamp(r["timestamp"] / 1000.0, tz=timezone.utc),
                "oi_contracts": Decimal(str(r["sumOpenInterest"])),
                "oi_quote": Decimal(str(r["sumOpenInterestValue"])),
            })
        return out


# ─────────────────────────── trades (aggTrades) ───────────────────────────

class BinanceAggTradesLoader(BaseLoader):
    """Fetch aggregate trades. Slightly less granular than raw trades but
    Binance's recommended cursor for backfill (raw trades isn't paginated by time).
    """

    source = "binance"
    dataset = "trades"
    rate_limit = _DEFAULT_RATE

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch(  # type: ignore[override]
        self,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        params = {
            "symbol": symbol,
            "startTime": int(start_ts.timestamp() * 1000),
            "endTime": int(end_ts.timestamp() * 1000),
            "limit": limit,
        }
        return await _get_json(self._client, _BASE_SPOT, "/api/v3/aggTrades", params)

    def parse(self, raw: list[dict[str, Any]], **kwargs: Any) -> Sequence[dict[str, Any]]:
        symbol = kwargs.get("symbol")
        if symbol is None:
            raise PermanentError("BinanceAggTradesLoader.parse: symbol required")
        out: list[dict[str, Any]] = []
        for r in raw:
            out.append({
                "symbol": symbol,
                "ts": datetime.fromtimestamp(r["T"] / 1000.0, tz=timezone.utc),
                "trade_id": int(r["a"]),
                "price": Decimal(str(r["p"])),
                "quantity": Decimal(str(r["q"])),
                "is_buyer_maker": bool(r["m"]),
            })
        return out
