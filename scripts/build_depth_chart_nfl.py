"""
Builds depth_chart_data_nfl/{team}.json for one NFL team.

Simpler than the NCAA version -- no 247Sports recruiting/transfer data applies
to NFL. PFF grades and Madden27 ratings are set by separate scripts (a manual
PFF export match, and update_video_game_ratings_nfl.py) that don't run every
time this one does -- so those fields are always carried forward from the
previous output rather than reset, or they'd be silently erased on the very
next Ourlads-only refresh.

Usage: python build_depth_chart_nfl.py <team_key> [output_path]
Team keys are defined in teams_config_nfl.py.
"""
import sys
import json
import datetime

from teams_config_nfl import NFL_TEAMS
from scrape_ourlads_nfl import scrape_ourlads_nfl_depth_chart


def normalize_name(name):
    return name.lower().strip()


def load_previous_data(output_path):
    if not output_path:
        return {}
    try:
        with open(output_path) as f:
            prev = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {normalize_name(r["player"]): r for r in prev.get("rows", [])}


def load_previous_metadata(output_path):
    if not output_path:
        return {}
    try:
        with open(output_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def build(team_key, output_path=None):
    if team_key not in NFL_TEAMS:
        raise ValueError(f"Unknown team key '{team_key}'. Add it to teams_config_nfl.py first.")
    team = NFL_TEAMS[team_key]

    print(f"Scraping Ourlads depth chart for {team['display_name']}...", file=sys.stderr)
    depth_chart, schemes = scrape_ourlads_nfl_depth_chart(team["ourlads_abbr"])
    print(f"  {len(depth_chart)} depth chart rows", file=sys.stderr)

    previous_by_norm_name = load_previous_data(output_path)
    previous_metadata = load_previous_metadata(output_path)

    output_rows = []
    for row in depth_chart:
        prev_match = previous_by_norm_name.get(normalize_name(row["player"]))
        out_row = {
            "position": row["position"],
            "player": row["player"],
            "jersey": row["jersey"],
            "code": row["code"],
            "isAcquired": row["isAcquired"],
            "pffGrade": None,
            "madden27Rating": None,
            "madden27Dev": None,
        }
        if prev_match:
            for k in ("pffGrade", "pffPositionRank", "pffPositionTotal", "pffPositionLabel", "pffTied",
                      "madden27Rating", "madden27Dev"):
                if out_row.get(k) is None:
                    out_row[k] = prev_match.get(k)
        output_rows.append(out_row)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    wrapped = {
        "generatedAt": now_iso,
        "ourladsUpdatedAt": now_iso,
        "madden27UpdatedAt": previous_metadata.get("madden27UpdatedAt"),
        "pffUpdatedAt": previous_metadata.get("pffUpdatedAt"),
        "team": team["display_name"],
        "offenseScheme": schemes.get("offense"),
        "defenseScheme": schemes.get("defense"),
        "rows": output_rows,
    }

    if output_path:
        with open(output_path, "w") as f:
            json.dump(wrapped, f, indent=2)
        print(f"Wrote {output_path}", file=sys.stderr)

    return wrapped


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_depth_chart_nfl.py <team_key> [output_path]", file=sys.stderr)
        sys.exit(1)
    team_key = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "depth_chart_data_nfl.json"
    build(team_key, out_path)
