"""
Builds depth_chart_data.json for one team by:
  1. Scraping the Ourlads depth chart (position/player/jersey/class/transfer flag)
  2. Scraping the 247Sports roster (name -> composite score + profile URL)
  3. Matching Ourlads names to 247 roster names
  4. For players flagged as transfers, fetching their individual 247 profile page
     for HS recruiting rank + transfer portal rank
  5. Writing the merged JSON in the same shape depth_charts.html expects

Usage: python build_depth_chart.py <team_key> [output_path]
Team keys are defined in teams_config.py.
"""
import sys
import json
import datetime

from teams_config import TEAMS
from scrape_ourlads import scrape_ourlads_depth_chart
from scrape_247 import scrape_247_roster, scrape_247_player_profile


def normalize_name(name):
    return name.lower().strip()


def build(team_key, output_path=None, fetch_transfer_detail=True):
    if team_key not in TEAMS:
        raise ValueError(f"Unknown team key '{team_key}'. Add it to teams_config.py first.")
    team = TEAMS[team_key]

    print(f"Scraping Ourlads depth chart for {team['display_name']}...", file=sys.stderr)
    depth_chart = scrape_ourlads_depth_chart(team["ourlads_slug"], team["ourlads_id"])
    print(f"  {len(depth_chart)} depth chart rows", file=sys.stderr)

    print(f"Scraping 247Sports roster for {team['display_name']}...", file=sys.stderr)
    roster = scrape_247_roster(team["sports247_slug"])
    print(f"  {len(roster)} roster entries", file=sys.stderr)
    roster_by_norm_name = {normalize_name(k): v for k, v in roster.items()}

    output_rows = []
    profile_cache = {}  # avoid re-fetching the same profile twice

    for row in depth_chart:
        norm = normalize_name(row["player"])
        roster_match = roster_by_norm_name.get(norm)

        out_row = {
            "position": row["position"],
            "player": row["player"],
            "jersey": row["jersey"],
            "class": row["class"],
            "isTransfer": row["isTransfer"],
            "compositeScore": roster_match["compositeScore"] if roster_match else None,
            "profileUrl": roster_match["profileUrl"] if roster_match else None,
            "transferRank": None,
            "transferPosRank": None,
            "hsNationalRank": None,
            "hsPositionRank": None,
            "hsStateRank": None,
            "pffGrade": None,  # populated separately from a manual PFF Elite export
        }

        if row["isTransfer"] and fetch_transfer_detail and out_row["profileUrl"]:
            url = out_row["profileUrl"]
            if url not in profile_cache:
                print(f"  Fetching transfer/HS detail for {row['player']}...", file=sys.stderr)
                try:
                    profile_cache[url] = scrape_247_player_profile(url)
                except Exception as e:
                    print(f"    failed: {e}", file=sys.stderr)
                    profile_cache[url] = {}
            detail = profile_cache[url]
            out_row.update({k: v for k, v in detail.items() if v is not None})
        elif not row["isTransfer"] and out_row["profileUrl"]:
            # non-transfers: still worth pulling HS rank if we want it displayed;
            # comment this block out if you want to keep to composite-score-only for speed
            pass

        output_rows.append(out_row)

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
        print("Usage: python build_depth_chart.py <team_key> [output_path]", file=sys.stderr)
        sys.exit(1)
    team_key = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "depth_chart_data.json"
    build(team_key, out_path)
