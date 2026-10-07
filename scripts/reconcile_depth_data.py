"""Merge freshly written depth chart JSON files with the latest copies on main,
so two workflows that touch the same files never overwrite each other's data.

Each depth chart file is written by several independent workflows:
  - build_depth_chart*.py owns the roster structure (rows, positions, CFBD data)
  - update_video_game_ratings*.py owns cfb27*/madden27* fields
  - merge_draft_ranks.py owns draftRank
  - PFF loads own pff* fields
Every owner stamps a top-level *UpdatedAt field when it writes. For each field
group, whichever side has the newer stamp wins; everything else comes from the
base side.

Usage:
  python3 reconcile_depth_data.py <data_dir> <git_ref> --base ours|theirs

  --base ours    the roster structure in the working tree wins (depth chart
                 builds); newer owner fields are pulled in from <git_ref>
  --base theirs  the roster structure at <git_ref> wins (ratings and draft
                 merges); this run's newer owner fields are applied on top

The working tree files are rewritten in place. Files that don't exist at
<git_ref> are left untouched.
"""

import datetime
import json
import os
import subprocess
import sys

FIELD_GROUPS = {
    "cfb27UpdatedAt": ("cfb27Rating", "cfb27Dev"),
    "madden27UpdatedAt": ("madden27Rating", "madden27Dev"),
    "draftRankUpdatedAt": ("draftRank",),
    "pffUpdatedAt": ("pffGrade", "pffPositionRank", "pffPositionTotal",
                     "pffPositionLabel", "pffTied"),
}


def parse_ts(value):
    if not value:
        return None
    try:
        ts = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts


def norm(name):
    return (name or "").lower().strip()


def index_rows(rows):
    by_name = {}
    for r in rows:
        by_name.setdefault(norm(r.get("player")), []).append(r)
    return by_name


def find_match(row, index, fields):
    candidates = index.get(norm(row.get("player")), [])
    if len(candidates) <= 1:
        return candidates[0] if candidates else None
    # The same name can appear more than once: a player listed at two
    # positions, or two different players who share a name. Narrow by jersey
    # and position, and accept a match only when the field values are
    # unambiguous.
    for key in (("jersey", "position"), ("jersey",)):
        narrowed = [c for c in candidates if all(c.get(k) == row.get(k) for k in key)]
        if len(narrowed) == 1:
            return narrowed[0]
        if narrowed:
            candidates = narrowed
            break
    values = {tuple(json.dumps(c.get(f)) for f in fields) for c in candidates}
    return candidates[0] if len(values) == 1 else None


def overlay(target, source, stamp, fields):
    """Copy one field group from source into target, matched by player."""
    index = index_rows(source.get("rows", []))
    for row in target.get("rows", []):
        match = find_match(row, index, fields)
        if match is None:
            continue
        for f in fields:
            if f in match:
                row[f] = match[f]
        # The ratings scripts backfill positions for reserve players listed
        # as "RES"; keep that backfill with the ratings it came from.
        if stamp == "cfb27UpdatedAt" and row.get("position") == "RES" \
                and match.get("position") not in (None, "RES"):
            row["position"] = match["position"]
    target[stamp] = source.get(stamp)


def reconcile(ours, theirs, base):
    if base == "ours":
        result, other = ours, theirs
    else:
        result, other = theirs, ours
    pulled = []
    for stamp, fields in FIELD_GROUPS.items():
        other_ts, result_ts = parse_ts(other.get(stamp)), parse_ts(result.get(stamp))
        if other_ts and (result_ts is None or other_ts > result_ts):
            overlay(result, other, stamp, fields)
            pulled.append(stamp)
    return result, pulled


def main():
    if len(sys.argv) != 5 or sys.argv[3] != "--base" or sys.argv[4] not in ("ours", "theirs"):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    data_dir, ref, base = sys.argv[1], sys.argv[2], sys.argv[4]

    changed = 0
    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(data_dir, fname)
        git_path = os.path.normpath(os.path.relpath(path)).replace(os.sep, "/")
        shown = subprocess.run(["git", "show", f"{ref}:{git_path}"],
                               capture_output=True, text=True)
        if shown.returncode != 0:
            continue  # new file on this side only
        with open(path) as f:
            ours = json.load(f)
        theirs = json.loads(shown.stdout)

        result, pulled = reconcile(ours, theirs, base)
        with open(path, "w") as f:
            json.dump(result, f, indent=2)
        if pulled:
            changed += 1
            side = ref if base == "ours" else "this run"
            print(f"  {fname}: took {', '.join(pulled)} from {side}", file=sys.stderr)
    print(f"Reconciled {data_dir} against {ref} (base={base}); "
          f"{changed} file(s) merged field groups.", file=sys.stderr)


if __name__ == "__main__":
    main()
