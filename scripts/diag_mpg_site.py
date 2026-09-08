import requests, json
output = []
for week in [1, 2]:
    try:
        resp = requests.get(f"https://mpg000f.github.io/cbb_power_rating/data/cfb/weekly/2026/week_{week:02d}.json", timeout=20)
        output.append(f"week_{week:02d}.json: status={resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get("ratings", [])
            output.append(f"  {len(rows)} rows, keys: {list(rows[0].keys()) if rows else 'none'}")
            osu = next((r for r in rows if r.get('team')=='Ohio State'), None)
            output.append(f"  Ohio State: {json.dumps(osu)}")
    except Exception as e:
        output.append(f"week_{week:02d}.json: ERROR {e}")

with open('../mpg_weekly_diag.txt', 'w') as f:
    f.write("\n".join(output))
