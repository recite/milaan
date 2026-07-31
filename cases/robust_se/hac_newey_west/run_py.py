"""statsmodels side of the Newey-West comparison."""

import inspect
import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.environ.get("MILAAN_LIB", str(Path(__file__).resolve().parents[3] / "src" / "milaan" / "lib"))
)

import milaan_py as cc
import numpy as np
import statsmodels.api as sm
from statsmodels.stats import sandwich_covariance as sc


def body(data_path):
    """Fit OLS and report HAC standard errors under several settings.

    statsmodels has no "just give me Newey-West" shorthand: `maxlags` is a
    required key, so the user must type something. Passing `None` invokes the
    package's own documented rule, `floor(4 * (T/100)^(2/9))`, which is the fair
    counterpart to R's default and is also what Stata's `newey` uses.

    Args:
        data_path: Path to `data.csv`.

    Returns:
        Quantities and diagnostics for the result schema.
    """
    d = cc.read_csv(data_path)
    x = np.asarray(d["x"])
    y = np.asarray(d["y"])
    design = sm.add_constant(x)
    n = len(y)

    def hac(maxlags, use_correction):
        fit = sm.OLS(y, design).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": maxlags, "use_correction": use_correction},
        )
        return fit.bse[1]

    quantities = {
        "se.x@default": hac(None, False),
        "se.x@lag3_noprewhite": hac(3, False),
        "se.x@lag3_noprewhite_adjust": hac(3, True),
        "se.x@ols": sm.OLS(y, design).fit().bse[1],
    }

    # Whether prewhitening is even reachable, established by introspection rather
    # than asserted: the absence of the option is part of the finding.
    hac_params = inspect.signature(sc.cov_hac).parameters
    return {
        "quantities": quantities,
        "diagnostics": {
            "n": n,
            "auto_maxlags": int(np.floor(4 * (n / 100) ** (2 / 9))),
            "cov_hac_parameters": sorted(hac_params),
            "prewhite_available": "prewhite" in hac_params,
        },
    }


cc.main("hac_newey_west", "py", body, packages=["numpy", "statsmodels", "scipy"])
