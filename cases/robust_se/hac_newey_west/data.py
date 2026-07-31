"""Deterministic regression data with heteroskedasticity and five clusters.

No random number generation anywhere: every value is a closed-form function of the
row index, so R and Python cannot receive different data. Values are written at 17
significant digits, which round-trips float64 exactly.
"""

import csv
import math
from pathlib import Path

N = 40
GROUPS = 5


def build() -> list[dict[str, float]]:
    """Construct the dataset.

    The response mixes two incommensurate periods so the residuals are neither
    homoskedastic nor serially independent -- the conditions robust and HAC
    covariance estimators exist for.

    Returns:
        One dict per row with keys `x`, `y`, `g`.
    """
    rows = []
    for i in range(N):
        x = i / (N - 1)
        g = i // (N // GROUPS) + 1
        y = math.sin(10 * x) + g / 10 + math.cos(3 * x)
        rows.append({"x": x, "y": y, "g": float(g)})
    return rows


def main() -> None:
    """Write `data.csv` beside this script."""
    rows = build()
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x", "y", "g"])
        for row in rows:
            writer.writerow([f"{row['x']:.17g}", f"{row['y']:.17g}", int(row["g"])])


if __name__ == "__main__":
    main()
