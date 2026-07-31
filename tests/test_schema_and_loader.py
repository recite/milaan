"""Result serialization and `case.yaml` parsing."""

import json

import pytest

from milaan.loader import CaseError, discover_cases, load_case, select_cases
from milaan.schema import Result

CASE_YAML = """
id: demo
title: A demonstration
family: fam
backends:
  - name: r
    cmd: ["Rscript", "run_r.R"]
  - name: py
    cmd: ["python3", "run_py.py"]
quantities:
  se.x:
    expect: DIVERGE
    reason: because the defaults differ
agree_tol: 1.0e-9
certified:
  coef.x: 1.5
invariants:
  - expr: "coef.x / coef.x"
    equals: 1.0
"""


@pytest.fixture
def case_dir(tmp_path):
    directory = tmp_path / "demo"
    directory.mkdir()
    (directory / "case.yaml").write_text(CASE_YAML)
    return directory


class TestResult:
    def test_round_trips_through_json(self, tmp_path):
        original = Result(
            case_id="c",
            backend="r",
            env={"language": "R", "version": "4.6.0"},
            quantities={"coef.x": 1.25, "se.x": None},
            diagnostics={"converged": True},
        )
        path = tmp_path / "r.json"
        original.dump(path)
        assert Result.load(path) == original

    def test_preserves_full_float_precision(self, tmp_path):
        # Losing digits in serialization would manufacture disagreement between
        # backends that actually agree.
        value = 0.27560153634181519
        path = tmp_path / "r.json"
        Result(case_id="c", backend="r", quantities={"se.x": value}).dump(path)
        assert Result.load(path).quantities["se.x"] == value

    def test_unknown_keys_are_ignored(self):
        result = Result.from_dict({"case_id": "c", "backend": "r", "future_field": 1})
        assert result.backend == "r"

    def test_missing_required_key_raises(self):
        with pytest.raises(ValueError, match="backend"):
            Result.from_dict({"case_id": "c"})

    def test_error_status_survives_the_round_trip(self, tmp_path):
        path = tmp_path / "r.json"
        Result(case_id="c", backend="sm", status="error", error="Singular").dump(path)
        loaded = Result.load(path)
        assert loaded.status == "error"
        assert loaded.error == "Singular"
        assert json.loads(path.read_text())["status"] == "error"


class TestLoadCase:
    def test_parses_every_block(self, case_dir):
        spec = load_case(case_dir)
        assert spec.id == "demo"
        assert [b.name for b in spec.backends] == ["r", "py"]
        assert spec.agree_tol == 1e-9
        assert spec.certified == {"coef.x": 1.5}
        assert spec.invariants[0].equals == 1.0
        assert spec.spec_for("se.x").expect == "DIVERGE"

    def test_unlisted_quantity_defaults_to_expecting_agreement(self, case_dir):
        assert load_case(case_dir).spec_for("anything").expect == "AGREE"

    def test_per_quantity_tolerance_falls_back_to_case_level(self, case_dir):
        agree, numeric = load_case(case_dir).tolerances_for("se.x")
        assert (agree, numeric) == (1e-9, 1e-5)

    def test_divergence_without_a_reason_is_rejected(self, tmp_path):
        # The whole point of the expectation mechanism is that a difference which
        # is expected has been explained.
        directory = tmp_path / "bad"
        directory.mkdir()
        (directory / "case.yaml").write_text(
            'id: bad\nbackends:\n  - {name: r, cmd: ["Rscript", "x.R"]}\n'
            "quantities:\n  se.x:\n    expect: DIVERGE\n"
        )
        with pytest.raises(CaseError, match="no reason"):
            load_case(directory)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(CaseError, match=r"no case\.yaml"):
            load_case(tmp_path)

    def test_no_backends_raises(self, tmp_path):
        directory = tmp_path / "empty"
        directory.mkdir()
        (directory / "case.yaml").write_text("id: empty\n")
        with pytest.raises(CaseError, match="no backends"):
            load_case(directory)

    def test_duplicate_backend_names_raise(self, tmp_path):
        directory = tmp_path / "dupe"
        directory.mkdir()
        (directory / "case.yaml").write_text(
            "id: dupe\nbackends:\n"
            '  - {name: r, cmd: ["a"]}\n  - {name: r, cmd: ["b"]}\n'
        )
        with pytest.raises(CaseError, match="duplicate backend"):
            load_case(directory)


class TestSelectCases:
    def test_empty_selection_returns_everything(self, case_dir):
        assert len(select_cases(case_dir.parent, [])) == 1

    def test_selects_by_id_and_by_family(self, case_dir):
        assert select_cases(case_dir.parent, ["demo"])[0].id == "demo"
        assert select_cases(case_dir.parent, ["fam"])[0].id == "demo"

    def test_unknown_name_raises_and_lists_what_exists(self, case_dir):
        with pytest.raises(CaseError, match="demo"):
            select_cases(case_dir.parent, ["nope"])


def test_repository_cases_all_parse():
    """Every case shipped in this repo must load and declare a reason for
    each expected divergence. Guards against a malformed case landing.
    """
    from milaan.cli import ROOT

    cases = discover_cases(ROOT / "cases")
    assert cases, "no cases discovered"
    for case in cases:
        for name, quantity in case.quantities.items():
            if quantity.expect != "AGREE":
                assert quantity.reason, f"{case.id}:{name} lacks a reason"
