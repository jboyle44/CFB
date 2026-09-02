"""
Builds depth_chart_data_nfl/{team}.json for one NFL team.

Simpler than the NCAA version -- no 247Sports recruiting/transfer data applies
to NFL. PFF grades stay a placeholder (pffGrade: null) for now; the user adds
those separately, same as the NCAA page.

Usage: python build_depth_chart_nfl.py <team_key> [output_path]
Team keys are defined in teams_config_nfl.py.
"""
import sys
import json
import datetime

from teams_config_nfl import NFL_TEAMS
from scrape_ourlads_nfl import scrape_ourlads_nfl_depth_chart


def build(team_key, output_path=None):
    if team_key not in NFL_TEAMS:
        raise ValueError(f"Unknown team key '{team_key}'. Add it to teams_config_nfl.py first.")
    team = NFL_TEAMS[team_key]

    print(f"Scraping Ourlads depth chart for {team['display_name']}...", file=sys.stderr)
    depth_chart = scrape_ourlads_nfl_depth_chart(team["ourlads_abbr"])
    print(f"  {len(depth_chart)} depth chart rows", file=sys.stderr)

    output_rows = [{
        "position": row["position"],
        "player": row["player"],
        "jersey": row["jersey"],
        "code": row["code"],
        "isAcquired": row["isAcquired"],
        "pffGrade": None,  # populated separately from a manual PFF export
    } for row in depth_chart]

    wrapped = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "team": team["display_name"],
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
