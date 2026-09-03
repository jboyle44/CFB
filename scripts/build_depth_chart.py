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


# Broad position buckets so the last-name fallback (used when the roster name
# doesn't exactly match CFBD's, e.g. a nickname like "Trey" vs the legal name
# "Anthony") can be gated on position -- unverified last-name-only matches can
# silently attribute a completely different person's data (confirmed with a
# real case: a roster with three different "Moore" players).
def site_position_bucket(pos):
    if pos in ("WR-X","WR-Z","WR-SL","WR-F","WR-H","WR-Y"): return "WR"
    if pos in ("TE","TE-Y","TE-H"): return "TE"
    if pos == "RB": return "RB"
    if pos == "FB": return "RB"
    if pos == "QB": return "QB"
    if pos in ("LT","RT","QT","ST","LG","RG","QG","SG","C"): return "OL"
    if pos in ("LOLB","LDE","JACK","WOLF","BUCK","LEO","CHEETAH","CHEET","RUSH","STUD",
               "DE","NT","LDT","DT","RDT","RDE","ROLB"): return "FRONT7"
    if pos in ("SLB","WLB","STING","MAC","MLB","MONEY","DOG"): return "FRONT7"
    if pos in ("NB","HUSKY","STAR","CASH","SPUR","BAN","ROVER","CAT",
               "LCB","RCB","FCB","BCB","FS","SS","BS"): return "DB"
    if pos in ("PT","PK","KO","LS","H","PR","KR"): return "ST"
    return None


def cfbd_position_bucket(pos):
    if not pos:
        return None
    p = pos.upper()
    return {
        "QB": "QB", "RB": "RB", "HB": "RB", "FB": "RB",
        "WR": "WR", "TE": "TE",
        "OT": "OL", "OG": "OL", "OL": "OL", "C": "OL", "IOL": "OL",
        "DL": "FRONT7", "DT": "FRONT7", "DE": "FRONT7", "EDGE": "FRONT7",
        "LB": "FRONT7", "ILB": "FRONT7", "OLB": "FRONT7",
        "CB": "DB", "S": "DB", "DB": "DB", "SAF": "DB",
        "K": "ST", "P": "ST", "LS": "ST",
    }.get(p)


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


