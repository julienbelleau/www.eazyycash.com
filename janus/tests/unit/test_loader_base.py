"""Tests for the base loader: idempotency hash, retries, lifecycle.

We don't hit the DB here — `record_*` and `archive_raw` are tested in
integration. The unit tests focus on the deterministic / pure parts:
content-hash determinism, ULID-ish ID format, retry behavior on transient
errors.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.data.loaders.base import BaseLoader, content_hash, new_job_id
from janus.errors import ExchangeUnavailableError, RateLimitedError


def test_content_hash_is_order_independent() -> None:
    a = {"x": 1, "y": [2, 3]}
    b = {"y": [2, 3], "x": 1}
    assert content_hash(a) == content_hash(b)


def test_content_hash_distinguishes_payloads() -> None:
    assert content_hash({"x": 1}) != content_hash({"x": 2})


@given(st.dictionaries(st.text(min_size=1, max_size=8), st.integers(), max_size=10))
def test_content_hash_is_64_hex(payload: dict[str, int]) -> None:
    h = content_hash(payload)
    assert len(h) == 64
    int(h, 16)  # parses as hex


def test_new_job_id_is_unique() -> None:
    ids = {new_job_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_new_job_id_fits_varchar32() -> None:
    assert len(new_job_id()) <= 32


# ─── retry behavior ───

class _CountingLoader(BaseLoader):
    source = "fake"
    dataset = "fake_ds"
    rate_limit = (1000, 1.0)  # effectively no rate limit in tests

    def __init__(self, fail_n: int, exc_cls: type[Exception]) -> None:
        super().__init__()
        self.fail_n = fail_n
        self.exc_cls = exc_cls
        self.calls = 0

    async def fetch(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        if self.calls <= self.fail_n:
            raise self.exc_cls("transient")
        return {"ok": True, "call": self.calls}

    def parse(self, raw: Any, **kwargs: Any) -> Sequence[dict[str, Any]]:
        return [raw]


@pytest.mark.asyncio()
async def test_retry_on_transient_then_success() -> None:
    loader = _CountingLoader(fail_n=3, exc_cls=RateLimitedError)
    out = await loader.fetch_with_retry()
    assert out == {"ok": True, "call": 4}
    assert loader.calls == 4


@pytest.mark.asyncio()
async def test_retry_gives_up_eventually() -> None:
    loader = _CountingLoader(fail_n=99, exc_cls=ExchangeUnavailableError)
    with pytest.raises(ExchangeUnavailableError):
        await loader.fetch_with_retry()
    # tenacity stop_after_attempt(5) → 5 calls then bubble up.
    assert loader.calls == 5
