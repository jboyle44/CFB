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
import time
import requests

BASE_URL = "https://api.collegefootballdata.com"

# Minimum gap enforced between consecutive CFBD requests, to stay under
# CFBD's short-term (per-minute) rate limit -- separate from the monthly
# quota. Confirmed real case: a rollout making dozens of back-to-back
# requests with no pacing tripped 429s well before the monthly quota was
# anywhere close to exhausted.
_MIN_REQUEST_GAP_SECONDS = 0.6
_last_request_time = [0.0]


def _paced_get(url, headers, params, timeout=20, max_retries=3):
    for attempt in range(max_retries):
        elapsed = time.time() - _last_request_time[0]
        if elapsed < _MIN_REQUEST_GAP_SECONDS:
            time.sleep(_MIN_REQUEST_GAP_SECONDS - elapsed)
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        _last_request_time[0] = time.time()
        if resp.status_code == 429:
            backoff = 2 ** attempt * 2  # 2s, 4s, 8s
            print(f"  429 rate limited, backing off {backoff}s (attempt {attempt+1}/{max_retries})")
            time.sleep(backoff)
            continue
        return resp
    resp.raise_for_status()  # exhausted retries, raise the last 429
    return resp


def _auth_headers():
    api_key = os.environ.get("CFBD_API_KEY")
    if not api_key:
        raise RuntimeError("CFBD_API_KEY environment variable not set")
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


def get_recruiting_players(team_display_name, year):
    """
    Returns (by_full_name, by_last_name) where:
      by_full_name: {full_name_lower: {"stars","rating","ranking","position"}}
      by_last_name: {last_name_lower: {...}} -- ONLY included when exactly one
        player on this team/year has that last name. This exists because
        recruiting databases sometimes use a player's legal first name (e.g.
        "Anthony Reddick") while the roster/depth chart uses a family
        nickname (e.g. "Trey Reddick") for the same person -- when there's
        no ambiguity, matching on last name alone safely recovers these.
    """
    resp = _paced_get(
        f"{BASE_URL}/recruiting/players",
        headers=_auth_headers(),
        params={"year": year, "team": team_display_name},
        timeout=20,
    )
    resp.raise_for_status()
    by_full_name = {}
    by_last_name_candidates = {}
    for r in resp.json():
        name = (r.get("name") or "").strip().lower()
        if not name:
            continue
        info = {
            "stars": r.get("stars"),
            "rating": r.get("rating"),
            "ranking": r.get("ranking"),
            "position": r.get("position"),
        }
        by_full_name[name] = info
        last = name.split()[-1] if name.split() else None
        if last:
            by_last_name_candidates.setdefault(last, []).append(info)

    by_last_name = {
        last: candidates[0] for last, candidates in by_last_name_candidates.items()
        if len(candidates) == 1
    }
    return by_full_name, by_last_name


def get_transfer_portal(year):
    """
    Returns a list of every transfer portal entry for a season, each with
    first_name/last_name/position/origin/destination/rating/stars. Ranking
    isn't provided directly -- sort by rating descending and enumerate to get
    an equivalent "#N transfer overall" and "#N at position" the same way
    247Sports displays it.
    """
    resp = _paced_get(
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
        full_name = f"{e.get('firstName','')} {e.get('lastName','')}".strip().lower()
        if not full_name:
            continue
        out[full_name] = {
            "stars": e.get("stars"),
            "rating": e.get("rating"),
            "origin": e.get("origin"),
            "destination": e.get("destination"),
            "transferDate": e.get("transferDate"),
            "overallRank": e.get("_overall_rank"),
            "positionRank": e.get("_position_rank"),
            "position": e.get("position"),
        }
    return out
