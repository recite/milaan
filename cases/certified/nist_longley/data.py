"""NIST StRD Longley: the reference test for linear least squares.

Sixteen observations, six predictors, and a design matrix so ill-conditioned that
Longley (1967) used it to show that the least-squares programs of the day could
not solve it. It became the standard against which numerical linear algebra in
statistics packages is checked, and NIST publishes certified coefficients to
fifteen digits.

Values transcribed from
https://www.itl.nist.gov/div898/strd/lls/data/LINKS/DATA/Longley.dat and embedded
here so the case needs no network at run time. Columns are y then x1..x6:
GNP deflator, GNP, unemployed, armed forces, population, year.
"""

import csv
from pathlib import Path

ROWS = [
    (60323, 83.0, 234289, 2356, 1590, 107608, 1947),
    (61122, 88.5, 259426, 2325, 1456, 108632, 1948),
    (60171, 88.2, 258054, 3682, 1616, 109773, 1949),
    (61187, 89.5, 284599, 3351, 1650, 110929, 1950),
    (63221, 96.2, 328975, 2099, 3099, 112075, 1951),
    (63639, 98.1, 346999, 1932, 3594, 113270, 1952),
    (64989, 99.0, 365385, 1870, 3547, 115094, 1953),
    (63761, 100.0, 363112, 3578, 3350, 116219, 1954),
    (66019, 101.2, 397469, 2904, 3048, 117388, 1955),
    (67857, 104.6, 419180, 2822, 2857, 118734, 1956),
    (68169, 108.4, 442769, 2936, 2798, 120445, 1957),
    (66513, 110.8, 444546, 4681, 2637, 121950, 1958),
    (68655, 112.6, 482704, 3813, 2552, 123366, 1959),
    (69564, 114.2, 502601, 3931, 2514, 125368, 1960),
    (69331, 115.7, 518173, 4806, 2572, 127852, 1961),
    (70551, 116.9, 554894, 4007, 2827, 130081, 1962),
]

COLUMNS = ["y", "x1", "x2", "x3", "x4", "x5", "x6"]


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in ROWS:
            writer.writerow([f"{v:.17g}" for v in row])


if __name__ == "__main__":
    main()
