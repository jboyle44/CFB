"""Shot-location backfill from CBBD play-by-play (/plays/date, shooting plays only).
One call per UTC date. Aggregates to team-game shot counts by range so the repo stays small.
Output: cbb/raw/shots_{season}.json.gz  rows: gameId, teamId, oppId, date, {range: [att, made]}
"""
import datetime as dt, gzip, json, os, sys, time, urllib.parse, urllib.request
from collections import defaultdict
KEY = os.environ["CFBD_API_KEY"]
MAX_CALLS = int(os.environ.get("MAX_CALLS", "3000"))
SEASONS = [int(s) for s in os.environ.get("SEASONS", "2025-2025").split("-")]
SEASONS = list(range(SEASONS[0], SEASONS[-1] + 1))
PROBE_DATE = os.environ.get("PROBE_DATE")
OUT = "cbb/raw"; os.makedirs(OUT, exist_ok=True)
calls = 0
log = open(os.path.join(OUT, "shots_fetch_log.txt"), "a")
def say(m): print(m); log.write(m + "\n"); log.flush()
def get(date):
    global calls
    if calls >= MAX_CALLS: raise RuntimeError(f"call ceiling {MAX_CALLS} reached")
    url = "https://api.collegebasketballdata.com/plays/date?" + urllib.parse.urlencode({"date": date, "shootingPlaysOnly": "true"})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json"})
    calls += 1
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r: return json.loads(r.read())
        except Exception as e:
            if attempt == 2: raise
            time.sleep(5)
def aggregate(plays, agg):
    for p in plays:
        si = p.get("shotInfo") or {}
        rng = si.get("range")
        if not rng or p.get("teamId") is None: continue
        k = (p["gameId"], p["teamId"])
        a = agg.setdefault(k, {"gameId": p["gameId"], "teamId": p["teamId"], "oppId": p.get("opponentId"),
                               "date": p.get("gameStartDate"), "shots": defaultdict(lambda: [0, 0])})
        a["shots"][rng][0] += 1
        a["shots"][rng][1] += int(bool(si.get("made")))
if PROBE_DATE:
    plays = get(PROBE_DATE)
    say(f"probe {PROBE_DATE}: {len(plays)} plays, games {len({p['gameId'] for p in plays})}")
    from collections import Counter
    say("ranges: " + json.dumps(Counter((p.get('shotInfo') or {}).get('range') for p in plays)))
    say("play types: " + json.dumps(Counter(p.get('playType') for p in plays).most_common(12)))
    say("sample: " + json.dumps(plays[0])[:1500])
    sys.exit(0)
try:
    for season in SEASONS:
        fp = os.path.join(OUT, f"shots_{season}.json.gz")
        if os.path.exists(fp): say(f"SKIP {fp}"); continue
        agg = {}
        d = dt.date(season - 1, 11, 1)
        while d <= dt.date(season, 4, 15):
            plays = get(d.isoformat())
            aggregate(plays, agg)
            d += dt.timedelta(days=1)
        rows = [{**v, "shots": dict(v["shots"])} for v in agg.values()]
        with gzip.open(fp, "wt") as f: json.dump(rows, f)
        say(f"OK shots {season}: {len(rows)} team-games, calls so far {calls}")
except Exception as e:
    say(f"STOPPED: {e}")
finally:
    say(f"total calls this run: {calls}"); log.close()
