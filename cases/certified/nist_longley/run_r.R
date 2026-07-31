source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "..", "src", "milaan", "lib")), "milaan.R"))

body <- function(data_path) {
  d <- read.csv(data_path)
  m <- lm(y ~ x1 + x2 + x3 + x4 + x5 + x6, data = d)
  b <- coef(m)

  list(
    quantities = list(
      "coef.b0" = b[["(Intercept)"]],
      "coef.b1" = b[["x1"]],
      "coef.b2" = b[["x2"]],
      "coef.b3" = b[["x3"]],
      "coef.b4" = b[["x4"]],
      "coef.b5" = b[["x5"]],
      "coef.b6" = b[["x6"]],
      "residual.sd" = summary(m)$sigma,
      "r.squared" = summary(m)$r.squared
    ),
    diagnostics = list(
      method = "QR with pivoting (R's lm)",
      rank = m$rank,
      # Condition number of the design matrix, the reason this dataset exists.
      condition_number = kappa(model.matrix(m), exact = TRUE)
    )
  )
}

cc_main("nist_longley", "r_lm", body, packages = c("stats"))
