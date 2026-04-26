"""Coinglass loader — aggregated liquidations across exchanges.

Phase 0 stub. Full implementation lands together with the Refractory Period
strategy (Phase 1), where liquidation flow is the primary signal.

The interface is fixed so the strategy code can already be written against
it. Calling fetch/parse raises NotImplementedError loudly — tests pin this.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from janus.data.loaders.base import BaseLoader


class CoinglassLiquidationLoader(BaseLoader):
    source = "coinglass"
    dataset = "liquidations"
    rate_limit = (5, 1.0)  # Coinglass paid tier; conservative until benchmarked.

    async def fetch(self, **kwargs: Any) -> Any:  # type: ignore[override]
        raise NotImplementedError(
            "CoinglassLiquidationLoader.fetch is a Phase 0 stub. "
            "Implement when Phase 1 (Refractory) is started."
        )

    def parse(self, raw: Any, **kwargs: Any) -> Sequence[dict[str, Any]]:
        raise NotImplementedError(
            "CoinglassLiquidationLoader.parse is a Phase 0 stub."
        )
