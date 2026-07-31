"""A perfectly separated binary outcome.

Every observation with x < 0 is a zero and every observation with x > 0 is a one,
so the likelihood is monotone in the slope and the maximum likelihood estimate does
not exist -- the supremum is at infinity. No finite answer is correct here. What
each package does when asked anyway is the observation.
"""

import csv
from pathlib import Path

X = [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def build() -> list[tuple[float, int]]:
    """Construct the separated dataset.

    Returns:
        `(x, y)` pairs, with `y` the sign indicator of `x`.
    """
    return [(x, 1 if x > 0 else 0) for x in X]


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x", "y"])
        for x, y in build():
            writer.writerow([f"{x:.17g}", y])


if __name__ == "__main__":
    main()
