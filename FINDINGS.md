# What the defaults cost

A running log. The README's table asks whether two implementations *agree*.
This file asks a different question of the same procedures: when you accept a
default and your data is not what the default assumes, **what rate do you
actually get?**

> This file is the **defaults** log, and it is deliberately separate from
> `probes/`. Everything here concerns a settled estimator reached through an
> unlucky default — real, worth recording, and mostly textbook. `probes/` is the
> pre-registered verification corpus, which asks whether a *recent* method's
> guarantee holds at all. Different question, different bar, different protocol.

Every entry sets the truth itself, so there is a right answer to compare
against. Every claim below is produced by a committed reproducer and gated with
[simcheck](https://github.com/finite-sample/simcheck), whose tolerance comes
from the replicate count rather than from a number someone picked.

Negative results are logged too. A file with only hits is a highlight reel.

---

## The selection criterion

A probe that checks a correct implementation **under its own assumptions** can
only reproduce a theorem. That is why the Benjamini–Hochberg probe was dropped:
BH is proved to control FDR under positive regression dependence, so measuring
it there confirms the proof and nothing else.

What is worth measuring is the gap between a package's **default** and the
**situation the user is actually in**. A default is a decision made silently on
the user's behalf. Every hit below has the same shape:

> The estimator is implemented correctly, and identically in both languages —
> often to Monte Carlo error or better. The entire failure lives in what each
> ecosystem hands you when you do not choose.

---

## Findings

### `scipy.stats.ttest_ind` — 44% false positives at a nominal 5%

`cases/hypothesis/ttest_default_variance/` · measured 2026-08-08

| | |
|---|---|
| **The default** | `equal_var=True` — pooled Student |
| **R's default** | `var.equal=FALSE` — Welch |
| **Claim** | size 0.05 under the null |
| **Worst measured** | **0.443** at n=(10,100), sd=(4,1), 20,000 replicates |
| **The good option** | Welch: 0.048–0.051 in every cell |
| **Warns?** | No |

Both directions bite. Smaller group carries the larger variance → nine times too
many false positives. Larger group carries it → **0.0022**, a test that fires
once in four hundred and fifty and detects nothing.

**More data makes it worse.** Holding the small group at ten and adding
observations only to the large one: 0.060 → 0.162 → 0.238 → 0.365 → 0.443 →
0.550 → 0.599. The size converges to **0.60, not 0.05**. Sampling more of
whichever group is cheap — the usual reason groups end up unequal — drives the
false-positive rate up monotonically.

R reproduces every cell to Monte Carlo error, so both languages implement both
tests correctly.

*Known:* Behrens–Fisher, and Welch is the settled recommendation (Ruxton 2006;
Delacre, Lakens & Leys 2017). *Added:* the magnitude, that it is the default in
the language's most-used stats package, and the direction.

---

### `statsmodels` `proportion_confint` — a zero-width 95% interval

`cases/proportions/binomial_ci_default/` · measured 2026-08-08

| | |
|---|---|
| **The default** | `method='normal'` — Wald |
| **R's defaults** | `prop.test` Wilson+cc, `binom.test` Clopper–Pearson |
| **Claim** | 95% coverage |
| **Worst measured** | **0.182** at p=0.01, n=20 (exact, by enumeration) |
| **The good option** | Wilson 0.983, Clopper–Pearson 0.983 |
| **Warns?** | No |

```python
proportion_confint(0, 20)   # -> (0.0, 0.0)
```

Zero successes in twenty trials and the interval is a **point** — it asserts the
proportion is exactly zero, with 95% confidence, from twenty observations.
`0.182 = 1 - 0.99²⁰` exactly: coverage is capped at `P(x ≥ 1)` because every
zero-success draw returns `(0, 0)`.

**More data does not reliably fix it.** At p = 0.05 coverage goes 0.639 at n=20,
*up* to 0.920 at n=50, then back *down* to 0.877 at n=100.

*Known:* Brown, Cai & DasGupta (2001) call Wald's coverage "persistently
chaotic". *Added:* it is the Python default and neither R default, so porting
silently swaps over-coverage for 18%.

---

### Cluster-robust SEs at few clusters

`cases/robust_se/cluster_small_g/` · measured 2026-08-05

| | |
|---|---|
| **The default** | `cov_type="cluster"` — CR1, normal critical value |
| **Claim** | 95% coverage |
| **Worst measured** | **0.730** at G=5 |
| **The good option** | `estimatr::lm_robust(se_type="CR2")` → 0.963 |
| **Warns?** | No |

statsmodels implements CR1 correctly and has no CR2 equivalent. It reports a
normal-based interval without marking that the nominal level is not what you get.

---

### Newey–West HAC: the conventions differ, and all of them under-cover

`cases/robust_se/hac_newey_west/` · measured 2026-08-05

| | |
|---|---|
| **The defaults** | R prewhitens and auto-selects bandwidth; statsmodels does neither and cannot prewhiten |
| **Claim** | 95% coverage |
| **Measured** | R default **0.863**; the statsmodels lag rule **0.801** |
| **Warns?** | No |

Point estimates differ **7×** out of the box. Once pinned to the same options
the two agree to 6e-16 — so this is convention, not defect. But the conventions
are not equivalent: the R default is better by about six points.

Separately, *every* variant under-covers, and slowly: 0.790 at T=100, 0.880 at
T=1000, still **0.903 at T=4000**. That part is textbook finite-sample HAC
behaviour (Andrews 1991; Kiefer & Vogelsang 2002) — the contribution is the
rate, not the existence.

---

### `fixest` changed its default VCOV, and every panel regression moved

Measured 2026-08-08 · `fixest` 0.14.2 · not committed as a case

| | |
|---|---|
| **The change** | fixest **0.13.0**, under "Breaking changes": *"the new default VCOV is `iid` for all estimations"* |
| **Before** | clustered by the first fixed effect |
| **Claim** | 95% coverage |
| **Measured** | IID **0.764**, `cluster=~firm` **0.958** |
| **Warns?** | prints `Standard-errors: IID`; no warning that the panel structure makes that a choice |

Bertrand–Duflo–Mullainathan design: G=40 firms × T=20 periods, AR(1) ρ=0.8 in
both `x` and the error, two-way fixed effects, 500 replicates. The fixed effects
absorb the level and not the serial correlation, so the IID standard error is
too small — mean interval width 0.144 against 0.252.

The consequence is not just the coverage. **The same script, unchanged, gives
different standard errors either side of a package upgrade**, and gets more
significant. `feols` is rank 79 in the frame with 117 scripts and 1054 calls.

This one is also squarely `kasauti`'s question — a number that moved between
releases — and unusually, the changelog *does* say so. "Documented, in a
breaking-changes section, and still easy to walk past" is its own category.

### `vcovHC` means two different estimators

Measured 2026-08-08 · `sandwich` 3.1.2, `plm` · not committed as a case

| package | default |
|---|---|
| `sandwich::vcovHC` | `type="HC3"` — heteroskedasticity-robust, **not** clustered |
| `plm::vcovHC` | `type="HC0"`, `method="arellano"` — **cluster-robust by group** |

Same call `vcovHC(m)`, and which estimator you get is decided by the model
object's class. Both packages appear in the frame under the same entry
(rank 111, 76 scripts, `packages: plm;sandwich`). On one panel: 0.0761
(sandwich HC3) against 0.0662 (plm arellano), with 0.0717 classical.

No coverage study run — the point here is the ambiguity of the call, not a rate.

## Negative results

### `scipy.stats.bootstrap` — no finding

Explored 2026-08-08, not committed as a case.

The hypothesis was sharp and wrong: that on skewed data the default BCa interval
would lose to the t-interval users reach for the bootstrap to avoid. It does not.

| lognormal(0, 1.5) mean | n=20 | n=50 | n=100 | n=500 | n=1000 |
|---|---|---|---|---|---|
| BCa (default) | 0.801 | 0.868 | 0.894 | 0.930 | 0.943 |
| percentile | 0.768 | 0.846 | 0.865 | 0.905 | 0.923 |
| basic | 0.713 | 0.781 | 0.822 | 0.877 | 0.917 |
| Student t | 0.768 | 0.832 | 0.858 | 0.885 | 0.923 |

BCa beats every alternative at every n. It under-covers for heavy skew, but that
is the known slow-convergence story the HAC case already carries, so a second
case would repeat a lesson rather than add one.

Worth recording as a contrast: on all-zero Bernoulli data scipy **warns and
declines** rather than returning a number. Given the same degenerate input,
statsmodels returns `(0.0, 0.0)` in silence.

### Benjamini–Hochberg under dependence — rejected before measuring

BH is proved to control FDR under positive regression dependence, which is the
case a probe would naturally construct. Measuring it reproduces the theorem. The
one number such a probe yields — that BY loses ~40% power — is arithmetic, not a
finding: BY divides by the harmonic sum, ≈5.9 at M=200.

---

## Why the sibling repositories cannot see any of this

`kasauti` asks whether a number moved between releases. None of these moved —
every default above has been the default for as long as the function has
existed, so there is no episode.

This repository asks whether two implementations agree. On the *estimators* they
do, in every case, often to machine precision. The disagreement is in the
defaults, and the cost of a default is not visible from a comparison at all.

Setting the truth ourselves is the only axis that produces the 0.443 and
the 0.182.
