# Sun & Abraham via `fixest::sunab`: does the fix's inference hold?

**Verdict: `HOLDS`** on both registered claims. The registered *secondary*
suspicion is **`UNINFORMATIVE`** — this DGP could not test it, and saying so is
the point of this note.

## Why this probe exists

`../../FINDINGS.md` records that under staggered adoption with dynamic effects,
the two-way fixed effects coefficient recovers 0.025 against a truth of 4.875
and has the wrong sign 35% of the time. Sun & Abraham (2021) is what applied
researchers are told to use instead. Nobody had publicly asked whether the
replacement's *inference* works.

## What was measured

Staggered adoption, three adopting cohorts plus a never-treated group, 12
periods, effects growing with time since adoption and strictly positive.
1000 replicates per cell, seed 20260808. fixest 0.14.2. 3000 replicates, zero
failures.

simcheck's 3-sigma band at 1000 replicates: **[0.9293, 0.9707]**.

| units | truth | sunab | bias | TWFE | TWFE bias |
|---|---|---|---|---|---|
| 40 | 4.000 | 3.999 | **−0.001** | 2.001 | −1.999 |
| 80 | 4.000 | 3.997 | **−0.003** | 1.999 | −2.001 |
| 200 | 4.000 | 3.999 | **−0.001** | 1.999 | −2.001 |

| units | sd(est) | SE default | SE cluster | cover default | cover cluster |
|---|---|---|---|---|---|
| 40 | 0.1460 | 0.1486 | 0.1483 | 0.953 | 0.941 |
| 80 | 0.1075 | 0.1055 | 0.1054 | 0.948 | 0.938 |
| 200 | 0.0657 | 0.0667 | 0.0667 | 0.950 | 0.953 |

Unbiased to three decimal places at every panel size, and the reported standard
error matches the actual sampling spread. Coverage is inside the band in all six
cells.

## Two checks had to pass before any of that counted

**The estimand check: 3000/3000.** `sunab`'s `agg="att"` averages over the
relative periods it estimates, which is not automatically "every treated
observation". Had those sets differed, the truth computed here would have been
the wrong target and the difference would have been an estimand mismatch
reported as bias. The probe asserts the sets match per replicate rather than
assuming it, because this is the way this probe could most easily have
manufactured a finding out of nothing.

**The sensitivity check: TWFE is off by −2.0 at every panel size**, half the
true effect. The failure sunab exists to remove was present throughout, so
`HOLDS` here is a real pass rather than a vacuous one.

## The registered suspicion is refuted, and that is not the same as "IID is fine"

The registration recorded, in advance, a suspicion: fixest 0.14.2 defaults to
IID standard errors (`../../FINDINGS.md`), so the fix for the TWFE bias might
ship with inference that does not hold.

It does not, here. The default SE and the clustered SE are **0.1486 against
0.1483** — indistinguishable, and both match `sd(est)`.

But the honest reading is not that the IID default is safe. It is that **this
DGP has nothing for clustering to catch.** Untreated potential outcomes are a
unit fixed effect plus i.i.d. noise, and the unit fixed effect is absorbed by
the estimator, so no within-unit correlation survives into the residuals. The
two standard errors coincide because there is no clustering left, not because
clustering does not matter.

Applying §3a's logic to the secondary question: the run never exercised the
failure mode, so the verdict on it is **`UNINFORMATIVE`**, not `HOLDS`. Testing
it properly needs serial correlation within unit — an AR(1) error, as in the
`feols` default-VCOV entry in FINDINGS.md, where IID covered 0.764 against
0.958 clustered. That is a separate registration and it is not written yet.

Recording a refuted suspicion as a pass would have been the more comfortable
write-up and the wrong one.

## What this is

A `HOLDS` on the method the discipline moved to. Given that the thing it
replaced returns the wrong sign a third of the time, "the replacement's point
estimate is unbiased and its interval covers" is worth having measured rather
than assumed — and nobody had.

It is not a general endorsement. One DGP, balanced cohorts, a never-treated
group present, no anticipation, homoskedastic i.i.d. errors. The design without
a never-treated group — where the estimand ambiguity is real and my minimal
Callaway–Sant'Anna implementation also degraded — is not covered here.

## Reproducing

```bash
Rscript --vanilla probe.R results.json.gz
uv run python probes/fixest/sunab_staggered_adoption/gate.py   # the tables
uv run pytest probes/fixest/sunab_staggered_adoption/gate.py   # the gates
```

Four gates, all passing: the estimand check, the sensitivity check, and the two
registered claims.

## One process note

The first run of this probe failed **all 3000 replicates**. fixest rejects the
logical produced by `I(rel >= 0)` inside a formula, which killed the TWFE arm —
and the probe had both fits behind a single `try`, so a broken *sensitivity*
arm discarded 3000 perfectly good sunab measurements. The arms now fail
independently, and only the claim under test can void a replicate. It is also
why the second run was smoke-tested at three replicates before being launched
at a thousand.
