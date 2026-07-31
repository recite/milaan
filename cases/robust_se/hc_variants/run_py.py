"""statsmodels side of the HC covariance comparison."""

import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.environ.get("MILAAN_LIB", str(Path(__file__).resolve().parents[3] / "src" / "milaan" / "lib"))
)

import milaan_py as cc
import numpy as np
import statsmodels.api as sm


def body(data_path):
    """Fit OLS and report classical plus HC0-HC3 standard errors.

    Args:
        data_path: Path to `data.csv`.

    Returns:
        Quantities and diagnostics for the result schema.
    """
    d = cc.read_csv(data_path)
    x = np.asarray(d["x"])
    y = np.asarray(d["y"])
    design = sm.add_constant(x)

    fit = sm.OLS(y, design).fit()
    quantities = {
        "coef.intercept": fit.params[0],
        "coef.x": fit.params[1],
        "se.intercept@ols": fit.bse[0],
        "se.x@ols": fit.bse[1],
    }
    for kind in ("HC0", "HC1", "HC2", "HC3"):
        robust = sm.OLS(y, design).fit(cov_type=kind)
        quantities[f"se.intercept@{kind}"] = robust.bse[0]
        quantities[f"se.x@{kind}"] = robust.bse[1]

    return {
        "quantities": quantities,
        "diagnostics": {"n": len(y), "df_residual": int(fit.df_resid)},
    }


cc.main("hc_variants", "py", body, packages=["numpy", "statsmodels", "scipy"])
