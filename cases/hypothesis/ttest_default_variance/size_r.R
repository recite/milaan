## Companion to size_py.py: the same design, run through R's default.
##
## R's t.test defaults to var.equal = FALSE, so the call a user writes without
## thinking about it is Welch. scipy's ttest_ind defaults to equal_var = TRUE,
## so the call a user writes without thinking about it is the pooled test. This
## script runs both from R, which is what shows the estimator itself is not in
## dispute -- only which one you get for free.

alpha <- 0.05
reps <- 20000
set.seed(5)

## Rejection rate under a true null, for one design and one variance assumption.
size <- function(n1, n2, sd1, sd2, var_equal) {
  rejected <- 0L
  for (i in seq_len(reps)) {
    a <- rnorm(n1, 0, sd1)
    b <- rnorm(n2, 0, sd2)
    if (t.test(a, b, var.equal = var_equal)$p.value < alpha) {
      rejected <- rejected + 1L
    }
  }
  rejected / reps
}

designs <- list(
  c(10, 10, 1, 1), c(10, 10, 1, 4),
  c(10, 30, 1, 1), c(10, 30, 4, 1), c(10, 30, 1, 4),
  c(20, 60, 4, 1), c(5, 45, 4, 1), c(10, 100, 4, 1)
)

cat(sprintf("True null in every cell. Nominal alpha = %.2f, %d replicates.\n\n", alpha, reps))
cat(sprintf("%5s%6s%6s%6s%18s%16s\n", "n1", "n2", "sd1", "sd2", "R default (Welch)", "var.equal=TRUE"))
for (d in designs) {
  cat(sprintf(
    "%5d%6d%6g%6g%18.4f%16.4f\n", d[1], d[2], d[3], d[4],
    size(d[1], d[2], d[3], d[4], FALSE),
    size(d[1], d[2], d[3], d[4], TRUE)
  ))
}

cat("\nWhat each language hands you when you do not choose:\n")
a <- rnorm(10, 0, 4)
b <- rnorm(100, 0, 1)
cat(sprintf("  R    t.test(a, b)        -> %s\n", t.test(a, b)$method))
cat("  scipy ttest_ind(a, b)     -> pooled Student (equal_var=True)\n")
