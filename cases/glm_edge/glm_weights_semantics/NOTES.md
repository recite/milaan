# GLM weights: everything agrees except the degrees of freedom

The first case here that does not ask whether two packages agree with each
other. It asks whether each package agrees with **itself** under a
transformation that cannot change the answer: writing the same dataset as six
counted covariate patterns, or as thirty-three individual rows.

If `weights` means "this row happened `w` times", the two files are the same
data and every quantity computed from them must match. That is a metamorphic
invariant, and it needs no second implementation to check — which is the point.
Cross-implementation agreement cannot catch an error two packages share; an
invariant a package violates on its own terms is caught with no comparison at
all.

## What each backend does with itself

| backend | coefficients | standard errors | residual df |
|---|---|---|---|
| R `glm(weights=)` | ok | ok | **FAIL — 3 vs 30** |
| statsmodels `freq_weights=` | ok | ok | ok |
| statsmodels `var_weights=` | ok | ok | **FAIL — 3 vs 30** |

Two things came out differently from how the case was first written, and both
are worth stating.

**Standard errors agree everywhere, including under `var_weights`.** The case was
built expecting the SE invariant to be what separates a frequency reading from a
variance reading. It isn't — not for a binomial family. The binomial variance
function already carries the trial count, so the two readings coincide on the
information matrix and all three backends reproduce the expansion's standard
errors. The invariant that was supposed to discriminate turns out not to.

**R's SE "failure" was the tolerance, not the package.** At `tol: 1e-8` R failed
this invariant at a ratio of 1.000006477. The two sides are separately converged
IRLS fits, and that ratio is R's own convergence tolerance showing through — not
a claim about weights. The invariant now runs at 1e-5 and the comment records
why. Reporting the original as a finding would have been wrong.

## The finding that survives

Residual degrees of freedom, on identical data with identical coefficients and
identical standard errors:

- **statsmodels `freq_weights`: 30** — 33 observations minus 3 parameters
- **R `glm(weights=)`: 3** — 6 written rows minus 3 parameters
- **statsmodels `var_weights`: 3**

A factor of ten, and nothing warns. R's behavior is defensible and documented:
for a binomial family `weights` is the number of trials, so each row is one
binomial observation and six rows is six observations. But a user who reaches for
`weights=` to mean "this pattern occurred seven times" gets coefficients and
standard errors that are exactly right, and a residual degrees of freedom that is
off by an order of magnitude — which propagates into every t statistic, every F
test, and every confidence interval built from the fit's df rather than from its
standard errors directly.

The three backends agreeing on the coefficient and disagreeing on the denominator
is the worst shape for this kind of error. Anything that disagreed loudly would
be noticed.

## Why the invariant found it and comparison would not have

Run only as a cross-implementation comparison, `df.residual@weighted` splits
2-to-1 and the natural reading is "statsmodels and R use different conventions,
pick one." The invariant reframes it: `freq_weights` reproduces the expansion and
the other two do not, so there is a fact of the matter about which one answers
the question the user asked, not merely a convention to choose between.

## Reproducing

```bash
milaan run glm_weights_semantics
```
