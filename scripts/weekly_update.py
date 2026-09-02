"""
Runs weekly via GitHub Actions. Pulls the current season's ranking -- the
CFP committee's poll once it starts releasing (~week 10-13 each year), the
AP poll as a proxy before that -- plus current SP+ ratings and games played
so far, recomputes BRR for every currently ranked team, and replaces that
season's rows in brr_data.json -- leaving all other years untouched.

IMPORTANT CAVEAT (read this if something looks wrong after a run):
"Ranked win / ranked loss / bad loss" here are tagged using each opponent's
rank in the MOST RECENT ranking (committee poll if out, AP poll otherwise),
recomputed fresh every run -- not the opponent's rank at the time the game
was actually played. This means a win over a team that was ranked in
September but has since fallen out of the poll will stop counting as a
"ranked win" later in the season. This is a simplification made for a live
in-season display; the historical model (2014-2025) uses each opponent's
FINAL season rank instead, which is why in-season BRR numbers won't be
perfectly apples-to-apples with prior years until the season is complete
and final rankings are out.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("CFBD_API_KEY")
BASE = "https://api.collegefootballdata.com"
HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

DATA_FILE = "brr_data.json"

COEFS = dict(
    intercept=14.3946, sp=0.1799, rw=0.8549, spw=0.0514,
    bl=-1.3402, cl=0.5983, l=-2.9912,
)
CLOSE_GAME_MARGIN = 8


def get(endpoint, params=None):
    r = requests.get(f"{BASE}{endpoint}", headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def current_season_year():
    now = datetime.now(timezone.utc)
    # CFB season "year" = the year it started in (e.g. games in Jan 2027 are
    # still part of the "2026" season). Season kicks off in August.
    return now.year if now.month >= 7 else now.year - 1


def fetch_latest_poll(year, keyword):
    """Generic helper: find the most recent week that has a poll whose name
    contains `keyword`, and return its rankings."""
    data = get("/rankings", {"year": year, "seasonType": "regular"})
    weeks = [
        w for w in data
        if any(keyword in p.get("poll", "") for p in w.get("polls", []))
    ]
    if not weeks:
        return None, None
    latest = max(weeks, key=lambda w: w["week"])
    poll = next(p for p in latest["polls"] if keyword in p["poll"])
    ranks = {team["school"]: team["rank"] for team in poll["ranks"]}
    return ranks, latest["week"]


def fetch_latest_ranking(year):
    """Prefer the official CFP committee ranking once it starts releasing
    each season; fall back to the AP poll before that. Returns
    (ranks, week, source_label)."""
    ranks, week = fetch_latest_poll(year, "Playoff Committee")
    if ranks:
        return ranks, week, "committee"
    ranks, week = fetch_latest_poll(year, "AP")
    if ranks:
        return ranks, week, "AP"
    return None, None, None


def fetch_sp_ratings(year):
    data = get("/ratings/sp", {"year": year})
    return {t["team"]: t.get("rating") for t in data}


def fetch_records(year):
    data = get("/records", {"year": year})
    return {t["team"]: t.get("conference") for t in data}


def fetch_games(year):
    return get("/games", {"year": year, "seasonType": "regular", "division": "fbs"})


def compute_features(year, ranks, sp_ratings, games):
    per_team = {}

    def bucket(team):
        if team not in per_team:
            per_team[team] = dict(w=0, l=0, rw=0, rl=0, bl=0, cl=0, spw=0.0)
        return per_team[team]

    for g in games:
        if g.get("homePoints") is None or g.get("awayPoints") is None:
            continue
        home, away = g["homeTeam"], g["awayTeam"]
        hp, ap = g["homePoints"], g["awayPoints"]
        margin = hp - ap

        for team, opp, m in [(home, away, margin), (away, home, -margin)]:
            b = bucket(team)
            win = m > 0
            close = abs(m) <= CLOSE_GAME_MARGIN
            opp_rank = ranks.get(opp)
            opp_sp = sp_ratings.get(opp, 0) or 0
            if win:
                b["w"] += 1
                b["spw"] += opp_sp
                if opp_rank:
                    b["rw"] += 1
            else:
                b["l"] += 1
                if opp_rank:
                    b["rl"] += 1
                else:
                    b["bl"] += 1
                if close:
                    b["cl"] += 1

    return per_team


def brr_score(sp, rw, spw, bl, cl, l):
    return (COEFS["intercept"] + COEFS["sp"] * sp + COEFS["rw"] * rw
            + COEFS["spw"] * spw + COEFS["bl"] * bl + COEFS["cl"] * cl
            + COEFS["l"] * l)


def main():
    if not API_KEY:
        print("ERROR: CFBD_API_KEY not set. Add it as a repo secret.", file=sys.stderr)
        sys.exit(1)

    year = current_season_year()
    print(f"Updating BRR for season {year}...")

    ranks, week, source = fetch_latest_ranking(year)
    if ranks is None:
        print(f"No ranking found yet for {year} -- likely too early in the season. Skipping update.")
        return
    print(f"Latest ranking: {source} poll, week {week}, {len(ranks)} ranked teams")

    sp_ratings = fetch_sp_ratings(year)
    conferences = fetch_records(year)
    games = fetch_games(year)
    print(f"Pulled {len(games)} games, {len(sp_ratings)} SP+ ratings")

    features = compute_features(year, ranks, sp_ratings, games)

    rows = []
    for team, rank in ranks.items():
        f = features.get(team, dict(w=0, l=0, rw=0, rl=0, bl=0, cl=0, spw=0.0))
        sp = sp_ratings.get(team, 0) or 0
        score = brr_score(sp, f["rw"], f["spw"], f["bl"], f["cl"], f["l"])
        rows.append({
            "year": year, "rank": rank, "team": team,
            "conf": conferences.get(team, "Unknown"),
            "sp": round(sp, 1), "rw": f["rw"], "spw": round(f["spw"], 1),
            "bl": f["bl"], "cl": f["cl"], "l": f["l"], "w": f["w"],
            "score": round(score, 2), "rankSource": source,
        })

    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, start=1):
        r["brrRank"] = i
        r["diff"] = r["brrRank"] - r["rank"]

    try:
        with open(DATA_FILE) as f:
            existing_data = json.load(f)
        existing = existing_data.get("rows", []) if isinstance(existing_data, dict) else existing_data
    except FileNotFoundError:
        existing = []

    existing = [r for r in existing if r["year"] != year]
    existing.extend(rows)

    # Wrapped in an object with a generation timestamp -- not a bare array
    # -- so the front end can show an accurate "data last refreshed at"
    # time instead of just describing the schedule in prose.
    with open(DATA_FILE, "w") as f:
        json.dump({
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "rows": existing,
        }, f, separators=(",", ":"))

    print(f"Wrote {len(rows)} rows for {year} (week {week}). Total rows in file: {len(existing)}")


if __name__ == "__main__":
    main()

