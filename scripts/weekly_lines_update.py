"""
Runs weekly via GitHub Actions (see .github/workflows/update_lines.yml).

For every regular-season FBS week of the current season, pulls:
  - games + final scores from CollegeFootballData (CFBD)
  - the closing/current market spread for each game from CFBD's /lines
  - MPG's power ratings (https://mpg000f.github.io/cbb_power_rating/#cfb),
    using that week's snapshot if MPG has published one yet, otherwise the
    latest season-level ratings file as an approximation

...and computes the model's projected spread and its pick against the
market spread for every game. Results are merged into lines_data.json,
keyed by CFBD gameId, so re-running this script is always safe:
  - games with no final score yet get their model line / vegas line / pick
    refreshed (since lines can move week to week and ratings update)
  - games that already have a final score AND were already graded are left
    alone, so we don't rewrite history when a stale re-run happens
  - games that just got a final score for the first time get graded

FBS-vs-FCS games are dropped entirely -- MPG doesn't rate FCS teams, so
there's no basis for a model spread against one. CFBD's own homeClassification
/awayClassification fields are used to filter these out (the `division=fbs`
query param only guarantees one side is FBS, not both).

It also snapshots MPG's full ratings grid (every FBS team, not just teams
playing that week) into ratings_history.json, one entry per season+week --
MPG's own site doesn't keep week-over-week history for the current season,
so this is our own independent record of it.

MODEL:
  model_spread = (home_rating - away_rating) + HFA
  HFA = +3.0 for the home team, 0 on a neutral site
  (positive model_spread means the home team is favored)

  vegas_spread is stored on the same home-team-perspective scale (positive
  = home favored), derived from CFBD's formattedSpread text so we don't
  have to guess the sign convention of the raw "spread" field.

  edge = model_spread - vegas_spread
  pick = home team if edge > 0 (model thinks home beats the number),
         away team if edge < 0

Only CFB (FBS) -- no NFL.
"""

import os
import re
import sys
import json
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("CFBD_API_KEY")
BASE = "https://api.collegefootballdata.com"
HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

MPG_BASE = "https://mpg000f.github.io/cbb_power_rating"

DATA_FILE = "lines_data.json"
RATINGS_HISTORY_FILE = "ratings_history.json"
HFA = 3.0
MAX_REGULAR_WEEK = 16
# Prefer these providers in order when a game has lines from more than one.
PROVIDER_PRIORITY = ["consensus", "DraftKings", "Bovada", "ESPN Bet", "Caesars"]


def get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def cfbd(endpoint, params=None):
    return get(f"{BASE}{endpoint}", params)


def current_season_year():
    now = datetime.now(timezone.utc)
    # CFB season "year" = the year it started in.
    return now.year if now.month >= 7 else now.year - 1


def fetch_mpg_ratings(year, week):
    """Try the week-specific MPG snapshot first, then fall back to the
    current season-level file. Returns (ratings_by_team, full_rows,
    source_label) -- full_rows is the raw list of team rating dicts, kept
    so we can snapshot the whole grid into ratings_history.json even
    though build_record() only needs the team->rating lookup."""
    try:
        data = get(f"{MPG_BASE}/data/cfb/weekly/{year}/week_{week:02d}.json")
        rows = data["ratings"]
        ratings = {r["team"]: r["rating"] for r in rows}
        return ratings, rows, f"weekly snapshot (week {week})"
    except Exception:
        pass
    try:
        data = get(f"{MPG_BASE}/data/cfb/ratings_{year}.json")
        rows = data["ratings"]
        ratings = {r["team"]: r["rating"] for r in rows}
        return ratings, rows, f"season file (last updated {data.get('lastUpdated', '?')})"
    except Exception as e:
        print(f"  WARNING: couldn't load MPG ratings for week {week}: {e}", file=sys.stderr)
        return {}, [], None


SPREAD_RE = re.compile(r"^(.*?)\s*([+-]?\d+(?:\.\d+)?)\s*$")


def vegas_home_spread(line_entry, home_team, away_team):
    """Parse a CFBD line's formattedSpread (e.g. 'Ohio State -6.5') into a
    home-team-perspective spread where positive = home favored. Returns
    None if the line can't be parsed (e.g. no line posted yet)."""
    fs = (line_entry or {}).get("formattedSpread")
    if not fs:
        return None
    fs = fs.strip()
    if fs.lower() in ("pick", "pick'em", "even", "pk"):
        return 0.0
    m = SPREAD_RE.match(fs)
    if not m:
        return None
    team_str, num_str = m.group(1).strip(), m.group(2)
    try:
        num = float(num_str)
    except ValueError:
        return None
    if team_str == home_team:
        return -num
    if team_str == away_team:
        return num
    # Team name in the line didn't match either side exactly (mascot/short
    # name mismatch) -- try a loose contains check both ways.
    if team_str in home_team or home_team in team_str:
        return -num
    if team_str in away_team or away_team in team_str:
        return num
    return None


def pick_best_line(lines):
    if not lines:
        return None
    by_provider = {l.get("provider"): l for l in lines if l.get("formattedSpread")}
    for provider in PROVIDER_PRIORITY:
        if provider in by_provider:
            return by_provider[provider]
    for l in lines:
        if l.get("formattedSpread"):
            return l
    return None


