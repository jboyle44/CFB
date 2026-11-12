"""Backfill CBB team box scores and betting lines from the CBBD API.

Shares the CFBD quota pool, so this script enforces a hard call ceiling,
skips files already fetched, and splits date windows only when a response
looks truncated. Output: cbb/raw/{team_box,lines}_{season}.json.gz
"""
import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://api.collegebasketballdata.com"
KEY = os.environ["CFBD_API_KEY"]
MAX_CALLS = int(os.environ.get("MAX_CALLS", "250"))
SEASONS = [int(s) for s in os.environ.get("SEASONS", "2014-2026").split("-")]
SEASONS = list(range(SEASONS[0], SEASONS[-1] + 1))
TRUNC = int(os.environ.get("TRUNC_THRESHOLD", "3000"))
OUT = "cbb/raw"
os.makedirs(OUT, exist_ok=True)

calls = 0
log = open(os.path.join(OUT, "cbbd_fetch_log.txt"), "a")


def say(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()


def get(path, params):
    global calls
    if calls >= MAX_CALLS:
        raise RuntimeError(f"call ceiling {MAX_CALLS} reached")
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json"})
    calls += 1
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    say(f"call {calls}: {path} {params} -> {len(data)} rows")
    time.sleep(0.5)
    return data


def fetch_window(path, season, start, end):
    """Fetch [start, end]; split in half if the response looks truncated."""
    rows = get(path, {"season": season, "startDateRange": start.isoformat(), "endDateRange": end.isoformat()})
    if len(rows) >= TRUNC and (end - start).days >= 2:
        mid = start + (end - start) / 2
        return fetch_window(path, season, start, mid) + fetch_window(path, season, mid + dt.timedelta(days=1), end)
    if len(rows) >= TRUNC:
        say(f"WARNING still truncated at 1-day window {start}..{end}")
    return rows


def month_windows(season):
    edges = [dt.date(season - 1, 11, 1), dt.date(season - 1, 12, 1), dt.date(season, 1, 1),
             dt.date(season, 2, 1), dt.date(season, 3, 1), dt.date(season, 4, 15)]
    return [(edges[i], edges[i + 1] - dt.timedelta(days=1)) for i in range(len(edges) - 1)]


def dedupe(rows, keyf):
    seen, out = set(), []
    for r in rows:
        k = keyf(r)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


JOBS = [
    ("team_box", "/games/teams", lambda r: (r.get("gameId"), r.get("teamId"))),
    ("lines", "/lines", lambda r: r.get("gameId")),
]

try:
    for season in SEASONS:
        for name, path, keyf in JOBS:
            fp = os.path.join(OUT, f"{name}_{season}.json.gz")
            if os.path.exists(fp):
                say(f"SKIP {fp} exists")
                continue
            rows = []
            for a, b in month_windows(season):
                rows += fetch_window(path, season, a, b)
            rows = dedupe(rows, keyf)
            with gzip.open(fp, "wt") as f:
                json.dump(rows, f)
            say(f"OK {name} {season}: {len(rows)} rows")
except Exception as e:  # keep whatever finished; the commit step still runs
    say(f"STOPPED: {e}")
finally:
    say(f"total calls this run: {calls}")
    log.close()
