# grf causal forest: do the pointwise CATE intervals cover?

**Verdict: `SLOW`.** I registered a prediction of `FAILS`. The registration also
recorded what would make `SLOW` the honest answer instead — *"if it is clearly
climbing toward 0.95, SLOW is the honest verdict and the n at which it arrives
is the finding"* — and that is what the sweep shows. Recording it as `FAILS`
because that is the more striking headline is exactly the temptation the
taxonomy exists to remove.

## What was measured

Randomised treatment with known propensity, ten covariates, effect
`tau(x) = 1 + 2·x1` varying in one coordinate, 2000 trees, grf's honesty
default. 1320 replicates. grf 2.6.1.

Coverage at each fixed test point, evaluated across replicates (predictions at
different `x` within a replicate are dependent, so they are not pooled):

| n | reps | x1=0.1 | x1=0.3 | x1=0.5 | x1=0.7 | x1=0.9 | ATE |
|---|---|---|---|---|---|---|---|
| 500 | 800 | **0.631** | 0.955 | 0.932 | 0.939 | **0.655** | 0.926 |
| 2000 | 400 | 0.875 | 0.940 | 0.938 | 0.940 | 0.860 | 0.930 |
| 4000 | 120 | 0.917 | 0.933 | 0.933 | 0.942 | 0.933 | 0.917 |

3-sigma bands: `[0.9269, 0.9731]` at 800 reps, `[0.9173, 0.9827]` at 400,
`[0.8903, 1.0000]` at 120.

## The interior is fine; the boundary is not

Every interior point — x1 = 0.3, 0.5, 0.7 — sits inside the band at every
sample size. The failure is entirely at the two boundary points, and the bias
column says why:

| n | bias x1=0.1 | x1=0.3 | x1=0.5 | x1=0.7 | bias x1=0.9 |
|---|---|---|---|---|---|
| 500 | **+0.1786** | −0.0002 | +0.0099 | +0.0077 | **−0.1691** |
| 2000 | +0.0546 | +0.0148 | +0.0065 | −0.0003 | −0.0538 |
| 4000 | +0.0288 | +0.0209 | −0.0052 | −0.0163 | −0.0242 |

The bias is symmetric and points inward: **positive where the true effect is
smallest, negative where it is largest**. A forest at x1 = 0.1 can only average
over neighbours on one side, and those neighbours have larger effects, so the
estimate is pulled up. At x1 = 0.9 it is pulled down. Interior points have
neighbours on both sides and the pulls cancel.

At n = 500 the bias at the boundary is 0.179 against a true effect of 1.2, and
the interval is centred 0.179 away from the truth while being sized for
sampling error alone. That is why coverage is 0.63.

## Why `SLOW` rather than `FAILS`

Boundary coverage climbs 0.631 → 0.875 → 0.917, and the bias falls at roughly
`n^-0.85` then `n^-0.92` — close to `1/n` and faster than the standard error's
`1/√n`, which is precisely the condition the asymptotic theory needs. The
guarantee is arriving; it is simply not there at n = 500.

Two honest caveats on the largest cell:

- **120 replicates cannot resolve it.** The band at n = 4000 is
  `[0.8903, 1.0000]`, so 0.917 is *inside* it. That cell contributes direction,
  not a verdict. It is short because a single forest at n = 8000 measured at 33
  minutes, so the registered sweep was re-scoped on compute grounds before any
  rate was seen — see `sweep_amendment` in the registration.
- **The ATE control is marginal at n = 500**: 0.926 against a band starting at
  0.9269. Inside the band at n = 2000 and n = 4000. It is not clean enough to
  say the harness is beyond suspicion at the smallest size, and that is worth
  stating rather than rounding away.

## What this is

The forest's own CATE interval, at grf's defaults, covers 63% at a nominal 95%
near the edge of the covariate range at n = 500. Applied users read pointwise
CATE intervals to identify who benefits most and least — and the extremes of the
covariate distribution are exactly where that question is asked, and exactly
where these intervals are worst.

The registration named the assumption most likely to be doing the work: grf's
subsampling-rate conditions, which applied users never set. This probe tested
**the defaults**, not the theorem. The theorem is asymptotic and the measurement
is consistent with it.

## Reproducing

```bash
Rscript --vanilla probe.R results.json.gz   # ~20 min; resumable
uv run python probes/grf/causal_forest_cate_ci/gate.py   # the tables
uv run pytest probes/grf/causal_forest_cate_ci/gate.py   # the gates
```

The sensitivity gate passes; the CATE gate fails at the boundary points, and the
ATE gate fails only at n = 500.

## A process note worth keeping

This probe was killed four times and timed out once. The first version wrote
output only at the end and lost five hours. Per-cell checkpointing then lost a
cell to a mid-cell kill. Per-cell *resume* would have silently double-counted
374 replicates on restart — coverage is a mean over rows, so it would have
reported a corrupted rate under a clean `complete: true`.

The fix was to seed each replicate from `(SEED, n, r)` alone, which is
simcheck's own rule for its runner. A truncated run then resumes to
**bit-identical** estimates. None of those three defects was found by reasoning
about the code; each was found by reading what an interruption actually left on
disk.
