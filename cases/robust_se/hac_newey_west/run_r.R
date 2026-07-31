source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "..", "src", "milaan", "lib")), "milaan.R"))
suppressPackageStartupMessages(library(sandwich))

body <- function(data_path) {
  d <- read.csv(data_path)
  m <- lm(y ~ x, data = d)

  se <- function(v) sqrt(v[2, 2])

  q <- list(
    # What a user gets by typing NeweyWest(m) and nothing else. prewhite = TRUE
    # and automatic bandwidth selection are both on.
    "se.x@default" = se(sandwich::NeweyWest(m)),

    # Same automatic bandwidth, prewhitening off. Isolates how much of the
    # default-vs-default gap is prewhitening alone.
    "se.x@auto_noprewhite" = se(sandwich::NeweyWest(m, prewhite = FALSE)),

    # Fully pinned: Bartlett kernel, three lags, no prewhitening, no
    # finite-sample adjustment. This is the configuration that should be
    # reproducible in any package that implements Newey-West at all.
    "se.x@lag3_noprewhite" = se(
      sandwich::NeweyWest(m, lag = 3, prewhite = FALSE, adjust = FALSE)
    ),
    "se.x@lag3_noprewhite_adjust" = se(
      sandwich::NeweyWest(m, lag = 3, prewhite = FALSE, adjust = TRUE)
    ),
    "se.x@ols" = se(vcov(m))
  )

  list(
    quantities = q,
    diagnostics = list(
      n = nrow(d),
      auto_bandwidth = as.numeric(sandwich::bwNeweyWest(m, prewhite = FALSE))
    )
  )
}

cc_main("hac_newey_west", "r", body, packages = c("sandwich"))
