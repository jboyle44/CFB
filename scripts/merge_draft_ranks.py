"""
Merges draft prospect ranks from draft_prospects.json into each matching
player's row in depth_chart_data/{team}.json.

Matched within the SPECIFIC team file for that prospect's own school (via
teams_config.py's display_name), not a global name search across all 68
teams -- same safety pattern already used for the class cross-reference in
build_draft_prospects.py, so two different people sharing a name on
different rosters can never cross-contaminate.

Run as part of the same weekly Tuesday workflow as the Tankathon scrape,
right after draft_prospects.json is built, so the depth charts stay in
sync with whatever the board looked like that week.

Usage: python merge_draft_ranks.py [prospects_path] [depth_chart_dir]
"""
import sys
import os
import json

from teams_config import TEAMS


def normalize_name(name):
    return name.lower().strip()


def merge(prospects_path="../draft_prospects.json", depth_chart_dir="../depth_chart_data"):
    try:
        with open(prospects_path) as f:
            prospects_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Could not read {prospects_path}: {e}", file=sys.stderr)
        return

    prospects = prospects_data.get("prospects", [])
    generated_at = prospects_data.get("generatedAt")

    display_name_to_key = {team["display_name"]: key for key, team in TEAMS.items()}

    # Group prospects by school first so each team file is only opened once.
    by_school = {}
    for p in prospects:
        school = p.get("school")
        if school:
            by_school.setdefault(school, []).append(p)

    touched = []
    for school, school_prospects in by_school.items():
        team_key = display_name_to_key.get(school)
        if not team_key:
            continue  # a school not in our 68 tracked teams -- nothing to merge into

        path = os.path.join(depth_chart_dir, f"{team_key}.json")
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue

        rank_by_name = {normalize_name(p["name"]): p["rank"] for p in school_prospects}
        changed = False
        for row in data.get("rows", []):
            rank = rank_by_name.get(normalize_name(row["player"]))
            if rank is not None and row.get("draftRank") != rank:
                row["draftRank"] = rank
                changed = True
            elif rank is None and row.get("draftRank") is not None:
                # No longer on the board (dropped out of the top ranking) --
                # clear the stale rank rather than leaving an outdated badge.
                row["draftRank"] = None
                changed = True

        if changed or data.get("draftRankUpdatedAt") != generated_at:
            data["draftRankUpdatedAt"] = generated_at
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            touched.append(team_key)

    print(f"Merged draft ranks into {len(touched)} team files: {touched}", file=sys.stderr)


if __name__ == "__main__":
    prospects_path = sys.argv[1] if len(sys.argv) > 1 else "../draft_prospects.json"
    depth_chart_dir = sys.argv[2] if len(sys.argv) > 2 else "../depth_chart_data"
    merge(prospects_path, depth_chart_dir)
