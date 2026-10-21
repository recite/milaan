"""The declarative spec format and reference-relative comparison."""

import shutil
import textwrap

import pytest

from milaan.compare import NEW_FINDING, compare_case
from milaan.loader import CaseError, load_spec
from milaan.schema import Result

SPEC = """
id: dispersion
family: descriptives
title: "sd versus np.std"
dataset: small_numeric
reference: r_sd
implementations:
  r_sd:        {lang: R,      expr: "sd(x)"}
  np_std:      {lang: Python, expr: "np.std(x)", expect: DIVERGE, reason: "ddof"}
  np_std_ddof: {lang: Python, expr: "np.std(x, ddof=1)"}
finding:
  cause: DEFINITION
  reconcilable: true
  reconciliation: "pass ddof=1"
"""


def write(tmp_path, body, name="dispersion.yaml"):
    root = tmp_path / "specs" / "descriptives"
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_text(textwrap.dedent(body))
    return path


def results(case_id, values):
    return [
        Result(case_id=case_id, backend=name, quantities={"value": v})
        for name, v in values.items()
    ]


class TestLoadSpec:
    def test_implementations_compile_to_backends(self, tmp_path):
        spec = load_spec(write(tmp_path, SPEC), root=tmp_path)
        assert [b.name for b in spec.backends] == ["r_sd", "np_std", "np_std_ddof"]
        assert spec.reference == "r_sd"
        assert "Rscript" in spec.backends[0].cmd[0]
        assert "sd(x)" in spec.backends[0].cmd

    def test_the_dataset_is_shared_not_owned(self, tmp_path):
        spec = load_spec(write(tmp_path, SPEC), root=tmp_path)
        assert spec.data_path == tmp_path / "datasets" / "small_numeric.csv"

    def test_a_reference_must_be_one_of_the_implementations(self, tmp_path):
        body = SPEC.replace("reference: r_sd", "reference: r_nonexistent")
        with pytest.raises(CaseError, match="not one of the implementations"):
            load_spec(write(tmp_path, body), root=tmp_path)

    def test_an_expected_divergence_needs_a_reason(self, tmp_path):
        body = SPEC.replace(', reason: "ddof"', "")
        with pytest.raises(CaseError, match="gives no reason"):
            load_spec(write(tmp_path, body), root=tmp_path)

    def test_an_unknown_language_is_refused(self, tmp_path):
        body = SPEC.replace(
            'lang: Python, expr: "np.std(x)"', 'lang: Julia, expr: "std(x)"'
        )
        with pytest.raises(CaseError, match="known languages"):
            load_spec(write(tmp_path, body), root=tmp_path)


class TestFinding:
    def test_an_unrecognised_cause_is_refused(self, tmp_path):
        body = SPEC.replace("cause: DEFINITION", "cause: VIBES")
        with pytest.raises(CaseError, match="is not one of"):
            load_spec(write(tmp_path, body), root=tmp_path)

    def test_reconcilable_without_a_reconciliation_is_refused(self, tmp_path):
        body = SPEC.replace('  reconciliation: "pass ddof=1"\n', "")
        with pytest.raises(CaseError, match="does not say"):
            load_spec(write(tmp_path, body), root=tmp_path)

    def test_irreducible_cannot_also_be_reconcilable(self, tmp_path):
        # If an argument makes them agree, the disagreement was never
        # irreducible; the label would be doing the opposite of its job.
        body = SPEC.replace("cause: DEFINITION", "cause: IRREDUCIBLE")
        with pytest.raises(CaseError, match="IRREDUCIBLE"):
            load_spec(write(tmp_path, body), root=tmp_path)


