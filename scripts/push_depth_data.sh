#!/usr/bin/env bash
# Commit and push depth chart data without clobbering other workflows' writes.
#
# Usage (from the repo root):
#   scripts/push_depth_data.sh <ours|theirs> "<commit message>" <data_dir> [extra paths...]
#
#   ours    this run rebuilt the rosters (depth chart scrapers)
#   theirs  this run only merged fields into existing rosters (ratings, draft ranks)
#
# Each attempt moves HEAD and the index to the latest origin/main while keeping
# this run's files in the working tree, reconciles field ownership with
# reconcile_depth_data.py, then commits and pushes. A rejected push just starts
# a fresh attempt; there is never a rebase that can stall on conflicts.

set -uo pipefail

base=$1; msg=$2; data_dir=$3; shift 3

for attempt in 1 2 3 4 5; do
  if ! git fetch -q origin main; then
    echo "Fetch failed (attempt $attempt)." >&2
    sleep $((attempt * 10)); continue
  fi
  git reset -q origin/main
  python3 scripts/reconcile_depth_data.py "$data_dir" origin/main --base "$base" || exit 1
  git add "$data_dir" "$@"
  if git diff --staged --quiet; then
    echo "No changes to commit."
    exit 0
  fi
  git commit -q -m "$msg"
  if git push origin HEAD:main; then
    echo "Pushed successfully (attempt $attempt)."
    exit 0
  fi
  echo "Push rejected (attempt $attempt); refetching main and retrying." >&2
  sleep $((attempt * 10))
done

echo "Push failed after 5 attempts." >&2
exit 1
