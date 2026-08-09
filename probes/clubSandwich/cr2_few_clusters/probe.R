## clubSandwich CR2 + Satterthwaite: does the interval cover at few clusters?
##
## Runs the design registered in preregistration.yaml and writes one row per
## replicate to results.json. It renders no verdict -- gate.py does that, so
## that the tolerance comes from simcheck and the replicate count rather than
## from anything decided here.

suppressMessages({
  library(clubSandwich)
  library(sandwich)
  library(lmtest)
  library(jsonlite)
})

BETA <- 0.5
PER_CLUSTER <- 30
CLUSTER_SD <- 0.6
NOISE_SD <- 1.0
REPS <- 2000
SEED <- 20260808
GRID <- c(5, 10, 20, 40)
LEVEL <- 0.95

## Moulton design: the cluster effect enters y only. If it entered x as well it
## would be an omitted variable, and coverage would fall as clusters were added.
draw <- function(n_clusters) {
  x_cluster <- rnorm(n_clusters)
  err_cluster <- rnorm(n_clusters) * CLUSTER_SD
  cluster <- rep(seq_len(n_clusters), each = PER_CLUSTER)
  x <- x_cluster[cluster]
  y <- BETA * x + err_cluster[cluster] + rnorm(length(x), sd = NOISE_SD)
  list(df = data.frame(y = y, x = x), cluster = cluster)
}

set.seed(SEED)
rows <- list()
for (g in GRID) {
  for (r in seq_len(REPS)) {
    d <- draw(g)
    fit <- lm(y ~ x, data = d$df)

    ## CR2 with Satterthwaite degrees of freedom -- the claim under test.
    ct <- coef_test(fit, vcov = "CR2", cluster = d$cluster, test = "Satterthwaite")
    i <- which(rownames(ct) == "x")
    est <- ct$beta[i]
    se <- ct$SE[i]
    df <- ct$df_Satt[i]
    crit <- qt(0.5 + LEVEL / 2, df)

    ## CR1 with a normal critical value, for context. Not the claim under test;
    ## recorded so the comparison in NOTES.md comes from this same run.
    v1 <- vcovCR(fit, cluster = d$cluster, type = "CR1S")
    se1 <- sqrt(v1[2, 2])

    rows[[length(rows) + 1]] <- list(
      n_clusters = g, estimate = est, se = se, df = df,
      lower = est - crit * se, upper = est + crit * se,
      lower_cr1 = est - 1.959964 * se1, upper_cr1 = est + 1.959964 * se1
    )
  }
}

out <- list(
  probe = "clubSandwich/cr2_few_clusters",
  truth = BETA,
  level = LEVEL,
  reps_per_cell = REPS,
  seed = SEED,
  grid = GRID,
  env = list(
    r = R.version.string,
    clubSandwich = as.character(packageVersion("clubSandwich")),
    sandwich = as.character(packageVersion("sandwich"))
  ),
  replicates = rows
)
## Gzipped: per-replicate rows are what let the gate be re-run without R, but
## eight thousand of them is 1.4 MB uncompressed and the corpus has many probes.
## Compressed it is a tenth of that at full fidelity.
args <- commandArgs(trailingOnly = TRUE)
path <- if (length(args)) args[1] else "results.json.gz"
con <- gzfile(path, "w")
writeLines(toJSON(out, auto_unbox = TRUE, digits = 12), con)
close(con)
