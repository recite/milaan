"""Three Python solvers on the same ill-conditioned system.

Selected by flag, so one script serves three backends:

* `statsmodels` -- `OLS`, which uses the pseudo-inverse
* `lstsq` -- `numpy.linalg.lstsq`, an SVD-based least-squares solve
* `normal` -- the textbook normal equations, `(X'X)^-1 X'y`

The third is included precisely because it is the wrong way to do this. Forming
`X'X` squares the condition number of the design, so a system that a QR or SVD
solve handles comfortably becomes one that a direct inverse cannot. Longley is
the dataset that made the point in 1967, and the certified values make the digit
loss measurable rather than merely asserted.
"""

import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.environ.get("MILAAN_LIB", str(Path(__file__).resolve().parents[3] / "lib"))
)

import milaan_py as cc
import numpy as np

METHODS = ("statsmodels", "lstsq", "normal")


def body(data_path):
    """Solve the Longley system by the selected method.

    Args:
        data_path: Path to `data.csv`.

    Returns:
        Quantities and diagnostics for the result schema.
    """
    method = next((m for m in METHODS if f"--{m}" in sys.argv), "statsmodels")

    d = cc.read_csv(data_path)
    y = np.asarray(d["y"], dtype=float)
    design = np.column_stack(
        [np.ones(len(y))] + [np.asarray(d[f"x{i}"], dtype=float) for i in range(1, 7)]
    )

    if method == "statsmodels":
        import statsmodels.api as sm

        fit = sm.OLS(y, design).fit()
        beta = fit.params
        residual_sd = float(np.sqrt(fit.mse_resid))
        r_squared = float(fit.rsquared)
    else:
        if method == "lstsq":
            beta = np.linalg.lstsq(design, y, rcond=None)[0]
        else:
            # The textbook formula, and the one to avoid: cond(X'X) = cond(X)^2.
            beta = np.linalg.inv(design.T @ design) @ design.T @ y
        residuals = y - design @ beta
        dof = len(y) - design.shape[1]
        residual_sd = float(np.sqrt(residuals @ residuals / dof))
        centred = y - y.mean()
        r_squared = float(1.0 - (residuals @ residuals) / (centred @ centred))

    quantities = {f"coef.b{i}": float(beta[i]) for i in range(7)}
    quantities["residual.sd"] = residual_sd
    quantities["r.squared"] = r_squared

    return {
        "quantities": quantities,
        "diagnostics": {
            "method": method,
            "condition_number": float(np.linalg.cond(design)),
            "condition_number_squared": float(np.linalg.cond(design.T @ design)),
        },
    }


method_name = next((m for m in METHODS if f"--{m}" in sys.argv), "statsmodels")
cc.main("nist_longley", method_name, body, packages=["numpy", "statsmodels"])
