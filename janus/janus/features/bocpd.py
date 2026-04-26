"""Bayesian Online Changepoint Detection (Adams & MacKay, 2007).

Why this exists (UPGRADES §1.4):
- The simple "rate-of-change of liquidations < 10% of peak for 5 minutes"
  rule from the original plan is a lagging exhaustion signal — by the
  time it triggers, the bottom is often 20-40 minutes in the past.
- BOCPD models the run-length distribution. When the underlying generative
  parameters of the liquidation series change abruptly (i.e. the cascade
  ends), the run-length posterior collapses, giving an earlier signal.

Implementation notes:
- Univariate Gaussian model with Normal-Gamma conjugate prior.
- Hazard function is constant (1/lambda) — exponential prior on run lengths.
- This is the standard "BOCPD with conjugate prior" formulation; we keep the
  state vectors trimmed to a bounded length (default 256) to keep memory O(1).

This module is intentionally dependency-free — only stdlib + numpy. Property
tested in tests/strategies/test_bocpd.py to confirm the run-length posterior
collapses on a synthetic mean shift.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _student_t_logpdf(x: float, mu: float, kappa: float, alpha: float, beta: float) -> float:
    """Log-pdf of the Student-t predictive distribution under Normal-Gamma prior."""
    nu = 2.0 * alpha
    var = beta * (kappa + 1.0) / (alpha * kappa)
    # Constants (avoid scipy import).
    from math import lgamma, log, pi
    z = (x - mu) ** 2 / var
    log_norm = (
        lgamma((nu + 1.0) / 2.0)
        - lgamma(nu / 2.0)
        - 0.5 * log(nu * pi * var)
    )
    return log_norm - ((nu + 1.0) / 2.0) * log(1.0 + z / nu)


@dataclass
class Bocpd:
    """Online Bayesian changepoint detector with Normal-Gamma conjugate prior.

    Public API:
        b = Bocpd.make(hazard_lambda=200.0)
        for x in stream:
            b.update(x)
            if b.run_length_map < SHORT:
                # changepoint very recent
                ...
    """

    hazard_lambda: float
    mu0: float
    kappa0: float
    alpha0: float
    beta0: float

    # State tensors (length == current max run length + 1).
    mu: np.ndarray
    kappa: np.ndarray
    alpha: np.ndarray
    beta: np.ndarray
    rl_probs: np.ndarray   # P(r_t = i | x_{1:t})

    max_rl: int = 256
    samples_seen: int = 0

    @classmethod
    def make(
        cls,
        hazard_lambda: float = 200.0,
        mu0: float = 0.0,
        kappa0: float = 1.0,
        alpha0: float = 1.0,
        beta0: float = 1.0,
        max_rl: int = 256,
    ) -> "Bocpd":
        return cls(
            hazard_lambda=hazard_lambda,
            mu0=mu0, kappa0=kappa0, alpha0=alpha0, beta0=beta0,
            mu=np.array([mu0]),
            kappa=np.array([kappa0]),
            alpha=np.array([alpha0]),
            beta=np.array([beta0]),
            rl_probs=np.array([1.0]),
            max_rl=max_rl,
        )

    def update(self, x: float) -> None:
        # Predictive log-prob of x under each run-length hypothesis.
        log_pred = np.array([
            _student_t_logpdf(x, self.mu[i], self.kappa[i], self.alpha[i], self.beta[i])
            for i in range(len(self.rl_probs))
        ])
        pred = np.exp(log_pred - log_pred.max())  # numerical stability

        h = 1.0 / self.hazard_lambda
        growth = self.rl_probs * pred * (1.0 - h)
        cp = (self.rl_probs * pred * h).sum()

        new_rl = np.concatenate(([cp], growth))
        new_rl /= new_rl.sum()

        # Update sufficient statistics conjugately.
        new_mu = np.concatenate(([self.mu0], (self.kappa * self.mu + x) / (self.kappa + 1.0)))
        new_kappa = np.concatenate(([self.kappa0], self.kappa + 1.0))
        new_alpha = np.concatenate(([self.alpha0], self.alpha + 0.5))
        new_beta = np.concatenate((
            [self.beta0],
            self.beta + (self.kappa * (x - self.mu) ** 2) / (2.0 * (self.kappa + 1.0)),
        ))

        # Bound state size — keep the most-likely tail.
        if len(new_rl) > self.max_rl:
            keep = self.max_rl
            new_rl = new_rl[:keep]
            new_mu = new_mu[:keep]
            new_kappa = new_kappa[:keep]
            new_alpha = new_alpha[:keep]
            new_beta = new_beta[:keep]
            new_rl /= new_rl.sum()

        self.rl_probs = new_rl
        self.mu = new_mu
        self.kappa = new_kappa
        self.alpha = new_alpha
        self.beta = new_beta
        self.samples_seen += 1

    @property
    def run_length_map(self) -> int:
        """MAP estimate of the current run length (modes of the posterior)."""
        return int(np.argmax(self.rl_probs))

    @property
    def changepoint_probability(self) -> float:
        """P(run_length == 0) — i.e. probability the most recent point is a CP."""
        return float(self.rl_probs[0])
