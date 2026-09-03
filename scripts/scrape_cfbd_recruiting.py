"""
Replaces the 247Sports scraper entirely. Uses CollegeFootballData.com's real,
authenticated API instead of scraping 247Sports' rendered pages -- no bot
detection risk since this is a proper API call, not a scrape. Requires the
CFBD_API_KEY environment variable (already set as a repo secret for the BRR
model's SP+ ratings).

Two endpoints:
  GET /recruiting/players  -- high school composite recruiting data
                               (stars, rating, national ranking)
  GET /player/portal       -- transfer portal data (stars, rating, origin/dest)
"""
import os
import requests

BASE_URL = "https://api.collegefootballdata.com"


def _auth_headers():
    api_key = os.environ.get("CFBD_API_KEY")
    if not api_key:
        raise RuntimeError("CFBD_API_KEY environment variable not set")
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


def get_recruiting_players(team_display_name, year):
    """
    Returns {player_name_lower: {"stars": int, "rating": float, "ranking": int}}
    for a team's high-school recruiting class in a given year. Call once per
    relevant recruiting class year and merge results if you need multiple
    classes (current roster spans several recruiting years).
    """
    resp = requests.get(
        f"{BASE_URL}/recruiting/players",
        headers=_auth_headers(),
        params={"year": year, "team": team_display_name},
        timeout=20,
    )
    resp.raise_for_status()
    out = {}
    for r in resp.json():
        name = (r.get("name") or "").strip().lower()
        if not name:
            continue
        out[name] = {
            "stars": r.get("stars"),
            "rating": r.get("rating"),
            "ranking": r.get("ranking"),
            "position": r.get("position"),
        }
    return out


def get_transfer_portal(year):
    """
    Returns a list of every transfer portal entry for a season, each with
    first_name/last_name/position/origin/destination/rating/stars. Ranking
    isn't provided directly -- sort by rating descending and enumerate to get
    an equivalent "#N transfer overall" and "#N at position" the same way
    247Sports displays it.
    """
    resp = requests.get(
        f"{BASE_URL}/player/portal",
        headers=_auth_headers(),
        params={"year": year},
        timeout=20,
    )
    resp.raise_for_status()
    entries = resp.json()

    # Compute overall rank (by rating, descending) and position rank.
    graded = [e for e in entries if e.get("rating") is not None]
    graded.sort(key=lambda e: e["rating"], reverse=True)
    for i, e in enumerate(graded, start=1):
        e["_overall_rank"] = i

    by_position = {}
    for e in graded:
        by_position.setdefault(e.get("position"), []).append(e)
    for pos, group in by_position.items():
        group.sort(key=lambda e: e["rating"], reverse=True)
        for i, e in enumerate(group, start=1):
            e["_position_rank"] = i

    out = {}
    for e in entries:
        full_name = f"{e.get('first_name','')} {e.get('last_name','')}".strip().lower()
        if not full_name:
            continue
        out[full_name] = {
            "stars": e.get("stars"),
            "rating": e.get("rating"),
            "origin": e.get("origin"),
            "destination": e.get("destination"),
            "overallRank": e.get("_overall_rank"),
            "positionRank": e.get("_position_rank"),
        }
    return out
