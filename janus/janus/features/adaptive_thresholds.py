"""Adaptive (online) quantile estimation via the P² algorithm.

Why this exists (UPGRADES §1.1):
- Fixed thresholds (e.g. "$200M liquidations is a cascade") rot. Crypto market
  cap doubled then halved over 2022-2025. The dollar amount that constituted
  an extreme event in 2022 is a yawn in 2024.
- We want thresholds expressed as quantiles ("liquidations in the top 5% of
  the trailing 90 days") so the strategy auto-recalibrates.
- Storing the full window O(N) and recomputing the quantile every tick is
  wasteful. The P² algorithm (Jain & Chlamtac, 1985) gives an O(1)-per-update,
  O(1)-memory estimate of any quantile with bounded error.

The estimator is *biased* during the warm-up (first ~5 samples). We expose a
`samples_seen` accessor so callers can refuse to act before warm-up.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class P2Quantile:
    """Single-quantile P² estimator.

    Reference: Jain, R., Chlamtac, I. (1985). The P² Algorithm for Dynamic
    Calculation of Quantiles and Histograms Without Storing Observations.
    Communications of the ACM, 28(10).
    """

    p: float           # target quantile in (0, 1)
    n: list[int]       # marker positions (1-indexed in the paper, 0-indexed here)
    np: list[float]    # desired marker positions
    dn: list[float]    # increment of desired marker positions per observation
    q: list[float]     # marker heights
    samples_seen: int  # total observations consumed

    @classmethod
    def make(cls, p: float) -> "P2Quantile":
        if not 0.0 < p < 1.0:
            raise ValueError(f"p must be in (0, 1), got {p}")
        return cls(
            p=p,
            n=[0, 1, 2, 3, 4],
            np=[0.0, 2.0 * p, 4.0 * p, 2.0 + 2.0 * p, 4.0],
            dn=[0.0, p / 2.0, p, (1.0 + p) / 2.0, 1.0],
            q=[],
            samples_seen=0,
        )

    def update(self, x: float) -> None:
        self.samples_seen += 1

        # Warm-up: collect first 5 observations sorted.
        if len(self.q) < 5:
            self.q.append(x)
            if len(self.q) == 5:
                self.q.sort()
            return

        # Find cell k such that q[k] <= x < q[k+1].
        if x < self.q[0]:
            self.q[0] = x
            k = 0
        elif x >= self.q[4]:
            self.q[4] = x
            k = 3
        else:
            k = 0
            for i in range(4):
                if self.q[i] <= x < self.q[i + 1]:
                    k = i
                    break

        # Increment marker positions and desired positions.
        for i in range(k + 1, 5):
            self.n[i] += 1
        for i in range(5):
            self.np[i] += self.dn[i]

        # Adjust heights of internal markers if needed.
        for i in (1, 2, 3):
            d = self.np[i] - self.n[i]
            if (d >= 1 and self.n[i + 1] - self.n[i] > 1) or (
                d <= -1 and self.n[i - 1] - self.n[i] < -1
            ):
                d_int = 1 if d >= 0 else -1
                qp = _parabolic(self, i, d_int)
                if self.q[i - 1] < qp < self.q[i + 1]:
                    self.q[i] = qp
                else:
                    self.q[i] = _linear(self, i, d_int)
                self.n[i] += d_int

    @property
    def value(self) -> float:
        """Current quantile estimate. Returns NaN before warm-up completes."""
        if len(self.q) < 5:
            return float("nan")
        return self.q[2]

    @property
    def is_warm(self) -> bool:
        return len(self.q) >= 5


def _parabolic(est: P2Quantile, i: int, d: int) -> float:
    qi = est.q[i]
    qim1 = est.q[i - 1]
    qip1 = est.q[i + 1]
    ni = est.n[i]
    nim1 = est.n[i - 1]
    nip1 = est.n[i + 1]
    return qi + d / (nip1 - nim1) * (
        (ni - nim1 + d) * (qip1 - qi) / (nip1 - ni)
        + (nip1 - ni - d) * (qi - qim1) / (ni - nim1)
    )


def _linear(est: P2Quantile, i: int, d: int) -> float:
    return est.q[i] + d * (est.q[i + d] - est.q[i]) / (est.n[i + d] - est.n[i])


@dataclass
class RollingQuantile:
    """A P² quantile bound to a strategy's threshold knob.

    Wraps `P2Quantile` and exposes the methods used by signal modules:
      * `feed(x)` — add an observation
      * `is_above_quantile(x)` — predicate after warm-up
    """

    estimator: P2Quantile
    min_warmup: int = 200       # don't act on the estimate until this many obs

    @classmethod
    def make(cls, p: float, min_warmup: int = 200) -> "RollingQuantile":
        return cls(estimator=P2Quantile.make(p), min_warmup=min_warmup)

    def feed(self, x: float) -> None:
        self.estimator.update(x)

    def threshold(self) -> float | None:
        if self.estimator.samples_seen < self.min_warmup:
            return None
        return self.estimator.value

    def is_above(self, x: float) -> bool:
        t = self.threshold()
        return t is not None and x >= t
