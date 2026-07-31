source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "..", "lib")), "milaan.R"))
suppressPackageStartupMessages(library(sandwich))

body <- function(data_path) {
  d <- read.csv(data_path)
  m <- lm(y ~ x, data = d)

  q <- list(
    "coef.intercept" = coef(m)[["(Intercept)"]],
    "coef.x" = coef(m)[["x"]],
    "se.x@ols" = sqrt(vcov(m)[2, 2]),
    "se.intercept@ols" = sqrt(vcov(m)[1, 1])
  )
  for (type in c("HC0", "HC1", "HC2", "HC3")) {
    v <- sandwich::vcovHC(m, type = type)
    q[[paste0("se.x@", type)]] <- sqrt(v[2, 2])
    q[[paste0("se.intercept@", type)]] <- sqrt(v[1, 1])
  }

  list(quantities = q, diagnostics = list(n = nrow(d), df_residual = m$df.residual))
}

cc_main("hc_variants", "r", body, packages = c("sandwich"))
