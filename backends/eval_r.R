#!/usr/bin/env Rscript
#
# Generic R backend: evaluate an expression against a dataset and write the
# result schema. This is what lets a comparison be four lines of YAML instead of
# a hundred and fifty lines of script.
#
#   Rscript eval_r.R --expr "sd(x)" [--setup "..."] <data.csv> <out.json>
#
# The data frame's columns are bound as variables, so `sd(x)` means the column
# named x, and the whole frame is available as `d` for expressions that need it.
# An expression returning several values becomes several quantities, named by
# position or by the names the expression itself supplies.
#
# On eval(): the expressions come from spec files in this repository, which are
# reviewed like any other source. This is a test harness deliberately running the
# code it is given -- the same trust boundary as the hand-written backend scripts
# it replaces, which are simply executed. It must never be pointed at a spec from
# an untrusted source.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "lib")), "milaan.R"))

flag <- function(flags, name, default = "") {
  hit <- which(flags == name)
  if (!length(hit) || hit[[1]] >= length(flags)) default else flags[[hit[[1]] + 1]]
}

parsed <- cc_args()
expr_text <- flag(parsed$flags, "--expr")
setup_text <- flag(parsed$flags, "--setup")
if (!nzchar(expr_text)) stop("eval_r.R: --expr is required")

body <- function(data_path) {
  env <- new.env(parent = globalenv())

  # A dataset is optional: an expression about random number generation, or one
  # over literals, has no columns to bind.
  if (nzchar(data_path) && file.exists(data_path) && file.size(data_path) > 0) {
    d <- utils::read.csv(data_path)
    for (nm in names(d)) assign(nm, d[[nm]], envir = env)
    assign("d", d, envir = env)
  }

  # Setup runs first and shares the environment, so it can seed the RNG, coerce
  # a column to a factor, or fit a model the expression then extracts from.
  if (nzchar(setup_text)) {
    eval(parse(text = setup_text), envir = env)
  }

  # Evaluated exactly once. Evaluating a second time to recover the names would
  # redraw anything stochastic, so an RNG spec would report one sample and label
  # it from another.
  raw <- eval(parse(text = expr_text), envir = env)
  labels <- names(raw)
  value <- as.numeric(raw)

  # Naming: a scalar is `value`; a vector is `value.1`, `value.2`, ... unless the
  # expression produced names, which are used verbatim. Positional names keep two
  # implementations comparable even when one of them labels its output and the
  # other does not.
  q <- list()
  if (length(value) == 1L) {
    q[["value"]] <- value[[1]]
  } else {
    for (i in seq_along(value)) {
      key <- if (!is.null(labels) && nzchar(labels[[i]])) labels[[i]] else as.character(i)
      q[[paste0("value.", key)]] <- value[[i]]
    }
  }

  list(
    quantities = q,
    diagnostics = list(expr = expr_text, n = length(value))
  )
}

cc_main(Sys.getenv("MILAAN_CASE", "spec"), Sys.getenv("MILAAN_BACKEND", "r"), body)
