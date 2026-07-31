"""Checking the catalogue against what replication archives actually call."""

import pytest

from milaan.coverage import PLUMBING, Coverage, Procedure, load_frame, measure
from milaan.schema import CaseSpec

FRAME = [
    Procedure(1, "R", "length", ["base"], 3268, 0.35),
    Procedure(2, "R", "mean", ["Matrix"], 1412, 0.15),
    Procedure(3, "R", "lm", ["stats"], 643, 0.07),
    Procedure(4, "R", "sd", ["stats"], 343, 0.04),
    Procedure(5, "Python", "OLS", ["statsmodels"], 15, 0.002),
]


def spec(case_id, covers):
    return CaseSpec(id=case_id, title="", family="f", directory=None, covers=covers)


class TestMeasure:
    def test_a_declared_procedure_is_marked_covered(self):
        result = measure([spec("linear_model", ["lm"])], list(FRAME))
        (lm,) = [p for p in result.procedures if p.fname == "lm"]
        assert lm.covered_by == ["linear_model"]
        assert lm.covered

    def test_several_comparisons_can_cover_one_procedure(self):
        result = measure(
            [spec("a", ["lm"]), spec("b", ["lm"])],
            list(FRAME),
        )
        (lm,) = [p for p in result.procedures if p.fname == "lm"]
        assert lm.covered_by == ["a", "b"]

    def test_a_name_the_frame_does_not_list_is_reported(self):
        # Usually a typo. Silently ignoring it would let a spec claim coverage it
        # does not have, which is the one thing this module exists to prevent.
        result = measure([spec("a", ["lmm"])], list(FRAME))
        assert result.undeclared == {"lmm": ["a"]}


class TestDenominator:
    def test_plumbing_is_excluded_by_default(self):
        # The raw ranking is led by data plumbing -- `length` at 3,268 scripts --
        # so counting it as uncovered makes the queue look longer than it is.
        result = measure([], list(FRAME))
        assert "length" not in [p.fname for p in result.top("R", 10)]
        assert "length" in [p.fname for p in result.top("R", 10, computing_only=False)]

    def test_the_rate_uses_the_same_denominator_as_the_listing(self):
        result = measure([spec("a", ["mean"])], list(FRAME))
        covered, total = result.rate("R", 10)
        assert (covered, total) == (1, 3)  # mean, lm, sd -- not length

    def test_language_selects_the_ranking(self):
        result = measure([], list(FRAME))
        assert [p.fname for p in result.top("Python", 5)] == ["OLS"]

    def test_plumbing_names_are_not_also_computing_procedures(self):
        # A name in both would be excluded from the denominator while a spec
        # still claimed it, which reads as coverage of something uncounted.
        assert "mean" not in PLUMBING
        assert "median" not in PLUMBING
        assert "quantile" not in PLUMBING
        assert "sd" not in PLUMBING


class TestLoadFrame:
    def test_reads_the_shipped_frame(self):
        from pathlib import Path

        frame = load_frame(
            Path(__file__).resolve().parents[1] / "data" / "sampling_frame.csv"
        )
        assert len(frame) > 100
        assert {p.language for p in frame} == {"R", "Python"}
        assert frame[0].rank == 1


@pytest.mark.slow
def test_the_shipped_catalogue_covers_the_procedures_it_claims():
    """No spec may claim a procedure the corpus never calls.

    The README says comparisons are chosen by usage rather than taste. This is
    what makes that falsifiable: a `covers:` entry with no counterpart in the
    frame means either a typo or a procedure nobody uses, and both are worth
    knowing before writing more specs about it.
    """
    from pathlib import Path

    from milaan.loader import discover_cases

    root = Path(__file__).resolve().parents[1]
    specs = discover_cases(root / "specs", root / "cases")
    result = measure(specs, load_frame(root / "data" / "sampling_frame.csv"))
    assert result.undeclared == {}
    covered, total = result.rate("R", 18)
    assert covered >= 10, f"coverage of the top {total} slipped to {covered}"


def test_coverage_is_a_dataclass_not_a_dict():
    assert isinstance(measure([], []), Coverage)
