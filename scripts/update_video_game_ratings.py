"""
Fetches CFB27 player ratings from teamcrafters.net and merges them into the
existing depth_chart_data/{team}.json files by player name. Adds two new
fields per row: cfb27Rating (OVR) and cfb27Dev (dev trait), plus a top-level
cfb27UpdatedAt timestamp.

Exact-name matching only -- see inline comment in update_team() for why a
last-name fallback isn't used here.
"""
import sys
import json
import glob
import os
import datetime

sys.path.insert(0, os.path.dirname(__file__))
from cfb27_team_ids import CFB27_TEAM_IDS
from scrape_teamcrafters import get_cfb27_ratings


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "vi", "vii"}


def normalize_name(name):
    # Strip periods too -- confirmed real mismatch: our site stores "Jr."
    # (with period) while teamcrafters.net's own scrape never includes one
    # ("Jr"), so exact string comparison never matched despite being the
    # same person.
    return name.lower().strip().replace(".", "")


def strip_suffix(name_norm):
    """Removes a trailing suffix token entirely, for matching names where
    one source has the suffix and the other doesn't -- a missing suffix,
    not just a formatting difference, so period-stripping alone doesn't
    help; the whole token needs to be droppable on either side."""
    parts = name_norm.split()
    if parts and parts[-1] in SUFFIXES:
        return " ".join(parts[:-1])
    return name_norm


def update_team(team_key, output_dir):
    if team_key not in CFB27_TEAM_IDS:
        print(f"  no teamcrafters ID for {team_key}, skipping", file=sys.stderr)
        return

    path = os.path.join(output_dir, f"{team_key}.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"  no existing data file for {team_key}, skipping", file=sys.stderr)
        return

    try:
        ratings = get_cfb27_ratings(CFB27_TEAM_IDS[team_key])
    except Exception as e:
        print(f"  fetch failed for {team_key}: {e}", file=sys.stderr)
        return

    # Suffix-stripped index for the fallback -- only keep an entry if it's
    # unambiguous (exactly one player on this team's roster reduces to that
    # stripped name), same safety pattern used elsewhere in this project.
    stripped_candidates = {}
    for name, info in ratings.items():
        key = strip_suffix(name)
        stripped_candidates.setdefault(key, []).append(info)
    ratings_by_stripped = {k: v[0] for k, v in stripped_candidates.items() if len(v) == 1}

    # Exact-name matching first. A last-name-only fallback would carry the same
    # risk already found and fixed for CFBD matching (misattributing a
    # different same-surnamed player's data) -- but there's no position
    # signal here to safely gate that fallback the way CFBD's matching does,
    # so we accept some misses from nickname/formatting differences rather
    # than risk a wrong match.
    matched = 0
    position_backfilled = 0
    for row in data.get("rows", []):
        norm = normalize_name(row["player"])
        info = ratings.get(norm)
        if not info:
            info = ratings_by_stripped.get(strip_suffix(norm))
        if info:
            row["cfb27Rating"] = info["ovr"]
            row["cfb27Dev"] = info["dev"]
            matched += 1
            # Position backfill -- ONLY for reserve players whose real
            # position is completely unknown (marked "RES" because they
            # were never seen on an active depth chart to backfill from).
            # Never touches any other player's position, active or
            # reserve, whether or not it happens to already be correct.
            if row.get("position") == "RES" and info.get("position"):
                row["position"] = info["position"]
                position_backfilled += 1
        else:
            row["cfb27Rating"] = row.get("cfb27Rating")  # preserve if present
            row["cfb27Dev"] = row.get("cfb27Dev")

    data["cfb27UpdatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  {team_key}: {matched}/{len(data.get('rows', []))} matched, "
          f"{position_backfilled} RES positions backfilled", file=sys.stderr)


if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "../depth_chart_data"
    for team_key in CFB27_TEAM_IDS:
        print(f"Updating {team_key}...", file=sys.stderr)
        update_team(team_key, output_dir)
