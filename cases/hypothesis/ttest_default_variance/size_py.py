"""What false-positive rate does ``scipy.stats.ttest_ind`` actually run at?

``ttest_ind(a, b)`` defaults to ``equal_var=True`` -- the pooled Student test.
R's ``t.test(a, b)`` defaults to ``var.equal = FALSE`` -- Welch. Same function
in each user's head, opposite assumption underneath, and nothing warns.

When the variances differ and the groups are different sizes, the pooled test's
size is not 0.05. Which way it goes depends on which group carries the larger
variance: if it is the smaller group the test rejects far too often, if it is
the larger group it barely rejects at all. The gate is
:func:`simcheck.assert_count_rate`, whose band comes from the replicate count.

Run as a script it prints the tables in NOTES.md; run under pytest it asserts.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import ttest_ind
from simcheck import assert_count_rate

ALPHA = 0.05
REPS = 20000
SEED = 5


def rejections(n1: int, n2: int, sd1: float, sd2: float, *, equal_var: bool) -> int:
    """How many of ``REPS`` replicates reject, with the null true in every one.

    Both groups are drawn with mean zero, so every rejection is a false
    positive. Only the variances and the group sizes differ.

    Args:
        n1: Size of the first group.
        n2: Size of the second group.
        sd1: Standard deviation of the first group.
        sd2: Standard deviation of the second group.
        equal_var: ``True`` for the pooled Student test scipy defaults to,
            ``False`` for Welch, which is what R defaults to.

    Returns:
        int: Number of replicates rejecting at ``ALPHA``.
    """
    rng = np.random.default_rng(SEED)
    a = rng.normal(0.0, sd1, (REPS, n1))
    b = rng.normal(0.0, sd2, (REPS, n2))
    # Unpacked rather than reached for by attribute: the scipy stub does not
    # declare `.pvalue` on TtestResult, while the tuple interface is stable.
    _statistic, pvalues = ttest_ind(a, b, axis=1, equal_var=equal_var)
    return int((np.asarray(pvalues) < ALPHA).sum())


def test_both_tests_hold_their_size_when_the_assumption_is_met() -> None:
    """The sanity check: with equal variances the default is fine.

    Without this the finding below could be read as "the pooled test is broken",
    which it is not. It is correct under its own assumption, and the assumption
    is simply not one the API asks about.
    """
    for equal_var in (True, False):
        label = "pooled" if equal_var else "welch"
        assert_count_rate(
            rejections(10, 30, 1.0, 1.0, equal_var=equal_var),
            REPS,
            ALPHA,
            label=f"{label}, equal variances",
        )


def test_welch_holds_its_size_when_the_assumption_is_not_met() -> None:
    """The positive control, and the reason the finding is worth reporting.

    Welch is measured on the identical design at the identical seed. If it also
    failed, the honest conclusion would be that unequal variances are hard
    rather than that the default is the wrong one.
    """
    assert_count_rate(
        rejections(10, 100, 4.0, 1.0, equal_var=False),
        REPS,
        ALPHA,
        label="welch, n=(10,100) sd=(4,1)",
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The finding. scipy.stats.ttest_ind defaults to equal_var=True and "
        "rejects 44% of the time under a true null at n=(10,100), sd=(4,1). "
        "strict=True so that if scipy ever changes this default the test starts "
        "passing and CI fails, forcing the case to be rewritten -- a corpus "
        "about silent staleness must not go stale silently."
    ),
)
def test_scipy_default_ttest_holds_its_nominal_size() -> None:
    """The claim, gated. Expected to fail: that is the finding, not a defect here.

    Ten observations with sd 4 against a hundred with sd 1, means equal, so
    every rejection is a false positive. The default rejects 44% of the time at
    a nominal 5%. The assertion is written the way it would be written if the
    claim held, so the failure message carries the measured rate.
    """
    assert_count_rate(
        rejections(10, 100, 4.0, 1.0, equal_var=True),
        REPS,
        ALPHA,
        label="scipy default, n=(10,100) sd=(4,1)",
    )


if __name__ == "__main__":
    print(f"True null in every cell. Nominal alpha = {ALPHA}, {REPS} replicates.\n")

    print("Which group carries the larger variance decides the direction:")
    print(
        f"{'n1':>5}{'n2':>6}{'sd1':>6}{'sd2':>6}{'scipy default':>16}{'Welch (R)':>12}"
    )
    for n1, n2, sd1, sd2 in (
        (10, 10, 1, 1),
        (10, 10, 1, 4),
        (10, 30, 1, 1),
        (10, 30, 4, 1),
        (10, 30, 1, 4),
        (20, 60, 4, 1),
        (5, 45, 4, 1),
        (10, 100, 4, 1),
    ):
        pooled = rejections(n1, n2, sd1, sd2, equal_var=True) / REPS
        welch = rejections(n1, n2, sd1, sd2, equal_var=False) / REPS
        print(f"{n1:>5}{n2:>6}{sd1:>6}{sd2:>6}{pooled:>16.4f}{welch:>12.4f}")

    print("\nHolding the small group fixed and adding data only to the large one:")
    print(f"{'n1':>5}{'n2':>6}{'total':>8}{'scipy default':>16}{'Welch (R)':>12}")
    for n2 in (10, 20, 30, 60, 100, 300, 1000):
        pooled = rejections(10, n2, 4.0, 1.0, equal_var=True) / REPS
        welch = rejections(10, n2, 4.0, 1.0, equal_var=False) / REPS
        print(f"{10:>5}{n2:>6}{10 + n2:>8}{pooled:>16.4f}{welch:>12.4f}")
