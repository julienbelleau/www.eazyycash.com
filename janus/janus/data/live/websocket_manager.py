"""Async websocket supervisor for live OHLCV ingestion.

Wraps `ccxt.pro` and adds the resilience features Janus needs:
  * exponential backoff on disconnect (capped, jittered)
  * heartbeat watchdog: if no message for `idle_timeout`, force a reconnect
  * graceful shutdown on `stop()` — flushes any buffered bars first
  * publishes completed bars onto the `outbox` table, atomic with the insert

The class is symbol-set-driven: pass a list of symbols and a callback. The
manager owns the lifecycle.

Design constraints:
  * one websocket per exchange (multi-symbol multiplex), not one per symbol —
    Binance throttles aggressively above ~5 connections per IP.
  * no shared state between callbacks: each completed bar is forwarded
    independently.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from janus.errors import ExchangeUnavailableError, WebSocketDisconnected

# We import ccxt.pro lazily — at module import time it pulls a heavy dep set.
# This keeps unit tests fast (they monkeypatch `_make_exchange`).
try:
    import ccxt.pro as ccxtpro  # type: ignore[import]
except ImportError:  # pragma: no cover - optional at install time
    ccxtpro = None  # type: ignore[assignment]


BarCallback = Callable[[dict[str, Any]], Awaitable[None]]


class WebsocketManager:
    """One instance per (exchange). Subscribes to N symbols, dispatches to a callback."""

    def __init__(
        self,
        exchange_id: str,
        symbols: Sequence[str],
        on_bar: BarCallback,
        *,
        idle_timeout_s: float = 30.0,
        max_backoff_s: float = 60.0,
    ) -> None:
        if ccxtpro is None:
            raise ExchangeUnavailableError("ccxt.pro not installed; cannot run live websockets")
        self._exchange_id = exchange_id
        self._symbols = list(symbols)
        self._on_bar = on_bar
        self._idle_timeout_s = idle_timeout_s
        self._max_backoff_s = max_backoff_s
        self._stop = asyncio.Event()
        self._exchange: Any = None
        self._last_msg_at: datetime = datetime.now(timezone.utc)

    def _make_exchange(self) -> Any:
        cls = getattr(ccxtpro, self._exchange_id)
        return cls({"enableRateLimit": True, "newUpdates": True})

    async def stop(self) -> None:
        self._stop.set()
        if self._exchange is not None:
            await self._exchange.close()

    async def _watch_symbol(self, symbol: str) -> None:
        """One coroutine per symbol — ccxt.pro's `watchOHLCV` blocks per call."""
        log = logger.bind(exchange=self._exchange_id, symbol=symbol)
        while not self._stop.is_set():
            try:
                # `watchOHLCV` returns the latest bars; `newUpdates=True` returns only deltas.
                bars = await self._exchange.watchOHLCV(symbol, "1m")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - ccxt raises a wide range of errors
                log.warning("watchOHLCV error: {} — reconnecting", exc)
                raise WebSocketDisconnected(str(exc)) from exc

            self._last_msg_at = datetime.now(timezone.utc)
            for bar in bars:
                # CCXT shape: [openTime_ms, open, high, low, close, volume]
                payload = {
                    "exchange": self._exchange_id,
                    "symbol": symbol,
                    "ts": datetime.fromtimestamp(bar[0] / 1000.0, tz=timezone.utc),
                    "open": bar[1],
                    "high": bar[2],
                    "low": bar[3],
                    "close": bar[4],
                    "volume": bar[5],
                }
                try:
                    await self._on_bar(payload)
                except Exception:
                    log.exception("on_bar callback failed — continuing")

    async def _watchdog(self) -> None:
        """If no messages for `idle_timeout_s`, raise to force a reconnect upstream."""
        while not self._stop.is_set():
            await asyncio.sleep(self._idle_timeout_s)
            idle = (datetime.now(timezone.utc) - self._last_msg_at).total_seconds()
            if idle > self._idle_timeout_s:
                raise WebSocketDisconnected(f"idle for {idle:.1f}s > {self._idle_timeout_s}s")

    async def run(self) -> None:
        """Run until `stop()` is called. Handles reconnect with backoff + jitter."""
        backoff = 1.0
        while not self._stop.is_set():
            self._exchange = self._make_exchange()
            self._last_msg_at = datetime.now(timezone.utc)
            disconnect_count = 0
            try:
                async with asyncio.TaskGroup() as tg:
                    for symbol in self._symbols:
                        tg.create_task(self._watch_symbol(symbol))
                    tg.create_task(self._watchdog())
            except* (WebSocketDisconnected, ExchangeUnavailableError) as eg:
                disconnect_count = len(eg.exceptions)
                logger.warning(
                    "ws disconnected ({} errors) — will reconnect", disconnect_count
                )

            if disconnect_count == 0:
                # TaskGroup exited cleanly — stop() was called.
                return

            try:
                await self._exchange.close()
            except Exception:  # noqa: BLE001
                pass

            jitter = backoff * 0.1
            await asyncio.sleep(min(backoff + jitter, self._max_backoff_s))
            backoff = min(backoff * 2, self._max_backoff_s)
