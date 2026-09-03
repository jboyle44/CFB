import json, os, requests

api_key = os.environ.get("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

result = {}
for yr in [2023, 2024, 2025, 2026]:
    resp = requests.get("https://api.collegefootballdata.com/player/portal",
        headers=headers, params={"year": yr}, timeout=20)
    if resp.status_code == 200:
        # broaden: any Evans transferring anywhere, not just to Indiana
        matches = [p for p in resp.json() if 'evans' in (p.get('lastName') or '').lower()
                   and p.get('position') in ('G', 'OL', 'T', 'C')]
        if matches:
            result[yr] = matches

with open('../evans_diag2.json', 'w') as f:
    json.dump(result, f, indent=2)
