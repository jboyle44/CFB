"""
Runs weekly via GitHub Actions (see .github/workflows/update_lines_nfl.yml).

The NFL counterpart to scripts/weekly_lines_update.py. Same DFI model, same
grading logic, different data sources:
  - games, market spreads, and final scores from the-odds-api.com (CFBD has
    no NFL coverage, so this uses a different provider)
  - MPG's NFL power ratings (https://mpg000f.github.io/cbb_power_rating/#nfl)

FREEZING: a game's model line, vegas line, edge, and pick are locked in as
soon as its kickoff time passes -- not just once it's graded. This matters
because grading depends on the-odds-api.com's free /scores endpoint, which
only looks back 3 days; if a run is ever missed and a game's score rolls
off that window before we catch it, this still guarantees its pre-game
line/pick snapshot never gets silently recomputed with whatever ratings or
market line happen to be current on a later run. Only fields filled in
after kickoff (score, status, atsResult, modelCorrect) are still writable
once a game is underway or done -- the pick itself is locked.

KNOWN LIMITATIONS (free-tier the-odds-api.com, unlike the CFBD-backed CFB
script):
  - /scores only returns games completed in the last 3 days. If this script
    doesn't run for more than ~3 days during the season, any games that
    finished and rolled off that window before the next run will never get
    graded -- there's no historical backfill on the free tier. Practically,
    running twice a week comfortably covers every slate.
  - the-odds-api.com doesn't label games as neutral-site (e.g. international
    games), so NEUTRAL_SITE_GAMES below is a manually maintained list of the
    2026 International Series games -- HFA is skipped for those. This list
    needs updating every season.
  - There's no "week number" in the API response, so week is computed from
    the game's date relative to the season's Week 1 start (see
    NFL_WEEK1_START below). This needs updating each season.
  - MPG's NFL ratings don't have a per-week snapshot file (yet) the way CFB
    does, so every week uses the same season-level ratings file until/unless
    MPG adds one -- but we snapshot it ourselves into ratings_history_nfl.json
    each run, same as the CFB script, so week-over-week history exists
    regardless of what MPG's own site shows.

MODEL: identical to the CFB script.
  model_spread = (home_rating - away_rating) + HFA   (HFA = +2.0 for NFL)
  edge = model_spread - vegas_spread
  pick = home team if edge > 0, away team if edge < 0
"""

import os
import sys
import json
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("ODDS_API_KEY")
BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"

MPG_BASE = "https://mpg000f.github.io/cbb_power_rating"

DATA_FILE = "lines_data_nfl.json"
RATINGS_HISTORY_FILE = "ratings_history_nfl.json"
HFA = 2.0
SEASON = 2026

# Week 1 of the 2026 NFL regular season starts Wednesday, Sept 9, 2026.
# Update this each season -- there's no reliable way to derive it from the
# API response.
NFL_WEEK1_START = datetime(2026, 9, 9, tzinfo=timezone.utc)
MAX_WEEK = 18

# MPG keys NFL teams by abbreviation; the-odds-api.com uses full team names.
# "LA" is the Rams -- the Chargers are always "LAC" in MPG's data.
ABBR_TO_NAME = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}
NAME_TO_ABBR = {v: k for k, v in ABBR_TO_NAME.items()}


# 2026 NFL International Series -- these are neutral-site games, so home
# field advantage shouldn't apply. the-odds-api.com doesn't flag this, so
# it's tracked manually here. Matched by (home_team, away_team, week) as
# confirmed against real API responses -- update this each season.
NEUTRAL_SITE_GAMES = {
    ("Los Angeles Rams", "San Francisco 49ers", 1),      # Melbourne, Australia
    ("Dallas Cowboys", "Baltimore Ravens", 3),           # Rio de Janeiro, Brazil
    ("Washington Commanders", "Indianapolis Colts", 4),  # London (Tottenham)
    ("Jacksonville Jaguars", "Philadelphia Eagles", 5),  # London (Tottenham)
    ("Jacksonville Jaguars", "Houston Texans", 6),       # London (Wembley)
    ("New Orleans Saints", "Pittsburgh Steelers", 7),    # Paris, France
    ("Atlanta Falcons", "Cincinnati Bengals", 9),        # Madrid, Spain
    ("Detroit Lions", "New England Patriots", 10),       # Munich, Germany
    ("San Francisco 49ers", "Minnesota Vikings", 11),    # Mexico City, Mexico
}

