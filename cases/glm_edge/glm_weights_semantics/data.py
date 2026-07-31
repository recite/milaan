"""One dataset written twice: weighted, and expanded.

Six distinct covariate patterns with integer counts, emitted in two forms:

* `data.csv` -- one row per pattern, with a count column `w`
* `expanded.csv` -- one row per observation, `w` copies of each pattern

If `w` is a *frequency* weight, the two forms are the same dataset written
differently, and every quantity computed from them must agree exactly. That is
the invariant. Where a package treats `w` as an analytic or precision weight
instead, coefficients still agree but standard errors do not, because the two
readings disagree about how many observations there are.

No RNG; the outcome is a deterministic function of the pattern.
"""

import csv
import math
from pathlib import Path

#: `(x1, x2, count)`. Counts are small and unequal so the expansion is a
#: different size from the weighted form in a way that shows up in any
#: sample-size-dependent quantity.
PATTERNS = [
    (0.0, 0.0, 7),
    (1.0, 0.0, 3),
    (2.0, 0.0, 5),
    (0.0, 1.0, 4),
    (1.0, 1.0, 8),
    (2.0, 1.0, 6),
]


def outcome(x1: float, x2: float) -> int:
    """Return the binary outcome for a covariate pattern.

    Args:
        x1: First covariate.
        x2: Second covariate.

    Returns:
        0 or 1, deterministically.
    """
    return int(math.sin(2.0 * x1 + 3.0 * x2) > 0.15)


def main() -> None:
    """Write `data.csv` and `expanded.csv` beside this script."""
    here = Path(__file__).parent

    with (here / "data.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x1", "x2", "y", "w"])
        for x1, x2, count in PATTERNS:
            writer.writerow([f"{x1:.17g}", f"{x2:.17g}", outcome(x1, x2), count])

    with (here / "expanded.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x1", "x2", "y"])
        for x1, x2, count in PATTERNS:
            for _ in range(count):
                writer.writerow([f"{x1:.17g}", f"{x2:.17g}", outcome(x1, x2)])


if __name__ == "__main__":
    main()
