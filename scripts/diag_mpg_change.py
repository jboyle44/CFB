import requests, json
resp = requests.get("https://mpg000f.github.io/cbb_power_rating/data/cfb/ratings_2026.json", timeout=20)
data = resp.json()
rows = data.get("ratings", [])
with open('../mpg_change_diag.txt', 'w') as f:
    f.write(f"total rows: {len(rows)}\n")
    f.write(f"keys in first row: {list(rows[0].keys()) if rows else 'none'}\n\n")
    osu = next((r for r in rows if r.get('team')=='Ohio State'), None)
    f.write(f"Ohio State full row: {json.dumps(osu, indent=2)}\n")
