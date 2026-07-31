source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "..", "lib")), "milaan.R"))
suppressPackageStartupMessages(library(logistf))

# Firth's penalized likelihood is the principled answer to separation: the Jeffreys
# prior penalty guarantees finite estimates and removes the first-order bias. It is
# included here as the reference point the other four backends should be read
# against, not as another contender.
body <- function(data_path) {
  d <- read.csv(data_path)
  caught <- cc_capture(logistf(y ~ x, data = d))
  m <- caught$value

  list(
    quantities = list(
      "coef.intercept" = m$coefficients[[1]],
      "coef.x" = m$coefficients[[2]],
      "se.x" = sqrt(diag(vcov(m)))[[2]],
      "pvalue.x" = m$prob[[2]]
    ),
    diagnostics = list(
      method = "Firth penalized likelihood",
      iterations = m$iter[[1]],
      warnings = caught$warnings
    )
  )
}

cc_main("logit_separation", "r_firth", body, packages = c("logistf"))
