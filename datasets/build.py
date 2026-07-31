"""Generate the shared datasets every spec draws on.

Datasets are shared rather than generated per comparison, so two specs about the
same procedure are measured on the same numbers and their results can be read
side by side. They are also small and deterministic -- no RNG anywhere, since a
catalogue about reproducibility that could not reproduce its own inputs would be
a poor advertisement.

Each is chosen to make a disagreement *visible*, not to be realistic. Eight
observations show a `ddof` gap of 6.9%; eight hundred would show 0.06% and the
finding would be true but invisible.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def small_numeric() -> list[dict[str, float]]:
    """A short numeric vector, and a second group to compare it against.

    Short on purpose. The `n` versus `n-1` denominator gap shrinks as `1/n`, so a
    large sample would hide the very thing several specs exist to show.

    Returns:
        Rows with `x` and `y`.
    """
    x = [2.1, 3.4, 1.9, 5.6, 4.2, 3.3, 2.8, 6.1]
    y = [3.9, 4.4, 5.1, 2.2, 6.3, 5.8, 4.9, 3.1]
    return [{"x": a, "y": b} for a, b in zip(x, y, strict=True)]


def unequal_spread() -> list[dict[str, float]]:
    """Two groups with very different variances and very different sizes.

    This is the design where Welch and Student pooled part company. With balanced
    groups of equal spread the two agree to three decimals and the difference in
    defaults looks like a curiosity; here it is the whole answer.

    Long format -- a `value` column and a `group` label -- rather than one column
    per group. Padding two unequal groups into a rectangle would introduce
    missing values, and R and Python also disagree about those, which would
    confound the thing this dataset exists to isolate.

    Returns:
        Rows with `value` and `group`.
    """
    wide = [1.0, 14.0, -6.0, 21.0, -11.0]
    narrow = [
        5.0,
        5.4,
        4.8,
        5.2,
        5.1,
        4.9,
        5.3,
        4.7,
        5.05,
        5.15,
        4.95,
        5.25,
        4.85,
        5.35,
        4.75,
        5.45,
        4.65,
        5.5,
        4.6,
        5.2,
    ]
    return [{"value": v, "group": 1} for v in wide] + [
        {"value": v, "group": 2} for v in narrow
    ]


def counts_2x2() -> list[dict[str, float]]:
    """A 2x2 contingency table, small enough that exact and asymptotic differ.

    Returns:
        Rows with `row`, `col`, and `n`.
    """
    table = {(1, 1): 3, (1, 2): 7, (2, 1): 8, (2, 2): 2}
    return [{"row": r, "col": c, "n": n} for (r, c), n in sorted(table.items())]


#: Name to builder. The name is what a spec's `dataset:` field refers to.
DATASETS = {
    "small_numeric": small_numeric,
    "unequal_spread": unequal_spread,
    "counts_2x2": counts_2x2,
}


def main() -> None:
    """Write every dataset as a CSV beside this script."""
    for name, build in DATASETS.items():
        rows = build()
        path = HERE / f"{name}.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        k: (
                            "NA"
                            if isinstance(v, float) and math.isnan(v)
                            else f"{v:.17g}"
                        )
                        for k, v in row.items()
                    }
                )
        print(f"{name}: {len(rows)} rows -> {path.name}")


if __name__ == "__main__":
    main()
