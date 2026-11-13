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
for g in picks["games"]:
    if g["line_status"] != "posted" or ts(g["date"]) <= snap:
        continue
    key = str(g["gameId"])
    prev = E.get(key)
    if prev and prev.get("result"):
        continue
    E[key] = {k: g[k] for k in ("gameId", "date", "home", "away", "neutral", "pick", "pick_line", "spread_home",
                                 "book", "edge", "tier", "tempo_flag")}
    E[key]["locked_at"] = picks["generated"]
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
    graded += 1

ledger["updated"] = datetime.now(timezone.utc).isoformat()
json.dump(ledger, open(led_p, "w"), indent=1)
done = [e for e in E.values() if e.get("result") and e["tier"] != "lean"]
w = sum(e["result"] == "W" for e in done); l = sum(e["result"] == "L" for e in done)
print(f"ledger: +{added} new, {updated} re-snapshotted, {graded} graded; plays record {w}-{l} "
      f"({len(E)} entries total)")
