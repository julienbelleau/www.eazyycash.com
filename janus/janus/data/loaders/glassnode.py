"""Glassnode loader — on-chain BTC/ETH metrics.

Phase 0 stub. Implementation lands when on-chain features are first consumed,
in Phase 1 (Refractory uses exchange flows) and Phase 3 (Stablecoin flow).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from janus.data.loaders.base import BaseLoader


class GlassnodeMetricLoader(BaseLoader):
    source = "glassnode"
    dataset = "onchain_metrics"
    rate_limit = (10, 60.0)  # Glassnode T1: very strict — 10 req/min.

    async def fetch(self, **kwargs: Any) -> Any:  # type: ignore[override]
        raise NotImplementedError(
            "GlassnodeMetricLoader.fetch is a Phase 0 stub. "
            "Implement when on-chain features are first consumed (Phase 1/3)."
        )

    def parse(self, raw: Any, **kwargs: Any) -> Sequence[dict[str, Any]]:
        raise NotImplementedError("GlassnodeMetricLoader.parse is a Phase 0 stub.")
