"""Macro features used by the regime detector (UPGRADES §4.2).

Crypto regimes are not independent of the macro state. Pivots in Fed policy,
DXY, or US 10Y yields routinely flip crypto from one regime to another.
Including these as features helps the HMM correctly classify Crisis/Cascade
vs. Trending Bear and Recovery vs. Range.

Phase 0 ships the *interface* — actual ingestion of FRED / Yahoo Finance is
out of scope until Phase 4 deployment, where it lands as another loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np


MacroSeriesId = Literal["DXY", "VIX", "US10Y", "GOLD", "SP500"]


@dataclass(frozen=True, slots=True)
class MacroPanel:
    """Aligned daily panel of macro series.

    Each ndarray is a daily series (most recent at the end).
    """

    dates: np.ndarray  # dtype=object (Python date)
    dxy: np.ndarray
    vix: np.ndarray
    us10y: np.ndarray
    gold: np.ndarray
    sp500: np.ndarray


def macro_log_returns(panel: MacroPanel) -> dict[MacroSeriesId, np.ndarray]:
    """Daily log returns for each non-rate series; absolute change for US10Y."""
    out: dict[MacroSeriesId, np.ndarray] = {}
    for sid, series in (("DXY", panel.dxy), ("VIX", panel.vix),
                        ("GOLD", panel.gold), ("SP500", panel.sp500)):
        if len(series) < 2:
            out[sid] = np.array([])
            continue
        ratios = np.clip(series[1:] / series[:-1], 1e-9, None)
        out[sid] = np.log(ratios)
    out["US10Y"] = np.diff(panel.us10y) if len(panel.us10y) >= 2 else np.array([])
    return out


def append_macro_to_features(
    feature_matrix: np.ndarray,
    panel: MacroPanel,
) -> np.ndarray:
    """Concatenate macro log returns to the existing feature matrix.

    The caller is responsible for date-aligning beforehand. We assume the
    panel and feature_matrix share the same row index after alignment.
    """
    rets = macro_log_returns(panel)
    # Align lengths to the shortest macro series.
    if not rets:
        return feature_matrix
    n = min(len(v) for v in rets.values() if len(v) > 0)
    if n == 0:
        return feature_matrix
    macro_block = np.column_stack([
        rets["DXY"][-n:], rets["VIX"][-n:], rets["US10Y"][-n:],
        rets["GOLD"][-n:], rets["SP500"][-n:],
    ])
    if feature_matrix.shape[0] != n:
        # Trim feature matrix to the macro length (most recent n rows).
        feature_matrix = feature_matrix[-n:]
    return np.column_stack([feature_matrix, macro_block])
