"""Coverage of the Newey-West interval under a DGP whose truth we set.

Companion to ``coverage_r.R``; see the "Which convention should you use?"
section of NOTES.md for what the numbers mean.
"""

import numpy as np
import statsmodels.api as sm

TRUTH = 0.5
RHO = 0.8
REPS = 1000


def ar1(n: int, rho: float, rng: np.random.Generator) -> np.ndarray:
    """Draw a stationary AR(1) series.

    Args:
        n: Length.
        rho: Autoregressive coefficient.
        rng: Source of randomness.

    Returns:
        np.ndarray: The series, started from its stationary distribution.
    """
    innovations = rng.standard_normal(n)
    out = np.empty(n)
    out[0] = innovations[0] / np.sqrt(1 - rho**2)
    for i in range(1, n):
        out[i] = rho * out[i - 1] + innovations[i]
    return out


def coverage(n_obs: int, reps: int = REPS, seed: int = 7) -> tuple[int, float]:
    """Coverage of the nominal 95% HAC interval at one sample size.

    Uses the Newey-West lag rule ``floor(4 * (T/100)^(2/9))``, which statsmodels
    does not apply for you -- ``cov_type="HAC"`` without ``maxlags`` raises -- but
    which is the number most users copy in.

    Args:
        n_obs: Series length.
        reps: Replicates.
        seed: Seed for the generator.

    Returns:
        tuple: The lag count used and the measured coverage.
    """
    rng = np.random.default_rng(seed)
    lags = int(np.floor(4 * (n_obs / 100) ** (2 / 9)))
    hits = 0
    for _ in range(reps):
        x = ar1(n_obs, RHO, rng)
        y = TRUTH * x + ar1(n_obs, RHO, rng)
        fit = sm.OLS(y, sm.add_constant(x)).fit(
            cov_type="HAC", cov_kwds={"maxlags": lags}
        )
        hits += abs(fit.params[1] - TRUTH) <= 1.96 * fit.bse[1]
    return lags, hits / reps


if __name__ == "__main__":
    print(f"{'T':>6} {'lags':>5} {'n_eff':>7} {'coverage':>9}")
    for n_obs in (100, 250, 500, 1000, 4000):
        lags, cov = coverage(n_obs)
        n_eff = n_obs * (1 - RHO) / (1 + RHO)
        print(f"{n_obs:>6} {lags:>5} {n_eff:>7.0f} {cov:>9.3f}")
