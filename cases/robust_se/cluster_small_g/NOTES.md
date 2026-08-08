# Cluster-robust standard errors when there are few clusters

## What happens

Clustering is the most common correction in the corpus: `sandwich` appears in 421
replication scripts, `multiwayvcov` in 142, `estimatr` in 180. All of them
implement a cluster-robust variance, and the arithmetic agrees. What differs is
the small-sample correction, and with few clusters that is the whole ballgame.

A Moulton design — a cluster-level regressor and a cluster-level error, mutually
independent, so OLS is unbiased and only the standard error is at stake.
Thirty observations per cluster, cluster error sd 0.6, 600 replicates, nominal
95%. The 3-sigma band is [0.923, 0.977].

| | G=5 | G=10 | G=20 | G=40 |
|---|---|---|---|---|
| naive OLS | 0.465 | 0.455 | 0.498 | 0.468 |
| `sandwich::vcovCL` CR0, z | 0.678 | 0.813 | 0.882 | 0.932 |
| `sandwich::vcovCL` CR1, t(G-1) | 0.825 | 0.887 | 0.902 | 0.948 |
| `multiwayvcov::cluster.vcov`, t(G-1) | 0.825 | 0.887 | 0.902 | 0.948 |
| **`estimatr::lm_robust` CR2, Satterthwaite** | **0.963** | **0.972** | **0.958** | **0.977** |
| `statsmodels` `cov_type="cluster"`, z | 0.730 | 0.797 | 0.908 | 0.923 |
| `statsmodels` `cov_type="cluster"`, t(G-1) by hand | 0.868 | 0.855 | 0.930 | 0.933 |

## What it means

**CR2 with Satterthwaite degrees of freedom is the only thing here that works at
five clusters.** `estimatr` and `clubSandwich` agree to the digit — they share the
implementation — and both sit inside the band at every cluster count tested. The
small-sample literature's recommendation survives measurement, which is a result
worth recording as much as a failure would be.

**The common default is not that.** CR1 with `t(G-1)` — what you get from
`vcovCL` at its defaults, and what `multiwayvcov::cluster.vcov` produces — covers
0.825 at five clusters and is still short of nominal at twenty. It reaches the
band only at forty. Between them `sandwich` and `multiwayvcov` account for 563
scripts in the corpus.

**statsmodels has no CR2 at all.** `cov_type="cluster"` implements CR1-style
scaling and reports normal-based intervals: 0.730 at five clusters, against
`estimatr`'s 0.963. Applying `t(G-1)` by hand recovers some of it and not enough
— 0.868 — because the correction that matters at small G is to the *variance*
estimator, not only to the critical value. A Python user with five clusters has
no route to a correctly-sized interval inside statsmodels.

This is the porting consequence, and it is the reverse of the direction people
usually worry about: the R ecosystem has the better small-sample tool, and the
translation loses it silently. Nothing warns, and the number stays plausible.

## The mistake this case nearly shipped with

The first version of this DGP gave the cluster effect to both `x` and `y`.
Coverage then *fell* as clusters were added — 0.413, 0.202, 0.022, 0.000 — which
is impossible for a consistent estimator and was the tell. With the cluster
effect in both, it is an omitted variable: OLS is biased for the target, the
standard error shrinks with G, and the interval walks away from the truth.
Recorded because it is the easy mistake in this design, and because a result that
looked like a devastating indictment of every package was a bug in the harness.

## Reproducing

    Rscript --vanilla coverage_r.R
    python3 coverage_py.py

Every number above is what they print.
