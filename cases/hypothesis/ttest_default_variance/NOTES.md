# The two-sample t-test: opposite defaults, and a 44% false-positive rate

## The call

```python
scipy.stats.ttest_ind(a, b)  # equal_var=True  -> pooled Student
```
```r
t.test(a, b)                    # var.equal=FALSE -> Welch
```

The same test in the user's head, the opposite assumption underneath. Nothing
warns in either direction.

## Size under a true null

Both groups drawn with mean zero, so every rejection is a false positive. Only
the variances and the group sizes differ. 20,000 replicates, nominal 0.05.

| n₁ | n₂ | sd₁ | sd₂ | scipy default | Welch (R default) |
|---|---|---|---|---|---|
| 10 | 10 | 1 | 1 | 0.0498 | 0.0483 |
| 10 | 10 | 1 | 4 | 0.0612 | 0.0508 |
| 10 | 30 | 1 | 1 | 0.0489 | 0.0493 |
| 10 | 30 | 4 | 1 | **0.2377** | 0.0493 |
| 10 | 30 | 1 | 4 | **0.0022** | 0.0498 |
| 20 | 60 | 4 | 1 | **0.2289** | 0.0503 |
| 5 | 45 | 4 | 1 | **0.4411** | 0.0512 |
| 10 | 100 | 4 | 1 | **0.4427** | 0.0481 |

Two directions, and both matter:

- **The smaller group has the larger variance** → the test rejects far too
  often. At n = (10, 100) it rejects 44% of the time when nothing is going on,
  nine times the rate it advertises.
- **The larger group has the larger variance** → 0.0022, a test that rejects
  once in every four hundred and fifty. It is not detecting anything, and
  nothing says so.

Welch sits between 0.0481 and 0.0512 in every cell.

## More data makes it worse

Hold the small group at ten and add observations only to the large one:

| n₁ | n₂ | total | scipy default | Welch |
|---|---|---|---|---|
| 10 | 10 | 20 | 0.0599 | 0.0496 |
| 10 | 20 | 30 | 0.1618 | 0.0492 |
| 10 | 30 | 40 | 0.2377 | 0.0493 |
| 10 | 60 | 70 | 0.3651 | 0.0485 |
| 10 | 100 | 110 | 0.4427 | 0.0481 |
| 10 | 300 | 310 | 0.5498 | 0.0493 |
| 10 | 1000 | 1010 | 0.5991 | 0.0490 |

The size does not converge to 0.05. It converges to about 0.60. Collecting more
data in the group that is cheap to sample — which is the usual reason group
sizes end up unequal — moves the false-positive rate *up*, monotonically. This
is the part that makes it dangerous in practice: the usual defence, that
asymptotics will sort it out, runs the wrong way here.

## The estimator is not in dispute

`size_r.R` runs both variants from R on the same design:

| design | scipy default | R `var.equal=TRUE` | scipy Welch | R Welch |
|---|---|---|---|---|
| (10,30) sd (4,1) | 0.2377 | 0.2389 | 0.0493 | 0.0527 |
| (20,60) sd (4,1) | 0.2289 | 0.2279 | 0.0503 | 0.0521 |
| (5,45) sd (4,1) | 0.4411 | 0.4482 | 0.0512 | 0.0537 |
| (10,100) sd (4,1) | 0.4427 | 0.4437 | 0.0481 | 0.0509 |
| (10,30) sd (1,4) | 0.0022 | 0.0021 | 0.0498 | 0.0508 |

Agreement to Monte Carlo error, cell for cell. Both languages implement both
tests correctly. The entire difference is which one you get when you do not
say.

## What is known, and what the measurement adds

**The Behrens-Fisher problem is old and the recommendation is settled.** Welch
is nearly as powerful as the pooled test when variances *are* equal and vastly
better when they are not; Ruxton (2006) and Delacre, Lakens and Leys (2017) both
argue it should simply be the default. R agrees, and has for a long time. None
of that is new here and it should not be dressed up as a discovery.

**What the measurement adds is the size of it, and where it lands.** The pooled
test is scipy's default, `scipy.stats.ttest_ind` is where a Python user goes,
and the two-sample t-test is the most-used procedure in applied statistics. A
9× false-positive rate on the most common test in the language's most common
statistics package is worth having a number for. So is the direction: it gets
worse with more data, not better.

**And a pre-test does not rescue it.** Screening with Levene or Bartlett first
and then choosing is the intuitive fix and a well-documented mistake — the
conditional procedure has its own distorted size, because you are choosing the
test using the data you then test with. Use Welch.

## Why this one is worth probing at all

The criterion the sibling cases use: a probe that checks a correct
implementation under its own assumptions only reproduces a theorem. The pooled
t-test *is* correct under its own assumption, and the passing sanity check in
`size_py.py` confirms it — with equal variances the default holds 0.0489. The
gap is between the assumption the API makes silently and the situation an
applied user is in, which is unequal groups with unequal spread more often than
not.

## Why neither sibling instrument can see it

`kasauti` asks whether a number moved between releases. `equal_var=True` has
been the default for as long as the function has existed, so nothing moved and
there is no episode.

This repository asks whether two implementations agree. On both estimators they
do, to Monte Carlo error — the table above is the proof. The disagreement is in
the defaults, which surfaces only because this case was written to compare what
each language hands you rather than to pin the options and check the arithmetic.

Setting the truth ourselves is what produces the 0.44.

## Reproducing

```bash
uv run python cases/hypothesis/ttest_default_variance/size_py.py   # tables
uv run pytest cases/hypothesis/ttest_default_variance/size_py.py   # gates
Rscript --vanilla cases/hypothesis/ttest_default_variance/size_r.R
```

Under pytest two tests pass and one fails. The failure is the finding:

```
AssertionError: scipy default, n=(10,100) sd=(4,1): observed rate 0.4427
outside the 3-sigma band [0.0454, 0.0546] for a nominal 0.0500 over 20000 replicates
```

The two that pass are what make it mean something: with equal variances the
default holds its size, so this is not "the pooled test is broken"; and Welch
holds its size on the identical design at the identical seed, so this is not
"unequal variances are hard".
