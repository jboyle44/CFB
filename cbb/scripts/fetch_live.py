"""Fetch current-season CBB data for live picks: box scores to date, upcoming
schedule, CBBD lines, and the-odds-api current spreads. ~4 CBBD calls + 1 odds credit."""
import datetime as dt, json, os, urllib.parse, urllib.request
OUT = "cbb/live"; os.makedirs(OUT, exist_ok=True)
SEASON = int(os.environ.get("SEASON", "2027"))
today = dt.date.today()
ahead = today + dt.timedelta(days=int(os.environ.get("DAYS_AHEAD", "14")))
start = dt.date(SEASON - 1, 11, 1)

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()), dict(r.headers)

def cbbd(path, **p):
    data, _ = get(f"https://api.collegebasketballdata.com{path}?{urllib.parse.urlencode(p)}",
                  {"Authorization": f"Bearer {os.environ['CFBD_API_KEY']}", "Accept": "application/json"})
    print(path, p, len(data)); return data

out = {
    "fetched_at": dt.datetime.utcnow().isoformat() + "Z",
    "team_box": cbbd("/games/teams", season=SEASON, startDateRange=start.isoformat(), endDateRange=today.isoformat()),
    "schedule": cbbd("/games", season=SEASON, startDateRange=today.isoformat(), endDateRange=ahead.isoformat()),
    "lines": cbbd("/lines", season=SEASON, startDateRange=today.isoformat(), endDateRange=ahead.isoformat()),
}
try:
    odds, hdr = get("https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds?" + urllib.parse.urlencode(
        {"apiKey": os.environ["ODDS_API_KEY"], "regions": "us", "markets": "spreads", "oddsFormat": "american"}))
    out["odds"] = odds
    out["odds_remaining"] = hdr.get("x-requests-remaining") or hdr.get("X-Requests-Remaining")
    print("odds events", len(odds), "remaining", out["odds_remaining"])
except Exception as e:
    out["odds"], out["odds_error"] = [], str(e); print("odds error", e)
json.dump(out, open(f"{OUT}/live_raw.json", "w"))
