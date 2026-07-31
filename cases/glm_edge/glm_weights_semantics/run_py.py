"""statsmodels side: `freq_weights` and `var_weights` against row expansion.

statsmodels is unusual in exposing the distinction explicitly. `freq_weights`
declares that a row stands for that many observations; `var_weights` declares
that a row's variance is scaled. R's `glm` has one `weights` argument and
resolves the meaning by family. Running both against the same expansion shows
which reading each corresponds to.

Selected by a flag so one script serves two backends.
"""

import os
import sys
from pathlib import Path

# Fallback is the source checkout; the runner normally sets MILAAN_LIB.
_LIB = Path(__file__).resolve().parents[3] / "src" / "milaan" / "lib"
sys.path.insert(0, os.environ.get("MILAAN_LIB", str(_LIB)))

import milaan_py as cc
import numpy as np
import statsmodels.api as sm


def body(data_path):
    """Fit the weighted and expanded forms and report both.

    Args:
        data_path: Path to `data.csv`.

    Returns:
        Quantities and diagnostics for the result schema.
    """
    kind = "var" if "--var-weights" in sys.argv else "freq"

    d = cc.read_csv(data_path)
    e = cc.read_csv(str(Path(data_path).with_name("expanded.csv")))

    design_w = sm.add_constant(np.column_stack([d["x1"], d["x2"]]))
    design_e = sm.add_constant(np.column_stack([e["x1"], e["x2"]]))
    weights = np.asarray(d["w"])

    kwargs = (
        {"freq_weights": weights} if kind == "freq" else {"var_weights": weights}
    )
    weighted = sm.GLM(
        np.asarray(d["y"]), design_w, family=sm.families.Binomial(), **kwargs
    ).fit()
    expanded = sm.GLM(
        np.asarray(e["y"]), design_e, family=sm.families.Binomial()
    ).fit()

    return {
        "quantities": {
            "coef.x1@weighted": weighted.params[1],
            "coef.x1@expanded": expanded.params[1],
            "coef.x2@weighted": weighted.params[2],
            "coef.x2@expanded": expanded.params[2],
            "se.x1@weighted": weighted.bse[1],
            "se.x1@expanded": expanded.bse[1],
            "se.x2@weighted": weighted.bse[2],
            "se.x2@expanded": expanded.bse[2],
            "df.residual@weighted": weighted.df_resid,
            "df.residual@expanded": expanded.df_resid,
        },
        "diagnostics": {
            "weight_kind": kind,
            "rows_weighted": len(d["y"]),
            "rows_expanded": len(e["y"]),
            "total_weight": float(weights.sum()),
        },
    }


cc.main(
    "glm_weights_semantics",
    "sm_var_weights" if "--var-weights" in sys.argv else "sm_freq_weights",
    body,
    packages=["numpy", "statsmodels"],
)
