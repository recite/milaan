# The default binomial interval, and what it does at small p

## The call

```python
from statsmodels.stats.proportion import proportion_confint

proportion_confint(0, 20)  # -> (0.0, 0.0)
```

Zero successes in twenty trials, and the default 95% interval is a point. Not a
wide interval, not a badly centred one: it asserts that the proportion is
exactly zero, with 95% confidence, from twenty observations. Nothing warns.

R, asked the same question:

```r
binom.test(0, 20)$conf.int   # [0.0000, 0.1684]
prop.test(0, 20)$conf.int    # [0.0000, 0.2005]
```

The signature is `proportion_confint(count, nobs, alpha=0.05, method='normal')`,
and `'normal'` is the Wald interval `p̂ ± z·sqrt(p̂(1-p̂)/n)`. At `p̂ = 0` the
standard error is zero, so the interval collapses. Neither of R's two standard
entry points defaults to Wald: `prop.test` is Wilson with a continuity
correction, `binom.test` is Clopper-Pearson.

## Coverage

Binomial coverage does not need simulating. There are `n + 1` possible outcomes,
so summing the binomial mass over those whose interval contains `p` gives the
answer exactly. Both languages compute it that way and agree on the Wald column
to three decimals, which is the check that the estimator itself is not in
dispute — only the default is.

Exact coverage, nominal 0.95:

| | | statsmodels default (Wald) | Wilson | Clopper-Pearson |
|---|---|---|---|---|
| p = 0.5 | n = 20 | 0.959 | 0.959 | 0.959 |
| | n = 1000 | 0.946 | 0.946 | 0.954 |
| p = 0.05 | n = 20 | **0.639** | 0.925 | 0.984 |
| | n = 50 | 0.920 | 0.962 | 0.988 |
| | n = 100 | **0.877** | 0.966 | 0.983 |
| | n = 1000 | 0.942 | 0.950 | 0.958 |
| p = 0.01 | n = 20 | **0.182** | 0.983 | 0.983 |
| | n = 50 | **0.395** | 0.911 | 0.986 |
| | n = 100 | **0.633** | 0.921 | 0.982 |
| | n = 200 | 0.865 | 0.948 | 0.984 |
| | n = 1000 | 0.927 | 0.964 | 0.976 |

A nominal 95% interval that contains the truth 18% of the time.

## Where the 0.182 comes from

Entirely from the degenerate interval, and this is exact rather than
approximate:

| n | P(x = 0 \| p = 0.01) | coverage |
|---|---|---|
| 20 | 0.818 | 0.182 |
| 50 | 0.605 | 0.395 |
| 100 | 0.366 | 0.633 |
| 200 | 0.134 | 0.865 |

`0.182 = 1 - 0.99²⁰`. Every draw with no successes returns `(0, 0)`, which
cannot contain any positive `p`, so coverage is capped at `P(x ≥ 1)`. At n = 20
and n = 50 that cap *is* the coverage, to four decimal places.

It stops being the whole story further out. At n = 500 the degenerate interval
fires 0.7% of the time and coverage is still 0.871, and at n = 1000 it
effectively never fires and coverage is 0.927. Past the boundary case the Wald
interval is simply mis-centred and too short, which is a separate defect from
the collapse and does not go away as fast.

## Two things worth separating

**That the Wald interval is bad is textbook.** Brown, Cai and DasGupta (2001)
call its coverage "persistently chaotic" and the paper is the standard citation.
Nothing above is news to that literature, and it should not be presented as a
discovery.

**What the measurement adds is that it is the default, and only in Python.**
The literature says do not use this interval. `proportion_confint` uses it
unless you say otherwise, and `statsmodels.stats.proportion` is where a Python
user lands. Both R entry points default elsewhere. So the same analysis, ported,
silently changes from an interval that over-covers to one that covers 18% of the
time — and the docstring does not mark `'normal'` as the choice the literature
advises against.

**And more data does not reliably fix it.** At p = 0.05 coverage goes 0.639 at
n = 20, up to 0.920 at n = 50, then back *down* to 0.877 at n = 100. Coverage
oscillates with n rather than climbing, so there is no sample size past which a
user can stop worrying, and no warning threshold that would be honest to add.
"n is large enough" is not a defence available here.

## Why this one is worth probing at all

The criterion the sibling cases use: a probe that checks a correct
implementation under its own assumptions only reproduces a theorem. This is not
that. The Wald interval is implemented correctly — R and Python agree on it to
three decimals — and the gap is between the package's default and the
situation an applied user is actually in. Rare events are the common case in
calibration work, A/B tests on low-conversion funnels, and any per-bin
proportion in a reliability diagram, all of which are small `p` at modest `n`.

## Why neither sibling instrument can see it

`kasauti` asks whether a number moved between releases. This one has not moved;
`method='normal'` has been the default for as long as the function has existed,
so there is no episode.

This repository asks whether two implementations agree. On the *estimator* they
do, exactly. The disagreement is in what each ecosystem hands you when you do
not choose — which shows up here only because the case was written to compare
defaults rather than to pin them.

Measuring against a truth we set is what produces the 0.182.

## Reproducing

```bash
uv run python cases/proportions/binomial_ci_default/coverage_py.py   # tables
uv run pytest cases/proportions/binomial_ci_default/coverage_py.py   # gates
Rscript --vanilla cases/proportions/binomial_ci_default/coverage_r.R
```

Under pytest, three tests pass and one fails. The failing one is the finding:

```
AssertionError: statsmodels default, n=20 p=0.01 coverage: observed rate 0.1757
outside the 3-sigma band [0.9397, 0.9603] for a nominal 0.9500 over 4000 replicates
```

The three that pass are what make that one mean something: the simulated
coverage is checked against the exact enumerated value before anything is
concluded from it; Wilson at n = 100, p = 0.2 covers and passes the same gate,
so the harness is not simply reporting failure for everything; and the
degenerate interval is asserted directly, separately from the rate it causes.
