# Stablecoin Stress Flow strategy — rationale

## 1. What inefficiency does the strategy exploit?

When a major stablecoin (USDC, USDT, DAI) micro-depegs by 0.1-0.5%, a
measurable portion of capital flees toward BTC/ETH within 30-180 minutes.
That flow is observable on-chain (exchange inflows of BTC, increase in
BTC/USDT vs BTC/USDC volume share). The flow front-runs the broader market's
re-pricing of the depeg event by ~30-90 minutes; we long BTC spot to capture
the flow before it's reflected in price.

## 2. Why does this inefficiency exist?

- **Composability friction.** The capital fleeing the stressed stablecoin
  doesn't move atomically. It hops: holder → DEX → swap to USDC/USDT → CEX
  → BTC. Each hop has minutes-of-friction and a portion of holders cut their
  hops short by going straight to BTC perps or spot, telegraphing the flow.
- **Risk-management asymmetry.** Treasury desks and OTC market makers run
  hard limits on stablecoin exposure. A 15-bp depeg triggers automated
  rebalancing that's slow (hours) but mechanical (predictable).
- **News-driven retail panic.** Twitter chatter amplifies the depeg framing;
  retail capital drains the stressed stablecoin disproportionally. The
  resulting BTC inflow is detectable from on-chain data ~10-20 minutes
  before exchange order books reflect it.

## 3. Why hasn't this already been arbitraged away?

- **Sub-100ms HFT firms can't do this trade.** The signal is on-chain,
  with 10-30 second blockchain latency. The trade is held for 1-6 hours.
  Neither end of that horizon matches HFT business models.
- **Rare events.** ~30-100 events over the past 4 years. Rare enough that
  building a dedicated team for it is a mismatched ROI for most quant shops.
- **Edge is borderline.** Net edge of ~30 bps after fees is *exactly* the
  zone where most discretionary traders give up — it's "annoying" rather
  than "obvious".

## 4. When will this inefficiency disappear?

- **CEX-DEX arbitrage gets faster.** A meaningful chunk of crypto trading
  is now MEV-bot driven; if those bots start consuming stablecoin-stress
  flow systematically, our 30-90 minute window compresses to <10 minutes
  and the trade dies.
- **Depegs stop being newsworthy.** If the next 12 months produce no major
  depeg event, retail panic conditioning fades and the flow magnitude
  shrinks below our edge floor.
- **A stablecoin gets a real run.** A *true* break-the-peg (USDT going
  to 0.95 and staying) would change the trade entirely — this strategy
  is calibrated to micro-depegs, not solvency events. Watch the issuer
  treasury ratio; sub-100% is the kill switch.

## 5. Known failure modes

- **Slow flow / fast arb.** Our 30-90 min window assumes flow lags arb. In
  recent years that's been compressing. The 45-minute clock in
  STRESS_PENDING is the trip-wire: if flow signal hasn't fired by then,
  the trade is stale.
- **False stress.** A glitchy DEX oracle prints a fake depeg → we detect
  stress that doesn't exist → we don't enter (flow signal won't fire).
  The strategy is *long-only* which is the natural risk control here.
- **Funding already priced.** When perps are already pricing in the flow
  (positive funding term structure), our edge collapses. We refuse to
  enter when `funding_already_priced` is true (UPGRADES §3.4).
- **Pool-depth blowup.** A 30-bp depeg in a $5M pool is a different beast
  from the same depeg in a $500M pool. Pool depth severity (UPGRADES §3.1)
  scales the urgency. We're calibrated for $200M+ pools; thinner pools
  should disable the strategy at the regime level.
- **Time stop reverses.** A 6h hold could see the depeg reverse and recover
  past entry by hour 7 — we miss the upside. Acceptable: this strategy is
  about *consistent small wins*, not capturing tails.
