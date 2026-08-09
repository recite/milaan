"""Does statsmodels' default binomial interval contain the truth 95% of the time?

``proportion_confint(count, nobs)`` defaults to ``method="normal"`` -- the Wald
interval. R's two standard entry points default to neither: ``prop.test`` gives
Wilson with a continuity correction and ``binom.test`` gives Clopper-Pearson.

Binomial coverage does not have to be simulated. There are only ``n + 1``
possible outcomes, so summing the binomial mass over those whose interval
contains ``p`` gives coverage exactly. This module computes it both ways and
checks they agree before drawing any conclusion from the simulation -- a
measurement that cannot be cross-checked is a measurement worth distrusting.

Run as a script it prints the tables in NOTES.md. Run under pytest it asserts,
via :func:`simcheck.assert_coverage`, whose band comes from the replicate count.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats as st
from simcheck import Estimate, MonteCarloResult, assert_coverage, monte_carlo
from statsmodels.stats.proportion import proportion_confint

NOMINAL = 0.95
REPS = 4000
METHODS = ("normal", "wilson", "beta", "agresti_coull", "jeffreys")
GRID_N = (20, 50, 100, 200, 500, 1000)
GRID_P = (0.5, 0.2, 0.05, 0.01)


def interval(x: int, n: int, method: str) -> tuple[float, float]:
    """One interval, as a pair of plain floats.

    ``proportion_confint`` is typed for its array-input overload, so pin the
    scalar case here once rather than casting at every call site.

    Args:
        x: Observed successes.
        n: Number of trials.
        method: A ``proportion_confint`` method name.

    Returns:
        tuple: Lower and upper endpoints.
    """
    low, high = np.asarray(
        proportion_confint(x, n, alpha=1 - NOMINAL, method=method), dtype=float
    )
    return float(low), float(high)


def exact_coverage(n: int, p: float, method: str) -> float:
    """Coverage by enumeration rather than by simulation.

    Args:
        n: Number of trials.
        p: True success probability.
        method: A ``proportion_confint`` method name.

    Returns:
        float: The probability that the interval contains ``p``.
    """
    covered = 0.0
    for x in range(n + 1):
        low, high = interval(x, n, method)
        if low <= p <= high:
            covered += float(st.binom.pmf(x, n, p))
    return covered


def study(n: int, p: float, method: str, reps: int = REPS) -> MonteCarloResult:
    """Simulate the same quantity, so the two routes can be compared.

    Args:
        n: Number of trials.
        p: True success probability.
        method: A ``proportion_confint`` method name.
        reps: Replicate count; the gate's tolerance is derived from it.

    Returns:
        MonteCarloResult: Estimates and coverage flags.
    """

    def replicate(rng: np.random.Generator) -> Estimate:
        x = int(rng.binomial(n, p))
        low, high = interval(x, n, method)
        return Estimate(value=x / n, lower=low, upper=high)

    return monte_carlo(replicate, truth=p, reps=reps, seed=7)


def test_the_simulation_agrees_with_the_exact_answer() -> None:
    """Validate the instrument before believing anything it reports.

    Coverage here is computable in closed form, so the simulated estimate has a
    known target. If these disagreed, every number below would be suspect and
    the disagreement -- not the package -- would be the finding.
    """
    for n, p, method in (
        (20, 0.01, "normal"),
        (100, 0.05, "normal"),
        (100, 0.5, "wilson"),
    ):
        result = study(n, p, method)
        exact = exact_coverage(n, p, method)
        # Three Monte Carlo standard errors of a proportion at `exact`.
        slack = 3.0 * float(np.sqrt(exact * (1 - exact) / result.reps))
        assert abs(result.coverage - exact) <= slack, (
            f"n={n} p={p} {method}: simulated {result.coverage:.4f} vs "
            f"exact {exact:.4f}, outside {slack:.4f}"
        )


def test_wilson_covers_where_it_should() -> None:
    """The positive control, without which the failing test proves nothing.

    A harness that reports under-coverage for everything is broken rather than
    informative. Wilson at these coordinates is genuinely near nominal, so this
    test must pass for the one below to mean anything.
    """
    assert_coverage(study(100, 0.2, "wilson"), NOMINAL, label="wilson, n=100 p=0.2")


def test_the_default_interval_is_degenerate_at_zero_successes() -> None:
    """The mechanism, stated separately from the coverage number it produces.

    Observe no successes in twenty trials and the default returns ``(0.0, 0.0)``
    -- zero width. It is not a wide interval or a badly centred one; it asserts
    that the proportion is exactly zero, with 95% confidence, from twenty
    observations. Nothing warns. R's ``binom.test(0, 20)`` gives [0, 0.168].
    """
    assert interval(0, 20, "normal") == (0.0, 0.0)
    assert interval(20, 20, "normal") == (1.0, 1.0)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The finding. proportion_confint defaults to method='normal' (Wald), "
        "which returns (0.0, 0.0) at zero successes and covers 0.182 at "
        "p=0.01, n=20. strict=True so that if statsmodels ever changes the "
        "default the test starts passing and CI fails, forcing a rewrite."
    ),
)
def test_statsmodels_default_binomial_interval_covers() -> None:
    """The claim, gated. Expected to fail: that is the finding, not a defect here.

    At p = 0.01 and n = 20 the default covers 0.182. That number is not an
    approximation failure -- it is exactly ``1 - P(x = 0) = 1 - 0.99**20``,
    because every draw that yields no successes produces the degenerate
    interval above and cannot contain any positive p. The assertion is written
    the way it would be written if the claim held, so the failure carries the
    measured rate.
    """
    assert_coverage(
        study(20, 0.01, "normal"), NOMINAL, label="statsmodels default, n=20 p=0.01"
    )


if __name__ == "__main__":
    for p in GRID_P:
        print(f"\n=== true p = {p} ===  exact coverage, nominal {NOMINAL}")
        print(f"{'n':>6}" + "".join(f"{m:>15}" for m in METHODS))
        for n in GRID_N:
            row = [exact_coverage(n, p, m) for m in METHODS]
            print(f"{n:>6}" + "".join(f"{v:>15.3f}" for v in row))

    print("\n=== how often the degenerate interval fires ===")
    print(f"{'n':>6}{'P(x=0 | p=0.01)':>18}{'exact coverage':>16}")
    for n in GRID_N:
        print(
            f"{n:>6}{st.binom.pmf(0, n, 0.01):>18.3f}"
            f"{exact_coverage(n, 0.01, 'normal'):>16.3f}"
        )
