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
import unicodedata

sys.path.insert(0, os.path.dirname(__file__))
from madden27_team_ids import MADDEN27_TEAM_IDS
from scrape_teamcrafters import get_madden27_ratings
from madden27_aliases import MADDEN27_ALIASES


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "vi", "vii"}


def normalize_name(name):
    """Lowercase, no periods, no accents, single spaces. Applied to BOTH our
    names and teamcrafters' names: teamcrafters keeps periods in initials
    ("a.j. brown") while Ourlads gives "AJ"/"A.J.", and accents differ
    ("Pi\u00f1eiro" vs "Pineiro"). Normalizing only one side missed ~40
    players, mostly initial-named ones (A.J. Brown, T.J. Watt, C.J. Stroud)."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return " ".join(name.lower().replace(".", "").split())


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


def build_league_index():
    """{normalized name: info} for names that appear exactly once across all
    Madden rosters (also indexed suffix-stripped, same uniqueness rule).
    teamcrafters pages are cached by the scraper, so this costs one fetch per
    team, shared with update_team."""
    counts, index = {}, {}
    for team_key, team_id in MADDEN27_TEAM_IDS.items():
        try:
            raw = get_madden27_ratings(team_id)
        except Exception as e:
            print(f"  league index: fetch failed for {team_key}: {e}", file=sys.stderr)
            continue
        for name, info in raw.items():
            norm = normalize_name(name)
            for key in {norm, strip_suffix(norm)}:
                counts[key] = counts.get(key, 0) + 1
                index[key] = info
    return {k: v for k, v in index.items() if counts[k] == 1}


def update_team(team_key, output_dir, league_index=None):
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
        raw = get_madden27_ratings(MADDEN27_TEAM_IDS[team_key])
    except Exception as e:
        print(f"  fetch failed for {team_key}: {e}", file=sys.stderr)
        return
    ratings = {normalize_name(n): info for n, info in raw.items()}
    aliases = {normalize_name(k): normalize_name(v)
               for k, v in MADDEN27_ALIASES.get(team_key, {}).items()}

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
        if not info and norm in aliases:
            # Known name differences (nicknames, shortened first names)
            # confirmed by hand on the same team -- see madden27_aliases.py.
            info = ratings.get(aliases[norm])
        if not info and league_index is not None:
            # Players traded or signed after teamcrafters' roster snapshot are
            # still listed under their old team. Accept a league-wide match
            # only when exactly one Madden player has that name.
            info = league_index.get(norm) or league_index.get(strip_suffix(norm))
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
    league_index = build_league_index()
    for team_key in MADDEN27_TEAM_IDS:
        print(f"Updating {team_key}...", file=sys.stderr)
        update_team(team_key, output_dir, league_index)
