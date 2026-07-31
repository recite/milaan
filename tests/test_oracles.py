"""Certified-value scoring and the metamorphic invariant evaluator."""

from pathlib import Path

import pytest

from milaan.oracles import (
    InvariantError,
    check_certified,
    check_invariants,
    evaluate_expression,
)
from milaan.schema import CaseSpec, Invariant, Result


def make_spec(**kwargs) -> CaseSpec:
    defaults = {"id": "t", "title": "t", "family": "f", "directory": Path(".")}
    return CaseSpec(**{**defaults, **kwargs})


class TestEvaluateExpression:
    def test_arithmetic_over_quantities(self):
        q = {"coef.x": 6.0, "coef.y": 3.0}
        assert evaluate_expression("coef.x / coef.y", q) == 2.0
        assert evaluate_expression("coef.x - coef.y * 2", q) == 0.0

    def test_names_with_dots_and_at_signs(self):
        # Canonical quantity names are not Python identifiers; they must still work.
        q = {"se.x@HC1": 4.0, "se.x@ols": 2.0}
        assert evaluate_expression("se.x@HC1 / se.x@ols", q) == 2.0

    def test_longest_name_wins_over_its_own_prefix(self):
        # "coef.x" is a prefix of "coef.x@scaled"; substituting the short one first
        # would corrupt the long one.
        q = {"coef.x": 5.0, "coef.x@scaled": 0.5}
        assert evaluate_expression("coef.x@scaled / coef.x", q) == 0.1

    def test_allowed_functions(self):
        assert evaluate_expression("sqrt(abs(v))", {"v": -9.0}) == 3.0

    def test_rejects_unknown_quantity(self):
        with pytest.raises(InvariantError, match="unknown quantity"):
            evaluate_expression("missing * 2", {"present": 1.0})

    def test_none_valued_quantity_is_unavailable(self):
        with pytest.raises(InvariantError):
            evaluate_expression("x * 2", {"x": None})

    def test_rejects_arbitrary_calls(self):
        # A case.yaml must not be able to execute code.
        with pytest.raises(InvariantError):
            evaluate_expression("__import__('os').system('true')", {})

    def test_rejects_attribute_access(self):
        with pytest.raises(InvariantError):
            evaluate_expression("x.__class__", {"x": 1.0})

    def test_rejects_comparison(self):
        with pytest.raises(InvariantError):
            evaluate_expression("x > 1", {"x": 1.0})

    def test_division_by_zero_is_an_invariant_error(self):
        with pytest.raises(InvariantError, match="division by zero"):
            evaluate_expression("a / b", {"a": 1.0, "b": 0.0})


class TestCheckInvariants:
    def test_holding_relation_passes(self):
        result = Result(
            case_id="t",
            backend="r",
            quantities={"coef.x": 5.0, "coef.x@scaled": 0.5},
        )
        inv = Invariant(expr="coef.x@scaled / coef.x", equals=0.1)
        (check,) = check_invariants([result], [inv])
        assert check.passed

    def test_violated_relation_fails(self):
        result = Result(case_id="t", backend="r", quantities={"a": 1.0, "b": 3.0})
        (check,) = check_invariants([result], [Invariant(expr="a / b", equals=1.0)])
        assert not check.passed
        assert check.observed == pytest.approx(1 / 3)

    def test_unevaluable_relation_is_a_failure_with_a_reason(self):
        result = Result(case_id="t", backend="r", quantities={"a": 1.0})
        (check,) = check_invariants([result], [Invariant(expr="a / z", equals=1.0)])
        assert not check.passed
        assert "unknown quantity" in (check.error or "")

    def test_errored_backends_are_skipped(self):
        results = [
            Result(case_id="t", backend="ok", quantities={"a": 1.0}),
            Result(case_id="t", backend="bad", status="error"),
        ]
        checks = check_invariants(results, [Invariant(expr="a", equals=1.0)])
        assert [c.backend for c in checks] == ["ok"]


class TestCheckCertified:
    def test_scores_each_backend_independently(self):
        spec = make_spec(certified={"coef.x": 1.0})
        results = [
            Result(case_id="t", backend="good", quantities={"coef.x": 1.0}),
            Result(case_id="t", backend="bad", quantities={"coef.x": 1.5}),
        ]
        by_backend = {c.backend: c for c in check_certified(results, spec)}
        assert by_backend["good"].passed
        assert not by_backend["bad"].passed

    def test_reports_correct_digits(self):
        spec = make_spec(certified={"coef.x": 1.0})
        result = Result(case_id="t", backend="r", quantities={"coef.x": 1.001})
        (check,) = check_certified([result], spec)
        assert check.digits == pytest.approx(3.0, abs=0.01)

    def test_exact_match_reports_infinite_digits(self):
        spec = make_spec(certified={"coef.x": 2.5})
        result = Result(case_id="t", backend="r", quantities={"coef.x": 2.5})
        (check,) = check_certified([result], spec)
        assert check.digits == float("inf")

    def test_unreported_quantity_is_not_scored(self):
        spec = make_spec(certified={"coef.x": 1.0})
        result = Result(case_id="t", backend="r", quantities={"other": 1.0})
        assert check_certified([result], spec) == []
