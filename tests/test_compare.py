"""Verdict classification and expectation checking."""

import math
from pathlib import Path

import pytest

from milaan.compare import (
    EXPECTED,
    NEW_FINDING,
    RESOLVED,
    UNCOMPARABLE,
    classify,
    compare_case,
    relative_difference,
    summarize,
    worst,
)
from milaan.schema import CaseSpec, QuantitySpec, Result


def make_spec(**kwargs) -> CaseSpec:
    defaults = {
        "id": "t",
        "title": "t",
        "family": "f",
        "directory": Path("."),
        "agree_tol": 1e-8,
        "numeric_tol": 1e-5,
    }
    return CaseSpec(**{**defaults, **kwargs})


def make_result(backend, quantities, status="ok"):
    return Result(case_id="t", backend=backend, quantities=quantities, status=status)


class TestRelativeDifference:
    def test_identical_values_are_zero(self):
        assert relative_difference(1.5, 1.5) == 0.0

    def test_scale_free(self):
        # The same 1% gap at two very different magnitudes reads the same.
        assert relative_difference(100.0, 101.0) == pytest.approx(1 / 101)
        assert relative_difference(1e-9, 1.01e-9) == pytest.approx(1 / 101)

    def test_both_zero_does_not_divide_by_zero(self):
        assert relative_difference(0.0, 0.0) == 0.0

    def test_both_below_the_floor_agree(self):
        # A denormal-scale value against an exact zero is not a disagreement:
        # one scikit-learn version returns 8.2e-16 where another returns 0.0,
        # and dividing by the floor would report that as 8e-4.
        assert relative_difference(8.248170715663733e-16, 0.0) == 0.0
        assert relative_difference(1e-15, -1e-15) == 0.0

    def test_one_above_the_floor_still_diverges(self):
        assert relative_difference(1e-15, 1e-6) == pytest.approx(1.0)

    def test_one_zero_is_total_disagreement(self):
        assert relative_difference(0.0, 5.0) == 1.0

    def test_both_nan_agree(self):
        # Two packages that both decline to produce a number behave alike.
        assert relative_difference(math.nan, math.nan) == 0.0

    def test_one_nan_diverges(self):
        assert relative_difference(math.nan, 1.0) == math.inf
        assert relative_difference(1.0, math.nan) == math.inf

    def test_infinities(self):
        assert relative_difference(math.inf, math.inf) == 0.0
        assert relative_difference(math.inf, 1.0) == math.inf

    def test_sign_matters(self):
        assert relative_difference(1.0, -1.0) == 2.0


class TestClassify:
    @pytest.mark.parametrize(
        ("reldiff", "expected"),
        [
            (0.0, "AGREE"),
            (9.9e-9, "AGREE"),
            (1e-8, "NUMERIC"),
            (9.9e-6, "NUMERIC"),
            (1e-5, "DIVERGE"),
            (math.inf, "DIVERGE"),
        ],
    )
    def test_bands_including_boundaries(self, reldiff, expected):
        # Boundaries are exclusive-below: exactly at the tolerance is the worse band.
        assert classify(reldiff, 1e-8, 1e-5) == expected

    def test_worst_of_empty_is_agree(self):
        assert worst([]) == "AGREE"

    def test_worst_picks_by_severity_not_order(self):
        assert worst(["DIVERGE", "AGREE", "NUMERIC"]) == "DIVERGE"
        assert worst(["AGREE", "NUMERIC"]) == "NUMERIC"


class TestCompareCase:
    def test_agreement_is_expected_by_default(self):
        results = [
            make_result("r", {"coef.x": 1.0}),
            make_result("py", {"coef.x": 1.0}),
        ]
        (c,) = compare_case(results, make_spec())
        assert c.verdict == "AGREE"
        assert c.outcome == EXPECTED

    def test_undocumented_divergence_is_a_new_finding(self):
        results = [make_result("r", {"se.x": 3.37}), make_result("py", {"se.x": 0.478})]
        (c,) = compare_case(results, make_spec())
        assert c.verdict == "DIVERGE"
        assert c.outcome == NEW_FINDING
        assert c.is_new_finding

    def test_documented_divergence_is_expected(self):
        spec = make_spec(
            quantities={"se.x": QuantitySpec(expect="DIVERGE", reason="prewhitening")}
        )
        results = [make_result("r", {"se.x": 3.37}), make_result("py", {"se.x": 0.478})]
        (c,) = compare_case(results, spec)
        assert c.outcome == EXPECTED
        assert not c.is_new_finding
        assert c.reason == "prewhitening"

    def test_closed_gap_is_reported_as_resolved(self):
        # A package upgrade that removes a documented difference should surface,
        # because the case notes have gone stale.
        spec = make_spec(
            quantities={"se.x": QuantitySpec(expect="DIVERGE", reason="was different")}
        )
        results = [make_result("r", {"se.x": 1.0}), make_result("py", {"se.x": 1.0})]
        (c,) = compare_case(results, spec)
        assert c.outcome == RESOLVED

    def test_single_backend_is_uncomparable_not_agreement(self):
        results = [make_result("r", {"se.x": 1.0}), make_result("py", {})]
        (c,) = compare_case(results, make_spec())
        assert c.outcome == UNCOMPARABLE
        assert c.absent_from == ["py"]

    def test_none_value_counts_as_absent(self):
        results = [
            make_result("r", {"se.x": 1.0}),
            make_result("py", {"se.x": None}),
        ]
        (c,) = compare_case(results, make_spec())
        assert c.absent_from == ["py"]
        assert c.outcome == UNCOMPARABLE

    def test_errored_backend_is_excluded_from_comparison(self):
        results = [
            make_result("r", {"coef.x": 1.0}),
            make_result("py", {"coef.x": 1.0}),
            make_result("sm", {}, status="error"),
        ]
        (c,) = compare_case(results, make_spec())
        assert set(c.values) == {"r", "py"}
        assert c.outcome == EXPECTED

    def test_quantities_are_the_union_across_backends(self):
        results = [
            make_result("r", {"a": 1.0, "b": 2.0}),
            make_result("py", {"a": 1.0, "c": 3.0}),
        ]
        assert [c.quantity for c in compare_case(results, make_spec())] == [
            "a",
            "b",
            "c",
        ]

    def test_worst_pair_wins_across_three_backends(self):
        results = [
            make_result("a", {"x": 1.0}),
            make_result("b", {"x": 1.0}),
            make_result("c", {"x": 2.0}),
        ]
        (c,) = compare_case(results, make_spec())
        assert c.verdict == "DIVERGE"
        assert len(c.pairwise) == 3

    def test_per_quantity_tolerance_override(self):
        spec = make_spec(quantities={"x": QuantitySpec(agree_tol=1e-2)})
        results = [make_result("r", {"x": 1.0}), make_result("py", {"x": 1.001})]
        (c,) = compare_case(results, spec)
        assert c.verdict == "AGREE"


def test_summarize_counts_outcomes_and_verdicts():
    results = [
        make_result("r", {"same": 1.0, "diff": 1.0}),
        make_result("py", {"same": 1.0, "diff": 9.0}),
    ]
    counts = summarize(compare_case(results, make_spec()))
    assert counts[EXPECTED] == 1
    assert counts[NEW_FINDING] == 1
    assert counts["verdict:AGREE"] == 1
    assert counts["verdict:DIVERGE"] == 1
