# clubSandwich CR2 + Satterthwaite at few clusters

**Verdict: `HOLDS`, conservative at G=5.** The registered prediction was
falsified, in the informative direction.

## What was measured

Moulton design, balanced clusters of 30, truth β = 0.5, 2000 replicates per
cell, seed 20260808. clubSandwich 0.7.0, R 4.6.0.

simcheck's 3-sigma band at 2000 replicates: **[0.9354, 0.9646]**.

| G | CR2 + Satterthwaite | width | CR1 + z | width |
|---|---|---|---|---|
| 5 | **0.9765** | **3.714** | 0.7160 | 0.964 |
| 10 | 0.9605 | 1.340 | 0.8210 | 0.715 |
| 20 | 0.9595 | 0.698 | 0.8965 | 0.526 |
| 40 | 0.9530 | 0.437 | 0.9265 | 0.382 |

## The prediction was falsified, and the falsifier was too coarse

The registration predicted coverage inside the band at every G, and recorded the
falsifier as *"coverage outside the band at any G, with the OLS-unbiasedness
check still passing."* That is exactly what happened at G=5.

But the falsifier does not distinguish **direction**, and here direction is
everything. CR2 does not fail to cover — it covers 0.9765 against a nominal
0.95. It is conservative, not invalid. A control that misses on the conservative
side says something entirely different about the harness than one that misses on
the liberal side, and the registration should have said so.

**The harness is validated regardless, by the arm the probe was not testing.**
CR1 with a normal critical value shows the textbook under-coverage — 0.716 at
G=5 climbing to 0.927 at G=40 — which is only possible if the DGP has real
within-cluster correlation. The OLS-unbiasedness gate passes at every G, ruling
out the omitted-variable version of this design. The instrument discriminates,
so the other pilot verdicts stand.

This is written into `../../PROTOCOL.md` as a change to how controls are
registered: a control's falsifier must be **one-sided**, because a conservative
control still demonstrates a working harness while a liberal one does not.

## Reporting width is what makes this readable

CR2 buys its coverage at G=5 with an interval **3.9× wider than CR1's** —
3.714 against 0.964. Coverage alone would show 0.9765 and read as a comfortable
pass. With width alongside it, the honest description is that at five clusters
the method is doing something close to declining to answer, and is right to.

That gap closes fast: 1.9× at G=10, 1.33× at G=20, 1.14× at G=40.

This is the concrete argument for the protocol rule that coverage may not be
reported without width, and for the simcheck width gate that is still queued —
`monte_carlo` currently receives the interval endpoints and discards them, so
the width column above is computed in `gate.py` by hand.

## What this is and is not

Pustejovsky and Tipton (2018) claim Type I error "close to nominal ... even when
the number of clusters is small". At G=5 the realised size is 0.024 against a
nominal 0.05 — a factor of two conservative. That is a deviation from the claim
as quoted, in the safe direction, and it costs power rather than validity. It is
also **not news**: the paper's own simulations show the correction erring
conservative at very small G.

The purpose here was never to find something. It was to establish that a method
whose guarantee is expected to hold does hold under this harness, so that a
`FAILS` elsewhere in the corpus means something. It does, with the refinement
above.

## Reproducing

```bash
Rscript --vanilla probe.R results.json
uv run python probes/clubSandwich/cr2_few_clusters/gate.py   # the table
uv run pytest probes/clubSandwich/cr2_few_clusters/gate.py   # the gates
```

The unbiasedness gate passes. The coverage gate fails at G=5 only, and the
message carries the rate:

```
AssertionError: CR2+Satterthwaite, G=5 coverage: observed rate 0.9765
outside the 3-sigma band [0.9354, 0.9646] for a nominal 0.9500 over 2000 replicates
```
