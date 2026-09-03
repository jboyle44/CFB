"""
Builds depth_chart_data.json for one team by:
  1. Scraping the Ourlads depth chart (position/player/jersey/class/transfer flag)
  2. Pulling recruiting composite/stars/ranking from CollegeFootballData.com's
     real, authenticated API (replaces the old 247Sports scraper entirely --
     no bot detection risk since this is a proper API call)
  3. Pulling transfer portal data (stars/rating/origin school) from the same
     API for players flagged as transfers
  4. Writing the merged JSON in the same shape depth_charts.html expects

Requires the CFBD_API_KEY environment variable (same key already used for the
BRR model's SP+ ratings).

Usage: python build_depth_chart.py <team_key> [output_path]
Team keys are defined in teams_config.py.
"""
import sys
import json
import datetime

from teams_config import TEAMS
from scrape_ourlads import scrape_ourlads_depth_chart
from scrape_cfbd_recruiting import get_recruiting_players, get_transfer_portal

CURRENT_YEAR = datetime.datetime.now().year


def normalize_name(name):
    return name.lower().strip()


def infer_recruiting_class_year(class_str):
    """
    Maps a class string like 'FR', 'RS SO', 'JR', 'RS SR' to the year that
    player's recruiting class most likely was, so we only query CFBD for the
    specific years actually present on the roster instead of guessing broadly.
    """
    if not class_str:
        return CURRENT_YEAR
    c = class_str.upper().strip()
    is_redshirt = c.startswith("RS")
    base = c.replace("RS", "").strip()
    years_back = {"FR": 0, "SO": 1, "JR": 2, "SR": 3, "GR": 4}.get(base, 1)
    if is_redshirt:
        years_back += 1
    return CURRENT_YEAR - years_back


def load_previous_data(output_path):
    """Carry forward last-known values for players CFBD doesn't have data for
    this run (e.g. walk-ons with no recruiting profile at all)."""
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
    team_name = team["display_name"]

    print(f"Scraping Ourlads depth chart for {team_name}...", file=sys.stderr)
    depth_chart, schemes = scrape_ourlads_depth_chart(team["ourlads_slug"], team["ourlads_id"])
    print(f"  {len(depth_chart)} depth chart rows", file=sys.stderr)

    previous_by_norm_name = load_previous_data(output_path)

    # Recruiting composite scores and transfer rankings never change once
    # assigned (they're historical/fixed), so on a steady-state week where the
    # roster hasn't changed, there's no reason to re-fetch anything -- only
    # query CFBD for players who don't already have cached data from a
    # previous run. This keeps the free-tier 1,000-calls/month budget
    # sustainable across 68+ teams updating twice a week; a full roster only
    # costs real API calls once, the first time each player appears.
    def already_has_recruit_data(row):
        prev = previous_by_norm_name.get(normalize_name(row["player"]))
        return prev is not None and prev.get("compositeScore") is not None

    def already_has_transfer_data(row):
        prev = previous_by_norm_name.get(normalize_name(row["player"]))
        return prev is not None and prev.get("transferRank") is not None

    needed_years = sorted({
        infer_recruiting_class_year(r["class"]) for r in depth_chart
        if not already_has_recruit_data(r)
    })
    recruiting_by_name = {}
    recruiting_by_last_name = {}
    if needed_years:
        print(f"Fetching CFBD recruiting data for new players, class years: {needed_years}...", file=sys.stderr)
        for yr in needed_years:
            try:
                by_full, by_last = get_recruiting_players(team_name, yr)
                recruiting_by_name.update(by_full)
                # Only keep a last-name fallback entry if it's unambiguous across
                # ALL years merged too, not just within one year's class.
                for last, info in by_last.items():
                    if last in recruiting_by_last_name and recruiting_by_last_name[last] != info:
                        recruiting_by_last_name[last] = None  # now ambiguous, drop it
                    elif last not in recruiting_by_last_name:
                        recruiting_by_last_name[last] = info
                print(f"  {yr}: {len(by_full)} players", file=sys.stderr)
            except Exception as e:
                print(f"  {yr}: failed ({e})", file=sys.stderr)
        recruiting_by_last_name = {k: v for k, v in recruiting_by_last_name.items() if v is not None}
    else:
        print("No new players needing recruiting data -- skipping CFBD recruiting call this run.", file=sys.stderr)

    needs_transfer_lookup = any(
        row["isTransfer"] and not already_has_transfer_data(row) for row in depth_chart
    )
    transfers_in = {}
    if needs_transfer_lookup:
        print(f"Fetching CFBD transfer portal data for new transfers...", file=sys.stderr)
        for yr in (CURRENT_YEAR, CURRENT_YEAR - 1):
            try:
                portal = get_transfer_portal(yr)
                for name, info in portal.items():
                    if info.get("destination") == team_name:
                        transfers_in[name] = info
            except Exception as e:
                print(f"  {yr} portal fetch failed: {e}", file=sys.stderr)
        print(f"  {len(transfers_in)} transfers in from CFBD", file=sys.stderr)
    else:
        print("No new transfers needing portal data -- skipping CFBD portal call this run.", file=sys.stderr)

    output_rows = []
    for row in depth_chart:
        norm = normalize_name(row["player"])
        recruit_match = recruiting_by_name.get(norm)
        if not recruit_match:
            last = norm.split()[-1] if norm.split() else None
            if last:
                recruit_match = recruiting_by_last_name.get(last)
        transfer_match = transfers_in.get(norm)
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

        if recruit_match and recruit_match.get("rating") is not None:
            # CFBD rating is a 0-1 decimal; rescale to the same 0-100-ish
            # ballpark the rest of the site already uses for composite scores.
            out_row["compositeScore"] = round(recruit_match["rating"] * 100)
            out_row["hsNationalRank"] = recruit_match.get("ranking")

        if row["isTransfer"] and transfer_match:
            if transfer_match.get("rating") is not None and out_row["compositeScore"] is None:
                out_row["compositeScore"] = round(transfer_match["rating"] * 100)
            out_row["transferRank"] = transfer_match.get("overallRank")
            out_row["transferPosRank"] = transfer_match.get("positionRank")

        # Fill any still-missing fields from last known-good data (e.g. walk-ons
        # with no CFBD recruiting profile at all).
        if prev_match:
            for k in ("compositeScore", "profileUrl", "transferRank", "transferPosRank",
                      "hsNationalRank", "hsPositionRank", "hsStateRank", "pffGrade"):
                if out_row.get(k) is None:
                    out_row[k] = prev_match.get(k)

        output_rows.append(out_row)

    wrapped = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "team": team_name,
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
        print("Usage: python build_depth_chart.py <team_key> [output_path]", file=sys.stderr)
        sys.exit(1)
    team_key = sys.argv[1]
    remaining = sys.argv[2:]
    remaining = [a for a in remaining if a != "--full"]  # kept for backward compat, no-op now
    out_path = remaining[0] if remaining else "depth_chart_data.json"
    build(team_key, out_path)
