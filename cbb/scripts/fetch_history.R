# Pull mirrored CollegeBasketballData history (john-b-edwards/cbbd-data releases)
# and write flat csv.gz files to cbb/raw/. Uses zero CBBD API quota.
suppressPackageStartupMessages({ library(data.table); library(jsonlite) })

base <- "https://github.com/john-b-edwards/cbbd-data/releases/download"
resources <- c("games", "lines", "team_box_scores")
seasons <- 2008:2026
out_dir <- "cbb/raw"
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
log <- file(file.path(out_dir, "fetch_log.txt"), "w")
say <- function(...) { msg <- paste0(...); cat(msg, "\n"); writeLines(msg, log) }

flatten <- function(df) {
  dt <- as.data.table(df)
  for (col in names(dt)) {
    v <- dt[[col]]
    if (is.list(v)) {
      set(dt, j = col, value = vapply(v, function(x) {
        if (is.null(x) || length(x) == 0) NA_character_ else as.character(toJSON(x, auto_unbox = TRUE, na = "null"))
      }, character(1)))
    } else if (inherits(v, c("POSIXct", "Date"))) {
      set(dt, j = col, value = format(v, "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"))
    }
  }
  dt
}

for (r in resources) {
  for (s in seasons) {
    url <- sprintf("%s/%s/%s_%d.rds", base, r, r, s)
    tmp <- tempfile(fileext = ".rds")
    ok <- tryCatch({ download.file(url, tmp, mode = "wb", quiet = TRUE); TRUE },
                   error = function(e) FALSE, warning = function(w) FALSE)
    if (!ok) { say(sprintf("MISS %s %d", r, s)); next }
    df <- tryCatch(readRDS(tmp), error = function(e) NULL)
    if (is.null(df)) { say(sprintf("BADREAD %s %d", r, s)); next }
    if (s == 2025) {
      sink(log); cat(sprintf("\n==== str %s %d ====\n", r, s)); str(df, max.level = 2, list.len = 80); sink()
    }
    dt <- flatten(df)
    fwrite(dt, file.path(out_dir, sprintf("%s_%d.csv.gz", r, s)))
    say(sprintf("OK %s %d rows=%d cols=%d", r, s, nrow(dt), ncol(dt)))
  }
}
close(log)
