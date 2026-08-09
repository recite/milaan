## rdrobust: does the robust bias-corrected CI cover at the bandwidth rdrobust
## itself selects?
##
## Runs the design registered in preregistration.yaml and writes one row per
## replicate. It renders no verdict -- gate.py does, so the tolerance comes from
## simcheck and the replicate count.
##
## All three arms rdrobust reports are recorded from the same call. The
## Conventional arm is not a rival under test: it is the instrument-sensitivity
## check of PROTOCOL.md 3a. If it covers acceptably, this DGP never generated
## the bias the Robust interval exists to survive.

suppressMessages({
  library(rdrobust)
  library(jsonlite)
})

TAU <- 0.5
REPS <- 2000
SEED <- 20260808
GRID <- c(500, 1000, 2000, 5000)
NOISE_SD <- 0.3

## Cubic on each side, different slope and curvature across the cutoff. The jump
## at zero is above(0) - below(0) = TAU by construction.
below <- function(x) 0.4 * x + 0.8 * x^2 - 0.6 * x^3
above <- function(x) TAU + 0.9 * x - 1.2 * x^2 + 0.4 * x^3

draw <- function(n) {
  x <- pmin(pmax(rnorm(n, 0, 0.5), -1), 1)
  mu <- ifelse(x < 0, below(x), above(x))
  list(x = x, y = mu + rnorm(n, 0, NOISE_SD))
}

set.seed(SEED)
rows <- list()
for (n in GRID) {
  for (r in seq_len(REPS)) {
    d <- draw(n)
    fit <- try(rdrobust(d$y, d$x), silent = TRUE)
    if (inherits(fit, "try-error")) {
      rows[[length(rows) + 1]] <- list(n = n, failed = TRUE)
      next
    }
    rows[[length(rows) + 1]] <- list(
      n = n, failed = FALSE,
      h = fit$bws[1, 1], b = fit$bws[2, 1],
      conv_est = fit$coef[1, 1],
      conv_lo = fit$ci[1, 1], conv_hi = fit$ci[1, 2],
      conv_se = fit$se[1, 1],
      robust_est = fit$coef[3, 1],
      robust_lo = fit$ci[3, 1], robust_hi = fit$ci[3, 2],
      robust_se = fit$se[3, 1]
    )
  }
}

out <- list(
  probe = "rdrobust/robust_ci_at_own_bandwidth",
  truth = TAU,
  level = 0.95,
  reps_per_cell = REPS,
  seed = SEED,
  grid = GRID,
  env = list(
    r = R.version.string,
    rdrobust = as.character(packageVersion("rdrobust"))
  ),
  replicates = rows
)

args <- commandArgs(trailingOnly = TRUE)
path <- if (length(args)) args[1] else "results.json.gz"
con <- gzfile(path, "w")
writeLines(toJSON(out, auto_unbox = TRUE, digits = 12), con)
close(con)
