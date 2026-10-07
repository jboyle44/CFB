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
import json
import os
import re
import tempfile
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


# Every team in a depth chart run is built by its own Python process, so
# responses are cached on disk for the duration of the run. The transfer portal
# endpoint returns the whole country's portal for a season, so without this
# each of the 68 teams re-downloaded the same 6 seasons (408 calls per run for
# 6 unique responses). The workflow points CFBD_CACHE_DIR at the runner's temp
# directory, so the cache never outlives a single run.
CACHE_DIR = os.environ.get("CFBD_CACHE_DIR") or os.path.join(tempfile.gettempdir(), "cfbd_cache")
_UNAVAILABLE_FLAG = os.path.join(CACHE_DIR, "UNAVAILABLE")


class CFBDUnavailable(RuntimeError):
    """CFBD is out of quota, rejecting the key, or skipped for this run."""


def cfbd_available():
    """False once any process in this run has hit a quota/auth failure, or
    when CFBD_SKIP=1 is set to refresh depth charts without spending calls."""
    return os.environ.get("CFBD_SKIP") != "1" and not os.path.exists(_UNAVAILABLE_FLAG)


def _mark_unavailable(reason):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_UNAVAILABLE_FLAG, "w") as f:
        f.write(reason)
    print(f"  CFBD unavailable for the rest of this run: {reason}")


def _cached(name, fetch):
    """Return the cached JSON for `name`, or call fetch() and cache it."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, re.sub(r"[^A-Za-z0-9_.-]", "_", name) + ".json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    data = fetch()
    tmp = path + f".{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)
    return data


def _paced_get(url, headers, params, timeout=20, max_retries=3):
    # Circuit breaker: once the monthly quota is gone (or the key is
    # rejected), every later call in the run fails the same way. Without
    # this, each one sat through the full 429 backoff, which is how the
    # Oct 6 run stretched from ~30 minutes to 1h43m.
    if not cfbd_available():
        raise CFBDUnavailable("CFBD skipped or unavailable for this run")
    for attempt in range(max_retries):
        elapsed = time.time() - _last_request_time[0]
        if elapsed < _MIN_REQUEST_GAP_SECONDS:
            time.sleep(_MIN_REQUEST_GAP_SECONDS - elapsed)
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        _last_request_time[0] = time.time()
        if resp.status_code in (401, 403):
            _mark_unavailable(f"HTTP {resp.status_code} from {url}")
            raise CFBDUnavailable(f"HTTP {resp.status_code}")
        if resp.status_code == 429:
            backoff = 2 ** attempt * 2  # 2s, 4s, 8s
            print(f"  429 rate limited, backing off {backoff}s (attempt {attempt+1}/{max_retries})")
            time.sleep(backoff)
            continue
        return resp
    # Still 429 after backing off: the monthly quota is exhausted, not just
    # the per-minute limit.
    _mark_unavailable(f"HTTP 429 after {max_retries} attempts from {url}")
    raise CFBDUnavailable("HTTP 429 after retries")


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
    # One national pull per class year, filtered locally. The year-only query
    # returns the full high school class (~4,000 recruits, 1 call), and a
    # 2026-10-07 probe confirmed filtering it by committedTo returns exactly
    # the same players as team-filtered queries. With the run cache, every
    # team shares these pulls: ~9 calls per run instead of one per
    # (school, year) pair (~357).
    def fetch():
        resp = _paced_get(
            f"{BASE_URL}/recruiting/players",
            headers=_auth_headers(),
            params={"year": year},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    players = [r for r in _cached(f"recruiting_{year}", fetch)
               if r.get("committedTo") == team_display_name]
    by_full_name = {}
    by_last_name_candidates = {}
    for r in players:
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
    def fetch():
        resp = _paced_get(
            f"{BASE_URL}/player/portal",
            headers=_auth_headers(),
            params={"year": year},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    entries = _cached(f"portal_{year}", fetch)

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
