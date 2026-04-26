# Narrative Rotation strategy — rationale

## 1. What inefficiency does the strategy exploit?

Crypto capital rotates between *narratives* (AI, RWA, DePIN, memes, L2s) on
attention-driven cycles. The leader of an active narrative gets crowded; the
2nd-derivative of its momentum (acceleration) turns negative weeks before
the leader visibly underperforms. Capital reallocates to a narrative with
positive-and-accelerating momentum — and we capture the early phase of that
new leader's run.

## 2. Why does this inefficiency exist?

- **Attention is a finite resource.** Crypto Twitter, retail-driven flow,
  and even allocator capital chase the narrative-of-the-month. A narrative's
  marginal buyer changes character (early-conviction → late-momentum →
  speculative tail) faster than fundamentals catch up.
- **Information asymmetry between code and price.** Real dev activity
  (GitHub commits, contract deployments) precedes price action by 2-4 weeks.
  A narrative whose dev activity is climbing while price is mid-pack is the
  high-probability candidate for the next rotation.
- **No structural arbitrage.** Quant funds that *could* trade this generally
  refuse equity in mid-cap altcoins (governance / custody / liquidity
  concerns). The cap-and-bond constraints they face leave the rotation alpha
  available to nimble capital.

## 3. Why hasn't this already been arbitraged away?

- **Identification cost.** "Which narrative is emerging?" is a hard inference
  problem when done correctly (look-ahead-free tag snapshots, beta-decomposed
  returns, dev-activity confirmation). Most retail-facing services oversimplify
  to the point of being noise.
- **Capacity ceiling.** Mid-cap baskets cap out at $2-10M deployable per
  position before our own footprint becomes visible. Capacity-aware sizing
  (UPGRADES §2.5) is the mechanical guard.
- **Holding period vs. quant rebalance cycles.** 30-60 day holds don't fit
  weekly-rebalanced systematic vehicles. Discretionary funds with longer
  horizons are the natural competitors but they're slow to identify rotation.

## 4. When will this inefficiency disappear?

- **Tokenized index products at scale.** A liquid "crypto narrative ETF" with
  active rebalancing would arbitrage the 2nd-derivative signal away. Watch:
  successful launches of multi-narrative indices on regulated venues.
- **Stable narrative duration.** If narratives stop rotating (i.e. one or two
  themes monopolise capital flow for >12 months), the strategy has no work
  to do. Watch: narrative-flow concentration metric — currently bouncing in
  3-6 month cycles.
- **Pure on-chain capital flow data becomes mainstream.** Once "this much USDC
  is moving from wallet cluster X to cluster Y" is a one-click view, the
  emergent-signal lead time compresses.

## 5. Known failure modes

- **Sector contagion.** When BTC dumps 20%, every narrative's index dumps too.
  Beta decomposition (UPGRADES §2.3) reduces but doesn't eliminate this — we
  add a regime gate to disarm the strategy in `Crisis/Cascade` regime.
- **Fake rotation / dead-cat bounce.** A narrative shows 3 days of accelerating
  momentum then resumes its decline. The 60-day time stop and the -15% basket
  stop bound the damage.
- **Tag drift.** A token's category changes mid-trade (e.g. a "DeFi" project
  pivots to "AI"). Snapshots are immutable per UPGRADES §2.4 — a mid-trade
  reclassification doesn't affect the position.
- **Capacity bug.** If we're holding a basket totalling >5% of the daily
  volume of any constituent, the capacity-aware sizing has been bypassed.
  Production-mode invariant: refuse the order at the execution layer.