# Standard NFL conference/division alignment (stable year to year barring
# realignment). Used for the Results & Trends AFC/NFC and division
# breakdowns -- NFL has no equivalent of CFB's P4/G6 or conference concept,
# so this replaces both.
DIVISION_BY_ABBR = {
    "BUF": "AFC East", "MIA": "AFC East", "NE": "AFC East", "NYJ": "AFC East",
    "BAL": "AFC North", "CIN": "AFC North", "CLE": "AFC North", "PIT": "AFC North",
    "HOU": "AFC South", "IND": "AFC South", "JAX": "AFC South", "TEN": "AFC South",
    "DEN": "AFC West", "KC": "AFC West", "LV": "AFC West", "LAC": "AFC West",
    "DAL": "NFC East", "NYG": "NFC East", "PHI": "NFC East", "WAS": "NFC East",
    "CHI": "NFC North", "DET": "NFC North", "GB": "NFC North", "MIN": "NFC North",
    "ATL": "NFC South", "CAR": "NFC South", "NO": "NFC South", "TB": "NFC South",
    "ARI": "NFC West", "LA": "NFC West", "SF": "NFC West", "SEA": "NFC West",
}


def get(url, params=None):
    p = dict(params or {})
    p["apiKey"] = API_KEY
    r = requests.get(url, params=p, timeout=30)
    r.raise_for_status()
    return r.json()


