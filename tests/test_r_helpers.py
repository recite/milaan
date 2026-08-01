"""`cc_flatten` turns an arbitrary R object into named scalars.

Exercised through `Rscript` rather than mocked, because the whole point of the
helper is what R's own type system does to `coef()`, `vcov()`, and a fitted
model -- a Python reimplementation of that would be testing the wrong thing.
"""

import json
import shutil
import subprocess

import pytest

from milaan.runner import LIB_DIR

pytestmark = pytest.mark.skipif(
    shutil.which("Rscript") is None, reason="R is not installed"
)


def flatten(expression: str) -> dict:
    """Run `cc_flatten` on an expression and return the result.

    Args:
        expression: R source producing the `cc_flatten` call.

    Returns:
        The flattened quantities as a dict.
    """
    script = (
        f'source("{LIB_DIR / "milaan.R"}")\n'
        f"cat(jsonlite::toJSON({expression}, auto_unbox = TRUE, digits = NA))\n"
    )
    proc = subprocess.run(
        ["Rscript", "--vanilla", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


class TestCcFlatten:
    def test_a_named_vector_becomes_dotted_names(self):
        found = flatten('cc_flatten(c(a = 1, b = 2), "coef")')
        assert found == {"coef.a": 1, "coef.b": 2}

    def test_a_matrix_uses_its_dimnames(self):
        found = flatten(
            'cc_flatten(matrix(1:4, 2, dimnames = list(c("r1", "r2"), '
            'c("c1", "c2"))), "v")'
        )
        assert found["v.r1.c2"] == 3

    def test_an_unnamed_position_is_bracketed_without_a_dot(self):
        # `resid[3]`, not `resid.[3]`, which would read as a component literally
        # named "[3]".
        assert flatten('cc_flatten(c(7, 8), "resid")') == {"resid[1]": 7, "resid[2]": 8}

    def test_a_bare_scalar_keeps_the_prefix_alone(self):
        assert flatten('cc_flatten(42, "loglik")') == {"loglik": 42}

    def test_nested_lists_recurse(self):
        found = flatten('cc_flatten(list(a = 1, b = c(p = 2)), "top")')
        assert found == {"top.a": 1, "top.b.p": 2}

    def test_non_numeric_leaves_are_dropped_rather_than_coerced(self):
        # A screen compares numbers. A changed string is not a moved quantity,
        # and coercing it to a factor code would invent one.
        found = flatten('cc_flatten(list(n = 3, label = "hc1", f = mean), "x")')
        assert found == {"x.n": 3}

    def test_a_logical_is_kept(self):
        # `converged` flipping between two versions is a moved quantity by any
        # reading, so it must not be filtered out with the strings.
        assert flatten('cc_flatten(list(converged = TRUE), "fit")') == {
            "fit.converged": 1
        }

    def test_empty_and_null_components_are_skipped(self):
        found = flatten('cc_flatten(list(a = NULL, b = numeric(0), c = 5), "z")')
        assert found == {"z.c": 5}

    def test_a_fitted_model_flattens_through_its_accessors(self):
        found = flatten(
            'cc_flatten(vcov(lm(y ~ x, data.frame(x = 1:8, y = (1:8)^2))), "vcov")'
        )
        assert set(found) == {
            "vcov.(Intercept).(Intercept)",
            "vcov.(Intercept).x",
            "vcov.x.(Intercept)",
            "vcov.x.x",
        }

    def test_an_oversized_object_stops_loudly(self):
        # Silence here would mean a screen quietly reporting a truncated view of
        # what a version returned, which is worse than refusing to report.
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            flatten('cc_flatten(1:50, "big", max = 4)')
        assert "more than 4 quantities" in excinfo.value.stderr
