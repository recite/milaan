source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "..", "lib")), "milaan.R"))

body <- function(data_path) {
  d <- read.csv(data_path)
  e <- read.csv(file.path(dirname(data_path), "expanded.csv"))

  # Same model, two encodings of the same data. R's glm documents `weights` for
  # a binomial family as the number of trials, which is a frequency reading, so
  # these should agree throughout.
  weighted <- glm(y ~ x1 + x2, family = binomial, data = d, weights = w)
  expanded <- glm(y ~ x1 + x2, family = binomial, data = e)

  sw <- summary(weighted)$coefficients
  se <- summary(expanded)$coefficients

  list(
    quantities = list(
      "coef.x1@weighted" = sw["x1", 1],
      "coef.x1@expanded" = se["x1", 1],
      "coef.x2@weighted" = sw["x2", 1],
      "coef.x2@expanded" = se["x2", 1],
      "se.x1@weighted" = sw["x1", 2],
      "se.x1@expanded" = se["x1", 2],
      "se.x2@weighted" = sw["x2", 2],
      "se.x2@expanded" = se["x2", 2],
      # Residual degrees of freedom is the cleanest tell: it is n - k under a
      # frequency reading and (rows) - k otherwise, with no floating point in
      # the way.
      "df.residual@weighted" = weighted$df.residual,
      "df.residual@expanded" = expanded$df.residual
    ),
    diagnostics = list(
      rows_weighted = nrow(d),
      rows_expanded = nrow(e),
      total_weight = sum(d$w)
    )
  )
}

cc_main("glm_weights_semantics", "r_glm", body, packages = c("stats"))
