# Shared helpers for R backend scripts.
#
# Every backend script is a standalone program invoked as
#   Rscript run_r.R <data.csv> <out.json>
# and its only job is to write the result schema. Errors are caught and written
# out as `status: "error"` rather than allowed to kill the process, because a
# package refusing to fit a model is a finding we want recorded next to the
# packages that did fit it.

suppressPackageStartupMessages(library(jsonlite))

# The runner appends the data and output paths to whatever the case declared as
# the backend command, so they are always the last two arguments. Reading from the
# end lets one script serve several backends that differ only by a flag.
cc_args <- function() {
  a <- commandArgs(trailingOnly = TRUE)
  if (length(a) < 2) stop("usage: Rscript <script> [flags...] <data.csv> <out.json>")
  n <- length(a)
  list(data = a[[n - 1]], out = a[[n]], flags = if (n > 2) a[seq_len(n - 2)] else character())
}

cc_env <- function(packages = character()) {
  versions <- list()
  for (p in packages) {
    versions[[p]] <- tryCatch(
      as.character(utils::packageVersion(p)),
      error = function(e) "not installed"
    )
  }
  list(
    language = "R",
    version = paste0(R.version$major, ".", R.version$minor),
    packages = versions
  )
}

# Collect warnings emitted while evaluating an expression. R's convention is to
# warn rather than fail on numerically doubtful fits, so the warnings are part of
# the result: they are the only signal separating "converged" from "diverged to
# infinity but stopped iterating".
cc_capture <- function(expr) {
  warnings <- character()
  value <- withCallingHandlers(
    expr,
    warning = function(w) {
      warnings <<- c(warnings, conditionMessage(w))
      invokeRestart("muffleWarning")
    }
  )
  list(value = value, warnings = warnings)
}

cc_write <- function(path, case_id, backend, quantities = list(),
                     diagnostics = list(), env = cc_env(),
                     status = "ok", error = NULL) {
  payload <- list(
    case_id = case_id,
    backend = backend,
    env = env,
    status = jsonlite::unbox(status),
    quantities = lapply(quantities, function(v) {
      if (is.null(v) || length(v) == 0 || !is.finite(v)) NULL else jsonlite::unbox(as.numeric(v))
    }),
    diagnostics = diagnostics,
    error = if (is.null(error)) NULL else jsonlite::unbox(as.character(error))
  )
  # digits = NA keeps full float64 precision; anything less would manufacture
  # disagreement between backends out of rounding.
  writeLines(jsonlite::toJSON(payload, auto_unbox = TRUE, null = "null",
                              digits = NA, pretty = TRUE), path)
}

# Wrap a backend body so that an uncaught error still produces a valid result
# file describing the failure.
cc_main <- function(case_id, backend, body, packages = character()) {
  args <- cc_args()
  env <- cc_env(packages)
  result <- tryCatch(
    body(args$data),
    error = function(e) list(status = "error", error = conditionMessage(e))
  )
  cc_write(
    args$out,
    case_id = case_id,
    backend = backend,
    quantities = if (is.null(result$quantities)) list() else result$quantities,
    diagnostics = if (is.null(result$diagnostics)) list() else result$diagnostics,
    env = env,
    status = if (is.null(result$status)) "ok" else result$status,
    error = result$error
  )
}
