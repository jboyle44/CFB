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


def load_previous_247_data(output_path):
    """If a previous output file exists, index it by normalized player name so we can
    carry forward composite/transfer/HS data on runs where 247Sports blocks the request."""
    if not output_path:
        return {}
    try:
        with open(output_path) as f:
            prev = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {normalize_name(r["player"]): r for r in prev.get("rows", [])}


def build(team_key, output_path=None, fetch_detail_for_all=False):
    if team_key not in TEAMS:
        raise ValueError(f"Unknown team key '{team_key}'. Add it to teams_config.py first.")
    team = TEAMS[team_key]

    print(f"Scraping Ourlads depth chart for {team['display_name']}...", file=sys.stderr)
    depth_chart = scrape_ourlads_depth_chart(team["ourlads_slug"], team["ourlads_id"])
    print(f"  {len(depth_chart)} depth chart rows", file=sys.stderr)

    print(f"Scraping 247Sports roster for {team['display_name']}...", file=sys.stderr)
    try:
        roster = scrape_247_roster(team["sports247_slug"])
        print(f"  {len(roster)} roster entries", file=sys.stderr)
    except Exception as e:
        print(f"  247Sports roster scrape failed ({e}); falling back to previously-saved "
              f"composite/transfer data for this run.", file=sys.stderr)
        roster = {}
    roster_by_norm_name = {normalize_name(k): v for k, v in roster.items()}
    previous_by_norm_name = load_previous_247_data(output_path)

    output_rows = []
    profile_cache = {}  # avoid re-fetching the same profile twice
    total = len(depth_chart)

    for i, row in enumerate(depth_chart, 1):
        norm = normalize_name(row["player"])
        roster_match = roster_by_norm_name.get(norm)
        prev_match = previous_by_norm_name.get(norm)

        out_row = {
            "position": row["position"],
            "player": row["player"],
            "jersey": row["jersey"],
            "class": row["class"],
            "isTransfer": row["isTransfer"],
            "compositeScore": None,
            "profileUrl": None,
            "transferRank": None,
            "transferPosRank": None,
            "hsNationalRank": None,
            "hsPositionRank": None,
            "hsStateRank": None,
            "pffGrade": None,  # populated separately from a manual PFF Elite export
        }

        if roster_match:
            out_row["compositeScore"] = roster_match["compositeScore"]
            out_row["profileUrl"] = roster_match["profileUrl"]
        elif prev_match:
            # 247 scrape failed/skipped this run -- carry forward last known values
            for k in ("compositeScore", "profileUrl", "transferRank", "transferPosRank",
                      "hsNationalRank", "hsPositionRank", "hsStateRank", "pffGrade"):
                out_row[k] = prev_match.get(k)

        should_fetch = roster_match and out_row["profileUrl"] and (row["isTransfer"] or fetch_detail_for_all)
        if should_fetch:
            url = out_row["profileUrl"]
            if url not in profile_cache:
                print(f"  [{i}/{total}] Fetching detail for {row['player']}...", file=sys.stderr)
                try:
                    profile_cache[url] = scrape_247_player_profile(url)
                except Exception as e:
                    print(f"    failed: {e}", file=sys.stderr)
                    profile_cache[url] = {}
            detail = profile_cache[url]
            out_row.update({k: v for k, v in detail.items() if v is not None})

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
        print("Usage: python build_depth_chart.py <team_key> [output_path] [--full]", file=sys.stderr)
        print("  --full  fetch HS/transfer detail for every player, not just transfers", file=sys.stderr)
        print("          (this makes ~70-80 requests to 247Sports for a full roster --", file=sys.stderr)
        print("          expect it to take a few minutes)", file=sys.stderr)
        sys.exit(1)
    team_key = sys.argv[1]
    remaining = sys.argv[2:]
    full = "--full" in remaining
    remaining = [a for a in remaining if a != "--full"]
    out_path = remaining[0] if remaining else "depth_chart_data.json"
    build(team_key, out_path, fetch_detail_for_all=full)
