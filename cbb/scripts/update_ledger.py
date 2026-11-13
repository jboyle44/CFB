"""Pick ledger: lock and grade picks.

Lock rule: a pick is recorded only when its line is POSTED by a book, and it is
re-snapshotted on every refresh until tip-off. Once a game starts, its entry is
frozen: it is graded at the last line shown on the board before tip.
Projected-line picks are never graded.

Usage: python update_ledger.py [picks.json] [live_raw.json] [ledger.json]
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

picks_p = Path(sys.argv[1] if len(sys.argv) > 1 else "cbb/live/picks.json")
raw_p = Path(sys.argv[2] if len(sys.argv) > 2 else "cbb/live/live_raw.json")
led_p = Path(sys.argv[3] if len(sys.argv) > 3 else "cbb/live/ledger.json")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


picks = json.load(open(picks_p))
raw = json.load(open(raw_p))
ledger = json.load(open(led_p)) if led_p.exists() else {"entries": {}}
E = ledger["entries"]
snap = ts(picks["generated"])

added = updated = 0
import os
BACKFILL = os.environ.get("BACKFILL") == "1"
now = datetime.now(timezone.utc)
for g in picks["games"]:
    if g["line_status"] != "posted" or ts(g["date"]) <= snap:
        continue
    if not BACKFILL and ts(g["date"]) <= now:
        continue   # game already started by the real clock: never lock after tip
    key = str(g["gameId"])
    prev = E.get(key)
    if prev and prev.get("result"):
        continue
    new = {k: g[k] for k in ("gameId", "date", "home", "away", "neutral", "pick", "pick_line", "spread_home",
                              "book", "edge", "tier", "tempo_flag")}
    new["stake"] = g.get("stake", 2 if g["tier"] == "strong" else 1 if g["tier"] == "play" else 0)
    new["locked_at"] = picks["generated"]
    new["recorded_at"] = prev.get("recorded_at", now.isoformat()) if prev else now.isoformat()
    # line tracking: first line/edge the pick was made at (reset if the model flips sides), plus every change
    if prev and prev.get("pick") == g["pick"] and "first_spread_home" in prev:
        for k in ("first_spread_home", "first_edge", "first_at", "first_pick_line", "line_history"):
            new[k] = prev[k]
    else:
        new.update({"first_spread_home": g["spread_home"], "first_edge": g["edge"], "first_at": picks["generated"],
                    "first_pick_line": g["pick_line"], "line_history": []})
    hist = new["line_history"]
    if not hist or hist[-1]["spread_home"] != g["spread_home"]:
        hist.append({"at": picks["generated"], "spread_home": g["spread_home"], "edge": g["edge"]})
    E[key] = new
    added += prev is None
    updated += prev is not None

# grade from box scores
pts = {}
for r in raw["team_box"]:
    p = ((r.get("teamStats") or {}).get("points") or {}).get("total")
    if p is not None:
        pts[(r["gameId"], r["team"])] = p
graded = 0
for key, e in E.items():
    if e.get("result"):
        continue
    hs, as_ = pts.get((e["gameId"], e["home"])), pts.get((e["gameId"], e["away"]))
    if hs is None or as_ is None:
        continue
    cover = (hs - as_) + e["spread_home"]
    if e["pick"] == e["away"]:
        cover = -cover
    e.update({"home_score": hs, "away_score": as_, "margin_vs_line": cover,
              "result": "W" if cover > 0 else "L" if cover < 0 else "P"})
    st = e.get("stake", 2 if e["tier"] == "strong" else 1 if e["tier"] == "play" else 0)
    e["units"] = round(st * 100 / 110, 2) if e["result"] == "W" else -st if e["result"] == "L" else 0.0
    graded += 1

ledger["updated"] = datetime.now(timezone.utc).isoformat()
json.dump(ledger, open(led_p, "w"), indent=1)
done = [e for e in E.values() if e.get("result") and e["tier"] != "lean"]
w = sum(e["result"] == "W" for e in done); l = sum(e["result"] == "L" for e in done)
print(f"ledger: +{added} new, {updated} re-snapshotted, {graded} graded; plays record {w}-{l} "
      f"({len(E)} entries total)")
