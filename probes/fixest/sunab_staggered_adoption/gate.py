"""Gate the sunab probe against its registered claims.

Three things, in the order they have to be believed:

1. the estimand check registered as ``estimand_hazard`` -- sunab's ``agg="att"``
   averages over the relative periods it estimates, and if that set does not
   cover every treated cell the truth is the wrong target and any "bias" is an
   estimand mismatch;
2. the sensitivity condition of PROTOCOL.md 3a -- two-way fixed effects on the
   identical replicates must be badly biased, or the failure sunab exists to
   fix was never present;
3. the two registered claims, unbiasedness and coverage, gated separately
   because the first is a theorem about weights and the second is an asymptotic
   approximation.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
from simcheck import MonteCarloResult, assert_coverage, assert_unbiased, binomial_band

HERE = Path(__file__).parent
RESULTS = HERE / "results.json.gz"
Z = 1.959964


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


def rows_for(data: dict, n_units: int) -> list[dict]:
    """Successful replicates at one panel size.

    Args:
        data: The parsed results file.
        n_units: Number of units.

    Returns:
        list: The replicate records.
    """
    return [
        r for r in data["replicates"] if r["n_units"] == n_units and not r["failed"]
    ]


def cell(data: dict, n_units: int, se: str = "cluster") -> MonteCarloResult:
    """Assemble one panel size into a result simcheck can gate.

    The truth varies slightly by replicate because it is computed from the
    realised treated cells, so coverage is evaluated per replicate against its
    own truth and ``MonteCarloResult.truth`` carries the common mean.

    Args:
        data: The parsed results file.
        n_units: Number of units.
        se: ``cluster`` or ``default``.

    Returns:
        MonteCarloResult: Estimates, standard errors and coverage flags.
    """
    rows = rows_for(data, n_units)
    est = np.array([r["est"] for r in rows])
    truth = np.array([r["truth"] for r in rows])
    err = np.array([r[f"se_{se}"] for r in rows])
    return MonteCarloResult(
        estimates=est,
        standard_errors=err,
        covered=np.abs(est - truth) <= Z * err,
        rejected=None,
        truth=float(truth.mean()),
    )


def twfe_bias(data: dict, n_units: int) -> float:
    """Mean bias of the two-way fixed effects coefficient at one panel size.

    Args:
        data: The parsed results file.
        n_units: Number of units.

    Returns:
        float: Mean estimate minus mean truth.
    """
    rows = [r for r in rows_for(data, n_units) if r["twfe"] is not None]
    return float(np.mean([r["twfe"] - r["truth"] for r in rows]))


def test_the_estimand_matches_what_sunab_targets() -> None:
    """The hazard registered in preregistration.yaml, checked rather than assumed.

    sunab's aggregate averages over the relative periods it estimates. If those
    did not cover every treated cell, the truth computed here would be the wrong
    target and the "bias" below would be an estimand mismatch dressed up as a
    finding.
    """
    data = load()
    bad = [r for r in data["replicates"] if not r["failed"] and not r["estimand_ok"]]
    assert not bad, (
        f"{len(bad)} replicates where sunab's estimated relative periods did not "
        "cover every treated cell; the truth is not the estimator's target"
    )


def test_the_probe_exercised_the_failure_mode_it_claims_to_test() -> None:
    """PROTOCOL.md 3a. TWFE must be badly biased on this data, or nothing is tested."""
    data = load()
    for n in data["grid"]:
        bias = twfe_bias(data, n)
        assert bias < -1.0, (
            f"TWFE bias at n_units={n} is only {bias:+.3f}; the staggered-adoption "
            "failure sunab exists to fix is not present, so the probe is "
            "UNINFORMATIVE rather than a pass"
        )


def test_sunab_is_unbiased_for_the_att() -> None:
    """Registered claim (a). A theorem about weights, so expected to hold exactly."""
    data = load()
    for n in data["grid"]:
        assert_unbiased(cell(data, n), label=f"sunab ATT, n_units={n}")


def test_sunab_interval_covers() -> None:
    """Registered claim (b), for both standard-error variants."""
    data = load()
    for n in data["grid"]:
        for se in ("cluster", "default"):
            assert_coverage(
                cell(data, n, se), data["level"], label=f"sunab {se} SE, n_units={n}"
            )


if __name__ == "__main__":
    data = load()
    env = data["env"]
    print(f"{data['probe']}  |  fixest {env['fixest']}, {env['r']}")
    print(f"nominal {data['level']}, {data['reps_per_cell']} replicates per cell\n")
    print(
        f"{'units':>6}{'truth':>8}{'sunab':>9}{'bias':>9}{'TWFE':>9}{'TWFE bias':>11}"
    )
    for n in data["grid"]:
        rows = rows_for(data, n)
        t = float(np.mean([r["truth"] for r in rows]))
        e = float(np.mean([r["est"] for r in rows]))
        w = float(np.mean([r["twfe"] for r in rows if r["twfe"] is not None]))
        print(f"{n:>6}{t:>8.3f}{e:>9.3f}{e - t:>9.3f}{w:>9.3f}{w - t:>11.3f}")

    print(
        f"\n{'units':>6}{'sd(est)':>10}{'SE default':>12}{'SE cluster':>12}"
        f"{'cov default':>13}{'cov cluster':>13}"
    )
    for n in data["grid"]:
        rows = rows_for(data, n)
        print(
            f"{n:>6}{np.std([r['est'] for r in rows], ddof=1):>10.4f}"
            f"{np.mean([r['se_default'] for r in rows]):>12.4f}"
            f"{np.mean([r['se_cluster'] for r in rows]):>12.4f}"
            f"{cell(data, n, 'default').coverage:>13.3f}"
            f"{cell(data, n, 'cluster').coverage:>13.3f}"
        )
    low, high = binomial_band(data["level"], data["reps_per_cell"])
    print(f"\nsimcheck 3-sigma band: [{low:.4f}, {high:.4f}]")