class TestReferenceRelativeComparison:
    def test_each_implementation_is_judged_against_the_reference(self, tmp_path):
        spec = load_spec(write(tmp_path, SPEC), root=tmp_path)
        got = compare_case(
            results(
                "dispersion", {"r_sd": 1.5341, "np_std": 1.4350, "np_std_ddof": 1.5341}
            ),
            spec,
        )
        (comparison,) = got
        assert comparison.reference == "r_sd"
        assert comparison.against_reference["np_std"] == ("DIVERGE", "EXPECTED")
        assert comparison.against_reference["np_std_ddof"] == ("AGREE", "EXPECTED")
        assert comparison.outcome == "EXPECTED"
        assert not comparison.is_new_finding

    def test_a_broken_reconciliation_is_a_new_finding(self, tmp_path):
        # The reason the comparison is per-implementation. np_std is *expected*
        # to diverge, so a worst-of verdict would be DIVERGE either way and the
        # ddof=1 variant silently failing to reconcile would pass unnoticed --
        # which is exactly the porting advice this repo exists to certify.
        spec = load_spec(write(tmp_path, SPEC), root=tmp_path)
        got = compare_case(
            results(
                "dispersion", {"r_sd": 1.5341, "np_std": 1.4350, "np_std_ddof": 1.9}
            ),
            spec,
        )
        (comparison,) = got
        assert comparison.against_reference["np_std_ddof"][1] == NEW_FINDING
        assert comparison.is_new_finding
        assert comparison.surprises == ["np_std_ddof"]

    def test_a_divergence_that_closed_is_reported_as_resolved(self, tmp_path):
        spec = load_spec(write(tmp_path, SPEC), root=tmp_path)
        got = compare_case(
            results(
                "dispersion", {"r_sd": 1.5341, "np_std": 1.5341, "np_std_ddof": 1.5341}
            ),
            spec,
        )
        assert got[0].against_reference["np_std"] == ("AGREE", "RESOLVED")
        assert got[0].outcome == "RESOLVED"

    def test_only_reference_pairs_are_measured(self, tmp_path):
        # Comparing numpy's default against numpy-with-ddof is arithmetic with
        # no question behind it, so it is not computed.
        spec = load_spec(write(tmp_path, SPEC), root=tmp_path)
        got = compare_case(
            results(
                "dispersion", {"r_sd": 1.5341, "np_std": 1.4350, "np_std_ddof": 1.5341}
            ),
            spec,
        )
        assert set(got[0].pairwise) == {("r_sd", "np_std"), ("r_sd", "np_std_ddof")}

    def test_without_a_reference_every_pair_is_compared(self, tmp_path):
        body = SPEC.replace("reference: r_sd\n", "")
        spec = load_spec(write(tmp_path, body), root=tmp_path)
        got = compare_case(results("dispersion", {"r_sd": 1.0, "np_std": 1.0}), spec)
        assert got[0].reference is None
        assert got[0].against_reference == {}


class TestDiscovery:
    def test_a_yaml_that_is_not_a_spec_is_skipped(self, tmp_path):
        # kasauti's bug records live beside their cases as bug.yaml, in a root
        # this function is handed. Treating every YAML as a spec broke it.
        from milaan.loader import discover_cases

        root = tmp_path / "bugs"
        root.mkdir()
        (root / "bug.yaml").write_text("id: r/pkg/1.0-thing\nseverity: HIGH\n")
        assert discover_cases(root) == []

    def test_a_misspelled_spec_is_reported_not_skipped(self, tmp_path):
        # Silently dropping this would mean a comparison that quietly never runs.
        from milaan.loader import discover_cases

        root = tmp_path / "specs"
        root.mkdir()
        (root / "typo.yaml").write_text("id: x\nreference: r\nimplementaions: {}\n")
        with pytest.raises(CaseError, match="declares no implementations"):
            discover_cases(root)


class TestMultiValueNaming:
    # This one genuinely shells out to Rscript, so it cannot run where R is
    # absent. The repo's existing idiom for that is tests/test_r_helpers.py:16.
    # This test predated CI and so had never met a machine without R; it failed
    # rather than skipped on the very first CI run, which is the right order of
    # discovery. The skip is declared because the dependency is real, not to
    # make a red check go away.
    @pytest.mark.slow
    @pytest.mark.skipif(shutil.which("Rscript") is None, reason="R is not installed")
    def test_both_languages_name_multi_valued_results_the_same_way(self, tmp_path):
        """R names a vector with c(a=, b=) and Python with a dict.

        They have to land on the same quantity keys or a multi-valued comparison
        has nothing to compare -- the two sides would each report quantities the
        other never produced, and every one would show up as `absent_from`
        rather than as a difference.
        """
        import json
        import os
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, "MILAAN_LIB": str(root / "src" / "milaan" / "lib")}
        out_r, out_py = tmp_path / "r.json", tmp_path / "py.json"
        subprocess.run(
            [
                "Rscript",
                "--vanilla",
                str(root / "backends" / "eval_r.R"),
                "--expr",
                "c(a=1, b=2)",
                os.devnull,
                str(out_r),
            ],
            check=True,
            env=env,
            capture_output=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(root / "backends" / "eval_py.py"),
                "--expr",
                "{'a': 1.0, 'b': 2.0}",
                os.devnull,
                str(out_py),
            ],
            check=True,
            env=env,
            capture_output=True,
        )
        keys = [set(json.loads(p.read_text())["quantities"]) for p in (out_r, out_py)]
        assert keys[0] == keys[1] == {"value.a", "value.b"}
