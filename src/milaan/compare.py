"""Turn a set of backend results into classified, expectation-checked findings.

The classification is deliberately blunt -- three bands on relative difference --
because the interesting judgment is not "how different" but "is this difference
already understood". That judgment lives in `case.yaml` as an expected verdict plus
a required reason, and this module's job is to detect when reality has drifted away
from what was written down.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations

from milaan.schema import CaseSpec, Result

#: Verdicts on a single quantity, ordered from best to worst. `compare` reports
#: the worst verdict across all backend pairs, so one divergent pair is enough to
#: mark the quantity divergent.
VERDICT_ORDER = ["AGREE", "NUMERIC", "DIVERGE"]

#: Outcomes of checking an observed verdict against the declared expectation.
EXPECTED = "EXPECTED"
NEW_FINDING = "NEW_FINDING"
RESOLVED = "RESOLVED"
UNCOMPARABLE = "UNCOMPARABLE"


def relative_difference(a: float, b: float, floor: float = 1e-12) -> float:
    """Return the scale-free difference between two values.

    Uses `|a - b| / max(|a|, |b|, floor)` so that the measure is meaningful for
    both a coefficient near 1 and a variance near 1e-9, and does not blow up when
    both values are zero.

    The floor is also a noise floor, not only a guard against dividing by zero:
    when *both* values fall below it they are treated as equal. Without that,
    comparing a denormal-scale result against an exact zero -- 8.2e-16 against
    0.0, say, which is what one scikit-learn version returns where another
    returns zero exactly -- divides by the floor and reports a relative
    difference of 8e-4, flagging two numbers that are zero for every purpose as
    divergent.

    Args:
        a: First value.
        b: Second value.
        floor: Scale below which two values are indistinguishable, and the lower
            bound on the denominator.

    Returns:
        Relative difference. `0.0` if both are NaN or both are below the floor,
        `inf` if exactly one is NaN or the two differ in sign of infinity.
    """
    a_nan, b_nan = math.isnan(a), math.isnan(b)
    if a_nan and b_nan:
        return 0.0
    if a_nan or b_nan:
        return math.inf
    if a == b:
        return 0.0
    if math.isinf(a) or math.isinf(b):
        return math.inf
    if abs(a) < floor and abs(b) < floor:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b), floor)


def classify(reldiff: float, agree_tol: float, numeric_tol: float) -> str:
    """Map a relative difference onto a verdict band.

    Args:
        reldiff: Relative difference from `relative_difference`.
        agree_tol: Below this, the values agree.
        numeric_tol: Below this, the difference is attributable to algorithm or
            convergence tolerance rather than to a difference in definition.

    Returns:
        One of `AGREE`, `NUMERIC`, `DIVERGE`.
    """
    if reldiff < agree_tol:
        return "AGREE"
    if reldiff < numeric_tol:
        return "NUMERIC"
    return "DIVERGE"


def worst(verdicts: list[str]) -> str:
    """Return the worst verdict in a list.

    Args:
        verdicts: Verdict strings.

    Returns:
        The worst verdict, or `AGREE` for an empty list.
    """
    if not verdicts:
        return "AGREE"
    return max(verdicts, key=VERDICT_ORDER.index)


@dataclass
class Comparison:
    """The verdict on one quantity across all backends.

    Attributes:
        quantity: Canonical quantity name.
        values: Backend name to reported value. Backends that did not report the
            quantity are absent from this map.
        absent_from: Backends that ran successfully but produced no such
            quantity. A package that cannot report a number the others can is a
            finding in itself, not a crash.
        verdict: Worst verdict across backend pairs.
        max_reldiff: Largest pairwise relative difference.
        pairwise: `(backend_a, backend_b)` to relative difference.
        expected: Verdict declared in `case.yaml`.
        outcome: `EXPECTED`, `NEW_FINDING`, `RESOLVED`, or `UNCOMPARABLE`.
        reason: Documented explanation for an expected divergence.
    """

    quantity: str
    values: dict[str, float] = field(default_factory=dict)
    absent_from: list[str] = field(default_factory=list)
    verdict: str = "AGREE"
    max_reldiff: float = 0.0
    pairwise: dict[tuple[str, str], float] = field(default_factory=dict)
    expected: str = "AGREE"
    outcome: str = EXPECTED
    reason: str | None = None

    @property
    def is_new_finding(self) -> bool:
        """Whether this quantity diverged more than the case documented.

        Returns:
            True when the observed verdict is worse than the expectation.
        """
        return self.outcome == NEW_FINDING


def _comparable(results: list[Result]) -> list[Result]:
    """Return only results that ran to completion.

    Args:
        results: All results for a case.

    Returns:
        Results with `status == "ok"`.
    """
    return [r for r in results if r.status == "ok"]


def compare_case(results: list[Result], spec: CaseSpec) -> list[Comparison]:
    """Compare every quantity across backends and check against expectations.

    Quantities are collected from the union of all successful backends, so a key
    only one backend produces still surfaces -- as an `absent_from` note rather
    than silently disappearing.

    Args:
        results: One result per backend.
        spec: The case specification carrying tolerances and expectations.

    Returns:
        One `Comparison` per quantity, sorted by name.
    """
    ok = _comparable(results)
    quantities = sorted({q for r in ok for q in r.quantities})

    comparisons = []
    for quantity in quantities:
        agree_tol, numeric_tol = spec.tolerances_for(quantity)
        declared = spec.spec_for(quantity)

        values: dict[str, float] = {}
        absent: list[str] = []
        for result in ok:
            if quantity not in result.quantities:
                absent.append(result.backend)
                continue
            value = result.quantities[quantity]
            if value is None:
                absent.append(result.backend)
            else:
                values[result.backend] = float(value)

        pairwise = {
            (a, b): relative_difference(values[a], values[b])
            for a, b in combinations(sorted(values), 2)
        }
        verdicts = [classify(d, agree_tol, numeric_tol) for d in pairwise.values()]
        comparison = Comparison(
            quantity=quantity,
            values=values,
            absent_from=sorted(absent),
            verdict=worst(verdicts),
            max_reldiff=max(pairwise.values(), default=0.0),
            pairwise=pairwise,
            expected=declared.expect,
            reason=declared.reason,
        )
        comparison.outcome = _outcome(comparison, len(values))
        comparisons.append(comparison)

    return comparisons


def _outcome(comparison: Comparison, n_values: int) -> str:
    """Check an observed verdict against its declared expectation.

    A verdict better than expected is reported as `RESOLVED` rather than passed
    over quietly: when a package upgrade closes a documented gap, the case notes
    have gone stale and should be revised.

    Args:
        comparison: The comparison to judge.
        n_values: How many backends produced a comparable value.

    Returns:
        One of the outcome constants.
    """
    if n_values < 2:
        return UNCOMPARABLE
    observed = VERDICT_ORDER.index(comparison.verdict)
    if comparison.expected not in VERDICT_ORDER:
        return NEW_FINDING
    expected = VERDICT_ORDER.index(comparison.expected)
    if observed > expected:
        return NEW_FINDING
    if observed < expected:
        return RESOLVED
    return EXPECTED


def summarize(comparisons: list[Comparison]) -> dict[str, int]:
    """Count comparisons by outcome and verdict.

    Args:
        comparisons: Comparisons for one or more cases.

    Returns:
        Counts keyed by outcome name and by `verdict:<VERDICT>`.
    """
    counts: dict[str, int] = {}
    for c in comparisons:
        counts[c.outcome] = counts.get(c.outcome, 0) + 1
        key = f"verdict:{c.verdict}"
        counts[key] = counts.get(key, 0) + 1
    return counts
