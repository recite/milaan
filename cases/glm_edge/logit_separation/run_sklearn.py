"""scikit-learn side, run twice: at its default penalty and unpenalized.

`LogisticRegression()` applies L2 regularization at `C=1.0` unless told otherwise.
On separated data that is the difference between a finite, plausible-looking
coefficient and an unbounded one -- and nothing in the API says so at the call
site. The two backends exist to put both numbers in the same table.
"""

import os
import sys
from pathlib import Path

# Fallback is the source checkout; the runner normally sets MILAAN_LIB.
_LIB = Path(__file__).resolve().parents[3] / "src" / "milaan" / "lib"
sys.path.insert(0, os.environ.get("MILAAN_LIB", str(_LIB)))

import milaan_py as cc
import numpy as np
from sklearn.linear_model import LogisticRegression


def body(data_path):
    """Fit scikit-learn's logistic regression in one of two configurations.

    Args:
        data_path: Path to `data.csv`.

    Returns:
        Quantities and diagnostics for the result schema.
    """
    penalized = "--penalty=none" not in sys.argv

    d = cc.read_csv(data_path)
    y = np.asarray(d["y"])
    x = np.asarray(d["x"]).reshape(-1, 1)

    kwargs = {} if penalized else {"penalty": None, "max_iter": 100000}
    model = LogisticRegression(**kwargs).fit(x, y)

    return {
        # No standard error or p-value: scikit-learn is a prediction library and
        # does not compute inferential quantities at all. Their absence from this
        # backend is itself reported, rather than silently filled in.
        "quantities": {
            "coef.intercept": float(model.intercept_[0]),
            "coef.x": float(model.coef_[0][0]),
        },
        "diagnostics": {
            "penalty": "l2 (C=1.0, the default)" if penalized else "none",
            "iterations": int(model.n_iter_[0]),
            "max_iter": int(model.max_iter),
            "hit_iteration_limit": bool(model.n_iter_[0] >= model.max_iter),
        },
    }


backend = "sklearn_default" if "--penalty=none" not in sys.argv else "sklearn_none"
cc.main("logit_separation", backend, body, packages=["numpy", "sklearn"])
