## Companion to coverage_py.py: what R's two standard entry points give.
##
## Neither R default is the Wald interval. prop.test() is Wilson with a
## continuity correction; binom.test() is Clopper-Pearson. Coverage is computed
## by enumeration here too -- there are only n + 1 outcomes, so simulation would
## add noise to a quantity available exactly.

nominal <- 0.95

## Coverage of an interval function, summed over every possible outcome.
exact_coverage <- function(n, p, ci) {
  total <- 0
  for (x in 0:n) {
    bounds <- ci(x, n)
    if (bounds[1] <= p && p <= bounds[2]) {
      total <- total + dbinom(x, n, p)
    }
  }
  total
}

wilson_cc <- function(x, n) as.numeric(prop.test(x, n, conf.level = nominal)$conf.int)
clopper_pearson <- function(x, n) as.numeric(binom.test(x, n, conf.level = nominal)$conf.int)

## The Wald interval R does not offer as a default, written out so the tables in
## both languages hold the same three columns.
wald <- function(x, n) {
  phat <- x / n
  half <- qnorm(1 - (1 - nominal) / 2) * sqrt(phat * (1 - phat) / n)
  c(max(0, phat - half), min(1, phat + half))
}

grid_n <- c(20, 50, 100, 200, 500, 1000)
grid_p <- c(0.5, 0.2, 0.05, 0.01)

for (p in grid_p) {
  cat(sprintf("\n=== true p = %g ===  exact coverage, nominal %.2f\n", p, nominal))
  cat(sprintf("%6s%18s%18s%18s\n", "n", "prop.test", "binom.test", "Wald"))
  for (n in grid_n) {
    cat(sprintf(
      "%6d%18.3f%18.3f%18.3f\n", n,
      exact_coverage(n, p, wilson_cc),
      exact_coverage(n, p, clopper_pearson),
      exact_coverage(n, p, wald)
    ))
  }
}

## The single call that motivates the case: no successes in twenty trials.
cat("\n=== zero successes in twenty trials ===\n")
cat(sprintf("prop.test(0, 20)  [%.4f, %.4f]\n", prop.test(0, 20)$conf.int[1], prop.test(0, 20)$conf.int[2]))
cat(sprintf("binom.test(0, 20) [%.4f, %.4f]\n", binom.test(0, 20)$conf.int[1], binom.test(0, 20)$conf.int[2]))
cat(sprintf("Wald(0, 20)       [%.4f, %.4f]  <- zero width\n", wald(0, 20)[1], wald(0, 20)[2]))
