# Newey-West: same estimator, different defaults

## What happens

Identical data, identical model, the standard Newey-West call in each language:

| | R | Python |
|---|---|---|
| `NeweyWest(m)` / `cov_type="HAC"` | **3.3676734944** | **0.4780828112** |

A factor of seven in a reported standard error, which is the difference between a
t of 0.6 and a t of 4.3.

## Why

The gap decomposes cleanly, and neither package is doing anything wrong.

| setting | R | ratio to previous |
|---|---|---|
| default (prewhite, auto bandwidth) | 3.3676734944 | |
| auto bandwidth, no prewhitening | 0.5304267384 | 6.35x |
| 3 lags, no prewhitening | 0.4780828112 | 1.11x |
| statsmodels, 3 lags, no correction | 0.4780828112 | agrees to 6e-16 |

Two independent defaults differ:

1. **Prewhitening.** R's `NeweyWest` sets `prewhite = TRUE`, running the moment
   conditions through a VAR(1) filter before applying the kernel and recolouring
   afterwards. This accounts for almost all of the gap. statsmodels cannot do it —
   `sandwich_covariance.cov_hac` takes `(results, nlags, weights_func,
   use_correction)` and nothing else, so the option is not merely off by default,
   it is absent.

2. **Bandwidth.** R selects the lag truncation from the data (Newey and West's
   automatic procedure via `bwNeweyWest`), choosing 5.22 here. statsmodels uses the
   fixed rule `floor(4 * (T/100)^(2/9))`, which is 3 at T = 40, and requires the
   user to pass `maxlags` explicitly — omitting the key raises `KeyError`, so there
   is no silent default, only a forced choice most users make by copying the rule.

Once both are pinned to Bartlett / 3 lags / no prewhitening / no finite-sample
correction, the two agree to 6e-16. This is the good outcome: the estimator is
implemented identically in both ecosystems, and everything visible at the surface
is convention.

## The finite-sample correction

`se.x@lag3_noprewhite_adjust` compares R's `adjust = TRUE` against statsmodels'
`use_correction = True`. They agree (0.4905026148, to 3e-16), so here the
similarly-named switches do mean the same thing — worth recording because in the
cluster-robust case they do not.

Worth noting for anyone relying on it: the statsmodels docstring for `cov_hac_simple`
says of that correction, verbatim, *"just guessing on correction factor, need
reference"*, and *"verified only for nlags=0, which is just White"*. The numbers
agree with R regardless, which is better evidence than the comment.

## Consequence

This is the most portable kind of error: nothing warns, nothing fails, and the
number is plausible either way. A researcher who moves a time-series analysis from
R to Python, or reads a Python tutorial while working in R, changes their standard
errors by a factor of seven without touching the model.

## Which convention should you use?

Everything above is a comparison, and a comparison cannot answer this. Neither
package is a reference for the other, and the finding is correctly filed as
convention rather than defect. But a researcher still has to pick a setting, and
a factor of seven in a standard error is not a matter of taste.

So: draw from a process whose coefficient we set, and count how often the nominal
95% interval contains it. `coverage_r.R` and `coverage_py.py` reproduce this.
AR(1) regressor and AR(1) errors, rho = 0.8, T = 100, 1000 replicates, nominal
0.95:

| setting | coverage |
|---|---|
| R `NeweyWest(m)` — prewhite, automatic bandwidth | **0.863** |
| R, `prewhite = FALSE`, automatic bandwidth | 0.808 |
| R, `prewhite = FALSE`, `lag = 3` | 0.783 |
| statsmodels, Newey-West lag rule (4 lags at T=100) | 0.801 |
| statsmodels HC0 | 0.618 |
| statsmodels, nonrobust | 0.647 |

Two things follow, and the second matters more than the first.

**The R default is the better convention here, by about six points.** Prewhitening
is doing real work, and it is the option statsmodels does not have. Someone moving
an analysis from R to Python and reaching for the lag rule loses that, on top of
the point-estimate gap this case already documents. "Neither package is doing
anything wrong" remains true about *bugs*; it does not make the two choices
equivalent.

**Every one of them under-covers, and that is not a defect either.** HAC standard
errors are consistent, not unbiased, and their nominal level is a large-sample
promise. What the measurement adds is how slowly it arrives:

| T | lags | effective n | coverage |
|---|---|---|---|
| 100 | 4 | 11 | 0.790 |
| 250 | 4 | 28 | 0.831 |
| 500 | 5 | 56 | 0.881 |
| 1000 | 6 | 111 | 0.880 |
| 4000 | 9 | 444 | 0.903 |

Effective n is `T(1-rho)/(1+rho)`, the independent-observation equivalent. At four
thousand observations the interval is still four and a half points short. This is
the known finite-sample behaviour of kernel HAC estimators (Andrews 1991;
Kiefer and Vogelsang 2002), not news to that literature — but it is a long way
from what a thousand-observation time series feels like it should give you, and
neither the docs nor the lag rule say so.

### Why neither sibling repository can see this

Worth stating plainly, because it marks the boundary of the comparison method.
This repository asks whether two implementations agree; they do, once pinned, to
6e-16. `kasauti` asks whether a number moved between releases; it has not moved,
so there is nothing to report. A property that is wrong in both languages and
wrong in every release is invisible to both instruments. Measuring against a
known truth is a third axis, and it is the only one that could have produced the
table above.
