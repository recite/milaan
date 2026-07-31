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
