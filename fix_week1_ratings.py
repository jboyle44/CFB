"""One-time correction: rebuild ratings_history.json's Week 1 entry using
MPG's own delta field to compute true pre-game ratings (rating - delta),
rather than the post-game state it was accidentally captured with."""
import requests, json, datetime

resp = requests.get("https://mpg000f.github.io/cbb_power_rating/data/cfb/weekly/2026/week_01.json", timeout=20)
data = resp.json()
rows = data.get("ratings", [])

corrected = []
for r in rows:
    delta = r.get("delta")
    rating = r.get("rating")
    if delta is None or rating is None:
        continue
    pre_game_rating = round(rating - delta, 1)
    corrected.append({
        "team": r.get("team"),
        "rating": pre_game_rating,
        "adjO": r.get("adjO"),  # not delta-corrected -- MPG doesn't expose a
        "adjD": r.get("adjD"),  # per-metric delta, only for overall rating
        "record": "0-0",  # true pre-game state, week 1 specifically
        "games": 0,
    })

corrected.sort(key=lambda t: -t["rating"])
for i, t in enumerate(corrected):
    t["rank"] = i + 1

with open("ratings_history.json") as f:
    history = json.load(f)

for entry in history:
    if entry.get("season") == 2026 and entry.get("week") == 1:
        entry["teams"] = corrected
        entry["source"] = "weekly snapshot (week 1), reconstructed pre-game via MPG's delta field"
        entry["capturedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

with open("ratings_history.json", "w") as f:
    json.dump(history, f, separators=(",", ":"))

print(f"Corrected {len(corrected)} teams for Week 1")
osu = next((t for t in corrected if t["team"] == "Ohio State"), None)
print(f"Ohio State check: {osu}")
