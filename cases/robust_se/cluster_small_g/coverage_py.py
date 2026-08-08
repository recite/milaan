"""Coverage of statsmodels' cluster-robust interval as the cluster count falls.

Companion to ``coverage_r.R``. See NOTES.md for the joint table and what it
means; the short version is that statsmodels offers no CR2 equivalent, and its
interval covers 0.730 where estimatr's covers 0.963.
"""

import numpy as np
import statsmodels.api as sm
from scipy import stats as st

TRUTH = 0.5
REPS = 600
TAU = 0.6
PER_CLUSTER = 30


def draw(n_clusters: int, rng: np.random.Generator) -> tuple[np.ndarray, ...]:
    """Draw a Moulton design: cluster-level regressor, cluster-level error.

    The two are independent, so OLS is unbiased for TRUTH and the only thing at
    stake is the standard error. Letting the cluster effect enter both ``x`` and
    ``y`` instead would make it an omitted variable, and coverage would fall
    towards zero as clusters are added -- a broken simulation rather than a
    broken package, and worth naming because it is the easy mistake here.

    Args:
        n_clusters: Number of clusters.
        rng: Source of randomness.

    Returns:
        tuple: outcome, regressor and cluster label arrays.
    """
    x_cluster = rng.standard_normal(n_clusters)
    err_cluster = rng.standard_normal(n_clusters) * TAU
    x = np.repeat(x_cluster, PER_CLUSTER)
    labels = np.repeat(np.arange(n_clusters), PER_CLUSTER)
    y = TRUTH * x + np.repeat(err_cluster, PER_CLUSTER) + rng.standard_normal(x.size)
    return y, x, labels


def coverage(n_clusters: int, reps: int = REPS, seed: int = 11) -> tuple[float, float]:
    """Coverage using the normal critical value and a t_{G-1} one.

    Args:
        n_clusters: Number of clusters.
        reps: Replicates.
        seed: Seed for the generator.

    Returns:
        tuple of float: coverage with z, and with t_{G-1}.
    """
    rng = np.random.default_rng(seed)
    hits_z = hits_t = 0
    for _ in range(reps):
        y, x, labels = draw(n_clusters, rng)
        fit = sm.OLS(y, sm.add_constant(x)).fit(
            cov_type="cluster", cov_kwds={"groups": labels}
        )
        err = abs(fit.params[1] - TRUTH)
        hits_z += err <= 1.959964 * fit.bse[1]
        hits_t += err <= st.t.ppf(0.975, n_clusters - 1) * fit.bse[1]
    return hits_z / reps, hits_t / reps


if __name__ == "__main__":
    grid = (5, 10, 20, 40)
    header = "".join(f"{f'G={g}':>8}" for g in grid)
    print(f"{'method':<32}{header}")
    with_z, with_t = zip(*(coverage(g) for g in grid), strict=True)
    print(f"{'statsmodels cluster + z':<32}" + "".join(f"{c:>8.3f}" for c in with_z))
    print(f"{'statsmodels cluster + t_{G-1}':<32}" + "".join(f"{c:>8.3f}" for c in with_t))
    print(f"\nREPS={REPS}, nominal 0.95, 3-sigma band +/- {3*np.sqrt(.95*.05/REPS):.3f}")
