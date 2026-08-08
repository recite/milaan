suppressMessages({library(estimatr); library(sandwich); library(lmtest); library(multiwayvcov); library(clubSandwich)})
TRUTH <- 0.5; REPS <- 600; TAU <- 0.6; PER <- 30

# Moulton setup: a cluster-level regressor and a cluster-level error component,
# INDEPENDENT of each other. OLS is unbiased for TRUTH; what fails is the naive
# standard error. Putting the cluster effect into both x and y instead makes it
# an omitted variable, so OLS is biased and coverage falls to zero as G grows --
# which is a broken simulation, not a broken package.
draw <- function(G) {
  cl <- rep(seq_len(G), each = PER)
  xg <- rnorm(G)                      # regressor varies at the cluster level
  ag <- rnorm(G, sd = TAU)            # cluster error, independent of xg
  x  <- rep(xg, each = PER)
  y  <- TRUTH * x + rep(ag, each = PER) + rnorm(G * PER)
  data.frame(y = y, x = x, cl = factor(cl))
}
cover <- function(est, se, df) {
  cv <- if (is.na(df)) 1.959964 else qt(0.975, df)
  abs(est - TRUTH) <= cv * se
}
set.seed(11)
Gs <- c(5, 10, 20, 40)
res <- list()
for (G in Gs) {
  hits <- c(naive_z = 0, CR0_z = 0, CR1_t = 0, CR2_Satt = 0, mwv_t = 0)
  for (r in seq_len(REPS)) {
    d <- draw(G); m <- lm(y ~ x, data = d); b <- coef(m)["x"]
    hits["naive_z"] <- hits["naive_z"] + cover(b, summary(m)$coefficients["x","Std. Error"], NA)
    V0 <- vcovCL(m, cluster = d$cl, type = "HC0", cadjust = FALSE)
    hits["CR0_z"] <- hits["CR0_z"] + cover(b, sqrt(V0["x","x"]), NA)
    V1 <- vcovCL(m, cluster = d$cl, type = "HC1")
    hits["CR1_t"] <- hits["CR1_t"] + cover(b, sqrt(V1["x","x"]), G - 1)
    lr <- lm_robust(y ~ x, data = d, clusters = cl, se_type = "CR2")
    hits["CR2_Satt"] <- hits["CR2_Satt"] + cover(lr$coefficients["x"], lr$std.error["x"], lr$df["x"])
    Vm <- cluster.vcov(m, d$cl)
    hits["mwv_t"] <- hits["mwv_t"] + cover(b, sqrt(Vm["x","x"]), G - 1)
  }
  res[[as.character(G)]] <- hits / REPS
}
cat(sprintf("%-10s%s\n", "method", paste(sprintf("%8s", paste0("G=", Gs)), collapse="")))
for (nm in names(res[[1]])) cat(sprintf("%-10s%s\n", nm, paste(sprintf("%8.3f", sapply(res, function(v) v[[nm]])), collapse="")))
cat(sprintf("\nREPS=%d, nominal 0.95, 3-sigma band +/- %.3f\n", REPS, 3*sqrt(.95*.05/REPS)))
