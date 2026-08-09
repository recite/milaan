# Verification probes: the protocol

A probe asks one question of one method: **does its stated inferential guarantee
hold, on data that satisfies its own assumptions?**

This is not the question the rest of this repository asks. `cases/` compares two
implementations on one dataset. A probe compares one implementation against a
truth we set ourselves, over many datasets, at several sample sizes.

## Why a protocol at all

The obvious way to do this work is also the way that makes it worthless: probe
twenty methods, write up the three that failed, and present the result as a
finding about statistical software. That is the same selection pathology the
work would be criticising, and a reader cannot distinguish it from an honest
survey after the fact.

Everything below exists to make that impossible, and to make the absence of it
checkable by someone who does not trust us.

## 1. Targets are selected by a rule

The frame is `data/sampling_frame.csv` — function-level usage across 1,233
published replication archives, from [softverse](https://github.com/recite/softverse).

A function enters the queue if all four hold:

1. **It makes an explicit inferential guarantee.** A nominal coverage, a size,
   an FDR bound, an unbiasedness claim. A point estimator with no uncertainty
   statement is out of scope.
2. **The guarantee is falsifiable by simulation.** There must exist a data
   generating process where the estimand is known by construction.
3. **The method is recent enough to be under-scrutinised** — roughly post-2015.
   This is the criterion that separates this work from re-measuring textbook
   results. The Wald binomial interval, Welch versus Student, and the two-way
   fixed effects DiD bias are all real, all measurable, and all settled; a probe
   of any of them reproduces a literature rather than adding to one.
4. **It clears a usage floor in the frame.** A guarantee nobody relies on is not
   worth the compute.

The queue is `QUEUE.md`, committed, ordered, and worked in order. Skipping a
target requires a written reason in that file.

## 2. Every probe is pre-registered

Before any result exists, the probe directory contains `preregistration.yaml`
and nothing else. It records:

| field | why |
|---|---|
| `claim` | quoted verbatim from the paper or the package documentation, with the source. Paraphrasing lets the claim drift toward whatever was measured. |
| `dgp` | how the data is generated and what the estimand is by construction. |
| `assumptions` | a checklist of the method's stated conditions, each marked as satisfied by this DGP, and **executable wherever possible** — assert parallel trends holds in the generated data rather than asserting it in prose. |
| `sweep` | the sample sizes. An asymptotic guarantee cannot be refuted at one `n`. |
| `reps`, `seed`, `gate` | the simcheck gate and the replicate count it derives its band from. |
| `prediction` | what we expect to happen, recorded so that a confirmed prior and a surprise stay distinguishable afterwards. |

Then it runs, once. **Re-running after seeing a result requires a new
registration that says why**, kept alongside the first.

The check on all of this is git: a registration whose commit postdates its
result is disqualified. That is verifiable by anyone, without trusting us.

## 3. The DGP must satisfy the method's assumptions

Violate them and a failure means nothing. This is the criterion that killed the
Benjamini-Hochberg probe earlier in this project, applied in the other
direction: BH is *proved* to control FDR under positive regression dependence,
so a probe constructed there could only reproduce the theorem. Equally, a probe
that breaks a method's stated conditions and reports that it broke has measured
nothing but its own DGP.

Adversarial is allowed and wanted. Out-of-assumption is not.

## 4. Verdicts come from a fixed vocabulary

| verdict | meaning |
|---|---|
| `HOLDS` | the nominal rate is met across the whole sweep. |
| `SLOW` | asymptotically fine, but not yet at the sizes measured. **Report the `n` at which it arrives.** Not a refutation — and that rate is usually the most useful number the probe produces. |
| `FAILS` | misses within its own stated assumptions, at sample sizes the method is sold for. |
| `DEFECT` | an implementation bug rather than an approximation. Must be reproducible and minimal, and gets reported upstream. |

`SLOW` is expected to be the modal verdict. Recording it as `FAILS` because that
reads better is the single easiest way to discredit the whole corpus.

No `FAILS` may be recorded from a single sample size. Distinguishing it from
`SLOW` is exactly what the sweep is for.

## 5. Everything is reported

Nulls included, with the denominator. A `HOLDS` on a heavily-used method is a
public good in its own right, and it is also the thing that makes the failures
credible — a corpus containing only failures is indistinguishable from a broken
instrument.

For that reason the pilot deliberately includes a target expected to pass. It is
a positive control, not filler.

### A control's falsifier must be one-sided

Learned from the first one. The `clubSandwich` control registered its falsifier
as "coverage outside the band at any G", and that fired — CR2 covers 0.9765 at
five clusters against a nominal 0.95.

But a control that misses **conservatively** still demonstrates a working
harness; one that misses **liberally** does not. A two-sided falsifier conflates
the two, and would have condemned the instrument on evidence that in fact
vindicated it. Controls therefore register a one-sided falsifier, and a
conservative miss is recorded as `HOLDS` with the direction and the width cost
stated.

The same probe also shows how the harness earns trust independently of its
control's verdict: the CR1 arm reproduced the textbook under-coverage
(0.716 at G=5 rising to 0.927 at G=40), which is only possible if the DGP
carries the within-cluster correlation it claims to.

## Layout

```
probes/
├── PROTOCOL.md                 this file
├── QUEUE.md                    the ranked target queue and the selection rule applied
└── <package>/<claim>/
    ├── preregistration.yaml    committed BEFORE the probe runs
    ├── probe.R | probe.py      writes per-replicate results as JSON
    ├── gate.py                 loads the JSON, builds a MonteCarloResult, calls simcheck
    ├── results.json            machine-written
    └── NOTES.md                the write-up, written last
```

R probes are subprocesses that write JSON, reusing `milaan.runner.run_backend`
(timeouts, `MILAAN_LIB`, `optional: true` so a missing Rscript skips rather than
fails, `sha256_file` for provenance). The gate is always Python and always
simcheck, so that the tolerance comes from the replicate count and never from a
number someone picked — including for findings whose estimator is R.

## What a probe may not do

- Quote a number in prose that its committed reproducer does not print.
- Report coverage without also reporting interval width. A vacuous interval
  covers everything; a gate that cannot see that is not a gate.
- Record a verdict for a method whose assumptions the DGP violates.
- Silently drop a target from the queue.
