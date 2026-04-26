"""DefiLlama loader — stablecoin supply / flows.

Phase 0 stub. Implementation lands in Phase 3 (Stablecoin Stress Flow).
DefiLlama's API is free + open; we just don't need it before Phase 3.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from janus.data.loaders.base import BaseLoader


class DefiLlamaStablecoinLoader(BaseLoader):
    source = "defillama"
    dataset = "stablecoin_supply"
    rate_limit = (1, 1.0)  # Free tier — 1 req/sec to be safe.

    async def fetch(self, **kwargs: Any) -> Any:  # type: ignore[override]
        raise NotImplementedError(
            "DefiLlamaStablecoinLoader.fetch is a Phase 0 stub. "
            "Implement in Phase 3 (Stablecoin Stress Flow)."
        )

    def parse(self, raw: Any, **kwargs: Any) -> Sequence[dict[str, Any]]:
        raise NotImplementedError("DefiLlamaStablecoinLoader.parse is a Phase 0 stub.")
