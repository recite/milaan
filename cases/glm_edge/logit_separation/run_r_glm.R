source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "..", "src", "milaan", "lib")), "milaan.R"))

body <- function(data_path) {
  d <- read.csv(data_path)
  caught <- cc_capture(glm(y ~ x, family = binomial, data = d))
  m <- caught$value
  s <- summary(m)$coefficients

  list(
    quantities = list(
      "coef.intercept" = s[1, 1],
      "coef.x" = s[2, 1],
      "se.x" = s[2, 2],
      "pvalue.x" = s[2, 4]
    ),
    diagnostics = list(
      converged = m$converged,
      iterations = m$iter,
      deviance = m$deviance,
      # The tell that the estimate has run away: fitted probabilities pinned to
      # the boundary. R reports converged = TRUE regardless.
      max_fitted = max(fitted(m)),
      min_fitted = min(fitted(m)),
      warnings = caught$warnings
    )
  )
}

cc_main("logit_separation", "r_glm", body, packages = c("stats"))
