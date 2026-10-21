# rdrobust: the robust CI at the bandwidth rdrobust chooses itself

**Verdict: `HOLDS`.** The registered prediction was confirmed, and the
sensitivity condition was met, so this is a real test rather than a vacuous one.

## What was measured

Sharp RD at zero. Cubic regression functions with different slope and curvature
on each side, running variable truncated normal, true jump 0.5, 2000 replicates
per cell, seed 20260808. rdrobust 4.0.0, R 4.6.0. Every call used package
defaults, so the bandwidth is the MSE-optimal one rdrobust selects itself.

simcheck's 3-sigma band at 2000 replicates: **[0.9354, 0.9646]**.

| n | mean h | Conventional | width | **Robust** | width |
|---|---|---|---|---|---|
| 500 | 0.2675 | 0.9265 | 0.3605 | **0.9410** | 0.4258 |
| 1000 | 0.2616 | 0.9350 | 0.2575 | **0.9485** | 0.3021 |
| 2000 | 0.2502 | 0.9310 | 0.1845 | **0.9440** | 0.2144 |
| 5000 | 0.2312 | 0.9200 | 0.1211 | **0.9530** | 0.1379 |

The Robust interval is inside the band at every sample size. 8000 calls, zero
failures.

## The probe could have failed, and that is what makes the pass mean something

Per `../../PROTOCOL.md` §3a, this claim is a conditional improvement: the robust
interval exists to stay valid at a bandwidth that invalidates the conventional
one. If the DGP had been smooth enough for the conventional interval to cover,
nothing would have been tested.

**The Conventional arm under-covers at every sample size** — 0.9265, 0.9350,
0.9310, 0.9200, all below the band's lower edge. The bias the robust interval
is built to survive was present throughout.

And it gets *worse* with n, not better: 0.9265 at n=500 down to 0.9200 at
n=5000, while its interval narrows from 0.361 to 0.121. That is the whole
argument of the source paper made visible — the MSE-optimal bandwidth trades
bias against variance, so as n grows the interval shrinks around a point that
stays off-centre, and the coverage shortfall does not wash out. An applied user
who assumes more data will rescue a conventional RD interval has it backwards.

## What the robust interval costs

Between 13% and 18% extra width — 0.4258 against 0.3605 at n=500, 0.1379
against 0.1211 at n=5000. That is a cheap price for the coverage it recovers,
and it is worth stating precisely because the previous probe in this corpus
found the opposite shape: clubSandwich's CR2 bought its coverage at five
clusters with an interval 3.9× wider. Both "hold", and they are not the same
kind of holding.

## What this is, and what it is not

This is a **`HOLDS` on a heavily-used method, from an independent DGP**. The
design is deliberately not the Lee-based one used in the source paper; the point
of an independent probe is an independent data generating process. Calonico,
Cattaneo and Titiunik's claim survives a design they did not choose.

It is not a general endorsement. The probe tested a sharp design with a
continuous running variable, plenty of mass at the cutoff, and smooth
polynomials on each side. The known hard cases are elsewhere — discrete running
variables (Kolesár & Rothe 2018), and designs where the smoothness the method
assumes is doubtful. Nothing here speaks to those.

A corpus of only failures would be indistinguishable from a broken instrument.
Results like this one are what make the failures in it credible, and they are a
public good on their own terms: nobody had checked.

## Reproducing

```bash
Rscript --vanilla probe.R results.json.gz          # ~25 min, 8000 calls
uv run python probes/rdrobust/robust_ci_at_own_bandwidth/gate.py   # the table
uv run pytest probes/rdrobust/robust_ci_at_own_bandwidth/gate.py   # the gates
```

Two gates, both passing. The first is the sensitivity check and has to be
believed before the second means anything:

```
test_the_probe_exercised_the_failure_mode_it_claims_to_test  PASSED
test_robust_bias_corrected_ci_covers_at_the_selected_bandwidth  PASSED
```

One process note worth recording: the gate was first run against a
`results.json.gz` the probe was still writing, and failed with a
`JSONDecodeError` rather than a wrong number. That is the right failure — a
truncated input should not be able to produce a plausible coverage rate.
