# Longley: how many digits each solver keeps

The third oracle, and the only one that can say who is *right*.

Cross-implementation agreement cannot: two packages sharing a formula agree and
you learn nothing. A metamorphic invariant cannot either: it shows an answer is
self-consistent, not that it is the true one. A certified value can. NIST
publishes the Longley coefficients to fifteen digits, so each backend is scored
against truth independently.

## Correct digits, worst coefficient

| backend | method | worst coefficient |
|---|---|---|
| R `lm` | QR with column pivoting | **13.0** |
| `statsmodels` OLS | pseudo-inverse | 10.8 |
| `numpy.linalg.lstsq` | SVD | 10.8 |
| **normal equations** | `(X'X)⁻¹X'y` | **7.1** |

Every backend agrees to at least seven digits, so a cross-implementation
comparison at any sane tolerance would call this case unanimous and move on.
Against the certified answer the spread is six digits.

## Why the normal equations lose

Measured on this design:

- **cond(X) = 4.86 × 10⁹**
- **cond(X'X) = 2.37 × 10¹⁹**

Forming `X'X` squares the condition number. Double precision carries about
sixteen significant digits, so a condition number of 10¹⁹ means the matrix being
inverted is, numerically, singular — there is no accuracy left to lose. That the
normal-equations backend still returns seven correct digits is luck, not
robustness.

This is the point Longley made in 1967, when the least-squares programs of the
day returned answers with no correct digits at all. The dataset survives as the
standard test because the failure is invisible without a certified answer: the
wrong result looks entirely reasonable.

## R's `lm` is the most accurate here

R keeps 13 digits on its worst coefficient where both NumPy-based solvers keep
10.8 — R's QR with column pivoting handles this design better than the SVD and
pseudo-inverse routes. Worth stating plainly, since the R-versus-Python cases
elsewhere in this suite tend to find R and Python agreeing exactly or R being the
one with the surprising default.

Two-and-a-bit digits is not a practical difference for Longley-sized problems.
It is a real difference in the numerical quality of the underlying solve, and it
is only visible because there is a certified answer to measure against.

## What the case is for

None of the backends is wrong. The case exists to demonstrate that "the packages
agree" and "the packages are right" are different claims, and that only the
second is worth asserting. It also gives the certified-value path in `oracles.py`
something real to run against, the same way `glm_weights_semantics` does for the
metamorphic path.

## Reproducing

```bash
milaan run nist_longley
```

Certified values and data transcribed from
<https://www.itl.nist.gov/div898/strd/lls/data/LINKS/DATA/Longley.dat> and
embedded in `data.py`, so the case needs no network.