def load_previous_metadata(output_path):
    """Top-level fields from the previous run (used to carry forward
    cfbdUpdatedAt on runs where no fresh CFBD fetch happens)."""
    if not output_path:
        return {}
    try:
        with open(output_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def build(team_key, output_path=None, fetch_detail_for_all=False):
    if team_key not in TEAMS:
        raise ValueError(f"Unknown team key '{team_key}'. Add it to teams_config.py first.")
    team = TEAMS[team_key]
    team_name = team["display_name"]

    print(f"Scraping Ourlads depth chart for {team_name}...", file=sys.stderr)
    depth_chart, schemes = scrape_ourlads_depth_chart(team["ourlads_slug"], team["ourlads_id"])
    print(f"  {len(depth_chart)} depth chart rows", file=sys.stderr)

    previous_by_norm_name = load_previous_data(output_path)
    previous_metadata = load_previous_metadata(output_path)

    # Transfer portal fetch happens FIRST now, because we need each transfer's
    # origin school before we can look up their recruiting profile correctly
    # -- a transfer was never a HS recruit to their CURRENT team, so searching
    # under team_name would never find them. Real example: Earl Little Jr. at
    # Ohio State was a 2022 Alabama signee; searching "Ohio State" recruiting
    # data can never surface that, only searching "Alabama" can.
    def already_has_transfer_data(row):
        prev = previous_by_norm_name.get(normalize_name(row["player"]))
        return prev is not None and prev.get("transferRank") is not None

    needs_transfer_lookup = any(
        row["isTransfer"] and not already_has_transfer_data(row) for row in depth_chart
    )
    transfers_in = {}
    # Full multi-year portal history per player (NOT filtered by destination)
    # -- needed to trace a multi-hop transfer (e.g. Alabama -> Florida State
    # -> Ohio State) back to their TRUE original school. A player's most
    # recent portal entry's "origin" is only their immediately-previous stop,
    # not necessarily where they were originally recruited -- their earliest
    # portal entry's origin is.
    #
    # Indexed BOTH by exact normalized name and by a suffix-stripped version,
    # because CFBD itself isn't consistent about suffix formatting across
    # different portal-year snapshots for the same person -- confirmed real
    # case: one year lists him as "Little II", another as "Little Jr." for
    # the same player. Exact-name matching alone would silently fail to link
    # these as the same person's history.
    SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

    def strip_suffix(name_norm):
        parts = [p for p in name_norm.split() if p.rstrip(".") not in SUFFIXES]
        return " ".join(parts)

    portal_history_by_name = {}
    portal_history_by_stripped_name = {}
    if needs_transfer_lookup:
        print(f"Fetching CFBD transfer portal data for new transfers...", file=sys.stderr)
        # 6 years covers a player's full realistic eligibility window (up to
        # a redshirt + 5 playing years) so multi-hop chains can be traced
        # back to their true origin regardless of how long ago they signed.
        for yr in range(CURRENT_YEAR, CURRENT_YEAR - 6, -1):
            try:
                portal = get_transfer_portal(yr)
                for name, info in portal.items():
                    portal_history_by_name.setdefault(name, []).append(info)
                    portal_history_by_stripped_name.setdefault(strip_suffix(name), []).append(info)
                    if info.get("destination") == team_name:
                        transfers_in[name] = info
            except Exception as e:
                print(f"  {yr} portal fetch failed: {e}", file=sys.stderr)
        print(f"  {len(transfers_in)} transfers in from CFBD", file=sys.stderr)
    else:
        print("No new transfers needing portal data -- skipping CFBD portal call this run.", file=sys.stderr)

    def true_origin_school(player_name_norm, fallback_match):
        """The origin of a transfer's EARLIEST portal entry -- their real
        original signing school, not just their most recent previous stop."""
        history = (portal_history_by_name.get(player_name_norm)
                   or portal_history_by_stripped_name.get(strip_suffix(player_name_norm)))
        if not history:
            return fallback_match["origin"] if fallback_match and fallback_match.get("origin") else None
        dated = [h for h in history if h.get("transferDate")]
        if not dated:
            return fallback_match["origin"] if fallback_match and fallback_match.get("origin") else None
        earliest = min(dated, key=lambda h: h["transferDate"])
        return earliest.get("origin") or (fallback_match.get("origin") if fallback_match else None)

    # Recruiting composite scores never change once assigned (they're
    # historical/fixed), so on a steady-state week where the roster hasn't
    # changed, there's no reason to re-fetch anything -- only query CFBD for
    # players who don't already have cached data from a previous run. This
    # keeps the free-tier calls/month budget sustainable across 68+ teams
    # updating twice a week; a full roster only costs real API calls once,
    # the first time each player appears.
    def already_has_recruit_data(row):
        prev = previous_by_norm_name.get(normalize_name(row["player"]))
        return prev is not None and prev.get("compositeScore") is not None

    # For each player needing recruit data, figure out which SCHOOL to query:
    # a transfer's own origin school (from the portal data above) if we have
    # it, otherwise fall back to the current team (works correctly for
    # non-transfers, and is the best guess available for a transfer whose
    # portal entry we couldn't find). Group by (school, year) and dedupe --
    # many transfers/recruits share both, so this stays cheap even though
    # we're now querying more than just one team.
    needed_school_years = set()
    for r in depth_chart:
        if already_has_recruit_data(r):
            continue
        yr = infer_recruiting_class_year(r["class"])
        if r["isTransfer"]:
            norm_name = normalize_name(r["player"])
            match = transfers_in.get(norm_name)
            school = true_origin_school(norm_name, match) or team_name
            if "little" in norm_name:
                print(f"DEBUG: norm_name={norm_name!r} match={match} school={school!r} yr={yr}", file=sys.stderr)
                print(f"DEBUG: exact history = {portal_history_by_name.get(norm_name)}", file=sys.stderr)
                print(f"DEBUG: stripped key = {strip_suffix(norm_name)!r}", file=sys.stderr)
                print(f"DEBUG: stripped history = {portal_history_by_stripped_name.get(strip_suffix(norm_name))}", file=sys.stderr)
        else:
            school = team_name
        needed_school_years.add((school, yr))

    recruiting_by_name = {}
    recruiting_by_last_name = {}
    if needed_school_years:
        print(f"Fetching CFBD recruiting data for {len(needed_school_years)} (school, year) pairs...",
              file=sys.stderr)
        for school, yr in sorted(needed_school_years):
            try:
                by_full, by_last = get_recruiting_players(school, yr)
                recruiting_by_name.update(by_full)
                # Only keep a last-name fallback entry if it's unambiguous across
                # ALL school/year combos merged too, not just within one.
                for last, info in by_last.items():
                    if last in recruiting_by_last_name and recruiting_by_last_name[last] != info:
                        recruiting_by_last_name[last] = None  # now ambiguous, drop it
                    elif last not in recruiting_by_last_name:
                        recruiting_by_last_name[last] = info
                print(f"  {school} {yr}: {len(by_full)} players", file=sys.stderr)
            except Exception as e:
                print(f"  {school} {yr}: failed ({e})", file=sys.stderr)
        recruiting_by_last_name = {k: v for k, v in recruiting_by_last_name.items() if v is not None}
    else:
        print("No new players needing recruiting data -- skipping CFBD recruiting call this run.", file=sys.stderr)

    output_rows = []
    for row in depth_chart:
        norm = normalize_name(row["player"])
        recruit_match = recruiting_by_name.get(norm)
        if not recruit_match:
            last = norm.split()[-1] if norm.split() else None
            if last:
                candidate = recruiting_by_last_name.get(last)
                if candidate:
                    site_bucket = site_position_bucket(row["position"])
                    cand_bucket = cfbd_position_bucket(candidate.get("position"))
                    if site_bucket and cand_bucket and site_bucket == cand_bucket:
                        recruit_match = candidate
                    # else: same last name, different role -- almost certainly
                    # a different person, don't risk a wrong match
        transfer_match = transfers_in.get(norm)
        prev_match = previous_by_norm_name.get(norm)

        out_row = {
            "position": row["position"],
            "player": row["player"],
            "jersey": row["jersey"],
            "class": row["class"],
            "isTransfer": row["isTransfer"],
            "compositeScore": None,   # HS recruiting rating
            "transferScore": None,    # transfer portal rating -- kept separate,
                                       # these are two different evaluations at
                                       # two different points in the player's career
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
            if transfer_match.get("rating") is not None:
                out_row["transferScore"] = round(transfer_match["rating"] * 100)
            out_row["transferRank"] = transfer_match.get("overallRank")
            out_row["transferPosRank"] = transfer_match.get("positionRank")

        # Fill any still-missing fields from last known-good data (e.g. walk-ons
        # with no CFBD recruiting profile at all). cfb27Rating/cfb27Dev are set
        # by a separate script (update_video_game_ratings.py) that doesn't run
        # every time this one does -- must always carry these forward or the
        # next depth-chart-only refresh silently erases them.
        if prev_match:
            for k in ("compositeScore", "transferScore", "profileUrl", "transferRank", "transferPosRank",
                      "hsNationalRank", "hsPositionRank", "hsStateRank", "pffGrade",
                      "pffPositionRank", "pffPositionTotal", "pffPositionLabel", "pffTied",
                      "cfb27Rating", "cfb27Dev"):
                if out_row.get(k) is None:
                    out_row[k] = prev_match.get(k)

        output_rows.append(out_row)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cfbd_fetched_this_run = bool(needed_school_years) or needs_transfer_lookup
    cfbd_updated_at = now_iso if cfbd_fetched_this_run else previous_metadata.get("cfbdUpdatedAt", now_iso)

    wrapped = {
        "generatedAt": now_iso,
        "ourladsUpdatedAt": now_iso,
        "cfbdUpdatedAt": cfbd_updated_at,
        "cfb27UpdatedAt": previous_metadata.get("cfb27UpdatedAt"),
        "pffUpdatedAt": previous_metadata.get("pffUpdatedAt"),
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
