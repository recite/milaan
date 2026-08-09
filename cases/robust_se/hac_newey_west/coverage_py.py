"""Coverage of the Newey-West interval under a DGP whose truth we set.

Companion to ``coverage_r.R``; see the "Which convention should you use?"
section of NOTES.md for what the numbers mean.
"""

import numpy as np
import pytest
import statsmodels.api as sm
from simcheck import assert_proportion

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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The finding. Kernel HAC standard errors are consistent, not unbiased, "
        "and their nominal level is a large-sample promise. At T=1000 -- which "
        "feels like plenty of data -- the interval covers ~0.88 against a "
        "nominal 0.95, and it is still short at T=4000. strict=True so that if "
        "statsmodels ever gains prewhitening or a data-driven bandwidth, this "
        "starts passing and CI forces the case to be rewritten."
    ),
)
def test_hac_interval_covers_at_a_thousand_observations() -> None:
    """The claim, gated. This file printed a table and asserted nothing.

    A study with no assertion cannot fail, so it was documentation rather than
    a check: statsmodels could have regressed arbitrarily far and nothing here
    would have noticed. The rate is now gated by simcheck, whose band comes
    from the replicate count.
    """
    _lags, rate = coverage(1000)
    assert_proportion(rate, REPS, 0.95, label="statsmodels HAC lag rule, T=1000")


def test_coverage_improves_with_the_series_length() -> None:
    """The part that is not a defect, asserted so it stays true.

    HAC is consistent, so the shortfall must shrink as T grows. If it ever
    stopped doing so the story in NOTES.md -- slow convergence rather than a
    broken estimator -- would be wrong, and that is worth catching.
    """
    # Fewer replicates than the rate test above, deliberately: this asserts an
    # ordering, not a rate, and the gap it checks (~0.79 against ~0.90) is an
    # order of magnitude wider than the Monte Carlo noise at 200. The T=4000
    # fits are what cost the time.
    _, short = coverage(100, reps=200)
    _, long = coverage(4000, reps=200)
    assert long > short, (
        f"coverage did not improve with T: {short:.3f} at T=100 against "
        f"{long:.3f} at T=4000, which contradicts consistency"
    )


if __name__ == "__main__":
    print(f"{'T':>6} {'lags':>5} {'n_eff':>7} {'coverage':>9}")
    for n_obs in (100, 250, 500, 1000, 4000):
        lags, cov = coverage(n_obs)
        n_eff = n_obs * (1 - RHO) / (1 + RHO)
        print(f"{n_obs:>6} {lags:>5} {n_eff:>7.0f} {cov:>9.3f}")
