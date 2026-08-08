# Coverage of the Newey-West interval under a DGP whose truth we set.
#
# The comparison in this case establishes that R and statsmodels compute the same
# estimator and differ only in convention. It cannot say which convention to pick,
# because agreement is not correctness and neither side is a reference. This does:
# draw many samples from a process with a known coefficient, and count how often
# the nominal 95% interval contains it.
suppressMessages({library(sandwich); library(lmtest)})

TRUTH <- 0.5
T_OBS <- 100
REPS  <- 1000
RHO   <- 0.8

set.seed(1)
hits <- c(default = 0, no_prewhite = 0, lag3 = 0)
for (r in seq_len(REPS)) {
  x <- as.numeric(arima.sim(list(ar = RHO), T_OBS))
  e <- as.numeric(arima.sim(list(ar = RHO), T_OBS))
  m <- lm(TRUTH * x + e ~ x)
  b <- coef(m)["x"]
  for (nm in names(hits)) {
    V <- switch(nm,
      default     = NeweyWest(m),
      no_prewhite = NeweyWest(m, prewhite = FALSE),
      lag3        = NeweyWest(m, prewhite = FALSE, lag = 3))
    se <- sqrt(V["x", "x"])
    hits[nm] <- hits[nm] + (abs(b - TRUTH) <= 1.96 * se)
  }
}
for (nm in names(hits)) cat(sprintf("%-12s %.3f\n", nm, hits[nm] / REPS))