def week_for(commence_time_iso):
    dt = datetime.fromisoformat(commence_time_iso.replace("Z", "+00:00"))
    delta_days = (dt - NFL_WEEK1_START).days
    if delta_days < 0:
        return 0  # preseason
    return min(delta_days // 7 + 1, MAX_WEEK)


def fetch_mpg_ratings():
    """NFL doesn't have a per-week snapshot file on MPG's site yet (unlike
    CFB), so this always uses the season-level ratings file. Returns
    (ratings_by_abbr, full_rows, source_label)."""
    try:
        r = requests.get(f"{MPG_BASE}/data/nfl/ratings_{SEASON}.json", timeout=30)
        r.raise_for_status()
        data = r.json()
        rows = data["ratings"]
        ratings = {row["team"]: row["rating"] for row in rows}
        return ratings, rows, f"season file (last updated {data.get('lastUpdated', '?')})"
    except Exception as e:
        print(f"  WARNING: couldn't load MPG NFL ratings: {e}", file=sys.stderr)
        return {}, [], None


def fetch_odds():
    """Upcoming/live NFL games with spreads. Doesn't include completed games."""
    games = get(f"{BASE}/sports/{SPORT}/odds", {"regions": "us", "markets": "spreads", "oddsFormat": "american"})
    return games


def fetch_scores():
    """Games from the last 3 days, with final scores where completed. Free
    tier caps daysFrom at 3."""
    return get(f"{BASE}/sports/{SPORT}/scores", {"daysFrom": 3})


def best_spread_for_home(game):
    """Pull the home team's signed spread from the first bookmaker that has
    one. the-odds-api.com already gives a signed number per team (negative =
    favorite), so no text parsing needed -- just negate to match our
    home-perspective convention (positive = home favored)."""
    home = game.get("home_team")
    for bm in game.get("bookmakers", []):
        for market in bm.get("markets", []):
            if market.get("key") != "spreads":
                continue
            for outcome in market.get("outcomes", []):
                if outcome.get("name") == home and outcome.get("point") is not None:
                    return -outcome["point"], bm.get("title")
    return None, None


def grade(home_score, away_score, vegas_spread):
    if home_score is None or away_score is None or vegas_spread is None:
        return None, None
    actual_margin = home_score - away_score
    diff = actual_margin - vegas_spread
    if abs(diff) < 1e-9:
        return "push", actual_margin
    return ("home_cover" if diff > 0 else "away_cover"), actual_margin


def build_record(game, ratings_by_abbr, ratings_source, existing_by_id, home_spread, provider):
    gid = game["id"]
    home_name, away_name = game["home_team"], game["away_team"]
    home_abbr = NAME_TO_ABBR.get(home_name)
    away_abbr = NAME_TO_ABBR.get(away_name)
    week = week_for(game["commence_time"])

    home_rating = ratings_by_abbr.get(home_abbr) if home_abbr else None
    away_rating = ratings_by_abbr.get(away_abbr) if away_abbr else None

    neutral = (home_name, away_name, week) in NEUTRAL_SITE_GAMES
    home_hfa = 0 if neutral else HFA

    model_spread = None
    if home_rating is not None and away_rating is not None:
        model_spread = round((home_rating - away_rating) + home_hfa, 1)

    edge = pick = pick_margin = None
    if model_spread is not None and home_spread is not None:
        edge = round(model_spread - home_spread, 1)
        if edge > 0:
            pick = home_name
        elif edge < 0:
            pick = away_name
        pick_margin = abs(edge)

    home_division = DIVISION_BY_ABBR.get(home_abbr)
    away_division = DIVISION_BY_ABBR.get(away_abbr)

    return {
        "gameId": gid,
        "season": SEASON,
        "week": week,
        "startDate": game["commence_time"],
        "neutralSite": neutral,
        "homeTeam": home_name,
        "awayTeam": away_name,
        "homeAbbr": home_abbr,
        "awayAbbr": away_abbr,
        "homeConference": home_division.split(" ")[0] if home_division else None,  # "AFC"/"NFC"
        "awayConference": away_division.split(" ")[0] if away_division else None,
        "homeDivision": home_division,   # e.g. "AFC East"
        "awayDivision": away_division,
        "homeRating": home_rating,
        "awayRating": away_rating,
        "ratingsSource": ratings_source,
        "modelSpread": model_spread,
        "vegasSpread": home_spread,
        "vegasProvider": provider,
        "edge": edge,
        "pick": pick,
        "pickMargin": pick_margin,
        "status": "scheduled",
        "homeScore": None,
        "awayScore": None,
        "actualMargin": None,
        "atsResult": None,
        "modelCorrect": None,
    }


def main():
    if not API_KEY:
        print("ERROR: ODDS_API_KEY not set. Add it as a repo secret.", file=sys.stderr)
        sys.exit(1)

    print(f"Updating NFL DFI lines/picks for season {SEASON}...")

    try:
        with open(DATA_FILE) as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = []
    existing_by_id = {r["gameId"]: r for r in existing}

    ratings_by_abbr, ratings_rows, ratings_source = fetch_mpg_ratings()
    print(f"  {len(ratings_by_abbr)} teams rated ({ratings_source})")

    # 1. Upcoming/live games + current lines -- refresh line/pick for any
    #    game whose kickoff hasn't happened yet. Once kickoff passes, the
    #    line/pick is frozen even if we haven't graded it yet (see the
    #    FREEZING note at the top of this file).
    try:
        odds_games = fetch_odds()
    except requests.HTTPError as e:
        print(f"  odds request failed: {e}")
        odds_games = []
    print(f"  {len(odds_games)} upcoming/live games with odds")

    now = datetime.now(timezone.utc)
    for g in odds_games:
        gid = g["id"]
        prior = existing_by_id.get(gid)
        if prior and prior.get("status") == "final":
            continue  # already graded and frozen
        commence = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
        if prior and commence <= now:
            continue  # kickoff has passed -- freeze the pre-game snapshot even if not graded yet
        home_spread, provider = best_spread_for_home(g)
        record = build_record(g, ratings_by_abbr, ratings_source, existing_by_id, home_spread, provider)
        existing_by_id[gid] = record

    # 2. Recently completed games (last 3 days) -- fill in scores and grade.
    try:
        recent = fetch_scores()
    except requests.HTTPError as e:
        print(f"  scores request failed: {e}")
        recent = []
    completed = [g for g in recent if g.get("completed")]
    print(f"  {len(completed)} completed games in the last 3 days")

    for g in completed:
        gid = g["id"]
        record = existing_by_id.get(gid)
        if record is None:
            # A completed game we never saw on the /odds endpoint (e.g. line
            # never posted, or it fell outside our polling window). Build a
            # minimal record so it's at least visible, even if ungraded.
            home_spread, provider = None, None
            record = build_record(g, ratings_by_abbr, ratings_source, existing_by_id, home_spread, provider)
        if record.get("status") == "final" and record.get("atsResult") is not None:
            continue  # already graded and frozen

        scores = {s["name"]: s.get("score") for s in (g.get("scores") or [])}
        home_score = scores.get(record["homeTeam"])
        away_score = scores.get(record["awayTeam"])
        record["homeScore"] = int(home_score) if home_score is not None else None
        record["awayScore"] = int(away_score) if away_score is not None else None
        record["status"] = "final"

        ats_result, actual_margin = grade(record["homeScore"], record["awayScore"], record["vegasSpread"])
        record["actualMargin"] = actual_margin
        record["atsResult"] = ats_result
        if ats_result == "push" or record["pick"] is None:
            record["modelCorrect"] = None
        else:
            picked_home = record["pick"] == record["homeTeam"]
            record["modelCorrect"] = (picked_home and ats_result == "home_cover") or \
                                      (not picked_home and ats_result == "away_cover")
        existing_by_id[gid] = record

    all_rows = sorted(existing_by_id.values(), key=lambda r: (r["season"], r["week"], r.get("startDate") or ""))
    with open(DATA_FILE, "w") as f:
        json.dump({
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "games": all_rows,
        }, f, separators=(",", ":"))

    # Snapshot the full ratings grid for this week, independent of MPG's own
    # site (it doesn't keep week-over-week history, and doesn't even have a
    # per-week file for NFL yet). Overwritten each run with whatever's
    # current, so a week's snapshot upgrades automatically once MPG
    # eventually publishes real weekly files.
    if ratings_rows:
        try:
            with open(RATINGS_HISTORY_FILE) as f:
                history = json.load(f)
        except FileNotFoundError:
            history = []
        current_week = week_for(datetime.now(timezone.utc).isoformat())
        history = [h for h in history if h.get("week") != current_week]
        history.append({
            "season": SEASON,
            "week": current_week,
            "source": ratings_source,
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "teams": [
                {"rank": r.get("rank"), "team": r.get("team"), "rating": r.get("rating"),
                 "adjOffEpa": r.get("adjOffEpa"), "adjDefEpa": r.get("adjDefEpa"), "games": r.get("games")}
                for r in ratings_rows
            ],
        })
        history.sort(key=lambda h: h["week"])
        with open(RATINGS_HISTORY_FILE, "w") as f:
            json.dump(history, f, separators=(",", ":"))

    graded = [r for r in all_rows if r.get("modelCorrect") is not None]
    correct = sum(1 for r in graded if r["modelCorrect"])
    print(f"Wrote {len(all_rows)} game rows to {DATA_FILE}.")
    if ratings_rows:
        print(f"Wrote ratings snapshot for week {current_week} to {RATINGS_HISTORY_FILE}.")
    print(f"Graded so far this season: {correct}-{len(graded) - correct} ATS.")


if __name__ == "__main__":
    main()
