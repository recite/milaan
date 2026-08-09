## grf causal forest: do the pointwise CATE confidence intervals cover?
##
## Runs the design registered in preregistration.yaml. Renders no verdict --
## gate.py does.
##
## Coverage is recorded separately at each fixed test point. Within one
## replicate the predictions at different x are dependent, so pooling them would
## understate the variance of the coverage estimate; across replicates at a
## FIXED point they are independent, which is what simcheck's band assumes.
##
## The ATE arm is an internal control rather than a rival: it is the
## well-behaved doubly-robust quantity, so if it failed too, suspicion belongs
## on the harness before the method.

suppressMessages({
  library(grf)
  library(jsonlite)
})

SEED <- 20260808
DIM <- 10
NOISE_SD <- 0.5
NUM_TREES <- 2000
X1_TEST <- c(0.1, 0.3, 0.5, 0.7, 0.9)

## Unequal on purpose: a forest costs ~1.1s at n=1500, so equal replication
## would spend the whole budget on the largest cell. simcheck derives its band
## from the replicate count, so the largest cell is simply judged with a wider
## band -- which the gate prints rather than hides.
## See the sweep_amendment block in preregistration.yaml: the original
## n=8000 cell measured at 33 minutes per forest, so 165 hours.
PLAN <- list(list(n = 500, reps = 800),
             list(n = 2000, reps = 400),
             list(n = 4000, reps = 120))

tau_fn <- function(x1) 1 + 2 * x1

draw <- function(n) {
  X <- matrix(runif(n * DIM), n, DIM)
  W <- rbinom(n, 1, 0.5)
  Y <- 2 * X[, 2] + (W - 0.5) * tau_fn(X[, 1]) + rnorm(n, 0, NOISE_SD)
  list(X = X, Y = Y, W = W)
}

## Test points: x1 varies, every other coordinate held at 0.5.
X_test <- matrix(0.5, length(X1_TEST), DIM)
X_test[, 1] <- X1_TEST
truth <- tau_fn(X1_TEST)

## Registered sensitivity condition: the effect must actually vary across the
## test points, or the pointwise claim collapses into the ATE claim.
stopifnot(diff(range(truth)) > 1.0)

args <- commandArgs(trailingOnly = TRUE)
path <- if (length(args)) args[1] else "results.json.gz"

## Written after every cell, and progress printed every 25 replicates.
##
## The first version of this probe wrote only at the very end. It ran for five
## hours and twelve minutes, produced nothing, and gave no way to tell slow from
## hung -- which is exactly the shape of failure this repository documents in
## other people's code. Partial output is not a nicety here: it is what makes
## the difference observable.
flush_out <- function(rows) {
  ns <- vapply(rows, function(x) as.numeric(x$n), 0)
  done <- vapply(PLAN, function(p) sum(ns == p$n) >= p$reps, TRUE)
  out <- list(
    probe = "grf/causal_forest_cate_ci", level = 0.95, seed = SEED,
    dimension = DIM, num_trees = NUM_TREES, x1_test = X1_TEST, truth = truth,
    ate_truth = 2.0, complete = all(done),
    cells_done = vapply(PLAN, `[[`, 0, "n")[done],
    plan = lapply(PLAN, function(p) list(n = p$n, reps = p$reps)),
    env = list(r = R.version.string, grf = as.character(packageVersion("grf"))),
    replicates = rows
  )
  con <- gzfile(path, "w")
  writeLines(jsonlite::toJSON(out, auto_unbox = TRUE, digits = 12), con)
  close(con)
}

## Resume at REPLICATE granularity, not cell granularity.
##
## Per-cell resume was still too coarse: this probe has now been killed four
## times, always mid-cell, so every attempt discarded that cell and restarted
## it. Progress never accumulated.
##
## Resuming inside a cell is only sound if a replicate does not depend on the
## draws before it, so each one seeds itself from (SEED, n, r) and nothing
## else. That is simcheck's own rule for its runner, and the reason is the same:
## replicate r is then reproducible on its own, and an interrupted run rejoins
## exactly where it stopped rather than approximately.
rows <- list()
done_counts <- list()
if (file.exists(path)) {
  prev <- jsonlite::fromJSON(path, simplifyVector = FALSE)
  if (!is.null(prev$replicates) && length(prev$replicates)) {
    rows <- prev$replicates
    ns <- vapply(rows, function(x) as.numeric(x$n), 0)
    for (nn in unique(ns)) done_counts[[as.character(nn)]] <- sum(ns == nn)
    cat(sprintf("resuming: %d replicates on disk (%s)\n", length(rows),
                paste(sprintf("n=%s:%d", names(done_counts),
                              unlist(done_counts)), collapse = ", ")))
  }
}

for (cellspec in PLAN) {
  n <- cellspec$n
  already <- done_counts[[as.character(n)]]
  already <- if (is.null(already)) 0 else already
  if (already >= cellspec$reps) {
    cat(sprintf("skipping n=%d, %d/%d already done\n", n, already, cellspec$reps))
    next
  }
  t_cell <- Sys.time()
  for (r in seq(already + 1, cellspec$reps)) {
    ## Replicate r is a function of (SEED, n, r) alone.
    set.seed(SEED + 7919L * as.integer(log2(n) * 100) + r)
    ## Flushed on the same cadence as the progress line, not only per cell. The
    ## previous version flushed per cell and was killed inside the first one,
    ## losing everything -- coarse checkpointing is the same defect as none.
    if (r %% 25 == 0) {
      flush_out(rows)
      cat(sprintf("n=%d  %d/%d  %.1f min elapsed in cell\n", n, r, cellspec$reps,
                  as.numeric(Sys.time() - t_cell, units = "mins")))
      flush.console()
    }
    d <- draw(n)
    cf <- try(causal_forest(d$X, d$Y, d$W, W.hat = 0.5, num.trees = NUM_TREES),
              silent = TRUE)
    if (inherits(cf, "try-error")) {
      rows[[length(rows) + 1]] <- list(n = n, failed = TRUE)
      next
    }
    p <- predict(cf, X_test, estimate.variance = TRUE)
    ate <- average_treatment_effect(cf)
    rows[[length(rows) + 1]] <- list(
      n = n, failed = FALSE,
      est = as.numeric(p$predictions),
      se = as.numeric(sqrt(p$variance.estimates)),
      ate_est = as.numeric(ate["estimate"]),
      ate_se = as.numeric(ate["std.err"])
    )
  }
  ## The ATE estimand is 1 + 2*E[x1] = 2 exactly for x1 ~ Uniform(0,1); it is
  ## stamped into the output by flush_out.
  flush_out(rows)
  cat(sprintf("cell n=%d done in %.1f min; %d replicates written\n",
              n, as.numeric(Sys.time() - t_cell, units = "mins"), length(rows)))
  flush.console()
}
