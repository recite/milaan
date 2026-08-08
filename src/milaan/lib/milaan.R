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

# Put an archived version ahead of the installed one for the rest of the session.
#
# `library(pkg, lib.loc = lib)` attaches the pinned version but leaves
# `.libPaths()` alone, so `packageVersion()` -- and therefore the `env` block of
# every result -- goes on reporting whatever is installed system-wide. A backend
# that loads sandwich 2.4-0 and records 3.1-2 is worse than one that fails.
#
# An empty path is a no-op, so one script serves both the pinned backend and the
# current one.
cc_pin <- function(lib) {
  if (length(lib) && nzchar(lib)) .libPaths(c(lib, .libPaths()))
  invisible(.libPaths())
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

# Flatten any R object into a flat list of named scalars.
#
# Deciding which ten numbers a case should report requires already understanding
# what moved, which is precisely what a screening run has not done yet. So a
# screen dumps everything the call returned and lets the comparison say which
# quantities differ; a case that has been understood still names its own.
#
# Names follow the existing convention: dots for named components, `[i]` and
# `[i,j]` for positions. Non-numeric leaves -- character, factor, function, call
# -- are skipped rather than coerced, because a screen compares numbers and a
# string that changed is not a moved quantity.
cc_flatten <- function(x, prefix = "", max = 2000) {
  out <- list()
  join <- function(a, b) {
    if (!nzchar(a)) return(b)
    # `coef.x` but `resid[3]`: a positional label is already punctuated, and a
    # stray dot before it would read as a component named "[3]".
    if (startsWith(b, "[")) paste0(a, b) else paste0(a, ".", b)
  }

  emit <- function(name, value) {
    if (length(out) >= max) {
      stop(sprintf(
        "cc_flatten: more than %d quantities under '%s'; pass a narrower object",
        max, prefix
      ))
    }
    out[[if (nzchar(name)) name else "value"]] <<- as.numeric(value)
  }

  walk <- function(value, name) {
    if (is.null(value) || length(value) == 0) {
      return(invisible(NULL))
    }
    if (is.list(value)) {
      labels <- names(value)
      for (i in seq_along(value)) {
        label <- if (!is.null(labels) && nzchar(labels[[i]])) {
          labels[[i]]
        } else {
          sprintf("[%d]", i)
        }
        walk(value[[i]], join(name, label))
      }
      return(invisible(NULL))
    }
    # Logical is numeric enough to be worth keeping: `converged` flipping from
    # TRUE to FALSE between two versions is a moved quantity by any reading.
    if (!is.numeric(value) && !is.logical(value)) {
      return(invisible(NULL))
    }

    dims <- dim(value)
    if (length(dims) == 2L) {
      labels <- dimnames(value)
      rows <- if (!is.null(labels) && !is.null(labels[[1]])) labels[[1]] else NULL
      cols <- if (!is.null(labels) && !is.null(labels[[2]])) labels[[2]] else NULL
      for (i in seq_len(dims[[1]])) {
        for (j in seq_len(dims[[2]])) {
          label <- if (!is.null(rows) && !is.null(cols)) {
            paste0(rows[[i]], ".", cols[[j]])
          } else {
            sprintf("[%d,%d]", i, j)
          }
          emit(join(name, label), value[i, j])
        }
      }
      return(invisible(NULL))
    }
    if (length(dims) > 2L) {
      flat <- as.vector(value)
      for (i in seq_along(flat)) emit(join(name, sprintf("[%d]", i)), flat[[i]])
      return(invisible(NULL))
    }

    labels <- names(value)
    if (length(value) == 1L && is.null(labels)) {
      emit(name, value[[1]])
      return(invisible(NULL))
    }
    for (i in seq_along(value)) {
      label <- if (!is.null(labels) && nzchar(labels[[i]])) {
        labels[[i]]
      } else {
        sprintf("[%d]", i)
      }
      emit(join(name, label), value[[i]])
    }
    invisible(NULL)
  }

  walk(x, prefix)
  out
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