def fetch_week_lines(year, week):
    games = cfbd("/lines", {"year": year, "week": week, "seasonType": "regular"})
    return {g["id"]: g for g in games}


def fetch_week_games(year, week):
    games = cfbd("/games", {"year": year, "week": week, "seasonType": "regular", "division": "fbs"})
    # division=fbs only guarantees at least one side is FBS -- an FBS team's
    # game against an FCS opponent still comes back. MPG doesn't rate FCS
    # teams, so there's no model spread to compute for those; drop them here
    # rather than silently carrying a null-rating record downstream.
    fbs_games = [
        g for g in games
        if (g.get("homeClassification") or "fbs").lower() == "fbs"
        and (g.get("awayClassification") or "fbs").lower() == "fbs"
    ]
    dropped = len(games) - len(fbs_games)
    if dropped:
        print(f"    (dropped {dropped} FBS-vs-FCS game{'s' if dropped != 1 else ''} for week {week})")
    return fbs_games


def grade(home_score, away_score, vegas_spread):
    """ATS grading from the home team's perspective. vegas_spread positive
    = home favored (same convention as everywhere else in this file)."""
    if home_score is None or away_score is None or vegas_spread is None:
        return None, None
    actual_margin = home_score - away_score
    diff = actual_margin - vegas_spread
    if abs(diff) < 1e-9:
        return "push", actual_margin
    return ("home_cover" if diff > 0 else "away_cover"), actual_margin


def build_record(game, ratings_by_team, ratings_source, existing_by_id):
    gid = game["id"]
    home, away = game["homeTeam"], game["awayTeam"]
    prior = existing_by_id.get(gid)

    home_score = game.get("homePoints")
    away_score = game.get("awayPoints")
    is_final = home_score is not None and away_score is not None

    # Once a game has been graded, freeze the line/pick/model fields --
    # only fill in / confirm the final score and grade.
    if prior and prior.get("status") == "final":
        prior["homeScore"] = home_score
        prior["awayScore"] = away_score
        return prior

    # Also freeze at kickoff even if we haven't graded it yet -- CFBD
    # sometimes lags in posting a final score, and without this a game that
    # already started would keep recomputing its model line against
    # updated ratings on every run until the score finally lands. This
    # mirrors the NFL script's identical protection.
    start_date = game.get("startDate")
    started = False
    if start_date:
        try:
            commence = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            started = commence <= datetime.now(timezone.utc)
        except ValueError:
            pass
    if prior and started:
        prior["homeScore"] = home_score
        prior["awayScore"] = away_score
        if is_final:
            prior["status"] = "final"
        return prior

    home_rating = ratings_by_team.get(home)
    away_rating = ratings_by_team.get(away)
    neutral = bool(game.get("neutralSite"))

    model_spread = None
    if home_rating is not None and away_rating is not None:
        model_spread = round((home_rating - away_rating) + (0 if neutral else HFA), 1)

    return {
        "gameId": gid,
        "season": game["season"],
        "week": game["week"],
        "startDate": game.get("startDate"),
        "neutralSite": neutral,
        "homeTeam": home,
        "awayTeam": away,
        "homeConference": game.get("homeConference"),
        "awayConference": game.get("awayConference"),
        "homeRating": home_rating,
        "awayRating": away_rating,
        "ratingsSource": ratings_source,
        "modelSpread": model_spread,
        "vegasSpread": None,
        "vegasProvider": None,
        "edge": None,
        "pick": None,
        "pickMargin": None,
        "status": "final" if is_final else "scheduled",
        "homeScore": home_score,
        "awayScore": away_score,
        "actualMargin": None,
        "atsResult": None,
        "modelCorrect": None,
    }


def apply_line_and_grade(record, line_game):
    if record["status"] == "final" and record.get("atsResult") is not None:
        return record  # already fully graded and frozen

    # Same kickoff freeze as build_record, but for the vegas line/edge/pick
    # specifically: apply_line_and_grade runs on every record regardless of
    # whether build_record just froze it, so without this the line could
    # keep drifting after kickoff even though the model spread is already
    # locked. Only skip if we've actually captured a line already -- if
    # kickoff passed before any line was ever posted, still take this one
    # grab so we're not left with nothing.
    started = False
    if record.get("startDate"):
        try:
            commence = datetime.fromisoformat(record["startDate"].replace("Z", "+00:00"))
            started = commence <= datetime.now(timezone.utc)
        except ValueError:
            pass
    if started and record.get("vegasSpread") is not None:
        return record

    best = pick_best_line((line_game or {}).get("lines", []))
    vegas = vegas_home_spread(best, record["homeTeam"], record["awayTeam"]) if best else None

    if vegas is not None:
        record["vegasSpread"] = vegas
        record["vegasProvider"] = best.get("provider")
        if record["modelSpread"] is not None:
            edge = round(record["modelSpread"] - vegas, 1)
            record["edge"] = edge
            if edge > 0:
                record["pick"] = record["homeTeam"]
            elif edge < 0:
                record["pick"] = record["awayTeam"]
            else:
                record["pick"] = None  # dead-even, no lean
            record["pickMargin"] = abs(edge)

    if record["status"] == "final":
        ats_result, actual_margin = grade(record["homeScore"], record["awayScore"], record["vegasSpread"])
        record["actualMargin"] = actual_margin
        record["atsResult"] = ats_result
        if ats_result == "push" or record["pick"] is None:
            record["modelCorrect"] = None
        else:
            picked_home = record["pick"] == record["homeTeam"]
            record["modelCorrect"] = (picked_home and ats_result == "home_cover") or \
                                      (not picked_home and ats_result == "away_cover")

    return record


