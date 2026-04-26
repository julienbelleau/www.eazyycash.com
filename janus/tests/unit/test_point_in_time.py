"""Point-in-time correctness invariant.

Strategies must NEVER see future data. The repository encodes this via
the `as_of` parameter: when set, no row with ts > as_of is returned.

This test stubs the SQL execution to verify the contract: regardless of
what's in the DB, the WHERE clause is correct. (A separate integration
test exercises the same logic against a real DB.)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from janus.data.repositories.ohlcv_repo import OhlcvRepository


@pytest.mark.asyncio()
async def test_repo_caps_end_at_as_of() -> None:
    """When as_of < end, fetch must use as_of as its upper bound, not end."""
    captured: dict[str, Any] = {}

    async def _exec(sql: Any, params: dict[str, Any]) -> Any:
        captured["params"] = params
        captured["sql"] = str(sql)
        result = MagicMock()
        result.__iter__.return_value = iter([])
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_exec)
    repo = OhlcvRepository(session)

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 31, tzinfo=timezone.utc)
    as_of = datetime(2024, 1, 10, tzinfo=timezone.utc)

    await repo.fetch(symbol="BTCUSDT", start=start, end=end, as_of=as_of)

    assert captured["params"]["end"] == as_of, (
        "as_of must override end when smaller — point-in-time is non-negotiable"
    )


@pytest.mark.asyncio()
async def test_repo_keeps_end_when_as_of_is_later() -> None:
    captured: dict[str, Any] = {}

    async def _exec(sql: Any, params: dict[str, Any]) -> Any:
        captured["params"] = params
        result = MagicMock()
        result.__iter__.return_value = iter([])
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_exec)
    repo = OhlcvRepository(session)

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 10, tzinfo=timezone.utc)
    as_of = datetime(2024, 1, 31, tzinfo=timezone.utc)

    await repo.fetch(symbol="BTCUSDT", start=start, end=end, as_of=as_of)
    assert captured["params"]["end"] == end


@pytest.mark.asyncio()
async def test_repo_rejects_inverted_range() -> None:
    session = MagicMock()
    repo = OhlcvRepository(session)
    with pytest.raises(ValueError, match="must be <="):
        await repo.fetch(
            symbol="BTCUSDT",
            start=datetime(2024, 1, 31, tzinfo=timezone.utc),
            end=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio()
async def test_repo_routes_resolution_to_correct_table() -> None:
    captured: dict[str, str] = {}

    async def _exec(sql: Any, params: dict[str, Any]) -> Any:
        captured["sql"] = str(sql)
        result = MagicMock()
        result.__iter__.return_value = iter([])
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_exec)
    repo = OhlcvRepository(session)

    base_kwargs: dict[str, Any] = {
        "symbol": "BTCUSDT",
        "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "end": datetime(2024, 1, 2, tzinfo=timezone.utc),
    }

    await repo.fetch(**base_kwargs, resolution="1m")
    assert "ohlcv_1m" in captured["sql"]
    assert " ts " in captured["sql"]  # base table column is `ts`

    await repo.fetch(**base_kwargs, resolution="1h")
    assert "ohlcv_1h" in captured["sql"]
    assert "bucket" in captured["sql"]  # CAGG column is `bucket`
