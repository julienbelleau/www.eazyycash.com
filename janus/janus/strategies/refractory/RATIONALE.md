# Refractory-Period strategy — rationale

CLAUDE.md mandates that every strategy answers the five questions below. Any
significant change to the strategy must update this file in the same commit.

## 1. What inefficiency does the strategy exploit?

After a leveraged liquidation cascade, the marginal trader who was driving
price (the leveraged perps trader) is *gone* — financially wiped or risk-off.
The order book during the immediate aftermath (≈30 min – 24h) is therefore
dominated by spot players and slow takers, both of whom mean-revert by
nature. The strategy buys spot at the exhaustion of the cascade and exits
when leverage repopulates (open interest recovers, funding normalises).

## 2. Why does this inefficiency exist (economic thesis)?

Three structural reasons:

1. **Leverage liquidation has irreversible cost.** The wiped margin is gone;
   re-funding accounts takes hours-to-days (CEX wire delays, recoupling
   strategies, psychological capitulation). The marginal pool of leverage is
   measurably thinner during this window.
2. **Risk parity / vol-target funds reduce gross.** When realised vol spikes,
   institutional vol-targeting algos cut crypto exposure — and they're slow
   to re-add it (typically waiting for the next monthly rebalance).
3. **Market makers widen spreads briefly during cascades**, then re-tighten as
   they realise the inventory imbalance is profitable. This re-tightening
   *itself* is mean-reverting price action.

## 3. Why hasn't this already been arbitraged away?

- **Capacity.** The signal triggers maybe 15-40 times/year on BTC at usable
  size. Total annual P&L for a $100M book is in the low single-digit millions.
  That's beneath the radar of true high-frequency firms but plenty for a
  solo book.
- **Identification difficulty.** "When does the cascade end?" is not trivial.
  Naïve "rate-of-change of liquidations < 10% peak" rules trigger 20-40
  minutes late. Our BOCPD + OFI + multi-criteria gating tightens the entry,
  which is what creates the edge.
- **Discomfort.** Long entries during peak fear are psychologically expensive.
  Discretionary traders pay an emotional premium to *not* take this trade.

## 4. When will this inefficiency disappear (signals to watch)?

- **Net-long perps OI no longer collapses during cascades.** Today, OI drops
  8-15% during a typical cascade. If that compresses to <3%, the pool of
  forced sellers is too thin to mean-revert from.
- **Liquidation cascades stop happening.** A regulatory cap on perps leverage
  (e.g. EU/US 5x cap) would eliminate the prerequisite of the strategy.
- **Spot dominance shrinks below 30% of CEX volume.** Already at ~40% as of
  mid-2025; if perps continue to take share, the spot demand we're capturing
  becomes too small relative to ambient noise.

## 5. Known failure modes

- **Macro contagion masquerading as a cascade.** A Fed-shock, equity crash,
  or stablecoin run can produce all the *measurable* features of a leveraged
  cascade while actually being a regime change. Our regime layer (Phase 4)
  is supposed to gate these out; until then, the time stop and SL must hold.
- **Single-asset bug.** Coinglass aggregation outage = our liq feed goes to
  zero, the cascade never "registers", we miss every entry. Cross-source
  validation + dead-letter monitoring catches this. The strategy must
  continue to require *all* features to be fresh (data quality job).
- **Over-fitting on historical cascades.** 2022 LUNA, 2022 FTX, 2024 yen-carry
  — these are unrepresentatively large events that anchor backtests. We
  require a stress test removing the top 5% of trades; if the strategy
  becomes unprofitable, the edge is event-dependent rather than structural.
- **Slow exit during fast recovery.** TP at 50% retracement leaves money on
  the table when the V-shape is severe. Trailing stop is the partial fix;
  a future enhancement (Phase 1.5) is conformal-prediction-calibrated TP.