def main():
    if not API_KEY:
        print("ERROR: CFBD_API_KEY not set. Add it as a repo secret.", file=sys.stderr)
        sys.exit(1)

    year = current_season_year()
    print(f"Updating CFB lines/picks for season {year}...")

    try:
        with open(DATA_FILE) as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = []
    existing_by_id = {r["gameId"]: r for r in existing if r.get("season") == year}
    kept_other_years = [r for r in existing if r.get("season") != year]

    try:
        with open(RATINGS_HISTORY_FILE) as f:
            existing_history = json.load(f)
    except FileNotFoundError:
        existing_history = []
    history_by_week = {(h["season"], h["week"]): h for h in existing_history if h.get("season") == year}
    kept_other_years_history = [h for h in existing_history if h.get("season") != year]

    captured_at = datetime.now(timezone.utc).isoformat()
    updated = {}
    for week in range(1, MAX_REGULAR_WEEK + 1):
        try:
            games = fetch_week_games(year, week)
        except requests.HTTPError as e:
            print(f"  Week {week}: games request failed ({e}), stopping.")
            break
        if not games:
            print(f"  Week {week}: no games scheduled yet, stopping scan.")
            break

        ratings_by_team, ratings_rows, ratings_source = fetch_mpg_ratings(year, week)
        try:
            line_games = fetch_week_lines(year, week)
        except requests.HTTPError as e:
            print(f"  Week {week}: lines request failed ({e}), continuing without lines.")
            line_games = {}

        week_final = sum(1 for g in games if g.get("homePoints") is not None)
        print(f"  Week {week}: {len(games)} games, {week_final} final, "
              f"{len(ratings_by_team)} teams rated ({ratings_source}), {len(line_games)} with lines")

        dropped_no_rating = 0
        for g in games:
            record = build_record(g, ratings_by_team, ratings_source, existing_by_id)
            record = apply_line_and_grade(record, line_games.get(g["id"]))
            # Belt-and-suspenders on top of the classification filter in
            # fetch_week_games(): a team can be tagged 'fbs' by CFBD (e.g.
            # mid-transition programs like Sacramento State or North Dakota
            # State) while MPG still has no rating history for it. No
            # rating on either side means no basis for a model spread, so
            # drop the game entirely rather than carrying nulls through.
            if record.get("homeRating") is None or record.get("awayRating") is None:
                dropped_no_rating += 1
                continue
            updated[g["id"]] = record
        if dropped_no_rating:
            print(f"    (dropped {dropped_no_rating} game{'s' if dropped_no_rating != 1 else ''} "
                  f"with no MPG rating on one side for week {week})")

        # Snapshot the full ratings grid for this week, independent of MPG's
        # own site (it doesn't keep week-over-week history for the current
        # season). Overwritten each run with whatever's best available, so
        # a week's snapshot upgrades automatically if MPG later publishes a
        # proper weekly file for it.
        if ratings_rows:
            history_by_week[(year, week)] = {
                "season": year,
                "week": week,
                "source": ratings_source,
                "capturedAt": captured_at,
                "teams": [
                    {
                        "rank": r.get("rank"),
                        "team": r.get("team"),
                        "rating": r.get("rating"),
                        "adjO": r.get("adjO"),
                        "adjD": r.get("adjD"),
                        "record": r.get("record"),
                        "games": r.get("games"),
                    }
                    for r in ratings_rows
                ],
            }

    all_rows = kept_other_years + list(updated.values())
    all_rows.sort(key=lambda r: (r["season"], r["week"], r.get("startDate") or ""))

    with open(DATA_FILE, "w") as f:
        json.dump(all_rows, f, separators=(",", ":"))

    all_history = kept_other_years_history + list(history_by_week.values())
    all_history.sort(key=lambda h: (h["season"], h["week"]))

    with open(RATINGS_HISTORY_FILE, "w") as f:
        json.dump(all_history, f, separators=(",", ":"))

    graded = [r for r in updated.values() if r.get("modelCorrect") is not None]
    correct = sum(1 for r in graded if r["modelCorrect"])
    print(f"Wrote {len(all_rows)} game rows ({len(updated)} for {year}) to {DATA_FILE}.")
    print(f"Wrote {len(all_history)} weekly ratings snapshots ({len(history_by_week)} for {year}) to {RATINGS_HISTORY_FILE}.")
    print(f"Graded so far this season: {correct}-{len(graded) - correct} ATS.")


if __name__ == "__main__":
    main()
