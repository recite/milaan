"""Gate the clubSandwich CR2 probe against its registered claim.

The estimator is R's. The verdict is simcheck's, so the tolerance comes from the
replicate count rather than from anything chosen in ``probe.R``. Run as a script
it prints the table for NOTES.md; run under pytest it asserts.

``probe.R`` must have written ``results.json`` first::

    Rscript --vanilla probe.R results.json
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest
from simcheck import MonteCarloResult, assert_coverage, assert_unbiased, binomial_band

HERE = Path(__file__).parent
RESULTS = HERE / "results.json.gz"


def load() -> dict:
    """Read the probe's output.

    Returns:
        dict: The parsed results file.

    Raises:
        FileNotFoundError: If the probe has not been run.
    """
    if not RESULTS.exists():
        raise FileNotFoundError(
            f"{RESULTS} missing -- run "
            f"`Rscript --vanilla {HERE / 'probe.R'} {RESULTS}` first"
        )
    with gzip.open(RESULTS, "rt") as handle:
        return json.load(handle)


def cell(data: dict, n_clusters: int, arm: str = "cr2") -> MonteCarloResult:
    """Assemble one grid cell into a result simcheck can gate.

    Args:
        data: The parsed results file.
        n_clusters: Which sweep point to select.
        arm: ``cr2`` for the claim under test, ``cr1`` for the context arm.

    Returns:
        MonteCarloResult: Estimates, standard errors and coverage flags.
    """
    rows = [r for r in data["replicates"] if r["n_clusters"] == n_clusters]
    truth = data["truth"]
    lo_key, hi_key = ("lower", "upper") if arm == "cr2" else ("lower_cr1", "upper_cr1")
    lower = np.array([r[lo_key] for r in rows])
    upper = np.array([r[hi_key] for r in rows])
    return MonteCarloResult(
        estimates=np.array([r["estimate"] for r in rows]),
        standard_errors=np.array([r["se"] for r in rows]),
        covered=(lower <= truth) & (truth <= upper),
        rejected=None,
        truth=truth,
    )


def mean_width(data: dict, n_clusters: int, arm: str = "cr2") -> float:
    """Mean interval width for one cell.

    Computed here rather than taken from simcheck, which does not retain
    interval endpoints. PROTOCOL.md forbids reporting coverage without width --
    a vacuous interval covers everything -- so until the width gate lands this
    is the reporting half of that requirement, done by hand.

    Args:
        data: The parsed results file.
        n_clusters: Which sweep point to select.
        arm: ``cr2`` or ``cr1``.

    Returns:
        float: Mean width over the cell's replicates.
    """
    rows = [r for r in data["replicates"] if r["n_clusters"] == n_clusters]
    lo_key, hi_key = ("lower", "upper") if arm == "cr2" else ("lower_cr1", "upper_cr1")
    return float(np.mean([r[hi_key] - r[lo_key] for r in rows]))


def test_ols_is_unbiased_so_the_dgp_is_not_the_finding() -> None:
    """Guard against the omitted-variable version of this design.

    If the cluster effect leaked into x, OLS would be biased and coverage would
    fall as clusters were ADDED -- a broken simulation reported as a broken
    method. This must pass before any coverage number here means anything.
    """
    data = load()
    for g in data["grid"]:
        assert_unbiased(cell(data, g), label=f"OLS slope, G={g}")


def test_cr2_satterthwaite_covers_from_ten_clusters_up() -> None:
    """The registered claim where it holds outright."""
    data = load()
    for g in [g for g in data["grid"] if g >= 10]:
        assert_coverage(cell(data, g), data["level"], label=f"CR2+Satterthwaite, G={g}")


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Recorded, not hidden. CR2 covers 0.9765 at five clusters against a "
        "nominal 0.95 -- conservative, not invalid, and it buys that coverage "
        "with an interval 3.9x wider than CR1's. simcheck's assert_coverage is "
        "two-sided, correctly, because over-coverage costs power. strict=True "
        "so that if the rate ever moves inside the band this stops being true "
        "silently."
    ),
)
def test_cr2_satterthwaite_covers_at_five_clusters() -> None:
    """The one cell where the control missed, split out so the miss is explicit."""
    data = load()
    assert_coverage(cell(data, 5), data["level"], label="CR2+Satterthwaite, G=5")


if __name__ == "__main__":
    data = load()
    env = data["env"]
    print(f"{data['probe']}  |  clubSandwich {env['clubSandwich']}, {env['r']}")
    print(
        f"truth={data['truth']}, nominal {data['level']}, "
        f"{data['reps_per_cell']} replicates per cell, seed {data['seed']}\n"
    )
    low, high = binomial_band(data["level"], data["reps_per_cell"])
    print(f"simcheck 3-sigma band at this replicate count: [{low:.4f}, {high:.4f}]\n")
    header = f"{'G':>5}{'CR2 cover':>12}{'width':>9}{'CR1+z cover':>14}{'width':>9}"
    print(header)
    for g in data["grid"]:
        c2 = cell(data, g, "cr2").coverage
        c1 = cell(data, g, "cr1").coverage
        print(
            f"{g:>5}{c2:>12.4f}{mean_width(data, g, 'cr2'):>9.4f}"
            f"{c1:>14.4f}{mean_width(data, g, 'cr1'):>9.4f}"
        )
