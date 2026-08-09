"""Gate the rdrobust probe against its registered claim.

The estimator is R's. The verdict is simcheck's, so the tolerance comes from the
replicate count rather than from anything chosen in ``probe.R``.

Three things are checked, in the order they have to be believed:

1. the sensitivity condition of PROTOCOL.md 3a -- the Conventional arm must
   under-cover, or this DGP never exercised the bias the Robust interval exists
   to survive and no verdict on it is meaningful;
2. the registered claim, that the Robust interval covers;
3. width, reported for every arm, because coverage alone cannot distinguish a
   valid interval from an enormous one.

``probe.R`` must have written ``results.json.gz`` first.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
from simcheck import MonteCarloResult, assert_coverage, binomial_band

HERE = Path(__file__).parent
RESULTS = HERE / "results.json.gz"
ARMS = {"conventional": "conv", "robust": "robust"}


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


def rows_for(data: dict, n: int) -> list[dict]:
    """Successful replicates at one sample size.

    A replicate where rdrobust errored is dropped and counted separately rather
    than silently treated as a miss, which would read as broken coverage.

    Args:
        data: The parsed results file.
        n: Sample size.

    Returns:
        list: The replicate records.
    """
    return [r for r in data["replicates"] if r["n"] == n and not r["failed"]]


def cell(data: dict, n: int, arm: str) -> MonteCarloResult:
    """Assemble one arm at one sample size into a result simcheck can gate.

    Args:
        data: The parsed results file.
        n: Sample size.
        arm: ``conventional`` or ``robust``.

    Returns:
        MonteCarloResult: Estimates, standard errors and coverage flags.
    """
    prefix = ARMS[arm]
    rows = rows_for(data, n)
    truth = data["truth"]
    lower = np.array([r[f"{prefix}_lo"] for r in rows])
    upper = np.array([r[f"{prefix}_hi"] for r in rows])
    return MonteCarloResult(
        estimates=np.array([r[f"{prefix}_est"] for r in rows]),
        standard_errors=np.array([r[f"{prefix}_se"] for r in rows]),
        covered=(lower <= truth) & (truth <= upper),
        rejected=None,
        truth=truth,
    )


def mean_width(data: dict, n: int, arm: str) -> float:
    """Mean interval width for one arm at one sample size.

    Computed here because simcheck does not retain interval endpoints.
    PROTOCOL.md forbids reporting coverage without width.

    Args:
        data: The parsed results file.
        n: Sample size.
        arm: ``conventional`` or ``robust``.

    Returns:
        float: Mean width.
    """
    prefix = ARMS[arm]
    rows = rows_for(data, n)
    return float(np.mean([r[f"{prefix}_hi"] - r[f"{prefix}_lo"] for r in rows]))


def sensitivity(data: dict) -> tuple[bool, list[int]]:
    """Did this DGP actually exercise the bias the robust interval addresses?

    The registered condition: the Conventional arm must under-cover -- fall
    below simcheck's band -- at a majority of sweep points.

    Args:
        data: The parsed results file.

    Returns:
        tuple: Whether the condition is met, and the sizes where it under-covers.
    """
    under = []
    for n in data["grid"]:
        low, _ = binomial_band(data["level"], len(rows_for(data, n)))
        if cell(data, n, "conventional").coverage < low:
            under.append(n)
    return len(under) > len(data["grid"]) / 2, under


def test_the_probe_exercised_the_failure_mode_it_claims_to_test() -> None:
    """PROTOCOL.md 3a. Must hold before any verdict on the robust arm counts.

    If the conventional interval covers fine at the MSE-optimal bandwidth, the
    bias that motivates the robust interval was never present, and reporting
    the robust arm as passing would claim something this run did not test.
    """
    data = load()
    met, under = sensitivity(data)
    assert met, (
        "instrument sensitivity unmet: the Conventional arm under-covers only at "
        f"{under or 'no'} sample sizes out of {data['grid']}. This DGP is too "
        "smooth to test the claim; the probe is UNINFORMATIVE, not a pass."
    )


def test_robust_bias_corrected_ci_covers_at_the_selected_bandwidth() -> None:
    """The registered claim, gated."""
    data = load()
    for n in data["grid"]:
        assert_coverage(
            cell(data, n, "robust"), data["level"], label=f"rdrobust Robust, n={n}"
        )


if __name__ == "__main__":
    data = load()
    env = data["env"]
    print(f"{data['probe']}  |  rdrobust {env['rdrobust']}, {env['r']}")
    print(
        f"truth={data['truth']}, nominal {data['level']}, "
        f"{data['reps_per_cell']} replicates per cell, seed {data['seed']}\n"
    )
    header = (
        f"{'n':>7}{'ok':>7}{'mean h':>9}"
        f"{'Conv cover':>12}{'width':>9}{'Robust cover':>14}{'width':>9}"
    )
    print(header)
    for n in data["grid"]:
        rows = rows_for(data, n)
        low, high = binomial_band(data["level"], len(rows))
        print(
            f"{n:>7}{len(rows):>7}{np.mean([r['h'] for r in rows]):>9.4f}"
            f"{cell(data, n, 'conventional').coverage:>12.4f}"
            f"{mean_width(data, n, 'conventional'):>9.4f}"
            f"{cell(data, n, 'robust').coverage:>14.4f}"
            f"{mean_width(data, n, 'robust'):>9.4f}"
        )
    low, high = binomial_band(data["level"], data["reps_per_cell"])
    print(f"\nsimcheck 3-sigma band: [{low:.4f}, {high:.4f}]")
    met, under = sensitivity(data)
    print(
        f"instrument sensitivity: {'MET' if met else 'NOT MET'} "
        f"(Conventional under-covers at n={under or 'none'})"
    )
