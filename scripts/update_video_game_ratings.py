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


def normalize_name(name):
    return name.lower().strip()


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

    # Exact-name matching only. A last-name-only fallback would carry the same
    # risk already found and fixed for CFBD matching (misattributing a
    # different same-surnamed player's data) -- but there's no position
    # signal here to safely gate that fallback the way CFBD's matching does,
    # so we accept some misses from nickname/formatting differences rather
    # than risk a wrong match.
    matched = 0
    for row in data.get("rows", []):
        norm = normalize_name(row["player"])
        info = ratings.get(norm)
        if info:
            row["cfb27Rating"] = info["ovr"]
            row["cfb27Dev"] = info["dev"]
            matched += 1
        else:
            row["cfb27Rating"] = row.get("cfb27Rating")  # preserve if present
            row["cfb27Dev"] = row.get("cfb27Dev")

    data["cfb27UpdatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  {team_key}: {matched}/{len(data.get('rows', []))} matched", file=sys.stderr)


if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "../depth_chart_data"
    for team_key in CFB27_TEAM_IDS:
        print(f"Updating {team_key}...", file=sys.stderr)
        update_team(team_key, output_dir)
