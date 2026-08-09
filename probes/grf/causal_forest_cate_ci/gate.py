"""Gate the grf causal-forest probe against its registered claims.

Coverage is evaluated separately at each fixed test point. Within one replicate
the five predictions are dependent, so pooling them would understate the
variance of the coverage estimate; across replicates at a FIXED point they are
independent, which is what simcheck's band assumes.

The ATE arm is an internal control rather than a rival: it is the well-behaved
doubly-robust quantity, so if it failed too, suspicion belongs on the harness
before the method.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
from simcheck import MonteCarloResult, assert_coverage, binomial_band

HERE = Path(__file__).parent
RESULTS = HERE / "results.json.gz"
Z = 1.959964


def load() -> dict:
    """Read the probe's output.

    Returns:
        dict: The parsed results file.

    Raises:
        FileNotFoundError: If the probe has not been run.
        ValueError: If the run never finished, so cells are short of their
            registered replicate counts.
    """
    if not RESULTS.exists():
        raise FileNotFoundError(
            f"{RESULTS} missing -- run "
            f"`Rscript --vanilla {HERE / 'probe.R'} {RESULTS}` first"
        )
    with gzip.open(RESULTS, "rt") as handle:
        data = json.load(handle)
    if not data.get("complete"):
        raise ValueError(
            "results.json.gz is from an interrupted run. The probe checkpoints "
            "every 25 replicates, so partial files are expected -- re-run the "
            "same command and it resumes. Gating a short cell would report a "
            "rate at a replicate count the registration did not specify."
        )
    return data


def rows_for(data: dict, n: int) -> list[dict]:
    """Successful replicates at one sample size.

    Args:
        data: The parsed results file.
        n: Sample size.

    Returns:
        list: The replicate records.
    """
    return [r for r in data["replicates"] if r["n"] == n and not r.get("failed")]


def cell(data: dict, n: int, point: int) -> MonteCarloResult:
    """One test point at one sample size.

    Args:
        data: The parsed results file.
        n: Sample size.
        point: Index into the test-point grid.

    Returns:
        MonteCarloResult: Estimates, standard errors and coverage flags.
    """
    rows = rows_for(data, n)
    truth = data["truth"][point]
    est = np.array([r["est"][point] for r in rows])
    err = np.array([r["se"][point] for r in rows])
    return MonteCarloResult(
        estimates=est,
        standard_errors=err,
        covered=np.abs(est - truth) <= Z * err,
        rejected=None,
        truth=float(truth),
    )


def ate_cell(data: dict, n: int) -> MonteCarloResult:
    """The ATE arm at one sample size.

    Args:
        data: The parsed results file.
        n: Sample size.

    Returns:
        MonteCarloResult: Estimates, standard errors and coverage flags.
    """
    rows = rows_for(data, n)
    truth = float(data["ate_truth"])
    est = np.array([r["ate_est"] for r in rows])
    err = np.array([r["ate_se"] for r in rows])
    return MonteCarloResult(
        estimates=est,
        standard_errors=err,
        covered=np.abs(est - truth) <= Z * err,
        rejected=None,
        truth=truth,
    )


def test_the_effect_varies_across_the_test_points() -> None:
    """Registered sensitivity condition.

    If the true effect were flat, the pointwise claim would collapse into the
    ATE claim and would not be separately tested.
    """
    data = load()
    truth = data["truth"]
    assert max(truth) - min(truth) > 1.0, (
        f"true effect spans only {max(truth) - min(truth):.3f} across the test "
        "points; the pointwise claim is not separately exercised, so the probe "
        "is UNINFORMATIVE rather than a pass"
    )


def test_the_ate_arm_covers() -> None:
    """The internal control. If this failed, suspect the harness first."""
    data = load()
    for n in [p["n"] for p in data["plan"]]:
        assert_coverage(ate_cell(data, n), data["level"], label=f"grf ATE, n={n}")


def test_pointwise_cate_intervals_cover() -> None:
    """The registered claim. Predicted to FAIL; see NOTES.md for the verdict."""
    data = load()
    for n in [p["n"] for p in data["plan"]]:
        for i, x1 in enumerate(data["x1_test"]):
            assert_coverage(
                cell(data, n, i), data["level"], label=f"grf CATE n={n}, x1={x1}"
            )


if __name__ == "__main__":
    data = load()
    env = data["env"]
    print(f"{data['probe']}  |  grf {env['grf']}, {env['r']}")
    print(
        f"nominal {data['level']}, {data['num_trees']} trees, dim {data['dimension']}\n"
    )

    head = f"{'n':>6}{'reps':>6}" + "".join(f"{f'x1={x}':>10}" for x in data["x1_test"])
    print(head + f"{'ATE':>10}")
    for spec in data["plan"]:
        n = spec["n"]
        rows = rows_for(data, n)
        cov = [cell(data, n, i).coverage for i in range(len(data["x1_test"]))]
        print(
            f"{n:>6}{len(rows):>6}"
            + "".join(f"{c:>10.3f}" for c in cov)
            + f"{ate_cell(data, n).coverage:>10.3f}"
        )

    print(f"\n{'n':>6}  3-sigma band at that cell's replicate count")
    for spec in data["plan"]:
        low, high = binomial_band(data["level"], len(rows_for(data, spec["n"])))
        print(f"{spec['n']:>6}  [{low:.4f}, {high:.4f}]")

    print(f"\n{'n':>6}" + "".join(f"{f'bias x1={x}':>13}" for x in data["x1_test"]))
    for spec in data["plan"]:
        n = spec["n"]
        biases = [cell(data, n, i).bias for i in range(len(data["x1_test"]))]
        print(f"{n:>6}" + "".join(f"{b:>13.4f}" for b in biases))
