"""Does statsmodels' cluster-robust interval cover, as the cluster count falls?

Companion to ``coverage_r.R``. The claim under test is the one every confidence
interval makes -- that it contains the truth 95% of the time -- so the gate is
:func:`simcheck.assert_coverage`, whose band comes from the replicate count
rather than from a number chosen by eye. Run as a script it prints the table in
NOTES.md; run under pytest it fails where the claim fails.
"""

from __future__ import annotations

import numpy as np
import pytest
import statsmodels.api as sm
from scipy import stats as st
from simcheck import MonteCarloResult, assert_coverage, binomial_band

TRUTH = 0.5
REPS = 600
TAU = 0.6
PER_CLUSTER = 30
GRID = (5, 10, 20, 40)


def draw(n_clusters: int, rng: np.random.Generator) -> tuple[np.ndarray, ...]:
    """Draw a Moulton design: cluster-level regressor, cluster-level error.

    The two are independent, so OLS is unbiased for TRUTH and the only thing at
    stake is the standard error. Letting the cluster effect enter both ``x`` and
    ``y`` instead makes it an omitted variable, and coverage then falls towards
    zero as clusters are *added* -- a broken simulation rather than a broken
    package, and worth naming because it is the easy mistake in this design.

    Args:
        n_clusters: Number of clusters.
        rng: Source of randomness.

    Returns:
        tuple: outcome, regressor and cluster-label arrays.
    """
    x_cluster = rng.standard_normal(n_clusters)
    err_cluster = rng.standard_normal(n_clusters) * TAU
    x = np.repeat(x_cluster, PER_CLUSTER)
    labels = np.repeat(np.arange(n_clusters), PER_CLUSTER)
    y = TRUTH * x + np.repeat(err_cluster, PER_CLUSTER) + rng.standard_normal(x.size)
    return y, x, labels


def study(n_clusters: int, use_t: bool, seed: int = 11) -> MonteCarloResult:
    """Run the replicates and package them for the simcheck gates.

    Args:
        n_clusters: Number of clusters.
        use_t: Apply a ``t(G-1)`` critical value rather than the normal one that
            statsmodels reports.
        seed: Seed for the generator.

    Returns:
        MonteCarloResult: Estimates, standard errors and coverage flags.
    """
    rng = np.random.default_rng(seed)
    critical = st.t.ppf(0.975, n_clusters - 1) if use_t else 1.959964
    estimates, errors, covered = [], [], []
    for _ in range(REPS):
        y, x, labels = draw(n_clusters, rng)
        fit = sm.OLS(y, sm.add_constant(x)).fit(
            cov_type="cluster", cov_kwds={"groups": labels}
        )
        estimates.append(fit.params[1])
        errors.append(fit.bse[1])
        covered.append(abs(fit.params[1] - TRUTH) <= critical * fit.bse[1])
    return MonteCarloResult(
        estimates=np.array(estimates),
        standard_errors=np.array(errors),
        covered=np.array(covered),
        rejected=None,
        truth=TRUTH,
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The finding. statsmodels cov_type='cluster' is CR1 with a normal "
        "critical value and covers 0.730 at G=5, where estimatr's CR2 covers "
        "0.963. strict=True so that if statsmodels ever ships CR2 the test "
        "starts passing and CI fails, forcing the case to be rewritten."
    ),
)
def test_statsmodels_cluster_interval_covers_with_few_clusters() -> None:
    """The claim, gated. Expected to fail: that is the finding, not a defect here.

    ``cov_type="cluster"`` reports a normal-based interval with CR1-style
    scaling, and statsmodels has no CR2 equivalent. At five clusters it covers
    0.730 against a nominal 0.95, where ``estimatr::lm_robust(se_type="CR2")``
    covers 0.963 on the same design. The assertion is written the way it would be
    written if the claim held, so that the failure message carries the number.
    """
    result = study(5, use_t=False)
    assert_coverage(result, 0.95, label="statsmodels cluster, G=5")


if __name__ == "__main__":
    header = "".join(f"{f'G={g}':>8}" for g in GRID)
    print(f"{'method':<32}{header}")
    for label, use_t in (
        ("statsmodels cluster + z", False),
        ("statsmodels cluster + t_{G-1}", True),
    ):
        rates = [study(g, use_t).coverage for g in GRID]
        print(f"{label:<32}" + "".join(f"{r:>8.3f}" for r in rates))
    low, high = binomial_band(0.95, REPS)
    print(f"\nREPS={REPS}, nominal 0.95, simcheck 3-sigma band [{low:.3f}, {high:.3f}]")
