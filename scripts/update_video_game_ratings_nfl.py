"""
Fetches Madden 27 player ratings from teamcrafters.net and merges them into
the existing depth_chart_data_nfl/{team}.json files by player name. Adds two
new fields per row: madden27Rating (OVR) and madden27Dev (dev trait), plus a
top-level madden27UpdatedAt timestamp.
"""
import sys
import json
import os
import datetime

sys.path.insert(0, os.path.dirname(__file__))
from madden27_team_ids import MADDEN27_TEAM_IDS
from scrape_teamcrafters import get_madden27_ratings


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "vi", "vii"}


def normalize_name(name):
    # Strip periods too -- confirmed real mismatch: our site stores "Jr."
    # (with period) while teamcrafters.net's own scrape never includes one
    # ("Jr"), so "Paris Johnson Jr." vs "paris johnson jr" never matched on
    # exact string comparison despite being the same person.
    return name.lower().strip().replace(".", "")


def strip_suffix(name_norm):
    """Removes a trailing suffix token entirely, for matching names where
    one source has the suffix and the other doesn't. Confirmed real case:
    our site has "Gardner Minshew II" but teamcrafters.net lists him under
    this same team as just "Gardner Minshew" (no suffix at all) -- a
    missing suffix, not a formatting difference, so period-stripping alone
    doesn't help; the whole token needs to be droppable on either side."""
    parts = name_norm.split()
    if parts and parts[-1] in SUFFIXES:
        return " ".join(parts[:-1])
    return name_norm


def update_team(team_key, output_dir):
    if team_key not in MADDEN27_TEAM_IDS:
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
        ratings = get_madden27_ratings(MADDEN27_TEAM_IDS[team_key])
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

    # Exact-name matching first; last-name-only fallback isn't used here
    # without a position signal to gate it (see update_video_game_ratings.py).
    matched = 0
    for row in data.get("rows", []):
        norm = normalize_name(row["player"])
        info = ratings.get(norm)
        if not info:
            info = ratings_by_stripped.get(strip_suffix(norm))
        if info:
            row["madden27Rating"] = info["ovr"]
            row["madden27Dev"] = info["dev"]
            matched += 1
        else:
            row["madden27Rating"] = row.get("madden27Rating")
            row["madden27Dev"] = row.get("madden27Dev")

    data["madden27UpdatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  {team_key}: {matched}/{len(data.get('rows', []))} matched", file=sys.stderr)


if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "../depth_chart_data_nfl"
    for team_key in MADDEN27_TEAM_IDS:
        print(f"Updating {team_key}...", file=sys.stderr)
        update_team(team_key, output_dir)
