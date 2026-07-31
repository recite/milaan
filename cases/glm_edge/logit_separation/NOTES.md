# Separation: five implementations, five behaviors

Twelve observations. Every `x < 0` is a zero, every `x > 0` is a one. The
likelihood is monotone in the slope, so the maximum likelihood estimate is
`+inf` and **no finite answer is correct**. The question is not who is right. It
is what each package does when handed an impossible problem, and whether the user
is told.

| | `coef.x` | `se.x` | `pvalue.x` | told? |
|---|---|---|---|---|
| R `glm` | 45.42257793 | 73292.39 | **0.9995** | warns "fitted probabilities numerically 0 or 1"; `converged = TRUE` |
| R `logistf` (Firth) | 1.649993341 | 0.8118 | **0.00113** | n/a — the principled answer |
| `statsmodels.Logit` | — | — | — | **"Perfect separation or prediction detected"**, then `LinAlgError` |
| `sklearn` default | 1.441540494 | — | — | nothing |
| `sklearn` `penalty=None` | 14.79162764 | — | — | nothing |

## The p-value inverts

R's `glm` reports **p = 0.9995** for a predictor that separates the outcome
perfectly. Firth reports **p = 0.0011**. Same data, opposite conclusions, and the
0.9995 is the one that comes out of the function nearly everyone calls.

This is the Hauck–Donner effect: the Wald statistic is `beta / se(beta)`, and under
separation the standard error diverges faster than the coefficient, so the ratio
collapses toward zero. The Wald test is simply the wrong instrument here. A
likelihood ratio or penalized-likelihood test is not fooled.

## The coefficients are tolerance settings, not estimates

Neither solver stops because it ran out of iterations. Both stop on their
convergence tolerance, and both report success:

| R `glm`, varying `epsilon` | | `sklearn` `penalty=None`, varying `tol` | |
|---|---|---|---|
| 1e-8 (default) | 45.422578 | 1e-4 (default) | 14.791628 |
| 1e-10 | 55.403263 | 1e-6 | 23.107499 |
| 1e-12 | 61.545469 | 1e-8 | 32.811530 |
| 1e-14 | 61.545469 | 1e-12 | 50.833357 |

`converged = TRUE` at every row on the left; `n_iter` far below the cap at every
row on the right. Raising R's `maxit` from 25 to 200 changes nothing — the
deviance criterion is met at iteration 25 either way. The reported coefficient is
a property of the stopping rule.

## scikit-learn's default is a different model

`LogisticRegression()` applies L2 regularization at `C=1.0` unless told otherwise.
Nothing at the call site says so. On this data that is the whole difference between
1.44 and an unbounded estimate:

| `C` | 1 | 10 | 100 | 1e4 | 1e8 |
|---|---|---|---|---|---|
| `coef.x` | 1.441540 | 3.070246 | 5.810645 | 12.442809 | 14.791370 |

So the default answer, 1.44, is a function of a penalty strength the user never
chose. It is finite, small, and entirely plausible — which is exactly what makes it
dangerous. A user who fits `LogisticRegression()` on separated data gets a
publishable-looking coefficient for a model they did not specify, with no warning,
no standard error, and nothing to suggest the MLE does not exist.

(As of scikit-learn 1.8 the `penalty` argument is deprecated in favour of
`l1_ratio` and `C`, and is slated for removal in 1.10. The unpenalized fit is
becoming harder to ask for, not easier.)

## statsmodels comes out best

It is the only backend that names the actual problem — *"Perfect separation or
prediction detected, parameter may not be identified"* — before failing with
`LinAlgError: Singular matrix`. Refusing to return a number for a quantity that
does not exist is the correct behavior, and it is worth being explicit that the
backend recorded here as `status: "error"` is the one that handled the case best.
The schema records errors as results for exactly this reason.

## What to do instead

Firth's penalized likelihood (`logistf` in R, `firthlogist` in Python) puts a
Jeffreys prior on the coefficients, which guarantees finite estimates and removes
the first-order bias. It is the reference row in the table above, not another
contender.
