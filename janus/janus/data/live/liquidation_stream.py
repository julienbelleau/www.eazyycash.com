"""Live liquidation stream — Binance forceOrder websocket.

The Binance USD-M futures stream `<symbol>@forceOrder` (or `!forceOrder@arr`
for all symbols) emits one message per liquidation. We:
  * subscribe to the all-symbols stream
  * buffer events for `flush_interval_s` (1s default) — this matches our
    1-minute bar rollup cadence and avoids a write-amplification storm
  * batch-insert into `liquidations` and atomically append to `outbox`

For Phase 0 we only validate that the stream parses correctly; the actual
DB writer is wired up in Phase 1 when the Refractory strategy consumes it.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from loguru import logger

from janus.errors import ExchangeUnavailableError, WebSocketDisconnected

# We use raw websocket access (websockets package transitively via httpx-ws or
# similar). To keep the dep surface small in Phase 0, we use a thin httpx-based
# long-poll fallback for now — the real ws client lands when Phase 1 begins.
# The shape of the parsed event is stable, so consumers can be written today.

_BINANCE_WS_HOST = "wss://fstream.binance.com/ws/!forceOrder@arr"


def parse_force_order_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Translate a Binance forceOrder payload into a `liquidations` row dict.

    Returns None if the payload is structurally invalid (defensive — we never
    crash on a malformed message, we drop it and log).
    """
    o = raw.get("o") or {}
    try:
        ts_ms = int(o["T"])
        symbol = str(o["s"])
        side_raw = str(o["S"])
        price = Decimal(str(o["p"]))
        qty = Decimal(str(o["q"]))
    except (KeyError, ValueError, TypeError):
        return None

    # Binance reports the *order* side. A liquidated long is closed via a SELL
    # order; a liquidated short is closed via a BUY. Invert here so consumers
    # can read "liquidated side" directly.
    side = "long" if side_raw == "SELL" else "short"

    return {
        "symbol": symbol,
        "ts": datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc),
        "side": side,
        "price": price,
        "quantity": qty,
        "notional_usd": price * qty,
        "source_order_id": str(o.get("c") or o.get("i") or ""),
    }


async def stream_force_orders(
    *,
    url: str = _BINANCE_WS_HOST,
    client: httpx.AsyncClient | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield parsed liquidation events from Binance's forceOrder stream.

    Phase 0 ships a placeholder: a real websocket client is added when
    the Refractory strategy lands. The interface is fixed so consumer code
    written today still works after the swap.
    """
    raise NotImplementedError(
        "stream_force_orders: real websocket client lands in Phase 1. "
        "Use parse_force_order_event() to test parsing today."
    )
    # Unreachable but keeps the AsyncIterator type contract:
    if False:  # pragma: no cover
        yield {}
