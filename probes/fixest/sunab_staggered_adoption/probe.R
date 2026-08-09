## Sun & Abraham via fixest::sunab: is the corrected estimator unbiased, and
## does its interval cover?
##
## Runs the design registered in preregistration.yaml. Renders no verdict --
## gate.py does, so the tolerance comes from simcheck and the replicate count.
##
## Three arms from each replicate:
##   sunab, default SE      -- what a user gets by typing the recommended fix
##   sunab, cluster by unit -- what the method's own theory assumes
##   TWFE                   -- NOT a rival. It is the instrument-sensitivity
##                             check of PROTOCOL.md 3a: the bias sunab exists to
##                             remove must be present in this data.

suppressMessages({
  library(fixest)
  library(jsonlite)
})

REPS <- 1000
SEED <- 20260808
GRID <- c(40, 80, 200)
TT <- 12
COHORTS <- c(4, 7, 10, 10000)  # 10000 = never treated
GROWTH <- 1.0
NOISE_SD <- 0.5

## Staggered adoption, effects growing with time since adoption, every true
## effect strictly positive. Untreated potential outcomes are unit FE + period
## FE + noise, with no cohort-specific trend, so parallel trends holds.
draw <- function(n_units) {
  unit <- rep(seq_len(n_units), each = TT)
  period <- rep(seq_len(TT), times = n_units)
  adopt <- rep(COHORTS[(seq_len(n_units) - 1) %% length(COHORTS) + 1], each = TT)
  rel <- period - adopt
  tau <- ifelse(rel >= 0, GROWTH * (rel + 1), 0)
  y <- rnorm(n_units)[unit] + rnorm(TT)[period] + tau +
    rnorm(n_units * TT, 0, NOISE_SD)
  ## Numeric, not logical: fixest rejects a logical produced by I() inside a
  ## formula ("The current SEXP type is not supported by the RealMat class").
  data.frame(y, unit, period, cohort = ifelse(adopt > TT, 10000, adopt), rel, tau,
             treated = as.numeric(rel >= 0))
}

set.seed(SEED)
rows <- list()
for (n_units in GRID) {
  for (r in seq_len(REPS)) {
    d <- draw(n_units)
    treated <- d[d$rel >= 0 & d$cohort < 10000, ]
    truth <- mean(treated$tau)

    ## The arms fail independently. An earlier version discarded the whole
    ## replicate when either did, so one broken sensitivity fit destroyed 3000
    ## perfectly good sunab measurements. Only the claim under test can void a
    ## replicate.
    m <- try(feols(y ~ sunab(cohort, period) | unit + period, data = d, notes = FALSE),
             silent = TRUE)
    if (inherits(m, "try-error")) {
      rows[[length(rows) + 1]] <- list(n_units = n_units, failed = TRUE)
      next
    }
    tw <- try(feols(y ~ treated | unit + period, data = d, notes = FALSE),
              silent = TRUE)

    ## The estimand check registered as estimand_hazard: sunab's agg="att"
    ## averages over the relative periods it estimates. If that set does not
    ## cover every treated relative period present in the data, the truth above
    ## is the wrong target and the comparison would measure an estimand
    ## mismatch rather than bias.
    est_e <- as.integer(sub("period::", "",
                            grep("^period::", names(coef(m)), value = TRUE)))
    covers_all <- all(sort(unique(treated$rel)) %in% est_e[est_e >= 0])

    a_def <- summary(m, agg = "att")$coeftable
    a_cl <- summary(m, agg = "att", cluster = ~unit)$coeftable

    rows[[length(rows) + 1]] <- list(
      n_units = n_units, failed = FALSE, truth = truth,
      estimand_ok = covers_all,
      est = a_def[1, 1],
      se_default = a_def[1, 2],
      se_cluster = a_cl[1, 2],
      twfe = if (inherits(tw, "try-error")) NA_real_ else tw$coeftable[1, 1]
    )
  }
}

out <- list(
  probe = "fixest/sunab_staggered_adoption",
  level = 0.95,
  reps_per_cell = REPS,
  seed = SEED,
  grid = GRID,
  periods = TT,
  cohorts = COHORTS,
  env = list(r = R.version.string, fixest = as.character(packageVersion("fixest"))),
  replicates = rows
)

args <- commandArgs(trailingOnly = TRUE)
path <- if (length(args)) args[1] else "results.json.gz"
con <- gzfile(path, "w")
writeLines(toJSON(out, auto_unbox = TRUE, digits = 12), con)
close(con)
