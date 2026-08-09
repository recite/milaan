# The target queue

The selection rule is in `PROTOCOL.md` §1. This file applies it, shows the
working, and fixes the order. Targets are worked top-down; skipping one requires
a written reason recorded here.

## A tension in the rule, and how it is resolved

Criterion 3 wants **recent** methods, because settled ones have been picked over
already. Criterion 4 wants **used** methods, measured against
`data/sampling_frame.csv`.

Those fight each other, and pretending otherwise would quietly bias the queue.
The frame is built from Harvard Dataverse replication archives across 34 social
science journals — it measures usage in *published* work, so a method released in
2021 can only appear in papers submitted afterwards, and those archives are still
accumulating. **The frame lags by years and under-counts exactly the methods
criterion 3 is looking for.**

The resolution is to keep the frame as the primary signal and read it correctly
rather than to substitute a friendlier one:

- **A recent method already visible in a lagging corpus is heavily used now.**
  `att_gt` (9 scripts) and `rdrobust` (8) sit near the bottom of the frame in
  absolute terms, but they are 2021 and 2014 methods appearing in a corpus whose
  mass is older work. Their presence at all is the signal.
- **Methods absent from the frame are not thereby disqualified**, but their usage
  must be attested by a stated secondary source rather than assumed. Those are
  marked **Tier B** below and carry an explicit `usage_evidence` field in their
  pre-registration. A Tier B target with no attested usage does not get probed.

Recording the tier keeps the reader able to tell which targets the rule selected
and which we argued in.

## Tier A — usage measured directly in the frame

| # | target | rank | scripts | calls | method year | guarantee under test |
|---|---|---|---|---|---|---|
| 1 | `rdrobust::rdrobust` | 660 | 8 | 51 | 2014 / v4.0 2023 | robust bias-corrected CI covers **at the MSE-optimal bandwidth it selects itself** |
| 2 | `did::att_gt` | 572 | 9 | 20 | 2021 | **simultaneous** confidence bands via multiplier bootstrap |
| 3 | `estimatr::lm_robust` | 155 | 55 | 471 | 2018 | CR2 + Satterthwaite cluster CI coverage at few clusters |
| 4 | `estimatr::iv_robust` | 517 | 11 | 77 | 2018 | robust IV CI coverage |
| 5 | `MatchIt::matchit` | 202 | 37 | 94 | ongoing | inference after matching — Abadie-Imbens (2008) proved the bootstrap **invalid** for NN matching, and `matchit` + `boot` is a standard pairing |

Not queued, with reasons: `felm` (41), `feols` (79), `coeftest` (76), `vcovHC`
(111), `vcovCL` (203), `lmer` (207) — all heavily used and all failing criterion
3. These are settled estimators whose behaviour is textbook. `feols` and `vcovHC`
did produce default-class results this session; those are logged in
`../FINDINGS.md` and are deliberately not part of this corpus.

## Tier B — too recent for the frame; usage attested separately

| # | target | method year | guarantee under test | why argued in |
|---|---|---|---|---|
| 6 | `fixest::sunab` | 2021 | Sun-Abraham interaction-weighted estimator and its SE | it is *the fix* for the TWFE staggered-adoption bias measured in `../FINDINGS.md`. Whether the fix's inference works is the question that finding raises and nobody has answered publicly |
| 7 | `grf` causal forest | 2019 | asymptotic normality of the CI under honest splitting | the normality result needs subsampling-rate conditions applied users never check; coverage at realistic `n` and dimension is folklore |
| 8 | `clubSandwich` CR2 | 2018 | small-sample-corrected cluster CI coverage | **the positive control** |
| 9 | `DoubleML` | 2018 | normality of the cross-fitted estimator after ML nuisance estimation | the rate conditions are asymptotic and the method is sold for exactly the settings where they bind |

Each Tier B pre-registration must fill `usage_evidence` before it runs.

## The pilot

Targets **1, 6, 7, 8** — `rdrobust`, `sunab`, `grf`, `clubSandwich`. Chosen
because all four are installed and runnable today (`rdrobust` 4.0.0, `fixest`
0.14.2, `grf` 2.6.1, `clubSandwich` 0.7.0), and because they span the taxonomy:
one delicate claim, one untested fix, one folklore claim, and one expected pass.

**`clubSandwich` is not filler.** If every target in a corpus fails, the corpus
is indistinguishable from a broken instrument. It runs in the pilot for the same
reason a positive control runs in an assay, and if it does not return `HOLDS`
the other three verdicts are void until the harness is fixed.

Phase 2 installs `did`, `didimputation`, `HonestDiD`, `synthdid`, `lmerTest`, and
the Python side — `doubleml`, `econml`, and the conformal libraries `mapie` and
`crepes`, whose finite-sample coverage promise is unusually crisp and therefore
unusually falsifiable.

## Log

| date | change | reason |
|---|---|---|
| 2026-08-08 | queue created | initial application of the selection rule |
