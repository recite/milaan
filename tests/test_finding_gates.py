"""Finding gates must expose API changes and damaged recorded evidence."""

import gzip
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

pytest_plugins = ["pytester"]
ROOT = Path(__file__).resolve().parents[1]
TTEST = ROOT / "cases/hypothesis/ttest_default_variance/size_py.py"
BINOMIAL = ROOT / "cases/proportions/binomial_ci_default/coverage_py.py"
GRF = ROOT / "probes/grf/causal_forest_cate_ci/gate.py"


def load_gate(path):
    spec = importlib.util.spec_from_file_location("finding_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ttest_finding_uses_the_library_default(monkeypatch):
    gate = load_gate(TTEST)

    def changed_default(a, b, *, axis):
        pvalues = np.ones(len(a))
        pvalues[::20] = 0.0
        return np.zeros(len(a)), pvalues

    monkeypatch.setattr(gate, "ttest_ind", changed_default)
    gate.test_scipy_default_ttest_holds_its_nominal_size()


def test_binomial_finding_uses_the_library_default(monkeypatch):
    gate = load_gate(BINOMIAL)

    def changed_default(x, n, *, alpha):
        return 0.2, 0.8

    monkeypatch.setattr(gate, "proportion_confint", changed_default)
    assert gate.interval(5, 20) == (0.2, 0.8)


@pytest.mark.parametrize("outcome", ["runtime_error", "unexpected_pass"])
def test_expected_findings_do_not_hide_runtime_errors_or_unexpected_passes(
    pytester, outcome
):
    replacement = (
        'raise RuntimeError("upstream API changed")'
        if outcome == "runtime_error"
        else "pass"
    )
    pytester.makepyfile(
        f"""
import importlib.util
spec = importlib.util.spec_from_file_location("finding_gate", {str(TTEST)!r})
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
def replacement(*args, **kwargs):
    {replacement}
gate.assert_count_rate = replacement
test_finding = gate.test_scipy_default_ttest_holds_its_nominal_size
"""
    )
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(failed=1)
    expected = "upstream API changed" if outcome == "runtime_error" else "XPASS(strict)"
    assert expected in result.stdout.str()


@pytest.mark.parametrize("damage", ["incomplete", "short_cell", "failed_replicate"])
def test_grf_rejects_damaged_results_before_coverage_gating(
    tmp_path, monkeypatch, damage
):
    gate = load_gate(GRF)
    data = gate.load()
    if damage == "incomplete":
        data["complete"] = False
    elif damage == "short_cell":
        data["replicates"].pop()
    else:
        data["replicates"][0]["failed"] = True
    path = tmp_path / "results.json.gz"
    path.write_bytes(gzip.compress(json.dumps(data).encode()))
    monkeypatch.setattr(gate, "RESULTS", path)
    with pytest.raises(ValueError, match=r"interrupted run|successful replicates"):
        gate.load()
