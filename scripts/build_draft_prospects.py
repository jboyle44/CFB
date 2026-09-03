"""
Builds draft_prospects.json from Tankathon's NFL Draft Big Board.

Tankathon doesn't expose class/eligibility (RS SO, JR, etc.) anywhere in
its own data -- checked both the big board listing and individual player
profile pages, neither has it. Instead, cross-reference each prospect
against our own depth_chart_data/{team}.json files, which already have
accurate class info scraped from Ourlads for every tracked team. Matched
within the SPECIFIC team file for that prospect's own school (via
teams_config.py's display_name), not a global name search across all 68
teams, so two different people who happen to share a name on different
rosters can never cross-contaminate. Only covers our 68 tracked FBS teams --
prospects from schools we don't track (there are a handful) won't get a
class, same as any other field these scripts can't fill in.

Usage: python build_draft_prospects.py [output_path]
"""
import sys
import os
import json
import datetime

from scrape_tankathon import scrape_big_board
from teams_config import TEAMS


def normalize_name(name):
    return name.lower().strip()


def load_class_lookup_by_school(depth_chart_dir="../depth_chart_data"):
    """Returns {display_name: {normalized_player_name: class_str}}."""
    lookup = {}
    for team_key, team in TEAMS.items():
        display_name = team["display_name"]
        path = os.path.join(depth_chart_dir, f"{team_key}.json")
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        by_name = {}
        for row in data.get("rows", []):
            cls = row.get("class")
            if cls:
                by_name[normalize_name(row["player"])] = cls
        lookup[display_name] = by_name
    return lookup


def build(output_path=None, depth_chart_dir="../depth_chart_data"):
    prospects = scrape_big_board()

    class_lookup = load_class_lookup_by_school(depth_chart_dir)
    matched = 0
    for p in prospects:
        school_lookup = class_lookup.get(p.get("school"), {})
        cls = school_lookup.get(normalize_name(p["name"]))
        p["class"] = cls
        if cls:
            matched += 1
    print(f"Class matched for {matched} of {len(prospects)} prospects", file=sys.stderr)

    wrapped = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "prospects": prospects,
    }

    if output_path:
        with open(output_path, "w") as f:
            json.dump(wrapped, f, indent=2)
        print(f"Wrote {len(prospects)} prospects to {output_path}", file=sys.stderr)

    return wrapped


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "draft_prospects.json"
    build(out_path)
