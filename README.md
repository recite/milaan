# milaan

**मिलान** — tallying, matching, reconciliation.

Does R agree with Python? A measured catalogue of where equivalent-looking
statistical calls disagree, by how much, why, and what it takes to make them
agree.

Re-running an R analysis in Python is an ordinary thing to do — a coauthor
prefers pandas, a reviewer wants the pipeline in one language, a student
reimplements a published result. This repository measures what that costs.

Sibling to [recite/kasauti](https://github.com/recite/kasauti), which asks the
other question: did a package's *past* defect corrupt work already published.

## What it has found

Every number below was measured by running the thing, not predicted.

| finding | |
|---|---|
| `sd(x)` and `np.std(x)` differ on **every vector** | numpy divides by `n`, R by `n-1`; `1.534135400990` against `1.435052263857` |
| `t.test` and `ttest_ind` have **opposite defaults** | R is Welch, scipy is Student pooled |
| `scale()` and `StandardScaler` disagree by the same factor | the `ddof` gap, propagated into every standardised regressor |
| R and Python's Newey–West standard errors differ **7×** out of the box | neither is wrong; R prewhitens and auto-selects bandwidth, statsmodels does neither |
| `sklearn.LogisticRegression()` silently applies L2 at `C=1.0` | its "unpenalized" coefficient is a function of `tol`, not of the data |
| R's `glm` reports **p = 0.9995** where Firth reports **p = 0.0011** | separated data; the Wald statistic collapses as the standard error diverges |
| GLM residual df is **30 or 3** for the same fit | statsmodels `freq_weights` vs R `glm(weights=)`; coefficients and SEs agree exactly |
| Normal equations keep **7.1** correct digits where R's QR keeps **13.0** | NIST Longley; every backend agrees to 7 digits, so comparison alone calls it unanimous |
| Kernel density bandwidth differs **11%** | R's `nrd0` guards with the IQR, scipy's Scott does not — and `'silverman'` matches neither |
| `wilcox.test` and `mannwhitneyu` disagree only about **ties** | the asymptotic arithmetic is identical to 12 digits; the automatic choice under ties is not |
| `lm` and `OLS` agree to the last digit | coefficients, standard errors, R², F — the most-used procedure in the corpus ports cleanly |
| `quantile` (all nine R types), `cor`, `fisher.test`, `chisq.test`, BH adjustment agree **exactly** | confirmed agreement is a result, not an absence of one |

## Agreement is not correctness, and disagreement is usually not a bug

Most divergence traces to a choice someone made, not to a defect. So every
documented disagreement carries a **cause**:

| cause | meaning | example |
|---|---|---|
| `DEFINITION` | the two functions compute different quantities | `sd` vs `np.std` — different denominator |
| `DEFAULT` | same quantity, different default option | `t.test` Welch vs `ttest_ind` pooled |
| `ALGORITHM` | same quantity and options, different numerics | QR vs normal equations on Longley |
| `IRREDUCIBLE` | cannot agree by construction | seeded RNG streams |
| `BUG` | one of them is wrong | a metric returning 1.25 on `[0,1]` |

and a **reconciliation** — the exact argument that makes them agree, or an
explicit statement that none exists. That field is the deliverable: a porting
guide derived from measurement rather than folklore.

## The RNG problem, which is not a bug and cannot be fixed

In a corpus of 1,233 published replication archives, the four most-called Python
things are `numpy.random.randn` (316 scripts), `seed` (252), `RandomState` (230),
and `rand` (223). Random number generation is the single most common operation in
the Python half of the replication literature.

Seeded streams differ across languages by construction. `set.seed(42)` in R and
`np.random.seed(42)` in Python index different generators through different
initialisations, so **a simulation-based result is not cross-language
reproducible even in principle** — no argument reconciles it, and no one has made
a mistake. `cause: IRREDUCIBLE`, `reconcilable: false`.

There are three independent reasons, any one sufficient. The seed does not mean
the same thing — both legacy generators are Mersenne-Twister, but they scramble
42 into the state differently, so the *uniform* streams already diverge. The
uniform-to-normal transform differs — R's `RNGkind()` reports `Inversion`, and
you can watch it invert (`qnorm` of R's uniform stream reproduces `rnorm` to
eight digits, off only because R spends two uniforms building a
higher-precision one), while numpy's legacy path uses a rejection-based polar
method that consumes a variable number. And `default_rng` swaps the bit
generator itself for PCG64, so numpy is not even self-consistent across its own
APIs: code written before and after numpy 1.17 draws differently.

R is not self-consistent either: `sample()` changed in R 3.6.0, silently
altering every result that drew from it. That one *was* a defect — the old
method mapped uniforms to integers with a small non-uniformity, material at
large `n` — so the fix is right and the old results were slightly biased. It is
recoverable within a single R via `RNGkind(sample.kind = "Rounding")`, which
makes it measurable here rather than a matter of archaeology.

### What it costs, which is less than it sounds

Same data, same estimator, both seeded 42, bootstrapping a standard error:

| B | R | Python | gap |
|---|---|---|---|
| 100 | 0.1565550777 | 0.1472249202 | **6.0%** |
| 1,000 | 0.1609462901 | 0.1568576464 | **2.5%** |
| 10,000 | 0.1587754598 | 0.1590406451 | 0.17% |

The analytic standard error is 0.15891143 and both converge on it. So this is
Monte Carlo error, not bias, and nobody is mistaken. What breaks is *exact*
reproduction, and the residual is Monte Carlo error at a rate almost no paper
reports: at B = 1,000, a very common choice, the two languages differ by 2.5% on
a standard error, so a bootstrap SE quoted to three significant figures has a
third figure that will not survive the port — and usually would not survive a
different seed in the same language either. Seen that way the cross-language
problem is a special case of an unreported one.

Where it does not wash out is wherever B is fixed at one by design: a single
train/test split, one imputation, one random subsample. There the draw is not an
estimate of the result, it is the result.

## Cases are data, not code

A hand-written case costs roughly 150 lines across four files. That stops scaling
at about fifteen. So a comparison is a spec the harness interprets:

```yaml
id: dispersion_ddof
family: descriptives
quantity: "dispersion of a numeric vector"
dataset: small_numeric
reference: r_sd                      # R is the reference: most of the corpus is R
implementations:
  r_sd:        {lang: R,      expr: "sd(x)"}
  np_std:      {lang: Python, expr: "np.std(x)",          expect: DIVERGE}
  np_std_ddof: {lang: Python, expr: "np.std(x, ddof=1)",  expect: AGREE}
  pd_std:      {lang: Python, expr: "pd.Series(x).std()", expect: AGREE}
finding:
  cause: DEFINITION
  reconcilable: true
  reconciliation: "pass ddof=1 to numpy; pandas already defaults to n-1"
```

**Reference-relative, not all-pairs.** The question is directional — does the
Python equivalent reproduce the R number — so a spec names a reference and every
other implementation declares its expectation against it.

**Expectations are required, with reasons.** A spec that merely records what
happened is a snapshot. Declaring what *should* happen, and why, makes the suite
a regression test: `milaan run --all --strict` exits non-zero the day an
undocumented divergence appears.

Cases needing genuine setup — Firth logistic regression, four estimators on the
same design matrix — stay as longhand backend scripts. Both live under the same
runner.

## Verdict bands

| verdict | relative difference |
|---|---|
| `AGREE` | < 1e-8 |
| `NUMERIC` | < 1e-5 — same answer, different arithmetic path |
| `DIVERGE` | anything larger |

with a 1e-12 noise floor, so an exact `0.0` against an `8.2e-16` is agreement
rather than an 8e-4 relative gap.

## Backends are processes

R, Python, and any pinned old version are all just commands that write a common
JSON result schema. No `rpy2`, no in-process bridge, no shared interpreter state.
A backend that cannot run reports itself as skipped, and `status: "error"` is a
*result* — a case where one implementation refuses to fit is a finding, not a
harness failure.

## Depending on it

kasauti runs its version-regression cases through this harness. The R and Python
backend helpers ship inside the package, so an ordinary install is enough:

```toml
dependencies = ["milaan"]
```

A backend script finds them through `MILAAN_LIB`, which the runner exports.

## Usage

```bash
make install
milaan list                      # every comparison
milaan run --all --strict        # non-zero exit on any undocumented divergence
milaan report                    # re-render from results on disk
make check                       # lint, types, tests
```

## Which procedures, and why those

Selection is not taste, and `milaan coverage` is what makes that checkable rather
than merely asserted:

```
10 of the top 18 R procedures by corpus usage are covered by 22 comparisons

   #  scripts procedure              covered by
   7     1412 mean                   central_tendency, missing_value_policy
  14      855 log                    --
  18      690 rnorm                  seeded_streams
  20      643 lm                     nist_longley, linear_model, hac_newey_west, hc_variants
  ...
```

The ranking is what published replication archives actually call, measured across
9,343 R and 6,233 Python scripts — `data/sampling_frame.csv`, carried over from
kasauti with its provenance. Every comparison declares a `covers:` list, and the
uncovered rows are the work queue, in order.

Declared rather than inferred, deliberately. Guessing which procedure a spec
exercises by matching identifiers in its expression is the technique that, applied
to changelog prose in kasauti, credited `Matrix` with 3,562 scripts that meant
base R. A short expression is more tractable than prose, but a spec that aliases
`quantile` in its setup would still be missed, and a coverage report that quietly
undercounts is worse than none. A `covers:` entry the frame does not list is
reported as an error.

The denominator excludes data plumbing — `length` at 3,268 scripts, `names` at
1,954 — via a short visible list in `coverage.py`. Not because those are
uninteresting but because a spec about `nrow` would agree trivially, and counting
it as uncovered makes the queue look longer than it is. Anything that estimates a
quantity stays in scope, `mean` and `log` included.

## Limits

Confirmed agreement on one dataset is not agreement everywhere. These are
existence proofs about defaults and definitions, not proofs of equivalence — a
spec that agrees here can still diverge on data with different scale,
conditioning, or missingness.

The reference is R, which encodes an assumption rather than a judgment about
quality: most of the replication corpus is R, so "can Python reproduce this" is
the question people actually face. Where Python is the better implementation, the
catalogue says so in the `cause` field.
