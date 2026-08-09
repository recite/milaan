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
PLAN <- list(list(n = 500, reps = 1000),
             list(n = 2000, reps = 600),
             list(n = 8000, reps = 300))

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

set.seed(SEED)
rows <- list()
for (cellspec in PLAN) {
  n <- cellspec$n
  for (r in seq_len(cellspec$reps)) {
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
}

out <- list(
  probe = "grf/causal_forest_cate_ci",
  level = 0.95,
  seed = SEED,
  dimension = DIM,
  num_trees = NUM_TREES,
  x1_test = X1_TEST,
  truth = truth,
  ## The ATE estimand: the average of tau over the covariate distribution,
  ## which for x1 ~ Uniform(0,1) is 1 + 2*E[x1] = 2 exactly.
  ate_truth = 2.0,
  plan = lapply(PLAN, function(p) list(n = p$n, reps = p$reps)),
  env = list(r = R.version.string, grf = as.character(packageVersion("grf"))),
  replicates = rows
)

args <- commandArgs(trailingOnly = TRUE)
path <- if (length(args)) args[1] else "results.json.gz"
con <- gzfile(path, "w")
writeLines(toJSON(out, auto_unbox = TRUE, digits = 12), con)
close(con)
